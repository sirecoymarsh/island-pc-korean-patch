"""Build the patch font "ISLAND KO" from Noto Sans CJK JP (variable, SIL OFL 1.1).

- keeps ASCII, every CP932 character, all Hangul syllables and compatibility jamo
- points the donor kanji code points (data/pua_table.json) at the Hangul / symbol glyphs
- points the two 凛音/リンネ colour-mark kanji (kocodec.RINNE_ALIAS) at 「린」「네」 (11-08)
- adds a round dot glyph on kocodec.RINNE_DOT for the 드러냄표 ruby (11-08 evening)
- redraws the dashes ― ─ as one bar across the whole cell, Hangul-stroke thick, so ―― is a solid line (11-09)
- weight instance (default 400), vertical metrics 880/120 like MS Gothic's 1.0 em cell
Usage: python -I build_font.py [--weight 400] [--out PATH]
"""
import argparse
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kocodec import RINNE_ALIAS, RINNE_DOT, Codec  # noqa: E402

# 11-08 evening, 드러냄표: the ruby dot over the リンネ 「린」「네」. Measured on the GOG copy (ruby size 10 px in the message
# windows and the backlog, the ruby cell centred over its letter): a 0.70 em dot centred 0.35 em above the baseline is
# 7 px across with a 2 px gap over the letter - about 0.27 of the 26 px text, like the Switch port's chosen 「큰 쪽」.
DOT_DIAMETER, DOT_CENTRE_Y = 700, 350


def add_dot_glyph(font, uni, name="rinnedot"):
    import math
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyf = font["glyf"]
    pen = TTGlyphPen(glyf)
    r, n = DOT_DIAMETER / 2.0, 64
    pts = [(500 + r * math.cos(-2 * math.pi * k / n), DOT_CENTRE_Y + r * math.sin(-2 * math.pi * k / n)) for k in range(n)]
    pen.moveTo((round(pts[0][0]), round(pts[0][1])))
    for x, y in pts[1:]:
        pen.lineTo((round(x), round(y)))
    pen.closePath()
    g = pen.glyph()
    font.setGlyphOrder(font.getGlyphOrder() + [name])
    glyf.glyphs[name] = g
    glyf.glyphOrder = font.getGlyphOrder()
    g.recalcBounds(glyf)
    font["hmtx"].metrics[name] = (1000, g.xMin)
    if "vmtx" in font:
        font["vmtx"].metrics[name] = (1000, 880 - g.yMax)
    for t in font["cmap"].tables:
        if t.isUnicode() and t.format in (4, 12):
            t.cmap[uni] = name

# 11-09 (user 「고쳐」 to: the long dash ―― looks dotted and thin): Noto's ― (U+2015, 14,829 in the Korean text) is drawn
# x 72..928 of its 1000 cell, 42 units thick - at the 26 px text a 3.7 px gap between dashes and a stroke thinner than
# Hangul (ㅡ is 69 units). The dashes the Korean text uses - ― and the box-drawing ─ (U+2500, 317; full width already
# but 40 thick) - become one bar across the whole cell, 69 units thick, at Noto's height (centre y 380), so ―― and
# ── read as one solid line.
DASH_THICK, DASH_CENTRE_Y = 69, 380
SOLID_DASHES = (0x2015, 0x2500)


def solid_dash(font, uni):
    """-> (glyph name, code points drawn with it)"""
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    cmap = font.getBestCmap()
    name = cmap[uni]
    users = sorted(cp for cp, g in cmap.items() if g == name)
    glyf = font["glyf"]
    adv = font["hmtx"].metrics[name][0]
    y0 = DASH_CENTRE_Y - DASH_THICK // 2
    y1 = y0 + DASH_THICK
    pen = TTGlyphPen(glyf)
    pen.moveTo((0, y0))
    pen.lineTo((0, y1))
    pen.lineTo((adv, y1))
    pen.lineTo((adv, y0))
    pen.closePath()
    g = pen.glyph()
    glyf.glyphs[name] = g
    g.recalcBounds(glyf)
    font["hmtx"].metrics[name] = (adv, 0)
    return name, users

SRC = r"Y:\AI\island-steam-ko\fontsrc\NotoSansCJKjp-VF.ttf"
PUA_TABLE = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")
FAMILY = "ISLAND KO"


