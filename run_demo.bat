@echo off
setlocal
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PY=%ROOT%\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" "%~dp0mod_demo_apply.py"
if errorlevel 1 pause & exit /b 1
"%PY%" "%~dp0mod_demo_node.py"
if errorlevel 1 pause & exit /b 1
echo.
echo Demo mod applied. Start LED HEARTS.exe.
pause
