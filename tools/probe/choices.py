import sys, os, glob, json, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
W = r"Y:\AI\island-steam-ko\work\ja\scene"
KIT = r"F:\AI\island-gemini\island-ko-kit"
src = [d for d in glob.glob(os.path.join(KIT, "*")) if os.path.isdir(d) and os.path.basename(d).startswith("\uc6d0")][0]
cache = {}
shapes = Counter(); extra_keys = Counter()
for p in sorted(glob.glob(os.path.join(src, "JP*.json"))):
    if int(os.path.basename(p)[2:6]) > 487:
        continue
    for e in json.load(open(p, encoding="utf-8"))["entries"]:
        if e["line_type"] != 48:
            continue
        extra_keys.update(k for k in e.keys())
        _, fn, ln = e["id"].split("::")
        if fn not in cache:
            cache[fn] = cs2.parse_cst(open(os.path.join(W, fn), "rb").read())[0]
        cmd = cache[fn][int(ln.split("_")[1])][1].decode("cp932")
        masked = cmd.replace(e["source_raw"], "<T>", 1) if e["source_raw"] else cmd + " <EMPTY>"
        masked = re.sub(r"[^\x00-\x7f<>]", "J", masked)
        shapes[masked[:60]] += 1
print("entry keys:", dict(extra_keys))
for s, n in shapes.most_common(30):
    print(n, s)
