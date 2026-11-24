"""HG-3 (CatSystem2 image) read / lossless write.

Decoder and img0000 encoder follow Codex's 10-28 tools
(`アイランド\scripts\inspect_hg3.py`, `parallel-ui-20261028\lane5-integration\codec\island_asset_patch.py`,
algorithm reference GARbro ImageHG3.cs, MIT). Kept here so the patch build does not import from the
Codex folder.

frames(blob)            -> [{'id','offset','length','width','height','bpp','x','y','canvas_width','canvas_height','tags'}]
decode(blob, frame)     -> PIL image (RGBA for 32 bpp / jpg+alpha, RGB for 24 bpp)
replace(blob, {fid: im})-> new blob; replaced frames are written as one lossless img0000 tag
                           (img_jpg/img_al frames are converted), every other byte kept.
"""
import io
import struct
import zlib

import numpy as np
from PIL import Image


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def frames(b):
    if b[:4] != b"HG-3" or u32(b, 4) != 12:
        raise ValueError("not HG-3")
    off = 12
    out = []
    seen = set()
    while off < len(b):
        if off in seen:
            raise ValueError("frame loop")
        seen.add(off)
        nxt, fid = struct.unpack_from("<II", b, off)
        end = off + nxt if nxt else len(b)
        p = off + 8
        tags = []
        while p < end:
            tag = b[p:p + 8].split(b"\0", 1)[0].decode("ascii")
            step, size = struct.unpack_from("<II", b, p + 8)
            if p + 16 + size > end:
                raise ValueError("tag overflow")
            tags.append({"tag": tag, "offset": p, "length": size, "step": step})
            if not step:
                break
            p += step
        if tags[0]["tag"] != "stdinfo":
            raise ValueError("no stdinfo")
        st = tags[0]["offset"] + 16
        w, h, bpp, x, y, cw, ch = struct.unpack_from("<IIIiiII", b, st)
        out.append({"id": fid, "offset": off, "length": end - off, "next": nxt, "width": w, "height": h,
                    "bpp": bpp, "x": x, "y": y, "canvas_width": cw, "canvas_height": ch, "tags": tags})
        if not nxt:
            break
        off += nxt
    return out


