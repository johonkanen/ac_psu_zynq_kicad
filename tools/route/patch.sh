#!/usr/bin/env bash
# DRC, then tools/route/patch_route.py on its unconnected items:  patch.sh IN.kicad_pcb OUT.kicad_pcb ARGS...
#   ARGS: --nets GROUPS | --tight --nets GROUPS | --fill --auto GROUPS | --planes   (the report path is put in after
#   --auto / --planes)
# Honours the chain's temporary keep-outs (work/route/keepouts.txt, written by tools/route.sh), else the DDR area.
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"; shift 2
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
cp "$IN" "$T/b.kicad_pcb"; for f in kicad_pro kicad_dru; do cp "$R/kicad/zynq_card.$f" "$T/b.$f"; done
FILL=(); [[ " $* " == *" --planes "* || " $* " == *" --fill "* || " $* " == *" --repair "* || " $* " == *" --trim "* ]] && FILL=(--refill-zones --save-board)
"$R/tools/p2k/bin/kicad-cli" pcb drc "${FILL[@]}" --severity-all --format json -o "$T/drc.json" "$T/b.kicad_pcb" > /dev/null 2>&1 || true
ARGS=()
for a in "$@"; do
    [ "$a" = "--fill" ] && continue
    ARGS+=("$a"); [[ "$a" == "--auto" || "$a" == "--planes" || "$a" == "--repair" || "$a" == "--trim" ]] && ARGS+=("$T/drc.json")
done
KEEP=(--keepout '*:147.5,52.3,179.5,77.3')
if [ -f "$R/work/route/keepouts.txt" ]; then    # the chain's temporary keep-outs (supply corridors, DDR)
    KEEP=(); while read -r k; do KEEP+=(--keepout "$k"); done < "$R/work/route/keepouts.txt"
fi
"$R/tools/p2k/bin/kipy" "$R/tools/route/patch_route.py" "$T/b.kicad_pcb" "$OUT" "${KEEP[@]}" "${ARGS[@]}" 2>&1 \
    | grep "^patch_route" | cut -c1-200 || true
