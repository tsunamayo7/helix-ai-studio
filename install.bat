@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Helix AI Studio v11.5.3 - Installer

echo ============================================================
echo  Helix AI Studio v11.5.3 - Installer
echo ============================================================
echo.

:: [1/5] Python check
echo [1/5] Python のバージョンを確認中... / Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません / Python not found
    echo         https://www.python.org/downloads/ からインストールしてください
    pause
    exit /b 1
)
python --version
echo [OK]
echo.

:: [2/5] pip upgrade
echo [2/5] pip をアップグレード中... / Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK]
echo.

:: [3/5] Core dependencies
echo [3/5] コア依存パッケージをインストール中... / Installing core dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] 一部のパッケージのインストールに失敗しました
    echo           requirements.txt を確認してください
) else (
    echo [OK] コア依存パッケージのインストール完了
)
echo.

:: [4/5] httpx (required for URL fetch fallback)
echo [4/5] httpx をインストール中... / Installing httpx...
pip install httpx --quiet
echo [OK]
echo.

:: [5/5] Data directories
echo [5/5] データディレクトリを作成中... / Creating data directories...
if not exist "config" mkdir config
if not exist "data" mkdir data
if not exist "data\information" mkdir data\information
if not exist "data\rag" mkdir data\rag
if not exist "data\memory" mkdir data\memory
if not exist "logs" mkdir logs
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

:: [Optional] Frontend build (requires Node.js)
echo ============================================================
echo  Web UI ビルド / Building Web UI
echo ============================================================
echo.
where node >nul 2>&1
if errorlevel 1 (
    echo [SKIP] Node.js が見つかりません / Node.js not found
    echo        Web UI はプリビルド版を使用します / Using pre-built Web UI
    echo        最新版をビルドするには Node.js をインストールしてください
    echo        https://nodejs.org/
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

:: Check Claude CLI
echo ============================================================
echo  Claude CLI の確認 / Checking Claude CLI
echo ============================================================
echo.
claude --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Claude CLI が見つかりません
    echo        cloudAI / mixAI 機能を使用するには Claude CLI のインストールが必要です
    echo        https://docs.anthropic.com/en/docs/claude-code
) else (
    echo [OK] Claude CLI が利用可能です
    claude --version
)
echo.

:: Done
echo ============================================================
echo  インストール完了 / Installation Complete
echo ============================================================
echo.
echo 起動方法 / To start:
echo   python HelixAIStudio.py
echo.
pause
