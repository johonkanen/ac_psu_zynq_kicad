#!/usr/bin/env python3
"""Block edit E1 (REUSE_LOG.md): lengthen the DDR3 CK pair in its In2 trunk (kipy; tools/p2k/bin/kipy tools/block_e1.py
[BOARD]). tools/build_pcb.sh --rebuild runs it right after tools/import_block.py.

Targets (DDR3_REVIEW.md, from tools/ddr3_review.py): CK_P +4.30 mm, CK_N +3.23 mm, which gives CK = DQS0 + 25 ps and
CK P/N matched. The trunk runs north from U20 on In2 (P left at x = U20 - 0.804, N right at - 0.600; pitch 0.204 mm):
1. **Coupled meander** in its 5 mm straight run (y = U20 -16.4 ... -11.5): the pair's centreline makes a serpentine of
   horizontal rungs at a 0.5 mm pitch (juliancoy's own CK meander, just north of it, is drawn the same way at 0.6), corners
   cut at 45 deg; P and N are its offsets at +-0.102 mm, so the pair stays coupled. The amplitude is solved so CK_N gains
   exactly 3.23 mm.
2. **P-only bump** on the free (west) side of CK_P in the short straight run north of his meander (y = U20 -24 ...
   -21.6), sized so CK_P gains exactly 4.30 mm: the skew fix (P/N was 7.1 ps, N longer).
Before anything is written, every new segment is checked against the other nets' copper on In2 (tracks, pads) and every
via, at the block's 0.102 mm clearance, and P against N at the same gap. Idempotent: refused if the CK trunk is not the
imported straight copper.
"""
import math
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")
mm, FM = pcbnew.ToMM, pcbnew.FromMM
W, H, CLR = 0.102, 0.102, 0.102          # track width, half the pair pitch, clearance (block rules)
ADD_P, ADD_N = 4.30, 3.23                # E1 targets, mm
PITCH, CH = 0.5, 0.15                    # rung pitch (0.19 mm between rungs), corner cut on the centreline
# in mm from U20 (rotation 0): the two straight runs, as imported
P_X, N_X = -0.804, -0.600
RUN1 = (-16.35, -11.65)                  # coupled meander window inside the straight run y -16.4 ... -11.5
RUN2 = (-23.70, -22.10)                  # P bump window inside P's straight run y -24.15 ... -21.6

b = pcbnew.LoadBoard(BOARD)
u20 = b.FindFootprintByReference("U20")
# pose rotation 0: U20 as on juliancoy's board (-90 deg); the offsets below are board-frame mm from U20
assert abs((u20.GetOrientationDegrees() + 90) % 360) < 1e-6, "block_e1: written for the block at rotation 0 (pose A)"
UX, UY = mm(u20.GetPosition().x), mm(u20.GetPosition().y)
In2 = pcbnew.In2_Cu
netP, netN = b.FindNet("DDR3_CK_P"), b.FindNet("DDR3_CK_N")


def straight(net, x, y0, y1):
    """The one In2 segment of `net` on x that spans y0..y1 (board mm)."""
    hits = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == In2
            and t.GetNetCode() == net.GetNetCode() and abs(mm(t.GetStart().x) - x) < 1e-3
            and abs(mm(t.GetEnd().x) - x) < 1e-3
            and min(mm(t.GetStart().y), mm(t.GetEnd().y)) < y0 and max(mm(t.GetStart().y), mm(t.GetEnd().y)) > y1]
    if len(hits) != 1:
        sys.exit(f"block_e1: {net.GetNetname()} has no single straight segment on x {x:.3f} over y {y0:.2f}..{y1:.2f}"
                 " (already edited, or not the imported block)")
    return hits[0]


