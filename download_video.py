import os
import yt_dlp

def download(url: str, out_dir: str = "downloads") -> None:
    os.makedirs(out_dir, exist_ok=True)

    common = {
        "format": "bv*+ba/b",               # best video + best audio, else best single file
        "merge_output_format": "mp4",
        "ignoreerrors": True,               # skip unavailable/private videos
        "retries": 10,
        "fragment_retries": 10,
        "windowsfilenames": True,           # safe filenames on any OS
        "download_archive": os.path.join(out_dir, "archive.txt"),  # resume / skip done
    }

    # 1) Probe the URL without downloading
    with yt_dlp.YoutubeDL({**common, "quiet": True, "extract_flat": "in_playlist"}) as ydl:
        info = ydl.extract_info(url, download=False)

    # 2) Pick the output template
    if info and info.get("_type") == "playlist":
        tmpl = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
        print(f"Playlist: {info.get('title')} ({len(info.get('entries', []))} items)")
    else:
        tmpl = "%(title)s [%(id)s].%(ext)s"
        print(f"Single video: {info.get('title') if info else url}")

    # 3) Download
    opts = {**common, "outtmpl": os.path.join(out_dir, tmpl)}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    print("Done!")

if __name__ == "__main__":
    # download("https://m.youtube.com/playlist?list=PLoROMvodv4rOaMFbaqxPDoLWjDaRAdP9D")
    download("https://m.youtube.com/playlist?list=PLoROMvodv4rOSOPzutgyCTapiGlY2Nd8u")
    # download("https://www.youtube.com/playlist?list=PLSQl0a2vh4HC65RNqfPbFw_LOx9h0w1ml", out_dir="khan_academy")
    
    # download("https://youtu.be/oGk1v1jQITw?si=4aPc3VueBxxUH3p8")
    # download("https://www.youtube.com/live/KEJni9avikM?si=cH__K30LTs1MmYM2")
    # download("https://youtu.be/mVfPGu8rrXM?si=wMPQ_yDsnKWrrtMw")