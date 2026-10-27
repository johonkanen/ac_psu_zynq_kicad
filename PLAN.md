# Plan: Zynq-7000 control card that reuses the DDR3 layout of an open board

Written 2026-10-26. The card does the same job as the Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the
Efinix Ti135 card (`~/dev/efinix_soc_board`): Linux, Gigabit Ethernet, eMMC, ADC and PWM/SPI I/O for the AC lab power
supply baseboard (`~/dev/ac_psu_kicad`). The difference is the method. **The DDR3 is not routed here.** The SoC, the
DDR3 and their routing come from an open-source Zynq board that is already fully routed, as one block:
**juliancoy/zynqPCB** (MIT), chosen 2026-10-26 after the UG933 review in `DDR3_REVIEW.md`.

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
are done here. So the main criterion for the source is a DDR3 route that works; eMMC and Ethernet on the source do not
matter.

**Package (user, 2026-10-26): XC7Z020 CLG484.** JLC has plenty of stock of both the -1 and -2 grades. That leaves two
CLG484 sources, and neither has a DDR proven in hardware:

| | pinguz97/Zynq-SoM | **juliancoy/zynqPCB** (https://github.com/juliancoy/zynqPCB) |
|---|---|---|
| DDR3 | 1 × x16, 512 MB, point to point, 22 Ω series | **2 × MT41K256M16HA (x32, 1 GB)**, fly-by, 40.2 Ω to VTT (TPS51200) |
| Board | 8 layers, JLC08121H-1080A, 1.2 mm, 50 × 42 mm | 8 layers, 1.6 mm, no stack-up in the file, 120 × 60 mm; the DDR block is 36 × 44 mm |
| Routed | yes, 0 unconnected | yes, 0 unconnected (KiCad 10 DRC, 2026-10-26) |
| UG933 review (`DDR3_REVIEW.md`) | **fails**: DRAM on byte lanes 2/3 (F1), VRP/VRN swapped (F2) | **passes** every check that could be made; impedance unknown (0.102 mm traces) |
| Tested | a builder reports DDR test failures (issue #3) | DDR3 "Untested"; only JTAG confirmed |
| Licence | CERN-OHL-S-2.0 | MIT |
| KiCad | 9 | 5 (legacy `.sch`, upgraded on import) |

**Decided 2026-10-26 (user): the block source is juliancoy/zynqPCB, with both DRAMs fitted: 1 GB, 32-bit.**
- Its address/command routing is a UG933 fly-by: TL0 ≈ 38 mm, TL1 ≈ 13 mm, 40.2 Ω to VTT 0.6 mm after the last DRAM.
- Die-to-die skews with the Xilinx package delays:
  - DQ/DM–DQS −10.8…+14.8 ps;
  - addr/cmd–CK +1…+25 ps.

  Both are inside the UG933 Appendix A limits at 1066 MT/s.
- To fix or check before the block is frozen (phase 0.1):
  - the impedance of its 0.102 mm traces on our stack-up (§4.3);
  - CK ≥ DQS on byte 0 has only +0.3 ps margin;
  - four U15 nets that `ddr3_review.py` could not walk (DRC says connected).
- **DRAM part:** juliancoy's MT41K256M16HA-125:E has 0 stock at JLC. Use **MT41K256M16TW-107:P** (C253882, 3,915 on
  2026-10-26; IT grade C367428). It is the same 96-ball map and pitch with a 1 mm narrower body (8 × 14 vs 9 × 14
  mm), so it fits the HA land. It is also DDR3L-1866, which relaxes the Appendix A limits (±91 / ±123 ps).

pinguz97 is not used; its die-length CLG484 footprint and delay script remain useful as references. The proven boards
are all CLG400 (kangyuzhe666, Stanlazy) or FBG676 (NASR-M, CIAA-ACC): **references only** (rules, lengths,
termination, PS7 settings), not copper sources.

Bring-up step 3 (the Zynq DDR test) is the final proof. Plan the PS7 DDR settings so the speed can be dropped
(533 → 400 MHz) if margins are tight.

---

## 2. What changes compared with the Agilex / Ti135 cards

| Item | Agilex 5 / Ti135 card | Zynq card |
|---|---|---|
| SoC | A5EB013B / Ti135N484I3 | **XC7Z020-1CLG484I** (or -2): dual Cortex-A9 667/766 MHz, 85k LC |
| DRAM | 1 GB LPDDR4 x32 (H9HCNNN8KUMLHR) | **1 GB DDR3L x32: 2 × MT41K256M16TW-107 [reuse]** on the juliancoy layout, the Zynq maximum (1 GB, 1 rank). VTT from a TPS51200 (C34771) |
| eMMC | KIOXIA THGAMVG7T13BAIL, 8-bit HS400 / HS200 | **Same KIOXIA part [keep]** on the IS21ES08G land (both are JEDEC 153-ball 11.5 × 13, 0.5 mm). The Zynq SDIO is **4-bit, SD HS ≤ 50 MHz** (~20 MB/s): enough for a rootfs. VCCQ = 1V8 sets bank 501 to 1.8 V (`ZYNQ_PCB_NOTES.md` §4.3) **[new]** |
| Ethernet | RTL8211FDI-CG, RGMII at 1.8 V | **RTL8211F(DI)-CG [keep, new layout]**: PS GEM0 on MIO 16–27 (bank 501), MDIO on MIO 52/53. The FDI is the industrial grade of the same die and footprint |
| QSPI | IS25WP128 (1.8 V) | **IS25WP128-RHLE [keep]**, bank 500 at 1.8 V (decided 2026-10-26); PS_CLK oscillator at 1.8 V |
| 3.3 V I/O | Ti135: 20 HVIO + 4 × SN74AXC8T245 | **HR banks 13/33/34/35 run at 3.3 V directly**: no translators. J3, J5, ADC mux selects and UART go straight to PL pins |
| Safe state of J3 outputs | translator OE + 10 k pull-downs | **PUDC_B tied high** (no internal pull-ups during configuration) + the 10 k pull-downs on every J3 pin **[keep]** |
| Configuration | SDM / SPI active | Zynq boot mode straps (QSPI boot, JTAG fallback), FSBL + bitstream + U-Boot in QSPI, Linux on eMMC |
| Software | br2-efinix / Altera HPS | mainline Linux, U-Boot and Xilinx `zynq_fsbl`; PetaLinux or Buildroot `zynq_zed_defconfig`-style board config |
| Stack-up | JLC08161H-3313, 1.6 mm | **JLC081611-7628, 1.6 mm, 1 oz inner** (decided 2026-10-26): GND on In1/In3/In5, signals on F/In2/In4/In6, the source's roles. 0.102 mm = 39.5 Ω on In2/In4 (§4.3) |

**Kept from the earlier cards:** outline 76.000 × 65.127 mm, J3/J6 bottom-side sockets numbered like the baseboard,
J9 HR911130A magjack and its position, J5 LCD, J1/J2 positions, the ADC front end (OPA365, SN74LV4051A, ADS7056),
the 10 k J3 pull-downs, `reference/baseboard_j11_pinout.csv`, `MECHANICAL.md`, and `tools/jlc`.

---

## 3. Licence

**Decided 2026-10-26 (user): MIT,** like the other cards in this family. juliancoy/zynqPCB is MIT too. Its copyright
and permission notice must stay with the copied portions, so `NOTICE` records the source, the commit and its licence
text. Nothing from pinguz97 (CERN-OHL-S) is copied.

---

## 4. How the block is reused

### 4.1 What the block contains

| Group | Parts in the source (refs as in juliancoy/zynqPCB) | Copper |
|---|---|---|
| SoC | U20 XC7Z020-CLG484 | fan-out of the DDR (bank 502) and power/GND balls |
| DDR3 | U16 (lanes 0/1), U15 (lanes 2/3); R51–R73 40.2 Ω VTT termination; R50 80.6 Ω CK; R46/R49 240 Ω ZQ; R75/R76 80.6 Ω VRN/VRP; R74 4.7 kΩ DRST_B; R47/R48 VREF divider; U8 TPS51200 + its caps; the DDR decaps | every `DDR3_*` net, `VREF`, `DDR3_VTT`, the 1V35 copper inside the outline |
| SoC power | the SoC decaps under/around U20 | their vias and pours inside the block outline |

**Not reused** (user, 2026-10-26: only the DDR3 is hard):
- **routed here [new]:** the eMMC (KIOXIA THGAMVG7T13BAIL), the Ethernet PHY (RTL8211F(DI)-CG, from our Ti135 sheet 09)
  and the QSPI flash;
- **dropped:** everything else on juliancoy (HDMI, audio, USB, sensors, LCD header, SD card, its regulators). Our power
  stage is fed from J6 5 V (see §5 step 6).
- **VTT enable:** juliancoy drives TPS51200 EN from PS_MIO14 (bank 500) with a 20 k pull-up to 3V3. Here EN is tied to
  the power-good chain or pulled up to our rail, so the bank 500 voltage stays free.

The SoC fan-out is copied only for the DDR balls (bank 502) and the power/GND balls under the SoC. The MIO and PL ball
escapes are routed here, to suit our placement.

**The block boundary** is a closed outline on `User.1` drawn around the reused copper. Inside it, nothing may be
changed without a note in `REUSE_LOG.md`. Outside it, the board is ours.

### 4.2 Transfer mechanism

The schematic is made first, so that ref, sheet path and net are identical to the source for every pad in the block.
Then the copper is copied, and the net of every copied item is checked against our netlist.

1. **Schematic import.** Open juliancoy's KiCad 5 project in KiCad 10 in `work/` (it upgrades the files). Then copy
   `DDR3.sch` and the CLG484 DDR/power units into `kicad/` as a sub-sheet.
   - juliancoy uses global net names (`DDR3_A0`, `VREF`, `DDR3_VTT`): keep them inside the sheet, so the net names
     come out the same.
   - Keep the reference designators of the block parts.
   - Annotate our own parts in ranges that cannot collide with them.
   - Swap the DRAM value to MT41K256M16TW-107 **on the same footprint**.
   - Re-wire only the sheet ports.
2. **Copper import, by a script.** `tools/import_block.py`, run under KiCad 10's Python (kipy/pcbnew as in the
   Ti135 repo):
   - open the source board (`DFTBoard.kicad_pcb`, upgraded to KiCad 10 format in `work/`);
   - select the footprints by ref, plus every track, arc, via and zone that lies inside the block outline and belongs
     to a block net;
   - apply one rigid transform (translation + 0/90/180/270°, never mirrored), so it lands where §5 step 4 puts it;
   - **map nets by pad, not by name:** each copied track takes the net of the pad it connects to in the source, which
     is then looked up as (ref, pad) in our board. Copper with no pad path (pours, stitching vias) is mapped by name,
     with an explicit table: `+1V35` → `1V35`, `GND` → `GND`; layers by role: `TOP_GND` → F.Cu, `GND0` → In1, `SIGNAL1` →
     In2, `GND1` → In3, `SIGNAL2` → In4, `GND2` → In5, `SIGNAL4` → In6, `BOTTOM` → B.Cu;
   - write the result into `kicad/zynq_card.kicad_pcb`;
   - report every item it could not map.

   KiCad's own route is the fallback: copy and paste between the two pcbnew windows, then "Update PCB from Schematic"
   with *re-link footprints by reference*. It works because the sheet paths match. But it is manual and not
   repeatable, which matters when the block has to be re-placed.
