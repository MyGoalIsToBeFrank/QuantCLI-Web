@echo off
chcp 65001 >nul
cd /d "%~dp0"
cd ..
set PYTHONIOENCODING=utf-8

set "NO_PAUSE=%QUANTCLI_NO_PAUSE%"
set "NO_COLOR_ARG="
set "ARGS="

:parse_args
if "%~1"=="" goto run_cli
if /I "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
    shift
    goto parse_args
)
if /I "%~1"=="--no-color" (
    set "NO_COLOR_ARG=1"
)
if defined ARGS (
    set "ARGS=%ARGS% %1"
) else (
    set "ARGS=%1"
)
shift
goto parse_args

:run_cli
if not "%NO_COLOR_ARG%"=="1" set FORCE_COLOR=1

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found. Please run QuantWebUI.bat or scripts\start.bat first.
    if not "%NO_PAUSE%"=="1" pause
    exit /b 1
)

.venv\Scripts\python.exe -m src.cli.main %ARGS%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%NO_PAUSE%"=="1" (
    echo.
    echo.
    echo Press any key to continue...
    pause >nul
)

exit /b %EXIT_CODE%
