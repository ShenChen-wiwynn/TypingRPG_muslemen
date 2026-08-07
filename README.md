# 打字 RPG（TypingRPG）

一條停在**工作列正上方**的無邊框橫條 HUD。你在**任何軟體**打字都會累積戰力 ——
每敲一鍵＝對怪物揮一刀，自動闖關、升級、掉裝、轉職、解成就。

> 只統計「敲了幾下」，**不記錄敲了什麼內容**，也不連網。

---

## 1. 開始遊戲

### 方式 A：直接跑 exe（給別人玩、或自己懶得裝 Python）

雙擊 `dist\TypingRPG.exe` 即可，**不需要安裝 Python 或任何套件**。

- 第一次啟動要等 **5～8 秒**（單檔 exe 要先把內容解壓到暫存區），期間畫面上完全沒有反應，別急著連點，不然會開出好幾個實例。
- 存檔 `save.json` 會生在 **exe 同一個資料夾**，所以請放在可寫入的位置（桌面、文件夾）。

### 方式 B：跑原始碼（開發／改數值時用）

```bash
pythonw "C:\Users\11411612\TypingRPG\typing_rpg.py"
```

用 `pythonw` 而不是 `python`，才不會多一個黑色終端機視窗。

需求：Python 3.13＋以下套件

```bash
pip install pynput pillow
```

- `pynput`：全域鍵盤統計（沒有它就只有視窗聚焦時才算數）
- `pillow`：背景圖與角色／怪物貼圖（沒有它會退回內建手繪像素）

---

## 2. 操作

| 操作 | 功能 |
|---|---|
| 在任何地方打字 | 攻擊怪物（連續敲擊會累積連擊倍率，停 2 秒歸零）|
| **左鍵拖曳** HUD | 移動位置（會記進存檔）|
| **右鍵** HUD | 選單：加屬性點／升技能／轉職／背包／商店／成就／難度／音效／縮放／置中／離開 |
| **ESC** | 關閉背包、商店、成就面板（不在遊戲視窗上也有效）|
| **Ctrl + Alt + `+` / `-` / `0`** | 放大／縮小／還原（全域快捷鍵）|

**遊戲流程**：Lv.10 一轉（劍士／法師／弓箭手／盜賊）、Lv.30 二轉；打滿 40 關會遇到最終 BOSS。
不符合職業的武器會**自動分解換金幣**（掉寶時、進背包時、轉職時都會處理，轉職後身上那把也會一併分解）。

---

## 3. 打包成 exe

需求（一次性）：

```bash
pip install pyinstaller pynput pillow
```

