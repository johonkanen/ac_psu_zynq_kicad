#!/usr/bin/env python3
"""Sheet 1 (ddr3): the DDR3 block schematic, imported from juliancoy/zynqPCB (MIT, NOTICE).

Source: reference/zynqpcb/DDR3.sch (KiCad 5 legacy, sheet path /58818A06/ in DFTBoard.sch), converted by
_legacy.convert() at the source coordinates: refs from the AR lines, wires/labels/notes 1:1, the global DDR3_* labels
keep their names, pin positions checked against the KiCad 5 symbols, +1V35 -> 1V35, +3V3 -> 3V3.

Changes to the block (REUSE_LOG.md):
- E3: the global label DDR3_VTT_EN (U8 EN; driven from PS_MIO14 + 20 k to 3V3 on juliancoy's Storage sheet) becomes
  a hierarchical label (sheet port), to be driven by our power sequencing;
- E4: U15/U16 value MT41K256M16HA-125:E -> MT41K256M16TW-107:P (same FBGA-96 land); the KiCad 5 SnapEDA fields
  (Field4..Field8) that name the old part are dropped.
"""
import os

from _common import *  # noqa: F401,F403
from _common import ROOT
from _legacy import convert
from p2k.sexpr import find

E3_PORT = "DDR3_VTT_EN"
E4 = {"value": "MT41K256M16TW-107:P", "fields": {"MPN": "MT41K256M16TW-107:P", "SPN": "", "LCSC": "C253882"},
      "drop": {"Field4", "Field5", "Field6", "Field7", "Field8"}}

NOTE = ("DDR3 block from juliancoy/zynqPCB (MIT, NOTICE), imported by tools/sheets/01_ddr3.py from DDR3.sch.\n"
        "References and DDR3_* names are the source's. Changes: REUSE_LOG.md E3 (DDR3_VTT_EN is a sheet port,\n"
        "driven by our power sequencing), E4 (U15/U16 MT41K256M16TW-107:P). Do not edit by hand.")


def main():
    sh = Sheet(os.path.join(ROOT, "kicad", "01_ddr3.kicad_sch")).clear()  # noqa: F405
    find(sh.tree, "paper")[1] = "A3"  # the source is A4, but its U20 unit runs into the frame
    r = convert(sh, "DDR3.sch", "/58818A06/", edits={"U15": E4, "U16": E4}, ports=(E3_PORT,))
    sh.text(NOTE, 12.7, 200.66)
    sh.save()
    print(f"01_ddr3: {len({p for p, _ in r['parts']})} parts, {r['power']} power symbols, {r['wires']} wires, "
          f"{r['texts']} texts")


if __name__ == "__main__":
    main()
