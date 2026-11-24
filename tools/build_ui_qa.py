"""검수 보기 option (11-08 user: unlock-all / relock / reset "가능하면 옵션에 넣어서 자연스런 게임 옵션의 하나로
보이도록"), as two more rows of the 「확인 창」 settings tab (its right column has room for two rows below
「게임 종료 확인」), plus the warning dialog shown before everything is opened.

Frames added (both editions' Korean UI images carry identical templates):
  sys_dialogconf.hg3  211 231 261 281   「모든 콘텐츠 열어 보기」 (off, on, focused off, focused on)
                      212 232 262 282   「처음 상태로 보기」
                      made from 210 230 260 280 (「게임 종료 확인」): its box and underline pixels kept, the
                      label redrawn (Malgun Gothic Bold 19 px, nearest to Codex's labels) in the template's
                      own colour for that state; placed 82 / 164 px below it, the column's row step
  sys_dialog.hg3      24                the warning before 「모든 콘텐츠 열어 보기」 (dialog number 14 ->
                      frame 14+10), two lines, Noto Sans KR Bold 17 px, near-black with the white
                      outline the other messages (10..22) have
Writes PNGs to work\\img-ko\\ui and manifest_qa.json ("add" rows; ko_art appends them), and previews
of the tab and the dialog to work\\img-ko\\ui\\preview_*.png.
Usage: python -I build_ui_qa.py"""
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
MANIFEST = os.path.join(ROOT, "work", "img-ko", "manifest_qa.json")
BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
NOTO = os.path.join(ROOT, "fontsrc", "NotoSansKR-VF.ttf")
# 11-09: row 12 is a real reset now (user: 「저 기능은 게임의 상태를 설치 초기로 돌리는거야」), not a view
ROWS = [("모든 콘텐츠 열어 보기", 1, 82), ("처음 상태로 되돌리기", 2, 164)]   # label, frame offset, y step
TEMPLATES = [210, 230, 260, 280]          # off, on, focused off, focused on of 「게임 종료 확인」
WARN_ID, WARN_POS = 24, (16, 10)
WARN_LINES = ["아직 보지 않은 장면·CG·결말도 보입니다.", "모든 콘텐츠를 열어 볼까요?"]
# 11-09 「처음 상태로 되돌리기」 (a real reset at the next start, with an undo): the question before each way -
# dialog 15 -> frame 25 (reset), dialog 16 -> frame 26 (back to the kept records)
FRESH_ID = 25
FRESH_LINES = ["지금 기록을 보관하고 설치 직후 상태로 되돌립니다.", "세이브와 설정은 그대로입니다.", "게임을 끝낼까요? 다시 켜면 적용됩니다."]
RESTORE_ID = 26
RESTORE_LINES = ["보관해 둔 기록으로 되돌립니다.", "처음 상태로 한 뒤의 기록도 따로 보관합니다.", "게임을 끝낼까요? 다시 켜면 적용됩니다."]


def label_geometry(a):
    """unchecked template: (x where the label starts, top row of its glyphs); the box ends before x 27"""
    al = a[:, :, 3]
    body = al[:a.shape[0] - 3]                  # the last two rows are the full-width underline
    cols = np.where((body[:, 27:] > 128).any(axis=0))[0]
    x0 = int(cols.min()) + 27
    rows = np.where((body[:, x0:] > 128).any(axis=1))[0]
    return x0, int(rows.min())


def draw_label(t, label, font, x0, top):
    """t: a state frame of the template row; x0/top in that frame's own coordinates"""
    a = np.asarray(t).copy()
    stop = a.shape[0] - 3
    al = a[:, :, 3]
    core = a[:stop, x0:][al[:stop, x0:] > 250][:, :3]
    col = tuple(int(v) for v in np.median(core, axis=0))
    a[:stop, x0 - 2:, 3] = 0                     # clear the old label (box and underline stay)
    im = Image.fromarray(a)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0, 0), label, font=font)
    d.text((x0 - bb[0], top - bb[1]), label, font=font, fill=col + (255,))
    im.alpha_composite(layer)
    return im, x0 + bb[2] - bb[0], col


