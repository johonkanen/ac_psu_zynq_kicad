"""KiCad 5 legacy sheet import for the block sheets (tools/sheets/01_ddr3.py, 05_soc_power.py).

KiCad 10 cannot save a legacy schematic from the command line (`kicad-cli sch upgrade` fails on save), so the block
sheets of juliancoy/zynqPCB (reference/zynqpcb/*.sch) are converted here, element by element, at the source
coordinates (PLAN.md §4.2 step 1):
- every symbol keeps its reference (from the AR line of the source sheet path), unit, position, rotation and fields;
- wires, junctions, no-connects and labels are copied 1:1;
- the library symbols become lib/zynq_card.kicad_sym ones (tools/gen_symbols.py); for each placed unit the pin
  positions are checked against the KiCad 5 symbol of the cache library, so the connectivity cannot change;
- power symbols are renamed to our rails (RAILS); the copper import maps the nets the same way.

convert() can keep a subset of the parts (keep=): the wires, labels, junctions and power symbols that then connect
to no kept pin are dropped too (prune()), so a sheet can take the block parts of a source sheet and leave the rest.
"""
import os
import re

from _common import ROOT, Sym, _eff, U  # noqa: F401
from p2k.sch_builder import lib
from p2k.sexpr import find, find_all, load

JC_DIR = os.path.join(ROOT, "reference", "zynqpcb")
JC_SYM = os.path.join(ROOT, "work", "jc_cache.kicad_sym")  # written by tools/gen_symbols.py
MIL = 0.0254

LIB_MAP = {
    "xilinx7:xc7z020clg484": "XC7Z020-CLG484",
    "DFTBoard-rescue:MT41K256M16HA-125_E-MT41K256M16HA-125_E": "MT41K256M16-FBGA96",
    "tps51200DRCR:TPS51200DRCR": "TPS51200",
    "Device:R": "R",
    "Device:R_Small": "R_Small",
    "Device:C_Small": "C_Small",
    "Device:Ferrite_Bead_Small": "FerriteBead_Small",
    "DFTBoard-rescue:LED-": "LED",
    "power:PWR_FLAG": "PWR_FLAG",
}
# source rail -> our power symbol
RAILS = {"power:GND": "GND", "power:+1V0": "1V0", "power:+1V8": "1V8", "power:+1V35": "1V35", "power:+3V3": "3V3"}
# legacy transform matrix (x_sch = a*x + b*y, y_sch = c*x + d*y, library Y up) -> eeschema rotation (CCW)
ROT = {(1, 0, 0, -1): 0, (0, -1, -1, 0): 90, (-1, 0, 0, 1): 180, (0, 1, 1, 0): 270}
# mirrored ones -> (rotation, mirror): eeschema rotates first, then "mirror x" flips Y, "mirror y" flips X
MIRROR = {}
for _m, _r in ROT.items():
    MIRROR.setdefault((_m[0], _m[1], -_m[2], -_m[3]), (_r, "x"))
    MIRROR.setdefault((-_m[0], -_m[1], _m[2], _m[3]), (_r, "y"))
FIELD_NAMES = {0: "Reference", 1: "Value", 2: "Footprint", 3: "Datasheet"}
SHAPES = {"Input": "input", "Output": "output", "BiDi": "bidirectional", "3State": "tri_state", "UnSpc": "passive"}


def mm(v):
    return round(int(v) * MIL, 4)


# ------------------------------------------------------------------ legacy reader

