#!/usr/bin/env bash
# U20 I/O breakout stubs (REUSE_LOG E14), after the placement: tools/fanout_u20.sh [BOARD]
#   1. tools/escape_u20.py: juliancoy's escape of each bare signal ball, copied where it clears our copper;
#   2. KiCadRoutingTools bga_fanout (dog-bone) for the rest, 0.48/0.25 mm vias (via-in-pad allowed);
#   3. again for what is left, 0.30/0.15 mm vias, which fit in a pad between the 0.48 mm dog-bones (JLC fills and
#      caps via-in-pad free on 6+ layers; DRC rule u20_via_in_pad);
# with the SMD pads near U20 shadowed for bga_fanout (tools/fanout_u20.py: it does not see the other face's pads).
# Then DRC (zones refilled): a new net in a clearance/short/crossing violation loses its stub again (prune), until clean.
# Stubs end 0.5 mm past the ball field (escape_u20) or at bga_fanout's exit margin; phase 4 routes on from there.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"; R="$(dirname "$H")"
K=~/dev/KiCadRoutingTools; P=$K/.venv/bin/python; KIPY=$R/tools/p2k/bin/kipy
B="$(realpath "${1:-$R/kicad/zynq_card.kicad_pcb}")"
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
quiet() { grep -v -i -E 'debug|assert|legacy zone|best-effort|swig/python' || true; }

cp "$B" "$T/b.kicad_pcb"
for f in kicad_pro kicad_dru; do cp "$R/kicad/zynq_card.$f" "$T/b.$f"; done
$KIPY "$H/fanout_u20.py" nets "$T/b.kicad_pcb" "$T/bare.txt" 2>&1 | quiet
$KIPY "$H/escape_u20.py" "$T/b.kicad_pcb" 2>&1 | quiet | head -1
$KIPY "$H/fanout_u20.py" shadow-on "$T/b.kicad_pcb" 2>&1 | quiet
for v in "0.48 0.25" "0.3 0.15"; do
    read -r size drill <<< "$v"
    $KIPY "$H/fanout_u20.py" nets "$T/b.kicad_pcb" "$T/nets.txt" 2>&1 | quiet
    mapfile -t NETS < "$T/nets.txt"
    [ ${#NETS[@]} -gt 0 ] || break
    $P "$K/py_router/bga_fanout.py" "$T/b.kicad_pcb" -c U20 -o "$T/o.kicad_pcb" \
        --layers F.Cu In2.Cu In4.Cu In6.Cu B.Cu --track-width 0.1 --clearance 0.102 \
        --via-size "$size" --via-drill "$drill" --escape-method dogbone --same-net-pad-clearance -1 \
        --check-for-previous --plane-drop off --escalation off --no-fix-drc-settings \
        --nets "${NETS[@]}" > "$T/fanout.log" 2>&1 || { tail -20 "$T/fanout.log"; exit 1; }
    echo "fanout_u20: vias $size/$drill: $(grep -o '"escaped": [0-9]*, "failed": [0-9]*' "$T/fanout.log")"
    mv "$T/o.kicad_pcb" "$T/b.kicad_pcb"
done
$KIPY "$H/fanout_u20.py" shadow-off "$T/b.kicad_pcb" 2>&1 | quiet
for pass in 1 2 3; do
    $KIPY "$H/refill_zones.py" "$T/b.kicad_pcb" > /dev/null 2>&1
    "$R/tools/p2k/bin/kicad-cli" pcb drc --format json -o "$T/drc.json" "$T/b.kicad_pcb" > /dev/null 2>&1 || true
    python3 "$H/fanout_u20_bad.py" "$T/drc.json" "$T/bare.txt" > "$T/bad.txt"
    [ -s "$T/bad.txt" ] || break
    echo "fanout_u20: DRC pass $pass"
    $KIPY "$H/fanout_u20.py" prune "$T/b.kicad_pcb" "$T/bad.txt" 2>&1 | quiet
done
$KIPY "$H/fanout_u20.py" nets "$T/b.kicad_pcb" "$T/nets.txt" 2>&1 | quiet
echo "fanout_u20: left for phase 4: $(sed 's|.*/||' "$T/nets.txt" | tr '\n' ' ')"
cp "$T/b.kicad_pcb" "$B"
