# Plan: Zynq-7000 control card that reuses the DDR3 layout of an open board

Written 2026-10-26. The card does the same job as the Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the
Efinix Ti135 card (`~/dev/efinix_soc_board`): Linux, Gigabit Ethernet, eMMC, ADC and PWM/SPI I/O for the AC lab power
supply baseboard (`~/dev/ac_psu_kicad`). The difference is the method. **The DDR3 is not routed here.** The SoC, the
DDR3 and their routing come from an open-source Zynq board that is already fully routed, as one block.

On both earlier cards, most of the layout time went into the memory (`AUTOROUTE_TRIAL.md`, `NEXT_SESSION.md`,
`KRT_LEARNING.md` in those repos). The autorouter never produced a usable LPDDR4 layout, and the hand route plus
tuning took several sessions. With a Zynq the memory is plain DDR3L on fixed PS pins (bank 502), and other people's
boards have already done this job.

Legend: **[keep]** carry over from the Agilex/Ti135 cards, **[reuse]** copy from the source board, **[new]** new work.

---

## 1. Source boards (surveyed 2026-10-26)

Searched GitHub and GitLab (including the OHWR group) for open Zynq-7000 boards with Ethernet, DDR3 and eMMC. Only
KiCad sources are useful for copper reuse. An Altium `.PcbDoc` can be imported into KiCad, but every Altium board found
is either unlicensed or a Zynq 7030, which JLC does not stock.

### Candidates with KiCad sources and a usable licence

| | **pinguz97/Zynq-SoM** | **electrodyssey/NASR-M** | **Stanlazy/7z010_ddr** (+ ZYNQ_Ruler) | **kangyuzhe666/ZYNQ7010-7020_AD9363** |
|---|---|---|---|---|
| URL | https://github.com/pinguz97/Zynq-SoM | https://github.com/electrodyssey/NASR-M | https://github.com/Stanlazy/7z010_ddr, https://github.com/Stanlazy/ZYNQ_Ruler | https://github.com/kangyuzhe666/ZYNQ7010-7020_AD9363 |
| Licence | **CERN-OHL-S-2.0** (strongly reciprocal) | **CERN-OHL-P-2.0** (permissive) | GPL-3.0 / LGPL-2.1 | **Apache-2.0** (permissive) |
| SoC | XC7Z020 **CLG484** (19 × 19, 0.8 mm) | XC7Z030 FBG676 (27 × 27) | XC7Z010 **CLG400** (17 × 17, 0.8 mm) | XC7Z010/7Z020 **CLG400** |
| DDR3 | 1 × MT41K256M16TW-107 (x16, **512 MB**), DDR3L 1.35 V, fly-by with VTT termination | 2 × MT41K256M16TW-107 (x32, **1 GB**) | 1 × MT41K256M16 (x16, 512 MB) | 1 × x16 256M16 (512 MB) |
| eMMC | ISSI IS21ES08G, 153-ball 11.5 × 13 (4-bit SDIO) | Samsung KLM8G1GETF-B041, 153-ball 11.5 × 13 | none (TF card on Ruler) | none (TF card) |
| Ethernet | **RTL8211F**, RGMII on PS GEM0 | RTL8211F-CG (+ a LAN8742 for the MCU) | none | RTL8211E, GbE "stable at 1000M" (README) |
| Also | W25Q128 QSPI, USB3318 ULPI, STM32G431 system controller, BMI323 | USB hub, SATA, SYZYGY pods, clock synth | STPMIC1 PMIC (Ruler) | AD9363 RF, USB3320C, W25Q128 (a PlutoSDR clone) |
| Board | 50 × 42 mm, **8 layers, JLC08121H-1080A, 1.2 mm**, epoxy-filled vias | 10 layers, JLC10161H-2116 | **4 layers**, JLC, 1.2 mm (README) | 148 × 118 mm, **4 layers** (sig/GND/PWR/sig), 1.6 mm |
| KiCad | 9.0 (file version 20241229) | 9 (20241229) | 5 (7z010_ddr), 6 (Ruler) | **converted from Altium** (20201116); Altium `.PcbDoc` also in the repo |
| Routed? | yes: DRC 0 unconnected (KiCad 10.0.7, 2026-10-26). Violations are library mismatch / courtyard only | yes: 0 unconnected; 499 clearance hits against its own rules | yes: 54 DDR nets, 1.5 m | DDR yes (50 nets, all on F/B, 0.152 mm). The 10 unconnected nets are outside the DDR; many rule violations from the Altium import |
| DDR lengths | DQ 10–18 mm, addr 4–17 + 18–33 mm | DQ 42–59 mm, addr ~115 mm | DQ 6.6–18 mm (die delays in the footprint, matched ±0.5 mm per README), addr 33–57 mm | **DQ/DM/DQS 32.1–33.8 mm, addr/cmd/CK 38.5–43.2 mm**: cleanly matched |
| Proven? | **"First prototype under testing, not fully verified"** (README). Issue #3 asks for the Vivado DDR settings | **DDR3 passes the Zynq DDR test, PS Ethernet works, Linux boots** (README, ERRATA.txt) | **DDR3L-1066 tested** on a JLC board | **Yes:** sold as a product (in trial production per README), runs openwifi |
| JLC stock of the SoC | XC7Z020-1CLG484I C89055: 116; -2CLG484I C157624: 309; -1CLG484C C1519066: 142 | XC7Z030-1FBG676C C1522023: **0** | XC7Z010-1CLG400C C2843417: 426; XC7Z020-1CLG400C C2988113: 174 | as Stanlazy |

