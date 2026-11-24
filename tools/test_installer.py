"""Installer round trip on a pristine copy (never the player's install, the game is not started):
install -> outputs equal our build -> language switch -> reinstall -> uninstall -> folder equals original.
Usage: python -I test_installer.py [--edition steam|gog|steam-en] [--probe] [RELEASE_DIR]
  steam-en = the GOG copy dressed as Steam set to English (make_fake_steam_en.py): must install as the
  English build ("gog") and be launched through Steam; --probe runs the DLL build probe in the
  installed copy (test_edition_dll.py --in)."""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"Y:\AI\island-steam-ko"
CFG = {
    "steam": {"orig": os.path.join(ROOT, "steam-orig"), "test": os.path.join(ROOT, "installtest"), "build": os.path.join(ROOT, "build", "ko"),
              "static": ["ISLAND-KO.ttf", "pua_table.txt", "msg_ko.txt", "exe_rsrc.bin", "cs2conf.dll", os.path.join("config", "startup.xml")],
              "original_lang": "ja", "expect": ("steam", "1")},
    "gog": {"orig": os.path.join(ROOT, "gog-orig"), "test": os.path.join(ROOT, "gog-installtest"), "build": os.path.join(ROOT, "build", "gog-ko"),
            "static": ["ISLAND-KO.ttf", "pua_table.txt", "language.txt", os.path.join("config", "startup.xml")],
            "original_lang": "en", "expect": ("gog", "0")},
    "steam-en": {"orig": os.path.join(ROOT, "steam-en-fake-orig"), "test": os.path.join(ROOT, "steam-en-fake-installtest"),
                 "build": os.path.join(ROOT, "build", "gog-ko"),
                 "static": ["ISLAND-KO.ttf", "pua_table.txt", "language.txt", os.path.join("config", "startup.xml")],
                 "original_lang": "en", "expect": ("gog", "1")},
}
ARCHIVES = ["scene.int", "fes.int", "config.int", "image.int", "movie.int"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tree(d):
    out = {}
    for r, ds, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, d)] = (os.path.getsize(p), sha(p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", default="gog")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("release", nargs="?", default=os.path.join(ROOT, "release", "ISLAND-KO-1.3"))
    a = ap.parse_args()
    c = CFG[a.edition]
    ORIG, T, BUILD = c["orig"], c["test"], c["build"]
    exe = os.path.join(a.release, "ISLAND 한국어 패치.exe")

    def run(*args):
        r = subprocess.run([exe] + list(args) + ["--game", T])
        log = open(os.path.join(a.release, "setup-last.log"), encoding="utf-8-sig").read()
        return r.returncode, log

    for r, ds, fs in os.walk(ORIG):
        for f in fs:
            p = os.path.join(r, f); q = os.path.join(T, os.path.relpath(p, ORIG))
            if not (os.path.exists(q) and os.path.getsize(q) == os.path.getsize(p)):
                os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copy2(p, q)
    for extra in ["version.dll", "island-ko.ini", "island-ko.log"]:
        if os.path.exists(os.path.join(T, extra)): os.remove(os.path.join(T, extra))
    if os.path.isdir(os.path.join(T, "ko")): shutil.rmtree(os.path.join(T, "ko"))
    before = tree(T)
    assert before == tree(ORIG), "install test copy differs from original"
    code, log = run("--install")
    print("install exit", code, "|", [l for l in log.splitlines() if l.startswith(("EDITION", "STEAM", "판"))])
    ed = next((l.split()[1] for l in log.splitlines() if l.startswith("EDITION")), None)
    st = next((l.split()[1] for l in log.splitlines() if l.startswith("STEAM")), None)
    print("edition / steam as expected %s: %s" % (c["expect"], (ed, st) == c["expect"]))
    print("\n".join("  " + l for l in log.splitlines() if l.startswith(("WARNING", "ERROR", "참고", "경고")) or "해시" in l))
    res = {}
    for arc in ARCHIVES:
        res[arc] = sha(os.path.join(T, "ko", arc)) == sha(os.path.join(BUILD, arc))
    for rel in c["static"]:
        res[rel] = sha(os.path.join(T, "ko", rel)) == sha(os.path.join(BUILD, rel))
    print("ko outputs identical to build:", res)
    print("version.dll is the release's:", sha(os.path.join(T, "version.dll")) == sha(os.path.join(a.release, "payload", "version.dll")))
    originals_untouched = all(tree(T).get(k) == v for k, v in before.items())
    print("originals untouched after install:", originals_untouched)
    ini = open(os.path.join(T, "island-ko.ini"), encoding="utf-8").read()
    print("language after install ko:", "language=ko" in ini)
    if a.probe:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import test_edition_dll
        test_edition_dll.in_copy(T, a.edition)
    code2, log2 = run("--lang", "original")
    ini = open(os.path.join(T, "island-ko.ini"), encoding="utf-8").read()
    print("lang original exit", code2, "ini has", c["original_lang"] + ":", "language=" + c["original_lang"] in ini)
    code3, log3 = run("--install")
    ini = open(os.path.join(T, "island-ko.ini"), encoding="utf-8").read()
    print("reinstall exit", code3, "language kept:", "language=" + c["original_lang"] in ini)
    code4, log4 = run("--uninstall")
    after = tree(T)
    print("uninstall exit", code4, "folder equals original:", after == before, "extra:", sorted(set(after) - set(before))[:5])
    print("uninstall log tail:", log4.strip().splitlines()[-1] if log4.strip() else "")


if __name__ == "__main__":
    main()
