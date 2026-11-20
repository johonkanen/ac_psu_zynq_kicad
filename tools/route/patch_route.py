#!/usr/bin/env python3
"""Close single connections the router leaves open, with a small exact maze search (kipy):

    patch_route.py IN.kicad_pcb OUT.kicad_pcb [--dry] SPEC [SPEC ...]
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --auto DRC.json GROUP[,GROUP...]
        every unconnected pair of kicad-cli's DRC report (JSON) on a net of these groups (tools/route_groups.json),
        from the copper at one end to the copper at the other; width 0.3 mm for VCCPLL, 0.15 mm for the PHY supply
        nets, else 0.1 mm; with --tight every track is 0.09 mm at 0.1 mm clearance (for what a first run left)
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --nets GROUP[,GROUP...]
        the same without a report (kicad-cli lists 499 unconnected items at most, too few on a board that is not
        routed yet): the pads of each net are grouped by the copper that already joins them, and the groups are
        joined nearest pair first
        --rip: when a pair has no path, find which one or two of our own routed nets block it, lift them, route
        the pair, route the lifted nets again; if any of that fails, everything is put back as it was
    patch_route.py IN.kicad_pcb OUT.kicad_pcb [--keep-box X0,Y0,X1,Y1] --evict LAYER,LAYER:X0,Y0,X1,Y1 [--evict ...]
        our nets with tracks on these layers in the rectangle are routed again with it closed, one at a time
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --reroute NET,NET,...   lift these nets, join them again in this order
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --trim DRC.json BASE.kicad_pcb   dangling copper off, net by net, checked
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --orphans               delete copper of our nets that reaches no pad
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --repair DRC.json
        the nets of ours in clearance / hole violations are lifted and routed again here
    patch_route.py IN.kicad_pcb OUT.kicad_pcb --planes DRC.json
        every unconnected SMD pad of a supply net (GND and the rails of PLANE below) that tools/route/plane_vias.py
        could not tie: a 0.2 mm track from the pad to the nearest point where it meets its rail's pour, on its own
        layer, or where a via reaches the pour on the rail's plane layer (run on a board with the zones filled)
    SPEC = REF.PAD>REF.PAD[:WIDTH[:LAYERS[:VIA]]]      e.g.  U20.H10>C529.1:0.3:B.Cu,F.Cu   R609.2>U20.F8
           WIDTH mm (default 0.1); LAYERS a comma list (default F.Cu,In2.Cu,In4.Cu,In6.Cu,B.Cu);
           VIA 0.3/0.15 (default) or 0.48/0.25, or "none"

KiCadRoutingTools gives up on pads it calls boxed in (0.4 mm-pitch PHY pins, balls among dog-bones, parts under the
BGA). This searches a 0.025 mm grid around the two pads (their bounding box + MARGIN) on the given layers, 8 directions,
with the real geometry: every pad, track and via of another net is kept CLR away (pads by their bounding box), a via
needs HOLE from its drill to foreign copper on every layer and H2H to other holes, the board edge EDGE. The start pad's
own net is free to touch. It starts from the first pad or any copper already joined to it (a breakout stub, its via)
and ends on the second pad or the copper joined to that. Pours are
ignored (they are refilled around the result); the temporary keep-outs of the chain are honoured through --keepout
LAYER:X0,Y0,X1,Y1 (LAYER * = every layer, vias too). Each spec is routed in turn and added to the obstacles of the next. A spec without a
path is reported and left open (exit code 1 at the end).
"""
import heapq
import os
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
G, CLR, HOLE, H2H, EDGE, MARGIN = 0.025, 0.105, 0.2, 0.25, 0.5, 2.5
ALL = ["F.Cu", "In2.Cu", "In4.Cu", "In6.Cu", "B.Cu"]
COPPER = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu"]
PLANES = {"In1.Cu", "In3.Cu", "In5.Cu"}

args = sys.argv[1:]
dry = "--dry" in args
keepouts = []
while "--keepout" in args:
    i = args.index("--keepout")
    lay, r = args[i + 1].split(":")
    keepouts.append((lay, tuple(float(v) for v in r.split(","))))
    del args[i:i + 2]
TIGHT = "--tight" in args      # second try: 0.09 mm tracks at the board minimum clearance (0.1 mm)
if TIGHT:
    CLR = 0.1005
args = [a for a in args if a not in ("--dry", "--tight", "--rip")]
b = pcbnew.LoadBoard(args[0])
# the board's own rule areas that forbid tracks (the heatsink pins' rings on F.Cu/B.Cu): closed, by their bounding box
for _z in b.Zones():
    if _z.GetIsRuleArea() and _z.GetDoNotAllowTracks() and not _z.GetZoneName().startswith("ROUTE_TMP"):
        _bb = _z.GetBoundingBox()
        for _l in _z.GetLayerSet().Seq():
            keepouts.append((pcbnew.LayerName(_l), (MM(_bb.GetLeft()) - 0.2, MM(_bb.GetTop()) - 0.2, MM(_bb.GetRight()) + 0.2, MM(_bb.GetBottom()) + 0.2)))
if os.environ.get("PATCH_MARGIN"):
    MARGIN = float(os.environ["PATCH_MARGIN"])      # search window beyond the two ends, mm (a long way round)
eb = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = MM(eb.GetLeft()), MM(eb.GetTop()), MM(eb.GetRight()), MM(eb.GetBottom())
lid = {pcbnew.LayerName(l): l for l in b.GetEnabledLayers().CuStack()}

