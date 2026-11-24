#!/usr/bin/env python3
"""EPFL CS-433 Machine Learning (Switzerland, taught in English, Jaggi/Flammarion).
Playlist links are scraped from the course pages for the years that published recordings."""
from qa_core import Source, run

run(Source(
    name="EPFL CS-433 Machine Learning",
    out_dir="epfl_cs433",
    playlist_pages=[
        "https://www.epfl.ch/labs/mlo/machine-learning-cs-433-2021",
        "https://www.epfl.ch/labs/mlo/machine-learning-cs-433-2020",
    ],
))
