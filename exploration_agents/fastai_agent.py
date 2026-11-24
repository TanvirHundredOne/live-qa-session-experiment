#!/usr/bin/env python3
"""fast.ai / Jeremy Howard courses: lessons were taught live with student questions.
NOTE: verify the channel handle below in your browser; override with --playlist-url if needed."""
from qa_core import Source, run

run(Source(
    name="fast.ai Practical Deep Learning",
    out_dir="fastai",
    channel_playlists_url="https://www.youtube.com/@howardjeremyp/playlists",
    title_regex=r"practical deep learning|deep learning for coders|foundations|stable diffusion|lesson",
    transcript_mode="fallback",
))
