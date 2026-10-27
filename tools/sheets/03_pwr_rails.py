#!/usr/bin/env python3
"""Sheet 3 (pwr_rails): 4 x TLV62585 (1V0, 1V8, 3V3, 1V35) and the NCP163 3V3_analog LDO.

Cells: the Ti135 card's TLV62585 cell (_power.py; Ti135 sheets 02/03) and its NCP163 circuit (Ti135 sheet 01).
Sizing (POWER_BUDGET.md, high case / 3 A part): 1V0 2.40 A (80 %, 2 x 22 u out), 1V8 0.40 A, 1V35 0.97 A, 3V3 0.49 A;
L WPN4020H1R0MT Isat 5.8 A > the 4 A switch limit. R2 = 100 k; R1 66.5 k / 200 k / 124 k / 453 k ->
0.999 / 1.800 / 1.344 / 3.318 V. Soft start 900 us (EN to 95 %), so every ramp is inside DS187 Table 7 (0.2-50 ms).
Enable chain (sheet 4, ZYNQ_PCB_NOTES.md §3): 1V0 (EN = 5V0) -> pg_1v0 -> 1V8 -> pg_1v8 -> 3V3 and 1V35 together ->
PG(3V3) & PG(1V35) wired AND = DDR3_VTT_EN (TPS51200 EN, sheet 1; pulled up by R25 to 3V3) -> PS_POR_B supervisor.
"""
from _common import *  # noqa: F401,F403
from _power import buck

sh = sheet("03_pwr_rails.kicad_sch")  # noqa: F405
sh.text("Order (sheet 4): 1V0 -> 1V8 (VCCPAUX, VCCPLL, VCCAUX, VCCO_MIO, bank 0) -> 3V3 (HR banks) and 1V35 (VCCO_DDR, DDR3L)\n"
        "-> DDR3_VTT_EN (TPS51200, sheet 1) -> U401 (300 ms) -> PS_POR_B. 1V8 is up before 3V3 starts: VCCO - VCCAUX <= 2.625 V.",
        g(14), g(14))  # noqa: F405
X = [g(50), g(160), g(270)]  # noqa: F405
buck(sh, {"U": "U301", "L": "L301", "R1": "R301", "R2": "R302", "CIN": "C301", "COUT": ["C302", "C303"], "CFF": "C304"},
     X[0], g(48), "1V0", "66.5k", pg="pg_1v0", couts=2,  # noqa: F405
     title="1V0: VCCPINT, VCCINT, VCCBRAM (2.40 A high)")
buck(sh, {"U": "U311", "L": "L311", "R1": "R311", "R2": "R312", "CIN": "C311", "COUT": ["C312"], "CFF": "C313"},
     X[1], g(48), "1V8", "200k", en="pg_1v0", pg="pg_1v8", couts=1,  # noqa: F405
     title="1V8: VCCPAUX, VCCPLL, VCCAUX, VCCO_MIO, bank 0 (0.40 A)")
buck(sh, {"U": "U321", "L": "L321", "R1": "R321", "R2": "R322", "CIN": "C321", "COUT": ["C322"], "CFF": "C323"},
     X[0], g(110), "3V3", "453k", en="pg_1v8", pg="DDR3_VTT_EN", couts=1,  # noqa: F405
     title="3V3: HR banks 13/33/34/35, PHY, eMMC, LCD (0.49 A)")
buck(sh, {"U": "U331", "L": "L331", "R1": "R331", "R2": "R332", "CIN": "C331", "COUT": ["C332"], "CFF": "C333"},
     X[1], g(110), "1V35", "124k", en="pg_1v8", pg="DDR3_VTT_EN", couts=1,  # noqa: F405
     title="1V35: VCCO_DDR, DDR3L, TPS51200 VLDOIN (0.97 A)")

# 3V3_analog for the ADC block (sheet 12), the Ti135 card's NCP163 circuit
u = sh.place("NCP163ASN330T1G", "U341", X[2], g(52), value="NCP163ASN330T1G")  # noqa: F405
set_field(sh, "U341", "Footprint", "Package_TO_SOT_SMD:SOT-23-5")  # noqa: F405
vin, gnd, en, nc, vout = u.pin(1), u.pin(2), u.pin(3), u.pin(4), u.pin(5)
n = left(vin, 6)  # noqa: F405
sh.wire(vin, n); sh.wire(n, up(n, 2)); power_at(sh, "5V0", up(n, 2), "up")  # noqa: F405
sh.wire(en, (n[0], en[1]), n); sh.junction(*n)
sh.no_connect(*nc)
sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")  # noqa: F405
_, ct, cb = vert2(sh, "C", "C341", n[0] - g(4), n[1] + g(6), "1u", text="left")  # noqa: F405
sh.wire(n, (ct[0], n[1]), ct)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
o = right(vout, 6)  # noqa: F405
sh.wire(vout, o)
_, ct, cb = vert2(sh, "C", "C342", o[0], o[1] + g(6), "1u", text="right")  # noqa: F405
sh.wire(o, ct); sh.junction(*o)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
sh.wire(o, up(o, 3)); power_at(sh, "3V3_analog", up(o, 3), "up")  # noqa: F405
for c in ("C341", "C342"):
    set_field(sh, c, "Footprint", "Capacitor_SMD:C_0402_1005Metric")  # noqa: F405
sh.text("3V3_analog: LDO from 5V0 for the ADC block (sheet 12),\nalways on (not in the SoC sequence).",
        X[2] - g(16), g(40))  # noqa: F405
sh.save()
print("03_pwr_rails: U301/U311/U321/U331 TLV62585, U341 NCP163")
