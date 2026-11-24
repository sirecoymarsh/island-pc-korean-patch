"""Step-by-step control of the running GOG test copy (one command per call):
  start | shot NAME | click X Y | rclick | move X Y | key VK | wheel D | activate | close | log [N] | state
Screens go to Y:\\AI\\island-steam-ko\\shots\\gogctl\\NAME.png (story screens are for reviewers only)."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots\gogctl"
U = gamectl.U


def attach():
    exe = os.path.join(gogenv.GAME, "ISLAND.exe")
    for pid, path in gamectl.processes():
        if path and os.path.normcase(path) == os.path.normcase(exe):
            ws = [w for w in gamectl.windows_of(pid) if gamectl.client_size(w[0])[0] >= 640]
            return gamectl.Game(pid, ws[0][0] if ws else None)
    return None


def activate(g):
    for msg, wp in ((gamectl.WM_ACTIVATEAPP, 1), (gamectl.WM_NCACTIVATE, 1), (gamectl.WM_ACTIVATE, 1), (gamectl.WM_SETFOCUS, 0)):
        U.PostMessageW(g.hwnd, msg, wp, 0)


def main():
    os.makedirs(SHOTS, exist_ok=True)
    cmd = sys.argv[1]
    a = sys.argv[2:]
    if cmd == "start":
        g = gogenv.start()
        print("started pid", g.pid if g else None, "hwnd", g.hwnd if g else None)
        return
    g = attach()
    if not g or not g.hwnd:
        print("game not running"); return
    if cmd == "shot":
        im = gamectl.capture(g.hwnd)
        for _ in range(6):
            if im is not None and max(im.convert("L").resize((16, 9)).tobytes()) > 8:
                break
            time.sleep(0.25); im = gamectl.capture(g.hwnd)
        p = os.path.join(SHOTS, a[0] + ".png"); im.save(p); print(p)
    elif cmd == "click":
        g.click(int(a[0]), int(a[1]), hold=0.1, settle=0.3); print("clicked", a)
    elif cmd == "rclick":
        g.rclick(); print("rclick")
    elif cmd == "move":
        g.move(int(a[0]), int(a[1])); print("moved", a)
    elif cmd == "key":
        g.key(int(a[0], 0)); print("key", a[0])
    elif cmd == "wheel":
        g.wheel(int(a[0])); print("wheel", a[0])
    elif cmd == "activate":
        activate(g); print("activate sent")
    elif cmd == "close":
        left = gogenv.finish(g); print("left", left)
    elif cmd == "log":
        n = int(a[0]) if a else 30
        for line in gogenv.read_log()[-n:]:
            print(line[:220])
    elif cmd == "state":
        r = gamectl.W.RECT(); U.GetWindowRect(g.hwnd, gamectl.C.byref(r))
        print("pid", g.pid, "hwnd", g.hwnd, "rect", (r.left, r.top, r.right, r.bottom), "fg is game", U.GetForegroundWindow() == g.hwnd,
              "shm", (g.shm.x, g.shm.y, g.shm.valid, g.shm.seq) if g.shm else None)


if __name__ == "__main__":
    main()
