@echo off
REM Activate virtual environment
call .venv\Scripts\activate
python preflight_receiver.py
pause
