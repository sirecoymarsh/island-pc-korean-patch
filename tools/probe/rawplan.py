import sys, json, collections; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\exe-raw\candidate"
p = json.load(open(D + r"\exe_raw_memory_plan.json", encoding="utf-8"))
print(type(p).__name__, list(p.keys())[:30] if isinstance(p, dict) else len(p))
for k, v in (p.items() if isinstance(p, dict) else []):
    if isinstance(v, list):
        print(k, "list", len(v))
        if v and isinstance(v[0], dict): print("  keys", list(v[0].keys()))
    elif isinstance(v, dict): print(k, "dict", list(v.keys())[:20])
    else: print(k, repr(v)[:150])
n = json.load(open(D + r"\native_resource_plan.json", encoding="utf-8"))
print("native plan:", json.dumps(n, ensure_ascii=False)[:1500])
