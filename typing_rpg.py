# -*- coding: utf-8 -*-
"""
打字 RPG - 工作列上方的掛機養成 HUD（楓之谷風·原創像素）
==========================================================
一條停靠在螢幕底部（工作列上方）的無邊框橫條，明亮 2D 橫向卷軸風。
在「任何軟體」打字都會累積戰力，每敲一鍵 = 對怪物揮一刀，
讓角色闖關、升級、掉裝、轉職、解成就。含像素動畫與音效。

※ 美術為原創手繪像素，僅致敬經典 2D MMORPG 氛圍，未使用任何版權素材。

- 只計算「敲了幾下」，不記錄內容（非鍵盤側錄）。
- 右鍵：加技能 / 轉職 / 裝備 / 成就 / 音效 / 置中 / 離開。 左鍵拖曳：移動。

執行：  pythonw typing_rpg.py     需求： pip install pynput     打包： build.bat
"""

import json
import math
import os
import random
import sys
import threading
import time
import tkinter as tk

try:
    from pynput import keyboard
except ImportError:
    keyboard = None
try:
    import winsound
except ImportError:
    winsound = None


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def res_path(rel):
    """唯讀資源路徑：先找 PyInstaller 打包內容，再找 exe/腳本同目錄。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    return os.path.join(app_dir(), rel)


SAVE_FILE = os.path.join(app_dir(), "save.json")
BG_IMAGE = res_path(os.path.join("assets", "forest_bg.png"))
BG_CROP_Y = 0.58           # 取原圖縱向此比例中心的橫帶當背景（0=上緣, 1=下緣）
PANEL_BG = res_path(os.path.join("assets", "panel_bg.png"))   # 背包/商店背景圖

# ====================== 平衡數值 ======================
BASE_ATK = 3
COMBO_WINDOW = 2.0
COMBO_STEP = 0.02
COMBO_MAX = 100
MONSTER_BASE_HP = 4800           # 血量基準（原始 12 → ×20 = 240 → 再 ×20）
MONSTER_HP_GROWTH = 1.14         # 標準難度
MONSTER_BASE_EXP = 6
MONSTER_EXP_GROWTH = 1.13
MONSTER_BASE_GOLD = 3
MONSTER_GOLD_GROWTH = 1.12
EXP_BASE = 18
EXP_GROWTH = 1.32
# 一場遊戲：打倒 (FINAL_STAGE-1) 隻小怪後，第 FINAL_STAGE 關為最終 BOSS 羊頭人
FINAL_STAGE = 40
FINAL_BOSS_HP_MULT = 12
FINAL_BOSS_EXP_MULT = 20
FINAL_BOSS_GOLD_MULT = 20
LVUP_ATK = 2
LVUP_ATTR_POINTS = 3             # 升級 +3 屬性點
LVUP_SKILL_POINTS = 1            # 升級 +1 技能點
DROP_CHANCE = 0.20
INVENTORY_CAP = 12
# ---- 屬性效果 ----
STR_ATK = 2.0                    # 力量：每點物理攻擊
INT_ATK = 2.0                    # 智慧：每點魔法攻擊
AGI_COMBO = 0.02                 # 敏捷：每點連擊機率（上限 0.6）
LUK_CRIT = 0.006                 # 幸運：每點爆擊率
SKILL_FILL_BASE = 3.0            # 每次敲擊技能充能（滿 100 釋放）
SKILL_FILL_PER_STAT = 0.55       # 每點敏捷/幸運增加的充能

MONSTERS_PER_STAGE = 3           # 每關出現的小怪數（讓範圍技能有意義）

# ---- 難度：每關血量成長率 ----
DIFFICULTIES = {"平緩": 1.11, "標準": 1.14, "硬核": 1.18}
DIFFICULTY_ORDER = ["平緩", "標準", "硬核"]

# ====================== HUD 尺寸 ======================
BAR_W = 900                # 設計用的「邏輯」寬度（繪圖座標）
BAR_H = 156                # 邏輯高度（Y 軸）
DEFAULT_SCALE = 0.5        # 預設顯示縮放（0.5 = 一半大小；1.0 = 原尺寸）
SCALE_MIN = 0.35
SCALE_MAX = 1.5
SCALE_STEP = 0.10
S = DEFAULT_SCALE          # 目前縮放（可用 Ctrl+Alt+ +/-/0 即時調整）
FRAME_MS = 33
FLOOR = 82                 # 舊地面基準（保留相容）

# 過肩視角（寶可夢式）：玩家在前景左下、背對鏡頭；怪物在對面右上
HERO_X = 200
HERO_FY = 148              # 玩家腳底 y（靠近鏡頭 → 偏下、偏大）
HERO_SCALE = 1.35
# 每關三隻小怪的位置（前→後），整體偏左（避開右上角提示）
MON_SLOTS = [(365, 106), (495, 94), (622, 84)]
BOSS_POS = (480, 150)
MON_X = MON_SLOTS[0][0]     # 相容：特效/浮字預設參考前排
MON_FY = MON_SLOTS[0][1]


def _win_w():
    return int(BAR_W * S)


def _win_h():
    return int(BAR_H * S)

# ====================== 怪物（原創造型 + 通用名稱）======================
# 魔法森林區域限定怪物。優先用 assets/monsters/<kind>.png 貼圖；
# 找不到貼圖時，用以下 (內建像素形狀, 主色) 當備援。
MKINDS = {
    "slime":       ("slime", "#5ac8ff"),
    "skeleton":    ("golem", "#e8e2d0"),
    "fairy":       ("ghost", "#b7e6a0"),
    "water":       ("dragon", "#4bc0d0"),
    "butterfly":   ("bat", "#d18aff"),
    "goblin":      ("stump", "#79b352"),
    "mermaid":     ("ghost", "#57d3c0"),
    "caterpillar": ("snail", "#a7d84b"),
    "lizard":      ("stump", "#7ab24a"),
    "goathead":    ("demon", "#8a6a3a"),   # 最終 BOSS 羊頭人（暫用惡魔像素替身）
}
# 魔法森林小怪（第 1..FINAL_STAGE-1 關隨機出現、逐關變強）
MONSTERS = [
    ("slime", "史萊姆"), ("fairy", "湖畔精靈"), ("butterfly", "蝴蝶精"),
    ("goblin", "哥布林"), ("mermaid", "人魚"), ("caterpillar", "毛蟲"),
    ("lizard", "蜥蜴"), ("skeleton", "骷髏士兵"), ("water", "水怪"),
]
# 最終 BOSS（第 FINAL_STAGE 關）
FINAL_BOSS = ("goathead", "羊頭人")

# 四大屬性（升級 +3 點分配）：key -> (名稱, 效果說明)
ATTRS = {
    "str": ("力量", "物理攻擊力 ↑"),
    "agi": ("敏捷", "連擊機率、物技充能 ↑"),
    "int": ("智慧", "魔法攻擊力 ↑"),
    "luk": ("幸運", "爆擊機率、魔技充能 ↑"),
}

RARITIES = [
    ("common", "普通", "#e8edf7", 60.0, 1.0),
    ("fine",   "精良", "#5ce68f", 26.0, 1.6),
    ("rare",   "稀有", "#5aa0ff", 10.0, 2.6),
    ("epic",   "史詩", "#c77dff", 3.4,  4.2),
    ("legend", "傳說", "#ffb02e", 0.6,  7.0),
]
RARITY_IDX = {r[0]: i for i, r in enumerate(RARITIES)}
WEAPON_NAMES = ["楓之劍", "鋼鐵長槍", "木製短弓", "秘銀法杖", "暗影匕首", "巨型戰斧", "十字弩"]
ACC_NAMES = ["楓葉護符", "專注戒指", "紅水靈項鍊", "貓咪頭巾", "咖啡因藥水", "力量手套"]

# ====================== 職業（劍士/法師/弓箭手/盜賊 + 經典二轉）======================
# vis: weapon 武器樣式, out 服裝色, hair 髮/帽色, hat 帽型
CLASSES = {
    # 一轉（Lv.10）
    "warrior": {"name": "劍士", "tier": 1, "bonus": {"atk_pct": 0.25},
                "desc": "攻擊 +25%", "vis": ("sword", "#c94b4b", "#6b3f2a", None)},
    "mage":    {"name": "法師", "tier": 1, "bonus": {"exp": 0.30},
                "desc": "經驗 +30%", "vis": ("staff", "#4b6bd9", "#2a3a6b", "wizard")},
    "archer":  {"name": "弓箭手", "tier": 1, "bonus": {"crit": 0.12},
                "desc": "爆擊 +12%", "vis": ("bow", "#3fa85a", "#7a5a2a", "cap")},
    "thief":   {"name": "盜賊", "tier": 1, "bonus": {"crit": 0.06, "gold": 0.30},
                "desc": "爆擊 +6%、金幣 +30%", "vis": ("dagger", "#5a4b6b", "#241a33", None)},
    # 二轉（Lv.30）—— 劍士
    "fighter": {"name": "狂戰士", "tier": 2, "from": "warrior", "bonus": {"atk_pct": 0.60, "crit": 0.05},
                "desc": "攻擊 +60%、爆擊 +5%", "vis": ("axe", "#d24b4b", "#5a2f1f", None)},
    "page":    {"name": "見習騎士", "tier": 2, "from": "warrior", "bonus": {"atk_pct": 0.45, "crit": 0.10},
                "desc": "攻擊 +45%、爆擊 +10%", "vis": ("sword", "#c9a24b", "#4a4a5a", "helm")},
    "spearman": {"name": "槍騎兵", "tier": 2, "from": "warrior", "bonus": {"atk_pct": 0.70},
                 "desc": "攻擊 +70%", "vis": ("spear", "#b34b8a", "#4a2f5a", "helm")},
    # 二轉 —— 法師
    "wiz_fp":  {"name": "火毒巫師", "tier": 2, "from": "mage", "bonus": {"exp": 0.55, "crit": 0.10},
                "desc": "經驗 +55%、爆擊 +10%", "vis": ("staff", "#d94b4b", "#6b1f1f", "wizard")},
    "wiz_il":  {"name": "冰雷巫師", "tier": 2, "from": "mage", "bonus": {"exp": 0.75},
                "desc": "經驗 +75%", "vis": ("staff", "#4bc9d9", "#1f4a6b", "wizard")},
    "cleric":  {"name": "僧侶", "tier": 2, "from": "mage", "bonus": {"exp": 0.50, "gold": 0.40},
                "desc": "經驗 +50%、金幣 +40%", "vis": ("wand", "#e8e2c0", "#c9a24b", "wizard")},
    # 二轉 —— 弓箭手
    "hunter":  {"name": "獵人", "tier": 2, "from": "archer", "bonus": {"crit": 0.25},
                "desc": "爆擊 +25%", "vis": ("bow", "#3fa85a", "#5a3f1f", "cap")},
    "crossbow": {"name": "弩弓手", "tier": 2, "from": "archer", "bonus": {"crit": 0.18, "atk_pct": 0.20},
                 "desc": "爆擊 +18%、攻擊 +20%", "vis": ("crossbow", "#8a6b3f", "#3f2f1f", "cap")},
    # 二轉 —— 盜賊
    "assassin": {"name": "刺客", "tier": 2, "from": "thief", "bonus": {"crit": 0.30},
                 "desc": "爆擊 +30%", "vis": ("dagger", "#3a3a4a", "#12101a", None)},
    "bandit":  {"name": "俠盜", "tier": 2, "from": "thief", "bonus": {"crit": 0.15, "gold": 0.80},
                "desc": "爆擊 +15%、金幣 +80%", "vis": ("dagger", "#6b4b2a", "#2a1a0f", None)},
}
NOVICE_VIS = ("sword", "#8aa0c0", "#6b4a2a", None)

# 職業 → 角色貼圖檔名（二轉沿用一轉外觀）
CLASS_SPRITE = {
    None: "novice",
    "warrior": "warrior", "fighter": "fighter", "page": "page", "spearman": "spearman",
    "mage": "mage", "wiz_fp": "wiz_fp", "wiz_il": "wiz_il", "cleric": "cleric",
    "thief": "thief", "assassin": "assassin", "bandit": "bandit",
    "archer": "archer", "hunter": "hunter", "crossbow": "crossbow",
}


def class_sprite_key(cid):
    return CLASS_SPRITE.get(cid, "novice")


HERO_SPRITE_H = 138        # 玩家貼圖邏輯高度（放大但不超出橫條）
MON_SPRITE_H = 69          # 一般怪物貼圖邏輯高度（×1.5）
MON_SPRITE_H_BOSS = 108    # Boss 貼圖邏輯高度（×1.5）

# 職業分組（用於裝備限制、打擊特效）
CLASS_GROUP = {
    None: "warrior",
    "warrior": "warrior", "fighter": "warrior", "page": "warrior", "spearman": "warrior",
    "mage": "mage", "wiz_il": "mage", "wiz_fp": "mage", "cleric": "mage",
    "archer": "archer", "hunter": "archer", "crossbow": "archer",
    "thief": "thief", "assassin": "thief", "bandit": "thief",
}


def class_group(cid):
    return CLASS_GROUP.get(cid, "warrior")


# 武器名稱 → 可使用的職業分組（飾品無限制）
WEAPON_CLASS = {
    "楓之劍": "warrior", "鋼鐵長槍": "warrior", "巨型戰斧": "warrior",
    "秘銀法杖": "mage", "木製短弓": "archer", "十字弩": "archer",
    "暗影匕首": "thief",
}
# 各分組專屬武器名池（生成/商店用）
GROUP_WEAPONS = {
    "warrior": ["楓之劍", "鋼鐵長槍", "巨型戰斧"],
    "mage": ["秘銀法杖"],
    "archer": ["木製短弓", "十字弩"],
    "thief": ["暗影匕首"],
}

# 職業打擊特效顏色（依分組）
HIT_STYLE = {"warrior": "#ffcf47", "mage": "#c07bff", "archer": "#8effa0", "thief": "#7ff0ff"}
# 範圍技能（打到全部小怪）；其餘為單體（可多段打目標）
AOE_SKILLS = {"fighter", "hunter", "bandit", "wiz_il"}

# 魔功系職業（用智慧攻擊、幸運充能技能）；其餘為物功系（用力量攻擊、敏捷充能）
MAGIC_CLASSES = {"mage", "wiz_il", "wiz_fp", "cleric"}


def is_magic_class(cid):
    return cid in MAGIC_CLASSES


# 各職業技能：key -> (名稱, 傷害倍率, 段數, 顏色, 額外爆擊率, 說明)
# 傷害 = 當前攻擊 × 倍率 × (1 + 技能等級×0.3)，分成「段數」次跳字
SKILL_DEF = {
    "warrior":  ("魔天一擊", 6.0, 1, "#ffd35c", 0.0, "單體高傷爆發"),
    "fighter":  ("劍氣縱橫", 9.0, 1, "#ff6a4b", 0.0, "範圍劍氣，超高傷"),
    "page":     ("氣絕劍",   4.5, 1, "#c9a24b", 0.15, "中傷＋易爆"),
    "spearman": ("槍無雙",   2.2, 4, "#8ec6ff", 0.0, "多段連刺"),
    "mage":     ("魔力爪",   1.9, 4, "#c07bff", 0.0, "多段魔法抓擊"),
    "wiz_il":   ("閃電雷鳴", 2.1, 5, "#7ad0ff", 0.0, "連鎖閃電多段"),
    "wiz_fp":   ("火焰箭",   5.5, 1, "#ff7a3c", 0.0, "高魔傷＋灼燒"),
    "cleric":   ("神聖之箭", 5.2, 1, "#fff2a8", 0.0, "神聖高傷"),
    "archer":   ("斷魂箭",   5.5, 1, "#b9ffcf", 1.0, "必爆單發"),
    "hunter":   ("爆炸箭",   4.2, 1, "#ff9a3c", 0.0, "範圍爆炸"),
    "crossbow": ("穿透箭",   7.5, 1, "#e0e6ff", 0.0, "超高穿透"),
    "thief":    ("劈空斬",   2.6, 1, "#c0f0ff", 0.0, "低傷、充能快"),
    "assassin": ("雙飛鏢",   3.2, 2, "#d0d0ff", 0.3, "兩段＋爆擊加成"),
    "bandit":   ("迴旋斬",   3.4, 2, "#9affc0", 0.0, "範圍斬"),
}
# 充能較慢的技能（威力高）：每次釋放需要更多充能
SKILL_COST = {"fighter": 150, "crossbow": 130, "warrior": 120}


def skill_of(cid):
    return SKILL_DEF.get(cid)

ACHIEVEMENTS = [
    {"id": "keys100",  "icon": "⌨", "name": "初試啼聲", "goal": lambda s: (s.total_keys, 100)},
    {"id": "keys10k",  "icon": "⌨", "name": "鍵盤戰士", "goal": lambda s: (s.total_keys, 10000)},
    {"id": "keys100k", "icon": "⌨", "name": "打字之神", "goal": lambda s: (s.total_keys, 100000)},
    {"id": "combo50",  "icon": "🔥", "name": "手速如飛", "goal": lambda s: (s.max_combo, 50)},
    {"id": "combo100", "icon": "🔥", "name": "心流大師", "goal": lambda s: (s.max_combo, 100)},
    {"id": "stage10",  "icon": "🗺", "name": "初出茅廬", "goal": lambda s: (s.stage, 10)},
    {"id": "stage50",  "icon": "🗺", "name": "遠征軍",   "goal": lambda s: (s.stage, 50)},
    {"id": "stage100", "icon": "🗺", "name": "百關斬將", "goal": lambda s: (s.stage, 100)},
    {"id": "boss1",    "icon": "👑", "name": "首殺 Boss", "goal": lambda s: (s.boss_kills, 1)},
    {"id": "boss10",   "icon": "👑", "name": "屠龍者",   "goal": lambda s: (s.boss_kills, 10)},
    {"id": "level25",  "icon": "⭐", "name": "嶄露頭角", "goal": lambda s: (s.level, 25)},
    {"id": "level50",  "icon": "⭐", "name": "傳奇勇者", "goal": lambda s: (s.level, 50)},
    {"id": "gold10k",  "icon": "💰", "name": "小富翁",   "goal": lambda s: (s.gold, 10000)},
    {"id": "rare1",    "icon": "🎁", "name": "尋寶獵人", "goal": lambda s: (1 if s.best_rarity >= 2 else 0, 1)},
    {"id": "legend1",  "icon": "🌟", "name": "傳說降臨", "goal": lambda s: (1 if s.best_rarity >= 4 else 0, 1)},
    {"id": "job1",     "icon": "🎖", "name": "找到天職", "goal": lambda s: (1 if s.class_id else 0, 1)},
    {"id": "job2",     "icon": "🎖", "name": "登峰造極", "goal": lambda s: (1 if (s.class_id and CLASSES[s.class_id]["tier"] == 2) else 0, 1)},
]

JINGLES = {
    "level":   [(523, 90), (659, 90), (784, 150)],
    "loot":    [(880, 70), (1174, 130)],
    "boss":    [(392, 120), (523, 120), (659, 120), (784, 240)],
    "achieve": [(659, 80), (880, 80), (1046, 170)],
    "class":   [(523, 100), (659, 100), (784, 100), (1046, 260)],
}


def rarity_of(key):
    return RARITIES[RARITY_IDX[key]]


# ====================== 遊戲資料 ======================
class GameState:
    def __init__(self):
        self.level = 1
        self.exp = 0
        self.gold = 0
        self.stage = 1
        self.total_keys = 0
        self.kills = 0
        self.finished = False           # 是否已擊敗最終 BOSS（本局結束）
        self.attr_points = 0
        self.skill_points = 0
        self.attrs = {"str": 0, "agi": 0, "int": 0, "luk": 0}
        self.skill_lv = {}              # class_id -> 技能等級
        self.pos_x = None
        self.pos_y = None
        self.class_id = None
        self.weapon = None
        self.accessory = None
        self.inventory = []
        self.achievements = []
        self.muted = False
        self.max_combo = 0
        self.boss_kills = 0
        self.best_rarity = 0
        self.scale = DEFAULT_SCALE
        self.difficulty = "標準"
        self.stage_serial = 0
        self.monsters = []              # 本關的怪物清單（每隻為 dict）
        self.is_boss = False
        self.spawn_stage()

    @property
    def growth(self):
        return DIFFICULTIES.get(self.difficulty, 1.14)

    def cls_bonus(self, key):
        c = CLASSES.get(self.class_id)
        return (c["bonus"] if c else {}).get(key, 0)

    def eq_stat(self, key):
        v = 0
        for item in (self.weapon, self.accessory):
            if item:
                v += item["stats"].get(key, 0)
        return v

    @property
    def is_magic(self):
        return is_magic_class(self.class_id)

    @property
    def atk(self):
        flat = BASE_ATK + (self.level - 1) * LVUP_ATK + self.eq_stat("atk_flat")
        if self.is_magic:
            flat += self.attrs["int"] * INT_ATK        # 智慧 → 魔法攻擊
        else:
            flat += self.attrs["str"] * STR_ATK        # 力量 → 物理攻擊
        pct = 1 + self.cls_bonus("atk_pct") + self.eq_stat("atk_pct")
        return max(1, int(flat * pct))

    @property
    def exp_to_next(self):
        return int(EXP_BASE * (EXP_GROWTH ** (self.level - 1)))

    @property
    def crit_chance(self):
        return min(0.95, 0.05 + self.attrs["luk"] * LUK_CRIT
                   + self.cls_bonus("crit") + self.eq_stat("crit"))

    @property
    def combo_extra_chance(self):
        return min(0.6, self.attrs["agi"] * AGI_COMBO)

    @property
    def gold_mult(self):
        return 1 + self.cls_bonus("gold") + self.eq_stat("gold")

    @property
    def exp_mult(self):
        return 1 + self.cls_bonus("exp") + self.eq_stat("exp")

    @property
    def loot_boost(self):
        return self.cls_bonus("loot")

    @property
    def class_name(self):
        c = CLASSES.get(self.class_id)
        return c["name"] if c else "新手冒險家"

    @property
    def vis(self):
        c = CLASSES.get(self.class_id)
        return c["vis"] if c else NOVICE_VIS

    @property
    def skill_fill_per_key(self):
        drive = self.attrs["luk"] if self.is_magic else self.attrs["agi"]
        return SKILL_FILL_BASE + drive * SKILL_FILL_PER_STAT

    @property
    def skill_level(self):
        return self.skill_lv.get(self.class_id, 0) if self.class_id else 0

    def combo_multiplier(self, combo):
        return 1 + min(combo, COMBO_MAX) * COMBO_STEP

    @staticmethod
    def _mk(kind, name, hp, boss=False):
        hp = max(1, int(hp))
        return {"kind": kind, "name": name, "hp": hp, "max_hp": hp,
                "disp": hp, "boss": boss, "rewarded": False}

    def spawn_stage(self):
        self.stage_serial += 1
        self.monsters = []
        if self.stage >= FINAL_STAGE:
            self.is_boss = True
            kind, name = FINAL_BOSS
            hp = MONSTER_BASE_HP * (self.growth ** (FINAL_STAGE - 1)) * FINAL_BOSS_HP_MULT
            self.monsters.append(self._mk(kind, "【最終BOSS】" + name, hp, boss=True))
        else:
            self.is_boss = False
            hp = MONSTER_BASE_HP * (self.growth ** (self.stage - 1))
            for _ in range(MONSTERS_PER_STAGE):
                kind, name = random.choice(MONSTERS)
                self.monsters.append(self._mk(kind, name, hp))

    def target(self):
        for m in self.monsters:
            if m["hp"] > 0:
                return m
        return None

    def alive(self):
        return [m for m in self.monsters if m["hp"] > 0]

    def reward_kill(self, m):
        """單隻怪物死亡結算，回傳 (exp, gold, 是否BOSS)。"""
        exp = MONSTER_BASE_EXP * (MONSTER_EXP_GROWTH ** (self.stage - 1))
        gold = MONSTER_BASE_GOLD * (MONSTER_GOLD_GROWTH ** (self.stage - 1))
        boss = m.get("boss", False)
        if boss:
            exp *= FINAL_BOSS_EXP_MULT
            gold *= FINAL_BOSS_GOLD_MULT
        exp = int(exp * self.exp_mult)
        gold = int(gold * self.gold_mult)
        self.exp += exp
        self.gold += gold
        self.kills += 1
        m["rewarded"] = True
        return exp, gold, boss

    def advance_if_clear(self):
        """全部小怪清空 → 進下一關（或結束）。回傳 True 表示本關結束。"""
        if any(m["hp"] > 0 for m in self.monsters):
            return False
        if self.is_boss:
            self.boss_kills += 1
            self.finished = True
        else:
            self.stage += 1
            self.spawn_stage()
        return True

    def try_level_up(self):
        gained = 0
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.attr_points += LVUP_ATTR_POINTS
            self.skill_points += LVUP_SKILL_POINTS
            gained += 1
        return gained

    def to_dict(self):
        return {
            "level": self.level, "exp": self.exp, "gold": self.gold,
            "stage": self.stage, "total_keys": self.total_keys, "kills": self.kills,
            "finished": self.finished, "attr_points": self.attr_points,
            "skill_points": self.skill_points, "attrs": self.attrs,
            "skill_lv": self.skill_lv, "pos_x": self.pos_x, "pos_y": self.pos_y,
            "class_id": self.class_id, "weapon": self.weapon,
            "accessory": self.accessory, "inventory": self.inventory,
            "achievements": self.achievements, "muted": self.muted,
            "max_combo": self.max_combo, "boss_kills": self.boss_kills,
            "best_rarity": self.best_rarity, "scale": self.scale,
            "difficulty": self.difficulty,
        }

    def load_dict(self, d):
        for k in ("level", "exp", "gold", "stage", "total_keys", "kills", "finished",
                  "attr_points", "skill_points", "pos_x", "pos_y", "class_id",
                  "weapon", "accessory", "muted", "max_combo", "boss_kills",
                  "best_rarity", "scale", "difficulty"):
            if k in d:
                setattr(self, k, d[k])
        self.attrs.update(d.get("attrs", {}))
        self.skill_lv = d.get("skill_lv", {}) or {}
        self.inventory = d.get("inventory", [])
        self.achievements = d.get("achievements", [])
        self.scale = max(SCALE_MIN, min(SCALE_MAX, self.scale))
        if self.difficulty not in DIFFICULTIES:
            self.difficulty = "標準"
        # 舊版存檔（沒有 attrs / monsters 制）→ 遷移：保留等級/職業/金幣，重置本局
        if "attrs" not in d or "difficulty" not in d:
            self.stage = 1
            self.exp = 0
            self.finished = False
            self.kills = 0
            self.attr_points = (self.level - 1) * LVUP_ATTR_POINTS
            self.skill_points = (self.level - 1) * LVUP_SKILL_POINTS
        if self.stage > FINAL_STAGE:
            self.stage = FINAL_STAGE
        self.spawn_stage()


# ---- 掉寶 ----
def roll_rarity(boost):
    weights = [r[3] * (1 + boost * 0.5 * i) for i, r in enumerate(RARITIES)]
    total = sum(weights)
    x = random.random() * total
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if x <= acc:
            return RARITIES[i][0]
    return RARITIES[0][0]


def generate_item(ilvl, boss, loot_boost, force_type=None, group=None):
    boost = loot_boost + (3 if boss else 0)
    rk = roll_rarity(boost)
    mult = rarity_of(rk)[4]
    rname = rarity_of(rk)[1]
    typ = force_type or ("weapon" if random.random() < 0.5 else "accessory")
    if typ == "weapon":
        g = group or random.choice(list(GROUP_WEAPONS))
        base = random.choice(GROUP_WEAPONS[g])
        stats = {"atk_flat": int((3 + ilvl * 0.9) * mult)}
        if RARITY_IDX[rk] >= 2:
            stats["atk_pct"] = round(0.05 * mult, 2)
        return {"type": "weapon", "rarity": rk, "name": f"{rname}·{base}",
                "ilvl": ilvl, "stats": stats, "wclass": WEAPON_CLASS.get(base, g)}
    base = random.choice(ACC_NAMES)
    n = 2 if RARITY_IDX[rk] >= 2 else 1
    stats = {}
    for a in random.sample(["crit", "gold", "exp"], n):
        stats[a] = {"crit": round(0.02 * mult, 3),
                    "gold": round(0.08 * mult, 2),
                    "exp": round(0.08 * mult, 2)}[a]
    return {"type": "accessory", "rarity": rk, "name": f"{rname}·{base}",
            "ilvl": ilvl, "stats": stats}


def can_equip(item, class_id):
    """飾品人人可用；武器需符合職業分組。"""
    if not item or item["type"] != "weapon":
        return True
    return item.get("wclass", "warrior") == class_group(class_id)


def item_score(item):
    if not item:
        return -1
    s = item["stats"]
    if item["type"] == "weapon":
        return s.get("atk_flat", 0) + s.get("atk_pct", 0) * 200
    return s.get("crit", 0) * 1000 + s.get("gold", 0) * 100 + s.get("exp", 0) * 100


def item_stat_text(item):
    s = item["stats"]
    p = []
    if "atk_flat" in s:
        p.append(f"攻擊 +{s['atk_flat']}")
    if "atk_pct" in s:
        p.append(f"攻擊 +{int(s['atk_pct']*100)}%")
    if "crit" in s:
        p.append(f"爆擊 +{s['crit']*100:.1f}%")
    if "gold" in s:
        p.append(f"金幣 +{int(s['gold']*100)}%")
    if "exp" in s:
        p.append(f"經驗 +{int(s['exp']*100)}%")
    return "、".join(p)


def salvage_value(item):
    return int((5 + item["ilvl"]) * rarity_of(item["rarity"])[4])


# ====================== 顏色/繪圖工具 ======================
UI_FONT = "Microsoft JhengHei"
PIXEL_FONT = "Consolas"
# 深色森林/地城氛圍
SKY_TOP = "#0e2b28"        # 林冠陰影（頂）
SKY_BOT = "#17443a"        # 林中（也當作淡出背景色）
FOREST_GROUND = "#1d5a42"  # 地面
LEAF_DK = "#0b241f"        # 葉叢剪影（深）
LEAF = "#1c5238"           # 葉叢（中）
LEAF_LT = "#2f7a4e"        # 葉緣高光
PLAT_TOP = "#3f9a5c"       # 平台草皮
PLAT_SIDE = "#245c39"      # 平台側面
GLOW = "#c8ff92"           # 螢火
GRASS = PLAT_TOP
GRASS_DK = PLAT_SIDE
SOIL = "#5a4030"
SOIL_DK = "#3f2c1f"
BORDER = "#0a1a16"
INK = "#20263a"
GOLD = "#ffd35c"
WHITE = "#ffffff"

# parchment 面板（給彈出視窗）
PBG = "#f5e6c0"
PBR = "#7a5228"
PTX = "#4a3418"
PACC = "#b8862f"


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    c1, c2 = c1.lstrip("#"), c2.lstrip("#")
    return "#%02x%02x%02x" % (
        int(lerp(int(c1[0:2], 16), int(c2[0:2], 16), t)),
        int(lerp(int(c1[2:4], 16), int(c2[2:4], 16), t)),
        int(lerp(int(c1[4:6], 16), int(c2[4:6], 16), t)))


def shade(hexc, f):
    """f<1 變暗、f>1 變亮；支援 #rgb 與 #rrggbb，看不懂就原色回傳"""
    h = hexc.lstrip("#")
    if len(h) == 3:                       # #555 → #555555
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        return hexc
    try:
        int(h, 16)
    except ValueError:
        return hexc
    r = max(0, min(255, int(int(h[0:2], 16) * f)))
    g = max(0, min(255, int(int(h[2:4], 16) * f)))
    b = max(0, min(255, int(int(h[4:6], 16) * f)))
    return "#%02x%02x%02x" % (r, g, b)


