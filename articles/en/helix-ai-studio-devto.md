---
title: I Built a Desktop App That Orchestrates Claude + Local LLMs in a Multi-Phase Pipeline
published: false
description: Helix AI Studio combines Claude, GPT, Gemini, and Ollama local models in a 3+1 Phase pipeline — precision goes up, API costs go down, privacy stays intact.
tags: ai, python, opensource, llm
cover_image: https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/images/demo.gif
---

## The Problem: Too Many AIs, No Good Way to Use Them Together

Here is a scenario most developers know well. You have Claude for its reasoning depth, GPT for breadth, a local 32B model for privacy-sensitive tasks, and maybe Gemini for its long context window. But using them means juggling browser tabs, copy-pasting between interfaces, and manually comparing outputs. There is no single tool that lets you *orchestrate* these models into a coherent pipeline.

I spent the past year building **Helix AI Studio** to solve exactly this. It is a PyQt6 desktop app (with a built-in React Web UI) that runs a multi-phase pipeline where Claude designs the plan, local LLMs execute it in parallel categories, and Claude validates the result. The whole thing runs from a single GUI -- no coding required.

## The Architecture: 3+1 Phase Pipeline

The core idea is division of labor. Each AI model does what it is best at:

### Phase 1: Claude Plans (Cloud)

Claude Code CLI (or Anthropic API / GPT / Gemini -- switchable) receives your prompt along with your project's BIBLE documentation. It produces:

- **Design analysis** -- breaking the task into structured sub-tasks
- **Acceptance criteria** -- what "done" looks like, as a checklist
- **Per-category instructions** -- specific instructions for each local LLM specialist

This is where the intelligence budget matters. You spend API tokens on *planning*, not on bulk execution.

### Phase 2: Local LLMs Execute (Private, Free)

Ollama models run sequentially on your GPU across five specialist categories:

| Category | Example Model | Role |
|---|---|---|
| Coding | `devstral:24b` | Implementation, refactoring |
| Research | `qwen3:32b` | Fact-checking, analysis |
| Reasoning | `qwq:32b` | Logic validation, edge cases |
| Translation | `qwen3:32b` | i18n, documentation |
| Vision | `llava:34b` | Image understanding |

Each category can be toggled on or off. The sequential executor handles VRAM management -- load, run, unload -- so you can run 32B+ models even on a single GPU.

**Key point**: This phase is entirely local. No data leaves your machine. Zero API cost.

### Phase 3: Claude Validates (Cloud)

Claude receives all Phase 2 outputs and runs them against the acceptance criteria from Phase 1. It produces:

- A **PASS/FAIL checklist** for each criterion
- An **integrated final response** that combines the best parts of each local model's output
- If criteria fail, a configurable quality loop retries Phase 2

### Phase 3.5 / Phase 4 (Optional)

Sonnet can optionally apply file changes from Phase 3's structured output directly to your codebase. Think of it as the "apply diff" step.

## Why This Architecture Works

**Precision goes up.** Multiple models cross-validate each other. Claude's planning ensures the local models get clear, structured instructions instead of vague prompts. The acceptance criteria check catches errors that any single model would miss.

**API costs go down.** You make exactly 2 cloud API calls per pipeline run (Phase 1 + Phase 3). The heavy execution work happens locally for free.

**Privacy stays intact.** Sensitive code, proprietary data, internal documentation -- all of it stays on your machine during Phase 2. Only the planning prompt and final validation go to the cloud.

## The Tech Stack

```
Desktop GUI:     PyQt6 (Cyberpunk Minimal theme)
Web Backend:     FastAPI + Uvicorn + WebSocket
Web Frontend:    React + Tailwind CSS
Local LLMs:     Ollama (httpx streaming)
Cloud AI:       Claude CLI / Anthropic API / OpenAI API / Google Gemini API
Database:       SQLite (shared between Desktop and Web)
Memory:         4-layer adaptive memory (Thread / Episodic / Semantic / Procedural)
Notifications:  Discord Webhook
i18n:           Japanese (default) + English
```

The dual-interface design means you can run the desktop app on your GPU workstation and access it from your phone via the Web UI. Same SQLite database, same chat history, same settings.

## Beyond the Pipeline: What Else It Does

- **cloudAI tab** -- Direct chat with Claude, GPT, or Gemini. Streaming, file attachments, adaptive thinking intensity.
- **localAI tab** -- Direct Ollama chat with tool use support (filesystem access, code execution).
- **4-layer memory system** -- Thread memory for current conversation, episodic for session summaries, semantic for knowledge graph, procedural for learned patterns. Includes RAPTOR multi-level summaries.
- **BIBLE-first documentation** -- Auto-discovers your project's specification document, parses it, and injects relevant sections into Phase 1/3 context.
- **RAG pipeline** -- Document chunking, vector search, and knowledge graph integration.
- **MCP support** -- Model Context Protocol servers for filesystem, git, web search connectors.

## Quick Start

**Step 1: Clone and install**

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
install.bat          # interactive installer
# or: pip install -r requirements.txt
```

**Step 2: Set up your AI backends**

- Install [Ollama](https://ollama.com/download) and pull a model: `ollama pull qwen3:32b`
- Install [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview): `npm install -g @anthropic-ai/claude-code`
- Or just enter API keys in Settings (Anthropic / OpenAI / Google -- all optional)

**Step 3: Run**

```bash
python HelixAIStudio.py
```

The mixAI tab is where the pipeline lives. Select your Phase 2 models, type a prompt, and watch the Neural Flow Visualizer show each phase in real time.

## Current Status

Helix AI Studio is at **v11.9.1** ("Color Purge"). It is free, open-source (MIT), and actively developed. The app runs on Windows with Python 3.12+.

I have been writing about the development process on [note.com](https://note.com/) (Japanese) and [Zenn](https://zenn.dev/) (Japanese technical articles). The GitHub repo has full English documentation.

## Links

- **GitHub**: [github.com/tsunamayo7/helix-ai-studio](https://github.com/tsunamayo7/helix-ai-studio)
- **Setup Guide**: [SETUP_GUIDE.md](https://github.com/tsunamayo7/helix-ai-studio/blob/main/SETUP_GUIDE.md)

---

If you are tired of copy-pasting between AI chat windows and want a single app that makes Claude, GPT, Gemini, and your local models work together as a team -- give Helix a try. Stars and feedback are very welcome.
