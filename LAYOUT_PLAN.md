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
| Stack-up | JLC081611-7628: F · In1 GND · In2 sig · In3 GND · In4 sig · In5 GND · In6 sig · B | ZYNQ_PCB_NOTES.md §6.4; user names 1.Top, 2.GND, 3.Sig, 4.GND, 5.Sig, 6.GND, 7.Sig, 8.Bottom (`board_setup.py`) |
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

## Step 2: the copper import (`tools/import_block.py`): done 2026-10-27

`tools/build_pcb.sh --rebuild` runs make_board → board_setup → import_block, then DRC and the copper check. The
method is in the script's docstring; in short:
1. **Block parts** (the 101 that `tools/check_block_netlist.py` knows) take the source pose through one rigid
   transform (`--at`/`--rot`; default pose A) and are locked. Every pad is checked against the moved source pad.
2. **Selection by connectivity.** A geometric graph of the source copper. Copied: each copper group that touches a
   block pad (on U20 only the balls on a rail or a block net), plus pad-less rail copper (stitching), clipped to the
   block outline. Not copied: juliancoy's MIO/PL escapes, and rail copper that serves only his other parts (about 40
   of them sit inside the block area: his regulators, sensors' decaps).
3. **Nets by pad;** pad-less copper by name (`+1V0/+1V8/+1V35/+3V3` → ours, GND, DDR3_VTT, VCCAUX).
4. **The REUSE_LOG copper edits (E3, E5–E9)** are made by the import: the changed balls are detached, their own
   fan-outs re-netted or dropped, stubs pruned. Per ball: REUSE_LOG.md, "Copper import".
5. **Zones.** The plan was to copy only the zones inside the block, but **juliancoy's rails under U20 are board-wide
   pours on the signal layers** (+1V8 on In2 and In4, +3V3 on In6, with 1V0/VCCAUX islands above them). So every
   zone on a block net is copied, clipped to the block outline (11 zones). The In1/In3/In5 GND planes are copies of
   his (his 0.102 mm minimum fill width reaches the vias under the BGA; KiCad's 0.25 mm default left 12 GND vias
   unconnected) over our whole board.
6. With the block: the outline on User.1 and as rule area `ddr3_block`, H1/H2 (NPTH 3.2 mm) with their keep-outs.

**Result at pose A** (U20 at (164, 87)):
- Block outline 37.6 × 45.6 mm (from U20: x −22.1…+15.5, y −34.7…+10.9). Its north edge is 0.65 mm from the board
  edge. H1 (178.93, 101.93), H2 (149.07, 72.07).
- Copied 9,030 tracks, 463 vias, 11 zones.
- **`tools/check_block_copper.py`: 0 failures.** All 82 signal nets match the source item by item (8,709 segments,
  184 vias); the only difference is E3 (23 items).
- **`tools/ddr3_review.py`, U16 and U15:** lengths, layers and via counts identical to the source. The delays differ
  by ≤ 5 ps (via barrels now from the real stack-up). All PASS at the derated limits; byte 0 CK ≥ DQS is +2.6 ps,
  so E1 is still needed.
- **DRC: parity 0, no clearance errors.** Inherited from the source (identical copper): 14 dangling 1V35 vias (F.Cu
  only, as on juliancoy), VREF and DQS2_P stubs. The rest is unrouted nets, block-footprint library mismatches and
  silk.
- Left for phase 4: the H10 via + VCCPLL planelet (E5); 3V3 to the 12 VCCO_34/35 balls; the J3 and other escapes.
- Render: `reports/pose_a_top.png` (`kicad-cli pcb render`).

Then the **block edits E1 (CK trunk; done 2026-10-29 by `tools/block_e1.py`) and optional E2**, checked with `ddr3_review.py` as
REUSE_LOG says. They are inside the block and do not depend on the pose, so they can wait until the pose is fixed.

