#!/usr/bin/env bash
# PCB build: stack-up / net classes / DRC rules, DRC with schematic parity, the block copper check (LAYOUT_PLAN.md).
#   tools/build_pcb.sh            keep the board as it is
#   tools/build_pcb.sh --rebuild  recreate the board from the schematic (tools/make_board.py) and copy the block into it
#                                 (tools/import_block.py). Only until routing outside the block starts: it drops
#                                 everything on the board. After that, use pcbnew's "Update PCB from Schematic".
set -euo pipefail
cd "$(dirname "$0")/.."
quiet() { grep -v -e "Debug: Adding duplicate" -e "Legacy zone fill" -e "best-effort" || true; }
if [[ "${1:-}" == "--rebuild" ]]; then
    tools/p2k/bin/kipy tools/make_board.py 2>&1 | quiet
    python3 tools/board_setup.py
    tools/p2k/bin/kipy tools/import_block.py 2>&1 | quiet
else
    python3 tools/board_setup.py
fi
mkdir -p reports
tools/p2k/bin/kicad-cli pcb drc --schematic-parity -o reports/drc.rpt kicad/zynq_card.kicad_pcb 2>&1 | grep -v Font | tail -3
grep -E "^\[" reports/drc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
tools/p2k/bin/kipy tools/check_block_copper.py 2>&1 | quiet
