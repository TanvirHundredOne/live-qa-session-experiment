#!/usr/bin/env python3
"""Harvard CS50 lectures: recorded in a live classroom with student questions.
NOTE: verify the channel handle/playlist titles; override with --playlist-url if needed."""
from qa_core import Source, run

run(Source(
    name="Harvard CS50 lectures",
    out_dir="../cs50",
    channel_playlists_url="https://www.youtube.com/@cs50/playlists",
    title_regex=r"lecture|cs50x|cs50 (?:20\d\d|introduction)",
    transcript_mode="fallback",
))
