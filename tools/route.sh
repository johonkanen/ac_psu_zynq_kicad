#!/usr/bin/env bash
# Routing chain: the placed board (git) -> the routed board, every step rerunnable (kicad-agentic-routing skill).
#   tools/route.sh [LAST_STEP [FROM_STEP]]        -> work/route/routed.kicad_pcb
# Input: kicad/zynq_card.kicad_pcb as committed at $BASE (the board before routing; placement changes since then are
# steps here). Work files work/route/NN_step.kicad_pcb (+ .log/.json). Net groups: tools/route/groups.py ->
# tools/route_groups.json; router defaults: routing.json. Nothing is written to kicad/ (copy the result when it is
# accepted).
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"
BASE="${BASE:-89d963e}"
SK="${ROUTING_SKILL:-$HOME/.claude/skills/kicad-agentic-routing/scripts}"
export KICAD_ENV="$R/tools/p2k/bin/kicad_env.sh" ROUTING_CONFIG="$R/routing.json"
K="${KRT:-$HOME/dev/KiCadRoutingTools}"; KIPY="$R/tools/p2k/bin/kipy"
LAST="${1:-}"; FROM="${2:-}"
W="$R/work/route"; mkdir -p "$W"
N=0; CUR=""; SKIP=0; [ -n "$FROM" ] && SKIP=1
quiet() { grep -v -i -E 'debug: adding|legacy zone|best-effort|swig/python|memory leak|no destructor' || true; }

begin() {   # begin NAME -> sets OUT; returns 1 when the step is skipped (resuming)
    N=$((N + 1)); OUT="$W/$(printf %02d "$N")_$1.kicad_pcb"; NAME="$1"
    if [ "$SKIP" = 1 ] && [ "$FROM" != "$1" ]; then CUR="$OUT"; return 1; fi
    SKIP=0; echo "== $1"; return 0
}
done_() { CUR="$OUT"; if [ "$LAST" = "$NAME" ]; then cp "$CUR" "$W/routed.kicad_pcb"; echo "stopped after $NAME"; exit 0; fi; }
step() {    # step NAME GROUPS [route.py options]: one router step, then lock the group
    begin "$1" || return 0
    python3 -I "$SK/route_step.py" "$CUR" "$OUT" "${@:2}" 2>&1 | cut -c1-500
    "$KIPY" -I "$SK/lock_tracks.py" "$OUT" lock "$2" 2>&1 | quiet | tail -1
    done_
}
area() {    # area NAME X0 Y0 X1 Y1 FORBID LAYERS...: a temporary rule area on $OUT (in place)
    (cd "$K" && .venv/bin/python py_router/add_rule_area.py "$OUT" "$OUT" --name "ROUTE_TMP_$1" --rect "$2" "$3" "$4" "$5" \
        --forbid $6 --layers "${@:7}" | head -1 | cut -c1-110)
    local l; for l in "${@:7}"; do echo "$l:$2,$3,$4,$5" >> "$W/keepouts.txt"; done    # for tools/route/patch.sh
}

# --- placement and breakout -----------------------------------------------------------------------------------
if begin in; then git show "$BASE:kicad/zynq_card.kicad_pcb" > "$OUT"; done_; fi
if begin place; then "$KIPY" tools/route/place_bucks.py "$CUR" "$OUT" 2>&1 | quiet; done_; fi
if begin fan; then
    "$KIPY" tools/route/groups.py "$CUR" 2>&1 | quiet | tail -1
    tools/route/refan_u20.sh "$CUR" "$OUT" 2>&1 | quiet
    # eMMC balls (0.5 mm pitch) and PHY pins (0.4 mm): breakouts copied from the Ti135 card where they clear
    "$KIPY" tools/route/escape_copy.py "$OUT" "$OUT" U1001 U901 2>&1 | quiet | grep -E "escape_copy|skipped"
    done_
