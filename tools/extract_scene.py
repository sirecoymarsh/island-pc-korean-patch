"""Extract scene.int (Steam JP original) CSTs, self-check the CST codec, and check that every kit
packet entry (JP0001..JP0487) points at a real CST line with the same raw text.
Output: counts only (no script text)."""
import glob
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2  # noqa: E402

ORIG = r"Y:\AI\island-steam-ko\steam-orig"
WORK = r"Y:\AI\island-steam-ko\work"
KIT = r"F:\AI\island-gemini\island-ko-kit"


def kit_dir(prefix_char):
    for d in glob.glob(os.path.join(KIT, "*")):
        if os.path.isdir(d) and os.path.basename(d).startswith(prefix_char):
            return d
    raise FileNotFoundError(prefix_char)


def main():
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    kif = cs2.Kif(os.path.join(ORIG, "scene.int"), key)
    outdir = os.path.join(WORK, "ja", "scene")
    os.makedirs(outdir, exist_ok=True)
    scenes = {}
    types = Counter()
    with open(kif.path, "rb") as fh:
        for e in kif.entries:
            blob = kif.read(e["name"], fh)
            with open(os.path.join(outdir, e["name"]), "wb") as f:
                f.write(blob)
            if not e["name"].lower().endswith(".cst"):
                continue
            lines, meta = cs2.parse_cst(blob)
            # codec self-check: rebuilt inner data must equal original inner data
            rebuilt = cs2.build_cst(lines, meta)
            l2, m2 = cs2.parse_cst(rebuilt)
            if l2 != lines or m2["input_table"] != meta["input_table"]:
                raise SystemExit("CST codec mismatch: " + e["name"])
            scenes[e["name"]] = lines
            types.update(t for t, _ in lines)
    print("archive entries", len(kif.entries), "cst", len(scenes), "line types", dict(sorted(types.items())))

    # no-change archive rebuild must be byte-identical
    tmp = os.path.join(WORK, "scene.nochange.int")
    kif.write(tmp, {})
    same = open(tmp, "rb").read() == open(kif.path, "rb").read()
    os.remove(tmp)
    print("no-change rebuild byte-identical:", same)

    src = kit_dir("\uc6d0")  # 원문
    files = sorted(glob.glob(os.path.join(src, "JP*.json")))
    seen = set()
    problems = Counter()
    by_type = Counter()
    for p in files:
        num = int(os.path.basename(p)[2:6])
        if num > 487:
            continue
        pk = json.load(open(p, encoding="utf-8"))
        for ent in pk["entries"]:
            arch, fname, ln = ent["id"].split("::")
            idx = int(ln.split("_")[1])
            if arch != "scene.int" or fname not in scenes:
                problems["unknown file"] += 1
                continue
            lines = scenes[fname]
            if idx != ent["command_index"] or idx >= len(lines):
                problems["bad index"] += 1
                continue
            typ, raw = lines[idx]
            by_type[(ent["line_type"], typ)] += 1
            try:
                text = raw.decode("cp932")
            except UnicodeDecodeError:
                problems["undecodable"] += 1
                continue
            if ent["line_type"] in (32, 33):
                if text != ent["source_raw"]:
                    problems["text mismatch %d" % ent["line_type"]] += 1
            else:
                if ent["source_raw"] not in text:
                    problems["choice text not inside command"] += 1
            if ent["id"] in seen:
                problems["duplicate id"] += 1
            seen.add(ent["id"])
    print("kit entries checked", len(seen), "by (kit type, cst type)", dict(by_type))
    print("problems", dict(problems))
    # visible text lines in CST not owned by any packet entry
    unowned = Counter()
    for fname, lines in scenes.items():
        for i, (typ, raw) in enumerate(lines):
            if typ in (0x20, 0x21):
                ident = "scene.int::%s::line_%05d" % (fname, i)
                if ident not in seen:
                    stripped = raw.replace(b"\\n", b"").replace(b"\\pc", b"").replace(b"\\pl", b"").strip()
                    unowned["type%02x %s" % (typ, "empty" if not stripped else "nonempty")] += 1
    print("CST text lines without kit entry", dict(unowned))


if __name__ == "__main__":
    main()
