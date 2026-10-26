"""UG933 DDR3 review of a Zynq-7000 board: die-to-die delays per pad-to-pad path, topology, termination parts.

Run under KiCad's Python: tools/p2k/bin/kipy tools/ddr3_review.py BOARD.kicad_pcb [--soc U2] [--dram U1]
                                [--mts 1066] [--json OUT.json]

- Paths are walked along the copper (segments, arcs, vias) from the SoC pad to the DRAM pad, so a fly-by stub or a
  branch to a termination resistor is not counted in the SoC -> DRAM delay. Stubs are reported separately.
- Delay = SoC pad-to-die (the footprint's pad die length x 6 ps/mm, the convention used to store it, see
  pinguz97 scripts/footprint_add_die_lengths.py) + copper length x the per-layer speed + vias.
- Per-layer speeds: from tools/zsolve_cases.py for JLC08121H-1080A (outer SE 5.95, outer diff 5.75, inner 6.75 ps/mm).
- Limits: UG933 Table 5-9 (+/-10 ps at the rated speed) and the Appendix A derating tables (DDR3L).
"""
import argparse, collections, heapq, json, math, re, sys
import pcbnew

ap = argparse.ArgumentParser()
ap.add_argument("board")
ap.add_argument("--soc", default="U2")
ap.add_argument("--dram", default="U1")
ap.add_argument("--mts", type=int, default=1066, help="operating data rate (MT/s)")
ap.add_argument("--json")
ap.add_argument("--ps-outer", type=float, default=5.95, help="outer SE speed, ps/mm (default JLC08121H-1080A)")
ap.add_argument("--ps-outer-diff", type=float, default=5.75)
ap.add_argument("--ps-inner", type=float, default=6.75, help="inner speed, ps/mm; JLC081611-7628: 6.63 (In2/In4), 6.80 (In6)")
ap.add_argument("--pkg", help="Xilinx package delay CSV (bank,ball,site,function,min ps,max ps,...): use its mean "
                "delay per ball instead of the footprint's pad die length")
a = ap.parse_args()

PS_OUTER, PS_OUTER_DIFF, PS_INNER = a.ps_outer, a.ps_outer_diff, a.ps_inner
PS_VIA = 7.0            # ps per mm of via barrel (rough; only the barrel between the two layers used)
DIE_PS_PER_MM = 6.0     # die length was stored as delay / 6 ps/mm
# UG933 Appendix A, DDR3L, SoC rated 1066, memory rated 1866 (MT41K256M16TW-107): {actual MT/s: (DQ-DQS, Addr-CK)} ps
DERATE = {1066: (91, 123), 800: (150, 150)}

b = pcbnew.LoadBoard(a.board)
mm = pcbnew.ToMM
layer_z = {}  # copper layer -> z from the top (mm), for via barrel lengths
z = 0.0
# the stack-up is read from the file: the SWIG stack-up descriptor is not iterable in KiCad 10's Python
txt = open(a.board, errors="ignore").read()
if "(stackup" in txt:
    txt = txt[txt.index("(stackup"):]
    for m in re.finditer(r'\(layer "([^"]+)"\s*(?:\d+\s*)?\(type "([^"]+)"\)\s*(?:\(color [^)]*\)\s*)?(?:\(thickness ([\d.]+)\))?',
                         txt[:txt.index("(copper_finish") if "(copper_finish" in txt else len(txt)]):
        name, typ, th = m.groups()
        if typ == "copper":
            layer_z[b.GetLayerID(name)] = z
        z += float(th or 0)
else:   # no stack-up in the file: spread the copper layers evenly over the board thickness
    cu = [l for l in range(pcbnew.PCB_LAYER_ID_COUNT) if pcbnew.IsCopperLayer(l) and b.IsLayerEnabled(l)]
    cu.sort(key=lambda l: (l != pcbnew.F_Cu, l == pcbnew.B_Cu, l))
    th = mm(b.GetDesignSettings().GetBoardThickness())
    for i, l in enumerate(cu):
        layer_z[l] = th * i / max(1, len(cu) - 1)

