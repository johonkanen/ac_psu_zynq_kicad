#!/usr/bin/env python3
"""C514 (0.47 uF, 1V35, ours) onto a 1V35 via and a GND via under U20 (kipy): place_c514.py IN.kicad_pcb OUT.kicad_pcb

Where tools/place_free.py put it, among the DDR data vias at (169.5, 79.4), its GND pad has no ground via in reach.
This looks for a 1V35 via and a GND via 0.75-1.20 mm apart under U20's DDR-bank rows (y 77.3-84), puts the capacitor
between them, each pad over its via (same net: the via ties the pad), and takes the nearest pose whose pads keep
0.102 mm (0.2 mm from a foreign via's hole) from every other B.Cu pad, track and via and whose courtyard is free.
"""
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
f = b.FindFootprintByReference("C514")
assert f.IsFlipped()
vias = [(MM(t.GetPosition().x), MM(t.GetPosition().y), MM(t.GetWidth(pcbnew.F_Cu)) / 2, MM(t.GetDrill()) / 2, t.GetNetname())
        for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
pads = []
for g in b.GetFootprints():
    if g.GetReference() == "C514":
        continue
    for p in g.Pads():
        if p.IsOnLayer(pcbnew.B_Cu):
            bb = p.GetBoundingBox()
            pads.append((MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()), p.GetNetname()))
tracks = [(MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth()) / 2, t.GetNetname())
          for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.B_Cu]
pw = sorted(MM(p.GetSize().x) for p in f.Pads())[0], sorted(MM(p.GetSize().y) for p in f.Pads())[0]
half = max(pw) / 2 + 0.02          # a pad as a circle of its longer half side: conservative


def seg_d(x, y, s):
    ax, ay, cx, cy = s[:4]
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - ax - t * (cx - ax), y - ay - t * (cy - ay))


def clear(x, y, net):
    for vx, vy, r, dr, n in vias:
        d = math.hypot(vx - x, vy - y)
        if n != net and d < half + max(r + 0.102, dr + 0.2):
            return False
    for l, t, r_, bt, n in pads:
        if n != net and math.hypot(max(l - x, 0, x - r_), max(t - y, 0, y - bt)) < half + 0.102:
            return False
    return all(s[5] == net or seg_d(x, y, s) >= half + s[4] + 0.102 for s in tracks)


u = b.FindFootprintByReference("U20").GetPosition()
cands = []
for ax, ay, _, _, an in vias:
    if an != "1V35" or not 77.3 < ay < 84 or abs(ax - MM(u.x)) > 9.5:
        continue
    for gx, gy, _, _, gn in vias:
        d = math.hypot(gx - ax, gy - ay)
        if gn == "GND" and 0.75 <= d <= 1.20 and clear(ax, ay, "1V35") and clear(gx, gy, "GND"):
            cands.append((math.hypot(ax - 169.5, ay - 79.4), ax, ay, gx, gy))
courts = [g.GetCourtyard(pcbnew.B_CrtYd).BBox() for g in b.GetFootprints() if g.IsFlipped() and g.GetReference() != "C514"]
p1 = next(p for p in f.Pads() if p.GetNetname() == "1V35")
p2 = next(p for p in f.Pads() if p.GetNetname() == "GND")
home, turn = f.GetPosition(), f.GetOrientationDegrees()
for _, ax, ay, gx, gy in sorted(cands):
    a1, a2 = p1.GetPosition(), p2.GetPosition()
    old = math.degrees(math.atan2(-(a2.y - a1.y), a2.x - a1.x))
    new = math.degrees(math.atan2(-(gy - ay), gx - ax))
    f.SetPosition(pcbnew.VECTOR2I(FM((ax + gx) / 2), FM((ay + gy) / 2)))
    f.SetOrientationDegrees(f.GetOrientationDegrees() + new - old)
    cy = f.GetCourtyard(pcbnew.B_CrtYd).BBox()
    if not any(cy.Intersects(c) for c in courts):
        break
else:
    f.SetPosition(home); f.SetOrientationDegrees(turn)
    sys.exit("place_c514: no via pair with a free courtyard")
# the short tracks from its old pads
for t in [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.B_Cu
          and t.GetNetname() in ("1V35", "GND") and min(math.hypot(MM(q.x) - 169.5, MM(q.y) - 79.4) for q in (t.GetStart(), t.GetEnd())) < 0.75
          and MM(t.GetLength()) < 1.5]:
    b.Delete(t)
print(f"C514 -> ({(ax + gx) / 2:.2f}, {(ay + gy) / 2:.2f}), 1V35 pad on the via at ({ax:.2f}, {ay:.2f}), GND pad on ({gx:.2f}, {gy:.2f})")
pcbnew.SaveBoard(sys.argv[2], b)
