"""검수 보기 option on the GOG test copy (off-screen; the test save has no story progress).
title -> settings -> 「확인 창」 tab: the two new rows -> 「모든 콘텐츠 열어 보기」 -> warning dialog -> 예
-> back to the title (the extras button must now show) -> extras: the six tabs and one CG opened
large -> settings -> 「플로차트」 -> 「처음 상태로 보기」 (exclusive) -> title / flowchart -> off again.
savegen.dat (the global records) is compared before and after: only the patch's own variables
may change. Captures in shots\\gog_qa_view (UI screens only), numbers printed.
Usage: python -I gog_qa_view_test.py"""
import os
import shutil
import struct
import sys
import time
import zlib

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

SHOTS = r"Y:\AI\island-steam-ko\shots\gog_qa_view"
SAVE = r"Y:\AI\island-steam-ko\gog-testsave"
VK_RETURN = 0x0D
T0 = time.time()
TITLE_CONFIG, TITLE_OMAKE = (177, 466), (177, 519)
BUBBLE_DIALOG, BUBBLE_FLOW = (222, 428), (862, 428)
ROW_OPEN, ROW_FRESH = (820, 478), (820, 560)
DIALOG_YES = (547, 349)
OMAKE_CG = (180, 362)
TABS = [(100, 134), (100, 217), (100, 300), (100, 383), (100, 466), (100, 549)]
THUMB0 = (322, 181)
PHASE = sys.argv[1] if len(sys.argv) > 1 else "all"      # all | open | fresh


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


def stable(g, limit=12):
    """a capture once the screen holds still; PrintWindow sometimes gives black frames for a while,
    so the last good capture (or a longer wait for one) is returned, never None"""
    prev, k, t = None, 0, time.time()
    last = None
    while time.time() - t < limit:
        time.sleep(0.5)
        im = shot_ok(g)
        if im is None:
            continue
        last = im
        s = sig(im)
        k = k + 1 if prev is not None and np.abs(s - prev).mean() < 0.8 else 0
        prev = s
        if k >= 2:
            return im
    if last is None:
        last = shot_ok(g, 100)
    if last is None:
        raise SystemExit("no capture (black frames for 20 s)")
    return last


def snap(g, name):
    im = stable(g)
    im.save(os.path.join(SHOTS, name + ".png"))
    ev("snap " + name)
    return im


def press(g, xy, settle=1.2):
    """hover, click; Enter on the hovered element when the click changed nothing"""
    g.move(*xy)
    time.sleep(settle)
    before = sig(stable(g, 4))
    g.click(xy[0], xy[1], hold=0.1, settle=0.2)
    time.sleep(1.8)
    after = sig(stable(g, 8))
    if np.abs(after - before).mean() < 2.0:
        g.key(VK_RETURN)
        time.sleep(1.8)
        stable(g, 8)
        return "enter"
    return "click"


def hover_enter(g, xy, settle=1.2):
    g.move(*xy)
    time.sleep(settle)
    g.key(VK_RETURN)
    time.sleep(2.0)


def back(g):
    g.rclick()
    time.sleep(2.0)
    stable(g, 8)


def quick(g, name):
    """capture now (no waiting for stillness); black frames are kept as they are"""
    im = g.shot()
    if im is not None:
        im.save(os.path.join(SHOTS, name + ".png"))
        ev("quick %s mean %.1f" % (name, float(np.asarray(im.convert("L")).mean())))
    else:
        ev("quick %s: no capture" % name)


def open_tab(g, bubble):
    """title -> settings menu -> a tab; the title's hover animation fools a click check, so Enter on
    the hovered button everywhere (GOG title buttons do not always take a posted click)"""
    hover_enter(g, TITLE_CONFIG)
    stable(g, 6)
    hover_enter(g, bubble)
    stable(g, 6)


def savegen():
    b = open(os.path.join(SAVE, "savegen.dat"), "rb").read()
    return zlib.decompress(b[16:])


