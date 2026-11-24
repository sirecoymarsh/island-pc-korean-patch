"""GOG test copy: Y:\\AI\\island-steam-ko\\gog-test (GOG originals + loader + ko\\), saves and settings
in Y:\\AI\\island-steam-ko\\gog-testsave (never %USERPROFILE%). The copy runs in test mode through
island-ko-test.ini (off-screen, never activated, own mutex, message boxes answered).

Usage: python -I gog_testgame.py [--lang ko|en] [--ko DIR] [--fresh-save] [--no-test-flag]
  --ko DIR : Korean files to put in gog-test\\ko (default: build\\gog-ko-test, then build\\gog-ko)"""
import argparse
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
ORIG = os.path.join(ROOT, "gog-orig")
TEST = os.path.join(ROOT, "gog-test")
SAVE = os.path.join(ROOT, "gog-testsave")
DLL = r"P:\AI\island-steam-ko\dll\out\version.dll"
# settings the GOG engine wrote on 10-28 (Codex trial) - used once as the template for setup.xml
SETUP_TEMPLATE = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\ui-trials-20261028\runtime\saves\gog-ui-trial\setup.xml"


def sync(src, dst):
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src) and int(os.path.getmtime(dst)) == int(os.path.getmtime(src)):
        return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return 1


def test_xml(text):
    """first active <save> -> the test save folder, sound keeps playing in the background off"""
    t, n = re.subn(r"(?m)^(\s*)<save>[^<]*</save>", lambda m: m.group(1) + "<save>" + SAVE + "</save>", text, count=1)
    assert n == 1
    return re.sub(r"<sticky>\d</sticky>", "<sticky>0</sticky>", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ko")
    ap.add_argument("--ko", action="append", default=None, help="may be given more than once; later folders win")
    ap.add_argument("--fresh-save", action="store_true")
    ap.add_argument("--no-test-flag", action="store_true")
    args = ap.parse_args()
    # never touch the copy while a game runs from it (11-08: the player's game was open from it)
    import gamectl
    running = [p for p, path in gamectl.processes() if path and os.path.normcase(os.path.dirname(path)) == os.path.normcase(TEST)]
    if running:
        raise SystemExit("ISLAND.exe is running from %s (pid %s) - not touching the copy" % (TEST, running))
    copied = 0
    for root, dirs, files in os.walk(ORIG):
        for fn in files:
            p = os.path.join(root, fn)
            copied += sync(p, os.path.join(TEST, os.path.relpath(p, ORIG)))
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    loose = open(os.path.join(ORIG, "config", "startup.xml"), "rb").read().decode("cp932")
    with open(os.path.join(TEST, "config", "startup.xml"), "wb") as f:
        f.write(test_xml(loose).encode("cp932"))
    ck = cs2.Kif(os.path.join(ORIG, "config.int"), key)
    ck.write(os.path.join(TEST, "config.int"), {"startup.xml": test_xml(ck.read("startup.xml").decode("cp932")).encode("cp932")})
    # Korean files: the release build, then the test variant (save path -> gog-testsave) over it
    srcs = list(args.ko) if args.ko else [d for d in (os.path.join(ROOT, "build", "gog-ko"), os.path.join(ROOT, "build", "gog-ko-test")) if os.path.isdir(d)]
    src = " + ".join(srcs)
    kod = os.path.join(TEST, "ko")
    wanted = {}
    for s in srcs:
        for root, dirs, files in os.walk(s):
            for fn in files:
                p = os.path.join(root, fn)
                wanted[os.path.relpath(p, s).lower()] = (p, os.path.relpath(p, s))
    if os.path.isdir(kod):   # drop files the new set does not have (e.g. a probe's)
        for root, dirs, files in os.walk(kod):
            for fn in files:
                p = os.path.join(root, fn)
                if os.path.relpath(p, kod).lower() not in wanted:
                    os.remove(p)
    for p, rel in wanted.values():
        copied += sync(p, os.path.join(kod, rel))
    shutil.copy2(DLL, os.path.join(TEST, "version.dll"))
    with open(os.path.join(TEST, "island-ko.ini"), "w", encoding="ascii") as f:
        f.write("[ISLAND-KO]\r\nlanguage=%s\r\n" % args.lang)
    flag = os.path.join(TEST, "island-ko-test.ini")
    if args.no_test_flag:
        if os.path.exists(flag):
            os.remove(flag)
    else:
        with open(flag, "w", encoding="ascii") as f:
            f.write("[TEST]\r\non=1\r\nx=4160\r\ny=200\r\n")
    if args.fresh_save and os.path.isdir(SAVE):
        shutil.rmtree(SAVE)
    os.makedirs(SAVE, exist_ok=True)
    sp = os.path.join(SAVE, "setup.xml")
    if not os.path.exists(sp):
        t = open(SETUP_TEMPLATE, "rb").read()
        t = re.sub(rb"<fullscreen>\d</fullscreen>", b"<fullscreen>0</fullscreen>", t)
        t = re.sub(rb"<setmode>\d</setmode>", b"<setmode>1</setmode>", t)
        t = re.sub(rb"<mute_master>\d</mute_master>", b"<mute_master>1</mute_master>", t)
        t = re.sub(rb"<face>[^<]*</face>", b"<face>MS Gothic</face>", t)  # a normal player's font
        ex = b"<export>" + os.path.join(SAVE, "export").encode("ascii") + b"</export>"
        pi = b"<picture>" + os.path.join(SAVE, "picture").encode("ascii") + b"</picture>"
        t = re.sub(rb"<export>[^<]*</export>", lambda m: ex, t)
        t = re.sub(rb"<picture>[^<]*</picture>", lambda m: pi, t)
        with open(sp, "wb") as f:
            f.write(t)
    print("gog test copy ready:", TEST, "files copied:", copied, "lang:", args.lang, "ko from:", src, "save:", SAVE,
          "test flag:", not args.no_test_flag)


if __name__ == "__main__":
    main()
