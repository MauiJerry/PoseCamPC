REM test_roundtrip.bat
@echo off
setlocal
pushd "%~dp0\.." >NUL 2>&1
if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] venv missing. Run scripts\setup.bat first.
  exit /b 1
)
REM Start RX in a new terminal window
start "PoseCamPC RX" cmd /k "call .venv\Scripts\activate.bat && python preflight_rx.py --osc-port 5005 --ndi-source PosePC-Test"
REM Give it a moment to bind the port
timeout /t 2 >NUL
REM Run TX in this window
call ".venv\Scripts\activate.bat"
python preflight_tx.py --ndi-name PosePC-Test --osc-ip 127.0.0.1 --osc-port 5005 --fps 30 --marks 33
popd >NUL 2>&1
