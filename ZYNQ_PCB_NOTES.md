# XC7Z020-CLG484 PCB design notes

Device rules for the schematic and the layout of the Zynq control card. The board-level decisions (which signal goes
where, part choices) are in `PLAN.md`; the review of the reused DDR3 block is in `DDR3_REVIEW.md`. This file covers
what the Zynq-7000 itself requires.

Written 2026-10-26, from:
- UG933 (PCB design guide) v1.13.1;
- DS187 (data sheet) v1.21;
- UG865 (packaging and pinout) v1.9;
- UG585 (TRM), the HTML edition on docs.amd.com.

The PDFs are not in git; `reference/vendor/README.md` lists them and how to fetch them. Items marked **[verify]**
still need checking against a primary source or the Vivado pin planner.

---

## 1. Package

- **XC7Z020-1CLG484I or -2CLG484I** (user decision 2026-10-26: either grade, whichever JLC has in stock).
- CLG484: 19 × 19 mm, 0.8 mm pitch, wire-bond, 22 × 22 array.
- **200 PL SelectIO** (all HR, in banks 13, 33, 34, 35) and **128 PS I/O** (UG865 Table 1-2).
- The -1 and -2 grades share the footprint and pinout; -2 runs the CPUs faster (766 vs 667 MHz).

| Bank | Type | Contents | VCCO on this card |
|---|---|---|---|
| 0 | config | PROGRAM_B, INIT_B, DONE, CFGBVS, JTAG, XADC, DXP/DXN, VCCBATT | 3.3 V |
| 13, 33, 34, 35 | PL HR (1.2–3.3 V) | user I/O; PUDC_B is IO_L21N_T3_DQS_PUDC_B_34 | **3.3 V** (J3, J5, ADC, LEDs directly; no translators) |
| 500 | PS MIO0 | MIO[15:0], PS_CLK, PS_POR_B | 1.8 V or 3.3 V, §4 |
| 501 | PS MIO1 | MIO[53:16], PS_MIO_VREF, PS_SRST_B | **1.8 V** (eMMC VCCQ, RGMII) |
| 502 | PS DDR | DDR3L x32 (2 × MT41K256M16TW-107, the juliancoy block), dedicated balls | 1.35 V |

The 7Z020 has no HP banks, so the PL I/O cannot use DCI or anything above 3.3 V.

## 2. Supplies

DS187 Table 2 (recommended operating conditions) and the plan for this card. PS and PL rails may be merged as UG933
allows, as on the source boards.

| Rail on the card | V | Zynq pins | Range (DS187) | Notes |
|---|---|---|---|---|
| `1V0` | 1.00 | VCCPINT, VCCINT, VCCBRAM | 0.95–1.05 | VCCPINT "can be combined with VCCINT" when the PL never powers down alone (UG933 Ch. 5). VCCINT and VCCBRAM must share a supply (DS187 note 5) |
| `1V8` | 1.80 | VCCPAUX, VCCAUX, VCCO_MIO1 (and MIO0 if at 1.8 V) | 1.71–1.89 | |
| `VCCPLL` | 1.80 | VCCPLL | 1.71–1.89 | from 1V8 through a 120 Ω @ 100 MHz 0603 bead + 10 µF 0603. A 0.47–4.7 µF 0402 cap goes ≤ 5.1 mm of trace from the VCCPLL/GND vias. A planelet ≥ 2 mm wide and < 76 mm long, or a trace ≤ 40 Ω and < 50.8 mm (UG933 Ch. 5; parts BLM18SG121TN1, GRM188R60G106ME47, GRM155R60J474KE19) |
| `1V35` | 1.35 | VCCO_DDR | 1.14–1.89 | DDR3L; also the DRAM VDD/VDDQ |
| `0V675` | VCCO_DDR / 2 | PS_DDR_VREF0/1, DRAM VREFCA/VREFDQ, VTT if used | – | divider or tracking regulator (§6.3) |
| `3V3` | 3.30 | VCCO_0, VCCO_13/33/34/35, (VCCO_MIO0 at 3.3 V) | 1.14–3.465 (HR VCCO) | |
| `VCCADC` | 1.80 | VCCADC_0 / GNDADC_0 | 1.71–1.89 | XADC unused: VCCADC to VCCAUX through a bead, GNDADC to GND **[verify against UG480]** |
| – | – | VCCBATT_0 | 1.0–1.89 | no bitstream encryption: tie to GND or VCCAUX (DS187 note 10). The source ties it to 1V8 |

