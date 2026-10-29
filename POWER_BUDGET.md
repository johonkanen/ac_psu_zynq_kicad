# Power budget, regulators and thermal

Written 2026-10-27. The Zynq rails come from **Vivado 2024.2 `report_power`** on the pin-plan design
(`vivado/pinplan/power.tcl`; results in `vivado/pinplan/power_summary.csv`).
- **What the model covers:** the PS7 as configured (both Cortex-A9 at 667 MHz, DDR3L x32 at 533 MHz, QSPI, GEM0, SD0,
  UART, I2C), the 52 PL I/O and the device static power.
- **The PS7 activity is Vivado's default,** which is close to both CPUs and the DDR fully busy: a heavy case for a
  control card.
- **The PL logic does not exist yet,** so its dynamic power is an allowance (below).
- **The other parts** are estimates from their data sheets, marked **[verify]** where no current table was checked.

## Input limit: the baseboard 5V_ISOL rail

The card takes 5V_ISOL from baseboard J12 (our J6), as the Ti60/Agilex/Ti135 cards do.
- Today the rail comes from **U8 = RECOM VXO7805-1000: 5 V, 1 A**, shared with the gate-driver logic (Ti135
  `POWER_BUDGET.md`).
- **The U8 upgrade to a 1.5–2 A part was decided on 2026-10-24** for the Ti135 card and requested from the `ac_psu_kicad`
  session. This card needs it too.

## Zynq rails (Vivado)

Two sizing cases at a fixed junction temperature:
- **typ:** typical process, Tj 85 °C;
- **high:** maximum process, Tj 100 °C, the I-grade limit.

| Zynq supply | V | typ (A) | high (A) | Notes |
|---|---|---|---|---|
| VCCPINT | 1.0 | 0.838 | 1.418 | 0.716 A of it is PS dynamic (CPUs, L2, DDR controller) |
| VCCINT | 1.0 | 0.081 | 0.550 | static only; the PL logic allowance is added below |
| VCCBRAM | 1.0 | 0.006 | 0.030 | |
| VCCPAUX | 1.8 | 0.085 | 0.096 | |
| VCCPLL | 1.8 | 0.017 | 0.020 | |
| VCCAUX | 1.8 | 0.043 | 0.124 | |
| VCCADC | 1.8 | 0.020 | 0.030 | XADC unused |
| VCCO_MIO0 / MIO1 | 1.8 | 0.003 / 0.004 | 0.004 / 0.005 | |
| VCCO_DDR | 1.35 | 0.413 | 0.417 | DDR3L x32 I/O at 533 MHz |
| VCCO_0/13/33/34/35 | 3.3 | 0.035 | 0.035 | 52 PL outputs at Vivado's default activity |
| **Total on chip** | | **1.91 W** | **3.03 W** | of which static 0.35 / 1.47 W |

**PL logic allowance** (PWM, four sigma-delta decimators, ADC and LCD SPI, register file):
- assumed about 30 % of the 7Z020 (16k LUT, 20k FF, 20 DSP, 20 BRAM) at 100 MHz and 12.5 % toggle;
- VCCINT **+0.25 A typ / +0.40 A high**, VCCAUX +0.02 / +0.04 A.

Replace it with `report_power` on the real design.

## Other loads

| Part | Rail | typ (A) | high (A) | Source |
|---|---|---|---|---|
| 2 × MT41K256M16TW-107 (DDR3L) | 1V35 | 0.20 | 0.36 | about IDD3N…IDD4R per chip at moderate / heavy traffic **[verify, Micron data sheet]** |
| VTT termination (24 × 40.2 Ω, TPS51200 from VLDOIN = 1V35) | 1V35 | 0.08 | 0.19 | about 8 mA per line at full imbalance |
| QSPI IS25WP128 | 1V8 | 0.010 | 0.015 | read current **[verify]** |
| eMMC THGAMVG7T13BAIL | 3V3 / 1V8 | 0.05 / 0.03 | 0.10 / 0.06 | VCC (NAND) / VCCQ, HS 50 MHz **[verify]** |
| RTL8211F(DI) at 1000BASE-T | 3V3 | 0.18 | 0.22 | its core and RGMII pad supplies come from internal LDOs (as on the Ti135 card) |
| 33.333 MHz PS_CLK oscillator, 1.8 V | 1V8 | 0.005 | 0.006 | |
| LCD module + backlight (J5) | 3V3 | 0.08 | 0.10 | as on the Ti135 card |
| J3: 10 k pull-downs on 32 pins | 3V3 | 0.005 | 0.011 | 0.33 mA per output that is high |
| LEDs, supervisor, UART translator, EEPROM | 3V3 / 1V8 | 0.011 / 0.002 | 0.020 / 0.003 | |
| ADC block (OPA365, ADS7056, SN74LV4051A) | 3V3_analog (LDO from 5V0) | 0.01 | 0.02 | as on the Ti135 card; the ADS7056 DVDD (SPI I/O, < 1 mA) is on 3V3 here (sheet 12) |

