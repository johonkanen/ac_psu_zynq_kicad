#!/usr/bin/env python3
"""U801 (IS25WP128, CSP-24 1.0 mm pitch) fan-out: one via per used ball, between the balls (kipy):

    tools/p2k/bin/kipy tools/fanout_u801.py [BOARD]

Every used ball gets a short F.Cu stub, diagonally outward, to a through via in the gap between four balls. The via
centre is 0.707 mm from each of those pad centres: the 0.48/0.25 mm via (net class) clears the 0.40 mm pads by 0.27 mm
copper and 0.38 mm hole-to-pad, vias are 1.0 mm apart. The signals then leave on the inner layers (phase 4), GND and
1V8 go to their planes and pours. Offsets are in the footprint's own frame, so the fan-out follows U801 wherever it
is placed; run after the placement (tools/build_pcb.sh --rebuild). Existing U801 fan-out copper is replaced. The
outer ring (A2/A3/A5, B1/B5, C1/C5, D1/D5, E1-E5) is not connected.
"""
import math
import os
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(TOOLS), "kicad", "zynq_card.kicad_pcb")
REF = "U801"
# ball -> via offset from the ball, footprint frame (mm); x = column 1..5, y = row A..E
ESC = {
    "A4": (-0.5, -0.5),     # ps_por_n (edge row)
    "B2": (-0.5, -0.5),     # qspi_sclk
    "B3": (-0.5, -0.5),     # GND
    "B4": (0.5, -0.5),      # 1V8
    "C2": (-0.5, 0.5),      # qspi_cs_n
    "C4": (0.5, 0.5),       # qspi_io2
    "D2": (-0.5, 0.5),      # qspi_io1
    "D3": (0.5, 0.5),       # qspi_io0
    "D4": (0.5, 0.5),       # qspi_io3
}
VIA, DRILL = 0.48, 0.25
WIDTH = {"GND": 0.2, "1V8": 0.2}    # signals: 0.1 (mio_fast)
mm, FM = pcbnew.ToMM, pcbnew.FromMM


def main():
    b = pcbnew.LoadBoard(PCB)
    f = b.FindFootprintByReference(REF)
    pads = {p.GetNumber(): p for p in f.Pads()}
    # footprint frame -> board: fitted on two pads (covers rotation and the side)
    p0, p1 = pads["B2"], pads["D4"]
    l0, l1 = p0.GetFPRelativePosition(), p1.GetFPRelativePosition()
    g0, g1 = p0.GetPosition(), p1.GetPosition()
    la = math.atan2(l1.y - l0.y, l1.x - l0.x)
    ga = math.atan2(g1.y - g0.y, g1.x - g0.x)
    mirror = f.IsFlipped()

    def to_board(dx, dy):
        if mirror:
            dx = -dx
        a = ga - (la if not mirror else math.pi - la)
        return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)

    # an earlier run's copper: vias within 0.9 mm of a used ball, F.Cu stubs starting on one
    near = [pads[n].GetPosition() for n in ESC]
    old = [t for t in b.GetTracks()
           if (isinstance(t, pcbnew.PCB_VIA) and any((t.GetPosition() - q).EuclideanNorm() < FM(0.9) for q in near))
           or (not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.F_Cu
               and any((t.GetStart() - q).EuclideanNorm() < 10 for q in near))]
    for t in old:
        b.Remove(t)
    for ball, (dx, dy) in ESC.items():
        p = pads[ball]
        ox, oy = to_board(dx, dy)
        c = p.GetPosition()
        v = pcbnew.VECTOR2I(c.x + FM(ox), c.y + FM(oy))
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(v)
        via.SetWidth(FM(VIA))
        via.SetDrill(FM(DRILL))
        via.SetNet(p.GetNet())
        b.Add(via)
        t = pcbnew.PCB_TRACK(b)
        t.SetLayer(pcbnew.F_Cu)
        t.SetStart(c)
        t.SetEnd(v)
        t.SetWidth(FM(WIDTH.get(p.GetNetname(), 0.1)))
        t.SetNet(p.GetNet())
        b.Add(t)
    pcbnew.SaveBoard(PCB, b)
    print(f"fanout_u801: {len(ESC)} balls, {len(ESC)} vias {VIA}/{DRILL} mm between the balls"
          f"{f', {len(old)} old items replaced' if old else ''}")


if __name__ == "__main__":
    main()
