@echo off
chcp 65001 >nul
title Helix AI Studio v2

cd /d "%~dp0"

echo ========================================
echo   Helix AI Studio v2
echo   http://localhost:8504
echo ========================================

where uv >nul 2>&1
if %errorlevel% neq 0 (
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

start "" "http://localhost:8504"

uv run python run.py

pause
