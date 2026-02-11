@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
REM Helix AI Studio - Build Script
REM Version: 1.0.1

echo ================================================================================
echo Helix AI Studio - Build Script
echo ================================================================================
echo.

REM Check current directory
echo [1/5] Current Directory: %CD%
echo.

REM Cleanup existing build artifacts
echo [2/5] Cleanup...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo Cleanup complete
echo.

REM Build with PyInstaller
echo [3/5] Building with PyInstaller...
echo Command: python -m PyInstaller HelixAIStudio.spec
python -m PyInstaller HelixAIStudio.spec

if !ERRORLEVEL! neq 0 (
    echo.
    echo ============================================================
    echo ERROR: Build failed
    echo ============================================================
    echo.
    echo Troubleshooting:
    echo 1. Check if PyInstaller is installed:
    echo    pip install pyinstaller
    echo.
    echo 2. Check if dependencies are installed:
    echo    pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Build complete
echo.

REM Copy .exe to project root
echo [4/5] Copying .exe to project root...
if exist "dist\HelixAIStudio.exe" (
    copy /y "dist\HelixAIStudio.exe" "HelixAIStudio.exe"
    echo Copy complete: HelixAIStudio.exe
) else (
    echo Warning: dist\HelixAIStudio.exe not found
    echo Build may not have completed successfully
    pause
    exit /b 1
)
echo.

REM Display build info
echo [5/5] Build Info
echo.
if exist "HelixAIStudio.exe" (
    echo [OK] Build successful
    echo [OK] Executable: %CD%\HelixAIStudio.exe
    echo.

    REM Display file size
    for %%A in ("HelixAIStudio.exe") do (
        echo File size: %%~zA bytes
    )
) else (
    echo [NG] Build failed
)

echo.
echo ================================================================================
echo Build process complete
echo ================================================================================
echo.
echo Next steps:
echo 1. Run HelixAIStudio.exe to launch the application
echo 2. Check logs\crash.log for error logs if any issues occur
echo.
pause
