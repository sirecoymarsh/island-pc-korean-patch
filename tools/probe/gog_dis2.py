import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("gog_xref.py", encoding="utf-8").read().split("targets = {}")[0])
md = Cs(CS_ARCH_X86, CS_MODE_32)
def strat2(va):
    try:
        off = pe.get_offset_from_rva(va - IB); e = data.index(b"\0", off); s = data[off:e]
        if 0 < len(s) < 80 and all(32 <= c < 127 for c in s): return s.decode()
    except Exception: pass
    return None
start = int(sys.argv[1], 16); end = int(sys.argv[2], 16)
code = tdata[start - tva: end - tva]
for ins in md.disasm(code, start):
    extra = ""
    for tok in ins.op_str.replace(",", " ").replace("[", " ").replace("]", " ").split():
        if tok.startswith("0x"):
            v = int(tok, 16)
            s = strat2(v)
            if s: extra += f'   ; "{s}"'
    print(hex(ins.address), ins.mnemonic, ins.op_str, extra)
