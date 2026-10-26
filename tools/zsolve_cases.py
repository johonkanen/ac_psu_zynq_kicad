"""Impedance cases for the JLC08121H-1080A stack-up (the pinguz97/Zynq-SoM board, DDR3_REVIEW.md):
python3 tools/zsolve_cases.py JOB, JOB = outer | in5 | sweep. Uses tools/zsolve.py (copied from efinix_soc_board).
Stack-up from Zynq_SoM.kicad_pcb: F 35 um / 76.4 um prepreg er 3.91 / In1 GND ... In4 GND / 152.8 um prepreg er 3.91 /
In5 / 200 um core er 4.36 / In6 GND / 76.4 um prepreg / B."""
import sys
from zsolve import z_se, z_diff
H = 0.0025
TC_OUT, TC_IN = 0.035, 0.0152
HP_OUT = 0.0764                     # F.Cu (B.Cu) to In1 (In6)
CORE, PP = 0.2, 0.1528              # In5 to In6 core, In5 to In4 prepreg
ER_PP, ER_CORE, ER_MASK = 3.91, 4.36, 3.8

def tr(ws, g, y0, y1):
    if g is None:
        return [(-ws / 2, ws / 2, y0, y1, 1.0)]
    c = g / 2 + ws / 2
    return [(-c - ws / 2, -c + ws / 2, y0, y1, 1.0), (c - ws / 2, c + ws / 2, y0, y1, -1.0)]

def outer(w, g=None):
    y0, y1 = HP_OUT, HP_OUT + TC_OUT
    t = tr(w, g, y0, y1)
    st = [(0, HP_OUT, ER_PP), (HP_OUT, HP_OUT + 0.02, ER_MASK)]
    for x0, x1, *_ in t:
        st.append((HP_OUT, y1 + 0.02, ER_MASK, x0 - 0.02, x1 + 0.02))
    return dict(stack=st, planes=[0], traces=t, top_open=True, width=3.0, h=H)

def in5(w, g=None):
    top = CORE + PP
    t = tr(w, g, CORE, CORE + TC_IN)
    return dict(stack=[(0, CORE, ER_CORE), (CORE, top, ER_PP)], planes=[0, top], traces=t, top_open=False,
                width=3.0, h=H)

cases = {
    "outer": [("SE", w, None) for w in (0.12, 0.15, 0.18, 0.20)] + [("DIFF", 0.10, 0.20), ("DIFF", 0.12, 0.15), ("DIFF", 0.13, 0.13)],
    "in5": [("SE", w, None) for w in (0.10, 0.12, 0.135, 0.16, 0.18)] + [("DIFF", 0.10, 0.20), ("DIFF", 0.10, 0.12), ("DIFF", 0.12, 0.15)],
}
for job in sys.argv[1:] or ["outer", "in5"]:
    f = {"outer": outer, "in5": in5}[job]
    for kind, w, g in cases[job]:
        z, ee = (z_se if g is None else z_diff)(**f(w, g))
        print(f"{job:6} {kind:4} w={w:.3f}" + (f" gap={g:.2f}" if g else "         ") +
              f"  Z={z:6.1f} ohm  eeff={ee:.2f}  {3.33564 * ee ** 0.5:.2f} ps/mm", flush=True)
