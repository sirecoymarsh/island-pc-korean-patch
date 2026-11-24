import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile, re
p = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND\ISLAND.exe"
pe = pefile.PE(p)
print("EntryRVA", hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint), "ImageBase", hex(pe.OPTIONAL_HEADER.ImageBase))
for s in pe.sections:
    print("SEC", s.Name.rstrip(b"\0"), hex(s.VirtualAddress), hex(s.Misc_VirtualSize), hex(s.SizeOfRawData), hex(s.PointerToRawData), "entropy=%.2f" % s.get_entropy())
want = re.compile(r"Font|Glyph|TextOut|MultiByte|WideChar|ACP", re.I)
for imp in pe.DIRECTORY_ENTRY_IMPORT:
    names = [i.name.decode() for i in imp.imports if i.name]
    hit = [n for n in names if want.search(n)]
    if hit: print("DLL", imp.dll.decode(), hit)
data = open(p, "rb").read()
for pat in [rb"default\.ttf", rb"FreeType : Face Load Error"]:
    for m in re.finditer(pat, data):
        off = m.start(); rva = pe.get_rva_from_offset(off)
        print(pat, hex(off), "VA", hex(pe.OPTIONAL_HEADER.ImageBase + rva))
