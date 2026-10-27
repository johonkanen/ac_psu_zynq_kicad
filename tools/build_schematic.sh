#!/usr/bin/env bash
# Regenerate the symbol library and every scripted sheet, rebuild the root sheet pins, run ERC and the block check.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_symbols.py
for s in tools/sheets/[0-9][0-9]_*.py; do python3 "$s"; done
python3 tools/sync_root.py >/dev/null
mkdir -p reports
tools/p2k/bin/kicad-cli sch erc -o reports/erc.rpt kicad/zynq_card.kicad_sch 2>&1 | grep -v Font | tail -1
grep -E "^\[" reports/erc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
python3 tools/check_block_netlist.py
