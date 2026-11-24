"""Load the ISLAND Korean kit (Steam PC packets JP0001-JP0487) with the reviewed translation.

review/out/<packet>.json is the canonical Korean when present, otherwise kit/번역/<packet>.json.
JP0488+ are Switch-only supplements and are not used for the Steam build.
"""
import glob
import json
import os

KIT = r"F:\AI\island-gemini\island-ko-kit"
REVIEW = r"F:\AI\island-gemini\review\out"
STEAM_LAST_PACKET = 487


def _kit_dir(first_char):
    for d in glob.glob(os.path.join(KIT, "*")):
        if os.path.isdir(d) and os.path.basename(d).startswith(first_char):
            return d
    raise FileNotFoundError(first_char)


def load():
    """Returns (entries, stats). entries: list of dict with id, file, index, line_type, source_raw,
    ko (str or None), packet, source (review|translation), and choice fields."""
    src_dir = _kit_dir("\uc6d0")   # 원문
    tr_dir = _kit_dir("\ubc88")    # 번역
    entries = []
    stats = {"packets": 0, "from_review": 0, "from_translation": 0, "missing_ko": 0}
    for p in sorted(glob.glob(os.path.join(src_dir, "JP*.json"))):
        base = os.path.basename(p)
        num = int(base[2:6])
        if num > STEAM_LAST_PACKET:
            continue
        stats["packets"] += 1
        pk = json.load(open(p, encoding="utf-8"))
        rp = os.path.join(REVIEW, base)
        tp = os.path.join(tr_dir, base)
        if os.path.exists(rp):
            ko_rows = json.load(open(rp, encoding="utf-8")); origin = "review"; stats["from_review"] += 1
        else:
            ko_rows = json.load(open(tp, encoding="utf-8")); origin = "translation"; stats["from_translation"] += 1
        ko = {r["id"]: r.get("ko") for r in ko_rows}
        for e in pk["entries"]:
            arch, fname, ln = e["id"].split("::")
            row = {
                "id": e["id"], "file": fname, "index": int(ln.split("_")[1]), "line_type": e["line_type"],
                "source_raw": e["source_raw"], "ko": ko.get(e["id"]), "packet": pk["packet_id"], "origin": origin,
            }
            if e["line_type"] == 48:
                row.update({k: e.get(k) for k in ("command_prefix", "command_suffix", "blank_choice", "choice_index", "choice_target")})
            if row["ko"] is None:
                stats["missing_ko"] += 1
            entries.append(row)
    return entries, stats
