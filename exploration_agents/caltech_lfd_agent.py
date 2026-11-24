#!/usr/bin/env python3
"""Caltech 'Learning From Data' (Yaser Abu-Mostafa): each lecture video = review + lecture + Q&A.
The agent scrapes Caltech's lecture page for the YouTube playlist link."""
from qa_core import Source, run

run(Source(
    name="Caltech Learning From Data",
    out_dir="../caltech_lfd",
    playlist_pages=["https://home.work.caltech.edu/lectures.html"],
    transcript_mode="fallback",  # descriptions rarely mention Q&A, so check captions too
))
