#!/usr/bin/env python3
"""Write the JLC assembly part numbers (`LCSC` field) into the schematic sheets (run after the sheet scripts:
tools/build_schematic.sh does).

A part is matched by its BOM line as tools/jlc/jlc_bom_cpl.py forms it: the MPN field (else the value) and the footprint
name. PARTS gives the LCSC number, and for juliancoy's exact parts that we buy as a JLC basic equivalent, the new MPN
(the source's MFR/SPN/SPR/SPURL fields name the old part and are dropped). REFS overrides single parts. Parts that
already have an LCSC field (set by their sheet script) are left alone; the connectors in HAND are hand-soldered and
get none. Chosen 2026-10-29 from JLC's stock (reports/jlc/bom_jlcpcb_filled.csv): basic parts where there is one,
capacitor voltage at least 6.3 V (4 V for 0402 X5R on rails up to 1V8), C0G below 1 nF.
Fails when a part with a footprint has no LCSC number and is not in HAND.
"""
import glob
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.sexpr import Sym, find, find_all, load, save  # noqa: E402

HAND = {"J1", "J2", "J3", "J5", "J6", "J9"}   # hand-soldered (user, 2026-10-29); J9 keeps its LCSC for reference

# (MPN or value, footprint name): (LCSC, new MPN or None)
PARTS = {
    # juliancoy's block parts (Digi-Key numbers in the source)
    ("CC0402KRX5R5BB474", "C_0402_1005Metric"): ("C47339", "CL05A474KP5NNNC"),
    ("GRM155R60G475ME47D", "C_0402_1005Metric"): ("C23733", "CL05A475MP5NRNC"),
    ("GRM188R61A106KE69J", "C_0603_1608Metric"): ("C19702", "CL10A106KP8NNNC"),
    ("JMK325ABJ107MM-P", "C_1210_3225Metric"): ("C49066", "CL32A107MQVNNNE"),
    ("GRM155R71H103KA88J", "C_0402_1005Metric"): ("C15195", "CL05B103KB5NNNC"),
    ("CC0402KRX7R6BB104", "C_0402_1005Metric"): ("C1525", "CL05B104KO5NNNC"),
    ("VLMB1300-GS08", "C_0603_1608Metric"): ("C435849", None),
    ("RT0402BRD0720KL", "R_0402_1005Metric"): ("C705630", None),        # 0.1 %, kept
    ("RC0402FR-07240RL", "R_0402_1005Metric"): ("C114755", None),
    ("RC0402FR-0710KL", "R_0402_1005Metric"): ("C25744", "0402WGF1002TCE"),
    ("RC0402FR-0780R6L", "R_0402_1005Metric"): ("C185392", None),
    ("RC0402FR-0740R2L", "R_0402_1005Metric"): ("C274892", None),
    ("RC0402JR-074K7L", "R_0402_1005Metric"): ("C25900", "0402WGF4701TCE"),
    ("RC0402FR-07100KL", "R_0402_1005Metric"): ("C25741", "0402WGF1003TCE"),
    ("RC0402FR-07150RL", "R_0402_1005Metric"): ("C140202", "RC-02K1500FT"),
    ("TPS51200DRCR", "VSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.4mm_ThermalVias"): ("C34771", None),
    (".47uF", "C_0402_1005Metric"): ("C47339", None),
    ("4.7uF", "C_0402_1005Metric"): ("C23733", None),
    ("47uF", "C_0805_2012Metric"): ("C16780", None),
    ("100uF", "C_1210_3225Metric"): ("C49066", None),
    ("4.7k", "R_0402_1005Metric"): ("C25900", None),
    # ours: capacitors
    ("100n", "C_0402_1005Metric"): ("C1525", None),
    ("10n", "C_0402_1005Metric"): ("C15195", None),
    ("220n", "C_0402_1005Metric"): ("C16772", None),
    ("470n", "C_0402_1005Metric"): ("C47339", None),
    ("1u", "C_0402_1005Metric"): ("C52923", None),
    ("2u2", "C_0402_1005Metric"): ("C12530", None),
    ("4u7", "C_0402_1005Metric"): ("C23733", None),
    ("4u7", "C_0603_1608Metric"): ("C19666", None),
    ("10u", "C_0603_1608Metric"): ("C19702", None),
    ("10u", "C_0805_2012Metric"): ("C15850", None),
    ("22u", "C_0805_2012Metric"): ("C45783", None),
    ("47u", "C_1206_3216Metric"): ("C96123", None),
    ("47u", "C_1210_3225Metric"): ("C77101", None),
    ("100u", "C_1210_3225Metric"): ("C49066", None),
    ("330u", "CP_EIA-7343-31_Kemet-D"): ("C116744", "T520D337M006ATE015"),   # polymer, 6.3 V, 15 mOhm
    ("22p", "C_0402_1005Metric"): ("C1555", None),
    ("27p", "C_0402_1005Metric"): ("C107002", None),
    ("680p C0G", "C_0402_1005Metric"): ("C113781", None),
    # ours: resistors (1 %, 0402)
    ("0R", "R_0402_1005Metric"): ("C17168", None),
    ("22R", "R_0402_1005Metric"): ("C25092", None),
    ("33", "R_0402_1005Metric"): ("C25105", None),
    ("33R", "R_0402_1005Metric"): ("C25105", None),
    ("100R", "R_0402_1005Metric"): ("C25076", None),
    ("330", "R_0402_1005Metric"): ("C25104", None),
    ("330R", "R_0402_1005Metric"): ("C25104", None),
    ("1k", "R_0402_1005Metric"): ("C11702", None),
    ("2.49k 1%", "R_0402_1005Metric"): ("C25884", None),
    ("4k7", "R_0402_1005Metric"): ("C25900", None),
    ("10k", "R_0402_1005Metric"): ("C25744", None),
    ("20k", "R_0402_1005Metric"): ("C25765", None),
    ("47k", "R_0402_1005Metric"): ("C25792", None),
    ("66.5k", "R_0402_1005Metric"): ("C2998095", None),
    ("100k", "R_0402_1005Metric"): ("C25741", None),
    ("121k", "R_0402_1005Metric"): ("C11693", None),
    ("124k", "R_0402_1005Metric"): ("C2933070", None),
    ("200k", "R_0402_1005Metric"): ("C25764", None),
    ("453k", "R_0402_1005Metric"): ("C27009", None),
    # ours: the rest
    ("red", "LED_0603_1608Metric"): ("C2286", "KT-0603R"),
    ("BLM18SG121TN1D", "L_0603_1608Metric"): ("C113030", None),
    ("BLM15PX121SN1D", "L_0402_1005Metric"): ("C88970", None),
    ("NCP163ASN330T1G", "SOT-23-5"): ("C603656", None),
    ("TPS3808G01DBVR", "SOT-23-6"): ("C19653", None),
    ("25MHz", "Crystal_SMD_3225-4Pin_3.2x2.5mm"): ("C70593", "X322525MRB4SI"),   # 18 pF load: 27 p + ~4 pF stray
}
# ref: {field: value}, on every unit
REFS = {
    # -2 (or -3) speed grade, either temperature grade (user, 2026-10-29); the -1 is not used
    "U20": {"Value": "XC7Z020-2CLG484I", "MPN": "XC7Z020-2CLG484I", "LCSC": "C157624"},
}
SOURCE_FIELDS = ("MFR", "SPN", "SPR", "SPURL")


