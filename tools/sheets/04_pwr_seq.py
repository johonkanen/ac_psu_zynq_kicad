#!/usr/bin/env python3
"""Sheet 4 (pwr_seq): the enable chain pull-ups and the PS_POR_B supervisor (ZYNQ_PCB_NOTES.md §3).

The Ti135 card's sheet 4 (power-good chain + TPS3808 into CRESET_N), re-ordered for the Zynq:
- pg_1v0 = PG(1V0), R401 100 k to 5V0 -> EN of 1V8. 1V0 (VCCPINT/VCCINT/VCCBRAM) first.
- pg_1v8 = PG(1V8), R402 100 k to 5V0 -> EN of 3V3 and 1V35. So 1V8 (VCCAUX, VCCPAUX, VCCO_MIO, VCCO_0) is at 95 %
  before 3V3 starts: VCCO - VCCAUX <= 2.625 V holds without using T_VCCO2VCCAUX.
- DDR3_VTT_EN = PG(3V3) & PG(1V35) (wired AND), pulled up by R25 (20 k to 3V3, sheet 1, REUSE_LOG E3): TPS51200 EN
  (VIH 1.7 V, abs max 6.5 V). The same node is U401 ~MR, the last power-good.
  ~MR has a 70-90 k internal pull-up to VDD (1V8): the node settles at about 3.0 V, inside V_MR <= 6.5 V
  (SBVS050 Rec. op.), and the 14 uA it feeds into 1V8 is harmless.
- TLV62585 PG is low while EN is low or in UVLO (SLVSDE5F Table 1), so a rail that drops pulls every later EN low.
U401 TPS3808G01: VDD = 1V8 (the PS_POR_B pull-up rail, R608 on sheet 6), so RESET is valid before PS_POR_B can rise.
- SENSE watches 1V0 (VCCPINT) through R403/R404: 0.405 V x (1 + 121/100) = 0.895 V. Power-off: PS_POR_B asserts
  before VCCPINT falls to 0.80 V and stays low while VDD (1V8, light load, ~400 uF) is up (DS187 eFUSE rule).
- CT = VDD: t_D = 300 ms (180-420 ms) after both ~MR and SENSE are good. DS187 Table 23 (33.33 MHz): PS_POR_B must not
  be released inside T_SLW of the last PL supply (VCCINT/VCCBRAM/VCCAUX/VCCO_0, i.e. 1V8 here) reaching 250 mV.
  Our release is 180-425 ms after it, outside every row (default 12..40, eFUSE CRC -16..12, PLL bypass -27..13,
  eFUSE + bypass -746..-705 ms). CT open (12-28 ms) would fall inside the eFUSE and bypass windows.
- RESET is open drain onto ps_por_n (R608 10 k to 1V8 on sheet 6). T_PSPOR (100 us) is met by far.
"""
from _common import *  # noqa: F401,F403

R0402 = "Resistor_SMD:R_0402_1005Metric"
sh = sheet("04_pwr_seq.kicad_sch")  # noqa: F405
sh.text("Power-up (ZYNQ_PCB_NOTES.md §3): 5V0 -> 1V0 -> pg_1v0 -> 1V8 -> pg_1v8 -> 3V3 + 1V35 -> DDR3_VTT_EN (TPS51200 VTT)\n"
        "-> U401 TPS3808G01 (CT = VDD: 300 ms) -> ps_por_n (PS_POR_B). Each TLV62585 ramps in 0.9 ms (DS187: 0.2-50 ms).\n"
        "300 ms keeps PS_POR_B release outside the DS187 Table 23 secure lockdown window in every boot configuration.",
        g(14), g(14))  # noqa: F405


def pullup(ref, net, x, y, rail, text):
    n = (x, y)
    hlabel_left(sh, net, n, 4)  # noqa: F405
    _, rt, rb = vert2(sh, "R", ref, n[0] + g(4), n[1] - g(5), "100k", text="right")  # noqa: F405
    sh.wire(n, (rb[0], n[1]), rb)
    sh.wire(rt, up(rt, 2)); power_at(sh, rail, up(rt, 2), "up")  # noqa: F405
    set_field(sh, ref, "Footprint", R0402)  # noqa: F405
    sh.text(text, x - g(10), y + g(4))  # noqa: F405


