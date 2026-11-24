#!/usr/bin/env python3
"""Cohere Labs Open Science Community talks (200+ guest talks, many with audience Q&A).
Playlist links are scraped from the community pages; the research 'Videos' playlist is included too."""
from qa_core import Source, run

run(Source(
    name="Cohere Labs community talks",
    out_dir="cohere_labs",
    playlists=["https://www.youtube.com/playlist?list=PLLalUvky4CLJKDaiWCumhsJpHNDhZeVll"],
    playlist_pages=[
        "https://labscommunity.cohere.com/community-programs",
        "https://labscommunity.cohere.com",
    ],
    transcript_mode="fallback",
))
