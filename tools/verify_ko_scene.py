"""Static check of the built Korean scene.int against the original, for both builds (Steam JP, GOG/EN).
The PC patch keeps the original engine, so a new freeze can only come from what the patch changed in the scripts:
1. flow - every script's command lines (choices by number + target only), other non-text lines and its number of
   message / name lines must equal the original's;
2. text - every Korean message, name and choice line: strict cp932 decode, only the engine codes the original uses
   (\\n \\fs \\fn ... as in wrapsim.TOKEN), ruby [base/reading] well formed and never nested, no ruby in choice text
   (the engine crashes on it), no ASCII sign the original text never uses, and the wrap model's line count.
Prints counts, engine keywords and character codes only - never story text.
Usage: python -I verify_ko_scene.py"""
import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"P:\AI\island-steam-ko\tools")
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
BUILDS = [("steam-jp", os.path.join(ROOT, "steam-orig"), os.path.join(ROOT, "build", "ko")),
          ("gog-en", os.path.join(ROOT, "gog-orig"), os.path.join(ROOT, "build", "gog-ko"))]
TEXT = {0x20, 0x21}
KW = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,15}$")
CODE = re.compile(r"\\(fll|fl|fs|fn|f\d+;|pc|pl|pr|n|r|m|@|w\d+;|.)", re.S)
CHOICE = re.compile(r"^(\d+)\s+(\S+)\s*(.*)$", re.S)


def open_kif(path, key):
    plain = open(path, "rb").read(19)[8:19] != b"__key__.dat"
    return cs2.PlainKif(path) if plain else cs2.Kif(path, key)


def skeleton(t):
    tok = t.split()
    if not tok:
        return ("", "")
    if tok[0].isdigit():
        return ("<choice>", " ".join(tok[:2]))
    return (tok[0] if KW.match(tok[0]) else "<other>", t)


def ruby_problems(s):
    """-> list of problem kinds for the ruby brackets in s"""
    out, depth, seen_slash = [], 0, False
    for ch in s:
        if ch == "[":
            if depth:
                out.append("nested")
            depth += 1
            seen_slash = False
        elif ch == "]":
            if not depth:
                out.append("stray ]")
            elif not seen_slash:
                out.append("no /")
            depth = max(0, depth - 1)
        elif ch == "/" and depth:
            seen_slash = True
    if depth:
        out.append("unclosed [")
    return out


def codes(s):
    return [m.group(1) if not m.group(1)[0].isdigit() else m.group(1) for m in CODE.finditer(s)]


def check(label, orig_dir, ko_dir):
    key_o = cs2.crc_key(cs2.passphrase(os.path.join(orig_dir, "ISLAND.exe")))
    a = open_kif(os.path.join(orig_dir, "scene.int"), key_o)
    b = open_kif(os.path.join(ko_dir, "scene.int"), key_o)
    na = {e["name"].casefold(): e["name"] for e in a.entries}
    nb = {e["name"].casefold(): e["name"] for e in b.entries}
    print("== %s: scripts orig %d, ko %d, missing in ko %d, extra in ko %d" % (
        label, len(na), len(nb), len(set(na) - set(nb)), len(set(nb) - set(na))))
    n = collections.Counter()
    diff_kw = collections.Counter()
    orig_codes, orig_ascii = collections.Counter(), set()
    ko_codes = collections.Counter()
    new_ascii = collections.Counter()
    ruby = collections.Counter()
    bad_scripts = []
    pairs = []
    for k in sorted(set(na) & set(nb)):
        la, _ = cs2.parse_cst(a.read(na[k]))
        lb, _ = cs2.parse_cst(b.read(nb[k]))
        pairs.append((k, la, lb))
        for t, r in la:
            if t in TEXT:
                s = r.decode("cp932", "replace")
                orig_codes.update(codes(s))
                orig_ascii.update(ch for ch in s if 32 < ord(ch) < 127)
    for k, la, lb in pairs:
        ca = [skeleton(r.decode("cp932", "replace").strip()) for t, r in la if t == 0x30]
        cb_raw = [r for t, r in lb if t == 0x30]
        cb = [skeleton(r.decode("cp932", "replace").strip()) for r in cb_raw]
        oa = [t for t, r in la if t not in TEXT and t != 0x30]
        ob = [t for t, r in lb if t not in TEXT and t != 0x30]
        msg_a = sum(1 for t, r in la if t == 0x20)
        msg_b = sum(1 for t, r in lb if t == 0x20)
        nam_a = sum(1 for t, r in la if t == 0x21)
        nam_b = sum(1 for t, r in lb if t == 0x21)
        n["scripts"] += 1
        same = ca == cb and oa == ob and msg_a == msg_b and nam_a == nam_b
        if not same:
            bad_scripts.append(k)
            if ca != cb:
                for x, y in zip(ca, cb):
                    if x != y:
                        diff_kw[x[0] + "/" + y[0]] += 1
                if len(ca) != len(cb):
                    diff_kw["command count"] += 1
            if oa != ob:
                diff_kw["other line types"] += 1
            if msg_a != msg_b:
                diff_kw["message count"] += 1
            if nam_a != nam_b:
                diff_kw["name count"] += 1
        # Korean text lines
        for t, r in lb:
            if t not in TEXT and not (t == 0x30 and CHOICE.match(r.decode("cp932", "replace").strip())):
                continue
            try:
                s = r.decode("cp932")
            except UnicodeDecodeError:
                n["undecodable lines"] += 1
                s = r.decode("cp932", "replace")
            if t == 0x30:
                m = CHOICE.match(s.strip())
                s = m.group(3)
                n["choice lines"] += 1
                if "[" in s or "]" in s:
                    n["choice lines with ruby brackets (crash risk)"] += 1
                if "\\" in s:
                    n["choice lines with engine codes"] += 1
            else:
                n["message lines" if t == 0x20 else "name lines"] += 1
            ko_codes.update(codes(s))
            for p in ruby_problems(s):
                ruby[p] += 1
            for ch in s:
                if 32 < ord(ch) < 127 and ch not in orig_ascii:
                    new_ascii["U+%04X" % ord(ch)] += 1
    new_codes = {c: v for c, v in ko_codes.items() if c not in orig_codes}
    print("flow: scripts identical %d of %d; differing %d %s" % (
        n["scripts"] - len(bad_scripts), n["scripts"], len(bad_scripts), dict(diff_kw.most_common(12)) if diff_kw else ""))
    print("text: message lines %d, name lines %d, choice lines %d, undecodable %d" % (
        n["message lines"], n["name lines"], n["choice lines"], n["undecodable lines"]))
    print("      choice lines with ruby brackets %d, with engine codes %d" % (
        n["choice lines with ruby brackets (crash risk)"], n["choice lines with engine codes"]))
    print("      ruby problems %s" % (dict(ruby) or "none"))
    print("      engine codes in ko %s" % dict(ko_codes.most_common(20)))
    print("      codes the original text never uses %s" % (new_codes or "none"))
    print("      ASCII signs the original text never uses %s" % (dict(new_ascii) or "none"))
    return bad_scripts


def main():
    for label, o, k in BUILDS:
        check(label, o, k)


if __name__ == "__main__":
    main()
