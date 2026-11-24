import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
p = sys.argv[1]
pe = pefile.PE(p, fast_load=True); data = open(p, "rb").read(); IB = pe.OPTIONAL_HEADER.ImageBase
def strat2(va):
    try:
        off = pe.get_offset_from_rva(va - IB); e = data.index(b"\0", off); s = data[off:e]
        if 0 < len(s) < 100 and all(32 <= c < 127 or c >= 0x80 for c in s):
            return s.decode("cp932", errors="replace")
    except Exception: pass
    return None
start = int(sys.argv[2], 16); end = int(sys.argv[3], 16)
off = pe.get_offset_from_rva(start - IB)
code = data[off: off + (end - start)]
md = Cs(CS_ARCH_X86, CS_MODE_32)
for ins in md.disasm(code, start):
    extra = ""
    for tok in ins.op_str.replace(",", " ").replace("[", " ").replace("]", " ").split():
        if tok.startswith("0x") and len(tok) >= 8:
            s = strat2(int(tok, 16))
            if s: extra += f'   ; "{s}"'
    print(hex(ins.address), ins.mnemonic, ins.op_str, extra)
