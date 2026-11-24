import sys, os, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile
EXE = r"Y:\AI\island-steam-ko\steam-orig\ISLAND.exe"
D = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\exe-raw\candidate"
before = open(D + r"\native_rsrc_before.bin", "rb").read()
after = open(D + r"\native_rsrc_after.bin", "rb").read()
RSRC_RVA = 0x4CA000


def leaves(blob, dir_size):
    """Walk an in-memory resource directory (RVAs relative to RSRC_RVA)."""
    out = {}
    def walk(off, path):
        n_named, n_id = struct.unpack_from("<HH", blob, off + 12)
        for i in range(n_named + n_id):
            name, target = struct.unpack_from("<II", blob, off + 16 + 8 * i)
            if name & 0x80000000:
                so = name & 0x7FFFFFFF
                ln = struct.unpack_from("<H", blob, so)[0]
                key = blob[so + 2: so + 2 + 2 * ln].decode("utf-16le")
            else:
                key = name
            if target & 0x80000000:
                walk(target & 0x7FFFFFFF, path + [key])
            else:
                rva, size = struct.unpack_from("<II", blob, target)
                out[tuple(path + [key])] = blob[rva - RSRC_RVA: rva - RSRC_RVA + size]
    walk(0, [])
    return out


a = leaves(before, None); b = leaves(after, None)
types = {4: "MENU", 5: "DIALOG", 6: "STRING", 9: "ACCEL", 16: "VERSION", 24: "MANIFEST", 3: "ICON", 14: "GROUP_ICON"}
changed = [k for k in b if a.get(k) != b[k]]
print("leaves before", len(a), "after", len(b), "changed", len(changed))
from collections import Counter
print(Counter(types.get(k[0], k[0]) for k in changed))
# show dialog captions (UTF-16) of changed dialogs, both languages
for k in changed:
    if k[0] != 5:
        continue
    def caption(blob):
        # DLGTEMPLATEEX or DLGTEMPLATE
        if struct.unpack_from("<HH", blob, 0) == (1, 0xFFFF):
            off = 26
        else:
            off = 18
        def sz(o):
            w = struct.unpack_from("<H", blob, o)[0]
            if w == 0xFFFF: return None, o + 4
            if w == 0: return "", o + 2
            e = o
            while struct.unpack_from("<H", blob, e)[0]: e += 2
            return blob[o:e].decode("utf-16le"), e + 2
        menu, o = sz(off); cls, o = sz(o); cap, o = sz(o)
        return cap
    print("DIALOG", k[1], repr(caption(a[k]))[:40], "->", repr(caption(b[k]))[:40])
