@echo off
rem ============================================================
rem  Build AvtoServis.exe (Windows). Requires Python 3.10+ and internet.
rem  Result: dist\AvtoServis.exe (single file, no Python needed to run)
rem ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Installing PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto fail

echo [2/3] Building exe...
python -m PyInstaller --noconfirm --clean --onefile --name AvtoServis app.py
if errorlevel 1 goto fail

echo [3/3] Done.
echo.
echo Your program: %~dp0dist\AvtoServis.exe
echo The database file autoservice.db will be created next to the exe on first start.
pause
exit /b 0

:fail
echo.
echo Build failed. See messages above.
pause
exit /b 1
