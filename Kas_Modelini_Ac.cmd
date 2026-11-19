@echo off
setlocal
cd /d "%~dp0"
set "TEMP=%~dp0.runtime\temp"
set "TMP=%TEMP%"
set "TMPDIR=%TEMP%"
set "APPDATA=%~dp0.runtime\appdata"
set "LOCALAPPDATA=%~dp0.runtime\localappdata"
if not exist "%TEMP%" mkdir "%TEMP%"
start "" /D "%~dp0" "%~dp0programs\mujoco-3.17.0\bin\simulate.exe" "%~dp0vendor\MS-Human-700\MS-Human-700-Locomotion.xml"
endlocal
