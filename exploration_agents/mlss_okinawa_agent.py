#!/usr/bin/env python3
"""MLSS Okinawa 2024 (OIST, Japan; lectures by Hashimoto, Orabona, Shai Ben-David, ...).
OIST says most lectures are on the program page; we scrape YouTube playlist links from the MLSS pages."""
from qa_core import Source, run

run(Source(
    name="MLSS Okinawa",
    out_dir="mlss_okinawa",
    playlist_pages=["https://groups.oist.jp/mlss"],
))
