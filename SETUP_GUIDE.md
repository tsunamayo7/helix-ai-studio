# Helix AI Studio - Setup Guide / セットアップガイド

> **Version**: v11.9.4
> **対象 OS**: Windows 10 / 11
> This guide covers first-time installation from scratch.
> このガイドでは、ゼロからの環境構築手順を網羅します。

---

## Table of Contents / 目次

1. [Prerequisites / 必要なもの](#1-prerequisites--必要なもの)
2. [Python Installation / Python のインストール](#2-python-installation--python-のインストール)
3. [Node.js Installation / Node.js のインストール](#3-nodejs-installation--nodejs-のインストール)
4. [Helix AI Studio Installation / 本体のインストール](#4-helix-ai-studio-installation--本体のインストール)
5. [API Key Setup / API キーの取得と設定](#5-api-key-setup--api-キーの取得と設定)
6. [Ollama Setup (Local LLM) / Ollama のセットアップ](#6-ollama-setup-local-llm--ollama-のセットアップ)
7. [Claude Code CLI (Optional) / Claude Code CLI の導入](#7-claude-code-cli-optional--claude-code-cli-の導入)
8. [Codex CLI (Optional) / Codex CLI の導入](#8-codex-cli-optional--codex-cli-の導入)
9. [First Launch / 初回起動](#9-first-launch--初回起動)
10. [Web UI Access / Web UI へのアクセス](#10-web-ui-access--web-ui-へのアクセス)
11. [Troubleshooting / トラブルシューティング](#11-troubleshooting--トラブルシューティング)

---

## 1. Prerequisites / 必要なもの

| Item | Required? | Notes |
|------|-----------|-------|
| Windows 10/11 | **Required** | macOS/Linux は未テスト |
| Python 3.10+ | **Required** | 3.12 推奨 |
| Node.js 18+ | Recommended | Web UI ビルド、Claude CLI に必要 |
| NVIDIA GPU (CUDA) | Recommended | Ollama でローカルLLM を実行する場合 |
| Internet connection | **Required** | API 接続、パッケージインストール |

**最低 1 つの AI バックエンドが必要です / At least one AI backend is required:**

| Backend | What you need |
|---------|--------------|
| Claude API (直接) | Anthropic API キー |
| OpenAI API (直接) | OpenAI API キー |
| Gemini API (直接) | Google API キー (無料枠あり) |
| Claude Code CLI | Node.js + `@anthropic-ai/claude-code` |
| Local LLM (Ollama) | Ollama + NVIDIA GPU |

---

## 2. Python Installation / Python のインストール

### Download / ダウンロード

1. https://www.python.org/downloads/ にアクセス
2. **Python 3.12.x** (最新の 3.12) をダウンロード

### Install / インストール

1. ダウンロードした `.exe` を実行
2. **最初の画面で必ず `Add Python to PATH` にチェック** を入れる

   ```
   ☑ Add Python 3.12 to PATH   ← ここが重要！
   ```

3. **Install Now** をクリック
4. インストール完了を待つ

### Verify / 確認

コマンドプロンプト（`Win + R` → `cmd` → Enter）を開いて:

```cmd
python --version
```

`Python 3.12.x` と表示されれば OK。

> **トラブル**: `'python' is not recognized` と出る場合 → PATH が通っていません。
> Python を再インストールして `Add Python to PATH` にチェックを入れてください。

---

## 3. Node.js Installation / Node.js のインストール

> Node.js は **Claude Code CLI** や **Web UI の再ビルド** に必要です。
> API キーのみで使う場合はスキップ可能ですが、インストール推奨です。

### Download / ダウンロード

1. https://nodejs.org/ にアクセス
2. **LTS (推奨版)** をダウンロード (v20 以上)

### Install / インストール

1. ダウンロードした `.msi` を実行
2. デフォルト設定のまま **Next** → **Install**

### Verify / 確認

```cmd
node --version
npm --version
```

両方バージョンが表示されれば OK。

---

## 4. Helix AI Studio Installation / 本体のインストール

### 4-1. Clone / ダウンロード

**Git がある場合:**

```cmd
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
```

**Git がない場合:**

1. https://github.com/tsunamayo7/helix-ai-studio にアクセス
2. **Code** → **Download ZIP** をクリック
3. ZIP を展開して、フォルダに移動

### 4-2. Run Installer / インストーラー実行

```cmd
install.bat
```

インストーラーが自動で以下を実行します:

| Step | Content |
|------|---------|
| 1/6 | Python バージョン確認 (3.10 以上) |
| 2/6 | pip アップグレード |
| 3/6 | コア依存パッケージ (`requirements.txt`) |
| 4/6 | httpx (URL 取得用) |
| 5/6 | データディレクトリ作成 |
| 6/6 | 設定ファイルテンプレート配置 |

その後、オプション機能について Y/N で選択を求められます:

| Option | Description | Recommendation |
|--------|-------------|---------------|
| browser-use | JS レンダリング対応 URL 取得 | 後でも OK |
| sentence-transformers | ローカル Embedding | Ollama があれば不要 |
| anthropic SDK | Claude API 直接接続 | **API 利用なら Y** |
| openai SDK | OpenAI API 直接接続 | **API 利用なら Y** |

> **ヒント**: よくわからない場合は全て `Y` を選んでおけば問題ありません。

### 4-3. Manual Install (Alternative) / 手動インストール

```cmd
pip install -r requirements.txt
pip install anthropic openai google-genai httpx
```

---

## 5. API Key Setup / API キーの取得と設定

Helix AI Studio は複数の AI プロバイダーに対応しています。
**少なくとも 1 つ** の API キーを設定してください。

### 5-1. Anthropic (Claude)

1. https://console.anthropic.com/settings/keys にアクセス
2. アカウント作成 / ログイン
3. **Create Key** をクリック
4. キーをコピー (`sk-ant-...` で始まる文字列)

> **料金**: 従量課金制。利用量に応じて課金されます。
> 参考: https://www.anthropic.com/pricing

### 5-2. OpenAI (GPT / Codex)

1. https://platform.openai.com/api-keys にアクセス
2. アカウント作成 / ログイン
3. **Create new secret key** をクリック
4. キーをコピー (`sk-...` で始まる文字列)

> **料金**: 従量課金制。
> 参考: https://openai.com/pricing

### 5-3. Google (Gemini)

1. https://aistudio.google.com/apikey にアクセス
2. Google アカウントでログイン
3. **Create API Key** をクリック
4. キーをコピー

> **料金**: 無料枠あり (1 分あたり 15 リクエストまで)。
> 参考: https://ai.google.dev/pricing

### 5-4. Brave Search API (Optional)

> localAI の Web 検索機能で使用します。

1. https://brave.com/search/api/ にアクセス
2. アカウント作成
3. **Free** プラン (月 2,000 クエリ) を選択
4. API キーを取得

### 5-5. Setting API Keys / キーの設定方法

**方法 A: アプリ内で設定 (推奨)**

1. `python HelixAIStudio.py` でアプリを起動
2. **一般設定** タブを開く
3. **API Keys** セクションに各キーを貼り付け
4. **保存** をクリック

**方法 B: 設定ファイルを直接編集**

`config/general_settings.json` を開いて:

```json
{
  "anthropic_api_key": "sk-ant-xxxxx",
  "openai_api_key": "sk-xxxxx",
  "google_api_key": "AIzaSyxxxxx",
  "brave_search_api_key": "BSAxxxxx"
}
```

**方法 C: 環境変数**

```cmd
set ANTHROPIC_API_KEY=sk-ant-xxxxx
set OPENAI_API_KEY=sk-xxxxx
set GEMINI_API_KEY=AIzaSyxxxxx
```

> **セキュリティ**: `config/general_settings.json` は `.gitignore` に含まれています。
> 絶対に API キーを Git にコミットしないでください。

---

## 6. Ollama Setup (Local LLM) / Ollama のセットアップ

> Ollama は **localAI** タブおよび **mixAI** の Phase 2 で使用します。
> API キーのみで使う場合はスキップ可能です。

### 6-1. Install / インストール

1. https://ollama.com/download にアクセス
2. **Windows** 版をダウンロード
3. インストーラーを実行

### 6-2. Verify / 確認

```cmd
ollama --version
```

### 6-3. Pull Models / モデルのダウンロード

```cmd
:: 汎用モデル (推奨)
ollama pull qwen3:32b

:: コーディング特化
ollama pull devstral:24b

:: 軽量モデル (VRAM が少ない場合)
ollama pull qwen3:8b
```

> **VRAM 目安**:
> - 8B モデル: 6GB VRAM
> - 27-32B モデル: 16-24GB VRAM
> - 70B+ モデル: 48GB+ VRAM

### 6-4. Start Ollama / 起動

Ollama はインストール後、通常は自動起動します (タスクトレイに表示)。

手動で起動する場合:

```cmd
ollama serve
```

接続確認:

```cmd
curl http://localhost:11434/
```

`Ollama is running` と表示されれば OK。

### 6-5. Configure in Helix / アプリ内設定

1. アプリ起動後、**localAI** タブまたは **mixAI** タブを開く
2. **設定** でモデルを選択
3. 各カテゴリ (coding / research / reasoning / translation / vision) にモデルを割り当て

---

## 7. Claude Code CLI (Optional) / Claude Code CLI の導入

> Claude Code CLI は **mixAI** の Phase 1/3 (CLI 経由) および **cloudAI** の CLI モードで使用します。
> API 直接接続 (v11.5.0+) を使う場合はスキップ可能です。

### Install / インストール

```cmd
npm install -g @anthropic-ai/claude-code
```

### Verify / 確認

```cmd
claude --version
```

### First-time Auth / 初回認証

```cmd
claude auth login
```

ブラウザが開き、Anthropic アカウントで認証します。

> 公式ドキュメント: https://docs.claude.com/en/docs/claude-code/overview

---

## 8. Codex CLI (Optional) / Codex CLI の導入

> OpenAI の Codex CLI は **cloudAI** タブで GPT-5.3-Codex を CLI 経由で使用する場合に必要です。
> API 直接接続を使う場合はスキップ可能です。

### Install / インストール

```cmd
npm install -g @openai/codex
```

### Verify / 確認

```cmd
codex --version
```

---

## 9. First Launch / 初回起動

```cmd
python HelixAIStudio.py
```

### 初回起動チェックリスト

1. **アプリが起動する** → GUI ウィンドウが表示されれば OK
2. **一般設定タブ** → API キーを設定
3. **cloudAI タブ** → クラウドモデルでチャットを試す
4. **localAI タブ** → Ollama モデルでチャットを試す (Ollama 起動時のみ)
5. **mixAI タブ** → 3+1 Phase パイプラインを実行

### Cloud Model Registration / クラウドモデルの登録

初回起動時、`config/cloud_models.json` は空です。

1. **cloudAI** タブ → **設定** を開く
2. **クラウドモデル管理** でモデルを追加

例:

| Display Name | Model ID | Provider |
|-------------|----------|----------|
| Claude Sonnet 4 | claude-sonnet-4-20250514 | anthropic |
| Claude Opus 4 | claude-opus-4-20250514 | anthropic |
| GPT-4o | gpt-4o | openai |
| Gemini 2.5 Pro | gemini-2.5-pro | google |

---

## 10. Web UI Access / Web UI へのアクセス

Helix AI Studio はデスクトップアプリ起動時に Web サーバーも自動起動します。

### Same PC / 同じ PC からアクセス

```
http://localhost:8500
```

### Other Devices (LAN) / 他のデバイスからアクセス

```
http://<PCのIPアドレス>:8500
```

IP アドレスの確認:

```cmd
ipconfig
```

> `IPv4 Address` の値を使用 (例: `192.168.1.100`)

### Remote Access / リモートアクセス

外部ネットワークからのアクセスには **Tailscale VPN** の利用を推奨します:

1. https://tailscale.com/ でアカウント作成
2. PC とモバイルデバイスに Tailscale をインストール
3. Tailscale IP を使ってアクセス

> **注意**: Web UI にはPIN 認証が設定されています。
> 一般設定タブ → Web UI セクション で PIN を確認/変更できます。

---

## 11. Troubleshooting / トラブルシューティング

### `python` コマンドが見つからない

```
'python' is not recognized as an internal or external command
```

**原因**: Python が PATH に追加されていない
**解決**: Python を再インストールし、`Add Python to PATH` にチェックを入れる

---

### `pip install` でエラーが出る

```
ERROR: Could not install packages due to an EnvironmentError
```

**解決**: 管理者権限でコマンドプロンプトを開く、または `--user` オプションを付ける:

```cmd
pip install -r requirements.txt --user
```

---

### PyQt6 のインポートエラー

```
ModuleNotFoundError: No module named 'PyQt6'
```

**解決**:

```cmd
pip install PyQt6 PyQt6-WebEngine
```

---

### Ollama に接続できない

```
Connection refused: localhost:11434
```

**確認事項**:
1. Ollama がインストールされているか: `ollama --version`
2. Ollama が起動しているか: タスクトレイを確認
3. 手動起動: `ollama serve`
4. ファイアウォールがブロックしていないか確認

---

### API キーエラー (401 Unauthorized)

**確認事項**:
1. API キーが正しくコピーされているか (前後の空白に注意)
2. API キーが有効か (プロバイダーのダッシュボードで確認)
3. 課金設定が完了しているか (Anthropic / OpenAI は要クレジットカード登録)

---

### Web UI にアクセスできない

**確認事項**:
1. デスクトップアプリが起動しているか
2. ポート 8500 が他のアプリに使われていないか
3. ファイアウォールがポート 8500 を許可しているか
4. 他デバイスからの場合、同じネットワーク上にいるか

---

### `npm install -g` で権限エラー

```
EACCES: permission denied
```

**解決**: 管理者権限でコマンドプロンプトを開いて実行:

```cmd
# 管理者権限の cmd で
npm install -g @anthropic-ai/claude-code
```

---

### frontend/dist が空 / Web UI が表示されない

```cmd
cd frontend
npm install
npm run build
cd ..
```

> `install.bat` を実行すると Node.js が検出された場合自動でビルドされます。

---

## Quick Reference / クイックリファレンス

```
# 起動
python HelixAIStudio.py

# Ollama モデル管理
ollama list                    # インストール済みモデル一覧
ollama pull <model>            # モデルダウンロード
ollama rm <model>              # モデル削除

# Claude Code CLI
claude auth login              # 認証
claude --version               # バージョン確認

# Web UI 再ビルド
cd frontend && npm run build && cd ..
```

---

*This guide is part of Helix AI Studio v11.5.4. For detailed architecture and feature documentation, see the [BIBLE](BIBLE/) directory.*
