"""version.dll build detection without the game: a probe exe (dll\\out\\edtest\\*.exe: with or without a
.bind section, version resource 2.6.1.68 / 2.6.1.80 / none) loads the proxy from a prepared folder; the
first island-ko.log line says what the DLL decided. Also: ko\\install.txt made for the other build
(Steam game language switched) must turn Korean off.
  python -I test_edition_dll.py              # the case table
  python -I test_edition_dll.py --in GAMEDIR # one probe (.bind + 2.6.1.80 = Steam English exe) run in an
                                             # installed copy, then the probe and its log are removed
Prints only the DLL's decisions and pass/fail."""
import argparse
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL = os.path.join(PROJ, "dll", "out", "version.dll")
PROBES = os.path.join(PROJ, "dll", "out", "edtest")
WORK = r"Y:\AI\claude-work\island-edtest"

# name, probe, language.txt in the folder, ko\install.txt edition (None = no install.txt), expected
CASES = [
    ("steam-ja", "edtest_v68_bind", False, "steam", dict(build="ja", steam="1", exe="2.6.1.68", lang="ko", native_cp="932")),
    ("steam-en", "edtest_v80_bind", True, "gog", dict(build="en", steam="1", exe="2.6.1.80", lang="ko", native_cp="949")),
    ("gog", "edtest_v80", True, "gog", dict(build="en", steam="0", exe="2.6.1.80", lang="ko", native_cp="949")),
    ("gog-no-language-txt", "edtest_v80", False, "gog", dict(build="en", steam="0", exe="2.6.1.80", lang="ko", native_cp="949")),
    ("bind-language-txt-no-version", "edtest_bind", True, "gog", dict(build="en", steam="1", exe="0.0.0.0", lang="ko", native_cp="949")),
    ("v68-language-txt", "edtest_v68", True, "gog", dict(build="en", steam="0", exe="2.6.1.68", lang="ko", native_cp="949")),
    ("plain", "edtest_plain", False, "steam", dict(build="ja", steam="0", exe="0.0.0.0", lang="ko", native_cp="932")),
    ("no-install-txt", "edtest_v80_bind", True, None, dict(build="en", steam="1", exe="2.6.1.80", lang="ko", native_cp="949")),
    ("steam-switched-ja-to-en", "edtest_v80_bind", True, "steam", dict(build="en", steam="1", exe="2.6.1.80", lang="original", native_cp="932", mismatch=True)),
    ("steam-switched-en-to-ja", "edtest_v68_bind", False, "gog", dict(build="ja", steam="1", exe="2.6.1.68", lang="original", native_cp="932", mismatch=True)),
]


def run_probe(folder, probe):
    exe = os.path.join(folder, probe + ".exe")
    shutil.copy2(os.path.join(PROBES, probe + ".exe"), exe)
    log = os.path.join(folder, "island-ko.log")
    if os.path.exists(log):
        os.remove(log)
    r = subprocess.run([exe], cwd=folder, timeout=30, env=dict(os.environ, ISLANDKO_TEST="1"))
    text = open(log, encoding="utf-8-sig").read()
    first = next(l for l in text.splitlines() if l.startswith("island-ko ") and " build=" in l)
    got = dict(re.findall(r"(\w+)=(\S+)", first.split(" game=")[0]))
    got["mismatch"] = "was installed for the" in text
    got["exit"] = r.returncode
    return got, exe, log


def check(got, exp):
    def ok(k, v):
        if k == "mismatch":
            return got["mismatch"] == v
        if v == "nonzero":   # AddFontResourceEx returns the number of faces it added
            return got.get(k) not in (None, "0")
        return got.get(k) == v
    bad = {k: (got.get(k), v) for k, v in exp.items() if not ok(k, v)}
    if "mismatch" not in exp and got["mismatch"]:
        bad["mismatch"] = (True, False)
    return bad


def table():
    os.makedirs(WORK, exist_ok=True)
    fails = 0
    for name, probe, langtxt, inst, exp in CASES:
        d = os.path.join(WORK, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(os.path.join(d, "ko"))
        shutil.copy2(DLL, os.path.join(d, "version.dll"))
        if langtxt:
            open(os.path.join(d, "language.txt"), "w", encoding="utf-8").write("probe\n")
        open(os.path.join(d, "island-ko.ini"), "w", encoding="utf-8").write("[ISLAND-KO]\nlanguage=ko\n")
        open(os.path.join(d, "ko", "scene.int"), "wb").close()
        open(os.path.join(d, "ko", "language.txt"), "w", encoding="ascii").write("#949\r\n")
        if inst:
            open(os.path.join(d, "ko", "install.txt"), "w", encoding="utf-8", newline="\r\n").write(
                "ISLAND Korean patch probe\nedition %s\ninstalled now\n" % inst)
        got, _, _ = run_probe(d, probe)
        bad = check(got, exp)
        fails += bool(bad)
        print("%-30s %-16s build=%s steam=%s exe=%s lang=%s native_cp=%s mismatch=%s exit=%s  %s" % (
            name, probe, got.get("build"), got.get("steam"), got.get("exe"), got.get("lang"), got.get("native_cp"),
            got["mismatch"], got["exit"], "PASS" if not bad else "FAIL %s" % bad))
    print("cases %d, failed %d" % (len(CASES), fails))
    return fails


# probe that stands in for each copy's exe, and what the DLL must decide in an installed copy
IN_COPY = {
    "steam": ("edtest_v68_bind", dict(build="ja", steam="1", exe="2.6.1.68", lang="ko", native_cp="932", font="nonzero")),
    "gog": ("edtest_v80", dict(build="en", steam="0", exe="2.6.1.80", lang="ko", native_cp="949", font="nonzero")),
    "steam-en": ("edtest_v80_bind", dict(build="en", steam="1", exe="2.6.1.80", lang="ko", native_cp="949", font="nonzero")),
}


def in_copy(game, kind="steam-en", expect=None):
    probe, exp = IN_COPY[kind]
    exp = expect or exp
    got, exe, log = run_probe(game, probe)
    os.remove(exe)
    os.remove(log)
    bad = check(got, exp)
    print("probe %s in %s: build=%s steam=%s exe=%s lang=%s native_cp=%s font=%s map=%s msgs=%s mismatch=%s  %s" % (
        probe, game, got.get("build"), got.get("steam"), got.get("exe"), got.get("lang"), got.get("native_cp"), got.get("font"),
        got.get("map"), got.get("msgs"), got["mismatch"], "PASS" if not bad else "FAIL %s" % bad))
    return bool(bad)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="game")
    ap.add_argument("--kind", default="steam-en", choices=sorted(IN_COPY))
    a = ap.parse_args()
    sys.exit(in_copy(a.game, a.kind) if a.game else table())
