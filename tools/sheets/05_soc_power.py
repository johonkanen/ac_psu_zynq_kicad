#!/usr/bin/env python3
"""Sheet 5 (soc_power): U20 unit 9 (core/aux supplies, GND) and the SoC decoupling.

Two parts:
1. The block: juliancoy's power.sch (sheet path /58508414/), converted by _legacy.convert() at the source coordinates,
   keeping only U20 unit 9 and the decaps that sit in the block copper (BLOCK). Their refs are the source's, so the
   copper import maps them. Unit 1 (config/XADC), JTAG, R9/R10 belong on sheet 6; juliancoy's regulators,
   sequencers and current-sense parts (U1-U5, U7, L1-L4, R1-R8, R88-R90, C1-C3, C6, C7, C10, C12, C13, C22, C25,
   C27, C32, C108) are dropped: our power stage is sheets 2-4.
2. Ours (C501.., FB501): the VCCPLL filter (E5) and what UG933 Tables 3-1/3-2 (CLG484, Z-7020) need beyond the
   block's caps, plus the block's 3V3 caps that juliancoy drew on other sheets (BLOCK_OTHER, source refs).

Rails (ZYNQ_PCB_NOTES.md §2): 1V0 = VCCINT + VCCBRAM + VCCPINT; 1V8 = VCCPAUX, VCCAUX (through FB1, now 0 ohm),
VCCO_MIO0/MIO1, VCCO_0 (bank 0 at 1.8 V as on juliancoy, decided 2026-10-27), VCCADC; VCCPLL from 1V8 through FB501;
1V35 = VCCO_DDR (sheet 1); 3V3 = VCCO_13/33/34/35. The VCCO pins sit on the bank units (sheets 1, 6, 11); their caps
are here, as rail rows.

Block changes (REUSE_LOG.md):
- E5: VCCPLL (H10) is cut from +1V8 and fed through FB501 + 10 uF + 0.47 uF (UG933 Ch. 5: a must when VCCPLL comes
  from VCCPAUX; juliancoy had the bead on VCCAUX instead). FB1 stays on its land as a 0 ohm jumper, so VCCAUX is on
  1V8 and the 1V8 caps count for it.
- E6: C59 (ball E12) and C122 (ball C6) were +3V3 MIO caps on juliancoy; both MIO banks are 1.8 V here.
"""
import os

from _common import *  # noqa: F401,F403
from _common import ROOT
from _legacy import convert
from p2k.sexpr import find

# power.sch decaps in the block copper: footprint centre within 4 mm of the U20 body (|dx|, |dy| <= 13.5 mm from the
# U20 centre on DFTBoard.kicad_pcb). C6/C12/C22/C25/C27/C32 (bulk at 15-22 mm, among juliancoy's regulators) are out.
BLOCK = {"C4", "C5", "C8", "C9", "C11", "C14", "C15", "C17", "C18", "C19", "C20", "C23", "C24", "C26", "C28", "C29",
         "C30", "C31", "C33", "C34", "FB1"}
# E5: the source wire from C6/C5 to the VCCPLL pin (H10); the C5-C6 stub then hangs loose and is pruned
E5_CUT = [(3200, 5800, 10150, 5800)]
E5_FB1 = {"value": "0", "fields": {"Description": "0 ohm jumper on juliancoy's VCCAUX bead land (REUSE_LOG E5)",
                                   "MFR": "UNI-ROYAL", "MPN": "0603WAF0000T5E", "LCSC": "C21189"},
          "drop": {"SPN", "SPR", "SPURL"}}  # the source fields name the bead

C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
C7343 = "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D"
L0603 = "Inductor_SMD:L_0603_1608Metric"

