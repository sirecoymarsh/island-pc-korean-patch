"""Scan GOG ISLAND.exe .text for functions that compare a byte against many message-code letters
(p, c, l, f, s, n, w, @, m) close together - candidates for the message escape parser."""
import sys, re, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
p = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND\ISLAND.exe"
pe = pefile.PE(p, fast_load=True); data = open(p, "rb").read(); IB = pe.OPTIONAL_HEADER.ImageBase
t = pe.sections[0]; td = data[t.PointerToRawData:t.PointerToRawData + t.SizeOfRawData]; tva = IB + t.VirtualAddress
md = Cs(CS_ARCH_X86, CS_MODE_32)
letters = {ord(c) for c in "pclfsnwm@r"}
hits = []
# linear sweep in chunks
off = 0
win = []
for ins in md.disasm(td, tva):
    if ins.mnemonic == "cmp":
        ops = ins.op_str.split(", ")
        if len(ops) == 2 and ops[1].startswith("0x"):
            try:
                v = int(ops[1], 16)
            except ValueError:
                continue
            if v in letters or v == 0x5C:
                win.append((ins.address, v))
    # keep window of last 0x300 bytes
    while win and ins.address - win[0][0] > 0x400:
        win.pop(0)
    vals = {v for a, v in win}
    if len(vals) >= 6 and 0x5C in vals:
        hits.append((win[0][0], sorted(chr(v) for v in vals)))
        win = []
seen = set()
for a, v in hits:
    k = a & ~0xFFF
    if k in seen:
        continue
    seen.add(k)
    print(hex(a), "".join(v))
