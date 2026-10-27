# zynq_soc_board

Linux-capable control card for the AC in/out lab power supply, based on an AMD **Zynq-7000 (XC7Z020-CLG484)**. It
has 1 GB DDR3L (2 × x16), Gigabit Ethernet (RTL8211F) and eMMC. It plugs into the power supply baseboard
([ac_psu_kicad](https://github.com/johonkanen/ac_psu_kicad)) in the place of the Ti60F225, Agilex 5
([agilex3_soc_control_card](https://github.com/johonkanen/agilex3_soc_control_card)) and Ti135
([efinix_soc_board](https://github.com/johonkanen/efinix_soc_board)) cards.

The SoC, the DDR3 and their routing are not laid out here. They are reused, as a routed block, from the open-source
[juliancoy/zynqPCB](https://github.com/juliancoy/zynqPCB) (MIT); see **[PLAN.md](PLAN.md)** and `NOTICE`. Licence: MIT.

| | |
|---|---|
| [STATUS.md](STATUS.md) | **start here:** status, decisions, next steps, how to run the tools |
| [PLAN.md](PLAN.md) | plan, source survey and decisions |
| [DDR3_REVIEW.md](DDR3_REVIEW.md) | UG933 review of the candidate DDR3 blocks |
| [POWER_BUDGET.md](POWER_BUDGET.md) | rail currents (Vivado `report_power`), regulators, thermal |
| [ZYNQ_PCB_NOTES.md](ZYNQ_PCB_NOTES.md) | Zynq-7000 rules: supplies, sequencing, boot straps, MIO, configuration pins, DDR3 routing |
| `tools/ddr3_review.py` | die-to-die DDR delay and topology check (KiCad Python) |
| `tools/zsolve_cases.py` | impedance and propagation speed for the stack-up (uses `tools/zsolve.py`) |
| `tools/stackup_scan.py` | impedance of one trace width on every layer of the JLC 8-layer templates |
| [REUSE_LOG.md](REUSE_LOG.md) | every change to the reused DDR3 block |
| `vivado/pinplan/` | Vivado pin plan: `pinplan.py` builds and checks the PS7 + PL pins; results in `zynq_pinplan.csv`, `ps7_mio.csv`, `mio.csv` |

Set-up after cloning:

```
git submodule update --init   # tools/jlc (jlc-tools), tools/p2k (proteus2kicad, KiCad 10 env), reference/zynqpcb (DDR3 source)
```

KiCad 10 runs through `tools/p2k/bin/kicad_env.sh` (AppImage at `~/kicad/kicad-10.0.7-x86_64.AppImage`). Vivado 2024.2
runs the pin plan (`vivado/pinplan/pinplan.py`).

Status: planning (phase 0 and the repository set-up done; next: the schematic).
