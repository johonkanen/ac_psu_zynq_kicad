# Status and handoff

Last updated: **2026-10-28** (phase 3: pose trials (step 3) and a rough placement of every part (step 4) at pose A0.
Before that, phase 3 steps 1–2: board, rules, and the block copper imported (2026-10-27). Before that, phase 2: project skeleton, sheets 1 (the imported DDR3 block), 2–4 (power input, rails, sequencing), 5 (SoC power), 6 (SoC config), 7 (clocks), 8–10 (QSPI, Ethernet, eMMC), 11 (PL banks), 12 (ADC) and 13 (connectors) done: **the schematic is complete**).
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
| `LAYOUT_PLAN.md` | phase 3: board setup, the block copper import, the block pose (A recommended), placement |
| `MECHANICAL.md` | outline, J3/J6/J9/J5/J1/J2 positions (copied from the Ti135 repo) |
| `NOTICE`, `LICENSE` | MIT; juliancoy's MIT notice for the copied block |
| `vivado/pinplan/` | Vivado pin plan and power: `pinplan.py`, `ps7.tcl`, `signals.csv`, `groups.csv`, `mio.csv`; results `zynq_pinplan.csv`, `ps7_mio.csv`, `power_summary.csv` |
| `reference/` | `zynqpcb/` (the block source, submodule), `baseboard_j11_pinout.csv` (the J3 authority), `stackup_scan_0p102mm.txt`, `vendor/README.md` (Xilinx PDFs to fetch; not in git) |
| `placement/` | placement inputs (KiCadRoutingTools): `groups.json`, `sketches_B/`, `flip_bottom.py`, `fix_intent.py`, `prep.sh`, `intent.json`, `touchup.py` (lock + proximity claims), `hand_fixes.sh` (step 4.4); pose trials `pose_trial.sh` + `pose_chain.txt` (LAYOUT_PLAN.md steps 3–4) |
| `tools/` | board: `make_board.py`, `board_setup.py`, `import_block.py`, `check_block_copper.py`, `apply_placement.py`, `place_analog.py`, `place_free.py`, `refill_zones.py`, `block_e1.py`, `build_pcb.sh`; `ddr3_review.py`, `stackup_scan.py`, `zsolve.py`/`zsolve_cases.py`, `ddr_survey.py`; submodules `jlc/` and `p2k/` |

## Decisions (do not reopen without the user)

| Item | Decision |
|---|---|
| SoC | **XC7Z020-1CLG484I or -2CLG484I**, whichever JLC stocks at order time (C89055 / C157624). 200 PL HR I/O, all at 3.3 V |
| Block source | **juliancoy/zynqPCB** (MIT), SoC + DDR3 only. pinguz97/Zynq-SoM rejected by the UG933 review |
| Memory | **1 GB DDR3L, 2 × MT41K256M16TW-107:P** (C253882) on juliancoy's HA land; 32-bit, 533 MHz |
| Licence | **MIT** |
| eMMC / Ethernet / QSPI | **designed and routed here, not copied.** KIOXIA THGAMVG7T13BAIL (SD0, 4-bit), RTL8211F(DI)-CG (GEM0 RGMII), ISSI IS25WP128-RHLE (shared parts with the other cards) |
| MIO banks | **both at 1.8 V** (MIO7/MIO8 pulled up); PS_CLK 33.333 MHz 1.8 V oscillator |
| Bank 0 (config/JTAG) | **1.8 V, as on juliancoy** (2026-10-27): CFGBVS to GND, JTAG J1 at 1.8 V; the block copper for VCCO_0/RSVDVCC/R9/R10 stays |
| VCCPLL | **own 120 Ω bead FB501 + 10 µF + 0.47 µF** from 1V8 (UG933 must; juliancoy had it on raw +1V8). juliancoy's VCCAUX bead FB1 becomes a **0 Ω jumper** (2026-10-27, REUSE_LOG E5) |
| Console | **PS UART1 on MIO48/49 + a translator with per-bit direction** to the 3.3 V J2 (not an LVC2T45) |
| JTAG | **J1 1×5 at 3.3 V** for FTDI mini-modules (no VREF), shifted to bank 0 by SN74AVC4T774RSVR (C779392), as on the Agilex 3 card (`~/dev/ti60f225_control_card`) |
| RSVDGND | **open** per UG865 v1.9 (REUSE_LOG E8) |
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

