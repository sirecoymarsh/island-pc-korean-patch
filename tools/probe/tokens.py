import sys, os, glob, json, re
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KIT = r"F:\AI\island-gemini\island-ko-kit"
REV = r"F:\AI\island-gemini\review\out"
dirs = {os.path.basename(d)[:1]: d for d in glob.glob(os.path.join(KIT, "*")) if os.path.isdir(d)}
SRC, TR = dirs["\uc6d0"], dirs["\ubc88"]
CODE = re.compile(r"\\[A-Za-z@]+[0-9;]*|\\.")
RUBY = re.compile(r"\[([^\[\]]*)\]")
src_codes = Counter(); ko_codes = Counter(); ruby_src = Counter(); ruby_ko = Counter()
mismatch_codes = 0; mismatch_ruby = 0; dollar = Counter(); other_brackets = Counter()
n = 0
for p in sorted(glob.glob(os.path.join(SRC, "JP*.json"))):
    if int(os.path.basename(p)[2:6]) > 487:
        continue
    pk = json.load(open(p, encoding="utf-8"))
    base = os.path.basename(p)
    rp = os.path.join(REV, base)
    ko = {e["id"]: e for e in json.load(open(rp if os.path.exists(rp) else os.path.join(TR, base), encoding="utf-8"))}
    for e in pk["entries"]:
        s = e["source_raw"]; k = ko[e["id"]]["ko"]; n += 1
        cs = CODE.findall(s); ck = CODE.findall(k)
        src_codes.update(cs); ko_codes.update(ck)
        if cs != ck:
            mismatch_codes += 1
        rs = RUBY.findall(s); rk = RUBY.findall(k)
        for r in rs:
            ruby_src["slash" if "/" in r else ("colon" if ":" in r else "plain")] += 1
        for r in rk:
            ruby_ko["slash" if "/" in r else ("colon" if ":" in r else "plain")] += 1
        if len(rs) != len(rk):
            mismatch_ruby += 1
        for ch in "$#{}<>|":
            if ch in k:
                dollar[ch] += 1
            if ch in s:
                other_brackets[ch] += 1
print("entries", n)
print("codes in source:", src_codes.most_common(30))
print("codes in ko:", ko_codes.most_common(30))
print("entries whose code sequence differs:", mismatch_codes)
print("ruby src:", dict(ruby_src), " ruby ko:", dict(ruby_ko), " entries with ruby count diff:", mismatch_ruby)
print("special chars in ko:", dict(dollar), " in src:", dict(other_brackets))
