@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo RLLS ESP32 data downloader - one-time setup
echo ============================================================

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.13"
if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" (
  echo ERROR: Neither "py" nor "python" was found.
  echo Install Python from https://www.python.org/downloads/windows/
  echo Then close this window and run setup_collector.cmd again.
  pause
  exit /b 1
)

if not exist ".venv-collector\Scripts\python.exe" (
  echo Creating the local Python environment...
  %PYTHON_CMD% -m venv .venv-collector
  if errorlevel 1 (
    echo ERROR: Could not create .venv-collector.
    echo Confirm that a normal Python 3 runtime is installed.
    pause
    exit /b 1
  )
)

echo Installing the serial-port dependency...
".venv-collector\Scripts\python.exe" -m pip install -r requirements-collector.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed. Check the internet connection.
  pause
  exit /b 1
)

echo.
echo SETUP COMPLETE.
echo Next, double-click scripts\download_flash_log.cmd.
pause
