@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -Command ". '.\scripts\environment.ps1'; $env:OMP_NUM_THREADS='1'; & '.\.venv312\Scripts\python.exe' '.\scripts\dashboard_server.py'"
if errorlevel 1 pause
endlocal
