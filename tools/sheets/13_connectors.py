#!/usr/bin/env python3
"""Sheet 13 (connectors): J3 (baseboard J11) with 10 k pull-downs, J5 LCD/touch, J2 UART console behind a
1.8 V <-> 3.3 V translator, and the I2C0 pull-ups.

Ported from the Ti135 card (efinix_soc_board/tools/sheets/14_connectors.py). Its level-shift sheet is not needed:
bank 34 is 3.3 V, so J3 is wired straight to the PL (sheet 11).
- J3: 2x19 1.27 mm socket on the bottom, J3 pin n = baseboard J11 pin n (reference/baseboard_j11_pinout.csv,
  MECHANICAL.md). Every digital J3 net has the sheet-11 name (zynq_pinplan.csv); the script checks each pin number
  against the pin plan's note column. 10 k pull-downs on all 32 digital pins (8 x 4D02WGJ0103TCE, C25725): with
  PUDC_B high (sheet 11) the PL has no pull-ups during configuration, so the baseboard sees low until the bitstream
  drives the pins (STATUS.md "J3 safe state", ZYNQ_PCB_NOTES.md §5). ISOADA1-3 are analog inputs to the mux
  (sheet 12): no pull-down, it would load the source. ISOGND = GND, pin 38 NC.
- J5: LCD/touch header, the Ti135 sheet 14 pinout (Ti60 J4), lcd_*/t_* straight from bank 33 (3.3 V).
- J2: UART console, family pinout (1 = RX into the SoC, 2 = TX, 3 = GND), 1 k series as on the Ti135 card.
  PS UART1 on MIO48/49 is 1.8 V (bank 501), J2 is 3.3 V: TX and RX go opposite ways, so U1301 SN74AVC4T774RSVR
  (C779392, per-bit direction, the J1 shifter of sheet 6; STATUS.md decision). A = J2 side on 3V3, B = MIO side on
  1V8. DIR1 = H: J2 RX A1 -> B1 uart_rx. DIR2 = L: uart_tx B2 -> A2. Bits 3/4 unused: DIR = H, A3/A4 to GND (inputs
  held), B3/B4 open. OE low. Either supply off -> all outputs off (Ioff). 10 k pull-up on the J2 RX side (idle high
  with nothing plugged in) and 10 k to 1V8 on uart_tx (B2 defined while MIO48 is tri-stated).
- I2C0 (MIO50/51): 4.7 k pull-ups to 1V8 (ZYNQ_PCB_NOTES.md §4.3, §7). No device on the bus yet (the MAC-address
  EEPROM is optional, not fitted).
Connector refs J2/J3/J5 are the family names (MECHANICAL.md).
"""
from _common import *  # noqa: F401,F403

sh = sheet("13_connectors.kicad_sch")  # noqa: F405
bb = baseboard_j11()  # noqa: F405
pp = pinplan()  # noqa: F405


def j3_net(pin):
    r = bb[pin]
    sig, d = r["signal"].lower(), r["direction_from_control_card"]
    if d in ("out", "in"):
        assert sig in pp and pp[sig]["note"] == f"J3.{pin}" and pp[sig]["dir"] == d, (pin, sig, pp.get(sig))
        return sig, "input" if d == "out" else "output"
    if d == "analog":
        return sig, "passive"
    return None, d


sh.text("J3 = baseboard J11 (2x19 1.27 mm socket on B.Cu, pin n = baseboard pin n, see MECHANICAL.md).\n"
        "Nets = sheet-11 names (bank 34, 3.3 V, no translators). Every digital pin has a 10 k pull-down: with PUDC_B\n"
        "high the PL has no pull-ups while unconfigured, so the baseboard sees low (J3 safe state). isoada1-3: analog, to the mux.",
        g(14), g(14))  # noqa: F405

