"""Flow test on the GOG test copy (gog-test, Korean mode, off-screen test mode, no Steam):
title -> new game -> advance through dialogue -> first choice (com01_selA):
  quick save -> pick 2nd choice -> advance -> quick load (confirm Yes) -> back at the choice?
  -> normal exit (no ending run - the user asked to leave endings out on Steam too).
Story screenshots are kept on disk for a separate reviewer only; this script prints events
and numbers, never text. Usage: python -I gog_flowtest.py [--to-title]"""
import json
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import gogenv  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
SHOTS = os.path.join(ROOT, "shots", "gog_flow")
SAVE = os.path.join(ROOT, "gog-testsave")
VK_CONTROL, VK_RETURN = 0x11, 0x0D
QSAVE, QLOAD = (1220, 674), (1220, 700)
YES = (547, 349)
CHOICE2 = [(669, 266), (669, 386)]
CHOICE3 = [(669, 206), (669, 326), (669, 446)]
LOG = []


def ev(msg):
    line = "%7.1f %s" % (time.time() - T0, msg)
    LOG.append(line)
    print(line, flush=True)


def sig(im):
    return im.resize((80, 45)).convert("L").tobytes()


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def row_light(im, y):
    px = [im.getpixel((x, y)) for x in range(330, 396, 2)]
    # normal frame left margin is white, the hover frame pink (g down to ~168), both ~90 % opaque
    return sum(1 for r, g, b in px if r > 185 and g > 140 and b > 190 and abs(r - b) < 75) / len(px)


def bands(im):
    """Choice buttons: light bands about 51 px high in x 330..395, y 120..640."""
    im = im.convert("RGB")
    out = []; cur = None
    for y in range(120, 640):
        ok = row_light(im, y) > 0.8
        if ok and cur is None:
            cur = y
        if not ok and cur is not None:
            if 40 <= y - cur <= 60:
                out.append((cur, y - 1))
            cur = None
    return out


def choice_layout(im):
    b = bands(im)
    if 2 <= len(b) <= 6 and all(abs((b[i + 1][0] - b[i][0]) - (b[1][0] - b[0][0])) <= 3 for i in range(len(b) - 1)):
        return [(669, (t + e) // 2) for t, e in b]
    return None


DIALOG_PNG = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\localization\ja\ui_source\sys_dialog\0000.png"
_DLG = None


def dialog_shown(im):
    """The in-game confirm dialog (sys_dialog frame 0 drawn at 429,234)."""
    global _DLG
    from PIL import Image
    if _DLG is None:
        _DLG = Image.open(DIALOG_PNG).convert("RGB").resize((99, 57)).tobytes()
    reg = im.convert("RGB").crop((429, 234, 826, 463)).resize((99, 57)).tobytes()
    return sum(abs(a - b) for a, b in zip(reg, _DLG)) / len(reg) < 30


def shot_ok(g, tries=8):
    """PrintWindow sometimes returns an all-black frame for the off-screen window: retry."""
    im = None
    for _ in range(tries):
        im = g.shot()
        if im is not None and max(im.convert("L").resize((16, 9)).tobytes()) > 8:
            return im
        time.sleep(0.25)
    return im


def hovered(im, cx, cy):
    r, g, b = im.convert("RGB").getpixel((cx - 330, cy))
    return r > 235 and g < 236 and b > 225  # pink hover frame


def pick(g, lay, idx):
    """Move onto the button, confirm the hover state, click, confirm the choice screen left."""
    cx, cy = lay[idx]
    for attempt in range(4):
        g.move(cx, cy)
        time.sleep(0.7)
        im = shot_ok(g)
        hv = im is not None and hovered(im, cx, cy)
        if attempt < 2:
            g.click(cx, cy, hold=0.15, settle=0.2)
        else:
            g.key(VK_RETURN)   # the hovered choice takes Enter
        time.sleep(2.5)
        im = shot_ok(g)
        if im is not None and not choice_layout(im) and not dialog_shown(im):
            ev("picked option %d (hover seen=%s, attempt %d)" % (idx + 1, hv, attempt + 1))
            return True
    ev("could not pick option %d" % (idx + 1))
    return False


def save_files():
    out = {}
    for r, d, fs in os.walk(SAVE):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, SAVE)] = (os.path.getsize(p), os.path.getmtime(p))
    return out


