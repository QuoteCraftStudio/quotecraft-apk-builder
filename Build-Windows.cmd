@echo off
setlocal
cd /d "%~dp0"
echo Packaging QuoteCraft APK Builder for Windows...
py -3 -m venv .packaging-env
if errorlevel 1 goto failed
".packaging-env\Scripts\python.exe" -m pip install "pyinstaller==6.22.3"
if errorlevel 1 goto failed
".packaging-env\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name QuoteCraft-APK-Builder --add-data "web;web" --add-data "templates;templates" desktop.py
if errorlevel 1 goto failed
if not exist "dist\QuoteCraft-APK-Builder.exe" goto failed
echo.
echo Finished: dist\QuoteCraft-APK-Builder.exe
echo This EXE includes Python. Android build tools are still installed separately.
explorer "%cd%\dist"
pause
exit /b 0
:failed
echo.
echo Packaging failed. Read the error above.
pause
exit /b 1
