#!/usr/bin/env python3
"""U20 I/O breakout stubs copied from juliancoy's board (kipy; REUSE_LOG E14):

    tools/p2k/bin/kipy tools/escape_u20.py [BOARD]

For every U20 signal ball that has no copper yet (the import drops juliancoy's MIO/PL escapes, LAYOUT_PLAN.md step
2) and that juliancoy escapes, his copper from the ball is copied on our net: the F.Cu dog-bone or surface run, the
via, and the track on to the edge of the ball field, cut EXIT mm past U20's courtyard. Routing (phase 4) starts from
the stub end. His escape is walked from the ball through his copper while it stays in the field; a walk that reaches
another pad is skipped. A ball whose copied copper would come closer than CLEAR to our copper on another net (our
parts and E-edits under the BGA differ from his) is dropped and listed. The balls he does not escape (his GND and
unused balls: bank 34 for J3, some MIO) get theirs from tools/fanout_u20.sh. Idempotent: a ball with copper is left.
"""
import os
import sys

import pcbnew

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from import_block import SOURCE, Graph  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(TOOLS), "kicad", "zynq_card.kicad_pcb")
SKIP = {"H10"}                     # VCCPLL: its planelet is REUSE_LOG E5 (phase 4)
EXIT, CLEAR = 0.5, 0.102            # stub end past the courtyard; copper clearance to other nets (board minimum), mm
mm, FM = pcbnew.ToMM, pcbnew.FromMM


def bare_signal_balls(b, u):
    """Our U20 balls on a signal net (two or more pads on the board, no zone) with no track or via on them."""
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    zoned = {z.GetNetname() for z in b.Zones() if not z.GetIsRuleArea()}
    npads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            npads[p.GetNetname()] = npads.get(p.GetNetname(), 0) + 1
    out = {}
    for p in u.Pads():
        n = p.GetNetname()
        if not n or n.startswith("unconnected-") or n in zoned or npads[n] < 2:
            continue
        if p.GetNumber() not in SKIP and not any(i.GetClass() in ("PCB_TRACK", "PCB_VIA", "PCB_ARC") for i in conn.GetConnectedItems(p)):
            out[p.GetNumber()] = p
    return out


def clip(a, z, box):
    """The point where the segment a (inside box) -> z (outside) leaves box (x0, y0, x1, y1)."""
    t = 1.0
    for k, (lo, hi) in enumerate(((box[0], box[2]), (box[1], box[3]))):
        d = z[k] - a[k]
        for edge in (lo, hi):
            if d and 0 <= (edge - a[k]) / d < t and ((edge == lo and d < 0) or (edge == hi and d > 0)):
                t = (edge - a[k]) / d
    return a[0] + t * (z[0] - a[0]), a[1] + t * (z[1] - a[1])


def walk(g, s, inside, box):
    """juliancoy's copper from ball item s while it stays in the field: [(item, cut end or None)], or why not."""
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
            if o.GetClass() != "PCB_TRACK":
                return "an arc"
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


def main():
    src, b = pcbnew.LoadBoard(SOURCE), pcbnew.LoadBoard(PCB)
    su, u = src.FindFootprintByReference("U20"), b.FindFootprintByReference("U20")
    assert abs(u.GetOrientationDegrees() - su.GetOrientationDegrees()) < 1e-6, "escape_u20: block not at rotation 0"
    d = u.GetPosition() - su.GetPosition()
    cb = su.GetCourtyard(pcbnew.F_CrtYd).BBox()
    field = (cb.GetLeft(), cb.GetTop(), cb.GetRight(), cb.GetBottom())
    inside = lambda p: field[0] < p.x < field[2] and field[1] < p.y < field[3]
    box = (mm(field[0]) - EXIT, mm(field[1]) - EXIT, mm(field[2]) + EXIT, mm(field[3]) + EXIT)
    g = Graph(src)
    spad = {p.GetNumber(): g.index[p.m_Uuid.AsString()] for p in su.Pads()}

    others = [t for t in b.GetTracks()]
    others += [p for fp in b.GetFootprints() for p in fp.Pads()]
    done, skipped, dropped = [], [], []
    for ball, pad in sorted(bare_signal_balls(b, u).items()):
        net = pad.GetNet()
        esc = walk(g, spad[ball], inside, box)
        if isinstance(esc, str):
            skipped.append(f"{ball} ({esc})")
            continue
        new = []
        for o, cut in esc:
            if o.GetClass() == "PCB_VIA":
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(o.GetPosition() + d)
                v.SetWidth(o.GetWidth(pcbnew.F_Cu))
                v.SetDrill(o.GetDrillValue())
                new.append(v)
            else:
                t = pcbnew.PCB_TRACK(b)
                t.SetLayer(o.GetLayer())
                a, z = cut if cut else (o.GetStart(), o.GetEnd())
                t.SetStart(a + d)
                t.SetEnd(z + d)
                t.SetWidth(o.GetWidth())
                new.append(t)
        for it in new:
            it.SetNet(net)
        hit = None
        for it in new:
            for lay in it.GetLayerSet().CuStack():
                sh = it.GetEffectiveShape(lay)
                for o in others:
                    if o.GetNetCode() == net.GetNetCode() or not o.IsOnLayer(lay):
                        continue
                    if sh.Collide(o.GetEffectiveShape(lay), FM(CLEAR) - 1):
                        hit = f"{b.GetLayerName(lay)}: {o.GetNetname().rsplit('/', 1)[-1] or 'no net'}"
                        if o.GetClass() == "PAD":
                            hit += f" ({o.GetParentFootprint().GetReference()}.{o.GetNumber()})"
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            dropped.append(f"{ball} {net.GetNetname().rsplit('/', 1)[-1]} ({hit})")
            continue
        for it in new:
            b.Add(it)
        others += new
        nv = sum(it.GetClass() == "PCB_VIA" for it in new)
        exits = sorted({b.GetLayerName(o.GetLayer()) for o, cut in esc if cut})
        done.append(f"{ball} {net.GetNetname().rsplit('/', 1)[-1]}: {len(new) - nv} tracks, {nv} vias, "
                    f"out on {'/'.join(exits) or 'nothing (stays in the field)'}")
    pcbnew.SaveBoard(PCB, b)
    print(f"escape_u20: {len(done)} balls escaped from juliancoy's copper, {len(dropped)} dropped (clash), "
          f"{len(skipped)} without a copyable escape")
    for s in done:
        print("  ", s)
    for s in dropped:
        print("   dropped", s)
    print("   none or not copyable:", ", ".join(skipped))


if __name__ == "__main__":
    main()
