"""Korean UI archives for the GOG/English ISLAND (engine 2.6.1.80) -> build\\gog-ko (or --out):

  fes.int      GOG original + Codex's GOG Korean FES (33: 5 UI screens + system-voice captions,
               10-28 v2, the set Codex ran on GOG) re-encoded from Codex's PUA to our donor-kanji
               codes (Codex's PUA bytes F0-F9 are split by the engine's CP932 parser in game).
               Message window and backlog font sizes go back to the Japanese values (the English
               build shrank them for English text): the Korean text is wrapped for them, like Steam.
  config.int + config\\startup.xml   Codex's GOG Korean XML, our font, original save path and
               sound focus line, VRAM area02 6->10 blocks (Codex's GOG fix for the captions)
  language.txt Codex's GOG exe-string table (UTF-8, "#949" -> the engine converts every exe
               string to CP949 for message boxes, menus, dialogs)
  image.int    GOG original + the Steam build's 32 Korean sys_*.hg3 (GOG's screen scripts use the
               Japanese logic; frame geometry checked in gog_image_report.json)
  movie.int    GOG original + the Korean-lyrics opening (same video as Steam's ko\\movie.int)
  ISLAND-KO.ttf, pua_table.txt   shared with Steam

Prints counts only. Usage: python -I build_gog_ui.py [--out DIR] [--test-save DIR] [--skip-big]"""
import argparse
import json
import os
import re
import shutil
import struct
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
from build_text import (QA_FILES, RINNE_FES, caption_fix, caption_place, caption_speakers, decide_caption,  # noqa: E402
                        fes_pack, fes_unpack, merge_xml, qa_fes, rinne_fes, sound_tab_option)
from hg3info import frames  # noqa: E402
from kocodec import Codec, codex_decoder  # noqa: E402
import ko_art  # noqa: E402

KO_MOVIES = os.path.join(r"Y:\AI\island-steam-ko", "work", "movie", "ko")


def ko_movies(edition):
    """Korean-subtitled endings/preview made by build_ko_movies.py (only those whose checks passed)"""
    rp = os.path.join(KO_MOVIES, "report.json")
    rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    out = {}
    for key, rec in sorted(rep.items()):
        ed, name = key.split("/")
        p = os.path.join(KO_MOVIES, ed, name + ".webm")
        if ed == edition and rec.get("ok") and os.path.exists(p):
            out[name + ".webm"] = open(p, "rb").read()
    return out

ROOT = r"Y:\AI\island-steam-ko"
GOG = os.path.join(ROOT, "gog-orig")
STEAM = os.path.join(ROOT, "steam-orig")
STEAM_BUILD = os.path.join(ROOT, "build", "ko")
OPENING = os.path.join(ROOT, "work", "movie", "opmovie.ko.webm")
DATA = os.path.join(os.path.dirname(HERE), "data")
PUA_TABLE = os.path.join(DATA, "pua_table.json")
CODEX = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드"
L5 = os.path.join(CODEX, "parallel-ui-20261028", "lane5-integration")
FES_DIR = os.path.join(L5, "system-voice-staging", "v2", "gog", "logical")
FES_MAP = os.path.join(L5, "system-voice-staging", "v2", "encoding_map.json")
XML_MAP = os.path.join(L5, "text-font", "encoding_map.json")
STAGE = os.path.join(CODEX, "ui-trials-20261028", "staging", "gog-ui-v1")

# English-build font sizes -> Japanese values (the Korean text is wrapped for these, as on Steam)
LAYOUT_JP = {
    "meswnd.fes": [("str layout size 18 20 22 26 30", "str layout size 18 22 26 30 34"), ("str layout move 0 6", "str layout move 0 8")],
    "log_01.fes": [("log layout size 18 20 22 24 26", "log layout size 18 22 26 30 34"), ("log layout move 0 6", "log layout move 0 8"),
                   ("name layout size 23", "name layout size 26")],
}


