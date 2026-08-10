# -*- coding: utf-8 -*-
"""從特效圖裁出各職業的「投射物 / 命中」特效（去黑底）。

來源：
  A. ChatGPT Image ...02_39_32.png  下排 5 個獨立特效 → 一轉職業的投射物
  B. ChatGPT Image ...02_42_09.png  10 列動畫分解表   → 二轉職業的投射物 + 命中

與 crop_assets.py / crop_tier2.py 不同：角色貼圖是實心的，用 floodfill 去背；
這裡是黑底上的發光特效，半透明輝光必須保留，所以改用「亮度 → alpha」，
RGB 原樣保留，這樣疊在遊戲背景上才會像加色發光而不是貼一塊黑方塊。
"""
import os
from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ASSETS, "fx")
# 來源大圖放 tools/src/，不放 assets/——assets 整包會被 PyInstaller 打進 exe，
# 這三張加起來 4.8MB 而遊戲從來不讀它們。
SRC = os.path.join(ROOT, "tools", "src")
SRC_T1 = os.path.join(SRC, "ChatGPT Image 2026年8月10日 下午02_39_32.png")
SRC_T2 = os.path.join(SRC, "ChatGPT Image 2026年8月10日 下午02_42_09.png")

# ---- 一轉：02_39_32 下排（y 529..720），左→右對應上排 5 個職業 ----
T1_Y = (520, 730)
T1_PROJ = {
    "novice":  (55, 304),      # 綠斬
    "warrior": (336, 639),     # 藍斬
    "mage":    (683, 1013),    # 紫球
    "thief":   (1089, 1379),   # 紫刃
    "archer":  (1411, 1737),   # 綠箭
}

# ---- 二轉：02_42_09，(y0, y1, proj_x0, proj_x1, hit_x0, hit_x1) ----
# 每列前兩格是角色蓄力（已有角色貼圖，不取），中段取最後一格飛行姿態當投射物，
# 最右一格是命中爆裂。座標由 tools 量測後微調。
T2 = {
    "spearman": (8, 101, 1142, 1296, 1364, 1466),
    "fighter":  (105, 202, 1145, 1294, 1347, 1496),
    "page":     (205, 303, 1063, 1259, 1330, 1503),
    "wiz_il":   (304, 403, 980, 1276, 1297, 1510),
    "wiz_fp":   (404, 501, 848, 1260, 1316, 1481),
    "cleric":   (501, 600, 1080, 1288, 1324, 1503),   # 長光束只取前端
    "hunter":   (602, 698, 1100, 1248, 1353, 1477),
    "crossbow": (703, 790, 1030, 1283, 1372, 1499),
    "assassin": (810, 888, 420, 590, 1356, 1477),     # 取三連匕首最密集的一格
    "bandit":   (914, 999, 620, 755, 1360, 1473),     # 取金綠弧斬，與盜賊的紫刃做區隔
}

# 一轉沒有獨立的命中格，沿用同色系二轉的爆裂圖
T1_HIT_FROM = {
    "novice": "hunter",     # 綠
    "warrior": "page",      # 藍
    "mage": "wiz_fp",       # 紫
    "thief": "assassin",    # 紫
    "archer": "hunter",     # 綠
}

MAX_W, MAX_H = 256, 160     # 存檔上限（遊戲內還會再依縮放取樣）


def to_glow_rgba(crop, lift=18, gain=1.35):
    """黑底發光圖 → RGBA：alpha 取自最大通道亮度，RGB 保留。"""
    r, g, b = crop.split()
    lum = ImageChops.lighter(ImageChops.lighter(r, g), b)
    # 壓掉接近全黑的底噪，並提高中間調的不透明度
    alpha = lum.point(lambda v: 0 if v <= lift else min(255, int((v - lift) * gain)))
    rgba = Image.merge("RGBA", (r, g, b, alpha))
    bb = rgba.getbbox()
    if bb:
        rgba = rgba.crop(bb)
    if rgba.width > MAX_W or rgba.height > MAX_H:
        rgba.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
    return rgba


def cut(img, box):
    return to_glow_rgba(img.crop(box).convert("RGB"))


def main():
    os.makedirs(OUT, exist_ok=True)
    made = {}

    t1 = Image.open(SRC_T1).convert("RGB")
    print("T1 src", t1.size)
    for key, (x0, x1) in T1_PROJ.items():
        im = cut(t1, (x0, T1_Y[0], x1, T1_Y[1]))
        im.save(os.path.join(OUT, key + "_proj.png"))
        made[key + "_proj"] = im.size
        print("  saved %-14s %s" % (key + "_proj", im.size))

    t2 = Image.open(SRC_T2).convert("RGB")
    print("T2 src", t2.size)
    for key, (y0, y1, px0, px1, hx0, hx1) in T2.items():
        p = cut(t2, (px0, y0, px1, y1))
        p.save(os.path.join(OUT, key + "_proj.png"))
        made[key + "_proj"] = p.size
        h = cut(t2, (hx0, y0, hx1, y1))
        h.save(os.path.join(OUT, key + "_hit.png"))
        made[key + "_hit"] = h.size
        print("  saved %-14s %s   %-14s %s" % (key + "_proj", p.size, key + "_hit", h.size))

    for key, src in T1_HIT_FROM.items():
        im = Image.open(os.path.join(OUT, src + "_hit.png"))
        im.save(os.path.join(OUT, key + "_hit.png"))
        made[key + "_hit"] = im.size
        print("  copied %-13s <- %s_hit" % (key + "_hit", src))

    print("\n共 %d 個檔案" % len(made))
    montage(sorted(made))


def montage(keys):
    """預覽拼圖：深藍底才看得出輝光是否有殘留黑邊。"""
    cw, ch, cols = 200, 120, 6
    rows = (len(keys) + cols - 1) // cols
    from PIL import ImageDraw
    sheet = Image.new("RGB", (cw * cols, ch * rows), (26, 32, 52))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(keys):
        im = Image.open(os.path.join(OUT, k + ".png")).convert("RGBA")
        im.thumbnail((cw - 12, ch - 28))
        cx, cy = (i % cols) * cw, (i // cols) * ch
        sheet.paste(im, (cx + 6, cy + 22), im)
        d.text((cx + 6, cy + 6), k, fill=(255, 220, 120))
    p = os.path.join(ROOT, "tools", "montage_fx.png")
    sheet.save(p)
    print("montage ->", p)


main()
