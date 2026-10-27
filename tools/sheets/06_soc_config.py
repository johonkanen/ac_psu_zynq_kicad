#!/usr/bin/env python3
"""Sheet 6 (soc_config): U20 unit 1 (bank 0: configuration, JTAG, XADC), units 6/7 (PS MIO banks 500/501), the boot
straps, PS reset and VREF, and the JTAG header J1 behind a 3.3 V <-> 1.8 V shifter.

- Bank 0 at 1.8 V, as on juliancoy (STATUS.md decisions, 2026-10-27): CFGBVS to GND, RSVDVCC to VCCO_0, XADC unused
  and tied off as on the source (VCCADC to 1V8, VP/VN/VREFP/VREFN/GNDADC to GND), DXP/DXN and VCCBATT to GND
  (UG865 Table 1-5). PROGRAM_B/INIT_B pull-ups are juliancoy's R9/R10 (block parts, source refs). RSVDGND (G10) is
  left open per UG865 v1.9 (REUSE_LOG E8; juliancoy tied it to GND).
- JTAG: J1 is driven by an FTDI mini-module at 3.3 V (no VREF pin). U601 shifts it to bank 0, the circuit of the
  Agilex 3 card (~/dev/ti60f225_control_card, SN74AVC4T774RSVR): TCK/TDI/TMS A->B, TDO B->A, OE low; TCK 1 k down,
  TMS/TDI 10 k up on the 3.3 V side, 10 k up on TDO at 1.8 V. J1 keeps the family 1x5 pinout (Ti135 J1).
- MIO (vivado/pinplan/mio.csv, ZYNQ_PCB_NOTES.md §4): both banks at 1.8 V. Boot straps on MIO[8:2], 20 k each, pull-ups
  to VCCO_MIO0: QSPI boot, JTAG cascaded, PLLs on, VMODE 1.8 V / 1.8 V. The interfaces leave as sheet ports; their
  pulls (eth_int_n, MDIO, I2C) sit with the parts on their sheets. PS_POR_B is an open-drain input from the supervisor
  (sheet 4), pulled up here; PS_CLK comes from sheet 7.
- E7 (REUSE_LOG): the VCCO_MIO balls are 1V8 here, +3V3 on juliancoy.
"""
from _common import *  # noqa: F401,F403

sh = sheet("06_soc_config.kicad_sch")  # noqa: F405
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
n = {"R": 0, "C": 0}


def ref(prefix):
    n[prefix] += 1
    return f"{prefix}6{n[prefix]:02d}"


def pull(net, rail, value, x, y, r=None, top=1):
    r = r or ref("R")
    pull_r(sh, r, x, y, net, rail, value, top)  # noqa: F405
    set_field(sh, r, "Footprint", R0402)  # noqa: F405
    return r


def decap(rail, x, y, value="100n"):
    c = ref("C")
    cap_row(sh, x, y, rail, [(c, value, C0402)])  # noqa: F405
    return c


sh.text("PS MIO banks 500/501 (1.8 V) and bank 0 (configuration, 1.8 V as on juliancoy). Pin plan:\n"
        "vivado/pinplan/mio.csv; rules: ZYNQ_PCB_NOTES.md §4-5, §7. Interfaces leave as sheet ports;\n"
        "their pull-ups sit with the parts on their sheets. JTAG J1 is 3.3 V (FTDI mini-module), shifted by U601.",
        g(10), g(14))  # noqa: F405

# ---------------------------------------------------------------- unit 6: bank 500 (QSPI, straps, GPIO, PS_CLK/POR)
MIO0 = {"A1": ("qspi_cs_n", "output"), "A2": ("qspi_io0", "bidirectional"), "F6": ("qspi_io1", "bidirectional"),
        "E4": ("qspi_io2", "bidirectional"), "A3": ("qspi_io3", "bidirectional"), "A4": ("qspi_sclk", "output"),
        "D5": ("emmc_rst_n", "output"), "C4": ("eth_rst_n", "output"), "G7": ("eth_int_n", "input"),
        "F7": ("ps_clk", "input"), "B5": ("ps_por_n", "input")}
