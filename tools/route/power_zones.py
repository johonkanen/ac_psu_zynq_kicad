#!/usr/bin/env python3
"""Supply pours outside the copied block, added after the signals are routed (kipy):

    power_zones.py IN.kicad_pcb OUT.kicad_pcb        zones named "pwr:<net>" (replaced on a re-run), then filled

The block keeps juliancoy's pours (1V8 on In2/In4, 3V3 and the 1V0 island on In6, GND on F, 1V35 on F/B); these
carry the rails on from there to our regulators and loads. Pours flow around the routed signals.
  In6   3V3 over the whole board (U321 at the east edge, PHY, eMMC, J5, the PL banks);
        1V0 from the block's island west of U20 down to the U301 cell (L301, C302, C303)
  In4   1V8 over the whole board (U311 south of the block; eMMC, flash, PHY, translators east of it)
  B.Cu  5V0: J6 -> a strip up the east edge (U321, U331) and a band along the south edge (U311, U301, the LDO)
        1V35: the U331 cell -> a strip west (y 72.7-76.3) into the block's B.Cu 1V35 pour under the DDR
        1V0 / 1V8 / 3V3: a patch at each cell's inductor and output capacitors, stitched to the rail's plane
  F.Cu, B.Cu   GND over the rest
A rule area j9_no_pour keeps every pour out from under the Ethernet jack J9 on all layers, as on the Ti135 card
(the jack is the card's galvanic isolation; user, 2026-11-17). Tracks stay (MDI pairs, LED nets).
The patches get their plane vias here (0.48/0.25 on a 0.9 mm grid beside the pads, each checked against the copper
of every layer); single pads are tied to the planes by the router's supply step afterwards.
"""
import math
import sys

import pcbnew

