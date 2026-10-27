#!/usr/bin/env python3
"""Project symbol library lib/zynq_card.kicad_sym (tools/p2k symgen).

    tools/gen_symbols.py           write the library
    tools/gen_symbols.py --check   fail if it is out of date

Sources: KiCad 10 standard symbols (copied and renamed), and the block's symbols from juliancoy/zynqPCB
(reference/zynqpcb/DFTBoard-cache.lib, KiCad 5, upgraded with `kicad-cli sym upgrade` into work/): the XC7Z020-CLG484
(all 9 units, used by sheet 1 and by our SoC sheets), the MT41K256M16 FBGA-96 and the TPS51200. The eMMC, RJ45,
Ethernet PHY, QSPI flash and ADS7056 symbols are the Ti135 card's (efinix_soc_board/tools/gen_symbols.py).
The block's passives (R, R_Small, C_Small, LED, FerriteBead_Small) use the KiCad 10 symbols; tools/sheets/_legacy.py
checks that their pins sit where the KiCad 5 ones did.
"""
import copy
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.symgen import IN, OUT, PAS, PI, PO, Sym, box, find, find_all, from_std, load, power, rename, run, set_prop  # noqa: E402

TI135_LIB = os.path.expanduser("~/dev/efinix_soc_board/lib/ti135_card.kicad_sym")

JC_LIB = os.path.join(ROOT, "reference", "zynqpcb", "DFTBoard-cache.lib")
JC_SYM = os.path.join(ROOT, "work", "jc_cache.kicad_sym")

# juliancoy cache name -> (our name, reference, value, description)
JC_SYMBOLS = {
    "xilinx7_xc7z020clg484": ("XC7Z020-CLG484", "U", "XC7Z020-1CLG484I",
                              "AMD Zynq-7000 SoC, CLG484 (symbol from juliancoy/zynqPCB, MIT)"),
    "DFTBoard-rescue_MT41K256M16HA-125_E-MT41K256M16HA-125_E": (
        "MT41K256M16-FBGA96", "U", "MT41K256M16TW-107:P",
        "4 Gb DDR3L x16, 96-ball FBGA (symbol from juliancoy/zynqPCB, MIT)"),
    "tps51200DRCR_TPS51200DRCR": ("TPS51200", "U", "TPS51200DRCR",
                                  "DDR termination regulator, VTT/VREF (symbol from juliancoy/zynqPCB, MIT)"),
}


def jc_cache():
    """The juliancoy cache library as a KiCad 10 .kicad_sym (re-upgraded when the source is newer)."""
    if not os.path.exists(JC_SYM) or os.path.getmtime(JC_SYM) < os.path.getmtime(JC_LIB):
        os.makedirs(os.path.dirname(JC_SYM), exist_ok=True)
        subprocess.run([os.path.join(TOOLS, "p2k", "bin", "kicad-cli"), "sym", "upgrade", "-o", JC_SYM, JC_LIB],
                       check=True, capture_output=True)
    return {s[1]: s for s in find_all(load(JC_SYM), "symbol")}


def from_jc(cache, name):
    new, ref, value, desc = JC_SYMBOLS[name]
    sym = rename(copy.deepcopy(cache[name]), new)
    set_prop(sym, "Reference", ref)
    set_prop(sym, "Value", value)
    set_prop(sym, "Footprint", "")
    set_prop(sym, "Datasheet", "")
    set_prop(sym, "Description", desc)
    sym[:] = [c for c in sym if not (isinstance(c, list) and c[0] == "property"
                                     and c[1] not in ("Reference", "Value", "Footprint", "Datasheet", "Description"))]
    # hidden power pins become passive (they are wired explicitly on our sheets)
    for sub in find_all(sym, "symbol"):
        for p in find_all(sub, "pin"):
            if find(p, "hide") and str(p[1]) in ("power_in", "power_out"):
                p[1] = Sym("passive")
    return sym