**Decoupling** (UG933 Tables 3-1 and 3-2, CLG484 Z-7020; capacitor specs in Table 3-3):

| Supply | 330 µF | 100 µF | 47 µF | 4.7 µF | 0.47 µF |
|---|---|---|---|---|---|
| VCCINT | 1 | – | – | 2 | 4 |
| VCCBRAM | – | 1 | – | 1 | 1 |
| VCCAUX | – | – | 1 | 1 | 2 |
| VCCO per HR bank | – | 1 (47 or 100) | | 2 | 4 |
| VCCO_0 | – | – | 1 | – | – |
| VCCPINT | – | 1 | – | 1 | 3 |
| VCCPAUX | – | 1 | – | 1 | 1 |
| VCCO_DDR | – | 1 | – | 1 | 4 |
| VCCO_MIO0 / MIO1 | – | 1 each | – | 1 each | 1 each |
| VCCPLL | 10 µF + 0.47–4.7 µF (above) | | | | |

UG933 allows consolidating bulk capacitors when rails are merged (*Bulk Capacitor Consolidation Rules*, Ch. 3).
0.47 µF parts go under the BGA on B.Cu, as on the earlier cards.

## 3. Power sequencing and reset (DS187, UG585)

- **PS order (recommended):** VCCPINT → VCCPAUX + VCCPLL → VCCO_MIO0/MIO1 + VCCO_DDR. Reverse it at power-off.
  Supplies with the same voltage may share a regulator and ramp together.
- **PL order (recommended):** VCCINT + VCCBRAM → VCCAUX → VCCO.
- PS and PL are independent: either may come up first.
- **Ramp time:** 0.2–50 ms for every rail (DS187 Table 7).
- **VCCO_MIO / VCCO – VCCAUX/VCCPAUX ≤ 2.625 V,** except for at most T_VCCO2VCCAUX per power cycle: 800 ms at
  Tj 85 °C, 500 ms at 100 °C (DS187 Table 7). A 3.3 V bank rising before 1V8 counts against that time. So bring 1V8
  up no later than 3V3, which the enable chain below does.
- **PS_POR_B:**
  - Low until VCCPINT, VCCPAUX and VCCO_MIO0 are at their minimum, then at least **T_PSPOR = 100 µs** more
    (DS187 Table 22).
  - Do not release it inside the secure lockdown window relative to the last PL supply ramp (DS187 Figure 1).
  - At power-off, before VCCPINT falls below 0.80 V, assert PS_POR_B (or stop PS_CLK, or let VCCPAUX < 0.70 V or
    VCCO_MIO0 < 0.90 V) until VCCPINT < 0.40 V. This protects the eFUSEs.

  → A supervisor on the last rail's power-good, ≥ 10 ms delay, open-drain onto PS_POR_B. It is the same scheme as the
  Ti135 card's TPS3808 into CRESET_N.
- **PS_SRST_B:**
  - pull up to VCCO_MIO1;
  - must be High to boot;
  - must not be asserted while the BootROM runs, or it locks down until the next POR (UG585 *External Reset Signal
    Pins*);
  - the minimum pulse is 3 PS_CLK cycles. A reset button belongs on PS_SRST_B, not on PS_POR_B (NASR-M ERRATA).
- **Proposed enable chain:** 5V0 → `1V0` → `1V8` (+ VCCPLL, VCCADC) → `3V3`, `1V35` → `0V675`/VTT → pg_all →
  supervisor → PS_POR_B. It meets both recommended orders and the VCCO – VCCAUX rule.

## 4. PS clock, boot mode and MIO

### 4.1 PS_CLK

