#!/usr/bin/env python3
"""Bottom-side part heights against the baseboard parts under the card (MECHANICAL.md, LAYOUT_PLAN.md step 4):

    tools/p2k/bin/kipy tools/check_heights.py [BOARD]

The baseboard (~/dev/ac_psu_kicad/kicad/ac_psu.kicad_pcb) is mapped into the card frame through its J11 header:
J3 pin n mates with J11 pin n (the fit is checked on J11 37/38 and J12 against J6). The card sits GAP mm above the
baseboard (the mated 1.27 mm socket + header; MECHANICAL.md takes the lower estimate). For every card part on B.Cu and
every baseboard top-side part whose courtyards overlap (each grown by TOL for the header alignment), the two heights
must leave MARGIN: h_card + h_base <= GAP - MARGIN. Heights are the package maximum (nominal + tolerance) of the part
we buy (tools/set_lcsc.py) or, for the baseboard, of its package; a footprint without an entry fails.
Also listed: the baseboard parts under the heatsink push-pins (H1/H2: what a barb below the card must clear) and the
baseboard parts that are not small SMD (mounting hole, THT) near the card.
Exit code 1 when a pair is too tall or a height is missing.
"""
import math
import os
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")
BASE = os.path.expanduser("~/dev/ac_psu_kicad/kicad/ac_psu.kicad_pcb")
GAP, MARGIN, TOL, BARB_R = 5.3, 0.3, 0.3, 3.0
mm = pcbnew.ToMM

# card B.Cu parts: footprint -> max height, mm (the part in the BOM)
CARD_H = {
    "R_0402_1005Metric": 0.40,                   # 0402WGF: 0.35 +/- 0.05
    "C_0402_1005Metric": 0.55,                   # CL05x: 0.5 +/- 0.05
    "R_Array_Convex_4x0402": 0.45,               # 4D02WGJ0103TCE
    "SOT-563": 0.60,                             # TLV62585P
    "C_0603_1608Metric": 0.90,                   # CL10A106KP8: 0.8 +/- 0.1 (also D7 LED, FB1 0 R)
    "L_0603_1608Metric": 0.90,                   # BLM18SG
    "Crystal_SMD_3225-4Pin_3.2x2.5mm": 0.90,     # X322525MRB4SI
    "VSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.4mm_ThermalVias": 1.00,   # TPS51200 DRC
    "C_0805_2012Metric": 1.45,                   # CL21A226MAQ / CL21A106KAY / CL21A476MQY: 1.25 +/- 0.2
    "C_1206_3216Metric": 1.80,                   # CL31A476MPH: 1.6 +/- 0.2
    "L_Coilcraft_XxL4020": 2.10,                 # WPN4020H1R0MT: 2.0 max (MECHANICAL.md) + 0.1
    "C_1210_3225Metric": 2.70,                   # CL32A107MQV: 2.5 +/- 0.2
}
CARD_SPACERS = {"J3", "J6"}                      # the sockets set the gap

# baseboard top-side parts: footprint (prefix) -> max height, mm (package)
BASE_H = {
    "R_0402": 0.40, "C_0402": 0.60, "C_0603": 0.95, "R_0805": 0.65, "L_0805": 1.35, "R_1206": 0.70,
    "C_1206": 1.80, "R_Array_Convex_4x0402": 0.45, "X2QFN-8": 0.40, "TSSOP-": 1.20, "SOT-23": 1.45,
    "SOIC-": 2.65, "D_SMA": 2.50,
    "R_Shunt_FKK5R0020FE": 1.00,                 # [verify] shunt body height
}
BASE_SPACERS = {"J11", "J12"}


def fp_name(f):
    return f.GetFPIDAsString().split(":")[-1]


def base_height(f):
    n = fp_name(f)
    return next((h for k, h in BASE_H.items() if n.startswith(k)), None)


