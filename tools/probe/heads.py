import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import glob, os, re
K = r"F:\AI\island-gemini\island-ko-kit"
p = sorted(glob.glob(os.path.join(K, "00_*.md")))[0]
for i, line in enumerate(open(p, encoding="utf-8"), 1):
    if line.startswith("#"):
        print(i, line.rstrip())
