"""Rebuild image.int = Steam original + Codex's Korean UI images (entries that differ), written
with our packer so the layout matches the original archive exactly.
Usage: python -I build_image.py [--out PATH]"""
import argparse
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import ko_art  # noqa: E402

ORIG = r"Y:\AI\island-steam-ko\steam-orig"
CDX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\ko\image.int"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"Y:\AI\island-steam-ko\build\ko\image.int")
    args = ap.parse_args()
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    a = cs2.Kif(os.path.join(ORIG, "image.int"), key)
    b = cs2.Kif(CDX, key)
    if [e["name"].casefold() for e in a.entries] != [e["name"].casefold() for e in b.entries]:
        raise SystemExit("entry lists differ")
    repl = {}
    with open(a.path, "rb") as fa, open(b.path, "rb") as fb:
        for ea, eb in zip(a.entries, b.entries):
            db = b.read(eb["name"], fb)
            if ea["size"] != eb["size"]:
                repl[ea["name"]] = db
                continue
            da = a.read(ea["name"], fa)
            if da != db:
                repl[ea["name"]] = db
    codex_ui = len(repl)
    # story images, shared signage, staff roll and thumbnails (ko_art: Codex's Switch Korean CGs + derived)
    art = ko_art.replacements("steam", a, repl)
    repl.update(art)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    total = a.write(args.out, repl)
    # read back every replaced entry
    c = cs2.Kif(args.out, key)
    bad = 0
    with open(args.out, "rb") as fc:
        for n, d in repl.items():
            bad += c.read(n, fc) != d
    print(json.dumps({"entries": len(a.entries), "replaced": len(repl), "codex_ui": codex_ui, "ko_art": len(art),
                      "readback_bad": bad, "bytes": total, "hg3": sum(1 for n in repl if n.lower().endswith(".hg3"))}))


if __name__ == "__main__":
    main()
