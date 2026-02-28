@echo off
REM ============================================================================
REM  Helix AI Studio - One-Click Installer for Windows
REM  Version: 11.9.4
REM  Author: tsunamayo7
REM  This script handles the COMPLETE environment setup.
REM ============================================================================
setlocal enabledelayedexpansion

REM --- UTF-8 mode ---
chcp 65001 >nul 2>&1

REM --- Script directory (where this .bat lives) ---
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

REM --- Color codes via Windows 10+ ANSI escape sequences ---
REM We use PowerShell to emit ANSI escapes for older terminals
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"

REM --- Color definitions ---
set "C_RESET=%ESC%[0m"
set "C_RED=%ESC%[91m"
set "C_GREEN=%ESC%[92m"
set "C_YELLOW=%ESC%[93m"
set "C_BLUE=%ESC%[94m"
set "C_MAGENTA=%ESC%[95m"
set "C_CYAN=%ESC%[96m"
set "C_WHITE=%ESC%[97m"
set "C_BOLD=%ESC%[1m"
set "C_DIM=%ESC%[2m"

REM --- Status tracking ---
set "STATUS_PYTHON=NOT CHECKED"
set "STATUS_PIP=NOT CHECKED"
set "STATUS_VENV=SKIPPED"
set "STATUS_DEPS=NOT INSTALLED"
set "STATUS_OLLAMA=NOT CHECKED"
set "STATUS_OLLAMA_MODELS=SKIPPED"
set "STATUS_NODEJS=NOT CHECKED"
set "STATUS_CONFIG=NOT CHECKED"
set "STATUS_FRONTEND=SKIPPED"
set "EXIT_CODE=0"