def read_legacy(path, src_path):
    """Components, wires, junctions, no-connects and texts of a KiCad 5 sheet. src_path is the sheet instance path
    (e.g. "/58818A06/"): a component's reference is the one its AR line gives for that path."""
    lines = open(path, encoding="utf-8").read().split("\n")
    comps, wires, junctions, noconns, texts = [], [], [], [], []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("$Comp"):
            c = {"fields": [], "ar": {}}
            i += 1
            while not lines[i].startswith("$EndComp"):
                t = lines[i]
                if t.startswith("L "):
                    _, c["lib"], c["ref"] = t.split()
                elif t.startswith("U "):
                    c["unit"] = int(t.split()[1])
                elif t.startswith("P "):
                    c["x"], c["y"] = (int(v) for v in t.split()[1:3])
                elif t.startswith("AR "):
                    m = re.match(r'AR Path="([^"]*)" Ref="([^"]*)"', t)
                    c["ar"][m.group(1)] = m.group(2)
                elif t.startswith("F "):
                    m = re.match(r'F (\d+) "((?:[^"\\]|\\.)*)" ([HV]) (-?\d+) +(-?\d+) +(\d+) +(\d+) ([LCR]) ([TCB])\S*'
                                 r'(?: +"([^"]*)")?', t)
                    c["fields"].append(dict(n=int(m.group(1)), text=m.group(2), orient=m.group(3),
                                            x=int(m.group(4)), y=int(m.group(5)), size=int(m.group(6)),
                                            hidden=m.group(7)[-1] == "1", hj=m.group(8), vj=m.group(9),
                                            name=m.group(10)))
                elif t.startswith("\t") and len(t.split()) == 4:
                    c["matrix"] = tuple(int(v) for v in t.split())
                i += 1
            ar = [r for p, r in c["ar"].items() if p.startswith(src_path)]
            c["ref"] = ar[0] if ar else c["ref"]
            comps.append(c)
        elif ln.startswith("Wire Wire Line"):
            wires.append(tuple(int(v) for v in lines[i + 1].split()))
            i += 1
        elif ln.startswith("Connection ~"):
            junctions.append(tuple(int(v) for v in ln.split()[2:4]))
        elif ln.startswith("NoConn ~"):
            noconns.append(tuple(int(v) for v in ln.split()[2:4]))
        elif ln.startswith("Text "):
            f = ln.split()
            texts.append(dict(kind=f[1], x=int(f[2]), y=int(f[3]), orient=int(f[4]), size=int(f[5]),
                              shape=f[6], text=lines[i + 1].replace("\\n", "\n")))
            i += 1
        elif ln.startswith(("Wire ", "Entry ", "$Bitmap", "$Sheet")):
            raise ValueError(f"unhandled legacy item: {ln}")
        i += 1
    return comps, wires, junctions, noconns, texts


# ------------------------------------------------------------------ symbols

def unit_pins(sym, unit):
    """{pin number: (x, y)} of one unit (plus the common unit 0), body style 1, library coordinates."""
    out = {}
    for sub in find_all(sym, "symbol"):
        _, u, style = sub[1].rsplit("_", 2)
        if int(u) in (0, unit) and int(style) in (0, 1):
            for p in find_all(sub, "pin"):
                at = find(p, "at")
                out[find(p, "number")[1]] = (round(float(at[1]), 4), round(float(at[2]), 4))
    return out


def check_pins(c, ours, theirs):
    """The pins of our symbol must sit where the KiCad 5 symbol had them (same numbers, same positions)."""
    a, b = unit_pins(ours, c["unit"]), unit_pins(theirs, c["unit"])
    if a != b:
        raise ValueError(f"{c['ref']} ({c['lib']} unit {c['unit']}): pins differ from the source symbol: "
                         f"{sorted(set(a.items()) ^ set(b.items()))[:6]}")
    return a


def pin_points(c, pins):
    """{pin number: (x, y) in mils} of a placed legacy component."""
    a, b, cc, d = c["matrix"]
    out = {}
    for num, (px, py) in pins.items():
        px, py = round(px / MIL), round(py / MIL)
        out[num] = (c["x"] + a * px + b * py, c["y"] + cc * px + d * py)
    return out


def field_node(key, val, f, sym_xy):
    just = {"L": "left", "R": "right", "C": None}[f["hj"]]
    vj = {"T": "top", "B": "bottom", "C": None}[f["vj"]]
    j = " ".join(v for v in (just, vj) if v)
    size = round(f["size"] * MIL, 4)
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if j:
        eff.append([Sym("justify"), *[Sym(v) for v in j.split()]])
    # an empty field of the KiCad 5 file sits at the origin; put it on the symbol instead
    x, y = (mm(f["x"]), mm(f["y"])) if (f["x"], f["y"]) != (0, 0) else sym_xy
    node = [Sym("property"), key, val, [Sym("at"), x, y, 0 if f["orient"] == "H" else 90]]
    if f["hidden"]:
        node.append([Sym("hide"), Sym("yes")])
    node.append(eff)
    return node


