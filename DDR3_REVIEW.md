# DDR3 review of the CLG484 source boards against UG933

Written 2026-10-26 (PLAN.md phase 0.1). Both CLG484 sources were checked against the Xilinx rules for the PS DDR
interface:
- **pinguz97/Zynq-SoM**, commit `ad96951`;
- **juliancoy/zynqPCB**, the fallback.

The rule set is in `ZYNQ_PCB_NOTES.md` §6.

**Result: the pinguz97 DDR block cannot be used as it is.** It has two functional faults:
- **F1:** the DRAM is wired to the wrong byte lanes;
- **F2:** VRP and VRN are swapped.

Either one alone breaks the interface. A builder of that board reports DDR test failures in the source's issue #3.
**juliancoy/zynqPCB passes every check that could be made.** Its open points are an unknown impedance and no hardware
test.

## Method

- **Delays:** `tools/ddr3_review.py` (run with KiCad 10's Python) walks the copper of every DDR net from the SoC ball to
  the DRAM ball: segments, arcs and vias, through a series resistor when there is one. It sums:
  - the package delay: the footprint's pad die length × 6 ps/mm, or `--pkg` with the Xilinx package delay CSV;
  - the copper: per-layer speeds from `tools/zsolve_cases.py` (field solve of JLC08121H-1080A): outer SE 5.95 ps/mm,
    outer differential 5.75 ps/mm, inner 6.75 ps/mm. These match the source's own Si9000 numbers (5.988 / 5.813 / 6.76);
  - vias: about 7 ps/mm of barrel.

  Skews are die to die (SoC die to the DRAM ball). DRAM package delays are not included.
- **Pin map:** each SoC ball's net was compared with the Xilinx function of that ball. The source's
  `scripts/xc7z020clg484_delays.csv` is the Vivado package file: bank, ball, site, function, min/max delay.
- **Other checks:** spacing, return vias, decoupling and termination parts were checked with small pcbnew scripts
  (the session's scratch scripts, not kept), and DRC with KiCad 10.0.7.
- **Limits:** UG933 Table 5-9 gives ±10 ps, but only for running at the SoC's rated speed with memory of the same
  rating. For MT41K256M16TW-107 (DDR3L-1866) run at 1066 MT/s, UG933 Appendix A (DDR3L) gives:
  - **DQ/DM–DQS ±91 ps**;
  - **address/command–CK ±123 ps**;
  - at 800 MT/s, ±150 ps for both.

  For 1600-rated memory at 1066 the limits are ±50 / ±103 ps.

## pinguz97/Zynq-SoM

| # | Check (source of the rule) | Board | Verdict |
|---|---|---|---|
| **F1** | **x16 data on PS_DDR_DQ[15:0], byte lanes 0 and 1** (UG585 *DDR I/O Signals*: "16-bit Data bus: [15:0]"; UG933: keep byte lanes together) | The DRAM is on **lanes 2 and 3**. Net `DDR_DQ0–7`/`DQS0`/`DM0` is on balls U1, AA1, U2, Y3, W3, AA3, W1, Y1 / V2, W2 / AA2 = PS_DDR_DQ24–31 / DQS3 / DM3. Net `DDR_DQ8–15`/`DQS1`/`DM1` is on M1, M2, N3, R1, R3, T1, T2, T3 / N2, P2 / P1 = PS_DDR_DQ16–23 / DQS2 / DM2. The lane 0/1 balls (B1…L3) are unconnected. The source's symbol pin names match Xilinx (0 mismatches), so this is the schematic, not a library error | **FAIL**: the controller drives lanes 0/1 in 16-bit mode, and 32-bit mode cannot train with lanes 0/1 open |
| **F2** | **VRP to GND, VRN to VCCO_DDR** (UG933 *PS_DDR_VRN, PS_DDR_VRP*; UG585 Table 10-3) | R46 VRN (M7) → GND, R47 VRP (N7) → +1V35: **swapped**. Also noted by a commenter on issue #3 (2026-04-17) | **FAIL**: DCI calibrates against the wrong rails |
| F3 | Impedance 40 Ω SE / 80 Ω diff ±10 % (UG933 Table 5-10) | Routed as 50 Ω (its rules are named `50ohm_inner`). Solved for its stack-up: F/B 0.12 mm → 50.6 Ω, In5 0.135 mm → 50.3 Ω, pairs 0.10/0.20 → 100.5 Ω (outer) / 105.8 Ω (In5). 40 Ω would take about 0.20 mm outer and over 0.18 mm on In5 | deviation: consistent within itself (VRP/VRN 100 Ω = 2 × 50 Ω, CK 100 Ω) |
| F4 | Addr/cmd/ctrl terminated with 40 Ω to VTT at the load (UG933 Table 5-7) | **22 Ω series resistors** 4–17 mm from the SoC (`*_T` is the net after the resistor), no VTT rail at all. UG933 Ch. 4 notes that the SSTL drivers are 40–50 Ω and SI is better *without* source-series resistors | deviation. The proven PlutoSDR clone runs this topology (one x16, point to point) with no termination at all, so it can work; it needs an SI check |
| F5 | DQ/DM–DQS per byte (Table 5-9, App. A) | lane "0": +0.2…+0.5 ps; lane "1": 0.0 ps. DQS P/N 0.1 / 0.0 ps | PASS (very tightly tuned) |
| F6 | Addr/cmd–CK (Table 5-9, App. A) | −22.8…−20.5 ps; CK P/N 0.0 ps | PASS against ±123 ps (a uniform 21 ps offset; the ±10 ps rated-speed limit does not apply) |
| F7 | CK ≥ DQS per byte (UG933, for write levelling) | CK 311 ps vs DQS 201 / 169 ps | PASS |
| F8 | Topology for one device: point to point (Table 5-12); max length 8.55" (Table 5-8) | point to point, 25–39 mm | PASS |
| F9 | ZQ 240 Ω; DRST_B 4.7 kΩ pull-down; CK differential termination at the DRAM | R45 240 Ω; R48 4.7 kΩ to GND; R50 100 Ω on B.Cu under U1 (UG933 Rclk 80 Ω for 80 Ω lines; 100 Ω matches its 100 Ω pair) | PASS |
| F10 | VREF = VCCO_DDR/2, 0.01–0.47 µF; a divider per IC recommended (Table 5-6 note) | one 10 k/10 k divider (R88/R89) for SoC and DRAM, 4 × 47 nF | PASS (minor: shared divider) |
| F11 | Each byte on one layer; DQ swaps only inside a byte (Table 5-12 text) | byte "0" on F.Cu, byte "1" on In5; DQ order swapped inside the lanes | PASS |
| F12 | Crosstalk spacing (rule of thumb ≥ 2 h edge to edge) | outside the BGAs: F/B ≥ 0.15 mm (h = 0.076 mm), In5 ≥ 0.2 mm (h = 0.15–0.20 mm) | PASS on F/B, marginal on In5 |
| F13 | Return vias next to signal vias | 50 of 85 DDR vias have their nearest GND via 1.0–2.0 mm away | minor |
| F14 | VCCO_DDR decoupling (UG933 Table 3-2, CLG484 Z-7020: 1 × 100 µF, 1 × 4.7 µF, 4 × 0.47 µF) | on +1V35: 100 µF, 47 µF, 2 × 4.7 µF, 4 × 470 nF, 12 × 47 nF (shared with the DRAM) | PASS |
| F15 | Data rate: PS DDR3L max 1066 Mb/s for every grade (DS187); memory rated ≥ that | MT41K256M16TW-107 (1866) | PASS |

**What a fix would take:**
- **F2** is trivial: swap the far ends of R46 and R47.
- **F1 is not trivial.** The lane 0/1 balls are in rows B–L of columns 1–3. The routed bytes go to rows M–AA (the
  author picked the lanes nearest the DRAM).
  - Moving the data means re-routing both bytes, about 22 nets, to the other half of bank 502.
  - It probably also means moving the DRAM north, which disturbs the address/CK copper.
  - That is most of the DDR routing that the reuse was meant to avoid.

**What is still worth taking from pinguz97:**
- the die-length CLG484 footprint, and `scripts/calculate_track_delays.py`;
- the stack-up and impedance solution;
- the tuning approach.

The delays in its footprint agree exactly with the Xilinx CSV: both runs give identical skews.

## juliancoy/zynqPCB (fallback)

2 × MT41K256M16HA-125:E (DDR3L-1600, x32, 1 GB). Fly-by: SoC → U16 (lanes 0/1) → U15 (lanes 2/3) → 40.2 Ω to VTT.
The VTT comes from a TPS51200. 8 layers, KiCad 5 file with no stack-up, MIT licence.

| Check | Board | Verdict |
|---|---|---|
| Byte lanes | ball lane = net lane for all 44 DQ/DM/DQS balls (U16 on lanes 0/1, U15 on lanes 2/3) | PASS |
| VRP/VRN | VRN (M7) → 80.6 Ω → +1V35; VRP (N7) → 80.6 Ω → GND | PASS (UG933 80 Ω) |
| Termination | addr/cmd/ctrl 40.2 Ω to VTT 0.6 mm after U15; CK 80.6 Ω at U15; ZQ 240 Ω each; DRST_B 4.7 kΩ; CKE not terminated | PASS (UG933 Table 5-7) |
| Fly-by geometry (Fig. 5-8: TL0 0–5.3", TL1 0.35–0.75", TL2 0–1.0") | TL0 ≈ 38 mm (1.5"), TL1 ≈ 13 mm (0.51"), TL2 ≈ 0.6 mm | PASS |
| DQ/DM–DQS, die to die with the Xilinx package delays | byte 0 −10.8…−0.9, byte 1 0…+14.8, byte 2 −8.0…−0.5, byte 3 −1.1…+12.4 ps. DQS P/N 4.4 / 5.4 / 2.5 / 9.1 ps | PASS against ±50 ps (1600 parts at 1066) and ±91 ps (1866 parts) |
| Addr/cmd–CK | at U16 +1.0…+25.2 ps, at U15 +6.2…+24.1 ps; CK P/N 7.3 ps | PASS against ±103 ps |
| CK ≥ DQS | byte 0 **+0.3 ps** (the minimum), byte 1 +88, bytes 2/3 +159 / +143 ps | PASS, no margin on byte 0 |
| VREF | 10 k/10 k divider into the TPS51200 REFIN; SoC VREF0/1 and both DRAMs on it, 8 caps | PASS |
| Impedance | every DDR trace is 0.102 mm, and the file has no stack-up. **Resolved 2026-10-26: on JLC081611-7628, In2/In4 are 39.5 Ω SE / 71.4 Ω diff and In6 is 45.5 / 74.6 Ω** (`ZYNQ_PCB_NOTES.md` §6.4) | PASS on that stack-up |
| Tested | README: "DDR3 PS Memory: Untested" | open |

Notes:
- The VTT regulator enable is driven from PS_MIO14 (bank 500), with a 20 k pull-up to 3V3. That is fine with bank 500
  at 3.3 V. Not part of a DDR-only block.
- Four U15 nets (A1, DM3, DQ20, WE#) could not be walked by the first version of the script. **Resolved 2026-10-27:**
  in each, a track ends inside a via's pad but up to 0.1 mm off its centre. The copper is connected; the script now
  joins such ends.
- **512 MB from this block:** fit only U16 (lanes 0/1) and run 16-bit. The empty U15 site leaves the 13 mm fly-by
  continuation to the VTT resistors, which is still a terminated line, plus unused lane 2/3 stubs (UG933 Table 5-5:
  unused DQ unconnected, pulled up by software). Fitting U15 too gives 1 GB with no layout change.
- The block (SoC + 2 DRAMs + VTT parts + copper) is 36 × 44 mm.

## juliancoy block on the chosen stack-up (2026-10-27)

Re-run with the JLC081611-7628 speeds:

```
ddr3_review.py --pkg <Xilinx CSV> --ps-outer 5.86 --ps-outer-diff 5.86 --ps-inner 6.63 --ps-layer SIGNAL4=6.80
```

Every DDR net is now walked on both DRAMs.

| Check | U16 (lanes 0/1) | U15 (lanes 2/3) | Limit at 1066 (1866 parts) | Verdict |
|---|---|---|---|---|
| DQ/DM − DQS | byte 0 −11.0…−0.9, byte 1 −0.3…+14.1 ps | byte 2 −8.3…+2.2, byte 3 −1.5…+19.6 ps | ±91 ps | PASS |
| DQS P/N | 4.3 / 5.4 ps | 2.5 / 8.9 ps | crossing in the linear region | PASS (DQS3: optional fix E2) |
| Addr/cmd − CK | +0.6…+29.1 ps | +3.9…+31.9 ps | ±123 ps | PASS |
| CK P/N | 7.1 ps | 7.2 ps | – | **fix (E1)** |
| CK − DQS | byte 0 **+0.0 ps**, byte 1 +85.9 ps | byte 2 +155.9, byte 3 +139.5 ps | CK ≥ DQS | **byte 0 has no margin: fix (E1)** |

**Fix E1 (`REUSE_LOG.md`):** lengthen the CK pair in its trunk before U16:
- CK_P +4.30 mm, CK_N +3.23 mm on In2;
- result: CK = DQS0 + 25 ps, CK P/N matched;
- addr/cmd − CK becomes about −24…+7 ps, still centred well inside ±123 ps;
- there is room beside two straight runs of the trunk.

The 25 ps margin covers the ±3 % propagation tolerance on the ~300 ps path. CK (In2) and DQS0 (In4) sit in identical
dielectrics in this symmetric stack-up, so their errors largely track each other.

## Recommendation

**Decided 2026-10-26 (user): switch to juliancoy/zynqPCB, both DRAMs fitted (1 GB), MIT licence.** The open points
from item 2 below are tracked in PLAN.md phase 0.1.

1. **Do not use the pinguz97 DDR copper.** Report F1 and F2 on its issue #3, since they explain that user's failures.
2. **Switch the block source to juliancoy/zynqPCB** (MIT). It is the only routed CLG484 DDR3 with no functional
   error found.
   - Check its impedance once the stack-up is chosen. 0.102 mm will be about 50–57 Ω on a thin 8-layer stack.
   - Either keep it as is (NASR-M runs 50/100 Ω DDR3 tracks and passes the Zynq DDR test, per its ERRATA.txt), or
     re-fit the widths outside the BGA with a stack-up that brings 0.102 mm closer to 40 Ω.
   - Re-time byte 0 so that CK ≥ DQS keeps some margin.
3. **Decide 512 MB (U16 only) or 1 GB (both).** The board is the same; only the BOM changes.
4. Whatever the source, the PS7 DDR settings must use board delays from `ddr3_review.py --json` (Vivado *DDR
   Configuration → Board delay* per byte: DQS-to-CLK and board delay).
