@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Helix AI Studio v11.6.0 - Installer

echo ============================================================
echo  Helix AI Studio v11.6.0 - Installer
echo ============================================================
echo.

:: ──────────────────────────────────────────
:: [1/6] Python check (version validation)
:: ──────────────────────────────────────────
echo [1/6] Python のバージョンを確認中... / Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python が見つかりません / Python not found
    echo.
    echo   以下からインストールしてください / Install from:
    echo   https://www.python.org/downloads/
    echo.
    echo   [重要] インストール時に "Add Python to PATH" にチェックを入れてください
    echo   [IMPORTANT] Check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

:: Extract Python version and validate >= 3.10
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
echo   Python !PYVER! detected
if !PYMAJOR! LSS 3 (
    echo [ERROR] Python 3.10 以上が必要です / Python 3.10+ required
    echo         現在のバージョン: !PYVER!
    pause
    exit /b 1
)
if !PYMAJOR!==3 if !PYMINOR! LSS 10 (
    echo [ERROR] Python 3.10 以上が必要です / Python 3.10+ required
    echo         現在のバージョン: !PYVER!
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK]
echo.

:: ──────────────────────────────────────────
:: [2/6] pip upgrade
:: ──────────────────────────────────────────
echo [2/6] pip をアップグレード中... / Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK]
echo.

:: ──────────────────────────────────────────
:: [3/6] Core dependencies
:: ──────────────────────────────────────────
echo [3/6] コア依存パッケージをインストール中... / Installing core dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] 一部のパッケージのインストールに失敗しました
    echo           requirements.txt を確認してください
) else (
    echo [OK] コア依存パッケージのインストール完了
)
echo.

:: ──────────────────────────────────────────
:: [4/6] httpx (required for URL fetch fallback)
:: ──────────────────────────────────────────
echo [4/6] httpx をインストール中... / Installing httpx...
pip install httpx --quiet
echo [OK]
echo.

:: ──────────────────────────────────────────
:: [5/6] Data directories
:: ──────────────────────────────────────────
echo [5/6] データディレクトリを作成中... / Creating data directories...
if not exist "config" mkdir config
if not exist "data" mkdir data
if not exist "data\information" mkdir data\information
if not exist "data\rag" mkdir data\rag
if not exist "data\memory" mkdir data\memory
if not exist "logs" mkdir logs
echo [OK]
echo.

:: ──────────────────────────────────────────
:: [6/6] Config template setup
:: ──────────────────────────────────────────
echo [6/6] 設定ファイルテンプレートを配置中... / Setting up config templates...
if not exist "config\general_settings.json" (
    if exist "config\general_settings.example.json" (
        copy "config\general_settings.example.json" "config\general_settings.json" >nul
        echo   general_settings.json created from template
    )
)
if not exist "config\cloud_models.json" (
    if exist "config\cloud_models.example.json" (
        copy "config\cloud_models.example.json" "config\cloud_models.json" >nul
        echo   cloud_models.json created from template
    )
)
echo [OK]
echo.

:: === Optional features ===
echo.
echo ============================================================
echo  オプション機能 / Optional Features
echo ============================================================
echo.
echo [オプション 1/4] Browser Use (JSレンダリング対応URL取得)
echo   localAI でJavaScriptが必要なWebページのコンテンツを取得可能になります。
echo   未インストールでも静的ページの取得は動作します。
echo.
echo   Install browser-use? / インストールしますか？ [Y/N]
set /p INSTALL_BU="> "
if /i "!INSTALL_BU!"=="Y" (
    echo browser-use をインストール中... / Installing browser-use...
    pip install browser-use --quiet
    if errorlevel 1 (
        echo [WARNING] browser-use のインストールに失敗しました / Failed to install browser-use
        echo           後で手動でインストールしてください / Install manually later:
        echo           pip install browser-use
    ) else (
        echo [OK] browser-use インストール完了 / browser-use installed
        echo       Chromium のインストールを実行中... / Installing Chromium...
        python -m playwright install chromium
        if errorlevel 1 (
            echo [WARNING] Chromium のインストールに失敗しました
            echo           後で手動で実行してください:
            echo           python -m playwright install chromium
        ) else (
            echo [OK] Chromium インストール完了 / Chromium installed
        )
    )
) else (
    echo [SKIP] browser-use をスキップしました
    echo        後でアプリ内「一般設定」→「オプションツール状態」からインストールできます
    echo        Or install manually: pip install browser-use
)
echo.

echo [オプション 2/4] sentence-transformers (ローカルEmbedding)
echo   RAG のEmbeddingをOllamaに依存せずローカルで生成できます。
echo   未インストールでもOllamaのEmbeddingで動作します。
echo.
echo   Install sentence-transformers? / インストールしますか？ [Y/N]
set /p INSTALL_ST="> "
if /i "!INSTALL_ST!"=="Y" (
    echo sentence-transformers をインストール中... / Installing sentence-transformers...
    pip install sentence-transformers --quiet
    if errorlevel 1 (
        echo [WARNING] sentence-transformers のインストールに失敗しました
    ) else (
        echo [OK] sentence-transformers インストール完了
    )
) else (
    echo [SKIP] sentence-transformers をスキップしました
)
echo.