pullup("R401", "pg_1v0", g(40), g(50), "5V0", "pg_1v0 = PG(1V0) -> EN of 1V8")  # noqa: F405
pullup("R402", "pg_1v8", g(40), g(80), "5V0", "pg_1v8 = PG(1V8) -> EN of 3V3 and 1V35")  # noqa: F405

# supervisor
X, Y = g(130), g(66)  # noqa: F405
u = sh.place("TPS3808DBV", "U401", X, Y, value="TPS3808G01DBVR", fields={"MPN": "TPS3808G01DBVR"})
set_field(sh, "U401", "Footprint", "Package_TO_SOT_SMD:SOT-23-6")  # noqa: F405
rst, gnd, mr, ct, sense, vdd = (u.pin(k) for k in (1, 2, 3, 4, 5, 6))
hlabel_left(sh, "DDR3_VTT_EN", mr, 12)  # noqa: F405
sh.text("DDR3_VTT_EN = PG(3V3) & PG(1V35), wired AND,\npull-up R25 20k to 3V3 (sheet 1) = TPS51200 EN",
        mr[0] - g(34), mr[1] + g(9))  # noqa: F405
sh.wire(vdd, up(vdd, 3)); power_at(sh, "1V8", up(vdd, 3), "up")  # noqa: F405
# CT to VDD: 300 ms
sh.wire(ct, left(ct, 3)); power_at(sh, "1V8", left(ct, 3), "left")  # noqa: F405
sh.text("CT = VDD (1V8): t_D = 300 ms", mr[0] - g(34), mr[1] + g(15))  # noqa: F405
# SENSE: 1V0 divider, 0.895 V, on the local label por_sense
q = left(sense, 3)  # noqa: F405
sh.wire(sense, q); sh.wire(q, up(q, 2)); sh.label("por_sense", *up(q, 2), 90)  # noqa: F405
xs, ys = g(84), g(92)  # noqa: F405
_, st, sb = vert2(sh, "R", "R403", xs, ys - g(5), "121k", text="left")  # noqa: F405
sh.wire(st, up(st, 2)); power_at(sh, "1V0", up(st, 2), "up")  # noqa: F405
_, bt, bb = vert2(sh, "R", "R404", xs, ys + g(5), "100k", text="left")  # noqa: F405
sh.wire(sb, (xs, ys), bt); sh.junction(xs, ys)
sh.wire((xs, ys), right((xs, ys), 4)); sh.label("por_sense", *right((xs, ys), 4), 0)  # noqa: F405
sh.wire(bb, down(bb, 2)); power_at(sh, "GND", down(bb, 2), "down")  # noqa: F405
for r in ("R403", "R404"):
    set_field(sh, r, "Footprint", R0402)  # noqa: F405
sh.text("SENSE divider: 1V0 < 0.895 V -> reset\n(asserted before VCCPINT reaches 0.80 V)", xs + g(4), ys + g(7))  # noqa: F405
sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")  # noqa: F405
hlabel_right(sh, "ps_por_n", rst, 8, "output")  # noqa: F405
sh.text("open drain; 10k pull-up to 1V8\nis R608 on sheet 6", rst[0] + g(2), rst[1] + g(4))  # noqa: F405
_, ct2, cb2 = vert2(sh, "C", "C401", X + g(22), Y - g(14), "100n", text="right")  # noqa: F405
sh.wire(ct2, up(ct2, 2)); power_at(sh, "1V8", up(ct2, 2), "up")  # noqa: F405
sh.wire(cb2, down(cb2, 2)); power_at(sh, "GND", down(cb2, 2), "down")  # noqa: F405
set_field(sh, "C401", "Footprint", "Capacitor_SMD:C_0402_1005Metric")  # noqa: F405
sh.save()
print("04_pwr_seq: R401-R404, U401, C401")
