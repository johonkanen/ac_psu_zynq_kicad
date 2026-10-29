#!/usr/bin/env python3
"""Put parts at the nearest free spot to a target, clear of the real copper (kipy):
    tools/p2k/bin/kipy tools/place_free.py IN OUT [--clear-vias] SPEC [SPEC ...]

Ported from the Ti135 card (its place_free.py, B.Cu decaps under its BGA), for both sides. SPEC is
    REF[@TARGET][:SIDE][/RMAX]
- TARGET: X,Y or X,Y,ROT (a point, mm; ROT fixes the orientation), or REF2.PAD (that pad); without it, the pads of the
  U-parts that share REF's signal net (its non-GND net that is not a rail), else U20's balls on REF's rail. So a decap
  goes as close to its rail's balls as there is room, and a strap next to its ball.
- SIDE: F or B (default B); RMAX: the search radius in mm (default 8).
Parts are placed in the order given (put the small ones that need the best spots first), each tried at 0.05 mm steps
outward from its target(s), at 0/90/180/270 deg (or ROT), until it clears, on its side: other nets' via copper 0.1 mm
and via holes 0.175 mm (vias are through, so they count on both sides), tracks and pads 0.1 mm, other courtyards
(through-hole parts count on both sides), 0.5 mm from the board edge, the 3 mm heatsink rings at H1/H2 (both sides)
the `ddr3_block` area: on F all of it (the block parts and the heatsink base: nothing of ours on top), on B all but
U20's courtyard (our decaps and straps go under U20 between the block's vias; the rest is the DDR, which keeps
switching and clock parts 2.5 mm away: LAYOUT_PLAN.md step 4). No copper is moved; zones are refilled
afterwards (they flow around the new pads).
--clear-vias: also no via (any net) inside the part's courtyard, so nothing sits on top of a via (a BGA's fan-out
vias under its package: the parts go beside the via field, not over it).
"""
import math
import sys

import pcbnew

mm, FM = pcbnew.ToMM, pcbnew.FromMM
CLR, HOLE_CLR, EDGE, MARGIN, STEP, RING = 0.1, 0.175, 0.5, 0.0005, 0.05, 3.0
RAILS = {"GND", "1V0", "1V8", "1V35", "3V3", "5V0", "3V3_analog", "DDR3_VTT", "/05 soc_power/VCCAUX",
         "/05 soc_power/VCCPLL"}

b = pcbnew.LoadBoard(sys.argv[1])
CLEAR_VIAS = "--clear-vias" in sys.argv[3:]
specs = [a for a in sys.argv[3:] if a != "--clear-vias"]
fps = {f.GetReference(): f for f in b.GetFootprints()}
eb = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = mm(eb.GetLeft()), mm(eb.GetTop()), mm(eb.GetRight()), mm(eb.GetBottom())
blk = next(z for z in b.Zones() if z.GetZoneName() == "ddr3_block").GetBoundingBox()
BLOCK = (mm(blk.GetLeft()), mm(blk.GetTop()), mm(blk.GetRight()), mm(blk.GetBottom()))
HOLES = [(mm(fps[h].GetPosition().x), mm(fps[h].GetPosition().y)) for h in ("H1", "H2")]
copper = lambda f: [p for p in f.Pads() if p.GetNumber() and p.IsOnCopperLayer()]
tht = lambda f: any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads())


def rect(bb):
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


U20 = rect(fps["U20"].GetCourtyard(pcbnew.F_CrtYd).BBox())


def court(f):
    bb = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
    return rect(bb) if bb.GetWidth() else rect(f.GetBoundingBox(False))


def rect_dist(r, s):
    dx = max(r[0] - s[2], s[0] - r[2], 0)
    dy = max(r[1] - s[3], s[1] - r[3], 0)
    return math.hypot(dx, dy)


def seg_rect(r, ax, ay, bx, by):
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.05))
    return min(rect_dist(r, (ax + (bx - ax) * i / n, ay + (by - ay) * i / n) * 2) for i in range(n + 1))


moving = {s.split("@")[0].split(":")[0].split("/")[0] for s in specs}
SIDES = (pcbnew.F_Cu, pcbnew.B_Cu)
vias = []
tracks = {lay: [] for lay in SIDES}
pads = {lay: [] for lay in SIDES}
courts = {lay: [] for lay in SIDES}
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        vias.append((mm(t.GetPosition().x), mm(t.GetPosition().y), t.GetNetCode(),
                     mm(t.GetWidth(pcbnew.F_Cu)) / 2 + CLR, mm(t.GetDrillValue()) / 2 + HOLE_CLR))
    elif t.GetLayer() in SIDES:
        tracks[t.GetLayer()].append((mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y),
                                     t.GetNetCode(), mm(t.GetWidth()) / 2 + CLR))


