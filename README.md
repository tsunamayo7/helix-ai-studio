<!-- SPDX-FileCopyrightText: 2026 Helix AI Studio Contributors -->
<!-- SPDX-License-Identifier: MIT -->

<div align="center">

# Helix AI Studio

**One prompt. Multiple AI models. One integrated answer.**

*A desktop app that makes Claude, GPT, Gemini, and local LLMs actually work **together** — sharing one RAG knowledge base, no copy-pasting, no coding required.*

[![GitHub stars](https://img.shields.io/github/stars/tsunamayo7/helix-ai-studio?style=social)](https://github.com/tsunamayo7/helix-ai-studio/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![Version](https://img.shields.io/badge/version-v12.0.0-brightgreen.svg)](https://github.com/tsunamayo7/helix-ai-studio/releases)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)
![i18n](https://img.shields.io/badge/i18n-ja%20%7C%20en-emerald)

[Japanese README](README_ja.md) · [Setup Guide](SETUP_GUIDE.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

> If Helix AI Studio looks useful to you, a star helps more developers discover it. Thank you!

</div>

---

## Why Helix?

| | |
|---|---|
| **Save tokens, not quality** | Claude handles 20% (planning + validation). Free local LLMs handle 80%. Same result, fraction of the cost. |
| **Or go all-cloud for precision** | Route any prompt directly to Claude, GPT, or Gemini when you want full cloud power. |
| **Build safely with Virtual Desktop** | Docker sandbox with a virtual screen — AI writes files inside an isolated container, you review the diff before anything touches your machine. |
| **One memory across all models** | A single RAG knowledge base shared by Claude, GPT, Gemini, and Ollama. Build once, every model benefits. |
| **Your hardware, your rules** | No Docker required. No subscription. `pip install` and run. Add Ollama for fully local, private inference. |

---

## Demo

### mixAI Pipeline — Cloud plans, local executes, cloud validates

![mixAI Pipeline Demo](docs/demo/desktop_mixai.gif)

### Virtual Desktop — Docker sandbox with NoVNC

![Virtual Desktop Demo](docs/demo/desktop_virtualdesktop.gif)

### localAI Chat — Any Ollama model, running on your GPU

![localAI Chat Demo](docs/demo/desktop_localai.gif)

---

## Quick Start

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
pip install -r requirements.txt
python HelixAIStudio.py          # macOS: python3
```

Add API keys in **Settings**, or install [Ollama](https://ollama.com) for fully local inference.
Web UI starts at `http://localhost:8500`.

> New to this? See [SETUP_GUIDE.md](SETUP_GUIDE.md) for a step-by-step walkthrough.

---

## How It Works

```
        YOUR PROMPT
              |
              v
 ┌─────────────────────────┐
 │    Phase 1: PLANNING    │  Cloud AI (Claude / GPT / Gemini)
 │  - Analyze the task     │
 │  - Create sub-tasks     │
 │  - Set pass/fail rules  │
 └─────────────────────────┘
              |
    ┌────┬───┴───┬────┐
    v    v       v    v
 ┌──────┐ ┌────────┐ ┌─────────┐ ┌────────┐
 │Coding│ │Research│ │Reasoning│ │ Vision │  Phase 2: LOCAL (your GPU)
 └──────┘ └────────┘ └─────────┘ └────────┘
    └────┬────┘           └─────┬─────┘
         └──────────┬───────────┘
                    v
 ┌─────────────────────────┐
 │   Phase 3: VALIDATION   │  Cloud AI
 │  - Integrate outputs    │
 │  - PASS / FAIL check    │
 │  - Final synthesis      │
 └─────────────────────────┘
              |
              v
         FINAL OUTPUT
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **mixAI Pipeline** | 3-phase orchestration: plan, execute, validate — one click |
| **cloudAI Chat** | Direct chat with Claude, GPT, Gemini via API |
| **localAI Chat** | Chat with any Ollama model on your GPU |
| **Docker Sandbox** | Isolated virtual desktop (NoVNC). AI writes files inside the container, you review the diff, then promote to host |
| **Unified RAG** | One knowledge base shared across all AI providers — local embeddings, build once |
| **Helix Pilot v2.0** | Vision LLM agent integrated into all chat tabs — reads your screen and executes GUI commands |
| **Web UI** | React-based mobile-friendly interface, accessible from any device on your LAN |
| **4-Layer Memory** | Thread, Episodic, Semantic, Procedural — context persists across sessions |
| **i18n** | Full Japanese and English UI, switchable at any time |

---

## Helix vs. Popular Alternatives

| | Open WebUI | AnythingLLM | Dify | LangChain | **Helix** |
|---|:---:|:---:|:---:|:---:|:---:|
| **GitHub Stars** | 60k+ | 30k+ | 129k+ | 80k+ | — |
| **Auto pipeline (cloud+local)** | Manual | Manual | Visual builder | Code required | **1-click** |
| **Unified RAG (cloud+local)** | — | Partial | Cloud only | Manual | **All models** |
| **Desktop app** | — | Yes | — | — | **Yes** |
| **LAN Web UI** | Yes | — | — | — | **Yes** |
| **Docker required** | Yes | Optional | Yes | N/A | **No** |
| **Setup** | docker run | Installer | docker compose | pip + code | **pip + run** |
| **Claude/GPT/Gemini native** | Via proxy | Yes | Yes | Yes | **Yes** |
| **Cost optimization** | — | — | — | Manual | **Built-in** |
| **MIT License** | Yes | Yes | Yes | Yes | **Yes** |

> **The gap Helix fills**: A GUI desktop app that automatically orchestrates cloud + local models in a cost-optimized pipeline — with a unified RAG knowledge base shared across all AI providers, zero Docker requirement, LAN access built in.

---

<details>
<summary><strong>Screenshots</strong></summary>

### Pipeline Monitor
![Pipeline Monitor](docs/demo/mixai_monitor.png)

### Pipeline Complete
![Pipeline Complete](docs/demo/mixai_complete.png)

### Cloud AI Chat
![Cloud AI Chat](docs/demo/cloudai_chat.png)

### Local AI Chat
![Local AI Chat](docs/demo/desktop_localai_chat.png)

### RAG Knowledge Base
![RAG Build](docs/demo/rag_build.png)

### Settings
![Settings](docs/demo/desktop_settings.png)

### Web UI
![Web UI](docs/demo/webui_chat.png)

</details>

---

## Installation

### Requirements

| Item | Requirement |
|------|-------------|
| OS | Windows 10/11 or macOS 12+ (Apple Silicon & Intel) |
| Python | 3.10+ (3.11 recommended) |
| GPU | NVIDIA + CUDA (optional, for local LLMs on Windows). macOS uses Metal/CPU. |
| RAM | 16 GB+ (32 GB+ for large models) |

### Setup

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
pip install -r requirements.txt
```

**(Optional) Local LLMs:**

```bash
ollama pull gemma3:4b           # Lightweight
ollama pull gemma3:27b          # Higher quality (16 GB+ VRAM)
ollama pull mistral-small3.2    # Vision tasks
```

**(Optional) Cloud AI keys:**

```bash
# Windows
copy config\general_settings.example.json config\general_settings.json
# macOS / Linux
cp config/general_settings.example.json config/general_settings.json
```

| Provider | Key source | Enables |
|---|---|---|
| Anthropic | [console.anthropic.com](https://console.anthropic.com/settings/keys) | Claude chat + pipeline planning |
| Google | [aistudio.google.com](https://aistudio.google.com/app/apikey) *(free tier)* | Gemini chat |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | GPT chat |

**Launch:**

```bash
python HelixAIStudio.py   # macOS: python3
```

### Update

```bash
git pull && pip install -r requirements.txt && python HelixAIStudio.py
```

> Settings (`config/`) and data (`data/`) are git-ignored and preserved across updates.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Desktop GUI | PyQt6 |
| Web UI | React + Vite + Tailwind CSS |
| Web Server | FastAPI + Uvicorn (WebSocket) |
| Cloud AI | Anthropic / OpenAI / Google Gemini APIs |
| CLI Backends | Claude Code CLI / Codex CLI |
| Local LLM | Ollama |
| Sandbox | Docker + Xvfb + NoVNC (optional) |
| Memory | SQLite + vector embeddings |
| i18n | Shared JSON (ja/en) for Desktop + Web |

---

## Security & Privacy

- **Phase 2 is 100% local** — code and documents stay on your machine during execution
- **API keys stay local** — stored in `config/general_settings.json` (git-ignored)
- **Web UI is private** — designed for local/VPN access, not public internet
- **Memory injection guard** — safety prompts prevent stored context from being used for prompt injection

> See [SECURITY.md](SECURITY.md) for details on compliance with Anthropic, OpenAI, and Ollama terms.

---

## Version History

| Version | Highlights |
|---------|-----------|
| **v12.0.0** | Docker Sandbox Virtual Desktop (NoVNC), Promotion Engine (diff preview + host apply), 7-tab layout |
| v11.9.7 | BIBLE/Pilot settings-tab migration, Feature Flags, Error translation system |
| v11.9.5 | Helix Pilot in-app integration (all 3 chat tabs + Settings), model-agnostic hardening, demo videos |
| v11.9.4 | Helix Pilot v2.0 — autonomous Vision LLM GUI agent |
| v11.9.0 | Unified Obsidian theme, SplashScreen |
| v11.5.0 | Multi-provider API (Anthropic/OpenAI/Google) |
| v11.0.0 | History tab, BIBLE cross-tab, cloud model selector |
| v9.0.0 | Web UI (React + FastAPI) |

See [CHANGELOG.md](CHANGELOG.md) for the full history.

---

## Articles & Resources

| Article | Language | Link |
|---------|----------|------|
| v11.9.4 Release — Helix Pilot v2.0, tab-switching UI, i18n | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n7268ff58d0b0) |
| v11.9.1 Release — color purge, pipeline automation | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n410888aabe47) |
| Architecture Deep Dive — multi-AI orchestration | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n5a97fbf68798) |
| Introduction & Setup Guide | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n410331c01ab0) |
| Beginner's Guide — use multiple AIs for free | JP | [note.com](https://note.com/ai_tsunamayo_7/n/nb23a3ece82f8) |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
For security issues, see [SECURITY.md](SECURITY.md).

---

## License

MIT — see [LICENSE](LICENSE)

**Author**: tsunamayo7 ([@tsunamayo7](https://github.com/tsunamayo7))

---

<div align="center">

**If Helix AI Studio is useful to you, please star the repo!**
Feedback, issues, and PRs are always welcome.

</div>
