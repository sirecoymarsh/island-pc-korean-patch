"""New sound-tab checkbox "자막 배경" (11-08 user: the black band behind the system-voice captions
should be an option, in the sound tab's empty space).

Frames added to sys_sound.hg3 (the Korean UI image both editions use):
  703 / 713 / 753 / 763  the checkbox in its four states (off, on, focused off, focused on), made from
                         702 / 712 / 752 / 762 ("동영상 스킵"): their box pixels, the label redrawn in the
                         font Codex used for these labels (Malgun Gothic Bold 17 px, fitted on 702)
                         and the template's own text colour; placed right of "시스템 보이스" (x 300)
  1440                   the help line shown at the top while the box is focused, in the style of
                         1405 (Malgun Gothic Bold 14 px, white, 1 px outline 45,49,61)
Writes PNGs to work\\img-ko\\ui and manifest_ui.json rows with "add" (ko_art appends them).
Usage: python -I build_ui_option.py"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import hg3  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
OUT = os.path.join(ROOT, "work", "img-ko", "ui")
MANIFEST = os.path.join(ROOT, "work", "img-ko", "manifest_ui.json")
BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
LABEL = "자막 배경"
HELP = "시스템 보이스 자막의 배경을 설정합니다."
X = 300                      # right of the "시스템 보이스" box (frame 700 at 94..258)
STATES = [(703, 702, 340), (713, 712, 338), (753, 752, 340), (763, 762, 338)]
HELP_ID, HELP_POS = 1440, (251, 42)


def text_colour(a, x0):
    m = a[:, x0:, 3] > 240
    return tuple(int(v) for v in np.median(a[:, x0:][m][:, :3], axis=0))


def main():
    os.makedirs(OUT, exist_ok=True)
    key = cs2.crc_key(cs2.passphrase(os.path.join(ROOT, "steam-orig", "ISLAND.exe")))
    b = cs2.Kif(os.path.join(ROOT, "build", "ko", "image.int"), key).read("sys_sound.hg3")
    fs = {f["id"]: f for f in hg3.frames(b)}
    font = ImageFont.truetype(BOLD, 17)
    rows = []
    boxes = []
    for fid, tid, y in STATES:
        t = np.asarray(hg3.decode(b, fs[tid]).convert("RGBA"))
        col = text_colour(t, 24)
        w = 22 + int(np.ceil(font.getlength(LABEL))) + 4
        im = Image.new("RGBA", (w, t.shape[0]), (0, 0, 0, 0))
        im.paste(Image.fromarray(np.ascontiguousarray(t[:, :22])), (0, 0))
        ImageDraw.Draw(im).text((22, -3 + (1 if t.shape[0] == 22 else 0)), LABEL, font=font, fill=col + (255,))
        p = os.path.join(OUT, "sys_sound_%d.png" % fid)
        im.save(p)
        rows.append({"entry": "sys_sound.hg3", "frame": fid, "edition": "both", "png": p,
                     "add": {"template": tid, "x": X, "y": y}, "method": "label redrawn on the template box"})
        boxes.append((X, y, X + w, y + t.shape[0]))
    hf = ImageFont.truetype(BOLD, 14)
    w = int(np.ceil(hf.getlength(HELP))) + 4
    im = Image.new("RGBA", (w, 17), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-1, -1), HELP, font=hf, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(45, 49, 61, 255))
    p = os.path.join(OUT, "sys_sound_%d.png" % HELP_ID)
    im.save(p)
    rows.append({"entry": "sys_sound.hg3", "frame": HELP_ID, "edition": "both", "png": p,
                 "add": {"template": 1405, "x": HELP_POS[0], "y": HELP_POS[1]}, "method": "help line, style of 1405"})
    # does the new box overlap anything shown on the sound tab?
    x0, y0, x1, y1 = min(b_[0] for b_ in boxes), min(b_[1] for b_ in boxes), max(b_[2] for b_ in boxes), max(b_[3] for b_ in boxes)
    hits = [i for i, f in fs.items() if f["width"] < 1280 and i < 1400 and not (f["x"] + f["width"] <= x0 or f["x"] >= x1 or f["y"] + f["height"] <= y0 or f["y"] >= y1)]
    json.dump(rows, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"rows": len(rows), "checkbox_rect": [x0, y0, x1, y1], "help_width": w, "frames_overlapping_the_box": sorted(hits)}))


if __name__ == "__main__":
    main()
