"""Pre-flip the parts that belong on B.Cu before placing (kipy flip_bottom.py BOARD [--drop-soc-decaps]).
- the power supplies: 4 x TLV62585 cells (sheet 3) and the J6 input caps (sheet 2), on the underside as on the Ti135
  card (LAYOUT_PLAN.md step 4). Their templates are fitted after the flip (prep.sh).
--drop-soc-decaps (the pose trials, LAYOUT_PLAN.md step 3): remove our SoC decaps C501-C529 and FB501. They are
placed by hand under/around U20 in step 4 and touch only rails, which the trial route leaves out."""
import sys

import pcbnew

POWER = ["C201", "C202", "C203"]
for n in (0, 1, 2, 3):
    c = f"3{n}"
    POWER += [f"U{c}1", f"L{c}1", f"R{c}1", f"R{c}2", f"C{c}1", f"C{c}2", f"C{c}3"]
POWER.append("C304")                       # the 1V0 cell's feed-forward cap (it has two output caps)
SOC_DECAPS = [f"C{i}" for i in range(501, 530)] + ["FB501"]

b = pcbnew.LoadBoard(sys.argv[1])
n = d = 0
for fp in list(b.GetFootprints()):
    r = fp.GetReference()
    if "--drop-soc-decaps" in sys.argv and r in SOC_DECAPS:
        b.Remove(fp)
        d += 1
    elif r in POWER and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        n += 1
pcbnew.SaveBoard(sys.argv[1], b)
print(f"flip_bottom: flipped {n}" + (f", dropped {d} SoC decaps" if d else ""))
