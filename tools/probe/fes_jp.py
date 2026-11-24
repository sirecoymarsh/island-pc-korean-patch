import sys, os, zlib, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
ORIG = r"Y:\AI\island-steam-ko\steam-orig"
CDX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\ko"
key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
a = cs2.Kif(os.path.join(ORIG, "fes.int"), key); b = cs2.Kif(os.path.join(CDX, "fes.int"), key)
def lines(k, n):
    return zlib.decompress(k.read(n)[16:]).decode("cp932", "replace").splitlines()
tot = Counter()
for e in a.entries:
    la = lines(a, e["name"]); lb = lines(b, e["name"])
    def jp_lines(L):
        out = []
        for i, l in enumerate(L):
            code = l.split("//")[0]
            if JP.search(code):
                out.append(i)
        return out
    ja, jb = jp_lines(la), jp_lines(lb)
    if ja or jb:
        tot["orig"] += len(ja); tot["codex_left"] += len(jb)
        print("%-22s orig_jp_lines=%3d codex_ko_left=%3d" % (e["name"], len(ja), len(jb)))
print(dict(tot))