3. **Check.** Run KiCad DRC with schematic parity. Then a script compares the length, layer and via count of every
   DDR net with the source (`tools/ddr_survey.py`, `tools/ddr3_review.py`). Expected: a difference of 0.

### 4.3 Stack-up and rules

- **Layer roles follow the source.** juliancoy is 8 layers:
  - L1 `TOP_GND`: signals + pours;
  - L2 GND;
  - L3 `SIGNAL1`: CK, part of addr/cmd;
  - L4 GND;
  - L5 `SIGNAL2`: the data bytes;
  - L6 GND;
  - L7 `SIGNAL4`: addr/cmd;
  - L8 `BOTTOM`: power pours, VTT.

  Every inner signal layer sits between two GND planes. There are no dedicated power planes: rails are pours on
  L1/L8 and on the signal layers (+1V0, +1V8, VCCAUX, +3V3 on L3/L5/L7). Our board uses the same roles. Our power
  goes on L8 pours and L1/L7 pours outside the block, with the regulators on B.Cu as on the Ti135 card.
- **Stack-up: JLC081611-7628** (1.593 mm, 1 oz inner), chosen 2026-10-26 by field-solving all 49 JLC 8-layer templates
  for juliancoy's 0.102 mm traces (`ZYNQ_PCB_NOTES.md` §6.4, `reference/stackup_scan_0p102mm.txt`):
  - In2/In4 (CK, data): 39.5 Ω SE / 71.4 Ω diff;
  - In6 (addr/cmd): 45.5 / 74.6 Ω, and 47.4 Ω even without a B plane;
  - F.Cu: 111 Ω, so it is used for fan-out only.

  No re-width of the block; termination as UG933. The MDI pairs go on F.Cu at 0.35/0.20 mm (102 Ω).
