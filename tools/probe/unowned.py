import sys, os, glob, json, re
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cs2
W = r"Y:\AI\island-steam-ko\work\ja\scene"
KIT = r"F:\AI\island-gemini\island-ko-kit"
src = [d for d in glob.glob(os.path.join(KIT, "*")) if os.path.isdir(d) and os.path.basename(d).startswith("\uc6d0")][0]
owned = {}
owned_text = defaultdict(list)
for p in sorted(glob.glob(os.path.join(src, "JP*.json"))):
    if int(os.path.basename(p)[2:6]) > 487:
        continue
    for e in json.load(open(p, encoding="utf-8"))["entries"]:
        owned[e["id"]] = e
        owned_text[(e["line_type"], e["source_raw"])].append(e["id"])
CODE = re.compile(r"\\(?:n|pc|pl|pr)|\s|\u3000")
norm = lambda s: CODE.sub("", s)
owned_norm = defaultdict(list)
for (t, s), ids in owned_text.items():
    owned_norm[(t, norm(s))].extend(ids)
per_file = Counter(); jp = Counter(); files_with = Counter()
dup_owned = 0; dup_norm = 0; unique_left = Counter()
for fn in sorted(os.listdir(W)):
    if not fn.endswith(".cst"):
        continue
    lines, meta = cs2.parse_cst(open(os.path.join(W, fn), "rb").read())
    n_owned = sum(1 for i in range(len(lines)) if "scene.int::%s::line_%05d" % (fn, i) in owned)
    for i, (typ, raw) in enumerate(lines):
        if typ not in (0x20, 0x21):
            continue
        ident = "scene.int::%s::line_%05d" % (fn, i)
        if ident in owned:
            continue
        t = raw.decode("cp932")
        if not norm(t):
            continue
        per_file[fn] += 1
        files_with["owned-file" if n_owned else "file-without-packets"] += 1
        if (typ, t) in owned_text:
            dup_owned += 1
        elif (typ, norm(t)) in owned_norm:
            dup_norm += 1
        else:
            unique_left[fn] += 1
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", t):
            jp[typ] += 1
print("files with unowned nonempty lines:", len(per_file), " top:", per_file.most_common(6))
print("located in:", dict(files_with))
print("exact duplicate of owned line:", dup_owned, " duplicate ignoring codes/space:", dup_norm, " no match:", sum(unique_left.values()), unique_left.most_common(8))
print("with Japanese chars by type:", dict(jp))

chars = Counter(); shapes = Counter()
for fn in sorted(os.listdir(W)):
    if not fn.endswith(".cst"):
        continue
    lines, meta = cs2.parse_cst(open(os.path.join(W, fn), "rb").read())
    for i, (typ, raw) in enumerate(lines):
        if typ not in (0x20, 0x21):
            continue
        if "scene.int::%s::line_%05d" % (fn, i) in owned:
            continue
        t = raw.decode("cp932")
        if not norm(t):
            continue
        chars.update(norm(t))
        shapes[re.sub(r"[A-Za-z0-9]", "a", t)[:12]] += 1
print("chars in unowned lines:", chars.most_common(40))
print("shapes:", shapes.most_common(12))