- 30–60 MHz, single-ended LVCMOS at the **VCCO_MIO0 level**;
- duty cycle 40–60 %, ≤ ±0.5 % RMS jitter, rise/fall ≤ 6 ns (DS187 Table 20);
- the usual choice is a 33.333 MHz oscillator, as on pinguz97 and the ZedBoard.

### 4.2 Boot mode straps (UG585 *Boot Mode Pin Settings*)

MIO[8:2] are sampled at PS_POR_B release. Every one needs **its own 20 kΩ** pull-up (1) or pull-down (0):
- **pull-ups go to VCCO_MIO0 only** (UG933 caution);
- no resistor trees: use one resistor plus a jumper if the strap must be changeable;
- the stub on MIO8 stays < 10 mm (it is also the QSPI feedback clock).

| Pin | Function | Setting on this card |
|---|---|---|
| MIO2 | BOOT_MODE[3]: JTAG chain | 0: cascaded (PS DAP + PL TAP on one JTAG) |
| MIO5 / MIO4 / MIO3 | BOOT_MODE[0] / [2] / [1]: boot device | **1 / 0 / 0 = Quad-SPI**. JTAG 000, NOR 001 (MIO3), NAND 010 (MIO4), SD 110 (MIO5 + MIO4) |
| MIO6 | BOOT_MODE[4]: PLLs | 0: PLLs enabled |
| MIO7 | VMODE[0]: bank 500 | 1 (pull-up) = 1.8 V, 0 = 2.5/3.3 V. **Must match VCCO_MIO0, or I/O damage is possible** |
| MIO8 | VMODE[1]: bank 501 | 1 (pull-up) = 1.8 V |

**The Zynq-7000 BootROM cannot boot from eMMC.** Its boot devices are QSPI, NOR, NAND, SD and JTAG. So:
- QSPI holds the FSBL, the bitstream and U-Boot;
- Linux and the rootfs go on the eMMC;
- JTAG boot is the recovery path, since the card has no SD socket.

### 4.3 MIO allocation (to be checked in the Vivado pin plan, PLAN.md phase 0.5)

| Interface | MIO | Bank | Notes |
|---|---|---|---|
| QSPI0 (single, x4) | 1–6, + 8 as the feedback clock | 500 | UG933: IO0–3 and SS matched to SCLK within ±50 ps. Minimum trace delay from T_QSPICKD < T_CKO,flash + 2·T_pd. To run above ~40 MHz, MIO8 carries only the strap resistor (feedback mode) |
| GEM0 RGMII | 16–27 | 501 | RTL8211F(DI) with internal delays (`rgmii-id`): DATA/CTL to CLK skew **≤ ±50 ps including package** (UG933). PS_MIO_VREF = VCCO_MIO1/2 = 0.9 V: divider + 10 nF |
| MDIO0 | 52, 53 | 501 | pull-up on MDIO |
| SD0 (eMMC, 4-bit) | 40–45 | 501 | **40–60 Ω series resistor (fit 0 Ω first) on CLK, next to the MIO pin.** PCB + package skew of DAT0–3 and CMD **between 50 and 200 ps relative to CLK** (UG933 *SDIO*; match them as a group to CLK and keep CLK the shortest). Zynq-7000 SDIO is 4-bit, SD 2.0 high speed ≤ 50 MHz: no HS200/HS400, so the eMMC DS ball stays unused. RST_n from a GPIO MIO |
| UART | e.g. 46/47 or 48/49 | 501 | console; 1.8 V, so a translator to the 3.3 V J2 header, or use a PL UART on a 3.3 V HR bank (EMIO) **[decide in the pin plan]** |
| I2C | free pair | 501 | 4.7 kΩ pull-ups at the far end; the PS I2C has no glitch filter, so add RC filters (UG933 *IIC*) |
| GPIO | rest | 500/501 | eMMC RST_n, PHY reset, PHY interrupt, LEDs |