items = []      # (kind, geometry, net code, layer name or None = every layer, drill radius)


def add_track(t):
    if isinstance(t, pcbnew.PCB_VIA):
        q = t.GetPosition()
        items.append(("circle", (MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.F_Cu)) / 2), t.GetNetCode(), None, MM(t.GetDrill()) / 2, True))
    else:
        pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if isinstance(t, pcbnew.PCB_ARC) else [t.GetStart(), t.GetEnd()]
        for a, c in zip(pts, pts[1:]):
            items.append(("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2), t.GetNetCode(),
                          pcbnew.LayerName(t.GetLayer()), 0, True))


def pad_layer(p):
    """The copper layer of an SMD pad: its own, not its footprint's side (the PHY's thermal land on B.Cu belongs to
    a top-side footprint)."""
    return "B.Cu" if p.IsOnLayer(pcbnew.B_Cu) and not p.IsOnLayer(pcbnew.F_Cu) else "F.Cu"


def rebuild_items():
    """Every pad, track and via of the board as obstacles (the last field: a track or via, which --rip may lift)."""
    items.clear()
    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.IsOnCopperLayer() and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            bb = p.GetBoundingBox()
            through = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            dr = max(MM(p.GetDrillSize().x), MM(p.GetDrillSize().y)) / 2 if through else 0
            items.append(("rect", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(),
                          None if through else pad_layer(p), dr, False))
    for t in b.GetTracks():
        add_track(t)


rebuild_items()


def dist(kind, g, x, y):
    if kind == "pad":       # an end pad: inside its real shape (the connectivity wants the track end on the copper)
        return 0.0 if g[4].HitTest(pcbnew.VECTOR2I(FM(x), FM(y))) else 1.0
    if kind == "rect":
        return math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3]))
    if kind == "circle":
        return math.hypot(x - g[0], y - g[1]) - g[2]
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def bbox_of(kind, g):
    if kind in ("rect", "pad"):
        return g[:4]
    if kind == "circle":
        return (g[0] - g[2], g[1] - g[2], g[0] + g[2], g[1] + g[2])
    return (min(g[0], g[2]) - g[4], min(g[1], g[3]) - g[4], max(g[0], g[2]) + g[4], max(g[1], g[3]) + g[4])


def pad_of(spec):
    ref, num = spec.split(".")
    f = b.FindFootprintByReference(ref)
    p = next(q for q in f.Pads() if q.GetNumber() == num)
    bb = p.GetBoundingBox()
    through = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
    return p, (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), None if through else pcbnew.LayerName(f.GetLayer())


CONN = None
TYPED = {t.m_Uuid.AsString(): t for t in b.GetTracks()}


def geom(o):
    if o.GetClass() == "PAD":
        bb = o.GetBoundingBox()
        through = o.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
        return [("pad", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()), o),
                 None if through else pad_layer(o))]
    if o.GetClass() == "PCB_VIA":
        q = o.GetPosition()
        return [("circle", (MM(q.x), MM(q.y), 0.05), None)]
    o = TYPED.get(o.m_Uuid.AsString(), o)            # the connectivity hands arcs back as plain tracks
    pts = [o.GetStart(), o.GetMid(), o.GetEnd()] if isinstance(o, pcbnew.PCB_ARC) else [o.GetStart(), o.GetEnd()]
    return [("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), 0.0), pcbnew.LayerName(o.GetLayer())) for a, c in zip(pts, pts[1:])]


def island(pad, rect=None, layer=None):
    """Geometry of the item and of the pads, tracks and vias joined to it: [(kind, geometry, layer or None)]."""
    out, seen, todo = geom(pad), {pad.m_Uuid.AsString()}, [pad]
    while todo:
        it = todo.pop()
        for o in CONN.GetConnectedItems(it):
            u = o.m_Uuid.AsString()
            if u in seen or o.GetClass() not in ("PCB_TRACK", "PCB_VIA", "PCB_ARC", "PAD"):
                continue
            seen.add(u); todo.append(o); out += geom(o)
    return out


def route(spec):
    parts = spec.split(":")
    a_s, z_s = parts[0].split(">")
    width = float(parts[1]) if len(parts) > 1 and parts[1] else 0.1
    layers = parts[2].split(",") if len(parts) > 2 and parts[2] else ALL
    via = parts[3] if len(parts) > 3 else "0.3/0.15"
    pa, ra, la = pad_of(a_s)
    pz, rz, lz = pad_of(z_s)
    return connect(spec, pa, pz, ra, rz, width, layers, via)


_cy = b.FindFootprintByReference("U901").GetCourtyard(pcbnew.F_CrtYd).BBox()
PHY = (MM(_cy.GetLeft()), MM(_cy.GetTop()), MM(_cy.GetRight()), MM(_cy.GetBottom()))
MDI = {n.GetNetCode() for n in b.GetNetInfo().NetsByName().values() if "eth_mdi_" in n.GetNetname()}
PLANE = {"3V3": ["In6.Cu"], "1V8": ["In4.Cu", "In2.Cu"], "1V0": ["In6.Cu"], "1V35": ["F.Cu", "B.Cu"], "5V0": ["B.Cu"],
         "GND": ["In1.Cu", "In3.Cu", "In5.Cu"]}
ZONES = {}
for _z in b.Zones():
    if not _z.GetIsRuleArea():
        for _l in _z.GetLayerSet().Seq():
            ZONES.setdefault((_z.GetNetname(), pcbnew.LayerName(_l)), []).append((_z, _l))


# PATCH_REACH=1: a plane counts only where its pour is reached from the rail's regulator on that layer alone (a flood
# from the seed, as tools/route/plane_reach.py). Without it a pad may be "tied" to an island that signals fenced off.
SEEDS = {("3V3", "In6.Cu"): (195.5, 87.5), ("1V8", "In4.Cu"): (168.5, 103.5), ("1V0", "In6.Cu"): (153.5, 102.0),
         ("1V35", "B.Cu"): (196.5, 74.5)}
REACH = {}
RS = 0.1


def reach(net, layer):
    if (net, layer) not in REACH:
        import collections
        sx, sy = SEEDS[(net, layer)]
        zs = ZONES.get((net, layer), [])
        nx, ny = int((EX1 - EX0) / RS) + 1, int((EY1 - EY0) / RS) + 1
        filled = [bytearray(any(z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(EX0 + i * RS), FM(EY0 + j * RS))) for z, l in zs)
                            for i in range(nx)) for j in range(ny)]
        si, sj = int((sx - EX0) / RS), int((sy - EY0) / RS)
        assert filled[sj][si], (net, layer, "seed not on the pour")
        seen, q = {(si, sj)}, collections.deque([(si, sj)])
        while q:
            i, j = q.popleft()
            for a, c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < nx and 0 <= c < ny and filled[c][a] and (a, c) not in seen:
                    seen.add((a, c)); q.append((a, c))
        REACH[(net, layer)] = seen
        print(f"patch_route: {net} on {layer}: reach from the regulator computed ({len(seen)} cells)")
    return REACH[(net, layer)]


