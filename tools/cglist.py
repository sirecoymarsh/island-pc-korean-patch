"""config.int/cglist.dat (the CG gallery list cgreg_init reads): header u32 0, u32 0, u32 count, then per
entry u32 size (with itself), name[64], u32 variants, variant names[64] each - the exe reads the count at
entry+0x44 and the variants from +0x48. Entry order = the CG number the gallery scripts use ($522).
Usage (check): python -I cglist.py"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402


def parse(blob):
    count = struct.unpack_from("<I", blob, 8)[0]
    off, out = 12, []
    for _ in range(count):
        size = struct.unpack_from("<I", blob, off)[0]
        name = blob[off + 4:off + 0x44].split(b"\0", 1)[0].decode("ascii")
        n = struct.unpack_from("<I", blob, off + 0x44)[0]
        variants = [blob[off + 0x48 + 0x40 * i:off + 0x88 + 0x40 * i].split(b"\0", 1)[0].decode("ascii") for i in range(n)]
        if size == 0 and len(out) == count - 1:       # the field is the distance to the next entry
            size = 0x48 + 0x40 * n
        if size != 0x48 + 0x40 * n:
            raise ValueError("cglist entry %d: size %d for %d variants" % (len(out), size, n))
        out.append((name, variants))
        off += size
    if off > len(blob) or any(blob[off:]):          # the file ends with a few zero bytes
        raise ValueError("cglist: unexpected tail of %d bytes" % (len(blob) - off))
    return out


def names(orig_dir):
    key = cs2.crc_key(cs2.passphrase(os.path.join(orig_dir, "ISLAND.exe")))
    return [n for n, _ in parse(cs2.Kif(os.path.join(orig_dir, "config.int"), key).read("cglist.dat"))]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = names(r"Y:\AI\island-steam-ko\gog-orig")
    b = names(r"Y:\AI\island-steam-ko\steam-orig")
    print("gog", len(a), "steam", len(b), "same:", a == b, "all start with a letter:", all(x[:1].isalpha() for x in a + b))
