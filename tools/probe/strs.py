import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import re
p = r"Y:\SteamLibrary\steamapps\common\ISLAND\ISLAND.exe"
data = open(p, "rb").read()
def around(off, span=200):
    s = max(0, off - span); e = off + span
    chunk = data[s:e]
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{3,}", chunk):
        out.append((hex(s + m.start()), m.group().decode()))
    return out
for o in [0x299f9f]:
    for a, t in around(o, 300): print(a, t)
print("----")
for pat in [rb"AddFontResource", rb"RemoveFontResource", rb"FR_PRIVATE", rb"GetProcAddress", rb"LoadLibrary", rb"SHIFTJIS", rb"charset", rb"codepage", rb"CP932", rb"932"]:
    hits = [m.start() for m in re.finditer(pat, data)]
    print(pat, len(hits), [hex(h) for h in hits[:8]])
