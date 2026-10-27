"""TLV62585PDRL buck cell shared by the power sheets, ported from the Ti135 card (efinix_soc_board/tools/sheets/_power.py).

    buck(sh, refs, x, y, rail, r1, en=None, pg=None, couts=1, title=None)

refs: dict with keys U, L, R1, R2, CIN, COUT (list; an entry may be (ref, value)), optional CFF.
rail: output power net; r1: top divider resistor (R2 = 100 k bottom, Vout = 0.6 V x (1 + R1/R2)).
en: None = EN tied to 5V0, else a hierarchical label name; pg: hierarchical label name for the open-drain PG output
(None = no connect). Cin 10 u 0805, L 1 uH 4x4 mm, Cout 22 u 0805 (couts of them), PWR_FLAG on the output.
CFF: 22 p feed-forward cap across R1. SLVSDE5F Table 4 note 2: above 47 uF of output capacitance a feed-forward
capacitor is needed, and every rail of this card carries more than that with the SoC decoupling (sheet 5).
Footprints are set per part here (this repo's library has no default footprints).
"""
from _common import *  # noqa: F401,F403

L_PART = {"MPN": "WPN4020H1R0MT", "LCSC": "C98359"}   # 1 uH 4x4 mm, 26 mOhm, Isat 5.8 A (> the 4 A switch limit)
U_PART = {"LCSC": "C485118"}
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"


def buck(sh, refs, x, y, rail, r1, en=None, pg=None, couts=1, title=None):
    """Returns the output node."""
    u = sh.place("TLV62585PDRL", refs["U"], x, y, value="TLV62585PDRLR", fields=U_PART)
    set_field(sh, refs["U"], "Footprint", "Package_TO_SOT_SMD:SOT-563")
    vin, en_p, gnd = u.pin(3), u.pin(4), u.pin(1)
    sw, fb, pgp = u.pin(2), u.pin(5), u.pin(6)
    if title:
        sh.text(title, x - g(16), y - g(9))
    # input: 5V0 + Cin
    n_in = left(vin, 8)
    sh.wire(vin, n_in)
    power_at(sh, "5V0", up(n_in, 2), "up"); sh.wire(n_in, up(n_in, 2))
    _, ct, cb = vert2(sh, "C", refs["CIN"], n_in[0] - g(4), n_in[1] + g(5), "10u", text="left")
    sh.wire(n_in, (ct[0], n_in[1]), ct); sh.junction(*n_in)
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
    set_field(sh, refs["CIN"], "Footprint", C0805)
    # enable
    if en is None:
        sh.wire(en_p, (n_in[0], en_p[1]), n_in)
    else:
        hlabel_left(sh, en, en_p, 3, "passive")
    sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")
    # SW -> L -> output
    _, la, lb = horiz2(sh, "L_Power", refs["L"], sw[0] + g(9), sw[1], "1u", text="above", fields=L_PART)
    set_field(sh, refs["L"], "Footprint", "Inductor_SMD:L_Coilcraft_XxL4020")
    sh.wire(sw, la)
    out = right(lb, 6)
    sh.wire(lb, out)
    # divider: R1 from the output down to the FB node, R2 to GND
    xr = out[0] + g(6)
    _, r1t, r1b = vert2(sh, "R", refs["R1"], xr, out[1] + g(5), r1, text="right")
    sh.wire(out, (xr, out[1]), r1t)
    mid = down(r1b, 1)
    sh.wire(r1b, mid)
    _, r2t, r2b = vert2(sh, "R", refs["R2"], xr, mid[1] + g(4), "100k", text="right")
    sh.wire(mid, r2t); sh.junction(*mid)
    sh.wire(r2b, down(r2b, 2)); power_at(sh, "GND", down(r2b, 2), "down")
    set_field(sh, refs["R1"], "Footprint", R0402); set_field(sh, refs["R2"], "Footprint", R0402)
    if refs.get("CFF"):
        xc = xr + g(11)
        _, cft, cfb = vert2(sh, "C", refs["CFF"], xc, out[1] + g(5), "22p", text="right")
        sh.wire((xc, out[1]), cft); sh.junction(xc, out[1])
        sh.wire(cfb, (xc, mid[1]), mid)
        set_field(sh, refs["CFF"], "Footprint", C0402)
    xf = out[0] - g(1)
    sh.wire(fb, (xf, fb[1]), (xf, mid[1]), mid)
    # PG
    if pg:
        hlabel_right(sh, pg, pgp, 3, "passive")
    else:
        sh.no_connect(*pgp)
    # output caps, rail symbol, PWR_FLAG
    xo = xr + g(20 if refs.get("CFF") else 14)
    sh.wire((xr, out[1]), (xo + g(8) * (couts - 1), out[1]))
    sh.junction(xr, out[1])
    for k, cref in enumerate(refs["COUT"][:couts]):
        cref, cval = cref if isinstance(cref, tuple) else (cref, "22u")
        cx = xo + g(8) * k
        _, ct, cb = vert2(sh, "C", cref, cx, out[1] + g(5), cval, text="right")
        sh.wire((cx, out[1]), ct)
        if k < couts - 1:
            sh.junction(cx, out[1])
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
        set_field(sh, cref, "Footprint", C0805)
    pr = up(out, 3)
    sh.wire(out, pr); sh.junction(*out)
    power_at(sh, rail, pr, "up")
    sh.wire(pr, right(pr, 3)); sh.pwr_flag(*right(pr, 3), 270)
    return out
