"""Check the sound-tab "자막 배경" option and the captions on the GOG test copy (off-screen; the test
save is set to mute 0 / master volume 0 for the run so the system voices fire without sound).

title -> settings menu (voice -> caption, band off by default) -> "사운드" bubble -> hover the new box
(help line) -> click it (band on: the click voice's caption) -> click again (band off).
Saves the captures in shots\\gog_sound_option and prints numbers.
Usage: python -I gog_sound_option_test.py"""
import json
import os
import re
import shutil
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots\gog_sound_option"
SETUP = r"Y:\AI\island-steam-ko\gog-testsave\setup.xml"
VK_RETURN = 0x0D
T0 = time.time()


def ev(m):
    print("%7.1f %s" % (time.time() - T0, m), flush=True)


def shot_ok(g, tries=12):
    for _ in range(tries):
        im = g.shot()
        if im is not None and np.asarray(im.convert("L")).max() > 8:
            return im
        time.sleep(0.2)
    return None


def sig(im):
    return np.asarray(im.convert("L").resize((160, 90)), dtype=np.int16)


def wait_stable(g, limit=90):
    prev, k, t = None, 0, time.time()
    while time.time() - t < limit:
        time.sleep(1.0)
        im = shot_ok(g)
        if im is None:
            continue
        s = sig(im)
        k = k + 1 if prev is not None and np.abs(s - prev).mean() < 1.0 else 0
        prev = s
        if k >= 3:
            return im
    return shot_ok(g)


def band(im):
    a = np.asarray(im.convert("RGB"), dtype=np.int16)[630:690, 40:1240]
    return {"band_mean": round(float(a.mean()), 1), "white_px": int((a.min(axis=2) > 200).sum()),
            "dark_px": int((a.max(axis=2) < 70).sum())}


def burst(g, label, seconds=3.0):
    """captures during a voice: the frame with the most white caption pixels is kept"""
    best, t = None, time.time()
    while time.time() - t < seconds:
        im = shot_ok(g, 3)
        if im is not None:
            m = band(im)
            if best is None or m["white_px"] > best[0]["white_px"]:
                best = (m, im)
        time.sleep(0.12)
    if best:
        best[1].save(os.path.join(SHOTS, label + ".png"))
        ev("%-16s %s" % (label, json.dumps(best[0])))
        return best[0]
    return None


def set_sound(mute, vol):
    t = open(SETUP, "rb").read()
    t = re.sub(rb"<mute_master>\d</mute_master>", b"<mute_master>%d</mute_master>" % mute, t)
    t = re.sub(rb"<vol_master>\d+</vol_master>", b"<vol_master>%d</vol_master>" % vol, t)
    open(SETUP, "wb").write(t)


def main():
    if os.path.isdir(SHOTS):
        shutil.rmtree(SHOTS)
    os.makedirs(SHOTS)
    res = {}
    set_sound(0, 0)
    g = None
    f0 = gamectl.gpu_fault_count()
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            ev("no window"); return
        # the title is ready when its bright bottom (band rows ~232) has held for 4 s (logo screens pause too)
        k, t = 0, time.time()
        while time.time() - t < 120 and k < 4:
            time.sleep(1.0)
            im = shot_ok(g)
            k = k + 1 if im is not None and abs(band(im)["band_mean"] - 232) < 12 else 0
        time.sleep(2.0)
        ev("title ready" if k >= 4 else "title not detected")
        g.move(140, 465); time.sleep(1.2); g.click(140, 465, hold=0.1, settle=0.2)
        res["menu_caption_band_off"] = burst(g, "menu_caption_band_off", 3.5)
        if abs(band(shot_ok(g))["band_mean"] - 232) < 12:      # still the title: Enter on the hovered button
            ev("click did not open the menu - Enter")
            g.key(VK_RETURN); res["menu_caption_band_off"] = burst(g, "menu_caption_band_off", 3.5)
        wait_stable(g, 20)
        g.move(755, 235); time.sleep(1.0); g.click(755, 235, hold=0.1, settle=0.2)
        res["sound_open"] = burst(g, "sound_open", 3.0)
        snd = wait_stable(g, 20)
        snd.save(os.path.join(SHOTS, "sound_tab.png"))
        g.move(330, 350); time.sleep(1.5)
        shot_ok(g).save(os.path.join(SHOTS, "sound_tab_hover.png"))
        g.click(330, 350, hold=0.1, settle=0.1)
        res["click_on"] = burst(g, "click_on_band", 3.0)
        shot_ok(g).save(os.path.join(SHOTS, "sound_tab_checked.png"))
        time.sleep(2.0)
        g.click(330, 350, hold=0.1, settle=0.1)
        res["click_off"] = burst(g, "click_off_band", 3.0)
        g.move(640, 200); time.sleep(1.0)
        shot_ok(g).save(os.path.join(SHOTS, "sound_tab_unchecked.png"))
    finally:
        left = gogenv.finish(g)
        set_sound(1, 100)
        ev("exit left=%s gpu faults %d->%d; test save sound restored" % (left, f0, gamectl.gpu_fault_count()))
        json.dump(res, open(os.path.join(SHOTS, "result.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