def main():
    os.makedirs(OUT, exist_ok=True)
    # the base the art step adds to: Codex's Korean UI images (both editions take theirs), not a built archive
    # that already carries these frames
    from build_image import CDX
    key = cs2.crc_key(cs2.passphrase(os.path.join(ROOT, "steam-orig", "ISLAND.exe")))
    k = cs2.Kif(CDX, key)
    b = k.read("sys_dialogconf.hg3")
    fs = {f["id"]: f for f in hg3.frames(b)}
    font = ImageFont.truetype(BOLD, 19)
    rows, report = [], {}
    preview = hg3.decode(b, fs[0]).convert("RGBA")
    base = fs[TEMPLATES[0]]
    x0, top0 = label_geometry(np.asarray(hg3.decode(b, base).convert("RGBA")))
    for label, off, step in ROWS:
        for tid in TEMPLATES:
            fid = tid + off
            assert fid not in fs, fid
            t = hg3.decode(b, fs[tid]).convert("RGBA")
            im, width, col = draw_label(t, label, font, x0 + base["x"] - fs[tid]["x"], top0 + base["y"] - fs[tid]["y"])
            assert width < 420, (label, width)
            p = os.path.join(OUT, "sys_dialogconf_%d.png" % fid)
            im.save(p)
            x, y = fs[tid]["x"], fs[tid]["y"] + step
            rows.append({"entry": "sys_dialogconf.hg3", "frame": fid, "edition": "both", "png": p,
                         "add": {"template": tid, "x": x, "y": y}, "method": "label redrawn on the template row"})
            report["%d" % fid] = {"pos": [x, y], "label_width": width, "colour": col}
            if tid == (210 if off == 1 else 230):  # preview: row 12 unchecked, row 13 checked
                preview.alpha_composite(im, (x, y))
    for fid in range(200, 211):
        preview.alpha_composite(hg3.decode(b, fs[fid]).convert("RGBA"), (fs[fid]["x"], fs[fid]["y"]))
    preview.convert("RGB").save(os.path.join(OUT, "preview_dialogconf.png"))
    # the warning messages
    b2 = k.read("sys_dialog.hg3")
    fs2 = {f["id"]: f for f in hg3.frames(b2)}
    nf = ImageFont.truetype(NOTO, 17)
    nf.set_variation_by_axes([700])
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    buttons_top = min(fs2[fid]["y"] for fid in (100, 101))
    for fid_msg, lines in ((WARN_ID, WARN_LINES), (FRESH_ID, FRESH_LINES), (RESTORE_ID, RESTORE_LINES)):
        assert fid_msg not in fs2
        widths = [probe.textbbox((0, 0), s, font=nf, stroke_width=1)[2] for s in lines]
        w, h = max(widths) + 6, 2 + 25 * len(lines)
        assert WARN_POS[0] + w <= 397 - 8, (fid_msg, widths)
        assert WARN_POS[1] + h <= buttons_top - 4, (fid_msg, h, buttons_top)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, s in enumerate(lines):
            d.text((2, 1 + 25 * i), s, font=nf, fill=(24, 24, 24, 255), stroke_width=1, stroke_fill=(255, 255, 255, 255))
        p = os.path.join(OUT, "sys_dialog_%d.png" % fid_msg)
        im.save(p)
        rows.append({"entry": "sys_dialog.hg3", "frame": fid_msg, "edition": "both", "png": p,
                     "add": {"template": 22, "x": WARN_POS[0], "y": WARN_POS[1]}, "method": "warning message, style of 10..22"})
        report["dialog_%d" % fid_msg] = {"widths": widths, "size": [w, h], "buttons_top": buttons_top}
        box = hg3.decode(b2, fs2[0]).convert("RGBA")
        for fid in (100, 101):
            box.alpha_composite(hg3.decode(b2, fs2[fid]).convert("RGBA"), (fs2[fid]["x"], fs2[fid]["y"]))
        box.alpha_composite(im, WARN_POS)
        box.convert("RGB").save(os.path.join(OUT, "preview_dialog%d.png" % fid_msg))
    json.dump(rows, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"rows": len(rows), "frames": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
