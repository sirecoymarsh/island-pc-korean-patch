"""Line layout model of the JP engine's message windows (measured 11-07 in game):
fixed cells - single-byte = 1 unit, double-byte = 2 units; 58 units per line in the ADV and novel
windows; a message starting with an opening bracket hangs continuation lines by 1 unit.
Codes: \\n hard break; \\fs \\fn \\fl \\fll \\fNN; change size; other codes have no width;
ruby [base/reading] takes the width of base."""
import re

TOKEN = re.compile(r"\\(?:fll|fl|fs|fn|f\d+;|pc|pl|pr|n|r|m|@|w\d+;)|\[[^\[\]]*\]|.", re.S)
OPENERS = "「『（(“‘〈《【"
SIZES = {"\\fs": 18, "\\fn": 26, "\\fl": 30, "\\fll": 34}


def units(ch):
    if ch in "\r\n":
        return 0
    try:
        return len(ch.encode("cp932"))
    except UnicodeEncodeError:
        return 2  # Hangul etc. are double-byte in the patch encoding


def tokens(text, base=26, unit=None):
    """[(kind, text, width_units)] kind: char|code|break|ruby. unit: optional per-char width function
    (default: CP932 byte count, the Steam JP engine's fixed cells)"""
    units_ = unit or units
    out = []
    size = base
    for m in TOKEN.finditer(text):
        t = m.group()
        if t == "\\n":
            out.append(("break", t, 0)); continue
        if t.startswith("\\"):
            if t in SIZES:
                size = SIZES[t] if t != "\\fn" else base
            elif re.match(r"\\f\d+;", t):
                size = int(t[2:-1])
            out.append(("code", t, 0)); continue
        if t.startswith("[") and "/" in t:
            b = t[1:-1].split("/", 1)[0]
            out.append(("ruby", t, sum(units_(c) for c in b) * size / base)); continue
        out.append(("char", t, units_(t) * size / base))
    return out


def char_wrap_lines(text, cap=58):
    """Number of visual lines the engine produces (character wrapping)."""
    toks = tokens(text)
    lines, x = 1, 0.0
    hang = 1 if text.lstrip("\\n").startswith(tuple(OPENERS)) else 0
    started = False
    for kind, t, w in toks:
        if kind == "break":
            lines += 1; x = hang if hang else 0; continue
        if kind == "code":
            continue
        limit = cap
        if x + w > limit + 1e-9 and started:
            lines += 1; x = hang
        x += w
        started = True
    return lines


def word_wrap(text, cap=58, margin=0, unit=None):
    """Insert \\n at spaces so no line exceeds cap-margin units. Returns (new_text, n_breaks).
    unit: optional per-char width function (gog_units for the GOG/English engine)."""
    toks = tokens(text, unit=unit)
    hang = 1 if text.startswith(tuple(OPENERS)) else 0
    limit = cap - margin
    out = []
    x = 0.0
    last_space = None   # index in out of the most recent breakable space on this line
    x_after_space = 0.0
    added = 0
    for kind, t, w in toks:
        if kind == "break":
            out.append(t); x = hang; last_space = None; continue
        if kind == "code":
            out.append(t); continue
        if t == " " and kind == "char":
            last_space = len(out); x_after_space = x + w
            out.append(t); x += w; continue
        if x + w > limit + 1e-9 and last_space is not None:
            out[last_space] = "\\n"
            added += 1
            x = hang + (x - x_after_space)
            last_space = None
        out.append(t); x += w
    return "".join(out), added


_GOG = None


def gog_units(ch):
    """GOG/English engine 2.6.1.80 (measured 11-07): double-byte = 2 cells (28 px at the novel
    window's 28 px font), single-byte = max(14 px, the glyph's own advance) - proportional Latin."""
    global _GOG
    if ch in "\r\n":
        return 0
    try:
        n = len(ch.encode("cp932"))
    except UnicodeEncodeError:
        return 2
    if n != 1:
        return 2
    if _GOG is None:
        import json
        import os
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "gog_sbcs_width28.json")
        _GOG = json.load(open(p, encoding="utf-8"))["width"]
    return max(14, _GOG.get(ch, 14)) / 14.0