**Phase 2, the schematic: done** (2026-10-27; closing check below).
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
- **Sheet 5 `05_soc_power`: U20 unit 9 and the SoC decoupling** (`tools/sheets/05_soc_power.py`).
  - The legacy converter is now shared: `tools/sheets/_legacy.py`. `convert(keep=...)` takes a subset of a source
    sheet and prunes the wires, labels and power symbols that no longer reach a kept pin. `cut=` drops source wires
    for a re-wire, and mirrored symbols are supported. Sheet 1 regenerates byte-identical through it.
  - From juliancoy's `power.sch` (`/58508414/`): U20 unit 9 and the 21 decaps in the block copper (footprint within
    4 mm of the U20 body: C4, C5, C8, C9, C11, C14, C15, C17–C20, C23, C24, C26, C28–C31, C33, C34, FB1), at the source
    coordinates. juliancoy's regulators, LM3880 sequencers, sense resistors and their bulk caps are dropped.
  - Also in the block, with source refs: the 16 3V3 caps under U20 that juliancoy drew on other sheets (C46…C122;
    REUSE_LOG).
  - Ours: FB501 + C528/C529 (VCCPLL, E5), and C501–C527, which bring each merged rail up to UG933 Tables 3-1/3-2
    (CLG484 Z-7020; the count is a note on the sheet). That is 330 µF tantalum + 100 µF + 2 × 4.7 µF + 3 × 0.47 µF on
    1V0, 3 × 100 µF + 2 × 47 µF on 1V8, 3 × 0.47 µF on 1V35, and 3 × 4.7 µF + 3 × 0.47 µF each for VCCO_34 and
    VCCO_35. Banks 34/35 had VCCO on GND on juliancoy, so they have no caps in the block.
  - Block changes: E5 (VCCPLL), E6 (C59/C122 → 1V8 for the MIO banks), E7 (planned, copper: VCCO_MIO balls
    +3V3 → 1V8, VCCO_34/35 balls GND → 3V3).
  - **`tools/check_block_netlist.py` covers sheets 1 and 5: 0 failures.** That is 99 parts, 555 pads (172 U20 balls)
    and 87 nets. Block parts on our sheets are refs < 200. Rails map +1V0/+1V8/+1V35/+3V3 → ours, and /Power/ → our
    sheet path. U20.H10, C59.1 and C122.1 are reported as expected differences.
  - ERC: only the not-yet-drawn items. (The undriven rails and `DDR3_VTT_EN` were closed by sheets 2–4.)
  - The VCCO pins are on the bank units (sheets 6, 11). Their caps are on sheet 5 as rail rows.
- **Vivado pin plan** re-run with `CFGBVS GND` / `CONFIG_VOLTAGE 1.8`: DRC 0, no critical warnings, pin plan
  unchanged.
