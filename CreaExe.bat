@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\build_release.py
set "BUILD_RESULT=%errorlevel%"
pause
exit /b %BUILD_RESULT%