JLC stock on 2026-10-26 (`tools/jlc/jlc_search.py`): MT41K256M16TW-107:P C253882 3,915; MT41K256M16TW-107 IT:P C367428
1,481; RTL8211F-CG C187932 68,978; IS21ES08G-JCLI 0 (IS21ES08GA-JCLI 13).

DDR3 copper on the pinguz97 board, measured from the file:
- DQ/DM/DQS byte 0 on F.Cu, byte 1 on In5, 10–18 mm, 0.12 mm (DQS pairs 0.1 mm);
- CK on In5, ~35 mm;
- address/command point to point through 22 Ω series resistors: Zynq → resistor 4–17 mm, resistor → DRAM (`*_T`)
  18–33 mm, on F/In5/B. There is no VTT termination;
- 98 nets, about 1.5 m of copper in all;
- die lengths are stored on the CLG484 pads (`scripts/footprint_add_die_lengths.py`), and the repo has a delay
  calculator (`scripts/calculate_track_delays.py`).

Stack-up roles: F sig · In1 GND · In2 power (1V0, 1V8, 3V3, VCCO_*) · In3 power + some signal (1V35) · In4 GND · In5 sig
+ 1V35 · In6 GND · B sig.

### Looked at and rejected

| Repo | Why not |
|---|---|
| ADubovitskiy/Zynq-7000-Board ("ZettBrett") | DDR3 + eMMC + GbE, but only a schematic PDF; no licence |
| juliancoy/zynqPCB (MIT, KiCad, 8 layers) | no Ethernet or eMMC (no longer needed), DDR untested: **kept as the CLG484 fallback**, see Choice |
| ciaa/Hardware, CIAA-ACC (KiCad, 12 layers, 1 GB DDR3, CIAA BSD-style licence) | XC7Z030-2FBG676I: not stocked at JLC; a large FMC/PCIe/104 board. Like NASR-M, only relevant for 1 GB |
| teodor961/Simple_SDR | not routed (0 tracks) |
| syabyr/xc7z020_devboard | DDR layout unfinished (1 track) |
| xjtuecho/EBAZ4205 (MIT, KiCad) | reverse-engineered mining board: NAND, 100 Mb Ethernet, no eMMC |
| antmicro/zynq-video-board | carrier for an Enclustra SoM: no DDR on the board, Altium |
| Hello-FPGA/ZYNQ7020_Core_Board, AnttiLukats/OZOM-Model-A | Altium, no licence |
| Ganghyeok-Lim/Proj-ZYNQ-7000_SOM_Bd, myildirim6198/HighSpeedZynqHWPlattform (MIT, Altium) | XC7Z030 FFG676: not stocked at JLC; Altium import needed |
| HasanTheSyrian/ALTAIR, iliasam/OpenZynqSDR_HW, KindaM3h/SpaceVNXBaseBoard | Altium; built on a bought SoM, or no eMMC/Ethernet |
| GitLab / OHWR (opendso, pandabox, city, pz-tio …) | no Zynq-7000 board with layout sources in the repo, or built on PicoZed/MicroZed SoMs |