def chamfer(pts, ch):
    """Cut each corner of a polyline by `ch` along both legs."""
    out = [pts[0]]
    for a, c, d in zip(pts, pts[1:], pts[2:]):
        u = (c[0] - a[0], c[1] - a[1]); lu = math.hypot(*u)
        v = (d[0] - c[0], d[1] - c[1]); lv = math.hypot(*v)
        k = min(ch, lu / 2, lv / 2)
        out += [(c[0] - u[0] / lu * k, c[1] - u[1] / lu * k), (c[0] + v[0] / lv * k, c[1] + v[1] / lv * k)]
    out.append(pts[-1])
    return [p for i, p in enumerate(out) if i == 0 or math.hypot(p[0] - out[i - 1][0], p[1] - out[i - 1][1]) > 1e-9]


def offset(pts, d):
    """Offset a polyline by d to the left of travel (y down: rotate the direction by +90 deg), mitred corners."""
    lines = []
    for a, c in zip(pts, pts[1:]):
        dx, dy = c[0] - a[0], c[1] - a[1]; L = math.hypot(dx, dy)
        nx, ny = dy / L, -dx / L                 # left of travel in a y-down frame
        lines.append(((a[0] + nx * d, a[1] + ny * d), (c[0] + nx * d, c[1] + ny * d)))
    out = [lines[0][0]]
    for (p1, p2), (q1, q2) in zip(lines, lines[1:]):
        r = (p2[0] - p1[0], p2[1] - p1[1]); s = (q2[0] - q1[0], q2[1] - q1[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            out.append(p2)
            continue
        t = ((q1[0] - p1[0]) * s[1] - (q1[1] - p1[1]) * s[0]) / den
        out.append((p1[0] + r[0] * t, p1[1] + r[1] * t))
    return out + [lines[-1][1]]


def length(pts):
    return sum(math.hypot(c[0] - a[0], c[1] - a[1]) for a, c in zip(pts, pts[1:]))


LEAD = 0.2                               # straight centreline at each end, so the offsets meet the straight copper


def serpentine(cx, y0, y1, amp):
    """Centreline from (cx, y0) down to (cx, y1): rungs at PITCH, swinging to cx -+ amp."""
    n = int((y1 - y0 - 2 * LEAD) / PITCH)
    y, side = y0 + LEAD, -1
    pts = [(cx, y0), (cx, y)]
    pts.append((cx + side * amp, y))
    for _ in range(n - 1):
        y += PITCH
        pts.append((cx + side * amp, y))
        side = -side
        pts.append((cx + side * amp, y))
    y += PITCH
    pts.append((cx + side * amp, y))
    pts.append((cx, y))
    pts.append((cx, y1))
    return chamfer(pts, CH)


cx = UX + (P_X + N_X) / 2
y0, y1 = UY + RUN1[0], UY + RUN1[1]
# drawn going +y (south); offset() puts +H on +x there: N (east) is +H, P (west) is -H
lo, hi = 0.05, 0.6
for _ in range(60):                      # solve the amplitude for CK_N's +3.23 mm
    amp = (lo + hi) / 2
    c = serpentine(cx, y0, y1, amp)
    addN = length(offset(c, +H)) - (y1 - y0)
    lo, hi = (amp, hi) if addN < ADD_N else (lo, amp)
cl = serpentine(cx, y0, y1, amp)
Npts, Ppts = offset(cl, +H), offset(cl, -H)
assert abs(Npts[0][0] - (UX + N_X)) < 1e-6 and abs(Ppts[0][0] - (UX + P_X)) < 1e-6, "offset sides"
addN1, addP1 = length(Npts) - (y1 - y0), length(Ppts) - (y1 - y0)

# P bump: west of P, rectangular with cut corners, sized for the rest of +4.30
need = ADD_P - addP1
px, b0, b1 = UX + P_X, UY + RUN2[0], UY + RUN2[1]
bw = 0.5                                  # the bump's extent along the run
lo, hi = 0.05, 1.0
for _ in range(60):
    e = (lo + hi) / 2
    yb = (b0 + b1) / 2 - bw / 2
    bump = chamfer([(px, b0), (px, yb), (px - e, yb), (px - e, yb + bw), (px, yb + bw), (px, b1)], CH)
    add = length(bump) - (b1 - b0)
    lo, hi = (e, hi) if add < need else (lo, e)
addP2 = length(bump) - (b1 - b0)

# clearance check against everything else on In2 and every via
def seg_seg(a, c, p, q):
    def pt_seg(pt, s0, s1):
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]; l2 = dx * dx + dy * dy
        t = 0 if l2 == 0 else max(0, min(1, ((pt[0] - s0[0]) * dx + (pt[1] - s0[1]) * dy) / l2))
        return math.hypot(pt[0] - s0[0] - t * dx, pt[1] - s0[1] - t * dy)
    return min(pt_seg(a, p, q), pt_seg(c, p, q), pt_seg(p, a, c), pt_seg(q, a, c))


segP1 = straight(netP, UX + P_X, y0, y1)
segN1 = straight(netN, UX + N_X, y0, y1)
segP2 = straight(netP, px, b0, b1)
new = [(netP, Ppts), (netN, Npts), (netP, bump)]
obst = []
for t in b.GetTracks():
    if t.GetNetCode() in (netP.GetNetCode(), netN.GetNetCode()):
        continue
    if t.GetClass() == "PCB_VIA":
        p = (mm(t.GetPosition().x), mm(t.GetPosition().y))
        obst.append((p, p, mm(t.GetWidth(In2)) / 2, t.GetNetname()))
    elif t.GetLayer() == In2:
        obst.append(((mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y)),
                     mm(t.GetWidth()) / 2, t.GetNetname()))
