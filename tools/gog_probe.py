"""Text-path probe for the GOG/English engine (never shipped): the first text lines of com01 are
replaced by neutral test strings that write the same Hangul in three ways -
  CP949 bytes as they are / donor kanji codes (kocodec, the Steam method) / the GOG decoder's
  $$<number>; escape (engine 2.6.1.80 returns that code point as Unicode -> GetGlyphOutlineW)
plus width rulers. Output: build\\gog-probe\\scene.int (+ the files the loader needs).
Usage: python -I gog_probe.py [novel|meswnd] [set]"""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import wrapsim  # noqa: E402
from kocodec import Codec  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
ORIG = os.path.join(ROOT, "gog-orig")
OUT = os.path.join(ROOT, "build", "gog-probe")
PUA = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")
STEAM_BUILD = os.path.join(ROOT, "build", "ko")

SAMPLE = "가나다라 마바사 한글 시험"
LONG = "다람쥐 헌 쳇바퀴에 타고파 키스의 고유 조건은 입술끼리 만나야 하고 특별한 기술은 필요치 않다 줄바꿈 시험을 위한 긴 문장입니다"


def esc(text, hexa=False):
    out = []
    for ch in text:
        if ord(ch) < 0x80:
            out.append(ch)
        else:
            out.append("$$0x%04X;" % ord(ch) if hexa else "$$%d;" % ord(ch))
    return "".join(out).encode("ascii")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "novel"
    which = sys.argv[2] if len(sys.argv) > 2 else "a"
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    codec = Codec.load(PUA)
    codec = Codec.build(SAMPLE + LONG, {c: list(b) for c, b in codec.enc.items()})
    donor = lambda s: codec.encode(s)  # noqa: E731
    if which == "a":
        probes = [
            b"1 CP949: " + SAMPLE.encode("cp949"),
            b"2 DONOR: " + donor(SAMPLE),
            b"3 ESC: " + esc(SAMPLE),
            b"4 HEX: " + esc(SAMPLE, True),
            b"5 RULER: " + b"0123456789" * 9,
            b"6 ASCII: The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox.",
        ]
    else:
        wrapped, _ = wrapsim.word_wrap("7 " + LONG, 58, 1)
        probes = [
            donor("7 " + LONG),
            esc("8 " + LONG),
            donor(wrapped),
            donor("「10 " + LONG + "」"),
            donor("11 " + "가" * 40),
            esc("12 " + "가" * 40),
        ]
    k = cs2.Kif(os.path.join(ORIG, "scene.int"), key)
    lines, meta = cs2.parse_cst(k.read("com01.cst"))
    if mode != "novel":
        assert lines[39][1] == b"novel on" and lines[41][1].startswith(b"view 1 novel"), (lines[39], lines[41])
        lines[39] = (0x30, b"novel off")
        lines[41] = (0x30, b"view 1 " + mode.encode())
    idx = [i for i, (t, r) in enumerate(lines) if t == 0x20 and len(r.replace(b"\\n", b"").replace(b"\\pc", b"").replace(b"\\r", b"").strip()) > 0][:len(probes)]
    for i, b in zip(idx, probes):
        lines[i] = (0x20, b)
    os.makedirs(OUT, exist_ok=True)
    k.write(os.path.join(OUT, "scene.int"), {"com01.cst": cs2.build_cst(lines, meta)})
    # the loader also needs the patch font and the donor table in ko\
    for fn in ["ISLAND-KO.ttf"]:
        shutil.copy2(os.path.join(STEAM_BUILD, fn), os.path.join(OUT, fn))
    with open(os.path.join(OUT, "pua_table.txt"), "w", encoding="utf-16", newline="\n") as f:
        for cp, ch in sorted(codec.pua_map().items()):
            f.write("%04X\t%s\n" % (cp, ch))
    json.dump({"mode": mode, "set": which, "replaced_line_indices": idx, "donor_extra": len(codec.enc)},
              open(os.path.join(OUT, "probe.json"), "w", encoding="utf-8"))
    print("gog probe", mode, which, "lines", idx)


if __name__ == "__main__":
    main()
