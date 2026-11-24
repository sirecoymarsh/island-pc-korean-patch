"""Assemble the release folder for both editions (no original game data is shipped):
  <release>\\ISLAND 한국어 패치.exe, 읽어 주세요.txt
  <release>\\payload\\version.dll
  <release>\\payload\\ko\\...            files for both editions (font, donor table, licence)
  <release>\\payload\\ko-steam\\..., ko-gog\\...   edition-only files (installed into ko\\)
  <release>\\payload\\entries\\<steam|gog|common>\\<archive>\\<entry>   Korean entries only
  <release>\\payload\\manifest.txt
Manifest rows (tab separated; column 1 is the edition, "all" for both):
  edition <ed> <exe sha256> <label> [other exe hashes] | orig <ed> <file> <sha256> [other hashes]
  file <ed> <payload src> <game dst> | known_dll <sha256>
  archive <ed> <archive> <entry dirs; ;-separated> <expected ko\\archive sha256>
Editions are builds, not stores: "steam" = Japanese build (2.6.1.68), "gog" = English build
(2.6.1.80: GOG, and Steam set to English - the same exe wrapped in SteamStub, known here only by
the SHA-1 of Steam's depot manifest, written as "sha1:<hex>").
Usage: python -I make_release.py [--version 1.3] [--out DIR]"""
import glob
import argparse
import hashlib
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
PROJ = os.path.dirname(HERE)
DLL = os.path.join(PROJ, "dll", "out", "version.dll")
SETUP = os.path.join(PROJ, "installer", "out", "ISLAND-KO-Setup.exe")
README = os.path.join(PROJ, "release-docs", "읽어 주세요.txt")
LICENSE = os.path.join(ROOT, "fontsrc", "LICENSE-NotoSansCJK.txt")
COMMON_STATIC = ["ISLAND-KO.ttf", "pua_table.txt"]
ARCHIVES = ["scene.int", "fes.int", "config.int", "image.int", "movie.int"]
EDITIONS = {
    "steam": {"orig": os.path.join(ROOT, "steam-orig"), "build": os.path.join(ROOT, "build", "ko"),
              "label": "일본어판(엔진 2.6.1.68)",
              "static": ["msg_ko.txt", "exe_rsrc.bin", "cs2conf.dll", "config/startup.xml"],
              "orig_files": ["ISLAND.exe", "scene.int", "fes.int", "config.int", "image.int", "movie.int", "cs2conf.dll", "config/startup.xml"]},
    "gog": {"orig": os.path.join(ROOT, "gog-orig"), "build": os.path.join(ROOT, "build", "gog-ko"),
            "label": "영어판(엔진 2.6.1.80)",
            "static": ["language.txt", "config/startup.xml"],
            "orig_files": ["ISLAND.exe", "scene.int", "fes.int", "config.int", "image.int", "movie.int", "config/startup.xml", "language.txt"],
            # Steam's English depot 857451 (F:\Steam\depotcache manifest, tools\vercheck_depots.py): its other 36
            # files equal the GOG copy byte for byte, only ISLAND.exe differs (SteamStub, 7,219,056 bytes)
            "alt": {"ISLAND.exe": ["sha1:807ef482bacc9edabf5aeb991c6fbe273ce0429b"]}},
}
# every island-ko version.dll ever packed or left in a test copy is "ours" (reinstall/uninstall must not
# take an older patch DLL for somebody else's)
PREVIOUS = glob.glob(os.path.join(ROOT, "release", "*", "payload", "manifest.txt"))
OLD_DLL_DIRS = [ROOT, r"Y:\AI\claude-work\island-gog"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def open_kif(path, key):
    plain = open(path, "rb").read(19)[8:19] != b"__key__.dat"
    return cs2.PlainKif(path) if plain else cs2.Kif(path, key)


def changed_entries(orig, build, key):
    a, b = open_kif(orig, key), open_kif(build, key)
    out = {}
    with open(a.path, "rb") as fa, open(b.path, "rb") as fb:
        for ea, eb in zip(a.entries, b.entries):
            assert ea["name"] == eb["name"]
            db = b.read(eb["name"], fb)
            if ea["size"] == eb["size"] and a.read(ea["name"], fa) == db:
                continue
            out[eb["name"]] = db
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.3")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or os.path.join(ROOT, "release", "ISLAND-KO-" + args.version)
    if os.path.isdir(out):
        shutil.rmtree(out)
    pay = os.path.join(out, "payload")
    os.makedirs(os.path.join(pay, "ko"))
    lines = ["# ISLAND Korean patch manifest - Japanese build (Steam depot 857454 build 3508164, engine 2.6.1.68)"
             " and English build (engine 2.6.1.80: GOG, Steam depot 857451)",
             "set\tversion\t" + args.version]
    shutil.copy2(DLL, os.path.join(pay, "version.dll"))
    lines.append("set\tdll_sha256\t" + sha(DLL))
    known = set()
    for pm in PREVIOUS:
        if os.path.exists(pm) and not os.path.abspath(pm).startswith(os.path.abspath(out) + os.sep):
            t = open(pm, encoding="utf-8").read()
            known |= set(re.findall(r"(?m)^set\tdll_sha256\t(\w+)", t)) | set(re.findall(r"(?m)^known_dll\t(\w+)", t))
    old_builds = 0
    for top in OLD_DLL_DIRS:
        for r, ds, fs in os.walk(top):
            for f in fs:
                if f.lower() == "version.dll" and not os.path.abspath(r).startswith(os.path.abspath(out)):
                    p = os.path.join(r, f)
                    if "island-ko ".encode("utf-16-le") in open(p, "rb").read():   # our log line
                        h = sha(p)
                        if h not in known:
                            known.add(h)
                            old_builds += 1
    known.discard(sha(DLL))
    lines += ["known_dll\t" + k for k in sorted(known)]
    for ed, cfg in EDITIONS.items():
        alt = cfg.get("alt", {})
        lines.append("\t".join(["edition", ed, sha(os.path.join(cfg["orig"], "ISLAND.exe")), cfg["label"]] + alt.get("ISLAND.exe", [])))
    for ed, cfg in EDITIONS.items():
        alt = cfg.get("alt", {})
        for rel in cfg["orig_files"]:
            lines.append("\t".join(["orig", ed, rel.replace("/", "\\"), sha(os.path.join(cfg["orig"], rel))] + alt.get(rel, [])))
    # files
    for rel in COMMON_STATIC:
        a = sha(os.path.join(EDITIONS["steam"]["build"], rel)); b = sha(os.path.join(EDITIONS["gog"]["build"], rel))
        assert a == b, rel
        shutil.copy2(os.path.join(EDITIONS["steam"]["build"], rel), os.path.join(pay, "ko", rel))
        lines.append("file\tall\tko\\%s\tko\\%s" % (rel, rel))
    shutil.copy2(LICENSE, os.path.join(pay, "ko", "LICENSE-NotoSansCJK.txt"))
    lines.append("file\tall\tko\\LICENSE-NotoSansCJK.txt\tko\\LICENSE-NotoSansCJK.txt")
    for ed, cfg in EDITIONS.items():
        for rel in cfg["static"]:
            dst = os.path.join(pay, "ko-" + ed, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(cfg["build"], rel), dst)
            lines.append("file\t%s\t%s\tko\\%s" % (ed, ("ko-" + ed + "/" + rel).replace("/", "\\"), rel.replace("/", "\\")))
    # archive entries: an entry that is byte-identical in both editions is stored once (common),
    # the rest per edition; the installer reads every ';'-separated folder of an archive line
    counts = {}
    for arc in ARCHIVES:
        per = {}
        for ed, cfg in EDITIONS.items():
            key = cs2.crc_key(cs2.passphrase(os.path.join(cfg["orig"], "ISLAND.exe")))
            per[ed] = changed_entries(os.path.join(cfg["orig"], arc), os.path.join(cfg["build"], arc), key)
        base = os.path.splitext(arc)[0]
        common = {n: d for n, d in per["steam"].items() if per["gog"].get(n) == d}
        sets = {"common": common}
        for ed in per:
            sets[ed] = {n: d for n, d in per[ed].items() if n not in common}
        dirs = {ed: ";".join(["entries\\%s\\%s" % (s, base) for s in ("common", ed) if sets[s]]) for ed in per}
        for name, ents in sets.items():
            if not ents:
                continue
            d = os.path.join(pay, "entries", name, base)
            os.makedirs(d)
            for n, data in ents.items():
                with open(os.path.join(d, n), "wb") as f:
                    f.write(data)
            counts["%s/%s" % (name, base)] = len(ents)
        for ed, cfg in EDITIONS.items():
            if not dirs[ed]:
                raise SystemExit("no entries for %s %s" % (ed, arc))
            lines.append("archive\t%s\t%s\t%s\t%s" % (ed, arc, dirs[ed], sha(os.path.join(cfg["build"], arc))))
    with open(os.path.join(pay, "manifest.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    shutil.copy2(SETUP, os.path.join(out, "ISLAND 한국어 패치.exe"))
    if os.path.exists(README):
        shutil.copy2(README, os.path.join(out, "읽어 주세요.txt"))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, d, fs in os.walk(out) for f in fs)
    print({"release": out, "entries": counts, "bytes": size, "known_dll": len(known), "old_builds_found": old_builds})


if __name__ == "__main__":
    main()
