import json, glob, os
K = r"F:\AI\island-gemini\island-ko-kit"
R = r"F:\AI\island-gemini\review\out"
dirs = sorted(glob.glob(os.path.join(K, "*")))
for d in dirs:
    print("DIR", repr(os.path.basename(d).encode('utf-8')), os.path.isdir(d))
tr = [d for d in dirs if os.path.isdir(d)]
for d in tr + [R]:
    fs = sorted(glob.glob(os.path.join(d, "JP0001*.json")))
    if not fs: continue
    o = json.load(open(fs[0], encoding="utf-8"))
    print("==", os.path.basename(d).encode('utf-8'), type(o).__name__, (list(o.keys()) if isinstance(o, dict) else len(o)))
    ents = o if isinstance(o, list) else o.get("entries") or o.get("translations")
    if isinstance(ents, list) and ents:
        e = ents[0]
        print("   entry keys:", list(e.keys()) if isinstance(e, dict) else type(e))
        for k, v in (e.items() if isinstance(e, dict) else []):
            if not isinstance(v, str) or all(ord(c) < 128 for c in v):
                print("     ", k, repr(v)[:100])
            else:
                print("     ", k, "<text len=%d>" % len(v))
