#!/usr/bin/env python3
"""LxMLS - Lisbon Machine Learning School (Portugal, in-person at IST, lectures streamed to YouTube).
Playlist links are scraped from the school's pages. NOTE: in the online 2020/21 editions the Q&A was
restricted to attendees, so expect Q&A mainly in the in-person years (2022+)."""
from qa_core import Source, run

run(Source(
    name="LxMLS Lisbon",
    out_dir="lxmls",
    playlist_pages=[
        "https://lxmls.github.io/2026/",
        "https://bgmartins.github.io/lxmls-website-2025",
        "https://bgmartins.github.io/lxmls-website-2024",
    ],
))
