#!/usr/bin/env python3
"""Bring U20's ball nets on the board in line with the schematic after a pin swap, and strip the old breakout stubs:

    kipy tools/route/pin_swap_board.py IN.kicad_pcb OUT.kicad_pcb [NETLIST.xml]

1. Every stub of tools/fanout_u20.sh (REUSE_LOG E14) goes: the copper connected to a U20 ball on one of our signal
   nets (tools/route_groups.json "signals"), followed through same-net copper. Kept: the QSPI escapes (E10, copied with
   the block) and nets with a block part on them. tools/fanout_u20.sh is run again afterwards.
2. Each U20 pad takes its net from the netlist (work/zynq_card_net.xml, written by tools/build_schematic.sh).
Nothing else changes; schematic parity is the check.
"""
import fnmatch
import json
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
b = pcbnew.LoadBoard(sys.argv[1])
xml = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "work", "zynq_card_net.xml")
KEEP = ["qspi_cs_n", "qspi_io?", "qspi_sclk", "cfg_program_n", "cfg_init_n"]
signals = [n for n in json.load(open(os.path.join(ROOT, "tools", "route_groups.json")))["signals"]
           if not any(fnmatch.fnmatchcase(n.split("/")[-1], k) for k in KEEP)]
u = b.FindFootprintByReference("U20")

# 1. strip the stubs
b.BuildConnectivity()
conn = b.GetConnectivity()
kill = {}
for p in u.Pads():
    if p.GetNetname() not in signals:
        continue
    todo, seen = [p], set()
    while todo:
        it = todo.pop()
        for o in conn.GetConnectedItems(it):
            if o.GetClass() in ("PCB_TRACK", "PCB_VIA", "PCB_ARC") and o.m_Uuid.AsString() not in seen:
                seen.add(o.m_Uuid.AsString())
                kill[o.m_Uuid.AsString()] = o
                todo.append(o)
            elif o.GetClass() == "PAD" and o.GetParentFootprint().GetReference() != "U20":
                sys.exit(f"pin_swap_board: {p.GetNetname()} is routed from U20.{p.GetNumber()} to "
                         f"{o.GetParentFootprint().GetReference()}: strip the routing first")
items = list(kill.values())
for it in items:
    b.Remove(it)
print(f"pin_swap_board: {len(items)} stub items removed from U20")

# 2. nets from the netlist
want = {}
for net in ET.parse(xml).getroot().iter("net"):
    for node in net.iter("node"):
        if node.get("ref") == "U20":
            want[node.get("pin")] = net.get("name")
changed = []
for p in u.Pads():
    name = want.get(p.GetNumber(), "")
    if p.GetNetname() != name:
        ni = b.FindNet(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(b, name)
            b.Add(ni)
        changed.append(f"{p.GetNumber()}: {p.GetNetname().split('/')[-1] or '-'} -> {name.split('/')[-1]}")
        p.SetNet(ni)
print(f"pin_swap_board: {len(changed)} balls re-netted")
for c in changed:
    print("  ", c)
pcbnew.SaveBoard(sys.argv[2], b)
