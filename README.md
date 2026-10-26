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
| [PLAN.md](PLAN.md) | plan, source survey and decisions |
| [DDR3_REVIEW.md](DDR3_REVIEW.md) | UG933 review of the candidate DDR3 blocks |
| [ZYNQ_PCB_NOTES.md](ZYNQ_PCB_NOTES.md) | Zynq-7000 rules: supplies, sequencing, boot straps, MIO, configuration pins, DDR3 routing |
| `tools/ddr3_review.py` | die-to-die DDR delay and topology check (KiCad Python) |
| `tools/zsolve_cases.py` | impedance and propagation speed for the stack-up (uses `tools/zsolve.py`) |

Status: planning.
