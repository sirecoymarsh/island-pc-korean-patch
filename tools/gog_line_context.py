"""Context around a GOG scene line, for a translator working INSIDE a subagent only.

Shows, for each GOG line near the target: index, type, GOG English, the Korean our GOG build put
there (if any) and the aligned Steam Japanese line. PRINTS SCRIPT TEXT - never run this in the
main session (the user is playing the story for the first time).

Usage:
  python -I gog_line_context.py <file.cst> <gog_index> [--radius N]
  python -I gog_line_context.py --dropped <kit id scene.int::file.cst::line_NNNNN> [--radius N]
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import kit  # noqa: E402
from build_gog_text import align  # noqa: E402
from kocodec import Codec  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
GOG = os.path.join(ROOT, "gog-orig")
STEAM = os.path.join(ROOT, "steam-orig")
BUILD = os.path.join(ROOT, "build", "gog-ko", "scene.int")
DATA = os.path.join(os.path.dirname(HERE), "data")
TYPES = {0x20: "TEXT", 0x21: "NAME", 0x30: "CMD ", 0x02: "IN  ", 0x03: "PAGE"}


def show(raw, codec=None):
    if codec:
        return codec.decode(raw)
    return raw.decode("cp932", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("index", nargs="?", type=int)
    ap.add_argument("--dropped")
    ap.add_argument("--radius", type=int, default=12)
    a = ap.parse_args()
    codec = Codec.load(os.path.join(DATA, "pua_table.json"))
    kg = cs2.crc_key(cs2.passphrase(os.path.join(GOG, "ISLAND.exe")))
    ks = cs2.crc_key(cs2.passphrase(os.path.join(STEAM, "ISLAND.exe")))
    entries, _ = kit.load()
    if a.dropped:
        _, fname, ln = a.dropped.split("::")
        steam_index = int(ln.split("_")[1])
    else:
        fname, steam_index = a.file, None
    lg, _ = cs2.parse_cst(cs2.Kif(os.path.join(GOG, "scene.int"), kg).read(fname))
    lk, _ = cs2.parse_cst(cs2.Kif(BUILD, kg).read(fname))
    ls, _ = cs2.parse_cst(cs2.Kif(os.path.join(STEAM, "scene.int"), ks).read(fname))
    rows = [e for e in entries if e["file"] == fname]
    kit_ko = {e["index"]: e["ko"] for e in rows}
    mp, _ = align(ls, lg, [e["index"] for e in rows])
    rev = {g: s for s, g in mp.items()}
    if steam_index is not None:
        # dropped kit line: show the Steam side with kit Korean, then the GOG side near its neighbours
        print("== Steam (Japanese) around dropped line %d, with kit Korean ==" % steam_index)
        for i in range(max(0, steam_index - a.radius), min(len(ls), steam_index + a.radius + 1)):
            t, r = ls[i]
            if t not in (0x20, 0x21, 0x30):
                continue
            mark = ">>" if i == steam_index else "  "
            print("%s S%-5d %s JP: %s" % (mark, i, TYPES.get(t, t), show(r)))
            if kit_ko.get(i):
                print("          KO: %s" % kit_ko[i])
            print("          -> GOG %s" % (mp.get(i, "none")))
        near = [mp[i] for i in range(steam_index - 3, steam_index + 4) if i in mp]
        center = near[len(near) // 2] if near else 0
    else:
        center = a.index
    print("== GOG around %d (EN = GOG English, KO = our GOG build, JP = aligned Steam line) ==" % center)
    for j in range(max(0, center - a.radius), min(len(lg), center + a.radius + 1)):
        t, r = lg[j]
        if t not in (0x20, 0x21, 0x30):
            continue
        mark = ">>" if (steam_index is None and j == center) else "  "
        print("%s G%-5d %s EN: %s" % (mark, j, TYPES.get(t, t), show(r)))
        if lk[j][1] != r:
            print("          KO: %s" % show(lk[j][1], codec))
        if j in rev:
            print("          JP: %s" % show(ls[rev[j]][1]))


if __name__ == "__main__":
    main()