- **Board thickness 1.6 mm**, as on the other cards, so J3/J6 and the HR911130A need no check.
- **DRC:** juliancoy's rules are 0.102 mm width and clearance everywhere. Write our rules from scratch the way
  `tools/board_setup.py` does in the Ti135 repo, with the block area exempt from width changes.

---

## 5. Work plan

### Phase 0: decisions and checks (desk work)

1. **Source review:** done 2026-10-26 (`DDR3_REVIEW.md`); **source decided: juliancoy/zynqPCB, both DRAMs**.
   Package decided: CLG484. Still to do on the block before it is frozen:
   - ~~the stack-up and impedance choice~~ **done 2026-10-26: JLC081611-7628** (§4.3);
   - ~~CK ≥ DQS margin on byte 0~~ **checked 2026-10-27:** 0.0 ps on this stack-up. Fix planned as `REUSE_LOG.md` E1
     (CK_P +4.30 mm, CK_N +3.23 mm in the trunk, which also matches CK P/N), made after the import;
   - ~~the four U15 nets~~ **checked 2026-10-27: connected** (a script limitation, now fixed);
   - re-run `ddr3_review.py` for both DRAMs on the imported block, and after E1;
   - optional: report pinguz97's F1/F2 on its issue #3 (public: ask first).
2. ~~Licence~~ **Decided 2026-10-26: MIT** (§3).
3. ~~512 MB vs 1 GB~~ **Decided 2026-10-26: 1 GB** (2 × MT41K256M16TW-107, 32-bit, the full juliancoy block).
4. **Speed grade: either is fine (user, 2026-10-26).** Buy whichever has stock at order time: XC7Z020-1CLG484I (C89055,
   116 at JLC on 2026-10-26) or -2CLG484I (C157624, 309). Both have the same footprint and pinout. Configure the PS7 DDR
   for DDR3L-1066 (533 MHz), the -1 limit, so one bitstream fits both grades. **Still open: the MT41K256M16 temperature
   range** against the card's target. The standard part (C253882) is 0…95 °C, IT (C367428) is −40…95 °C.
