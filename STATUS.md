# Status and handoff

Last updated: **2026-10-27** (phase 2 started: project skeleton and sheet 1, the imported DDR3 block, done).
Read this first if you are picking the work up (human or agent).

## What this repository is

A Linux control card for the AC lab power supply (baseboard `johonkanen/ac_psu_kicad`, locally `~/dev/ac_psu_kicad`),
built around an **AMD Zynq-7000 XC7Z020-CLG484** with **1 GB DDR3L**, Gigabit Ethernet and eMMC. It sits beside the
Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the Ti135 card (`~/dev/efinix_soc_board`), and uses the same
outline, connectors and baseboard.

**The method:** the SoC, the two DDR3L chips and their routing are **copied as a routed block** from the open-source
**juliancoy/zynqPCB** (MIT, `reference/zynqpcb`, commit `5cb7c70`). The DDR3 is not routed here. Everything else (power,
eMMC, Ethernet, QSPI, PL I/O, connectors) is designed and routed here.

| Document | Content |
|---|---|
| `PLAN.md` | the plan: source survey, block contents, transfer mechanism, phases, risks, decisions (§7) |
| `DDR3_REVIEW.md` | UG933 review of the candidate DDR3 blocks. pinguz97 rejected (wrong byte lanes, VRP/VRN swapped); juliancoy checked on our stack-up |
| `REUSE_LOG.md` | every change to the copied block: E1–E4 are planned, to be made after the import |
| `ZYNQ_PCB_NOTES.md` | Zynq-7000 rules: supplies, decoupling, sequencing, PS_POR_B, boot straps, MIO plan (§4.3), PL pin plan (§4.4), config pins, DDR3 rules, stack-up (§6.4), PS7 DDR settings, required resistors |
| `POWER_BUDGET.md` | rail currents (Vivado `report_power`), 4 × TLV62585 + TPS51200, thermal, heatsink |
| `MECHANICAL.md` | outline, J3/J6/J9/J5/J1/J2 positions (copied from the Ti135 repo) |
| `NOTICE`, `LICENSE` | MIT; juliancoy's MIT notice for the copied block |
| `vivado/pinplan/` | Vivado pin plan and power: `pinplan.py`, `ps7.tcl`, `signals.csv`, `groups.csv`, `mio.csv`; results `zynq_pinplan.csv`, `ps7_mio.csv`, `power_summary.csv` |
| `reference/` | `zynqpcb/` (the block source, submodule), `baseboard_j11_pinout.csv` (the J3 authority), `stackup_scan_0p102mm.txt`, `vendor/README.md` (Xilinx PDFs to fetch; not in git) |
| `tools/` | `ddr3_review.py`, `stackup_scan.py`, `zsolve.py`/`zsolve_cases.py`, `ddr_survey.py`; submodules `jlc/` and `p2k/` |

## Decisions (do not reopen without the user)

