# zynq_soc_board

Linux-capable control card for the AC in/out lab power supply, based on an AMD **Zynq-7000 (XC7Z020-CLG484)**. It
has 512 MB DDR3L, Gigabit Ethernet (RTL8211F) and eMMC. It plugs into the power supply baseboard
([ac_psu_kicad](https://github.com/johonkanen/ac_psu_kicad)) in the place of the Ti60F225, Agilex 5
([agilex3_soc_control_card](https://github.com/johonkanen/agilex3_soc_control_card)) and Ti135
([efinix_soc_board](https://github.com/johonkanen/efinix_soc_board)) cards.

The SoC, the DDR3 and their routing are not laid out here. They are reused from an open-source Zynq board, as a
routed block; see **[PLAN.md](PLAN.md)**.

Status: planning.
