---
title: "Helix AI Studio v2.0: 7 AI Providers, Pipeline, and CrewAI in One Self-Hosted App"
published: false
description: "I built a self-hosted AI chat app that connects 7 providers, adds a 3-step pipeline, and CrewAI multi-agent — all in one lightweight web UI."
tags: ai, python, opensource, webdev
cover_image: https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_01_chat_main.png
---

## TL;DR

I rebuilt my self-hosted AI chat app from the ground up. **Helix AI Studio v2.0** now connects **7 AI providers**, runs a **3-step automated pipeline** (Plan → Execute → Final Answer), and supports **CrewAI multi-agent** teams — all in a single lightweight web UI you can run entirely on your own hardware.

**[Live Demo](https://helix-ai-studio.onrender.com)** | **[GitHub](https://github.com/tsunamayo7/helix-ai-studio)** | MIT License

---

## Why I Built This

A few months ago, I shared the [first version of Helix AI Studio](https://dev.to/tsunamayo7/i-built-a-self-hosted-ai-chat-app-that-connects-7-providers-in-one-ui-12ok) on Dev.to. The idea was simple: I was tired of switching between ChatGPT, Claude, Ollama's terminal, and various other AI tools throughout my day. I wanted **one UI** that could talk to all of them.

The response from the community was encouraging, but as I kept using it daily, I realized the app needed to go beyond just "chat with multiple providers." I needed:

- **Automated workflows** — not just Q&A, but multi-step task execution
- **Team-based AI** — multiple agents collaborating on complex problems
- **CLI integration** — using Claude Code, Codex, and Gemini CLI directly from the web UI
- **Better UX** — real-time streaming of final answers, language switching, smoother navigation

So I rebuilt it. Here's what v2.0 looks like.

---

## What's New in v2.0

### 1. 3-Step Pipeline: Plan → Execute → Final Answer

This is the biggest addition. Instead of just sending a prompt and getting a response, v2.0 can run an **automated pipeline**:

```
Step 1: Plan    — A cloud/CLI model analyzes your task and generates a plan
Step 2: Execute — A local model (or CrewAI team) executes the plan
Step 3: Final Answer — A cloud/CLI model verifies results and delivers the answer
```

![Pipeline Demo](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_pipeline_demo.gif)

Why does this matter? Because different models are good at different things. A powerful cloud model like Claude can create an excellent plan, a fast local model can do the heavy lifting, and then Claude can verify the output. You get **cloud-quality reasoning with local-model execution** — and you control every step.

The final answer now streams in real-time, so you see the verified result as it's being generated rather than waiting for the entire pipeline to complete.

### 2. CrewAI Multi-Agent Teams

Sometimes a single model isn't enough. v2.0 integrates **CrewAI** for multi-agent collaboration, running entirely on local models via Ollama.

Three preset teams are ready to go:

- **dev_team** — for coding tasks (architect, developer, reviewer)
- **research_team** — for research and analysis
- **writing_team** — for content creation

Each agent in the team can use a different model, and the system estimates VRAM usage so you know if your GPU can handle it before kicking off the task. This is all Ollama-only — no cloud API costs for multi-agent runs.

### 3. CLI Agent Integration

This was a game-changer for my workflow. v2.0 can use **Claude Code CLI**, **Codex CLI**, and **Gemini CLI** as providers, directly from the web UI.

![Provider Switch](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_provider_switch.gif)

The CLI tools are auto-detected — if you have them installed, they appear in the provider dropdown. If not, they're hidden. No configuration needed. This means you can use Claude Code's full capabilities (file editing, shell commands, etc.) through Helix's interface, alongside your local Ollama models and cloud APIs.

### 4. English/Japanese UI

The entire UI now supports both English and Japanese with a one-click toggle. As a developer based in Japan, this was important for my daily use, but it also makes the project accessible to a wider audience.

---

## The Full Feature Set

For those who missed the v1 post, here's what Helix AI Studio brings together:

### 7 AI Providers in One UI

| Provider | Method | Streaming |
| --- | --- | :---: |
| **Ollama** | HTTP API (localhost) | Yes |
| **Claude API** | Anthropic SDK | Yes |
| **OpenAI API** | OpenAI SDK | Yes |
| **vLLM / llama.cpp / LM Studio** | OpenAI-compatible API | Yes |
| **Claude Code CLI** | `claude -p` | Pseudo |
| **Codex CLI** | `codex exec` | Pseudo |
| **Gemini CLI** | `gemini -p` | Pseudo |

Switch between any provider with one click. Models auto-load per provider.

![Streaming Demo](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_streaming_demo.gif)

### RAG Knowledge Base

Drag and drop your documents (.txt, .md, .py, .json, PDF, Office files, and 25+ formats) and they're automatically chunked, embedded, and stored in Qdrant. When you chat, relevant knowledge is auto-injected into context.

The RAG pipeline is serious:

- **Docling Parser** for PDF, Office docs, and images
- **Hybrid search** — dense vector + BM25 sparse + RRF fusion
- **TEI Reranker** (bge-reranker-v2-m3) for precision re-scoring
- **Ollama embedding** (qwen3-embedding) — runs locally, zero API cost

### Mem0 Shared Memory

This is one of my favorite features. Helix uses **Mem0** for persistent, cross-session memory backed by Qdrant. The AI remembers your preferences, past decisions, and context across conversations.

Even better — the memory is **shared across tools**. My Claude Code CLI sessions, Codex CLI, and Open WebUI all read from the same Qdrant collection. It's like giving all your AI tools a shared brain.

### MCP Tool Integration

Helix includes a **Model Context Protocol** client that can connect to any MCP server via stdio transport. This means you can extend the AI's capabilities with external tools — file system access, database queries, API calls, whatever MCP servers you have running.

### Web Search

Click the search button or let the LLM decide on its own when it needs current information. Tool-use capable models can autonomously trigger web searches mid-conversation.

![Search Demo](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_search_demo.gif)

---

## Tech Stack

Helix AI Studio is deliberately lightweight:

- **Backend**: FastAPI + Python 3.12
- **Frontend**: Jinja2 templates + Tailwind CSS + Alpine.js
- **Database**: SQLite (chat history) + Qdrant (vectors)
- **Streaming**: WebSocket
- **Deployment**: Docker Compose or bare metal

No React. No Next.js. No npm build step. The frontend is server-rendered with progressive enhancement via Alpine.js. This keeps the app fast, simple to deploy, and easy to modify.

```
Browser (http://localhost:8504)
  │
  ├── WebSocket ─── streaming chat
  ├── REST API ──── settings, history, models, memory, RAG, MCP, pipeline
  │
  Helix AI Studio (FastAPI + Jinja2 + Tailwind CSS + Alpine.js)
    ├── Cloud AI ──────→ Claude API / OpenAI API
    ├── Local AI ──────→ Ollama / vLLM / llama.cpp
    ├── CLI Agents ────→ Claude Code / Codex / Gemini CLI
    ├── RAG ───────────→ Qdrant + Ollama Embedding
    ├── Memory ────────→ Mem0 HTTP → Qdrant
    └── MCP ───────────→ stdio transport → Any MCP server
```

---

## Getting Started

### One-Click Deploy (Free)

The fastest way to try it:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/tsunamayo7/helix-ai-studio)

This deploys to Render's free tier. You'll use cloud API providers (Claude/OpenAI) — just enter your API keys in Settings after deploy.

Or try the **[Live Demo](https://helix-ai-studio.onrender.com)** directly (no API key needed for the demo instance).

### Local Install

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
uv sync
uv run python run.py
```

Open http://localhost:8504.

### Docker Compose (Full Stack)

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
docker compose up -d
```

This starts Helix AI Studio + Ollama + Qdrant + Mem0 — everything you need.

---

## 100% Self-Hosted: Why It Matters

Every feature in Helix AI Studio can run **entirely on your hardware**:

- **Ollama** for inference — no tokens sent to any cloud
- **Qdrant** for vector storage — your documents stay local
- **Mem0** for memory — your context never leaves your machine
- **SQLite** for chat history — no external database needed

You can add cloud APIs (Claude, OpenAI) when you want their power, but the baseline is fully local. For anyone working with sensitive data, internal documentation, or just wanting to avoid API costs — this is the point.

---

## What I Learned Building This

A few takeaways from the v2.0 rebuild:

**Pipelines beat single-shot prompts.** For anything beyond simple Q&A, breaking the task into Plan → Execute → Verify produces dramatically better results. The verification step alone catches so many errors that a single-shot approach would miss.

**Local + Cloud hybrid is the sweet spot.** Running everything in the cloud is expensive. Running everything locally limits your capabilities. Using cloud models for planning and verification while local models handle execution gives you the best of both worlds.

**CrewAI on local models is viable.** With enough VRAM (I use an RTX PRO 6000 with 96GB), you can run multi-agent teams entirely on Ollama. The quality won't match GPT-4-class agents, but for many tasks it's good enough — and the cost is zero.

**Server-rendered + Alpine.js is underrated.** I considered React/Next.js but went with Jinja2 templates and Alpine.js instead. The result is a snappy UI with zero build step, easy customization, and a fraction of the complexity. For tools like this, you don't need a SPA framework.

---

## What's Next

The roadmap includes:

- **Artifact rendering** — live previews for HTML/SVG/Mermaid/React generated by the AI
- **Voice input/output** — speech-to-text and TTS integration
- **More MCP servers** — expanding the tool ecosystem
- **Better CrewAI workflows** — custom team definitions and task chains

---

## Try It Out

**[Live Demo](https://helix-ai-studio.onrender.com)** — no setup needed, play with it right now.

**[GitHub](https://github.com/tsunamayo7/helix-ai-studio)** — star the repo if you find it useful.

![App Tour](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_navigation_demo.gif)

If you're building something similar or have questions about the architecture, drop a comment below. I'm happy to go deeper on any part of the stack.

And if you find Helix useful, a **star on GitHub** really helps with visibility. Thanks for reading!
