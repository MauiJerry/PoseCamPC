@echo off
setlocal enabledelayedexpansion

REM -----------------------------------------------------------------------------
REM PoseCamPC Setup (Windows) - pyenv + venv + local NDI wheel
REM Usage:
REM   scripts\setup.bat                (defaults to Python 3.12.6)
REM   scripts\setup.bat --py 3.11.9    (switch to Python 3.11.9)
REM -----------------------------------------------------------------------------

REM Ensure we run from the REPO ROOT (this script lives in /scripts)
pushd "%~dp0\.." >NUL 2>&1

set "TARGET_PY=3.12.6"
if "%~1"=="--py" (
  if "%~2"=="" (
    echo [ERROR] Missing version after --py
    exit /b 2
  )
  set "TARGET_PY=%~2"
)

echo === Ensuring pyenv-win is available ===
where pyenv >NUL 2>&1
if errorlevel 1 (
  echo [ERROR] pyenv-win not on PATH.
  echo Install it, then reopen your terminal:
  echo   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://pyenv-win.github.io/pyenv-win/install.ps1 ^| iex"
  exit /b 1
)

echo === Checking/Installing Python %TARGET_PY% with pyenv-win ===
call pyenv versions --bare | findstr /R /C:"^%TARGET_PY%$" >NUL
if errorlevel 1 (
  echo [INFO] Installing %TARGET_PY% ...
  call pyenv install %TARGET_PY%
  if errorlevel 1 (
    echo [ERROR] pyenv install %TARGET_PY% failed.
    exit /b 1
  )
) else (
  echo [OK] Python %TARGET_PY% already installed
)

echo === Selecting Python %TARGET_PY% for this folder ===
call pyenv local %TARGET_PY%
if errorlevel 1 (
  echo [WARN] pyenv local failed; writing .python-version directly
  > ".python-version" echo %TARGET_PY%
)

echo === Resolving Python path ===
set "PYEXE="
for /f "usebackq delims=" %%I in (`call pyenv which python 2^>NUL`) do set "PYEXE=%%~fI"
if not defined PYEXE (
  REM Fallback to the pyenv versions directory
  set "PYEXE=%USERPROFILE%\.pyenv\pyenv-win\versions\%TARGET_PY%\python.exe"
)
if not exist "%PYEXE%" (
  echo [ERROR] Could not resolve Python executable for %TARGET_PY%.
  echo Tried: %PYEXE%
  exit /b 1
)
echo [OK] Using Python: "%PYEXE%"

echo === (Re)creating virtual environment .venv ===
if exist ".venv" (
  echo [INFO] Removing existing .venv ...
  rmdir /s /q ".venv"
)
"%PYEXE%" -m venv ".venv"
if errorlevel 1 (
  echo [ERROR] venv create failed
  exit /b 1
)

echo === Activating venv ===
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Could not activate venv
  exit /b 1
)

echo === Upgrading pip/setuptools/wheel ===
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo [ERROR] pip upgrade failed
  exit /b 1
)

echo === Installing requirements.txt (without NDI) ===
if exist "requirements.txt" (
  pip install -r "requirements.txt"
  if errorlevel 1 (
    echo [ERROR] pip install -r requirements.txt failed
    exit /b 1
  )
) else (
  echo [WARN] requirements.txt not found. Skipping.
)

echo === Installing local NDI wheel if present ===
set "NDI_WHL="
for %%F in (ndi\ndi_python-*.whl) do set "NDI_WHL=%%~fF"
if not defined NDI_WHL (
  for %%F in (ndi\NDIlib-*.whl) do set "NDI_WHL=%%~fF"
)
if defined NDI_WHL (
  echo [INFO] Found local NDI wheel: %NDI_WHL%
  pip install "%NDI_WHL%"
  if errorlevel 1 (
    echo [ERROR] Failed to install local NDI wheel.
    echo        Try switching Python:  scripts\setup.bat --py 3.11.9
    exit /b 1
  )
) else (
  echo [INFO] No local NDI wheel found under .\ndi\  (this is OK if you haven't added it yet)
)

echo.
echo === DONE ===
echo venv: .venv
echo Python: %TARGET_PY%   (%PYEXE%)
echo Activate: call .venv\Scripts\activate.bat
echo Run:      scripts\test_rx.bat  /  scripts\test_tx.bat
echo.
popd >NUL 2>&1
exit /b 0
