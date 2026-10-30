#!/usr/bin/env bash
# Step 4.4 fixes after the KRT placement (LAYOUT_PLAN.md step 4), with tools/place_free.py:
#   placement/hand_fixes.sh [IN [OUT]]     default: kicad/zynq_card.kicad_pcb in place
# The order is the priority: who gets the best spots under U20 (B.Cu, between the block's vias).
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
IN="${1:-$R/kicad/zynq_card.kicad_pcb}"; OUT="${2:-$IN}"
SPECS=(
  # the QSPI flash first (its straps below follow it), by its escape vias (REUSE_LOG E10, U20 NE): the block's east
  # edge is the eMMC's, so it lands south-east of the block
  U801@172.0,80.6:F/25
  # VCCPLL filter at H10 (E5: C529 within 5.1 mm of the H10/GND vias; FB501 between the 1V8 and VCCPLL balls)
  C529 FB501@U20.H10 C528
  # our SoC decaps (sheet 5), 0402 at their rails' balls: 470 n first, then 4.7 u
  C505 C506 C507 C513 C514 C515 C519 C520 C521 C525 C526 C527
  C503 C504 C516 C517 C518 C522 C523 C524
  # config: PS_MIO_VREF divider and cap at F8, PS_POR_B / PS_SRST_B / DONE pulls, the MIO boot straps at their balls
  C601 R609 R610 R608@U20.B5 R611 R612 R607
  # the QSPI straps (at the flash or their balls); the PHY crystal under the PHY area on B.Cu (0.8 mm; F is full of
  # the PHY's passives) with its load caps
  Y901/10 C910@Y901.1 C911@Y901.3
  # PS_CLK oscillator on F at the block edge nearest F7 (on B it would sit under the DDR), its supply filter beside it,
  # the 33 R source-series at its output; the SD0 CLK 0 R at its ball (E14)
  Y701@U20.F7:F/20 FB701@Y701.4:F C701@Y701.4:F R701@Y701.3:F R1001@U20.E14
  # RGMII TX series 22 R at the SoC end (sheet 9: TX at the SoC, RX at the PHY): U20's TX balls (NE corner) have no
  # room under U20 and the eMMC fills F.Cu at the block's east edge, so B.Cu just east of the block, west of the eMMC
  # ball field (x >= 183), in ball order; R606 (MIO7 strap on emmc_rst_n, no room at D5) on top of the column
  R606@180.6,81.55 R901@180.6,82.6 R904@180.6,83.65 R906@180.6,84.7 R903@180.6,85.75 R905@180.6,86.8 R902@180.6,87.85
  # bulk caps too tall for B.Cu (2.5-3.1 mm; B.Cu parts stay under 2.0 mm): on F at the block edge by their rails
  C502:F/25 C501:F/25 C508:F/25 C509:F/25 C510:F/25 C511:F/25 C512:F/25
)
"$R/tools/p2k/bin/kipy" "$R/tools/place_free.py" "$IN" "$OUT" "${SPECS[@]}" 2>&1 | grep -v -e swig -e "Debug: Adding" \
    -e "Legacy zone" -e "best-effort"
# U801's fan-out (tools/fanout_u801.py: one via between the balls per used ball), then its decap, the CS# pull-up and
# the MIO boot straps on B.Cu beside the via field, never over a via (--clear-vias), each at its ball (2026-10-29)
"$R/tools/p2k/bin/kipy" "$R/tools/fanout_u801.py" "$OUT" 2>&1 | grep -v -e swig -e "Debug: Adding"
"$R/tools/p2k/bin/kipy" "$R/tools/place_free.py" "$OUT" "$OUT" --clear-vias C801@U801.B4/5 R801@U801.C2/5 R601@U801.D3/6 \
    R602@U801.D2/6 R603@U801.C4/6 R604@U801.D4/6 R605@U801.B2/6 2>&1 | grep -v -e swig -e "Debug: Adding" \
    -e "Legacy zone" -e "best-effort"
# The PHY in front of the magjack (as on the zynq_mini, 2026-10-29): U901 at J9's pin side, MDI facing the jack
# (180 deg: RX west to the SoC, TX north, crystal side south); decaps, FB901, RSET and the RX series 22 R on F.Cu around
# it; straps, LED/MDIO/INT pull-ups, the reset buffer and the crystal under it on B.Cu. MDI 4.2-7.1 mm to J9's pins.
"$R/tools/p2k/bin/kipy" "$R/tools/place_free.py" "$OUT" "$OUT" U901@185.5,61.6,180:F/0.5 \
    C921:F/6 C931:F/6 C934:F/6 C933:F/6 C936:F/6 C941@U901.29:F/6 C922:F/6 C932:F/6 C930:F/6 C935:F/6 \
    C940@U901.29:F/6 FB901:F/6 C920:F/8 R931:F/6 R910:F/6 R912:F/6 R908:F/6 R911:F/6 R909:F/6 R907:F/6 \
    Y901@U901.36:B/6 C910@Y901.1:B/4 C911@Y901.3:B/4 \
    R920:B/6 R921:B/6 R922:B/6 R923:B/6 R924:B/6 R925:B/6 R926:B/6 R927:B/6 R928:B/8 R950@U901.34:B/8 R929:B/8 \
    R930:B/8 U902@U901.12:B/10 C901:B/8 R932:B/8 R933:B/10 C951@U902.5:B/10 C950@J9.1:F/6 2>&1 \
    | grep -v -e swig -e "Debug: Adding" -e "Legacy zone" -e "best-effort"
# The PHY area tightened (2026-10-30, after the Avaota A1 PHY layout, U12 + HR911130A; used only as a reference, it is
# CERN-OHL-S): the MDI corridor between U901 and J9 and the TX/MDC/MDIO exit north of U901 are kept free of F.Cu parts
# (--keepout). The VDD10 decaps of pins 3 and 8 (C933, C934) go on B.Cu just outside those pins: one via per pin
# between the MDI pins (x +3.25 from U901), the GND pad to the exposed pad's B.Cu copper. FB901/C920 move north-east,
# out of the D pair's path; R909/R911 (RX, north) and C930 out of the TX exit, to the north-west corner; R933 to U902,
# R950 to J9's LED pin. The RX resistors stay split around the west side: the block keep-out leaves 2.85 mm there.
"$R/tools/p2k/bin/kipy" "$R/tools/place_free.py" "$OUT" "$OUT" --keepout=F:188.34,58.6,190.07,64.6 \
    --keepout=F:189.4,56.9,190.07,66.3 --keepout=F:183.5,52.5,186.3,58.455 \
    C933@189.45,63.08,90:B/0.5 C934@189.45,60.12,90:B/0.5 \
    C930@182.3,57.95,0:F/1 R909@182.3,56.9,0:F/1 R911@182.3,55.85,0:F/1 \
    C920@187.3,55.6,90:F/1.5 FB901@188.9,56.0,90:F/1.5 R933:B/8 R950@J9.11:B/10 2>&1 \
    | grep -v -e swig -e "Debug: Adding" -e "Legacy zone" -e "best-effort"