- **Sheet 6 `06_soc_config`** (`tools/sheets/06_soc_config.py`): U20 units 1 (bank 0), 6 and 7 (MIO banks 500/501), and the
  following parts:
  - boot straps R601–R607 (20 k; QSPI boot, JTAG cascaded, PLLs on, VMODE 1.8/1.8);
  - PS_POR_B pull-up R608. The supervisor's open-drain output (sheet 4) drives the `ps_por_n` port;
  - PS_MIO_VREF divider R609/R610 + C601 (with a PWR_FLAG) and the PS_SRST_B pull-up R611;
  - juliancoy's R9/R10 (PROGRAM_B/INIT_B, block refs, source pads) and DONE 330 Ω R612 **[verify UG470]**;
  - J1 (1×5 family pinout, 3.3 V) → U601 SN74AVC4T774RSVR → bank 0, with R613–R616 and C602/C603: the Agilex 3
    card's circuit;
  - RSVDGND open (E8). XADC and bank-0 tie-offs as on the source.
  - **Sheet ports for the other sheets** (they must use these names):
    - `ps_clk` (sheet 7), `ps_por_n` (sheet 4);
    - `qspi_cs_n`, `qspi_sclk`, `qspi_io0`–`3` (sheet 8);
    - `rgmii_txc`, `rgmii_txd0`–`3`, `rgmii_tx_ctl`, `rgmii_rxc`, `rgmii_rxd0`–`3`, `rgmii_rx_ctl`, `mdc`, `mdio`,
      `eth_rst_n`, `eth_int_n` (sheet 9);
    - `sd_clk`, `sd_cmd`, `sd_dat0`–`3`, `emmc_rst_n` (sheet 10);
    - `uart_tx`, `uart_rx` (J2 translator), `i2c_scl`, `i2c_sda`.

    Their pulls go with the parts: eth_int_n, MDIO and I2C pull-ups to 1V8; the SD0 CLK 0 Ω series at the MIO pin.
  - Block check: sheet 6 is in `SHEETS`. On its U20 units only the rail/GND balls and the balls on a block part's net
    are compared; the MIO/JTAG signal balls are ours. J-refs are never block parts. Result: **0 failures** (101 parts,
    583 pads, 196 U20 balls). The expected differences are E3 (B6), E5, E6, E7 (the VCCO_MIO balls) and E8 (G10).
  - New ERC entries, all for sheets not drawn yet:
    - `isolated_pin_label` for the ports that have one pin so far;
    - `label_dangling` on the root for the strapped ports;
    - `pin_not_driven` on PS_CLK.
- **Sheet 7 `07_clocks`** (`tools/sheets/07_clocks.py`): the 33.333 MHz PS_CLK oscillator.
  - Y701 YXC OT322533.3333MJBA4SL (C2831392, 1.8–3.3 V CMOS, 3225, ±20 ppm), from the Agilex 3 card's OT3225 family.
  - The circuit is that card's: EN tied to VDD, supply through FB701 BLM18PG121SN1D (C14709, basic) + C701 470 nF,
    and R701 33 Ω source-series to the `ps_clk` port.
  - The PL has no clock input; the PHY's 25 MHz crystal goes on sheet 9.
- **Sheets 2–4, power** (`tools/sheets/02_pwr_input.py`, `03_pwr_rails.py`, `04_pwr_seq.py`, cell `_power.py`), ported from
  the Ti135 sheets 01/03/04 and its TLV62585 cell. Symbols added to `tools/gen_symbols.py`: TLV62585PDRL (Ti135 box),
  NCP163, TPS3808DBV (~RESET made open drain), L_Power, Conn_02x03, power symbols 5V0 and 3V3_analog.
  - **Sheet 2:** J6 (pins 1/3/5 GND = ISOGND, 2/4/6 5V0 = 5V_ISOL), PWR_FLAGs on 5V0 and GND, bulk C201 47 µF 1206,
    C202 22 µF, C203 100 nF. The Ti135 card has no other input protection, so none is added.
  - **Sheet 3:** U301 1V0 (R1 66.5 k, 2 × 22 µF out), U311 1V8 (200 k), U321 3V3 (453 k), U331 1V35 (124 k): 10 µF in,
    WPN4020H1R0MT 1 µH, 22 p feed-forward, PWR_FLAG on each rail. Load vs 3 A: 1V0 2.40 A high (80 %), the rest
    ≤ 0.97 A. U341 NCP163 → 3V3_analog (from 5V0, always on).
  - **Sheet 4:** R401/R402 100 k to 5V0 on `pg_1v0` (EN of 1V8) and `pg_1v8` (EN of 3V3 and 1V35).
    PG(3V3) & PG(1V35) is wired onto `DDR3_VTT_EN` (pull-up = R25 on sheet 1), which also feeds U401 TPS3808G01 ~MR.
    U401: VDD 1V8, SENSE = 1V0 through R403 121 k / R404 100 k (0.895 V, the power-off eFUSE rule), CT = VDD
    (300 ms, 180–420 ms), open-drain RESET → `ps_por_n` (R608 on sheet 6).
  - **The PS_POR_B lockdown [verify] is closed** (DS187 v1.21 Table 23, now in `reference/vendor/`): the release is
    180–425 ms after 1V8 (the last of VCCINT/VCCBRAM/VCCAUX/VCCO_0), outside every T_SLW range. The Ti135 value,
    CT open (12–28 ms), would fall inside the eFUSE-CRC and PLL-bypass windows. `ZYNQ_PCB_NOTES.md` §3 updated.
  - ERC: the `power_pin_not_driven` errors are gone; sheets 2–4 have no ERC entries. Block check still 0 failures.
  - To check at layout or on the bench:
    - the TLV62585 is specified for 10–47 µF out, and every rail carries hundreds of µF (sheet 5). The Ti135 cell
      handles this with the 22 p feed-forward cap; check the loop on the first board (load step);
    - 1V0 at 2.4 A in a SOT-563 needs copper for heat;
    - LCSC numbers for U341 and U401 are not set yet (the Ti135 sheets have none either).