Bank voltage choice:
- **Bank 501 at 1.8 V** is fixed by the eMMC VCCQ and the 1.8 V RGMII.
- **Bank 500** is open:
  - at 1.8 V: the shared IS25WP128 (1.8 V) works, and PS_CLK is a 1.8 V oscillator;
  - at 3.3 V: a 3.3 V flash (W25Q128JV, as on pinguz97).
  - Recommended: **1.8 V**, so the flash part stays common with the Agilex/Ti135 cards **[decide]**.

## 5. PL configuration and JTAG (bank 0)

| Pin | Connection | Source |
|---|---|---|
| CFGBVS_0 | **to VCCO_0 (3.3 V)**; to GND only if VCCO_0 ≤ 1.8 V. Wrong = damage | UG865 Table 1-5 |
| PROGRAM_B_0 | 4.7 kΩ pull-up to VCCO_0 (not floating) | UG933, UG470 **[verify value]** |
| INIT_B_0 | 4.7 kΩ pull-up to VCCO_0 (open drain) | UG470 **[verify value]** |
| DONE_0 | 330 Ω pull-up to VCCO_0, optional LED | UG470 **[verify value]** |
| PUDC_B (IO_L21N_T3_DQS_PUDC_B_34) | **tie to VCCO_34 (High) directly or through ≤ 1 kΩ** → no internal pull-ups during configuration. Never float | UG865 Table 1-5 |
| TCK, TMS, TDI | pull-ups (UG933 *Boot Mode Pins* note); JTAG at VCCO_0 = 3.3 V. One header serves PS and PL (cascaded, MIO2 = 0) | UG933 |
| DXP_0 / DXN_0 | tie to GND when unused | UG865, UG933 |
| VP/VN, VREFP/VREFN | XADC unused: tie to GNDADC; VREFP/VREFN to GND selects the internal reference | UG480 **[verify]** |
| RSVDVCC[3:1] | **tie to VCCO_0** | UG865 Table 1-5 |
| RSVDGND | do not connect | UG865 Table 1-5 |
| VCCBATT_0 | GND or VCCAUX (no encryption) | DS187 |

**PUDC_B High plus the 10 kΩ pull-downs on every J3 pin** keep the PWM/gate outputs low until the bitstream drives them.
This is the Zynq equivalent of the Ti135 card's gated translator OE (Ti135 `MIGRATION_PLAN.md` §3.2).

## 6. DDR3/DDR3L

### 6.1 Memory types, and why not DDR4

**The Zynq-7000 PS DDR controller supports DDR3, DDR3L, DDR2 and LPDDR2 only** (UG933 Table 5-1, UG585 *DDR Memory
Types*). There is no DDR4 option:
- not in the PS;
- not in the PL either: the 7-series MIG has no DDR4 support, and the 7Z020 has only HR banks anyway.

DDR4 begins with Zynq UltraScale+ (MPSoC). So "DDR4 routing" does not apply to this card; the rules below are the
DDR3/DDR3L ones.

**Controller limits** (UG585 *Connectivity Limitations*):
- 1 GB total;
- 16- or 32-bit data width (ECC only as 16 + 10 bits);
- 1 rank;
- 15 row bits and 3 bank bits: one x16 4 Gb chip (MT41K256M16) is the most a 16-bit bus can hold, so 512 MB;
- **16-bit mode uses PS_DDR_DQ[15:0], i.e. byte lanes 0 and 1** (UG585 *DDR I/O Signals*). Lanes 2/3 are left
  unconnected (UG933 Table 5-5).

Data rate: **DDR3/DDR3L ≤ 1066 Mb/s on every speed grade** (DS187 Table 18). Run 1066, with 800 as the fallback.

### 6.2 Connections (UG933 Ch. 5)

