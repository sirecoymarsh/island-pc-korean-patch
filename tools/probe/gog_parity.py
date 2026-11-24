"""GOG (English, engine 2.6.1.80, no DRM) vs Steam JP: can the same patch structure apply?
Prints facts only (no script text)."""
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pefile
import cs2

G = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND"
S = r"Y:\AI\island-steam-ko\steam-orig"

pe = pefile.PE(os.path.join(G, "ISLAND.exe"))
imps = {i.dll.decode().upper(): [x.name.decode() for x in i.imports if x.name] for i in pe.DIRECTORY_ENTRY_IMPORT}
print("GOG imports VERSION.dll:", "VERSION.DLL" in imps, imps.get("VERSION.DLL", [])[:6])
print("GOG has .bind (Steam DRM):", any(s.Name.startswith(b".bind") for s in pe.sections))
for f in ["CreateFileA", "CreateFileW", "MessageBoxA", "CreateFontIndirectA", "GetGlyphOutlineW", "GetForegroundWindow"]:
    print("  imports", f, any(f in v for v in imps.values()))

kg = cs2.crc_key(cs2.passphrase(os.path.join(G, "ISLAND.exe")))
ks = cs2.crc_key(cs2.passphrase(os.path.join(S, "ISLAND.exe")))
a = cs2.Kif(os.path.join(G, "scene.int"), kg)
b = cs2.Kif(os.path.join(S, "scene.int"), ks)
na = {e["name"].lower() for e in a.entries}; nb = {e["name"].lower() for e in b.entries}
print("scene files GOG", len(na), "Steam", len(nb), "same names", na == nb)
same_count = same_cmds = same_types = 0
diff_files = []
with open(a.path, "rb") as fa, open(b.path, "rb") as fb:
    for e in b.entries:
        n = e["name"]
        if n.lower() not in na:
            continue
        la, _ = cs2.parse_cst(a.read(n, fa))
        lb, _ = cs2.parse_cst(b.read(n, fb))
        if len(la) == len(lb):
            same_count += 1
            if [t for t, _ in la] == [t for t, _ in lb]:
                same_types += 1
                if all(ra == rb for (ta, ra), (tb, rb) in zip(la, lb) if ta == 0x30):
                    same_cmds += 1
                else:
                    diff_files.append(n)
            else:
                diff_files.append(n)
        else:
            diff_files.append(n)
print("CST same line count:", same_count, " same line types:", same_types, " identical command lines:", same_cmds, " differing files:", len(diff_files), diff_files[:8])

lang = open(os.path.join(G, "language.txt"), "rb").read()
print("GOG language.txt bytes", len(lang), "starts", lang[:3], "has #-control lines:", len(re.findall(rb"(?m)^#\d+", lang)), re.findall(rb"(?m)^#\d+", lang)[:3])
