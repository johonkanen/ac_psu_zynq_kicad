# Layout plan: phase 3 (board, block import, placement)

Written 2026-10-27, at the start of phase 3. It expands PLAN.md §4.2 (transfer) and §5 phase 3 into steps and
scripts. Routing outside the block is phase 4 (PLAN.md §5). The tools are KiCadRoutingTools (`~/dev/KiCadRoutingTools`,
as in the Ti135 repo) and this repo's scripts, run with `tools/p2k/bin/kipy`.

## Ground rules

- `kicad/zynq_card.kicad_pcb` is the only real board. Tool runs work on copies in `work/`. A result is applied back
  only after its check passes.
- **The block is copied, never re-drawn.** Inside the `User.1` outline, every change is a `REUSE_LOG.md` entry.
- **Rebuild until the first copper outside the block.** `tools/build_pcb.sh --rebuild` recreates the board:
  make_board → import_block → apply_placement. After phase 4 starts, schematic changes go in with
  "Update PCB from Schematic".
- Gate for each step: DRC with our rules, schematic parity 0, the block copper check 0 differences, commit.

## Fixed inputs

| Item | Value | Where |
|---|---|---|
| Outline | 76.000 × 65.127 mm, KiCad x 131.531…207.531, y 51.694…116.821; aux origin (100, 100) | MECHANICAL.md |
| J3 / J6 (B.Cu), J9 / J5 / J1 / J2 (top) | the MECHANICAL.md positions, checked by make_board | MECHANICAL.md |
| Stack-up | JLC081611-7628: F · In1 GND · In2 sig · In3 GND · In4 sig · In5 GND · In6 sig · B | ZYNQ_PCB_NOTES.md §6.4 |
| Layer map from the source | `TOP_GND` → F, `GND0` → In1, `SIGNAL1` → In2, `GND1` → In3, `SIGNAL2` → In4, `GND2` → In5, `SIGNAL4` → In6, `BOTTOM` → B | PLAN.md §4.2 |
| Block rules | 0.102 mm width / clearance, juliancoy's via sizes; exempt from our width rules | PLAN.md §4.3 |
| Heatsink | 2 × NPTH Ø3.2 mm at U20 ± (14.93, 14.93) in the block frame, Ø6 mm F/B keep-out, nothing taller than the package under the 24 × 23.5 mm base | POWER_BUDGET.md §Heatsink |
| Bottom side | ≤ 5.3 mm gap to the baseboard; power cells on B.Cu, as on the Ti135 card | MECHANICAL.md |

## The block, measured on the source (2026-10-27)

Source frame (juliancoy `DFTBoard.kicad_pcb`), U20 at (166.0, 142.0), rotation −90°. Offsets below are from U20.

| | Extent | Note |
|---|---|---|
| DDR3 copper (`DDR3_*` tracks and vias) | x −21.1…+14.9, y −32.7…−3.6 | DRAMs U15/U16 at y −25.5, U8 (VTT) at (−15.2, −28.8) on B.Cu |
| Block parts (centres, the 101 parts of `tools/check_block_netlist.py`) | x −21.1…+13.4, y −33.2…+8.1 | |
| U20 body | ±9.5 | |
| **Block, with pads** | **about 39 × 43 mm**: x −22.5…+16, y −34…+9.5 | PLAN.md said 36 × 44 |

U20 I/O banks, in the same frame (centroid of the I/O balls):

| Bank | Side of U20 | Use here |
|---|---|---|
| 502 (DDR) | north (−y) | the block |
| 500 (MIO 0–15, QSPI) | north-east | U801 |
| 501 (MIO 16–53: RGMII, SD0, UART, I2C, MDIO) | east | U901, U1001, U1301 |
| 34 | south, centre | J3 (32 signals) |
| 33 | south-west | ADC, J5, LEDs |
| 13 | west | spare |
| 35 | south-east | spare |

## Step 1: board and rules (no copper): done 2026-10-27

New scripts, ported from the Ti135 repo:

| Script | Content |
|---|---|
| `tools/make_board.py` | board from the netlist; outline and aux origin; J3/J6/J9/J5/J1/J2 placed and their pad positions asserted against MECHANICAL.md; pad pin functions/types set (the placer needs them); everything else off-board |
| `tools/board_setup.py` | the JLC081611-7628 stack-up (8 Cu, thicknesses and εr from §6.4); net classes: DDR3 (0.102), RGMII/SD/QSPI (0.09–0.102 inner), MDI (0.35/0.20 on F, 100 Ω), power; `kicad/zynq_card.kicad_dru` with our rules and a `User.1`-area exception for the block |
| `tools/build_pcb.sh` | runs them, then DRC; `--rebuild` as in the ground rules |

