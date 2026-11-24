import sys, os, difflib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
ORIG = r"Y:\AI\island-steam-ko\steam-orig"
CDX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload"
key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
which = sys.argv[1]  # archive or loose
side = sys.argv[2] if len(sys.argv) > 2 else "ko"
if which == "loose":
    a = open(os.path.join(ORIG, "config", "startup.xml"), "rb").read()
    b = open(os.path.join(CDX, side, "config", "startup.xml"), "rb").read()
else:
    ka = cs2.Kif(os.path.join(ORIG, "config.int"), key); kb = cs2.Kif(os.path.join(CDX, side, "config.int"), key)
    a = ka.read(which); b = kb.read(which)
def dec(x):
    # Codex PUA: decode cp932 (PUA bytes F040.. -> U+E000..)
    return x.decode("cp932", "replace").splitlines()
la, lb = dec(a), dec(b)
n = 0
for line in difflib.unified_diff(la, lb, lineterm="", n=0):
    if line.startswith(("---", "+++", "@@")):
        continue
    print(line[:160]); n += 1
    if n > int(sys.argv[3] if len(sys.argv) > 3 else 60):
        break
