@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Helix AI Studio v12.5.0 - Auto Installer

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║       Helix AI Studio v12.5.0 — Auto Installer         ║
echo  ║                                                         ║
echo  ║  All dependencies will be installed automatically.      ║
echo  ║  全ての依存関係を自動でインストールします。              ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set ERRORS=0
set WARNINGS=0

:: ════════════════════════════════════════════
:: [1/8] Python version check
:: ════════════════════════════════════════════
echo [1/8] Python 確認 / Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python が見つかりません / Python not found
    echo.
    echo    1. https://www.python.org/downloads/ からダウンロード
    echo    2. インストール時に "Add Python to PATH" に必ずチェック
    echo    3. インストール後、このスクリプトを再実行してください
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if !PYMAJOR! LSS 3 goto :python_too_old
if !PYMAJOR!==3 if !PYMINOR! LSS 10 goto :python_too_old
echo   [OK] Python !PYVER!
goto :python_ok

:python_too_old
echo  [ERROR] Python 3.10 以上が必要です (現在: !PYVER!)
echo          https://www.python.org/downloads/
pause
exit /b 1

:python_ok
echo.

:: ════════════════════════════════════════════
:: [2/8] pip upgrade
:: ════════════════════════════════════════════
echo [2/8] pip アップグレード / Upgrading pip ...
python -m pip install --upgrade pip --quiet 2>nul
echo   [OK]
echo.

:: ════════════════════════════════════════════
:: [3/8] Core Python packages
:: ════════════════════════════════════════════
echo [3/8] Python パッケージ一括インストール / Installing all Python packages ...
echo       (PyQt6, FastAPI, Anthropic, OpenAI, Google GenAI, CrewAI, etc.)
pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo   [WARN] 一部パッケージでエラー — 個別にリトライします
    set /a WARNINGS+=1
    pip install -r requirements.txt 2>nul
)
echo   [OK] コアパッケージ完了
echo.

:: ════════════════════════════════════════════
:: [4/8] Optional tools (auto-install all)
:: ════════════════════════════════════════════
echo [4/8] オプションツール自動インストール / Installing optional tools ...

echo       - browser-use (Web ブラウジング) ...
pip install browser-use --quiet 2>nul
if errorlevel 1 (
    echo         [WARN] browser-use のインストールに失敗
    set /a WARNINGS+=1
) else (
    echo         [OK] browser-use
    echo       - Chromium (ヘッドレスブラウザ) ...
    python -m playwright install chromium --quiet 2>nul
    if errorlevel 1 (
        python -m playwright install chromium 2>nul
        if errorlevel 1 (
            echo         [WARN] Chromium のインストールに失敗
            set /a WARNINGS+=1
        ) else (
            echo         [OK] Chromium
        )
    ) else (
        echo         [OK] Chromium
    )
)

echo       - sentence-transformers (ローカル Embedding) ...
pip install sentence-transformers --quiet 2>nul
if errorlevel 1 (
    echo         [WARN] sentence-transformers のインストールに失敗
    set /a WARNINGS+=1
) else (
    echo         [OK] sentence-transformers
)

echo       - httpx ...
pip install httpx --quiet 2>nul
echo         [OK] httpx
echo.

:: ════════════════════════════════════════════
:: [5/8] Data directories + Config templates
:: ════════════════════════════════════════════
echo [5/8] ディレクトリ・設定テンプレート / Creating directories + config ...
for %%d in (config data data\information data\rag data\memory data\rag_db logs) do (
    if not exist "%%d" mkdir "%%d"
)

:: Copy all example configs to actual configs (only if not already existing)
for %%f in (config\general_settings config\cloud_models config\config config\app_settings config\web_config config\helix_pilot) do (
    if not exist "%%f.json" (
        if exist "%%f.example.json" (
            copy "%%f.example.json" "%%f.json" >nul 2>&1
            echo       %%f.json created
        )
    )
)
echo   [OK]
echo.

:: ════════════════════════════════════════════
:: [6/8] Node.js + Frontend build
:: ════════════════════════════════════════════
echo [6/8] Web UI ビルド / Building Web UI ...
where node >nul 2>&1
if errorlevel 1 (
    :: Try to install Node.js via winget
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo       Node.js が見つかりません。winget でインストールします ...
        winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent 2>nul
        :: Refresh PATH
        for /f "tokens=*" %%p in ('where node 2^>nul') do set NODE_PATH=%%p
    )
)

