#!/usr/bin/env python3
"""Tie loose supply pads to their planes with a via each (kipy), ported from the Ti135 card's decap_connect.py:

    plane_vias.py IN.kicad_pcb OUT.kicad_pcb DRC.json [--dry] [--stitch PITCH]

--stitch PITCH (mm): first, a GND via at every point of a PITCH grid where the F.Cu or B.Cu ground pour has copper
and the via is legal on every layer; not in the DDR area nor under U20 (the block has its own), nor under the jack.
This ties the pieces of the outer ground pours to In1/In3/In5.

Every SMD pad on GND or a plane rail that kicad-cli's DRC report (JSON, zones filled) lists as unconnected gets, in
this order:
  1. a via in the pad if the site is legal on every layer and, for a rail pad, lies on the rail's pour on its plane
     layer (PLANE below; GND reaches In1/In3/In5 anywhere but under the jack). Pads of 0805 and larger get two;
  2. a straight track to a via of the same net within 0.9 mm;
  3. a new via within 0.9 mm (or between four balls of U20 / U1001 within 1.3 mm) and a track to it;
  4. a straight track to a via of the same net within 2.5 mm;
  5. a two-segment track (0.2 mm, else 0.15 mm) to a via of the same net within 4 mm.
A pad with none of these is reported and left open. Legal = 0.102 mm to foreign copper on the layers the item is
on, 0.2 mm from a hole to foreign copper, 0.25 mm hole to hole. Zones are refilled at the end. tools/route.sh runs it
in a loop with DRC until nothing changes: a pour island with several pads needs only the first of them tied.
"""
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
PLANE = {"3V3": ["In6.Cu"], "1V8": ["In4.Cu", "In2.Cu"], "1V0": ["In6.Cu"], "1V35": ["F.Cu", "B.Cu"], "5V0": ["B.Cu"]}
CLR, HOLE, H2H = 0.102, 0.2, 0.25
VIA, DRILL, TRK = 0.3, 0.15, 0.2

b = pcbnew.LoadBoard(sys.argv[1])
dry = "--dry" in sys.argv
import json
import re
listed = set()
for x in json.load(open(sys.argv[3]))["unconnected_items"]:
    for i in x["items"]:
        m = re.match(r"(?:PTH pad|Pad) (\S+) \[[^\]]*\] of (\S+)", i["description"])
        if m:
            listed.add((m.group(2), m.group(1)))
every = True
zones = {}
for z in b.Zones():
    for l in z.GetLayerSet().Seq():
        zones.setdefault((z.GetNetname(), pcbnew.LayerName(l)), []).append((z, l))
items = []     # kind, geometry, net code, layer name or None (= all layers), drill radius (vias)


def add_item(t):
    if isinstance(t, pcbnew.PCB_VIA):
        q = t.GetPosition()
        items.append(("circle", (MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.B_Cu)) / 2), t.GetNetCode(), None, MM(t.GetDrill()) / 2))
    else:
        arc = isinstance(t, pcbnew.PCB_ARC)                  # two chords through the mid point, a little fatter
        pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if arc else [t.GetStart(), t.GetEnd()]
        for a, c in zip(pts, pts[1:]):
            items.append(("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2 + (0.05 if arc else 0)),
                          t.GetNetCode(), pcbnew.LayerName(t.GetLayer()), 0))


for f in b.GetFootprints():
    for p in f.Pads():
        if not p.IsOnCopperLayer():                           # the 0201 footprint's paste-only pads
            continue
        bb = p.GetBoundingBox()
        through = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
        items.append(("rect", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(),
                      None if through else pcbnew.LayerName(f.GetLayer()), 0))
for t in b.GetTracks():
    add_item(t)


