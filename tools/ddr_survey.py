"""Survey DDR3 routing in a KiCad 6+ board: per-net layers, length, vias; footprint positions."""
import re, sys, math, collections

t = open(sys.argv[1], errors="ignore").read()
pat = sys.argv[2] if len(sys.argv) > 2 else r"DDR|DQ|DM|BA\d|ADDR|CAS|RAS|WE|ODT|CKE|CK_|DRAM|MEM|A\d+$"

nets = dict(re.findall(r'^\s*\(net (\d+) "([^"]*)"\)', t, re.M))
if not nets:  # KiCad 10 uses net names directly on items
    pass

def netname(blk):
    m = re.search(r'\(net (\d+)\)', blk) or re.search(r'\(net "([^"]*)"\)', blk) or re.search(r'\(net \d+ "([^"]*)"\)', blk)
    if not m:
        return None
    v = m.group(1)
    return nets.get(v, v)

seg_len = collections.defaultdict(float)
seg_layers = collections.defaultdict(collections.Counter)
via_n = collections.Counter()
for m in re.finditer(r'\((segment|arc)\b(.*?)\(uuid', t, re.S):
    blk = m.group(2)
    n = netname(blk)
    if n is None:
        continue
    s = re.search(r'\(start ([-\d.]+) ([-\d.]+)\)', blk); e = re.search(r'\(end ([-\d.]+) ([-\d.]+)\)', blk)
    L = math.dist(map(float, s.groups()), map(float, e.groups()))
    if m.group(1) == "arc":
        md = re.search(r'\(mid ([-\d.]+) ([-\d.]+)\)', blk)
        L = math.dist(map(float, s.groups()), map(float, md.groups())) + math.dist(map(float, md.groups()), map(float, e.groups()))
    lay = re.search(r'\(layer "?([^")]+)"?\)', blk).group(1)
    w = float(re.search(r'\(width ([\d.]+)\)', blk).group(1))
    seg_len[n] += L
    seg_layers[n][(lay, round(w, 3))] += L
for m in re.finditer(r'\(via\b(.*?)\(uuid', t, re.S):
    n = netname(m.group(1))
    if n:
        via_n[n] += 1

for fm in re.finditer(r'\(footprint "([^"]+)"\s*(?:\(locked\)|\(layer "([^"]+)"\)|\s)*.*?\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\).*?\(property "Reference" "([^"]+)".*?\(property "Value" "([^"]+)"', t, re.S):
    fp, side, x, y, r, ref, val = fm.groups()
    if re.search(r'BGA|XC7|Xilinx|CLG|FBG|RTL|KSZ|QFN|MT41|KLM|RJ45|Hanrun', fp + val, re.I):
        print(f"FP {ref:6} {val:24} {fp:50} at {x},{y} rot {r} {side}")

edge = [tuple(map(float, g)) for g in re.findall(r'\(gr_(?:line|rect)\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\).*?\(layer "Edge.Cuts"\)', t, re.S)]
if edge:
    xs = [v for e in edge for v in (e[0], e[2])]; ys = [v for e in edge for v in (e[1], e[3])]
    print(f"OUTLINE {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} mm")

sel = sorted(n for n in seg_len if re.search(pat, n.split("/")[-1], re.I))
tot = 0
for n in sel:
    lays = ", ".join(f"{l}@{w}:{L:.1f}" for (l, w), L in seg_layers[n].most_common())
    print(f"{n:40} {seg_len[n]:7.2f} mm  vias {via_n[n]:2}  {lays}")
    tot += seg_len[n]
print(f"{len(sel)} nets, {tot:.0f} mm")
