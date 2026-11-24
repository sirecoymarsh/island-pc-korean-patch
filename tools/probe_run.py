"""Probe run: test copy with the probe scene.int (first 5 text lines of com01 replaced by neutral
test strings). Starts a new game, captures each probe line (burst after each advance), opens the
backlog, never advances past the 5th probe line. Usage: probe_run.py [tag]"""
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import testenv  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
TAG = sys.argv[1] if len(sys.argv) > 1 else ""
SHOTS = os.path.join(ROOT, "shots", "probe" + ("_" + TAG if TAG else ""))
KO_SCENE = os.path.join(ROOT, "testgame", "ko", "scene.int")
PROBE = os.path.join(ROOT, "build", "probe", "scene.int")
REAL = os.path.join(ROOT, "build", "ko", "scene.int")


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


def start_new_game(g, shots):
    title = wait_stable(g)
    title.save(os.path.join(shots, "00_title.png"))
    tsig = sig(title)
    g.click(140, 361)  # 처음부터
    time.sleep(4)
    im = g.shot()
    if same(sig(im), tsig, 40):
        g.key(0x0D)  # the hovered button takes Enter
        time.sleep(4)
    return tsig


def main():
    os.makedirs(SHOTS, exist_ok=True)
    for f in os.listdir(SHOTS):
        os.remove(os.path.join(SHOTS, f))
    shutil.copy2(PROBE, KO_SCENE)
    f0 = gamectl.gpu_fault_count()
    g = None
    try:
        g = testenv.start()
        if not g or not g.hwnd:
            print("no game window"); return
        start_new_game(g, SHOTS)
        wait_stable(g, n=2, step=1.0, limit=30)
        for i in range(5):
            last = None
            for k in range(8):
                im = g.shot()
                if im is not None:
                    im.save(os.path.join(SHOTS, "line%d_%02d.png" % (i + 1, k)))
                time.sleep(0.5)
            if i < 4:
                g.click(640, 400)
                time.sleep(0.8)
        g.wheel(120)
        time.sleep(2.5)
        g.shot(os.path.join(SHOTS, "backlog.png"))
        print("log tail:")
        for line in testenv.read_log()[-6:]:
            print("  LOG", line[:200])
    finally:
        left = testenv.finish(g)
        shutil.copy2(REAL, KO_SCENE)
        print("left", left, "gpu faults", f0, gamectl.gpu_fault_count(), "scene restored", os.path.getsize(KO_SCENE) == os.path.getsize(REAL))


if __name__ == "__main__":
    main()
