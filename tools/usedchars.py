"""Every character the Steam game can show in its own text: original scenario/FES/XML/CSV text
entries, real CP932 strings in ISLAND.exe / cs2conf.dll (.rdata/.rsrc, NUL-terminated, containing
kana or Japanese punctuation), plus our Korean-mode texts.
Kanji in this set are never used as donor codes for Hangul."""
import os
import re
import sys
import zlib

import pefile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ORIG = r"Y:\AI\island-steam-ko\steam-orig"
TEXT_ARCHIVES = ["scene.int", "fes.int", "config.int", "kcs.int", "kx2.int", "mot.int", "ptcl.int"]
TEXT_EXT = (".cst", ".fes", ".xml", ".csv", ".txt", ".ini", ".tbl")
JP_MARK = re.compile(r"[\u3040-\u30ff\u3001\u3002\u300c\u300d\uff01\uff1f]")


def strict_text(b):
    try:
        return b.decode("cp932")
    except UnicodeDecodeError:
        return None


def pe_strings(path):
    out = set()
    pe = pefile.PE(path, fast_load=True)
    for s in pe.sections:
        name = s.Name.rstrip(b"\0")
        if name not in (b".rdata", b".rsrc", b"_RDATA"):
            continue
        data = s.get_data()
        for chunk in data.split(b"\0"):
            if len(chunk) < 4 or not any(c >= 0x80 for c in chunk):
                continue
            t = strict_text(chunk)
            if t and JP_MARK.search(t) and not any(ord(c) < 0x20 and c not in "\r\n\t" for c in t):
                out.update(t)
    return out


def original_chars():
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    chars = set()
    for arc in TEXT_ARCHIVES:
        k = cs2.Kif(os.path.join(ORIG, arc), key)
        with open(k.path, "rb") as fh:
            for e in k.entries:
                if not e["name"].lower().endswith(TEXT_EXT):
                    continue
                d = k.read(e["name"], fh)
                if d[:8] == b"CatScene":
                    for t, raw in cs2.parse_cst(d)[0]:
                        chars.update(raw.decode("cp932", "ignore"))
                    continue
                if d[:4] == b"FES\0":
                    d = zlib.decompress(d[16:])
                chars.update(d.decode("cp932", "ignore"))
    chars.update(open(os.path.join(ORIG, "config", "startup.xml"), "rb").read().decode("cp932", "ignore"))
    for rel in ["ISLAND.exe", "cs2conf.dll"]:
        chars |= pe_strings(os.path.join(ORIG, rel))
    return chars