- **Sheets 8–10, the MIO peripherals** (`tools/sheets/08_qspi.py`, `09_ethernet.py`, `10_emmc.py`), ported from
  the Ti135 card. Its symbols are now in `tools/gen_symbols.py`: IS25WP128-RHLE, RTL8211FD, HR911130A,
  THGAMVG7T13BAIL, plus Crystal_GND24 and 74LVC1G07. Its two custom footprints (the CSP-24 flash land and the
  HR911130A) are copied into `lib/zynq_card.pretty`, which has a new `fp-lib-table` entry. Every part's footprint
  is set on the sheet: `fill_footprints()` in `_common.py` fills R/C/etc. by symbol and fails on a part without
  one.
  - Every port uses the sheet-6 name. A netlist export confirms each one lands on the right U20 ball (the
    symbol's balls match Vivado's `pkgpins.csv` and `ps7_mio.csv`).
  - **Sheet 8:** U801 IS25WP128-RHLE (C1349419) on 1V8, C801 100 n.
    - R801 10 k is the CS# pull-up.
    - The boot straps on IO0–3/SCLK stay on sheet 6. WP# is strapped low, which is harmless while SRWD = 0;
      HOLD# is high.
    - **RESET# (A4) is on `ps_por_n`**, so the flash resets with the PS. This is our choice; the Ti135 card only
      pulled it up. It is open drain, and R608 is the pull-up.
    - The ball map (A4 RESET#, B2 SCLK, C2 CS#, D3/D2/C4/D4 IO0–3, B4/B3 VCC/GND) is the one checked against the
      ISSI data sheet on the Agilex 5 card (`SHARED_PARTS.md`). The ISSI PDF could not be fetched here (bot check).
  - **Sheet 9:** the Ti135 sheet with its refs and values (U901 RTL8211FDI-CG, U902 74LVC1G07, Y901 25 MHz,
    J9 HR911130A, R901–R933, R950, C901–C951). Checked against the RTL8211F data sheet Rev. 1.7:
    - **RGMII level:** CFG_EXT = 0 and CFG_LDO = 10 run the RGMII and MDIO pads from the internal LDO at 1.8 V, so
      DVDD_RG is caps only. This matches both 1.8 V MIO banks. Table 58: MDIO is at the pad voltage, and every
      other pin is 3.3 V.
    - **INTB [verify] closed:** pin 31 is O/OD ("supports 3.3 V pull-up"). So R930 4k7 goes to 1V8, and
      Vol 0.4 V is below the MIO VIL of 0.63 V.
    - **R933 is 1 k (Ti135: 10 k):** the MIO9 pull-up is on at reset (DS187 IRPU up to 220 µA at 1.8 V). 10 k
      would leave `eth_rst_n` near 1 V. 1 k keeps it at ≤ 0.22 V, so the PHY stays in reset until software
      releases it.
    - Port renames: `eth_mdc`/`eth_mdio` → `mdc`/`mdio`.
    - The J9 pinout was re-checked against the HanRun drawing.
  - **Sheet 10:** U1001 THGAMVG7T13BAIL (C7599693) on SD0, 4-bit.
    - VCC 3V3 (C1001 4u7 + C1002 220n), VCCQ 1V8 (C1003 4u7 + C1004 100n), VDDi C1005 2u2: the KIOXIA values
      from the Agilex 5 card's `SHARED_PARTS.md`.
    - 47 k pull-ups on CMD and DAT0–7 (DAT4–7 are unused but not left floating), and a 47 k pull-down on DS.
    - The RST_n pull-up is the MIO7 VMODE strap (R606, sheet 6).
    - R1001 is the 0 R on `sd_clk` at the MIO pin.
  - Parts without an LCSC number yet: Y901 (25 MHz 3225) and FB901 (BLM15PX121SN1D), as on the Ti135 card.
  - **ERC:** the `isolated_pin_label`/`label_dangling` entries for these ports are gone. What is left is expected:
    - `isolated_pin_label` × 8: `uart_tx`/`uart_rx` and `i2c_scl`/`i2c_sda` (label and port each). Their sheets
      are not drawn yet (J2 translator on sheet 13; the I²C EEPROM).
    - `missing_unit`, `missing_power_pin` and `missing_bidi_pin` on U20: the PL bank units, sheet 11.

    Block check: 0 failures. kicad-cli's "annotation errors" warning on the netlist export is from before this
    change.
- **Sheet 11 `11_soc_pl`** (`tools/sheets/11_soc_pl.py`): U20 units 2–5 (PL banks 34, 33, 35, 13), all VCCO on 3V3.
  All nine U20 units are now placed.
  - **Labels:** one hierarchical label per pin-plan signal, named as in `zynq_pinplan.csv`. The script asserts each
    ball's bank and pin function against the symbol. Unused balls get a no-connect flag.
  - **Bank 34:** the 32 J3 ports. **PUDC_B (K16) is tied straight to 3V3 (VCCO_34)**, and the J3 pull-downs go on
    sheet 13.
  - **Bank 33:** the ADC ports (sheet 12) and the LCD/touch ports (sheet 13). The user LEDs are on this sheet:
    D1101/D1102 red 0603 with R1101/R1102 1 k to 3V3, active low.
  - **Banks 13 and 35:** spare.
  - U20's footprint is set on these units too (the block's BGA-484, as on sheets 1 and 5).
  - **New block change E9 (copper planned):** juliancoy ties every I/O ball of banks 34 and 35 to GND, along with
    their VCCO (UG933: an unused bank on one potential). With VCCO at 3V3 (E7), those 100 balls carry our nets or
    stay open. Their GND vias must be dropped at the import.
  - **Block check:** sheet 11 is in `SHEETS`. The VCCO_34/35 balls (E7) and the bank 34/35 I/O balls (E9) are
    generated into EXPECTED from the symbol, and a whole bank is reported on one line. VCCO_13/33 match the source's
    +3V3. Result: **0 failures** (101 parts, 709 pads, 322 U20 balls).
  - **ERC, all expected:**
    - `isolated_pin_label` × 108: the ADC, LCD/touch and J3 ports (sheets 12/13), plus UART/I²C as before;
    - `pin_to_pin` × 1: PUDC_B, a bidirectional pin, on the 3V3 rail with its PWR_FLAG. This is the intended tie.

    The U20 `missing_unit` entries are gone.
