#!/usr/bin/env bash
# What closed the last connections after tools/route.sh, in the order it was run by hand on 2026-11-20:
#   tools/route/finish.sh IN.kicad_pcb OUT.kicad_pcb       (IN: work/route/routed.kicad_pcb)
# Not deterministic, like the chain: check each step's output. tools/route/patch.sh reads the chain's keep-outs from
# work/route/keepouts.txt (the supply corridors must be in it, or a re-routed net cuts a supply strip: that
# happened to the B.Cu 1V35 strip once).
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
P="$R/tools/route/patch.sh"; KIPY="$R/tools/p2k/bin/kipy"
"$P" "$IN" "$T/a.kicad_pcb" --repair                       # nets in hole / clearance violations, routed again
"$P" "$T/a.kicad_pcb" "$T/b.kicad_pcb" --orphans           # copper of our nets that reaches no pad
# placement: R923 (strap) under its series resistor R911, C932 off the PHY's pins 22-23 to B.Cu; then the PHY's
# 1.0 V net and phy_rxd2 again
"$KIPY" "$R/tools/place_free.py" "$T/b.kicad_pcb" "$T/c.kicad_pcb" R923@R911.2:B/5 C932@U901.21:B/4 | grep -E "R923|C932"
"$KIPY" - "$T/c.kicad_pcb" <<'PY'
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
for t in [t for t in b.GetTracks() if t.GetNetname().endswith(("phy_vdd10", "phy_rxd2"))]:
    b.Delete(t)
pcbnew.SaveBoard(sys.argv[1], b)
PY
PATCH_MAX_LIFT=5 "$P" "$T/c.kicad_pcb" "$T/d.kicad_pcb" --rip --nets signals,phy_pwr,soc_pwr
"$R/tools/route/tie_planes.sh" "$T/d.kicad_pcb" "$T/e.kicad_pcb" "$T/open.txt"
PATCH_MAX_LIFT=5 "$P" "$T/e.kicad_pcb" "$T/f.kicad_pcb" --rip --planes --padfile "$T/open.txt"
"$P" "$T/f.kicad_pcb" "$T/g.kicad_pcb" --fill --auto supply       # pads tied to a plane island only: a track to good copper
"$KIPY" "$R/tools/route/place_c514.py" "$T/g.kicad_pcb" "$OUT" | tail -1
echo "finish: now tools/check_block_copper.py, check_heights.py and check_board.sh on $OUT"
