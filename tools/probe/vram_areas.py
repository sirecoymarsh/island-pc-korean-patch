import re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
t = open(r"Y:\AI\island-steam-ko\steam-orig\config\startup.xml", "rb").read().decode("cp932", "replace")
i = t.find("<area00>")
blk = t[t.rfind("<", 0, t.rfind("\n", 0, i - 200)):]
s = t.rfind("\n", 0, i - 400)
seg = t[s: t.find("<bpp>", i) + 40]
print(re.sub(r"[^\x00-\x7f]+", "~", seg))
areas = re.findall(r"<area(\d+)>\s*<sx>(\d+)</sx>\s*<sy>(\d+)</sy>\s*<dx>(\d+)</dx>\s*<dy>(\d+)</dy>", seg)
print("areas (256px units):", areas)