5. ~~I/O budget and pin plan~~ **done 2026-10-27** (`vivado/pinplan/`, `ZYNQ_PCB_NOTES.md` §4.3–4.4):
   - 52 PL signals: J3 on bank 34; ADC, LCD and LEDs on bank 33. Banks 13 and 35 are free.
   - MIO: QSPI 1–6/8, RGMII 16–27, SD0 40–45, UART1 48/49 (+ translator to J2), I2C0 50/51, MDIO 52/53.
   - Vivado 2024.2: synthesis + placement, DRC 0.
   - Vivado 2026.1 did not start: its node-locked license names MAC `00:15:5d:af:66:90`, and WSL2 now has
     `…:6e:fc`. Re-host the license, or keep using 2024.2 (no license needed for the 7Z020).
6. ~~Power budget~~ **done 2026-10-27** (`POWER_BUDGET.md`, Vivado `report_power`):
   - 5 V input 0.89 A typical / 1.44 A high, so the card needs the planned 1.5–2 A baseboard U8.
   - Rails: 4 × TLV62585 (1V0 up to 2.4 A, 1V8, 1V35, 3V3) + the block's TPS51200 for VTT.
   - **Thermal:** the ambient is 40 °C worst case. A heatsink is required: worst-case silicon is not stable bare. With
     **Wakefield 960-23-33-D-AB-0** (diagonal push pins), Tj is 61 °C (+4 °C for the PL).
   - **Heatsink holes:** 2 × NPTH Ø3.2 mm at (+14.93, +14.93) / (−14.93, −14.93) mm from U20, on the block-frame
     diagonal that is free of block copper (`POWER_BUDGET.md` §Heatsink).
