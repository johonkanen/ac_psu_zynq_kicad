#!/usr/bin/env python3
"""Sheet 1 (ddr3): the DDR3 block schematic, imported from juliancoy/zynqPCB (MIT, NOTICE).

Source: reference/zynqpcb/DDR3.sch (KiCad 5 legacy, sheet path /58818A06/ in DFTBoard.sch). KiCad 10 cannot save a
legacy schematic from the command line, so this script converts the sheet itself, element by element, at the
source coordinates (PLAN.md §4.2 step 1):
- every symbol keeps its reference (from the AR line of the DDR3 sheet path), unit, position, rotation and fields;
- wires, junctions, no-connects, labels and notes are copied 1:1; the global DDR3_* labels keep their names;
- the library symbols become lib/zynq_card.kicad_sym ones (tools/gen_symbols.py); for each placed unit the pin
  positions are checked against the KiCad 5 symbol of the cache library, so the connectivity cannot change;
- power symbols are renamed to our rails: +1V35 -> 1V35, +3V3 -> 3V3 (the copper import maps the nets the same way).

Changes to the block (REUSE_LOG.md):
- E3: the global label DDR3_VTT_EN (U8 EN; driven from PS_MIO14 + 20 k to 3V3 on juliancoy's Storage sheet) becomes
  a hierarchical label (sheet port), to be driven by our power sequencing;
- E4: U15/U16 value MT41K256M16HA-125:E -> MT41K256M16TW-107:P (same FBGA-96 land); the KiCad 5 SnapEDA fields
  (Field4..Field8) that name the old part are dropped.
"""
import os
import re

from _common import *  # noqa: F401,F403
from _common import ROOT, Sym, _eff, U  # noqa: F401
from p2k.sch_builder import lib
from p2k.sexpr import find, find_all, load

SRC = os.path.join(ROOT, "reference", "zynqpcb", "DDR3.sch")
SRC_PATH = "/58818A06/"  # DDR3 sheet instance in DFTBoard.sch
JC_SYM = os.path.join(ROOT, "work", "jc_cache.kicad_sym")  # written by tools/gen_symbols.py
MIL = 0.0254

LIB_MAP = {
    "xilinx7:xc7z020clg484": "XC7Z020-CLG484",
    "DFTBoard-rescue:MT41K256M16HA-125_E-MT41K256M16HA-125_E": "MT41K256M16-FBGA96",
    "tps51200DRCR:TPS51200DRCR": "TPS51200",
    "Device:R": "R",
    "Device:R_Small": "R_Small",
    "Device:C_Small": "C_Small",
    "DFTBoard-rescue:LED-": "LED",
    "power:GND": "GND",
    "power:+1V35": "1V35",
    "power:+3V3": "3V3",
    "power:PWR_FLAG": "PWR_FLAG",
}
# legacy transform matrix (x_sch = a*x + b*y, y_sch = c*x + d*y, library Y up) -> eeschema rotation (CCW)
ROT = {(1, 0, 0, -1): 0, (0, -1, -1, 0): 90, (-1, 0, 0, 1): 180, (0, 1, 1, 0): 270}
FIELD_NAMES = {0: "Reference", 1: "Value", 2: "Footprint", 3: "Datasheet"}
SHAPES = {"Input": "input", "Output": "output", "BiDi": "bidirectional", "3State": "tri_state", "UnSpc": "passive"}

E3_PORT = "DDR3_VTT_EN"
E4_REFS = ("U15", "U16")
E4_VALUE = "MT41K256M16TW-107:P"
E4_FIELDS = {"MPN": E4_VALUE, "SPN": "", "LCSC": "C253882"}
E4_DROP = {"Field4", "Field5", "Field6", "Field7", "Field8"}


def mm(v):
    return round(int(v) * MIL, 4)


# ------------------------------------------------------------------ legacy reader

def read_legacy(path):
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
            ar = [r for p, r in c["ar"].items() if p.startswith(SRC_PATH)]
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