### Choice

**Scope (user, 2026-10-26): only the SoC and the DDR3 are reused.** The eMMC and the Ethernet PHY are easy to route and
are done here. So the main criterion for the source is a DDR3 route that is **proven in hardware**; eMMC and Ethernet
on the source do not matter.

**Package (user, 2026-10-26): XC7Z020 CLG484.** JLC has plenty of stock of both the -1 and -2 grades. That leaves two
CLG484 sources, and neither has a DDR proven in hardware:

| | pinguz97/Zynq-SoM | juliancoy/zynqPCB (https://github.com/juliancoy/zynqPCB) |
|---|---|---|
| DDR3 | 1 × x16, 512 MB, fly-by + VTT termination | 2 × MT41K256M16HA (x32, 1 GB) |
| Board | 8 layers, JLC08121H-1080A, 1.2 mm, 50 × 42 mm | 8 layers, 1.6 mm, 120 × 60 mm |
| Routed | yes, 0 unconnected | yes, 0 unconnected (KiCad 10 DRC, 2026-10-26) |
| DDR lengths | DQ 10–18 mm, addr 4–17 + 18–33 mm | DQ ~30 mm, addr ~50 mm; **CK_P/N differ by 1.5 mm**: not tuned |
| Tested | "first prototype under testing" | DDR3 "Untested"; only JTAG confirmed |
| Licence | CERN-OHL-S-2.0 | MIT |

**Primary source: pinguz97/Zynq-SoM.** It is compact, and its lengths look deliberately matched. It is in recent KiCad,
already on a JLC 8-layer stack-up, and stores the CLG484 die lengths on its footprint. It also matches the 512 MB decision.

**Fallback: juliancoy/zynqPCB.** It is the only other routed CLG484 DDR3, but it would need its CK pair and byte
lanes re-tuned first, and it brings the second DRAM.

The proven boards are all CLG400 (kangyuzhe666, Stanlazy) or FBG676 (NASR-M, CIAA-ACC). **They stay as references
only** (rules, lengths, termination, PS7 settings), not as copper sources.

**Review result (2026-10-26, `DDR3_REVIEW.md`): the pinguz97 DDR block fails.**
- Its x16 DRAM is wired to Zynq byte lanes 2/3, but 16-bit mode uses lanes 0/1 (UG585).
- Its VRP/VRN resistors are swapped.
- A builder reports DDR test failures (its issue #3).

**juliancoy/zynqPCB passes every check that could be made:**
- correct lanes and VRP/VRN;
- UG933 fly-by with 40 Ω VTT termination;
- skews within the derated limits.

Its impedance is unknown and it is untested. **Recommended: switch the block source to juliancoy, fitted with only
U16 for 512 MB, or both DRAMs for 1 GB. Decision pending.**

The review steps, as run:
1. **Ask the pinguz97 author** whether the prototype's DDR passed (open a GitHub issue or join #3).
2. **Check the route against Xilinx UG933** (Zynq-7000 PCB design guide, DDR3 rules). Compute die-to-die delays with the
   stored die lengths:
   - DQ/DM to DQS per byte;
   - DQS P/N;
   - address/command to CK;
   - CK P/N;
   - fly-by and stub lengths, the termination, the VREF routing and the reference planes under every DDR trace.

   Tools: `ddr_survey.py` and the source's `calculate_track_delays.py`.
3. **Fix any violation inside the block before it is frozen**, and record it in `REUSE_LOG.md`.
4. Bring-up step 3 (the Zynq DDR test) is the final proof. Plan the PS7 DDR settings so the speed can be dropped
   (533 → 400 MHz) if margins are tight.

---

## 2. What changes compared with the Agilex / Ti135 cards

| Item | Agilex 5 / Ti135 card | Zynq card |
|---|---|---|
| SoC | A5EB013B / Ti135N484I3 | **XC7Z020-1CLG484I** (or -2): dual Cortex-A9 667/766 MHz, 85k LC |
| DRAM | 1 GB LPDDR4 x32 (H9HCNNN8KUMLHR) | **512 MB DDR3L x16, MT41K256M16TW-107 [reuse]**. The Zynq PS has only DDR_A[14:0], so one x16 chip tops out at 4 Gb = 512 MB. 1 GB needs two chips (x32): see §1, fallback B |
| eMMC | KIOXIA THGAMVG7T13BAIL, 8-bit HS400 / HS200 | **Same KIOXIA part [keep]** on the IS21ES08G land (both are JEDEC 153-ball 11.5 × 13, 0.5 mm). The Zynq SDIO is **4-bit, SD HS ≤ 50 MHz** (~20 MB/s): enough for a rootfs. VCCQ = 1V8 is only possible if the MIO bank holding SD0/SD1 is at 1.8 V: check the source's bank 501 voltage |
| Ethernet | RTL8211FDI-CG, RGMII at 1.8 V | **RTL8211F(DI)-CG [reuse]**: PS GEM0 on MIO 16–27 (bank 501), MDIO on MIO 52/53. The FDI is the industrial grade of the same die and footprint |
| QSPI | IS25WP128 (1.8 V) | W25Q128JV (3.3 V) **[reuse]**, unless bank 500 is moved to 1.8 V. That would invalidate the source's MIO bank voltage: keep the source's |
| 3.3 V I/O | Ti135: 20 HVIO + 4 × SN74AXC8T245 | **HR banks 13/33/34/35 run at 3.3 V directly**: no translators. J3, J5, ADC mux selects and UART go straight to PL pins |
| Safe state of J3 outputs | translator OE + 10 k pull-downs | **PUDC_B tied high** (no internal pull-ups during configuration) + the 10 k pull-downs on every J3 pin **[keep]** |
| Configuration | SDM / SPI active | Zynq boot mode straps (QSPI boot, JTAG fallback), FSBL + bitstream + U-Boot in QSPI, Linux on eMMC |
| Software | br2-efinix / Altera HPS | mainline Linux, U-Boot and Xilinx `zynq_fsbl`; PetaLinux or Buildroot `zynq_zed_defconfig`-style board config |
| Stack-up | JLC08161H-3313, 1.6 mm | **JLC08121H-1080A, 1.2 mm**, the source's, so its DDR widths stay at their impedance (§4.3) |

**Kept from the earlier cards:** outline 76.000 × 65.127 mm, J3/J6 bottom-side sockets numbered like the baseboard,
J9 HR911130A magjack and its position, J5 LCD, J1/J2 positions, the ADC front end (OPA365, SN74LV4051A, ADS7056),
the 10 k J3 pull-downs, `reference/baseboard_j11_pinout.csv`, `MECHANICAL.md`, and `tools/jlc`.

---

## 3. Licence

The pinguz97 board is **CERN-OHL-S-2.0**. A board that contains its copper is a modified version, so **this repository
and its outputs must be CERN-OHL-S-2.0**:
- keep the source's notices;
- add a NOTICE file with the origin and the commit used;
- publish the sources of anything made and distributed.

The other cards in this family are MIT.

**Decided 2026-10-26: this repository is CERN-OHL-S-2.0.** `LICENSE` holds the licence text, and `NOTICE` records the
source and its commit.

---

## 4. How the block is reused

### 4.1 What the block contains

| Group | Parts in the source (refs as in pinguz97) | Copper |
|---|---|---|
| SoC | U2 XC7Z020-CLG484 (with die lengths on its pads) | fan-out of the DDR and power/GND balls |
| DDR3 | U1 MT41K256M16, ZQ, VRP/VRN, address/command termination resistors, VTT/VREF regulator and caps, DDR decaps | every DDR net, the 1V35 / 0V675 / VREF copper |
| SoC power | the SoC decaps under/around U2, VCCPLL filter | their vias and pours inside the block outline |
**Not reused** (user, 2026-10-26: only the DDR3 is hard):
- **routed here [new]:** the eMMC (KIOXIA THGAMVG7T13BAIL), the Ethernet PHY (RTL8211F(DI)-CG, from our Ti135 sheet 09)
  and the QSPI flash;
- **dropped:** the DF40 board-to-board connectors, the STM32 system controller, USB3318, BMI323, the mounting holes,
  and the source's VIN regulators. Our power stage is fed from J6 5 V (see §5 step 6).

The SoC fan-out is copied only for the DDR balls (bank 502) and the power/GND balls under the SoC. The MIO and PL ball
escapes are routed here, to suit our placement.

**The block boundary** is a closed outline on `User.1` drawn around the reused copper. Inside it, nothing may be
changed without a note in `REUSE_LOG.md`. Outside it, the board is ours.

### 4.2 Transfer mechanism

The schematic is made first, so that ref, sheet path and net are identical to the source for every pad in the block.
Then the copper is copied, and the net of every copied item is checked against our netlist.

1. **Schematic import.** Copy `zynq_ddr.kicad_sch`, `DDR3L.kicad_sch` and `zynq_power.kicad_sch` into `kicad/` as
   sub-sheets, **with the source's sheet names**, e.g. `Zynq_B502_DDR`.
   Net names like `/Zynq_B502_DDR/DDR_A0` then come out the same.
   - Keep the reference designators of the block parts.
   - Annotate our own parts in ranges that cannot collide with them.
   - Replace the parts we change (eMMC → KIOXIA) **on the same footprint**.
   - Re-wire only the sheet ports.
2. **Copper import, by a script.** `tools/import_block.py`, run under KiCad 10's Python (kipy/pcbnew as in the
   Ti135 repo):
   - open the source board (upgraded to KiCad 10 format in `work/`);
   - select the footprints by ref, plus every track, arc, via and zone that lies inside the block outline and belongs
     to a block net;
   - apply one rigid transform (translation + 0/90/180/270°, never mirrored), so it lands where §5 step 4 puts it;
   - **map nets by pad, not by name:** each copied track takes the net of the pad it connects to in the source, which
     is then looked up as (ref, pad) in our board. Copper with no pad path (pours, stitching vias) is mapped by name,
     with an explicit table: `+1V35` → `1V35`, `GND` → `GND` …;
   - write the result into `kicad/zynq_card.kicad_pcb`;
   - report every item it could not map.

   KiCad's own route is the fallback: copy and paste between the two pcbnew windows, then "Update PCB from Schematic"
   with *re-link footprints by reference*. It works because the sheet paths match. But it is manual and not
   repeatable, which matters when the block has to be re-placed.
3. **Check.** Run KiCad DRC with schematic parity. Then a script compares the length, layer and via count of every
   DDR net with the source (`ddr_survey.py`, from this session, moved into `tools/`). Expected: a difference of 0.

### 4.3 Stack-up and rules

- **Use JLC08121H-1080A (1.2 mm), as the source does.** The DDR widths (0.12 / 0.135 mm SE, 0.1 mm pairs) were chosen
  for that dielectric. Mapping them onto JLC08161H-3313 changes the impedance and means re-widening every trace,
  which is the work this plan avoids.
- **Check 1.2 mm against the through-hole parts:**
  - J3/J6 1.27 mm sockets: fine at 1.2 mm;
  - HR911130A board locks / pegs: check the drawing;
  - any press-fit parts.
- **Layer roles follow the source:** F sig · In1 GND · In2 power · In3 power/sig · In4 GND · In5 sig · In6 GND · B sig.
  Our own nets outside the block use the same roles. Inside the block, In2/In3 are the source's power pours; extend them
  outward instead of redrawing them.
- **DRC:** copy the source's `Zynq_SoM.kicad_dru` and net classes as a base. Add our area rules (J3 edge exception, MDI
  pairs) the way `tools/board_setup.py` does in the Ti135 repo.