# ====================== HUD ======================
class TypingRPG:
    def __init__(self, root):
        self.root = root
        self.state = GameState()
        self.load()
        global S
        S = self.state.scale                 # 套用存檔的縮放
        self._pending = 0
        self._zoom_pending = None            # 待處理的縮放指令（由監聽緒設定）
        self._esc_pending = False            # 全域 ESC（由監聽緒設定，主迴圈關面板）
        self._mods = set()                   # 目前按住的修飾鍵
        self._lock = threading.Lock()
        self.combo = 0
        self.last_key_time = 0.0
        self.listener = None
        self.have_listener = False
        self.frame = 0
        self.shake = 0.0
        self.lunge = 0.0
        self.combo_pulse = 0.0
        self.hitflash = 0.0
        self.lvlup = 0.0
        self.skill_gauge = 0.0          # 技能充能（0..cost）
        self.skill_flash = 0.0          # 技能釋放特效計時
        self.skill_color = GOLD
        self.banner = None
        self.floats = []
        self.sparks = []
        self.fireflies = [{"x": random.uniform(20, BAR_W - 20),
                           "y": random.uniform(10, 70),
                           "s": random.uniform(0.4, 1.3),
                           "p": random.uniform(0, 6.28)} for _ in range(14)]
        self._disp_exp = self.state.exp
        self._last_stage_serial = self.state.stage_serial
        self._last_level = self.state.level
        self.inv_win = None
        self.ach_win = None
        self.shop_win = None
        self._bg_src = None          # PIL 原圖
        self._bg_photo = None        # 依視窗尺寸裁切後的 PhotoImage
        self._cls_src = {}           # 職業角色 PIL 圖
        self._mon_src = {}           # 怪物 PIL 圖
        self._spr_cache = {}         # 依縮放快取的 PhotoImage
        self._build_window()
        self._purge_unusable_weapons()        # 舊存檔裡不符職業的裝備開檔就清掉
        self._start_listener()
        self.root.after(FRAME_MS, self._loop)
        self.root.after(20000, self._autosave)
        self.root.after(1500, self._keep_on_top)

    # ---------- 音效 ----------
    def play_sfx(self, name):
        if self.state.muted or winsound is None:
            return
        seq = JINGLES.get(name)
        if not seq:
            return
        def run():
            try:
                for f, d in seq:
                    winsound.Beep(int(f), int(d))
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    # ---------- 視窗 ----------
    def _build_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        sw = r.winfo_screenwidth()
        wb = self._work_area_bottom()
        x = self.state.pos_x if self.state.pos_x is not None else (sw - _win_w()) // 2
        y = self.state.pos_y if self.state.pos_y is not None else wb - _win_h() - 8
        x = max(0, min(x, sw - _win_w()))
        r.geometry(f"{_win_w()}x{_win_h()}+{x}+{y}")
        self.canvas = tk.Canvas(r, width=_win_w(), height=_win_h(), bg=SKY_TOP,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<Button-3>", self._popup_menu)
        # ESC 關閉面板（bind_all 涵蓋 app 內所有 widget，含各面板的按鈕）
        r.bind_all("<Escape>", lambda e: self._close_panels())
        self._drag = None
        self._load_bg()
        self._load_sprites()
        self._draw_background()

    # ---------- 角色 / 怪物貼圖 ----------
    def _load_sprites(self):
        try:
            from PIL import Image
        except ImportError:
            return
        cdir = res_path(os.path.join("assets", "classes"))
        mdir = res_path(os.path.join("assets", "monsters"))
        for k in set(CLASS_SPRITE.values()):
            p = os.path.join(cdir, k + ".png")
            if os.path.exists(p):
                try:
                    self._cls_src[k] = Image.open(p).convert("RGBA")
                except Exception:
                    pass
        for k in MKINDS:
            p = os.path.join(mdir, k + ".png")
            if os.path.exists(p):
                try:
                    self._mon_src[k] = Image.open(p).convert("RGBA")
                except Exception:
                    pass

    def _spr(self, src_dict, key, target_h_logical):
        """取得依目前縮放調整後的 PhotoImage（有快取）；無圖回傳 None。"""
        src = src_dict.get(key)
        if src is None:
            return None
        ph = max(1, int(round(target_h_logical * S)))
        ck = (id(src_dict), key, ph)
        img = self._spr_cache.get(ck)
        if img is None:
            try:
                from PIL import Image, ImageTk
            except ImportError:
                return None
            iw, ih = src.size
            pw = max(1, int(round(iw * ph / ih)))
            img = ImageTk.PhotoImage(src.resize((pw, ph), Image.LANCZOS))
            self._spr_cache[ck] = img
        return img

    # ---------- 背景圖 ----------
    def _load_bg(self):
        """載入外部背景圖（assets/forest_bg.png）；沒有 Pillow 或檔案則保持手繪森林。"""
        try:
            from PIL import Image  # noqa
        except ImportError:
            self._bg_src = None
            return
        if not os.path.exists(BG_IMAGE):
            self._bg_src = None
            return
        try:
            self._bg_src = Image.open(BG_IMAGE).convert("RGB")
        except Exception:
            self._bg_src = None
            return
        self._render_bg_photo()

    def _render_bg_photo(self):
        """以『寬度為準』縮放：整張圖左右完全填滿橫條（X 軸完全涵蓋），
        高於視窗的部分依 BG_CROP_Y 取縱向橫帶。"""
        if self._bg_src is None:
            self._bg_photo = None
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self._bg_photo = None
            return
        W, H = _win_w(), _win_h()
        iw, ih = self._bg_src.size
        sc = W / iw                          # 以寬度為準 → X 軸完全涵蓋
        nw, nh = W, max(1, int(round(ih * sc)))
        im = self._bg_src.resize((nw, nh), Image.LANCZOS)
        if nh >= H:                          # 較高 → 取縱向橫帶
            top = int((nh - H) * BG_CROP_Y)
            top = max(0, min(nh - H, top))
            im = im.crop((0, top, W, top + H))
        else:                                # 較矮 → 垂直置中，上下留空
            canvas_im = Image.new("RGB", (W, H), (6, 12, 10))
            canvas_im.paste(im, (0, (H - nh) // 2))
            im = canvas_im
        self._bg_photo = ImageTk.PhotoImage(im)

    def _apply_edge_fade(self, im, W, H):
        """把影像四邊柔和淡出到暗色，減少明顯的矩形邊界感。"""
        from PIL import Image
        mx = max(8, int(W * 0.07))
        my = max(6, int(H * 0.32))
        colf = [1.0] * W
        for x in range(W):
            if x < mx:
                colf[x] = x / mx
            elif x > W - mx - 1:
                colf[x] = (W - 1 - x) / mx
        rowf = [1.0] * H
        for y in range(H):
            if y < my:
                rowf[y] = y / my
            elif y > H - my - 1:
                rowf[y] = (H - 1 - y) / my
        data = bytearray(W * H)
        i = 0
        for y in range(H):
            ry = max(0.0, min(1.0, rowf[y]))
            for x in range(W):
                v = ry * max(0.0, min(1.0, colf[x]))
                data[i] = int(255 * (v * v * (3 - 2 * v)))   # smoothstep 柔化
                i += 1
        mask = Image.frombytes("L", (W, H), bytes(data))
        dark = Image.new("RGB", (W, H), (5, 9, 8))
        return Image.composite(im, dark, mask)

    def _work_area_bottom(self):
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            return rect.bottom
        except Exception:
            return self.root.winfo_screenheight() - 48

    def _drag_start(self, e):
        self._drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def _drag_move(self, e):
        if not self._drag:
            return
        sx, sy, ox, oy = self._drag
        nx, ny = ox + (e.x_root - sx), oy + (e.y_root - sy)
        self.root.geometry(f"+{nx}+{ny}")
        self.state.pos_x, self.state.pos_y = nx, ny

    # ---------- 背景（畫一次，tag=bg）----------
    def _platform(self, cx, cy, rw, rh, tag="bg"):
        self._ovl(cx - rw, cy - rh + 5, cx + rw, cy + rh + 5, LEAF_DK, tags=tag)            # 落地陰影
        self._ovl(cx - rw, cy - rh + 3, cx + rw, cy + rh + 3, PLAT_SIDE, tags=tag)          # 側面
        self._ovl(cx - rw, cy - rh, cx + rw, cy + rh, PLAT_TOP, tags=tag)                   # 草皮
        self._ovl(cx - rw + 4, cy - rh + 1, cx + rw - 4, cy + rh - 3, LEAF_LT, tags=tag)    # 高光

    def _draw_background(self):
        self.canvas.delete("bg")
        # 有外部背景圖就直接鋪圖（角色自身已有陰影，不需平台）
        if self._bg_photo is not None:
            self.canvas.create_image(0, 0, anchor="nw", image=self._bg_photo, tags="bg")
            return  # 邊界已由影像四邊淡出處理，不再畫硬邊框
        # 否則手繪森林（fallback）
        # 森林漸層（頂暗 → 地面）
        steps = 44
        for i in range(steps):
            y0 = BAR_H * i / steps
            y1 = BAR_H * (i + 1) / steps
            col = lerp_color(SKY_TOP, FOREST_GROUND, (i / steps) ** 1.3)
            self._rect(0, y0, BAR_W, y1 + 1, col, tags="bg")
        # 林冠陰影（頂部大剪影）
        for lx, rw, rh in [(120, 150, 46), (BAR_W * 0.5, 190, 40), (BAR_W - 120, 160, 52)]:
            self._ovl(lx - rw, -rh + 6, lx + rw, rh - 6, LEAF_DK, tags="bg")
        # 中景葉叢
        for lx, ly in [(70, 8), (300, 2), (560, 6), (BAR_W - 90, 4)]:
            self._ovl(lx - 60, ly - 26, lx + 60, ly + 26, LEAF, tags="bg")
            self._ovl(lx - 44, ly - 30, lx + 30, ly + 14, LEAF_LT, tags="bg")
        # 中央微光池（吸引視線到戰場）
        self._ovl(BAR_W * 0.42, 30, BAR_W * 0.42 + 260, 96, shade(FOREST_GROUND, 1.25), tags="bg")
        # 兩座平台：怪物（遠·上）、玩家（近·下）
        self._platform(MON_X, MON_FY + 4, 64, 12)
        self._platform(HERO_X, HERO_FY + 3, 82, 15)
        # 邊框
        self._rect(1, 1, BAR_W - 1, BAR_H - 1, "", outline=BORDER, width=2, tags="bg")

    # ---------- 右鍵選單 ----------
    def _popup_menu(self, e):
        s = self.state
        m = tk.Menu(self.root, tearoff=0)
        # 屬性加點（升級 +3 點）
        m.add_command(label=f"⭐ 屬性點：{s.attr_points}", state="disabled")
        for key, (name, desc) in ATTRS.items():
            m.add_command(label=f"{name}  Lv.{s.attrs[key]}   （{desc}）",
                          state="normal" if s.attr_points > 0 else "disabled",
                          command=lambda k=key: self._spend_attr(k))
        m.add_separator()
        # 職業技能升級（升級 +1 技能點）
        sk = skill_of(s.class_id)
        if sk:
            m.add_command(
                label=f"✨ 升級技能「{sk[0]}」 Lv.{s.skill_level}   技能點：{s.skill_points}",
                state="normal" if s.skill_points > 0 else "disabled",
                command=self._upgrade_skill)
        else:
            m.add_command(label="✨ 技能：轉職後開放", state="disabled")
        m.add_separator()
        opts = self._class_options()
        if opts:
            job = tk.Menu(m, tearoff=0)
            for cid, label in opts:
                job.add_command(label=label, command=lambda c=cid: self._change_class(c))
            m.add_cascade(label="🎖 轉職！", menu=job)
        else:
            nxt = "（Lv.10 可一轉）" if s.class_id is None else \
                  ("（Lv.30 可二轉）" if CLASSES[s.class_id]["tier"] == 1 else "（已達頂點）")
            m.add_command(label=f"🎖 職業：{s.class_name} {nxt}", state="disabled")
        m.add_command(label="🎒 裝備 / 背包", command=self._open_inventory)
        m.add_command(label="🏪 商店", command=self._open_shop)
        m.add_command(label="🏆 成就", command=self._open_achievements)
        diff = tk.Menu(m, tearoff=0)
        for name in DIFFICULTY_ORDER:
            diff.add_command(label=("● " if name == s.difficulty else "○ ") + name,
                             command=lambda nm=name: self._set_difficulty(nm))
        m.add_cascade(label=f"🎚 難度：{s.difficulty}", menu=diff)
        m.add_command(label=("🔈 音效：關閉中" if s.muted else "🔊 音效：開啟中"),
                      command=self._toggle_mute)
        zoom = tk.Menu(m, tearoff=0)
        zoom.add_command(label="放大  (Ctrl+Alt++)", command=lambda: self._do_zoom("in"))
        zoom.add_command(label="縮小  (Ctrl+Alt+-)", command=lambda: self._do_zoom("out"))
        zoom.add_command(label="還原預設  (Ctrl+Alt+0)", command=lambda: self._do_zoom("reset"))
        m.add_cascade(label=f"🔍 縮放：{int(S * 100)}%", menu=zoom)
        m.add_separator()
        m.add_command(label="🔄 重新開始本局", command=self._restart)
        m.add_command(label="↺ 置中位置", command=self._recenter)
        m.add_command(label="✕ 離開遊戲", command=self._on_close)
        m.tk_popup(e.x_root, e.y_root)

    def _spend_attr(self, key):
        if self.state.attr_points <= 0:
            return
        self.state.attr_points -= 1
        self.state.attrs[key] += 1
        self._add_float(BAR_W * 0.16, 30, f"{ATTRS[key][0]} +1", "#8ad0ff", size=12, life=1.0)

    def _upgrade_skill(self):
        s = self.state
        sk = skill_of(s.class_id)
        if s.skill_points <= 0 or not sk:
            return
        s.skill_points -= 1
        s.skill_lv[s.class_id] = s.skill_lv.get(s.class_id, 0) + 1
        self.banner = (f"技能「{sk[0]}」 Lv.{s.skill_lv[s.class_id]}", 1.2)

    def _restart(self):
        keep = (self.state.pos_x, self.state.pos_y, self.state.muted,
                self.state.scale, self.state.difficulty)
        self.state = GameState()
        (self.state.pos_x, self.state.pos_y, self.state.muted,
         self.state.scale, self.state.difficulty) = keep
        self.state.spawn_stage()
        self.combo = 0
        self.skill_gauge = 0.0
        self.floats = []
        self.sparks = []
        self.banner = ("新的冒險開始！", 1.4)
        self._disp_exp = 0
        self._last_stage_serial = self.state.stage_serial
        self._last_level = 1
        self.save()

    def _set_difficulty(self, name):
        if name in DIFFICULTIES:
            self.state.difficulty = name
            self.banner = (f"難度：{name}", 1.2)

    def _toggle_mute(self):
        self.state.muted = not self.state.muted

    def _recenter(self):
        sw = self.root.winfo_screenwidth()
        x = (sw - _win_w()) // 2
        y = self._work_area_bottom() - _win_h() - 8
        self.root.geometry(f"{_win_w()}x{_win_h()}+{x}+{y}")
        self.state.pos_x, self.state.pos_y = x, y

    # ---------- 縮放 ----------
    def _do_zoom(self, action):
        if action == "in":
            ns = S + SCALE_STEP
        elif action == "out":
            ns = S - SCALE_STEP
        else:
            ns = DEFAULT_SCALE
        self._apply_scale(round(max(SCALE_MIN, min(SCALE_MAX, ns)), 2))

    def _apply_scale(self, ns):
        global S
        old_h = _win_h()
        ox, oy = self.root.winfo_x(), self.root.winfo_y()
        S = ns
        self.state.scale = ns
        neww, newh = _win_w(), _win_h()
        new_y = oy + old_h - newh                       # 底邊固定（貼齊工作列）
        sw = self.root.winfo_screenwidth()
        ox = max(0, min(ox, sw - neww))
        self.root.geometry(f"{neww}x{newh}+{ox}+{new_y}")
        self.canvas.config(width=neww, height=newh)
        self._spr_cache.clear()                          # 貼圖依新縮放重算
        self._render_bg_photo()                          # 背景圖依新尺寸重裁
        self._draw_background()                          # 背景需依新縮放重畫
        self.state.pos_x, self.state.pos_y = ox, new_y
        self.banner = (f"縮放 {int(ns * 100)}%", 1.0)

    # ---------- 轉職 ----------
    def _class_options(self):
        s = self.state
        if s.class_id is None and s.level >= 10:
            return [(cid, f"{c['name']}（{c['desc']}）")
                    for cid, c in CLASSES.items() if c["tier"] == 1]
        if s.class_id and CLASSES[s.class_id]["tier"] == 1 and s.level >= 30:
            return [(cid, f"{c['name']}（{c['desc']}）")
                    for cid, c in CLASSES.items()
                    if c["tier"] == 2 and c.get("from") == s.class_id]
        return []

    def _change_class(self, cid):
        self.state.class_id = cid
        c = CLASSES[cid]
        self.banner = (f"轉職成為 {c['name']}！", 1.8)
        self.lvlup = 1.0
        self.play_sfx("class")
        # 轉職後舊職業的武器（含身上那把）一律自動分解
        n, gold = self._purge_unusable_weapons()
        if n:
            self.banner = (f"轉職！自動分解 {n} 件舊職業裝備 +{gold}G", 2.0)
            self._refresh_inventory()

    # ---------- 鍵盤 ----------
    def _start_listener(self):
        if keyboard is None:
            self.root.bind_all("<Key>", lambda e: self._on_key())
            return
        self.have_listener = True
        self.listener = keyboard.Listener(on_press=self._on_press,
                                          on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

    def _on_key(self):
        with self._lock:
            self._pending += 1

    # pynput：全域按下（含縮放快捷鍵偵測，執行於監聽緒）
    def _on_press(self, key):
        with self._lock:
            self._pending += 1
        K = keyboard.Key
        if key == K.esc:
            # 全域 ESC：即使焦點不在遊戲上也能關掉面板（主迴圈處理）
            with self._lock:
                self._esc_pending = True
            return
        if key in (K.ctrl_l, K.ctrl_r, K.ctrl):
            self._mods.add("ctrl")
            return
        if key in (K.alt_l, K.alt_r, getattr(K, "alt_gr", None)):
            self._mods.add("alt")
            return
        if "ctrl" in self._mods and "alt" in self._mods:
            act = self._zoom_key(key)
            if act:
                with self._lock:
                    self._zoom_pending = act

    def _on_release(self, key):
        K = keyboard.Key
        if key in (K.ctrl_l, K.ctrl_r, K.ctrl):
            self._mods.discard("ctrl")
        elif key in (K.alt_l, K.alt_r, getattr(K, "alt_gr", None)):
            self._mods.discard("alt")

    @staticmethod
    def _zoom_key(key):
        char = getattr(key, "char", None)
        vk = getattr(key, "vk", None)
        if char in ("+", "=") or vk in (107, 187):      # + / = / 數字鍵盤+
            return "in"
        if char in ("-", "_") or vk in (109, 189):      # - / _ / 數字鍵盤-
            return "out"
        if char == "0" or vk in (48, 96):               # 0 / 數字鍵盤0
            return "reset"
        return None

    # ---------- 主迴圈 ----------
    def _loop(self):
        with self._lock:
            n = self._pending
            self._pending = 0
            zp = self._zoom_pending
            self._zoom_pending = None
            esc = self._esc_pending
            self._esc_pending = False
        if zp:
            self._do_zoom(zp)
        if esc:
            self._close_panels()
        now = time.time()
        if n > 0:
            if now - self.last_key_time > COMBO_WINDOW:
                self.combo = 0
            self.last_key_time = now
            self._process_keys(n)
        elif self.combo and now - self.last_key_time > COMBO_WINDOW:
            self.combo = 0
        self._check_achievements()
        self._update_anim()
        self._render()
        self.root.after(FRAME_MS, self._loop)

    def _mon_pos(self, idx):
        """怪物 idx 的位置；BOSS 用置中大位。"""
        if self.state.is_boss:
            return BOSS_POS
        return MON_SLOTS[idx] if idx < len(MON_SLOTS) else MON_SLOTS[-1]

    def _process_keys(self, n):
        s = self.state
        if s.finished:
            return                          # 本局已結束，不再戰鬥
        total_dmg = 0
        crit_any = False
        events = []                         # (exp, gold, boss, drop)
        won = False
        for _ in range(n):
            tgt = s.target()
            if tgt is None:
                break
            # 連擊（敏捷：機率額外 +1）
            self.combo += 1
            if random.random() < s.combo_extra_chance:
                self.combo += 1
            s.max_combo = max(s.max_combo, self.combo)
            s.total_keys += 1
            dmg = s.atk * s.combo_multiplier(self.combo)
            if random.random() < s.crit_chance:
                dmg *= 2
                crit_any = True
            dmg = max(1, int(dmg))
            total_dmg += dmg
            tgt["hp"] -= dmg               # 普攻打目標（最前一隻）
            # 技能充能與釋放
            sk = skill_of(s.class_id)
            if sk:
                self.skill_gauge += s.skill_fill_per_key
                cost = SKILL_COST.get(s.class_id, 100)
                while self.skill_gauge >= cost and s.alive():
                    self.skill_gauge -= cost
                    total_dmg += self._cast_skill(sk)
            # 結算剛死亡的怪物
            for m in s.monsters:
                if m["hp"] <= 0 and not m["rewarded"]:
                    exp, gold, boss = s.reward_kill(m)
                    drop = None if boss else self._roll_loot(s.stage - 1)
                    events.append((exp, gold, boss, drop))
                    lv = s.try_level_up()
                    if lv:
                        self.banner = (f"LEVEL UP!  Lv.{s.level}", 1.4)
                        self.lvlup = 1.0
                        self.play_sfx("level")
            # 全部清空 → 進關 / 勝利
            if not s.alive():
                if s.advance_if_clear() and s.finished:
                    won = True
                break
        self.shake = min(1.0, self.shake + 0.6)
        self.lunge = 1.0
        self.combo_pulse = 1.0
        self.hitflash = 1.0
        tgt = s.target()
        tx, ty = self._mon_pos(s.monsters.index(tgt)) if tgt in s.monsters else (MON_X, MON_FY)
        self._spawn_sparks(tx, ty - 16)
        self._add_float(tx + random.uniform(-14, 14), ty - 30,
                        f"{total_dmg:,}" + ("!" if crit_any else ""),
                        GOLD if crit_any else WHITE,
                        size=17 if crit_any else 13, life=0.85, crit=crit_any)
        for exp, gold, boss, drop in events:
            self._add_float(MON_X, MON_FY - 12, f"+{exp} EXP  +{gold}G",
                            "#ffe58a" if boss else "#b9ffcf", size=11, life=1.2)
            if drop:
                self._add_float(MON_X + 40, MON_FY - 22, drop, GOLD, size=11, life=1.5)
        if won:
            self.play_sfx("boss")
            self.banner = ("🏆 討伐成功！", 2.2)
            self.lvlup = 1.0
            self.save()

    def _cast_skill(self, sk):
        """釋放職業技能，回傳造成的總傷害。範圍技能打全部小怪。"""
        name, mult, hits, color, crit_bonus, note = sk
        s = self.state
        per_target = max(1, int(s.atk * mult * (1 + s.skill_level * 0.3)))
        aoe = s.class_id in AOE_SKILLS
        targets = s.alive() if aoe else ([s.target()] if s.target() else [])
        total = 0
        self.skill_flash = 1.0
        self.skill_color = color
        for m in targets:
            m["hp"] -= per_target
            total += per_target
            idx = s.monsters.index(m)
            tx, ty = self._mon_pos(idx)
            for i in range(hits):
                self._add_float(tx + random.uniform(-20, 20), ty - 34 - i * 5,
                                f"{max(1, per_target // hits):,}", color,
                                size=16, life=0.95, crit=True)
            self._spawn_sparks(tx, ty - 16)
        self._add_float(MON_X, MON_FY - 52, name + ("（範圍）" if aoe else ""),
                        color, size=13, life=1.1)
        return total

    # ---------- 掉寶 ----------
    def _roll_loot(self, ilvl):
        s = self.state
        if random.random() > (DROP_CHANCE + s.loot_boost * 0.10):
            return None
        item = generate_item(max(1, ilvl), False, s.loot_boost)
        ri = RARITY_IDX[item["rarity"]]
        s.best_rarity = max(s.best_rarity, ri)
        # 無法裝備（不符職業）的武器 → 自動分解換金幣
        if not can_equip(item, s.class_id):
            s.gold += salvage_value(item)
            return f"分解 {item['name']} +{salvage_value(item)}G"
        if ri >= 2:
            self.play_sfx("loot")
        slot = "weapon" if item["type"] == "weapon" else "accessory"
        cur = getattr(s, slot)
        if item_score(item) > item_score(cur):
            if cur:
                self._to_inventory(cur)
            setattr(s, slot, item)
            self._refresh_inventory()
            return f"裝備 {item['name']}"
        self._to_inventory(item)
        self._refresh_inventory()
        return f"獲得 {item['name']}"

    def _to_inventory(self, item):
        s = self.state
        s.inventory.append(item)
        # 任何進背包的東西都先過濾一次職業限制（不必等到打開背包）
        self._purge_unusable_weapons()
        if len(s.inventory) > INVENTORY_CAP:
            s.inventory.sort(key=item_score)
            s.gold += salvage_value(s.inventory.pop(0))

    # ---------- 成就 ----------
    def _check_achievements(self):
        s = self.state
        for a in ACHIEVEMENTS:
            if a["id"] in s.achievements:
                continue
            cur, target = a["goal"](s)
            if cur >= target:
                s.achievements.append(a["id"])
                self.banner = (f"🏆 成就：{a['name']}", 1.6)
                self.play_sfx("achieve")

    # ---------- 特效資料 ----------
    def _monster_cx(self):
        return MON_X

    def _add_float(self, x, y, text, color, size=12, life=0.9, crit=False):
        self.floats.append({"x": x, "y": y, "vy": -34, "text": text, "color": color,
                            "size": size, "life": life, "maxlife": life, "crit": crit})

    def _hit_color(self):
        return HIT_STYLE.get(class_group(self.state.class_id), "#ffcf47")

    def _spawn_sparks(self, x=None, y=None):
        x = MON_X if x is None else x
        y = (MON_FY - 16) if y is None else y
        col = self._hit_color()
        for _ in range(5):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(40, 120)
            self.sparks.append({"x": x, "y": y, "vx": math.cos(ang) * spd,
                                "vy": math.sin(ang) * spd - 30, "life": 0.32,
                                "maxlife": 0.32, "col": col})

    def _update_anim(self):
        self.frame += 1
        dt = FRAME_MS / 1000.0
        s = self.state
        # 每隻怪物血條平滑；換關瞬間補滿
        if s.stage_serial != self._last_stage_serial:
            self._last_stage_serial = s.stage_serial
            for m in s.monsters:
                m["disp"] = m["max_hp"]
        else:
            for m in s.monsters:
                m["disp"] += (m["hp"] - m["disp"]) * 0.30
                if abs(m["disp"] - m["hp"]) < 0.5:
                    m["disp"] = m["hp"]
        if s.level != self._last_level:
            self._last_level = s.level
            self._disp_exp = 0
        else:
            self._disp_exp += (s.exp - self._disp_exp) * 0.20
            if abs(self._disp_exp - s.exp) < 0.5:
                self._disp_exp = s.exp
        for a in ("shake", "lunge", "combo_pulse", "hitflash", "lvlup", "skill_flash"):
            setattr(self, a, max(0.0, getattr(self, a) - dt * 4))
        if self.banner:
            txt, tmr = self.banner
            tmr -= dt
            self.banner = (txt, tmr) if tmr > 0 else None
        nf = []
        for f in self.floats:
            f["life"] -= dt
            f["vy"] += 60 * dt
            f["y"] += f["vy"] * dt
            if f["life"] > 0:
                nf.append(f)
        self.floats = nf
        ns = []
        for p in self.sparks:
            p["life"] -= dt
            p["vy"] += 140 * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["life"] > 0:
                ns.append(p)
        self.sparks = ns

    # ============ 繪圖基礎（皆以「邏輯座標」呼叫，內部乘上縮放 S） ============
    # 低階（可指定 tag/寬度）——所有畫布繪製都應經過這些，才會一起縮放
    def _rect(self, x0, y0, x1, y1, fill, outline="", width=1, tags="dyn"):
        self.canvas.create_rectangle(x0 * S, y0 * S, x1 * S, y1 * S, fill=fill,
                                     outline=outline, width=width, tags=tags)

    def _ovl(self, x0, y0, x1, y1, fill, outline="", width=1, tags="dyn"):
        self.canvas.create_oval(x0 * S, y0 * S, x1 * S, y1 * S, fill=fill,
                                outline=outline, width=width, tags=tags)

    def _plg(self, pts, fill, outline="", tags="dyn"):
        self.canvas.create_polygon([p * S for p in pts], fill=fill, outline=outline, tags=tags)

    def _line(self, x0, y0, x1, y1, fill, width=1, tags="dyn"):
        self.canvas.create_line(x0 * S, y0 * S, x1 * S, y1 * S, fill=fill,
                                width=max(1, width), tags=tags)

    def _arc(self, x0, y0, x1, y1, start, extent, outline, width=1, tags="dyn"):
        self.canvas.create_arc(x0 * S, y0 * S, x1 * S, y1 * S, start=start, extent=extent,
                               style="arc", outline=outline, width=max(1, width), tags=tags)

    # 便利別名（沿用舊呼叫）
    def _px(self, x, y, w, h, color, out=""):
        self._rect(x, y, x + w, y + h, color, out)

    def _oval(self, x0, y0, x1, y1, color, out=""):
        self._ovl(x0, y0, x1, y1, color, out)

    def _poly(self, pts, color, out=""):
        self._plg(pts, color, out)

    def _text(self, x, y, txt, color=WHITE, size=11, anchor="center", bold=True,
              outline=INK, font=UI_FONT):
        fs = max(1, int(round(size * S)))
        f = (font, fs, "bold" if bold else "normal")
        if outline:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
                self.canvas.create_text(x * S + dx, y * S + dy, text=txt, fill=outline,
                                        font=f, anchor=anchor, tags="dyn")
        self.canvas.create_text(x * S, y * S, text=txt, fill=color, font=f,
                                anchor=anchor, tags="dyn")

    def _bar(self, x1, y, w, h, frac, c1, c2, bg="#20263f"):
        self._rect(x1, y, x1 + w, y + h, bg, outline=INK, width=1)
        frac = max(0.0, min(1.0, frac))
        if frac > 0.01:
            fw = w * frac
            self._rect(x1, y, x1 + fw, y + h, c1)
            self._rect(x1, y, x1 + fw, y + h / 2, c2)

    # ============ 玩家角色（優先用貼圖，否則像素備援） ============
    def _draw_hero(self, cx, fy, vis, bob, lunge):
        img = self._spr(self._cls_src, class_sprite_key(self.state.class_id), HERO_SPRITE_H)
        if img is not None:
            dx = lunge * 8
            self._ovl(cx - 15, fy - 3, cx + 15, fy + 4, LEAF_DK)   # 影子
            self.canvas.create_image((cx + dx) * S, (fy - bob) * S,
                                     anchor="s", image=img, tags="dyn")
            return
        self._draw_hero_pixel(vis, cx, fy, bob, lunge)

    def _draw_hero_pixel(self, vis, cx, fy, bob, lunge):
        weapon, out, hair, hat = vis
        s = HERO_SCALE
        # 攻擊時朝怪物（右上）踏步
        cx += lunge * 6
        fy -= lunge * 3
        skin = "#f0c49a"

        def B(x, y, w, h, color):
            self._px(cx + x * s, fy + (y - bob) * s, w * s, h * s, color)

        def O(x0, y0, x1, y1, color, out=""):
            self._ovl(cx + x0 * s, fy + (y0 - bob) * s, cx + x1 * s, fy + (y1 - bob) * s, color, out)

        # 影子
        self._ovl(cx - 11 * s, fy - 2, cx + 11 * s, fy + 4, LEAF_DK)
        # 腿（背面）
        B(-6, -9, 5, 9, "#33304a")
        B(1, -9, 5, 9, "#2b2840")
        # 身體（背部）
        B(-8, -23, 16, 15, out)
        B(-8, -23, 16, 3, shade(out, 1.2))          # 肩線高光
        B(-1, -22, 2, 13, shade(out, 0.75))         # 脊椎縫線
        # 背後裝備：近戰=盾、弓手=箭袋、其餘=披風
        if weapon in ("sword", "axe", "spear"):
            O(-6, -21, 6, -9, "#c9ccd8", "#8a8fa2")  # 圓盾
            O(-2.5, -17, 2.5, -12, "#e8b64b")        # 盾心
        elif weapon in ("bow", "crossbow"):
            B(3, -24, 3, 12, "#7a5330")              # 箭袋
            B(3, -26, 1.4, 4, "#e8e0c0")
            B(6, -26, 1.4, 4, "#e8e0c0")
        else:
            self._plg([cx - 7 * s, fy + (-22 - bob) * s, cx + 7 * s, fy + (-22 - bob) * s,
                       cx + 4 * s, fy + (-6 - bob) * s, cx - 4 * s, fy + (-6 - bob) * s],
                      shade(out, 0.8))               # 披風
            B(-8, -23, 16, 15, out)
            B(-1, -22, 2, 13, shade(out, 0.75))
        # 後腦（背面全是頭髮）
        B(-6, -34, 12, 12, hair)
        B(-6, -24, 12, 2, skin)                      # 脖子
        # 帽子（背面）
        if hat == "wizard":
            self._plg([cx - 9 * s, fy + (-32 - bob) * s, cx + 9 * s, fy + (-32 - bob) * s,
                       cx + 2 * s, fy + (-50 - bob) * s], hair)
        elif hat == "cap":
            B(-7, -37, 14, 5, hair)
            self._plg([cx - 7 * s, fy + (-35 - bob) * s, cx - 15 * s, fy + (-37 - bob) * s,
                       cx - 7 * s, fy + (-32 - bob) * s], "#e8d060")   # 羽毛在後
        elif hat == "helm":
            B(-7, -36, 14, 6, hair)
            B(-2, -40, 4, 4, "#d84b4b")              # 盔頂裝飾
        # 武器高舉朝右上方的怪物
        self._draw_weapon(weapon, cx + 9 * s, fy + (-16 - bob) * s, s)

    def _draw_weapon(self, kind, hx, hy, s):
        steel = "#dfe4f0"
        if kind in ("sword", "axe", "spear"):
            L = 30 if kind == "spear" else 22
            tipx, tipy = hx + L * 0.7 * s, hy - L * s
            self._line(hx, hy, tipx, tipy, "#7a5a2a" if kind != "sword" else steel,
                       width=max(1, int(2 * s)))
            if kind == "sword":
                self._line(hx - 3 * s, hy - 2 * s, hx + 5 * s, hy - 6 * s, "#b0863a",
                           width=max(1, int(2 * s)))                     # 護手
            elif kind == "axe":
                self._plg([tipx, tipy, tipx + 8 * s, tipy - 2 * s,
                           tipx + 8 * s, tipy + 8 * s, tipx, tipy + 6 * s], steel)
            else:  # spear
                self._plg([tipx - 1 * s, tipy, tipx + 4 * s, tipy - 1 * s,
                           tipx + 1 * s, tipy - 6 * s], steel)
        elif kind in ("staff", "wand"):
            L = 26 if kind == "staff" else 18
            tipx, tipy = hx + L * 0.6 * s, hy - L * s
            self._line(hx, hy, tipx, tipy, "#8a5a2a", width=max(1, int(2 * s)))
            self._ovl(tipx - 4 * s, tipy - 4 * s, tipx + 4 * s, tipy + 4 * s, "#7ad0ff")
            self._ovl(tipx - 1.5 * s, tipy - 1.5 * s, tipx + 1.5 * s, tipy + 1.5 * s, WHITE)
        elif kind == "bow":
            self._arc(hx - 2 * s, hy - 16 * s, hx + 14 * s, hy + 6 * s, -60, 150,
                      "#9a6a33", width=max(1, int(2 * s)))
            self._line(hx + 12 * s, hy - 14 * s, hx + 12 * s, hy + 4 * s, "#e8e8e8")
        elif kind == "crossbow":
            self._line(hx - 2 * s, hy, hx + 12 * s, hy - 8 * s, "#8a5a2a", width=max(1, int(2 * s)))
            self._line(hx + 3 * s, hy - 6 * s, hx + 9 * s, hy + 2 * s, "#6b4020", width=max(1, int(2 * s)))
        elif kind == "dagger":
            self._line(hx, hy, hx + 8 * s, hy - 10 * s, steel, width=max(1, int(2 * s)))

    # ============ 怪物像素畫 ============
    def _draw_monster(self, cx, fy, kind, target_h, hop, flash):
        # 優先使用貼圖
        img = self._spr(self._mon_src, kind, target_h)
        if img is not None:
            self._ovl(cx - target_h * 0.34, fy - 3,
                      cx + target_h * 0.34, fy + 5, LEAF_DK)      # 影子
            self.canvas.create_image(cx * S, (fy - hop) * S,
                                     anchor="s", image=img, tags="dyn")
            return
        # 像素備援
        shape, base = MKINDS.get(kind, ("slime", "#7ed957"))
        col = WHITE if flash > 0.5 else base
        dk = shade(base, 0.7)
        s = target_h / 40.0
        cx = int(cx)
        fy = int(fy)
        # 影子
        self._oval(cx - 16 * s, fy - 2, cx + 16 * s, fy + 4, "#3a5a2a")
        oy = -int(hop)

        def R(x, y, w, h, color, out=""):
            self._px(cx + x * s, fy + oy + y * s, w * s, h * s, color, out)

        def O(x0, y0, x1, y1, color, out=""):
            self._oval(cx + x0 * s, fy + oy + y0 * s, cx + x1 * s, fy + oy + y1 * s, color, out)

        def eyes(ex=3, ey=-14, r=1.6):
            self._oval(cx - (ex + r) * s, fy + oy + ey * s, cx - (ex - r) * s, fy + oy + (ey + 2 * r) * s, INK)
            self._oval(cx + (ex - r) * s, fy + oy + ey * s, cx + (ex + r) * s, fy + oy + (ey + 2 * r) * s, INK)

        if shape == "slime":
            O(-15, -20, 15, 2, col, dk)
            O(-15, -20, 15, -4, lerp_color(col, WHITE, 0.25))
            self._oval(cx - 6 * s, fy + oy - 16 * s, cx - 1 * s, fy + oy - 11 * s, INK)
            self._oval(cx + 1 * s, fy + oy - 16 * s, cx + 6 * s, fy + oy - 11 * s, INK)
            R(-4, -8, 8, 2, dk)                        # 嘴
        elif shape == "snail":
            R(-14, -6, 22, 6, "#c8a06a")               # 身體
            O(-6, -22, 12, 0, col, dk)                 # 殼
            O(-2, -18, 8, -6, lerp_color(col, WHITE, 0.3))
            R(-14, -12, 2, 6, "#c8a06a")               # 觸角
            self._oval(cx - 15 * s, fy + oy - 14 * s, cx - 11 * s, fy + oy - 10 * s, INK)
        elif shape == "mushroom":
            R(-4, -12, 8, 12, "#f0e2c0")               # 柄
            O(-14, -24, 14, -6, col, dk)               # 傘
            for sx in (-8, 0, 8):
                self._oval(cx + (sx - 2) * s, fy + oy - 20 * s, cx + (sx + 2) * s, fy + oy - 16 * s, WHITE)
            self._oval(cx - 5 * s, fy + oy - 9 * s, cx - 2 * s, fy + oy - 6 * s, INK)
            self._oval(cx + 2 * s, fy + oy - 9 * s, cx + 5 * s, fy + oy - 6 * s, INK)
        elif shape == "pig":
            O(-15, -18, 15, 0, col, dk)
            R(-4, -10, 8, 6, shade(col, 0.85))         # 鼻
            R(-2, -8, 2, 2, INK)
            R(1, -8, 2, 2, INK)
            self._poly([cx - 14 * s, fy + oy - 18 * s, cx - 8 * s, fy + oy - 22 * s, cx - 7 * s, fy + oy - 15 * s], col)
            self._poly([cx + 14 * s, fy + oy - 18 * s, cx + 8 * s, fy + oy - 22 * s, cx + 7 * s, fy + oy - 15 * s], col)
            eyes(6, -15, 1.4)
        elif shape == "bat":
            O(-9, -18, 9, -2, col, dk)                 # 身
            wf = math.sin(self.frame * 0.5) * 4
            self._poly([cx - 8 * s, fy + oy - 14 * s, cx - 22 * s, fy + oy + (-18 + wf) * s,
                        cx - 20 * s, fy + oy - 6 * s, cx - 8 * s, fy + oy - 8 * s], dk)
            self._poly([cx + 8 * s, fy + oy - 14 * s, cx + 22 * s, fy + oy + (-18 + wf) * s,
                        cx + 20 * s, fy + oy - 6 * s, cx + 8 * s, fy + oy - 8 * s], dk)
            self._poly([cx - 6 * s, fy + oy - 18 * s, cx - 3 * s, fy + oy - 24 * s, cx - 1 * s, fy + oy - 18 * s], col)
            self._poly([cx + 6 * s, fy + oy - 18 * s, cx + 3 * s, fy + oy - 24 * s, cx + 1 * s, fy + oy - 18 * s], col)
            eyes(3, -14, 1.4)
        elif shape == "ghost":
            O(-11, -22, 11, -4, col, "#c4c8e0")
            R(-11, -8, 22, 6, col)
            for gx in (-9, -3, 3):
                self._poly([cx + gx * s, fy + oy - 2 * s, cx + (gx + 3) * s, fy + oy - 6 * s,
                            cx + (gx + 6) * s, fy + oy - 2 * s], col)
            eyes(4, -16, 1.8)
            R(-2, -10, 4, 3, "#b0b4d0")
        elif shape == "stump":
            R(-11, -20, 22, 20, col, dk)
            R(-11, -20, 22, 4, shade(col, 1.2))
            for ry in (-14, -8):
                R(-11, ry, 22, 1, dk)
            self._poly([cx - 6 * s, fy + oy - 24 * s, cx - 10 * s, fy + oy - 30 * s, cx - 2 * s, fy + oy - 26 * s], GRASS_DK)
            self._poly([cx + 6 * s, fy + oy - 24 * s, cx + 10 * s, fy + oy - 30 * s, cx + 2 * s, fy + oy - 26 * s], GRASS_DK)
            eyes(4, -14, 1.6)
        elif shape == "golem":
            R(-16, -30, 32, 30, col, dk)
            R(-16, -30, 32, 5, shade(col, 1.2))
            R(-22, -22, 6, 16, dk)                     # 手臂
            R(16, -22, 6, 16, dk)
            self._oval(cx - 9 * s, fy + oy - 24 * s, cx - 4 * s, fy + oy - 19 * s, "#ff5d5d")
            self._oval(cx + 4 * s, fy + oy - 24 * s, cx + 9 * s, fy + oy - 19 * s, "#ff5d5d")
            R(-8, -10, 16, 3, INK)
        elif shape == "dragon":
            O(-16, -26, 16, -2, col, dk)               # 身
            O(6, -34, 22, -18, col, dk)                # 頭
            self._poly([cx + 20 * s, fy + oy - 30 * s, cx + 30 * s, fy + oy - 28 * s, cx + 20 * s, fy + oy - 24 * s], shade(col, 1.1))  # 吻
            self._poly([cx + 8 * s, fy + oy - 34 * s, cx + 12 * s, fy + oy - 44 * s, cx + 16 * s, fy + oy - 34 * s], dk)  # 角
            wf = math.sin(self.frame * 0.3) * 5
            self._poly([cx - 10 * s, fy + oy - 22 * s, cx - 30 * s, fy + oy + (-34 + wf) * s,
                        cx - 26 * s, fy + oy - 8 * s], shade(col, 0.85))          # 翅
            self._oval(cx + 12 * s, fy + oy - 30 * s, cx + 16 * s, fy + oy - 26 * s, GOLD)
        elif shape == "demon":
            wf = math.sin(self.frame * 0.25) * 4
            wing = shade(col, 0.6)
            # 大蝙蝠翼（身後）
            self._poly([cx - 10 * s, fy + oy - 26 * s, cx - 34 * s, fy + oy + (-40 + wf) * s,
                        cx - 30 * s, fy + oy + (-20 + wf) * s, cx - 26 * s, fy + oy - 24 * s,
                        cx - 24 * s, fy + oy - 10 * s, cx - 12 * s, fy + oy - 18 * s], wing)
            self._poly([cx + 10 * s, fy + oy - 26 * s, cx + 34 * s, fy + oy + (-40 + wf) * s,
                        cx + 30 * s, fy + oy + (-20 + wf) * s, cx + 26 * s, fy + oy - 24 * s,
                        cx + 24 * s, fy + oy - 10 * s, cx + 12 * s, fy + oy - 18 * s], wing)
            O(-14, -28, 14, -2, col, dk)
            self._poly([cx - 12 * s, fy + oy - 26 * s, cx - 18 * s, fy + oy - 40 * s, cx - 6 * s, fy + oy - 28 * s], dk)  # 角
            self._poly([cx + 12 * s, fy + oy - 26 * s, cx + 18 * s, fy + oy - 40 * s, cx + 6 * s, fy + oy - 28 * s], dk)
            self._oval(cx - 8 * s, fy + oy - 20 * s, cx - 3 * s, fy + oy - 15 * s, "#ffe14b")
            self._oval(cx + 3 * s, fy + oy - 20 * s, cx + 8 * s, fy + oy - 15 * s, "#ffe14b")
            for mx2 in (-6, -2, 2):
                self._poly([cx + mx2 * s, fy + oy - 8 * s, cx + (mx2 + 2) * s, fy + oy - 4 * s,
                            cx + (mx2 + 4) * s, fy + oy - 8 * s], WHITE)
        else:
            O(-14, -18, 14, 0, col, dk)
            eyes()

    # ============ 主繪製 ============
    def _render(self):
        c = self.canvas
        c.delete("dyn")
        s = self.state
        t = self.frame * FRAME_MS / 1000.0

        # 螢火微光（背景）
        for fl in self.fireflies:
            fx = fl["x"] + math.sin(t * fl["s"] + fl["p"]) * 10
            fy = fl["y"] + math.cos(t * fl["s"] * 0.7 + fl["p"]) * 6
            a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 3 + fl["p"]))
            self._oval(fx - 3, fy - 3, fx + 3, fy + 3, lerp_color(SKY_BOT, GLOW, a * 0.4))
            self._oval(fx - 1, fy - 1, fx + 1, fy + 1, lerp_color(GLOW, WHITE, a))

        mx = MON_X
        boss = s.is_boss
        target_h = MON_SPRITE_H_BOSS if boss else MON_SPRITE_H
        tgt = s.target()

        # 斬擊（朝目標，顏色依職業）
        if tgt is not None and self.lunge > 0.3:
            txp, typ = self._mon_pos(s.monsters.index(tgt))
            a = self.lunge
            self._arc(txp - 30, typ - 34, txp + 6, typ + 2, 30, 130,
                      lerp_color("#ffffff", self._hit_color(), a), width=int(2 + 3 * a))

        # 勇者（前景·左下）
        bob = math.sin(t * 3) * 2
        self._draw_hero(HERO_X, HERO_FY, s.vis, bob, self.lunge)

        # 火花（顏色依職業）
        for p in self.sparks:
            k = p["life"] / p["maxlife"]
            r = 2 + 2 * k
            self._oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r,
                       lerp_color(p.get("col", "#ffcf47"), "#ffffff", k))

        # 每隻怪物 + 名稱/血條（腳底下方）；目標較亮
        for i, m in enumerate(s.monsters):
            if m["hp"] <= 0:
                continue
            cx, fy = self._mon_pos(i)
            hop = abs(math.sin(t * 4 + i * 1.3)) * (2 if boss else 4)
            flash = self.hitflash if m is tgt else 0.0
            self._draw_monster(cx, fy, m["kind"], target_h, hop, flash)
            by = fy + 5
            nmcol = GOLD if boss else (WHITE if m is tgt else "#c2cadf")
            self._text(cx, by, m["name"], color=nmcol, size=10 if boss else 8)
            bw = 130 if boss else 62
            self._bar(cx - bw / 2, by + (10 if boss else 8), bw, 5,
                      m["disp"] / m["max_hp"], "#ff4d4d", "#ff9a9a")
            if boss:
                self._text(cx, by + 13, f"{max(0,int(m['disp'])):,}/{m['max_hp']:,}",
                           size=6, outline="")

        # 左上：關卡進度 + 等級 + 職業（各自一行，避免擁擠）
        stage_txt = ("⚔ 最終BOSS戰" if boss else f"🗺 {s.stage}/{FINAL_STAGE}")
        self._text(12, 11, stage_txt, color="#ffe9a8", size=10, anchor="w")
        self._text(12, 27, f"Lv.{s.level}", color=GOLD, size=11, anchor="w")
        self._text(12, 41, s.class_name, color="#eaf0ff", size=9, anchor="w")

        # 右上：金幣 + 攻擊 + 累計鍵
        rx = BAR_W - 12
        self._oval(rx - 92, 6, rx - 82, 16, GOLD, "#a8791f")
        self._text(rx - 87, 11, "$", color="#7a5a10", size=7, outline="")
        self._text(rx - 78, 11, f"{s.gold:,}", color="#fff0b0", size=10, anchor="w")
        self._text(rx, 27, f"⚔ {s.atk}   ⌨ {s.total_keys:,}", color="#dfe6ff", size=9, anchor="e")

        # 連擊（中上）
        if self.combo >= 2:
            mult = s.combo_multiplier(self.combo)
            csz = int(13 + self.combo_pulse * 7)
            self._text(BAR_W * 0.5, 12, f"COMBO {self.combo}", color=GOLD, size=csz, font=PIXEL_FONT)
            self._text(BAR_W * 0.5, 26, f"x{mult:.2f}", color="#ffd35c", size=9)

        # 技能充能條（左側，等級/職業下方）
        sk = skill_of(s.class_id)
        if sk:
            cost = SKILL_COST.get(s.class_id, 100)
            frac = min(1.0, self.skill_gauge / cost)
            self._bar(12, 52, 116, 6, frac, sk[3], lerp_color(sk[3], WHITE, 0.4), bg="#20263f")
            self._text(70, 55, sk[0], size=6, outline="")

        # 提示（屬性點 / 技能點 / 轉職）
        hint = []
        if s.attr_points > 0:
            hint.append(f"⭐{s.attr_points}屬性")
        if s.skill_points > 0:
            hint.append(f"✨{s.skill_points}技能")
        if self._class_options():
            hint.append("🎖轉職")
        if hint:
            blink = 0.5 + 0.5 * math.sin(t * 5)
            self._text(rx, 44, "、".join(hint) + "（右鍵）",
                       color=lerp_color("#dfe6ff", GOLD, blink), size=9, anchor="e")

        # EXP 底條（滿版）
        self._bar(6, BAR_H - 8, BAR_W - 12, 4, self._disp_exp / s.exp_to_next,
                  "#4bd06a", "#a8f0b8", bg="#123a26")
        self._text(BAR_W / 2, BAR_H - 6, f"EXP {int(self._disp_exp):,}/{s.exp_to_next:,}",
                   size=6, outline="")

        # 技能釋放光環
        if self.skill_flash > 0:
            a = self.skill_flash
            rad = (1 - a) * 40 + 10
            self._ovl(MON_X - rad, (MON_FY - 22) - rad * 0.7,
                      MON_X + rad, (MON_FY - 22) + rad * 0.7, "",
                      outline=lerp_color(SKY_BOT, self.skill_color, a), width=int(1 + 3 * a))

        # 升級光芒（環繞玩家）
        if self.lvlup > 0:
            self._draw_lvlup(HERO_X, HERO_FY - 30, self.lvlup)

        # 浮動傷害字
        for f in self.floats:
            k = f["life"] / f["maxlife"]
            pop = 1.25 - 0.25 * k if k > 0.7 else 1.0
            sz = max(6, int(f["size"] * (0.6 + 0.4 * min(1, (1 - k) * 4)) * pop))
            col = f["color"] if k > 0.35 else lerp_color(SKY_BOT, f["color"], k / 0.35)
            self._text(f["x"], f["y"], f["text"], color=col, size=sz, font=PIXEL_FONT)

        # 橫幅
        if self.banner:
            txt, tmr = self.banner
            k = min(1.0, tmr / 1.4)
            self._text(mx, 26, txt, color=lerp_color(SKY_BOT, GOLD, min(1, k * 1.6)),
                       size=int(15 + (1 - k) * 3), font=PIXEL_FONT)

        # 勝利結算畫面
        if s.finished:
            self._rect(3, 3, BAR_W - 3, BAR_H - 3, "#0a0f14")
            self._rect(3, 3, BAR_W - 3, BAR_H - 3, "", outline=GOLD, width=2)
            self._text(BAR_W / 2, 24, "🏆 討伐成功！羊頭人已被擊敗", color=GOLD,
                       size=15, font=PIXEL_FONT)
            self._text(BAR_W / 2, 50,
                       f"等級 {s.level}    擊殺 {s.kills}    最大連擊 {s.max_combo}",
                       color=WHITE, size=11)
            self._text(BAR_W / 2, 72,
                       f"總敲擊 {s.total_keys:,}    金幣 {s.gold:,}    職業 {s.class_name}",
                       color="#dfe6ff", size=11)
            blink = 0.5 + 0.5 * math.sin(t * 4)
            self._text(BAR_W / 2, 100, "右鍵 →「🔄 重新開始本局」展開新冒險",
                       color=lerp_color("#8090b0", GOLD, blink), size=11)

    def _draw_lvlup(self, cx, cy, k):
        n = 12
        rad = (1 - k) * 40 + 8
        for i in range(n):
            ang = math.tau * i / n + (1 - k) * 2
            x = cx + math.cos(ang) * rad
            y = cy + math.sin(ang) * rad * 0.6
            r = 2 + 2 * k
            self._oval(x - r, y - r, x + r, y + r, lerp_color(SKY_BOT, GOLD, k))
        self._ovl(cx - rad, cy - rad * 0.6, cx + rad, cy + rad * 0.6, "",
                  outline=lerp_color(SKY_BOT, "#fff6c0", k), width=2)

    # ============ 彈出視窗（背景圖 + Canvas）============
    def _panel_bg_photo(self, w, h):
        try:
            from PIL import Image, ImageTk, ImageEnhance
        except ImportError:
            return None
        if not os.path.exists(PANEL_BG):
            return None
        if getattr(self, "_panel_src", None) is None:
            try:
                self._panel_src = Image.open(PANEL_BG).convert("RGB")
            except Exception:
                self._panel_src = False
        if not self._panel_src:
            return None
        iw, ih = self._panel_src.size
        sc = max(w / iw, h / ih)
        im = self._panel_src.resize((max(w, int(iw * sc)), max(h, int(ih * sc))), Image.LANCZOS)
        im = im.crop((0, 0, w, h))
        im = ImageEnhance.Brightness(im).enhance(0.5)   # 壓暗、提升可讀性
        return ImageTk.PhotoImage(im)

    def _panel_top(self, title, w, h):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.attributes("-topmost", True)
        top.configure(bg="#0c1116")
        # 多個面板同時開時錯開，不要疊在一起
        n_open = sum(1 for a in ("inv_win", "shop_win", "ach_win")
                     if getattr(self, a, None) and tk.Toplevel.winfo_exists(getattr(self, a)))
        px = self.root.winfo_x() + 20 + n_open * 34
        py = max(20, self.root.winfo_y() - h - 10 + n_open * 28)
        top.geometry(f"{w}x{h}+{px}+{py}")
        cv = tk.Canvas(top, width=w, height=h, highlightthickness=0, bg="#0c1116")
        cv.pack(fill="both", expand=True)
        ph = self._panel_bg_photo(w, h)
        if ph is not None:
            cv._bg = ph
            cv.create_image(0, 0, anchor="nw", image=ph)
        top._cv = cv
        top._pw = w   # 面板寬度（不可叫 _w，那是 Tkinter 內部的 widget 路徑名）
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        # ESC 關閉：綁在視窗與畫布上，並額外在主視窗做 app 級綁定（見 _build_window），
        # 這樣不論鍵盤焦點落在面板、按鈕還是 HUD 上都關得掉。
        for wdg in (top, cv):
            wdg.bind("<Escape>", lambda e: self._close_panels())
        cv.configure(takefocus=True)
        # 面板是從右鍵選單開的；選單放開 grab 時會把焦點還給原視窗，
        # 因此要延後再搶焦點，否則 focus_force() 會被蓋掉、ESC 收不到。
        top.after(80, lambda: self._grab_panel_focus(top))
        return top

    def _grab_panel_focus(self, top):
        try:
            if not tk.Toplevel.winfo_exists(top):
                return
            top.lift()
            top.focus_force()
            top._cv.focus_set()
        except tk.TclError:
            pass

    def _close_panels(self):
        """關掉所有開著的面板，回傳是否有關到東西。"""
        closed = False
        for attr in ("inv_win", "shop_win", "ach_win"):
            win = getattr(self, attr, None)
            try:
                if win and tk.Toplevel.winfo_exists(win):
                    win.destroy()
                    closed = True
            except tk.TclError:
                pass
            setattr(self, attr, None)
        return closed

    def _add_close(self, top):
        """在面板右上角加一個 ✕ 關閉鈕（每次重繪都要呼叫）。"""
        b = tk.Button(top._cv, text="✕", bg="#7a2f2f", fg="#fff", relief="flat", bd=0,
                      activebackground="#a04040", font=(UI_FONT, 9, "bold"),
                      command=top.destroy)
        top._cv.create_window(top._pw - 6, 6, window=b, anchor="ne", width=24, height=22)

    def _cv_text(self, cv, x, y, txt, fg="#f2ecd6", size=10, bold=True, anchor="w"):
        f = (UI_FONT, size, "bold" if bold else "normal")
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cv.create_text(x + dx, y + dy, text=txt, fill="#000000", font=f, anchor=anchor)
        cv.create_text(x, y, text=txt, fill=fg, font=f, anchor=anchor)

    def _cv_button(self, cv, x, y, txt, cmd, bg="#b8862f", fg="#fff", w=44):
        b = tk.Button(cv, text=txt, bg=bg, fg=fg, relief="flat", bd=0,
                      activebackground=shade(bg, 1.2), font=(UI_FONT, 8, "bold"), command=cmd)
        cv.create_window(x, y, window=b, anchor="e", width=w, height=20)

    def _open_inventory(self):
        if self.inv_win and tk.Toplevel.winfo_exists(self.inv_win):
            self.inv_win.destroy()
        self.inv_win = self._panel_top("🎒 裝備 / 背包", 480, 440)
        self._build_inventory(self.inv_win)

    def _clear_panel(self, cv):
        """清空面板：連同嵌在 canvas 上的按鈕一起銷毀（不然每次重繪會累積）。"""
        for child in cv.winfo_children():
            child.destroy()
        cv.delete("all")
        ph = getattr(cv, "_bg", None)
        if ph is not None:
            cv.create_image(0, 0, anchor="nw", image=ph)

    def _refresh_inventory(self):
        if self.inv_win and tk.Toplevel.winfo_exists(self.inv_win):
            self._clear_panel(self.inv_win._cv)
            self._build_inventory(self.inv_win)

    def _purge_unusable_weapons(self):
        """把背包（含身上）不符目前職業的武器自動分解換金幣，回傳 (件數, 金幣)。"""
        s = self.state
        keep, gold, n = [], 0, 0
        for it in s.inventory:
            if it.get("type") == "weapon" and not can_equip(it, s.class_id):
                gold += salvage_value(it)
                n += 1
            else:
                keep.append(it)
        if n:
            s.inventory = keep
        # 轉職後身上那把可能也不能用了
        if s.weapon and not can_equip(s.weapon, s.class_id):
            gold += salvage_value(s.weapon)
            n += 1
            s.weapon = None
        if gold:
            s.gold += gold
        return n, gold

    def _build_inventory(self, top):
        s = self.state
        cv = top._cv
        purged, pg = self._purge_unusable_weapons()
        self._cv_text(cv, 16, 18, "🎒 裝備 / 背包", GOLD, 13)
        if purged:
            self._cv_text(cv, 150, 18, f"（自動分解 {purged} 件不符職業裝備 +{pg}G）",
                          "#ffb0a0", 8)
        self._cv_text(cv, 16, 40, "── 目前裝備 ──", "#ffd98a", 10)
        yy = 60
        for slot, tag in (("weapon", "🗡 武器"), ("accessory", "💍 飾品")):
            item = getattr(s, slot)
            if item:
                col = rarity_of(item["rarity"])[2]
                self._cv_text(cv, 26, yy, f"{tag}：{item['name']}（{item_stat_text(item)}）", col, 9)
            else:
                self._cv_text(cv, 26, yy, f"{tag}：（無）", "#9aa0b0", 9)
            yy += 20
        grp = {"warrior": "劍系", "mage": "法系", "archer": "弓系", "thief": "盜系"}[class_group(s.class_id)]
        self._cv_text(cv, 16, yy + 4, f"── 背包（{len(s.inventory)}/{INVENTORY_CAP}）　可用武器：{grp} ──",
                      "#ffd98a", 10)
        yy += 26
        if not s.inventory:
            self._cv_text(cv, 26, yy, "（空空如也，去打怪掉寶吧！）", "#9aa0b0", 9)
        for idx, item in sorted(enumerate(s.inventory), key=lambda p: -item_score(p[1])):
            if yy > top._pw and False:
                break
            col = rarity_of(item["rarity"])[2]
            usable = can_equip(item, s.class_id)
            self._cv_text(cv, 26, yy, item["name"], col, 9)
            self._cv_text(cv, 150, yy, item_stat_text(item), "#c7cfe0", 8)
            self._cv_button(cv, top._pw - 12, yy, "分解", lambda i=idx: self._salvage(i), bg="#7a4030")
            if usable:
                self._cv_button(cv, top._pw - 60, yy, "裝備", lambda i=idx: self._equip(i), bg="#b8862f")
            else:
                self._cv_text(cv, top._pw - 62, yy, "✖不符職業", "#ff8a8a", 8, anchor="e")
            yy += 22
            if yy > 428:
                break
        self._add_close(top)

    def _equip(self, idx):
        s = self.state
        if idx >= len(s.inventory):
            return
        item = s.inventory[idx]
        if not can_equip(item, s.class_id):
            return                          # 不符職業，無法裝備
        s.inventory.pop(idx)
        slot = "weapon" if item["type"] == "weapon" else "accessory"
        cur = getattr(s, slot)
        setattr(s, slot, item)
        if cur:
            s.inventory.append(cur)
        self._refresh_inventory()

    def _salvage(self, idx):
        s = self.state
        if idx >= len(s.inventory):
            return
        s.gold += salvage_value(s.inventory.pop(idx))
        self._refresh_inventory()

    # ---------- 商店 ----------
    def _shop_prices(self):
        lv = self.state.level
        return {"weapon": 80 + lv * 30, "accessory": 80 + lv * 30, "skill": 200 + lv * 20}

    def _open_shop(self):
        if self.shop_win and tk.Toplevel.winfo_exists(self.shop_win):
            self.shop_win.destroy()
        self.shop_win = self._panel_top("🏪 商店", 480, 300)
        self._build_shop(self.shop_win)

    def _refresh_shop(self):
        if self.shop_win and tk.Toplevel.winfo_exists(self.shop_win):
            self._clear_panel(self.shop_win._cv)
            self._build_shop(self.shop_win)

    def _build_shop(self, top):
        s = self.state
        cv = top._cv
        p = self._shop_prices()
        self._cv_text(cv, 16, 18, "🏪 商店", GOLD, 13)
        self._cv_text(cv, top._pw - 40, 18, f"💰 {s.gold:,}", "#fff0b0", 11, anchor="e")
        grp = {"warrior": "劍系", "mage": "法系", "archer": "弓系", "thief": "盜系"}[class_group(s.class_id)]
        rows = [
            (f"🗡 隨機武器（{grp}·符合職業）", p["weapon"], "buy_weapon"),
            ("💍 隨機飾品", p["accessory"], "buy_acc"),
            ("✨ 技能點 ×1", p["skill"], "buy_skill"),
        ]
        yy = 56
        for label, price, act in rows:
            afford = s.gold >= price
            self._cv_text(cv, 26, yy, label, "#f2ecd6", 10)
            self._cv_text(cv, 300, yy, f"{price:,} G", "#ffd98a" if afford else "#8a7a5a", 10)
            self._cv_button(cv, top._pw - 14, yy, "購買" if afford else "金幣不足",
                            (lambda a=act, pr=price: self._buy(a, pr)) if afford else (lambda: None),
                            bg="#b8862f" if afford else "#555", w=64)
            yy += 34
        self._cv_text(cv, 16, yy + 6, "＊武器只會賣符合你職業的類型；買到的裝備進背包。",
                      "#c7cfe0", 8)
        self._cv_text(cv, 16, yy + 22, "＊ESC 或右上 ✕ 可關閉視窗。", "#c7cfe0", 8)
        self._add_close(top)

    def _buy(self, act, price):
        s = self.state
        if s.gold < price:
            return
        s.gold -= price
        if act == "buy_skill":
            s.skill_points += 1
            self.banner = ("購買技能點 +1", 1.2)
        elif act == "buy_weapon":
            item = generate_item(max(1, s.level), False, 1, force_type="weapon",
                                 group=class_group(s.class_id))
            self._to_inventory(item)
            self.banner = (f"購入 {item['name']}", 1.2)
        else:
            item = generate_item(max(1, s.level), False, 1, force_type="accessory")
            self._to_inventory(item)
            self.banner = (f"購入 {item['name']}", 1.2)
        self._refresh_shop()
        self._refresh_inventory()

    def _open_achievements(self):
        if self.ach_win and tk.Toplevel.winfo_exists(self.ach_win):
            self.ach_win.destroy()
        self.ach_win = self._panel_top("🏆 成就", 440, 500)
        s = self.state
        cv = self.ach_win._cv
        self._cv_text(cv, self.ach_win._pw / 2, 18,
                      f"🏆 成就　已解鎖 {len(s.achievements)} / {len(ACHIEVEMENTS)}",
                      GOLD, 12, anchor="center")
        yy = 42
        for a in ACHIEVEMENTS:
            cur, target = a["goal"](s)
            got = a["id"] in s.achievements
            self._cv_text(cv, 18, yy, f"{'✅' if got else '🔒'} {a['icon']} {a['name']}",
                          (GOLD if got else "#aab0c0"), 10)
            self._cv_text(cv, self.ach_win._pw - 16, yy,
                          ("完成" if got else f"{min(cur,target):,}/{target:,}"),
                          "#c7cfe0", 9, anchor="e")
            yy += 24
        self._add_close(self.ach_win)

    # ---------- 存讀檔 ----------
    def load(self):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                self.state.load_dict(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _keep_on_top(self):
        # 週期性重新宣告置頂，避免被其他視窗蓋掉
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
        except tk.TclError:
            pass
        self.root.after(1500, self._keep_on_top)

    def _autosave(self):
        self.save()
        self.root.after(20000, self._autosave)

    def _on_close(self):
        self.save()
        if self.listener:
            self.listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = TypingRPG(root)
    root.mainloop()