for f in b.GetFootprints():
    for pd in f.Pads():
        if pd.IsOnLayer(In2) and pd.GetNetCode() not in (netP.GetNetCode(), netN.GetNetCode()):
            p = (mm(pd.GetPosition().x), mm(pd.GetPosition().y))
            obst.append((p, p, mm(max(pd.GetSize().x, pd.GetSize().y)) / 2, pd.GetNetname()))
worst = (9, "")
for net, pts in new:
    for a, c in zip(pts, pts[1:]):
        for p, q, r, n in obst:
            if min(abs(p[0] - a[0]), abs(p[0] - c[0])) > 2 or min(abs(p[1] - a[1]), abs(p[1] - c[1])) > 2:
                continue
            d = seg_seg(a, c, p, q) - r - W / 2
            if d < worst[0]:
                worst = (d, f"{net.GetNetname()} to {n}")
pn = min(seg_seg(a, c, p, q) for a, c in zip(Ppts, Ppts[1:]) for p, q in zip(Npts, Npts[1:])) - W
if worst[0] < CLR - 1e-4 or pn < CLR - 1e-4:
    sys.exit(f"block_e1: amplitude {amp:.3f}: clearance {worst[0]:.3f} mm ({worst[1]}), P-N gap {pn:.3f} mm < {CLR}: "
             "nothing written")


def replace(seg, ya, yb, pts):
    """Split `seg` at ya/yb (its own x), drop the middle, add `pts` between."""
    x = mm(seg.GetStart().x)
    s, e = sorted((mm(seg.GetStart().y), mm(seg.GetEnd().y)))
    net, lay = seg.GetNet(), seg.GetLayer()
    b.Remove(seg)
    for a, c in [((x, s), (x, ya)), ((x, yb), (x, e))] + list(zip(pts, pts[1:])):
        if math.hypot(c[0] - a[0], c[1] - a[1]) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
        t.SetWidth(FM(W))
        t.SetLayer(lay)
        t.SetNet(net)
        b.Add(t)


replace(segP1, y0, y1, Ppts)
replace(segN1, y0, y1, Npts)
replace(segP2, b0, b1, bump)
pcbnew.SaveBoard(BOARD, b)
print(f"block_e1: coupled meander y {y0:.2f}..{y1:.2f}, amplitude {amp:.3f} mm ({len(cl) - 1} centreline segments): "
      f"CK_N +{addN1:.3f}, CK_P +{addP1:.3f} mm; P bump {e:.3f} mm west at y {b0:.2f}..{b1:.2f}: CK_P +{addP2:.3f} mm "
      f"-> CK_P +{addP1 + addP2:.3f}, CK_N +{addN1:.3f} mm. Clearance {worst[0]:.3f} mm ({worst[1]}), P-N gap {pn:.3f}")