- **Sheet 12 `12_adc`** (`tools/sheets/12_adc.py`): the Ti135 sheet 13 with its parts and symbols, refs renumbered
  to 12xx. The ADS7056 symbol comes from the Ti135 library (`from_ti135()` in `tools/gen_symbols.py`), and its
  footprint is copied into `lib/zynq_card.pretty`.
  - **U1201 SN74LV4051APWR (C7793)**, on the CD4051B symbol as on the Ti135 card. Checked against TI SCLS428K: it has
    the same 4051 pinout, pins 7 and 8 are both GND (the symbol's VEE pin goes to GND), and VIH = 0.7 VCC = 2.31 V
    at 3.3 V (5.5 V tolerant). So the pin plan's part is right, and `adbsel0`–`2` come straight from bank 33 (the
    Ti135 card needed translators). INH to GND, X0 = GND.
  - U1202 OPA365AIDBVR, 33 R + 680 p C0G kickback RC, **U1203 ADS7056IRUGR: AVDD 3V3_analog (U341), DVDD 3V3**
    (SBAS769: DVDD 1.65–3.6 V, independent of AVDD; pin map checked). 33 R series on CS/SCLK/SDO.
  - Rail monitors: X1 1V0 (100 R), X2 1V8, X3 3V3/2 (1k/1k), X5 1V35; these were VCORE/1V8/3V3/1V1 on the Ti135
    card. X4/X6/X7 = `isoada2`/`3`/`1` from J3.
  - Ports: `adc_cs_n`, `adc_sclk`, `adc_sdo`, `adbsel0`–`2` (sheet 11), `isoada1`–`3` (sheet 13).
