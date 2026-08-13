# -*- coding: utf-8 -*-
"""從「職業技能打擊特效表」裁出各職業的投射物 / 命中特效（去黑底）。

來源：tools/src/ChatGPT Image 2026年8月13日 下午04_48_41.png
      14 列 = 14 個職業技能，每列 = 職業角色 + 蓄力→飛行 5 格 + 最右命中爆裂。

去背方式沿用 crop_fx.py：黑底發光圖不能用 floodfill（會吃掉半透明輝光），
改用「亮度 → alpha」，RGB 原樣保留，疊在遊戲背景上才會像加色發光。
本檔會覆蓋 crop_fx.py 產出的舊特效（novice 沒有專屬技能，沿用同色系的）。
"""
import os
from PIL import Image, ImageChops, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "fx")
SRC = os.path.join(ROOT, "tools", "src",
                   "ChatGPT Image 2026年8月13日 下午04_48_41.png")

# 列分隔線 y（由格線偵測取得，共 15 條 → 14 列）
ROW_Y = [8, 78, 147, 215, 282, 350, 417, 484, 552, 619, 687, 754, 821, 906, 1011]

# 每列：職業 key、投射物 x 範圍、命中爆裂 x 範圍。
# 多數列的格子之間有黑縫，可自動切；光束型技能（page/wiz_il/crossbow）整條連在
# 一起，x 範圍是照亮度谷底手動指定的。投射物一律取「最後一格飛行姿態」。
ROWS = [
    ("warrior",  (958, 1238), (1255, 1452)),   # 魔天一擊
    ("fighter",  (874, 1127), (1168, 1522)),   # 劍氣縱橫
    ("page",     (1024, 1195), (1255, 1440)),  # 氣絕劍（光束，手動切）
    ("spearman", (1095, 1245), (1265, 1365)),  # 槍無雙（連續星芒只取最大那顆）
    ("mage",     (1040, 1155), (1200, 1480)),  # 魔力爪
    ("wiz_il",   (900, 1215), (1225, 1500)),   # 閃電雷鳴（連續電流，取前端）
    ("wiz_fp",   (805, 1142), (1180, 1481)),   # 火焰箭
    ("cleric",   (880, 1182), (1285, 1425)),   # 神聖之箭
    ("archer",   (998, 1197), (1228, 1468)),   # 斷魂箭
    ("hunter",   (1086, 1217), (1235, 1462)),  # 爆炸箭
    ("crossbow", (1000, 1290), (1365, 1475)),  # 穿透箭（連續箭列，取前端）
    ("thief",    (792, 1166), (1233, 1453)),   # 劈空斬
    ("assassin", (990, 1168), (1224, 1466)),   # 雙飛鏢
    ("bandit",   (1140, 1275), (1285, 1480)),  # 迴旋斬
]

# 初心者沒有專屬技能圖，沿用同色系職業的特效
INHERIT = {"novice": "warrior"}

MAX_W, MAX_H = 256, 160     # 存檔上限（遊戲內還會再依縮放取樣）
PROJ_MAX_AR = 7.0           # 投射物最大長寬比，太長的光束只留前端（飛行方向的頭）


def to_glow_rgba(crop, lift=20, gain=1.35):
    """黑底發光圖 → RGBA：alpha 取自最大通道亮度，RGB 保留。"""
    r, g, b = crop.split()
    lum = ImageChops.lighter(ImageChops.lighter(r, g), b)
    alpha = lum.point(lambda v: 0 if v <= lift else min(255, int((v - lift) * gain)))
    rgba = Image.merge("RGBA", (r, g, b, alpha))
    bb = rgba.getbbox()
    if bb:
        rgba = rgba.crop(bb)
    return rgba


def fit(rgba):
    if rgba.width > MAX_W or rgba.height > MAX_H:
        rgba.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
    return rgba


def trim_head(rgba, max_ar=PROJ_MAX_AR):
    """特效朝右飛，太長的光束只保留右端（含尾巴淡出的一段）。"""
    if rgba.width <= rgba.height * max_ar:
        return rgba
    keep = int(rgba.height * max_ar)
    return rgba.crop((rgba.width - keep, 0, rgba.width, rgba.height))


def main():
    os.makedirs(OUT, exist_ok=True)
    src = Image.open(SRC).convert("RGB")
    print("src", src.size)
    made = {}
    for i, (key, pbox, hbox) in enumerate(ROWS):
        y0, y1 = ROW_Y[i] + 3, ROW_Y[i + 1] - 3
        p = fit(trim_head(to_glow_rgba(src.crop((pbox[0], y0, pbox[1], y1)))))
        h = fit(to_glow_rgba(src.crop((hbox[0], y0, hbox[1], y1))))
        p.save(os.path.join(OUT, key + "_proj.png"))
        h.save(os.path.join(OUT, key + "_hit.png"))
        made[key + "_proj"] = p.size
        made[key + "_hit"] = h.size
        print("  %-9s proj %-10s hit %s" % (key, p.size, h.size))

    for key, src_key in INHERIT.items():
        for suf in ("proj", "hit"):
            im = Image.open(os.path.join(OUT, f"{src_key}_{suf}.png"))
            im.save(os.path.join(OUT, f"{key}_{suf}.png"))
            made[f"{key}_{suf}"] = im.size
            print("  %-9s <- %s (%s)" % (key, src_key, suf))

    print("\n共 %d 個檔案" % len(made))
    montage(sorted(made))


def montage(keys):
    """預覽拼圖：深藍底才看得出輝光是否有殘留黑邊。"""
    cw, ch, cols = 210, 130, 6
    rows = (len(keys) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), (26, 32, 52))
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(keys):
        im = Image.open(os.path.join(OUT, k + ".png")).convert("RGBA")
        im.thumbnail((cw - 12, ch - 28))
        cx, cy = (i % cols) * cw, (i // cols) * ch
        sheet.paste(im, (cx + 6, cy + 22), im)
        d.text((cx + 6, cy + 6), "%s %dx%d" % (k, im.width, im.height),
               fill=(255, 220, 120))
    p = os.path.join(ROOT, "tools", "montage_fx_skill.png")
    sheet.save(p)
    print("montage ->", p)


main()
