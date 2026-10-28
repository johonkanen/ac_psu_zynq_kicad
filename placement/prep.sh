#!/usr/bin/env bash
# Placement inputs (KiCadRoutingTools plan-pcb-placement), ported from the Ti135 repo:
#   placement/prep.sh [BOARD [RUN_DIR [--drop-soc-decaps]]]   default kicad/zynq_card.kicad_pcb, work/place
# Strips the copper (the placer refuses a routed board; the block parts and H1/H2 stay where tools/import_block.py put
# them, locked), locks the connectors, unplaces the rest, flips the power cells to B.Cu, emits and fixes the intent
# (block and heatsink keep-outs), fits the buck cell templates. A seed goes back onto the board with its copper through
# tools/apply_placement.py, which never moves a locked part.
# The pose trials (placement/pose_trial.sh) pass their own board and --drop-soc-decaps.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
R="$(dirname "$H")"; K=~/dev/KiCadRoutingTools; P=$K/.venv/bin/python
SRC="$(realpath "${1:-$R/kicad/zynq_card.kicad_pcb}")"; W="$(realpath -m "${2:-$R/work/place}")"; DROP="${3:-}"
mkdir -p "$W"; cd "$W"; cp "$H/groups.json" .
$P -X utf8 $K/tests/stress/strip_copper_only.py "$SRC" stripped.kicad_pcb | tail -1
$P -X utf8 $K/py_placer/place_pose.py stripped.kicad_pcb locked.kicad_pcb lock J3 J6 J9 J5 J1 J2 | tail -1
$P -X utf8 $K/.claude/skills/plan-pcb-placement/scripts/make_unplaced.py locked.kicad_pcb fixed.kicad_pcb --keep-locked \
    | tail -1
for b in stripped locked fixed; do for e in kicad_pro kicad_dru; do cp "${SRC%.kicad_pcb}.$e" $b.$e; done; done
cp "$(dirname "$SRC")/fp-lib-table" . 2>/dev/null || true
$R/tools/p2k/bin/kipy "$H/flip_bottom.py" fixed.kicad_pcb $DROP 2>&1 | grep -v "swig/python"
$P -X utf8 $K/py_tools/check_floorplan.py fixed.kicad_pcb --emit-intent intent.json > /dev/null 2>&1 || true
$R/tools/p2k/bin/kipy "$H/fix_intent.py" intent.json fixed.kicad_pcb  # the zones survive the strip, unfilled
# buck cell templates (TI TLV62585 Figure 24; B.Cu variants: sides and turns mirrored, as on the Ti135 card)
for sk in "$H"/sketches_B/U*.json; do
    $P -X utf8 $K/py_tools/fit_template.py fixed.kicad_pcb --sketch "$sk" --intent intent.json \
        --write-intent intent.json \
        | grep -E "^  (ground return|NOTE)" | grep -v ESTIMATED || true
done
[[ -n "$DROP" ]] || cp intent.json "$H/intent.json"
