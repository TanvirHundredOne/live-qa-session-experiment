#!/usr/bin/env python3
"""
Stanford CS playlist Q&A agent (Ollama + yt-dlp).

For every Stanford CS playlist:
  1. Ask a local LLM (Gemma via Ollama) whether each video's description /
     chapters indicate a Q&A section inside the lecture.
  2. If at least one video has Q&A -> download the whole playlist.
  3. Write <playlist>/qa_lectures.csv listing the lectures that have Q&A.
Then move on to the next playlist.

Setup:
  pip install yt-dlp ollama
  ollama pull <your gemma tag>     # check `ollama list` for the exact tag
  ffmpeg must be installed (yt-dlp merges video+audio with it)

Usage:
  python stanford_qa_agent.py --model gemma4:e4b
  python stanford_qa_agent.py --dry-run                 # classify only, no downloads
  python stanford_qa_agent.py --playlist-url <URL> ...  # skip discovery
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import ollama
from yt_dlp import YoutubeDL

CHANNEL_PLAYLISTS = "https://www.youtube.com/@stanfordonline/playlists"
CS_TITLE_RE = re.compile(r"\bCS\s?-?\d{2,3}[A-Z]?\b", re.I)
QA_HINT_RE = re.compile(r"\b(q\s*&\s*a|q\s*and\s*a|questions?|ask me anything|audience)\b", re.I)
LECTURE_NUM_RE = re.compile(r"\b(?:lecture|lec|lesson)\s*[#:.\-]?\s*(\d+)\b", re.I)

SCHEMA = {
    "type": "object",
    "properties": {
        "has_qa": {"type": "boolean"},
        "evidence": {"type": "string"},
    },
    "required": ["has_qa", "evidence"],
}

SYSTEM_PROMPT = (
    "You inspect YouTube lecture metadata. Decide whether the VIDEO ITSELF "
    "contains a Q&A (questions and answers / audience questions) section.\n"
    "Answer has_qa=true ONLY if the description or chapter list explicitly shows "
    "a Q&A segment in this video (e.g. a chapter or timestamp named 'Q&A', "
    "'Questions', 'Audience questions', or text saying the lecture ends with Q&A).\n"
    "Answer has_qa=false if Q&A is only mentioned generically (e.g. 'post questions "
    "on Ed', 'office hours', course logistics) or if there is no sign of it.\n"
    "'evidence' must be a short quote (max 15 words) from the metadata, or 'none'."
)


# --------------------------------------------------------------------------- #
# YouTube helpers
# --------------------------------------------------------------------------- #
def discover_playlists():
    opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(CHANNEL_PLAYLISTS, download=False)
    out = []
    for e in info.get("entries") or []:
        title = e.get("title") or ""
        if e.get("url") and CS_TITLE_RE.search(title):
            out.append({"title": title, "url": e["url"]})
    return out


def list_videos(playlist_url):
    opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
    videos = []
    for i, e in enumerate(info.get("entries") or [], start=1):
        if e and e.get("id"):
            videos.append({
                "index": i,
                "id": e["id"],
                "title": e.get("title") or "",
                "url": f"https://www.youtube.com/watch?v={e['id']}",
            })
    return info.get("title") or "playlist", videos


def fetch_metadata(video_url):
    opts = {"quiet": True, "skip_download": True, "no_warnings": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
    chapters = [
        f"{int(c.get('start_time', 0))}s: {c.get('title', '')}"
        for c in (info.get("chapters") or [])
    ]
    return info.get("description") or "", chapters


# --------------------------------------------------------------------------- #
# LLM step
# --------------------------------------------------------------------------- #
def classify(model, title, description, chapters, max_chars=6000):
    hint_lines = [
        ln.strip() for ln in (description.splitlines() + chapters) if QA_HINT_RE.search(ln)
    ]
    user = (
        f"TITLE: {title}\n\n"
        f"CHAPTERS:\n{chr(10).join(chapters) or '(none)'}\n\n"
        f"LINES MATCHING Q&A KEYWORDS (regex hint, may be false positives):\n"
        f"{chr(10).join(hint_lines[:15]) or '(none)'}\n\n"
        f"DESCRIPTION:\n{description[:max_chars]}"
    )
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        format=SCHEMA,
        options={"temperature": 0},
    )
    try:
        data = json.loads(resp["message"]["content"])
        return bool(data.get("has_qa")), str(data.get("evidence", ""))[:200]
    except (json.JSONDecodeError, KeyError, TypeError):
        return False, "parse_error"


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def lecture_number(video):
    m = LECTURE_NUM_RE.search(video["title"])
    return int(m.group(1)) if m else video["index"]


def download_playlist(url, folder, max_height):
    folder.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(folder / "%(playlist_index)03d - %(title)s.%(ext)s"),
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]",
        "merge_output_format": "mp4",
        "download_archive": str(folder / ".downloaded.txt"),  # resumable
        "ignoreerrors": True,
        "writedescription": False,
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["lecture_number", "playlist_index", "title", "url", "evidence"],
        )
        w.writeheader()
        w.writerows(rows)


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip()[:120]


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #
def process_playlist(pl, args, cache, cache_path):
    print(f"\n=== {pl['title']} ===")
    try:
        title, videos = list_videos(pl["url"])
    except Exception as e:
        print(f"  ! could not list playlist: {e}")
        return

    qa_rows = []
    for v in videos:
        if v["id"] in cache:
            has_qa, evidence = cache[v["id"]]["has_qa"], cache[v["id"]]["evidence"]
        else:
            try:
                desc, chapters = fetch_metadata(v["url"])
                has_qa, evidence = classify(args.model, v["title"], desc, chapters)
            except Exception as e:
                print(f"  ! {v['title']}: {e}")
                continue
            cache[v["id"]] = {"has_qa": has_qa, "evidence": evidence}
            cache_path.write_text(json.dumps(cache, indent=1))
            time.sleep(args.sleep)
        print(f"  [{'Q&A' if has_qa else '   '}] {v['index']:>3}. {v['title']}")
        if has_qa:
            qa_rows.append({
                "lecture_number": lecture_number(v),
                "playlist_index": v["index"],
                "title": v["title"],
                "url": v["url"],
                "evidence": evidence,
            })

    if not qa_rows:
        print("  -> no Q&A found, skipping playlist")
        return

    folder = Path(args.out) / safe_name(title)
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "qa_lectures.csv", qa_rows)
    print(f"  -> {len(qa_rows)} lectures with Q&A; CSV written to {folder}")

    if args.dry_run:
        print("  -> dry run: not downloading")
    else:
        download_playlist(pl["url"], folder, args.max_height)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="gemma4:e4b", help="Ollama model tag (see `ollama list`)")
    p.add_argument("--out", default="stanford_playlists")
    p.add_argument("--max-height", type=int, default=720, help="max video height to download")
    p.add_argument("--playlist-url", action="append", help="explicit playlist URL(s); skips discovery")
    p.add_argument("--dry-run", action="store_true", help="classify + CSV only, no downloads")
    p.add_argument("--sleep", type=float, default=1.0, help="delay between metadata requests")
    args = p.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.out) / "classification_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    if args.playlist_url:
        playlists = [{"title": u, "url": u} for u in args.playlist_url]
    else:
        print("Discovering Stanford CS playlists...")
        playlists = discover_playlists()
    print(f"{len(playlists)} playlists to process")

    for pl in playlists:
        process_playlist(pl, args, cache, cache_path)


if __name__ == "__main__":
    sys.exit(main())