def in_pour(net, layer, x, y, r=0.16):
    for z, l in ZONES.get((net, layer), []):
        if all(z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(x + dx), FM(y + dy))) for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))):
            if os.environ.get("PATCH_REACH") == "1" and (net, layer) in SEEDS:
                return (int((x - EX0) / RS), int((y - EY0) / RS)) in reach(net, layer)
            return True
    return False


def connect(spec, pa, pz, ra, rz, width, layers, via, plane=False, soft=None):
    # soft: net codes whose tracks may be crossed (at a price) instead of blocking. Then nothing is drawn: the
    # result is the set of nets the cheapest path crosses (None when even that finds no path). For --rip.
    """pa, pz: board items (pad, track or via) of one net; ra, rz: the boxes that span the search window.
    plane: pz is None, the search ends where the track meets the net's pour or a via reaches its plane."""
    global CONN
    vd, vh = (0, 0) if via == "none" else (float(v) for v in via.split("/"))
    code = pa.GetNetCode()
    b.BuildConnectivity()
    CONN = b.GetConnectivity()
    isl_a = island(pa)
    isl_z = [] if plane else island(pz)
    if any(g[1][:4] == h[1][:4] and g[2] == h[2] for g in isl_a for h in isl_z if g[0] == h[0] == "pad"):
        print(f"patch_route: {spec}: already joined")
        return True
    pname = pa.GetNetname()
    x0 = max(min(ra[0], rz[0]) - MARGIN, EX0 + EDGE); y0 = max(min(ra[1], rz[1]) - MARGIN, EY0 + EDGE)
    x1 = min(max(ra[2], rz[2]) + MARGIN, EX1 - EDGE); y1 = min(max(ra[3], rz[3]) + MARGIN, EY1 - EDGE)
    nx, ny = int((x1 - x0) / G) + 1, int((y1 - y0) / G) + 1
    need = width / 2 + CLR
    vneed = max(vd / 2 + CLR, vh / 2 + HOLE)
    L = len(layers)
    free = [bytearray(b"\x01") * (nx * ny) for _ in layers]       # [layer][j * nx + i]
    via_ok = bytearray(b"\x01" if vd else b"\x00") * (nx * ny)
    reach = max(need, vneed, vh / 2 + H2H + 0.3)

    def cells(bb, pad):
        i0, i1 = max(0, int((bb[0] - pad - x0) / G)), min(nx, int((bb[2] + pad - x0) / G) + 2)
        j0, j1 = max(0, int((bb[1] - pad - y0) / G)), min(ny, int((bb[3] + pad - y0) / G) + 2)
        return i0, i1, j0, j1

    smap = [[0] * (nx * ny) for _ in layers] if soft else None
    for kind, g, n, lay, dr, is_track in items:
        if n == code and not dr:
            continue
        lift = bool(soft) and is_track and n in soft
        # the MDI pairs keep 0.2 mm to other nets (rule mdi_spacing), but for their breakout inside the PHY's
        # courtyard (rule mdi_breakout: 0.1 mm, the VDD10 vias of pins 3 and 8 sit between the pairs there)
        wide = 0.0
        if (n in MDI) != (code in MDI):
            ib = bbox_of(kind, g)
            if not (ib[0] < PHY[2] and PHY[0] < ib[2] and ib[1] < PHY[3] and PHY[1] < ib[3]):     # as KiCad: the item meets it
                wide = 0.1
        bb = bbox_of(kind, g)
        if bb[2] < x0 - reach or bb[0] > x1 + reach or bb[3] < y0 - reach or bb[1] > y1 + reach:
            continue
        i0, i1, j0, j1 = cells(bb, reach)
        on = [k for k, l in enumerate(layers) if lay in (None, l)] if n != code else []
        # a track also keeps HOLE from a foreign via's drill (its ring may be narrower than that)
        need_i = (max(need, width / 2 + HOLE - (g[2] - dr)) if kind == "circle" else need) + wide
        if kind == "rect" and dr:                      # a drilled pad: HOLE from its hole too (an NPTH has no ring)
            need_i = max(need_i, width / 2 + HOLE - max(0.0, min(g[2] - g[0], g[3] - g[1]) / 2 - dr))
        hh = (dr + vh / 2 + H2H - (g[2] if kind == "circle" else 0)) if (vd and dr) else -1e9
        for j in range(j0, j1):
            y = y0 + j * G
            row = j * nx
            for i in range(i0, i1):
                d = dist(kind, g, x0 + i * G, y)
                if n != code:
                    if d < need_i:
                        for k in on:
                            if lift:
                                smap[k][row + i] = n
                            else:
                                free[k][row + i] = 0
                    if d < vneed + wide:
                        via_ok[row + i] = 0
                if d < hh:
                    via_ok[row + i] = 0
    for lay, r in keepouts:
        i0, i1, j0, j1 = cells(r, 0)
        for k, l in enumerate(layers):
            if lay in ("*", l):
                for j in range(j0, j1):
                    for i in range(i0, i1):
                        free[k][j * nx + i] = 0
        if lay == "*":
            for j in range(j0, j1):
                for i in range(i0, i1):
                    via_ok[j * nx + i] = 0

    def mask(isl):
        m = [bytearray(nx * ny) for _ in layers]
        for kind, g, lay in isl:
            i0, i1, j0, j1 = cells(bbox_of(kind, g), G)
            for j in range(j0, j1):
                for i in range(i0, i1):
                    if dist(kind, g, x0 + i * G, y0 + j * G) <= G * 0.6:
                        for k, l in enumerate(layers):
                            if lay in (None, l):
                                m[k][j * nx + i] = 1
        return m

    start, goal = mask(isl_a), mask(isl_z)
    for k in range(L):                      # the two islands are walkable
        for c in range(nx * ny):
            if start[k][c] or goal[k][c]:
                free[k][c] = 1
    # A*
    zc = ((rz[0] + rz[2]) / 2, (rz[1] + rz[3]) / 2)
    best, heap, prev = {}, [], {}
    for k in range(L):
        for c in range(nx * ny):
            if start[k][c]:
                best[(k, c)] = 0.0
                heapq.heappush(heap, (0.0, 0.0, k, c))
    D = G * 1.41421356
    moves = [(1, 0, G), (-1, 0, G), (0, 1, G), (0, -1, G), (1, 1, D), (1, -1, D), (-1, 1, D), (-1, -1, D)]
    VIA_COST, end, plane_via = 1.5, None, False
    hw = 0.0 if plane else 0.999
    while heap:
        f_, c0, k, c = heapq.heappop(heap)
        if c0 > best.get((k, c), 1e9):
            continue
        if goal[k][c]:
            end = (k, c)
            break
        j, i = divmod(c, nx)
        if plane:
            x, y = x0 + i * G, y0 + j * G
            # ending in the pour on the track's own layer: only where that layer is the rail's plane (5V0 and 1V35
            # on the outer layers). An outer GND pour piece may be the very fragment the pad sits in
            if c0 > 0.2 and not start[k][c] and pname != "GND" and layers[k] in PLANE[pname] \
                    and in_pour(pname, layers[k], x, y, width / 2 + 0.03):
                end = (k, c)
                break
            came_by_via = (k, c) in prev and prev[(k, c)][1] == c
            if via_ok[c] and not came_by_via and any(in_pour(pname, pl, x, y) for pl in PLANE[pname] if pl != layers[k]):
                end = (k, c)
                plane_via = True
                break
        fk = free[k]
        for di, dj, w in moves:
            a2, e2 = i + di, j + dj
            if 0 <= a2 < nx and 0 <= e2 < ny and fk[e2 * nx + a2]:
                nc, c2 = c0 + w, e2 * nx + a2
                if smap and smap[k][c2]:
                    nc += 1.0
                if nc < best.get((k, c2), 1e9):
                    best[(k, c2)] = nc; prev[(k, c2)] = (k, c)
                    heapq.heappush(heap, (nc + math.hypot(x0 + a2 * G - zc[0], y0 + e2 * G - zc[1]) * hw, nc, k, c2))
        if via_ok[c]:
            for k2 in range(L):
                if k2 != k and free[k2][c]:
                    nc = c0 + VIA_COST
                    if nc < best.get((k2, c), 1e9):
                        best[(k2, c)] = nc; prev[(k2, c)] = (k, c)
                        heapq.heappush(heap, (nc + math.hypot(x0 + i * G - zc[0], y0 + j * G - zc[1]) * hw, nc, k2, c))
    if end is None:
        if soft:
            return None
        print(f"patch_route: {spec}: NO PATH ({pa.GetNetname().split('/')[-1]}, {nx}x{ny} cells, {len(best)} reached)")
        return False
    path = [end]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()
    if soft:
        return {smap[k][c] for k, c in path if smap[k][c]}
    path = [(k, c // nx, c % nx) for k, c in path]
    net = pa.GetNet()
    made, nv, length = [], 0, 0.0
    k = 0
    while k < len(path) - 1:
        li, j, i = path[k]
        lj, j2, i2 = path[k + 1]
        if lj != li:
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(FM(x0 + i * G), FM(y0 + j * G))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(FM(vd)); v.SetDrill(FM(vh)); v.SetNet(net)
            made.append(v); nv += 1; k += 1
            continue
        d = (i2 - i, j2 - j)
        m = k + 1
        while m < len(path) - 1 and path[m + 1][0] == li and (path[m + 1][2] - path[m][2], path[m + 1][1] - path[m][1]) == d:
            m += 1
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(FM(x0 + i * G), FM(y0 + j * G)))
        t.SetEnd(pcbnew.VECTOR2I(FM(x0 + path[m][2] * G), FM(y0 + path[m][1] * G)))
        t.SetWidth(FM(width)); t.SetLayer(lid[layers[li]]); t.SetNet(net)
        made.append(t); length += MM(t.GetLength()); k = m
    if plane_via:
        li, j, i = path[-1]
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(FM(x0 + i * G), FM(y0 + j * G))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(FM(vd)); v.SetDrill(FM(vh)); v.SetNet(net)
        made.append(v); nv += 1
    for it in made:
        b.Add(it)
        add_track(it)
    used = sorted({layers[p[0]] for p in path})
    print(f"patch_route: {spec}: {pa.GetNetname().split('/')[-1]} {length:.2f} mm, {nv} vias, on {'/'.join(used)}")
    return True


import json
import os
import re

RIP = "--rip" in sys.argv
MAXV = int(os.environ.get("PATCH_MAX_LIFT", "3"))
ALLG = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "route_groups.json")))
ok = []
netpads = {}
for f in b.GetFootprints():
    for p in f.Pads():
        netpads.setdefault(p.GetNetname(), []).append(p)