def speed(layer, diff):
    if layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        return PS_OUTER_DIFF if diff else PS_OUTER
    return PS_INNER

fp = {f.GetReference(): f for f in b.GetFootprints()}
PKG = {}
if a.pkg:
    import csv
    for row in csv.reader(open(a.pkg)):
        try:
            PKG[row[1]] = (float(row[4]) + float(row[5])) / 2
        except (IndexError, ValueError):
            pass
soc, dram = fp[a.soc], fp[a.dram]

def is_ddr(n):
    return re.search(r"DDR", n) and not re.search(r"VTT|VREF|VDD|1V35|0V675|VRN|VRP|ZQ", n)

nets = sorted({p.GetNetname() for p in soc.Pads() if is_ddr(p.GetNetname())})

def key(p):
    return (round(p.x / 1000), round(p.y / 1000))   # 1 um grid

def build_graph(net):
    """Nodes: (x_um, y_um, layer). Edges: track pieces (length, layer) and vias. Pads connect their layers."""
    G = collections.defaultdict(list)
    def add(u, v, L, kind, lay):
        G[u].append((v, L, kind, lay)); G[v].append((u, L, kind, lay))
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == "PCB_VIA":
            p = key(t.GetPosition())
            lays = sorted((l for l in layer_z if t.IsOnLayer(l)), key=lambda l: layer_z[l])
            for l0, l1 in zip(lays, lays[1:]):
                add(p + (l0,), p + (l1,), abs(layer_z[l1] - layer_z[l0]), "via", None)
        else:
            add(key(t.GetStart()) + (t.GetLayer(),), key(t.GetEnd()) + (t.GetLayer(),), mm(t.GetLength()), "trk",
                t.GetLayer())
    return G

def pad_nodes(G, pad):
    """Graph nodes that lie on the pad copper (any of its layers)."""
    out = []
    for n in list(G):
        x, y, l = n
        if pad.IsOnLayer(l) and pad.HitTest(pcbnew.VECTOR2I(x * 1000, y * 1000)):
            out.append(n)
    return out

def shortest(G, src, dst, diff):
    """Dijkstra on delay from any src node to any dst node; returns (delay, length per layer, vias, path nodes)."""
    dst = set(dst)
    pq = [(0.0, n) for n in src]; best = {n: 0.0 for n in src}; prev = {}
    heapq.heapify(pq)
    while pq:
        d, u = heapq.heappop(pq)
        if u in dst:
            per = collections.Counter(); vias = set(); n = u
            while n in prev:
                p, L, kind, lay = prev[n]
                if kind == "via":
                    vias.add(n[:2])     # one via spans several layer hops
                else:
                    per[b.GetLayerName(lay)] += L
                n = p
            return d, per, len(vias), u
        if d > best.get(u, 1e18):
            continue
        for v, L, kind, lay in G[u]:
            w = L * (PS_VIA if kind == "via" else speed(lay, diff))
            if d + w < best.get(v, 1e18):
                best[v] = d + w; prev[v] = (u, L, kind, lay); heapq.heappush(pq, (d + w, v))
    return None

