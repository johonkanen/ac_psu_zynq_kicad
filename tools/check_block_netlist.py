#!/usr/bin/env python3
"""Check sheet 1 (ddr3) against juliancoy's board: every pad of the block parts must have the source's net.

    tools/check_block_netlist.py

Exports the netlist of kicad/zynq_card.kicad_sch (kicad-cli) and the pad nets of reference/zynqpcb/DFTBoard.kicad_pcb
(pcbnew, via tools/p2k/bin/kipy; cached in work/jc_pcb_padnets.csv). For the parts placed on sheet 1 (U20: only the
pins of the units on that sheet):
- connectivity: two pads share a net here exactly when they share one on the source board;
- names: the DDR3_* nets, VREF, DDR3_VTT and the rails come out under the expected names (NET_MAP);
- every part of the sheet is on the source board with the same footprint.
Known differences (REUSE_LOG.md) are listed in EXPECTED and reported, not failed.
U20 balls that are not on sheet 1 (e.g. B6 = PS_MIO14, which drove DDR3_VTT_EN in the source, E3) are not compared.
"""
import collections
import csv
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
WORK = os.path.join(ROOT, "work")
PCB = os.path.join(ROOT, "reference", "zynqpcb", "DFTBoard.kicad_pcb")
PADNETS = os.path.join(WORK, "jc_pcb_padnets.csv")
SCH = os.path.join(ROOT, "kicad", "zynq_card.kicad_sch")
SHEET = "/01 ddr3/"  # sheet name on the root (make_skeleton: "NN name")

# source net -> our net: rails renamed; local labels of juliancoy's /DDR3/ sheet get our sheet path (net_name())
NET_MAP = {
    "+1V35": "1V35",
    "+3V3": "3V3",
    "DDR3_VTT_EN": "/DDR3_VTT_EN",  # E3: a sheet port (U8 EN + R25), named by the root sheet
}
# (ref, pad): reason. The net differs from the source by design.
EXPECTED = {}

PADNETS_PY = """
import csv, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
w = csv.writer(open(sys.argv[2], "w", newline=""))
w.writerow(["ref", "pad", "net", "value", "footprint"])
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNumber():
            w.writerow([fp.GetReference(), p.GetNumber(), p.GetNetname(), fp.GetValue(), fp.GetFPIDAsString()])
"""


def source_pads():
    if not os.path.exists(PADNETS) or os.path.getmtime(PADNETS) < os.path.getmtime(PCB):
        os.makedirs(WORK, exist_ok=True)
        script = os.path.join(WORK, "jc_padnets.py")
        open(script, "w").write(PADNETS_PY)
        subprocess.run([os.path.join(TOOLS, "p2k", "bin", "kipy"), script, PCB, PADNETS], check=True,
                       capture_output=True)
    pads, fps = {}, {}
    with open(PADNETS) as f:
        for r in csv.DictReader(f):
            if r["pad"]:
                pads[(r["ref"], r["pad"])] = r["net"]
                fps[r["ref"]] = r["footprint"]
    return pads, fps


def our_netlist():
    out = os.path.join(WORK, "zynq_card_net.xml")
    os.makedirs(WORK, exist_ok=True)
    subprocess.run([os.path.join(TOOLS, "p2k", "bin", "kicad-cli"), "sch", "export", "netlist", "--format",
                    "kicadxml", "-o", out, SCH], check=True, capture_output=True)
    x = ET.parse(out).getroot()
    comps = {}
    for c in x.iter("comp"):
        sheet = c.find("sheetpath").get("names")
        comps[c.get("ref")] = dict(sheet=sheet, footprint=(c.findtext("footprint") or ""), value=c.findtext("value"))
    pads = {}
    for n in x.iter("net"):
        for node in n.iter("node"):
            pads[(node.get("ref"), node.get("pin"))] = n.get("name")
    return comps, pads


def main():
    src, src_fp = source_pads()
    comps, ours = our_netlist()
    block = {r for r, c in comps.items() if c["sheet"] == SHEET and not r.startswith("#")}
    # U20 is on several sheets: compare only the pins that are drawn on sheet 1
    sheet_pins = sheet1_pins()
    keys = sorted(k for k in ours if k[0] in block and (k[0] != "U20" or k[1] in sheet_pins))
    fails = []
    for r in sorted(block):
        if r not in src_fp:
            fails.append(f"{r}: not on the source board")
        elif comps[r]["footprint"] != src_fp[r]:
            fails.append(f"{r}: footprint {comps[r]['footprint']} != source {src_fp[r]}")
    # connectivity by pad sets
    by_ours, by_src = collections.defaultdict(set), collections.defaultdict(set)
    for k in keys:
        if k in EXPECTED:
            continue
        if k not in src:
            fails.append(f"{k[0]}.{k[1]}: pad not on the source board")
            continue
        by_ours[ours[k]].add(k)
        by_src[src[k]].add(k)
    for net, ks in by_ours.items():
        snets = {src[k] for k in ks}
        if len(snets) != 1:
            fails.append(f"net {net}: joins source nets {sorted(snets)}")
            continue
        s = snets.pop()
        if by_src[s] != ks:
            fails.append(f"source net {s} is split here: {sorted(by_src[s] - ks)[:5]}")
        want = net_name(s)
        if not s.startswith("Net-(") and net != want:
            fails.append(f"net {net}: expected the name {want} (source {s})")
    for k, why in EXPECTED.items():
        print(f"expected difference {k[0]}.{k[1]}: here {ours.get(k)}, source {src.get(k)} ({why})")
    named = {n for n in by_ours if n.startswith("DDR3_")}
    print(f"check_block_netlist: {len(block)} parts, {len(keys)} pads, {len(by_ours)} nets "
          f"({len(named)} DDR3_*), {len(fails)} failures")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails or not block else 0


def net_name(src_net):
    if src_net in NET_MAP:
        return NET_MAP[src_net]
    if src_net.startswith("/DDR3/"):
        return SHEET + src_net[len("/DDR3/"):]
    return src_net


def sheet1_pins():
    """Pin numbers of the U20 units placed on sheet 1."""
    sys.path.insert(0, os.path.join(TOOLS, "p2k"))
    from p2k.sexpr import find, find_all, load
    tree = load(os.path.join(ROOT, "kicad", "01_ddr3.kicad_sch"))
    pins = set()
    for s in find_all(tree, "symbol"):
        if any(p[1] == "Reference" and p[2] == "U20" for p in find_all(s, "property")):
            pins |= {p[1] for p in find_all(s, "pin")}
    return pins


if __name__ == "__main__":
    sys.exit(main())
