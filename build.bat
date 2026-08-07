@echo off
REM ============================================================
REM  打包 打字 RPG 成單一 .exe（免安裝 Python 即可執行）
REM  需求：pip install pyinstaller pynput
REM ============================================================
cd /d "%~dp0"

echo [1/2] 清理舊的 build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TypingRPG.spec del /q TypingRPG.spec

echo [2/2] 開始打包...
REM  --add-data "assets;assets" 把背景圖 / 角色 / 怪物貼圖內嵌進 exe，
REM  少了它 exe 會退回內建手繪版（res_path 會先找 PyInstaller 的 _MEIPASS）
REM  --icon 指定 exe 圖示；ico 要放在專案根目錄，放 dist\ 會被上面的清理步驟刪掉
pyinstaller --onefile --noconsole --name TypingRPG ^
    --icon "TypingRPG.ico" ^
    --add-data "assets;assets" ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    typing_rpg.py

echo.
echo ============================================================
echo  完成！執行檔在： dist\TypingRPG.exe
echo  （雙擊即可玩，存檔 save.json 會生在 exe 同目錄）
echo ============================================================
pause
