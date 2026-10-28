#!/usr/bin/env python3
"""Copy footprint poses (position, orientation, side, lock) from a placed board onto kicad/zynq_card.kicad_pcb
(run under KiCad's python: tools/p2k/bin/kipy tools/apply_placement.py PLACED.kicad_pcb [--board BOARD [--out OUT]]
[--keep-locks]). --board places another board instead and --out saves the result elsewhere (the pose trials,
placement/pose_trial.sh). --keep-locks keeps this board's lock flags (for a partial re-placement made on a copy with
extra parts locked). Ported from the Ti135 repo.

The placed board is a KiCadRoutingTools place_simple seed made from this board (work/place/, LAYOUT_PLAN.md step 4),
so the footprints match by reference. **A part locked on this board is never moved** (the block parts sit under the
copied copper, tools/import_block.py). A part only on this board (added to the schematic since, or dropped from the
placement run) keeps its position and is listed; a part only on the placed board is ignored.
"""
import argparse
import os

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "kicad", "zynq_card.kicad_pcb")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("placed")
    ap.add_argument("--board", default=PCB)
    ap.add_argument("--out")
    ap.add_argument("--keep-locks", action="store_true")
    a = ap.parse_args()
    src = {fp.GetReference(): fp for fp in pcbnew.LoadBoard(a.placed).GetFootprints()}
    board = pcbnew.LoadBoard(a.board)
    dst = {fp.GetReference(): fp for fp in board.GetFootprints()}
    new = sorted(set(dst) - set(src))
    moved = 0
    for ref, s in src.items():
        d = dst.get(ref)
        if d is None or d.IsLocked():
            continue
        if d.IsFlipped() != s.IsFlipped():
            d.Flip(d.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        d.SetOrientation(s.GetOrientation())
        d.SetPosition(s.GetPosition())
        if not a.keep_locks:
            d.SetLocked(s.IsLocked())
        moved += 1
    pcbnew.SaveBoard(a.out or a.board, board)
    print(f"apply_placement: {moved} footprints placed from {os.path.relpath(a.placed, ROOT)}"
          + (f"; not on it, left where they were: {', '.join(new)}" if new else ""))


if __name__ == "__main__":
    main()
