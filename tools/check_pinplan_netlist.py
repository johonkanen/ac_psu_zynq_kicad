#!/usr/bin/env python3
"""Phase-2 closing check: every PL pin-plan signal and every MIO signal sits on its U20 ball in the netlist, and the
net reaches the part at the far end.

    tools/check_pinplan_netlist.py      (after tools/build_schematic.sh, which exports work/zynq_card_net.xml)

- PL: vivado/pinplan/zynq_pinplan.csv (signal -> ball). The net on that ball must carry the signal's name, and the far
  end is J3.<n> from the note column (j3), J5.<n> (lcd, the sheet-13 order), the ADC parts (adc) or the LED (led).
- MIO: MIO number -> ball from the XC7Z020-CLG484 symbol pin names (PS_MIO<n>_50x), checked against
  vivado/pinplan/ps7_mio.csv (Vivado's PS7 settings); the expected net and far-end pad per MIO are below.
  Every other MIO ball must be unconnected.
"""
import csv
import os
import sys
import xml.etree.ElementTree as ET

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.sexpr import find, find_all, load  # noqa: E402

NET = os.path.join(ROOT, "work", "zynq_card_net.xml")
LIB = os.path.join(ROOT, "lib", "zynq_card.kicad_sym")
PP = os.path.join(ROOT, "vivado", "pinplan", "zynq_pinplan.csv")
PS7 = os.path.join(ROOT, "vivado", "pinplan", "ps7_mio.csv")

LCD = ["t_irq", "t_do", "t_din", "t_cs_n", "t_clk", "lcd_mosi", "lcd_led", "lcd_sck", "lcd_miso",
       "lcd_dc", "lcd_reset_n", "lcd_cs_n"]  # J5 pins 1-12 (sheet 13)
PL_FAR = {"adc_cs_n": ("R1210", "1"), "adc_sclk": ("R1211", "1"), "adc_sdo": ("R1212", "1"),
          "adbsel0": ("U1201", "11"), "adbsel1": ("U1201", "10"), "adbsel2": ("U1201", "9"),
          "led0_n": ("D1101", None), "led1_n": ("D1102", None),
          **{s: ("J5", str(i)) for i, s in enumerate(LCD, 1)}}
LOCAL = {"led0_n": "/11 soc_pl/led0_n", "led1_n": "/11 soc_pl/led1_n"}

# MIO: (net, far-end ref, pin or None, ps7_mio.csv peripheral)
MIO = {1: ("qspi_cs_n", "U801", "C2", "Quad SPI Flash"), 2: ("qspi_io0", "U801", "D3", "Quad SPI Flash"),
       3: ("qspi_io1", "U801", "D2", "Quad SPI Flash"), 4: ("qspi_io2", "U801", "C4", "Quad SPI Flash"),
       5: ("qspi_io3", "U801", "D4", "Quad SPI Flash"), 6: ("qspi_sclk", "U801", "B2", "Quad SPI Flash"),
       7: ("emmc_rst_n", "U1001", "K5", "GPIO"), 8: ("/06 soc_config/qspi_fbclk", "R607", None, "Quad SPI Flash"),
       9: ("eth_rst_n", "U902", "2", "GPIO"), 10: ("eth_int_n", "U901", "31", "GPIO"),
       16: ("rgmii_txc", "R901", None, "Enet 0"), 17: ("rgmii_txd0", "R903", None, "Enet 0"),
       18: ("rgmii_txd1", "R904", None, "Enet 0"), 19: ("rgmii_txd2", "R905", None, "Enet 0"),
       20: ("rgmii_txd3", "R906", None, "Enet 0"), 21: ("rgmii_tx_ctl", "R902", None, "Enet 0"),
       22: ("rgmii_rxc", "R907", None, "Enet 0"), 23: ("rgmii_rxd0", "R909", None, "Enet 0"),
       24: ("rgmii_rxd1", "R910", None, "Enet 0"), 25: ("rgmii_rxd2", "R911", None, "Enet 0"),
       26: ("rgmii_rxd3", "R912", None, "Enet 0"), 27: ("rgmii_rx_ctl", "R908", None, "Enet 0"),
       40: ("sd_clk", "R1001", None, "SD 0"), 41: ("sd_cmd", "U1001", "M5", "SD 0"),
       42: ("sd_dat0", "U1001", "A3", "SD 0"), 43: ("sd_dat1", "U1001", "A4", "SD 0"),
       44: ("sd_dat2", "U1001", "A5", "SD 0"), 45: ("sd_dat3", "U1001", "B2", "SD 0"),
       48: ("uart_tx", "U1301", "11", "UART 1"), 49: ("uart_rx", "U1301", "12", "UART 1"),
       50: ("i2c_scl", "R1305", None, "I2C 0"), 51: ("i2c_sda", "R1306", None, "I2C 0"),
       52: ("mdc", "U901", "13", "Enet 0"), 53: ("mdio", "U901", "14", "Enet 0")}


def main():
    x = ET.parse(NET).getroot()
    net_of, nodes = {}, {}
    for n in x.iter("net"):
        ns = {(d.get("ref"), d.get("pin")) for d in n.iter("node")}
        nodes[n.get("name")] = ns
        for k in ns:
            net_of[k] = n.get("name")
    fails = []

    def check(what, ball, want, ref, pin):
        got = net_of.get(("U20", ball))
        want = want if want.startswith("/") else "/" + want
        if got != want:
            fails.append(f"{what}: U20.{ball} on {got}, want {want}")
        elif not any(r == ref and (pin is None or p == pin) for r, p in nodes[got]):
            fails.append(f"{what}: {got} does not reach {ref}{'.' + pin if pin else ''}")

    with open(PP) as f:
        pl = list(csv.DictReader(f))
    for r in pl:
        s = r["signal"]
        if r["group"] == "j3":
            far = ("J3", r["note"].split(".")[1])
        else:
            far = PL_FAR[s]
        check(f"PL {s}", r["ball"], LOCAL.get(s, s), *far)

    sym = next(s for s in find_all(load(LIB), "symbol") if s[1] == "XC7Z020-CLG484")
    ball = {}
    for sub in find_all(sym, "symbol"):
        for p in find_all(sub, "pin"):
            name = find(p, "name")[1]
            if name.startswith("PS_MIO") and name[6:].split("_")[0].isdigit():
                ball[int(name[6:].split("_")[0])] = find(p, "number")[1]
    assert len(ball) == 54, len(ball)
    with open(PS7) as f:
        ps7 = {int(r[0]): r[1] for r in csv.reader(f) if r and r[0].isdigit()}
    for mio, b in sorted(ball.items()):
        if mio in MIO:
            net, ref, pin, periph = MIO[mio]
            if ps7.get(mio) != periph:
                fails.append(f"MIO{mio}: ps7_mio.csv has {ps7.get(mio)!r}, want {periph!r}")
            check(f"MIO{mio}", b, net, ref, pin)
        else:
            got = net_of.get(("U20", b))
            if got and not got.startswith("unconnected-"):
                fails.append(f"MIO{mio} (spare): U20.{b} on {got}")
    for f_ in fails:
        print("FAIL", f_)
    print(f"check_pinplan_netlist: {len(pl)} PL signals, {len(MIO)} MIO signals, "
          f"{54 - len(MIO)} spare MIO open; {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