def layout_jp(name, text):
    n = 0
    for a, b in LAYOUT_JP.get(name, []):
        text, k = re.subn(r"(?m)^(\s*)" + re.escape(a) + r"(\s*)$", lambda m: m.group(1) + b + m.group(2), text)
        if k != 1:
            raise SystemExit("layout line not found once in %s: %s (%d)" % (name, a, k))
        n += k
    return text, n


LANG_EXTRA = os.path.join(DATA, "gog_language_extra_ko.json")
LANG_KEY = re.compile(r"^\$(\d{4}-\d{4})\$$")
FMT = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z%]|\\n")


def apply_language(text, extra):
    """Put Korean on language.txt keys Codex left in English. The value is the line(s) after
    `$NNNN-NNNN$` up to a blank, comment or key line; the format codes must match the Japanese
    comment above the key (the exe's printf arguments follow the Japanese table)."""
    lines = text.split("\r\n")
    where = {}
    for i, l in enumerate(lines):
        m = LANG_KEY.match(l)
        if m:
            where[m.group(1)] = i
    n = 0
    for key, ko in sorted(extra.items(), reverse=True):   # bottom-up keeps earlier indexes valid
        if key.startswith("_"):
            continue
        i = where.get(key)
        if i is None:
            raise SystemExit("language.txt key not found: " + key)
        j = i + 1
        while j < len(lines) and lines[j] and not lines[j].startswith("//") and not LANG_KEY.match(lines[j]):
            j += 1
        k = i - 1
        while k >= 0 and not lines[k].startswith("//"):
            k -= 1
        jp = lines[k][2:] if k >= 0 else ""
        if FMT.findall(jp) != FMT.findall(ko):
            raise SystemExit("format codes differ from the Japanese for %s" % key)
        ko.encode("cp949")
        lines[i + 1:j] = [ko]
        n += 1
    return "\r\n".join(lines), n


