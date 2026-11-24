"""Compare the ISLAND launch option now with the pre-test backup, and list which other lines of
localconfig.vdf differ (Steam rewrites the file itself, e.g. play time)."""
import difflib
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import steam_launchopt as so  # noqa: E402

cur_text = open(so.VDF, encoding="utf-8").read()
bk = sorted(glob.glob(os.path.join(so.BACKUP_DIR, "localconfig.vdf.*")))[0]
bk_text = open(bk, encoding="utf-8").read()
cur = so.find(cur_text)[2]
old = so.find(bk_text)[2]
print("backup:", os.path.basename(bk))
print("launch option equal to backup:", cur == old)
diff = [l for l in difflib.unified_diff(bk_text.splitlines(), cur_text.splitlines(), lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---"))]
keys = {}
for l in diff:
    m = re.match(r'[+-]\s*"([^"]+)"', l)
    keys[m.group(1) if m else l[:30]] = keys.get(m.group(1) if m else l[:30], 0) + 1
print("other differing lines:", len(diff), "by key:", keys)
