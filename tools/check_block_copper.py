#!/usr/bin/env python3
"""Check the imported block copper against juliancoy's board, item by item (LAYOUT_PLAN.md step 2).

    tools/p2k/bin/kipy tools/check_block_copper.py [BOARD]

BOARD defaults to kicad/zynq_card.kicad_pcb. The pose comes from U20 (our position and orientation against the
source's), the block area from the rule area `ddr3_block`. For every signal net of the block (the source nets of the
block parts other than U20, without the rails: DDR3_*, VREF, ZQ, VRP/VRN, DDR3_VTT_EN, ...):
- every source track and via that lies inside the block area, moved by the pose, must be on our board with the same
  layer, end points, width (via: size, drill, layers) and our net for that source net (found through the pads);
- our board must have nothing else on that net inside the block area.
A difference is a failure unless the net is in EXPECTED (a REUSE_LOG entry). Then a summary per net class: segments,
length per layer, vias, both boards.
The rails are not compared item by item (the import clips them and re-nets the changed balls' fan-outs); their
counts inside the block are printed.
"""
import collections
import os
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from import_block import PCB, RAIL_MAP, SOURCE, Pose  # noqa: E402

# source net: why its copper differs (REUSE_LOG.md)
EXPECTED = {
    "DDR3_VTT_EN": "E3: the branch to U20 B6 (PS_MIO14) is removed; R25-U8 EN stays",
    "DDR3_CK_P": "E1: coupled meander + P bump in the In2 trunk (tools/block_e1.py), +4.30 mm",
    "DDR3_CK_N": "E1: coupled meander in the In2 trunk (tools/block_e1.py), +3.23 mm",
}
mm = pcbnew.ToMM


def key(item, pose=None):
    """A comparable description of a track/arc/via, optionally moved by the pose."""
    p = pose.point if pose else (lambda v: v)
    if item.GetClass() == "PCB_VIA":
        q = p(item.GetPosition())
        return ("via", q.x, q.y, item.GetWidth(pcbnew.F_Cu), item.GetDrillValue(),
                tuple(item.GetLayerSet().CuStack()))
    a, b = p(item.GetStart()), p(item.GetEnd())
    ends = tuple(sorted(((a.x, a.y), (b.x, b.y))))
    mid = ()
    if item.GetClass() == "PCB_ARC":
        m = p(item.GetMid())
        mid = (m.x, m.y)
    return (item.GetClass(), item.GetLayer(), ends, mid, item.GetWidth())


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else PCB
    src, ours = pcbnew.LoadBoard(SOURCE), pcbnew.LoadBoard(path)
    s20, o20 = src.FindFootprintByReference("U20"), ours.FindFootprintByReference("U20")
    rot = (o20.GetOrientationDegrees() - s20.GetOrientationDegrees()) % 360
    pose = Pose(s20.GetPosition(), o20.GetPosition(), rot)
    area = next(z for z in ours.Zones() if z.GetZoneName() == "ddr3_block").GetBoundingBox()

    # the block parts as tools/import_block.py picks them (our locked connectors share refs with juliancoy's)
    block = {r for r in (fp.GetReference() for fp in ours.GetFootprints())
             if src.FindFootprintByReference(r) is not None and r != "U20" and not r.startswith(("J", "H"))
             and int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or 999) < 200}
    opads = {(fp.GetReference(), p.GetNumber()): p.GetNetname() for fp in ours.GetFootprints() for p in fp.Pads()}
    mapping = collections.defaultdict(set)
    for fp in src.GetFootprints():
        if fp.GetReference() in block:
            for p in fp.Pads():
                if p.GetNetname():
                    mapping[p.GetNetname()].add(opads.get((fp.GetReference(), p.GetNumber())))
    nets = {n: m for n, m in mapping.items() if n not in RAIL_MAP}

    def inside(item, moved):
        bb = item.GetBoundingBox()
        if moved:
            a, b = pose.point(bb.GetOrigin()), pose.point(bb.GetEnd())
            bb = pcbnew.BOX2I(a, pcbnew.VECTOR2L(b.x - a.x, b.y - a.y))
            bb.Normalize()
        return area.Contains(bb)

    src_items = collections.defaultdict(list)
    for t in src.GetTracks():
        if t.GetNetname() in nets and inside(t, True):
            src_items[t.GetNetname()].append(t)
    our_items = collections.defaultdict(list)
    for t in ours.GetTracks():
        if inside(t, False):
            our_items[t.GetNetname()].append(t)

    fails, expected = [], []
    stats = {"source": collections.Counter(), "ours": collections.Counter()}
    for sn in sorted(nets):
        if len(nets[sn]) != 1:
            fails.append(f"{sn}: maps to several of our nets {sorted(map(str, nets[sn]))}")
            continue
        on = next(iter(nets[sn]))
        want = collections.Counter(key(t, pose) for t in src_items[sn])
        have = collections.Counter(key(t) for t in our_items[on])
        for side, items in (("source", src_items[sn]), ("ours", our_items[on])):
            for t in items:
                if t.GetClass() == "PCB_VIA":
                    stats[side]["vias"] += 1
                else:
                    stats[side][f"mm {src.GetLayerName(t.GetLayer()) if side == 'source' else ours.GetStandardLayerName(t.GetLayer())}"] += mm(t.GetLength())
                    stats[side]["segments"] += 1
        missing, extra = sum((want - have).values()), sum((have - want).values())
        if missing or extra:
            line = f"{sn} -> {on}: {missing} source items missing, {extra} extra"
            (expected if sn in EXPECTED else fails).append(line + (f" ({EXPECTED[sn]})" if sn in EXPECTED else ""))
    rails = collections.Counter(RAIL_MAP[t.GetNetname()] for t in src.GetTracks()
                                if t.GetNetname() in RAIL_MAP and inside(t, True))
    orails = collections.Counter(t.GetNetname() for t in ours.GetTracks()
                                 if t.GetNetname() in set(RAIL_MAP.values()) and inside(t, False))

    print(f"check_block_copper: pose U20 ({mm(o20.GetPosition().x):g}, {mm(o20.GetPosition().y):g}), rotation {rot:g}")
    for side in ("source", "ours"):
        st = stats[side]
        lens = ", ".join(f"{k[3:]} {v:.1f}" for k, v in sorted(st.items()) if k.startswith("mm "))
        print(f"  {side:6s}: {st['segments']} segments, {st['vias']} vias; mm per layer: {lens}")
    print("  rails inside the block (items, source -> ours): "
          + ", ".join(f"{n} {rails[n]} -> {orails[n]}" for n in sorted(set(rails) | set(orails))))
    for e in expected:
        print("  expected difference:", e)
    print(f"check_block_copper: {len(nets)} signal nets, {len(fails)} failures")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
