"""Steam (JP) vs GOG ISLAND.exe and the other root files: PE header, sections, imports, version resource, engine
strings (.rdata etc. - the Steam .text is SteamStub-encrypted). Prints numbers and engine identifiers only."""
import hashlib
import os
import re
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
S = r'Y:\AI\island-steam-ko\steam-orig'
G = r'Y:\AI\island-steam-ko\gog-orig'


def pe(path):
    b = open(path, 'rb').read()
    o = struct.unpack_from('<I', b, 0x3c)[0]
    machine, nsec, ts, _, _, optsz, ch = struct.unpack_from('<HHIIIHH', b, o + 4)
    opt = o + 24
    magic, lmaj, lmin = struct.unpack_from('<HBB', b, opt)
    entry = struct.unpack_from('<I', b, opt + 16)[0]
    imagebase = struct.unpack_from('<I', b, opt + 28)[0]
    ndirs = struct.unpack_from('<I', b, opt + 92)[0]
    dirs = [struct.unpack_from('<II', b, opt + 96 + 8 * i) for i in range(ndirs)]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        name = b[so + 40 * i:so + 40 * i + 8].rstrip(b'\0').decode('latin-1')
        vsz, va, rsz, rptr = struct.unpack_from('<IIII', b, so + 40 * i + 8)
        secs.append((name, va, vsz, rptr, rsz))

    def rva2off(rva):
        for n, va, vsz, rptr, rsz in secs:
            if va <= rva < va + max(vsz, rsz):
                return rva - va + rptr
        return None
    imports = {}
    irva = dirs[1][0] if ndirs > 1 else 0
    if irva:
        p = rva2off(irva)
        while p is not None:
            oft, _, _, name_rva, ft = struct.unpack_from('<IIIII', b, p)
            if not name_rva:
                break
            dll = b[rva2off(name_rva):].split(b'\0', 1)[0].decode('latin-1').lower()
            funcs = []
            t = rva2off(oft or ft)
            while t is not None:
                v = struct.unpack_from('<I', b, t)[0]
                if not v:
                    break
                if v & 0x80000000:
                    funcs.append('#%d' % (v & 0xffff))
                else:
                    q = rva2off(v)
                    funcs.append(b[q + 2:].split(b'\0', 1)[0].decode('latin-1') if q is not None else '?')
                t += 4
            imports[dll] = funcs
            p += 20
    return {'bytes': b, 'machine': machine, 'timestamp': ts, 'linker': '%d.%d' % (lmaj, lmin), 'entry': entry,
            'imagebase': imagebase, 'sections': secs, 'imports': imports, 'rva2off': rva2off}


def strings(b, secs, skip=('.text', '.bind')):
    out = set()
    for n, va, vsz, rptr, rsz in secs:
        if n in skip:
            continue
        out |= set(m.group().decode('latin-1') for m in re.finditer(rb'[\x20-\x7e]{6,}', b[rptr:rptr + rsz]))
    return out


def verinfo(path):
    ps = ("$v=(Get-Item -LiteralPath '%s').VersionInfo; '{0}|{1}|{2}|{3}|{4}' -f $v.FileVersion,$v.ProductVersion,"
          "$v.ProductName,$v.CompanyName,$v.FileDescription") % path
    return subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout.strip()


s, g = pe(os.path.join(S, 'ISLAND.exe')), pe(os.path.join(G, 'ISLAND.exe'))
print('== ISLAND.exe')
print('size  steam %d / gog %d' % (len(s['bytes']), len(g['bytes'])))
import datetime
for k in ('machine', 'linker', 'imagebase'):
    print('%-10s steam %s / gog %s' % (k, s[k], g[k]))
for nm, x in (('steam', s), ('gog', g)):
    print('built (PE time) %s %s' % (nm, datetime.datetime.utcfromtimestamp(x['timestamp']).strftime('%Y-%m-%d %H:%M UTC')))
