#!/usr/bin/env python3
"""Project symbol library lib/zynq_card.kicad_sym (tools/p2k symgen).

    tools/gen_symbols.py           write the library
    tools/gen_symbols.py --check   fail if it is out of date

Sources: KiCad 10 standard symbols (copied and renamed), and the block's symbols from juliancoy/zynqPCB
(reference/zynqpcb/DFTBoard-cache.lib, KiCad 5, upgraded with `kicad-cli sym upgrade` into work/): the XC7Z020-CLG484
(all 9 units, used by sheet 1 and by our SoC sheets), the MT41K256M16 FBGA-96 and the TPS51200.
The block's passives (R, R_Small, C_Small, LED) use the KiCad 10 symbols; tools/sheets/01_ddr3.py checks that their
pins sit where the KiCad 5 ones did.
"""
import copy
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.symgen import Sym, find, find_all, from_std, load, power, rename, run, set_prop  # noqa: E402

JC_LIB = os.path.join(ROOT, "reference", "zynqpcb", "DFTBoard-cache.lib")
JC_SYM = os.path.join(ROOT, "work", "jc_cache.kicad_sym")

# juliancoy cache name -> (our name, reference, value, description)
JC_SYMBOLS = {
    "xilinx7_xc7z020clg484": ("XC7Z020-CLG484", "U", "XC7Z020-1CLG484I",
                              "AMD Zynq-7000 SoC, CLG484 (symbol from juliancoy/zynqPCB, MIT)"),
    "DFTBoard-rescue_MT41K256M16HA-125_E-MT41K256M16HA-125_E": (
        "MT41K256M16-FBGA96", "U", "MT41K256M16TW-107:P",
        "4 Gb DDR3L x16, 96-ball FBGA (symbol from juliancoy/zynqPCB, MIT)"),
    "tps51200DRCR_TPS51200DRCR": ("TPS51200", "U", "TPS51200DRCR",
                                  "DDR termination regulator, VTT/VREF (symbol from juliancoy/zynqPCB, MIT)"),
}


def jc_cache():
    """The juliancoy cache library as a KiCad 10 .kicad_sym (re-upgraded when the source is newer)."""
    if not os.path.exists(JC_SYM) or os.path.getmtime(JC_SYM) < os.path.getmtime(JC_LIB):
        os.makedirs(os.path.dirname(JC_SYM), exist_ok=True)
        subprocess.run([os.path.join(TOOLS, "p2k", "bin", "kicad-cli"), "sym", "upgrade", "-o", JC_SYM, JC_LIB],
                       check=True, capture_output=True)
    return {s[1]: s for s in find_all(load(JC_SYM), "symbol")}


def from_jc(cache, name):
    new, ref, value, desc = JC_SYMBOLS[name]
    sym = rename(copy.deepcopy(cache[name]), new)
    set_prop(sym, "Reference", ref)
    set_prop(sym, "Value", value)
    set_prop(sym, "Footprint", "")
    set_prop(sym, "Datasheet", "")
    set_prop(sym, "Description", desc)
    sym[:] = [c for c in sym if not (isinstance(c, list) and c[0] == "property"
                                     and c[1] not in ("Reference", "Value", "Footprint", "Datasheet", "Description"))]
    # hidden power pins become passive (they are wired explicitly on our sheets)
    for sub in find_all(sym, "symbol"):
        for p in find_all(sub, "pin"):
            if find(p, "hide") and str(p[1]) in ("power_in", "power_out"):
                p[1] = Sym("passive")
    return sym


def build():
    cache = jc_cache()
    syms = [from_jc(cache, n) for n in JC_SYMBOLS]
    syms += [
        from_std("Device", "R", "R", "R"),
        from_std("Device", "R_Small", "R_Small", "R"),
        from_std("Device", "C", "C", "C"),
        from_std("Device", "C_Small", "C_Small", "C"),
        from_std("Device", "LED", "LED", "D"),
        rename(from_std("power", "PWR_FLAG", "PWR_FLAG", "#FLG"), "PWR_FLAG"),
    ]
    syms += [power(n, n == "GND") for n in ("GND", "1V35", "3V3")]
    return syms


if __name__ == "__main__":
    sys.exit(run(build))
