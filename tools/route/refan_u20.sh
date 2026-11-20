#!/usr/bin/env bash
# U20 breakout redone for routing (REUSE_LOG E16):  tools/route/refan_u20.sh IN.kicad_pcb OUT.kicad_pcb
#   1. tools/route/pin_swap_board.py: the old stubs (E14) off, U20's ball nets from the schematic (pin plan with
#      vivado/pinplan/balls.csv: J3 signals on package-edge balls);
#   2. tools/escape_u20.py with our B.Cu parts under U20 that sat on juliancoy's escape vias counted as movable, so
#      every escape he has is copied (67 balls);
#   3. tools/place_free.py: those 12 parts to the nearest spot clear of the vias. The strip east of U20 (no DDR copper)
#      is open for the VCCPLL bead, its 10 uF and the config pull-ups; C529 stays within 5.1 mm of H10 (UG933);
#   4. tools/fanout_u20.sh for the balls juliancoy leaves bare (dog-bones, then via-in-pad).
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"
KIPY="$R/tools/p2k/bin/kipy"
quiet() { grep -v -i -E 'debug: adding|legacy zone|best-effort|swig/python|memory leak' || true; }
MOV=C529,C601,C504,C516,C521,FB501,C528,R609,R610,R611,R607,R608
"$KIPY" "$R/tools/route/pin_swap_board.py" "$IN" "$OUT" 2>&1 | quiet | grep "pin_swap_board"
ESCAPE_U20_MOVABLE=$MOV "$KIPY" "$R/tools/escape_u20.py" "$OUT" 2>&1 | quiet | grep -E "escape_u20:|dropped"
"$KIPY" "$R/tools/place_free.py" "$OUT" "$OUT" --b-open=164.0,79.0,179.4,97.8 C529 C601 C504 C516 C521 \
    FB501@U20.H10/12 C528@FB501.2/10 R609/12 R610/12 R611/14 R607/14 R608@U20.B5/16 2>&1 | quiet
"$R/tools/fanout_u20.sh" "$OUT"
