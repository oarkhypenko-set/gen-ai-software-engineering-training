@echo off
rem Start the Banking Transactions API on http://localhost:3000
rem
rem   demo\run.bat                 start the server with demo data (demo\sample-data.json)
rem   set SEED_DATA=0 ^& demo\run.bat   start with an empty store
rem   demo\run.bat test            run the test suite instead
rem
rem Creates .venv and installs requirements.txt on first run.
setlocal

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment ...
    python -m venv .venv || goto :error
)

echo Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto :error

if /i "%~1"=="test" (
    ".venv\Scripts\python.exe" -m pytest
    exit /b %errorlevel%
)

if not defined SEED_DATA set SEED_DATA=1
if not defined PORT set PORT=3000
echo Starting API on http://localhost:%PORT% (seed data: %SEED_DATA%). Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m src.app
exit /b %errorlevel%

:error
echo Failed. Make sure Python 3.11+ is installed and on PATH.
exit /b 1