fi
# --- prep: the block's pours off the routing layers; keep-outs for the DDR and for the supply copper to come -----
if begin prep; then
    python3 tools/route/zones.py drop "$CUR" "$OUT" "$W/pours.txt" F.Cu In2.Cu In4.Cu In6.Cu B.Cu
    : > "$W/keepouts.txt"
    ALL="F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu"
    area DDR    147.5 52.3 179.5 77.3 "tracks vias" $ALL        # the DRAMs and their buses
    echo "*:147.5,52.3,179.5,77.3" >> "$W/keepouts.txt"
    area V135   174.3 72.6 198.2 76.4 "tracks vias" B.Cu        # 1V35: U331 cell -> the block's B.Cu pour
    area V10    146.5 90.0 158.6 104.6 "tracks" In6.Cu          # 1V0: U301 cell -> the block's In6 pour
    area V18    166.0 97.0 176.0 104.6 "tracks" In4.Cu          # 1V8: U311 cell -> the block's In4 pour
    area V50S   139.0 110.6 207.1 113.1 "tracks" B.Cu           # 5V0 band along the south edge
    area V50E   203.3 71.8 207.1 116.4 "tracks" B.Cu            # 5V0 strip up the east edge
    area VAUX4  164.3 84.8 174.0 87.5 "tracks" In4.Cu           # the block's VCCAUX pours under U20
    area VAUX6  160.3 84.9 165.5 86.8 "tracks" In6.Cu
    area V50a   199.0 76.0 203.4 77.15 "tracks" B.Cu            # 5V0 tabs to the cells' input capacitors
    area V50b   200.0 89.05 203.4 90.25 "tracks" B.Cu
    area V50c   172.8 104.7 177.0 110.7 "tracks" B.Cu
    area V50d   158.3 104.45 162.1 110.7 "tracks" B.Cu
    area P10    152.4 99.6 157.0 105.75 "tracks" B.Cu           # the cells' output patches (L, COUT, plane vias)
    area P18    167.4 100.65 171.35 106.45 "tracks" B.Cu
    area P33    194.6 85.0 198.55 90.8 "tracks" B.Cu
    area P135   195.5 72.0 197.5 77.75 "tracks" B.Cu
    area V135F  175.5 72.6 178.6 76.4 "tracks vias" F.Cu        # 1V35: F.Cu link between the block's F and B pours
    # Locks: the copied block entirely. KICAD_RIP_PREEXISTING=0 did not stop a router step from ripping DDR3_DQ4
    # (18 items, found by tools/check_block_copper.py) to get a QSPI net through; a locked track is never ripped.
    # Our own breakout stubs stay free (locking them all cost about ten nets: the router re-lays stubs when it
    # may), but for the config stubs (the qspi step ripped the ps_clk escape and could not put it back).
    "$KIPY" -I "$SK/lock_tracks.py" "$OUT" lock-all 2>&1 | quiet | tail -1
    "$KIPY" tools/route/unlock_nets.py "$OUT" signals,phy_pwr,soc_pwr,bucks 2>&1 | quiet | tail -1
    "$KIPY" -I "$SK/lock_tracks.py" "$OUT" lock cfg 2>&1 | quiet | tail -1
    done_
fi
# --- signals: near the SoC and most constrained first --------------------------------------------------------
# The MIO side (fine-pitch flash, eMMC, PHY) takes 0.30/0.15 mm vias at 0.125 mm clearance (hole to copper 0.2 mm).
SMALL=(--via-size 0.3 --via-drill 0.15 --clearance 0.125 --hole-to-hole-clearance 0.25)
patch() {   # patch NAME ARGS...: tools/route/patch.sh as a chain step
    begin "$1" || return 0
    tools/route/patch.sh "$CUR" "$OUT" "${@:2}"
    done_
}
# the nets that get fenced in when they come late: the long ones by the router, the short local ones (PHY supplies,
# crystal, LEDs, VREF, VCCPLL) by the patch router, before anything lies around their pads
step hard     hard "${SMALL[@]}"
# supply pads that share a tight spot: joined to each other now, tied to their plane as one later (tie)
patch local0  U901.29\>C940.1:0.15 U901.29\>C941.1:0.15 R612.1\>C19.1:0.15 C19.1\>R10.2:0.15
patch local   --nets local,phy_pwr
"$KIPY" -I "$SK/lock_tracks.py" "$CUR" lock local,phy_pwr 2>&1 | quiet | tail -1
step qspi     qspi "${SMALL[@]}"
step emmc     emmc "${SMALL[@]}"
step rgmii_tx rgmii_tx "${SMALL[@]}"
step rgmii_rx rgmii_rx "${SMALL[@]}"
step eth_slow eth_slow "${SMALL[@]}"
step phy_pwr  phy_pwr "${SMALL[@]}" --track-width 0.15
step cfg      cfg "${SMALL[@]}"
# bank 33 (SW corner of U20) before the J3 bundle, which passes outside it
step lcd      lcd --ordering original
step adc      adc
step j3       j3 --ordering original
step bucks    bucks --power-nets 'Net-(U3?1-SW)' --power-nets-widths 0.5
step soc_pwr  soc_pwr --track-width 0.3
step leftovers signals,phy_pwr,bucks,soc_pwr "${SMALL[@]}"
patch patch1  --nets signals,phy_pwr,soc_pwr
patch patch2  --tight --nets signals,phy_pwr,soc_pwr
patch rip     --rip --nets signals,phy_pwr,soc_pwr      # lift one or two of our nets that box a pad in, re-route them
cp "$CUR" "$W/routed_signals.kicad_pcb"; echo "wrote work/route/routed_signals.kicad_pcb"

# --- supplies: keep-outs off, the block's pours back, our pours (tools/route/power_zones.py), pads tied to the planes
if begin pours; then
    python3 tools/route/zones.py rmarea "$CUR" "$OUT" ROUTE_TMP_
    python3 tools/route/zones.py restore "$OUT" "$OUT" "$W/pours.txt"
    "$KIPY" tools/route/power_zones.py "$OUT" "$OUT" 2>&1 | quiet
    done_
fi
if begin tie; then tools/route/tie_planes.sh "$CUR" "$OUT" "$W/tie_open.txt"; done_; fi
# what the via script could not reach (eMMC balls, PHY pins): a track to the pour or to a via site; then the sense
# resistors far from their rail (mon_*, por_sense dividers), pad to pad
patch tie2    --rip --planes --padfile "$W/tie_open.txt"
patch sense   --fill --auto supply
if begin clean; then tools/route/drop_dangling.sh "$CUR" "$OUT" "$W/04_prep.kicad_pcb"; done_; fi
"$KIPY" -I "$SK/lock_tracks.py" "$CUR" unlock 2>&1 | quiet | tail -1
cp "$CUR" "$W/routed.kicad_pcb"; echo "wrote work/route/routed.kicad_pcb"