def place(sh, c, name, ref, pins, project):
    x, y, rot = mm(c["x"]), mm(c["y"]), ROT[c["matrix"]]
    node = [Sym("symbol"), [Sym("lib_id"), f"{project}:{name}"], [Sym("at"), x, y, rot], [Sym("unit"), c["unit"]],
            [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("no")], [Sym("uuid"), U(f"sym:{ref}:{c['unit']}")]]
    seen = set()
    for f in c["fields"]:
        key = FIELD_NAMES.get(f["n"]) or f["name"]
        val = f["text"]
        if f["n"] == 0:
            val = ref
        elif f["n"] == 1 and ref.startswith("#PWR"):
            val = name  # the power symbol's value is the net name
        if ref in E4_REFS:
            if key in E4_DROP:
                continue
            if key == "Value":
                val = E4_VALUE
            val = E4_FIELDS.get(key, val)
        if key in seen:  # a KiCad 5 custom field named like a KiCad 10 built-in one
            continue
        seen.add(key)
        node.append(field_node(key, val, f, (x, y)))
    if ref in E4_REFS:
        for key in E4_FIELDS.keys() - seen:
            node.append([Sym("property"), key, E4_FIELDS[key], [Sym("at"), x, y, 0], _eff(hide=True)])
    for num in pins:
        node.append([Sym("pin"), num, [Sym("uuid"), U(f"pin:{ref}:{c['unit']}:{num}")]])
    node.append([Sym("instances"), [Sym("project"), project,
                                    [Sym("path"), sh.inst_path, [Sym("reference"), ref], [Sym("unit"), c["unit"]]]]])
    sh._cache(name)
    sh._add(node)


# ------------------------------------------------------------------ text items

def text_node(t):
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
    if t["kind"] == "GLabel" and t["text"] == E3_PORT:  # E3
        return [Sym("hierarchical_label"), t["text"], [Sym("shape"), Sym("input")], [Sym("at"), x, y, rot],
                [Sym("effects"), font, [Sym("justify"), Sym(just)]], [Sym("uuid"), U()]]
    if t["kind"] == "GLabel":
        return [Sym("global_label"), t["text"], [Sym("shape"), shape], [Sym("at"), x, y, rot],
                [Sym("fields_autoplaced"), Sym("yes")], [Sym("effects"), font, [Sym("justify"), Sym(just)]],
                [Sym("uuid"), U()],
                [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), x, y, 0], _eff(just, hide=True)]]
    raise ValueError(f"unhandled text kind {t['kind']}")


NOTE = ("DDR3 block from juliancoy/zynqPCB (MIT, NOTICE), imported by tools/sheets/01_ddr3.py from DDR3.sch.\n"
        "References and DDR3_* names are the source's. Changes: REUSE_LOG.md E3 (DDR3_VTT_EN is a sheet port,\n"
        "driven by our power sequencing), E4 (U15/U16 MT41K256M16TW-107:P). Do not edit by hand.")


def main():
    comps, wires, junctions, noconns, texts = read_legacy(SRC)
    sh = Sheet(os.path.join(ROOT, "kicad", "01_ddr3.kicad_sch")).clear()  # noqa: F405
    find(sh.tree, "paper")[1] = "A3"  # the source is A4, but its U20 unit runs into the frame
    project = sh.project
    theirs = {s[1]: s for s in find_all(load(JC_SYM), "symbol")}
    ours = lib()
    pwr = 0
    refs = set()
    for c in comps:
        name = LIB_MAP[c["lib"]]
        jc_name = c["lib"].replace(":", "_")
        pins = check_pins(c, ours[name], theirs[jc_name])
        if c["ref"].startswith("#"):
            pwr += 1
            ref = f"{c['ref'][:4]}{pwr:03d}"
        else:
            ref = c["ref"]
            if "?" in ref:
                raise ValueError(f"unannotated part at {c['x']},{c['y']}: {c['lib']}")
            if (ref, c["unit"]) in refs:
                raise ValueError(f"duplicate {ref} unit {c['unit']}")
            refs.add((ref, c["unit"]))
        place(sh, c, name, ref, pins, project)
    for x1, y1, x2, y2 in wires:
        sh.wire((mm(x1), mm(y1)), (mm(x2), mm(y2)))
    for x, y in junctions:
        sh.junction(mm(x), mm(y))
    for x, y in noconns:
        sh.no_connect(mm(x), mm(y))
    for t in texts:
        sh._add(text_node(t))
    sh.text(NOTE, 12.7, 200.66)
    sh.pwr = pwr
    sh.save()
    parts = sorted({r for r, _ in refs})
    print(f"01_ddr3: {len(parts)} parts, {pwr} power symbols, {len(wires)} wires, {len(texts)} texts")


if __name__ == "__main__":
    main()