def avc4t774():
    """SN74AVC4T774RSVR (C779392), the JTAG shifter of the Agilex 3 card (~/dev/ti60f225_control_card): RSV
    (UQFN-16) pin numbers, the same as the SN74AXC4T774RSV (TI SCES898C Table 4-1). DIRx/OE are referenced to VCCA."""
    io, inp = "bidirectional", "input"
    left = [(14, "VCCA", PI), (15, "DIR1", inp), (16, "DIR2", inp), (5, "DIR3", inp), (6, "DIR4", inp),
            (7, "~{OE}", inp), (1, "A1", io), (2, "A2", io), (3, "A3", io), (4, "A4", io), (8, "GND", PI)]
    right = [(13, "VCCB", PI), None, None, None, None, None, (12, "B1", io), (11, "B2", io), (10, "B3", io),
             (9, "B4", io)]
    s = box("SN74AVC4T774", "U", left, right, value="SN74AVC4T774RSVR",
            desc="4-bit dual-supply translator, per-bit direction, UQFN-16 (RSV). DIRx = H: A to B")
    set_prop(s, "Datasheet", "https://www.ti.com/lit/ds/symlink/sn74avc4t774.pdf")
    return s


def tlv62585p():
    """TLV62585PDRLR (SOT-563), the Ti135 card's generated symbol (efinix_soc_board/tools/gen_symbols.py)."""
    left = [(3, "VIN", PI), (4, "EN", IN)]
    right = [(2, "SW", PO), (5, "FB", IN), (6, "PG", "open_collector")]
    s = box("TLV62585PDRL", "U", left, right, bottom=[(1, "GND", PI)], value="TLV62585PDRLR",
            desc="TI 3 A synchronous buck, 2.5-5.5 V in, 0.6 V FB, power good, SOT-563 (PDRL)")
    set_prop(s, "Datasheet", "https://www.ti.com/lit/ds/symlink/tlv62585.pdf")
    return s


def tps3808():
    """TPS3808DBV from the KiCad library, with ~RESET as open drain (SBVS050: open-drain RESET output)."""
    s = from_std("Power_Supervisor", "TPS3808DBV", "TPS3808DBV", "U")
    for sub in find_all(s, "symbol"):
        for p in find_all(sub, "pin"):
            if find(p, "number")[1] == "1":
                p[1] = Sym("open_collector")
    return s


BIDI = "bidirectional"


def emmc():
    """KIOXIA THGAMVG7T13BAIL, the Ti135 card's symbol (JEDEC 153-ball ball map, checked against the KIOXIA data
    sheet on the Agilex 5 card, SHARED_PARTS.md)."""
    left = [("M6", "CLK", IN), ("M5", "CMD", BIDI), ("H5", "DS", OUT), ("K5", "RST_n", IN), None] + \
        [(b, f"DAT{i}", BIDI) for i, b in enumerate(["A3", "A4", "A5", "B2", "B3", "B4", "B5", "B6"])]
    right = [("E6", "VCC", PI), ("F5", "VCC", PI), ("J10", "VCC", PI), ("K9", "VCC", PI), None,
             ("C6", "VCCQ", PI), ("M4", "VCCQ", PI), ("N4", "VCCQ", PI), ("P3", "VCCQ", PI), ("P5", "VCCQ", PI), None,
             ("C2", "VDDi", PO), None,
             ("A6", "VSS", PI), ("E7", "VSS", PI), ("G5", "VSS", PI), ("H10", "VSS", PI), ("J5", "VSS", PI),
             ("K8", "VSS", PI), ("C4", "VSSQ", PI), ("N2", "VSSQ", PI), ("N5", "VSSQ", PI), ("P4", "VSSQ", PI),
             ("P6", "VSSQ", PI)]
    s = box("THGAMVG7T13BAIL", "U", left, right,
            desc="KIOXIA e-MMC 5.1, 16 GB, 153-ball 11.5x13 mm 0.5 mm. VCCQ 1.8 V only. NC/RFU/VSF balls not shown (leave open)")
    set_prop(s, "Datasheet", "https://www.lcsc.com/datasheet/C7599693.pdf")
    return s


