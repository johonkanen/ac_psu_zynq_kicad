#!/usr/bin/env python3
"""Helpers for tools/fanout_u20.sh, the U20 fan-out of the balls juliancoy does not escape (kipy):

    tools/p2k/bin/kipy tools/fanout_u20.py nets BOARD OUT     U20 signal balls with no copper -> OUT, one net a line
    tools/p2k/bin/kipy tools/fanout_u20.py shadow-on BOARD    cover the SMD pads near U20 with marker tracks
    tools/p2k/bin/kipy tools/fanout_u20.py shadow-off BOARD   remove them
    tools/p2k/bin/kipy tools/fanout_u20.py prune BOARD NETFILE  remove all copper of these nets (they had none before)

KiCadRoutingTools' bga_fanout does not see the SMD pads of parts on the other face (our decaps on B.Cu under U20): it
put through vias on 14 of them. It does see tracks, so each SMD pad of another part within REACH of U20's courtyard
gets a no-net track on its layer that covers the pad (along its long side, width = short side, round ends past the
pad ends), widened by MARK nm so shadow-off finds exactly these again (bga_fanout gives some of them the pad's net).
"""
import os
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from escape_u20 import bare_signal_balls  # noqa: E402

REACH = 2.0       # mm around U20's courtyard
MARK = 123        # nm added to a shadow track's width
FM = pcbnew.FromMM


def shadows(b):
    return [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetWidth() % 1000 == MARK]


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(path)
    u = b.FindFootprintByReference("U20")
    if cmd == "nets":
        nets = sorted(p.GetNetname() for p in bare_signal_balls(b, u).values())
        open(sys.argv[3], "w").write("".join(n + "\n" for n in nets))
        print(f"fanout_u20: {len(nets)} U20 signal balls without copper")
        return
    if cmd == "prune":
        nets = {n.strip() for n in open(sys.argv[3]) if n.strip()}
        old = [t for t in b.GetTracks() if t.GetNetname() in nets]
        for t in old:
            b.Remove(t)
        pcbnew.SaveBoard(path, b)
        print(f"fanout_u20: pruned {len(nets)} nets ({len(old)} items): {' '.join(sorted(n.rsplit('/', 1)[-1] for n in nets))}")
        return
    for t in shadows(b):
        b.Remove(t)
    n = 0
    if cmd == "shadow-on":
        area = u.GetCourtyard(pcbnew.F_CrtYd).BBox()
        area.Inflate(FM(REACH))
        for fp in b.GetFootprints():
            if fp.GetReference() == "U20":
                continue
            for p in fp.Pads():
                if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not area.Intersects(p.GetBoundingBox()):
                    continue
                bb = p.GetBoundingBox()
                w, h = bb.GetWidth(), bb.GetHeight()
                c = bb.GetCenter()
                t = pcbnew.PCB_TRACK(b)
                t.SetLayer(pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu)
                if w >= h:
                    t.SetStart(pcbnew.VECTOR2I(bb.GetLeft(), c.y))
                    t.SetEnd(pcbnew.VECTOR2I(bb.GetRight(), c.y))
                else:
                    t.SetStart(pcbnew.VECTOR2I(c.x, bb.GetTop()))
                    t.SetEnd(pcbnew.VECTOR2I(c.x, bb.GetBottom()))
                t.SetWidth(min(w, h) // 1000 * 1000 + MARK)
                b.Add(t)
                n += 1
    pcbnew.SaveBoard(path, b)
    print(f"fanout_u20: {cmd}, {n} pad shadows")


if __name__ == "__main__":
    main()
