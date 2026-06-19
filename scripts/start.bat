@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0.."

echo ========================================
echo  Tongfu Strategy Platform
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python.exe -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Please make sure python.exe is installed and in PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment found
)

echo [2/4] Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/4] Starting backend server...
start "TongfuStrategyServer" cmd /k ".venv\Scripts\python.exe src\api_server.py"
if errorlevel 1 (
    echo ERROR: Failed to start server.
    pause
    exit /b 1
)

echo [4/4] Waiting for server...
timeout /t 3 /nobreak >nul 2>&1

echo Opening browser...
start "" "http://127.0.0.1:5000/"

echo.
echo Server started. Do not close this window.
echo If you want to stop, close the "TongfuStrategyServer" window.
pause

popd
