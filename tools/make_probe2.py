"""Probe scene.int to measure line capacity per message-window type.
Replaces com01's first 'novel on' / 'view 1 novel' commands with the wanted window type and the first
five text lines with neutral rulers. Usage: python -I make_probe2.py <novel|meswnd|fullwnd>"""
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

DIGITS = "".join("%02d" % i for i in range(1, 50))
HANGUL = "".join("가나다라마바사아자차"[i % 10] if i % 10 else str(i // 10 % 10) for i in range(1, 80))
SETS = {
    "a": ["1:" + DIGITS, "2:" + HANGUL, "「3:" + HANGUL[:70] + "」",
          "4 띄어쓰기 시험 가나 다라 마바 사아 자차 가나 다라 마바 사아 자차 가나 다라 마바 사아 자차 가나 다라 마바 사아 자차 끝",
          "5:" + DIGITS[:30] + "。"],
    "b": ["1", "2", "3", "4:" + HANGUL, "「5:" + HANGUL[:70] + "」"],
    "c": ["1", "2", "3",
          "4 다람쥐 헌 쳇바퀴에 타고파. 키스의 고유 조건은 입술끼리 만나야 하고 특별한 기술은 필요치 않다. 동해 물과 백두산이 마르고 닳도록 하느님이 보우하사 우리나라 만세.",
          "「5 남산 위에 저 소나무 철갑을 두른 듯 바람 서리 불변함은 우리 기상일세. 가을 하늘 공활한데 높고 구름 없이 밝은 달은 우리 가슴 일편단심일세.」"],
}
PROBES = SETS["a"]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "meswnd"
    global PROBES
    PROBES = SETS[sys.argv[2] if len(sys.argv) > 2 else "a"]
    key = cs2.crc_key(cs2.passphrase(os.path.join(ROOT, "steam-orig", "ISLAND.exe")))
    codec = Codec.load(PUA)
    kif = cs2.Kif(os.path.join(BUILD, "scene.int"), key)
    lines, meta = cs2.parse_cst(kif.read("com01.cst"))
    if mode == "novel":
        pass
    else:
        assert lines[39][1] == b"novel on" and lines[41][1].startswith(b"view 1 novel"), (lines[39], lines[41])
        lines[39] = (0x30, b"novel off")
        lines[41] = (0x30, b"view 1 " + mode.encode())
    idx = [i for i, (t, r) in enumerate(lines) if t == 0x20 and len(r.replace(b"\\n", b"").replace(b"\\pc", b"").replace(b"\\r", b"").strip()) > 0][:len(PROBES)]
    import wrapsim
    for i, text in zip(idx, PROBES):
        if len(sys.argv) > 3 and sys.argv[3] == "wrap":
            text = wrapsim.word_wrap(text, 58, 1)[0]
        lines[i] = (0x20, codec.encode(text))
    os.makedirs(OUT, exist_ok=True)
    kif.write(os.path.join(OUT, "scene.int"), {"com01.cst": cs2.build_cst(lines, meta)})
    json.dump({"mode": mode, "replaced_line_indices": idx, "probes": PROBES}, open(os.path.join(OUT, "probe.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("probe", mode, idx)


if __name__ == "__main__":
    main()
