#!/usr/bin/env bash
# Supply planes after the routing (2026-11-20), in the order it was run by hand:  planes_fix.sh IN.kicad_pcb OUT.kicad_pcb
# The signals had cut the pours: the In6 neck of the 1V0 pour (1 of U20's 22 core vias reached from the regulator on
# that layer), the 3V3 pour at U20 and at the PHY, strips of the In4 1V8 pour. tools/route/plane_reach.py measures it.
# 1. our signals off In4/In6 inside the block area (west, south and east of U20; the breakout stubs under U20 stay),
#    off In6 at the 1V0 neck and beside the PHY, off In4 beside the eMMC. A net that finds no other way is put back;
# 2. the 0.1 mm supply tracks of 3V3 and 1V8 out, the pads tied again to plane copper that is reached from the
#    regulator (PATCH_REACH=1), 0.2 mm; what has no pad (via to via) by --auto supply;
# 3. GND pour pieces and pads (tie_planes.sh), dangling copper net by net (--trim), fiducials.
# The rectangles of step 1 must be in work/route/keepouts.txt afterwards (tools/route.sh does not write them yet), or
# the next re-route goes straight back onto the plane layers. Check with plane_reach.py and check_board.sh.
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
P="$R/tools/route/patch.sh"; KIPY="$R/tools/p2k/bin/kipy"; K="$R/work/route/keepouts.txt"
BOX="--keep-box 153.7,77.3,174.3,97.3"
AREAS=(In4.Cu,In6.Cu:141.9,77.3,153.7,97.9 In4.Cu,In6.Cu:141.9,97.3,179.5,99.5 In4.Cu,In6.Cu:174.3,77.3,179.5,97.9)
E=(); for a in "${AREAS[@]}"; do E+=(--evict "$a"); done
"$P" "$IN" "$T/a.kicad_pcb" $BOX "${E[@]}"
"$P" "$T/a.kicad_pcb" "$T/b.kicad_pcb" $BOX "${E[@]}"                    # again: the first pass made room
for a in "${AREAS[@]}" In6.Cu:150.0,83.0,160.5,92.5 In6.Cu:179.6,61.5,185.3,77.0 In4.Cu:183.4,64.0,185.3,84.0 \
         In6.Cu:166.0,87.0,168.6,90.6 In4.Cu:168.6,78.6,174.3,89.4 B.Cu:158.5,77.3,170.5,83.7; do
    for l in $(echo "${a%%:*}" | tr , ' '); do grep -qxF "$l:${a#*:}" "$K" || echo "$l:${a#*:}" >> "$K"; done
done
PATCH_MARGIN=26 "$P" "$T/b.kicad_pcb" "$T/c.kicad_pcb" --evict In6.Cu:150.0,83.0,160.5,92.5      # the 1V0 neck
PATCH_MARGIN=14 PATCH_MAX_LIFT=4 PATCH_ACCEPT_EQUAL=1 "$P" "$T/c.kicad_pcb" "$T/d.kicad_pcb" --rip --reroute dab_pwm_pri_lo_iso \
    || cp "$T/c.kicad_pcb" "$T/d.kicad_pcb"
PATCH_MARGIN=8 "$P" "$T/d.kicad_pcb" "$T/e.kicad_pcb" --evict In6.Cu:166.0,87.0,168.6,90.6
PATCH_MARGIN=6 "$P" "$T/e.kicad_pcb" "$T/f.kicad_pcb" --evict In4.Cu:183.4,64.0,185.3,84.0
PATCH_MARGIN=6 "$P" "$T/f.kicad_pcb" "$T/f2.kicad_pcb" --evict In6.Cu:179.6,61.5,185.3,77.0
# under U20's north-east corner (the VCCO_MIO vias), stubs and all; and off the B.Cu 1V35 pour's tab under U20
PATCH_MARGIN=5 "$P" "$T/f2.kicad_pcb" "$T/f3.kicad_pcb" --evict In4.Cu:168.6,78.6,174.3,89.4
PATCH_MARGIN=5 "$P" "$T/f3.kicad_pcb" "$T/g.kicad_pcb" --evict B.Cu:158.5,77.3,170.5,83.7
"$KIPY" - "$T/g.kicad_pcb" <<'PY'
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
for t in [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() in ("3V3", "1V8")
          and abs(pcbnew.ToMM(t.GetWidth()) - 0.1) < 1e-6]:
    b.Delete(t)
pcbnew.SaveBoard(sys.argv[1], b)
PY
cp "$T/g.kicad_pcb" "$T/h.kicad_pcb"
for pass in 1 2 3 4; do
    PATCH_REACH=1 PATCH_MAX_LIFT=4 "$P" "$T/h.kicad_pcb" "$T/i.kicad_pcb" --rip --planes | tail -1
    cp "$T/i.kicad_pcb" "$T/h.kicad_pcb"
done
PATCH_AUTO_WIDTH=0.2 "$P" "$T/h.kicad_pcb" "$T/j.kicad_pcb" --fill --auto supply | tail -1
"$R/tools/route/tie_planes.sh" "$T/j.kicad_pcb" "$T/k.kicad_pcb" "$T/open.txt" | grep -E "plane_vias:|left open"
PATCH_REACH=1 PATCH_MAX_LIFT=4 "$P" "$T/k.kicad_pcb" "$T/l.kicad_pcb" --rip --planes --padfile "$T/open.txt" | tail -1
for pass in 1 2 3; do
    "$P" "$T/l.kicad_pcb" "$T/m.kicad_pcb" --trim "$R/work/route/01_in.kicad_pcb" | tail -1; cp "$T/m.kicad_pcb" "$T/l.kicad_pcb"
done
"$R/tools/p2k/bin/kicad_env.sh" "$KIPY" "$R/tools/route/fiducials.py" "$T/l.kicad_pcb" "$OUT" | grep "^FID"
echo "planes_fix: now plane_reach.py, check_board.sh, check_block_copper.py, check_heights.py on $OUT"
