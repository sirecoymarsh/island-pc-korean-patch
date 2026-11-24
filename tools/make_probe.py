"""Probe scene.int for the test copy: the first text lines of com01 are replaced with neutral test
strings (colour-code candidates, line wrapping, Korean ruby). Never shipped.
Usage: python -I make_probe.py   -> Y:\\AI\\island-steam-ko\\build\\probe\\scene.int"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
from kocodec import Codec  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
BUILD = os.path.join(ROOT, "build", "ko")
OUT = os.path.join(ROOT, "build", "probe")
PUA = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")

PROBES = [
    "1 색 후보 A: \\c[a0d8f0]린네\\c 와 린네",
    "2 색 후보 B: $C[a0d8f0]린네$C 와 린네",
    "3 색 후보 C: \\C[a0d8f0]린네\\C 와 린네 / \\c#a0d8f0;린네\\c;",
    "4 줄바꿈: 다람쥐 헌 쳇바퀴에 타고파. 키스의 고유 조건은 입술끼리 만나야 하고 특별한 기술은 필요치 않다. 동해 물과 백두산이 마르고 닳도록 하느님이 보우하사.",
    "5 루비: [가나/다라]와 [강조/・・] 그리고 ・ · … ―― 「」 『』 ！？ 0123 ABC abc",
]


def main():
    key = cs2.crc_key(cs2.passphrase(os.path.join(ROOT, "steam-orig", "ISLAND.exe")))
    codec = Codec.load(PUA)
    # probe strings may use chars outside the table: extend a private copy
    extra = Codec.build("".join(PROBES), {c: list(b) for c, b in codec.enc.items()})
    if len(extra.enc) != len(codec.enc):
        print("probe needs", len(extra.enc) - len(codec.enc), "extra glyph codes (not in font) - shown as blanks")
    kif = cs2.Kif(os.path.join(BUILD, "scene.int"), key)
    lines, meta = cs2.parse_cst(kif.read("com01.cst"))
    idx = [i for i, (t, r) in enumerate(lines) if t == 0x20 and len(r.replace(b"\\n", b"").replace(b"\\pc", b"").replace(b"\\r", b"").strip()) > 0][:len(PROBES)]
    for i, text in zip(idx, PROBES):
        lines[i] = (0x20, extra.encode("\\n" + text + "\\pc") if False else extra.encode(text))
    os.makedirs(OUT, exist_ok=True)
    kif.write(os.path.join(OUT, "scene.int"), {"com01.cst": cs2.build_cst(lines, meta)})
    json.dump({"replaced_line_indices": idx}, open(os.path.join(OUT, "probe.json"), "w"))
    print("probe scene.int", os.path.join(OUT, "scene.int"), "lines", idx)


if __name__ == "__main__":
    main()
