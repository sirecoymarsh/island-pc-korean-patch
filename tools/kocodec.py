"""Korean <-> CatSystem2 (CP932) byte codec for the Steam JP engine.

The JP engine renders text through GDI GetGlyphOutlineA with a SHIFTJIS_CHARSET font, so every
character must be a CP932 code the engine accepts. Its text parser only treats 0x81-0x9F/0xE0-0xEF
as lead bytes (CP932 user-defined F0-F9 codes are split into two single bytes - seen in game,
11-07), so characters CP932 cannot express (Hangul, middle dot, ...) are put on "donor" kanji
codes: JIS kanji with lead byte 0x88-0x9F that appear nowhere in the game's own text (scenario,
screen scripts, settings, exe/dll strings) nor in our Korean texts. The patch font (Korean mode
only) maps those kanji code points to the Hangul glyphs.

Second bytes that equal an ASCII character the engine or the FES/XML parsers treat specially
are skipped for safety: \ [ ] { | } @ ` ^ ~
"""
import json
import os

SKIP_TRAIL = {0x5C, 0x5B, 0x5D, 0x7B, 0x7C, 0x7D, 0x40, 0x60, 0x5E, 0x7E}

# 11-08 凛音/リンネ colour marks (build_text.RINNE_*): two more unused kanji, far from the donor sequence, carry the
# リンネ side's 「린」「네」. Text boxes with a userfont map draw them as coloured images; anywhere else (the novel
# window's name prefix, ...) the patch font draws them as the plain Hangul glyphs (build_font.py). Never donors.
RINNE_ALIAS = {"堯": "린", "槇": "네"}     # CP932 EA9F, EAA0
# 11-08 evening: the user moved the distinction to emphasis dots (드러냄표) over each letter (Switch port the same).
# The dot is a ruby character on one more unused kanji code; the patch font draws it as a round dot (build_font.py).
RINNE_DOT = "瑤"                                # CP932 EAA2


def donor_slots(exclude, leads=(range(0x88, 0xA0), range(0xE0, 0xEB))):
    """Unused JIS kanji codes in order (lead 0x88-0x9F first), without risky second bytes."""
    out = []
    for rng in leads:
        for lead in rng:
            for trail in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
                if trail in SKIP_TRAIL:
                    continue
                b = bytes([lead, trail])
                try:
                    u = b.decode("cp932")
                except UnicodeDecodeError:
                    continue
                if len(u) == 1 and 0x4E00 <= ord(u) <= 0x9FFF and u not in exclude:
                    out.append((b, u))
    return out


def cp932_ok(ch):
    try:
        b = ch.encode("cp932")
    except UnicodeEncodeError:
        return False
    # cp932 also round-trips PUA E000.. to F040..; those slots are ours, never source text
    return not (0xE000 <= ord(ch) <= 0xF8FF) and b.decode("cp932") == ch


class Codec:
    def __init__(self, table):
        # table: {char: [lead, trail]}
        self.enc = {c: bytes(v) for c, v in table.items()}
        self.dec = {v: c for c, v in self.enc.items()}

    @classmethod
    def build(cls, chars, prior=None, exclude=()):
        """Assign donor kanji codes to every char of `chars` that CP932 cannot express.
        exclude: characters the game shows anywhere (never used as donors).
        prior: existing {char: [lead, trail]} kept as is (stable across rebuilds)."""
        table = dict(prior or {})
        used = {tuple(v) for v in table.values()}
        excl = set(exclude) | set(chars) | set(RINNE_ALIAS) | {RINNE_DOT}
        free = [b for b, u in donor_slots(excl) if tuple(b) not in used]
        need = sorted({c for c in chars if not cp932_ok(c) and c not in table and c not in "\r\n"})
        if len(need) > len(free):
            raise ValueError("donor capacity exceeded: need %d free %d" % (len(need), len(free)))
        for c, b in zip(need, free):
            table[c] = list(b)
        return cls(table)

    def save(self, path):
        rows = sorted(self.enc.items(), key=lambda kv: kv[1])
        data = {
            "format": "island-steam-ko-donor-v2",
            "note": "char -> CP932 code of an unused kanji; the Korean-mode font maps that kanji to the char's glyph",
            "count": len(rows),
            "entries": [{"char": c, "unicode": "U+%04X" % ord(c), "cp932": b.hex(), "slot": "U+%04X" % ord(b.decode("cp932"))} for c, b in rows],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls({e["char"]: list(bytes.fromhex(e["cp932"])) for e in data["entries"]})

    def encode(self, text):
        out = bytearray()
        for ch in text:
            b = self.enc.get(ch)
            if b is not None:
                out += b
                continue
            if not cp932_ok(ch):
                raise UnicodeEncodeError("kocodec", text, 0, 1, "no code for U+%04X" % ord(ch))
            out += ch.encode("cp932")
        return bytes(out)

    def decode(self, data):
        """Decode CP932 bytes, mapping our donor codes back to their chars."""
        back = self.slot_chars()
        return "".join(back.get(c, c) for c in data.decode("cp932"))

    def slot_chars(self):
        """{donor kanji: real char}"""
        return {b.decode("cp932"): c for c, b in self.enc.items()}

    def pua_map(self):
        """{donor code point: target char} for the font builder and the loader table."""
        return {ord(b.decode("cp932")): c for c, b in self.enc.items()}


def codex_decoder(codex_map_path):
    """Decode Codex-encoded UI text (their PUA assignment E000+i) back to Unicode."""
    with open(codex_map_path, encoding="utf-8") as f:
        m = json.load(f)
    back = {e["pua_codepoint"]: e["char"] for e in m["entries"]}

    def dec(data):
        s = data.decode("cp932")
        return "".join(back.get(ord(c), c) if 0xE000 <= ord(c) <= 0xF8FF else c for c in s)

    return dec, back
