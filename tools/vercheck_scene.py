"""Steam (JP) vs GOG scene.int: is the story flow the same (branches, choices' targets, jumps, staging commands)?
Text lines (message / name) are compared only by count; commands are compared exactly, choice lines by number and
target only (their wording is language). Prints counts and engine command keywords only - no story text."""
import collections
import difflib
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'P:\AI\island-steam-ko\tools')
import cs2  # noqa: E402

S = r'Y:\AI\island-steam-ko\steam-orig'
G = r'Y:\AI\island-steam-ko\gog-orig'


def open_kif(path, key):
    plain = open(path, 'rb').read(19)[8:19] != b'__key__.dat'
    return cs2.PlainKif(path) if plain else cs2.Kif(path, key)


ks = cs2.crc_key(cs2.passphrase(os.path.join(S, 'ISLAND.exe')))
kg = cs2.crc_key(cs2.passphrase(os.path.join(G, 'ISLAND.exe')))
a = open_kif(os.path.join(S, 'scene.int'), ks)
b = open_kif(os.path.join(G, 'scene.int'), kg)
na = {e['name'].casefold(): e['name'] for e in a.entries}
nb = {e['name'].casefold(): e['name'] for e in b.entries}
print('scripts: steam %d, gog %d, same names %d' % (len(na), len(nb), len(set(na) & set(nb))))

TEXT = {0x20, 0x21}
types_a, types_b = collections.Counter(), collections.Counter()
kw = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,15}$')


def skeleton(raw):
    """a command line -> what must match between languages"""
    t = raw.decode('cp932', 'replace').strip()
    tok = t.split()
    if not tok:
        return ('', '')
    if tok[0].isdigit():  # a choice: number, target (the wording after them is language)
        return ('<choice>', ' '.join(tok[:2]))
    return (tok[0] if kw.match(tok[0]) else '<other>', t)


tot = collections.Counter()
diff_kw = collections.Counter()
text_count_diff = 0
scripts_same_flow = 0
scripts_diff = []
other_type_diff = 0
for k in sorted(set(na) & set(nb)):
    la, ma = cs2.parse_cst(a.read(na[k]))
    lb, mb = cs2.parse_cst(b.read(nb[k]))
    types_a.update(t for t, r in la)
    types_b.update(t for t, r in lb)
    ca = [skeleton(r) for t, r in la if t == 0x30]
    cb = [skeleton(r) for t, r in lb if t == 0x30]
    oa = [(t, r) for t, r in la if t not in TEXT and t != 0x30]
    ob = [(t, r) for t, r in lb if t not in TEXT and t != 0x30]
    xa = sum(1 for t, r in la if t in TEXT)
    xb = sum(1 for t, r in lb if t in TEXT)
    tot['commands steam'] += len(ca)
    tot['commands gog'] += len(cb)
    tot['text lines steam'] += xa
    tot['text lines gog'] += xb
    same = ca == cb
    if not same:
        sm = difflib.SequenceMatcher(None, ca, cb, autojunk=False)
        n = 0
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                continue
            for x in ca[i1:i2]:
                diff_kw['steam ' + op + ' ' + x[0]] += 1
                n += 1
            for x in cb[j1:j2]:
                diff_kw['gog ' + op + ' ' + x[0]] += 1
                n += 1
        scripts_diff.append(n)
    if [t for t, r in oa] != [t for t, r in ob]:
        other_type_diff += 1
    if xa != xb:
        text_count_diff += 1
    if same:
        scripts_same_flow += 1
print('line types steam:', sorted(types_a.items()))
print('line types gog:  ', sorted(types_b.items()))
print('commands: steam %d / gog %d; text lines (message+name): steam %d / gog %d' % (
    tot['commands steam'], tot['commands gog'], tot['text lines steam'], tot['text lines gog']))
print('scripts whose command lines are identical (choices by number+target): %d of %d' % (scripts_same_flow, len(set(na) & set(nb))))
print('scripts with any command difference: %d (differing command lines per script: %s)' % (len(scripts_diff), sorted(scripts_diff)[-12:]))
print('differing command lines by keyword:', sorted(diff_kw.items(), key=lambda kv: -kv[1])[:25])
print('scripts whose other non-text line types differ: %d; whose text line count differs: %d' % (other_type_diff, text_count_diff))
