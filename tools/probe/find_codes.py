"""Byte-pattern scan of the GOG ISLAND.exe (unencrypted, same engine family) for the message
escape-code parser: clusters of 'cmp <r8/m8>, imm8' against f, l, s, n, p, c, w near each other."""
import sys, re
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
p = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND\ISLAND.exe"
pe = pefile.PE(p, fast_load=True); data = open(p, "rb").read(); IB = pe.OPTIONAL_HEADER.ImageBase
t = pe.sections[0]; td = data[t.PointerToRawData:t.PointerToRawData + t.SizeOfRawData]; tva = IB + t.VirtualAddress
md = Cs(CS_ARCH_X86, CS_MODE_32)
want = {ord(c): c for c in "flsnpcwmr@"}
hits = defaultdict(set)
# candidate instruction starts: decode at every offset where the byte looks like a cmp opcode
for m in re.finditer(rb"[\x3c\x80\x83]", td):
    off = m.start()
    try:
        ins = next(md.disasm(td[off:off + 8], tva + off, 1))
    except StopIteration:
        continue
    if ins.mnemonic != "cmp":
        continue
    ops = ins.op_str.split(", ")
    if len(ops) != 2 or not ops[1].startswith("0x"):
        continue
    try:
        v = int(ops[1], 16)
    except ValueError:
        continue
    if v in want:
        hits[(tva + off) >> 8].add(want[v])
best = []
for blk, s in hits.items():
    s2 = set(s) | hits.get(blk - 1, set()) | hits.get(blk + 1, set())
    if {"f", "l", "s", "n"} <= s2:
        best.append((len(s2), blk << 8, "".join(sorted(s2))))
for n, a, s in sorted(best, reverse=True)[:15]:
    print(hex(a), s)
