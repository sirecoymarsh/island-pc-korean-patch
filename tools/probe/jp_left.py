import sys, os, json, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kit
J = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff\uff66-\uff9f]")
RUBY = re.compile(r"\[([^\[\]]*)\]")
entries, _ = kit.load()
rep = json.load(open(r"Y:\AI\island-steam-ko\build\text_report.json", encoding="utf-8"))
ids = set(rep["problem_ids"].get("japanese_left", []))
rids = set(rep["problem_ids"].get("ruby_shape", []))
chars = Counter(); where = Counter(); per_entry_kinds = Counter(); origin = Counter(); packets = Counter()
rshape = Counter()
for e in entries:
    if e["id"] in ids:
        ko = e["ko"]
        inruby = "".join(m.group(1) for m in RUBY.finditer(ko))
        outside = RUBY.sub("", ko)
        cs = J.findall(ko)
        chars.update(cs)
        kinds = set()
        for c in cs:
            if c in "\u30fb\u30fc\u30fd\u30fe\u3005":
                kinds.add("punct-like")
            elif c in inruby and c not in outside:
                kinds.add("inside-ruby")
            else:
                kinds.add("text")
        per_entry_kinds["+".join(sorted(kinds))] += 1
        origin[e["origin"]] += 1
        packets[e["packet"][:6]] += 1
    if e["id"] in rids:
        for m in RUBY.finditer(e["ko"]):
            g = m.group(1)
            rshape["slashes=%d empty_part=%s" % (g.count("/"), any(not x.strip() for x in g.split("/")))] += 1
print("japanese chars (char:count):", chars.most_common(40))
print("entry kinds:", dict(per_entry_kinds))
print("origin:", dict(origin), " packets:", len(packets))
print("ruby shapes in flagged entries:", dict(rshape))