Result (`tools/build_pcb.sh --rebuild`):
- 309 footprints, 438 nets. J3 (B.Cu, 0°), J6 (B.Cu, 90°) and J9 (270°) on their MECHANICAL.md pads; J5/J1/J2 at
  their positions; everything else staged east of the board.
- **The 101 block parts take their footprint from juliancoy's board** (copied, then reset to the origin), so the
  pads under the copied copper are the source's. Only their silk text is changed (0.6/0.1 → 0.8/0.15 mm, JLC).
- Stack-up JLC081611-7628 written from a table in `board_setup.py` (1.593 mm + mask); In1/In3/In5 typed as planes.
- Net classes: `ddr3`/`ddr3_diff` 0.102/0.102, vias 0.48/0.25 (the block's only via size); `mio_fast` 0.1;
  `mdi` 0.35/0.20 (F.Cu only, 0.2 mm spacing as a track rule because the PHY pads are 0.4 mm pitch); `PWR` 0.3;
  `PWR_CORE` 0.5 (1V0, 5V0). JLC minimums: 0.09 trace/space, 0.45/0.2 via.
- **DRC: schematic parity 0.** Left: 499 unconnected (nothing is routed), 98 `lib_footprint_mismatch` (exactly the
  block parts with library footprints: they keep the KiCad 5 versions on purpose), J9's silk over the edge (the jack
  overhangs by design) and U1203's 0.1 mm reference text (the ADS7056 footprint from the Ti135 library).

## Step 2: the copper import (`tools/import_block.py`)

PLAN.md §4.2 step 2, plus what the schematic phase has added since:

1. Read `reference/zynqpcb/DFTBoard.kicad_pcb` (KiCad upgrades it on load; the legacy zone fills are dropped and
   refilled here).
2. **Select:** the block footprints by ref (the ones `tools/check_block_netlist.py` knows, minus C107); every track,
   arc and via whose net is a block net and that lies inside the block outline.
3. **Zones:** juliancoy's zones on block nets that lie inside the block (`+1V35` × 2, `DDR3_VTT`, `+1V0`, the VCCAUX
   pieces) are copied. **The board-wide zones** (GND, +1V8, +3V3, +5V, GNDA: they span the whole 117 × 58 mm source)
   are **not** copied; our planes are drawn on our outline in phase 4 and connect to the copied vias.
4. **Transform:** one rigid move + rotation (0/90/180/270°, never mirrored), taken from the pose (step 3). The
   `User.1` block outline and the two heatsink holes go with it.
5. **Nets by pad:** a copied item takes the net of the source pad it connects to, looked up as (ref, pad) on our
   board. Copper with no pad path (stitching vias, pours) is mapped by name: `+1V35` → `1V35`, `+1V0` → `1V0`,
   `+1V8` → `1V8`, `+3V3` → `3V3`, `GND` → `GND`.
6. **The REUSE_LOG copper edits, made by the import:**
   - **E7/E9:** the fan-out of the VCCO_MIO balls (+3V3 → 1V8), the VCCO_34/35 balls (GND → 3V3) and the 100
     bank 34/35 I/O balls (GND → ours / open) take the net of our ball, never the source's. Where a source via joins
     such a ball to a GND plane, the via is dropped or its plane connection removed; the script lists every one;
   - **E8:** the G10 (RSVDGND) connection is dropped;
   - **E5:** the H10 (VCCPLL) via is cut from +1V8 and gets the `VCCPLL` net; the planelet to C528 is drawn in
     phase 4;
   - **E6:** C59/C122 pads take 1V8 (by pad, automatic).
7. Write into `kicad/zynq_card.kicad_pcb`; print every item it could not map. **Expected: none.**

Check, `tools/check_block_copper.py` (new):
- per DDR net: length, layer list and via count against the source (`tools/ddr_survey.py`): **0 differences**;
- `tools/ddr3_review.py` for U16 and U15 on our board: the same numbers as `DDR3_REVIEW.md`;
- DRC with schematic parity: no unconnected item inside the block except the E5 planelet and the nets that leave
  it (rails, MIO, PL).

Then the **block edits E1 (CK trunk) and optional E2** by hand in pcbnew, checked with `ddr3_review.py` as
REUSE_LOG says. They are inside the block and do not depend on the pose, so they can wait until the pose is fixed.

## Step 3: the block pose

**Pose A, the source orientation (0°), U20 at about (164, 87): agreed by the user 2026-10-27**, subject to the quick-route comparison below.

