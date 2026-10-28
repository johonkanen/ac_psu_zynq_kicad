#!/usr/bin/env bash
# One block pose trial (LAYOUT_PLAN.md step 3):  placement/pose_trial.sh NAME X Y ROT [SEEDS]
# In work/pose/NAME: the block imported with U20 at (X, Y), rotation ROT (tools/import_block.py), our SoC decaps
# dropped, the placement inputs (placement/prep.sh), place_simple over SEEDS (default 0-5), then judge_seeds routes
# the best seeds with placement/pose_chain.txt (block copper protected) and scores them (s<S>_fast.score.json, the
# ranking in judge.log).
# The base board (make_board + board_setup, no copper) is work/pose/base.kicad_pcb, made when missing: delete it after
# a schematic change.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
R="$(dirname "$H")"; K=~/dev/KiCadRoutingTools; P=$K/.venv/bin/python; KIPY=$R/tools/p2k/bin/kipy
NAME=$1; X=$2; Y=$3; ROT=$4; SEEDS=${5:-0-5}
BASE=$R/work/pose/base.kicad_pcb; W=$R/work/pose/$NAME
quiet() { grep -v -e "swig/python" -e "Debug: Adding duplicate" -e "Legacy zone fill" -e "best-effort" || true; }
if [[ ! -f $BASE ]]; then
    mkdir -p "$(dirname "$BASE")"
    P2K_PCB=$BASE $KIPY $R/tools/make_board.py 2>&1 | quiet | tail -1
    P2K_PCB=$BASE python3 $R/tools/board_setup.py
fi
rm -rf "$W"; mkdir -p "$W/wk"
P2K_PCB=$BASE $KIPY $R/tools/import_block.py --at "$X" "$Y" --rot "$ROT" --out "$W/board.kicad_pcb" 2>&1 \
    | quiet | tail -1
$KIPY "$H/flip_bottom.py" "$W/board.kicad_pcb" --drop-soc-decaps 2>&1 | quiet
"$H/prep.sh" "$W/board.kicad_pcb" "$W" 2>&1 | quiet | grep -v "ground return"
cd "$W"
$P -X utf8 $K/py_placer/place_simple.py fixed.kicad_pcb 'wk/s{seed}.kicad_pcb' --seeds "$SEEDS" --groups groups.json \
    --intent intent.json --jobs 4 --json 'wk/s{seed}.json' > place.log 2>&1 || true
tail -4 place.log
cd $K   # KICAD_RIP_PREEXISTING=0: the router must never rip the block copper (it did, and restored it, on 2026-10-28)
KICAD_RIP_PREEXISTING=0 $P -X utf8 py_placer/judge_seeds.py "$W/wk/judge.json" --chain "$H/pose_chain.txt" \
    --intent "$W/intent.json" --jobs 2 > "$W/judge.log" 2>&1 || true
grep -v "^JSON_SUMMARY" "$W/judge.log" | tail -12
