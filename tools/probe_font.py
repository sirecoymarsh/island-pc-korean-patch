"""GDI check of the patch font, the way the JP engine uses it (CreateFontIndirectA charset 128,
GetGlyphOutlineA with CP932 codes). Process-private registration; nothing installed.
Checks: face match, metrics vs MS Gothic, every PUA code renders the same bitmap as the real
character via GetGlyphOutlineW."""
import ctypes as C
import ctypes.wintypes as W
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kocodec import Codec  # noqa: E402

FONT = sys.argv[1] if len(sys.argv) > 1 else r"Y:\AI\island-steam-ko\build\ko\ISLAND-KO.ttf"
FAMILY = sys.argv[2] if len(sys.argv) > 2 else "ISLAND KO"
PUA_TABLE = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")


class FIXED(C.Structure):
    _fields_ = [("fract", W.WORD), ("value", C.c_short)]


class MAT2(C.Structure):
    _fields_ = [("eM11", FIXED), ("eM12", FIXED), ("eM21", FIXED), ("eM22", FIXED)]


class POINT(C.Structure):
    _fields_ = [("x", W.LONG), ("y", W.LONG)]


class GM(C.Structure):
    _fields_ = [("bbx", W.UINT), ("bby", W.UINT), ("origin", POINT), ("incx", C.c_short), ("incy", C.c_short)]


class LOGFONTA(C.Structure):
    _fields_ = [("height", W.LONG), ("width", W.LONG), ("esc", W.LONG), ("ori", W.LONG), ("weight", W.LONG),
                ("italic", W.BYTE), ("underline", W.BYTE), ("strike", W.BYTE), ("charset", W.BYTE),
                ("outprec", W.BYTE), ("clipprec", W.BYTE), ("quality", W.BYTE), ("pitch", W.BYTE), ("face", C.c_char * 32)]


class TEXTMETRICW(C.Structure):
    _fields_ = [("tmHeight", W.LONG), ("tmAscent", W.LONG), ("tmDescent", W.LONG), ("tmInternalLeading", W.LONG),
                ("tmExternalLeading", W.LONG), ("tmAveCharWidth", W.LONG), ("tmMaxCharWidth", W.LONG), ("tmWeight", W.LONG),
                ("tmOverhang", W.LONG), ("tmDigitizedAspectX", W.LONG), ("tmDigitizedAspectY", W.LONG),
                ("tmFirstChar", W.WCHAR), ("tmLastChar", W.WCHAR), ("tmDefaultChar", W.WCHAR), ("tmBreakChar", W.WCHAR),
                ("tmItalic", W.BYTE), ("tmUnderlined", W.BYTE), ("tmStruckOut", W.BYTE), ("tmPitchAndFamily", W.BYTE), ("tmCharSet", W.BYTE)]


g = C.WinDLL("gdi32", use_last_error=True)
g.AddFontResourceExW.argtypes = [W.LPCWSTR, W.DWORD, W.LPVOID]
g.RemoveFontResourceExW.argtypes = [W.LPCWSTR, W.DWORD, W.LPVOID]
g.CreateCompatibleDC.restype = W.HDC
g.CreateCompatibleDC.argtypes = [W.HDC]
g.CreateFontIndirectA.argtypes = [C.POINTER(LOGFONTA)]
g.CreateFontIndirectA.restype = W.HFONT
g.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
g.SelectObject.restype = W.HGDIOBJ
g.DeleteObject.argtypes = [W.HGDIOBJ]
g.GetTextFaceW.argtypes = [W.HDC, C.c_int, W.LPWSTR]
g.GetTextMetricsW.argtypes = [W.HDC, C.POINTER(TEXTMETRICW)]
g.GetTextCharset.argtypes = [W.HDC]
for n in ["GetGlyphOutlineA", "GetGlyphOutlineW"]:
    fn = getattr(g, n)
    fn.argtypes = [W.HDC, W.UINT, W.UINT, C.POINTER(GM), W.DWORD, W.LPVOID, C.POINTER(MAT2)]
    fn.restype = W.DWORD
MAT = MAT2(FIXED(0, 1), FIXED(0, 0), FIXED(0, 0), FIXED(0, 1))
GGO_GRAY8 = 6


def glyph(hdc, code, ansi):
    gm = GM()
    fn = g.GetGlyphOutlineA if ansi else g.GetGlyphOutlineW
    n = fn(hdc, code, GGO_GRAY8, C.byref(gm), 0, None, C.byref(MAT))
    if n == 0xFFFFFFFF:
        return None
    buf = C.create_string_buffer(max(n, 1))
    fn(hdc, code, GGO_GRAY8, C.byref(gm), n, buf, C.byref(MAT))
    return (hashlib.sha1(buf.raw[:n]).hexdigest(), gm.bbx, gm.bby, gm.origin.x, gm.origin.y, gm.incx)


def make(dc, face, height):
    lf = LOGFONTA()
    lf.height = height
    lf.weight = 400
    lf.charset = 128
    lf.quality = 4
    lf.face = face.encode("cp932")
    h = g.CreateFontIndirectA(C.byref(lf))
    old = g.SelectObject(dc, h)
    buf = C.create_unicode_buffer(64)
    g.GetTextFaceW(dc, 64, buf)
    tm = TEXTMETRICW()
    g.GetTextMetricsW(dc, C.byref(tm))
    return h, old, buf.value, tm


def main():
    codec = Codec.load(PUA_TABLE)
    added = g.AddFontResourceExW(FONT, 0x10, None)
    assert added > 0, "AddFontResourceExW failed"
    dc = g.CreateCompatibleDC(None)
    rep = {}
    try:
        for height in (-26, 26):
            h, old, face, tm = make(dc, FAMILY, height)
            rep["ours_h%d" % height] = {"face": face, "charset": g.GetTextCharset(dc), "tmHeight": tm.tmHeight, "tmAscent": tm.tmAscent, "tmDescent": tm.tmDescent}
            if height == -26:
                bad = 0; empty = 0
                for ch, b in codec.enc.items():
                    a = glyph(dc, int.from_bytes(b, "big"), True)
                    w = glyph(dc, ord(ch), False)
                    if a is None or a != w:
                        bad += 1
                    elif a[1] == 0:
                        empty += 1
                jp = {}
                for ch in "日本語のテスト、。「」……！？―ソ表能":
                    bb = ch.encode("cp932")
                    a = glyph(dc, int.from_bytes(bb, "big") if len(bb) == 2 else bb[0], True)
                    w = glyph(dc, ord(ch), False)
                    jp[ch] = a is not None and a == w
                rep["pua_checked"] = len(codec.enc); rep["pua_mismatch"] = bad; rep["pua_blank_glyph"] = empty
                rep["japanese_ok"] = all(jp.values())
                sp = glyph(dc, 0x20, True); ha = glyph(dc, int.from_bytes(codec.enc["\uac00"], "big"), True)
                rep["advance_space_px"] = sp[5]; rep["advance_hangul_px"] = ha[5]
            g.SelectObject(dc, old); g.DeleteObject(h)
        for height in (-26, 26):
            h, old, face, tm = make(dc, "\uff2d\uff33 \u30b4\u30b7\u30c3\u30af", height)
            rep["msgothic_h%d" % height] = {"face": face, "tmHeight": tm.tmHeight, "tmAscent": tm.tmAscent, "tmDescent": tm.tmDescent}
            g.SelectObject(dc, old); g.DeleteObject(h)
    finally:
        g.RemoveFontResourceExW(FONT, 0x10, None)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
