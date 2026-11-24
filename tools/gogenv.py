"""GOG test session helpers (no Steam): start the GOG test copy outside the Claude app's process
tree (WMI Win32_Process.Create, SW_SHOWNOACTIVATE), find its window, normal exit, DLL log.
The copy itself is in test mode through island-ko-test.ini (see gog_testgame.py)."""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402

GAME = r"Y:\AI\island-steam-ko\gog-test"


def preflight(game=GAME):
    """Refuse to start while any ISLAND.exe runs (the player's game or a stale test), and when the
    copy is not in test mode or would start full screen."""
    procs = gamectl.processes()
    if procs:
        raise SystemExit("ISLAND.exe already running: %s" % procs)
    flag = os.path.join(game, "island-ko-test.ini")
    if not os.path.exists(flag) or "on=1" not in open(flag, encoding="ascii").read():
        raise SystemExit("test flag missing: " + flag)
    setup = os.path.join(r"Y:\AI\island-steam-ko\gog-testsave", "setup.xml")
    if os.path.exists(setup) and b"<fullscreen>0</fullscreen>" not in open(setup, "rb").read():
        raise SystemExit("test save is set to full screen")


def wmi_start(exe, cwd):
    ps = ("$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]4};"
          "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"%s\"'; CurrentDirectory='%s'; ProcessStartupInformation=$si};"
          "\"$($r.ReturnValue) $($r.ProcessId)\"") % (exe, cwd)
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    rv, pid = (out.split() + ["", ""])[:2]
    return int(rv or -1), int(pid or 0)


def start(game=GAME, timeout=90):
    preflight(game)
    exe = os.path.join(game, "ISLAND.exe")
    rv, pid = wmi_start(exe, game)
    if rv != 0:
        raise SystemExit("WMI create failed: %s" % rv)
    t0 = time.time()
    while time.time() - t0 < timeout:
        procs = [p for p, path in gamectl.processes() if path and os.path.normcase(path) == os.path.normcase(exe)]
        if procs:
            pid = procs[0]
            ws = [w for w in gamectl.windows_of(pid) if gamectl.client_size(w[0])[0] >= 640]
            if ws:
                return gamectl.Game(pid, ws[0][0])
        time.sleep(0.5)
    return gamectl.Game(pid, None) if pid else None


def read_log(game=GAME):
    p = os.path.join(game, "island-ko.log")
    if not os.path.exists(p):
        return []
    return open(p, encoding="utf-8-sig", errors="replace").read().splitlines()


def finish(g, game=GAME, timeout=30):
    """Normal exit through the game's own close path (message box auto-answered Yes)."""
    if g and g.hwnd:
        g.close()
        t0 = time.time()
        while time.time() - t0 < timeout and g.alive():
            time.sleep(0.5)
    exe = os.path.join(game, "ISLAND.exe")
    return [p for p, path in gamectl.processes() if path and os.path.normcase(path) == os.path.normcase(exe)]
