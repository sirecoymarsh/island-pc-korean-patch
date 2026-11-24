"""CatSystem2 (ISLAND Steam JP, engine 2.6.1.68) archive / scene helpers.

KIF (.int) reading follows Codex's verified adapter (localization/ja/audit/no_change_roundtrip.json);
this module adds a writer that keeps every untouched entry byte-identical and only re-encrypts the
offset/size of entries whose payload changes.
"""
import hashlib
import struct
import zlib

import pefile
from Crypto.Cipher import Blowfish

MASK = 0xFFFFFFFF
ALPHABET = b"zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA"


def mt_first(seed):
    mt = []
    for _ in range(624):
        upper = seed & 0xFFFF0000
        seed = (69069 * seed + 1) & MASK
        mt.append(upper | ((seed & 0xFFFF0000) >> 16))
        seed = (69069 * seed + 1) & MASK
    y = (mt[0] & 0x80000000) | (mt[1] & 0x7FFFFFFF)
    y = mt[397] ^ (y >> 1) ^ ([0, 0x9908B0DF][y & 1])
    y ^= y >> 11
    y ^= (y << 7) & 0x9D2C5680
    y ^= (y << 15) & 0xEFC60000
    y ^= y >> 18
    return y & MASK


def crc_key(value):
    table = []
    for i in range(256):
        v = i << 24
        for _ in range(8):
            v = ((v << 1) ^ (0x04C11DB7 if v & 0x80000000 else 0)) & MASK
        table.append(v)
    key = MASK
    for b in value:
        key = (~table[(key >> 24) ^ b] ^ (key << 8)) & MASK
    return key


