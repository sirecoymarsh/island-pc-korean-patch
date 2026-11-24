"""First smoke test: Steam launches the test copy, title screen, DLL log, normal exit."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import testenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots"


def main():
    os.makedirs(SHOTS, exist_ok=True)
    f0 = gamectl.gpu_fault_count()
    t0 = time.time()
    g = testenv.start()
    if not g:
        print("game did not start"); testenv.wrapper_mode(False); return
    print("pid", g.pid, "hwnd", g.hwnd, "start %.1fs" % (time.time() - t0))
    if g.hwnd:
        print("client", gamectl.client_size(g.hwnd), "foreground is game:", gamectl.U.GetForegroundWindow() == g.hwnd)
    for i in range(6):
        time.sleep(5)
        if g.hwnd:
            g.shot(os.path.join(SHOTS, "smoke_%02d.png" % i))
    log = testenv.read_log()
    left = testenv.finish(g)
    f1 = gamectl.gpu_fault_count()
    print("log lines:", len(log))
    for line in log[:40]:
        print("  LOG", line[:220])
    print("left processes:", left, "gpu faults before/after:", f0, f1)


if __name__ == "__main__":
    main()