```
 y 52  ┌──────────────────────────────────────────────────────────────┐
       │J3 ┊   ┌───── DDR3: U15  U16, VTT, termination ──┐  ┌─ J9 ───┤
       │.. ┊   │        (block, north of U20)            │  │ RJ45   ├─▶
       │.. ┊   │  ○ hole (−,−)                           │  └────────┤ y 70
 y 75  │.. ┊   │                ┌─────────┐ 500 → QSPI   │  U901 PHY │
       │J1 ┊   │           13   │   U20   │ 501 → PHY,   │  Y901     │
       │   ┊   │                │         │       eMMC   │  U1001    │
       │   ┊   │            33  └─────────┘   35         │  eMMC     │
 y 97  │   ┊   └────────────────── 34 ───────────○ (+,+)─┘           │
       │J2 ┊ ADC (bank 33)    J3 escapes → west      B.Cu: power cells│
       │      J5 ─────────────────────────────                  J6   │
 y 117 └──────────────────────────────────────────────────────────────┘
      x 131.5        x 141                     x 180               207.5
```

- Block north edge at y ≈ 53 (U20 y − 34), U20 body south edge at y ≈ 96.5, heatsink (+,+) hole at (179, 102),
  (−,−) hole at (149, 72).
- Block x ≈ 141.5…180: a 5 mm corridor west of it for the J3 signals (x 136–141), and 27 mm east of it for the
  PHY, eMMC, QSPI and oscillator, under J9 (J9 body ends at y ≈ 70).
- **Why:** the MIO side (banks 500/501) faces east, toward J9, so RGMII and MDI stay short. Bank 33 (ADC, LCD)
  faces south-west toward the ADC and J5. The DDR faces north, away from everything that is routed here. The cost
  is that bank 34 (J3) faces south, so its 32 slow 3.3 V signals run west and then north up the corridor to J3.
- This matches PLAN.md §5 phase 3.2 ("J3's signals leave the HR banks on the opposite side of the BGA from the
  DDR"); the DDR points north, not at J3.

**Alternative B, block rotated so the DDR points east** (U20 at about (152, 86)): bank 34 then faces J3 directly,
but the MIO side faces south, so the PHY sits south of the block and the MDI pairs run about 30 mm north to J9 next to
the DDR. The other two rotations put bank 34 or the MIO side on the far side from its connector.

**How it is decided** (PLAN.md §5 phase 3.2): import the block at A (two or three x/y offsets) and at B, place the
rest with the placer, and quick-route the non-block nets for each (KiCadRoutingTools, as in the Ti135 placement work).
Keep the pose with the fewest open nets and vias. **Expected: A.** The user confirms the pose before step 4 is
applied.

## Step 4: placement of the rest

| Step | Tool / by hand |
|---|---|
| 1. Placement inputs (`placement/`, ported from the Ti135 repo): J3/J6/J9/J5/J1/J2 and every block part locked; groups (power cells B.Cu, PHY, eMMC, QSPI, ADC, J3 pull-downs, translators, SoC config, our SoC decaps); the four TLV62585 cells held to the Ti135 template | `placement/prep.sh` |
| 2. Seeds, quick-route the best few, keep the best | `place_simple.py`, `judge_seeds.py` |
| 3. Apply, check courtyards, edge, keep-outs (heatsink base and holes) | `tools/apply_placement.py`, `check_assembly` |
| 4. By hand: our SoC decaps (C501–C527) on B.Cu under/around U20 without touching the block's vias; FB501/C528/C529 next to H10 (C529 within 5.1 mm); Y701 at PS_CLK; R1001 at the SD0 CLK ball; Y901 tight to the PHY; RN1301–RN1308 at J3 | pcbnew |

Placement rules:
- **Power cells on B.Cu, south and east** (y > 98 and/or x > 180), near J6 and away from the DDR. Nothing switching
  under the DDR area or within 2.5 mm of a DDR trace (In6 is 0.42 mm from B.Cu).
- **Heatsink keep-out:** no top-side part taller than the package (≈ 1.5 mm) in the 24 × 23.5 mm base area; no part
  in the Ø6 mm rings on F/B.
- **Bottom side:** every B.Cu part under 2.0 mm (WPN4020), checked against the baseboard parts below (MECHANICAL.md).
  The block's B.Cu parts (U8, termination, decaps) are included in that check.

## Gate to phase 4

- DRC (our rules) with no errors apart from unrouted nets outside the block; parity 0.
- `tools/check_block_copper.py`: 0 differences except the logged E-edits.
- `ddr3_review.py` on both DRAMs, after E1: byte 0 CK − DQS ≥ +20 ps, CK P/N ≤ 1 ps.
- Renders of F/B and each inner layer in `reports/`; the pose and the placement committed; STATUS.md updated.

## Open points for phase 3

- **The pose** (step 3): A agreed by the user (2026-10-27), to be confirmed by the quick-route score.
- **JLC quote** for the block's via sizes and 0.102/0.102 mm on 1 oz inner (STATUS.md open items): needed before
  `board_setup.py` freezes the rules.
- **Heatsink barbs** against the baseboard parts: once the pose is fixed, the two hole positions are known in the
  baseboard frame.