# the block's other 3V3 decaps under U20 (juliancoy drew them on the LCD50/Audio/USB/Storage sheets); value and
# footprint as on DFTBoard.kicad_pcb. The ball each one sits at is in the comment.
BLOCK_OTHER_3V3 = [
    ("C116", ".47uF", C0402),  # V11 bank 13
    ("C117", ".47uF", C0402),  # Y7 bank 13
    ("C118", ".47uF", C0402),  # AA10 bank 13
    ("C50", ".47uF", C0402),  # U18 bank 33
    ("C65", ".47uF", C0402),  # U18 bank 33
    ("C46", ".47uF", C0402),
    ("C47", ".47uF", C0402),
    ("C55", ".47uF", C0402),
    ("C119", ".47uF", C0402),
    ("C121", ".47uF", C0402),
    ("C57", "4.7uF", C0402),  # U18 bank 33
    ("C114", "4.7uF", C0402),
    ("C61", "47uF", "Capacitor_SMD:C_0805_2012Metric"),
    ("C67", "100uF", C1210),
]
BLOCK_OTHER_1V8 = [("C59", "4.7uF", C0402), ("C122", "4.7uF", C0402)]  # E6: E12 (MIO1), C6 (MIO0)

cn = [500]


def cref():
    cn[0] += 1
    return f"C{cn[0]}"


def caps(spec):
    out = []
    for val, n, fp, *sym in spec:
        out += [(cref(), val, fp, *sym) for _ in range(n)]
    return out


NOTE = ("U20 unit 9 and the SoC decoupling. Left/bottom: juliancoy/zynqPCB power.sch (MIT, NOTICE), converted by\n"
        "tools/sheets/05_soc_power.py: only the decaps in the block copper, source refs and positions. Do not edit by\n"
        "hand. Changes: REUSE_LOG.md E5 (VCCPLL through FB501, FB1 = 0 ohm), E6 (C59/C122 on 1V8: MIO banks at 1.8 V).\n"
        "UG933 Tables 3-1/3-2 (CLG484, Z-7020) per merged rail; the C5xx rows add what the block lacks.\n"
        "0.47 uF within 12.7 mm of the BGA edge, 4.7 uF within 50 mm, bulk anywhere near (UG933 Ch. 3).")

COUNT = ("UG933 count, block + C5xx:\n"
         "1V0  (VCCINT+VCCBRAM+VCCPINT): 330u 1, 100u 2, 4u7 4, 470n 8\n"
         "     block C28 100u, C9 C24 4u7, C8 C23 C29 C30 C31 470n (+ C11 10u)\n"
         "1V8  (VCCAUX+VCCPAUX+MIO0+MIO1+VCCO_0): 100u 3, 47u 2, 4u7 4, 470n 5\n"
         "     block C5 C19 C20 C59 C122 4u7, C4 C14 C15 C17 C18 C34 470n (+ C26 C33 10u)\n"
         "VCCPLL: 120R bead + 10u 0603 + 0.47-4.7u 0402 within 5.1 mm of the H10/GND vias\n"
         "1V35 (VCCO_DDR): 100u 1, 4u7 1, 470n 4; sheet 1 has C99 100u, C100 4u7, C101 470n\n"
         "3V3  (VCCO_13/33/34/35): 47u 1 (one per four HR banks), 4u7 8, 470n 16\n"
         "     block C61 47u, C67 100u, C57 C114 4u7, ten 470n (banks 13/33; banks 34/35 had VCCO on GND)")


