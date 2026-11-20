#!/usr/bin/env python3
"""Unlock the tracks and vias of the nets of some groups (kipy): unlock_nets.py BOARD GROUP[,GROUP...]
The copied block stays locked. Used before a step that may rip and re-route our own nets."""
import json
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
groups = json.load(open(os.path.join(ROOT, "tools", "route_groups.json")))
nets = {n for g in sys.argv[2].split(",") for n in groups[g]}
b = pcbnew.LoadBoard(sys.argv[1])
n = 0
for t in b.GetTracks():
    if t.GetNetname() in nets and t.IsLocked():
        t.SetLocked(False); n += 1
pcbnew.SaveBoard(sys.argv[1], b)
print(f"unlock_nets: {n} tracks and vias of {sys.argv[2]} unlocked")