def place(sh, c, name, ref, pins, edit=None):
    """Place a legacy component. edit (block changes, REUSE_LOG.md): {"value": new value, "fields": {key: value}
    (replaced, or added hidden), "drop": {field names}}."""
    edit = edit or {}
    x, y = mm(c["x"]), mm(c["y"])
    rot, mirror = (ROT[c["matrix"]], None) if c["matrix"] in ROT else MIRROR[c["matrix"]]
    node = [Sym("symbol"), [Sym("lib_id"), f"{sh.project}:{name}"], [Sym("at"), x, y, rot]]
    if mirror:
        node.append([Sym("mirror"), Sym(mirror)])
    node += [[Sym("unit"), c["unit"]], [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("no")], [Sym("uuid"), U(f"sym:{ref}:{c['unit']}")]]
    fields = edit.get("fields", {})
    seen = set()
    for f in c["fields"]:
        key = FIELD_NAMES.get(f["n"]) or f["name"]
        if key in edit.get("drop", ()) or key in seen:  # seen: a KiCad 5 custom field named like a built-in one
            continue
        val = f["text"]
        if f["n"] == 0:
            val = ref
        elif f["n"] == 1:
            val = name if ref.startswith("#PWR") else edit.get("value", val)  # a power symbol's value is its net
        val = fields.get(key, val)
        seen.add(key)
        node.append(field_node(key, val, f, (x, y)))
    for key in fields.keys() - seen:
        node.append([Sym("property"), key, fields[key], [Sym("at"), x, y, 0], _eff(hide=True)])
    for num in pins:
        node.append([Sym("pin"), num, [Sym("uuid"), U(f"pin:{ref}:{c['unit']}:{num}")]])
    node.append([Sym("instances"), [Sym("project"), sh.project,
                                    [Sym("path"), sh.inst_path, [Sym("reference"), ref], [Sym("unit"), c["unit"]]]]])
    sh._cache(name)
    sh._add(node)


# ------------------------------------------------------------------ text items

def text_node(t, ports=()):
    """A legacy text item; global labels named in `ports` become hierarchical labels (sheet ports)."""
    x, y, size = mm(t["x"]), mm(t["y"]), round(t["size"] * MIL, 4)
    # spin style 0..3: text right of / above / left of / below the anchor; KiCad 5 global and hierarchical labels
    # count the other way round (0 = text left of the anchor)
    o = t["orient"] if t["kind"] in ("Label", "Notes") else (t["orient"] + 2) % 4
    rot = {0: 0, 1: 90, 2: 180, 3: 270}[o]
    just = "left" if o in (0, 1) else "right"
    font = [Sym("font"), [Sym("size"), size, size]]
    if t["kind"] == "Notes":
        return [Sym("text"), t["text"], [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x, y, rot],
                [Sym("effects"), font, [Sym("justify"), Sym("left"), Sym("bottom")]], [Sym("uuid"), U()]]
    if t["kind"] == "Label":
        return [Sym("label"), t["text"], [Sym("at"), x, y, rot],
                [Sym("effects"), font, [Sym("justify"), Sym(just), Sym("bottom")]], [Sym("uuid"), U()]]
    shape = Sym(SHAPES[t["shape"]])
    if t["kind"] == "GLabel" and t["text"] in ports:
        return [Sym("hierarchical_label"), t["text"], [Sym("shape"), Sym("input")], [Sym("at"), x, y, rot],
                [Sym("effects"), font, [Sym("justify"), Sym(just)]], [Sym("uuid"), U()]]
    if t["kind"] == "GLabel":
        return [Sym("global_label"), t["text"], [Sym("shape"), shape], [Sym("at"), x, y, rot],
                [Sym("fields_autoplaced"), Sym("yes")], [Sym("effects"), font, [Sym("justify"), Sym(just)]],
                [Sym("uuid"), U()],
                [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), x, y, 0], _eff(just, hide=True)]]
    raise ValueError(f"unhandled text kind {t['kind']}")


# ------------------------------------------------------------------ pruning

def _on(p, w):
    """Point p lies on wire w (end points included)."""
    x1, y1, x2, y2 = w
    return (min(x1, x2) <= p[0] <= max(x1, x2) and min(y1, y2) <= p[1] <= max(y1, y2)
            and (x2 - x1) * (p[1] - y1) == (y2 - y1) * (p[0] - x1))


