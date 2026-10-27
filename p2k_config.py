"""proteus2kicad (tools/p2k) configuration of the Zynq-7000 (XC7Z020-CLG484) control card.

This board is a new design, not a Proteus conversion: only the schematic/symbol helpers
(make_skeleton, symgen, sheetkit/sch_builder, render_sheet) and later build_pcb are used.
Sheet 1 is the DDR3 block imported from juliancoy/zynqPCB (tools/sheets/01_ddr3.py): it keeps the source's
reference designators (all below 200). Our sheets use sheet x 100 ranges (R201.. on sheet 2).
Mechanical reference coordinates (outline, J3/J6/J9 positions) are in MECHANICAL.md.
"""

PROJECT = "zynq_card"  # KiCad project / library name

# (sheet number, sheet name, file). Reference designators use sheet x 100 ranges, except sheet 1 (the block).
SHEETS = [
    (1, "ddr3", "01_ddr3.kicad_sch"),
    (2, "pwr_input", "02_pwr_input.kicad_sch"),
    (3, "pwr_rails", "03_pwr_rails.kicad_sch"),
    (4, "pwr_seq", "04_pwr_seq.kicad_sch"),
    (5, "soc_power", "05_soc_power.kicad_sch"),
    (6, "soc_config", "06_soc_config.kicad_sch"),
    (7, "clocks", "07_clocks.kicad_sch"),
    (8, "qspi", "08_qspi.kicad_sch"),
    (9, "ethernet", "09_ethernet.kicad_sch"),
    (10, "emmc", "10_emmc.kicad_sch"),
    (11, "soc_pl", "11_soc_pl.kicad_sch"),
    (12, "adc", "12_adc.kicad_sch"),
    (13, "connectors", "13_connectors.kicad_sch"),
]
SCH_TITLE = "Zynq-7000 control card"
SCH_COMPANY = "Jari Honkanen"
SCH_REV = "0.1"
SCH_COMMENT = "XC7Z020-CLG484 control card for the AC lab PSU baseboard"
SCH_NOTE = ("XC7Z020-CLG484 control card. Plan: PLAN.md, device rules: ZYNQ_PCB_NOTES.md,\n"
            "mechanics: MECHANICAL.md, pin plan: vivado/pinplan/zynq_pinplan.csv.\n"
            "Sheet 1 (ddr3) is the routed block from juliancoy/zynqPCB (MIT, NOTICE); changes in REUSE_LOG.md.")
