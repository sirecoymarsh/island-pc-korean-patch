import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json, glob, os, collections, re
K = r"F:\AI\island-gemini\island-ko-kit"
R = r"F:\AI\island-gemini\review\out"
dirs = {os.path.basename(d): d for d in glob.glob(os.path.join(K, "*")) if os.path.isdir(d)}
TR = [d for n, d in dirs.items() if n.startswith("\ubc88")][0]   # 번역
SRC = [d for n, d in dirs.items() if n.startswith("\uc6d0")][0]  # 원문
files = sorted(glob.glob(os.path.join(SRC, "JP*.json")))
used = collections.Counter(); n_entries = 0; n_review = 0; n_tr = 0
noncp = collections.Counter(); hangul = set()
for p in files:
    pid = os.path.basename(p)[:6]
    num = int(pid[2:])
    if num > 487: continue
    base = os.path.basename(p)
    rp = os.path.join(R, base); tp = os.path.join(TR, base)
    if os.path.exists(rp): ko = json.load(open(rp, encoding="utf-8")); n_review += 1
    else: ko = json.load(open(tp, encoding="utf-8")); n_tr += 1
    for e in ko:
        t = e["ko"]; n_entries += 1
        for ch in t:
            used[ch] += 1
            try: ch.encode("cp932")
            except UnicodeEncodeError:
                noncp[ch] += 1
            if 0xAC00 <= ord(ch) <= 0xD7A3: hangul.add(ch)
print("packets review/out:", n_review, " translation-only:", n_tr, " entries:", n_entries)
print("distinct chars:", len(used), " distinct non-CP932:", len(noncp), " distinct hangul syllables:", len(hangul))
cats = collections.Counter()
import unicodedata
for ch in noncp:
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3: cats["hangul_syllable"] += 1
    elif 0x3130 <= o <= 0x318F: cats["hangul_compat_jamo"] += 1
    else: cats["other:" + unicodedata.category(ch)] += 1
print(dict(cats))
others = [(hex(ord(c)), unicodedata.name(c, "?"), noncp[c]) for c in noncp if not (0xAC00 <= ord(c) <= 0xD7A3)]
print("non-hangul non-cp932 chars:", others[:60])
# KS X 1001 coverage (cp949 encodable via euc-kr subset)
not_ksx = [c for c in hangul if len(c.encode("euc_kr", errors="ignore")) == 0]
print("hangul not in KS X 1001 (2350):", len(not_ksx))
