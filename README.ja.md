# Helix AI Studio

7つのAIプロバイダ・RAGナレッジベース・MCPツール統合・Mem0共有記憶・CrewAIマルチエージェント・パイプラインを統合した軽量Webアプリです。

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/)
[![Ollama](https://img.shields.io/badge/Ollama-supported-black?logo=ollama&logoColor=white)](https://ollama.com/)
[![Self-Hosted](https://img.shields.io/badge/Self--Hosted-100%25-green)](https://github.com/tsunamayo7/helix-ai-studio)

> **[English README (README.md)](README.md)**

---

## デモ

### チャット — ストリーミング応答

![ストリーミングデモ](docs/images/ja/gh_streaming_demo.gif)

OllamaによるリアルタイムWebSocketストリーミング。プロンプトを入力して送信すると、シンタックスハイライト付きのコードブロックが即座にストリーミング表示されます。

### プロバイダ & モデル切替

![プロバイダ切替](docs/images/ja/gh_provider_switch.gif)

ローカル (Ollama)・Cloud API (Claude/OpenAI)・CLI (Claude Code/Codex/Gemini) をワンクリックで切替。モデルはプロバイダに応じて自動読み込み。

### アプリツアー — 全機能

![アプリツアー](docs/images/ja/gh_navigation_demo.gif)

チャット → パイプライン → ナレッジベース → 設定 — すべてが1つの軽量Webアプリに。

### スクリーンショット

| チャットUI | RAGナレッジベース | パイプライン | 設定 |
|:---:|:---:|:---:|:---:|
| ![チャット](docs/images/ja/gh_01_chat_main.png) | ![RAG](docs/images/ja/gh_03_knowledge_base.png) | ![パイプライン](docs/images/ja/gh_04_pipeline.png) | ![設定](docs/images/ja/gh_05_settings.png) |
| ダークテーマ、サイドバー、履歴 | ドラッグ&ドロップ、Qdrant検索 | 計画 → 実行 → 検証 | Cloud/Local/Mem0/MCP設定 |

---

## なぜ Helix AI Studio？

- **7プロバイダを1つのUIで** — Ollama、Claude、OpenAI、vLLM/llama.cpp、Claude Code CLI、Codex CLI、Gemini CLI。ワンクリックで切替。
- **100% ローカル対応** — Ollama + Qdrant だけでマシン上で完全に動作。クラウドAPI不要。
- **ベンダーロックインなし** — お好みのモデルを使い、いつでもプロバイダを切替、データは自分のハードウェアに。
- **RAG + Mem0 + MCP を一つのアプリに** — ナレッジベース、永続共有記憶、外部ツール統合 — すべてビルトイン、プラグイン不要。

---

## 特徴

### 7つのAIプロバイダ

| プロバイダ | 方式 | モデル検出 | ストリーミング |
|----------|--------|:-:|:-:|
| **Ollama** | HTTP API (localhost:11434) | 自動 | Yes |
| **Claude API** | Anthropic SDK | 自動 (キー検証) | Yes |
| **OpenAI API** | OpenAI SDK | 自動 (`models.list()`) | Yes |
| **OpenAI互換** | HTTP API (vLLM, llama.cpp, LM Studio) | 自動 (`/v1/models`) | Yes |
| **Claude Code CLI** | `claude -p` | 自動検出 | 疑似 |
| **Codex CLI** | `codex exec` | 自動検出 | 疑似 |
| **Gemini CLI** | `gemini -p` | 自動検出 | 疑似 |

CLIツールは自動検出 — 未インストールの場合はUIから非表示。

### RAG ナレッジベース

- ドラッグ&ドロップでドキュメントアップロード (.txt, .md, .py, .json 他25+形式)
- **Qdrant** ベクトルDBでセマンティック検索
- **Ollama embedding** (qwen3-embedding:8b) — ローカル実行、API費用ゼロ
- 関連ナレッジチャンクをチャットコンテキストに自動注入
- 検索テストUI搭載

### MCP ツール統合

- **Model Context Protocol** クライアントで外部ツール接続
- **stdio transport** — 任意のMCPサーバーと互換
- サーバー起動/停止管理、ツール検出・実行

### チャット

- WebSocketストリーミングでリアルタイム応答
- プロバイダ・モデルをワンクリックで切替
- 応答ごとにモデル情報バッジ表示
- 会話履歴の自動保存・復元
- `@search`, `@file`, `@ls` チャットコマンド
- Mem0記憶 + RAGナレッジをコンテキストに自動注入

### Mem0 共有記憶

- Mem0 HTTP API で記憶の検索・追加
- Qdrant直接検索フォールバック
- 全AIツール（Claude Code, Codex, Open WebUI）で共有

### パイプライン

3ステップ自動パイプライン:

```
Step 1: 計画 (Cloud/CLI/Local) — タスク分析と計画生成
Step 2: 実行 (Local/CrewAI) — 計画の実行
Step 3: 検証 (Cloud/CLI/Local) — 結果検証と品質評価
```

### CrewAI マルチエージェント

- Ollamaのみ、VRAM管理付きマルチエージェント実行
- 3つのプリセットチーム: dev_team, research_team, writing_team
- ロールごとのモデル選択とVRAM推定

### UI

- ダークテーマ + レスポンシブデザイン
- **日本語 / 英語** 言語切替
- Markdownレンダリング + シンタックスハイライト + コードコピー
- Tailscale経由でモバイルアクセス可能

---

## クイックスタート

### 方法1: ローカルインストール

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
uv sync
uv run python run.py
```

ブラウザで http://localhost:8504 を開く。

### 方法2: Docker Compose

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
docker compose up -d
```

Helix AI Studio + Ollama + Qdrant + Mem0 が起動します。

> **Note**: ローカルインストールはポート **8504**、Docker Compose はポート **8502**。

---

## セットアップ

### 1. Ollama（必須）

```bash
ollama pull gemma3:27b
ollama pull qwen3-embedding:8b  # RAG & Mem0用
```

### 2. Qdrant（RAGに必須）

```bash
docker run -d -p 6333:6333 qdrant/qdrant:latest
```

### 3. Cloud AI（任意）

設定画面でAPIキーを入力:
- **Claude**: [Anthropic Console](https://console.anthropic.com/)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/)

### 4. CLIエージェント（任意）

```bash
npm install -g @anthropic-ai/claude-code  # Claude Code
npm install -g @openai/codex              # Codex CLI
npm install -g @google/gemini-cli         # Gemini CLI
```

### 5. Mem0 共有記憶（任意）

設定画面でMem0 HTTP URLを設定（デフォルト: http://localhost:8080）。

---

## 関連プロジェクト

| プロジェクト | 説明 |
|---------|-------------|
| [helix-pilot](https://github.com/tsunamayo7/helix-pilot) | GUI自動操作MCPサーバー — AIがWindowsデスクトップを操作 |
| [helix-sandbox](https://github.com/tsunamayo7/helix-sandbox) | セキュアサンドボックスMCPサーバー — Docker + Windows Sandbox |

---

## サポート

このプロジェクトが役に立ったら、ぜひスターをお願いします！他の人の目に留まりやすくなり、開発のモチベーションにもなります。

[![Star History Chart](https://api.star-history.com/svg?repos=tsunamayo7/helix-ai-studio&type=Date)](https://star-history.com/#tsunamayo7/helix-ai-studio&Date)

---

## ライセンス

MIT