def main():
    sh = Sheet(os.path.join(ROOT, "kicad", "05_soc_power.kicad_sch")).clear()  # noqa: F405
    find(sh.tree, "paper")[1] = "A3"
    r = convert(sh, "power.sch", "/58508414/", notes=False, cut=E5_CUT,
                keep=lambda c: c["ref"] in BLOCK or (c["ref"] == "U20" and c["unit"] == 9),
                symbols={"FB1": "R_Small"}, edits={"FB1": E5_FB1})
    got = {p for p, _ in r["parts"]} - {"U20"}
    if got != BLOCK:
        raise ValueError(f"block parts: missing {sorted(BLOCK - got)}, extra {sorted(got - BLOCK)}")
    sh.text(NOTE, g(10), g(30))  # noqa: F405
    sh.text(COUNT, g(232), g(52))  # noqa: F405

    # UG933 rows: what the block lacks (C5xx), and the block's caps from juliancoy's other sheets
    rows = [
        ((g(10), g(48)), "1V0", "1V0: VCCINT/VCCBRAM/VCCPINT bulk and the missing mid/high-frequency caps",  # noqa: F405
         caps([("330u", 1, C7343, "C_Polarized"), ("100u", 1, C1210), ("4u7", 2, C0402),
               ("470n", 3, C0402)])),
        ((g(90), g(48)), "1V8", "1V8: VCCPAUX, MIO0, MIO1 100u; VCCAUX, VCCO_0 47u",  # noqa: F405
         caps([("100u", 3, C1210), ("47u", 2, C1210)])),
        ((g(150), g(48)), "1V35", "1V35 VCCO_DDR: 3 more 470n at bank 502",  # noqa: F405
         caps([("470n", 3, C0402)])),
        ((g(10), g(80)), "3V3", "3V3 VCCO_34 (no caps in the block)",  # noqa: F405
         caps([("4u7", 3, C0402), ("470n", 3, C0402)])),
        ((g(190), g(80)), "3V3", "3V3 VCCO_35 (no caps in the block)",  # noqa: F405
         caps([("4u7", 3, C0402), ("470n", 3, C0402)])),
        ((g(10), g(180)), "3V3", "Block 3V3 caps under U20 (juliancoy's other sheets, source refs): banks 13/33",  # noqa: F405
         BLOCK_OTHER_3V3),
        ((g(150), g(180)), "1V8", "Block, E6: MIO1 (E12), MIO0 (C6)", BLOCK_OTHER_1V8),  # noqa: F405
    ]
    for (x, y), rail, title, cs in rows:
        cap_row(sh, x, y, rail, cs, title, pitch=g(8))  # noqa: F405

    # E5: VCCPLL. H10 is the top pin of the converted unit 9, at the source position (10150, 5800) mil
    h10 = (257.81, 147.32)
    sh.wire(h10, left(h10, 6))  # noqa: F405
    sh.label("VCCPLL", *left(h10, 6), 180)  # noqa: F405
    x0, y0 = g(262), g(84)  # noqa: F405
    fb = "FB501"
    pll = [(cref(), "10u", C0603), (cref(), "470n", C0402)]
    sh.text("E5: VCCPLL from 1V8 through a 120R bead (UG933 Fig. 5-2:\n"
            "BLM18SG121TN1D, GRM188R60J106ME47, GRM155R60J474KE19).\n"
            f"Planelet >= 2 mm wide, < 76 mm long, {pll[0][0]} to the H10 via;\n"
            f"{pll[1][0]} within 5.1 mm of trace from the H10/GND vias.\n"
            "Replaces juliancoy's direct +1V8.",
            x0 - g(4), y0 - g(8))  # noqa: F405
    _, a, b = horiz2(sh, "FerriteBead_Small", fb, x0 + g(8), y0, "BLM18SG121TN1D", text="above")  # noqa: F405
    set_field(sh, fb, "Footprint", L0603)  # noqa: F405
    sh.wire(a, left(a, 3)); power_at(sh, "1V8", left(a, 3), "left")  # noqa: F405
    node = right(b, 4)  # noqa: F405
    sh.wire(b, node)
    for j, (ref, val, fp) in enumerate(pll):
        cx = node[0] + j * g(8)  # noqa: F405
        _, ct, cb = vert2(sh, "C", ref, cx, y0 + g(5), val, text="right")  # noqa: F405
        set_field(sh, ref, "Footprint", fp)  # noqa: F405
        sh.wire((cx, y0), ct)
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
    end = (node[0] + g(14), y0)  # noqa: F405
    sh.wire(node, (node[0] + g(8), y0), end)  # noqa: F405
    sh.junction(*node); sh.junction(node[0] + g(8), y0)  # noqa: F405
    sh.label("VCCPLL", *end, 0)
    sh.wire(end, up(end, 3)); sh.pwr_flag(*up(end, 3), 0)  # noqa: F405  # the bead drives the VCCPLL power input

    sh.save()
    print(f"05_soc_power: {len(got)} block parts + U20 unit 9, {r['power']} source power symbols, "
          f"{r['wires']} source wires; ours FB501, C501..C{cn[0]}")


if __name__ == "__main__":
    main()