def parts(pl):
    """The pads of one net grouped by the copper that joins them."""
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    left, out = {p.m_Uuid.AsString(): p for p in pl}, []
    while left:
        u, p0 = left.popitem()
        comp, seen, todo = [p0], {u}, [p0]
        while todo:
            for o in conn.GetConnectedItems(todo.pop()):
                ou = o.m_Uuid.AsString()
                if ou not in seen:
                    seen.add(ou); todo.append(o)
                    if ou in left:
                        comp.append(left.pop(ou))
        out.append(comp)
    return out

def box(p):
    bb = p.GetBoundingBox()
    return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))

ours = {n for g in ("signals", "phy_pwr", "soc_pwr") for n in ALLG[g]}
code_of = {n: b.FindNet(n).GetNetCode() for n in ours if b.FindNet(n)}
name_of = {c: n for n, c in code_of.items()}

KEEP_BOXES = []      # --keep-box X0,Y0,X1,Y1: copper inside stays when a net is lifted (the breakout stubs under U20)
while "--keep-box" in sys.argv:
    _i = sys.argv.index("--keep-box")
    KEEP_BOXES.append(tuple(float(v) for v in sys.argv[_i + 1].split(",")))
    del sys.argv[_i:_i + 2]


def hand(t):
    """Copper a lift leaves: the user's hand-routed J3 pin <-> pull-down array links (B.Cu, west of x 141.5, 0.37 mm
    between the pins: this router cannot redo them at its clearance), and what lies inside a --keep-box."""
    pts = [t.GetPosition()] if isinstance(t, pcbnew.PCB_VIA) else [t.GetStart(), t.GetEnd()]
    if any(all(r[0] <= MM(q.x) <= r[2] and r[1] <= MM(q.y) <= r[3] for q in pts) for r in KEEP_BOXES):
        return True
    return not isinstance(t, pcbnew.PCB_VIA) and MM(t.GetStart().x) < 141.5 and MM(t.GetEnd().x) < 141.5 \
        and pcbnew.LayerName(t.GetLayer()) == "B.Cu"


