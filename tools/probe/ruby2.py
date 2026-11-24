import sys, os, json, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kit
RUBY = re.compile(r"\[([^\[\]]*)\]")
entries, _ = kit.load()
rep = json.load(open(r"Y:\AI\island-steam-ko\build\text_report.json", encoding="utf-8"))
rids = set(rep["problem_ids"].get("ruby_shape", []))
def shape(g):
    b, _, r = g.partition("/")
    cls = lambda s: "empty" if not s.strip() else ("dots" if set(s) <= set("・.･…‥﹅﹒") else "text")
    return "base=%s ruby=%s" % (cls(b), cls(r))
src_sh = Counter(); ko_sh = Counter(); flagged_src = Counter()
for e in entries:
    for m in RUBY.finditer(e["source_raw"]): src_sh[shape(m.group(1))] += 1
    for m in RUBY.finditer(e["ko"] or ""): ko_sh[shape(m.group(1))] += 1
    if e["id"] in rids:
        for m in RUBY.finditer(e["source_raw"]): flagged_src[shape(m.group(1))] += 1
print("source ruby shapes:", dict(src_sh))
print("ko ruby shapes:", dict(ko_sh))
print("flagged entries - their source ruby shapes:", dict(flagged_src))
for e in entries:
    for side, t in (("src", e["source_raw"]), ("ko", e["ko"] or "")):
        for m in RUBY.finditer(t):
            b, _, r = m.group(1).partition("/")
            if not b.strip():
                print(side, e["packet"][:6], "base=%r ruby=%r" % (b, r))
