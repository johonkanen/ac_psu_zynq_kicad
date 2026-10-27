# PS7 settings for the control card (sourced by the generated build.tcl). See ZYNQ_PCB_NOTES.md §4 and §6.5.
#
# DDR trace lengths are from tools/ddr3_review.py on the juliancoy block (JLC081611-7628 speeds), SoC ball -> DRAM ball,
# with REUSE_LOG.md E1 applied (CK +3.77 mm on average). Bytes 0/1 go to U16 and bytes 2/3 to U15, so their CK lengths
# differ. The package delays are added by the IP (PCW_PACKAGE_DDR_*). Propagation: 6.63 ps/mm on In2/In4 = 168 ps/inch.
#
# The training start values are set directly (UG585 "DRAM Training"; the IP does not fill them from the lengths in batch
# mode, and ps7_init uses these fields, not PCW_PACKAGE_DDR_*):
#   DQS_TO_CLK  = CK - DQS delay at the DRAM (write levelling start), die to die, package included as UG585 asks;
#   BOARD_DELAY = SoC-DRAM delay = (CK + DQS) / 2, die to die (read-gate training uses 2 x board delay: CK out, DQS back).
# From ddr3_review.py --json (total_ps, Xilinx package delays, JLC081611-7628 speeds) with REUSE_LOG E1 (+25 ps on CK):
#   byte 0: CK 317.2 ps, DQS 292.2   byte 1: CK 317.2, DQS 206.2   byte 2: CK 403.1, DQS 222.2   byte 3: CK 403.1, DQS 238.7
# Cross-check: Vivado's own package-inclusive values from the lengths (PCW_PACKAGE_DDR_DQS_TO_CLK_DELAY_n) come out
# 0.031 / 0.117 / 0.187 / 0.164 ns.
set PS7_CONFIG [dict create \
  CONFIG.PCW_PRESET_BANK0_VOLTAGE            {LVCMOS 1.8V} \
  CONFIG.PCW_PRESET_BANK1_VOLTAGE            {LVCMOS 1.8V} \
  CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ      {33.333333} \
  CONFIG.PCW_APU_PERIPHERAL_FREQMHZ          {666.666666} \
  CONFIG.PCW_QSPI_PERIPHERAL_ENABLE          {1} \
  CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE       {1} \
  CONFIG.PCW_QSPI_GRP_FBCLK_ENABLE           {1} \
  CONFIG.PCW_QSPI_PERIPHERAL_FREQMHZ         {200} \
  CONFIG.PCW_ENET0_PERIPHERAL_ENABLE         {1} \
  CONFIG.PCW_ENET0_ENET0_IO                  {MIO 16 .. 27} \
  CONFIG.PCW_ENET0_GRP_MDIO_ENABLE           {1} \
  CONFIG.PCW_ENET0_GRP_MDIO_IO               {MIO 52 .. 53} \
  CONFIG.PCW_SD0_PERIPHERAL_ENABLE           {1} \
  CONFIG.PCW_SD0_SD0_IO                      {MIO 40 .. 45} \
  CONFIG.PCW_SDIO_PERIPHERAL_FREQMHZ         {50} \
  CONFIG.PCW_UART1_PERIPHERAL_ENABLE         {1} \
  CONFIG.PCW_UART1_UART1_IO                  {MIO 48 .. 49} \
  CONFIG.PCW_I2C0_PERIPHERAL_ENABLE          {1} \
  CONFIG.PCW_I2C0_I2C0_IO                    {MIO 50 .. 51} \
  CONFIG.PCW_GPIO_MIO_GPIO_ENABLE            {1} \
  CONFIG.PCW_USB0_PERIPHERAL_ENABLE          {0} \
  CONFIG.PCW_USE_M_AXI_GP0                   {0} \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ        {100} \
  CONFIG.PCW_EN_CLK0_PORT                    {1} \
  CONFIG.PCW_UIPARAM_DDR_MEMORY_TYPE         {DDR 3 (Low Voltage)} \
  CONFIG.PCW_UIPARAM_DDR_PARTNO              {MT41K256M16 RE-125} \
  CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH           {32 Bit} \
  CONFIG.PCW_UIPARAM_DDR_FREQ_MHZ            {533.333333} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_WRITE_LEVEL   {1} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_READ_GATE     {1} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_DATA_EYE      {1} \
  CONFIG.PCW_UIPARAM_DDR_USE_INTERNAL_VREF   {0} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_0_LENGTH_MM   {37.78} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_1_LENGTH_MM   {37.78} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_2_LENGTH_MM   {50.76} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_3_LENGTH_MM   {50.76} \
  CONFIG.PCW_UIPARAM_DDR_DQS_0_LENGTH_MM     {31.94} \
  CONFIG.PCW_UIPARAM_DDR_DQS_1_LENGTH_MM     {18.59} \
  CONFIG.PCW_UIPARAM_DDR_DQS_2_LENGTH_MM     {21.63} \
  CONFIG.PCW_UIPARAM_DDR_DQS_3_LENGTH_MM     {18.77} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_0_PROPOGATION_DELAY {168} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_1_PROPOGATION_DELAY {168} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_2_PROPOGATION_DELAY {168} \
  CONFIG.PCW_UIPARAM_DDR_CLOCK_3_PROPOGATION_DELAY {168} \
  CONFIG.PCW_UIPARAM_DDR_DQS_0_PROPOGATION_DELAY   {168} \
  CONFIG.PCW_UIPARAM_DDR_DQS_1_PROPOGATION_DELAY   {168} \
  CONFIG.PCW_UIPARAM_DDR_DQS_2_PROPOGATION_DELAY   {168} \
  CONFIG.PCW_UIPARAM_DDR_DQS_3_PROPOGATION_DELAY   {168} \
  CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_0  {0.025} \
  CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_1  {0.111} \
  CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_2  {0.181} \
  CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_3  {0.164} \
  CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY0        {0.305} \
  CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY1        {0.262} \
  CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY2        {0.313} \
  CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY3        {0.321} \
]

# MIO electrical settings (UG933 / UG585): RGMII as HSTL 1.8 V (receivers referenced to PS_MIO_VREF = 0.9 V), no pull-ups
# on RGMII; fast slew on QSPI, RGMII and SD0.
foreach i {16 17 18 19 20 21 22 23 24 25 26 27} {
  dict set PS7_CONFIG CONFIG.PCW_MIO_${i}_IOTYPE {HSTL 1.8V}
  dict set PS7_CONFIG CONFIG.PCW_MIO_${i}_PULLUP {disabled}
}
foreach i {1 2 3 4 5 6 8 16 17 18 19 20 21 22 23 24 25 26 27 40 41 42 43 44 45} {
  dict set PS7_CONFIG CONFIG.PCW_MIO_${i}_SLEW {fast}
}
