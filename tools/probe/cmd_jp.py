import sys, os, glob, json, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
W = r"Y:\AI\island-steam-ko\work\ja\scene"
KIT = r"F:\AI\island-gemini\island-ko-kit"
src = [d for d in glob.glob(os.path.join(KIT, "*")) if os.path.isdir(d) and os.path.basename(d).startswith("\uc6d0")][0]
owned = set()
for p in glob.glob(os.path.join(src, "JP*.json")):
    if int(os.path.basename(p)[2:6]) > 487:
        continue
    for e in json.load(open(p, encoding="utf-8"))["entries"]:
        owned.add(e["id"])
JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uff01-\uff5e]")
kinds = Counter(); files = Counter()
for fn in sorted(os.listdir(W)):
    if not fn.endswith(".cst"):
        continue
    lines, _ = cs2.parse_cst(open(os.path.join(W, fn), "rb").read())
    for i, (typ, raw) in enumerate(lines):
        if typ != 0x30:
            continue
        if "scene.int::%s::line_%05d" % (fn, i) in owned:
            continue
        t = raw.decode("cp932", "replace")
        if JP.search(t):
            tok = t.split(" ")[0]
            kinds[re.sub(r"\d+", "9", tok)[:20]] += 1
            files[fn] += 1
print("non-choice commands with Japanese chars, by first token:", kinds.most_common(30))
print("files:", len(files))
