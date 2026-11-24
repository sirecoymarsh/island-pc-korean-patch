"""Korean PC images taken straight from Codex's Switch-port Korean CG work (cg-opening-20261101).

Measured first (11-07): the Switch `_en` originals equal the GOG PC images and the shared
backgrounds/CGs equal both PC editions, so no re-drawing is needed:
  full   - Codex's Korean image replaces the whole frame (item007a-f, sum007a/b, sys_staffroll): the
           art is the same in both editions, only the text differs, and Codex's image has none of
           the English or Japanese text left.
  patch  - only the pixels Codex changed (Korean result != Switch original) are copied onto the PC
           frame; every other pixel stays the PC original (shared signage on backgrounds and CGs).
Writes PNGs to Y:\\AI\\island-steam-ko\\work\\img-ko\\direct and manifest_direct.json (read by ko_art.py).
Prints names and counts only. Usage: python -I build_ko_art.py"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import hg3  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
OUT = os.path.join(ROOT, "work", "img-ko", "direct")
MANIFEST = os.path.join(ROOT, "work", "img-ko", "manifest_direct.json")
CG = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\cg-opening-20261101"
FULL = {"item007a_en", "item007b_en", "item007c_en", "item007d_en", "item007e_en", "item007f_en",
        "sum007a_en", "sum007b_en", "sys_staffroll_en"}
SKIP = {"manpu_gogogo_en"}           # different canvas -> derived (subagent)


def pc_name(n):
    n = n.lower()
    return (n[:-3] if n.endswith("_en") else n) + ".hg3"


def main():
    os.makedirs(OUT, exist_ok=True)
    m = json.load(open(os.path.join(CG, "edited", "cg-manifest.json"), encoding="utf-8"))
    arcs = {}
    for ed in ("steam", "gog"):
        g = os.path.join(ROOT, ed + "-orig")
        arcs[ed] = cs2.Kif(os.path.join(g, "image.int"), cs2.crc_key(cs2.passphrase(os.path.join(g, "ISLAND.exe"))))
    rows = []
    for e in m["entries"]:
        if e["archive"] == "MANUAL" or e["name"] in SKIP:
            continue
        name = pc_name(e["name"])
        if name.casefold() not in arcs["gog"].by_name:
            continue
        ko = Image.open(os.path.join(CG, e["output"])).convert("RGBA")
        src = Image.open(os.path.join(CG, e["source_png"])).convert("RGBA")
        per = {}
        for ed, k in arcs.items():
            b = k.read(name)
            fs = hg3.frames(b)
            if len(fs) != 1:
                raise SystemExit("%s: %d frames" % (name, len(fs)))
            f = fs[0]
            pc = hg3.decode(b, f).convert("RGBA")
            if pc.size != ko.size:
                raise SystemExit("%s %s: size %s vs Korean %s" % (ed, name, pc.size, ko.size))
            if e["name"] in FULL:
                out = ko
                method = "full"
            else:
                a_ko, a_src, a_pc = (np.asarray(x) for x in (ko, src, pc))
                mask = np.any(a_ko != a_src, axis=2)
                out = Image.fromarray(np.where(mask[..., None], a_ko, a_pc).astype(np.uint8), "RGBA")
                method = "patch"
            arr = np.asarray(out)
            changed = int(np.any(arr != np.asarray(pc), axis=2).sum())
            per[ed] = (out, method, changed, f["bpp"])
        same = np.array_equal(np.asarray(per["steam"][0]), np.asarray(per["gog"][0]))
        eds = [("both", per["gog"])] if same else [("steam", per["steam"]), ("gog", per["gog"])]
        for ed, (im, method, changed, bpp) in eds:
            if bpp == 24:
                im = im.convert("RGB")
            p = os.path.join(OUT, name[:-4] + ("" if ed == "both" else "." + ed) + ".png")
            im.save(p)
            rows.append({"entry": name, "frame": 0, "edition": ed, "png": p, "method": method,
                         "checks": {"changed_pixels_vs_pc": changed if ed != "both" else {k: v[2] for k, v in per.items()},
                                    "codex_id": "%s_%s" % (e["archive"], e["id"])}})
        print("%-16s %-5s %s" % (name, per["gog"][1], "both" if same else "per-edition"))
    json.dump(rows, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("rows", len(rows), "entries", len({r["entry"] for r in rows}))


if __name__ == "__main__":
    main()