where node >nul 2>&1
if errorlevel 1 (
    if exist "frontend\dist\index.html" (
        echo   [OK] プリビルド版 Web UI を使用
    ) else (
        echo   [WARN] Node.js が見つかりません — Web UI はビルドできません
        echo          https://nodejs.org/ からインストール後、以下を実行:
        echo          cd frontend ^&^& npm install ^&^& npm run build
        set /a WARNINGS+=1
    )
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo       Node.js %%v detected
    if exist "frontend\package.json" (
        echo       依存パッケージをインストール中 ...
        cd frontend
        call npm install --silent 2>nul
        echo       ビルド中 ...
        call npm run build 2>nul
        if errorlevel 1 (
            echo   [WARN] Web UI ビルドに失敗
            set /a WARNINGS+=1
        ) else (
            echo   [OK] Web UI ビルド完了
        )
        cd ..
    )
)
echo.

:: ════════════════════════════════════════════
:: [7/8] Ollama check / auto-install
:: ════════════════════════════════════════════
echo [7/8] Ollama (ローカルLLM) 確認 / Checking Ollama ...
set OLLAMA_INSTALLED=0
where ollama >nul 2>&1
if not errorlevel 1 (
    set OLLAMA_INSTALLED=1
) else (
    :: Check default install path
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set OLLAMA_INSTALLED=1
    )
)

if !OLLAMA_INSTALLED!==0 (
    echo       Ollama が見つかりません。ダウンロードしてインストールします ...
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent 2>nul
        if not errorlevel 1 (
            echo   [OK] Ollama をインストールしました
            set OLLAMA_INSTALLED=1
        ) else (
            echo   [WARN] Ollama の自動インストールに失敗
            echo          https://ollama.com/download から手動でインストールしてください
            set /a WARNINGS+=1
        )
    ) else (
        :: Try downloading with curl
        echo       winget が利用できないため、手動インストールが必要です
        echo          https://ollama.com/download
        set /a WARNINGS+=1
    )
) else (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo       %%v
    echo   [OK] Ollama インストール済み
)

:: Check Ollama server
if !OLLAMA_INSTALLED!==1 (
    curl -s -o nul -w "" http://localhost:11434/ >nul 2>&1
    if not errorlevel 1 (
        echo   [OK] Ollama サーバー接続OK (localhost:11434)

        :: Check if any models are installed
        for /f %%c in ('ollama list 2^>nul ^| find /c /v ""') do set MODEL_COUNT=%%c
        if !MODEL_COUNT! LEQ 1 (
            echo.
            echo       推奨モデルをダウンロードします (初回は時間がかかります) ...
            echo       - gemma3:4b (軽量、3GB) ...
            ollama pull gemma3:4b 2>nul
            if not errorlevel 1 (
                echo         [OK] gemma3:4b
            )
        ) else (
            echo   [OK] モデルがインストール済みです
        )
    ) else (
        echo   [--] Ollama サーバーが起動していません
        echo        Ollama アプリを起動してから、このアプリを使ってください
    )
)
echo.

:: ════════════════════════════════════════════
:: [8/8] Claude CLI / Codex CLI check
:: ════════════════════════════════════════════
echo [8/8] CLI ツール確認 / Checking CLI tools ...
where node >nul 2>&1
if not errorlevel 1 (
    claude --version >nul 2>&1
    if errorlevel 1 (
        echo       Claude Code CLI をインストール中 ...
        call npm install -g @anthropic-ai/claude-code 2>nul
        if not errorlevel 1 (
            echo   [OK] Claude Code CLI
        ) else (
            echo   [--] Claude Code CLI のインストールに失敗 (後で手動インストール可能)
        )
    ) else (
        echo   [OK] Claude Code CLI
    )

    codex --version >nul 2>&1
    if errorlevel 1 (
        echo       Codex CLI をインストール中 ...
        call npm install -g @openai/codex 2>nul
        if not errorlevel 1 (
            echo   [OK] Codex CLI
        ) else (
            echo   [--] Codex CLI のインストールに失敗 (後で手動インストール可能)
        )
    ) else (
        echo   [OK] Codex CLI
    )
) else (
    echo   [--] Node.js がないため CLI ツールはスキップ (API直接接続で代替可能)
)
echo.

:: ════════════════════════════════════════════
:: Summary
:: ════════════════════════════════════════════
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║           インストール完了！ / Install Complete!         ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

if !WARNINGS! GTR 0 (
    echo  [!] !WARNINGS! 件の警告がありました（上のログを確認してください）
    echo.
)

echo  ┌────────────────────────────────────────────────────────┐
echo  │  起動方法 / How to start:                              │
echo  │                                                        │
echo  │    python HelixAIStudio.py                             │
echo  │                                                        │
echo  │  Web UI:  http://localhost:8500                        │
echo  └────────────────────────────────────────────────────────┘
echo.
echo  APIキーの設定:
echo    起動後「一般設定」タブ → API Keys セクションで入力
echo    (Ollama のみ使う場合は API キー不要です)
echo.
echo    - Anthropic : https://console.anthropic.com/settings/keys
echo    - Google    : https://aistudio.google.com/apikey (無料枠あり)
echo    - OpenAI    : https://platform.openai.com/api-keys
echo.

pause