def hr911130a():
    """HanRun HR911130A magjack, the Ti135 card's symbol."""
    left = [(2, "MDI0+", PAS), (3, "MDI0-", PAS), (4, "MDI1+", PAS), (7, "MDI1-", PAS), (5, "MDI2+", PAS),
            (6, "MDI2-", PAS), (8, "MDI3+", PAS), (9, "MDI3-", PAS), None, (1, "TCT", PAS), (10, "CHS", PAS)]
    right = [(11, "LEDG_A", PAS), (12, "LEDG_K", PAS), None, (14, "LEDY_A", PAS), (13, "LEDY_K", PAS), None,
             ("SH", "SHIELD", PAS)]
    s = box("HR911130A", "J", left, right, value="HR911130A",
            desc="HanRun RJ45 with 10/100/1000Base-T magnetics, green (11 A / 12 K) and yellow (14 A / 13 K) LEDs. "
                 "TCT = chip-side centre taps, CHS = 75 R / 1000 p Bob Smith common (LCSC C54408)")
    set_prop(s, "Datasheet", "https://datasheet.lcsc.com/datasheet/pdf/d9b1e130e54a44fe9872ced55aa393e4.pdf")
    return s


def rtl8211fd():
    """Realtek RTL8211FD(I)-CG, 40-pin QFN 5x5 0.4 mm, from the data sheet Rev. 1.7 (Table 1-9), the Ti135 card's
    symbol. Strap functions in the pin names: RXD3/RXC/RXCTL = PHYAD0..2, RXD2 = PLLOFF, RXD1 = TXDLY,
    RXD0 = RXDLY, LED0 = CFG_EXT, LED1/LED2 = CFG_LDO0/1."""
    left = [(20, "TXC", IN), (19, "TXCTL", IN), (18, "TXD0", IN), (17, "TXD1", IN), (16, "TXD2", IN),
            (15, "TXD3", IN), None,
            (27, "RXC/PHYAD1", BIDI), (26, "RXCTL/PHYAD2", BIDI), (25, "RXD0/RXDLY", BIDI),
            (24, "RXD1/TXDLY", BIDI), (23, "RXD2/PLLOFF", BIDI), (22, "RXD3/PHYAD0", BIDI), None,
            (13, "MDC", IN), (14, "MDIO", BIDI), (31, "INTB/PMEB", "open_collector"), (12, "PHYRSTB", IN), None,
            (36, "XTAL_IN", IN), (37, "XTAL_OUT", OUT), (35, "CLKOUT", OUT)]
    right = [(1, "MDIP0", BIDI), (2, "MDIN0", BIDI), (4, "MDIP1", BIDI), (5, "MDIN1", BIDI), (6, "MDIP2", BIDI),
             (7, "MDIN2", BIDI), (9, "MDIP3", BIDI), (10, "MDIN3", BIDI), None,
             (32, "LED0/CFG_EXT", BIDI), (33, "LED1/CFG_LDO0", BIDI), (34, "LED2/CFG_LDO1", BIDI), None,
             (39, "RSET", PAS), (30, "LDO_OUT", PO), (28, "DVDD_RG", PO)]
    top = [(11, "AVDD33", PI), (40, "AVDD33", PI), (29, "DVDD33", PI), (3, "AVDD10", PI), (8, "AVDD10", PI),
           (38, "AVDD10", PI), (21, "DVDD10", PI)]
    s = box("RTL8211FD", "U", left, right, top=top, bottom=[(41, "GND", PI)], value="RTL8211FDI-CG",
            desc="Realtek 10/100/1000 PHY, RGMII, 3.3 V single supply with 1.0 V core LDO (LDO_OUT -> AVDD10/DVDD10) "
                 "and RGMII pad LDO (DVDD_RG), QFN-40 5x5 (LCSC C692886)")
    set_prop(s, "Datasheet", "https://static.chipdip.ru/lib/595/DOC042595102.pdf")
    return s


