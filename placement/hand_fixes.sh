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
