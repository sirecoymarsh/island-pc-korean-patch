import sys, os, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
G = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND"
key = cs2.crc_key(cs2.passphrase(os.path.join(G, "ISLAND.exe")))
k = cs2.Kif(os.path.join(G, "scene.int"), key)
shapes = Counter(); ex = []
with open(k.path, "rb") as fh:
    for name in ["com01.cst", "com02.cst", "com05.cst", "sum01.cst"]:
        if name.casefold() not in k.by_name:
            print("missing", name); continue
        lines, _ = cs2.parse_cst(k.read(name, fh))
        for typ, raw in lines:
            if typ != 0x30:
                continue
            t = raw.decode("cp932", "replace")
            m = re.match(r"^(\d+) (\S+) (.*)$", t)
            if m and ("_sel" in m.group(2) or "BAD" in m.group(2) or m.group(2)[:3] in ("sum", "lin", "kar", "com")):
                txt = m.group(3)
                shapes["spaces=%d quoted=%s" % (txt.count(" "), txt[:1] in "\"'")] += 1
print(dict(shapes))