u6 = place_unit(sh, "XC7Z020-CLG484", "U20", g(72), g(30), 6)  # noqa: F405
for ball in u6.pins:
    if ball in MIO0:
        attach(sh, u6, ball, "hlabel", MIO0[ball][0], n=8, shape=MIO0[ball][1], side="left")  # noqa: F405
    elif ball == "E5":  # MIO8: QSPI feedback clock, only its strap (keep the stub < 10 mm)
        attach(sh, u6, ball, "label", "qspi_fbclk", n=8, side="left")  # noqa: F405
    elif ball in ("B3", "C6"):  # VCCO_MIO0 (stacked)
        if ball == "B3":
            attach(sh, u6, ball, "power", "1V8", n=4, side="left")  # noqa: F405
    else:  # MIO0, MIO11-15: spare (MIO14 was juliancoy's VTT enable, REUSE_LOG E3)
        attach(sh, u6, ball, "nc")  # noqa: F405
sh.text("MIO0, MIO11-15: spare", g(98), g(64))  # noqa: F405

# boot straps, MIO[8:2] (UG585 Boot Mode Pin Settings): one 20 k each, pull-ups to VCCO_MIO0
SX, SY = g(14), g(104)  # noqa: F405
sh.text("Boot straps (sampled at PS_POR_B release), 20 k each, pull-ups to VCCO_MIO0 (1V8):\n"
        "MIO2 = 0 JTAG cascaded, MIO5/4/3 = 1/0/0 QSPI boot, MIO6 = 0 PLLs on, MIO7 = 1 / MIO8 = 1: banks 500/501\n"
        "at 1.8 V (must match VCCO_MIO0/1). PS_POR_B: open drain from the supervisor (sheet 4), 10 k up.",
        SX - g(2), SY - g(16))  # noqa: F405
STRAPS = [("qspi_io0", "GND"), ("qspi_io1", "GND"), ("qspi_io2", "GND"), ("qspi_io3", "1V8"),
          ("qspi_sclk", "GND"), ("emmc_rst_n", "1V8"), ("qspi_fbclk", "1V8")]
for k, (net, rail) in enumerate(STRAPS):
    pull(net, rail, "20k", SX + k * g(9), SY)  # noqa: F405
pull("ps_por_n", "1V8", "10k", SX + len(STRAPS) * g(9), SY)  # noqa: F405

# ---------------------------------------------------------------- unit 7: bank 501 (RGMII, SD0, UART, I2C, MDIO)
MIO1 = {16: "rgmii_txc", 17: "rgmii_txd0", 18: "rgmii_txd1", 19: "rgmii_txd2", 20: "rgmii_txd3", 21: "rgmii_tx_ctl",
        22: "rgmii_rxc", 23: "rgmii_rxd0", 24: "rgmii_rxd1", 25: "rgmii_rxd2", 26: "rgmii_rxd3", 27: "rgmii_rx_ctl",
        40: "sd_clk", 41: "sd_cmd", 42: "sd_dat0", 43: "sd_dat1", 44: "sd_dat2", 45: "sd_dat3",
        48: "uart_tx", 49: "uart_rx", 50: "i2c_scl", 51: "i2c_sda", 52: "mdc", 53: "mdio"}
OUT = {16, 17, 18, 19, 20, 21, 40, 48, 50, 52}
IN = {22, 23, 24, 25, 26, 27, 49}
u7 = place_unit(sh, "XC7Z020-CLG484", "U20", g(178), g(24), 7)  # noqa: F405
from p2k.sch_builder import lib  # noqa: E402
from p2k.sexpr import find, find_all  # noqa: E402
names = {find(p, "number")[1]: find(p, "name")[1] for sub in find_all(lib()["XC7Z020-CLG484"], "symbol")
         if sub[1].endswith("_7_1") for p in find_all(sub, "pin")}
