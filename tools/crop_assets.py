# -*- coding: utf-8 -*-
"""從使用者提供的兩張圖裁出職業角色與怪物貼圖。"""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = r"C:\Users\11411612\TypingRPG"
CLASS_SRC = r"C:\Users\11411612\Downloads\ChatGPT Image 2026年8月7日 下午02_06_00.png"
MON_SRC = r"C:\Users\11411612\Downloads\Gemini_Generated_Image_par1cepar1cepar1.png"  # 白底圖鑑
os.makedirs(os.path.join(ROOT, "assets", "classes"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "assets", "monsters"), exist_ok=True)


def trim_alpha(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


# ---------- 職業角色（黑底 → flood fill 去背）----------
def crop_classes():
    img = Image.open(CLASS_SRC).convert("RGB")
    W, H = img.size
    y0, y1 = int(H * 0.05), int(H * 0.73)     # 避開底部文字標籤
    keys = ["novice", "warrior", "mage", "thief", "archer"]
    # 等分成 5 欄（角色均勻排列），各欄去黑底後再裁到內容
    for i, key in enumerate(keys):
        xs = int(W * i / 5)
        xe = int(W * (i + 1) / 5)
        box = (xs, y0, xe, y1)
        crop = img.crop(box).convert("RGB")
        seed = (255, 0, 255)
        w, h = crop.size
        for cxy in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1), (w//2, 0), (w//2, h-1)]:
            try:
                ImageDraw.floodfill(crop, cxy, seed, thresh=42)
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
        # 羽化 alpha
        r_, g_, b_, al = rgba.split()
        al = al.filter(ImageFilter.GaussianBlur(0.6))
        rgba = Image.merge("RGBA", (r_, g_, b_, al))
        out = os.path.join(ROOT, "assets", "classes", key + ".png")
        rgba.save(out)
        print("saved", key, rgba.size)


# ---------- 怪物（場景圖 → 橢圓柔邊裁切）----------
# 白底圖鑑座標（原始 2816x1536，已排除文字標籤）(x0,y0,x1,y1)
MON_BOXES = {
    "slime":       (183, 169, 662, 535),
    "butterfly":   (100, 620, 662, 1077),
    "fairy":       (753, 211, 1274, 795),
    "mermaid":     (612, 901, 1112, 1429),
    "water":       (1457, 246, 2069, 676),
    "skeleton":    (2098, 77, 2499, 560),
    "goblin":      (1450, 711, 1781, 1077),
    "caterpillar": (2105, 824, 2555, 1105),
    "lizard":      (1654, 1119, 2231, 1422),
}


def crop_monsters():
    img = Image.open(MON_SRC).convert("RGB")
    W, H = img.size
    print("monster src size:", (W, H))
    for key, (x0, y0, x1, y1) in MON_BOXES.items():
        box = (max(0, x0), max(0, y0), min(W, x1), min(H, y1))
        crop = img.crop(box).convert("RGB")
        w, h = crop.size
        seed = (255, 0, 255)
        # 從邊界多點對白底做 flood fill 去背
        pts = []
        for t in range(0, w, max(1, w // 12)):
            pts += [(t, 0), (t, h - 1)]
        for t in range(0, h, max(1, h // 12)):
            pts += [(0, t), (w - 1, t)]
        for p in pts:
            try:
                ImageDraw.floodfill(crop, p, seed, thresh=48)
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
        rgba = Image.merge("RGBA", (r_, g_, b_, al))
        rgba.save(os.path.join(ROOT, "assets", "monsters", key + ".png"))
        print("saved monster", key, rgba.size)


def montage():
    """輸出預覽拼圖以檢查裁切。"""
    cells = []
    for key in ["novice", "warrior", "mage", "thief", "archer"]:
        cells.append(("cls:" + key, os.path.join(ROOT, "assets", "classes", key + ".png")))
    for key in MON_BOXES:
        cells.append(("mon:" + key, os.path.join(ROOT, "assets", "monsters", key + ".png")))
    cw, ch, cols = 200, 200, 7
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cw*cols, ch*rows), (40, 44, 60))
    d = ImageDraw.Draw(sheet)
    for i, (name, path) in enumerate(cells):
        im = Image.open(path).convert("RGBA")
        im.thumbnail((cw-16, ch-30))
        cx = (i % cols) * cw
        cy = (i // cols) * ch
        sheet.paste(im, (cx+8, cy+22), im)
        d.text((cx+8, cy+4), name, fill=(255, 220, 120))
    out = os.path.join(ROOT, "tools", "montage.png")
    sheet.save(out)
    print("montage:", out)


crop_classes()
crop_monsters()
montage()
print("DONE")
