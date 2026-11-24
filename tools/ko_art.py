"""Korean PC images (beyond Codex's 32 UI images) -> HG3 replacements for one edition.

Reads every Y:\\AI\\island-steam-ko\\work\\img-ko\\manifest_*.json (lists of
{"entry", "frame", "edition": both|steam|gog, "png", "method", "checks"}) written by
build_ko_art.py (straight from Codex's Switch Korean CGs) and by the derive/staff-roll helpers, and
rewrites the named frames of that edition's HG3 losslessly (hg3.replace keeps every other frame,
tag and the frame geometry). Prints names and counts only.
"""
import glob
import json
import os
from collections import defaultdict

from PIL import Image

import hg3

ROOT = r"Y:\AI\island-steam-ko"
IMG_KO = os.path.join(ROOT, "work", "img-ko")


def rows_for(edition):
    rows = []
    for p in sorted(glob.glob(os.path.join(IMG_KO, "manifest_*.json"))):
        for r in json.load(open(p, encoding="utf-8")):
            if r["edition"] in ("both", edition):
                r = dict(r, manifest=os.path.basename(p))
                rows.append(r)
    seen = {}
    for r in rows:
        k = (r["entry"].casefold(), int(r["frame"]))
        if k in seen:
            raise SystemExit("frame %s/%d given twice (%s, %s)" % (r["entry"], r["frame"], seen[k], r["manifest"]))
        seen[k] = r["manifest"]
    return rows


def replacements(edition, kif, base=None):
    """{entry name as in the archive: new HG3 bytes}; base = already replaced blobs to build on"""
    base = base or {}
    by_entry = defaultdict(dict)
    adds = defaultdict(list)       # rows with "add": {"template", "x", "y"} -> new frames
    for r in rows_for(edition):
        if r.get("add"):
            adds[r["entry"]].append(r)
        else:
            by_entry[r["entry"]][int(r["frame"])] = r["png"]
    out = {}
    for entry in sorted(set(by_entry) | set(adds)):
        name = kif.by_name[entry.casefold()]["name"]
        blob = base.get(name) or kif.read(name)
        geo = {f["id"]: f for f in hg3.frames(blob)}
        ims = {}
        for fid, png in by_entry.get(entry, {}).items():
            im = Image.open(png)
            im.load()
            f = geo[fid]
            if im.size != (f["width"], f["height"]):
                raise SystemExit("%s frame %d: png %s vs frame %dx%d" % (name, fid, im.size, f["width"], f["height"]))
            ims[fid] = im.convert("RGBA" if f["bpp"] == 32 else "RGB")
        if ims:
            blob = hg3.replace(blob, ims)
        if adds.get(entry):
            new = []
            for r in sorted(adds[entry], key=lambda r: int(r["frame"])):
                im = Image.open(r["png"])
                im.load()
                a = r["add"]
                new.append((int(r["frame"]), int(a["template"]), im, int(a["x"]), int(a["y"])))
            blob = hg3.add_frames(blob, new)
        out[name] = blob
    return out