def court(f, xform=None):
    lay = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    bb = f.GetCourtyard(lay).BBox()
    if not bb.GetWidth():
        bb = f.GetBoundingBox(False)
    pts = [(mm(x), mm(y)) for x in (bb.GetLeft(), bb.GetRight()) for y in (bb.GetTop(), bb.GetBottom())]
    if xform:
        pts = [xform(p) for p in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(r, s, grow):
    return r[0] - grow < s[2] and s[0] - grow < r[2] and r[1] - grow < s[3] and s[1] - grow < r[3]


def main():
    card, base = pcbnew.LoadBoard(PCB), pcbnew.LoadBoard(BASE)
    pads = lambda b, ref: {p.GetNumber(): (mm(p.GetPosition().x), mm(p.GetPosition().y))
                           for p in b.FindFootprintByReference(ref).Pads()}
    j11, j3, j12, j6 = pads(base, "J11"), pads(card, "J3"), pads(base, "J12"), pads(card, "J6")
    a0, a1, b0, b1 = j11["1"], j11["37"], j3["1"], j3["37"]
    th = math.atan2(b1[1] - b0[1], b1[0] - b0[0]) - math.atan2(a1[1] - a0[1], a1[0] - a0[0])
    c, s = math.cos(th), math.sin(th)

    def xf(p):
        x, y = p[0] - a0[0], p[1] - a0[1]
        return b0[0] + c * x - s * y, b0[1] + s * x + c * y

    err = max(math.dist(xf(j11["38"]), j3["38"]), max(math.dist(xf(j12[str(42 + n)]), j6[str(n)]) for n in range(1, 7)))
    if err > 0.01:
        sys.exit(f"check_heights: the J11/J12 -> J3/J6 fit is off by {err:.3f} mm")
    eb = card.GetBoardEdgesBoundingBox()
    outline = (mm(eb.GetLeft()), mm(eb.GetTop()), mm(eb.GetRight()), mm(eb.GetBottom()))

    under, other, fails = [], [], []
    for f in base.GetFootprints():
        if f.IsFlipped() or f.GetReference() in BASE_SPACERS:
            continue
        r = court(f, xf)
        if not overlap(r, outline, 2.0):
            continue
        h = base_height(f)
        if h is None:
            other.append((f.GetReference(), fp_name(f), f.GetValue(), r))
            continue
        under.append((f.GetReference(), fp_name(f), h, r))
    worst, pairs, missing = {}, 0, set()
    for f in card.GetFootprints():
        if not f.IsFlipped() or f.GetReference() in CARD_SPACERS:
            continue
        h = CARD_H.get(fp_name(f))
        if h is None:
            missing.add(fp_name(f))
            continue
        r = court(f)
        for bref, bfp, bh, br in under:
            if overlap(r, br, TOL):
                pairs += 1
                left = GAP - h - bh
                key = (f.GetReference(), bref)
                worst[key] = (left, h, bh, fp_name(f), bfp)
                if left < MARGIN:
                    fails.append(f"{f.GetReference()} ({fp_name(f)}, {h} mm) over {bref} ({bfp}, {bh} mm): "
                                 f"{left:.2f} mm left")
    print(f"check_heights: baseboard mapped through J11/J12 (fit {err * 1000:.1f} um); gap {GAP} mm, margin {MARGIN} mm")
    print(f"  {len(under)} baseboard parts under the card, {pairs} overlapping pairs")
    tight = sorted(worst.items(), key=lambda kv: kv[1][0])[:8]
    for (cr, br), (left, h, bh, cf, bf) in tight:
        print(f"  {cr:6s} {h:.2f} + {br:5s} {bh:.2f} -> {left:.2f} mm left   ({cf} over {bf})")
    print("  heatsink push-pins (a barb below the card must clear these):")
    for hr in ("H1", "H2"):
        p = card.FindFootprintByReference(hr).GetPosition()
        hx, hy = mm(p.x), mm(p.y)
        near = [(bref, bh, math.hypot(max(br[0] - hx, hx - br[2], 0), max(br[1] - hy, hy - br[3], 0)))
                for bref, bfp, bh, br in under]
        near = sorted((n for n in near if n[2] < BARB_R), key=lambda n: n[2])
        txt = ", ".join(f"{b} {h} mm at {d:.1f} mm" for b, h, d in near) or "nothing"
        room = GAP - max((h for _, h, d in near if d == 0), default=0)
        print(f"    {hr} ({hx:.2f}, {hy:.2f}): within {BARB_R} mm: {txt}; room below the card {room:.2f} mm")
    for ref, fpn, val, r in other:
        inside = overlap(r, outline, 0)
        print(f"  not a small SMD part: {ref} {fpn} ({val}) at x {r[0]:.1f}..{r[2]:.1f}, y {r[1]:.1f}..{r[3]:.1f}"
              f" - {'UNDER the card' if inside else 'outside the outline'}")
    for m in sorted(missing):
        fails.append(f"no height for the card footprint {m} (CARD_H)")
    for f in fails:
        print("  FAIL", f)
    print(f"check_heights: {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