def lift(codes):
    """Delete the tracks and vias of these nets; what is needed to put them back."""
    saved = []
    for t in list(b.GetTracks()):
        if t.GetNetCode() in codes and not hand(t):
            via = isinstance(t, pcbnew.PCB_VIA)
            if isinstance(t, pcbnew.PCB_ARC):
                return None                           # not ours to re-draw
            cp = lambda v: pcbnew.VECTOR2I(v.x, v.y)   # noqa: E731
            saved.append((via, cp(t.GetPosition()) if via else cp(t.GetStart()), None if via else cp(t.GetEnd()),
                          t.GetWidth(pcbnew.F_Cu) if via else t.GetWidth(), t.GetDrill() if via else 0,
                          None if via else t.GetLayer(), t.GetNet(), t.IsLocked()))
    kept = [t for t in b.GetTracks() if t.GetNetCode() in codes and hand(t)]
    for t in [t for t in b.GetTracks() if t.GetNetCode() in codes and not hand(t)]:
        b.Delete(t)                                   # Delete, not Remove: Remove leaves pcbnew's lists unusable
    items[:] = [it for it in items if not (it[5] and it[2] in codes)]
    for t in kept:
        add_track(t)
    return saved

def put_back(saved):
    for via, a, z, w, dr, lay, net, locked in saved:
        if via:
            t = pcbnew.PCB_VIA(b); t.SetPosition(a); t.SetViaType(pcbnew.VIATYPE_THROUGH); t.SetWidth(w); t.SetDrill(dr)
        else:
            t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(z); t.SetWidth(w); t.SetLayer(lay)
        t.SetNet(net); t.SetLocked(locked); b.Add(t); add_track(t)

