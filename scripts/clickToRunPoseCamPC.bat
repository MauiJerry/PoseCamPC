@echo off
REM Change to the directory where this batch file resides
cd /d "%~dp0"

REM Go up one level to the Python source directory
cd ..

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

echo PoseCamPC exited. waiting to close terminal window
pause
