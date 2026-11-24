"""UI tour on the GOG test copy (no story screens): title -> settings (each tab) -> back -> exit.
Hover first, then Enter (GOG title buttons do not always take a posted click).
Usage: python -I gog_uitour.py"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots\gog_ui"
VK_RETURN, VK_ESCAPE = 0x0D, 0x1B


def sig(im):
    return im.resize((80, 45)).convert("L").tobytes()


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def shot_ok(g, tries=8):
    im = None
    for _ in range(tries):
        im = g.shot()
        if im is not None and max(im.convert("L").resize((16, 9)).tobytes()) > 8:
            return im
        time.sleep(0.25)
    return im


def press(g, x, y, settle=1.2):
    """hover, click, and Enter when the click did not change the screen"""
    g.move(x, y)
    time.sleep(settle)
    before = sig(shot_ok(g))
    g.click(x, y, hold=0.1, settle=0.3)
    time.sleep(2.5)
    if diff(sig(shot_ok(g)), before) < 3:
        g.key(VK_RETURN)
        time.sleep(2.5)
        return "enter"
    return "click"


def main():
    os.makedirs(SHOTS, exist_ok=True)
    g = None
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            print("no window"); return
        prev = None; stable = 0; t0 = time.time()
        while time.time() - t0 < 90:
            time.sleep(1)
            im = shot_ok(g)
            s = sig(im)
            stable = stable + 1 if prev is not None and diff(s, prev) < 1.5 else 0
            prev = s
            if stable >= 3 and time.time() - t0 > 20:
                break
        im.save(os.path.join(SHOTS, "title.png"))
        how = press(g, 140, 465)          # settings
        im = shot_ok(g); im.save(os.path.join(SHOTS, "config_0.png"))
        print("settings opened by", how)
        # the settings screen has tabs on the left/top - capture a few positions by keyboard paging
        for i, (x, y) in enumerate([(120, 160), (120, 220), (120, 280), (120, 340), (120, 400), (120, 460)]):
            g.move(x, y); time.sleep(0.8)
            g.click(x, y, hold=0.1, settle=0.3); time.sleep(1.5)
            shot_ok(g).save(os.path.join(SHOTS, "config_%d.png" % (i + 1)))
        g.rclick(); time.sleep(2.0)
        shot_ok(g).save(os.path.join(SHOTS, "after_back.png"))
        print("log tail:")
        for line in gogenv.read_log()[-5:]:
            if not line.startswith("font face"):
                print("  LOG", line[:160])
    finally:
        left = gogenv.finish(g)
        print("left", left)


if __name__ == "__main__":
    main()