def qspi_flash():
    """IS25WP128-RHLE, 24-ball TFBGA 6x8 mm 5x5 array (same ball map as MX25U25645G / MT25QU), the Ti135 card's
    symbol. NC/DNU balls omitted."""
    left = [("C2", "CS#", IN), ("B2", "SCLK", IN), ("A4", "RESET#", IN)]
    right = [("D3", "SI/IO0", BIDI), ("D2", "SO/IO1", BIDI), ("C4", "WP#/IO2", BIDI), ("D4", "HOLD#/IO3", BIDI)]
    s = box("IS25WP128-RHLE", "U", left, right, top=[("B4", "VCC", PI)], bottom=[("B3", "GND", PI)],
            desc="ISSI 128 Mbit 1.8 V QSPI NOR flash, 24-ball TFBGA 6x8 mm, dedicated RESET# on A4")
    set_prop(s, "Datasheet", "https://www.issi.com/WW/pdf/25LP-WP128F.pdf")
    return s


def from_ti135(name, ref):
    """Copy a symbol from the Ti135 card's generated library (read-only source)."""
    sym = copy.deepcopy(next(x for x in find_all(load(TI135_LIB), "symbol") if x[1] == name))
    set_prop(sym, "Footprint", "")
    return sym


def build():
    cache = jc_cache()
    syms = [from_jc(cache, n) for n in JC_SYMBOLS]
    syms += [
        from_std("Device", "R", "R", "R"),
        from_std("Device", "R_Small", "R_Small", "R"),
        from_std("Device", "C", "C", "C"),
        from_std("Device", "C_Small", "C_Small", "C"),
        from_std("Device", "C_Polarized", "C_Polarized", "C"),
        from_std("Device", "LED", "LED", "D"),
        from_std("Device", "FerriteBead_Small", "FerriteBead_Small", "FB"),
        from_std("Device", "L", "L_Power", "L", desc="Power inductor 4x4 mm (regulator output)"),
        from_std("Connector_Generic", "Conn_02x03_Odd_Even", "Conn_02x03_Odd_Even", "J"),
        from_std("Regulator_Linear", "NCP163ASN330T1G", "NCP163ASN330T1G", "U"),
        tps3808(),
        tlv62585p(),
        from_std("Connector_Generic", "Conn_01x05", "Conn_01x05", "J"),
        from_std("Oscillator", "ASE-xxxMHz", "ASE-xxxMHz", "Y"),
        avc4t774(),
        from_std("Device", "Crystal_GND24", "Crystal_GND24", "Y"),
        from_std("74xGxx", "74LVC1G07", "74LVC1G07", "U"),
        qspi_flash(),
        rtl8211fd(),
        hr911130a(),
        emmc(),
        from_std("Analog_Switch", "CD4051B", "CD4051B", "U"),
        from_std("Amplifier_Operational", "OPA365xxDBV", "OPA365xxDBV", "U"),
        from_ti135("ADS7056", "U"),
        from_std("Device", "R_Pack04", "R_Pack04", "RN"),
        from_std("Connector_Generic", "Conn_02x19_Odd_Even", "Conn_02x19_Odd_Even", "J"),
        from_std("Connector_Generic", "Conn_01x14", "Conn_01x14", "J"),
        from_std("Connector_Generic", "Conn_01x03", "Conn_01x03", "J"),
        rename(from_std("power", "PWR_FLAG", "PWR_FLAG", "#FLG"), "PWR_FLAG"),
    ]
    syms += [power(n, n == "GND") for n in ("GND", "5V0", "1V0", "1V8", "1V35", "3V3", "3V3_analog")]
    return syms


if __name__ == "__main__":
    sys.exit(run(build))
