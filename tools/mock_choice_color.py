"""Mock-up of the first 「린네 / 린네」 choice on the Steam choice screen (synthetic: real button
images, patch font, engine colours). A: as on Switch (2nd 린네 light blue a0d8f0), B: same while the
mouse is on the 1st choice (engine hover = pink button + text 176,226,255)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BTN = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\localization\ja\ui_source\sys_select"
FONT = r"Y:\AI\island-steam-ko\build\ko\ISLAND-KO.ttf"
OUT = r"Y:\AI\island-steam-ko\shots\choice_color_mock.png"


def text(img, xy, s, fill, size=24):
    f = ImageFont.truetype(FONT, size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = xy
    for dx in (-1, 0, 1):          # engine: outline around + shadow right-down
        for dy in (-1, 0, 1):
            d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0, 255))
    d.text((x + 2, y + 2), s, font=f, fill=(0, 0, 0, 200))
    d.text((x, y), s, font=f, fill=fill)
    img.alpha_composite(layer)


def screen(hover_first, label):
    img = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    g = ImageDraw.Draw(img)
    for y in range(720):  # neutral evening-sky gradient instead of a story scene
        g.line([(0, y), (1280, y)], fill=(40 + y // 12, 70 + y // 10, 110 + y // 9, 255))
    normal = Image.open(BTN + r"\0000.png").convert("RGBA")
    hover = Image.open(BTN + r"\0002.png").convert("RGBA")
    for i, (bg, col) in enumerate([(hover if hover_first else normal, (176, 226, 255, 255) if hover_first else (255, 255, 255, 255)),
                                   (normal, (160, 216, 240, 255))]):
        y = 240 + 120 * i
        img.alpha_composite(bg, (320, y))
        text(img, (404, y + 12), "린네", col)
    g = ImageDraw.Draw(img)
    g.rectangle([0, 0, 1280, 44], fill=(0, 0, 0, 180))
    ImageDraw.Draw(img).text((16, 8), label, font=ImageFont.truetype(FONT, 24), fill=(255, 255, 255, 255))
    return img


def main():
    a = screen(False, "A. 아무 칸에도 마우스가 없을 때 — 둘째 「린네」만 연한 하늘색(스위치와 같은 a0d8f0)")
    b = screen(True, "B. 첫째 칸에 마우스를 올렸을 때 — 스팀판은 올린 칸 글자가 원래 하늘색(176,226,255)")
    out = Image.new("RGBA", (1280, 1440))
    out.paste(a, (0, 0)); out.paste(b, (0, 720))
    out.convert("RGB").resize((960, 1080)).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