rows = {}
for net in nets:
    short = net.split("/")[-1]
    diff = bool(re.search(r"_[PN]$", short))
    G = build_graph(net)
    sp = [p for p in soc.Pads() if p.GetNetname() == net][0]
    dps = [p for p in dram.Pads() if p.GetNetname() == net]
    others = [(f.GetReference(), p.GetNumber(), f.GetValue()) for f in b.GetFootprints()
              if f.GetReference() not in (a.soc, a.dram) for p in f.Pads() if p.GetNetname() == net]
    die = mm(sp.GetPadToDieLength())
    if PKG:
        die = PKG.get(sp.GetNumber(), 0.0) / DIE_PS_PER_MM
    r = dict(net=short, soc_pad=sp.GetNumber(), die_mm=round(die, 3), others=others)
    # a series resistor between the SoC and the DRAM: follow it onto the second net
    legs = [(G, sp, None)]
    if not dps:
        for ref, num, val in others:
            if not ref.startswith("R") or len(fp[ref].Pads()) != 2:
                continue
            rin = [p for p in fp[ref].Pads() if p.GetNumber() == num][0]
            rout = [p for p in fp[ref].Pads() if p.GetNumber() != num][0]
            d2 = [p for p in dram.Pads() if p.GetNetname() == rout.GetNetname()]
            if d2:
                r["series"] = (ref, val, rout.GetNetname().split("/")[-1])
                legs = [(G, sp, rin), (build_graph(rout.GetNetname()), rout, d2[0])]
                dps = d2
                break
    else:
        legs = [(G, sp, dps[0])]
    if not dps:
        r["error"] = "no DRAM pad"
    else:
        d = 0.0; per = collections.Counter(); vias = 0; ok = True
        for g, p0, p1 in legs:
            res = shortest(g, pad_nodes(g, p0), pad_nodes(g, p1), diff)
            if res is None:
                ok = False; break
            d += res[0]; per.update(res[1]); vias += res[2]
        if "series" in r:   # the resistor body: pad centre to pad centre on the top layer
            rr = fp[r["series"][0]].Pads()
            Lr = mm((rr[0].GetPosition() - rr[1].GetPosition()).EuclideanNorm())
            d += Lr * PS_OUTER; per["(R body)"] += Lr
        if not ok:
            r["error"] = "no copper path SoC -> DRAM"
        else:
            r.update(dram_pad=dps[0].GetNumber(), board_ps=round(d, 1), total_ps=round(d + die * DIE_PS_PER_MM, 1),
                     length_mm=round(sum(per.values()), 2), layers={k: round(v, 2) for k, v in per.items()}, vias=vias)
            if "series" in r:   # where the series resistor sits: SoC -> R leg length
                r["soc_to_R_mm"] = round(sum(shortest(G, pad_nodes(G, sp), pad_nodes(G, legs[0][2]), diff)[1].values()), 2)
        # termination branch: DRAM pad -> resistor pad
        for ref, num, val in others:
            if not ref.startswith("R"):
                continue
            rp = [p for p in fp[ref].Pads() if p.GetNumber() == num][0]
            res2 = shortest(G, pad_nodes(G, dps[0]), pad_nodes(G, rp), diff)
            if res2:
                r.setdefault("to_term", []).append((ref, val, round(sum(res2[1].values()), 2)))
    rows[short] = r

def grp(name):
    n = re.sub(r"^DDR3?L?_", "", name)
    if m := re.match(r"DQ(\d+)$", n):
        return f"byte{int(m.group(1)) // 8}"
    if m := re.match(r"(?:DM|DQS)(\d)", n):
        return f"byte{m.group(1)}"
    if re.match(r"CK_?[PN+-]$", n):
        return "clock"
    if re.search(r"RST|RESET", n):
        return "reset"
    return "addr_cmd"

def find(pat):
    """The row whose net name matches pat (e.g. DQS0 P side, CK N side), whatever the board's naming."""
    for n in rows:
        if re.fullmatch(pat, re.sub(r"^DDR3?L?_", "", n)):
            return n
    return None

groups = collections.defaultdict(list)
for n, r in rows.items():
    groups[grp(n)].append(r)

lim_dq, lim_ac = DERATE.get(a.mts, (10, 10))
print(f"# {a.board}  SoC {a.soc} -> DRAM {a.dram}, {a.mts} MT/s; derated limits DQ-DQS +/-{lim_dq} ps, "
      f"addr/cmd-CK +/-{lim_ac} ps (UG933 App. A, DDR3L); rated-speed limit +/-10 ps (Table 5-9)\n")
for r in rows.values():
    if "error" in r:
        print("ERROR", r["net"], r["error"])

def tot(n):
    return rows[n].get("total_ps")