def gap(kind, g, x, y):
    if kind == "rect":
        return math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3]))
    if kind == "circle":
        return math.hypot(x - g[0], y - g[1]) - g[2]
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def via_ok(p, code):
    need = max(VIA / 2 + CLR, DRILL / 2 + HOLE) - 1e-6
    for k, g, n, lay, dr in items:
        d = gap(k, g, p[0], p[1])
        if n != code and d < need:
            return False
        if k == "circle" and d + g[2] < dr + DRILL / 2 + H2H - 1e-6:          # hole to hole, any net
            return False
        if k == "rect" and lay is None and d < DRILL / 2 + H2H:               # a through-hole pad's drill
            return False
    pt = pcbnew.VECTOR2I(FM(p[0]), FM(p[1]))
    if any(z.Outline().Contains(pt) for z in NO_VIA):                         # heatsink pins, keep-outs
        return False
    return True


def seg_ok(a, c, code, layer, w=TRK):
    n_s = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.04))
    need = w / 2 + CLR - 1e-6
    for i in range(n_s + 1):
        x, y = a[0] + (c[0] - a[0]) * i / n_s, a[1] + (c[1] - a[1]) * i / n_s
        for k, g, n, lay, dr in items:
            if n != code and lay in (None, layer) and gap(k, g, x, y) < need:
                return False
    return True


def on_plane(net, p, own=None):
    if net == "GND":
        return not (J9[0] < p[0] < J9[2] and J9[1] < p[1] < J9[3])
    for lay in PLANE[net]:
        if lay == own:
            continue
        for z, l in zones.get((net, lay), []):
            if all(z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(p[0] + dx), FM(p[1] + dy))) for dx, dy in ((0, 0), (.15, 0), (-.15, 0), (0, .15), (0, -.15))):
                return True
    return False


def has_copper(p, f):
    """A track end, a via or a pour of the pad's net on the pad."""
    for t in b.GetTracks():
        if t.GetNetCode() != p.GetNetCode():
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            if p.HitTest(t.GetPosition()):
                return True
        elif t.IsOnLayer(f.GetLayer()) and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())):
            return True
    return False        # a pour on the pad does not count: the DRC report says the pad is not connected


