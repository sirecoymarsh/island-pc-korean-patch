import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile, struct, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
p = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND\ISLAND.exe"
pe = pefile.PE(p); data = open(p, "rb").read(); IB = pe.OPTIONAL_HEADER.ImageBase
text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
tdata = data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
tva = IB + text.VirtualAddress
def find_refs(va):
    pat = struct.pack("<I", va)
    return [tva + m.start() for m in re.finditer(re.escape(pat), tdata)]
def strat(va):
    off = pe.get_offset_from_rva(va - IB); e = data.index(b"\0", off); return data[off:e]
targets = {}
for s in [b"default.ttf", b"font", b"FreeType : Face Load Error! > %s"]:
    for m in re.finditer(re.escape(s) + b"\0", data):
        off = m.start()
        try: va = IB + pe.get_rva_from_offset(off)
        except Exception: continue
        if not (0x809000 <= va < 0x90b000): continue
        refs = find_refs(va)
        if refs: targets[(s, va)] = refs
for k, v in targets.items(): print(k[0], hex(k[1]), [hex(x) for x in v][:10])
md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = False
def dis(va, before=0x60, after=0xC0):
    start = va - before
    code = tdata[start - tva: start - tva + before + after]
    for ins in md.disasm(code, start):
        mark = "  <==" if ins.address == va or (ins.address < va < ins.address + ins.size) else ""
        print(hex(ins.address), ins.mnemonic, ins.op_str, mark)
for k, v in targets.items():
    if k[0] == b"default.ttf":
        for r in v[:2]:
            print("==== ref", hex(r)); dis(r - 1, 0x80, 0x140)
