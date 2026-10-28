#!/usr/bin/env python3
"""The analog section placed as on the Ti135 card (kipy; tools/p2k/bin/kipy tools/place_analog.py [IN [OUT]]).

The ADC chain (sheet 12: SN74LV4051A mux, OPA365 buffer, 33 R + 680 p kickback filter, ADS7056, rail-monitor
resistors, SPI series resistors) and the 3V3_analog LDO (U341) are the Ti135 card's sheet 13 with the refs renumbered.
That card copied them from the Agilex 5 card (~/dev/agilex3_soc_control_card) and then adjusted them by hand, on the
same outline with J3/J1/J2/J5 at the same coordinates as ours. So the parts take the Ti135 card's final positions and
rotations relative to J3 (TI135 below; read from ~/dev/efinix_soc_board/kicad/ti135_card.kicad_pcb at 0d4280c,
2026-10-28; that repository is not modified). They sit just below J3, where the isoada inputs (J3 pins 1, 3, 4) arrive.
(~/dev/ti60f225_control_card is not a source: another baseboard connector, two ADC chains, no NCP163.)

1. Every unlocked part of ours whose courtyard is in the way of a copied part (same side, or either is through-hole) is
   parked east of the board (the KRT placement put other parts here); they are listed, for a KRT re-place with the
   rest locked.
2. A copied part that hits a fixed obstacle (a locked part: the block, the connectors, H1/H2; the `ddr3_block` area;
   the 3 mm heatsink rings; 0.5 mm from the edge) goes to the nearest free spot within 8 mm, any of 4 rotations: the
   top of the Ti135 group (mux, its decap, two monitor resistors) is inside our block area.
3. C342 (the LDO output cap; the Ti135 card had it far away) goes next to U341's output pin.
4. The 8 J3 pull-down arrays (RN1301-RN1308) go to B.Cu in a column beside J3, each level with the J3 pins it pulls
   down, signal pads towards J3 (the Ti135 card's place_analog.py step 3, as on the Agilex card).
5. These parts are locked, so a later placement run keeps them.
"""
import math
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")
mm, FM = pcbnew.ToMM, pcbnew.FromMM
# ours: (Ti135 ref, x, y from J3, rotation, value)
TI135 = {
    "U1201": ("U1301", 6.280, 20.897, 0, "SN74LV4051APWR"), "U1202": ("U1302", 6.231, 25.985, -90, "OPA365AIDBVR"),
    "U1203": ("U1303", 1.022, 32.062, 90, "ADS7056IRUGR"), "C1201": ("C1301", 8.440, 34.563, 90, "1u"),
    "C1202": ("C1302", 5.190, 29.076, 90, "680p C0G"), "C1203": ("C1303", 6.940, 17.589, 180, "100n"),
    "C1204": ("C1304", 7.405, 31.642, 90, "4u7"), "C1205": ("C1305", 8.681, 27.122, 90, "100n"),
    "C1206": ("C1306", 8.830, 32.062, 90, "1u"), "R1201": ("R1301", 10.890, 19.922, 90, "100R"),
    "R1202": ("R1302", 9.274, 17.527, 0, "1k"), "R1203": ("R1303", 9.143, 24.222, 0, "1k"),
    "R1204": ("R1304", 3.418, 24.222, 0, "1k"), "R1205": ("R1305", 9.028, 25.305, 0, "1k"),
    "R1206": ("R1306", 6.279, 29.067, -90, "33R"), "R1210": ("R1310", 7.895, 29.510, 0, "33R"),
    "R1211": ("R1311", 9.880, 32.737, 90, "33R"), "R1212": ("R1312", 9.652, 34.757, 90, "33R"),
    "U341": ("U101", 5.630, 34.997, 0, "NCP163ASN330T1G"), "C341": ("C104", 5.356, 37.502, 0, "1u"),
}
NEAR = {"C342": ("U341", "5")}     # ours only: ref -> (partner, pad)
ARRAYS = [f"RN13{i:02d}" for i in range(1, 9)]
ARRAY_PITCH = 2.7                  # the Ti135 card's column pitch
EDGE, RING = 0.5, 3.0


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else PCB
    out = sys.argv[2] if len(sys.argv) > 2 else src
    b = pcbnew.LoadBoard(src)
    fp = {f.GetReference(): f for f in b.GetFootprints()}
    ours = set(TI135) | set(NEAR)
    for r, v in TI135.items():
        assert fp[r].GetValue() == v[4], (r, fp[r].GetValue(), v[4])
    j3 = fp["J3"].GetPosition()
    e = b.GetBoardEdgesBoundingBox()
    ex0, ey0 = mm(e.GetLeft()) + EDGE, mm(e.GetTop()) + EDGE
    ex1, ey1 = mm(e.GetRight()) - EDGE, mm(e.GetBottom()) - EDGE
    blk = next(z for z in b.Zones() if z.GetZoneName() == "ddr3_block").GetBoundingBox()
    block = (mm(blk.GetLeft()), mm(blk.GetTop()), mm(blk.GetRight()), mm(blk.GetBottom()))
    rings = [(mm(fp[h].GetPosition().x), mm(fp[h].GetPosition().y)) for h in ("H1", "H2")]

    def court(f):
        bb = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
        if bb.GetWidth() == 0:
            bb = f.GetBoundingBox(False)
        return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())

    def tht(f):
        return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads())

    def overlap(a, c):
        return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]

    def meets(f, o):
        return (o.IsFlipped() == f.IsFlipped() or tht(o) or tht(f)) and overlap(court(f), court(o))

    def fixed_hit(f, placed):
        a = court(f)
        if a[0] < ex0 or a[1] < ey0 or a[2] > ex1 or a[3] > ey1 or overlap(a, block):
            return True
        for cx, cy in rings:
            nx, ny = min(max(cx, a[0]), a[2]), min(max(cy, a[1]), a[3])
            if math.hypot(nx - cx, ny - cy) < RING:
                return True
        return any(meets(f, o) for o in b.GetFootprints()
                   if o.GetReference() != f.GetReference() and (o.IsLocked() or o.GetReference() in placed))

    def put(f, x, y, rot):
        if f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))

    def nearest(f, x0, y0, rot0, placed, rmax=8.0):
        for rad in [i * 0.1 for i in range(0, int(rmax * 10) + 1)]:
            n = max(1, int(2 * math.pi * rad / 0.1))
            for k in range(n):
                a = 2 * math.pi * k / n
                for rot in (rot0, rot0 + 90, rot0 + 180, rot0 + 270):
                    put(f, x0 + rad * math.cos(a), y0 + rad * math.sin(a), rot)
                    if not fixed_hit(f, placed):
                        return rad
        return None

    for r in ours:                       # unlock (a re-run) and park off the board, out of each other's way
        fp[r].SetLocked(False)
        put(fp[r], 260.0, 150.0, 0)
    placed, moved, later = [], [], []
    for r, (tr, dx, dy, rot, _) in TI135.items():     # first every part that fits on its Ti135 spot ...
        put(fp[r], mm(j3.x) + dx, mm(j3.y) + dy, rot)
        if fixed_hit(fp[r], placed):
            later.append(r)
            put(fp[r], 260.0, 150.0, 0)
        else:
            placed.append(r)
    for r in later:                                  # ... then the others at the nearest free spot
        tr, dx, dy, rot, _ = TI135[r]
        rad = nearest(fp[r], mm(j3.x) + dx, mm(j3.y) + dy, rot, placed)
        moved.append(f"{r} ({tr}) off its Ti135 spot: {'%.1f mm away' % rad if rad is not None else 'NO FREE SPOT'}")
        placed.append(r)
    for r, (pr, pad) in NEAR.items():
        p = next(q for q in fp[pr].Pads() if q.GetNumber() == pad)
        rad = nearest(fp[r], mm(p.GetPosition().x), mm(p.GetPosition().y), 0, placed)
        moved.append(f"{r} placed by {pr}.{pad}: {'%.1f mm' % rad if rad is not None else 'NO FREE SPOT'}")
        placed.append(r)
    # the J3 pull-down arrays: B.Cu, a column just east of J3's courtyard, each level with the mean of its J3 pins,
    # signal pads towards J3 (the Ti135 card's place_analog.py, as on the Agilex card)
    j3f, jc = fp["J3"], court(fp["J3"])
    want = []
    for r in ARRAYS:
        f = fp[r]
        f.SetLocked(False)
        sig = [p.GetNumber() for p in f.Pads()
               if p.GetNetname() != "GND" and any(q.GetNetCode() == p.GetNetCode() for q in j3f.Pads())]
        ys = [mm(q.GetPosition().y) for p in f.Pads() if p.GetNumber() in sig
              for q in j3f.Pads() if q.GetNetCode() == p.GetNetCode()]
        want.append((sum(ys) / len(ys), r, sig))
    want.sort()
    y = None
    for ty, r, sig in want:
        f = fp[r]
        if not f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(90)
        half = (court(f)[2] - court(f)[0]) / 2
        y = ty if y is None else max(ty, y + ARRAY_PITCH)
        for rot in (90, 270):    # the rotation that puts the J3-side pads nearest J3
            f.SetOrientationDegrees(rot)
            f.SetPosition(pcbnew.VECTOR2I(FM(jc[2] + half + 0.05), FM(y)))
            sx = [mm(p.GetPosition().x) for p in f.Pads() if p.GetNumber() in sig]
            ox = [mm(p.GetPosition().x) for p in f.Pads() if p.GetNumber() not in sig]
            if sum(sx) / len(sx) < sum(ox) / len(ox):
                break
        if fixed_hit(f, placed):
            moved.append(f"{r}: hits a fixed part or area in the J3 column")
        placed.append(r)
    moved.append(f"arrays on B.Cu at x {mm(fp[ARRAYS[0]].GetPosition().x):.2f}, y {want[0][0]:.1f}..{y:.1f}")

    parked, x = [], 215.0
    for o in b.GetFootprints():
        r = o.GetReference()
        if r in ours or r in ARRAYS or o.IsLocked():
            continue
        if any(meets(fp[a], o) for a in placed):
            o.SetPosition(pcbnew.VECTOR2I(FM(x), FM(60.0)))
            x += 4
            parked.append(r)
    for r in placed:
        fp[r].SetLocked(True)
    pcbnew.SaveBoard(out, b)
    print(f"place_analog: {len(TI135)} parts at the Ti135 card's positions from J3, + {', '.join(NEAR)}, "
          f"+ {len(ARRAYS)} J3 pull-down arrays; locked")
    for m in moved:
        print("  " + m)
    print("  parked east of the board (re-place them): " + (", ".join(sorted(parked)) or "none"))


if __name__ == "__main__":
    main()