def props(sym):
    return {p[1]: p for p in find_all(sym, "property")}


def set_prop(sym, key, value):
    ps = props(sym)
    if key in ps:
        ps[key][2] = value
        return
    at = find(sym, "at")
    sym.insert(sym.index(ps["Datasheet"]) + 1 if "Datasheet" in ps else len(sym),
               [Sym("property"), key, value, [Sym("at"), at[1], at[2], 0],
                [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("hide"), Sym("yes")]]])


def main():
    missing, n = [], 0
    for path in sorted(glob.glob(os.path.join(ROOT, "kicad", "*.kicad_sch"))):
        tree, changed = load(path), False
        for sym in find_all(tree, "symbol"):
            ps = props(sym)
            ref = ps.get("Reference", [0, 0, ""])[2]
            fpn = ps.get("Footprint", [0, 0, ""])[2].split(":")[-1]
            if not fpn or ref.startswith("#"):
                continue
            if ref in REFS:
                for k, v in REFS[ref].items():
                    set_prop(sym, k, v)
                changed = True
                continue
            if ps.get("LCSC", [0, 0, ""])[2] or ref in HAND:
                continue
            mpn = ps.get("MPN", [0, 0, ""])[2]
            hit = PARTS.get((mpn or ps["Value"][2], fpn))
            if hit is None:
                missing.append(f"{ref} ({mpn or ps['Value'][2]}, {fpn})")
                continue
            lcsc, new = hit
            set_prop(sym, "LCSC", lcsc)
            if new:
                set_prop(sym, "MPN", new)
                sym[:] = [c for c in sym if not (isinstance(c, list) and c and c[0] == "property"
                                                 and c[1] in SOURCE_FIELDS)]
            changed, n = True, n + 1
        if changed:
            save(path, tree)
    print(f"set_lcsc: {n} parts given an LCSC number, {', '.join(REFS)} set")
    if missing:
        sys.exit("set_lcsc: no LCSC number for " + ", ".join(sorted(set(missing))))


if __name__ == "__main__":
    main()
