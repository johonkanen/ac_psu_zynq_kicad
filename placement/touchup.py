"""A KRT touch-up: re-place a few parts with everything else locked, each pulled to the chip it serves (kipy).
    kipy touchup.py lock BOARD OUT REF...       OUT = BOARD with every part locked except REF... (then prep.sh OUT)
    kipy touchup.py claims INTENT BOARD REF...  add a proximity claim per REF to INTENT (place_simple --claim-weight)
A claim pulls REF's pads on a net it shares with its partner (not GND) to the partner's pads on that net. The partner is
the first chip (U/Y/J/D, not REF) in REF's group (placement/groups.json) that shares such a net, the group anchor
first, then the anchors of the groups it is `near` (the config straps: U20); a part with none gets no claim. Parts of
the power groups get none (their cells follow the TLV62585 templates and sit by J6, not at the rails' loads).
max_mm: 3 for a capacitor (decoupling), 5 for the rest.
As on the Ti135 card (its 2026-10-25 touch-up of the PHY area: place_simple --claim-weight 20)."""
import json
import os
import sys

import pcbnew

H = os.path.dirname(os.path.abspath(__file__))


def lock(board, out, refs):
    b = pcbnew.LoadBoard(board)
    n = 0
    for f in b.GetFootprints():
        if f.GetReference() in refs:
            f.SetLocked(False)
            n += 1
        else:
            f.SetLocked(True)
    missing = set(refs) - {f.GetReference() for f in b.GetFootprints()}
    assert not missing, missing
    pcbnew.SaveBoard(out, b)
    print(f"touchup: {n} parts free, the rest locked -> {out}")


def claims(intent, board, refs):
    b = pcbnew.LoadBoard(board)
    fp = {f.GetReference(): f for f in b.GetFootprints()}
    groups = json.load(open(os.path.join(H, "groups.json")))["groups"]
    d = json.load(open(intent))
    prox = [c for c in d.get("proximity", []) if c.get("ref") not in refs]
    none = []
    for r in refs:
        g = next(g for g in groups if r in g["refs"])
        if g.get("role") == "power":
            continue
        near = [n["anchor"] for n in groups if n["name"] in g.get("near", [])]
        chips = [g["anchor"]] + [c for c in g["refs"] if c != g["anchor"]] + near
        mine = {p.GetNetname() for p in fp[r].Pads() if p.GetNetname() and p.GetNetname() != "GND"}
        for c in chips:
            if c == r or c[0] not in "UYJD":
                continue
            shared = mine & {p.GetNetname() for p in fp[c].Pads()}
            if shared:
                prox.append({"ref": r, "near": c, "basis": "pad_edge", "max_mm": 3.0 if r[0] == "C" else 5.0,
                             "pads": {r: sorted({p.GetNumber() for p in fp[r].Pads() if p.GetNetname() in shared}),
                                      c: sorted({p.GetNumber() for p in fp[c].Pads() if p.GetNetname() in shared})}})
                break
        else:
            none.append(r)
    d["proximity"] = prox
    json.dump(d, open(intent, "w"), indent=1)
    added = sum(c["ref"] in refs for c in prox)
    print(f"touchup: {added} claims" + (f"; no partner chip: {', '.join(none)}" if none else ""))


if __name__ == "__main__":
    if sys.argv[1] == "lock":
        lock(sys.argv[2], sys.argv[3], set(sys.argv[4:]))
    else:
        claims(sys.argv[2], sys.argv[3], sys.argv[4:])
