<!-- SPDX-FileCopyrightText: 2026 Helix AI Studio Contributors -->
<!-- SPDX-License-Identifier: MIT -->

<div align="center">

# Helix AI Studio

### Claude, GPT, Gemini, and local LLMs — all in one app.

*Multiple AIs collaborate automatically and deliver one refined answer.*
*Free with local LLMs. Add API keys for cloud AIs.*

[![GitHub stars](https://img.shields.io/github/stars/tsunamayo7/helix-ai-studio?style=social)](https://github.com/tsunamayo7/helix-ai-studio/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v12.5.0-brightgreen.svg)](https://github.com/tsunamayo7/helix-ai-studio/releases)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

[Japanese](README_ja.md) · [Setup Guide](SETUP_GUIDE.md) · [Changelog](CHANGELOG.md)

![Helix AI Studio Screenshot](docs/demo/cloudai_chat.png)

</div>

---

## Getting Started

Copy-paste 3 lines. The installer sets up everything.

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

```bash
python HelixAIStudio.py   # launch
```

The desktop app opens. Access from your phone at `http://localhost:8500`.

<details>
<summary>What the installer does</summary>

- Installs all AI-related packages
- Installs Ollama (local AI engine) and downloads a starter model
- Builds the Web UI
- Sets up CLI tools (Claude Code / Codex)
- Creates config files

If anything fails, the installer keeps going. Failed items show as `[WARN]`.

</details>

> First time? See the [Setup Guide](SETUP_GUIDE.md).

---

## What Helix does

| Feature | What it does |
|---------|-------------|
| **mixAI Pipeline** | Multiple AIs auto-collaborate: plan → execute → validate → refine → one answer |
| **cloudAI Chat** | Chat with Claude, GPT, or Gemini. Switch models mid-conversation — context carries over |
| **localAI Chat** | Fully offline with any Ollama model. Zero API cost |
| **Virtual Desktop** | AI writes and runs code inside a Docker sandbox. Your machine stays clean |
| **RAG** | Load PDFs and documents into a shared knowledge base for every AI |
| **Web UI** | Access from phones and tablets on your LAN |
| **MCP Support** | External tool integration via Model Context Protocol |
| **i18n** | Japanese and English UI, switchable with one click |

---

## See it in action

### Multiple AIs collaborate on one task (mixAI Pipeline)

Claude plans, Mistral and Gemma execute, then results are merged and validated. One prompt does it all.

![mixAI Pipeline Demo](docs/demo/gif/demo_mixai_pipeline.gif)

### Pick any model and chat (cloudAI)

Switch between Claude, GPT, and Gemini from a dropdown. Change models — your conversation continues.

![cloudAI Demo](docs/demo/gif/demo_cloudai_models.gif)

### Generate code with local LLMs (localAI)

Ollama's qwen3.5 (122B) writes Python code. No internet, zero API cost.

![localAI Demo](docs/demo/gif/demo_localai_chat.gif)

### Preview AI-built apps instantly (Virtual Desktop)

Apps run inside a Docker Virtual Desktop. Your actual machine stays untouched.

![Virtual Desktop Demo](docs/demo/gif/demo_vd_sandbox.gif)

---

## API Keys

**Using only local AI (Ollama)? No API key needed.** Start for free.

For cloud AIs:

| Provider | Get your key | Notes |
|----------|-------------|-------|
| Google | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Gemini (**free tier**) |
| Anthropic | [console.anthropic.com](https://console.anthropic.com/settings/keys) | Claude |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | GPT |

Enter keys in the Settings tab after launch.

---

## How Helix compares

| What you want | Open WebUI | AnythingLLM | Dify | CrewAI | **Helix** |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-AI pipeline** | — | — | Builder | Code | **GUI, one click** |
| **AI agent teams** | — | — | Plugins | Code required | **Configure in UI** |
| **Desktop app** | — | Yes | — | — | **Yes** |
| **Mobile access** | Yes | — | — | — | **Yes** |
| **No Docker needed** | Required | Optional | Required | pip | **Not required** |

> No other tool offers a GUI-based multi-AI pipeline.

---

## How the Pipeline Works

```
        YOUR PROMPT
              |
              v
 ┌─────────────────────────┐
 │    Phase 1: PLANNING    │  Cloud AI decides strategy and sub-tasks
 └─────────────────────────┘
              |
    ┌────┬───┴───┬────┐
    v    v       v    v
 ┌──────┐┌──────┐┌──────┐┌──────┐
 │ Code ││ Research ││Reason││Vision│  Phase 2: Agents work in parallel
 └──────┘└──────┘└──────┘└──────┘
         └──────┬──────┘
                v
 ┌─────────────────────────┐
 │   Phase 3: VALIDATION   │  Merge outputs, run quality checks
 └─────────────────────────┘
              |
              v
 ┌─────────────────────────┐
 │  Phase 4: REFINEMENT    │  Polish and produce final answer
 └─────────────────────────┘
              |
              v
         FINAL OUTPUT
```

> Phase 2 supports CrewAI: Sequential or Hierarchical mode.

---

<details>
<summary><strong>More Screenshots</strong></summary>

### Pipeline Running
![Pipeline Monitor](docs/demo/mixai_monitor.png)

### Pipeline Complete
![Pipeline Complete](docs/demo/mixai_complete.png)

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

<details>
<summary><strong>Tech Stack</strong></summary>

| Layer | Technology |
|-------|-----------|
| Desktop | PyQt6 |
| Web UI | React + Vite + Tailwind CSS |
| Server | FastAPI + Uvicorn (WebSocket) |
| Cloud AI | Anthropic / OpenAI / Google Gemini APIs |
| CLI | Claude Code CLI / Codex CLI |
| Local LLM | Ollama |
| Multi-Agent | CrewAI (Sequential / Hierarchical) |
| Sandbox | Docker + Xvfb + NoVNC (optional) |
| Memory | SQLite + vector embeddings |
| Tools | MCP (Model Context Protocol) |

</details>

---

## Security

- **Phase 2 runs 100% locally** — code and documents never leave your machine
- **API keys stay local** — git-ignored
- **Web UI is LAN-only** — not exposed to the internet

> Details in [SECURITY.md](SECURITY.md)

---

## Updating

```bash
git pull && pip install -r requirements.txt && python HelixAIStudio.py
```

> Settings (`config/`) and data (`data/`) are preserved across updates.

---

## Version History

| Version | Highlights |
|---------|-----------|
| **v12.5.0** | CrewAI integration, MCP across all tabs, 5-phase pipeline |
| **v12.0.0** | Docker Virtual Desktop, 7-tab layout |
| v11.9.4 | Helix Pilot v2.0 — autonomous Vision LLM GUI agent |
| v11.5.0 | Multi-provider API |
| v9.0.0 | Web UI (React + FastAPI) |

See [CHANGELOG.md](CHANGELOG.md) for details.

---

## Articles

| Article | Language | Link |
|---------|----------|------|
| Helix Pilot v2.0 Release | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n7268ff58d0b0) |
| Multi-AI Orchestration Deep Dive | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n5a97fbf68798) |
| Use Multiple AIs for Free | JP | [note.com](https://note.com/ai_tsunamayo_7/n/nb23a3ece82f8) |

---

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT — [LICENSE](LICENSE)

**Author**: tsunamayo7 ([@tsunamayo7](https://github.com/tsunamayo7))

---

<div align="center">

**If this is useful, a star helps others find it.**

</div>