def main():
    if os.path.isdir(SHOTS):
        shutil.rmtree(SHOTS)
    os.makedirs(SHOTS)
    before = savegen()
    g = None
    f0 = gamectl.gpu_fault_count()
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            ev("no window"); return
        k, t = 0, time.time()
        while time.time() - t < 120 and k < 4:
            time.sleep(1.0)
            im = shot_ok(g)
            a = np.asarray(im.convert("RGB"), dtype=np.int16)[630:690, 40:1240] if im is not None else None
            k = k + 1 if a is not None and abs(float(a.mean()) - 232) < 12 else 0
        time.sleep(2.0)
        ev("title ready" if k >= 4 else "title not detected")
        snap(g, "01_title_real")
        if PHASE in ("all", "open"):
            open_tab(g, BUBBLE_DIALOG); snap(g, "03_dialogtab")
            g.move(*ROW_OPEN); time.sleep(1.2); snap(g, "04_row_open_hover")
            g.key(VK_RETURN); time.sleep(2.5); snap(g, "05_warning")
            hover_enter(g, DIALOG_YES); snap(g, "06_open_on")
            back(g); back(g); snap(g, "07_title_open")
            hover_enter(g, TITLE_OMAKE); snap(g, "08_omake_menu")
            hover_enter(g, OMAKE_CG); snap(g, "09_tab0")
            for i, xy in enumerate(TABS[1:], 1):
                hover_enter(g, xy); snap(g, "%02d_tab%d" % (9 + i, i))
            hover_enter(g, TABS[0]); snap(g, "15_tab0_again")
            hover_enter(g, THUMB0); snap(g, "16_cgview")
            back(g); snap(g, "17_after_cgview")
            back(g); snap(g, "18_title")
            open_tab(g, BUBBLE_FLOW); snap(g, "19_flow_open")
            back(g); back(g); snap(g, "19b_title")
        if PHASE in ("all", "fresh"):
            open_tab(g, BUBBLE_DIALOG); quick(g, "20a_tab")
            g.move(*ROW_FRESH); time.sleep(1.2); quick(g, "20b_hover")
            g.key(VK_RETURN)
            for k in range(6):
                time.sleep(0.5); quick(g, "20c_after_enter_%d" % k)
            snap(g, "20d_fresh_on")
            back(g); back(g); snap(g, "21_title_fresh")
            hover_enter(g, TITLE_OMAKE); quick(g, "21b_omake_try")
            stable(g, 6)
            open_tab(g, BUBBLE_FLOW); snap(g, "22_flow_fresh")
            back(g); hover_enter(g, BUBBLE_DIALOG); stable(g, 6)
            g.move(*ROW_FRESH); time.sleep(1.2); g.key(VK_RETURN); time.sleep(2.0); snap(g, "23_all_off")
            back(g); back(g); snap(g, "24_title_real_again")
    finally:
        left = gogenv.finish(g)
        ev("exit left=%s gpu faults %d->%d" % (left, f0, gamectl.gpu_fault_count()))
        for p in left:                      # only the game this test started, never another instance
            if g is not None and p == g.pid:
                os.system("taskkill /PID %d /F >nul 2>nul" % p)
                ev("test game %d did not exit - stopped" % p)
        log = gogenv.read_log()
        ev("log: %s" % [x[:120] for x in log[:1]])
    after = savegen()
    n = min(len(before), len(after))
    diff = [i for i in range(0, n - 3, 4) if before[i:i + 4] != after[i:i + 4]]
    ev("savegen %d -> %d bytes, changed dwords: %d at %s" % (len(before), len(after), len(diff), [hex(i) for i in diff[:40]]))
    for i in diff[:40]:
        ev("   %06x  %d -> %d" % (i, struct.unpack_from("<i", before, i)[0], struct.unpack_from("<i", after, i)[0]))


if __name__ == "__main__":
    main()
