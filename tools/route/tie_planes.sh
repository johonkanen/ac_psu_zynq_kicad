#!/usr/bin/env bash
# Supply pads to their planes: DRC (zones refilled) -> tools/route/plane_vias.py, repeated until no pad is added.
# The first pass also stitches the F.Cu / B.Cu ground pours to the planes on a 2.5 mm grid.
#   tools/route/tie_planes.sh IN.kicad_pcb OUT.kicad_pcb [OPEN.txt]     OPEN.txt: the pads left open (REF.PAD per line)
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
cp "$IN" "$T/b.kicad_pcb"; for f in kicad_pro kicad_dru; do cp "$R/kicad/zynq_card.$f" "$T/b.$f"; done
for pass in 1 2 3 4 5 6; do
    "$R/tools/p2k/bin/kicad-cli" pcb drc --refill-zones --save-board --severity-all --format json -o "$T/drc.json" \
        "$T/b.kicad_pcb" > /dev/null 2>&1 || true
    STITCH=(); [ "$pass" = 1 ] && STITCH=(--stitch 2.5)
    "$R/tools/p2k/bin/kipy" "$R/tools/route/plane_vias.py" "$T/b.kicad_pcb" "$T/b.kicad_pcb" "$T/drc.json" "${STITCH[@]}" 2>&1 \
        | grep -E "^decap_connect|^plane_vias|^  [a-z ]+: [0-9]|^    " | sed "s/^decap_connect/plane_vias pass $pass/" | cut -c1-240 > "$T/out.txt"
    cat "$T/out.txt"
    grep -q "^plane_vias pass $pass: 0 loose" "$T/out.txt" && break
    grep -E "^  (in pad|beside|track|dogleg): [1-9]" -q "$T/out.txt" || break
done
cp "$T/b.kicad_pcb" "$OUT"
[ -n "${3:-}" ] && { grep -E "^    [A-Z]+[0-9]+\.[A-Z0-9]+ " "$T/out.txt" | awk '{print $1}' > "$3" || true; }