**`ddr3_review.py` run** (the Vivado package delays come from `vivado/pinplan/build/pkgpins.csv`, in fs; convert to a
ps CSV with columns bank, ball, site, function, min, max):
```
tools/p2k/bin/kipy tools/ddr3_review.py kicad/zynq_card.kicad_pcb --soc U20 --dram U16 --pkg work/pkg_delays_ps.csv \
    --ps-outer 5.86 --ps-outer-diff 5.86 --ps-inner 6.63 --ps-layer In6.Cu=6.80
```

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

### Pose trials (2026-10-28)

`placement/pose_trial.sh NAME X Y ROT` runs one trial in `work/pose/NAME`:
1. the block is imported onto a copper-free base board (`work/pose/base.kicad_pcb`, make_board + board_setup through
   `P2K_PCB`) at the pose;
2. our SoC decaps are dropped, since they are placed by hand and touch only rails;
3. `placement/prep.sh` runs, then `place_simple` places 6 seeds;
4. `judge_seeds` routes the best seeds with `placement/pose_chain.txt`. The chain applies the seed to the board with
   the block copper and routes the signal nets outside the block on F/In2/In4/In6/B. GND and the rails are left out
   because they become pours.

Rotation 270 puts the DDR east; rotation 90 puts the block off the board, and the import now refuses that.

Open nets of the best seed, and of the next three, with the block copper protected (`KICAD_RIP_PREEXISTING=0`,
rerun 2026-10-28). The first runs let the router rip block copper: it ripped `DDR3_DQ21` and the VRP net for RGMII
and restored them, and those scores (in brackets) were too kind to A0.

| Trial | U20, rotation | Best seed (first run) | Next three seeds | Vias / copper of the best |
|---|---|---|---|---|
| A0 | (164, 87), 0 | 35 (29) | 38, 39, 40 | 751 / 6.95 m |
| Aw | (161, 87), 0 | 32 (32) | 34, 37, 40 | 736 / 6.55 m |
| Ae | (167, 87), 0 | 26 (28) | 38, 40, 40 | 741 / 6.67 m |
| B0 | (152, 86), 270 | 37 (36) | 43, 44, 47 | 740 / 7.37 m |
| B1 | (150, 84), 270 | 43 (36) | 45, 46, 53 | 748 / 7.01 m |

- **A beats B** at the best seed and across the seeds. A0/Aw/Ae overlap within the seed spread (only Ae's best seed
  stands out).
