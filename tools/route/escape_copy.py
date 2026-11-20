#!/usr/bin/env python3
"""Pin breakouts copied from a sibling card that has the same part in the same orientation (kipy):

    escape_copy.py IN.kicad_pcb OUT.kicad_pcb REF [REF ...]

Source: the Ti135 card (~/dev/efinix_soc_board, read only), routed and ordered 2026-11-17. For every pad of REF on
one of our nets that has no copper yet, the source's copper from the same pad is followed while it stays inside the
part's courtyard (plus EXIT mm), moved by the difference of the two parts' positions and put on our net: the stub
out of a 0.5 mm-pitch eMMC ball or a 0.4 mm-pitch PHY pin, its via if it has one. The router goes on from the stub
end; it cannot leave such pads by itself (it reports them as boxed in). Layers: F, In2 and B keep their layer, the
source's In5 (its second signal layer) becomes our In4; copper on its plane layers is not copied. A pad whose copied
copper would come closer than CLEAR to our other copper is skipped and listed.
"""
import os
import sys

import pcbnew

mm, FM = pcbnew.ToMM, pcbnew.FromMM
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
from escape_u20 import clip  # noqa: E402
from import_block import Graph  # noqa: E402



def walk(g, s, inside, box):
    """The source's copper from pad item s while it stays inside: [(item, cut end or None)], or why not. As
    escape_u20.walk, but an arc ends the stub instead of dropping the pad (the source's length-tuning bends)."""
    seen, todo, out = {s}, [s], []
    while todo:
        k = todo.pop()
        for j, _ in g.adj[k]:
            if j in seen:
                continue
            seen.add(j)
            o = g.items[j]
            if o.GetClass() == "PAD":
                return f"reaches {o.GetParentFootprint().GetReference()}.{o.GetNumber()}"
            if o.GetClass() == "PCB_VIA":
                out.append((o, None))
                todo.append(j)
                continue
            if o.GetClass() == "PCB_ARC":
                continue                                 # the stub ends before the first arc (length tuning)
            a, z = o.GetStart(), o.GetEnd()
            ia, iz = inside(a), inside(z)
            if ia and iz:
                out.append((o, None))
                todo.append(j)
            elif ia or iz:
                p, q = (a, z) if ia else (z, a)
                cut = clip((mm(p.x), mm(p.y)), (mm(q.x), mm(q.y)), box)
                out.append((o, (p, pcbnew.VECTOR2I(FM(cut[0]), FM(cut[1])))))
    return out if out else "no copper"


SRC = os.path.expanduser("~/dev/efinix_soc_board/kicad/ti135_card.kicad_pcb")
LAYERS = {"F.Cu": "F.Cu", "In2.Cu": "In2.Cu", "In5.Cu": "In4.Cu", "B.Cu": "B.Cu"}
EXIT, CLEAR, HOLE = 0.5, 0.102, 0.2
RAILS = {"GND", "1V0", "1V8", "1V35", "3V3", "5V0"}

src, b = pcbnew.LoadBoard(SRC), pcbnew.LoadBoard(sys.argv[1])
g = Graph(src)
lid = {pcbnew.LayerName(l): l for l in b.GetEnabledLayers().CuStack()}
others = [t for t in b.GetTracks()] + [p for fp in b.GetFootprints() for p in fp.Pads()]
b.BuildConnectivity()
conn = b.GetConnectivity()

