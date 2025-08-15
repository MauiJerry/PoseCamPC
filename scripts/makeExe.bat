@echo off
setlocal
if not exist .venv\Scripts\activate.bat (
  echo venv missing. Run scripts\setup.bat first.
  exit /b 1
)
call .venv\Scripts\activate.bat
pyinstaller --onefile  --add-data ".venv\Lib\site-packages\mediapipe\modules;mediapipe/modules"  poseCamPC.py
