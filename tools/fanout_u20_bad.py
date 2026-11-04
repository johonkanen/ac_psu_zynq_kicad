#!/usr/bin/env python3
"""tools/fanout_u20.sh: the nets of BARE (the U20 balls the run fanned out) that sit in a copper violation of the
kicad-cli DRC report DRC_JSON, one a line on stdout: python3 tools/fanout_u20_bad.py DRC_JSON BARE"""
import json
import re
import sys

KINDS = {"clearance", "hole_clearance", "hole_to_hole", "shorting_items", "solder_mask_bridge", "tracks_crossing"}
d, bare = json.load(open(sys.argv[1])), {n.strip() for n in open(sys.argv[2]) if n.strip()}
bad = {n for v in d["violations"] if v["type"] in KINDS for i in v["items"]
       for n in re.findall(r"\[([^\]]+)\]", i["description"]) if n in bare}
print("".join(n + "\n" for n in sorted(bad)), end="")
