#!/usr/bin/env python3
"""Three fiducials per side for the assembly (kipy, inside the KiCad environment): fiducials.py IN.kicad_pcb OUT.kicad_pcb

Fiducial:Fiducial_1mm_Mask2mm (KiCad's library), board-only footprints FID1..FID6 (not in the schematic, not in the
BOM or placement files; existing FIDn are replaced). On each side the three free spots nearest to three corners of
the board (NW, NE, SE on top; the mirror choice does not matter to the machine): free = 1.6 mm from the fiducial's
centre to every pad of that side and every through-hole pad, 1.3 mm to every track of that layer and every via,
1.4 mm outside every courtyard of that side (its own is a 2.5 mm circle), 2 mm from the board edge and outside the rule areas. The pours
flow around the 1 mm dot by their own clearance; the 2 mm mask opening may show pour copper, which the cameras accept
less well than bare laminate: check the three top ones on the render.
"""
import math
import os
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
lib = os.path.join(os.environ["KICAD_MOUNT"], "share", "kicad", "footprints", "Fiducial.pretty")
for f in [f for f in b.GetFootprints() if f.GetReference().startswith("FID")]:
    b.Delete(f)
eb = b.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = MM(eb.GetLeft()), MM(eb.GetTop()), MM(eb.GetRight()), MM(eb.GetBottom())
areas = [z.GetBoundingBox() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() != "ddr3_block"]
n = 0
for side, layer, crt in (("F", pcbnew.F_Cu, pcbnew.F_CrtYd), ("B", pcbnew.B_Cu, pcbnew.B_CrtYd)):
    pads = [(MM(p.GetBoundingBox().GetLeft()), MM(p.GetBoundingBox().GetTop()), MM(p.GetBoundingBox().GetRight()),
             MM(p.GetBoundingBox().GetBottom())) for f in b.GetFootprints() for p in f.Pads()
            if p.IsOnLayer(layer) or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
    courts = [f.GetCourtyard(crt).BBox() for f in b.GetFootprints() if f.IsFlipped() == (side == "B")]
    courts = [(MM(c.GetLeft()) - 1.4, MM(c.GetTop()) - 1.4, MM(c.GetRight()) + 1.4, MM(c.GetBottom()) + 1.4) for c in courts if c.GetWidth() > 0]
    segs = [(MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y)) for t in b.GetTracks()
            if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == layer]
    vias = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]

    def free(x, y):
        if any(math.hypot(max(l - x, 0, x - r), max(t - y, 0, y - bt)) < 1.6 for l, t, r, bt in pads):
            return False
        if any(l < x < r and t < y < bt for l, t, r, bt in courts):
            return False
        if any(a.Contains(pcbnew.VECTOR2I(FM(x), FM(y))) for a in areas):
            return False
        if any(math.hypot(vx - x, vy - y) < 1.3 for vx, vy in vias):
            return False
        for ax, ay, cx, cy in segs:
            l2 = (cx - ax) ** 2 + (cy - ay) ** 2
            t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
            if math.hypot(x - ax - t * (cx - ax), y - ay - t * (cy - ay)) < 1.3:
                return False
        return True

    for cx, cy in ((X0, Y0), (X1, Y0), (X1, Y1)) if side == "F" else ((X1, Y0), (X0, Y0), (X0, Y1)):
        cands = sorted((math.hypot(x - cx, y - cy), x, y)
                       for x in [X0 + 2 + 0.5 * i for i in range(int((X1 - X0 - 4) / 0.5) + 1)]
                       for y in [Y0 + 2 + 0.5 * j for j in range(int((Y1 - Y0 - 4) / 0.5) + 1)])
        spot = next(((x, y) for d, x, y in cands if free(x, y)), None)
        assert spot, (side, cx, cy)
        n += 1
        f = pcbnew.FootprintLoad(lib, "Fiducial_1mm_Mask2mm")
        f.SetReference(f"FID{n}")
        f.SetValue("Fiducial")
        b.Add(f)
        f.SetPosition(pcbnew.VECTOR2I(FM(spot[0]), FM(spot[1])))
        if side == "B":
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        f.Reference().SetVisible(False)
        f.Value().SetVisible(False)
        pads.append((spot[0] - 1.0, spot[1] - 1.0, spot[0] + 1.0, spot[1] + 1.0))
        print(f"FID{n} {side} ({spot[0]:.1f}, {spot[1]:.1f}), {math.hypot(spot[0] - cx, spot[1] - cy):.1f} mm from its corner")
pcbnew.SaveBoard(sys.argv[2], b)
