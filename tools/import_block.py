#!/usr/bin/env python3
"""Copy juliancoy's routed SoC + DDR3 block into kicad/zynq_card.kicad_pcb (PLAN.md §4.2 step 2, LAYOUT_PLAN.md step 2).

    tools/p2k/bin/kipy tools/import_block.py [--at X Y] [--rot DEG] [--out BOARD]

Run on a board fresh from tools/make_board.py (it refuses a board that already has copper); P2K_PCB names another
one, as for make_board and board_setup. --at is U20's centre on
our board (default: pose A, LAYOUT_PLAN.md step 3), --rot a rotation of the whole block (0/90/180/270, never
mirrored), --out another board file (pose trials in work/; the .kicad_pro/.kicad_dru are copied beside it).

1. **Block parts** (our footprints whose ref is on the source board, made by make_board from the source's own
   footprints) take the source pose through one rigid transform, and are locked. Every pad is checked against the
   transformed source pad.
2. **Selection.** A geometric connectivity graph of the source copper (tracks, arcs, vias, pads). Copied: every
   copper group that touches a *block pad* (a pad of a block part other than U20; on U20 only the balls on a rail or on
   a block part's net, as tools/check_block_netlist.py compares them), plus pad-less rail copper (stitching vias).
   Only items inside the block outline are kept. The outline is the box around the block parts and the DDR3
   copper, plus MARGIN. So juliancoy's MIO/PL escapes and the rail copper to his regulators are not copied.
3. **Nets by pad.** Each copper group takes the net our board has on the pads it touches. A group with no pad
   (stitching) is mapped by name (RAILS). A group that would join two of our nets is a failure.
4. **Changed balls** (our net differs from the source's: REUSE_LOG E3 and E5-E9). Their pads are detached first:
   - a copper group that serves only changed pads with one real net (a ball's fan-out) takes that net: the VCCO_34/
     35 vias go to 3V3 (E7), the bank 34 J3 balls keep their fan-out (E9), H10 becomes VCCPLL (E5);
   - a group serving an open ball (E8 RSVDGND, the unused bank 34/35 balls) is dropped;
   - in a group that also serves unchanged pads, the items on the changed pad are dropped (E3: the PS_MIO14 branch).
   Then every track end that lost its connection, and every signal via that no longer joins two layers, is pruned
   back, repeatedly (stubs to juliancoy's parts too).
5. **Zones.** The source zones on block nets are copied, clipped to the block outline (several of juliancoy's rails
   are board-wide pours on the signal layers: +1V8 on In2/In4, +3V3 on In6). The GND planes on In1/In3/In5 become our
   own, over the whole board. The others (+5V, GNDA, his regulators' nodes) are not copied.
6. **Ours, with the block:** the outline on User.1 and as the rule area `ddr3_block` (tools/board_setup.py rules),
   the two heatsink holes H1/H2 (NPTH 3.2 mm at U20 +-(14.93, 14.93) mm in the block frame, POWER_BUDGET.md) with
   their keep-outs: copper-free within 2.1 mm of the centre on every layer (0.5 mm from the hole wall) and within
   3 mm on F/B (the push-pin head and barb).
Layer map: the source layers sit at our IDs (TOP_GND = F.Cu, GND0 = In1, SIGNAL1 = In2, GND1 = In3, SIGNAL2 = In4,
GND2 = In5, SIGNAL4 = In6, BOTTOM = B.Cu); the script asserts it.
"""
import argparse
import collections
import math
import os
import shutil
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from check_block_netlist import NET_MAP, RAILS, net_name  # noqa: E402
from p2k.build_pcb import load_fp  # noqa: E402

SOURCE = os.path.join(ROOT, "reference", "zynqpcb", "DFTBoard.kicad_pcb")
PCB = os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")
BASE = os.environ.get("P2K_PCB", PCB)   # the board read: make_board's output (P2K_PCB, as tools/make_board.py)
POSE_A = (164.0, 87.0)          # U20 centre, LAYOUT_PLAN.md step 3
MARGIN = 0.5                    # around the block parts and DDR3 copper
SRC_LAYERS = {pcbnew.F_Cu: "TOP_GND", pcbnew.In1_Cu: "GND0", pcbnew.In2_Cu: "SIGNAL1", pcbnew.In3_Cu: "GND1",
              pcbnew.In4_Cu: "SIGNAL2", pcbnew.In5_Cu: "GND2", pcbnew.In6_Cu: "SIGNAL4", pcbnew.B_Cu: "BOTTOM"}
