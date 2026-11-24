#!/usr/bin/env python3
"""KHIPU - Latin American Meeting in AI (Montevideo 2019/2023, Santiago 2025, Sao Paulo 2027).
Some talks are in Spanish; the English-only gate in qa_core skips them."""
from qa_core import Source, run

run(Source(
    name="KHIPU Latin American AI",
    out_dir="khipu",
    channel_playlists_url="https://www.youtube.com/@khipu_ai/playlists",
    title_regex=r"khipu|20(19|2\d)|lecture|fundamentals",
))
