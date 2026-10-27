#!/usr/bin/env python3
"""Sheet 7 (clocks): the 33.333 MHz PS_CLK oscillator.

PS_CLK (ZYNQ_PCB_NOTES.md §4.1, DS187 Table 20): 30-60 MHz single-ended LVCMOS at the VCCO_MIO0 level (1.8 V here),
duty 40-60 %, rise/fall <= 6 ns. Y701 YXC OT322533.3333MJBA4SL (C2831392; 1.8-3.3 V CMOS, 3225, +-20 ppm,
-40..85 C), the 33.333 MHz member of the OT3225 family on the Agilex 3 card. Its circuit is the one there
(~/dev/ti60f225_control_card, `osc` group): EN tied to VDD, the supply through a BLM18PG121SN1D bead with 470 nF,
a 33 R source-series resistor at the oscillator. The PL has no clock input in the pin plan; the PHY's 25 MHz crystal
is on sheet 9.
"""
from _common import *  # noqa: F401,F403

sh = sheet("07_clocks.kicad_sch")  # noqa: F405
sh.text("PS_CLK: Y701 33.333 MHz, 1.8 V CMOS (bank 500 = VCCO_MIO0 = 1.8 V) -> R701 33 R at Y701 -> ps_clk (U20 F7).\n"
        "Circuit of the Agilex 3 card's oscillator: EN tied to VDD, supply through FB701 with C701 470 n.\n"
        "Layout: Y701 close to F7, one point-to-point trace, R701 at the oscillator pin.", g(14), g(14))  # noqa: F405

X, Y = g(70), g(50)  # noqa: F405
y = sh.place("ASE-xxxMHz", "Y701", X, Y, value="33.333MHz",
             fields={"MPN": "OT322533.3333MJBA4SL", "LCSC": "C2831392"})
set_field(sh, "Y701", "Footprint", "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm")  # noqa: F405
out = y.pin(3)

# supply: 1V8 -> FB701 -> osc_vdd (VDD and EN), C701 470 n
_, a, b = horiz2(sh, "FerriteBead_Small", "FB701", X - g(24), Y - g(12), "BLM18PG121SN1D", text="above",  # noqa: F405
                 fields={"MPN": "BLM18PG121SN1D", "LCSC": "C14709"})
set_field(sh, "FB701", "Footprint", "Inductor_SMD:L_0603_1608Metric")  # noqa: F405
sh.wire(a, left(a, 3)); power_at(sh, "1V8", left(a, 3), "left")  # noqa: F405
node = right(b, 8)  # noqa: F405
sh.wire(b, node)
sh.label("osc_vdd", *node, 0)
sh.wire(node, up(node, 3)); sh.pwr_flag(*up(node, 3), 0)  # noqa: F405  # the bead drives the oscillator's VDD
attach(sh, y, 4, "label", "osc_vdd", n=4)  # noqa: F405
attach(sh, y, 1, "label", "osc_vdd", n=4)  # noqa: F405  # EN high: always on
_, ct, cb = vert2(sh, "C", "C701", X - g(22), Y + g(4), "470n", text="left")  # noqa: F405
set_field(sh, "C701", "Footprint", "Capacitor_SMD:C_0402_1005Metric")  # noqa: F405
sh.wire(ct, up(ct, 2)); sh.label("osc_vdd", *up(ct, 2), 90)  # noqa: F405
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
attach(sh, y, 2, "power", "GND", n=3)  # noqa: F405

# output: 33 R at the source -> ps_clk port
_, ra, rb = horiz2(sh, "R", "R701", out[0] + g(10), out[1], "33", text="above")  # noqa: F405
set_field(sh, "R701", "Footprint", "Resistor_SMD:R_0402_1005Metric")  # noqa: F405
sh.wire(out, ra)
hlabel_right(sh, "ps_clk", rb, 6, "output")  # noqa: F405
sh.save()
print("07_clocks: Y701, FB701, C701, R701")