def _swap32(data):
    import array
    a = array.array("I")
    a.frombytes(bytes(data[: len(data) // 4 * 4]))
    a.byteswap()
    return a.tobytes()


def decipher(cipher, data):
    if cipher is None:
        return data
    n = len(data) // 8 * 8
    return _swap32(cipher.decrypt(_swap32(data[:n]))) + data[n:]


def encipher(cipher, data):
    if cipher is None:
        return data
    n = len(data) // 8 * 8
    return _swap32(cipher.encrypt(_swap32(data[:n]))) + data[n:]


def passphrase(exe_path):
    pe = pefile.PE(exe_path, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
    res = {}
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        for name in typ.directory.entries:
            for lang in name.directory.entries:
                st = lang.data.struct
                res[(str(typ.name or typ.id), str(name.name or name.id))] = pe.get_data(st.OffsetToData, st.Size)
    key = bytes(x ^ 0xCD for x in res.get(("KEY_CODE", "KEY"), b"")) or b"windmill"
    code = res[("V_CODE2", "DATA")]
    return decipher(Blowfish.new(key, Blowfish.MODE_ECB), code).split(b"\0", 1)[0]


class Kif:
    """Encrypted KIF archive. entries: list of dict(index, name, offset, size)."""

    def __init__(self, path, main_key):
        self.path = path
        self.main_key = main_key
        with open(path, "rb") as f:
            magic, count = struct.unpack("<4sI", f.read(8))
            if magic != b"KIF\0":
                raise ValueError("not KIF: %s" % path)
            self.count = count
            self.raw_index = f.read(count * 72)
        if self.raw_index[:11] != b"__key__.dat":
            raise ValueError("unencrypted KIF not expected here")
        seed = struct.unpack_from("<I", self.raw_index, 68)[0]
        self.cipher = Blowfish.new(struct.pack("<I", mt_first(seed)), Blowfish.MODE_ECB)
        self.entries = []
        for i in range(1, count):
            e = self.raw_index[i * 72:(i + 1) * 72]
            nk = mt_first((main_key + i) & MASK)
            k = sum(nk.to_bytes(4, "little")) & 255
            name = bytearray(e[:64])
            for j, c in enumerate(name):
                if c == 0:
                    break
                a = ALPHABET.find(bytes([c]))
                if a >= 0:
                    name[j] = ALPHABET[51 - ((a - k % 52) % 52)]
                k += 1
            name = bytes(name).split(b"\0", 1)[0].decode("cp932")
            off, n = struct.unpack("<II", e[64:])
            off, n = struct.unpack("<II", decipher(self.cipher, struct.pack("<II", (off + i) & MASK, n)))
            self.entries.append({"index": i, "name": name, "offset": off, "size": n})
        self.by_name = {e["name"].casefold(): e for e in self.entries}

    def read(self, name, fh=None):
        e = self.by_name[name.casefold()]
        own = fh is None
        if own:
            fh = open(self.path, "rb")
        try:
            fh.seek(e["offset"])
            return decipher(self.cipher, fh.read(e["size"]))
        finally:
            if own:
                fh.close()

    def _enc_entry(self, i, off, n):
        x, y = struct.unpack("<II", encipher(self.cipher, struct.pack("<II", off, n)))
        return struct.pack("<II", (x - i) & MASK, y)

    def write(self, out_path, replacements):
        """Write a new archive. replacements: {name: plaintext payload}. Unchanged entries keep
        their original encrypted bytes. Layout of this packer (checked on all 8 Steam archives):
        [KIF hdr][index count*72] then for each entry i (index order) [raw index record i-1][data i].
        The record copies are rewritten with the new offsets so the file looks like a fresh pack."""
        repl = {k.casefold(): v for k, v in replacements.items()}
        unknown = set(repl) - set(self.by_name)
        if unknown:
            raise KeyError("not in archive: %s" % sorted(unknown)[:5])
        index = bytearray(self.raw_index)
        order = sorted(self.entries, key=lambda e: e["offset"])
        if [e["index"] for e in order] != list(range(1, self.count)):
            raise ValueError("offset order differs from index order")
        data_start = 8 + self.count * 72
        payloads = []
        with open(self.path, "rb") as src:
            prev_end = data_start
            for e in order:
                if e["offset"] != prev_end + 72:
                    raise ValueError("unexpected layout at %s" % e["name"])
                prev_end = e["offset"] + e["size"]
            src.seek(0, 2)
            if prev_end != src.tell():
                raise ValueError("trailing bytes after last entry")
            # first pass: compute new offsets
            cursor = data_start
            sizes = []
            for e in order:
                key = e["name"].casefold()
                n = len(repl[key]) if key in repl else e["size"]
                cursor += 72
                i = e["index"]
                index[i * 72 + 64:i * 72 + 72] = self._enc_entry(i, cursor, n)
                sizes.append((cursor, n))
                cursor += n
            with open(out_path, "wb") as dst:
                dst.write(struct.pack("<4sI", b"KIF\0", self.count))
                dst.write(bytes(index))
                for e, (off, n) in zip(order, sizes):
                    j = e["index"] - 1
                    dst.write(bytes(index[j * 72:(j + 1) * 72]))
                    key = e["name"].casefold()
                    if key in repl:
                        dst.write(encipher(self.cipher, repl[key]))
                    else:
                        src.seek(e["offset"])
                        dst.write(src.read(e["size"]))
                total = dst.tell()
        return total


class PlainKif:
    """Unencrypted KIF (movie.int etc.). Layout of this packer: [hdr][index] then per entry
    [its own index record][data]."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            magic, count = struct.unpack("<4sI", f.read(8))
            if magic != b"KIF\0":
                raise ValueError("not KIF")
            self.count = count
            self.raw_index = f.read(count * 72)
        if self.raw_index[:11] == b"__key__.dat":
            raise ValueError("encrypted KIF - use Kif")
        self.entries = []
        for i in range(count):
            r = self.raw_index[i * 72:(i + 1) * 72]
            off, n = struct.unpack("<II", r[64:])
            self.entries.append({"index": i, "name": r[:64].split(b"\0", 1)[0].decode("cp932"), "offset": off, "size": n})
        self.by_name = {e["name"].casefold(): e for e in self.entries}

    def read(self, name, fh=None):
        e = self.by_name[name.casefold()]
        with open(self.path, "rb") as f:
            f.seek(e["offset"])
            return f.read(e["size"])

    def write(self, out_path, replacements):
        repl = {k.casefold(): v for k, v in replacements.items()}
        if set(repl) - set(self.by_name):
            raise KeyError("not in archive")
        index = bytearray(self.raw_index)
        cursor = 8 + self.count * 72
        layout = []
        for e in self.entries:
            n = len(repl[e["name"].casefold()]) if e["name"].casefold() in repl else e["size"]
            cursor += 72
            index[e["index"] * 72 + 64:e["index"] * 72 + 72] = struct.pack("<II", cursor, n)
            layout.append((e, cursor, n))
            cursor += n
        with open(self.path, "rb") as src, open(out_path, "wb") as dst:
            dst.write(struct.pack("<4sI", b"KIF\0", self.count))
            dst.write(bytes(index))
            for e, off, n in layout:
                dst.write(bytes(index[e["index"] * 72:(e["index"] + 1) * 72]))
                if e["name"].casefold() in repl:
                    dst.write(repl[e["name"].casefold()])
                else:
                    src.seek(e["offset"])
                    left = e["size"]
                    while left:
                        b = src.read(min(left, 8 << 20))
                        dst.write(b)
                        left -= len(b)
            return dst.tell()


# ---------------- CST (CatScene) ----------------

def parse_cst(blob):
    """Returns (lines, meta). lines: list of (type, raw_bytes_without_framing)."""
    if blob[:8] != b"CatScene":
        raise ValueError("signature")
    comp, uncomp = struct.unpack_from("<II", blob, 8)
    if len(blob) != 16 + (comp or uncomp):
        raise ValueError("outer size")
    data = zlib.decompress(blob[16:]) if comp else blob[16:]
    total, inputs, ot, st = struct.unpack_from("<IIII", data)
    if len(data) != uncomp or total != len(data) - 16 or ot != inputs * 8 or (st - ot) % 4:
        raise ValueError("inner header")
    input_table = data[16:16 + ot]
    count = (st - ot) // 4
    offsets = struct.unpack_from("<" + "I" * count, data, 16 + ot)
    lines = []
    body = data[16 + st:]
    for i, off in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < count else len(body)
        raw = body[off:end]
        if raw[:1] != b"\x01" or raw[-1:] != b"\0":
            raise ValueError("framing at %d" % i)
        lines.append((raw[1], raw[2:-1]))
    return lines, {"inputs": inputs, "input_table": input_table, "compressed": bool(comp)}


def build_cst(lines, meta, level=9):
    body = bytearray()
    offsets = []
    for typ, raw in lines:
        offsets.append(len(body))
        if b"\0" in raw:
            raise ValueError("NUL inside line")
        body += b"\x01" + bytes([typ]) + raw + b"\0"
    input_table = meta["input_table"]
    ot = len(input_table)
    st = ot + 4 * len(offsets)
    inner = struct.pack("<IIII", 0, meta["inputs"], ot, st) + input_table + struct.pack("<" + "I" * len(offsets), *offsets) + bytes(body)
    inner = struct.pack("<I", len(inner) - 16) + inner[4:]
    if meta.get("compressed", True):
        comp = zlib.compress(inner, level)
        return b"CatScene" + struct.pack("<II", len(comp), len(inner)) + comp
    return b"CatScene" + struct.pack("<II", 0, len(inner)) + inner


def sha256(b):
    return hashlib.sha256(b).hexdigest()
