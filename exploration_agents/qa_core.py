#!/usr/bin/env python3
"""
Shared engine for the per-source Q&A agents (Ollama + yt-dlp).

Pipeline per playlist (same rules as the Stanford/MIT agents):
  1. For each video, decide with a local LLM whether it contains a Q&A section.
       a. description + chapters check
       b. (optional) transcript fallback: find the densest cluster of
          "any questions / great question / the question is ..." cues in the
          auto-captions, then let the LLM confirm that excerpt.
  2. If at least one video has Q&A -> download the whole playlist.
  3. Write qa_lectures.csv (lecture_number, playlist_index, title, url,
     method, qa_start, evidence) next to the downloaded videos.
Then continue with the next playlist.

Requires: pip install yt-dlp ollama   (+ ffmpeg for downloads)
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import ollama
from yt_dlp import YoutubeDL

YDL_BASE = {}  # shared yt-dlp options (cookies, throttling); filled in by run()


def new_ydl(opts):
    return YoutubeDL({**YDL_BASE, **opts})

QA_HINT_RE = re.compile(r"\b(q\s*&\s*a|q\s*and\s*a|questions?|ask me anything|audience)\b", re.I)
Q_CUES = re.compile(
    r"(any questions|great question|good question|thank you for (?:the|your) question|"
    r"next question|question from|the question is|repeat the question|question\?)",
    re.I,
)
LECTURE_NUM_RES = [
    re.compile(r"\b(?:lecture|lec|lesson|session|week)\s*[#:.\-]?\s*(\d+)\b", re.I),
    re.compile(r"^\s*(\d+)\s*[.:\-|]"),
]
YT_LIST_RE = re.compile(r"youtube\.com/(?:playlist\?|embed/videoseries\?|watch\?[^\"'\s<>]*?)list=([\w-]+)")
EN_STOP = set("the of and to in is that for with on as are this we be by it from at or an can will you your".split())


def is_english(text, min_words=25):
    """Cheap stopword-ratio check; short/empty samples are assumed English."""
    text = re.sub(r"https?://\S+", " ", text)
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < min_words:
        return True
    return sum(w in EN_STOP for w in words) / len(words) > 0.12

SCHEMA = {
    "type": "object",
    "properties": {"has_qa": {"type": "boolean"}, "evidence": {"type": "string"}},
    "required": ["has_qa", "evidence"],
}
DESC_PROMPT = (
    "You inspect YouTube video metadata. Decide whether the VIDEO ITSELF contains a "
    "Q&A section (audience questions answered by the speaker).\n"
    "has_qa=true ONLY if the description or chapters explicitly show a Q&A segment in "
    "this video (chapter/timestamp named 'Q&A', 'Questions', 'Audience questions', or "
    "text saying the session includes/ends with Q&A).\n"
    "has_qa=false if Q&A is only mentioned generically (forums, office hours, logistics, "
    "'submit questions') or there is no sign of it.\n"
    "'evidence': short quote (max 15 words) from the metadata, or 'none'."
)
TRANSCRIPT_PROMPT = (
    "You read an excerpt of an auto-generated transcript of a lecture or talk. Decide "
    "whether it contains a live Q&A exchange: someone other than the lecturer (audience "
    "member, host, moderator) asks questions and the speaker answers them.\n"
    "Rhetorical questions the lecturer asks while teaching do NOT count.\n"
    "'evidence': short quote (max 15 words) showing the exchange, or 'none'."
)


@dataclass
class Source:
    name: str
    out_dir: str
    playlists: list = field(default_factory=list)       # explicit playlist URLs
    playlist_pages: list = field(default_factory=list)  # web pages scanned for YouTube playlist links
    channel_playlists_url: str = ""                      # e.g. https://www.youtube.com/@x/playlists
    title_regex: str = ""                                # keep only channel playlists matching this
    transcript_mode: str = "fallback"                    # off | fallback | only
    model: str = "gemma4:e4b"
    english_only: bool = True                            # skip non-English videos


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip()[:120]


def hms(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def lecture_number(video):
    for rx in LECTURE_NUM_RES:
        m = rx.search(video["title"])
        if m:
            return int(m.group(1))
    return video["index"]


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def discover(src, cli_urls):
    if cli_urls:
        return [{"title": u, "url": u} for u in cli_urls]
    found = {u: {"title": u, "url": u} for u in src.playlists}

    for page in src.playlist_pages:
        try:
            html = http_get(page)
        except Exception as e:
            print(f"  ! could not read {page}: {e}")
            continue
        for pid in dict.fromkeys(YT_LIST_RE.findall(html)):
            url = f"https://www.youtube.com/playlist?list={pid}"
            found.setdefault(url, {"title": url, "url": url})

    if src.channel_playlists_url:
        try:
            opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
            with new_ydl(opts) as ydl:
                info = ydl.extract_info(src.channel_playlists_url, download=False)
            rx = re.compile(src.title_regex, re.I) if src.title_regex else None
            for e in info.get("entries") or []:
                title = e.get("title") or ""
                if e.get("url") and (rx is None or rx.search(title)):
                    found.setdefault(e["url"], {"title": title, "url": e["url"]})
        except Exception as e:
            print(f"  ! channel discovery failed ({src.channel_playlists_url}): {e}")
    return list(found.values())


def list_videos(playlist_url):
    opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
    with new_ydl(opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
    videos = []
    for i, e in enumerate(info.get("entries") or [], start=1):
        if e and e.get("id"):
            videos.append({
                "index": i, "id": e["id"], "title": e.get("title") or "",
                "url": f"https://www.youtube.com/watch?v={e['id']}",
            })
    return info.get("title") or "playlist", videos


# --------------------------------------------------------------------------- #
# Evidence gathering
# --------------------------------------------------------------------------- #
def fetch_info(url):
    with new_ydl({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(url, download=False)


def get_transcript(info):
    """Return [(seconds, text)] from English manual or auto captions (json3)."""
    for pool in ("subtitles", "automatic_captions"):
        for lang, fmts in (info.get(pool) or {}).items():
            if not lang.startswith("en"):
                continue
            for f in fmts:
                if f.get("ext") == "json3" and "tlang=" not in f.get("url", ""):
                    data = json.loads(http_get(f["url"]))
                    lines = []
                    for ev in data.get("events", []):
                        txt = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
                        txt = txt.replace("\n", " ").strip()
                        if txt:
                            lines.append((ev.get("tStartMs", 0) / 1000, txt))
                    return lines
    return []


def find_qa_window(lines, window=300, min_hits=4, max_chars=4500):
    """Densest cluster of Q&A cue phrases -> (start_sec, excerpt) or None."""
    hits = [t for t, txt in lines if Q_CUES.search(txt)]
    best_count, best_start, j = 0, None, 0
    for i, t in enumerate(hits):
        while hits[j] < t - window:
            j += 1
        if i - j + 1 > best_count:
            best_count, best_start = i - j + 1, hits[j]
    if best_count < min_hits:
        return None
    lo, hi = best_start - 30, best_start + window + 30
    text = " ".join(txt for t, txt in lines if lo <= t <= hi)
    return best_start, text[:max_chars]


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
def ask(model, system, user):
    resp = ollama.chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=SCHEMA,
        options={"temperature": 0},
    )
    try:
        d = json.loads(resp["message"]["content"])
        return bool(d.get("has_qa")), str(d.get("evidence", ""))[:200]
    except (json.JSONDecodeError, KeyError, TypeError):
        return False, "parse_error"


def judge(src, mode, video):
    info = fetch_info(video["url"])
    evidence = "none"
    desc = info.get("description") or ""
    if src.english_only and not is_english(f"{video['title']} {desc[:2000]}"):
        return {"has_qa": False, "evidence": "non-English video skipped", "method": "non_english", "qa_start": ""}

    if mode != "only":
        chapters = [f"{int(c.get('start_time', 0))}s: {c.get('title', '')}"
                    for c in (info.get("chapters") or [])]
        hints = [ln.strip() for ln in desc.splitlines() + chapters if QA_HINT_RE.search(ln)]
        user = (
            f"TITLE: {video['title']}\n\nCHAPTERS:\n{chr(10).join(chapters) or '(none)'}\n\n"
            f"LINES MATCHING Q&A KEYWORDS (hint, may be false positives):\n"
            f"{chr(10).join(hints[:15]) or '(none)'}\n\nDESCRIPTION:\n{desc[:6000]}"
        )
        has, evidence = ask(src.model, DESC_PROMPT, user)
        if has:
            return {"has_qa": True, "evidence": evidence, "method": "description", "qa_start": ""}

    if mode in ("fallback", "only"):
        try:
            win = find_qa_window(get_transcript(info))
        except Exception as e:
            win, evidence = None, f"transcript_error: {e}"[:200]
        if win:
            start, excerpt = win
            has, ev = ask(src.model, TRANSCRIPT_PROMPT, f"TITLE: {video['title']}\n\nEXCERPT:\n{excerpt}")
            if has:
                return {"has_qa": True, "evidence": ev, "method": "transcript", "qa_start": hms(start)}
    return {"has_qa": False, "evidence": evidence, "method": mode, "qa_start": ""}


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def download_playlist(url, folder, max_height):
    folder.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(folder / "%(playlist_index)03d - %(title)s.%(ext)s"),
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]",
        "merge_output_format": "mp4",
        "download_archive": str(folder / ".downloaded.txt"),
        "ignoreerrors": True,
    }
    with new_ydl(opts) as ydl:
        ydl.download([url])


def write_csv(path, rows):
    cols = ["lecture_number", "playlist_index", "title", "url", "method", "qa_start", "evidence"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def process_playlist(src, args, mode, pl, cache, cache_path):
    print(f"\n=== {pl['title']} ===")
    try:
        title, videos = list_videos(pl["url"])
    except Exception as e:
        print(f"  ! could not list playlist: {e}")
        return

    rows = []
    for v in videos:
        key = f"{mode}:{v['id']}"
        if key in cache:
            r = cache[key]
        else:
            try:
                r = judge(src, mode, v)
            except Exception as e:
                print(f"  ! {v['title']}: {e}")
                continue
            cache[key] = r
            cache_path.write_text(json.dumps(cache, indent=1))
            time.sleep(args.sleep)
        print(f"  [{'Q&A' if r['has_qa'] else '   '}] {v['index']:>3}. {v['title']}")
        if r["has_qa"]:
            rows.append({"lecture_number": lecture_number(v), "playlist_index": v["index"],
                         "title": v["title"], "url": v["url"], **{k: r[k] for k in ("method", "qa_start", "evidence")}})

    if not rows:
        print("  -> no Q&A found, skipping playlist")
        return
    folder = Path(args.out) / safe_name(title)
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "qa_lectures.csv", rows)
    print(f"  -> {len(rows)} videos with Q&A; CSV written to {folder}")
    if args.dry_run:
        print("  -> dry run: not downloading")
    else:
        download_playlist(pl["url"], folder, args.max_height)


def run(src):
    p = argparse.ArgumentParser(description=f"Q&A agent: {src.name}")
    p.add_argument("--model", default=src.model, help="Ollama model tag (see `ollama list`)")
    p.add_argument("--out", default=src.out_dir)
    p.add_argument("--max-height", type=int, default=720)
    p.add_argument("--playlist-url", action="append", help="explicit playlist URL(s); overrides discovery")
    p.add_argument("--transcript", choices=["off", "fallback", "only"], default=src.transcript_mode,
                   help="off: description only | fallback: description then transcript | only: transcript only")
    p.add_argument("--dry-run", action="store_true", help="classify + CSV only, no downloads")
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="use your logged-in browser session, e.g. brave, chrome, firefox, edge")
    p.add_argument("--browser-profile", help="browser profile name, e.g. \"Default\" or \"Profile 1\"")
    p.add_argument("--cookies", metavar="FILE", help="Netscape cookies.txt exported from your browser")
    p.add_argument("--download-sleep", type=float, default=3.0,
                   help="seconds to wait between video downloads (be gentle with a logged-in account)")
    p.add_argument("--allow-non-english", action="store_true", help="do not skip non-English videos")
    args = p.parse_args()
    src.model = args.model
    if args.cookies:
        YDL_BASE["cookiefile"] = args.cookies
    elif args.cookies_from_browser:
        YDL_BASE["cookiesfrombrowser"] = (args.cookies_from_browser, args.browser_profile, None, None)
    if args.download_sleep > 0:
        YDL_BASE["sleep_interval"] = args.download_sleep
        YDL_BASE["max_sleep_interval"] = args.download_sleep * 2.5
    src.english_only = src.english_only and not args.allow_non_english

    Path(args.out).mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.out) / "classification_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    print(f"[{src.name}] discovering playlists...")
    playlists = discover(src, args.playlist_url)
    print(f"{len(playlists)} playlists to process (transcript mode: {args.transcript})")
    for pl in playlists:
        process_playlist(src, args, args.transcript, pl, cache, cache_path)


if __name__ == "__main__":
    sys.exit("qa_core is a library; run one of the *_agent.py files.")