import os, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
paths = [("steam loose", r"Y:\AI\island-steam-ko\steam-orig\config\startup.xml"),
         ("gog pre", r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\system-voice-20261028\runtime\startup.pre-caption-vram.xml"),
         ("gog patched", r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\system-voice-20261028\runtime\gog-test\config\startup.xml")]
for name, p in paths:
    if not os.path.exists(p):
        print("missing", name)
        continue
    t = open(p, "rb").read().decode("cp932", "replace")
    hits = [m.start() for m in re.finditer("4352", t)]
    print("==", name, "hits", len(hits))
    for h in hits[:3]:
        s = t.rfind("\n", 0, max(0, h - 160))
        e = t.find("\n", h + 80)
        print(re.sub(r"[^\x00-\x7f]+", "~", t[s:e]))