## Per card rail

| Rail | Loads | typ (A) | high (A) | typ / high (W) |
|---|---|---|---|---|
| `1V0` | VCCPINT + VCCINT + VCCBRAM + PL allowance | 1.18 | 2.40 | 1.18 / 2.40 |
| `1V8` | VCCPAUX, VCCPLL, VCCAUX, VCCADC, VCCO_MIO0/1, QSPI, eMMC VCCQ, oscillator, misc | 0.24 | 0.40 | 0.43 / 0.73 |
| `1V35` | VCCO_DDR, 2 × DDR3L, VTT (TPS51200) | 0.69 | 0.97 | 0.94 / 1.31 |
| `3V3` | HR banks, RTL8211F, eMMC VCC, LCD, J3 pull-downs, LEDs | 0.36 | 0.49 | 1.19 / 1.60 |
| `3V3_analog` | ADC block (LDO from 5V0, input power) | 0.01 | 0.02 | 0.05 / 0.10 |
| **Sum of outputs** | | | | **3.79 / 6.14** |
| **At 5 V input, about 85 % efficiency** | | **0.89 A** | **1.44 A** | 4.5 / 7.2 |

**Result:**
- **Typical** use (0.89 A) already takes almost all of today's 1 A 5V_ISOL.
- **The high case needs the planned 1.5–2 A U8.**

The Ti135 estimate was 0.80 / 1.25 A, so the Zynq card is a little heavier, mostly from the dual A9 at 667 MHz and the
DDR3L I/O.

**Ways to cut power, by effect:**
1. **CPU clock** 667 → 333–400 MHz. The model's 0.72 A of PS dynamic is mostly the CPUs at full load. A control card
   spends most of its time idle, so the real draw is lower than modelled anyway.
