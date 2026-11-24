"""A copy of the GOG (English build) game folder that looks like Steam with the game language set to
English (depot 857451): every file the same, ISLAND.exe given a SteamStub-like ".bind" section at the
end of the file (146,800 bytes, so the exe is 7,219,056 bytes like Steam's). Not SteamStub at all -
the section is filler, the exe still runs as the GOG exe. For installer / DLL edition tests only.
Usage: python -I make_fake_steam_en.py [DST]   (default Y:\\AI\\island-steam-ko\\steam-en-fake-orig)"""
import os
import shutil
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = r"Y:\AI\island-steam-ko\gog-orig"
STEAM_JP = r"Y:\AI\island-steam-ko\steam-orig\ISLAND.exe"
DST = sys.argv[1] if len(sys.argv) > 1 else r"Y:\AI\island-steam-ko\steam-en-fake-orig"
BIND_SIZE = 7219056 - 7072256        # Steam English exe - GOG exe = the .bind section of Steam's exe


def align(v, a):
    return (v + a - 1) // a * a


def sections(b):
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    n = struct.unpack_from("<H", b, pe + 6)[0]
    opt = pe + 24
    secs = opt + struct.unpack_from("<H", b, pe + 20)[0]
    return pe, opt, secs, n


def add_bind(exe):
    b = bytearray(open(exe, "rb").read())
    pe, opt, secs, n = sections(b)
    names = [bytes(b[secs + 40 * i:secs + 40 * i + 8]).rstrip(b"\0") for i in range(n)]
    if b".bind" in names:
        print("already has .bind:", names)
        return
    assert struct.unpack_from("<H", b, opt)[0] == 0x10B, "PE32 expected"
    sect_align, file_align = struct.unpack_from("<II", b, opt + 32)
    size_of_headers = struct.unpack_from("<I", b, opt + 60)[0]
    sec_dir = struct.unpack_from("<II", b, opt + 96 + 4 * 8)   # certificate table
    assert sec_dir == (0, 0), "signed exe - appending would break the signature"
    new = secs + 40 * n
    assert new + 40 <= size_of_headers and not any(b[new:new + 40]), "no room for another section header"
    last_va, last_vs = struct.unpack_from("<II", b, secs + 40 * (n - 1) + 12)[0], struct.unpack_from("<I", b, secs + 40 * (n - 1) + 8)[0]
    last_raw, last_rs = struct.unpack_from("<II", b, secs + 40 * (n - 1) + 20)[0], struct.unpack_from("<I", b, secs + 40 * (n - 1) + 16)[0]
    assert last_raw + last_rs == len(b), "data after the last section"
    # characteristics of the real SteamStub section (Steam's Japanese exe)
    j = open(STEAM_JP, "rb").read(4096)
    jpe, jopt, jsecs, jn = sections(j)
    jch = None
    for i in range(jn):
        if j[jsecs + 40 * i:jsecs + 40 * i + 5] == b".bind":
            jch = struct.unpack_from("<I", j, jsecs + 40 * i + 36)[0]
    va = align(last_va + last_vs, sect_align)
    raw = len(b)
    assert raw % file_align == 0
    struct.pack_into("<8sIIIIIIHHI", b, new, b".bind", BIND_SIZE, va, BIND_SIZE, raw, 0, 0, 0, 0, jch)
    struct.pack_into("<H", b, pe + 6, n + 1)
    struct.pack_into("<I", b, opt + 56, va + align(BIND_SIZE, sect_align))   # SizeOfImage
    filler = bytearray(BIND_SIZE)
    tag = b"island-ko test copy: not SteamStub, a filler section named .bind (Steam English exe stand-in)"
    filler[:len(tag)] = tag
    b += filler
    tmp = exe + ".tmp"
    open(tmp, "wb").write(b)
    os.replace(tmp, exe)
    print("ISLAND.exe: .bind added at VA 0x%x, raw 0x%x, characteristics 0x%08x, file %d bytes" % (va, raw, jch, len(b)))


def main():
    n = 0
    for r, ds, fs in os.walk(SRC):
        for f in fs:
            p = os.path.join(r, f)
            q = os.path.join(DST, os.path.relpath(p, SRC))
            if os.path.exists(q) and (os.path.getsize(q) == os.path.getsize(p) or os.path.basename(q) == "ISLAND.exe"):
                continue
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.copy2(p, q)   # a real copy - never a hard link to the GOG copy
            n += 1
    print("copied %d files into %s" % (n, DST))
    add_bind(os.path.join(DST, "ISLAND.exe"))


if __name__ == "__main__":
    main()
