"""Copy the Steam JP install (read-only source) to a pristine reference folder and verify
against Codex's recorded snapshot. Prints only file names/sizes/hash status."""
import sys, os, json, hashlib, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = r"Y:\SteamLibrary\steamapps\common\ISLAND"
DST = r"Y:\AI\island-steam-ko\steam-orig"
SNAP = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\logs\steam-ja-snapshot.json"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""): h.update(b)
    return h.hexdigest()
snap = {r["path"]: r for r in json.load(open(SNAP, encoding="utf-8"))["files"]}
rows = []; bad = 0
for root, dirs, files in os.walk(SRC):
    for fn in files:
        p = os.path.join(root, fn); rel = os.path.relpath(p, SRC).replace("\\", "/")
        q = os.path.join(DST, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        d = sha(p)
        if not os.path.exists(q) or os.path.getsize(q) != os.path.getsize(p) or sha(q) != d:
            shutil.copy2(p, q)
        assert sha(q) == d
        st = "same-as-codex" if rel in snap and snap[rel]["sha256"] == d else ("DIFF" if rel in snap else "new")
        if st != "same-as-codex": bad += 1
        rows.append({"path": rel, "size": os.path.getsize(p), "sha256": d, "vs_codex_snapshot": st})
missing = sorted(set(snap) - {r["path"] for r in rows})
json.dump({"source": SRC, "copy": DST, "files": rows, "missing_vs_codex": missing}, open(os.path.join(DST, "..", "steam-orig.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("files", len(rows), "total bytes", sum(r["size"] for r in rows), "not-same", bad, "missing", missing)
for r in rows:
    if r["vs_codex_snapshot"] != "same-as-codex": print("  ", r["path"], r["vs_codex_snapshot"])
print("exe sha256", [r["sha256"] for r in rows if r["path"] == "ISLAND.exe"])
