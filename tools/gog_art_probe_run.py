"""Run the art probe (gog_art_probe.py) on the GOG test copy, off-screen and muted.

For every image block the screen above the message window is compared with our Korean PNG and with
the GOG original (the Korean must match better); the staff roll is captured while it scrolls and each
capture is located in our Korean roll; each movie must play for about its length (the capture of a
playing movie is black off-screen, so playback is timed: click -> movie -> the next screen).
Screens are kept on disk for a reviewer subagent only; this prints numbers.
Prepare first:  python -I gog_testgame.py --ko build\\gog-ko --ko build\\gog-ko-test --ko build\\gog-art-probe
Usage: python -I gog_art_probe_run.py"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import gamectl  # noqa: E402
import gogenv  # noqa: E402
import hg3  # noqa: E402
import ko_art  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
SHOTS = os.path.join(ROOT, "shots", "gog_art_probe")
BLOCKS = os.path.join(ROOT, "build", "gog-art-probe", "probe_blocks.json")
VK_RETURN = 0x0D
TOP = 470          # compare rows above the message window
LOG = []


def ev(msg):
    line = "%7.1f %s" % (time.time() - T0, msg)
    LOG.append(line)
    print(line, flush=True)


def sig(im):
    return np.asarray(im.convert("L").resize((80, 45)), dtype=np.int16)


def diff(a, b):
    return float(np.abs(a - b).mean())


def shot_ok(g, tries=8):
    im = None
    for _ in range(tries):
        im = g.shot()
        if im is not None and np.asarray(im.convert("L").resize((16, 9))).max() > 8:
            return im
        time.sleep(0.25)
    return im


def bright(im):
    return im is not None and np.asarray(im.convert("L").resize((16, 9))).max() > 8


def wait_stable(g, limit, need=3, step=0.6, want_bright=True):
    prev = None
    n = 0
    t = time.time()
    im = None
    while time.time() - t < limit:
        time.sleep(step)
        im = g.shot()
        if im is None or (want_bright and not bright(im)):
            prev, n = None, 0
            continue
        s = sig(im)
        n = n + 1 if prev is not None and diff(s, prev) < 0.8 else 0
        prev = s
        if n >= need:
            return im, time.time() - t
    return im, None


def expected(entry, x, y, png_by_entry, gog_img):
    def crop(img):
        a = np.asarray(img.convert("RGB"))
        canvas = np.zeros((720, 1280, 3), np.uint8)
        h, w = a.shape[:2]
        sx0, sy0 = max(0, -x), max(0, -y)
        dx0, dy0 = max(0, x), max(0, y)
        cw, ch = min(w - sx0, 1280 - dx0), min(h - sy0, 720 - dy0)
        canvas[dy0:dy0 + ch, dx0:dx0 + cw] = a[sy0:sy0 + ch, sx0:sx0 + cw]
        return canvas
    ko = crop(Image.open(png_by_entry[entry])) if entry in png_by_entry else None
    b = gog_img.read(entry)
    org = crop(hg3.decode(b, hg3.frames(b)[0]))
    return ko, org


def score(screen, ref):
    a = np.asarray(screen.convert("RGB").resize((1280, 720)), dtype=np.int16)[:TOP]
    b = ref.astype(np.int16)[:TOP]
    d = np.abs(a - b).max(axis=2)
    return round(float(d.mean()), 2), round(100.0 * float((d > 32).mean()), 2)


def main():
    global T0
    T0 = time.time()
    if os.path.isdir(SHOTS):
        shutil.rmtree(SHOTS)
    os.makedirs(SHOTS)
    blocks = json.load(open(BLOCKS, encoding="utf-8"))
    png_by_entry = {}
    for r in ko_art.rows_for("gog"):
        if int(r["frame"]) == 0:
            png_by_entry[r["entry"]] = r["png"]
    gog = os.path.join(ROOT, "gog-orig")
    gimg = cs2.Kif(os.path.join(gog, "image.int"), cs2.crc_key(cs2.passphrase(os.path.join(gog, "ISLAND.exe"))))
    f0 = gamectl.gpu_fault_count()
    results = []
    g = None
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            ev("no game window"); return
        ev("game up pid=%d" % g.pid)
        im, _ = wait_stable(g, 120, need=3, step=1.0)
        title = sig(im)
        ev("title stable")
        for attempt in range(3):
            g.move(140, 361); time.sleep(1.2); g.key(VK_RETURN); time.sleep(3.5)
            s = shot_ok(g)
            if s is not None and diff(sig(s), title) > 12:
                break
        ev("new game")
        for b in blocks:
            chk = b["check"]
            kind = chk[0]
            t_click = time.time()
            if kind == "roll":
                caps = []
                t_end = time.time() + 400   # 6700 engine frames; slower if the engine throttles off-screen
                while time.time() < t_end:
                    time.sleep(6)
                    s = g.shot()
                    if s is not None and bright(s):
                        p = os.path.join(SHOTS, "%02d_%s_%03d.png" % (b["n"], b["id"], len(caps)))
                        s.save(p); caps.append(p)
                    # the roll ends with bg40 shown and the marker text: stable bright screen that is not credits
                    if len(caps) >= 3:
                        a1 = sig(Image.open(caps[-1])); a0 = sig(Image.open(caps[-2]))
                        if diff(a1, a0) < 0.8 and time.time() - t_click > 100:
                            break
                im, _ = wait_stable(g, 60)
                results.append({"n": b["n"], "id": b["id"], "kind": kind, "captures": len(caps), "elapsed": round(time.time() - t_click, 1)})
                ev("staff roll: %d captures, %.0f s" % (len(caps), time.time() - t_click))
            elif kind == "movie":
                # black while the movie plays off-screen; bright again when bg14 + marker show
                dur = chk[2]
                seen_black = False
                t_back = None
                while time.time() - t_click < dur + 60:
                    time.sleep(1.0)
                    s = g.shot()
                    if s is None or not bright(s):
                        seen_black = True
                        continue
                    if seen_black and time.time() - t_click > 3:
                        t_back = time.time() - t_click
                        break
                im, _ = wait_stable(g, 30)
                el = round(t_back, 1) if t_back else None
                ok = el is not None and dur - 3 <= el <= dur + 20
                results.append({"n": b["n"], "id": b["id"], "kind": kind, "seconds": el, "movie_len": dur, "black_seen": seen_black, "ok": ok})
                ev("movie %s: back after %s s (length %.0f) ok=%s" % (b["id"], el, dur, ok))
            else:
                im, st = wait_stable(g, 25)
                if im is None:
                    results.append({"n": b["n"], "id": b["id"], "kind": kind, "error": "no stable screen"})
                    ev("%s: no stable screen" % b["id"])
                else:
                    im.save(os.path.join(SHOTS, "%02d_%s.png" % (b["n"], b["id"])))
                    if kind == "frame":
                        ko, org = expected(chk[1], chk[2], chk[3], png_by_entry, gimg)
                        r = {"n": b["n"], "id": b["id"], "kind": kind,
                             "vs_korean": score(im, ko) if ko is not None else None, "vs_gog_original": score(im, org)}
                        r["korean_closer"] = r["vs_korean"] is not None and r["vs_korean"][0] < r["vs_gog_original"][0]
                    else:   # fg effect over bg14: where does the screen differ from plain bg14 Korean?
                        ko, _ = expected("bg14.hg3", 0, 0, png_by_entry, gimg)
                        a = np.asarray(im.convert("RGB").resize((1280, 720)), dtype=np.int16)
                        d = np.abs(a - ko.astype(np.int16)).max(axis=2) > 40
                        d[TOP:] = False
                        ys, xs = np.nonzero(d)
                        r = {"n": b["n"], "id": b["id"], "kind": kind, "changed_px": int(d.sum()),
                             "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None}
                    results.append(r)
                    ev("%s %s" % (b["id"], json.dumps({k: v for k, v in r.items() if k not in ("n", "id", "kind")})))
            g.click(640, 120, hold=0.05, settle=0.1)   # next block
        im, _ = wait_stable(g, 60)
        ev("end of probe")
    finally:
        left = gogenv.finish(g)
        mb = [l for l in gogenv.read_log() if "messagebox" in l]
        ev("exit: left=%s gpu faults %d->%d messageboxes=%d" % (left, f0, gamectl.gpu_fault_count(), len(mb)))
        json.dump({"results": results, "events": LOG}, open(os.path.join(SHOTS, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
