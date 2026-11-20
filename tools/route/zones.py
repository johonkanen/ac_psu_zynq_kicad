#!/usr/bin/env python3
"""Lift copper pours out of a board file for routing and put them back (plain text, no pcbnew):

    zones.py drop IN.kicad_pcb OUT.kicad_pcb SAVE.txt LAYER [LAYER ...]   pours on these layers -> SAVE.txt
    zones.py restore IN.kicad_pcb OUT.kicad_pcb SAVE.txt                  append the saved pours (unfilled)
    zones.py rmarea IN.kicad_pcb OUT.kicad_pcb PREFIX                     remove the rule areas named PREFIX...

KiCadRoutingTools routes no track through another net's pour, and the copied block's pours cover the whole block on
F/In2/In4/In6. Rule areas (keep-outs) stay. A restored pour comes back without its fill: fill afterwards.
"""
import re
import sys


def blocks(text):
    """(start, end) of every top-level '(zone' block."""
    out = []
    for m in re.finditer(r"^\t\(zone\n", text, re.M):
        i, depth = m.start() + 1, 0
        while True:
            c = text[i]
            if c == '"':
                i = text.index('"', i + 1)
                while text[i - 1] == "\\":
                    i = text.index('"', i + 1)
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((m.start(), i + 2))
    return out


def unfilled(z):
    """The zone without its (filled_polygon ...) blocks."""
    out, i = [], 0
    for m in re.finditer(r"^\t\t\(filled_polygon\n", z, re.M):
        if m.start() < i:
            continue
        j, depth = m.start() + 2, 0
        while True:
            if z[j] == "(":
                depth += 1
            elif z[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(z[i:m.start()]); i = j + 2
    return "".join(out) + z[i:]


mode, src, dst, save = sys.argv[1:5]
text = open(src).read()
if mode == "drop":
    layers = sys.argv[5:]
    keep, saved, pos = [], [], 0
    for a, e in blocks(text):
        z = text[a:e]
        lay = re.search(r'^\t\t\(layers? ([^\n]*)\)', z, re.M).group(1).replace('"', "").split()
        if "(keepout" not in z and set(lay) & set(layers):
            keep.append(text[pos:a]); saved.append(unfilled(z)); pos = e
    open(dst, "w").write("".join(keep) + text[pos:])
    open(save, "w").write("".join(saved))
    print(f"zones: {len(saved)} pours lifted from {' '.join(layers)}")
elif mode == "rmarea":
    keep, pos, n = [], 0, 0
    for a, e in blocks(text):
        if re.search(r'^\t\t\(name "' + re.escape(save), text[a:e], re.M):
            keep.append(text[pos:a]); pos = e; n += 1
    open(dst, "w").write("".join(keep) + text[pos:])
    print(f"zones: {n} rule areas {save}* removed")
else:
    saved = open(save).read()
    end = text.rstrip().rfind(")")
    open(dst, "w").write(text[:end] + saved + ")\n")
    print(f"zones: {saved.count(chr(9) + '(zone' + chr(10))} pours restored")