def main():
    global T0
    T0 = time.time()
    if os.path.isdir(SHOTS):
        shutil.rmtree(SHOTS)
    os.makedirs(SHOTS)
    f0 = gamectl.gpu_fault_count()
    g = None
    result = {"title": False, "new_game": False, "choice_seen": 0, "quick_save_file": False, "quick_load_back": None,
              "ending_to_title": False, "normal_exit": False}
    try:
        g = gogenv.start()
        if not g or not g.hwnd:
            ev("no game window"); return
        ev("game up pid=%d" % g.pid)
        # title
        prev = None; stable = 0
        while time.time() - T0 < 120:
            time.sleep(1)
            im = g.shot()
            if im is None:
                continue
            s = sig(im)
            stable = stable + 1 if prev is not None and diff(s, prev) < 1.5 else 0
            prev = s
            if stable >= 3 and im.convert("L").resize((1, 1)).getpixel((0, 0)) > 120:
                break
        im.save(os.path.join(SHOTS, "title.png"))
        title_sig = sig(im)
        result["title"] = True
        ev("title stable")
        # GOG title buttons: a posted click does not always land and the hover glow alone changes
        # the screen; Enter on the hovered button does land. The first scene is dark, the title
        # bright - judge by that, not by "the screen changed".
        def title_like(im):
            return im is not None and im.convert("L").resize((1, 1)).getpixel((0, 0)) > 110 and diff(sig(im), title_sig) < 12
        for attempt in range(3):
            g.move(140, 361)
            time.sleep(1.2)
            g.key(VK_RETURN)
            time.sleep(3.5)
            if not title_like(shot_ok(g)):
                break
            ev("still at the title after Enter (attempt %d) - trying a click" % (attempt + 1))
            g.click(140, 361, hold=0.1, settle=0.3)
            time.sleep(3.5)
            if not title_like(shot_ok(g)):
                break
        result["new_game"] = not title_like(shot_ok(g))
        ev("new game started=%s" % result["new_game"])
        if not result["new_game"]:
            return
        phase = "to_choice"
        prev = None; stable = 0; n = 0; last_progress = time.time(); shots = 0
        after_load_wait = None
        deadline = time.time() + 30 * 60
        choice_sig = None
        while time.time() < deadline:
            # advance: click in the upper area (never on choice buttons)
            g.click(640, 120, hold=0.03, settle=0.03)
            time.sleep(0.12)
            n += 1
            if n % 4:
                continue
            im = g.shot()
            if im is None:
                continue
            s = sig(im)
            if prev is not None and diff(s, prev) < 1.0:
                stable += 1
            else:
                stable = 0; last_progress = time.time()
            prev = s
            if n % 200 == 0 and shots < 40:
                im.save(os.path.join(SHOTS, "run_%03d.png" % shots)); shots += 1
            # title again?
            if phase == "to_title" and diff(s, title_sig) < 4:
                result["ending_to_title"] = True
                im.save(os.path.join(SHOTS, "title_after_ending.png"))
                ev("back at title after the ending")
                break
            if phase == "to_choice" and title_like(im) and stable >= 2:
                restarts = locals().get("restarts", 0) + 1
                ev("unexpected title before the choice (restart %d)" % restarts)
                if restarts > 1:
                    break
                g.move(140, 361); time.sleep(1.2); g.key(VK_RETURN); time.sleep(3)
                if diff(sig(g.shot()), title_sig) < 3:
                    g.key(VK_RETURN); time.sleep(3)
                continue
            lay = choice_layout(im) if stable >= 2 else None
            if lay and phase == "to_choice":
                result["choice_seen"] += 1
                time.sleep(1.0)
                im = g.shot(); im.save(os.path.join(SHOTS, "choice_first.png"))
                choice_sig = sig(im)
                ev("choice screen, %d options" % len(lay))
                before = save_files()
                g.click(*QSAVE)
                time.sleep(1.5)
                im = shot_ok(g)
                if im is not None and dialog_shown(im):
                    im.save(os.path.join(SHOTS, "qsave_dialog.png"))
                    ev("quick save asked for confirmation - Yes")
                    g.click(*YES)
                time.sleep(2.0)
                im = shot_ok(g)
                if im is not None and dialog_shown(im):
                    ev("a dialog is still open after quick save - Yes")
                    g.click(*YES)
                    time.sleep(1.5)
                after = save_files()
                changed = [k for k in after if before.get(k) != after[k]]
                result["quick_save_file"] = bool(changed)
                ev("quick save: changed save files=%d" % len(changed))
                g.shot(os.path.join(SHOTS, "after_qsave.png"))
                pick(g, lay, 1)
                phase = "after_pick"
                pick_time = time.time()
                continue
            if phase == "after_pick" and time.time() - pick_time > 12:
                g.click(*QLOAD)
                time.sleep(2.0)
                im = shot_ok(g)
                im.save(os.path.join(SHOTS, "qload_dialog.png"))
                ev("quick load dialog shown=%s" % dialog_shown(im))
                g.click(*YES)
                time.sleep(5.0)
                im = shot_ok(g)
                im.save(os.path.join(SHOTS, "after_qload.png"))
                d = diff(sig(im), choice_sig)
                lay2 = choice_layout(im)
                result["quick_load_back"] = bool(lay2) and d < 6
                ev("quick load: choice layout=%s diff_to_saved_choice=%.1f" % (bool(lay2), d))
                if "--to-title" not in sys.argv:
                    break
                if lay2:
                    pick(g, lay2, 1)
                phase = "to_title"
                continue
            if stable >= 25 and time.time() - last_progress > 20:
                b = bands(im)
                im.save(os.path.join(SHOTS, "stuck_%d.png" % int(time.time() - T0)))
                ev("no progress for 20s (phase %s), light bands=%s - pressing Enter" % (phase, b))
                g.key(VK_RETURN); stable = 0; last_progress = time.time()
        log = gogenv.read_log()
        ev("dll log lines=%d messageboxes=%d" % (len(log), sum("messagebox" in l for l in log)))
    finally:
        left = gogenv.finish(g)
        result["normal_exit"] = not left
        mb = [l for l in gogenv.read_log() if "messagebox" in l]
        ev("exit: left=%s gpu faults %d->%d last messagebox=%s" % (left, f0, gamectl.gpu_fault_count(), mb[-1][:120] if mb else None))
        json.dump({"result": result, "events": LOG}, open(os.path.join(SHOTS, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
