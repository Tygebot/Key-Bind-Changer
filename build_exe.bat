@echo off
REM Builds a standalone KeyBindChanger.exe with PyInstaller. Run this on
REM Windows, from this folder (the one containing main.py).
REM
REM The result is dist\KeyBindChanger.exe -- a single file you can copy
REM anywhere and run directly, without needing Python installed.

echo.
echo === KeyBind Changer - building KeyBindChanger.exe ===
echo.

python -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

echo Installing/checking app dependencies...
python -m pip install -r requirements.txt

echo.
echo Building (this can take a minute)...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name KeyBindChanger ^
    --icon icon.ico ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    main.py

echo.
if exist dist\KeyBindChanger.exe (
    echo Done! Your executable is at: dist\KeyBindChanger.exe
) else (
    echo Something went wrong -- scroll up for the PyInstaller error.
)
echo.
pause
