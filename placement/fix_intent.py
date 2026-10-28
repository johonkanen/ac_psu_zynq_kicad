"""Hand fixes to check_floorplan's emitted intent (kipy fix_intent.py INTENT BOARD):
- keep-outs: the block outline (the `ddr3_block` rule area, both sides; only the block's own parts and H2 inside),
  and the heatsink push-pin rings, radius 3 mm around H1/H2 on both sides (POWER_BUDGET.md §Heatsink);
- Y701 is an oscillator, not a crystal: no crystal proximity rule;
- the power sheets keep per-part faces (their cells are pre-flipped to B.Cu by flip_bottom.py)."""
import json
import sys

import pcbnew

p, board = sys.argv[1], pcbnew.LoadBoard(sys.argv[2])
d = json.load(open(p))
mm = pcbnew.ToMM
block = sorted(r for r in (fp.GetReference() for fp in board.GetFootprints())   # block parts (import_block's
               if r in ("H1", "H2") or (not r.startswith("J")                       # rule: refs < 200) and H1/H2
                                         and int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or 999) < 200))
keep = []
for z in board.Zones():
    if z.GetZoneName() == "ddr3_block":
        bb = z.GetBoundingBox()
        keep.append({"name": "ddr3_block", "rect": [round(mm(v), 3) for v in
                                                    (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())],
                     "sides": ["F", "B"], "allow": block,
                     "why": "the copied SoC + DDR3 block (REUSE_LOG.md): its copper is fixed, "
                            "so nothing of ours inside"})
for h in ("H1", "H2"):
    pos = board.FindFootprintByReference(h).GetPosition()
    keep.append({"name": f"heatsink_{h}", "circle": [round(mm(pos.x), 3), round(mm(pos.y), 3), 3.0],
                 "sides": ["F", "B"], "allow": [h], "why": "heatsink push pin head and barb (POWER_BUDGET.md)"})
assert len(keep) == 3, keep
d["keepouts"] = keep
d.setdefault("context", {}).pop("keepouts_note", None)
d["proximity"] = [r for r in d.get("proximity", []) if r.get("ref") != "Y701" and r.get("near") != "Y701"]
for b in d["blocks"]:
    if any(r in b["refs"] for r in ("C201", "U301")):
        b.pop("side", None)
        d["context"].get("basis", {}).pop(f"blocks[{b['name']}].side", None)
json.dump(d, open(p, "w"), indent=1)
print(f"fix_intent: {len(keep)} keep-outs; block rect {keep[0]['rect']}")
