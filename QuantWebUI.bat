@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0"

call "scripts\start.bat"

popd
