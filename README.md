# Helix AI Studio

All-in-one AI chat studio — local LLM, cloud API, CLI agents, shared memory, web search, file operations, CrewAI multi-agent, and pipeline in a single web app.

ローカルLLM・クラウドAPI・CLIエージェント・共有記憶・Web検索・ファイル操作・CrewAIマルチエージェント・パイプラインを統合したWebベースのAI開発環境です。

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features / 機能一覧

### 7 AI Providers / 7つのAIプロバイダ

| Provider | Method | Model Detection | Streaming |
|----------|--------|:-:|:-:|
| **Ollama** | HTTP API (localhost:11434) | Auto | Yes |
| **Claude API** | Anthropic SDK | Auto (key validation) | Yes |
| **OpenAI API** | OpenAI SDK | Auto (`models.list()`) | Yes |
| **OpenAI-Compatible** | HTTP API (vLLM, llama.cpp, LM Studio) | Auto (`/v1/models`) | Yes |
| **Claude Code CLI** | `claude -p` | Auto-detect installed | Pseudo |
| **Codex CLI** | `codex exec` | Auto-detect installed | Pseudo |
| **Gemini CLI** | `gemini -p` | Auto-detect installed | Pseudo |

CLI tools are automatically detected — if not installed, they are hidden from the UI.

CLIツールは自動検出されます。未インストールの場合はUIに表示されません。

### Chat / チャット

- WebSocket streaming chat with real-time response / WebSocketストリーミングチャット
- Provider and model switching with one click / プロバイダ・モデルをワンクリック切替
- Model info badge on every response (provider type, model name, response time) / 回答ごとにモデル情報バッジ表示
- Conversation history auto-save and restore / 会話履歴の自動保存・復元
- `@search` command for web search (DuckDuckGo, free) / Web検索コマンド
- `@file` command to read local files / ファイル読み取りコマンド
- `@ls` command to list directory contents / ディレクトリ一覧コマンド

### Mem0 Shared Memory / Mem0 共有記憶

- Search and add memories via Mem0 HTTP API / Mem0 HTTP APIで記憶の検索・追加
- Auto-inject relevant memories into chat context / チャット時に関連記憶を自動注入
- Qdrant direct search fallback (when Mem0 HTTP returns empty) / Qdrant直接検索フォールバック
- Toggle ON/OFF with visible button / ON/OFFボタンで切替
- Shared across all AI tools (Claude Code, Codex, Gemini CLI, Open WebUI) / 全AIツールで記憶共有

### Pipeline / パイプライン

3-step automated pipeline for complex tasks:

3ステップ自動パイプライン:

```
Step 1: Plan (Cloud/CLI/Local) — タスクを分析し実行計画を生成
Step 2: Execute (Local/CrewAI) — 計画に基づいて実行
Step 3: Verify (Cloud/CLI/Local) — 結果を検証し品質評価
```

- All steps support any provider (Cloud API, CLI, Ollama) / 全ステップで任意のプロバイダを選択可能
- Step 2 supports CrewAI multi-agent mode / Step 2はCrewAIマルチエージェント対応
- Mem0 memories auto-injected into all steps / 全ステップでMem0記憶を自動注入

### CrewAI Multi-Agent / CrewAI マルチエージェント

- Ollama-only, VRAM-managed multi-agent execution / Ollamaローカル専用、VRAM管理付き
- 3 preset teams / プリセット3チーム:
  - **dev_team**: Architect + Engineer + Reviewer
  - **research_team**: Researcher + Analyst
  - **writing_team**: Writer + Editor
- Per-role model selection from Ollama models / 役割ごとにOllamaモデルを選択
- Real-time VRAM usage estimation / VRAMリアルタイム推定表示
- Sequential execution to minimize VRAM switching / 同一モデルグループ化でVRAM切替最小化

### Web Search & File Operations / Web検索・ファイル操作

- **Web Search**: DuckDuckGo (free, no API key required) / DuckDuckGo無料検索
- **File Read**: Read local files with path traversal protection / ファイル読み取り（パストラバーサル防止付き）
- **File Write**: Write files to allowed directories / ファイル書き込み
- **Directory List**: Browse local file system / ディレクトリ一覧
- Chat commands: `@search query`, `@file path`, `@ls path` / チャットコマンド対応

### UI

- Dark theme / ダークテーマ
- Japanese UI / 日本語インターフェース
- Responsive design (mobile accessible via Tailscale) / レスポンシブ（Tailscale経由でスマホ対応）
- Markdown rendering with syntax highlight / Markdownレンダリング＋コードハイライト
- Code block copy button / コードブロックコピーボタン

