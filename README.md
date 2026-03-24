# Helix AI Studio

All-in-one AI chat studio — local LLM, cloud API, CLI agents, shared memory, and multi-step pipeline in a single web app.

ローカルLLM・クラウドAPI・CLIエージェント・共有記憶・マルチステップパイプラインを統合したWebベースのAI開発環境です。

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features / 機能

### AI Providers / AIプロバイダ

| Provider | Method | Model Detection | Streaming |
|----------|--------|:-:|:-:|
| **Ollama** | HTTP API (localhost:11434) | Auto | Yes |
| **Claude API** | Anthropic SDK | Auto (key validation) | Yes |
| **OpenAI API** | OpenAI SDK | Auto (`models.list()`) | Yes |
| **OpenAI-Compatible** | HTTP API (vLLM, llama.cpp, LM Studio) | Auto (`/v1/models`) | Yes |
| **Claude Code CLI** | `claude -p` | Auto-detect installed | Pseudo |
| **Codex CLI** | `codex exec` | Auto-detect installed | Pseudo |
| **Gemini CLI** | `gemini -p` | Auto-detect installed | Pseudo |

- CLI tools are automatically detected. If not installed, they are simply hidden from the UI.
- CLIツールは自動検出されます。未インストールの場合はUIに表示されません。

### Core Features / コア機能

- **Chat** — ストリーミングチャット（WebSocket）、プロバイダ・モデルをワンクリック切替
- **Mem0 Memory** — 共有記憶の検索・追加。チャット時に関連記憶を自動注入
- **Pipeline** — 3ステップ自動パイプライン（Cloud計画 → Local実行 → Cloud検証）
- **History** — 全会話を自動保存・検索・復元
- **Settings** — APIキー・接続先をブラウザから設定。接続テスト付き

### UI

- Dark theme (ダークテーマ固定)
- Japanese UI (日本語インターフェース)
- Responsive (スマートフォンからもアクセス可能)
- Markdown rendering with syntax highlight
- Code block copy button

---

## Quick Start / クイックスタート

### Option 1: Local Install / ローカルインストール

```bash
# Clone
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# Install (requires Python 3.12+ and uv)
uv sync

# Start
uv run python run.py
```

Open http://localhost:8502 in your browser.

ブラウザで http://localhost:8502 を開いてください。

### Option 2: Docker Compose / Docker一括起動

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# Start all services (Ollama + Qdrant + Mem0 + Helix AI Studio)
docker compose up -d

# Open browser
# http://localhost:8502
```

This starts:
- **Helix AI Studio** on port 8502
- **Ollama** on port 11434 (GPU-accelerated)
- **Qdrant** on port 6333 (vector database for Mem0)
- **Mem0 HTTP** on port 8080 (shared memory server)

---

## Setup / セットアップ

### 1. Ollama (Local LLM)

Install [Ollama](https://ollama.com/) and pull a model:

```bash
ollama pull gemma3:27b
```

Helix AI Studio will auto-detect all available Ollama models.

### 2. Cloud AI (Optional)

Open Settings page (http://localhost:8502/settings) and enter your API keys:

- **Claude**: Get key from [Anthropic Console](https://console.anthropic.com/)
- **OpenAI**: Get key from [OpenAI Platform](https://platform.openai.com/)

Models are auto-detected after entering a valid key.

### 3. CLI Agents (Optional)

If you have any of these installed, they will be auto-detected:

```bash
# Claude Code (Anthropic)
npm install -g @anthropic-ai/claude-code

# Codex CLI (OpenAI)
npm install -g @openai/codex

# Gemini CLI (Google)
npm install -g @google/gemini-cli
```

### 4. Mem0 Shared Memory (Optional)

For persistent memory across sessions, set up Mem0:

```bash
# Install Qdrant
# Install Ollama embedding model
ollama pull qwen3-embedding:8b

# Start Mem0 HTTP server
# Configure in Settings page: URL = http://localhost:8080
```

Or use Docker Compose (see above) which sets up everything automatically.

### 5. OpenAI-Compatible API (Optional)

If you run vLLM, llama.cpp server, LM Studio, or any OpenAI-compatible API:

1. Open Settings
2. Enter the API URL (e.g., `http://localhost:8000/v1`)
3. Enter API key if required
4. Models are auto-detected from `/v1/models`

---

## Architecture / アーキテクチャ

```
Browser (http://localhost:8502)
    |
    |-- WebSocket (streaming chat)
    |-- REST API (settings, history, models, memory, pipeline)
    |
Helix AI Studio (FastAPI + Jinja2 + Tailwind + Alpine.js)
    |
    |-- Cloud AI ------> Claude API (anthropic SDK)
    |                |-> OpenAI API (openai SDK)
    |
    |-- Local AI ------> Ollama (HTTP API)
    |                |-> OpenAI-Compatible (vLLM, llama.cpp, etc.)
    |
    |-- CLI Agents ----> Claude Code CLI (claude -p)
    |                |-> Codex CLI (codex exec)
    |                |-> Gemini CLI (gemini -p)
    |
    |-- Memory --------> Mem0 HTTP API -> Qdrant + Ollama Embedding
    |
    |-- Pipeline ------> Step 1: Cloud AI (plan)
                     |-> Step 2: Local LLM (execute)
                     |-> Step 3: Cloud AI (verify)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, aiosqlite |
| Frontend | Jinja2, Tailwind CSS (CDN), Alpine.js (CDN) |
| Database | SQLite |
| Cloud AI | anthropic SDK, openai SDK |
| Local AI | Ollama HTTP API, OpenAI-compatible API |
| CLI | claude, codex, gemini (auto-detected) |
| Memory | Mem0 HTTP API, Qdrant, Ollama Embedding |
| Streaming | WebSocket |

---

## Pipeline / パイプライン

3-step automated pipeline for complex tasks:

```
Step 1: Plan (Cloud AI)
  "This task requires: 1) data model design, 2) API implementation, 3) tests"
      |
Step 2: Execute (Local LLM)
  Runs the plan using local LLM (Ollama) -- no API costs
      |
Step 3: Verify (Cloud AI)
  Reviews the output for quality, correctness, and completeness
```

- Each step's model is configurable
- Progress is shown in real-time via WebSocket
- Results are saved to database for review

---

## Configuration / 設定

All settings are managed from the browser UI (http://localhost:8502/settings).

| Setting | Default | Description |
|---------|---------|-------------|
| Ollama URL | `http://localhost:11434` | Ollama server address |
| OpenAI-Compatible URL | (empty) | vLLM / llama.cpp / LM Studio URL |
| Mem0 URL | `http://localhost:8080` | Mem0 shared memory server |
| Mem0 User ID | `tsunamayo7` | User ID for memory isolation |
| Mem0 Auto Inject | `true` | Auto-inject relevant memories into chat |
| Default Cloud Model | `claude-sonnet-4-20250514` | Default model for cloud chat |
| Default Local Model | `gemma3:27b` | Default model for local chat |

API keys can also be set via environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

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

---

## License

MIT