- Seeds at 68–83 open nets with about 4.3 m of copper are routes that stopped early; they are not placements.
- Still without `KICAD_PYTHON` (the router then blocks the block pours' outlines, not their fills): the same at
  every pose.
- **Open at every pose, whatever the pose:**
  - QSPI (MIO1-6, balls A1-A4/E4/F6, the U20 row facing the DDR) is walled in by byte-0 DDR copper
    (`boxed_in_static`). juliancoy escapes these balls on F.Cu between the DDR traces to one via each and runs on
    B.Cu (8.7–17.7 mm per net). Our import dropped his MIO escapes; they are now copied (REUSE_LOG E10).
  - 3V3_analog and 5V0, which the chain does not route.
- **Kept: A0** (user, 2026-10-28), the pose the board already has; Ae (+3 mm east) is equal within the noise.

## Step 4: placement of the rest

| Step | Tool / by hand |
|---|---|
| 1. Placement inputs (`placement/`, ported from the Ti135 repo): J3/J6/J9/J5/J1/J2 and every block part locked; groups (power cells B.Cu, PHY, eMMC, QSPI, ADC, J3 pull-downs, translators, SoC config, our SoC decaps); the four TLV62585 cells held to the Ti135 template | `placement/prep.sh` |
| 2. Seeds, quick-route the best few, keep the best | `place_simple.py`, `judge_seeds.py` |
| 3. Apply, check courtyards, edge, keep-outs (heatsink base and holes) | `tools/apply_placement.py`, `check_assembly` |
| 4. By hand: our SoC decaps (C501–C527) on B.Cu under/around U20 without touching the block's vias; FB501/C528/C529 next to H10 (C529 within 5.1 mm); Y701 at PS_CLK; R1001 at the SD0 CLK ball; Y901 tight to the PHY; RN1301–RN1308 at J3 | pcbnew |

**Rough placement: done 2026-10-28** (at pose A0, before the user confirmed it):
- **Inputs, ported from the Ti135 repo** (`placement/`):
  - `groups.json`: 20 groups;
  - `sketches_B/U3x1.json`: the TLV62585 cells, from the Ti135 B.Cu templates (U301 as is, the 1-output-cap cells
    from its U331);
  - `flip_bottom.py`: the power cells to B.Cu;
  - `fix_intent.py`: keep-outs for the block rect (only the block parts and H1/H2 allowed) and Ø6 mm rings at
    H1/H2, plus the Y701 oscillator fix;
  - `prep.sh [BOARD [RUN_DIR [--drop-soc-decaps]]]`: strips the copper first (the placer refuses a routed board;
    the zones survive, unfilled). A seed goes back onto the board with its copper through
    `tools/apply_placement.py`, which never moves a locked part.
- **First pass:** 178 parts from A0's best judged seed (`work/pose/A0/wk/s4`), then C501–C529/FB501 in a second
  run with every other part locked, on B.Cu, as group `soc_decaps`. **It scattered the groups:** the intent had no
  proximity claims, so 36 Ethernet parts sat 11–65 mm from U901, two J3 arrays 70 mm from J3, the ADC chain spread
  over 30 mm.
- **Second pass (the board now):**
  1. **`tools/place_analog.py`**, ported from the Ti135 card: the ADC chain and the 3V3_analog LDO take the Ti135
     card's final positions relative to J3. That card copied the Agilex 5 card and adjusted by hand, on our outline,
     with the same circuit and J1/J2/J3/J5 at the same coordinates. 15 of 20 parts sit exactly on their Ti135 spots.
     The mux (U1201), its decap and two monitor resistors would be inside our block area, so they go to the nearest
     free spot (2.5–4.8 mm). C342 sits at the LDO output. The 8 J3 pull-down arrays go to B.Cu in a column beside J3,
     each level with its pins. These parts are locked. (`~/dev/ti60f225_control_card` is not a usable source: another
     baseboard connector, two ADC chains, no NCP163.)
  2. **A KRT re-place of the other 143 parts with proximity claims** (`placement/touchup.py`). Locked: the analog
     section, the block, the connectors, H1/H2, our SoC decaps. Each part claims the pads of the chip it serves on a
     shared non-GND net (its group's chips first, then the anchors of the groups it is `near`), 3 mm for a cap and
     5 mm for the rest, `--claim-weight 20` as on the Ti135 card. The power groups get no claims: their templates
     hold them. 6 seeds; the judge's best is s1 (`work/place2`).
  - **Result against the first pass:** claimed parts' median distance to their partner pins 11.1 → 4.0 mm, parts
    more than 1 mm past their claim 75 → 35. Farthest member from its group anchor: Ethernet 65 → 23 mm, J3 arrays
    71 → 22, supervisor 43 → 7, JTAG 18 → 7. Quick route: 68 joins needed (the first pass's A0 seeds: 58–69).
    Unmet claims are mostly the config straps, whose balls are inside the block keep-out.
- **Checks:**
  - DRC: parity 0; no courtyard, clearance or short errors. 499 unconnected (unchanged), silk overlaps 199.
    20 dangling vias: the source's 14 plus the 6 QSPI escape vias (E10), which wait for phase 4.
  - `tools/check_block_copper.py`: 0 failures. It now picks the block parts as the import does: our locked
    connectors share refs with juliancoy's parts.
  - No part off the board.
- Renders: `reports/rough_placement_top.png` / `_bottom.png`.
- **Step 4.4 fixes, done 2026-10-28** (`placement/hand_fixes.sh` → `tools/place_free.py`, ported from the Ti135
  card and made two-sided). Each part goes to the nearest spot to its target that clears the real copper on its side:
  other nets' vias (both sides), tracks, pads, courtyards, the edge, the heatsink rings. On F nothing of ours enters the
  block area; on B only U20's courtyard is open, so nothing lands under the DDR. The order is the priority. Results:
  - **VCCPLL (E5):** C529 1.9 mm from H10, FB501 3.0, C528 3.5 (B.Cu);
  - **our 0402 SoC decaps** (470 n, then 4.7 u): 0–3.1 mm from their rails' balls, under U20 between the block's
    vias;
  - **config:** C601/R609/R610 (PS_MIO_VREF) 2.6–3.6 mm from F8; R608 (PS_POR_B) 1.1 mm from B5; R611, R612, the
    MIO straps at their balls; the four QSPI straps under U801 (same nets);
  - **U801 (QSPI flash):** F, south-east of the block at (183.8, 93.9), 17.7 mm from its escape vias. The block's east
    edge is the eMMC's; north of it is the PHY's;
  - **Y901:** B.Cu, 2.5 mm from the PHY's crystal pins, load caps 1.6 mm from it (F around the PHY is full);
  - **Y701 (PS_CLK):** F just south of the block (166.5, 99.7), 16 mm from F7, with FB701/C701 at its supply and
    R701 at its output (source series). On B it would sit under the DDR;
  - **R1001 (SD0 CLK 0 R):** B, 4.1 mm from E14;
  - **bulk caps too tall for B.Cu** (330 µF tantalum 3.1 mm, 100/47 µF 1210 ≈ 2.5 mm): F at the block's south and
    east edges, 10–18 mm from their rails' balls.
  - Zones refilled: no pour has more pieces than before. DRC: parity 0, no clearance/courtyard/mask errors; block
    copper check 0 failures.
- **Silkscreen: no reference designators** (user, 2026-10-29): `tools/make_board.py` hides the Reference field and
  any `${REFERENCE}` text on F/B.SilkS (the F.Fab reference stays), `import_block.py` the same for H1/H2. The 199 silk
  overlaps are gone; left: J9's outline over the edge and its shield pads (the jack overhangs by design).
- **Copper layer user names** (user, 2026-10-29): 1.Top, 2.GND, 3.Sig, 4.GND, 5.Sig, 6.GND, 7.Sig, 8.Bottom, set by
  `board_setup.py` (LAYER_NAMES). The file keeps the standard names on items, zones and in the rule file (`'F.Cu'`
  in the DRU still matches: tested with MDI tracks), and KRT reads those; pcbnew's `GetLayerName` returns the user
  name, so `ddr3_review.py`, `check_block_copper.py` and `import_block.py` use `GetStandardLayerName`.
- `tools/build_pcb.sh --rebuild` ends with `tools/refill_zones.py`: the import fills the zones before the placement
  is put back, and a stale fill under a moved pad reads as a clearance error.
- **Bottom-side heights (2026-10-29):** `tools/check_heights.py` maps the baseboard (`~/dev/ac_psu_kicad`) into the
  card frame through J11/J12 (fit 1 um) and checks every overlapping pair of card B.Cu part and baseboard top part
  (max package heights, courtyards + 0.3 mm) against the 5.3 mm gap with 0.3 mm margin. **All pass**: C67
  (juliancoy's 100 u 1210 on 3V3, 2.7 mm max) over baseboard **U17** (Si8661 SOIC-16W, 2.65 mm) left −0.05 mm, so C67
  is now 22 u 1206 (REUSE_LOG E12, user): 0.85 mm. Tightest L331 over D1 (SMA) 0.70 mm, C28 over U12 1.15 mm. The
  heatsink push-pin **H1 lands on U17** (2.65 mm below the card); the barb goes a few mm and fits (user, 2026-10-29).
  H2 is 1.7 mm from U15. Baseboard H4 (mounting
  hole) is under the card with no card part within 5 mm; U8 and the 35 mm C12 have courtyards touching the card edge.
- **PHY area (2026-10-29):** the RX series resistors, straps and decaps sit tight around U901 (F), Y901 under it (B).
  The **TX series 22 R were at the PHY** (R902-R906; R901 alone north of it), against sheet 9 ("TX at the SoC, RX
  at the PHY"): now a column on **B.Cu at x 180.6, y 82.6-87.85**, just east of the block and west of the eMMC ball
  field (U20's TX balls are in its NE corner; no room under U20, the eMMC fills F at the block edge), in ball order.
  **R606** (MIO7 strap on `emmc_rst_n`) had gone to the eMMC's K5 ball inside its ball field (B.Cu): now on top of
  that column. Both in `placement/hand_fixes.sh`.
- **U801 fan-out (2026-10-29, `tools/fanout_u801.py`, run by `build_pcb.sh --rebuild`):** each of the 9 used balls
  (A4 `ps_por_n`, B2 SCLK, B3 GND, B4 1V8, C2 CS#, C4/D2/D3/D4 IO2/IO1/IO0/IO3) takes an F.Cu stub (0.1 mm, GND/1V8
  0.2 mm) diagonally outward to a standard **0.48/0.25 mm via between four balls**: 0.707 mm from each pad centre, so
  0.27 mm copper and 0.38 mm hole-to-pad clearance, vias 1.0 mm apart. Offsets in the footprint frame. The Agilex 5
  card (same IS25WP128, footprint and rotation, its U2) has 0.3/0.15 mm vias **in** the pads (via-in-pad, below our
  minimums, filled vias at the fab) and leaves west on In2; ours leaves west on the inner layers from between the
  balls. R601-R605 (MIO boot straps) sat on B.Cu where the vias go, and C801/R801 were 30 mm away: all now on B.Cu
  beside the via field, 0.25-1.3 mm from their balls, with `place_free.py --clear-vias` (no via inside a courtyard).
  DRC: no clearance errors; `via_dangling` 20 → 28 (the 8 vias wait for routing; the GND one is on the planes).
- **What KRT is good for here** (survey, 2026-10-28; the Ti135 card's experience agrees): coarse placement by
  function and side, the buck templates, scoring alternatives, and re-placing a few parts with the rest locked and
  claims to their pins. Not for parts among existing copper (its placer sees courtyards, not vias or tracks), not
  for layouts copied from a sibling card, and not without claims (it scatters the helpers). Its quick-route scores
  rank alternatives, but they are noisy (one pose's seeds span 26–40 open nets) and do not predict routability.
  Always run the router with `KICAD_RIP_PREEXISTING=0` and `KICAD_PYTHON=tools/p2k/bin/kipy`.

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
- `ddr3_review.py` on both DRAMs, after E1: byte 0 CK − DQS ≥ +20 ps, CK P/N ≤ 1 ps. **Met 2026-10-29: +27.5 ps,
  0.0/0.1 ps** (`tools/block_e1.py`, REUSE_LOG.md "E1 as built").
- Renders of F/B and each inner layer in `reports/`; the pose and the placement committed; STATUS.md updated.

## Open points for phase 3

- **The pose** (step 3): **A0 confirmed by the user (2026-10-28)** after the trials (A ahead of B).
- **QSPI escapes:** copy juliancoy's MIO1-6 fan-outs (F.Cu to one via) with the block; without them the QSPI balls
  cannot be routed.
- **JLC quote** for the block's via sizes and 0.102/0.102 mm on 1 oz inner (STATUS.md open items): needed before
  `board_setup.py` freezes the rules.
- ~~**Heatsink barbs** against the baseboard parts~~: H1 over U17 (2.65 mm room), H2 beside U15; the barb fits
  (user, 2026-10-29).