class _Bits:
    def __init__(self, b):
        self.b = b
        self.i = 0

    def bit(self):
        v = (self.b[self.i // 8] >> (self.i % 8)) & 1
        self.i += 1
        return v

    def gamma(self):
        n = 0
        while not self.bit():
            n += 1
            if n >= 32:
                raise ValueError("gamma overflow")
        v = 1
        for _ in range(n):
            v = v * 2 + self.bit()
        return v


def decode(b, f):
    w, h, px = f["width"], f["height"], f["bpp"] // 8
    tags = {t["tag"]: t for t in f["tags"]}
    if "img_jpg" in tags:
        t = tags["img_jpg"]
        im = Image.open(io.BytesIO(b[t["offset"] + 16:t["offset"] + 16 + t["length"]])).convert("RGBA")
        if "img_al" in tags:
            p = tags["img_al"]["offset"] + 16
            comp, n = struct.unpack_from("<II", b, p)
            alpha = zlib.decompress(b[p + 8:p + 8 + comp])
            if len(alpha) != n or n != w * h:
                raise ValueError("bad img_al")
            im.putalpha(Image.frombytes("L", (w, h), alpha))
        return im
    t = tags.get("img0000")
    if not t:
        raise ValueError("no image tag: %s" % list(tags))
    p = t["offset"] + 16
    start, rows, dp, du, cp, cu = struct.unpack_from("<6I", b, p)
    if start != 0 or rows != h:
        raise ValueError("partial img0000 not supported")
    data = zlib.decompress(b[p + 24:p + 24 + dp])
    ctl = zlib.decompress(b[p + 24 + dp:p + 24 + dp + cp])
    bits = _Bits(ctl)
    copy = bool(bits.bit())
    n = bits.gamma()
    packed = bytearray(n)
    src = dst = 0
    while dst < n:
        count = bits.gamma()
        if copy:
            packed[dst:dst + count] = data[src:src + count]
            src += count
        dst += count
        copy = not copy
    q = np.frombuffer(bytes(packed), dtype=np.uint8).reshape(4, -1).astype(np.uint32)
    tables = []
    for i in range(4):
        vals = np.arange(256, dtype=np.uint32)
        tables.append((((vals & 0xC0) << 18) | ((vals & 0x30) << 12) | ((vals & 0x0C) << 6) | (vals & 3)) << (6 - i * 2))
    vals = tables[0][q[0]] | tables[1][q[1]] | tables[2][q[2]] | tables[3][q[3]]
    raw = np.frombuffer(vals.astype("<u4").tobytes(), dtype=np.uint8).astype(np.int16)
    raw = np.where(raw & 1, (raw >> 1) ^ 255, raw >> 1).astype(np.uint8)
    pix = raw[:w * h * px].reshape(h, w, px).copy()
    pix[0] = np.cumsum(pix[0], axis=0, dtype=np.uint32).astype(np.uint8)
    pix = np.cumsum(pix, axis=0, dtype=np.uint32).astype(np.uint8)
    if px == 4:
        return Image.fromarray(pix[::-1][:, :, [2, 1, 0, 3]], "RGBA")
    return Image.fromarray(pix[::-1][:, :, [2, 1, 0]], "RGB")


class _BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.position = 0

    def bit(self, value):
        if self.position % 8 == 0:
            self.data.append(0)
        self.data[-1] |= int(bool(value)) << (self.position % 8)
        self.position += 1

    def gamma(self, value):
        bits = bin(value)[2:]
        for _ in bits[1:]:
            self.bit(0)
        for c in bits:
            self.bit(c == "1")


def encode_img0000(image, w, h, bpp):
    if image.size != (w, h) or bpp not in (24, 32):
        raise ValueError("geometry %s vs %s bpp %d" % (image.size, (w, h), bpp))
    mode = "RGBA" if bpp == 32 else "RGB"
    pixels = np.asarray(image.convert(mode), dtype=np.uint8)
    order = [2, 1, 0, 3] if bpp == 32 else [2, 1, 0]
    raw = pixels[::-1, :, order].copy()
    delta = raw.copy()
    delta[1:] = raw[1:] - raw[:-1]
    delta[0, 1:] = raw[0, 1:] - raw[0, :-1]
    values = delta.reshape(-1).astype(np.uint16)
    zigzag = np.where(values & 128, ((values ^ 255) << 1) | 1, values << 1).astype(np.uint8)
    padding = (-len(zigzag)) % 4
    if padding:
        zigzag = np.pad(zigzag, (0, padding))
    groups = zigzag.reshape(-1, 4).astype(np.uint32)
    packed = np.empty((4, len(groups)), dtype=np.uint8)
    for plane in range(4):
        v = (groups >> (6 - plane * 2)) & 3
        packed[plane] = v[:, 0] | (v[:, 1] << 2) | (v[:, 2] << 4) | (v[:, 3] << 6)
    linear = packed.reshape(-1)
    nonzero = linear != 0
    cuts = np.flatnonzero(nonzero[1:] != nonzero[:-1]) + 1
    bounds = np.concatenate(([0], cuts, [len(linear)]))
    ctl = _BitWriter()
    ctl.bit(bool(nonzero[0]))
    ctl.gamma(len(linear))
    for a, c in zip(bounds[:-1], bounds[1:]):
        ctl.gamma(int(c - a))
    literal = linear[nonzero].tobytes()
    ed = zlib.compress(literal, 9)
    ec = zlib.compress(bytes(ctl.data), 9)
    return struct.pack("<6I", 0, h, len(ed), len(literal), len(ec), len(ctl.data)) + ed + ec


def add_frames(blob, new):
    """Append frames: new = [(frame_id, template_id, PIL image, x, y)]. Each new frame copies the
    template frame's tags (stdinfo with width/height/x/y set from the image and position, the
    other tags as they are) and gets one lossless img0000. Existing frames stay byte for byte."""
    fs = frames(blob)
    by_id = {f["id"]: f for f in fs}
    for fid, tid, _, _, _ in new:
        if fid in by_id:
            raise ValueError("frame %d already exists" % fid)
        if tid not in by_id:
            raise ValueError("template frame %d missing" % tid)
    out = bytearray(blob[:12])
    for i, f in enumerate(fs):
        raw = bytearray(blob[f["offset"]:f["offset"] + f["length"]])
        if i == len(fs) - 1:                      # the old last frame now points at the first new one
            raw += bytes((-len(raw)) % 4)
            struct.pack_into("<I", raw, 0, len(raw))
        out += raw
    for k, (fid, tid, im, x, y) in enumerate(new):
        t = by_id[tid]
        bpp = t["bpp"]
        im = im.convert("RGBA" if bpp == 32 else "RGB")
        w, h = im.size
        tags = []
        for tg in t["tags"]:
            data = bytearray(blob[tg["offset"] + 16:tg["offset"] + 16 + tg["length"]])
            if tg["tag"] == "stdinfo":
                struct.pack_into("<IIIii", data, 0, w, h, bpp, x, y)
            if tg["tag"] in ("img_jpg", "img_al", "img0000"):
                continue
            tags.append((tg["tag"], bytes(data)))
        tags = tags[:1] + [("img0000", encode_img0000(im, w, h, bpp))] + tags[1:]
        body = bytearray(struct.pack("<II", 0, fid))
        for n, (name, data) in enumerate(tags):
            last = n == len(tags) - 1
            pad = (-len(data)) % 4
            body += name.encode("ascii").ljust(8, b"\0") + struct.pack("<II", 0 if last else 16 + len(data) + pad, len(data)) + data
            if not last:
                body += bytes(pad)
        if k < len(new) - 1:
            body += bytes((-len(body)) % 4)
            struct.pack_into("<I", body, 0, len(body))
        out += body
    res = bytes(out)
    rf = frames(res)
    # existing frames by their place in the file (ids can repeat: Steam's userfont.hg3 has two frames with id 3)
    for i, f in enumerate(fs[:-1]):
        g = rf[i]
        if blob[f["offset"]:f["offset"] + f["length"]] != res[g["offset"]:g["offset"] + g["length"]]:
            raise AssertionError("existing frame %d (#%d in the file) changed" % (f["id"], i))
    nf = {g["id"]: g for g in rf[len(fs):]}
    for fid, _, im, x, y in new:
        g = nf[fid]
        if (g["x"], g["y"]) != (x, y) or decode(res, g).convert("RGBA").tobytes() != im.convert("RGBA").tobytes():
            raise AssertionError("new frame %d does not read back" % fid)
    return res


def replace(blob, repl):
    """repl: {frame_id: PIL image}. Frame ids must be unique in the file."""
    fs = frames(blob)
    ids = [f["id"] for f in fs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate frame ids")
    unknown = set(repl) - set(ids)
    if unknown:
        raise ValueError("unknown frames %s" % sorted(unknown))
    out = bytearray(blob[:12])
    for i, f in enumerate(fs):
        raw = blob[f["offset"]:f["offset"] + f["length"]]
        if f["id"] not in repl:
            out += raw
            continue
        im = repl[f["id"]]
        bpp = f["bpp"]
        if f["bpp"] == 24 and im.mode == "RGBA" and im.getextrema()[3] != (255, 255):
            raise ValueError("alpha on a 24-bit frame %d" % f["id"])
        keep = []
        for t in f["tags"]:
            if t["tag"] in ("img_jpg", "img_al", "img0000"):
                continue
            keep.append((t["tag"], blob[t["offset"] + 16:t["offset"] + 16 + t["length"]]))
        payload = encode_img0000(im, f["width"], f["height"], bpp)
        tags = keep[:1] + [("img0000", payload)] + keep[1:]
        body = bytearray(raw[:8])
        for n, (name, data) in enumerate(tags):
            last = n == len(tags) - 1
            pad = (-len(data)) % 4
            step = 0 if last else 16 + len(data) + pad
            body += name.encode("ascii").ljust(8, b"\0") + struct.pack("<II", step, len(data)) + data
            if not last:
                body += bytes(pad)
        if f["next"]:
            pad = (-len(body)) % 4
            body += bytes(pad)
            struct.pack_into("<I", body, 0, len(body))
        else:
            struct.pack_into("<I", body, 0, 0)
        out += body
    new = bytes(out)
    # read back: same ids/geometry, replaced frames decode to the requested pixels
    nf = frames(new)
    if [f["id"] for f in nf] != ids:
        raise AssertionError("frame order changed")
    for a, c in zip(fs, nf):
        for k in ("width", "height", "bpp", "x", "y", "canvas_width", "canvas_height"):
            if a[k] != c[k]:
                raise AssertionError("frame %d %s changed" % (a["id"], k))
        if a["id"] in repl:
            want = repl[a["id"]].convert("RGBA" if a["bpp"] == 32 else "RGB")
            got = decode(new, c)
            if got.convert(want.mode).tobytes() != want.tobytes():
                raise AssertionError("frame %d decode mismatch" % a["id"])
        elif blob[a["offset"]:a["offset"] + a["length"]] != new[c["offset"]:c["offset"] + c["length"]] and a is not fs[-1]:
            raise AssertionError("untouched frame %d changed" % a["id"])
    return new
