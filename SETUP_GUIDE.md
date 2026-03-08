# Helix AI Studio — セットアップガイド

> **Version**: v12.8.0
> **対象 OS**: Windows 10/11, macOS 12+ (Apple Silicon & Intel), Linux (Ubuntu 22.04+)

**はじめに**: このガイドでは Helix AI Studio のインストールから起動までを説明します。
3 行コピペするだけで、インストーラーが必要なものを全自動でセットアップします。

---

## まずはこれだけ（3ステップで起動）

### Windows

```cmd
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
install.bat
```

### macOS / Linux

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
chmod +x install.sh && ./install.sh
```

**インストーラーが自動で行うこと:**

| ステップ | 内容 |
|---------|------|
| 1 | Python 3.10+ の確認 |
| 2 | pip アップグレード |
| 3 | 全 Python パッケージ一括インストール (PyQt6, FastAPI, AI SDK, CrewAI 等) |
| 4 | オプションツール自動インストール (browser-use, Chromium, sentence-transformers) |
| 5 | データディレクトリ・設定テンプレート作成 |
| 6 | Node.js 検出 → Web UI 自動ビルド (未検出の場合はプリビルド版を使用) |
| 7 | Ollama 検出 → 未インストールなら自動インストール → 推奨モデルDL |
| 8 | Claude Code CLI / Codex CLI 自動インストール |

> インストーラーの実行中、**ユーザー入力は一切不要**です。
> 失敗した項目は [WARN] として表示され、後から手動で対応できます。

**起動:**

```bash
python HelixAIStudio.py   # macOS: python3 HelixAIStudio.py
```

Web UI: `http://localhost:8500`

---

## 初回セットアップの流れ

起動後、以下の順番で設定すると最短で動作確認できます。

| 順序 | タブ | やること |
|------|------|---------|
| 1 | **一般設定** | API キーを設定（Anthropic / OpenAI / Google） |
| 2 | **CloudAI設定** | クラウドモデルの登録・認証方式・実行オプション・MCP設定 |
| 3 | **Ollama設定** | Ollama 接続管理・モデル管理・MCP設定・Browser Use |
| 4 | **soloAI** | チャットで動作確認（クラウド / ローカル統合モデルセレクタ） |
| 5 | **mixAI / RAG / Virtual Desktop** | パイプライン・ナレッジ・仮想環境は必要に応じて |

> **Ollama のみ（API キー不要）でも soloAI タブからローカルモデルで即チャットできます。**

---

## 前提条件

| 項目 | 必須 | 備考 |
|------|------|------|
| Python 3.10+ | **必須** | 3.11 推奨。インストーラーが自動確認 |
| インターネット接続 | **必須** | パッケージダウンロード・API接続用 |
| NVIDIA GPU + CUDA | 推奨 | ローカルLLM (Ollama) 使用時。macOS は Metal 推論 |
| RAM 16GB+ | 推奨 | 大型モデル (27B+) には 32GB 推奨 |

> **Python だけあれば始められます。** Node.js、Ollama、Docker は全てインストーラーが自動導入します。

---

## 依存関係の全体像

### 自動インストールされるもの

| カテゴリ | パッケージ | 用途 | フォールバック |
|---------|----------|------|-------------|
| **GUI** | PyQt6, PyQt6-WebEngine | デスクトップアプリ | — |
| **Web** | FastAPI, Uvicorn, React (ビルド済み) | Web UI サーバー | — |
| **Claude** | anthropic SDK | Claude API 直接接続 | Claude Code CLI |
| **GPT** | openai SDK | OpenAI API 直接接続 | Codex CLI |
| **Gemini** | google-genai | Google Gemini API | — |
| **ローカルLLM** | httpx (+ Ollama 本体) | Ollama 経由のローカル推論 | — |
| **MCP** | mcp SDK | 外部ツール連携プロトコル | — |
| **RAG** | PyMuPDF, networkx, numpy, pandas | ドキュメント解析・ナレッジグラフ | — |
| **認証** | PyJWT, cryptography | Web UI セキュリティ | — |
| **マルチエージェント** | crewai[tools] | Phase 2 エージェントチーム | Sequential 実行 |
| **ブラウザ** | browser-use, Playwright | JS ページ取得 | httpx 静的取得 |
| **Embedding** | sentence-transformers | ローカル埋め込み | Ollama Embedding |
| **CLI** | Claude Code CLI, Codex CLI | CLI モード実行 | API SDK |

### 手動インストールが必要なもの

| ツール | 必要な場面 | インストール方法 |
|--------|----------|----------------|
| **Docker Desktop** | Virtual Desktop タブ（Docker バックエンド） | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **API キー** | クラウド AI 使用時 | 下記「API キー設定」参照 |

> **Windows 11 Pro/Enterprise**: Windows Sandbox が標準で利用可能（Docker 不要）。
> Docker がなくても他の全機能は動作します。

---

## API キーの設定

**最低 1 つ**のバックエンドが必要です。Ollama（ローカル）のみなら API キーは不要。

### 取得先

