"""End of a test session: close Steam (it was started by the tests), then put the ISLAND launch
option back to the value saved before the tests (steam_launchopt.py restore).
Refuses while any ISLAND.exe runs."""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import testenv  # noqa: E402


def main():
    if gamectl.processes():
        raise SystemExit("ISLAND.exe is running: %s" % gamectl.processes())
    testenv.wrapper_mode(False)
    if gamectl.steam_running():
        subprocess.Popen([gamectl.STEAM, "-shutdown"], close_fds=True)
        t0 = time.time()
        while time.time() - t0 < 90 and gamectl.steam_running():
            time.sleep(2)
        print("steam closed:", not gamectl.steam_running(), "after %.0fs" % (time.time() - t0))
    if gamectl.steam_running():
        raise SystemExit("Steam still running - launch option not restored")
    r = subprocess.run(["python", "-I", os.path.join(HERE, "steam_launchopt.py"), "restore"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip() or r.stderr.strip())


if __name__ == "__main__":
    main()