- **Sheet 13 `13_connectors`** (`tools/sheets/13_connectors.py`), from the Ti135 sheet 14. The Ti135 level-shift
  sheet is not needed (bank 34 is 3.3 V).
  - **J3** (2×19 1.27 mm socket, bottom): pin n = baseboard J11 pin n from `reference/baseboard_j11_pinout.csv`.
    The script asserts, for each digital pin, that the net is the sheet-11 name and that the pin plan's note says
    `J3.<n>` with the same direction. All 32 match.
    - RN1301–RN1308: 4D02WGJ0103TCE (4 × 10 k, C25725) pull-downs on all 32 digital pins (the J3 safe state).
    - ISOADA1–3 (pins 4/3/1) go to the mux unpulled (a pull-down would load the analog source). ISOGND = GND;
      pin 38 NC.
  - **J5:** the Ti135 1×14 pinout, `lcd_*`/`t_*` from bank 33.
  - **J2:** family pinout 1 RX, 2 TX, 3 GND, with R1301/R1302 1 k series as on the Ti135 card.
    - U1301 SN74AVC4T774RSVR (C779392): A = J2 at 3V3, B = MIO at 1V8. DIR1 = H (J2 RX → `uart_rx`), DIR2 = L
      (`uart_tx` → J2 TX).
    - Bits 3/4 are unused: DIR H, A3/A4 to GND, B3/B4 open. OE to GND. C1301/C1302 are 100 n.
    - R1303 10 k pulls the J2 RX side high (idle with nothing plugged in). R1304 10 k pulls `uart_tx` to 1V8 (B2 stays
      defined while MIO48 is tri-stated).
  - **I2C0:** R1305/R1306 4.7 k to 1V8. **No device on the bus:** no MAC-address EEPROM for now (user, 2026-10-27). The UG933 RC glitch filters are not drawn either.
  - `vivado/pinplan/mio.csv` MIO48 note corrected: SN74LVC2T45 → SN74AVC4T774 (a note only, no pin change).
- **Closing check, `tools/check_pinplan_netlist.py`** (new, run by `build_schematic.sh` after the block check). It
  reads the exported netlist:
  - every pin-plan signal (52) must be on its ball (`zynq_pinplan.csv`), with its own net name, and reach its far end
    (J3.n from the note column, J5.n, the ADC parts, the LEDs);
  - every MIO signal (34) must be on its ball (MIO → ball from the symbol pin names, with the peripheral checked
    against `ps7_mio.csv`), reaching its part (flash, PHY, eMMC, translators, pulls);
  - the 20 spare MIO must be open.

  **Result: 0 failures.** A negative test (swapped expectations) gives 3 failures, as it should.
