# Print packet schema (keys/types only, no text content)
import json, glob, os, sys, collections
K = r"F:\AI\island-gemini\island-ko-kit"
src = sorted(glob.glob(os.path.join(K, "*", "JP0001-*.json")))
for p in src:
    d = json.load(open(p, encoding="utf-8"))
    print("FILE", os.path.basename(os.path.dirname(p)), os.path.basename(p))
    def walk(o, path="", depth=0):
        if depth > 4: return
        if isinstance(o, dict):
            for k, v in o.items():
                t = type(v).__name__
                extra = f" len={len(v)}" if isinstance(v, (list, dict)) else ""
                if isinstance(v, (int, float, bool)) or (isinstance(v, str) and all(ord(c) < 128 for c in v) and len(v) < 80):
                    extra += f" val={v!r}"
                print("  " * depth + f"{path}.{k}: {t}{extra}")
                if isinstance(v, (dict,)): walk(v, path + "." + k, depth + 1)
                elif isinstance(v, list) and v: walk(v[0], path + "." + k + "[0]", depth + 1)
    walk(d)
