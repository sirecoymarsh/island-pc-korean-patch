import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile, re
p = r"Y:\SteamLibrary\steamapps\common\ISLAND\ISLAND.exe"
pe = pefile.PE(p)
print("Machine", hex(pe.FILE_HEADER.Machine), "EntryRVA", hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint), "ImageBase", hex(pe.OPTIONAL_HEADER.ImageBase))
for s in pe.sections:
    print("SEC", s.Name.rstrip(b"\0"), hex(s.VirtualAddress), hex(s.Misc_VirtualSize), hex(s.SizeOfRawData), "entropy=%.2f" % s.get_entropy())
want = re.compile(r"Font|Glyph|TextOut|ExtTextOut|MultiByte|WideChar|CodePage|ACP|Locale|DrawText|GetTextExtent|CharNext|IsDBCS", re.I)
for imp in pe.DIRECTORY_ENTRY_IMPORT:
    names = [i.name.decode() for i in imp.imports if i.name]
    hit = [n for n in names if want.search(n)]
    print("DLL", imp.dll.decode(), len(names), hit)
data = open(p, "rb").read()
for pat in [rb"font\\", rb"\.ttf", rb"\.otf", rb"FONT", rb"faceruby", rb"steam_appid", rb"language", rb"cs2conf"]:
    hits = [m.start() for m in re.finditer(pat, data)]
    print(pat, len(hits), [hex(h) for h in hits[:6]])
