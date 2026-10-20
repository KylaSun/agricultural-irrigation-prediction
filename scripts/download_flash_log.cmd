@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo RLLS ESP32 onboard-log downloader
echo ============================================================
echo SAFETY: turn OFF the solar module and disconnect its 5V/USB
echo output from the ESP32 before connecting the computer USB.
echo.

set /p SAFE=Type YES after the solar-module output is disconnected:
if /I not "%SAFE%"=="YES" (
  echo Cancelled. No serial connection was opened.
  pause
  exit /b 1
)

if not exist ".venv-collector\Scripts\python.exe" (
  echo ERROR: Setup has not been completed.
  echo First double-click scripts\setup_collector.cmd.
  pause
  exit /b 1
)

echo.
echo Detected serial ports:
".venv-collector\Scripts\python.exe" collector\list_ports.py
echo.
set /p PORT=Enter the ESP32 port exactly, for example COM3:
if "%PORT%"=="" (
  echo ERROR: A COM port is required.
  pause
  exit /b 1
)

set /p LOGNAME=Optional file name, for example field_20261020 (Enter for automatic):
echo.
if "%LOGNAME%"=="" (
  ".venv-collector\Scripts\python.exe" collector\download_flash_log.py --port "%PORT%" --timeout 300
) else (
  ".venv-collector\Scripts\python.exe" collector\download_flash_log.py --port "%PORT%" --name "%LOGNAME%" --timeout 300
)

if errorlevel 1 (
  echo.
  echo DOWNLOAD FAILED. Read the error above and use the troubleshooting guide:
  echo docs\DATA_DOWNLOAD_HANDOFF_CN.md
  pause
  exit /b 1
)

echo.
echo DOWNLOAD COMPLETE. The ESP32 copy was NOT deleted.
echo Opening the output folder...
start "" explorer.exe "%CD%\data\live"
pause