- **ERC: 0 errors, 4 warnings, all `pin_to_pin` (bidirectional pin on a rail with a PWR_FLAG), all intended ties:**
  - U20 K16 PUDC_B → 3V3 (sheet 11);
  - U1201 pin 13 X0 → GND (the mux zero reference);
  - U1301 A3/A4 → GND (unused translator inputs).

  No `isolated_pin_label` is left. Block check: 0 failures (101 parts, 709 pads, 322 U20 balls).
- **Phase 3 (layout), planned in `LAYOUT_PLAN.md`** (2026-10-27):
  - **Pose A agreed (user, 2026-10-27):** the source orientation, U20 at about (164, 87), MIO side toward J9.
  - **Step 1 done:** `tools/make_board.py`, `tools/board_setup.py`, `tools/build_pcb.sh`. Parity 0; the block parts
    carry juliancoy's own footprints. Details in LAYOUT_PLAN.md step 1.
  - **Step 2 done:** `tools/import_block.py` copies the block at pose A (`tools/build_pcb.sh --rebuild`).
    `tools/check_block_copper.py`: all 82 block signal nets identical to the source except E3. `ddr3_review.py` on
    both DRAMs: same lengths/vias, all PASS derated. E3/E6/E7 (MIO)/E8/E9 copper done by the import; E5 planelet and
    VCCO_34/35 connections left for phase 4 (REUSE_LOG.md). Details in LAYOUT_PLAN.md step 2.
  - **Step 3, pose trials (2026-10-28):** `placement/pose_trial.sh NAME X Y ROT` (import at the pose onto a copper-free
    base, place 6 seeds, quick-route the signal nets outside the block). Best open nets: A0 (164, 87) 29, Aw (161, 87)
    32, Ae (167, 87) 28, B0 (152, 86, rot 270) 36, B1 (150, 84, rot 270) 36. **A beats B; A0/Aw/Ae are within the
    noise.** Those runs let the router rip (and restore) block copper; `pose_trial.sh` now forbids it
    (`KICAD_RIP_PREEXISTING=0`). The clean judge rerun was stopped for lack of memory. Details in LAYOUT_PLAN.md
    step 3.
  - **QSPI cannot be routed at any pose:** the MIO1-6 balls (A1-A4/E4/F6) face the DDR and are walled in by byte-0
    copper. juliancoy escapes them on F.Cu to one via each; our import drops those escapes. They must be copied with the
    block (new REUSE_LOG entry, below).
  - **Step 4, rough placement done (2026-10-28) at A0**, in two passes (LAYOUT_PLAN.md step 4):
    - the first pass (A0's best trial seed, no proximity claims) scattered the groups (Ethernet parts up to 65 mm
      from U901);
    - **now:** the ADC chain, LDO and J3 pull-down arrays copied from the Ti135 card (`tools/place_analog.py`; that
      card copied the Agilex 5 card, on our outline), then KRT re-placed the other 143 parts with proximity claims to
      their chips (`placement/touchup.py`, `work/place2` seed 1). Claimed parts' median distance 11.1 → 4.0 mm.
    - DRC: parity 0, no courtyard/clearance errors; block copper check 0 failures; no part off the board. Renders
      `reports/rough_placement_top.png`/`_bottom.png`.
  - **Pose trials rerun with the block copper protected:** best open nets Ae 26, Aw 32, A0 35, B0 37, B1 43. A beats
    B; the A offsets overlap within the seed spread. **A0 kept (user, 2026-10-28).**
  - **QSPI escapes copied (REUSE_LOG E10):** `import_block.py` copies juliancoy's F.Cu run from each QSPI ball to its
    via. On a trial board 3 of the 6 QSPI nets then route; the rest stop at U801's inner CSP balls.
  - Fixes in passing:
    - `import_block.py` and `board_setup.py` take `P2K_PCB` (the trial base board). The STATUS command from 2026-10-27
      could not work: the import read the real board, which has copper;
    - `import_block.py`: a trial's `.kicad_pro` was overwritten by the save (KiCad's default 0.2 mm classes); and a
      block outside the board is now refused (rot 90 at (152, 86) was 14 mm off the west edge);
    - `check_block_copper.py` picks the block parts as the import does (our locked connectors share refs with
      juliancoy's);
    - `build_pcb.sh --rebuild` now puts the placement back (`tools/apply_placement.py`); checked: every pose, side and
      lock round-trips.
  - **Start here next session (left off 2026-10-28):**
    1. **Pose A0 confirmed by the user (2026-10-28).**
    2. **E1 done (2026-10-29):** `tools/block_e1.py` (run by `--rebuild`): byte 0 CK − DQS +27.5 ps, CK P/N 0.0/0.1 ps,
       all PASS derated (REUSE_LOG.md, "E1 as built"). E2 (DQS3 pair, 9.0 ps at U15) stays optional.
    3. **Step 4.4 fixes: done 2026-10-28** (`placement/hand_fixes.sh`, `tools/place_free.py`; results in
       LAYOUT_PLAN.md step 4). Left: bottom-side heights against the baseboard, a look at the PHY area.
       **No designator silkscreen** (user, 2026-10-29): hidden by `make_board.py`.
    4. **U801 fan-out:** its inner CSP balls (C2, C4, D2, D4) need vias between the 1.0 mm-pitch balls (the router
       wanted below-standard vias); decide with the flash placement.
    - Note: `tools/build_pcb.sh --rebuild` recreates the board (make_board → board_setup → import_block →
      apply_placement); safe until routing outside the block starts.
- Open from phase 2:
  - **ADS7056IRUGR (C2669798) shows −6 orderable at JLC** (2026-10-27, oversold). Check it before ordering or
    source it separately;
  - LCSC numbers for U341, U401, Y901, FB901.

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
  - ~~E1~~ done 2026-10-29 (`tools/block_e1.py`): byte 0 CK − DQS +27.5 ps, CK P/N 0.0 ps;
  - E2 (optional): match the DQS3 pair;
  - E3: TPS51200 EN;
  - E4: the DRAM part swap;
  - E5–E9: copper parts of the schematic changes (VCCPLL planelet, MIO/bank 34/35 VCCO balls, RSVDGND, banks 34/35
    I/O balls off GND);
  - E10, juliancoy's QSPI escapes (MIO1-6, F.Cu to one via each): done at the import (2026-10-28).

  Then re-run `tools/ddr3_review.py` for both DRAMs.
- [ ] **[verify] items:**
  - `ZYNQ_PCB_NOTES.md` §8: UG470 PROGRAM_B/INIT_B/DONE values, XADC tie-off, IS25WP128 support in `program_flash`/U-Boot, the IS25WP128 reset recovery time (RESET# on
    `ps_por_n`, sheet 8);
  - `POWER_BUDGET.md`: the DDR3L/eMMC/QSPI currents.
- [ ] **Heatsink:** the push-pin grip range for 1.6 mm board + package + tape, and the barb protrusion against the
      5.3 mm card-to-baseboard gap.
- [ ] **JLC quote:** the JLC081611-7628 surcharge, 1 oz inner minimum width/space (the block needs 0.102/0.102 mm), and
      the block's via sizes.
- [ ] **The DDR3L temperature grade:** standard 0…95 °C (C253882) or IT −40…95 °C (C367428).
- [ ] **Baseboard U8 upgrade to 1.5–2 A:** confirm it in the `ac_psu_kicad` redraw.
- [ ] **ADS7056 stock** at JLC (−6 orderable on 2026-10-27).
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
