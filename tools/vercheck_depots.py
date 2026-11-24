"""(ISLAND) What the Steam client would put in the game folder for each language: the cached depot manifests
(F:\\Steam\\depotcache - 857451 and 857454) read here - file count, size, and each file's SHA-1 matched against the
clean Steam (JP) copy and the GOG copy. Also: do the two ISLAND.exe share the archive key (the GOG exe on Steam data)?
Read only; prints file names of the game folder (engine files) and numbers."""
import hashlib
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'P:\AI\island-steam-ko\tools')
import cs2  # noqa: E402

DC = r'F:\Steam\depotcache'
S = r'Y:\AI\island-steam-ko\steam-orig'
G = r'Y:\AI\island-steam-ko\gog-orig'


def varint(b, o):
    v = s = 0
    while True:
        c = b[o]
        o += 1
        v |= (c & 0x7f) << s
        s += 7
        if not c & 0x80:
            return v, o


def fields(b):
    o = 0
    while o < len(b):
        key, o = varint(b, o)
        no, wt = key >> 3, key & 7
        if wt == 0:
            v, o = varint(b, o)
        elif wt == 2:
            n, o = varint(b, o)
            v = b[o:o + n]
            o += n
        elif wt == 1:
            v = b[o:o + 8]
            o += 8
        elif wt == 5:
            v = b[o:o + 4]
            o += 4
        else:
            raise ValueError('wire type %d' % wt)
        yield no, v


def manifest(path):
    b = open(path, 'rb').read()
    o, files, meta = 0, [], {}
    while o + 8 <= len(b):
        magic, ln = struct.unpack_from('<II', b, o)
        o += 8
        if magic == 0x32C415AB:
            break
        part = b[o:o + ln]
        o += ln
        if magic == 0x71F617D0:  # payload
            for no, v in fields(part):
                if no == 1:
                    f = {'name': None, 'size': 0, 'flags': 0, 'sha': None}
                    for n2, v2 in fields(v):
                        if n2 == 1:
                            f['name'] = v2.decode('utf-8', 'replace')
                        elif n2 == 2:
                            f['size'] = v2
                        elif n2 == 3:
                            f['flags'] = v2
                        elif n2 == 5:
                            f['sha'] = v2.hex()
                    files.append(f)
        elif magic == 0x1F4812BE:  # metadata
            for no, v in fields(part):
                meta[no] = v
    return files, meta


def local(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            h = hashlib.sha1()
            with open(p, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 22), b''):
                    h.update(chunk)
            out[h.hexdigest()] = os.path.relpath(p, root)
    return out


ls, lg = local(S), local(G)
print('local copies: steam %d files, gog %d files' % (len(ls), len(lg)))
for name in sorted(os.listdir(DC)):
    if not name.startswith('85745'):
        continue
    files, meta = manifest(os.path.join(DC, name))
    real = [f for f in files if f['sha'] and f['sha'] != '0' * 40]
    total = sum(f['size'] for f in files)
    in_s = sum(1 for f in real if f['sha'] in ls)
    in_g = sum(1 for f in real if f['sha'] in lg)
    print('== depot %s: %d files (%d with content), %.2f GB, filenames encrypted: %s, created %s' % (
        name.split('_')[0], len(files), len(real), total / 1e9, bool(meta.get(4)), meta.get(3)))
    print('   files identical to the Steam (JP) copy: %d, to the GOG copy: %d, to neither: %d' % (
        in_s, in_g, sum(1 for f in real if f['sha'] not in ls and f['sha'] not in lg)))
    exe = [f for f in files if f['name'] and f['name'].lower().endswith('island.exe')]
    for f in exe:
        print('   ISLAND.exe in it: size %d, same as steam copy: %s, same as GOG copy: %s' % (
            f['size'], f['sha'] in ls, f['sha'] in lg))
    lang = [f for f in files if f['name'] and os.path.basename(f['name']).lower() in ('language.txt', 'cs2conf.dll', 'direct.dat')]
    for f in lang:
        print('   %s: size %d, = steam copy %s, = GOG copy %s' % (f['name'], f['size'], f['sha'] in ls, f['sha'] in lg))
    neither = [f['name'] for f in real if f['sha'] not in ls and f['sha'] not in lg]
    print('   names of files in neither copy (first 25):', neither[:25])

ps = cs2.passphrase(os.path.join(S, 'ISLAND.exe'))
pg = cs2.passphrase(os.path.join(G, 'ISLAND.exe'))
print('== archive key: the two exe embed the same passphrase: %s' % (ps == pg))