for ball, name in names.items():
    if name.startswith("PS_MIO") and name[6:].split("_")[0].isdigit():
        mio = int(name[6:].split("_")[0])
        if mio in MIO1:
            shape = "output" if mio in OUT else "input" if mio in IN else "bidirectional"
            attach(sh, u7, ball, "hlabel", MIO1[mio], n=8, shape=shape, side="left")  # noqa: F405
        else:  # 28-39 (USB0, unused), 46, 47
            attach(sh, u7, ball, "nc")  # noqa: F405
    elif name == "PS_MIO_VREF_501":
        attach(sh, u7, ball, "label", "ps_mio_vref", n=8, side="left")  # noqa: F405
    elif name == "PS_SRST_B_501":
        attach(sh, u7, ball, "label", "ps_srst_n", n=8, side="left")  # noqa: F405
    elif ball == "A10":  # VCCO_MIO1 (stacked)
        attach(sh, u7, ball, "power", "1V8", n=4, side="left")  # noqa: F405
sh.text("MIO28-39 (USB0), 46, 47: spare", g(148), g(150))  # noqa: F405

# PS_MIO_VREF = VCCO_MIO1 / 2 for the HSTL RGMII receivers (UG865, UG933); PS_SRST_B pulled up to VCCO_MIO1
VX, VY = g(110), g(140)  # noqa: F405
sh.text("PS_MIO_VREF = 0.9 V (HSTL 1.8 V RGMII receivers): 10 k / 10 k + 10 n.\n"
        "PS_SRST_B: 10 k to VCCO_MIO1; must stay high while the BootROM runs (no button).", VX - g(2), VY - g(16))  # noqa: F405
r_top = pull("ps_mio_vref", "1V8", "10k", VX, VY)  # noqa: F405
r_bot = pull("ps_mio_vref", "GND", "10k", VX + g(9), VY)  # noqa: F405
c_vref = ref("C")
_, ct, cb = vert2(sh, "C", c_vref, VX + g(18), VY, "10n", text="right")  # noqa: F405
set_field(sh, c_vref, "Footprint", C0402)  # noqa: F405
sh.wire(ct, up(ct, 2)); sh.label("ps_mio_vref", *up(ct, 2), 90)  # noqa: F405
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")  # noqa: F405
fx = VX + g(26)  # noqa: F405
sh.label("ps_mio_vref", fx, VY - g(4), 90); sh.wire((fx, VY - g(4)), (fx, VY)); sh.pwr_flag(fx, VY, 180)  # noqa: F405
pull("ps_srst_n", "1V8", "10k", VX + g(34), VY)  # noqa: F405

# ---------------------------------------------------------------- unit 1: bank 0
UNIT1 = {"T13": ("power", "GND"), "N12": ("power", "GND"), "N11": ("power", "GND"), "K12": ("power", "GND"),
         "G9": ("power", "GND"), "M12": ("power", "GND"), "L11": ("power", "GND"), "L12": ("power", "GND"),
         "M11": ("power", "GND"), "T7": ("power", "1V8"), "T8": ("power", "1V8"), "T10": ("power", "1V8"),
         "K11": ("power", "1V8"), "R12": ("power", "1V8"), "G10": ("nc", None),
         "T12": ("label", "cfg_done"), "T14": ("label", "cfg_init_n"), "T11": ("label", "cfg_program_n"),
         "G11": ("label", "jtag_tck_1v8"), "H13": ("label", "jtag_tdi_1v8"), "G14": ("label", "jtag_tdo_1v8"),
         "G12": ("label", "jtag_tms_1v8")}
u1 = place_unit(sh, "XC7Z020-CLG484", "U20", g(290), g(30), 1)  # noqa: F405
for ball, (kind, net) in UNIT1.items():
    attach(sh, u1, ball, kind, net, n=6, side="left")  # noqa: F405
sh.text("CFGBVS to GND: bank 0 at 1.8 V. XADC unused: VCCADC 1V8, analog inputs to GND.\n"
        "RSVDGND open (UG865 v1.9; REUSE_LOG E8). RSVDVCC to VCCO_0.", g(250), g(18))  # noqa: F405

