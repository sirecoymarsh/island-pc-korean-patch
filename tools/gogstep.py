"""Step-by-step control of the GOG test copy (test mode, off-screen) across separate commands:
  gogstep.py start                 start the test copy (refuses while any ISLAND.exe runs)
  gogstep.py hover X Y [name]      move the virtual cursor there (twice, to make the hover stick), capture
  gogstep.py enter [name]          Enter on the hovered element, capture
  gogstep.py click X Y [name]      posted click, capture
  gogstep.py back [name]           right click, capture
  gogstep.py shot name             capture
  gogstep.py marks                 print tab/checkbox/menu markers of the current screen
  gogstep.py close                 normal exit (message box answered); stops only the test copy's game
Captures: shots\\gog_qa_step\\<name>.png (UI screens; gallery captures are deleted after checking)."""
import os
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots\gog_qa_step"
EXE = os.path.join(gogenv.GAME, "ISLAND.exe")
VK_RETURN = 0x0D


def game():
    procs = [p for p, path in gamectl.processes() if path and os.path.normcase(path) == os.path.normcase(EXE)]
    if not procs:
        raise SystemExit("test game not running")
    ws = [w for w in gamectl.windows_of(procs[0]) if gamectl.client_size(w[0])[0] >= 640]
    return gamectl.Game(procs[0], ws[0][0])


def capture(g, name, wait=2.0):
    time.sleep(wait)
    im = None
    for _ in range(40):
        im = g.shot()
        if im is not None and np.asarray(im.convert("L")).max() > 8:
            break
        time.sleep(0.25)
    os.makedirs(SHOTS, exist_ok=True)
    if name:
        im.save(os.path.join(SHOTS, name + ".png"))
    marks(im, name)
    return im


def marks(im, name=""):
    a = np.asarray(im.convert("RGB")).astype(int)

    def mag(x, y):
        r, gg, b = a[y, x]
        return r > 180 and gg < 130 and b > 140
    tabs = [n for n, x in (("sound", 80), ("text", 162), ("dialog", 244), ("key", 326), ("touch", 408), ("flow", 490)) if mag(x, 647)]
    col = a[240:460, 429:432].mean(axis=2)
    print("%-22s mean %5.1f tab=%s row11=%s row12=%s dialog_box=%s title_6btn_text=%d" % (
        name, a.mean(), tabs, mag(718, 477), mag(718, 559), int((col < 160).sum()) > 300,
        int((a[560:586, 100:250].mean(axis=2) < 90).sum())))


def main():
    cmd = sys.argv[1]
    arg = sys.argv[2:]
    if cmd == "start":
        g = gogenv.start()
        t, k = time.time(), 0
        while time.time() - t < 120 and k < 4:
            time.sleep(1.0)
            im = g.shot()
            if im is None:
                continue
            band = np.asarray(im.convert("RGB"), dtype=np.int16)[630:690, 40:1240]
            k = k + 1 if abs(float(band.mean()) - 232) < 12 else 0
        time.sleep(2.0)
        print("started pid", g.pid, "title ready" if k >= 4 else "title not detected")
        capture(g, "00_title", 0)
        return
    g = game()
    if cmd == "hover":
        x, y = int(arg[0]), int(arg[1])
        g.move(x, y); time.sleep(0.6); g.move(x + 2, y + 1); time.sleep(0.6)
        capture(g, arg[2] if len(arg) > 2 else "", 0.6)
    elif cmd == "enter":
        g.key(VK_RETURN)
        capture(g, arg[0] if arg else "", 2.5)
    elif cmd == "click":
        x, y = int(arg[0]), int(arg[1])
        g.click(x, y, hold=0.1, settle=0.3)
        capture(g, arg[2] if len(arg) > 2 else "", 2.0)
    elif cmd == "back":
        g.rclick()
        capture(g, arg[0] if arg else "", 2.5)
    elif cmd == "shot":
        capture(g, arg[0], 0)
    elif cmd == "marks":
        capture(g, "", 0)
    elif cmd == "close":
        pid = g.pid
        left = gogenv.finish(g)
        if pid in left:
            os.system("taskkill /PID %d /F >nul 2>nul" % pid)
            print("did not exit - stopped", pid)
        print("closed; left", [p for p in left if p != pid])


if __name__ == "__main__":
    main()
