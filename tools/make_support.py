"""Support files read by the loader DLL (version.dll) from <game>\\ko\\:
  pua_table.txt  UTF-16LE  "E000<TAB>X"   our PUA code -> real character
  msg_ko.txt     UTF-16LE  "JP<TAB>KO"    Codex's reviewed exe UI strings (MessageBoxA etc.)
  exe_rsrc.bin   header + Codex's Korean .rsrc image (dialogs/menus/string tables)
Usage: python -I make_support.py [--out DIR]
"""
import argparse
import json
import os
import struct
import sys

import pefile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kocodec import Codec  # noqa: E402

ORIG_EXE = r"Y:\AI\island-steam-ko\steam-orig\ISLAND.exe"
CDX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\exe-raw\candidate"
PUA_TABLE = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")


def fnv64(b):
    h = 1469598103934665603
    for x in b:
        h ^= x
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def esc(s):
    return s.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"Y:\AI\island-steam-ko\build\ko")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    codec = Codec.load(PUA_TABLE)
    rows = sorted(codec.pua_map().items())
    with open(os.path.join(args.out, "pua_table.txt"), "w", encoding="utf-16", newline="\n") as f:
        for cp, ch in rows:
            f.write("%04X\t%s\n" % (cp, ch))

    plan = json.load(open(os.path.join(CDX, "exe_raw_memory_plan.json"), encoding="utf-8"))
    seen = {}
    for e in plan["entries"]:
        src, tgt = e["source_raw"], e["target"]
        if not src or src == tgt:
            continue
        if src in seen and seen[src] != tgt:
            continue
        seen[src] = tgt
    # longest patterns first so specific messages win over short captions
    msgs = sorted(seen.items(), key=lambda kv: -len(kv[0]))
    with open(os.path.join(args.out, "msg_ko.txt"), "w", encoding="utf-16", newline="\n") as f:
        for s, t in msgs:
            f.write(esc(s) + "\t" + esc(t) + "\n")

    pe = pefile.PE(ORIG_EXE, fast_load=True)
    sec = [s for s in pe.sections if s.Name.rstrip(b"\0") == b".rsrc"][0]
    raw = pe.__data__[sec.PointerToRawData: sec.PointerToRawData + sec.SizeOfRawData]
    before = open(os.path.join(CDX, "native_rsrc_before.bin"), "rb").read()
    after = open(os.path.join(CDX, "native_rsrc_after.bin"), "rb").read()
    vsize = sec.Misc_VirtualSize
    assert before == bytes(raw), "Codex before.bin is not this exe's .rsrc"
    rplan = json.load(open(os.path.join(CDX, "native_resource_plan.json"), encoding="utf-8"))
    new_dir = [p for p in rplan["patches"] if p["kind"] == "resource_directory_size"][0]
    new_vs = [p for p in rplan["patches"] if p["kind"] == "resource_virtual_size"][0]
    nd = struct.unpack("<I", bytes.fromhex(new_dir["after_hex"]))[0]
    nv = struct.unpack("<I", bytes.fromhex(new_vs["after_hex"]))[0]
    assert struct.unpack("<I", bytes.fromhex(new_dir["before_hex"]))[0] == pe.OPTIONAL_HEADER.DATA_DIRECTORY[2].Size
    hdr = struct.pack("<IIIII", 0x53524B49, 1, sec.VirtualAddress, vsize, vsize) + struct.pack("<Q", fnv64(raw[:vsize])) + struct.pack("<III", len(after), nd, nv)
    with open(os.path.join(args.out, "exe_rsrc.bin"), "wb") as f:
        f.write(hdr + after)
    print(json.dumps({"pua_rows": len(rows), "messages": len(msgs), "rsrc_rva": hex(sec.VirtualAddress), "rsrc_vsize": hex(vsize),
                      "after_len": len(after), "new_dir_size": hex(nd), "new_vsize": hex(nv)}))


if __name__ == "__main__":
    main()