def build(esc, d, net):
    """The source items of one pad as our items (not yet on the board), and the first clash or None."""
    new = []
    for o, cut in esc:
        if o.GetClass() == "PCB_VIA":
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(o.GetPosition() + d)
            v.SetWidth(max(o.GetWidth(pcbnew.F_Cu), FM(0.3)))
            v.SetDrill(o.GetDrillValue())
            new.append(v)
            continue
        lay = LAYERS.get(pcbnew.LayerName(o.GetLayer()))
        if lay is None:
            return new, f"source copper on {pcbnew.LayerName(o.GetLayer())}"
        arc = o.GetClass() == "PCB_ARC"
        t = pcbnew.PCB_ARC(b) if arc else pcbnew.PCB_TRACK(b)
        t.SetLayer(lid[lay])
        a, z = cut if cut else (o.GetStart(), o.GetEnd())
        t.SetStart(a + d)
        t.SetEnd(z + d)
        if arc:
            t.SetMid(o.GetMid() + d)
        t.SetWidth(o.GetWidth())
        new.append(t)
    for it in new:
        it.SetNet(net)
        clr = CLEAR
        if it.GetClass() == "PCB_VIA":                   # hole to copper 0.2 mm: the ring may be less than that
            clr = max(CLEAR, HOLE - (mm(it.GetWidth(pcbnew.F_Cu)) - mm(it.GetDrillValue())) / 2)
        for lay in it.GetLayerSet().CuStack():
            sh = it.GetEffectiveShape(lay)
            for o in others:
                if o.GetNetCode() != net.GetNetCode() and o.IsOnLayer(lay) and sh.Collide(o.GetEffectiveShape(lay), FM(clr) - 1):
                    bad = f"{pcbnew.LayerName(lay)}: {o.GetNetname().rsplit('/', 1)[-1] or 'no net'}"
                    if o.GetClass() == "PAD":
                        bad += f" ({o.GetParentFootprint().GetReference()}.{o.GetNumber()})"
                    return new, bad
    return new, None



for ref in sys.argv[3:]:
    su, u = src.FindFootprintByReference(ref), b.FindFootprintByReference(ref)
    assert abs(u.GetOrientationDegrees() - su.GetOrientationDegrees()) < 1e-6 and u.IsFlipped() == su.IsFlipped(), ref
    d = u.GetPosition() - su.GetPosition()
    cb = su.GetCourtyard(pcbnew.F_CrtYd).BBox()
    field = (cb.GetLeft(), cb.GetTop(), cb.GetRight(), cb.GetBottom())
    inside = lambda p: field[0] < p.x < field[2] and field[1] < p.y < field[3]  # noqa: E731
    box = (mm(field[0]) - EXIT, mm(field[1]) - EXIT, mm(field[2]) + EXIT, mm(field[3]) + EXIT)
    spad = {p.GetNumber(): g.index[p.m_Uuid.AsString()] for p in su.Pads()}
    done, skipped = [], []
    for pad in u.Pads():
        net, num = pad.GetNet(), pad.GetNumber()
        name = pad.GetNetname()
        if not name or name in RAILS or name.startswith("unconnected-") or num not in spad:
            continue
        if any(i.GetClass() in ("PCB_TRACK", "PCB_VIA", "PCB_ARC") for i in conn.GetConnectedItems(pad)):
            continue
        esc = walk(g, spad[num], inside, box)
        if isinstance(esc, str):
            skipped.append(f"{num} {name.split('/')[-1]} ({esc})")
            continue
        for in5 in ("In4.Cu", "In6.Cu", "In2.Cu"):    # our layer for the source's In5 copper: the first that clears
            LAYERS["In5.Cu"] = in5
            new, bad = build(esc, d, net)
            if not bad or not bad.startswith("In"):
                break
        if bad:
            skipped.append(f"{num} {name.split('/')[-1]} ({bad})")
            continue
        for it in new:
            b.Add(it)
        others += new
        nv = sum(it.GetClass() == "PCB_VIA" for it in new)
        done.append(f"{num} {name.split('/')[-1]}: {len(new) - nv} tracks, {nv} vias")
    print(f"escape_copy {ref}: {len(done)} pads, {len(skipped)} skipped")
    for s in done:
        print("  ", s)
    for s in skipped:
        print("   skipped", s)
pcbnew.SaveBoard(sys.argv[2], b)
