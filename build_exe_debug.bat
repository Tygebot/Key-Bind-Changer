@echo off
REM Same as build_exe.bat, but keeps the console window open so you can see
REM the live debug log while the app runs (useful while troubleshooting --
REM debug.log under %%APPDATA%%\KeyBindChanger always has this too, with
REM or without a console).

echo.
echo === KeyBind Changer - building KeyBindChanger-debug.exe (console build) ===
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
python -m PyInstaller --noconfirm --onefile --console ^
    --name KeyBindChanger-debug ^
    --icon icon.ico ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    main.py

echo.
if exist dist\KeyBindChanger-debug.exe (
    echo Done! Your executable is at: dist\KeyBindChanger-debug.exe
) else (
    echo Something went wrong -- scroll up for the PyInstaller error.
)
echo.
pause