VGRID = {}
for v in vias:
    VGRID.setdefault((int(v[0] // 1), int(v[1] // 1)), []).append(v)


def vias_near(r):
    for i in range(int(r[0] // 1) - 1, int(r[2] // 1) + 2):
        for j in range(int(r[1] // 1) - 1, int(r[3] // 1) + 2):
            yield from VGRID.get((i, j), ())


def add_footprint(f):
    for p in copper(f):
        for lay in SIDES:
            if p.IsOnLayer(lay):
                pads[lay].append((rect(p.GetBoundingBox()), p.GetNetCode()))
    for lay in SIDES:
        if tht(f) or (lay == pcbnew.B_Cu) == f.IsFlipped():
            courts[lay].append(court(f))


for f in b.GetFootprints():
    if f.GetReference() not in moving:
        add_footprint(f)


def fits(f):
    lay = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
    cf = court(f)
    if cf[0] < EX0 + EDGE or cf[1] < EY0 + EDGE or cf[2] > EX1 - EDGE or cf[3] > EY1 - EDGE:
        return False
    if cf[0] < BLOCK[2] and BLOCK[0] < cf[2] and cf[1] < BLOCK[3] and BLOCK[1] < cf[3]:
        inside_u20 = U20[0] <= cf[0] and cf[2] <= U20[2] and U20[1] <= cf[1] and cf[3] <= U20[3]
        if lay == pcbnew.F_Cu or not inside_u20:
            return False
    if any(rect_dist(cf, (hx, hy, hx, hy)) < RING for hx, hy in HOLES):
        return False
    for oc in courts[lay]:
        if cf[0] < oc[2] and oc[0] < cf[2] and cf[1] < oc[3] and oc[1] < cf[3]:
            return False
    if CLEAR_VIAS and any(rect_dist(cf, (x, y, x, y)) < dc - CLR + MARGIN for x, y, n, dc, dh in vias_near(cf)):
        return False
    for p in copper(f):
        pr = rect(p.GetBoundingBox())
        net = p.GetNetCode()
        for x, y, n, dc, dh in vias_near(pr):
            if n != net:
                d = rect_dist(pr, (x, y, x, y))
                if d < dc + MARGIN or d < dh + MARGIN:
                    return False
        for ax, ay, bx, by, n, dc in tracks[lay]:
            if n == net or min(ax, bx) > pr[2] + 1 or max(ax, bx) < pr[0] - 1 \
                    or min(ay, by) > pr[3] + 1 or max(ay, by) < pr[1] - 1:
                continue
            if seg_rect(pr, ax, ay, bx, by) < dc + MARGIN:
                return False
        for q, n in pads[lay]:
            if n != net and rect_dist(pr, q) < CLR + MARGIN:
                return False
    return True


def targets(f, tgt):
    if tgt and "." in tgt and not tgt.replace(".", "").replace(",", "").replace("-", "").isdigit():
        r2, pad = tgt.split(".", 1)
        p = next(q for q in fps[r2].Pads() if q.GetNumber() == pad)
        return [(mm(p.GetPosition().x), mm(p.GetPosition().y))], None
    if tgt:
        v = [float(a) for a in tgt.split(",")]
        return [(v[0], v[1])], ([v[2]] if len(v) > 2 else None)
    nets = [p.GetNetname() for p in copper(f) if p.GetNetname() and p.GetNetname() != "GND"]
    sig = [n for n in nets if n not in RAILS]
    if sig:
        pts = [(mm(q.GetPosition().x), mm(q.GetPosition().y)) for o in b.GetFootprints()
               if o.GetReference()[0] == "U" and o.GetReference() != f.GetReference()
               for q in o.Pads() if q.GetNetname() in sig]
        if pts:
            return pts, None
    pts = [(mm(q.GetPosition().x), mm(q.GetPosition().y)) for q in fps["U20"].Pads() if q.GetNetname() in nets]
    if not pts:
        sys.exit(f"place_free: {f.GetReference()}: no target found; give one")
    return pts, None


done = []
for spec in specs:
    head, rmax = (spec.split("/") + ["8"])[:2] if "/" in spec else (spec, "8")
    head, side = (head.split(":") + ["B"])[:2] if ":" in head else (head, "B")
    ref, tgt = (head.split("@") + [""])[:2] if "@" in head else (head, "")
    rmax = float(rmax)
    f = fps[ref]
    if f.IsFlipped() != (side == "B"):
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    pts, rots = targets(f, tgt)
    rots = rots or [0, 90, 180, 270]
    cand = {}
    for px, py in pts:
        for i in range(-int(rmax / STEP), int(rmax / STEP) + 1):
            for j in range(-int(rmax / STEP), int(rmax / STEP) + 1):
                x, y = round(round(px / STEP) * STEP + i * STEP, 3), round(round(py / STEP) * STEP + j * STEP, 3)
                d = math.hypot(x - px, y - py)
                if d <= rmax and d < cand.get((x, y), 1e9):
                    cand[(x, y)] = d
    ok = False
    for (x, y), d in sorted(cand.items(), key=lambda kv: kv[1]):
        for rot in rots:
            f.SetOrientationDegrees(rot)
            f.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
            if fits(f):
                ok = True
                break
        if ok:
            break
    if not ok:
        sys.exit(f"place_free: no free spot within {rmax} mm for {ref} ({side})")
    add_footprint(f)
    done.append(f"{ref} {side} ({x:.2f}, {y:.2f}) {rot:g} deg, {d:.2f} mm from its target")
    print("  " + done[-1], flush=True)
pcbnew.SaveBoard(sys.argv[2], b)
print(f"place_free: {len(done)} parts placed")