REM ============================================================================
REM  HEADER
REM ============================================================================
cls
echo.
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%     _   _      _ _         _    ___   ____  _             _ _        %C_RESET%
echo %C_CYAN%%C_BOLD%    ^| ^| ^| ^| ___^| (_)_  __ ^| ^|  / _ \ ^|_  _^|/ ___^| _   _  __^| (_) ___   %C_RESET%
echo %C_CYAN%%C_BOLD%    ^| ^|_^| ^|/ _ \ ^| \ \/ / ^| ^| ^| ^|_^| ^|  ^| ^| \___ \^| ^| ^| ^|/ _` ^| ^|/ _ \  %C_RESET%
echo %C_CYAN%%C_BOLD%    ^|  _  ^|  __/ ^| ^|^>  ^<  ^| ^| ^|  _  ^|  ^| ^|  ___) ^| ^|_^| ^| (_^| ^| ^| (_) ^| %C_RESET%
echo %C_CYAN%%C_BOLD%    ^|_^| ^|_^|\___)_^|_/_/\_\ ^|_^| ^|_^| ^|_^| ^|___^|^|____/ \__,_^|\__,_^|_^|\___/  %C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.
echo %C_MAGENTA%    v11.9.4 - Complete Environment Installer%C_RESET%
echo %C_DIM%    by tsunamayo7%C_RESET%
echo.
echo %C_CYAN%============================================================================%C_RESET%
echo.
echo %C_WHITE%  [JA] Helix AI Studio の完全セットアップを開始します。%C_RESET%
echo %C_WHITE%  [EN] Starting complete setup for Helix AI Studio.%C_RESET%
echo.
echo %C_YELLOW%  [JA] 各ステップで確認を求めます。強制インストールはしません。%C_RESET%
echo %C_YELLOW%  [EN] You will be prompted at each step. Nothing is forced.%C_RESET%
echo.
echo %C_CYAN%----------------------------------------------------------------------------%C_RESET%
echo.
pause

REM ============================================================================
REM  STEP 1: Python Check
REM ============================================================================
echo.
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 1/9: Python%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] Python 3.10+ の確認%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Checking Python 3.10+%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_RED%  [X] Python is not installed or not in PATH.%C_RESET%
    echo %C_RED%  [X] Python がインストールされていないか、PATHに含まれていません。%C_RESET%
    echo.
    echo %C_YELLOW%  [JA] Python 3.10以上をインストールしてください。%C_RESET%
    echo %C_YELLOW%  [EN] Please install Python 3.10 or higher.%C_RESET%
    echo.
    set /p "OPEN_PYTHON=[JA] Pythonダウンロードページを開きますか？ / [EN] Open Python download page? (Y/N): "
    if /i "!OPEN_PYTHON!"=="Y" (
        start https://www.python.org/downloads/
        echo %C_GREEN%  -> ブラウザで開きました / Opened in browser.%C_RESET%
    )
    echo.
    echo %C_RED%  [JA] Pythonインストール後、このスクリプトを再実行してください。%C_RESET%
    echo %C_RED%  [EN] Please re-run this script after installing Python.%C_RESET%
    set "STATUS_PYTHON=NOT INSTALLED"
    set "EXIT_CODE=1"
    goto :SUMMARY
)

REM Get Python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYTHON_VER=%%v"

REM Parse major.minor
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

echo %C_GREEN%  [OK] Python %PYTHON_VER% detected.%C_RESET%
echo %C_GREEN%  [OK] Python %PYTHON_VER% が見つかりました。%C_RESET%

REM Check version >= 3.10
set "PY_OK=0"
if %PY_MAJOR% gtr 3 set "PY_OK=1"
if %PY_MAJOR% equ 3 if %PY_MINOR% geq 10 set "PY_OK=1"

if %PY_OK% equ 0 (
    echo %C_RED%  [!] Python 3.10+ is required, but %PYTHON_VER% was found.%C_RESET%
    echo %C_RED%  [!] Python 3.10以上が必要ですが、%PYTHON_VER% が見つかりました。%C_RESET%
    echo %C_YELLOW%  [JA] アップグレードしてから再実行してください。%C_RESET%
    echo %C_YELLOW%  [EN] Please upgrade and re-run this script.%C_RESET%
    set "STATUS_PYTHON=TOO OLD (%PYTHON_VER%)"
    set "EXIT_CODE=1"
    goto :SUMMARY
)

set "STATUS_PYTHON=OK (%PYTHON_VER%)"
echo.

REM ============================================================================
REM  STEP 2: pip Check
REM ============================================================================
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 2/9: pip%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] pip パッケージマネージャの確認%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Checking pip package manager%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_YELLOW%  [!] pip is not available. Attempting to install...%C_RESET%
    echo %C_YELLOW%  [!] pip が見つかりません。インストールを試みます...%C_RESET%
    python -m ensurepip --default-pip 2>nul
    if %errorlevel% neq 0 (
        echo %C_RED%  [X] Failed to install pip.%C_RESET%
        echo %C_RED%  [X] pip のインストールに失敗しました。%C_RESET%
        set "STATUS_PIP=FAILED"
        set "EXIT_CODE=1"
        goto :SUMMARY
    )
)

for /f "tokens=*" %%p in ('python -m pip --version 2^>^&1') do set "PIP_INFO=%%p"
echo %C_GREEN%  [OK] %PIP_INFO%%C_RESET%
set "STATUS_PIP=OK"
echo.

REM --- Upgrade pip ---
echo %C_DIM%  Upgrading pip to latest... / pip を最新版に更新中...%C_RESET%
python -m pip install --upgrade pip >nul 2>&1
echo %C_GREEN%  [OK] pip upgraded. / pip 更新完了。%C_RESET%
echo.

REM ============================================================================
REM  STEP 3: Virtual Environment (Optional)
REM ============================================================================
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 3/9: Virtual Environment%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] 仮想環境の作成（任意）%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Create virtual environment (optional)%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    echo %C_GREEN%  [OK] Virtual environment already exists at: venv\%C_RESET%
    echo %C_GREEN%  [OK] 仮想環境は既に存在します: venv\%C_RESET%
    echo %C_DIM%  Activating... / 有効化中...%C_RESET%
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
    set "STATUS_VENV=OK (existing)"
) else (
    echo %C_YELLOW%  [JA] 仮想環境を作成しますか？%C_RESET%
    echo %C_YELLOW%       パッケージをシステムPythonから隔離できます（推奨）。%C_RESET%
    echo %C_YELLOW%  [EN] Create a virtual environment?%C_RESET%
    echo %C_YELLOW%       This isolates packages from system Python (recommended).%C_RESET%
    echo.
    set /p "CREATE_VENV=  Create venv? / 仮想環境を作成? (Y/N): "
    if /i "!CREATE_VENV!"=="Y" (
        echo.
        echo %C_DIM%  Creating virtual environment... / 仮想環境を作成中...%C_RESET%
        python -m venv "%SCRIPT_DIR%\venv"
        if %errorlevel% neq 0 (
            echo %C_RED%  [X] Failed to create virtual environment.%C_RESET%
            echo %C_RED%  [X] 仮想環境の作成に失敗しました。%C_RESET%
            set "STATUS_VENV=FAILED"
        ) else (
            echo %C_GREEN%  [OK] Virtual environment created. / 仮想環境を作成しました。%C_RESET%
            call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
            echo %C_GREEN%  [OK] Activated. / 有効化しました。%C_RESET%
            set "STATUS_VENV=OK (created)"

            REM Upgrade pip inside venv
            python -m pip install --upgrade pip >nul 2>&1
        )
    ) else (
        echo %C_DIM%  Skipped. / スキップしました。%C_RESET%
        set "STATUS_VENV=SKIPPED (user choice)"
    )
)
echo.

REM ============================================================================
REM  STEP 4: Install Python Dependencies
REM ============================================================================
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 4/9: Python Dependencies%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] Python パッケージのインストール (requirements.txt)%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Installing Python packages (requirements.txt)%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

if not exist "%SCRIPT_DIR%\requirements.txt" (
    echo %C_RED%  [X] requirements.txt not found!%C_RESET%
    echo %C_RED%  [X] requirements.txt が見つかりません！%C_RESET%
    set "STATUS_DEPS=MISSING requirements.txt"
    set "EXIT_CODE=1"
    goto :STEP5
)

echo %C_WHITE%  [JA] 以下のパッケージがインストールされます:%C_RESET%
echo %C_WHITE%  [EN] The following packages will be installed:%C_RESET%
echo %C_DIM%       PyQt6, anthropic, openai, google-genai, fastapi, uvicorn,%C_RESET%
echo %C_DIM%       httpx, mcp, networkx, numpy, pandas, aiohttp, PyMuPDF,%C_RESET%
echo %C_DIM%       pyyaml, cryptography, requests, qrcode, etc.%C_RESET%
echo.
echo %C_YELLOW%  [JA] これには数分かかる場合があります。%C_RESET%
echo %C_YELLOW%  [EN] This may take several minutes.%C_RESET%
echo.

set /p "INSTALL_DEPS=  Install? / インストール? (Y/N): "
if /i "!INSTALL_DEPS!"=="Y" (
    echo.
    echo %C_DIM%  Installing... / インストール中...%C_RESET%
    echo %C_DIM%  ------------------------------------------------%C_RESET%
    python -m pip install -r "%SCRIPT_DIR%\requirements.txt"
    if %errorlevel% neq 0 (
        echo %C_RED%  [X] Some packages failed to install.%C_RESET%
        echo %C_RED%  [X] 一部のパッケージのインストールに失敗しました。%C_RESET%
        set "STATUS_DEPS=PARTIAL (some errors)"
        set "EXIT_CODE=1"
    ) else (
        echo.
        echo %C_GREEN%  [OK] All packages installed successfully!%C_RESET%
        echo %C_GREEN%  [OK] 全パッケージのインストールが完了しました！%C_RESET%
        set "STATUS_DEPS=OK"
    )
) else (
    echo %C_DIM%  Skipped. / スキップしました。%C_RESET%
    set "STATUS_DEPS=SKIPPED (user choice)"
)
echo.

REM ============================================================================
REM  STEP 5: Ollama Check
REM ============================================================================
:STEP5
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 5/9: Ollama (Local LLM)%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] Ollama ローカルLLMエンジンの確認%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Checking Ollama local LLM engine%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_YELLOW%  [!] Ollama is not installed.%C_RESET%
    echo %C_YELLOW%  [!] Ollama がインストールされていません。%C_RESET%
    echo.
    echo %C_WHITE%  [JA] Ollama はローカルLLM（localAIタブ・mixAIタブ）に必要です。%C_RESET%
    echo %C_WHITE%  [EN] Ollama is needed for the localAI and mixAI tabs.%C_RESET%
    echo.
    set /p "OPEN_OLLAMA=[JA] Ollamaダウンロードページを開きますか？ / [EN] Open Ollama download page? (Y/N): "
    if /i "!OPEN_OLLAMA!"=="Y" (
        start https://ollama.com/download
        echo %C_GREEN%  -> ブラウザで開きました / Opened in browser.%C_RESET%
    )
    set "STATUS_OLLAMA=NOT INSTALLED"
    echo.
    goto :STEP7
) else (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do set "OLLAMA_VER=%%v"
    echo %C_GREEN%  [OK] !OLLAMA_VER!%C_RESET%
    set "STATUS_OLLAMA=OK (!OLLAMA_VER!)"
)
echo.

REM ============================================================================
REM  STEP 6: Ollama Models
REM ============================================================================
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 6/9: Ollama Models%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] 推奨モデルのダウンロード%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Download recommended models%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

REM --- Check if Ollama service is running ---
echo %C_DIM%  Checking if Ollama is running... / Ollama の稼働確認中...%C_RESET%
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_YELLOW%  [!] Ollama service is not running.%C_RESET%
    echo %C_YELLOW%  [!] Ollama サービスが起動していません。%C_RESET%
    echo.
    echo %C_WHITE%  [JA] Ollama を起動してからモデルをダウンロードしてください。%C_RESET%
    echo %C_WHITE%  [EN] Please start Ollama and download models later.%C_RESET%
    echo %C_WHITE%  [JA] コマンド: ollama pull gemma3:4b%C_RESET%
    echo %C_WHITE%  [EN] Command:  ollama pull gemma3:4b%C_RESET%
    set "STATUS_OLLAMA_MODELS=SKIPPED (Ollama not running)"
    echo.
    goto :STEP7
)

echo %C_GREEN%  [OK] Ollama is running. / Ollama 稼働中。%C_RESET%
echo.

REM --- Show currently installed models ---
echo %C_WHITE%  [JA] 現在インストール済みのモデル:%C_RESET%
echo %C_WHITE%  [EN] Currently installed models:%C_RESET%
echo %C_DIM%  ------------------------------------------------%C_RESET%
ollama list 2>nul
echo %C_DIM%  ------------------------------------------------%C_RESET%
echo.

REM --- gemma3:4b ---
echo %C_WHITE%  [JA] gemma3:4b (2.3GB) - 軽量モデル。初心者にお勧め。%C_RESET%
echo %C_WHITE%  [EN] gemma3:4b (2.3GB) - Lightweight model. Recommended for beginners.%C_RESET%
echo.
set /p "PULL_4B=  Download gemma3:4b? / gemma3:4b をダウンロード? (Y/N): "
if /i "!PULL_4B!"=="Y" (
    echo.
    echo %C_DIM%  Downloading gemma3:4b... This may take a few minutes.%C_RESET%
    echo %C_DIM%  gemma3:4b をダウンロード中... 数分かかることがあります。%C_RESET%
    ollama pull gemma3:4b
    if %errorlevel% equ 0 (
        echo %C_GREEN%  [OK] gemma3:4b downloaded successfully!%C_RESET%
    ) else (
        echo %C_RED%  [X] Failed to download gemma3:4b.%C_RESET%
    )
)
echo.

REM --- gemma3:27b ---
echo %C_WHITE%  [JA] gemma3:27b (17GB) - 高性能モデル。VRAM 16GB以上推奨。%C_RESET%
echo %C_WHITE%  [EN] gemma3:27b (17GB) - High-performance model. Needs 16GB+ VRAM.%C_RESET%
echo %C_YELLOW%  [JA] 注意: ダウンロードに時間がかかります。大容量GPUが必要です。%C_RESET%
echo %C_YELLOW%  [EN] Note: Large download. Requires a high-VRAM GPU.%C_RESET%
echo.
set /p "PULL_27B=  Download gemma3:27b? / gemma3:27b をダウンロード? (Y/N): "
if /i "!PULL_27B!"=="Y" (
    echo.
    echo %C_DIM%  Downloading gemma3:27b... This will take a while.%C_RESET%
    echo %C_DIM%  gemma3:27b をダウンロード中... かなり時間がかかります。%C_RESET%
    ollama pull gemma3:27b
    if %errorlevel% equ 0 (
        echo %C_GREEN%  [OK] gemma3:27b downloaded successfully!%C_RESET%
    ) else (
        echo %C_RED%  [X] Failed to download gemma3:27b.%C_RESET%
    )
)

set "STATUS_OLLAMA_MODELS=OK"
echo.

REM ============================================================================
REM  STEP 7: Node.js Check
REM ============================================================================
:STEP7
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 7/9: Node.js (Web UI)%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] Node.js の確認（Web UI ビルド用、任意）%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Checking Node.js (for Web UI build, optional)%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_YELLOW%  [!] Node.js is not installed.%C_RESET%
    echo %C_YELLOW%  [!] Node.js がインストールされていません。%C_RESET%
    echo.
    echo %C_WHITE%  [JA] Node.js はWeb UI（ブラウザ版）のビルドに必要です。%C_RESET%
    echo %C_WHITE%       デスクトップアプリのみ使用する場合は不要です。%C_RESET%
    echo %C_WHITE%  [EN] Node.js is needed to build the Web UI (browser version).%C_RESET%
    echo %C_WHITE%       Not needed if you only use the desktop app.%C_RESET%
    echo.
    set /p "OPEN_NODE=[JA] Node.jsダウンロードページを開きますか？ / [EN] Open Node.js download page? (Y/N): "
    if /i "!OPEN_NODE!"=="Y" (
        start https://nodejs.org/
        echo %C_GREEN%  -> ブラウザで開きました / Opened in browser.%C_RESET%
    )
    set "STATUS_NODEJS=NOT INSTALLED (optional)"
    echo.
    goto :STEP8
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
    echo %C_GREEN%  [OK] Node.js !NODE_VER! detected.%C_RESET%
    echo %C_GREEN%  [OK] Node.js !NODE_VER! が見つかりました。%C_RESET%
    set "STATUS_NODEJS=OK (!NODE_VER!)"
)
echo.

REM ============================================================================
REM  STEP 8: Config Template Files
REM ============================================================================
:STEP8
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 8/9: Configuration Files%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] 設定ファイルテンプレートのコピー%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Copying configuration template files%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

set "CONFIG_COPIED=0"
set "CONFIG_EXISTED=0"
set "CONFIG_DIR=%SCRIPT_DIR%\config"

REM --- config.json ---
if exist "%CONFIG_DIR%\config.json" (
    echo %C_GREEN%  [OK] config\config.json already exists.%C_RESET%
    set /a "CONFIG_EXISTED+=1"
) else (
    if exist "%CONFIG_DIR%\config.example.json" (
        copy "%CONFIG_DIR%\config.example.json" "%CONFIG_DIR%\config.json" >nul
        echo %C_GREEN%  [+] config\config.example.json -> config\config.json%C_RESET%
        set /a "CONFIG_COPIED+=1"
    ) else (
        echo %C_YELLOW%  [!] config\config.example.json not found, skipping.%C_RESET%
    )
)

REM --- general_settings.json ---
if exist "%CONFIG_DIR%\general_settings.json" (
    echo %C_GREEN%  [OK] config\general_settings.json already exists.%C_RESET%
    set /a "CONFIG_EXISTED+=1"
) else (
    if exist "%CONFIG_DIR%\general_settings.example.json" (
        copy "%CONFIG_DIR%\general_settings.example.json" "%CONFIG_DIR%\general_settings.json" >nul
        echo %C_GREEN%  [+] config\general_settings.example.json -> config\general_settings.json%C_RESET%
        set /a "CONFIG_COPIED+=1"
    ) else (
        echo %C_YELLOW%  [!] config\general_settings.example.json not found, skipping.%C_RESET%
    )
)

REM --- cloud_models.json ---
if exist "%CONFIG_DIR%\cloud_models.json" (
    echo %C_GREEN%  [OK] config\cloud_models.json already exists.%C_RESET%
    set /a "CONFIG_EXISTED+=1"
) else (
    if exist "%CONFIG_DIR%\cloud_models.example.json" (
        copy "%CONFIG_DIR%\cloud_models.example.json" "%CONFIG_DIR%\cloud_models.json" >nul
        echo %C_GREEN%  [+] config\cloud_models.example.json -> config\cloud_models.json%C_RESET%
        set /a "CONFIG_COPIED+=1"
    ) else (
        echo %C_YELLOW%  [!] config\cloud_models.example.json not found, skipping.%C_RESET%
    )
)

REM --- helix_pilot.json ---
if exist "%CONFIG_DIR%\helix_pilot.json" (
    echo %C_GREEN%  [OK] config\helix_pilot.json already exists.%C_RESET%
    set /a "CONFIG_EXISTED+=1"
) else (
    if exist "%CONFIG_DIR%\helix_pilot.example.json" (
        copy "%CONFIG_DIR%\helix_pilot.example.json" "%CONFIG_DIR%\helix_pilot.json" >nul
        echo %C_GREEN%  [+] config\helix_pilot.example.json -> config\helix_pilot.json%C_RESET%
        set /a "CONFIG_COPIED+=1"
    ) else (
        echo %C_YELLOW%  [!] config\helix_pilot.example.json not found, skipping.%C_RESET%
    )
)

echo.
echo %C_WHITE%  [JA] !CONFIG_COPIED! ファイルをコピー、!CONFIG_EXISTED! ファイルは既存。%C_RESET%
echo %C_WHITE%  [EN] !CONFIG_COPIED! files copied, !CONFIG_EXISTED! files already existed.%C_RESET%
set "STATUS_CONFIG=OK (!CONFIG_COPIED! copied, !CONFIG_EXISTED! existing)"

echo.
echo %C_YELLOW%  [JA] 重要: config\general_settings.json に API キーを設定してください！%C_RESET%
echo %C_YELLOW%       - anthropic_api_key  (Claude API)%C_RESET%
echo %C_YELLOW%       - openai_api_key     (OpenAI / GPT API)%C_RESET%
echo %C_YELLOW%       - google_api_key     (Google Gemini API)%C_RESET%
echo %C_YELLOW%  [EN] Important: Set your API keys in config\general_settings.json!%C_RESET%
echo %C_YELLOW%       - anthropic_api_key  (Claude API)%C_RESET%
echo %C_YELLOW%       - openai_api_key     (OpenAI / GPT API)%C_RESET%
echo %C_YELLOW%       - google_api_key     (Google Gemini API)%C_RESET%
echo.

REM --- Create data directories if they don't exist ---
if not exist "%SCRIPT_DIR%\data" mkdir "%SCRIPT_DIR%\data"
if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"
if not exist "%SCRIPT_DIR%\data\information" mkdir "%SCRIPT_DIR%\data\information"
echo %C_DIM%  Created data/ and logs/ directories if missing.%C_RESET%
echo %C_DIM%  data/ と logs/ ディレクトリを作成しました（未存在の場合）。%C_RESET%
echo.

REM ============================================================================
REM  STEP 9: Frontend Build (Optional)
REM ============================================================================
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%  STEP 9/9: Frontend Build (Web UI)%C_RESET%
echo %C_CYAN%%C_BOLD%  [JA] フロントエンドのビルド（Web UI、任意）%C_RESET%
echo %C_CYAN%%C_BOLD%  [EN] Build frontend (Web UI, optional)%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo %C_YELLOW%  [!] Node.js is not available. Skipping frontend build.%C_RESET%
    echo %C_YELLOW%  [!] Node.js が利用できません。フロントエンドビルドをスキップします。%C_RESET%
    set "STATUS_FRONTEND=SKIPPED (no Node.js)"
    goto :SUMMARY
)

if not exist "%SCRIPT_DIR%\frontend\package.json" (
    echo %C_YELLOW%  [!] frontend/package.json not found. Skipping frontend build.%C_RESET%
    echo %C_YELLOW%  [!] frontend/package.json が見つかりません。スキップします。%C_RESET%
    set "STATUS_FRONTEND=SKIPPED (no package.json)"
    goto :SUMMARY
)

echo %C_WHITE%  [JA] Web UI をビルドしますか？%C_RESET%
echo %C_WHITE%       デスクトップアプリのみ使用する場合は不要です。%C_RESET%
echo %C_WHITE%  [EN] Build the Web UI?%C_RESET%
echo %C_WHITE%       Not needed if you only use the desktop app.%C_RESET%
echo.
set /p "BUILD_FRONTEND=  Build Web UI? / Web UI をビルド? (Y/N): "
if /i "!BUILD_FRONTEND!"=="Y" (
    echo.
    echo %C_DIM%  Installing npm packages... / npm パッケージインストール中...%C_RESET%
    cd /d "%SCRIPT_DIR%\frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo %C_RED%  [X] npm install failed.%C_RESET%
        echo %C_RED%  [X] npm install に失敗しました。%C_RESET%
        set "STATUS_FRONTEND=FAILED (npm install)"
        cd /d "%SCRIPT_DIR%"
        goto :SUMMARY
    )

    echo.
    echo %C_DIM%  Building frontend... / フロントエンドをビルド中...%C_RESET%
    call npm run build
    if %errorlevel% neq 0 (
        echo %C_RED%  [X] npm run build failed.%C_RESET%
        echo %C_RED%  [X] npm run build に失敗しました。%C_RESET%
        set "STATUS_FRONTEND=FAILED (npm build)"
        cd /d "%SCRIPT_DIR%"
        goto :SUMMARY
    )

    cd /d "%SCRIPT_DIR%"
    echo %C_GREEN%  [OK] Frontend built successfully!%C_RESET%
    echo %C_GREEN%  [OK] フロントエンドのビルドが完了しました！%C_RESET%
    set "STATUS_FRONTEND=OK"
) else (
    echo %C_DIM%  Skipped. / スキップしました。%C_RESET%
    set "STATUS_FRONTEND=SKIPPED (user choice)"
)
echo.

REM ============================================================================
REM  SUMMARY
REM ============================================================================
:SUMMARY
echo.
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%                   INSTALLATION SUMMARY / インストール結果%C_RESET%
echo %C_CYAN%%C_BOLD%============================================================================%C_RESET%
echo.

REM --- Display each status with color coding ---
call :PRINT_STATUS "Python"               "%STATUS_PYTHON%"
call :PRINT_STATUS "pip"                  "%STATUS_PIP%"
call :PRINT_STATUS "Virtual Environment"  "%STATUS_VENV%"
call :PRINT_STATUS "Python Packages"      "%STATUS_DEPS%"
call :PRINT_STATUS "Ollama"               "%STATUS_OLLAMA%"
call :PRINT_STATUS "Ollama Models"        "%STATUS_OLLAMA_MODELS%"
call :PRINT_STATUS "Node.js"              "%STATUS_NODEJS%"
call :PRINT_STATUS "Config Files"         "%STATUS_CONFIG%"
call :PRINT_STATUS "Frontend (Web UI)"    "%STATUS_FRONTEND%"

echo.
echo %C_CYAN%----------------------------------------------------------------------------%C_RESET%

if %EXIT_CODE% equ 0 (
    echo.
    echo %C_GREEN%%C_BOLD%  [JA] セットアップが完了しました！%C_RESET%
    echo %C_GREEN%%C_BOLD%  [EN] Setup completed successfully!%C_RESET%
) else (
    echo.
    echo %C_YELLOW%%C_BOLD%  [JA] セットアップは一部完了です。上記のエラーを確認してください。%C_RESET%
    echo %C_YELLOW%%C_BOLD%  [EN] Setup partially completed. Please review errors above.%C_RESET%
)

echo.
echo %C_CYAN%  [JA] 次のステップ / [EN] Next steps:%C_RESET%
echo %C_WHITE%    1. config\general_settings.json に API キーを設定%C_RESET%
echo %C_WHITE%       Set API keys in config\general_settings.json%C_RESET%
echo %C_WHITE%    2. config\cloud_models.json にクラウドモデルを登録%C_RESET%
echo %C_WHITE%       Register cloud models in config\cloud_models.json%C_RESET%
echo %C_WHITE%    3. Ollama を起動（localAI 使用時）%C_RESET%
echo %C_WHITE%       Start Ollama (for localAI usage)%C_RESET%
echo %C_WHITE%    4. python HelixAIStudio.py でアプリを起動%C_RESET%
echo %C_WHITE%       Run: python HelixAIStudio.py%C_RESET%
echo.
echo %C_CYAN%----------------------------------------------------------------------------%C_RESET%
echo.

REM --- Offer to launch ---
if %EXIT_CODE% equ 0 (
    if exist "%SCRIPT_DIR%\HelixAIStudio.py" (
        set /p "LAUNCH_APP=[JA] アプリを起動しますか？ / [EN] Launch the app now? (Y/N): "
        if /i "!LAUNCH_APP!"=="Y" (
            echo.
            echo %C_GREEN%  [JA] Helix AI Studio を起動しています...%C_RESET%
            echo %C_GREEN%  [EN] Launching Helix AI Studio...%C_RESET%
            echo.

            REM If venv was activated, use that python
            if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" (
                start "" "%SCRIPT_DIR%\venv\Scripts\python.exe" "%SCRIPT_DIR%\HelixAIStudio.py"
            ) else (
                start "" python "%SCRIPT_DIR%\HelixAIStudio.py"
            )
        )
    )
)

echo.
echo %C_CYAN%%C_BOLD%  Thank you for installing Helix AI Studio!%C_RESET%
echo %C_CYAN%%C_BOLD%  Helix AI Studio をご利用いただきありがとうございます！%C_RESET%
echo.

endlocal
exit /b %EXIT_CODE%

REM ============================================================================
REM  SUBROUTINES
REM ============================================================================

:PRINT_STATUS
REM Usage: call :PRINT_STATUS "Label" "Status"
set "LABEL=%~1"
set "STAT=%~2"

REM Pad label to 22 chars for alignment
set "PADDED=%LABEL%                      "
set "PADDED=!PADDED:~0,22!"

REM Color based on status prefix
echo !STAT! | findstr /i /c:"OK" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_GREEN%  [OK]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"FAIL" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_RED%  [NG]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"NOT INSTALLED" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_YELLOW%  [--]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"SKIP" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_DIM%  [--]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"PARTIAL" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_YELLOW%  [!!]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"TOO OLD" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_RED%  [NG]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

echo !STAT! | findstr /i /c:"MISSING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   %C_RED%  [NG]  !PADDED!  :  !STAT!%C_RESET%
    goto :eof
)

REM Default
echo   %C_DIM%  [??]  !PADDED!  :  !STAT!%C_RESET%
goto :eof
