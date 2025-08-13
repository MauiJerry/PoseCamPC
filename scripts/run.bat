@echo off
setlocal
if not exist .venv\Scripts\activate.bat (
  echo venv missing. Run scripts\setup.bat first.
  exit /b 1
)
call .venv\Scripts\activate.bat
python -X faulthandler -m pip --version >NUL 2>&1
if errorlevel 1 (
  echo venv seems broken; re-run scripts\setup.bat
  exit /b 1
)
python poseCamPC.py