def check_enc(codec, text, where):
    try:
        return codec.encode(text)
    except UnicodeEncodeError as e:
        raise SystemExit("%s: character outside the shared donor table (%s)" % (where, e.reason))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "gog-ko"))
    ap.add_argument("--test-save", default=None, help="save folder for a test copy (else the original path)")
    ap.add_argument("--test-sticky", type=int, default=None)
    ap.add_argument("--skip-big", action="store_true", help="no image.int / movie.int (test variants link the main build's)")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "config"), exist_ok=True)
    kg = cs2.crc_key(cs2.passphrase(os.path.join(GOG, "ISLAND.exe")))
    ks = cs2.crc_key(cs2.passphrase(os.path.join(STEAM, "ISLAND.exe")))
    codec = Codec.load(PUA_TABLE)
    rep = {}

    # ---------- fes.int ----------
    fdec, _ = codex_decoder(FES_MAP)
    fk = cs2.Kif(os.path.join(GOG, "fes.int"), kg)
    repl = {}
    layout_lines = 0
    cap_fixed = 0
    sound_opt = 0
    qa_edits = {}
    rinne_edits = {}
    cap_moved = {}
    speakers = 0
    for fn in sorted(os.listdir(FES_DIR)):
        if not fn.lower().endswith(".fes"):
            continue
        data, z = fes_unpack(open(os.path.join(FES_DIR, fn), "rb").read())
        text = fdec(data)
        text, n = layout_jp(fn, text)
        layout_lines += n
        text, c1 = caption_fix(text)
        cap_fixed += c1
        if fn.lower() == "conf_sound.fes":
            text, sound_opt = sound_tab_option(text)
            text = decide_caption(text)[0]
        text, sp = caption_speakers(text)
        speakers += sp
        text, cm = caption_place(fn, text)
        if cm:
            cap_moved[fn] = cm
        elif fn.lower().startswith("conf_") and "ko_cap_text" in text:
            raise SystemExit("settings caption place: %s not edited" % fn)
        text, q = qa_fes(fn, text)
        if q:
            qa_edits[fn] = q
        text, r = rinne_fes(fn, text)
        if r:
            rinne_edits[fn] = r
        repl[fn] = fes_pack(check_enc(codec, text, fn), z)
    for fn in LAYOUT_JP:
        if fn in repl:
            continue
        data, z = fes_unpack(fk.read(fn))
        text, n = layout_jp(fn, data.decode("cp932"))
        layout_lines += n
        text, r = rinne_fes(fn, text)
        if r:
            rinne_edits[fn] = r
        repl[fn] = fes_pack(text.encode("cp932"), z)
    have = {k.lower() for k in repl}
    for e in fk.entries:                      # 검수 보기 / 린네 colour scripts Codex did not touch (omake_cgview.fes)
        low = e["name"].lower()
        if (low in QA_FILES or low in RINNE_FES) and low not in have:
            data, z = fes_unpack(fk.read(e["name"]))
            text, q = qa_fes(e["name"], data.decode("cp932"))
            if low in QA_FILES:
                qa_edits[e["name"]] = q
            text, r = rinne_fes(e["name"], text)
            if r:
                rinne_edits[e["name"]] = r
            repl[e["name"]] = fes_pack(text.encode("cp932"), z)
    missing = [n for n in QA_FILES if n not in {k.lower() for k in qa_edits}]
    if missing:
        raise SystemExit("검수 보기: scripts not edited: %s" % missing)
    missing = [n for n in RINNE_FES if n not in {k.lower() for k in rinne_edits}]
    if missing:
        raise SystemExit("린네 colour: scripts not edited: %s" % missing)
    fk.write(os.path.join(args.out, "fes.int"), repl)
    chk = cs2.Kif(os.path.join(args.out, "fes.int"), kg)
    rep["fes"] = {"replaced": len(repl), "layout_lines_to_japanese": layout_lines, "caption_draws_reordered": cap_fixed, "sound_tab_option_edits": sound_opt,
                  "qa_view_edits": qa_edits, "rinne_fes_edits": rinne_edits, "settings_caption_draws_moved": cap_moved,
                  "caption_lines_with_speaker": speakers,
                  "readback_ok": all(chk.read(n) == b for n, b in repl.items())}

    # ---------- config.int + loose startup.xml ----------
    xdec, _ = codex_decoder(XML_MAP)
    ck = cs2.Kif(os.path.join(GOG, "config.int"), kg)
    sk = cs2.Kif(os.path.join(STAGE, "config.int"), kg)
    crepl = {}
    restored = 0
    for n in ["startup.xml"]:
        t, r, nf = merge_xml(xdec(sk.read(n)), ck.read(n).decode("cp932"), args.test_save, args.test_sticky)
        restored += r
        crepl[n] = check_enc(codec, t, "config.int/" + n)
    # adv.xml: the English build adds a save comment for saves made at a choice ("[Choice]");
    # use the Korean wording of the same string in select.fes (strvar 156)
    sel = fdec(fes_unpack(open(os.path.join(FES_DIR, "select.fes"), "rb").read())[0])
    m = re.search(r"(?m)^\s*strvar 156 (\S.*?)\s*$", sel)
    adv = ck.read("adv.xml").decode("cp932")
    adv2, k = re.subn(r"<selectcomment>[^<]*</selectcomment>", lambda _: "<selectcomment>" + m.group(1) + "</selectcomment>", adv)
    assert m and k == 1
    crepl["adv.xml"] = check_enc(codec, adv2, "config.int/adv.xml")
    ck.write(os.path.join(args.out, "config.int"), crepl)
    t, r, nf = merge_xml(xdec(open(os.path.join(STAGE, "config", "startup.xml"), "rb").read()),
                         open(os.path.join(GOG, "config", "startup.xml"), "rb").read().decode("cp932"), args.test_save, args.test_sticky)
    restored += r
    with open(os.path.join(args.out, "config", "startup.xml"), "wb") as f:
        f.write(check_enc(codec, t, "config/startup.xml"))
    for name, data in [("startup.xml", crepl["startup.xml"]), ("loose", open(os.path.join(args.out, "config", "startup.xml"), "rb").read())]:
        s = codec.decode(data)
        assert "ISLAND UI Korean" not in s and "ISLAND KO" in s, name
        assert re.search(r"<area02>\s*<sx>0</sx>\s*<sy>17</sy>\s*<dx>10</dx>", s), name
        if args.test_save is None:
            assert "gog-ui-trial" not in s and "%USERPROFILE%\\%brand%\\%title%" in s, name
    rep["config"] = {"replaced": len(crepl) + 1, "save_or_sticky_lines_restored": restored, "adv_selectcomment": True}

    # ---------- language.txt ----------
    lt = open(os.path.join(STAGE, "language.txt"), "rb").read()
    assert lt.startswith(b"#949\r\n")
    lt, nlang = apply_language(lt.decode("utf-8"), json.load(open(LANG_EXTRA, encoding="utf-8")))
    lt = lt.encode("utf-8")
    with open(os.path.join(args.out, "language.txt"), "wb") as f:
        f.write(lt)
    rep["language"] = {"bytes": len(lt), "first_line": "#949", "keys_translated_here": nlang}

    # ---------- static ----------
    for fn in ["ISLAND-KO.ttf", "pua_table.txt"]:
        shutil.copy2(os.path.join(STEAM_BUILD, fn), os.path.join(args.out, fn))

    if not args.skip_big:
        # ---------- image.int ----------
        ig = cs2.Kif(os.path.join(GOG, "image.int"), kg)
        is_ = cs2.Kif(os.path.join(STEAM, "image.int"), ks)
        # Codex's 32 Korean UI images: from Codex's own payload (the Steam build now also carries the
        # ko_art images, whose Steam variants must not reach GOG - 11-08 staff roll size mismatch)
        from build_image import CDX
        ik = cs2.Kif(CDX, ks)
        irepl = {}
        geo = {}
        with open(is_.path, "rb") as fs, open(ik.path, "rb") as fko, open(ig.path, "rb") as fg:
            for e in ik.entries:
                es = is_.by_name[e["name"].casefold()]
                dk = ik.read(e["name"], fko)
                if es["size"] == e["size"] and is_.read(es["name"], fs) == dk:
                    continue
                dg = ig.read(e["name"], fg)
                fk_, fg_ = frames(dk), frames(dg)
                geo[e["name"]] = {"frames": len(fk_), "frames_gog": len(fg_),
                                  "frames_same_geometry_as_gog": sum(1 for (i, a), (j, b) in zip(fk_, fg_) if i == j and a == b),
                                  "frame_ids_equal": [i for i, _ in fk_] == [j for j, _ in fg_]}
                if not geo[e["name"]]["frame_ids_equal"]:
                    raise SystemExit("frame list differs: " + e["name"])
                irepl[e["name"]] = dk
        n_ui = len(irepl)
        art = ko_art.replacements("gog", ig, irepl)
        irepl.update(art)
        ig.write(os.path.join(args.out, "image.int"), irepl)
        c = cs2.Kif(os.path.join(args.out, "image.int"), kg)
        with open(c.path, "rb") as fc:
            ok = all(c.read(n, fc) == d for n, d in irepl.items())
        json.dump(geo, open(os.path.join(DATA, "gog_image_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rep["image"] = {"replaced": len(irepl), "codex_ui": n_ui, "ko_art": len(art), "readback_ok": ok, "bytes": os.path.getsize(c.path)}

        # ---------- movie.int ----------
        mk = cs2.PlainKif(os.path.join(GOG, "movie.int"))
        mrepl = {"opmovie.webm": open(OPENING, "rb").read()}
        mrepl.update(ko_movies("gog"))
        mk.write(os.path.join(args.out, "movie.int"), mrepl)
        mc = cs2.PlainKif(os.path.join(args.out, "movie.int"))
        rep["movie"] = {"replaced": sorted(mrepl), "readback": all(mc.read(n) == d for n, d in mrepl.items()),
                        "others_unchanged": all(mc.read(e["name"]) == mk.read(e["name"]) for e in mk.entries if e["name"] not in mrepl)}
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
