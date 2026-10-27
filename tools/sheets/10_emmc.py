#!/usr/bin/env python3
"""Sheet 10 (emmc): KIOXIA THGAMVG7T13BAIL (U1001, C7599693), 16 GB e-MMC 5.1, on SD0 (MIO40-45, bank 501, 1.8 V),
4-bit.

Ported from the Ti135 card (efinix_soc_board/tools/sheets/10_emmc.py), cut down to the Zynq SDIO
(ZYNQ_PCB_NOTES.md §4.3): 4-bit, SD 2.0 high speed <= 50 MHz, so DAT4-7 and DS are unused but not left floating.
KIOXIA data sheet values (as checked on the Agilex 5 card, SHARED_PARTS.md):
- VCCQ 1.70-1.95 V only, from the same supply as the host I/O (data sheet requirement): 1V8 = VCCO_MIO1.
  VCC 2.7-3.6 V: 3V3. Decoupling per the data sheet: VCC 4u7 + 220n, VCCQ 4u7 + 100n, VDDi 2u2 (1-4.7 u).
- Pull-ups to VCCQ: CMD 4.7-100 k, DAT0-7 10-100 k; DS pull-down 10-100 k. 47 k each, the Ti135 values.
- RST_n: emmc_rst_n is MIO7, which also carries the VMODE[0] strap: its 20 k pull-up to 1V8 on sheet 6 is the
  RST_n pull-up (the RST_n function is disabled until EXT_CSD[162] is set, so it is harmless either way).
- CLK: R1001 0 R in series at the MIO pin (UG933 SDIO: 0 R placeholder, 40-60 R if the edge needs damping).
- No card detect / write protect: `non-removable` in the device tree.
"""
from _common import *  # noqa: F401,F403

sh = sheet("10_emmc.kicad_sch")  # noqa: F405
sh.text("e-MMC on SD0 (MIO40-45, bank 501, 1.8 V), 4-bit. Pull-ups to 1V8 (= VCCQ, the same supply as VCCO_MIO1, as the\n"
        "data sheet requires). RST_n pull-up = the MIO7 strap on sheet 6. R1001 (CLK, 0 R) sits at the MIO pin.",
        g(14), g(14))  # noqa: F405
UX, UY = g(150), g(80)  # noqa: F405
u = sh.place("THGAMVG7T13BAIL", "U1001", UX, UY, value="THGAMVG7T13BAIL", fields={"LCSC": "C7599693"})
set_field(sh, "U1001", "Footprint", "Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm")  # noqa: F405
sig = {"M5": "sd_cmd", "H5": "emmc_ds", "K5": "emmc_rst_n",
       "A3": "sd_dat0", "A4": "sd_dat1", "A5": "sd_dat2", "B2": "sd_dat3",
       "B3": "emmc_dat4", "B4": "emmc_dat5", "B5": "emmc_dat6", "B6": "emmc_dat7"}
for pin, net in sig.items():
    attach(sh, u, pin, "label", net, 4)  # noqa: F405
attach(sh, u, "M6", "label", "emmc_clk", 4)  # noqa: F405
for pin in ("E6", "F5", "J10", "K9"):
    attach(sh, u, pin, "power", "3V3", 3)  # noqa: F405
for pin in ("C6", "M4", "N4", "P3", "P5"):
    attach(sh, u, pin, "power", "1V8", 3)  # noqa: F405
for pin in ("A6", "E7", "G5", "H10", "J5", "K8", "C4", "N2", "N5", "P4", "P6"):
    attach(sh, u, pin, "power", "GND", 3)  # noqa: F405
attach(sh, u, "C2", "label", "emmc_vddi", 4)  # noqa: F405

# SoC side: hierarchical labels (sheet 6 port names), CLK through R1001 0 R
series_r(sh, "R1001", g(40), g(50), "0R", "hlabel", "sd_clk", "label", "emmc_clk", "input")  # noqa: F405
for k, (net, shape) in enumerate([("sd_cmd", "bidirectional"), ("emmc_rst_n", "input")] +
                                 [(f"sd_dat{i}", "bidirectional") for i in range(4)]):
    p = (g(40), g(58) + k * g(3))  # noqa: F405
    hlabel(sh, net, *p, 180, shape)  # noqa: F405
    sh.wire(p, right(p, 6)); sh.label(net, *right(p, 6), 0)  # noqa: F405
sh.text("R1001: at the MIO40 pin", g(30), g(45))  # noqa: F405

# pulls
sh.text("47 k pull-ups to 1V8 (CMD, DAT0-7; DAT4-7 unused in 4-bit mode); DS (HS400 strobe, unused) 47 k pull-down",
        g(30), g(108))  # noqa: F405
pulls = [("sd_cmd", "1V8")] + [(f"sd_dat{i}", "1V8") for i in range(4)] + \
    [(f"emmc_dat{i}", "1V8") for i in range(4, 8)] + [("emmc_ds", "GND")]
for k, (net, rail) in enumerate(pulls):
    pull_r(sh, f"R10{10 + k:02d}", g(30) + k * g(8), g(122), net, rail, "47k")  # noqa: F405

# decoupling (KIOXIA data sheet)
cap_row(sh, g(30), g(160), "3V3", [("C1001", "4u7", None), ("C1002", "220n", None)], "VCC 3V3: 4u7 + 220n")  # noqa: F405
cap_row(sh, g(90), g(160), "1V8", [("C1003", "4u7", None), ("C1004", "100n", None)], "VCCQ 1V8: 4u7 + 100n")  # noqa: F405
_, ct, cb = vert2(sh, "C", "C1005", g(150), g(160), "2u2", text="right")  # noqa: F405
sh.wire(ct, up(ct, 2)); sh.label("emmc_vddi", *up(ct, 2), 90)  # noqa: F405
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
sh.text("VDDi: 2u2 (1-4.7 u)", g(154), g(152))  # noqa: F405

fill_footprints(sh, {"R": R0402, "C": C0402})  # noqa: F405
sh.save()
print("10_emmc: U1001, R1001, R1010-R1019, C1001-C1005")
