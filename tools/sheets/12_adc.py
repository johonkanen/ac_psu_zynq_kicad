#!/usr/bin/env python3
"""Sheet 12 (adc): 8:1 mux -> unity-gain buffer -> ADS7056 (14 bit, 2.5 MSPS).

Ported from the Ti135 card (efinix_soc_board/tools/sheets/13_adc.py, its parts and symbols), whose front end comes
from the Agilex 3 card (~/dev/ti60f225_control_card docs/design-notes.md, "ADC front end for 2.5 MSPS"):
- U1201 SN74LV4051APWR (C7793) on 3V3_analog (U341, sheet 3). TI SCLS428K: the 4051 pinout of the CD4051B symbol,
  pins 7 and 8 both GND (the symbol's VEE pin goes to GND), logic inputs VIH = 0.7 VCC = 2.31 V at 3.3 V and
  5.5 V tolerant, so adbsel0-2 come straight from bank 33 (3.3 V; the Ti135 card needed translators). INH to GND.
  X0 = GND as a zero reference.
- U1202 OPA365 buffer (50 MHz; the ADS7056 kickback RC needs UGB >= 28 MHz).
- Kickback RC at AINP: 33 R + 680 p C0G (ADS7056 data sheet 2.5 MSPS design).
- U1203 ADS7056: AVDD = reference, 4u7 0603 + 100 n at the pin, from 3V3_analog. DVDD = 3V3 (ZYNQ_PCB_NOTES.md §4.4:
  SPI straight to the 3.3 V bank 33; SBAS769: DVDD 1.65-3.6 V, independent of AVDD). The Ti135 card had DVDD at 1V8.
- CS / SCLK / SDO 33 R series (60 MHz SCLK). Capture SDO with a phase-shifted clock (design note).
Mux inputs: X1/X2/X3/X5 monitor card rails 1V0, 1V8, 3V3/2, 1V35 (the Ti135 VCORE, 1V8, 3V3/2, 1V1);
X4/X6/X7 = isoada2/3/1 from J3 (sheet 13).
Port names are sheet 11's: adc_cs_n, adc_sclk, adc_sdo, adbsel0-2.
"""
from _common import *  # noqa: F401,F403

sh = sheet("12_adc.kicad_sch")  # noqa: F405
sh.text("ADC chain: mux U1201 -> buffer U1202 -> ADS7056 U1203 (Ti135 sheet 13; front end as on the Agilex 3 card, 2.5 MSPS).\n"
        "Mux: X0 GND (zero ref), X1 1V0, X2 1V8, X3 3V3/2, X4 isoada2, X5 1V35, X6 isoada3, X7 isoada1.\n"
        "Full scale 0..3.3 V (AVDD = reference, 3V3_analog). DVDD on 3V3: SPI and selects straight to bank 33.",
        g(14), g(14))  # noqa: F405

# mux (SN74LV4051A, CD4051B symbol: same pinout, pin 7 = GND on the TI part)
m = sh.place("CD4051B", "U1201", g(80), g(80), value="SN74LV4051APWR", fields={"LCSC": "C7793"})
attach(sh, m, "13", "power", "GND", 3)  # X0 = zero reference  # noqa: F405
for pin, net in (("14", "mon_1v0"), ("15", "mon_1v8"), ("12", "mon_3v3"), ("1", "isoada2"),
                 ("5", "mon_1v35"), ("2", "isoada3"), ("4", "isoada1")):
    attach(sh, m, pin, "hlabel" if net.startswith("isoada") else "label", net, 4)  # noqa: F405
for pin, net in (("11", "adbsel0"), ("10", "adbsel1"), ("9", "adbsel2")):
    attach(sh, m, pin, "hlabel", net, 4, shape="input")  # noqa: F405
for pin in ("6", "7", "8"):
    attach(sh, m, pin, "power", "GND", 3)  # noqa: F405
attach(sh, m, "16", "power", "3V3_analog", 3)  # noqa: F405
attach(sh, m, "3", "label", "adc_mux_out", 4)  # noqa: F405
cap_row(sh, g(60), g(120), "3V3_analog", [("C1201", "1u", None)], "U1201 VCC")  # noqa: F405
sh.text("SN74LV4051A (SCLS428K): pins 7/8 GND; VIH 2.31 V at 3.3 V", g(56), g(56))  # noqa: F405

