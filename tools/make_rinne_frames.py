"""The coloured 「린」「네」 userfont frames for the 凛音/リンネ distinction (user decision 「색으로 구분」, 11-08).

The engine draws a userfont image by scaling its 32x32 canvas to the current text size (choice 24, ADV window /
backlog / name label 26, novel and full windows 28, ruby 10 - measured 11-08 on the GOG copy with a solid box and a
1-px frame) and puts its own outline + drop shadow around the image's alpha, exactly as for text. So a frame is the
glyph fill only, drawn like a 32-px character of the patch font: PIL size 32 at (+1, -1) in the canvas (best match
to the engine's own 26-px 「린네」 on the GOG copy: candidates size 31/32/33 and offsets -1..+1 compared side by side).

  frames 20, 21 #a0c8e8  choices (select.fes, novelselect.fes) - the user's pick on the PC choice screen; #a0d8f0
                         would be nearly the hovered option's colour 176,226,255
  frames 22, 23 #a0d8f0  message windows, name labels, backlog - the Switch colour
  frames 24, 25 #3c8cc8  the save/load panel: black text, no outline, light panel - #a0d8f0 was ~1.2:1 there

-> Y:\\AI\\island-steam-ko\\work\\img-ko\\rinne\\userfont_<frame>.png + work\\img-ko\\manifest_rinne.json (read by ko_art.py
for both editions). Usage: python -I make_rinne_frames.py"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kocodec import Codec  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
IMG_KO = os.path.join(ROOT, "work", "img-ko")
OUT = os.path.join(IMG_KO, "rinne")
FONT = os.path.join(ROOT, "build", "gog-ko", "ISLAND-KO.ttf")
PUA = os.path.join(os.path.dirname(HERE), "data", "pua_table.json")
SIZE, DX, DY = 32, 1, -1
FRAMES = [(20, "린", "a0c8e8", "choices"), (21, "네", "a0c8e8", "choices")]
# (11-08 evening: the message windows, backlog and save panel moved to emphasis dots - frames 22-25 dropped;
#  choices cannot take a ruby on the PC engine, so they keep the colour)


def draw(ch, colour, codec):
    donor = {real: slot for slot, real in codec.slot_chars().items()}[ch]
    fill = tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))
    im = Image.new("RGBA", (32, 32), fill + (0,))
    ImageDraw.Draw(im).text((DX, DY), donor, font=ImageFont.truetype(FONT, SIZE), fill=fill + (255,))
    a = np.asarray(im)[:, :, 3]
    ys, xs = np.nonzero(a)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    if box[0] == 0 or box[1] == 0 or box[2] == 32 or box[3] == 32:
        raise SystemExit("%s touches the canvas edge: %s" % (ch, box))
    return im.crop(box), box


def main():
    codec = Codec.load(PUA)
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for frame, ch, colour, where in FRAMES:
        im, box = draw(ch, colour, codec)
        png = os.path.join(OUT, "userfont_%d.png" % frame)
        im.save(png)
        rows.append({"entry": "userfont.hg3", "frame": frame, "edition": "both", "png": png,
                     "add": {"template": 2, "x": box[0], "y": box[1]},
                     "method": "凛音/リンネ colour (user 「색으로 구분」 11-08): the リンネ 「린네」 in %s; fill #%s only, patch font at %d px "
                               "at (%+d,%+d) on the 32x32 canvas - the engine scales it to the text size and adds outline + shadow" % (where, colour, SIZE, DX, DY),
                     "checks": {"size": list(im.size)}})
        print("frame %d: #%s %dx%d at %d,%d" % (frame, colour, im.width, im.height, box[0], box[1]))
    json.dump(rows, open(os.path.join(IMG_KO, "manifest_rinne.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    old = os.path.join(IMG_KO, "manifest_choice.json")       # 1.3.2 first cut (frames 8, 9 with their own outline)
    if os.path.exists(old):
        os.makedirs(os.path.join(IMG_KO, "old"), exist_ok=True)
        shutil.move(old, os.path.join(IMG_KO, "old", "manifest_choice.json"))
        print("moved the old choice manifest to work\\img-ko\\old")


if __name__ == "__main__":
    main()