echo [オプション 3/4] Anthropic SDK (Claude API直接アクセス)
echo   Claude モデルにAPIキーで直接アクセスできるようになります。
echo   未インストールでもClaude CLIフォールバックで動作します。
echo.
echo   Install anthropic SDK? / インストールしますか？ [Y/N]
set /p INSTALL_ANTHROPIC="> "
if /i "!INSTALL_ANTHROPIC!"=="Y" (
    echo anthropic をインストール中... / Installing anthropic SDK...
    pip install "anthropic>=0.40.0" --quiet
    if errorlevel 1 (
        echo [WARNING] anthropic のインストールに失敗しました / Failed to install anthropic
        echo           後で手動でインストールしてください / Install manually later:
        echo           pip install anthropic
    ) else (
        echo [OK] anthropic SDK インストール完了 / anthropic SDK installed
    )
) else (
    echo [SKIP] anthropic SDK をスキップしました
    echo        後で手動でインストールできます: pip install anthropic
)
echo.

echo [オプション 4/4] OpenAI SDK (OpenAI API直接アクセス)
echo   OpenAI および互換モデルにAPIキーで直接アクセスできるようになります。
echo   未インストールでも他のバックエンドで動作します。
echo.
echo   Install openai SDK? / インストールしますか？ [Y/N]
set /p INSTALL_OPENAI="> "
if /i "!INSTALL_OPENAI!"=="Y" (
    echo openai をインストール中... / Installing openai SDK...
    pip install "openai>=1.0.0" --quiet
    if errorlevel 1 (
        echo [WARNING] openai のインストールに失敗しました / Failed to install openai
        echo           後で手動でインストールしてください / Install manually later:
        echo           pip install openai
    ) else (
        echo [OK] openai SDK インストール完了 / openai SDK installed
    )
) else (
    echo [SKIP] openai SDK をスキップしました
    echo        後で手動でインストールできます: pip install openai
)
echo.

:: ──────────────────────────────────────────
:: Frontend build (requires Node.js)
:: ──────────────────────────────────────────
echo ============================================================
echo  Web UI ビルド / Building Web UI
echo ============================================================
echo.
where node >nul 2>&1
if errorlevel 1 (
    echo [SKIP] Node.js が見つかりません / Node.js not found
    if exist "frontend\dist\index.html" (
        echo        プリビルド版 Web UI を使用します / Using pre-built Web UI
    ) else (
        echo [WARNING] Web UI が利用できません。Node.js をインストールしてビルドしてください。
        echo           https://nodejs.org/
    )
) else (
    echo Node.js が見つかりました / Node.js found:
    node --version
    if exist "frontend\package.json" (
        echo frontend の依存パッケージをインストール中... / Installing frontend dependencies...
        cd frontend
        call npm install --silent 2>nul
        echo Web UI をビルド中... / Building Web UI...
        call npm run build 2>nul
        if errorlevel 1 (
            echo [WARNING] Web UI のビルドに失敗しました / Failed to build Web UI
            echo           プリビルド版を使用します / Using pre-built version
        ) else (
            echo [OK] Web UI ビルド完了 / Web UI built successfully
        )
        cd ..
    ) else (
        echo [SKIP] frontend/package.json が見つかりません
    )
)
echo.

:: ──────────────────────────────────────────
:: Environment check summary
:: ──────────────────────────────────────────
echo ============================================================
echo  外部ツール確認 / External Tools Check
echo ============================================================
echo.

:: Ollama check
set OLLAMA_OK=0
where ollama >nul 2>&1
if not errorlevel 1 (
    set OLLAMA_OK=1
    echo [OK] Ollama CLI が利用可能です
    ollama --version 2>nul
) else (
    echo [--] Ollama が見つかりません
)

:: Ollama server connectivity
curl -s -o nul -w "" http://localhost:11434/ >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama サーバーに接続できました (localhost:11434^)
) else (
    if !OLLAMA_OK!==1 (
        echo [--] Ollama はインストール済みですがサーバーが起動していません
        echo      起動方法: Ollama アプリを起動するか、ターミナルで ollama serve
    ) else (
        echo [--] Ollama サーバーに接続できません
        echo      localAI 機能を使うには Ollama が必要です
        echo      https://ollama.com/download
    )
)
echo.

:: Claude CLI check
claude --version >nul 2>&1
if errorlevel 1 (
    echo [--] Claude CLI が見つかりません
    echo      cloudAI / mixAI(CLI経由^) を使うにはインストールが必要です
    echo      npm install -g @anthropic-ai/claude-code
) else (
    echo [OK] Claude CLI が利用可能です
    claude --version
)
echo.

:: Node.js check (already checked above but show in summary)
where node >nul 2>&1
if not errorlevel 1 (
    echo [OK] Node.js が利用可能です
) else (
    echo [--] Node.js が見つかりません (Web UI 再ビルドには必要^)
)
echo.

:: ──────────────────────────────────────────
:: Done — Next steps
:: ──────────────────────────────────────────
echo ============================================================
echo  インストール完了！ / Installation Complete!
echo ============================================================
echo.
echo  起動方法 / To start:
echo    python HelixAIStudio.py
echo.
echo ────────────────────────────────────────
echo  次のステップ / Next Steps
echo ────────────────────────────────────────
echo.
echo  1. APIキー設定 / API Key Setup (いずれか1つ以上):
echo     アプリ起動後「一般設定」タブ → API Keys セクションで設定
echo     After launch: Settings tab → API Keys section
echo.
echo     - Anthropic : https://console.anthropic.com/settings/keys
echo     - OpenAI    : https://platform.openai.com/api-keys
echo     - Google    : https://aistudio.google.com/apikey
echo.
echo  2. ローカルLLM (localAI) を使う場合:
echo     a. Ollama をインストール: https://ollama.com/download
echo     b. モデルをダウンロード:
echo        ollama pull qwen3:32b
echo        ollama pull devstral:24b
echo     c. Ollama が起動した状態でアプリを起動
echo.
echo  3. 詳細な手順書 / Detailed setup guide:
echo     SETUP_GUIDE.md を参照してください
echo.
pause