---

## 5. Work plan

### Phase 0: decisions and checks (desk work)

1. **Source review** (§1): **done 2026-10-26, `DDR3_REVIEW.md`.** pinguz97 fails (F1 byte lanes, F2 VRP/VRN), and
   juliancoy/zynqPCB passes. Next: decide the switch to juliancoy, and report F1/F2 on pinguz97 issue #3.
   **Package decided 2026-10-26: CLG484.**
2. ~~Licence~~ **Decided 2026-10-26:** CERN-OHL-S for this repo (§3).
3. ~~512 MB vs 1 GB~~ **Decided 2026-10-26: 512 MB** (one x16 DDR3L, the pinguz97 block). 512 MB is plenty for a Linux
   control card (Buildroot rootfs, no desktop).
4. **Speed grade: either is fine (user, 2026-10-26).** Buy whichever has stock at order time: XC7Z020-1CLG484I (C89055,
   116 at JLC on 2026-10-26) or -2CLG484I (C157624, 309). Both have the same footprint and pinout. Configure the PS7 DDR
   for DDR3L-1066 (533 MHz), the -1 limit, so one bitstream fits both grades. **Still open: the MT41K256M16 temperature
   range** against the card's target. The standard part is 0…95 °C, IT is −40…95 °C.
5. **I/O budget** on the CLG484 HR banks (13, 33, 34, 35), all at 3.3 V:
   - J3: 32;
   - J5 LCD: 12;
   - ADC SPI 3 (ADS7056 DVDD at 3.3 V, or a 1.8 V bank) + mux 3;
   - UART: 2;
   - LEDs: 2–3;
   - spare.

   Roughly 60 of ~200 pins. Do the pin plan in a Vivado dummy project (PS7 with DDR, GEM0, SD0, QSPI, UART, I2C), the
   way `efinity/pinplan/pinplan.py` did it for the Ti135.