7. **Software path:** confirm the PS7 config (Vivado board delays from `tools/ddr3_review.py --json`)
   and a Buildroot/PetaLinux image for a Zynq with eMMC on SD0. A ZedBoard or EBAZ4205-class board is enough to try the
   software early.

### Phase 1: repository and tools

1. **Done 2026-10-26:** `git init`, `README.md`, `LICENSE` (MIT), `NOTICE`, this plan, `DDR3_REVIEW.md`,
   `ZYNQ_PCB_NOTES.md`, `tools/ddr3_review.py`, `tools/zsolve*.py`.
2. **Done 2026-10-27:** submodules `tools/jlc` (jlc-tools `06e4105`, as in the Ti135 repo) and `tools/p2k`
   (proteus2kicad `8828f55`, one commit newer than the Ti135 repo's; KiCad 10 env `tools/p2k/bin/kicad_env.sh`).
3. **Done 2026-10-27:** `reference/zynqpcb` = juliancoy/zynqPCB at `5cb7c70` (its latest commit). The import script reads
   that commit.
4. **Done 2026-10-27:** `MECHANICAL.md` (with an origin note) and `reference/baseboard_j11_pinout.csv` from the Ti135
   repo (commit 53f655b).

### Phase 2: schematic

1. Import the block sheets (§4.2 step 1).
2. **[new]** `emmc` (KIOXIA THGAMVG7T13BAIL on SD0, 4-bit; VCCQ at the MIO bank voltage, §2), `ethernet` (RTL8211F(DI)
   on GEM0 RGMII + MDIO, from the Ti135 sheet 09) and `qspi` (IS25WP128-RHLE). **Both MIO banks (500 and 501) are at
   1.8 V**, with MIO7/MIO8 pulled up; the MIO pin assignment comes from the Vivado pin plan (phase 0.5).
3. New sheets: `pwr_input` (J6), `pwr_rails` (TLV62585 cells from the Ti135 card), `pwr_seq` (Zynq order:
   VCCPINT → VCCPAUX/VCCPLL → VCCO_DDR/VCCO_MIO; PL rails per DS187), `soc_config` (boot-mode straps, PS_POR_B
   supervisor, PS_SRST_B, PUDC_B high, JTAG J1), `soc_pl` (HR banks to J3/J5/ADC/LEDs), `adc` [keep], `connectors`
   (J3 + pull-downs, J5, J2, J9 MDI).
4. ERC; netlist check that every block pad has the source's net (script).

### Phase 3: placement

1. Fix the mechanical parts from `MECHANICAL.md` (J3, J6, J9, J5, J1, J2).
2. **Place the block as one rigid unit** (36 × 44 mm).
   - Point the DDR side away from J3 (west edge): J3's 32 signals leave the HR banks on the opposite side of the BGA.
   - Leave room on the J9 (east) side for the PHY, which is routed here.
   - Several block poses can be scored quickly: for each candidate, run the import and a quick route of the non-block
     nets (KiCadRoutingTools `route.py`, as in the Ti135 placement work).
3. **Heatsink:** add the two NPTH Ø3.2 mm push-pin holes with the block, at ±14.93 mm on its free diagonal, plus the
   Ø6 mm keep-outs. Keep the 24 × 23.5 mm base area clear of anything taller than the package.
4. Place the rest around the block: power cells on B.Cu (as on the Ti135 card), ADC south, J3 pull-downs at J3.
5. The bottom-side parts must stay under the 5.3 mm card-to-baseboard gap. The block has U8 (TPS51200) and parts on
   B.Cu; check them against the baseboard parts below.

### Phase 4: routing (only outside the block)

1. MIO escapes from the SoC; **eMMC** (CLK, CMD, DAT0–3, RST_n, ≤ 52 MHz, matched to CLK within a few mm) and
   **QSPI** close to the SoC.
2. **RGMII** SoC → PHY as two matched groups (TX, RX), with the PHY internal delays (`rgmii-id`). Then the **MDI pairs**
   PHY → J9 (100 Ω on the outer layer next to GND; NASR-M ERRATA: inner-layer MDI gave poorer SI).
3. PL I/O to J3/J5/ADC/LEDs. These are slow 3.3 V signals, so KiCadRoutingTools `route.py` is fine here.
4. Power: extend the block's pours (L1/L8 and the inner signal-layer pours) to our regulators; GND stitching; F/B GND
   flood where free.
5. Gate: DRC 0 errors and parity 0; the block-diff script reports 0 changes inside the block.

### Phase 5: sign-off and order

1. DDR review, even though the copper is copied:
   - delays from `tools/ddr3_review.py` with the Xilinx package delays, for both DRAMs;
   - Vivado PS7 DDR board delays (DQS-to-CLK, board delay per byte) computed from them;
   - the reference planes under the DDR on our stack-up (should be identical).
2. `/review-routed-board`; JLC DFM (check juliancoy's via sizes against the JLC 8-layer rules); stock check with
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
| The juliancoy DDR is untested (no proven CLG484 source exists) | UG933 review done (`DDR3_REVIEW.md`), fix the open points before freezing (phase 0.1); the PS7 DDR can be slowed down; bring-up step 3 tests it before anything else; a 16-bit fallback with U15 unfitted and lanes 2/3 unused needs no layout change |
| Net mismatch after the copy (a pad on the wrong net) | pad-based mapping, DRC parity, net-by-net comparison with the source |
| KiCad 5 → 10 format upgrade changes something (legacy zone fills, footprint text) | upgrade in `work/`, then compare segment counts and lengths per net before and after |
| The 0.102 mm DDR traces and the stack-up | JLC081611-7628 puts them at 39.5–45.5 Ω; check JLC's 1 oz inner minimum width/space (4/4 mil) and the surcharge at quote time |
| The eMMC swap to KIOXIA changes the ball use | both are JEDEC 153-ball; check every used ball (CLK, CMD, DAT0–3, RST_n, VCC, VCCQ, VDDi, VSS) against the KIOXIA data sheet |
| DRAM stock (HA-125 has 0 at JLC) | MT41K256M16TW-107 on the same land (3,915 pcs) |
| The SoC at JLC: 116 / 309 pcs | order early, as with the Ti135 parts |
| MIT notice of the source | kept in `NOTICE` |
| Zynq junction temperature (1.8–3.0 W on a 76 × 65 mm card) | heatsink on U20, thermal vias, CPU clock cap; measure with the XADC temperature sensor (`POWER_BUDGET.md`) |

## 7. Decisions (2026-10-26)

1. **1 GB** DDR3L: 2 × MT41K256M16TW-107, 32-bit.
2. **MIT** licence for this repo.
3. **Only the SoC and DDR3 come from the block.** The eMMC, the Ethernet PHY and the QSPI are routed here; they are easy
   compared with the DDR.
4. **Speed grade -1 or -2**, whichever is in stock; the PS7 DDR runs at the -1 limit.
5. **Package XC7Z020 CLG484**, with JLC stock for both grades.
6. **Block source: juliancoy/zynqPCB** (commit `5cb7c70`), after the UG933 review rejected pinguz97.
7. **Both MIO banks at 1.8 V; QSPI flash IS25WP128-RHLE** (shared with the Agilex/Ti135 cards).
8. **Stack-up JLC081611-7628** (1.6 mm, 1 oz inner); MDI pairs on F.Cu.

Still open:
- the block edits E1–E4 in `REUSE_LOG.md` (made after the import);
- the DDR3 temperature grade (phase 0.4).
