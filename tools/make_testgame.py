"""Assemble a Steam test copy: Y:\\AI\\island-steam-ko\\testgame (original files + loader + ko\\).
Every save/config the test copy writes goes to Y:\\AI\\island-steam-ko\\testsave (never the
player's AppData folder). Usage: python -I make_testgame.py [--lang ko|ja] [--fresh-save]"""
import argparse
import glob
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
ORIG = os.path.join(ROOT, "steam-orig")
TEST = os.path.join(ROOT, "testgame")
SAVE = os.path.join(ROOT, "testsave")
BUILD = os.path.join(ROOT, "build", "ko")
BUILD_TEST = os.path.join(ROOT, "build", "ko-test")
DLL = r"P:\AI\island-steam-ko\dll\out\version.dll"
CODEX_CS2CONF = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\ko\cs2conf.dll"


def sync(src, dst):
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src) and int(os.path.getmtime(dst)) == int(os.path.getmtime(src)):
        return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return 1


def test_xml(text):
    t, n = re.subn(r"(?m)^(\s*)<save>[^<]*</save>", lambda m: m.group(1) + "<save>" + SAVE + "</save>", text, count=1)
    assert n == 1
    t = re.sub(r"<sticky>\d</sticky>", "<sticky>0</sticky>", t)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ko")
    ap.add_argument("--fresh-save", action="store_true")
    args = ap.parse_args()
    copied = 0
    for root, dirs, files in os.walk(ORIG):
        for fn in files:
            p = os.path.join(root, fn)
            copied += sync(p, os.path.join(TEST, os.path.relpath(p, ORIG)))
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))
    # base (Japanese) config with the test save folder
    loose = open(os.path.join(ORIG, "config", "startup.xml"), "rb").read().decode("cp932")
    with open(os.path.join(TEST, "config", "startup.xml"), "wb") as f:
        f.write(test_xml(loose).encode("cp932"))
    ck = cs2.Kif(os.path.join(ORIG, "config.int"), key)
    ck.write(os.path.join(TEST, "config.int"), {n: test_xml(ck.read(n).decode("cp932")).encode("cp932") for n in ("startup.xml", "startup_master.xml")})
    # Korean files
    kod = os.path.join(TEST, "ko")
    os.makedirs(os.path.join(kod, "config"), exist_ok=True)
    for fn in ["scene.int", "fes.int", "image.int", "ISLAND-KO.ttf", "pua_table.txt", "msg_ko.txt", "exe_rsrc.bin"]:
        copied += sync(os.path.join(BUILD, fn), os.path.join(kod, fn))
    copied += sync(CODEX_CS2CONF, os.path.join(kod, "cs2conf.dll"))
    copied += sync(os.path.join(BUILD_TEST, "config.int"), os.path.join(kod, "config.int"))
    copied += sync(os.path.join(BUILD_TEST, "config", "startup.xml"), os.path.join(kod, "config", "startup.xml"))
    shutil.copy2(DLL, os.path.join(TEST, "version.dll"))
    with open(os.path.join(TEST, "island-ko.ini"), "w", encoding="ascii") as f:
        f.write("[ISLAND-KO]\r\nlanguage=%s\r\n" % args.lang)
    # test save folder: window mode, muted, screen-mode question answered; font left as the
    # player's MS Gothic on purpose (the loader must override it)
    if args.fresh_save and os.path.isdir(SAVE):
        shutil.rmtree(SAVE)
    os.makedirs(SAVE, exist_ok=True)
    sp = os.path.join(SAVE, "setup.xml")
    if not os.path.exists(sp):
        user = glob.glob(os.path.join(os.environ["APPDATA"], "*", "ISLAND", "setup.xml"))
        t = open(user[0], "rb").read()  # bytes: the player's file mixes CP932 and CP949 paths
        t = re.sub(rb"<fullscreen>\d</fullscreen>", b"<fullscreen>0</fullscreen>", t)
        t = re.sub(rb"<setmode>\d</setmode>", b"<setmode>1</setmode>", t)
        t = re.sub(rb"<mute_master>\d</mute_master>", b"<mute_master>1</mute_master>", t)
        ex = b"<export>" + os.path.join(SAVE, "export").encode("ascii") + b"</export>"
        pi = b"<picture>" + os.path.join(SAVE, "picture").encode("ascii") + b"</picture>"
        t = re.sub(rb"<export>[^<]*</export>", lambda m: ex, t)
        t = re.sub(rb"<picture>[^<]*</picture>", lambda m: pi, t)
        with open(sp, "wb") as f:
            f.write(t)
    print("test copy ready:", TEST, "files copied:", copied, "lang:", args.lang, "save:", SAVE)


if __name__ == "__main__":
    main()
