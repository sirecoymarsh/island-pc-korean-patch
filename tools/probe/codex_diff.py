import sys, os, hashlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
ORIG = r"Y:\AI\island-steam-ko\steam-orig"
CDX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload"
key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
h = lambda b: hashlib.sha256(b).hexdigest()[:12]
for arc in ["config.int", "fes.int"]:
    for side in ["ja", "ko"]:
        a = cs2.Kif(os.path.join(ORIG, arc), key)
        b = cs2.Kif(os.path.join(CDX, side, arc), key)
        names_a = [e["name"] for e in a.entries]; names_b = [e["name"] for e in b.entries]
        print("==", arc, side, "entries orig", len(names_a), "codex", len(names_b), "same names/order", names_a == names_b)
        fa = open(a.path, "rb"); fb = open(b.path, "rb")
        for e in b.entries:
            nb = b.read(e["name"], fb)
            if e["name"].casefold() in a.by_name:
                na = a.read(e["name"], fa)
                if na != nb:
                    print("   changed", e["name"], len(na), "->", len(nb))
            else:
                print("   added", e["name"], len(nb))
        for n in set(x.casefold() for x in names_a) - set(x.casefold() for x in names_b):
            print("   removed", n)
for side in ["ja", "ko"]:
    for f in ["ISLAND.exe", "cs2conf.dll", "config/startup.xml", "image.int"]:
        p = os.path.join(CDX, side, f); q = os.path.join(ORIG, f)
        if not os.path.exists(p):
            print(side, f, "absent"); continue
        same = os.path.getsize(p) == os.path.getsize(q) and (f == "image.int" or open(p, "rb").read() == open(q, "rb").read())
        print(side, f, os.path.getsize(q), "->", os.path.getsize(p), "identical" if same else "DIFFERENT")
    md = os.path.join(CDX, side, "manual")
    for root, ds, fs in os.walk(md):
        for fn in fs:
            p = os.path.join(root, fn); rel = os.path.relpath(p, os.path.join(CDX, side))
            q = os.path.join(ORIG, rel)
            st = "new" if not os.path.exists(q) else ("same" if open(p, "rb").read() == open(q, "rb").read() else "changed")
            if st != "same":
                print(side, rel, st)
