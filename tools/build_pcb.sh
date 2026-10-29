#!/usr/bin/env bash
# PCB build: stack-up / net classes / DRC rules, DRC with schematic parity, the block copper check (LAYOUT_PLAN.md).
#   tools/build_pcb.sh            keep the board as it is
#   tools/build_pcb.sh --rebuild  recreate the board from the schematic (tools/make_board.py), copy the block into it
#                                 (tools/import_block.py) and put every other part back where it was
#                                 (tools/apply_placement.py, from a copy in work/). Only until routing outside the block
#                                 starts: it drops all other copper. After that, use pcbnew's
#                                 "Update PCB from Schematic".
set -euo pipefail
cd "$(dirname "$0")/.."
quiet() { grep -v -e "Debug: Adding duplicate" -e "Legacy zone fill" -e "best-effort" || true; }
if [[ "${1:-}" == "--rebuild" ]]; then
    mkdir -p work && cp kicad/zynq_card.kicad_pcb work/before_rebuild.kicad_pcb
    tools/p2k/bin/kipy tools/make_board.py 2>&1 | quiet
    python3 tools/board_setup.py
    tools/p2k/bin/kipy tools/import_block.py 2>&1 | quiet
    tools/p2k/bin/kipy tools/apply_placement.py work/before_rebuild.kicad_pcb 2>&1 | quiet | grep -v swig/python
    tools/p2k/bin/kipy tools/refill_zones.py 2>&1 | quiet
else
    python3 tools/board_setup.py
fi
mkdir -p reports
tools/p2k/bin/kicad-cli pcb drc --schematic-parity -o reports/drc.rpt kicad/zynq_card.kicad_pcb 2>&1 | grep -v Font | tail -3
grep -E "^\[" reports/drc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
tools/p2k/bin/kipy tools/check_block_copper.py 2>&1 | quiet