---

## Quick Start / クイックスタート

### Option 1: Local Install / ローカルインストール

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
uv sync
uv run python run.py
```

Open http://localhost:8504 in your browser.

ブラウザで http://localhost:8504 を開いてください。

### Option 2: Docker Compose / Docker一括起動

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
docker compose up -d
```

This starts Helix AI Studio (8504) + Ollama (11434) + Qdrant (6333) + Mem0 (8080).

---

## Setup / セットアップ

### 1. Ollama (Required / 必須)

Install [Ollama](https://ollama.com/) and pull a model:

```bash
ollama pull gemma3:27b
```

All available Ollama models are auto-detected.

### 2. Cloud AI (Optional / 任意)

Open Settings (http://localhost:8504/settings) and enter API keys:

- **Claude**: [Anthropic Console](https://console.anthropic.com/)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/)

### 3. CLI Agents (Optional / 任意)

Automatically detected if installed:

```bash
npm install -g @anthropic-ai/claude-code  # Claude Code
npm install -g @openai/codex              # Codex CLI
npm install -g @google/gemini-cli         # Gemini CLI
```

### 4. Mem0 Shared Memory (Optional / 任意)

```bash
ollama pull qwen3-embedding:8b  # Embedding model
# Start Qdrant and Mem0 HTTP server
# Configure in Settings: URL = http://localhost:8080
```

### 5. Large MoE Models (Optional / 任意)

For running 400B+ MoE models locally with llama.cpp:

See [docs/qwen35-397b-setup.md](docs/qwen35-397b-setup.md) for Qwen3.5-397B-A17B setup guide.

---

## Architecture / アーキテクチャ

```
Browser (http://localhost:8504)
    |
    |-- WebSocket --- streaming chat
    |-- REST API ---- settings, history, models, memory, pipeline, tools
    |
Helix AI Studio (FastAPI + Jinja2 + Tailwind CSS + Alpine.js)
    |
    |-- Cloud AI ---------> Claude API / OpenAI API
    |-- Local AI ---------> Ollama / OpenAI-Compatible (vLLM, llama.cpp)
    |-- CLI Agents -------> Claude Code / Codex / Gemini CLI
    |-- Memory -----------> Mem0 HTTP -> Qdrant + Ollama Embedding
    |-- CrewAI -----------> Multi-agent (Ollama-only, VRAM-managed)
    |-- Web Search -------> DuckDuckGo (free)
    |-- File Operations --> Local filesystem (path traversal protected)
    |-- Pipeline ---------> Step1 Plan -> Step2 Execute -> Step3 Verify
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, aiosqlite, httpx |
| Frontend | Jinja2, Tailwind CSS (CDN), Alpine.js (CDN) |
| Database | SQLite |
| AI | anthropic SDK, openai SDK, Ollama HTTP API |
| Memory | Mem0 HTTP API, Qdrant direct search fallback |
| Search | DuckDuckGo (free, no API key) |

---

## Chat Commands / チャットコマンド

| Command | Description |
|---------|-------------|
| `@search Python FastAPI` | Web search and inject results into LLM context |
| `@file C:/path/to/file.py` | Read file and inject contents into LLM context |
| `@ls C:/path/to/dir` | List directory and inject into LLM context |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| WebSocket | `/ws/chat` | Streaming chat |
| GET | `/api/models` | All provider models |
| GET/PUT | `/api/settings` | Settings CRUD |
| GET | `/api/conversations` | Conversation list |
| POST | `/api/memory/search` | Search Mem0 memories |
| POST | `/api/tools/search` | Web search (DuckDuckGo) |
| POST | `/api/tools/files/read` | Read file |
| POST | `/api/pipeline/run` | Run pipeline |
| GET | `/api/crew/teams` | CrewAI preset teams |
| GET | `/api/crew/vram` | VRAM status |

---

## Related Projects / 関連プロジェクト

| Project | Description |
|---------|-------------|
| [helix-pilot](https://github.com/tsunamayo7/helix-pilot) | GUI automation MCP server — AI controls Windows desktop |
| [helix-sandbox](https://github.com/tsunamayo7/helix-sandbox) | Secure sandbox MCP server — Docker + Windows Sandbox |

---

## Development / 開発

```bash
uv sync --dev
uv run python -m pytest tests/ -v
uv run ruff check helix_studio/
```

## License

MIT