def cp932_unicodes():
    out = set()
    for a in range(0x20, 0x100):
        try:
            out.add(ord(bytes([a]).decode("cp932")))
        except UnicodeDecodeError:
            pass
    for a in list(range(0x81, 0xA0)) + list(range(0xE0, 0xFD)):
        for b in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            try:
                s = bytes([a, b]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(s) == 1 and not (0xE000 <= ord(s) <= 0xF8FF):
                out.add(ord(s))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weight", type=int, default=400)
    ap.add_argument("--out", default=r"Y:\AI\island-steam-ko\build\ko\ISLAND-KO.ttf")
    ap.add_argument("--family", default=FAMILY)
    args = ap.parse_args()
    codec = Codec.load(PUA_TABLE)
    pua = codec.pua_map()  # {pua cp: char}
    font = TTFont(SRC, recalcTimestamp=False)
    cmap = font.getBestCmap()
    required = set(range(0x20, 0x7F)) | set(range(0xAC00, 0xD7A4)) | set(range(0x3131, 0x318F))
    required |= cp932_unicodes()
    required |= {ord(c) for c in pua.values()}
    required -= set(pua)  # donor kanji: their own glyphs are not needed in the Korean-mode font
    missing_targets = sorted(c for c in pua.values() if ord(c) not in cmap)
    if missing_targets:
        raise SystemExit("source font lacks glyphs for: %s" % ["U+%04X" % ord(c) for c in missing_targets])
    lacking = sorted(u for u in required if u not in cmap)
    required &= set(cmap)
    opt = subset.Options()
    opt.recalc_timestamp = False
    opt.notdef_outline = True
    opt.name_IDs = ["*"]
    opt.name_legacy = True
    opt.name_languages = ["*"]
    opt.layout_features = []
    opt.hinting = False
    ss = subset.Subsetter(options=opt)
    ss.populate(unicodes=required)
    ss.subset(font)
    font = instantiateVariableFont(font, {"wght": args.weight}, inplace=True)
    cmap = font.getBestCmap()
    for t in font["cmap"].tables:
        if t.isUnicode() and t.format in (4, 12):
            for cp, ch in pua.items():
                t.cmap[cp] = cmap[ord(ch)]
            for k, ch in RINNE_ALIAS.items():          # the 凛音/リンネ colour marks: plain 「린」「네」 where no userfont map
                t.cmap[ord(k)] = cmap[ord(ch)]
    add_dot_glyph(font, ord(RINNE_DOT))
    dashes = {"U+%04X" % u: solid_dash(font, u) for u in SOLID_DASHES}
    style = "Regular"
    names = {1: args.family, 2: style, 3: "%s;%d;island-steam-ko" % (args.family, args.weight), 4: args.family,
             6: args.family.replace(" ", "") + "-" + style, 16: args.family, 17: style}
    name = font["name"]
    name.names = [r for r in name.names if r.nameID not in names]
    for k, v in names.items():
        name.setName(v, k, 3, 1, 0x409)
        name.setName(v, k, 1, 0, 0)
    os2 = font["OS/2"]
    os2.usWinAscent, os2.usWinDescent = 880, 120
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = 880, -120, 0
    os2.usWeightClass = args.weight
    os2.ulCodePageRange1 |= (1 << 0) | (1 << 17) | (1 << 19)
    os2.fsSelection = (os2.fsSelection & ~0b1100001) | 0b1000000  # REGULAR, not bold/italic
    hh = font["hhea"]
    hh.ascent, hh.descent, hh.lineGap = 880, -120, 0
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    font.save(args.out)
    chk = TTFont(args.out)
    cm = chk.getBestCmap()
    bad = [cp for cp, ch in list(pua.items()) + [(ord(k), ch) for k, ch in RINNE_ALIAS.items()] if cm.get(cp) != cm.get(ord(ch))]
    h = hashlib.sha256(open(args.out, "rb").read()).hexdigest()
    print(json.dumps({"font": args.out, "family": args.family, "weight": args.weight, "glyphs": len(chk.getGlyphOrder()),
                      "cmap": len(cm), "pua_mapped": len(pua), "pua_bad": len(bad), "required_absent_in_source": len(lacking),
                      "bytes": os.path.getsize(args.out), "sha256": h,
                      "solid_dashes": {k: [n, ["U+%04X" % c for c in users]] for k, (n, users) in dashes.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
