#!/usr/bin/env python3
"""Sheet 8 (qspi): the boot flash U801 ISSI IS25WP128-RHLE (C1349419) on QSPI0, bank 500 at 1.8 V.

The Ti135 card's flash (efinix_soc_board/tools/sheets/06_fpga_config.py, U601), re-wired for Zynq QSPI boot
(ZYNQ_PCB_NOTES.md §4.2/§4.3, vivado/pinplan/mio.csv):
- MIO1 CS#, MIO2-5 IO0-3, MIO6 SCLK, single x4, SCLK <= 100 MHz with the feedback clock on MIO8 (strap only, sheet 6).
- Ball map (24-ball TFBGA 6x8 mm, 5x5 array, the H package code): A4 RESET#, B2 SCLK, B3 GND, B4 VCC, C2 CS#,
  D3 IO0, D2 IO1, C4 IO2, D4 IO3. Checked against the ISSI data sheet on the Agilex 5 card (SHARED_PARTS.md); the
  same ball map as the MX25U25645G footprint, copied from the Ti135 card into lib/zynq_card.pretty.
- VCC 1.65-1.95 V: 1V8, the VCCO_MIO0 rail. 100 n at B4.
- CS#: R801 10 k to 1V8, so the flash stays deselected while MIO1 is tri-stated (power-up, POR, JTAG boot).
- IO0-IO3 and SCLK carry the boot-mode straps on sheet 6 (20 k): IO2 (WP#) is strapped low and IO3 (HOLD#) high.
  WP# low only matters with the status register's SRWD bit set (default 0); HOLD# is high, so x1 reads by the
  BootROM work. In quad mode (QE = 1) both pins are I/O.
- RESET# (dedicated, A4) on ps_por_n: the supervisor (sheet 4, open drain, R608 10 k to 1V8 on sheet 6) resets
  the flash together with the PS, so a warm power cycle cannot leave it in a mode the BootROM does not expect.
  PS_POR_B release -> first BootROM QSPI access (PLL lock, BootROM start) is far longer than the flash's reset
  recovery time [verify tRST in the ISSI data sheet].
"""
from _common import *  # noqa: F401,F403

sh = sheet("08_qspi.kicad_sch")  # noqa: F405
sh.text("QSPI boot flash (ZYNQ_PCB_NOTES.md §4.3): U801 IS25WP128-RHLE, 1.8 V, on QSPI0 = MIO1-6 (bank 500).\n"
        "Boot straps on IO0-3/SCLK are on sheet 6 (20 k). CS# pull-up R801; RESET# on ps_por_n (supervisor, sheet 4).\n"
        "Layout (UG933 QSPI): IO0-3 and CS# matched to SCLK within +/-50 ps; MIO8 (feedback clock) stays a short stub.",
        g(14), g(14))  # noqa: F405

X, Y = g(90), g(60)  # noqa: F405
u = sh.place("IS25WP128-RHLE", "U801", X, Y, value="IS25WP128-RHLE", fields={"LCSC": "C1349419"})
set_field(sh, "U801", "Footprint", "zynq_card:MX25U25645G_CSP24_6x8mm_P1.0mm")  # noqa: F405
F = u.pin
hlabel_left(sh, "qspi_cs_n", F("C2"), 12, "input")  # noqa: F405
hlabel_left(sh, "qspi_sclk", F("B2"), 12, "input")  # noqa: F405
hlabel_left(sh, "ps_por_n", F("A4"), 12, "input")  # noqa: F405
for ball, net in (("D3", "qspi_io0"), ("D2", "qspi_io1"), ("C4", "qspi_io2"), ("D4", "qspi_io3")):
    hlabel_right(sh, net, F(ball), 12, "bidirectional")  # noqa: F405
attach(sh, u, "B4", "power", "1V8", 2)  # noqa: F405
attach(sh, u, "B3", "power", "GND", 2)  # noqa: F405

# CS# pull-up: a label on the hierarchical net
pull_r(sh, "R801", X - g(22), Y + g(22), "qspi_cs_n", "1V8", "10k")  # noqa: F405
sh.text("R801: CS# high while MIO1 is tri-stated", X - g(34), Y + g(40))  # noqa: F405
cap_row(sh, X + g(26), Y + g(24), "1V8", [("C801", "100n", None)], "U801 VCC (B4)")  # noqa: F405

fill_footprints(sh, {"R": R0402, "C": C0402})  # noqa: F405
sh.save()
print("08_qspi: U801, R801, C801")
