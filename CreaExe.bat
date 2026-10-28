@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name MovieDownloader --add-binary "bin\yt-dlp.exe;bin" main.py
pause
