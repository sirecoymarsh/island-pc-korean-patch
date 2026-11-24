"""Steam game-language switch, simulated on a test copy (no Steam; the game is not started):
the patch is installed for one build, then the game files are replaced by the other build's (what
Steam does when the game language changes) while version.dll, island-ko.ini and ko\\ stay.
Checks: the installer sees ko\\ was made for the other build, the DLL turns Korean off (probe),
installing again builds ko\\ for the new build (= our build), the DLL is Korean again, and
uninstalling leaves exactly the new build's files.
Usage: python -I test_steam_switch.py [--first steam-en|steam] [RELEASE_DIR]"""
import argparse
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_edition_dll  # noqa: E402
from test_installer import CFG, ARCHIVES, ROOT, sha, tree  # noqa: E402

T = os.path.join(ROOT, "switchtest")
OURS = {"version.dll", "island-ko.ini", "island-ko.log"}


def files(d):
    return {os.path.relpath(os.path.join(r, f), d) for r, ds, fs in os.walk(d) for f in fs}


def lay_out(orig):
    """the game files of one build into T; our files (version.dll, ini, ko\\) are left alone"""
    for rel in files(T):
        if rel in OURS or rel.split(os.sep)[0] == "ko":
            continue
        os.remove(os.path.join(T, rel))
    for rel in files(orig):
        q = os.path.join(T, rel)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(os.path.join(orig, rel), q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", default="steam-en", choices=["steam-en", "steam"])
    ap.add_argument("release", nargs="?", default=os.path.join(ROOT, "release", "ISLAND-KO-1.3"))
    a = ap.parse_args()
    first, second = a.first, ("steam" if a.first == "steam-en" else "steam-en")
    exe = os.path.join(a.release, "ISLAND 한국어 패치.exe")

    def run(*args):
        r = subprocess.run([exe] + list(args) + ["--game", T])
        log = open(os.path.join(a.release, "setup-last.log"), encoding="utf-8-sig").read()
        head = {l.split()[0]: l.split()[1:] for l in log.splitlines() if l.startswith(("EDITION", "STEAM"))}
        return r.returncode, log, head

    if os.path.isdir(T):
        shutil.rmtree(T)
    os.makedirs(T)
    lay_out(CFG[first]["orig"])
    code, log, head = run("--install")
    print("1 install on %s: exit %d, edition %s, steam %s" % (first, code, head["EDITION"][0], head["STEAM"][0]))
    lay_out(CFG[second]["orig"])
    print("2 game files swapped to %s (version.dll, ini, ko\\ kept)" % second)
    code, log, head = run("--edition")
    st = head["STEAM"]
    print("3 installer sees: edition %s, steam %s, ko\\ made for %s -> mismatch reported: %s" % (
        head["EDITION"][0], st[0], st[st.index("INSTALLED_FOR") + 1], st[st.index("INSTALLED_FOR") + 1] != head["EDITION"][0]))
    kind = second
    probe, exp = test_edition_dll.IN_COPY[kind]
    off = dict(exp, lang="original", native_cp="932", mismatch=True)
    off.pop("font")
    print("4 DLL before reinstall:", end=" ")
    test_edition_dll.in_copy(T, kind, off)
    code, log, head = run("--install")
    c = CFG[second]
    same = {arc: sha(os.path.join(T, "ko", arc)) == sha(os.path.join(c["build"], arc)) for arc in ARCHIVES}
    same.update({rel: sha(os.path.join(T, "ko", rel)) == sha(os.path.join(c["build"], rel)) for rel in c["static"]})
    leftovers = sorted(rel for rel in files(os.path.join(T, "ko")) if not os.path.exists(os.path.join(c["build"], rel))
                       and rel not in ("install.txt", "LICENSE-NotoSansCJK.txt"))
    print("5 reinstall: exit %d, edition %s, ko\\ equal to our %s build: %s, files left from the other build: %s" % (
        code, head["EDITION"][0], second, all(same.values()), leftovers or "none"))
    print("6 DLL after reinstall:", end=" ")
    test_edition_dll.in_copy(T, kind)
    ini = open(os.path.join(T, "island-ko.ini"), encoding="utf-8").read()
    print("  language kept ko:", "language=ko" in ini)
    code, log, head = run("--uninstall")
    after = tree(T)
    print("7 uninstall: exit %d, folder equals the %s originals: %s" % (code, second, after == tree(c["orig"])))


if __name__ == "__main__":
    main()
