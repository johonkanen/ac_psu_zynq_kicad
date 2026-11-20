#!/usr/bin/env bash
# Delete the dangling tracks and vias the routing left behind:  drop_dangling.sh IN.kicad_pcb OUT.kicad_pcb BASE.kicad_pcb
# kicad-cli's DRC decides (track_dangling, via_dangling, zones refilled); an item that is already on BASE (the board
# before routing: the copied block with the dangling vias and stubs it inherits from the source, and the breakout
# stubs) is never touched. Repeated until nothing is left: deleting one piece of a chain leaves the next dangling.
# A pass that opens a connection (a route that met its stub mid-way) is undone and ends the run.
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN="$(realpath "$1")"; OUT="$(realpath -m "$2")"; BASE="$(realpath "$3")"
T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
cp "$IN" "$T/b.kicad_pcb"; for f in kicad_pro kicad_dru; do cp "$R/kicad/zynq_card.$f" "$T/b.$f"; done
for pass in 1 2 3 4 5 6 7 8; do
    "$R/tools/p2k/bin/kicad-cli" pcb drc --refill-zones --save-board --severity-all --format json -o "$T/drc.json" \
        "$T/b.kicad_pcb" > /dev/null 2>&1 || true
    cp "$T/b.kicad_pcb" "$T/keep.kicad_pcb"
    n=$("$R/tools/p2k/bin/kipy" - "$T/b.kicad_pcb" "$T/drc.json" "$BASE" <<'PY' 2>/dev/null | tail -1
import json, re, sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
keep = set(re.findall(r'\(uuid "([0-9a-f-]+)"\)', open(sys.argv[3]).read()))
bad = {i["uuid"] for v in json.load(open(sys.argv[2]))["violations"] if v["type"] in ("track_dangling", "via_dangling")
       for i in v["items"]} - keep
kill = [t for t in b.GetTracks() if t.m_Uuid.AsString() in bad]
for t in kill:
    b.Delete(t)
pcbnew.SaveBoard(sys.argv[1], b)
print(len(kill))
PY
)
    echo "drop_dangling: pass $pass, $n items deleted"
    [ "$n" = 0 ] && break
    cp "$T/b.kicad_pcb" "$T/try.kicad_pcb"; cp "$T/b.kicad_pro" "$T/try.kicad_pro"; cp "$T/b.kicad_dru" "$T/try.kicad_dru"
    "$R/tools/p2k/bin/kicad-cli" pcb drc --refill-zones --severity-all --format json -o "$T/after.json" \
        "$T/try.kicad_pcb" > /dev/null 2>&1 || true
    u0=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['unconnected_items']))" "$T/drc.json")
    u1=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['unconnected_items']))" "$T/after.json")
    if [ "$u1" -gt "$u0" ]; then    # a route that joined its stub mid-way: the stub was holding it. Undo and stop
        echo "drop_dangling: pass $pass opened $((u1 - u0)) connections: undone, stopping"
        cp "$T/keep.kicad_pcb" "$T/b.kicad_pcb"; break
    fi
done
cp "$T/b.kicad_pcb" "$OUT"
