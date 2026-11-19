@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -Command ". '.\scripts\environment.ps1'; & '.\.venv312\Scripts\python.exe' '.\scripts\replay_walk.py'"
if errorlevel 1 pause
endlocal