print('version resource steam: %s' % verinfo(os.path.join(S, 'ISLAND.exe')))
print('version resource gog:   %s' % verinfo(os.path.join(G, 'ISLAND.exe')))
print('sections steam:', [(n, vsz) for n, va, vsz, rp, rs in s['sections']])
print('sections gog:  ', [(n, vsz) for n, va, vsz, rp, rs in g['sections']])
print('entry point steam %#x / gog %#x' % (s['entry'], g['entry']))
si, gi = s['imports'], g['imports']
print('import DLLs: steam %d, gog %d; only steam %s; only gog %s' % (len(si), len(gi), sorted(set(si) - set(gi)), sorted(set(gi) - set(si))))
fs = {d + '!' + f for d, fl in si.items() for f in fl}
fg = {d + '!' + f for d, fl in gi.items() for f in fl}
print('imported functions: steam %d, gog %d, common %d; only steam %s; only gog %s' % (
    len(fs), len(fg), len(fs & fg), sorted(fs - fg)[:30], sorted(fg - fs)[:30]))
ss, sg = strings(s['bytes'], s['sections']), strings(g['bytes'], g['sections'])
print('readable strings outside code: steam %d, gog %d, common %d (%.1f%% of steam, %.1f%% of gog)' % (
    len(ss), len(sg), len(ss & sg), 100 * len(ss & sg) / max(1, len(ss)), 100 * len(ss & sg) / max(1, len(sg))))
ver = re.compile(r'(?i)(cs2|catsystem|ver(sion)?)[^\n]{0,40}\d+\.\d+(\.\d+)*')
for nm, st in (('steam', ss), ('gog', sg)):
    hits = sorted(t for t in st if ver.search(t) and len(t) < 80)
    print('engine version strings %s: %s' % (nm, hits[:8]))
# the same code? the GOG .text against the Steam one is not comparable (encrypted); compare .rdata byte-for-byte
for sec in ('.rdata', '.data', '.rsrc'):
    a = [x for x in s['sections'] if x[0] == sec]
    c = [x for x in g['sections'] if x[0] == sec]
    if a and c:
        A = s['bytes'][a[0][3]:a[0][3] + a[0][4]]
        C = g['bytes'][c[0][3]:c[0][3] + c[0][4]]
        same = sum(1 for i in range(min(len(A), len(C))) if A[i] == C[i])
        print('%s: steam %d bytes / gog %d bytes, same bytes at same offset %.1f%%, identical %s' % (
            sec, len(A), len(C), 100 * same / max(1, max(len(A), len(C))), A == C))
print('only-gog strings that look like file names:', sorted(t for t in sg - ss if re.search(r'\.(txt|xml|int|dll|dat|fes|cst|ini)\b', t, re.I))[:20])
print('only-steam strings that look like file names:', sorted(t for t in ss - sg if re.search(r'\.(txt|xml|int|dll|dat|fes|cst|ini)\b', t, re.I))[:20])

print('== other root files')
for fn in sorted(set(os.listdir(S)) | set(os.listdir(G))):
    a, c = os.path.join(S, fn), os.path.join(G, fn)
    if fn.endswith('.int') or fn == 'ISLAND.exe':
        continue
    if os.path.isdir(a) or os.path.isdir(c):
        la = sorted(os.listdir(a)) if os.path.isdir(a) else None
        lc = sorted(os.listdir(c)) if os.path.isdir(c) else None
        same = None
        if la is not None and lc is not None:
            same = [f for f in set(la) & set(lc) if os.path.isfile(os.path.join(a, f)) and open(os.path.join(a, f), 'rb').read() == open(os.path.join(c, f), 'rb').read()]
        print('%-14s dir: steam %s files, gog %s files, same name+bytes %s' % (fn, None if la is None else len(la), None if lc is None else len(lc), None if same is None else len(same)))
        continue
    ha = hashlib.sha256(open(a, 'rb').read()).hexdigest()[:12] if os.path.exists(a) else None
    hc = hashlib.sha256(open(c, 'rb').read()).hexdigest()[:12] if os.path.exists(c) else None
    print('%-14s steam %s / gog %s %s' % (fn, ha, hc, '(same)' if ha == hc else ''))
