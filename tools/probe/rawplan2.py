import sys, json, collections; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\exe-raw\candidate"
p = json.load(open(D + r"\exe_raw_memory_plan.json", encoding="utf-8"))
E = p["entries"]
print(collections.Counter(e["method"] for e in E))
cons = collections.Counter()
for e in E:
    for c in e.get("consumers") or []:
        cons[str(c)[:60]] += 1
print(cons.most_common(15))
print(collections.Counter(x["kind"] for x in p["patches"]))
print(p["counts"]); print(p["limitations"])
for e in E[:12]:
    print(hex(e["source_rva"]), e["method"], repr(e["source_raw"])[:60], "->", repr(e["target"])[:50])