# ---- J3
JX, JY = g(70), g(40)  # noqa: F405
j3 = sh.place("Conn_02x19_Odd_Even", "J3", JX, JY, value="2x19 1.27mm socket (bottom)")
set_field(sh, "J3", "Footprint", "Connector_PinSocket_1.27mm:PinSocket_2x19_P1.27mm_Vertical")  # noqa: F405
pulled = []
for pin in range(1, 39):
    p = j3.pin(pin)
    net, kind = j3_net(pin)
    side = "left" if pin % 2 else "right"
    if kind == "gnd":
        q = left(p, 4) if side == "left" else right(p, 4)  # noqa: F405
        sh.wire(p, q)
        power_at(sh, "GND", q, side)  # noqa: F405
    elif kind == "nc":
        sh.no_connect(*p)
    else:
        (hlabel_left if side == "left" else hlabel_right)(sh, net, p, 6, kind)  # noqa: F405
        if kind != "passive":
            pulled.append(net)
assert len(pulled) == sum(1 for r in pp.values() if r["group"] == "j3") == 32, len(pulled)

# ---- pull-down packs: 8 x 4 x 10 k (4D02WGJ0103TCE), signal on pins 1-4, GND on 5-8
PX, PY = g(140), g(34)  # noqa: F405
for k in range(0, len(pulled), 4):
    nets = pulled[k:k + 4]
    i = k // 4
    x, y = PX + (i % 4) * g(24), PY + (i // 4) * g(44)  # noqa: F405
    rn = sh.place("R_Pack04", f"RN13{i + 1:02d}", x, y, value="4x10k",
                  fields={"MPN": "4D02WGJ0103TCE", "LCSC": "C25725"})
    for j, net in enumerate(nets):
        top = rn.pin(1 + j)  # pins 1..4 at the bottom of the symbol
        q = down(top, 2 + 2 * j)  # noqa: F405
        sh.wire(top, q)
        sh.label(net, *q, 270)
    gnds = [rn.pin(n) for n in (5, 6, 7, 8)]
    ytop = up(gnds[0], 2)  # noqa: F405
    for gp in gnds:
        sh.wire(gp, (gp[0], ytop[1]))
    sh.wire((gnds[-1][0], ytop[1]), (gnds[0][0], ytop[1]))
    for gp in gnds[1:-1]:
        sh.junction(gp[0], ytop[1])
    sh.junction(gnds[0][0], ytop[1])
    q = up((gnds[0][0], ytop[1]), 2)  # noqa: F405
    sh.wire((gnds[0][0], ytop[1]), q)
    power_at(sh, "GND", q, "up")  # noqa: F405
sh.text("J3 pull-downs: 8 x 4D02WGJ0103TCE (4 x 10 k, C25725)", PX - g(4), PY - g(16))  # noqa: F405

# ---- J5 LCD + touch (2.8" SPI TFT module), the Ti135/Ti60 J4 pinout, 3.3 V straight from bank 33
lcd = ["t_irq", "t_do", "t_din", "t_cs_n", "t_clk", "lcd_mosi", "lcd_led", "lcd_sck", "lcd_miso",
       "lcd_dc", "lcd_reset_n", "lcd_cs_n"]
assert sorted(lcd) == sorted(s for s, r in pp.items() if r["group"] == "lcd")
shape = {"t_irq": "output", "t_do": "output", "lcd_miso": "output"}
j5 = sh.place("Conn_01x14", "J5", g(60), g(132), value="LCD 1x14 2.54mm")
set_field(sh, "J5", "Footprint", "Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical")  # noqa: F405
for i, net in enumerate(lcd, 1):
    hlabel_left(sh, net, j5.pin(i), 6, shape.get(net, "input"))  # noqa: F405
p = j5.pin(13)
sh.wire(p, left(p, 4)); power_at(sh, "GND", left(p, 4), "left")  # noqa: F405
p = j5.pin(14)
sh.wire(p, left(p, 4)); power_at(sh, "3V3", left(p, 4), "left")  # noqa: F405
sh.text("J5: LCD/touch header, Ti135 J5 (Ti60 J4) pinout\n(wired to the LCD with jumper wires).", g(30), g(112))  # noqa: F405

# ---- J2 UART console: MIO48/49 (1.8 V) -> U1301 -> J2 (3.3 V)
TX, TY = g(170), g(160)  # noqa: F405
sh.text("J2: UART console (PS UART1, MIO48 TX / MIO49 RX, 1.8 V), family pinout 1 RX, 2 TX, 3 GND at 3.3 V.\n"
        "U1301 SN74AVC4T774RSVR (C779392), per-bit direction: A = J2 side (3V3), B = MIO side (1V8).\n"
        "DIR1 = H: J2 RX A1 -> B1; DIR2 = L: TX B2 -> A2; bits 3/4 unused (DIR H, A3/A4 to GND). OE low.",
        TX - g(44), TY - g(24))  # noqa: F405
u = sh.place("SN74AVC4T774", "U1301", TX, TY, fields={"MPN": "SN74AVC4T774RSVR", "LCSC": "C779392"})
set_field(sh, "U1301", "Footprint", "Package_DFN_QFN:UQFN-16_1.8x2.6mm_P0.4mm")  # noqa: F405
for pin, kind, net in ((14, "power", "3V3"), (15, "power", "3V3"), (16, "power", "GND"), (5, "power", "3V3"),
                       (6, "power", "3V3"), (7, "power", "GND"), (8, "power", "GND"), (13, "power", "1V8"),
                       (1, "label", "uart_rx_3v3"), (2, "label", "uart_tx_3v3"),
                       (3, "power", "GND"), (4, "power", "GND"), (10, "nc", None), (9, "nc", None)):
    attach(sh, u, pin, kind, net, n=4)  # noqa: F405
hlabel_right(sh, "uart_rx", u.pin(12), 6, "output")  # noqa: F405
hlabel_right(sh, "uart_tx", u.pin(11), 6, "input")  # noqa: F405
cap_row(sh, TX - g(14), TY + g(26), "3V3", [("C1301", "100n", None)], "VCCA")  # noqa: F405
cap_row(sh, TX + g(20), TY + g(26), "1V8", [("C1302", "100n", None)], "VCCB")  # noqa: F405

j2 = sh.place("Conn_01x03", "J2", g(130), g(160), value="UART 3V3")
set_field(sh, "J2", "Footprint", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")  # noqa: F405
for pin, ref, net, txt in ((1, "R1301", "uart_rx_3v3", "above"), (2, "R1302", "uart_tx_3v3", "below")):
    _, a, b = horiz2(sh, "R", ref, g(116), j2.pin(pin)[1], "1k", text=txt)  # noqa: F405
    sh.wire(b, j2.pin(pin))
    sh.wire(a, left(a, 2)); sh.label(net, *left(a, 2), 180)  # noqa: F405
p = j2.pin(3)
sh.wire(p, left(p, 2), down(left(p, 2), 2)); power_at(sh, "GND", down(left(p, 2), 2), "down")  # noqa: F405
sh.text("J2: 1 RX (into the SoC), 2 TX, 3 GND", g(100), g(150))  # noqa: F405
pull_r(sh, "R1303", g(130), g(186), "uart_rx_3v3", "3V3", "10k")  # noqa: F405
pull_r(sh, "R1304", g(212), g(186), "uart_tx", "1V8", "10k")  # noqa: F405
sh.text("R1303: RX idle high with J2 open; R1304: B2 defined while MIO48 is off", g(124), g(206))  # noqa: F405

# ---- I2C0 (MIO50/51): pull-ups to 1V8
IX, IY = g(270), g(160)  # noqa: F405
sh.text("I2C0 (MIO50 SCL, MIO51 SDA, 1.8 V): 4.7 k pull-ups to 1V8\n(ZYNQ_PCB_NOTES.md §4.3). No device fitted yet.",
        IX - g(6), IY - g(24))  # noqa: F405
for k, (net, ref) in enumerate((("i2c_scl", "R1305"), ("i2c_sda", "R1306"))):
    x = IX + k * g(12)  # noqa: F405
    p = (x - g(6), IY + g(14) + k * g(4))  # noqa: F405
    hlabel(sh, net, *p, 180, "bidirectional")  # noqa: F405
    sh.wire(p, right(p, 4)); sh.label(net, *right(p, 4), 0)  # noqa: F405
    pull_r(sh, ref, x, IY, net, "1V8", "4.7k")  # noqa: F405

fill_footprints(sh, {"R": R0402, "C": C0402, "R_Pack04": "Resistor_SMD:R_Array_Convex_4x0402"})  # noqa: F405
sh.save()
print(f"13_connectors: J2, J3, J5, U1301, RN1301-RN1308 ({len(pulled)} pull-downs), R1301-R1306, C1301-C1302")
