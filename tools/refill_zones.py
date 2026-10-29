#!/usr/bin/env python3
"""Refill every zone of kicad/zynq_card.kicad_pcb (kipy; tools/p2k/bin/kipy tools/refill_zones.py [BOARD]).
tools/build_pcb.sh --rebuild runs it last: tools/import_block.py fills the zones before tools/apply_placement.py puts
our parts back, and a stale fill under a moved pad reads as a clearance error."""
import os
import sys

import pcbnew

board = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "kicad", "zynq_card.kicad_pcb")
b = pcbnew.LoadBoard(board)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(board, b)
print(f"refill_zones: {len(b.Zones())} zones refilled")