CX, CY = g(232), g(104)  # noqa: F405
sh.text("PROGRAM_B / INIT_B: juliancoy's R9/R10 (block), 4.7 k to VCCO_0.\n"
        "DONE: 330 R to VCCO_0 [verify UG470].", CX - g(2), CY - g(16))  # noqa: F405
pull("cfg_program_n", "1V8", "4.7k", CX, CY, r="R9", top=2)  # source: pad 2 on +1V8
pull("cfg_init_n", "1V8", "4.7k", CX + g(9), CY, r="R10", top=2)
pull("cfg_done", "1V8", "330", CX + g(18), CY)  # noqa: F405

# ---------------------------------------------------------------- JTAG: J1 (3.3 V) -> U601 -> bank 0 (1.8 V)
JX, JY = g(258), g(150)  # noqa: F405
sh.text("JTAG: J1 at 3.3 V (FTDI mini-module, no VREF), U601 SN74AVC4T774RSVR (C779392) to bank 0 at 1.8 V,\n"
        "as on the Agilex 3 card. DIR1-3 = H: TCK/TDI/TMS A->B; DIR4 = L: TDO B->A; OE low.", JX - g(40), JY - g(16))  # noqa: F405
u = sh.place("SN74AVC4T774", "U601", JX, JY, fields={"MPN": "SN74AVC4T774RSVR", "LCSC": "C779392"})
set_field(sh, "U601", "Footprint", "Package_DFN_QFN:UQFN-16_1.8x2.6mm_P0.4mm")  # noqa: F405
for pin, kind, net in ((14, "power", "3V3"), (15, "power", "3V3"), (16, "power", "3V3"), (5, "power", "3V3"),
                       (6, "power", "GND"), (7, "power", "GND"), (8, "power", "GND"), (13, "power", "1V8"),
                       (1, "label", "jtag_tck"), (2, "label", "jtag_tdi"), (3, "label", "jtag_tms"),
                       (4, "label", "jtag_tdo"), (12, "label", "jtag_tck_1v8"), (11, "label", "jtag_tdi_1v8"),
                       (10, "label", "jtag_tms_1v8"), (9, "label", "jtag_tdo_1v8")):
    attach(sh, u, pin, kind, net, n=4)  # noqa: F405
decap("3V3", JX - g(14), JY + g(24))  # noqa: F405
decap("1V8", JX + g(20), JY + g(24))  # noqa: F405

PX, PY = g(178), g(184)  # noqa: F405
for k, (net, rail, value) in enumerate((("jtag_tck", "GND", "1k"), ("jtag_tms", "3V3", "10k"),
                                        ("jtag_tdi", "3V3", "10k"), ("jtag_tdo_1v8", "1V8", "10k"))):
    pull(net, rail, value, PX + k * g(9), PY)  # noqa: F405
sh.text("JTAG pulls: TCK 1 k down, TMS/TDI 10 k up (3.3 V side);\n10 k up on TDO at 1.8 V (B4 defined while TDO is off).",
        PX - g(2), PY - g(16))  # noqa: F405

j1 = sh.place("Conn_01x05", "J1", g(318), g(178), value="JTAG 3V3")  # noqa: F405
set_field(sh, "J1", "Footprint", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")  # noqa: F405
for pin, net in ((1, "jtag_tdi"), (2, "jtag_tck"), (3, "jtag_tms"), (4, "jtag_tdo")):
    p = j1.pin(pin)
    sh.wire(p, left(p, 6)); sh.label(net, *left(p, 6), 180)  # noqa: F405
p = j1.pin(5)
sh.wire(p, left(p, 2), down(left(p, 2), 2)); power_at(sh, "GND", down(left(p, 2), 2), "down")  # noqa: F405
sh.text("J1: 1 TDI, 2 TCK, 3 TMS, 4 TDO, 5 GND (family pinout)", g(300), g(168))  # noqa: F405

sh.save()
print(f"06_soc_config: R601..R6{n['R']:02d}, C601..C6{n['C']:02d}, U601, J1, R9, R10, U20 units 1/6/7")