| Item | Decision |
|---|---|
| SoC | **XC7Z020-1CLG484I or -2CLG484I**, whichever JLC stocks at order time (C89055 / C157624). 200 PL HR I/O, all at 3.3 V |
| Block source | **juliancoy/zynqPCB** (MIT), SoC + DDR3 only. pinguz97/Zynq-SoM rejected by the UG933 review |
| Memory | **1 GB DDR3L, 2 × MT41K256M16TW-107:P** (C253882) on juliancoy's HA land; 32-bit, 533 MHz |
| Licence | **MIT** |
| eMMC / Ethernet / QSPI | **designed and routed here, not copied.** KIOXIA THGAMVG7T13BAIL (SD0, 4-bit), RTL8211F(DI)-CG (GEM0 RGMII), ISSI IS25WP128-RHLE (shared parts with the other cards) |
| MIO banks | **both at 1.8 V** (MIO7/MIO8 pulled up); PS_CLK 33.333 MHz 1.8 V oscillator |
| Console | **PS UART1 on MIO48/49 + a 2-bit translator** to the 3.3 V J2 |
| ADC | ADS7056 DVDD at **3.3 V** (SPI straight to the 3.3 V bank) |
| Boot | **QSPI boot** (the BootROM cannot boot from eMMC); Linux on eMMC; JTAG for recovery |
| Stack-up | **JLC081611-7628**, 1.6 mm, 1 oz inner. GND on In1/In3/In5, signals on F/In2/In4/In6 (juliancoy's roles). 0.102 mm = 39.5 Ω on In2/In4, 45.5 Ω on In6; F/B are poor impedance layers (fan-out, power, slow signals; MDI pairs 0.35/0.20 mm on F.Cu = 102 Ω) |
| Thermal | ambient 40 °C worst case. **Heatsink required: Wakefield-Vette 960-23-33-D-AB-0** (diagonal push pins), NPTH Ø3.2 mm at ±14.93 mm on the block diagonal that is free of block copper |
| Power | 5V_ISOL from J6. 0.89 A typical / 1.44 A high, so it relies on the baseboard U8 upgrade to 1.5–2 A (decided in the Ti135 work). 4 × TLV62585 (1V0, 1V8, 1V35, 3V3) + the block's TPS51200 (VTT) + NCP163 (3V3_analog) |
| Outline, J3/J6/J9/J5 | as the other cards (`MECHANICAL.md`); J3/J6 bottom-side sockets numbered like the baseboard |
| J3 safe state | PUDC_B (K16) tied to VCCO_34 + 10 k pull-downs on every J3 pin |

## Where we left off

**Phase 0 (decisions and checks): done.** See PLAN.md §5, phase 0.
- DDR3 block review, stack-up choice, the Vivado pin plan (DRC 0), the power budget and thermal.
- What is still open from phase 0 is listed under *Open items*.

**Phase 1 (repository): done.**
- Submodules `tools/jlc`, `tools/p2k` and `reference/zynqpcb`.
- `MECHANICAL.md` and the baseboard pinout copied from the Ti135 repo.

**Phase 2, the schematic: in progress.**
- **Done: the project and sheet 1.** `p2k_config.py` (project `zynq_card`, 13 sheets), `kicad/` from `p2k make_skeleton`,
  `lib/zynq_card.kicad_sym` from `tools/gen_symbols.py`, `tools/sync_root.py` and `tools/sheets/_common.py` (both copied
  from the Ti135 repo), and `tools/build_schematic.sh`, which rebuilds everything and runs ERC plus the block check.
- **Sheet 1 `01_ddr3` is the imported block** (`tools/sheets/01_ddr3.py`).
  - KiCad 10 cannot save a legacy `.sch` from the CLI: `kicad-cli sch upgrade` fails on save, and the netlist export
    finds 0 symbols. So the script converts juliancoy's `DDR3.sch` itself, at the source coordinates: refs come from
    the AR line of `/58818A06/`, and wires, labels and notes are copied 1:1.
  - The symbols come from `DFTBoard-cache.lib`, upgraded with `kicad-cli sym upgrade`; the XC7Z020 symbol has all 9
    units. The pin positions of each placed unit are checked against the KiCad 5 symbol. Rails: `+1V35` → `1V35`,
    `+3V3` → `3V3`.
  - 62 parts: U20 unit 8 (bank 502), U15, U16, U8, R46–R76, R25, R101, R102, D7 (PGOOD LED), C93–C110, C125–C131.
  - E3 and E4 are made in the schematic (REUSE_LOG).
  - **`tools/check_block_netlist.py`: 0 failures.** It covers 393 pads and 84 nets, 72 of them `DDR3_*`. Every pad has
    the net it has on `DFTBoard.kicad_pcb`, by pad sets and by name, and every footprint matches.
  - ERC shows only what is expected now: the rails and `DDR3_VTT_EN` are undriven, and U20 units 1–7 and 9 are not
    placed yet.
- **Next:**
  1. **The U20 power unit (9) and the SoC decaps.** juliancoy's `power.sch` holds U20 units 1 and 9 and the SoC decaps
     that are inside the block copper. Keep the decap refs (< 200) when drawing sheet 5 `soc_power`, so the copper
     import can map them. Extend `01_ddr3.py`'s converter, or the check, to cover them.
  2. **Draw the new sheets:**
     - power input (J6);
     - TLV62585 rails (cells from the Ti135 repo's `_power.py`);
     - power sequencing + PS_POR_B supervisor, which also drives `DDR3_VTT_EN` (E3);
     - SoC power/decoupling (UG933 Tables 3-1/3-2);
     - clocks;
     - boot straps and configuration (`ZYNQ_PCB_NOTES.md` §4–5, §7);
     - QSPI;
     - eMMC;
     - Ethernet (from the Ti135 sheet 09);
     - PL I/O (from `vivado/pinplan/zynq_pinplan.csv`);
     - ADC (from the Ti135 sheet 13, DVDD at 3V3);
     - connectors (J3 + pull-downs, J5, J2 + translator, J1 JTAG, J9).

     The sheet numbers are in `p2k_config.py`.
  3. ERC, then a netlist check that every PL/MIO signal lands on the ball from the pin plan.

**Suggested way to work on phase 2:**
- **Script the sheets like the Ti135 repo** (`efinix_soc_board/tools/sheets/NN_*.py` + `_common.py`, with
  `tools/p2k`): one script per sheet, rebuilt from scratch.
- **Draw the first sheet in this session to fix the pattern.** Then independent sheets can be drawn by parallel agents,
  each in its own git worktree, with one session merging and running ERC.

**Conventions (from the Ti135 repo, plus the block):**
- No global labels in our own sheets: sheets connect through hierarchical labels on the root. Rails only through power
  symbols. Signal nets in lower snake_case; active low ends in `_n`; differential pairs end in `_P`/`_N`.
- **The block keeps juliancoy's names and refs:** all of them are below 200 (R ≤ 106, C ≤ 131, U ≤ 23).
- **Our references use sheet number × 100, starting at sheet 2** (R201…, U1201…), so they never collide with the
  block's.
- Baseboard/user connectors keep their family names: J1 JTAG, J2 UART, J3 baseboard J11, J5 LCD, J6 baseboard J12,
  J9 RJ45.
- Hidden power pins become passive, as in the Ti135 symbols.

## Open items

- [ ] **Block edits after the import** (`REUSE_LOG.md`):
  - E1: CK_P +4.30 mm, CK_N +3.23 mm in the trunk, giving CK = DQS0 + 25 ps and CK P/N matched;
  - E2 (optional): match the DQS3 pair;
  - E3: TPS51200 EN;
  - E4: the DRAM part swap.

  Then re-run `tools/ddr3_review.py` for both DRAMs.
- [ ] **[verify] items:**
  - `ZYNQ_PCB_NOTES.md` §8: UG470 PROGRAM_B/INIT_B/DONE values, XADC tie-off, the PS_POR_B lockdown window, the
    RTL8211F INTB level, IS25WP128 support in `program_flash`/U-Boot;
  - `POWER_BUDGET.md`: the DDR3L/eMMC/QSPI currents.
- [ ] **Heatsink:** the push-pin grip range for 1.6 mm board + package + tape, and the barb protrusion against the
      5.3 mm card-to-baseboard gap.
- [ ] **JLC quote:** the JLC081611-7628 surcharge, 1 oz inner minimum width/space (the block needs 0.102/0.102 mm), and
      the block's via sizes.
- [ ] **The DDR3L temperature grade:** standard 0…95 °C (C253882) or IT −40…95 °C (C367428).
- [ ] **Baseboard U8 upgrade to 1.5–2 A:** confirm it in the `ac_psu_kicad` redraw.
- [ ] Optional: report pinguz97's two DDR faults on its issue #3 (public; ask the user first).

## How to run the tools

```
git submodule update --init
source tools/p2k/bin/kicad_env.sh        # KiCad 10.0.7 AppImage (~/kicad/kicad-10.0.7-x86_64.AppImage): kicad-cli, kipy

# DDR3 die-to-die review of a board (JLC081611-7628 speeds, Xilinx package delays)
tools/p2k/bin/kipy tools/ddr3_review.py BOARD.kicad_pcb --soc U20 --dram U16 \
    --pkg <xc7z020clg484 package-delay CSV> --ps-outer 5.86 --ps-outer-diff 5.86 --ps-inner 6.63 --ps-layer SIGNAL4=6.80

# stack-up impedance scan (JLC templates from gsuberland/jlcpcb_autogenerated_stackups)
python3 tools/stackup_scan.py --w 0.102 --gap 0.102 <templates>.kicad_pcb

# Vivado pin plan + DRC, then power (Vivado 2024.2; no license needed for the 7Z020)
python3 vivado/pinplan/pinplan.py
cd vivado/pinplan/build && vivado -mode batch -source ../power.tcl
```

Notes:
- **Vivado 2026.1 does not start:** its node-locked license (`~/.Xilinx/Vivado_2026_basic_00155daf6690.lic`) names
  MAC `00:15:5d:af:66:90`, and WSL2 now has `…:6e:fc`. Use `~/Xilinx/2024.2/Vivado/2024.2`, or re-host the license.
- **Xilinx PDFs** (UG933, DS187, UG865) are fetched from the docs.amd.com API (`reference/vendor/README.md`) and are not
  in git. UG585 (the TRM) is HTML only; the topics used are named in `ZYNQ_PCB_NOTES.md` §Sources.
- **The package-delay CSV:** pinguz97's `scripts/xc7z020clg484_delays.csv` was used; the same data comes from
  `vivado/pinplan/build/pkgpins.csv` (MIN/MAX_DELAY per ball) after `pinplan.py`.

## Related sessions and repositories

- `~/dev/agilex3_soc_control_card` (Agilex 5 card), session `agilex3-soc-control-card-d4`: **do not modify from
  here**; send notes to its session (user rule). On 2026-10-27 it was told that its heatsink holes are 3.0 mm, but the
  Wakefield pins need Ø3.18 mm.
- `~/dev/efinix_soc_board` (Ti135 card), session `efinix-soc-board-da`: the source of `MECHANICAL.md`, the baseboard
  pinout, the TLV62585 cells, the Ethernet and ADC sheets, and the sheet-script framework.
- `~/dev/ac_psu_kicad` (baseboard), session `ac-psu-kicad-73`: J11/J12 pinout authority; the U8 upgrade.
