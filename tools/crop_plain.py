# -*- coding: utf-8 -*-
"""草原地圖素材：背景、7 隻小怪、魔王「風之精靈王」。

來源圖用的是「畫出來的」棋盤格假透明（實際是 RGB，沒有 alpha），
所以要自己去背。不能只用亮度門檻——魔王的白披風、蘑菇的白斑點、
老虎的白毛都會被挖空。作法是先算出「中性亮色」遮罩，再只清掉
從畫面邊界連通進來的那一塊，內部的白色因此完整保留。
"""
import os
from collections import deque
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "src")
MON_OUT = os.path.join(ROOT, "assets", "monsters")
BG_OUT = os.path.join(ROOT, "assets", "plain_bg.png")

SRC_MOBS = os.path.join(SRC, "plain_monsters.png")
SRC_BOSS = os.path.join(SRC, "plain_boss.png")
SRC_BG = os.path.join(SRC, "plain_bg_raw.png")

# 小怪由左至右的檔名（順序即來源圖的排列）
MOB_KEYS = ["rockgolem", "mush_red", "mush_brown", "grass_slime",
            "red_slime", "tiger", "sheep"]


def bg_mask(im):
    """回傳 bytearray：1 = 疑似棋盤格背景（夠亮且三通道接近相等）。"""
    W, H = im.size
    px = im.load()
    m = bytearray(W * H)
    i = 0
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if r > 228 and g > 228 and b > 228 and max(r, g, b) - min(r, g, b) < 10:
                m[i] = 1
            i += 1
    return m


def flood_border(mask, W, H):
    """只保留從邊界連通的背景（掃描線洪水填充），回傳 1 = 要透明。"""
    out = bytearray(W * H)
    stack = deque()
    for x in range(W):
        for y in (0, H - 1):
            if mask[y * W + x] and not out[y * W + x]:
                stack.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if mask[y * W + x] and not out[y * W + x]:
                stack.append((x, y))
    while stack:
        x, y = stack.pop()
        row = y * W
        if out[row + x] or not mask[row + x]:
            continue
        xl = x
        while xl > 0 and mask[row + xl - 1] and not out[row + xl - 1]:
            xl -= 1
        xr = x
        while xr < W - 1 and mask[row + xr + 1] and not out[row + xr + 1]:
            xr += 1
        for xx in range(xl, xr + 1):
            out[row + xx] = 1
        for ny in (y - 1, y + 1):
            if 0 <= ny < H:
                nrow = ny * W
                for xx in range(xl, xr + 1):
                    if mask[nrow + xx] and not out[nrow + xx]:
                        stack.append((xx, ny))
    return out


def strip_checker(im):
    """去掉棋盤格假透明，回傳 RGBA。"""
    im = im.convert("RGB")
    W, H = im.size
    transparent = flood_border(bg_mask(im), W, H)
    alpha = Image.frombytes("L", (W, H),
                            bytes(0 if t else 255 for t in transparent))
    # 邊緣柔化一格，避免鋸齒；柔化會把近零 alpha 抹出淡淡的殘影，
    # 殘影雖然看不見卻會讓 getbbox() 量到整張圖，所以再壓掉一層地板
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))
    alpha = alpha.point(lambda v: 0 if v < 12 else v)
    rgba = im.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def split_columns(rgba, n_expect):
    """依 alpha 的欄位投影切出各隻小怪。"""
    W, H = rgba.size
    a = rgba.getchannel("A").load()
    on = []
    for x in range(W):
        hit = False
        for y in range(0, H, 2):
            if a[x, y] > 40:
                hit = True
                break
        on.append(hit)
    segs, x = [], 0
    while x < W:
        if on[x]:
            x0 = x
            while x < W and on[x]:
                x += 1
            if x - x0 > 20:
                segs.append((x0, x - 1))
        else:
            x += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < 25:
            merged[-1] = (merged[-1][0], s[1])
        else:
            merged.append(list(s))
    print("  切出 %d 段 (預期 %d): %s" %
          (len(merged), n_expect, " ".join("%d-%d" % (a_, b_) for a_, b_ in merged)))
    return merged


def crop_bg(path):
    """去掉上下白邊，只留草原場景。"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    rows = []
    for y in range(H):
        white = 0
        for x in range(0, W, 8):
            r, g, b = px[x, y]
            if r > 245 and g > 245 and b > 245:
                white += 1
        rows.append(white < (W // 8) * 0.92)
    ys = [y for y, ok in enumerate(rows) if ok]
    top, bot = ys[0], ys[-1]
    print("  背景內容帶 y=%d..%d (原高 %d)" % (top, bot, H))
    return im.crop((0, top, W, bot + 1))


def main():
    os.makedirs(MON_OUT, exist_ok=True)

    print("背景:")
    bg = crop_bg(SRC_BG)
    bg.save(BG_OUT)
    print("  saved", BG_OUT, bg.size)

    print("小怪:")
    sheet = strip_checker(Image.open(SRC_MOBS))
    segs = split_columns(sheet, len(MOB_KEYS))
    if len(segs) != len(MOB_KEYS):
        raise SystemExit("切出的段數與預期不符，請調整門檻")
    for key, (x0, x1) in zip(MOB_KEYS, segs):
        sub = sheet.crop((x0, 0, x1 + 1, sheet.height))
        bb = sub.getbbox()
        if bb:
            sub = sub.crop(bb)
        sub.thumbnail((320, 320), Image.LANCZOS)
        sub.save(os.path.join(MON_OUT, key + ".png"))
        print("  saved %-12s %s" % (key, sub.size))

    print("魔王:")
    boss = strip_checker(Image.open(SRC_BOSS))
    bb = boss.getbbox()
    if bb:
        boss = boss.crop(bb)
    boss.thumbnail((420, 420), Image.LANCZOS)
    boss.save(os.path.join(MON_OUT, "windking.png"))
    print("  saved windking", boss.size)


main()
