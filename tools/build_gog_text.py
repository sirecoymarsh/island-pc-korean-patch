"""Korean scene.int for the GOG/English ISLAND (engine 2.6.1.80, no DRM).

The kit (JP0001-JP0487, review/out first) is keyed to the Steam JP scripts. GOG keeps the same 499
CSTs; 483 have the same line types as Steam (identity mapping), 16 differ by a line or two (an
English line appended at the end, a name line dropped, a line merged or moved past an input mark).
Those are aligned in two levels: command lines (choice text masked) are anchors, and between
anchors the kit's name/text lines are matched to GOG's content lines of the same type (difflib).

Text treatment is the Steam build's (normalize_ko, check_entry, donor-kanji codes from the shared
data/pua_table.json, word wrap at 58 cells with margin 1) except single-byte widths follow the GOG
engine (wrapsim.gog_units). Choice lines keep GOG's own "N label " prefix.

Prints counts only - never script text (the user is playing the story for the first time).
Usage: python -I build_gog_text.py [--out DIR] [--no-wrap]"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import kit  # noqa: E402
import wrapsim  # noqa: E402
from build_text import (CHOICE_JP_NOTE, CODE, check_entry, choice_note, choice_text, narrow_dots, normalize_ko,  # noqa: E402
                        rinne_apply, rinne_plan)
from kocodec import Codec  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
GOG = os.path.join(ROOT, "gog-orig")
STEAM = os.path.join(ROOT, "steam-orig")
DATA = os.path.join(os.path.dirname(HERE), "data")
PUA_TABLE = os.path.join(DATA, "pua_table.json")
GOG_EXTRA = os.path.join(DATA, "gog_extra_ko.json")   # Korean for GOG-only lines (optional)
# Korean that replaces what the kit put on a GOG line - for lines the English edition merged
# (the kit line that lost its GOG partner is folded into the neighbour). {"file::gog_index": ko}
GOG_OVERRIDE = os.path.join(DATA, "gog_override_ko.json")
CHOICE = re.compile(rb"^(\d+ \S+ )(.*)$", re.S)


def sig(t, r):
    """anchor signature of a command line (choice text masked)"""
    m = CHOICE.match(r)
    if m and not r.startswith(b"#"):
        return (t, b"CHOICE " + m.group(1))
    return (t, r)


def is_content(t, r):
    if t == 0x21:
        return True
    if t != 0x20:
        return False
    s = CODE.sub("", r.decode("cp932", "replace"))
    s = re.sub(r"\\[A-Za-z]+\d*;?", "", s)
    return bool(s.strip())


def line_sig(t, r):
    return sig(t, r) if t == 0x30 else (t,)


def align(ls, lg, kit_idx):
    """Line map Steam -> GOG for one file: ({steam index: gog index} over all aligned lines, notes).
    1) difflib over whole-line signatures (command bytes with choice text masked, other lines by
       type) - equal blocks map line by line;
    2) lines left over in the differing blocks (a text line moved past an input mark, ...) are
       paired inside the same command segment, by type in order, when the counts agree."""
    if len(ls) == len(lg) and [t for t, _ in ls] == [t for t, _ in lg]:
        return {i: i for i in range(len(ls))}, []
    notes = []
    sm = difflib.SequenceMatcher(a=[line_sig(*x) for x in ls], b=[line_sig(*x) for x in lg], autojunk=False)
    out = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                out[i1 + k] = j1 + k
        else:
            notes.append("%s S%d:%d G%d:%d" % (op, i1, i2, j1, j2))
    kit_set = set(kit_idx)
    rev = {g: s for s, g in out.items()}

    def seg_s(i):
        while i >= 0 and not (ls[i][0] == 0x30 and i in out):
            i -= 1
        return out.get(i, -1) if i >= 0 else -1

    def seg_g(j):
        while j >= 0 and not (lg[j][0] == 0x30 and j in rev):
            j -= 1
        return j

    left_s = defaultdict(list)
    for i in sorted(kit_set - set(out)):
        left_s[(seg_s(i), ls[i][0])].append(i)
    left_g = defaultdict(list)
    for j in range(len(lg)):
        if j not in rev and is_content(*lg[j]):
            left_g[(seg_g(j), lg[j][0])].append(j)
    for key, si in left_s.items():
        gj = left_g.get(key, [])
        if len(si) == len(gj):
            for a, b in zip(si, gj):
                out[a] = b
            notes.append("paired %d moved line(s)" % len(si))
    return out, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "gog-ko"))
    ap.add_argument("--no-wrap", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    kg = cs2.crc_key(cs2.passphrase(os.path.join(GOG, "ISLAND.exe")))
    ks = cs2.crc_key(cs2.passphrase(os.path.join(STEAM, "ISLAND.exe")))
    entries, kstats = kit.load()
    codec = Codec.load(PUA_TABLE)
    extra = json.load(open(GOG_EXTRA, encoding="utf-8")) if os.path.exists(GOG_EXTRA) else {}
    override = json.load(open(GOG_OVERRIDE, encoding="utf-8")) if os.path.exists(GOG_OVERRIDE) else {}
    need = sorted({c for e in entries if e["ko"] for c in e["ko"] if c not in codec.enc}
                  | {c for v in list(extra.values()) + list(override.values()) for c in v if c not in codec.enc})
    unencodable = [c for c in need if not (c in "\r\n" or _cp932_ok(c))]
    if unencodable:
        raise SystemExit("characters outside the shared donor table: %d (font/table would change)" % len(unencodable))

    by_file = defaultdict(list)
    for e in entries:
        by_file[e["file"]].append(e)
    src = cs2.Kif(os.path.join(GOG, "scene.int"), kg)
    stm = cs2.Kif(os.path.join(STEAM, "scene.int"), ks)
    rep = {"kit": kstats, "problems": Counter(), "align_notes": {}, "dropped": [], "gog_left": {}, "extra_used": 0, "same_as_steam": 0,
           "override_used": 0}
    rinne, rinne_st = rinne_plan(entries)
    rinne_done = Counter()
    notes_added = 0
    # cross-check with the English release, which writes 凛音 "Rinne" and リンネ "Rinné" ($$233;): kit form x English form
    rinne_en = Counter()
    ACCENT = re.compile(r"Rinn(?:\$\$233;|\$\$0x[eE]9;)")

    def gog_ko(t, ko):
        """encode Korean for a GOG text/name line the way kit lines are (normalize, wrap)"""
        nonlocal wraps
        ko, ndot = narrow_dots(ko)
        rep["problems"]["narrowed_middle_dots"] += ndot
        ko, _ = normalize_ko(ko)
        if t == 0x20 and not args.no_wrap:
            ko, n = wrapsim.word_wrap(ko, 58, 1, wrapsim.gog_units)
            wraps += n
        return codec.encode(ko)
    ids = defaultdict(list)
    repl = {}
    replaced = Counter()
    wraps = 0
    with open(src.path, "rb") as fg, open(stm.path, "rb") as fs:
        for ent in src.entries:
            fname = ent["name"]
            lg, meta = cs2.parse_cst(src.read(fname, fg))
            rows = by_file.get(fname, [])
            done = set()
            ls, _ = cs2.parse_cst(stm.read(fname, fs))
            mp, notes = align(ls, lg, [e["index"] for e in rows])
            rev = {g: s for s, g in mp.items()}
            if notes:
                rep["align_notes"][fname] = notes
            if rows:
                for e in rows:
                    gi = mp.get(e["index"])
                    if gi is None:
                        rep["dropped"].append(e["id"])
                        continue
                    typ, raw = lg[gi]
                    assert typ == e["line_type"], (fname, e["index"], gi)
                    ko, ndot = narrow_dots(e["ko"])
                    rep["problems"]["narrowed_middle_dots"] += ndot
                    ko, nfix = normalize_ko(ko)
                    if nfix:
                        rep["problems"]["fixed_dot_on_blank"] += nfix
                    for tag in check_entry(e, ko):
                        rep["problems"][tag] += 1
                        ids[tag].append(e["id"])
                    if typ == 0x20 and not args.no_wrap:
                        ko, n = wrapsim.word_wrap(ko, 58, 1, wrapsim.gog_units)
                        wraps += n
                    en = raw.decode("cp932", "replace")
                    if "Rinn" in en or "リンネ" in e["source_raw"] or "凛音" in e["source_raw"]:
                        jp = ("kata" if "リンネ" in e["source_raw"] else "") + ("kanji" if "凛音" in e["source_raw"] else "")
                        enf = ("accent" if ACCENT.search(en) else "") + ("plain" if "Rinne" in en else "")
                        rinne_en[("type%d" % e["line_type"], jp or "-", enf or "-", "coloured" if e["id"] in rinne else "plain")] += 1
                    if e["id"] in rinne:
                        before = ko.count("린네")
                        ko, marked, in_ruby = rinne_apply(ko, rinne[e["id"]], e["line_type"])
                        if before != e["ko"].count("린네"):
                            raise SystemExit("rinne: formatting changed the 「린네」 count in " + e["id"])
                        rinne_done["planned_%d" % e["line_type"]] += 1
                        rinne_done["lines_%d" % e["line_type"]] += bool(marked)
                        rinne_done["pairs_%d" % e["line_type"]] += marked
                        rinne_done["left_in_ruby"] += in_ruby
                    if typ == 0x30:
                        m = CHOICE.match(raw)
                        assert m and m.group(1).decode("cp932") == e["command_prefix"], e["id"]
                        if not e.get("blank_choice"):
                            ko, nn = choice_note(e, ko)
                            notes_added += nn
                        new = m.group(1) + (m.group(2) if e.get("blank_choice") else codec.encode(choice_text(ko, "gog")))
                    else:
                        new = codec.encode(ko)
                    lg[gi] = (typ, new)
                    done.add(gi)
                    replaced[typ] += 1
            # GOG content lines nobody replaced: GOG-only English lines
            for j, (t, r) in enumerate(lg):
                if j in done:
                    continue
                key = "%s::%d" % (fname, j)
                if is_content(t, r) or (t == 0x30 and CHOICE.match(r) and not r.startswith(b"#") and _is_choice_cmd(lg, j)):
                    if j in rev and ls[rev[j]] == (t, r):
                        rep["same_as_steam"] += 1   # e.g. a name line the kit leaves as it is
                        continue
                    if key in extra:
                        lg[j] = (t, gog_ko(t, extra[key]))
                        rep["extra_used"] += 1
                        done.add(j)
                        continue
                    rep["gog_left"].setdefault(fname, []).append(j)
            for j in sorted(done):
                key = "%s::%d" % (fname, j)
                if key in override:
                    t = lg[j][0]
                    if t not in (0x20, 0x21):
                        raise SystemExit("override on a non-text line: " + key)
                    lg[j] = (t, gog_ko(t, override[key]))
                    rep["override_used"] += 1
            if done:
                repl[fname] = cs2.build_cst(lg, meta)
                l2, m2 = cs2.parse_cst(repl[fname])
                assert len(l2) == len(lg) and m2["input_table"] == meta["input_table"]
    if notes_added != len(CHOICE_JP_NOTE):
        raise SystemExit("choice note: %d of %d options got their Japanese spelling" % (notes_added, len(CHOICE_JP_NOTE)))
    planned_here = {e["id"] for e in entries if e["id"] in rinne} - set(rep["dropped"])
    if sum(rinne_done["planned_%d" % t] for t in (32, 33, 48)) != len(planned_here):
        raise SystemExit("rinne: %d planned lines seen of %d" % (sum(rinne_done["planned_%d" % t] for t in (32, 33, 48)), len(planned_here)))
    out_scene = os.path.join(args.out, "scene.int")
    src.write(out_scene, repl)
    # read back
    chk = cs2.Kif(out_scene, kg)
    bad = 0
    with open(out_scene, "rb") as fh:
        for fname, blob in repl.items():
            bad += chk.read(fname, fh) != blob
    rep["scene"] = {"files_changed": len(repl), "replaced_by_type": {hex(k): v for k, v in replaced.items()}, "word_wrap_breaks": wraps,
                    "dropped_kit_entries": len(rep["dropped"]), "gog_only_lines_left": sum(len(v) for v in rep["gog_left"].values()),
                    "untouched_same_as_steam": rep["same_as_steam"], "gog_only_translated": rep["extra_used"],
                    "merged_line_overrides": rep["override_used"], "choice_japanese_notes": notes_added,
                    "rinne": {"dotted_text_lines": rinne_done["lines_32"], "dotted_pairs": rinne_done["pairs_32"],
                              "left_in_ruby": rinne_done["left_in_ruby"], "coloured_choice_options": rinne_done["lines_48"],
                              "name_labels_unmarked": rinne_done["planned_33"],
                              "planned_but_dropped_in_gog": len({e["id"] for e in entries if e["id"] in rinne} & set(rep["dropped"])),
                              "plan": dict(rinne_st)},
                    "readback_mismatch": bad, "bytes": os.path.getsize(out_scene)}
    rep["rinne_vs_english"] = {" / ".join(k): v for k, v in sorted(rinne_en.items())}
    rep["problems"] = dict(rep["problems"])
    json.dump({"report": rep, "problem_ids": dict(ids)}, open(os.path.join(DATA, "gog_text_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep["scene"], ensure_ascii=False))
    print("problems", rep["problems"], "align notes in", len(rep["align_notes"]), "files; gog-only lines in", sorted(rep["gog_left"])[:20])


def _cp932_ok(c):
    from kocodec import cp932_ok
    return cp932_ok(c)


def _is_choice_cmd(lines, j):
    """choice commands look like the kit's: "N <scene>_sel?_N text" or "N BAD_NN text" """
    m = CHOICE.match(lines[j][1])
    return bool(m and re.match(rb"^\d+ (\S*_sel\S*|BAD_\d+) $", m.group(1)))


if __name__ == "__main__":
    main()