def prune(wires, junctions, noconns, labels, kept_pins, power_pins):
    """Drop what a reduced sheet no longer needs. kept_pins: points of the kept parts' pins; power_pins: {power
    symbol index: point}. Wires are dropped when they hang off the sheet's kept connectivity: a wire end that meets
    nothing but this wire (no other wire, kept pin, label or power symbol) is removed, repeatedly; and so is every
    wire of a group that holds no kept pin. Returns the kept (wires, junctions, noconns, labels, power indices)."""
    kept_pins = set(kept_pins)
    wires = list(wires)
    lab_pts = {(t["x"], t["y"]) for t in labels}
    pwr_pts = set(power_pins.values())

    def anchors(p, ws):
        n = sum(1 for w in ws if _on(p, w))
        return n + (p in kept_pins) + (p in lab_pts) + (p in pwr_pts)

    changed = True
    while changed:
        changed = False
        for w in list(wires):
            for p in ((w[0], w[1]), (w[2], w[3])):
                if anchors(p, wires) == 1:
                    wires.remove(w)
                    changed = True
                    break
    # groups: wires joined at shared points; a label joins its point, a pin its point
    parent = list(range(len(wires)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(wires):
        for j in range(i):
            b = wires[j]
            if any(_on(p, b) for p in ((a[0], a[1]), (a[2], a[3]))) or any(_on(p, a) for p in ((b[0], b[1]), (b[2], b[3]))):
                parent[root(i)] = root(j)
    live = {root(i) for i, w in enumerate(wires) if any(_on(p, w) for p in kept_pins)}
    wires = [w for i, w in enumerate(wires) if root(i) in live]

    def touched(p):
        return p in kept_pins or any(_on(p, w) for w in wires)

    labels = [t for t in labels if touched((t["x"], t["y"]))]
    power = [k for k, p in power_pins.items() if touched(p)]
    junctions = [j for j in junctions if sum(1 for w in wires if _on(j, w)) + (j in kept_pins) >= 3]
    noconns = [n for n in noconns if n in kept_pins]
    return wires, junctions, noconns, labels, power


# ------------------------------------------------------------------ the sheet

def convert(sh, src, src_path, keep=None, edits=None, symbols=None, ports=(), notes=True, rails=None, cut=()):
    """Draw a legacy sheet (or the parts of it for which keep(c) is true) onto `sh` at the source coordinates.
    edits: {ref: place() edit}; symbols: {ref: our symbol name} for a part that takes another symbol (its pins are
    checked like the rest); ports: global labels that become sheet ports; notes: copy the Notes texts; cut: source
    wires (x1, y1, x2, y2 in mils) to leave out, for a block change that re-wires a pin (what then hangs loose is
    pruned).
    Returns {"parts": {(ref, unit)}, "power": n, "wires": n, "texts": n}."""
    comps, wires, junctions, noconns, texts = read_legacy(os.path.join(JC_DIR, src), src_path)
    missing = set(cut) - set(wires)
    if missing:
        raise ValueError(f"cut: no such wire in {src}: {sorted(missing)}")
    wires = [w for w in wires if w not in cut]
    rails = {**RAILS, **(rails or {})}
    theirs = {s[1]: s for s in find_all(load(JC_SYM), "symbol")}
    ours = lib()
    edits, symbols = edits or {}, symbols or {}
    parts, power, kept_pins = [], {}, []
    for c in comps:
        is_pwr = c["ref"].startswith("#")
        if is_pwr and c["lib"] not in rails and c["lib"] not in LIB_MAP:
            # a rail we do not have (+5V): its pin is at the origin; prune() must drop it
            power[len(parts)] = (c["x"], c["y"])
            parts.append((c, None, None))
            continue
        if not is_pwr:
            if keep and not keep(c):
                continue
            name = symbols.get(c["ref"], LIB_MAP[c["lib"]])
        else:
            name = rails.get(c["lib"]) or LIB_MAP[c["lib"]]
        pins = check_pins(c, ours[name], theirs[c["lib"].replace(":", "_")])
        pts = pin_points(c, pins)
        if is_pwr:
            power[len(parts)] = next(iter(pts.values()))
        else:
            if "?" in c["ref"]:
                raise ValueError(f"unannotated part at {c['x']},{c['y']}: {c['lib']}")
            kept_pins += pts.values()
        parts.append((c, name, pins))
    labels = [t for t in texts if t["kind"] != "Notes"]
    if keep:
        wires, junctions, noconns, labels, kept_pwr = prune(wires, junctions, noconns, labels, kept_pins, power)
        parts = [p for k, p in enumerate(parts) if k not in power or k in kept_pwr]
    out = {"parts": set(), "power": 0, "wires": len(wires), "texts": 0}
    for c, name, pins in parts:
        if name is None:
            raise ValueError(f"{c['lib']} at {c['x']},{c['y']} is still connected and has no rail here (RAILS)")
        if c["ref"].startswith("#"):
            sh.pwr += 1
            ref = f"{c['ref'][:4]}{sh.pwr:03d}"
            out["power"] += 1
        else:
            ref = c["ref"]
            if (ref, c["unit"]) in out["parts"]:
                raise ValueError(f"duplicate {ref} unit {c['unit']}")
            out["parts"].add((ref, c["unit"]))
        place(sh, c, name, ref, pins, edits.get(ref))
    for x1, y1, x2, y2 in wires:
        sh.wire((mm(x1), mm(y1)), (mm(x2), mm(y2)))
    for x, y in junctions:
        sh.junction(mm(x), mm(y))
    for x, y in noconns:
        sh.no_connect(mm(x), mm(y))
    kept = {id(t) for t in labels}
    for t in texts:  # in source order
        if id(t) in kept or (notes and t["kind"] == "Notes"):
            sh._add(text_node(t, ports))
            out["texts"] += 1
    return out