# rail monitors (series R limits the current into the mux)
sh.text("Rail monitors", g(14), g(140))  # noqa: F405
for k, (rail, net, val) in enumerate((("1V0", "mon_1v0", "100R"), ("1V8", "mon_1v8", "1k"),
                                      ("3V3", "mon_3v3", "1k"), ("1V35", "mon_1v35", "1k"))):
    pull_r(sh, f"R12{k + 1:02d}", g(18) + k * g(8), g(152), net, rail, val)  # noqa: F405
pull_r(sh, "R1205", g(18) + 4 * g(8), g(152), "mon_3v3", "GND", "1k")  # noqa: F405
sh.text("3V3 via 1k/1k divider", g(46), g(166))  # noqa: F405

# buffer
b = sh.place("OPA365xxDBV", "U1202", g(160), g(80), value="OPA365AIDBVR", fields={"LCSC": "C96626"})
attach(sh, b, "3", "label", "adc_mux_out", 4)  # noqa: F405
out = b.pin("1")
nin = b.pin("4")
node = right(out, 4)  # noqa: F405
sh.wire(out, node)
sh.wire(nin, (nin[0], nin[1] + g(4)), (node[0], nin[1] + g(4)), node)  # noqa: F405
sh.junction(*node)
attach(sh, b, "5", "power", "3V3_analog", 2)  # noqa: F405
attach(sh, b, "2", "power", "GND", 2)  # noqa: F405
_, a, r = horiz2(sh, "R", "R1206", node[0] + g(6), node[1], "33R", text="above")  # noqa: F405
sh.wire(node, a)
ainp = right(r, 4)  # noqa: F405
sh.wire(r, ainp)
_, ct, cb = vert2(sh, "C", "C1202", ainp[0], ainp[1] + g(5), "680p C0G", text="right")  # noqa: F405
sh.wire(ainp, ct); sh.junction(*ainp)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
sh.wire(ainp, right(ainp, 4)); sh.label("adc_ainp", *right(ainp, 4), 0)  # noqa: F405
cap_row(sh, g(150), g(120), "3V3_analog", [("C1203", "100n", None)], "U1202 V+")  # noqa: F405

# ADC
a7 = sh.place("ADS7056", "U1203", g(250), g(80), value="ADS7056IRUGR", fields={"LCSC": "C2669798"})
set_field(sh, "U1203", "Footprint", "zynq_card:ads7056")  # noqa: F405
attach(sh, a7, "7", "label", "adc_ainp", 4)  # noqa: F405
attach(sh, a7, "8", "power", "GND", 3)  # noqa: F405
attach(sh, a7, "5", "power", "GND", 3)  # noqa: F405
attach(sh, a7, "6", "power", "3V3_analog", 3)  # noqa: F405
attach(sh, a7, "4", "power", "3V3", 7)  # noqa: F405
for pin, net in (("1", "adc_cs_n_r"), ("3", "adc_sclk_r"), ("2", "adc_sdo_r")):
    attach(sh, a7, pin, "label", net, 4)  # noqa: F405
cap_row(sh, g(230), g(120), "3V3_analog", [("C1204", "4u7", "Capacitor_SMD:C_0603_1608Metric"), ("C1205", "100n", None)],  # noqa: F405
        "AVDD = reference: 4u7 0603 + 100n at the pin")
cap_row(sh, g(290), g(120), "3V3", [("C1206", "1u", None)], "DVDD 3V3")  # noqa: F405
sh.text("SPI series 33 R (60 MHz SCLK); DVDD 3V3 = bank 33", g(220), g(140))  # noqa: F405
for k, (soc, local, shape) in enumerate((("adc_cs_n", "adc_cs_n_r", "input"), ("adc_sclk", "adc_sclk_r", "input"),
                                         ("adc_sdo", "adc_sdo_r", "output"))):
    series_r(sh, f"R12{10 + k:02d}", g(240), g(148) + k * g(5), "33R", "hlabel", soc, "label", local, shape)  # noqa: F405

fill_footprints(sh, {"R": R0402, "C": C0402, "CD4051B": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",  # noqa: F405
                     "OPA365xxDBV": "Package_TO_SOT_SMD:SOT-23-5"})
sh.save()
print("12_adc: U1201-U1203, R1201-R1206, R1210-R1212, C1201-C1206")