FM, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
BOARD = [(131.0, 51.2), (208.0, 51.2), (208.0, 117.3), (131.0, 117.3)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


ZONES = [  # net, layer, priority, outline, clearance, min width
    ("GND", "F.Cu", 0, BOARD, 0.2, 0.2),
    ("GND", "B.Cu", 0, BOARD, 0.2, 0.2),
    ("3V3", "In6.Cu", 0, BOARD, 0.102, 0.102),
    ("1V8", "In4.Cu", 0, BOARD, 0.102, 0.102),
    # 1V0: from inside the block's island (its south-west lobe, x 143-151 at y 91-95) to the U301 cell
    ("1V0", "In6.Cu", 4, [(146.6, 90.2), (151.2, 90.2), (158.4, 97.5), (158.4, 104.4), (152.4, 104.4), (152.4, 99.0),
                          (146.6, 93.2)], 0.102, 0.102),
    ("1V0", "B.Cu", 2, rect(152.5, 99.7, 156.9, 105.65), 0.15, 0.2),
    ("1V8", "B.Cu", 2, rect(167.5, 100.75, 171.25, 106.35), 0.15, 0.2),
    ("3V3", "B.Cu", 2, rect(194.7, 85.1, 198.45, 90.7), 0.15, 0.2),
    ("1V35", "B.Cu", 3, rect(174.3, 72.7, 197.4, 76.3), 0.15, 0.2),
    ("1V35", "B.Cu", 3, rect(195.6, 72.1, 197.4, 77.65), 0.15, 0.2),
    # the block's F.Cu and B.Cu 1V35 pours meet nowhere by themselves: a F.Cu patch into its F.Cu pour (east edge
    # x 176) over the B.Cu strip, with vias
    ("1V35", "F.Cu", 3, rect(175.6, 72.7, 178.5, 76.3), 0.15, 0.2),
    # 5V0: east strip, south band, J6's pin row, a tab to each cell's input capacitor and VIN pin
    ("5V0", "B.Cu", 2, rect(203.4, 71.9, 208.0, 117.3), 0.15, 0.2),
    ("5V0", "B.Cu", 2, rect(139.0, 110.75, 208.0, 113.0), 0.15, 0.2),
    ("5V0", "B.Cu", 2, rect(199.9, 114.45, 208.0, 117.3), 0.15, 0.2),
    ("5V0", "B.Cu", 2, rect(200.1, 89.15, 203.6, 90.15), 0.15, 0.2),        # U321
    ("5V0", "B.Cu", 2, rect(199.1, 76.1, 203.6, 77.05), 0.15, 0.2),         # U331
    ("5V0", "B.Cu", 2, rect(172.9, 104.8, 176.9, 105.75), 0.15, 0.2),       # U311
    ("5V0", "B.Cu", 2, rect(175.4, 104.95, 176.9, 110.9), 0.15, 0.2),
    ("5V0", "B.Cu", 2, rect(158.4, 104.55, 162.0, 105.45), 0.15, 0.2),      # U301
    ("5V0", "B.Cu", 2, rect(160.3, 104.55, 162.0, 110.9), 0.15, 0.2),
]
PATCH_VIAS = [  # net, patch on B.Cu (the area beside the pads), plane layer
    ("1V0", (152.6, 99.8, 154.9, 104.3), "In6.Cu"),
    ("1V8", (167.6, 100.85, 169.4, 106.25), "In4.Cu"),
    ("3V3", (194.8, 85.2, 196.6, 90.6), "In6.Cu"),
    ("1V35", (176.3, 72.9, 178.4, 76.1), "B.Cu"),
]
J9 = rect(190.04, 53.06, 208.0, 70.19)

for z in list(b.Zones()):
    if z.GetZoneName().startswith("pwr:") or z.GetZoneName() == "j9_no_pour":
        b.Remove(z)
# the block's F.Cu pours move up one priority (GND 0 -> 1, 1V35 1 -> 2), so that our board-wide F.Cu GND pour
# (priority 0, 0.2 mm clearance) lies under the block's own (0.102 mm) instead of beside it at the same priority
for z in b.Zones():
    if not z.GetIsRuleArea() and not z.GetZoneName() and pcbnew.LayerName(z.GetFirstLayer()) == "F.Cu" \
            and z.GetAssignedPriority() == {"GND": 0, "1V35": 1}.get(z.GetNetname(), -1):
        z.SetAssignedPriority(z.GetAssignedPriority() + 1)
for net, layer, prio, pts, clr, minw in ZONES:
    z = pcbnew.ZONE(b)
    z.SetLayer(b.GetLayerID(layer)) if hasattr(b, "GetLayerID") else None
    ni = b.FindNet(net)
    assert ni is not None, net
    z.SetNet(ni)
    z.SetZoneName(f"pwr:{net}")
    # KiCad reports two pours of one net and one priority that overlap (zones_intersect): every pour of ours gets
    # its own priority, above the block's pour of that net and layer (block: 0-5) and in the order of the table
    z.SetAssignedPriority(prio if prio == 0 else 10 * prio + ZONES.index((net, layer, prio, pts, clr, minw)))
    z.SetLocalClearance(FM(clr))
    z.SetMinThickness(FM(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)          # solid, as the block's pours
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(FM(x), FM(y))
    b.Add(z)
z = pcbnew.ZONE(b)
z.SetIsRuleArea(True); z.SetZoneName("j9_no_pour")
ls = pcbnew.LSET()
for l in b.GetEnabledLayers().CuStack():
    ls.AddLayer(l)
z.SetLayerSet(ls)
z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
o = z.Outline(); o.NewOutline()
for x, y in J9:
    o.Append(FM(x), FM(y))
b.Add(z)

# --- plane vias in the cell output patches -----------------------------------------------------------------------
VIA, DRILL, CLR, HOLE, H2H = 0.48, 0.25, 0.102, 0.2, 0.25
obst = []       # (kind, geometry, net code, drill radius)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnCopperLayer():
            bb = p.GetBoundingBox()
            obst.append(("rect", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(), 0))
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        q = t.GetPosition()
        obst.append(("circle", (MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.F_Cu)) / 2), t.GetNetCode(), MM(t.GetDrill()) / 2))
    else:
        a, c = t.GetStart(), t.GetEnd()
        obst.append(("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2), t.GetNetCode(), 0))


def gap(kind, g, x, y):
    if kind == "rect":
        return math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3]))
    if kind == "circle":
        return math.hypot(x - g[0], y - g[1]) - g[2]
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def via_ok(x, y, code):
    need = max(VIA / 2 + CLR, DRILL / 2 + HOLE)
    for k, g, n, dr in obst:
        d = gap(k, g, x, y)
        if k == "rect" and d < VIA / 2 + 0.15:          # beside the pads, never in one (no via-in-pad here)
            return False
        if n != code and d < need:
            return False
        if k == "circle" and d + g[2] < dr + DRILL / 2 + H2H:
            return False
    return True


for net, (x0, y0, x1, y1), plane in PATCH_VIAS:
    ni = b.FindNet(net)
    n, y = 0, y0 + VIA / 2
    while y <= y1 - VIA / 2 + 1e-6:
        x = x0 + VIA / 2
        while x <= x1 - VIA / 2 + 1e-6:
            if via_ok(x, y, ni.GetNetCode()):
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(pcbnew.F_Cu, FM(VIA)) if False else v.SetWidth(FM(VIA))
                v.SetDrill(FM(DRILL)); v.SetNet(ni); b.Add(v)
                obst.append(("circle", (x, y, VIA / 2), ni.GetNetCode(), DRILL / 2))
                n += 1
            x += 0.9
        y += 0.9
    print(f"power_zones: {net} patch: {n} vias to {plane}")

zones = b.Zones()
pcbnew.ZONE_FILLER(b).Fill(zones)
pcbnew.SaveBoard(sys.argv[2], b)
print(f"power_zones: {len(ZONES)} pours, j9_no_pour, filled")
