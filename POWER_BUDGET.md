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
| ADC block (OPA365, ADS7056, SN74LV4051A) | 3V3_analog (LDO from 5V0) | 0.01 | 0.02 | as on the Ti135 card |

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

Vivado still-air estimates. "bare" is θJA 22 °C/W, estimated for this 76 × 65 mm card; Vivado's own 4" × 4" board
gives 17.3 °C/W. "heatsink" is θJA 10 °C/W, a small BGA heatsink with thermal tape. The PL allowance is not included:
add about +5 °C bare.

| Case | Ambient | Tj | Verdict (I grade, Tj ≤ 100 °C) |
|---|---|---|---|
| typical silicon, bare | 40 °C (Vivado θJA 17.3) | 71 °C | OK |
| typical silicon, bare | 50 °C | 93 °C | marginal |
| typical silicon, bare | 60 °C | 108 °C | **over** |
| worst silicon, bare | 50 °C | thermal runaway (Vivado caps at 125 °C) | **over** |
| typical silicon, heatsink | 60 °C | 79 °C | OK |
| worst silicon, heatsink | 60 °C | 85 °C | OK |
| worst silicon, heatsink | 70 °C | 99.6 °C | at the limit |

**Consequences for the layout:**
- **Plan a heatsink:** a 19 × 19 mm BGA heatsink on the top of U20 with thermal tape or a clip. Keep the area around
  the SoC on F.Cu free of tall parts, and check the height in the enclosure.
- **Thermal vias:** GND vias in the BGA's centre GND balls into In1/In3/In5, plus copper pours on F/B around the SoC.
  This lowers θJA, especially for the bare case.
- **CPU clock:** cap it in software (cpufreq) if the enclosure runs hot; at 333 MHz the PS dynamic roughly halves.
- **Measure** the Zynq die temperature on the first board: XADC on-chip temperature, readable from Linux.

## Open

- [ ] **The enclosure ambient** around the control card, and the space above it for a heatsink.
- [ ] Re-run `vivado/pinplan/power.tcl` on the real design: replace the PL allowance, and set the real CPU clock.
- [ ] Check the DDR3L, eMMC and QSPI currents against their data sheets.
- [ ] Measure the 5V_ISOL current and the die temperature on the first board.
- [ ] Confirm the U8 upgrade to 1.5–2 A in the baseboard redraw (`ac_psu_kicad`).
