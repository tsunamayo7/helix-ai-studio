@echo off
cd /d "%~dp0"
python -m PyInstaller --onefile --windowed --name hello_world hello_world.py
echo Build completed.
pause