GND_PLANES = (pcbnew.In1_Cu, pcbnew.In3_Cu, pcbnew.In5_Cu)
HOLES = ((14.93, 14.93), (-14.93, -14.93))   # block frame, from U20 (POWER_BUDGET.md §Heatsink)
HOLE_FP = "MountingHole:MountingHole_3.2mm_M3"
# source net -> ours for copper with no pad (the rest goes by pad); check_block_netlist's map plus GND and VTT
RAIL_MAP = {**{k: v for k, v in NET_MAP.items() if k.startswith("+")}, "GND": "GND", "DDR3_VTT": "DDR3_VTT",
            "/Power/VCCAUX": "/05 soc_power/VCCAUX"}

mm, iu = pcbnew.ToMM, pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(iu(x), iu(y))


def real(net):
    return bool(net) and not net.startswith("unconnected-(")


# ---- connectivity graph of the source copper -------------------------------------------------------------------
class Graph:
    """Items: tracks/arcs/vias (copper) and pads. Edges from each track end and each via to what covers that point on
    a shared layer. adj[i] = {(j, end)}: end 0/1 = the track end of i at which j connects, None for a via."""
    CELL = iu(1.0)

    def __init__(self, board):
        self.items = []
        for t in board.GetTracks():
            self.items.append(t)
        self.n_copper = len(self.items)
        for fp in board.GetFootprints():
            self.items.extend(fp.Pads())
        self.index = {}
        self.grid = collections.defaultdict(list)
        for i, it in enumerate(self.items):
            self.index[it.m_Uuid.AsString()] = i
            bb = it.GetBoundingBox()
            for cx in range(bb.GetLeft() // self.CELL, bb.GetRight() // self.CELL + 1):
                for cy in range(bb.GetTop() // self.CELL, bb.GetBottom() // self.CELL + 1):
                    self.grid[(cx, cy)].append(i)
        self.adj = collections.defaultdict(set)
        for i in range(self.n_copper):
            it = self.items[i]
            if it.GetClass() == "PCB_VIA":
                for j in self.at(it.GetPosition(), None, i):
                    self.link(i, None, j)
            else:
                for end, pt in enumerate((it.GetStart(), it.GetEnd())):
                    for j in self.at(pt, it.GetLayer(), i):
                        self.link(i, end, j)

    def at(self, pt, layer, skip):
        """Items covering pt (on `layer`, or on any copper layer of the via `skip` when layer is None)."""
        via = self.items[skip] if layer is None else None
        for j in self.grid[(pt.x // self.CELL, pt.y // self.CELL)]:
            if j == skip:
                continue
            o = self.items[j]
            if layer is not None:
                if not o.IsOnLayer(layer):
                    continue
                if o.GetClass() == "PAD":
                    if o.HitTest(pt, 0, layer):
                        yield j
                elif o.HitTest(pt, 0):
                    yield j
            elif o.GetClass() == "PAD":
                if any(o.IsOnLayer(lay) and o.HitTest(pt, 0, lay) for lay in via.GetLayerSet().CuStack()):
                    yield j
            elif o.GetClass() == "PCB_VIA":
                if o.HitTest(pt, 0):
                    yield j
            # a track end inside the via is found from the track's side

    def link(self, i, end, j):
        self.adj[i].add((j, end))
        jend = None
        o = self.items[j]
        if o.GetClass() in ("PCB_TRACK", "PCB_ARC"):
            pi = self.items[i]
            pt = pi.GetPosition() if end is None else (pi.GetStart(), pi.GetEnd())[end]
            ds = (o.GetStart() - pt).EuclideanNorm(), (o.GetEnd() - pt).EuclideanNorm()
            jend = 0 if ds[0] <= ds[1] else 1
        self.adj[j].add((i, jend))

    def groups(self, nodes, through=lambda i: True):
        """Connected groups of `nodes` (a set of item indices); a node for which through() is false is a leaf
        (joins nothing to anything)."""
        seen, out = set(), []
        for s in nodes:
            if s in seen or not through(s):
                continue
            grp, todo = {s}, [s]
            seen.add(s)
            while todo:
                k = todo.pop()
                for j, _ in self.adj[k]:
                    if j in nodes and j not in grp:
                        grp.add(j)
                        if through(j):
                            seen.add(j)
                            todo.append(j)
            out.append(grp)
        return out


# ---- geometry ---------------------------------------------------------------------------------------------------
class Pose:
    def __init__(self, src_c, dst, rot):
        self.delta = pcbnew.VECTOR2I(dst.x - src_c.x, dst.y - src_c.y)
        self.dst, self.rot = dst, rot

    def apply(self, item):
        item.Move(self.delta)
        if self.rot:
            item.Rotate(self.dst, pcbnew.EDA_ANGLE(self.rot, pcbnew.DEGREES_T))

    def point(self, pt):
        x, y = pt.x - self.dst.x + self.delta.x, pt.y - self.dst.y + self.delta.y
        a = math.radians(self.rot)
        # KiCad's positive rotation is counter-clockwise on screen (y down)
        rx, ry = x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)
        return pcbnew.VECTOR2I(int(round(self.dst.x + rx)), int(round(self.dst.y + ry)))


def rect_poly(x0, y0, x1, y1):
    p = pcbnew.SHAPE_POLY_SET()
    p.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        p.Append(int(x), int(y))
    return p


def circle_poly(c, r, n=48):
    p = pcbnew.SHAPE_POLY_SET()
    p.NewOutline()
    for k in range(n):
        a = 2 * math.pi * k / n
        p.Append(int(c.x + r * math.cos(a)), int(c.y + r * math.sin(a)))
    return p


def rule_area(board, poly, layers, name, keepout):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for lay in layers:
        ls.AddLayer(lay)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    z.Outline().Append(poly)
    for f in ("Tracks", "Vias", "ZoneFills"):
        getattr(z, f"SetDoNotAllow{f}")(keepout)
    z.SetDoNotAllowPads(False)          # the hole's own NPTH pad
    z.SetDoNotAllowFootprints(False)
    board.Add(z)
    return z


# ---- the import ------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", nargs=2, type=float, default=POSE_A)
    ap.add_argument("--rot", type=float, default=0.0, choices=(0.0, 90.0, 180.0, 270.0))
    ap.add_argument("--out", default=PCB)
    a = ap.parse_args()

    src = pcbnew.LoadBoard(SOURCE)
    for lay, name in SRC_LAYERS.items():
        assert src.GetLayerName(lay) == name, (lay, src.GetLayerName(lay))
    board = pcbnew.LoadBoard(BASE)
    if len(board.GetTracks()) or any(z.GetZoneName() == "ddr3_block" for z in board.Zones()):
        sys.exit("import_block: the board already has copper; rebuild it with tools/make_board.py first")
    ours = {fp.GetReference(): fp for fp in board.GetFootprints()}
    sfps = {fp.GetReference(): fp for fp in src.GetFootprints()}
    block = sorted(r for r in ours if r in sfps and not r.startswith("J")
                   and int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or 999) < 200)
    u20 = sfps["U20"].GetPosition()
    pose = Pose(u20, V(*a.at), a.rot)
    log = []

    # pads: source net, our net; which are block pads, which changed
    our_net = {(r, p.GetNumber()): p.GetNetname() for r in block for p in ours[r].Pads()}
    block_nets = {p.GetNetname() for r in block if r != "U20" for p in sfps[r].Pads() if p.GetNetname()}
    rails = RAILS | {"DDR3_VTT"}

    def is_block_pad(fp, pad):
        r, n = fp.GetReference(), pad.GetNetname()
        if r not in block or not n:
            return False
        return r != "U20" or n in rails or n in block_nets

    def changed(fp, pad):
        n = pad.GetNetname()
        if n.startswith("Net-("):
            return False      # unnamed: the pad-set equality is tools/check_block_netlist.py's
        return our_net[(fp.GetReference(), pad.GetNumber())] != net_name(n)

    g = Graph(src)
    pad_of = {}
    for i in range(g.n_copper, len(g.items)):
        p = g.items[i]
        pad_of[i] = (p.GetParentFootprint(), p)
    bpads = {i for i, (fp, p) in pad_of.items() if is_block_pad(fp, p)}
    chg = {i for i in bpads if changed(*pad_of[i])}
    keep_pads = bpads - chg
    copper = set(range(g.n_copper))

    # outline: block parts and the DDR3 copper (every group on a non-rail block net), plus MARGIN
    allg = g.groups(copper | set(pad_of))
    sel = set()
    for grp in allg:
        cu = grp & copper
        if not cu:
            continue
        if grp & bpads:
            sel |= cu
        elif not (grp & set(pad_of)) and all(g.items[i].GetNetname() in RAIL_MAP for i in cu):
            sel |= cu          # stitching: rail copper that touches no pad (pour connections)
    box = pcbnew.BOX2I()
    for r in block:
        box.Merge(sfps[r].GetBoundingBox(False, False))
    for i in sel:
        if g.items[i].GetNetname() not in RAIL_MAP:
            box.Merge(g.items[i].GetBoundingBox())
    box.Inflate(iu(MARGIN))
    x0, y0, x1, y1 = box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom()
    log.append(f"block outline (source frame, from U20): x {mm(x0 - u20.x):+.2f}..{mm(x1 - u20.x):+.2f}, "
               f"y {mm(y0 - u20.y):+.2f}..{mm(y1 - u20.y):+.2f} mm ({mm(x1 - x0):.2f} x {mm(y1 - y0):.2f})")

    def inside(i):
        bb = g.items[i].GetBoundingBox()
        return bb.GetLeft() >= x0 and bb.GetRight() <= x1 and bb.GetTop() >= y0 and bb.GetBottom() <= y1

    outside = collections.Counter(g.items[i].GetNetname() for i in sel if not inside(i))
    kept = {i for i in sel if inside(i)}
    if outside:
        log.append("not copied, outside the outline: " + ", ".join(f"{n or '(no net)'} {c}"
                                                                   for n, c in outside.most_common()))
    # rail copper inside the outline that is not ours: it serves only juliancoy's other parts (or his signal balls)
    foreign, parts = collections.Counter(), set()
    for grp in allg:
        cu = {i for i in grp & copper if inside(i) and g.items[i].GetNetname() in RAIL_MAP}
        if cu and not (cu & sel):
            foreign.update(g.items[i].GetNetname() for i in cu)
            parts |= {pad_of[j][0].GetReference() for j in grp if j in pad_of}
    if foreign:
        log.append("not copied, rail copper inside the outline serving only juliancoy's other parts: "
                   + ", ".join(f"{n} {c}" for n, c in foreign.most_common())
                   + f" (parts: {', '.join(sorted(parts - set(block))) or '-'})")

    # changed balls: fan-outs that serve only changed pads take their net or go; other items on a changed pad go
    net_of = {}
    dropped = collections.Counter()
    for grp in g.groups(kept):
        touched = {j for i in grp for j, _ in g.adj[i] if j in bpads}
        c = touched & chg
        if not c:
            continue
        if touched <= chg:
            nets = {our_net[(pad_of[j][0].GetReference(), pad_of[j][1].GetNumber())] for j in c}
            if len(nets) == 1 and real(next(iter(nets))):
                net = nets.pop()
                for i in grp:
                    net_of[i] = net
                dropped[f"fan-out re-netted to {net}"] += len(grp)
            else:
                kept -= grp
                dropped["fan-out of an open/split changed ball, dropped"] += len(grp)
        else:
            on_chg = {i for i in grp if any(j in c for j, _ in g.adj[i])}
            kept -= on_chg
            dropped["items on a changed ball, dropped"] += len(on_chg)

    # prune track ends and non-rail vias that lost every connection they had in the source
    alive_pads = keep_pads | {j for j in chg if any(i in net_of for i, _ in g.adj[j])}

    def layer(j):
        o = g.items[j]
        if o.GetClass() == "PAD":
            return pcbnew.F_Cu if o.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        return None if o.GetClass() == "PCB_VIA" else o.GetLayer()

    def joins_layers(js):
        lays = {layer(j) for j in js}
        return None in lays or len(lays) >= 2

    pruned = collections.Counter()
    while True:
        gone = set()
        for i in kept:
            it = g.items[i]
            ends = collections.defaultdict(list)
            for j, end in g.adj[i]:
                ends[end].append(j)
            for end, js in ends.items():
                n = sum(j in kept or j in alive_pads for j in js)
                if end is not None and n == 0:
                    gone.add(i)
                # a signal via that no longer joins two layers is a stub end too; rail vias also feed pours
                elif end is None and it.GetNetname() not in RAIL_MAP and joins_layers(js) \
                        and not joins_layers([j for j in js if j in kept or j in alive_pads]):
                    gone.add(i)
        if not gone:
            break
        for i in gone:
            pruned[g.items[i].GetNetname()] += 1
        kept -= gone
    if pruned:
        log.append("pruned (lost their connection): " + ", ".join(f"{n} {c}" for n, c in pruned.most_common()))
    for k, v in dropped.items():
        log.append(f"{k}: {v} items")
    # each changed ball: what it has now (phase 4 connects the ones without copper)
    state = collections.defaultdict(list)
    for j in sorted(chg, key=lambda j: pad_of[j][1].GetNumber()):
        fp, p = pad_of[j]
        n = our_net[(fp.GetReference(), p.GetNumber())]
        had = any(i < g.n_copper for i, _ in g.adj[j])
        has = any(i in kept for i, _ in g.adj[j])
        what = ("fan-out kept, re-netted" if has else "fan-out dropped" if had else "no copper of its own in the source")
        state[(what, real(n))].append(f"{fp.GetReference()}.{p.GetNumber()}")
    for (what, connected), pads in sorted(state.items()):
        log.append(f"changed balls/pads, {what}, {'on a net' if connected else 'open'}: {len(pads)}"
                   + (f" ({' '.join(pads)})" if len(pads) <= 16 else ""))

    # nets: by pad, else by name
    fails = []
    for grp in g.groups(kept):
        pads = {j for i in grp for j, _ in g.adj[i] if j in keep_pads}
        nets = {our_net[(pad_of[j][0].GetReference(), pad_of[j][1].GetNumber())] for j in pads}
        nets |= {net_of[i] for i in grp if i in net_of}
        if len(nets) > 1:
            fails.append(f"a copper group joins {sorted(nets)}")
            continue
        if nets:
            net = nets.pop()
        else:
            sn = {g.items[i].GetNetname() for i in grp}
            net = RAIL_MAP.get(next(iter(sn))) if len(sn) == 1 else None
            if net is None:
                fails.append(f"no net for a pad-less group on {sorted(sn)}")
                continue
        for i in grp:
            net_of[i] = net

    # write: footprints, copper, zones, outline, holes
    for r in block:
        s, d = sfps[r], ours[r]
        if s.IsFlipped() != d.IsFlipped():
            d.Flip(d.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        d.SetOrientation(s.GetOrientation())
        d.SetPosition(s.GetPosition())
        pose.apply(d)
        d.SetLocked(True)
        # each pad on a source pad of the same number and layers (numbers repeat: thermal and paste pads)
        sp = collections.defaultdict(list)
        for q in s.Pads():
            sp[q.GetNumber()].append((pose.point(q.GetPosition()), list(q.GetLayerSet().Seq())))
        for p in d.Pads():
            lays = list(p.GetLayerSet().Seq())
            off = min(((p.GetPosition() - w).EuclideanNorm() for w, ql in sp[p.GetNumber()] if ql == lays),
                      default=math.inf)
            if off > 2:
                fails.append(f"{r}.{p.GetNumber()}: pad not on the transformed source pad ({mm(off):.4f} mm off)")
    nets = {n: board.FindNet(n) for n in set(net_of.values())}
    for n, ni in nets.items():
        if ni is None:
            fails.append(f"net {n} is not on our board")
    if fails:
        for f in fails:
            print("import_block: FAIL", f)
        sys.exit(1)
    count = collections.Counter()
    for i in sorted(kept):
        it = g.items[i]
        new = it.Duplicate().Cast()     # (PCB_TRACK(track) would make an empty track with that parent)
        board.Add(new)
        new.SetNet(nets[net_of[i]])
        pose.apply(new)
        count[it.GetClass()] += 1

    clip = rect_poly(x0, y0, x1, y1)
    zlog = []
    for z in src.Zones():
        sn = z.GetNetname()
        if z.GetIsRuleArea() or sn not in RAIL_MAP or (sn == "GND" and z.GetLayer() in GND_PLANES):
            continue
        new = pcbnew.ZONE(z)
        new.Outline().BooleanIntersection(clip)
        if new.Outline().OutlineCount() == 0:
            continue
        board.Add(new)
        new.SetNet(board.FindNet(RAIL_MAP[sn]))
        new.UnFill()
        pose.apply(new)
        zlog.append(f"{RAIL_MAP[sn]}@{board.GetLayerName(z.GetLayer())}")
    # our GND planes: juliancoy's (his fill settings: 0.102 mm minimum width, which reaches the vias under the BGA),
    # on our whole board
    edge = board.GetBoardEdgesBoundingBox()
    for z in src.Zones():
        if z.GetNetname() == "GND" and z.GetLayer() in GND_PLANES:
            new = pcbnew.ZONE(z)
            new.Outline().RemoveAllContours()
            new.Outline().Append(rect_poly(edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom()))
            board.Add(new)
            new.SetNet(board.FindNet("GND"))
            new.UnFill()
    log.append("zones copied (clipped to the outline): " + ", ".join(zlog)
               + "; GND planes In1/In3/In5 over the whole board (ours)")

    outline = rect_poly(x0, y0, x1, y1)
    area = rule_area(board, outline, [lay for lay in SRC_LAYERS], "ddr3_block", keepout=False)
    pose.apply(area)
    bb = area.GetBoundingBox()
    if not (edge.GetLeft() <= bb.GetLeft() and bb.GetRight() <= edge.GetRight()
            and edge.GetTop() <= bb.GetTop() and bb.GetBottom() <= edge.GetBottom()):
        sys.exit(f"import_block: the block outline x {mm(bb.GetLeft()):.2f}..{mm(bb.GetRight()):.2f}, "
                 f"y {mm(bb.GetTop()):.2f}..{mm(bb.GetBottom()):.2f} is not inside the board")
    for k in range(4):
        p0, p1 = outline.CVertex(k), outline.CVertex((k + 1) % 4)
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.User_1)
        s.SetStart(p0)
        s.SetEnd(p1)
        s.SetWidth(iu(0.1))
        board.Add(s)
        pose.apply(s)
    for n, (hx, hy) in enumerate(HOLES, 1):
        c = pcbnew.VECTOR2I(u20.x + iu(hx), u20.y + iu(hy))
        fp = load_fp(HOLE_FP)
        fp.SetReference(f"H{n}")
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        board.Add(fp)
        fp.SetPosition(c)
        pose.apply(fp)
        fp.SetLocked(True)
        for poly, layers, name in ((circle_poly(c, iu(2.1)), list(SRC_LAYERS), f"heatsink_h{n}_wall"),
                                   (circle_poly(c, iu(3.0)), [pcbnew.F_Cu, pcbnew.B_Cu], f"heatsink_h{n}_pin")):
            pose.apply(rule_area(board, poly, layers, name, keepout=True))
        log.append(f"H{n} at ({mm(fp.GetPosition().x):.2f}, {mm(fp.GetPosition().y):.2f})")

    board.BuildConnectivity()           # the filler needs it to tell islands from connected copper
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(a.out, board)
    if a.out != PCB:        # after the save, which writes the .kicad_pro of the board it read (P2K_PCB's)
        for ext in (".kicad_pro", ".kicad_dru"):
            shutil.copy(os.path.splitext(PCB)[0] + ext, os.path.splitext(a.out)[0] + ext)
        shutil.copy(os.path.join(ROOT, "kicad", "fp-lib-table"), os.path.dirname(os.path.abspath(a.out)))
    for line in log:
        print("import_block: " + line)
    print(f"import_block: {len(block)} block parts at U20 ({a.at[0]:g}, {a.at[1]:g}), rotation {a.rot:g}; "
          f"copied {count['PCB_TRACK']} tracks, {count['PCB_ARC']} arcs, {count['PCB_VIA']} vias, "
          f"{len(zlog)} zones -> {os.path.relpath(a.out, ROOT)}")


if __name__ == "__main__":
    main()
