#!/usr/bin/env python3
"""Deep Learning Indaba (Africa; Stellenbosch, Accra, ...). Lectures/tutorials streamed + recorded.
NOTE: the channel handle below is from memory - verify it, or pass --playlist-url."""
from qa_core import Source, run

run(Source(
    name="Deep Learning Indaba",
    out_dir="indaba",
    playlist_pages=["https://deeplearningindaba.com/2018/indaba/programme/"],
    channel_playlists_url="https://www.youtube.com/@DeepLearningIndaba/playlists",
    title_regex=r"indaba|20(1[89]|2\d)|lecture|keynote|tutorial",
))
