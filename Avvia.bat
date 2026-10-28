@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "Movie Downloader" ".venv\Scripts\pythonw.exe" main.py