然後在專案資料夾雙擊 **`build.bat`** 就好。它會清掉舊的 `build\`、`dist\`、`.spec` 再重新打包，輸出在 `dist\TypingRPG.exe`（約 25 MB）。

等價的手動指令：

```bash
pyinstaller --onefile --noconsole --name TypingRPG --add-data "assets;assets" --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 typing_rpg.py
```

**`--add-data "assets;assets"` 不能少** —— 少了它，背景圖和所有角色／怪物貼圖都不會進 exe，遊戲會安靜地退回內建手繪版，看起來像「美術全部不見了」。

其他注意事項：

- 改了 `typing_rpg.py` 之後 **exe 不會自己更新**，要重跑 `build.bat`。
- `build\` 是打包中間產物，可以隨時整個刪掉。
- 打包前先把遊戲關掉，不然 `dist\TypingRPG.exe` 會被鎖住寫不進去。

---

## 4. 提供給他人

### 要壓縮哪些檔案

**只要 `dist\TypingRPG.exe` 這一個檔案。** 貼圖、背景、Python 直譯器全都已經包在裡面了。

不要整個資料夾壓下去：

| 項目 | 要給嗎 | 原因 |
|---|---|---|
| `dist\TypingRPG.exe` | ✅ **只要這個** | 完全獨立可執行 |
| `build\` | ❌ | 打包中間產物，將近 30 MB 的垃圾 |
| `assets\` | ❌ | 已經內嵌進 exe |
| `save.json` | ❌ | **你的存檔**，附上去對方會直接繼承你的進度 |
| `typing_rpg.py`、`tools\`、`__pycache__\`、`.spec` | ❌ | 開發用；除非你要給的是原始碼版 |

做法：新建一個空資料夾 → 把 `TypingRPG.exe` 複製進去 → 對資料夾按右鍵「壓縮成 ZIP 檔案」。

### 對方拿到之後要做什麼

1. **先解壓縮出來**，不要在壓縮檔預覽視窗裡直接雙擊 —— 那樣會解到暫存資料夾，存檔跟著被清掉。
2. 放在**可寫入**的位置（桌面、文件）。**不要**放 `C:\Program Files` 或唯讀的網路磁碟：存檔寫在 exe 同目錄，而且寫入失敗時程式是**靜默跳過**的，會玩得很開心但完全存不了檔。
3. 雙擊 `TypingRPG.exe`。就這樣，不用裝任何東西（64 位元 Windows 即可）。

### 一定要先告訴對方的三件事

- **SmartScreen**：exe 沒有數位簽章，第一次會跳「Windows 已保護您的電腦」，要點「其他資訊 → 仍要執行」。
- **防毒可能誤判**：PyInstaller 單檔封裝 ＋ 全域鍵盤 hook，正好是 keylogger 的典型特徵，被隔離的機率不低，可能要請對方加例外。順帶把「只統計次數、不記錄內容、不連網」講清楚，對方看到警告才不會誤會。
- **遊戲長什麼樣**：它是工作列正上方的無邊框橫條，**不是一般視窗，工作列上也不會有圖示**。很多人第一次會找不到，記得附上第 2 節的操作表。

### 如果要給的是原始碼版

附 `typing_rpg.py` ＋ `assets\` ＋ `build.bat` ＋ 這份 README，並刪掉 `build\`、`dist\`、`__pycache__\`、`save.json`。對方需要 Python 3.13 和 `pip install pynput pillow`。

---

## 5. 調平衡數值

所有數值集中在 `typing_rpg.py` 開頭的「平衡數值」區（約第 57～92 行），改完存檔重開即可（跑 exe 的話要重新打包）。

常用的幾個：

| 常數 | 目前值 | 說明 |
|---|---|---|
| `MONSTER_BASE_HP` | `4800` | 怪物血量基準（原始 12，先後兩次 ×20）|
| `DIFFICULTIES` | 平緩 1.11／標準 1.14／硬核 1.18 | 每關血量成長率，可在右鍵選單切換 |
| `MONSTERS_PER_STAGE` | `3` | 每關小怪數 |
| `FINAL_STAGE` | `40` | 第幾關是最終 BOSS |
| `BASE_ATK` / `LVUP_ATK` | `3` / `2` | 初始攻擊力／每級成長 |
| `COMBO_STEP` / `COMBO_MAX` | `0.02` / `100` | 連擊每段加成／上限（滿連擊＝ 3 倍傷害）|
| `DROP_CHANCE` | `0.20` | 掉寶率 |
| `INVENTORY_CAP` | `12` | 背包格數（滿了自動分解最弱的）|

以目前 `MONSTER_BASE_HP = 4800`，理論值大約是：清完第 1 關約 **1,600 下**；標準難度全破約 **6.7 萬下**（有加屬性點），硬核難度約 **20 萬下**。

---

## 6. 專案結構

```
TypingRPG\
├─ typing_rpg.py      主程式（單檔）
├─ build.bat          打包腳本
├─ save.json          你的存檔（跑原始碼時）
├─ assets\
│  ├─ forest_bg.png   HUD 背景
│  ├─ panel_bg.png    背包／商店面板背景
│  ├─ classes\        各職業角色貼圖
│  └─ monsters\       怪物貼圖
├─ tools\             貼圖去背／裁切腳本
└─ dist\TypingRPG.exe 打包輸出（＋它自己的 save.json）
```

---

## 7. 改程式時的兩個地雷

留給未來的自己：

- **不要把自訂屬性命名為 `_w`**（例如拿來存面板寬度）。`_w` 是 Tkinter 存 widget 路徑名的內部欄位，覆蓋掉之後該視窗的每一個 Tk 呼叫都會丟 `TclError`，而且因為是 `--noconsole` / `pythonw`，你**完全看不到 traceback**，只會看到「視窗開了但一片空白、ESC 也關不掉」。面板寬度現在叫 `_pw`。
- **`shade()` 早期只吃六位數 hex**，傳 `#555` 這種三位數會 `ValueError` 炸掉整個面板繪製（商店「金幣不足」的灰按鈕就踩過）。現在已支援三位數並在無法解析時原色回傳，但自訂顏色時仍建議統一寫六位數。

除錯小技巧：懷疑 GUI 有安靜的例外時，改用 `python`（不是 `pythonw`）從終端機跑，traceback 才看得到。
