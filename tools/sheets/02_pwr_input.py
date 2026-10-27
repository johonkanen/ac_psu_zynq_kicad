#!/usr/bin/env python3
"""Sheet 2 (pwr_input): J6 = baseboard J12 (5V_ISOL / ISOGND) and the 5V0 input bulk capacitance.

The Ti135 card's sheet 1 (efinix_soc_board/tools/sheets/01_pwr_input.py). J6 pin n = baseboard J12 pin 42 + n:
pins 1/3/5 = GND (baseboard ISOGND), 2/4/6 = 5V0 (baseboard 5V_ISOL, from baseboard U8; MECHANICAL.md, POWER_BUDGET.md).
Card GND is the baseboard's ISOGND domain. The Ti135 card has no input protection beyond the bulk capacitors (the
rail is the isolated output of the baseboard's U8 regulator, on a mated header), and neither does this one.
The 3V3_analog LDO, on the Ti135 sheet 1, is on sheet 3 here.
"""
from _common import *  # noqa: F401,F403

sh = sheet("02_pwr_input.kicad_sch")  # noqa: F405
sh.text("J6 = baseboard J12 (2x3 1.27 mm socket on B.Cu, MECHANICAL.md): 5V0 = baseboard 5V_ISOL, GND = ISOGND.\n"
        "Supply budget: POWER_BUDGET.md (0.89 A typ / 1.44 A high; needs the baseboard U8 upgrade to 1.5-2 A).",
        g(14), g(14))  # noqa: F405

j6 = sh.place("Conn_02x03_Odd_Even", "J6", g(40), g(50), value="2x3 1.27mm (bottom)")  # noqa: F405
set_field(sh, "J6", "Footprint", "Connector_PinSocket_1.27mm:PinSocket_2x03_P1.27mm_Vertical")  # noqa: F405
for pin in (1, 3, 5):
    p = j6.pin(pin); sh.wire(p, left(p, 4)); power_at(sh, "GND", left(p, 4), "left")  # noqa: F405
rail = right(j6.pin(2), 6)  # noqa: F405
for pin in (2, 4, 6):
    p = j6.pin(pin); sh.wire(p, (rail[0], p[1]))
sh.wire((rail[0], j6.pin(2)[1]), (rail[0], j6.pin(6)[1]))
sh.junction(rail[0], j6.pin(4)[1]); sh.junction(*rail)
top = up(rail, 6)  # noqa: F405
sh.wire(rail, top)
power_at(sh, "5V0", top, "up")  # noqa: F405
sh.wire(top, right(top, 2)); sh.pwr_flag(*right(top, 2), 270)  # noqa: F405
gf = (g(24), g(60)); power_at(sh, "GND", gf, "down"); sh.wire(gf, up(gf, 2)); sh.pwr_flag(*up(gf, 2), 0)  # noqa: F405
sh.text("GND: the card's only ground\n(baseboard ISOGND)", g(14), g(68))  # noqa: F405

# bulk input capacitance on 5V0 (each TLV62585 also has its own 10 u, sheet 3)
for k, (ref, val, fp) in enumerate((("C201", "47u", C1206), ("C202", "22u", C0805),  # noqa: F405
                                    ("C203", "100n", "Capacitor_SMD:C_0402_1005Metric"))):
    x = g(70) + k * g(8)  # noqa: F405
    _, ct, cb = vert2(sh, "C", ref, x, g(52), val, text="right")  # noqa: F405
    sh.wire(ct, up(ct, 2)); power_at(sh, "5V0", up(ct, 2), "up")  # noqa: F405
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
    set_field(sh, ref, "Footprint", fp)  # noqa: F405
sh.text("Input bulk at J6 (the regulators have their own 10u).", g(66), g(40))  # noqa: F405
sh.save()
print("02_pwr_input: J6, C201-C203")