def lift_and_retry(spec, victims, attempt, joined):
    """--rip: lift the (one or two) nets in the way, run attempt(), route the lifted nets again; all or nothing."""
    names = [name_of[c] for c in victims]
    whole = {n: len(parts(netpads[n])) for n in names}
    before = {t.m_Uuid.AsString() for t in b.GetTracks()}
    saved = lift(victims)
    if saved is None:
        return False
    print(f"patch_route: {spec}: lifting {', '.join(n.split('/')[-1] for n in names)}")
    good = attempt() and joined()
    for n in names if good else []:
        join_net(n, None)
        good = good and len(parts(netpads[n])) <= whole[n]
    if good:
        return True
    new = [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]
    gone = {t.GetNetCode() for t in new} | set(victims)
    for t in new:
        b.Delete(t)
    items[:] = [it for it in items if not (it[5] and it[2] in gone)]
    for t in b.GetTracks():           # the surviving tracks of those nets (stubs, earlier work)
        if t.GetNetCode() in gone:
            add_track(t)
    put_back(saved)
    print(f"patch_route: {spec}: lifted nets put back (no gain)")
    return False


def join_net(name, rip):
    """Join the pad groups of one net, nearest pair first. True when the net ends up in one piece."""
    short = name.split("/")[-1]
    width = 0.09 if TIGHT else 0.2 if short == "VCCPLL" else 0.15 if short in ("phy_avdd33", "phy_vdd10", "phy_dvdd_rg") else 0.1
    failed = set()
    while True:
        comps = parts(netpads.get(name, []))
        cand = sorted((math.hypot(MM(p.GetPosition().x - q.GetPosition().x), MM(p.GetPosition().y - q.GetPosition().y)),
                       p.m_Uuid.AsString(), q.m_Uuid.AsString(), p, q)
                      for i, ca in enumerate(comps) for cb in comps[i + 1:] for p in ca for q in cb)
        cand = [c for c in cand if (c[1], c[2]) not in failed]
        if len(comps) < 2 or not cand:
            return len(comps) < 2
        d, pu, qu, p, q = cand[0]
        spec = f"{short} {p.GetParentFootprint().GetReference()}.{p.GetNumber()} > {q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
        r = connect(spec, p, q, box(p), box(q), width, ALL, "0.3/0.15")
        if not r and width > 0.1:                   # a supply net among balls or fine-pitch pins: neck down
            r = connect(spec + " at 0.1 mm", p, q, box(p), box(q), 0.1, ALL, "0.3/0.15")
        if r and len(parts(netpads[name])) >= len(comps):
            print(f"patch_route: {spec}: drawn but not joined (check it)")
            r = False
        if not r and rip:
            soft = set(code_of.values()) - {p.GetNetCode()}
            victims = connect(spec, p, q, box(p), box(q), 0.1, ALL, "0.3/0.15", soft=soft)
            if victims and len(victims) <= MAXV:
                r = lift_and_retry(spec, victims, lambda: connect(spec, p, q, box(p), box(q), 0.1, ALL, "0.3/0.15"),
                                   lambda: len(parts(netpads[name])) < len(comps))
        if rip is not None:
            ok.append(bool(r))
        if not r:
            # the same two groups by another pad pair would fail the same way: give up on every pair of them
            ca = next(c for c in comps if any(x.m_Uuid.AsString() == pu for x in c))
            cb = next(c for c in comps if any(x.m_Uuid.AsString() == qu for x in c))
            failed |= {(x.m_Uuid.AsString(), y.m_Uuid.AsString()) for x in ca for y in cb}
            failed |= {(y.m_Uuid.AsString(), x.m_Uuid.AsString()) for x in ca for y in cb}


if "--auto" in args:
    import json
    import fnmatch
    import os
    i = args.index("--auto")
    report, groups = json.load(open(args[i + 1])), args[i + 2]
    allg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "route_groups.json")))
    nets = {n for g in groups.split(",") for n in allg[g]}
    by_uuid = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
    for f in b.GetFootprints():
        for p in f.Pads():
            by_uuid[p.m_Uuid.AsString()] = p
    ok = []
    for u in report["unconnected_items"]:
        its = [by_uuid.get(x["uuid"]) for x in u["items"][:2]]
        if len(its) < 2 or None in its or its[0].GetNetname() not in nets:
            continue
        name = its[0].GetNetname().split("/")[-1]
        width = 0.3 if name == "VCCPLL" else 0.15 if fnmatch.fnmatch(name, "phy_*d*") and name in ("phy_avdd33", "phy_vdd10", "phy_dvdd_rg") else 0.1
        boxes = [(x["pos"]["x"], x["pos"]["y"], x["pos"]["x"], x["pos"]["y"]) for x in u["items"][:2]]
        if TIGHT:
            width = 0.09
        if os.environ.get("PATCH_AUTO_WIDTH"):          # supply links: wider than a signal
            width = float(os.environ["PATCH_AUTO_WIDTH"])
        ok.append(connect(f"{name} ({boxes[0][0]:.2f}, {boxes[0][1]:.2f}) > ({boxes[1][0]:.2f}, {boxes[1][1]:.2f})",
                          its[0], its[1], boxes[0], boxes[1], width, ALL, "0.3/0.15"))
    print(f"patch_route: {sum(ok)} of {len(ok)} open connections closed")
