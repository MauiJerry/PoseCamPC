@echo off
REM Activate virtual environment
call .venv\Scripts\activate
python preflight_posepc.py
pause
