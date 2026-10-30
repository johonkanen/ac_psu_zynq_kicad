#!/usr/bin/env python3
"""Block edit E13 (REUSE_LOG.md): move C99 north, out from under the heatsink base (kipy; tools/p2k/bin/kipy
tools/block_e13.py [BOARD]). tools/build_pcb.sh --rebuild runs it after tools/block_e1.py.

C99 (100 uF 1210 on 1V35, F.Cu, 2.7 mm max) sat with its body 1.2-1.4 mm inside the heatsink base (24 x 23.5 mm on
U20, POWER_BUDGET.md §Heatsink), where nothing may be taller than the package (about 1.5 mm). It moves DY mm north
(towards U15). Its GND via-in-pad (pad 2) stays: the inner layers have DDR3 copper everywhere under the moved pad (no
0.48 mm via fits there at 0.102 mm), and a flat via under the base is fine. An F.Cu GND track (W mm) joins pad 2 to it;
pad 1 takes 1V35 from the F.Cu pour, refilled after (tools/refill_zones.py). Idempotent: refused unless C99 is at its
imported place.
"""
import math
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")
mm, FM = pcbnew.ToMM, pcbnew.FromMM
DY, W = 2.2, 0.3                         # move north, mm; GND track width (juliancoy's GND stubs)
IMPORTED = (-7.1, -12.2)                 # C99 from U20 as imported (block at rotation 0, pose A), board mm

b = pcbnew.LoadBoard(BOARD)
u20, c99 = b.FindFootprintByReference("U20"), b.FindFootprintByReference("C99")
assert abs((u20.GetOrientationDegrees() + 90) % 360) < 1e-6, "block_e13: written for the block at rotation 0 (pose A)"
ux, uy = mm(u20.GetPosition().x), mm(u20.GetPosition().y)
cx, cy = mm(c99.GetPosition().x), mm(c99.GetPosition().y)
if math.hypot(cx - ux - IMPORTED[0], cy - uy - IMPORTED[1]) > 1e-3:
    sys.exit(f"block_e13: C99 is at ({cx:.3f}, {cy:.3f}), not its imported place (already moved?)")

gnd = next(p for p in c99.Pads() if p.GetNumber() == "2")
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetPosition() == gnd.GetPosition()]
if len(vias) != 1 or vias[0].GetNetname() != "GND":
    sys.exit("block_e13: no single GND via in C99 pad 2")
c99.Move(pcbnew.VECTOR2I(0, -FM(DY)))
t = pcbnew.PCB_TRACK(b)
t.SetLayer(pcbnew.F_Cu)
t.SetStart(gnd.GetPosition())
t.SetEnd(vias[0].GetPosition())
t.SetWidth(FM(W))
t.SetNet(vias[0].GetNet())
b.Add(t)
pcbnew.SaveBoard(BOARD, b)
print(f"block_e13: C99 {DY} mm north, to ({cx:.2f}, {cy - DY:.2f}); pad 2 to its GND via by a {W} mm F.Cu track")
