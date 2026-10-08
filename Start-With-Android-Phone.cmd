@echo off
cd /d "%~dp0"
py -3 server.py --phone
if errorlevel 1 pause
