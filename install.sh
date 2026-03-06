#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  Helix AI Studio v12.5.0 — Auto Installer (macOS / Linux)
#
#  Usage:   chmod +x install.sh && ./install.sh
#  All dependencies will be installed automatically.
# ══════════════════════════════════════════════════════════════
set -e

WARNINGS=0
warn() { echo "  [WARN] $1"; ((WARNINGS++)) || true; }
ok()   { echo "  [OK] $1"; }
info() { echo "       $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       Helix AI Studio v12.5.0 — Auto Installer         ║"
echo "║                                                         ║"
echo "║  All dependencies will be installed automatically.      ║"
echo "║  全ての依存関係を自動でインストールします。              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

OS="$(uname -s)"
ARCH="$(uname -m)"
echo "OS: $OS ($ARCH)"
echo ""

# ════════════════════════════════════════════
# [1/8] Python version check
# ════════════════════════════════════════════
echo "[1/8] Python 確認 / Checking Python ..."

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "  [ERROR] Python 3.10+ が見つかりません / Python 3.10+ not found"
    echo ""
    if [ "$OS" = "Darwin" ]; then
        echo "  macOS: brew install python@3.12"
        echo "     or: https://www.python.org/downloads/"
    else
        echo "  Linux: sudo apt install python3.12 python3.12-venv python3-pip"
        echo "     or: https://www.python.org/downloads/"
    fi
    exit 1
fi

ok "Python $($PYTHON_CMD --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
PIP_CMD="$PYTHON_CMD -m pip"
echo ""

# ════════════════════════════════════════════
# [2/8] pip upgrade
# ════════════════════════════════════════════
echo "[2/8] pip アップグレード / Upgrading pip ..."
$PIP_CMD install --upgrade pip --quiet 2>/dev/null || $PIP_CMD install --upgrade pip
ok "pip"
echo ""

# ════════════════════════════════════════════
# [3/8] Core Python packages
# ════════════════════════════════════════════
echo "[3/8] Python パッケージ一括インストール / Installing all Python packages ..."
info "(PyQt6, FastAPI, Anthropic, OpenAI, Google GenAI, CrewAI, etc.)"

$PIP_CMD install -r requirements.txt --quiet 2>/dev/null || {
    warn "一部パッケージでエラー — リトライ中"
    $PIP_CMD install -r requirements.txt
}
ok "コアパッケージ完了"
echo ""

# ════════════════════════════════════════════
# [4/8] Optional tools (auto-install all)
# ════════════════════════════════════════════
echo "[4/8] オプションツール自動インストール / Installing optional tools ..."

info "- browser-use (Web ブラウジング) ..."
if $PIP_CMD install browser-use --quiet 2>/dev/null; then
    ok "browser-use"
    info "- Chromium (ヘッドレスブラウザ) ..."
    if $PYTHON_CMD -m playwright install chromium 2>/dev/null; then
        ok "Chromium"
    else
        warn "Chromium のインストールに失敗"
    fi
else
    warn "browser-use のインストールに失敗"
fi

info "- sentence-transformers (ローカル Embedding) ..."
if $PIP_CMD install sentence-transformers --quiet 2>/dev/null; then
    ok "sentence-transformers"
else
    warn "sentence-transformers のインストールに失敗"
fi

info "- httpx ..."
$PIP_CMD install httpx --quiet 2>/dev/null
ok "httpx"
echo ""

# ════════════════════════════════════════════
# [5/8] Data directories + Config templates
# ════════════════════════════════════════════
echo "[5/8] ディレクトリ・設定テンプレート / Creating directories + config ..."

for d in config data data/information data/rag data/memory data/rag_db logs; do
    mkdir -p "$d"
done

for name in general_settings cloud_models config app_settings web_config helix_pilot; do
    if [ ! -f "config/${name}.json" ] && [ -f "config/${name}.example.json" ]; then
        cp "config/${name}.example.json" "config/${name}.json"
        info "config/${name}.json created"
    fi
done
ok "ディレクトリ・設定テンプレート"
echo ""

# ════════════════════════════════════════════
# [6/8] Node.js + Frontend build
# ════════════════════════════════════════════
echo "[6/8] Web UI ビルド / Building Web UI ..."

if ! command -v node &>/dev/null; then
    if [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
        info "Node.js が見つかりません。Homebrew でインストールします ..."
        brew install node 2>/dev/null || true
    elif [ "$OS" = "Linux" ]; then
        info "Node.js が見つかりません。インストールを試みます ..."
        if command -v apt-get &>/dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_20.x 2>/dev/null | sudo -E bash - 2>/dev/null
            sudo apt-get install -y nodejs 2>/dev/null || true
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y nodejs 2>/dev/null || true
        fi
    fi
fi

if command -v node &>/dev/null; then
    info "Node.js $(node --version) detected"
    if [ -f "frontend/package.json" ]; then
        info "依存パッケージをインストール中 ..."
        (cd frontend && npm install --silent 2>/dev/null)
        info "ビルド中 ..."
        if (cd frontend && npm run build 2>/dev/null); then
            ok "Web UI ビルド完了"
        else
            warn "Web UI ビルドに失敗"
        fi
    fi
elif [ -f "frontend/dist/index.html" ]; then
    ok "プリビルド版 Web UI を使用"
else
    warn "Node.js が見つかりません — Web UI はビルドできません"
    info "https://nodejs.org/ からインストール後: cd frontend && npm install && npm run build"
fi
echo ""

# ════════════════════════════════════════════
# [7/8] Ollama (Local LLM)
# ════════════════════════════════════════════
echo "[7/8] Ollama (ローカルLLM) 確認 / Checking Ollama ..."

OLLAMA_INSTALLED=0
if command -v ollama &>/dev/null; then
    OLLAMA_INSTALLED=1
    ok "Ollama $(ollama --version 2>&1 | head -1)"
else
    info "Ollama が見つかりません。インストールします ..."
    if [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
        if brew install ollama 2>/dev/null; then
            OLLAMA_INSTALLED=1
            ok "Ollama をインストールしました (brew)"
        else
            warn "Ollama の自動インストールに失敗"
            info "https://ollama.com/download から手動でインストールしてください"
        fi
    elif [ "$OS" = "Linux" ]; then
        if curl -fsSL https://ollama.com/install.sh 2>/dev/null | sh 2>/dev/null; then
            OLLAMA_INSTALLED=1
            ok "Ollama をインストールしました"
        else
            warn "Ollama の自動インストールに失敗"
            info "https://ollama.com/download から手動でインストールしてください"
        fi
    else
        warn "Ollama を自動インストールできません"
        info "https://ollama.com/download"
    fi
fi

if [ "$OLLAMA_INSTALLED" -eq 1 ]; then
    if curl -s http://localhost:11434/ &>/dev/null; then
        ok "Ollama サーバー接続OK (localhost:11434)"

        model_count=$(ollama list 2>/dev/null | wc -l)
        if [ "$model_count" -le 1 ]; then
            echo ""
            info "推奨モデルをダウンロードします (初回は時間がかかります) ..."
            info "- gemma3:4b (軽量、3GB) ..."
            if ollama pull gemma3:4b 2>/dev/null; then
                ok "gemma3:4b"
            fi
        else
            ok "モデルがインストール済みです"
        fi
    else
        echo "  [--] Ollama サーバーが起動していません"
        if [ "$OS" = "Darwin" ]; then
            info "起動方法: brew services start ollama  or  ollama serve"
        else
            info "起動方法: ollama serve &"
        fi
    fi
fi
echo ""

# ════════════════════════════════════════════
# [8/8] Claude CLI / Codex CLI
# ════════════════════════════════════════════
echo "[8/8] CLI ツール確認 / Checking CLI tools ..."

if command -v node &>/dev/null; then
    if ! command -v claude &>/dev/null; then
        info "Claude Code CLI をインストール中 ..."
        if npm install -g @anthropic-ai/claude-code 2>/dev/null; then
            ok "Claude Code CLI"
        else
            echo "  [--] Claude Code CLI のインストールに失敗 (後で手動インストール可能)"
        fi
    else
        ok "Claude Code CLI"
    fi

    if ! command -v codex &>/dev/null; then
        info "Codex CLI をインストール中 ..."
        if npm install -g @openai/codex 2>/dev/null; then
            ok "Codex CLI"
        else
            echo "  [--] Codex CLI のインストールに失敗 (後で手動インストール可能)"
        fi
    else
        ok "Codex CLI"
    fi
else
    echo "  [--] Node.js がないため CLI ツールはスキップ (API直接接続で代替可能)"
fi
echo ""

# ════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           インストール完了！ / Install Complete!         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [ "$WARNINGS" -gt 0 ]; then
    echo "  [!] ${WARNINGS} 件の警告がありました（上のログを確認してください）"
    echo ""
fi

echo "┌────────────────────────────────────────────────────────┐"
echo "│  起動方法 / How to start:                              │"
echo "│                                                        │"
echo "│    $PYTHON_CMD HelixAIStudio.py                        │"
echo "│                                                        │"
echo "│  Web UI:  http://localhost:8500                        │"
echo "└────────────────────────────────────────────────────────┘"
echo ""
echo "  APIキーの設定:"
echo "    起動後「一般設定」タブ → API Keys セクションで入力"
echo "    (Ollama のみ使う場合は API キー不要です)"
echo ""
echo "    - Anthropic : https://console.anthropic.com/settings/keys"
echo "    - Google    : https://aistudio.google.com/apikey (無料枠あり)"
echo "    - OpenAI    : https://platform.openai.com/api-keys"
echo ""
