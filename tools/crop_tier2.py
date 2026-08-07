# -*- coding: utf-8 -*-
"""從二轉職業黑底圖裁出 10 隻角色貼圖（去黑底）。"""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = r"C:\Users\11411612\TypingRPG"
SRC = r"C:\Users\11411612\Downloads\ChatGPT Image 2026年8月7日 下午02_48_03.png"
OUT = os.path.join(ROOT, "assets", "classes")
os.makedirs(OUT, exist_ok=True)

# 1536x1024，(x0,y0,x1,y1)，已避開底部標籤
BOXES = {
    "spearman": (10, 25, 345, 475),
    "fighter":  (355, 70, 565, 475),
    "page":     (585, 105, 800, 475),
    "wiz_il":   (800, 75, 1020, 475),
    "wiz_fp":   (1025, 85, 1260, 475),
    "cleric":   (1265, 95, 1475, 475),
    "hunter":   (85, 550, 365, 915),
    "crossbow": (395, 555, 655, 915),
    "assassin": (695, 555, 965, 915),
    "bandit":   (995, 555, 1255, 915),
}


def trim_alpha(im):
    b = im.getbbox()
    return im.crop(b) if b else im


def cut(img, box):
    crop = img.crop(box).convert("RGB")
    w, h = crop.size
    seed = (255, 0, 255)
    pts = []
    for t in range(0, w, max(1, w // 14)):
        pts += [(t, 0), (t, h - 1)]
    for t in range(0, h, max(1, h // 14)):
        pts += [(0, t), (w - 1, t)]
    for p in pts:
        try:
            ImageDraw.floodfill(crop, p, seed, thresh=40)
        except Exception:
            pass
    rgba = crop.convert("RGBA")
    px = rgba.load()
    for yy in range(h):
        for xx in range(w):
            r, g, b, a = px[xx, yy]
            if (r, g, b) == seed:
                px[xx, yy] = (0, 0, 0, 0)
    rgba = trim_alpha(rgba)
    r_, g_, b_, al = rgba.split()
    al = al.filter(ImageFilter.GaussianBlur(0.6))
    return Image.merge("RGBA", (r_, g_, b_, al))


def main():
    img = Image.open(SRC).convert("RGB")
    print("src size", img.size)
    for key, box in BOXES.items():
        im = cut(img, box)
        im.save(os.path.join(OUT, key + ".png"))
        print("saved", key, im.size)
    # 預覽拼圖
    keys = list(BOXES)
    cw, ch, cols = 190, 230, 5
    rows = (len(keys)+cols-1)//cols
    sheet = Image.new("RGB", (cw*cols, ch*rows), (30, 30, 40))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(keys):
        im = Image.open(os.path.join(OUT, k+".png")).convert("RGBA")
        im.thumbnail((cw-16, ch-30))
        cx, cy = (i % cols)*cw, (i//cols)*ch
        sheet.paste(im, (cx+8, cy+22), im)
        d.text((cx+8, cy+4), k, fill=(255, 220, 120))
    sheet.save(os.path.join(ROOT, "tools", "montage_tier2.png"))
    print("montage_tier2 saved")


main()
