#!/usr/bin/env python3
"""Per-step result of the routing chain from work/route/NN_step.json: python3 tools/route/summary.py"""
import glob
import json
import os

W = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "work", "route")
for f in sorted(glob.glob(os.path.join(W, "[0-9][0-9]_*.json"))):
    d = json.load(open(f))
    fs = [n.split("/")[-1] for n in d.get("failed_single", [])]
    fm = [f"{m['net_name'].split('/')[-1]}({len(m['failed_pads'])})" for m in d.get("failed_multipoint", [])]
    print(f"{os.path.basename(f)[:-5]:16s} ok {d.get('successful', '?'):>3}  open: {' '.join(fs + fm) or '-'}")