| Item | DDR3/DDR3L value |
|---|---|
| VCCO_DDR | 1.5 V (DDR3) / **1.35 V (DDR3L)** |
| PS_DDR_VREF0/1 | VCCO_DDR / 2: a divider or tracking regulator plus 0.01–0.47 µF. A separate divider and HF cap per IC if dividers are used. Floating when the internal VREF is used, which limits the rate to 800 Mb/s |
| VTT (only with parallel termination) | VCCO_DDR / 2 from a DDR termination regulator (e.g. TPS51200) |
| **PS_DDR_VRP → GND, PS_DDR_VRN → VCCO_DDR** | each through **2 × the trace impedance**: **80 Ω** for 40 Ω traces (UG933 Table 5-2). pinguz97 has these swapped (`DDR3_REVIEW.md` F2) |
| Rterm (addr/cmd/ctrl, to VTT, near the last DRAM) | **40 Ω** |
| Rclk (across CK_P/CK_N at the DRAM) | **80 Ω** |
| DRST_B | not terminated; **4.7 kΩ pull-down** |
| ZQ (DRAM) | **240 Ω 1 %** to GND per DRAM |
| DM | connect (DDR3 data mask) |
| TDQS_P/N (x8 parts) | not supported: leave floating |
| Single-ended DQS | DQS → DQS_P, DQS_N to the DRAM DQS# or a VCCO/2 divider |
| Unused pins (x16, no ECC) | lane 2/3 DQ/DQS/DM unconnected (software pull-ups) |

### 6.3 Routing (UG933 Ch. 5 and Appendix A)

- **Impedance:** 40 Ω single-ended and 80 Ω differential, ±10 %. Every DDR signal except DRST_B is controlled; for
  DDR3, CKE is controlled too.
- **Max length:** 8.55" (217 mm) for data and for addr/cmd.
- **Topology** (Table 5-12):
  - one DRAM: point to point for data, clock and addr/cmd;
  - two DRAMs: data point to point; clock fly-by; addr/cmd fly-by (or balanced T).
  - **Fly-by:** TL0 0–5.3", TL1 between DRAMs 0.35–0.75" (8.9–19 mm), TL2 to Rterm 0–1.0", total ≤ 8.55".
  - **Balanced T:** TL0 ≤ 3", equal branches on one layer, Rterm at the split.
  - Fly-by and point to point are recommended.
- **Delay matching, package delays included** (Table 5-9):
  - DQ/DM to DQS_P/N in the byte ±10 ps;
  - addr/cmd/ctrl to CK_P/N ±10 ps.

  These limits hold only at the SoC's rated speed with memory of the same rating. Appendix A relaxes them:

  | DDR3L, SoC rated 1066 | memory 1866 | memory 1600 | memory 1333 | memory 1066 |
  |---|---|---|---|---|
  | DQ/DM–DQS at 1066 | ±91 ps | ±50 ps | ±45 ps | ±10 ps |
  | addr–CK at 1066 | ±123 ps | ±103 ps | ±83 ps | ±10 ps |
  | both at 800 | ±150 ps | ±150 ps | ±150 ps | ±150 ps |

  (DDR3 at 1.5 V: DQ–DQS 104/91/73/45 ps at 1066; Table A-1.) With MT41K256M16TW-107 (1866) at 1066 MT/s the budget is
  **±91 / ±123 ps**.
- **CK ≥ DQS for every byte.** Write levelling can only delay DQS to meet CK. Read levelling is per byte, so
  bit-to-bit skew inside a byte matters. **Addr/cmd has no training**, only a fixed programmable offset, so keep
  CK–addr skew small.
- **Differential pairs:** match P/N so the crossing falls in the linear part of the edges (a few ps).
- **Swaps:** bit and byte swapping are allowed for DDR3 (Table 5-12 text), but bits stay inside their byte group. On
  a x16 part, "byte swap" means DRAM lower/upper byte ↔ controller lane 0/1, not a move to lanes 2/3.
- Keep each byte (DQ, DM, DQS) on one layer, over a solid GND reference. Change layers only next to a GND return via.
- **Place the DRAM as close as possible** (UG933).
- **Delays in KiCad:**
  - store the Xilinx package delays on the CLG484 pads: pad die length = mean delay / 6 ps/mm, as pinguz97's
    `footprint_add_die_lengths.py` does. KiCad 10 also takes pad-to-die *delays* directly, as the Ti135 repo's
    `tools/pad_to_die.py` writes;
  - measure die to die with `tools/ddr3_review.py` (`--pkg` takes the Vivado package CSV);
  - the per-layer speeds come from `tools/zsolve_cases.py` for the chosen stack-up.