| プロバイダー | 取得先 | 料金 | 使えるようになる機能 |
|------------|--------|------|-------------------|
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/settings/keys) | 従量課金 | Claude チャット, パイプライン計画 |
| **Google** | [aistudio.google.com](https://aistudio.google.com/app/apikey) | **無料枠あり** | Gemini チャット |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/api-keys) | 従量課金 | GPT チャット |

### 設定方法（3 つから選択）

**方法 A: アプリ内で設定（推奨）**

1. `python HelixAIStudio.py` で起動
2. **一般設定** タブ → **API Keys** セクション
3. キーを貼り付けて **保存**

**方法 B: 設定ファイル直接編集**

```json
// config/general_settings.json
{
  "anthropic_api_key": "sk-ant-xxxxx",
  "openai_api_key": "sk-xxxxx",
  "google_api_key": "AIzaSyxxxxx"
}
```

**方法 C: 環境変数**

```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-xxxxx

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-xxxxx
```

> `config/general_settings.json` は `.gitignore` 対象です。API キーが公開されることはありません。

---

## Ollama のセットアップ（ローカル LLM）

> インストーラーが自動で Ollama をインストールします。
> ここでは手動セットアップや追加モデルの導入方法を説明します。

### 手動インストール（インストーラーが失敗した場合）

| OS | コマンド |
|----|---------|
| Windows | [ollama.com/download](https://ollama.com/download) からインストーラーをDL |
| macOS | `brew install ollama` |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |

### 推奨モデル

```bash
# 汎用（推奨）
ollama pull gemma3:4b           # 軽量 (3GB VRAM)
ollama pull qwen3:32b           # 高品質 (20GB VRAM)

# コーディング特化
ollama pull devstral:24b        # Mistral のコーディングモデル

# Vision（Helix Pilot 用）
ollama pull mistral-small3.2    # 画像認識対応
```

### VRAM 目安

| モデルサイズ | 必要 VRAM | 推奨 GPU |
|------------|----------|---------|
| 4B | 3-4 GB | GTX 1660 以上 |
| 8B | 6-8 GB | RTX 3060 以上 |
| 27-32B | 16-20 GB | RTX 4090 / M1 Pro |
| 70B+ | 40+ GB | A100 / M2 Ultra |

### 起動確認

```bash
ollama serve                           # サーバー起動
curl http://localhost:11434/           # → "Ollama is running"
ollama list                            # インストール済みモデル一覧
```

---

## Virtual Desktop のセットアップ

> **Windows Sandbox（デフォルト）**: Windows 11 Pro/Enterprise なら追加インストール不要。設定 → アプリ → オプション機能 で有効化するだけ。Auto モード選択時は Windows Sandbox が最優先で使用されます。
> **Docker（上級者向け）**: Docker Desktop をインストールすると、埋め込みビューやファイル閲覧など全機能が使えます。Windows Sandbox が利用できない環境では Docker にフォールバックします。

### Docker Desktop のインストール（上級者向け・任意）

1. [docker.com](https://www.docker.com/products/docker-desktop/) からダウンロード
2. インストールを完了させ、Docker サービスを起動した状態にする
3. Helix AI Studio を起動 → Virtual Desktop タブで Docker ランタイムが選択可能に

### Sandbox イメージのビルド

```bash
docker build -t helix-sandbox -f docker/sandbox/Dockerfile docker/sandbox/
```

> 初回ビルドには数分かかります。以降は Helix が自動でコンテナを管理します。

---

## Web UI へのアクセス

デスクトップアプリ起動時に Web サーバーが自動で立ち上がります。

| アクセス元 | URL |
|-----------|-----|
| 同じ PC | `http://localhost:8500` |
| LAN 内の他デバイス | `http://<PCのIP>:8500` |
| 外部ネットワーク | [Tailscale VPN](https://tailscale.com/) 経由推奨 |

```bash
# IP アドレスの確認
# Windows
ipconfig
# macOS / Linux
ifconfig | grep "inet "
```

> Web UI には PIN 認証が設定されています。一般設定 → Web UI セクションで確認・変更できます。

---

## トラブルシューティング

### Python が見つからない

```
'python' is not recognized as an internal or external command
```

**解決**: Python を再インストールして **Add Python to PATH** にチェック。
macOS: `brew install python@3.12` または python.org からDL。

### pip install でエラー

```bash
pip install -r requirements.txt --user      # 権限エラー時
pip install -r requirements.txt --break-system-packages  # Linux の externally-managed
```

### PyQt6 が起動しない (Linux)

```bash
sudo apt install libgl1-mesa-glx libegl1 libxcb-xinerama0
```

### Ollama に接続できない

```bash
ollama serve            # サーバーを手動起動
curl http://localhost:11434/  # 接続テスト
```

### Web UI が表示されない

1. デスクトップアプリが起動していることを確認
2. `frontend/dist/index.html` が存在するか確認
3. なければ: `cd frontend && npm install && npm run build`

### npm install -g で権限エラー

```bash
# macOS / Linux
sudo npm install -g @anthropic-ai/claude-code

# Windows (管理者権限で cmd を開く)
npm install -g @anthropic-ai/claude-code
```

---

## 手動インストール（インストーラーを使わない場合）

```bash
# 1. 基本パッケージ
pip install -r requirements.txt

# 2. オプションツール
pip install browser-use sentence-transformers httpx
python -m playwright install chromium

# 3. 設定テンプレート
cp config/general_settings.example.json config/general_settings.json

# 4. Web UI ビルド (Node.js 必要)
cd frontend && npm install && npm run build && cd ..

# 5. CLI ツール (Node.js 必要)
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex

# 6. 起動
python HelixAIStudio.py
```

---

## アップデート

```bash
git pull
pip install -r requirements.txt
python HelixAIStudio.py
```

> `config/` と `data/` は git 管理対象外のため、アップデートで消えることはありません。

---

## クイックリファレンス

```bash
# 起動
python HelixAIStudio.py           # macOS: python3

# Ollama
ollama list                        # モデル一覧
ollama pull <model>                # モデルDL
ollama rm <model>                  # モデル削除
ollama serve                       # サーバー起動

# Claude CLI
claude auth login                  # 初回認証
claude --version                   # バージョン確認

# Web UI 再ビルド
cd frontend && npm run build && cd ..

# Virtual Desktop (Docker backend)
docker build -t helix-sandbox -f docker/sandbox/Dockerfile docker/sandbox/
```

---

*Helix AI Studio v12.8.0 — Setup Guide*
