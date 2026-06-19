@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0.."

echo ========================================
echo  Tongfu Data Updater
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    python.exe -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Please make sure python.exe is installed and in PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment found
)

echo [2/3] Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/3] Updating data...
.venv\Scripts\python.exe -m src.cli.main data update

echo.
echo Done.
pause

popd