### 6.4 PS7 configuration (Vivado)

- *DDR Configuration*:
  - memory part MT41K256M16 RE-125 (or the closest), DDR3 (low voltage), **32-bit** (2 × x16, 1 GB), 533.333 MHz,
    no ECC;
  - **Board delay** and **DQS to Clock delay** per byte, computed from `ddr3_review.py --json`: the trace delay of
    each byte's DQS and of CK, in ns;
  - write levelling, read gate and read DQS training: **on**.
- Run the FSBL's DDR init, then the Vitis `zynq_dram_test` (bring-up step 3) before anything else.

## 7. Required resistors at a glance

| Net | Part | Value |
|---|---|---|
| MIO2–MIO8 | one resistor each, to VCCO_MIO0 or GND | 20 kΩ (§4.2) |
| PS_POR_B | supervisor output, open drain, + pull-up to VCCO_MIO0 | 4.7–10 kΩ |
| PS_SRST_B | pull-up to VCCO_MIO1 | 4.7–10 kΩ |
| PS_MIO_VREF | divider VCCO_MIO1/2 + 10 nF | 2 × 10 kΩ (as on pinguz97) |
| CFGBVS_0 | to VCCO_0 | direct |
| PUDC_B | to VCCO_34 | ≤ 1 kΩ |
| PROGRAM_B / INIT_B / DONE | pull-ups to VCCO_0 | 4.7 k / 4.7 k / 330 Ω **[verify UG470]** |
| TCK/TMS/TDI | pull-ups to VCCO_0 | 4.7–10 kΩ |
| PS_DDR_VRP / VRN | to GND / to VCCO_DDR | 2 × Z0 (80 Ω for 40 Ω) |
| DRAM ZQ | to GND | 240 Ω 1 % |
| DDR_DRST_B | to GND | 4.7 kΩ |
| SD0 CLK | series, at the MIO pin | 0 Ω placeholder (40–60 Ω) |
| eMMC CMD / DAT0–3 | pull-ups to VCCQ (1V8) | 10–47 kΩ (KIOXIA: CMD 4.7–100 k, DAT 10–100 k) |
| I2C SCL/SDA | pull-ups at the far end | 4.7 kΩ |

## 8. Open items **[verify]**

- [ ] UG470 values for PROGRAM_B / INIT_B / DONE.
- [ ] XADC tie-off if it stays unused (UG480).
- [ ] The PS_POR_B secure-lockdown window (DS187 Figure 1) against the enable chain.
- [ ] Bank 500 voltage (1.8 V + IS25WP128, or 3.3 V + W25Q128JV), §4.3.
- [ ] The full MIO and PL pin plan in Vivado (PLAN.md phase 0.5).
- [ ] The UART path: PS UART on 1.8 V MIO plus a translator, or a PL UART on a 3.3 V bank.

## Sources

- UG933 *Zynq-7000 SoC PCB Design Guide* v1.13.1 (2019): Ch. 3 (decoupling), Ch. 5 (PS power and signalling, DDR),
  Appendix A (derating).
- DS187 *Zynq-7000 SoC (Z-7007S … Z-7020) Data Sheet: DC and AC Switching Characteristics* v1.21 (2020): Table 2,
  power sequencing, Table 7, Tables 18/20/22, Figure 1.
- UG865 *Zynq-7000 SoC Packaging and Pinout* v1.9 (2021): Tables 1-2 and 1-5.
- UG585 *Zynq-7000 SoC Technical Reference Manual* (docs.amd.com, map `27MqOpdJbAciY4iKGTycVA`): *Boot Mode Pin
  Settings*, *External Reset Signal Pins*, *DDR Memory Types, Densities, and Data Widths*, *DDR I/O Signals*.
- Package delays: `scripts/xc7z020clg484_delays.csv` in pinguz97/Zynq-SoM (a Vivado package file export).