def mk_via(p, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(p[0]), FM(p[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FM(VIA)); v.SetDrill(FM(DRILL)); v.SetNet(net); b.Add(v)
    items.append(("circle", (p[0], p[1], VIA / 2), net.GetNetCode(), None, DRILL / 2))


def mk_trk(a, c, net, layer, w=TRK):
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
    t.SetWidth(FM(w)); t.SetLayer(layer); t.SetNet(net); b.Add(t)
    items.append(("seg", (a[0], a[1], c[0], c[1], w / 2), net.GetNetCode(), pcbnew.LayerName(layer), 0))


J9 = (189.8, 52.8, 208.0, 70.4)       # j9_no_pour: no plane under the jack
NO_VIA = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
bga_sites = []                                           # centres between four balls of the 0.8 mm BGAs
for ref in ("U20", "U1001"):
    pts = sorted({(round(MM(p.GetPosition().x), 3), round(MM(p.GetPosition().y), 3)) for p in b.FindFootprintByReference(ref).Pads()})
    xs = sorted({q[0] for q in pts}); ys = sorted({q[1] for q in pts})
    px = min(round(c2 - c1, 3) for c1, c2 in zip(xs, xs[1:])); py = min(round(c2 - c1, 3) for c1, c2 in zip(ys, ys[1:]))
    bga_sites += [(x + px / 2, y + py / 2) for x in [xs[0] - px] + xs for y in [ys[0] - py] + ys]

if "--stitch" in sys.argv:
    pitch = float(sys.argv[sys.argv.index("--stitch") + 1])
    gnd = b.FindNet("GND")
    eb = b.GetBoardEdgesBoundingBox()
    ucy = b.FindFootprintByReference("U20").GetCourtyard(pcbnew.F_CrtYd).BBox()
    skip = [(147.5, 52.3, 179.5, 77.3), (MM(ucy.GetLeft()), MM(ucy.GetTop()), MM(ucy.GetRight()), MM(ucy.GetBottom())), J9]
    n, y = 0, MM(eb.GetTop()) + 1.0
    while y < MM(eb.GetBottom()) - 0.9:
        x = MM(eb.GetLeft()) + 1.0
        while x < MM(eb.GetRight()) - 0.9:
            q = (x, y)
            if not any(r[0] < x < r[2] and r[1] < y < r[3] for r in skip) and via_ok(q, gnd.GetNetCode()) and any(
                    z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(x + dx), FM(y + dy)))
                    for lay in ("F.Cu", "B.Cu") for z, l in zones.get(("GND", lay), [])
                    for dx, dy in ((0, 0),)):
                mk_via(q, gnd); n += 1
            x += pitch
        y += pitch
    print(f"plane_vias: {n} GND stitching vias on a {pitch} mm grid")
    # every piece of an outer ground pour that still has no via (a sliver between tracks, a patch round one pad):
    # the first legal site inside it, anywhere on the board
    vias = [(g[0], g[1]) for k, g, nc, lay, dr in items if k == "circle" and nc == gnd.GetNetCode()]
    m, none = 0, 0
    for lay in ("F.Cu", "B.Cu"):
        for z, l in zones.get(("GND", lay), []):
            ps = z.GetFilledPolysList(l)
            for i in range(ps.OutlineCount()):
                if any(ps.Contains(pcbnew.VECTOR2I(FM(vx), FM(vy)), i) for vx, vy in vias):
                    continue
                bb = ps.Outline(i).BBox()
                site, yy = None, MM(bb.GetTop()) + 0.2
                while site is None and yy < MM(bb.GetBottom()):
                    xx = MM(bb.GetLeft()) + 0.2
                    while xx < MM(bb.GetRight()):
                        if all(ps.Contains(pcbnew.VECTOR2I(FM(xx + dx), FM(yy + dy)), i) for dx, dy in ((0, 0), (.2, 0), (-.2, 0), (0, .2), (0, -.2))) \
                                and via_ok((xx, yy), gnd.GetNetCode()):
                            site = (xx, yy)
                            break
                        xx += 0.15
                    yy += 0.15
                if site:
                    mk_via(site, gnd); vias.append(site); m += 1
                else:                   # no room in the piece itself: its pads go through the pad rules below
                    none += 1
                    for f in b.GetFootprints():
                        if pcbnew.LayerName(f.GetLayer()) == lay:
                            for q in f.Pads():
                                if q.GetNetname() == "GND" and ps.Contains(q.GetPosition(), i):
                                    listed.add((f.GetReference(), q.GetNumber()))
    print(f"plane_vias: {m} more for pour pieces without a via; {none} pieces have no legal site")

todo = []
for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    if every:
        for p in f.Pads():
            if p.GetNumber() and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and (p.GetNetname() == "GND" or p.GetNetname() in PLANE) \
                    and (f.GetReference(), p.GetNumber()) in listed and not has_copper(p, f):
                todo.append((f, p))
        continue
    if not f.GetReference().startswith("C"):
        continue
    pads = [p for p in f.Pads() if p.GetNumber()]
    nets = {p.GetNetname() for p in pads}
    if len(pads) != 2 or "GND" not in nets or not (nets & set(PLANE) or f.GetReference() in also_gnd):
        continue
    for p in pads:
        if (p.GetNetname() == "GND" or p.GetNetname() in PLANE) and not has_copper(p, f):
            todo.append((f, p))
# anchors for rule 3: vias on their plane, of each net
anchors = {}
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA) and (t.GetNetname() in PLANE or t.GetNetname() == "GND"):
        q = (MM(t.GetPosition().x), MM(t.GetPosition().y))
        anchors.setdefault(t.GetNetname(), []).append(q)