6. **Power budget:** VCCINT/VCCPINT 1.0 V, VCCAUX/VCCPAUX 1.8 V, VCCO 3.3 V, VCCO_DDR 1.35 V, VTT/VREF 0.675 V, and the
   PHY rails, from the Xilinx Power Estimator. Check it against the 5V_ISOL limit in the Ti135 `POWER_BUDGET.md`.
   Reuse the TLV62585 cells from the Ti135 card for the rails outside the block (1V0, 1V8, 3V3). Put the 1V35 and VTT
   regulation inside the block, as in the source.
7. **Software path:** confirm the PS7 config (Vivado board delays from the source's lengths, `calculate_track_delays.py`)
   and a Buildroot/PetaLinux image for a Zynq with eMMC on SD0. A ZedBoard or EBAZ4205-class board is enough to try the
   software early.

### Phase 1: repository and tools

1. **Done 2026-10-26:** `git init`, `README.md`, `LICENSE` (CERN-OHL-S-2.0), `NOTICE`, this plan.
2. Add the submodules `tools/jlc` (jlc-tools) and `tools/p2k` (proteus2kicad, KiCad 10 env), as in the Ti135 repo.
3. Add the source as a pinned submodule `reference/zynq-som` (pinguz97/Zynq-SoM at a fixed commit). The import
   script always reads that commit.
4. Copy `MECHANICAL.md` and `reference/baseboard_j11_pinout.csv` from the Ti135 repo, with their origin noted.

### Phase 2: schematic

1. Import the block sheets (§4.2 step 1).
2. **[new]** `emmc` (KIOXIA THGAMVG7T13BAIL on SD0, 4-bit; VCCQ at the MIO bank voltage, §2), `ethernet` (RTL8211F(DI)
   on GEM0 RGMII + MDIO, from the Ti135 sheet 09) and `qspi`. Choose the bank 500/501 voltages in the Vivado pin plan
   (phase 0.5): the eMMC VCCQ must be 1.8 V, and RGMII must run at 1.8 V or 3.3 V to match the PHY.
3. New sheets: `pwr_input` (J6), `pwr_rails` (TLV62585 cells from the Ti135 card), `pwr_seq` (Zynq order:
   VCCPINT → VCCPAUX/VCCPLL → VCCO_DDR/VCCO_MIO; PL rails per DS187), `soc_config` (boot-mode straps, PS_POR_B
   supervisor, PS_SRST_B, PUDC_B high, JTAG J1), `soc_pl` (HR banks to J3/J5/ADC/LEDs), `adc` [keep], `connectors`
   (J3 + pull-downs, J5, J2, J9 MDI).
4. ERC; netlist check that every block pad has the source's net (script).

### Phase 3: placement

1. Fix the mechanical parts from `MECHANICAL.md` (J3, J6, J9, J5, J1, J2).
2. **Place the block as one rigid unit.**
   - The PHY must face J9, so rotate the block until the PHY side points east (J9 is on the east edge, J3 on the west).
   - The DDR side then faces north or south, away from J3's 32 signals, which leave the HR banks on the opposite side.
   - Several block poses can be scored quickly: for each candidate, run the import and a quick route of the non-block
     nets (KiCadRoutingTools `route.py`, as in the Ti135 placement work).
3. Place the rest around the block: power cells on B.Cu (as on the Ti135 card), ADC south, J3 pull-downs at J3.
4. The bottom-side parts must stay under the 5.3 mm card-to-baseboard gap. **The source has its eMMC on B.Cu**; check
   it against the baseboard parts below.

### Phase 4: routing (only outside the block)

1. MIO escapes from the SoC; **eMMC** (CLK, CMD, DAT0–3, RST_n, ≤ 52 MHz, matched to CLK within a few mm) and
   **QSPI** close to the SoC.
2. **RGMII** SoC → PHY as two matched groups (TX, RX), with the PHY internal delays (`rgmii-id`). Then the **MDI pairs**
   PHY → J9 (100 Ω on the outer layer next to GND; NASR-M ERRATA: inner-layer MDI gave poorer SI).
3. PL I/O to J3/J5/ADC/LEDs. These are slow 3.3 V signals, so KiCadRoutingTools `route.py` is fine here.
4. Power: extend the block's In2/In3 pours to our regulators; GND stitching; F/B GND flood.
5. Gate: DRC 0 errors and parity 0; the block-diff script reports 0 changes inside the block.

### Phase 5: sign-off and order

1. DDR review, even though the copper is copied:
   - delays from `calculate_track_delays.py`;
   - Vivado PS7 DDR board delays (DQS-to-CLK, board delay per byte) computed from them;
   - the reference planes under the DDR on our stack-up (should be identical).
2. `/review-routed-board`; JLC DFM; epoxy-filled and capped vias (as the source specifies); stock check with
   `tools/jlc/stock_check.py`.

### Phase 6: bring-up

1. Rails and sequencing, PS_POR_B.
2. JTAG ID.
3. **Zynq DDR memory test** (the FSBL/`zynq_dram_test` in Vitis).
4. QSPI programming, then U-Boot.
5. eMMC, Ethernet (RTL8211F: device-tree `phy-mode = "rgmii-id"`, LED register as on the Ti135 card).
6. ADC, then J3 outputs with the baseboard attached.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| The pinguz97 DDR is unproven (no proven CLG484 source exists) | ask the author and review against UG933 before the import (phase 0.1); the PS7 DDR can be slowed down; bring-up step 3 tests it before anything else |
| Net mismatch after the copy (a pad on the wrong net) | pad-based mapping, DRC parity, net-by-net comparison with the source |
| KiCad 9 → 10 format upgrade changes something | upgrade in `work/`, then compare segment counts and lengths per net before and after |
| The 1.2 mm stack-up does not suit J9 or the sockets | check the drawings in phase 0; if 1.6 mm is forced, recompute the DDR widths with `zsolve.py` (Ti135 repo) and accept a re-width pass on the block |
| The eMMC swap to KIOXIA changes the ball use | both are JEDEC 153-ball; check every used ball (CLK, CMD, DAT0–3, RST_n, VCC, VCCQ, VDDi, VSS) against the KIOXIA data sheet |
| The 512 MB limit | decided in phase 0.3; fallback B covers 1 GB |
| The SoC at JLC: 116 / 309 pcs | order early, as with the Ti135 parts |
| CERN-OHL-S obligations | decided in phase 0.2 |

## 7. Decisions (2026-10-26)

1. **512 MB** DDR3L (one x16 chip). NASR-M / XC7Z030 is not used.
2. **CERN-OHL-S-2.0** for this repo.
3. **Only the SoC and DDR3 come from the block.** The eMMC, the Ethernet PHY and the QSPI are routed here; they are easy
   compared with the DDR.
4. **Speed grade -1 or -2**, whichever is in stock; the PS7 DDR runs at the -1 limit.
5. **Package XC7Z020 CLG484**, with JLC stock for both grades. Source: pinguz97/Zynq-SoM, fallback juliancoy/zynqPCB (§1).

Still open:
- **the block source after the UG933 review** (`DDR3_REVIEW.md`): pinguz97 fails, and the recommendation is
  juliancoy/zynqPCB (512 MB with U16 only, or 1 GB);
- the DDR3 temperature grade (phase 0.4).
