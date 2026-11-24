"""System-voice caption check on the GOG test copy (off-screen, muted): title -> hover each title
button -> settings -> click each bottom tab; after every action a burst of captures, and in each the
caption band (Codex's ko_cap_bg: x 32..1248, y 624..696) is measured: band shown? white text
pixels inside it? Prints numbers only (caption wording is never printed); frames with a band are
kept in shots\\gog_caption for a reviewer.
Usage: python -I gog_caption_test.py [tag]"""
import json
import os
import shutil
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

TAG = next((a for a in sys.argv[1:] if not a.startswith("--")), "run")
SHOTS = os.path.join(r"Y:\AI\island-steam-ko\shots", "gog_caption_" + TAG)
VK_RETURN = 0x0D
T0 = time.time()


def ev(m):
    print("%7.1f %s" % (time.time() - T0, m), flush=True)


def measure(im):
    a = np.asarray(im.convert("RGB").resize((1280, 720)), dtype=np.int16)
    if a.max() < 8:
        return None                      # PrintWindow sometimes returns an all-black frame
    band = a[630:690, 40:1240]
    return {"band_mean": float(band.mean()), "white_px": int((band.min(axis=2) > 200).sum())}


def burst(g, label, seconds=3.0, step=0.15):
    """band shown = the band rows get much darker than in the brightest frame of the burst"""
    frames = []
    t = time.time()
    while time.time() - t < seconds:
        im = g.shot()
        m = measure(im) if im is not None else None
        if m:
            frames.append((m, im))
        time.sleep(step)
    if not frames:
        ev("%-14s no usable frames" % label)
        return None
    hi = max(m["band_mean"] for m, _ in frames)
    dark = [(m, im) for m, im in frames if m["band_mean"] < 0.7 * hi]
    r = {"frames": len(frames), "band_frames": len(dark), "band_mean_min": round(min(m["band_mean"] for m, _ in frames), 1),
         "band_mean_max": round(hi, 1), "white_px_in_band_frames": max([m["white_px"] for m, _ in dark], default=0),
         "white_px_no_band": max([m["white_px"] for m, _ in frames if m["band_mean"] >= 0.7 * hi], default=0)}
    if dark:
        m, im = max(dark, key=lambda x: x[0]["white_px"])
        im.save(os.path.join(SHOTS, "%s.png" % label))
    ev("%-14s %s" % (label, json.dumps(r)))
    return r


def shot_ok(g, tries=10):
    im = None
    for _ in range(tries):
        im = g.shot()
        if im is not None and np.asarray(im.convert("L")).max() > 8:
            return im
        time.sleep(0.2)
    return im


def sig(im):
    return np.asarray(im.convert("L").resize((320, 180)), dtype=np.int16)


def changed(g, ref, thr=6.0):
    """the content area (above the tab bar) differs from ref"""
    s = sig(shot_ok(g))
    return float(np.abs(s[20:150] - ref[20:150]).mean()) > thr


def wait_stable(g, limit=60):
    prev = None
    k = 0
    t = time.time()
    while time.time() - t < limit:
        time.sleep(1.0)
        im = shot_ok(g)                  # skip PrintWindow's all-black frames
        if im is None or np.asarray(im.convert("L")).max() <= 8:
            continue
        s = np.asarray(im.convert("L").resize((80, 45)), dtype=np.int16)
        k = k + 1 if prev is not None and np.abs(s - prev).mean() < 1.5 else 0
        prev = s
        if k >= 3 and s.mean() > 60:
            return im
    return None


def main():
    if os.path.isdir(SHOTS):
        shutil.rmtree(SHOTS)
    os.makedirs(SHOTS)
    res = {}
    g = None
    f0 = gamectl.gpu_fault_count()
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            ev("no window"); return
        ev("game up")
        res["title_start"] = burst(g, "title_start", 8.0)
        title = wait_stable(g, 90) or shot_ok(g)   # the title takes input only once its intro has settled
        tsig = sig(title)
        for y in (308, 361, 413, 465, 520):
            g.move(140, y)
            res["hover_%d" % y] = burst(g, "hover_%d" % y, 2.5)
        opened = False
        for attempt in range(3):                   # settings: hover, click; Enter if the click did not land
            g.move(140, 465); time.sleep(1.2)
            g.click(140, 465, hold=0.1, settle=0.3)
            res["settings_open_%d" % attempt] = burst(g, "settings_open", 3.0)
            if changed(g, tsig):
                opened = True; break
            g.key(VK_RETURN)
            res["settings_enter_%d" % attempt] = burst(g, "settings_enter", 3.0)
            if changed(g, tsig):
                opened = True; break
        ev("settings opened: %s" % opened)
        if "--quick" in sys.argv:
            return
        wait_stable(g, 20)
        for i, x in enumerate((80, 162, 244, 326, 408, 490, 80)):
            before = sig(shot_ok(g))
            g.move(x, 646); time.sleep(0.6)
            g.click(x, 646, hold=0.08, settle=0.05)
            r = burst(g, "tab_%d" % i, 2.5)
            sw = changed(g, before)
            if not sw:
                g.key(VK_RETURN)
                r = burst(g, "tab_%d_enter" % i, 2.5)
                sw = changed(g, before)
            if r is not None:
                r["switched"] = sw
            res["tab_%d" % i] = r
            ev("tab %d switched: %s" % (i, sw))
        g.rclick(); time.sleep(2.0)
    finally:
        left = gogenv.finish(g)
        ev("exit left=%s gpu faults %d->%d" % (left, f0, gamectl.gpu_fault_count()))
        json.dump(res, open(os.path.join(SHOTS, "result.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