elif "--repair" in args:
    # clearance and hole violations between routed nets: the net of ours in each (not the block's, not an MDI pair)
    # is lifted and joined again by this router, which keeps hole and MDI distances the main router does not know
    report = json.load(open(args[args.index("--repair") + 1]))
    seen = set()
    for v in report["violations"]:
        if v["type"] not in ("clearance", "hole_clearance", "hole_to_hole", "shorting_items", "tracks_crossing"):
            continue
        names = [m for i in v["items"] for m in re.findall(r"\[([^\]]+)\]", i["description"])]
        cand = [n for n in names if n in code_of and "Track" in " ".join(i["description"] for i in v["items"] if f"[{n}]" in i["description"])] \
            or [n for n in names if n in code_of]
        if not cand or cand[0] in seen:
            continue
        name = cand[0]
        seen.add(name)
        pieces = len(parts(netpads[name]))
        before = {t.m_Uuid.AsString() for t in b.GetTracks()}
        saved = lift({code_of[name]})
        if saved is None:
            continue
        join_net(name, None)
        good = len(parts(netpads[name])) <= pieces
        if not good:
            for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
                b.Delete(t)
            items[:] = [it for it in items if not (it[5] and it[2] == code_of[name])]
            put_back(saved)
        ok.append(good)
        print(f"patch_route: {name.split('/')[-1]} ({v['type']}): {'re-routed' if good else 'put back, not repaired'}")
    print(f"patch_route: {sum(ok)} of {len(ok)} nets with violations re-routed")
elif "--reroute" in args:
    # --reroute NET,NET,...: lift these nets of ours (short names) and join them again in this order (the one that
    # could not get through first); kept only if no net ends up in more pieces than before
    short = {n.split("/")[-1]: n for n in ours}
    names = [short[x] for x in args[args.index("--reroute") + 1].split(",")]
    pieces = {n: len(parts(netpads[n])) for n in names}
    before = {t.m_Uuid.AsString() for t in b.GetTracks()}
    saved = lift({code_of[n] for n in names})
    watch = {n: len(parts(netpads[n])) for n in ours if n not in names} if RIP else {}
    for n in names:
        join_net(n, None if not RIP else True)
    after = {n: len(parts(netpads[n])) for n in names}
    worse = [n for n, k in watch.items() if len(parts(netpads[n])) > k]
    same_ok = os.environ.get("PATCH_ACCEPT_EQUAL") == "1"        # a re-route to cure a violation: no fewer pieces to gain
    if RIP and (worse or not ((same_ok or sum(after.values()) < sum(pieces.values())) and all(after[n] <= pieces[n] for n in names))):
        # with --rip other nets were lifted and re-laid on the way: nothing to put back piece by piece, so
        # nothing is written at all
        print("patch_route: pieces per net before -> after:", ", ".join(f"{n.split('/')[-1]} {pieces[n]} -> {after[n]}" for n in names),
              "; worse:", [n.split("/")[-1] for n in worse])
        print("patch_route: no gain, board not written")
        sys.exit(2)
    print("patch_route: pieces per net before -> after:", ", ".join(f"{n.split('/')[-1]} {pieces[n]} -> {after[n]}" for n in names))
    if RIP or (sum(after.values()) < sum(pieces.values()) and all(after[n] <= pieces[n] for n in names)):
        ok.append(True)                                     # (with --rip the failing case has left above)
    else:
        for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
            b.Delete(t)
        codes = {code_of[n] for n in names}
        items[:] = [it for it in items if not (it[5] and it[2] in codes)]
        put_back(saved)
        ok.append(False)
        print("patch_route: put back (no gain)")
elif "--evict" in args:
    # --evict LAYER[,LAYER]:X0,Y0,X1,Y1 (repeatable): our nets with a track on these layers ending in the rectangle
    # (outside the keep-boxes) are lifted and joined again one at a time, the rectangles closed for those layers. A
    # net that does not come back whole is put back as it was. To get signals off a supply plane's layer.
    zones_ = []
    while "--evict" in args:
        i = args.index("--evict")
        lays, r = args[i + 1].split(":")
        zones_.append((lays.split(","), tuple(float(v) for v in r.split(","))))
        del args[i:i + 2]
    for lays, r in zones_:
        keepouts.extend((l, r) for l in lays)
    todo = []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() not in ours or hand(t) or t.GetNetname() in todo:
            continue
        ln = pcbnew.LayerName(t.GetLayer())
        if any(ln in lays and any(r[0] < MM(q.x) < r[2] and r[1] < MM(q.y) < r[3] for q in (t.GetStart(), t.GetEnd())) for lays, r in zones_):
            todo.append(t.GetNetname())
    print(f"patch_route: {len(todo)} nets to move:", " ".join(n.split("/")[-1] for n in todo))
    for name in todo:
        pieces = len(parts(netpads[name]))
        before = {t.m_Uuid.AsString() for t in b.GetTracks()}
        saved = lift({code_of[name]})
        if saved is None:
            ok.append(False); continue
        join_net(name, None)
        good = len(parts(netpads[name])) <= pieces
        if not good:
            for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
                b.Delete(t)
            items[:] = [it for it in items if not (it[5] and it[2] == code_of[name])]
            for t in b.GetTracks():
                if t.GetNetCode() == code_of[name]:
                    add_track(t)
            put_back(saved)
        ok.append(good)
        print(f"patch_route: {name.split('/')[-1]}: {'moved' if good else 'PUT BACK (no route off the layer)'}")
    print(f"patch_route: {sum(ok)} of {len(ok)} nets moved off the layers")
