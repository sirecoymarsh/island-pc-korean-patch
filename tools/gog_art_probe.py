"""In-game check of the new Korean images and movies on the GOG test copy (never shipped).

build\\gog-art-probe\\scene.int = our GOG Korean scene.int with com01.cst (the first scene of a new
game) replaced by a probe: the original set-up lines 0-38, then one block per check
  [layer commands, wait, "#<n>" text, click]   - images, compared with our PNGs by gog_art_probe_run.py
  [str 90 sys_staffroll_kar, fesjs staffroll]  - the staff roll scroll (about 112 s)
  [movie <name>.webm 3 100]                    - each Korean-subtitled movie, played to the end
and "title" at the end. The text lines are neutral ASCII markers.
Usage: python -I gog_art_probe.py   (prints the block list)"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
GOG = os.path.join(ROOT, "gog-orig")
BUILD = os.path.join(ROOT, "build", "gog-ko", "scene.int")
OUT = os.path.join(ROOT, "build", "gog-art-probe")

# (id, commands, check) - check: ("frame", entry, x, y) = screen shows that entry's Korean PNG with
# its top-left at screen (x, y) (negative = the part of a large image); ("roll", entry); ("movie", name, seconds)
BLOCKS = [
    ("item007a", ["eg 0 item007a"], ("frame", "item007a.hg3", 0, 0)),
    ("item007b", ["eg 0 item007b"], ("frame", "item007b.hg3", 0, 0)),
    ("item007c", ["eg 0 item007c"], ("frame", "item007c.hg3", 0, 0)),
    ("item007d", ["eg 0 item007d"], ("frame", "item007d.hg3", 0, 0)),
    ("item007e", ["eg 0 item007e"], ("frame", "item007e.hg3", 0, 0)),
    ("item007f", ["eg 0 item007f"], ("frame", "item007f.hg3", 0, 0)),
    ("sum007a", ["eg 0 sum007a"], ("frame", "sum007a.hg3", 0, 0)),
    ("sum007b", ["eg 0 sum007b"], ("frame", "sum007b.hg3", 0, 0)),
    ("sum043a", ["eg 0 sum043a"], ("frame", "sum043a.hg3", 0, 0)),
    ("sum025b", ["eg 0 sum025b"], ("frame", "sum025b.hg3", 0, 0)),
    ("sum007bl", ["eg", "bg 0 sum007bl -640 -360"], ("frame", "sum007bl.hg3", -640, -360)),
    ("bg14", ["bg 0 bg14 0 0"], ("frame", "bg14.hg3", 0, 0)),   # the engine keeps the last bg position when none is given
    ("bg14l", ["bg 0 bg14l -640 -360"], ("frame", "bg14l.hg3", -640, -360)),
    ("bg14cl", ["bg 0 bg14cl -640 -360"], ("frame", "bg14cl.hg3", -640, -360)),
    ("bg14nl", ["bg 0 bg14nl -640 -360"], ("frame", "bg14nl.hg3", -640, -360)),
    ("bg40l", ["bg 0 bg40l -640 -360"], ("frame", "bg40l.hg3", -640, -360)),
    ("bg40", ["bg 0 bg40 0 0"], ("frame", "bg40.hg3", 0, 0)),
    ("manpu", ["bg 0 bg14 0 0", "fg 2 manpu_gogogo 0 0 0 0"], ("fg", "manpu_gogogo.hg3")),
    ("staffroll_title", ["eg 0 sys_staffroll"], ("frame", "sys_staffroll.hg3", 0, 0)),
    ("staffroll", ["bg", "fg", "str 90 sys_staffroll_kar", "fesjs staffroll", "bg 0 bg40"], ("roll", "sys_staffroll_kar.hg3")),
    # a background under each movie, so the screen is bright again (and timeable) when it ends
    ("opmovie_win", ["bg 0 bg14", "movie opmovie_win.webm 3 100"], ("movie", "opmovie_win", 35.0)),
    ("edmovie2_kar", ["bg 0 bg40", "movie edmovie2_kar.webm 3 100"], ("movie", "edmovie2_kar", 220.0)),
    ("edmovie2_lin", ["bg 0 bg14", "movie edmovie2_lin.webm 3 100"], ("movie", "edmovie2_lin", 220.0)),
    ("edmovie2_sar", ["bg 0 bg40", "movie edmovie2_sar.webm 3 100"], ("movie", "edmovie2_sar", 220.0)),
    ("edmovie3", ["bg 0 bg14", "movie edmovie3.webm 3 100"], ("movie", "edmovie3", 314.0)),
]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated block ids")
    a = ap.parse_args()
    blocks = [b for b in BLOCKS if not a.only or b[0] in a.only.split(",")]
    os.makedirs(OUT, exist_ok=True)
    key = cs2.crc_key(cs2.passphrase(os.path.join(GOG, "ISLAND.exe")))
    k = cs2.Kif(BUILD, key)
    orig, meta = cs2.parse_cst(k.read("com01.cst"))
    assert orig[38] == (0x30, b"wait") and orig[39] == (0x30, b"novel on"), "unexpected com01 set-up"
    lines = list(orig[:39])
    for n, (bid, cmds, chk) in enumerate(blocks, 1):
        for c in cmds:
            lines.append((0x30, c.encode("ascii")))
        lines.append((0x30, b"wait"))
        lines.append((0x20, ("#%d" % n).encode("ascii")))
        lines.append((0x02, b""))
    lines.append((0x30, b"title"))
    # input table: one block per click (each ends with a 0x02 line), the rest after the last one
    pairs, start = [], 0
    for i, (t, _) in enumerate(lines):
        if t == 0x02:
            pairs.append((i + 1 - start, start))
            start = i + 1
    pairs.append((len(lines) - start, start))
    import struct
    meta = dict(meta, inputs=len(pairs), input_table=b"".join(struct.pack("<II", c, s) for c, s in pairs))
    blob = cs2.build_cst(lines, meta)
    l2, m2 = cs2.parse_cst(blob)
    assert l2 == lines and m2["inputs"] == len(pairs)
    k.write(os.path.join(OUT, "scene.int"), {"com01.cst": blob})
    json.dump([{"n": n, "id": b, "check": c} for n, (b, _, c) in enumerate(blocks, 1)],
              open(os.path.join(OUT, "probe_blocks.json"), "w", encoding="utf-8"), indent=1)
    print("probe blocks", len(blocks), "lines", len(lines), "inputs", len(pairs), "->", OUT)


if __name__ == "__main__":
    main()
