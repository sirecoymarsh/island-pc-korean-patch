"""List HG-3 frame ids with their canvas rectangles (stdinfo). Usage: hg3info.py <entry> [ids...]"""
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"


def frames(blob):
    assert blob[:4] == b"HG-3", blob[:4]
    hdr = struct.unpack_from("<I", blob, 4)[0]
    pos = hdr
    out = []
    while pos + 8 <= len(blob):
        nxt, fid = struct.unpack_from("<II", blob, pos)
        tp = pos + 8
        info = None
        while tp + 16 <= len(blob):
            tag = blob[tp:tp + 8].rstrip(b"\0")
            tnext, tlen = struct.unpack_from("<II", blob, tp + 8)
            if tag == b"stdinfo":
                w, h, bpp, ox, oy, tw, th = struct.unpack_from("<IIIiiII", blob, tp + 16)
                info = (w, h, ox, oy, tw, th)
            if not tnext:
                break
            tp += tnext
        out.append((fid, info))
        if not nxt:
            break
        pos += nxt
    return out


def main():
    name = sys.argv[1]
    want = {int(x) for x in sys.argv[2:]}
    key = cs2.crc_key(cs2.passphrase(os.path.join(ROOT, "steam-orig", "ISLAND.exe")))
    k = cs2.Kif(os.path.join(ROOT, "build", "ko", "image.int"), key)
    for fid, info in frames(k.read(name)):
        if not want or fid in want:
            if info:
                w, h, ox, oy, tw, th = info
                print("frame %d  rect x=%d..%d y=%d..%d  center=(%d,%d)  canvas %dx%d" % (fid, ox, ox + w, oy, oy + h, ox + w // 2, oy + h // 2, tw, th))
            else:
                print("frame %d (no stdinfo)" % fid)


if __name__ == "__main__":
    main()
