#!/usr/bin/env python3
"""Sheet 11 (soc_pl): U20 units 2-5, the PL HR banks 13, 33, 34 and 35, all at 3.3 V (LVCMOS33).

One hierarchical label per used ball, named after the signal in vivado/pinplan/zynq_pinplan.csv (Vivado pin plan,
DRC 0; ZYNQ_PCB_NOTES.md §4.4). Pin swaps inside a bank are made there, then this script is re-run; it checks
each ball's pin function against the symbol. Unused balls: no-connect flag (Vivado's default unused-pin pull-down).
The Ti135 card's sheet 11 pattern (efinix_soc_board/tools/sheets/11_fpga_io.py).
- Bank 34: the 32 J3 signals (pull-downs with J3 on sheet 13). PUDC_B (K16, IO_L3P_T0_DQS_PUDC_B_34) is tied
  straight to VCCO_34 = 3V3 (UG865 Table 1-5: directly or through <= 1 k, never floating): internal pull-ups off
  during configuration, so the J3 pull-downs hold every baseboard input low until the PL drives it (STATUS.md, "J3
  safe state").
- Bank 33: the ADC (sheet 12), the LCD/touch J5 (sheet 13) and the two user LEDs (here: active low, 1 k to 3V3).
- Banks 13 and 35: spare, VCCO on 3V3.
- VCCO: 13/33 on 3V3 as on juliancoy (block copper, caps in the block). 34/35 are GND on juliancoy and 3V3 here
  (REUSE_LOG E7, their caps on sheet 5). juliancoy also tied every I/O ball of banks 34/35 to GND (UG933 "Unconnected
  VCCO Pins": an unused bank's VCCO and I/O on one potential); here they are our nets or open (REUSE_LOG E9).
"""
from _common import *  # noqa: F401,F403
from p2k.sch_builder import lib  # noqa: E402
from p2k.sexpr import find, find_all  # noqa: E402

sh = sheet("11_soc_pl.kicad_sch")  # noqa: F405
pp = pinplan()  # noqa: F405
by_ball = {r["ball"]: (s, r) for s, r in pp.items()}
SHAPE = {"out": "output", "in": "input", "inout": "bidirectional"}
LOCAL = {"led0_n", "led1_n"}  # used on this sheet only

sh.text("U20 PL banks 13, 33, 34, 35: HR I/O, all at 3.3 V (LVCMOS33). Signal <-> ball from vivado/pinplan/pinplan.py\n"
        "(zynq_pinplan.csv, Vivado DRC 0). Change pins there, then re-run this script. Unused balls are left open.\n"
        "Bank 34 = J3 (pull-downs on sheet 13), bank 33 = ADC, LCD/touch, LEDs; banks 13 and 35 spare.",
        g(14), g(14))  # noqa: F405

names = {}
for sub in find_all(lib()["XC7Z020-CLG484"], "symbol"):
    for p in find_all(sub, "pin"):
        names[find(p, "number")[1]] = find(p, "name")[1]

# (unit, bank, x): bank 34 first (longest labels), the spare banks last
UNITS = [(4, 34, g(46)), (3, 33, g(124)), (5, 35, g(202)), (2, 13, g(280))]  # noqa: F405
Y = g(40)  # noqa: F405
used, spare = 0, 0
for unit, bank, x in UNITS:
    u = place_unit(sh, "XC7Z020-CLG484", "U20", x, Y, unit)  # noqa: F405
    vcco = False
    for ball, p in u.pins.items():
        name = names[ball]
        if name.startswith("VCCO_"):
            if not vcco:  # stacked pins: one connection point
                attach(sh, u, ball, "power", "3V3", n=4, side="left")  # noqa: F405
                vcco = True
        elif "PUDC_B" in name:
            attach(sh, u, ball, "power", "3V3", n=4, side="left")  # noqa: F405
        elif ball in by_ball:
            sig, r = by_ball[ball]
            assert r["pin_function"] == name and int(r["bank"]) == bank, (sig, ball, name, r)
            if sig in LOCAL:
                attach(sh, u, ball, "label", sig, n=12, side="left")  # noqa: F405
            else:
                hlabel_left(sh, sig, p, 4, SHAPE[r["dir"]])  # noqa: F405
            used += 1
        else:
            sh.no_connect(*p)
            spare += 1
    sh.text(f"Bank {bank}: VCCO_{bank} = 3V3", x + g(2), Y + g(104))  # noqa: F405
assert used == len(pp), (used, len(pp))

# PUDC_B
sh.text("PUDC_B (K16) tied to VCCO_34 (UG865: directly or <= 1 k):\n"
        "no internal pull-ups during configuration; J3 pull-downs\n"
        "on sheet 13 hold the baseboard inputs low (J3 safe state).", g(10), g(184))  # noqa: F405

# user LEDs on bank 33 (active low, the pin sinks the current)
for k, net in enumerate(("led0_n", "led1_n")):
    x, y = g(140) + k * g(14), g(192)  # noqa: F405
    _, rt, rb = vert2(sh, "R", f"R11{k + 1:02d}", x, y, "1k", text="right")  # noqa: F405
    sh.wire(rt, up(rt, 2)); power_at(sh, "3V3", up(rt, 2), "up")  # noqa: F405
    _, dt, db = vert2(sh, "LED", f"D11{k + 1:02d}", x, y + g(8), "red", top=2, text="right")  # noqa: F405
    sh.wire(rb, dt)
    sh.wire(db, down(db, 2)); sh.label(net, *down(db, 2), 270)  # noqa: F405
sh.text("User LEDs on bank 33 (active low)", g(134), g(180))  # noqa: F405

fill_footprints(sh, {"R": R0402, "LED": "LED_SMD:LED_0603_1608Metric",  # noqa: F405
                     "XC7Z020-CLG484": "DFTcustom:BGA-484_19.0x19.0mm_Layout22x22_P0.80mm_dia0.40mm"})  # sheets 1/5  # noqa: F405
sh.save()
print(f"11_soc_pl: U20 units 2-5, {used} signals ({len(pp) - len(LOCAL)} ports), {spare} spare balls open; "
      "R1101, R1102, D1101, D1102")