2. **LCD and backlight** off the budget (about 0.3 W).
3. **Ethernet at 100 Mbit/s** (roughly halves the PHY's power).
4. **DDR at 400 MHz** (about −0.1 W of VCCO_DDR).

## Regulators

**Four TLV62585PDRLR** (3 A, SOT-563, C485118), the same part and cell as on the Ti135 card (Ti135 `POWER_BUDGET.md`:
WPN4020H1R0MT 1 µH, 10 µF in, 22 µF out). VFB = 0.6 V, R2 = 100 kΩ:

| Rail | Vout | R1 (top) | Vout with E96 | high load / 3 A |
|---|---|---|---|---|
| `1V0` | 1.00 V (0.95–1.05) | 66.7 k → **66.5 k** | 0.999 V | 2.40 A, 80 %: use 2 × 22 µF out, as for the Ti135 VCORE |
| `1V8` | 1.80 V | **200 k** | 1.800 V | 0.40 A |
| `1V35` | 1.35 V (DDR3L 1.283–1.45) | 125 k → **124 k** | 1.344 V | 0.97 A |
| `3V3` | 3.30 V | 450 k → **453 k** | 3.318 V | 0.49 A |

Other regulators:
- **VTT / VREF:** the block's TPS51200 (C34771), fed from 1V35. Its enable comes from our power-good chain
  (REUSE_LOG E3).
- **3V3_analog:** NCP163ASN330T1G LDO from 5V0, as on the Agilex/Ti135 cards.

**Order and power-up current:**
- **Sequence:** `1V0` → `1V8` → `3V3`, `1V35` → VTT → PS_POR_B, per `ZYNQ_PCB_NOTES.md` §3.
- **Power-up current** (DS187 Table 6): ICCPINTQ + 70 mA, ICCAUXQ + 60 mA, ICCDDRQ + 100 mA, ICCOQ + 90 mA per bank.
  All of it is within these regulators.

## Thermal

The Zynq is the hot part: 1.8–3.0 W on chip. The CLG484 is a wire-bond package with no lid, and its leakage rises
steeply with temperature.

**Enclosure ambient: 40 °C worst case, with room above the card for a heatsink** (user, 2026-10-27).

Package data (UG865 Table 5-1, XC7Z020-CLG484): **θJB 7.4, θJC 3.35, θJA 18.2 °C/W** (JEDEC board, still air);
13.9 °C/W at 250 LFM.

Vivado still-air estimates (`vivado/pinplan/power_summary.csv`):
- **bare:** θJA 22 °C/W, estimated for this 76 × 65 mm card (smaller than the JEDEC and Vivado boards);
- **heatsink:** θJA 10 °C/W. Estimate: the case path (θJC 3.35 + about 0.5 for thermal tape + about 9–10 for the
  23 × 23 × 33 mm pin-fin in natural convection) runs in parallel with the board path (about 22), which gives
  8–9 °C/W. 10 is used as the conservative value.

The PL allowance (+0.25 / +0.40 W) is not in the Vivado model: add θJA × P, i.e. +2.5…4 °C with the heatsink and
+5…9 °C bare.

| Case | Ambient | Tj | Verdict (I grade, Tj ≤ 100 °C) |
|---|---|---|---|
| typical silicon, bare | 40 °C | 81 °C (+5…9 for the PL) | marginal |
| **worst silicon, bare** | 40 °C | **thermal runaway** (Vivado caps at 125 °C) | **over** |
| typical silicon, heatsink | 40 °C | 57 °C (+3) | OK |
| **worst silicon, heatsink** | **40 °C** | **61 °C (+4)** | **OK, about 35 °C margin** |
| worst silicon, heatsink | 60 °C | 85 °C | OK |
| worst silicon, heatsink | 70 °C | 99.6 °C | at the limit |

**Decided 2026-10-27: a heatsink is fitted. It is required, not optional:** on this card, worst-case silicon without
it is not stable even at 40 °C.

### Heatsink: Wakefield-Vette 960-23-33-D-AB-0

The same part the Agilex card reserved:
- DigiKey 345-1804-ND; 23 × 23 mm footprint, 33 mm pin fins, black anodised aluminium;
- 2.8 °C/W at 200 LFM (sink only);
- **two plastic push pins on the diagonal** with compression springs.

Drawing: Wakefield-Vette *960 Series Plastic Push Pin Heat Sinks*, 23 mm page.

| Item | Value |
|---|---|
| PCB holes | **2 × Ø3.18 mm (0.125")**, on the diagonal at **(+14.93, +14.93) and (−14.93, −14.93) mm** from the heatsink centre, i.e. a 29.85 mm square pitch. Place the centre on U20's centre |
| Heatsink base | 24.00 × 23.50 mm; with the pin tabs it is 36.71 mm across the diagonal. The CLG484 body is 19 × 19 mm, so the base overhangs 2.5 mm per side: nothing taller than the package (about 1.5 mm) under the base |
| Hole type on this card | **NPTH Ø3.2 mm** (JLC NPTH ±0.05 mm), with a copper keep-out ring on all layers. The Agilex card uses plated GND vias, 5 mm pad / 3.0 mm drill |
| Keep-out | Ø6 mm around each hole on F.Cu and B.Cu for the pin head, spring and barb; no tracks within 0.5 mm of the hole wall on any layer |
| Which diagonal | In the juliancoy block frame, **(+,+)/(−,−)** around U20: no block copper within 3 mm. The other diagonal cuts the DDR3_VTT_EN trace. Keep the same diagonal relative to the block when it is placed (it rotates with the block) |
| Interface | thermal tape or pad between heatsink and package (the "-0" suffix means no interface material is fitted) |

**Checked against the Agilex card** (`~/dev/agilex3_soc_control_card`, read only from here):
- **Position: OK.** The holes are at (+14.98, +14.84) and (−14.88, −15.01) mm from U7, i.e. the ±14.93 mm pattern
  within 0.1 mm. Commit `3b15c92` "move heat sink pins to match 960-23-33-D-AB-0".
- **Size: wrong.** The holes are **3.0 mm drills, smaller than the Ø3.18 mm the push pins need.** The pins may not go
  in, or may crack.
- Its own board note still says "heatsink mounting holes are just a sketch". To report to that card's session: the
  drill should be about 3.2 mm (NPTH, or PTH finished at ≥ 3.18 mm).

Still to check:
- **[verify]** the push-pin grip range for our stack: 1.6 mm PCB + about 1.5 mm CLG484 + tape. The datasheet has no
  number; Mouser's page on the 960 pins gives a 4–9.4 mm stack-up range.
- ~~[verify] how far the barbs stick out below the card~~: a few mm, fits the gap (user, 2026-10-29). H1 is over
  baseboard U17 (2.65 mm room; `MECHANICAL.md`).

### Other thermal measures

- **Thermal vias:** GND vias in the BGA's centre GND balls into In1/In3/In5, plus GND pours on F/B around the SoC.
- **CPU clock:** a software cap (cpufreq) is still available as a fallback.
- **Measure** the die temperature on the first board with the XADC on-chip sensor, readable from Linux.

## Open

- [x] ~~The enclosure ambient~~ 40 °C worst case, room for a heatsink (2026-10-27): Wakefield 960-23-33-D-AB-0.
- [ ] Push-pin grip range. (~~Barb protrusion~~: fits, user 2026-10-29.)
- [ ] Re-run `vivado/pinplan/power.tcl` on the real design: replace the PL allowance, and set the real CPU clock.
- [ ] Check the DDR3L, eMMC and QSPI currents against their data sheets.
- [ ] Measure the 5V_ISOL current and the die temperature on the first board.
- [ ] Confirm the U8 upgrade to 1.5–2 A in the baseboard redraw (`ac_psu_kicad`).
