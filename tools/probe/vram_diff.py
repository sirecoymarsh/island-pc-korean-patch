import difflib, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
a = open(r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\system-voice-20261028\runtime\startup.pre-caption-vram.xml", "rb").read().decode("cp932", "replace").splitlines()
b = open(r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\system-voice-20261028\runtime\gog-test\config\startup.xml", "rb").read().decode("cp932", "replace").splitlines()
for l in difflib.unified_diff(a, b, lineterm="", n=6):
    print(re.sub(r"[^\x00-\x7f]+", "~", l)[:140])