how, left = {"in pad": [], "beside": [], "track": [], "dogleg": []}, []
for f, p in todo:
    net, name, lay = p.GetNet(), p.GetNetname(), f.GetLayer()
    c = (MM(p.GetPosition().x), MM(p.GetPosition().y))
    bb = p.GetBoundingBox(); hx, hy = MM(bb.GetWidth()) / 2, MM(bb.GetHeight()) / 2
    big = max(hx, hy) > 0.45
    sites = [c] if not big else ([(c[0], c[1] - 0.36), (c[0], c[1] + 0.36)] if hy > hx else [(c[0] - 0.36, c[1]), (c[0] + 0.36, c[1])])
    sites += [(c[0] + dx * 0.05, c[1] + dy * 0.05) for dx in range(-3, 4) for dy in range(-3, 4)
              if abs(dx * 0.05) <= hx - 0.05 and abs(dy * 0.05) <= hy - 0.05]
    done = 0
    for s in sites:
        if done < (2 if big else 1) and via_ok(s, net.GetNetCode()) and on_plane(name, s, pcbnew.LayerName(lay)):
            mk_via(s, net); done += 1
    if done:
        how["in pad"].append(f"{f.GetReference()}.{p.GetNumber()}"); continue
    near = sorted((math.hypot(a[0] - c[0], a[1] - c[1]), a) for a in anchors.get(name, []))

    def to_anchor(reach):
        for d, a in near:
            if d > reach:
                return False
            if seg_ok(c, a, net.GetNetCode(), pcbnew.LayerName(f.GetLayer())):
                mk_trk(c, a, net, lay); how["track"].append(f"{f.GetReference()}.{p.GetNumber()}"); return True
        return False

    if to_anchor(0.9):
        continue
    ring = [(c[0] + r * math.cos(a * math.pi / 12), c[1] + r * math.sin(a * math.pi / 12))
            for r in (0.45, 0.55, 0.65, 0.75, 0.9) for a in range(24)] + \
           [q for q in bga_sites if math.hypot(q[0] - c[0], q[1] - c[1]) < 1.3]
    ring.sort(key=lambda q: math.hypot(q[0] - c[0], q[1] - c[1]))
    ok = False
    for q in ring:
        if via_ok(q, net.GetNetCode()) and on_plane(name, q, pcbnew.LayerName(lay)) and seg_ok(c, q, net.GetNetCode(), pcbnew.LayerName(f.GetLayer())):
            mk_via(q, net); mk_trk(c, q, net, lay); anchors.setdefault(name, []).append(q)
            how["beside"].append(f"{f.GetReference()}.{p.GetNumber()}"); ok = True; break
    def dogleg(reach):
        """Two segments to a via of the net: axis-parallel then 45 degrees, or the other way round."""
        for w in (TRK, 0.15):
            for d, a in near:
                if d > reach:
                    break
                dx, dy = a[0] - c[0], a[1] - c[1]
                m = min(abs(dx), abs(dy)); sx, sy = math.copysign(1, dx), math.copysign(1, dy)
                for e in ((c[0] + sx * m, c[1] + sy * m), (a[0] - sx * m, a[1] - sy * m), (a[0], c[1]), (c[0], a[1])):
                    if seg_ok(c, e, net.GetNetCode(), pcbnew.LayerName(f.GetLayer()), w) and seg_ok(e, a, net.GetNetCode(), pcbnew.LayerName(f.GetLayer()), w):
                        mk_trk(c, e, net, lay, w); mk_trk(e, a, net, lay, w)
                        how["dogleg"].append(f"{f.GetReference()}.{p.GetNumber()}"); return True
        return False

    if not ok and not to_anchor(2.5) and not dogleg(4.0):
        nd = f"nearest {name} via {near[0][0]:.2f} mm" if near else "no via of the net"
        left.append(f"{f.GetReference()}.{p.GetNumber()} {name} ({c[0]:.1f}, {c[1]:.1f}) {pcbnew.LayerName(f.GetLayer())} {nd}")
print(f"decap_connect: {len(todo)} loose pads")
for k, v in how.items():
    print(f"  {k}: {len(v)}  {' '.join(v)}")
print(f"  left open: {len(left)}")
for l in left:
    print("   ", l)
if not dry:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(sys.argv[2], b)
