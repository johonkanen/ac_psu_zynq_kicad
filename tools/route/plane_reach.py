#!/usr/bin/env python3
"""How many of a part's supply balls a rail's pour reaches from its regulator, on one layer alone (kipy):

    plane_reach.py BOARD NET LAYER SEED_X,SEED_Y REF [X0,Y0,X1,Y1]       (zones filled: check_board.sh's copy)

A flood over the filled copper of every pour of NET on LAYER (0.1 mm grid, inside the rectangle; default the board),
started at SEED (a point on the pour at the regulator). Counted: the vias of NET inside REF's courtyard that the flood
reaches. DRC calls a ball connected however thin the path; this says whether the plane itself carries it. On
2026-11-20 two signals across the neck of the 1V0 pour left 1 of U20's 22 core vias on it.
"""
import collections
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
net, layer, ref = sys.argv[2], sys.argv[3], sys.argv[5]
sx, sy = (float(v) for v in sys.argv[4].split(","))
eb = b.GetBoardEdgesBoundingBox()
x0, y0, x1, y1 = (float(v) for v in sys.argv[6].split(",")) if len(sys.argv) > 6 else \
    (MM(eb.GetLeft()), MM(eb.GetTop()), MM(eb.GetRight()), MM(eb.GetBottom()))
S = 0.1
zs = [(z, l) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == net
      for l in z.GetLayerSet().Seq() if pcbnew.LayerName(l) == layer]
nx, ny = int((x1 - x0) / S) + 1, int((y1 - y0) / S) + 1
filled = [[any(z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(x0 + i * S), FM(y0 + j * S))) for z, l in zs) for i in range(nx)]
          for j in range(ny)]
si, sj = int((sx - x0) / S), int((sy - y0) / S)
if not filled[sj][si]:
    sys.exit(f"plane_reach: no {net} copper on {layer} at the seed ({sx}, {sy})")
seen, q = {(si, sj)}, collections.deque([(si, sj)])
while q:
    i, j = q.popleft()
    for a, c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
        if 0 <= a < nx and 0 <= c < ny and filled[c][a] and (a, c) not in seen:
            seen.add((a, c)); q.append((a, c))
cy = b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox()
vias = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in b.GetTracks()
        if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net and cy.Contains(t.GetPosition())]
hit = [v for v in vias if any((int((v[0] + dx - x0) / S), int((v[1] + dy - y0) / S)) in seen
                              for dx, dy in ((0, 0), (.15, 0), (-.15, 0), (0, .15), (0, -.15)))]
print(f"plane_reach: {net} on {layer}: {len(hit)} of {len(vias)} vias under {ref} reached from ({sx}, {sy})")
for v in vias:
    if v not in hit:
        print(f"   not reached: ({v[0]:.2f}, {v[1]:.2f})")
