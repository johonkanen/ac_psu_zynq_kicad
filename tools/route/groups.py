#!/usr/bin/env python3
"""Net groups for the routing chain -> tools/route_groups.json (kipy tools/route/groups.py [BOARD]).

Patterns are matched on the last part of the net name; the JSON holds full names, in the order the router should
take them (J3 nets by J3 pin, the LCD nets by J5 pin). Every signal net outside the copied block must fall in one
group; a net in none, or in two, stops the script."""
import fnmatch
import json
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
b = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb"))
POWER = {"GND", "1V0", "1V8", "1V35", "3V3", "5V0", "3V3_analog", "DDR3_VTT"}
GROUPS = {
    "rgmii_tx": ["rgmii_tx*", "phy_tx*"],
    "rgmii_rx": ["rgmii_rx*", "phy_rx*"],
    "eth_slow": ["mdc", "mdio", "eth_int_n", "eth_rst_n", "phy_rstb", "eth_led_*", "phy_led*", "eth_ct", "phy_rset",
                 "phy_xi", "phy_xo"],
    "phy_pwr": ["phy_avdd33", "phy_dvdd_rg", "phy_vdd10"],
    "emmc": ["sd_*", "emmc_*"],
    "qspi": ["qspi_*"],
    "cfg": ["ps_por_n", "ps_clk", "Net-(Y701-OUT)", "osc_vdd", "ps_mio_vref", "ps_srst_n", "cfg_*", "i2c_*",
            "uart_*", "jtag_*", "Net-(J2-*", "por_sense", "pg_*", "DDR3_VTT_EN"],
    "j3": [],           # filled below: every net on a J3 pin
    "lcd": ["lcd_*", "t_*"],
    "adc": ["adc_*", "adbsel*", "mon_*", "Net-(U1202--)", "led?_n", "Net-(D110?-A)"],
    "bucks": ["Net-(U3?1-FB)", "Net-(U3?1-SW)"],
    "soc_pwr": ["VCCPLL"],          # VCCAUX is the block's: its pours on In4/In6 come back after routing
    "mdi": ["eth_mdi_*"],
}
pads = {}
for f in b.GetFootprints():
    for p in f.Pads():
        pads.setdefault(p.GetNetname(), []).append((f.GetReference(), p.GetNumber()))
block = {n for n in pads if n.endswith("/VCCAUX") or ("DDR3" in n and n != "/DDR3_VTT_EN") or n.startswith("/01 ddr3/") or "(U20H-" in n or "(U8-" in n or "(D7-" in n}
nets = [n for n, ps in pads.items() if n and n not in POWER and n not in block and len(ps) > 1
        and not n.startswith("unconnected")]
short = {n: n.split("/")[-1] for n in nets}
j3 = {}
for n in nets:
    for ref, num in pads[n]:
        if ref == "J3":
            j3[n] = int(num)
out = {g: [] for g in GROUPS}
out["j3"] = sorted(j3, key=j3.get)
for n in sorted(nets):
    if n in j3:
        continue
    hit = [g for g, pats in GROUPS.items() if any(fnmatch.fnmatchcase(short[n], p) for p in pats)]
    assert len(hit) == 1, (n, hit)
    out[hit[0]].append(n)
j5 = {n: int(num) for n in out["lcd"] for ref, num in pads[n] if ref == "J5"}
out["lcd"].sort(key=j5.get)
# nets the router fenced in when they came late (passes 1-5): first of all, and the short local ones by
# tools/route/patch_route.py before the router lays anything around their pads
HARD = ["rgmii_rxd0", "rgmii_rx_ctl", "mdc", "eth_int_n", "qspi_io1", "rgmii_txc", "adbsel0", "adasel1_iso"]
LOCAL = ["phy_led0", "phy_led1", "phy_xi", "phy_xo", "phy_rset", "eth_led_k", "eth_led_a", "eth_ct", "ps_mio_vref",
         "ps_srst_n", "VCCPLL", "osc_vdd"]
out["hard"] = [n for h in HARD for n in nets if short[n] == h]
out["local"] = [n for h in LOCAL for n in nets if short[n] == h]
assert len(out["hard"]) == len(HARD) and len(out["local"]) == len(LOCAL)
out["supply"] = ["1V0", "1V8", "1V35", "3V3", "5V0", "3V3_analog"]
out["signals"] = [n for g in out for n in out[g] if g not in ("phy_pwr", "soc_pwr", "bucks", "mdi", "supply", "hard", "local")]
json.dump(out, open(os.path.join(ROOT, "tools", "route_groups.json"), "w"), indent=1)
print("groups:", ", ".join(f"{g} {len(v)}" for g, v in out.items()))
