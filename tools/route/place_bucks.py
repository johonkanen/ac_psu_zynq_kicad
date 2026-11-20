#!/usr/bin/env python3
"""Finish the regulator placement before routing (kipy): place_bucks.py IN.kicad_pcb OUT.kicad_pcb

The hand placement of 2026-10-31 gave the east-side cells one template (the 3V3 cell U321 is in place) and left the
1V0 and 1V8 cells parked east of the board edge. Each cell moves rigidly, by its regulator (x, y, turn in degrees):
  1V0   U301 -> (158.0, 106.0)       B.Cu south of the block: L301 and the output caps below U20's 1V0 pour (In6)
  1V8   U311 -> (172.5, 106.2)       B.Cu south of the block, where the 1V35 cell was: 6 mm from the block's In4
                                     1V8 pour, which the east-side loads (eMMC, flash, PHY) share
  1V35  U331 -> (198.7, 77.5), 180   B.Cu east, above the 3V3 cell, output side west: a B.Cu strip (y 72.6-76.4)
                                     takes 1V35 straight to the block's B.Cu 1V35 pour under the DDR, with no rail
                                     crossing the MIO fan-out east of U20
5V0 reaches all four on B.Cu: a strip up the east edge from J6 and a band along the south edge (tools/route/
power_zones.py). Change TARGET and re-run tools/route.sh to try another arrangement.
Four small nudges clear courtyard overlaps left by the same hand placement (below).
"""
import sys

import pcbnew

TARGET = {"U301": ((158.0, 106.0), 0, ["L301", "C301", "C302", "C303", "C304", "R301", "R302"]),
          "U311": ((172.5, 106.2), 0, ["L311", "C311", "C312", "C313", "R311", "R312"]),
          "U331": ((198.7, 77.5), 180, ["L331", "C331", "C332", "C333", "R331", "R332"])}
b = pcbnew.LoadBoard(sys.argv[1])
edge = b.GetBoardEdgesBoundingBox()
for u, ((x, y), turn, parts) in TARGET.items():
    fu = b.FindFootprintByReference(u)
    centre = fu.GetPosition()
    d = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)) - centre
    for r in [u] + parts:
        f = b.FindFootprintByReference(r)
        if turn:
            f.Rotate(centre, pcbnew.EDA_ANGLE(turn, pcbnew.DEGREES_T))
        f.Move(d)
        assert edge.Contains(f.GetBoundingBox(False)), (r, "off the board")
    print(f"{u} cell -> ({x}, {y}), turned {turn} deg")
# courtyard overlaps left by the same hand placement: L301 0.6 mm over its output caps, and the eMMC (turned 90 deg)
# 0.7 mm over C1001, C1004 and R1019 at its east edge
for ref, dx, dy in (("L301", 0, -0.6), ("C1001", 0.75, 0), ("C1004", 0.75, 0), ("R1019", 0.75, 0)):
    b.FindFootprintByReference(ref).Move(pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy)))
    print(f"{ref} moved by ({dx}, {dy})")
pcbnew.SaveBoard(sys.argv[2], b)
