import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile, struct, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
p = sys.argv[1]; targets = [int(x, 16) for x in sys.argv[2:]]
pe = pefile.PE(p, fast_load=True); data = open(p, "rb").read(); IB = pe.OPTIONAL_HEADER.ImageBase
text = pe.sections[0]
tdata = data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]; tva = IB + text.VirtualAddress
for t in targets:
    hits = []
    for m in re.finditer(rb"\xe8", tdata):
        a = tva + m.start()
        if m.start() + 5 > len(tdata): continue
        rel = struct.unpack_from("<i", tdata, m.start() + 1)[0]
        if a + 5 + rel == t: hits.append(a)
    # also absolute refs (vtables / push imm)
    absr = [tva + m.start() for m in re.finditer(re.escape(struct.pack("<I", t)), tdata)]
    print(hex(t), "calls:", [hex(h) for h in hits][:20], "absrefs:", [hex(h) for h in absr][:10])