ck = [tot(n) for n in (find(r"CK_?[P+]"), find(r"CK_?[N-]")) if n and tot(n) is not None]
ckm = sum(ck) / len(ck) if ck else None
print(f"{'net':16} {'ball':5} {'die mm':>6} {'len mm':>7} {'vias':>4} {'total ps':>8}  {'skew ps':>8}  layers")
summary = {}
for g in sorted(groups):
    rs = sorted(groups[g], key=lambda r: r["net"])
    if g.startswith("byte"):
        i = g[-1]
        dqp, dqn = find(rf"DQS_?P?{i}_?P?\+?"), find(rf"DQS_?N?{i}_?N?-?")
        ref = [tot(dqp) if dqp else None, tot(dqn) if dqn else None]
        if None in ref:
            continue    # this byte lane is not on this DRAM
        refm = sum(ref) / 2
        refname = f"DQS{i}"
    elif g in ("addr_cmd", "clock"):
        refm, refname = ckm, "CK"
    else:
        refm, refname = None, ""
    print(f"-- {g} (skew vs {refname or '-'})")
    sk = []
    for r in rs:
        if "total_ps" not in r:
            continue
        s = None if refm is None else r["total_ps"] - refm
        if s is not None and grp(r["net"]) != "clock" and not re.search(r"DQS", r["net"]):
            sk.append(s)
        lays = " ".join(f"{k}:{v}" for k, v in r["layers"].items())
        term = " term " + ", ".join(f"{x}({v}) {L} mm" for x, v, L in r.get("to_term", [])) if r.get("to_term") else ""
        if "series" in r:
            term += f" series {r['series'][0]}({r['series'][1]}) at {r['soc_to_R_mm']} mm from the SoC"
        print(f"{r['net']:16} {r['soc_pad']:5} {r['die_mm']:6.2f} {r['length_mm']:7.2f} {r['vias']:4} "
              f"{r['total_ps']:8.1f}  {'' if s is None else f'{s:+8.1f}'}  {lays}{term}")
    if g.startswith("byte"):
        p, n = ref
        summary[g] = dict(dq_dqs_min=round(min(sk), 1), dq_dqs_max=round(max(sk), 1), dqs_pn=round(abs(p - n), 1),
                          dqs_ps=round(refm, 1))
    elif g == "addr_cmd":
        summary[g] = dict(ac_ck_min=round(min(sk), 1), ac_ck_max=round(max(sk), 1))
    elif g == "clock":
        summary[g] = dict(ck_pn=round(abs(ck[0] - ck[1]), 1), ck_ps=round(ckm, 1))
print("\n# summary")
for g, s in summary.items():
    print(g, s)
for g, s in summary.items():
    if g.startswith("byte"):
        ok = max(abs(s["dq_dqs_min"]), abs(s["dq_dqs_max"])) <= lim_dq
        print(f"{g}: DQ/DM-DQS {s['dq_dqs_min']}..{s['dq_dqs_max']} ps -> {'PASS' if ok else 'FAIL'} (derated "
              f"+/-{lim_dq}); rated +/-10: {'PASS' if max(abs(s['dq_dqs_min']), abs(s['dq_dqs_max'])) <= 10 else 'FAIL'}"
              f"; CK >= DQS: {'PASS' if ckm >= s['dqs_ps'] else 'FAIL'} ({ckm - s['dqs_ps']:+.1f} ps)")
if "addr_cmd" in summary:
    s = summary["addr_cmd"]
    ok = max(abs(s["ac_ck_min"]), abs(s["ac_ck_max"])) <= lim_ac
    print(f"addr_cmd: A/C-CK {s['ac_ck_min']}..{s['ac_ck_max']} ps -> {'PASS' if ok else 'FAIL'} (derated +/-{lim_ac})"
          f"; rated +/-10: {'PASS' if max(abs(s['ac_ck_min']), abs(s['ac_ck_max'])) <= 10 else 'FAIL'}")
if a.json:
    json.dump(dict(rows=rows, summary=summary), open(a.json, "w"), indent=1)
