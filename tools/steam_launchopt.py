"""Read / set / restore the Steam launch option of ISLAND (app 857450) in localconfig.vdf.
Steam must be closed (it rewrites the file on exit). Only that one value changes; a backup of
the whole file is kept and the result is checked line by line.
Usage: python -I steam_launchopt.py show | set-test | restore"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
VDF = r"F:\steam\userdata\62409541\config\localconfig.vdf"
BACKUP_DIR = r"Y:\AI\island-steam-ko\steam-config-backup"
STATE = os.path.join(BACKUP_DIR, "launch_option_state.json")
WRAPPER = r'"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "P:\AI\island-steam-ko\tools\steam_wrapper.ps1" %command%'


def vdf_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def vdf_unescape(s):
    return re.sub(r"\\(.)", lambda m: m.group(1), s)


def steam_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"], capture_output=True, text=True).stdout
    return "steam.exe" in out.lower()


def find(text):
    """Locate the LaunchOptions line inside the apps/857450 block."""
    for m in re.finditer(r'\n(\t+)"857450"\n\1\{\n', text):
        indent = m.group(1)
        end = text.find("\n" + indent + "}", m.end())
        block = text[m.end():end]
        lm = re.search(r'\n?(\t+)"LaunchOptions"\t\t"((?:[^"\\]|\\.)*)"', block)
        if lm and "LastPlayed" in block:
            s = m.end() + lm.start(2)
            return s, m.end() + lm.end(2), vdf_unescape(lm.group(2))
    return None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    text = open(VDF, encoding="utf-8").read()
    loc = find(text)
    if not loc:
        raise SystemExit("LaunchOptions for 857450 not found")
    s, e, cur = loc
    if cmd == "show":
        print(json.dumps({"current": cur, "steam_running": steam_running()}, ensure_ascii=False))
        return
    if steam_running():
        raise SystemExit("Steam is running - close it first")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if cmd == "set-test":
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(VDF, os.path.join(BACKUP_DIR, "localconfig.vdf." + stamp))
        if not os.path.exists(STATE):
            json.dump({"original": cur, "saved_at": stamp}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        new = WRAPPER
    elif cmd == "restore":
        new = json.load(open(STATE, encoding="utf-8"))["original"]
    else:
        raise SystemExit("unknown command")
    out = text[:s] + vdf_escape(new) + text[e:]
    a, b = text.split("\n"), out.split("\n")
    diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert len(a) == len(b) and len(diff) <= 1, "unexpected change"
    with open(VDF, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(json.dumps({"set": cmd, "value": find(open(VDF, encoding="utf-8").read())[2]}, ensure_ascii=False))
    if cmd == "restore":
        os.remove(STATE)


if __name__ == "__main__":
    main()