elif "--trim" in args:
    # --trim DRC.json BASE.kicad_pcb: the tracks and vias the report calls dangling, net by net, unless they are on
    # BASE (the block's inherited ones). A net whose pads end up in more groups than before gets its items back: a
    # route may have joined a stub mid-way, and then the "dangling" stub end is holding it.
    i = args.index("--trim")
    report = json.load(open(args[i + 1]))
    keep = set(re.findall(r'\(uuid "([0-9a-f-]+)"\)', open(args[i + 2]).read()))
    bad = {x["uuid"] for v in report["violations"] if v["type"] in ("track_dangling", "via_dangling") for x in v["items"]} - keep
    by_net = {}
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in bad:
            by_net.setdefault(t.GetNetname(), []).append(t)
    cp = lambda v: pcbnew.VECTOR2I(v.x, v.y)   # noqa: E731
    n_del = 0
    for name, ts in sorted(by_net.items()):
        if any(isinstance(t, pcbnew.PCB_ARC) for t in ts):
            continue
        before = len(parts(netpads.get(name, [])))
        saved = [(isinstance(t, pcbnew.PCB_VIA), cp(t.GetPosition()) if isinstance(t, pcbnew.PCB_VIA) else cp(t.GetStart()),
                  None if isinstance(t, pcbnew.PCB_VIA) else cp(t.GetEnd()),
                  t.GetWidth(pcbnew.F_Cu) if isinstance(t, pcbnew.PCB_VIA) else t.GetWidth(),
                  t.GetDrill() if isinstance(t, pcbnew.PCB_VIA) else 0, None if isinstance(t, pcbnew.PCB_VIA) else t.GetLayer(),
                  t.GetNet(), t.IsLocked()) for t in ts]
        for t in ts:
            b.Delete(t)
        if len(parts(netpads.get(name, []))) > before:
            put_back(saved)
            print(f"patch_route: {name.split('/')[-1]}: {len(ts)} dangling items kept (they hold the net together)")
        else:
            n_del += len(ts)
    print(f"patch_route: {n_del} dangling items deleted")
elif "--orphans" in args:
    # copper of our nets that reaches no pad (a breakout stub left beside the final route): deleted
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    seen, kill = set(), []
    for t in b.GetTracks():
        u = t.m_Uuid.AsString()
        if u in seen or t.GetNetname() not in ours:
            continue
        comp, todo, pad = [t], [t], False
        seen.add(u)
        while todo:
            for o in conn.GetConnectedItems(todo.pop()):
                ou = o.m_Uuid.AsString()
                if o.GetClass() == "PAD":
                    pad = True
                elif ou not in seen:
                    seen.add(ou); comp.append(o); todo.append(o)
        if not pad:
            kill += comp
    ids = {o.m_Uuid.AsString() for o in kill}
    for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]:
        b.Delete(t)
    print(f"patch_route: {len(ids)} items without a pad deleted")
elif "--nets" in args:
    for g in args[args.index("--nets") + 1].split(","):
        for name in ALLG[g]:
            join_net(name, RIP)
    print(f"patch_route: {sum(ok)} of {len(ok)} open connections closed")
elif "--planes" in args:
    import json
    import re
    report = json.load(open(args[args.index("--planes") + 1]))
    pads = {(f.GetReference(), p.GetNumber()): p for f in b.GetFootprints() for p in f.Pads()}
    todo = []
    if "--padfile" in sys.argv:            # pads tools/route/plane_vias.py left open (pour pieces show as zones in the report)
        for line in open(sys.argv[sys.argv.index("--padfile") + 1]):
            ref, num = line.strip().split(".")
            if (ref, num) in pads and pads[(ref, num)].GetNetname() in PLANE:
                todo.append((ref, num))
    for u in report["unconnected_items"]:
        for x in u["items"]:
            m = re.match(r"Pad (\S+) \[([^\]]*)\] of (\S+)", x["description"])
            if m and m.group(2) in PLANE and (m.group(3), m.group(1)) in pads and (m.group(3), m.group(1)) not in todo:
                todo.append((m.group(3), m.group(1)))
    for ref, num in todo:
        p = pads[(ref, num)]
        bb = p.GetBoundingBox()
        r = (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
        own = pcbnew.LayerName(p.GetParentFootprint().GetLayer())
        MARGIN = 6.0
        spec = f"{ref}.{num} {p.GetNetname()} -> plane"
        lays = [own] + [l for l in PLANE[p.GetNetname()] if l in ("F.Cu", "B.Cu") and l != own]
        wd = 0.2 if ref not in ("U20", "U1001", "U901") else 0.1
        wd = float(os.environ.get("PATCH_PLANE_WIDTH", wd))
        res = connect(spec, p, None, r, r, wd, lays, "0.3/0.15", plane=True)
        if not res and RIP:
            victims = connect(spec, p, None, r, r, 0.1, lays, "0.3/0.15", plane=True, soft=set(code_of.values()))
            if victims and len(victims) <= MAXV:
                res = lift_and_retry(spec, victims, lambda: connect(spec, p, None, r, r, min(wd, 0.2), lays, "0.3/0.15", plane=True),
                                     lambda: True)
        ok.append(bool(res))
    print(f"patch_route: {sum(ok)} of {len(ok)} supply pads tied")
else:
    ok = [route(s) for s in args[2:]]
if not dry:
    pcbnew.SaveBoard(args[1], b)
sys.exit(0 if all(ok) else 1)
