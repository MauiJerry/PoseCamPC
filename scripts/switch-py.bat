@echo off
setlocal
if "%1"=="" (
  echo Usage: scripts\switch-py.bat 3.11.9
  exit /b 2
)
scripts\setup.bat --py %1
