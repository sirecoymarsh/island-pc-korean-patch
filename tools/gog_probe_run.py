"""Probe run on the GOG test copy (gog-test\\ko = build\\gog-probe): new game, capture each probe
line (burst after each advance), open the backlog, never advance past the last probe line.
Usage: python -I gog_probe_run.py [tag] [n_lines]"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
TAG = sys.argv[1] if len(sys.argv) > 1 else "a"
NLINES = int(sys.argv[2]) if len(sys.argv) > 2 else 6
SHOTS = os.path.join(ROOT, "shots", "gog_probe_" + TAG)
START = (120, 360)


def sig(im):
    return im.resize((80, 45)).convert("L").tobytes()


def same(a, b, tol=3):
    return a is not None and b is not None and sum(abs(x - y) > 12 for x, y in zip(a, b)) <= tol


def wait_stable(g, n=3, step=1.0, limit=90):
    prev = None; stable = 0; t0 = time.time(); im = None
    while time.time() - t0 < limit:
        time.sleep(step)
        im = g.shot()
        s = sig(im) if im is not None else None
        stable = stable + 1 if same(s, prev) else 0
        prev = s
        if stable >= n:
            break
    return im


def main():
    os.makedirs(SHOTS, exist_ok=True)
    for f in os.listdir(SHOTS):
        os.remove(os.path.join(SHOTS, f))
    f0 = gamectl.gpu_fault_count()
    g = None
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            print("no game window"); return
        print("pid", g.pid, "client", gamectl.client_size(g.hwnd))
        title = wait_stable(g)
        title.save(os.path.join(SHOTS, "00_title.png"))
        tsig = sig(title)
        g.click(*START)
        time.sleep(4)
        im = g.shot()
        if same(sig(im), tsig, 40):
            g.key(0x0D)
            time.sleep(4)
        wait_stable(g, n=2, step=1.0, limit=30)
        for i in range(NLINES):
            for k in range(6):
                im = g.shot()
                if im is not None:
                    im.save(os.path.join(SHOTS, "line%d_%02d.png" % (i + 1, k)))
                time.sleep(0.5)
            if i < NLINES - 1:
                g.click(640, 400)
                time.sleep(0.8)
        g.wheel(120)
        time.sleep(2.5)
        g.shot(os.path.join(SHOTS, "backlog.png"))
        log = gogenv.read_log()
        print("log:")
        for line in log:
            if "redirect" in line and "scene.int" not in line:
                continue
            print("  LOG", line[:200])
    finally:
        left = gogenv.finish(g)
        print("left", left, "gpu faults", f0, gamectl.gpu_fault_count())


if __name__ == "__main__":
    main()
