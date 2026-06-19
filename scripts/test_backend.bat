@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0.."

echo ========================================
echo  Backend Self Test
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found. Please run QuantWebUI.bat or scripts\start.bat first.
    pause
    exit /b 1
)

.venv\Scripts\python.exe tests\test_backend.py

echo.
echo Done.
pause

popd
