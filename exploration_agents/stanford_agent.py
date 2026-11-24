# https://www.youtube.com/@stanfordonline

#!/usr/bin/env python3
"""Stanford Online lectures: recorded in a live classroom with student questions.
NOTE: verify the channel handle/playlist titles; override with --playlist-url if needed."""
from qa_core import Source, run

run(Source(
    name="Stanford Online lectures",
    out_dir="./stanford_online_2",
    channel_playlists_url="https://www.youtube.com/@stanfordonline/playlists",
    title_regex=r"lecture|stanford (?:20\d\d|introduction)",
    transcript_mode="fallback",
))
