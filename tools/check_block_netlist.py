#!/usr/bin/env python3
"""Check the block sheets against juliancoy's board: every pad of the block parts must have the source's net.

    tools/check_block_netlist.py

Exports the netlist of kicad/zynq_card.kicad_sch (kicad-cli) and the pad nets of reference/zynqpcb/DFTBoard.kicad_pcb
(pcbnew, via tools/p2k/bin/kipy; cached in work/jc_pcb_padnets.csv). The block parts are every part of sheet 1
(ddr3) and the parts of sheets 5 (soc_power) and 6 (soc_config) with a reference below 200 (the source's: U20, the SoC
decaps, R9/R10). U20 counts with the units drawn on those sheets: every pin on sheets 1 and 5; on sheet 6 only the
balls on a source rail or on a net of another block part (FULL_U20, RAILS). For them:
- connectivity: two pads share a net here exactly when they share one on the source board;
- names: the DDR3_* nets, VREF, DDR3_VTT and the rails come out under the expected names (NET_MAP: +1V0/+1V8/+1V35/
  +3V3 -> ours; the source's sheet-local nets get our sheet path);
- every block part is on the source board with the same footprint.
Known differences (REUSE_LOG.md) are listed in EXPECTED and reported, not failed.
U20 balls on units not drawn yet (e.g. B6 = PS_MIO14, which drove DDR3_VTT_EN in the source, E3) are not compared.
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
# block sheets: our sheet path (make_skeleton: "/NN name/") -> (file, juliancoy's sheet path for its local nets)
SHEETS = {
    "/01 ddr3/": ("01_ddr3.kicad_sch", "/DDR3/"),
    "/05 soc_power/": ("05_soc_power.kicad_sch", "/Power/"),
    "/06 soc_config/": ("06_soc_config.kicad_sch", None),
    "/11 soc_pl/": ("11_soc_pl.kicad_sch", None),
}
# U20 units on these sheets are compared pin by pin. On the other block sheets only the U20 balls on a source rail
# (their fan-out is block copper) or on a net of another block part are: the signal balls are routed here.
FULL_U20 = {"/01 ddr3/", "/05 soc_power/"}
RAILS = {"GND", "+1V0", "+1V8", "+1V35", "+3V3", "/Power/VCCAUX"}

# source net -> our net: rails renamed; local labels of juliancoy's sheets get our sheet path (net_name())
NET_MAP = {
    "+1V0": "1V0",
    "+1V8": "1V8",
    "+1V35": "1V35",
    "+3V3": "3V3",
    "DDR3_VTT_EN": "/DDR3_VTT_EN",  # E3: a sheet port (U8 EN + R25), named by the root sheet
    "PROGRAM_B": "/06 soc_config/cfg_program_n",  # R9
    "INIT_B": "/06 soc_config/cfg_init_n",  # R10
}
# (ref, pad): reason. The net differs from the source by design.
# block parts on another footprint than the source's (REUSE_LOG.md): ref -> (footprint, pad offset allowed, mm, why).
# tools/make_board.py builds them from the library, tools/import_block.py checks their pads within the offset.
FP_SWAP = {
    "C67": ("Capacitor_SMD:C_1206_3216Metric", 0.1,
            "E12: 22 uF 1206 (1.8 mm max) instead of 100 uF 1210 (2.7 mm): over baseboard U17; pads 0.075 mm out"),
}
EXPECTED = {
    ("U20", "H10"): "E5: VCCPLL through FB501, not straight on +1V8",
    ("C59", "1"): "E6: MIO1 (E12) cap, the MIO banks are 1.8 V here",
    ("C122", "1"): "E6: MIO0 (C6) cap, the MIO banks are 1.8 V here",
    **{("U20", b): "E7: VCCO_MIO0 on 1V8 (bank 500 at 1.8 V)" for b in ("B3", "C6")},
    **{("U20", b): "E7: VCCO_MIO1 on 1V8 (bank 501 at 1.8 V)" for b in ("A10", "B13", "D9", "E12")},
    ("U20", "G10"): "E8: RSVDGND left open (UG865 v1.9: do not connect)",
    ("U20", "B6"): "E3: PS_MIO14 no longer drives DDR3_VTT_EN (spare MIO)",
}


def u20_pin_names():
    """{ball: pin name} of the XC7Z020 symbol in lib/zynq_card.kicad_sym."""
    sys.path.insert(0, os.path.join(TOOLS, "p2k"))
    from p2k.sexpr import find, find_all, load
    sym = next(s for s in find_all(load(os.path.join(ROOT, "lib", "zynq_card.kicad_sym")), "symbol")
               if s[1] == "XC7Z020-CLG484")
    return {find(p, "number")[1]: find(p, "name")[1] for sub in find_all(sym, "symbol") for p in find_all(sub, "pin")}


# Banks 34/35 (sheet 11): juliancoy left them unused with VCCO and every I/O ball on GND (UG933 "Unconnected VCCO
# Pins"). Here they are powered (E7) and their I/O balls carry our nets or stay open (E9).
for _ball, _name in u20_pin_names().items():
    for _bank in ("34", "35"):
        if _name.startswith(f"VCCO_{_bank}"):
            EXPECTED[("U20", _ball)] = f"E7: VCCO_{_bank} on 3V3 (bank {_bank} at 3.3 V)"
        elif _name.startswith("IO_") and _name.endswith(f"_{_bank}"):
            EXPECTED[("U20", _ball)] = f"E9: bank {_bank} I/O ball off GND (our net or open)"

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
    block = {r for r, c in comps.items() if c["sheet"] in SHEETS and is_block(r, c["sheet"])}
    # U20 is on several sheets: compare the pins of the units drawn on the block sheets (FULL_U20, RAILS)
    sheet_pins = u20_pins()
    block_nets = {n for (r, _), n in src.items() if r in block and r != "U20" and n}

    def compared(pad):
        sheet = sheet_pins.get(pad)
        net = src.get(("U20", pad))
        return sheet in FULL_U20 or (sheet and (net in RAILS or net in block_nets))

    keys = sorted(k for k in ours if k[0] in block and (k[0] != "U20" or compared(k[1])))
    fails = []
    for r in sorted(block):
        if r not in src_fp:
            fails.append(f"{r}: not on the source board")
        elif comps[r]["footprint"] != src_fp[r]:
            if FP_SWAP.get(r, ("",))[0] == comps[r]["footprint"]:
                print(f"expected difference {r}: footprint {comps[r]['footprint']}, source {src_fp[r]} "
                      f"({FP_SWAP[r][2]})")
            else:
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
    by_why = collections.defaultdict(list)
    for k, why in EXPECTED.items():
        if k in keys:
            by_why[why].append(k)
    for why, ks in by_why.items():
        if len(ks) <= 8:
            for k in ks:
                print(f"expected difference {k[0]}.{k[1]}: here {ours.get(k)}, source {src.get(k)} ({why})")
        else:  # a whole bank: one line
            print(f"expected difference, {len(ks)} pads ({why}): source {sorted({src.get(k) for k in ks})}, "
                  f"here {len({ours.get(k) for k in ks})} nets")
    named = {n for n in by_ours if n.startswith("DDR3_")}
    u20 = [k for k in keys if k[0] == "U20"]
    print(f"check_block_netlist: {len(block)} parts, {len(keys)} pads ({len(u20)} U20 balls), {len(by_ours)} nets "
          f"({len(named)} DDR3_*), {len(fails)} failures")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails or not block else 0


def is_block(ref, sheet):
    """Sheet 1 is all block; elsewhere the block parts keep the source's references, all below 200 (but the
    family connectors J1..J9 are ours)."""
    if ref.startswith(("#", "J")):
        return False
    num = ref.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return sheet == "/01 ddr3/" or (num.isdigit() and int(num) < 200)


def net_name(src_net):
    if src_net in NET_MAP:
        return NET_MAP[src_net]
    for ours, (_, theirs) in SHEETS.items():
        if theirs and src_net.startswith(theirs):
            return ours + src_net[len(theirs):]
    return src_net


def u20_pins():
    """{pin number: our sheet path} of the U20 units placed on the block sheets."""
    sys.path.insert(0, os.path.join(TOOLS, "p2k"))
    from p2k.sexpr import find_all, load
    pins = {}
    for path, (fname, _) in SHEETS.items():
        for s in find_all(load(os.path.join(ROOT, "kicad", fname)), "symbol"):
            if any(p[1] == "Reference" and p[2] == "U20" for p in find_all(s, "property")):
                pins.update({p[1]: path for p in find_all(s, "pin")})
    return pins


if __name__ == "__main__":
    sys.exit(main())
