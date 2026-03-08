<!-- SPDX-FileCopyrightText: 2026 Helix AI Studio Contributors -->
<!-- SPDX-License-Identifier: MIT -->

<div align="center">

# Helix AI Studio

### One prompt. Multiple AI models. One integrated answer.

**Claude, GPT, Gemini, and local LLMs — orchestrated automatically.**

*Send one prompt. AI models plan, execute in parallel, validate, and refine — delivering one polished answer.*

*Free with local LLMs (Ollama). Add API keys for cloud AIs.*

[![GitHub stars](https://img.shields.io/github/stars/tsunamayo7/helix-ai-studio?style=social)](https://github.com/tsunamayo7/helix-ai-studio/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v12.8.0-brightgreen.svg)](https://github.com/tsunamayo7/helix-ai-studio/releases)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

[Japanese](README_ja.md) · [Setup Guide](SETUP_GUIDE.md) · [Changelog](CHANGELOG.md)

![Helix AI Studio Screenshot](docs/demo/best/README/readme_01_mixai_main.png)

</div>

---

## Why Helix?

Most AI tools let you chat with **one model at a time**. Helix is different:

🔀 **Multi-AI Pipeline** — Multiple models collaborate automatically on every prompt. One plans, others execute, results get validated and refined. No manual copy-pasting between AI tabs.

💰 **Free with local LLMs** — Run Ollama models with zero API cost, fully offline. Mix local + cloud when you want more power.

🖥️ **Virtual Desktop** — AI writes and runs code inside an isolated sandbox (Windows Sandbox by default, Docker optional). Your machine stays clean. Preview apps instantly.

📱 **Desktop + Web** — PyQt6 desktop app + React web UI. Access from your phone on LAN.

🔌 **Extensible** — MCP support, CrewAI integration, RAG with PDF loading.

🔒 **Private** — Phase 2 runs 100% locally. API keys are git-ignored. Web UI is LAN-only.

---

## Getting Started

Copy-paste 3 lines. The installer sets up everything.

### Windows

```bash
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
python HelixAIStudio.py    # launch
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

## Features at a Glance

| Feature | What it does |
|---------|-------------|
| **mixAI Pipeline** | Multiple AIs auto-collaborate: plan → execute → validate → refine → one answer |
| **soloAI Chat** | Unified chat for Cloud AI (Claude, GPT, Gemini) and local Ollama models in one tab. Switch freely — context carries over |
| **Virtual Desktop** | AI writes and runs code inside an isolated sandbox (Windows Sandbox by default, Docker optional). Your machine stays clean |
| **RAG** | Load PDFs and documents into a shared knowledge base for every AI |
| **History** | Unified chat history across all sessions (supports legacy cloudAI/localAI logs) |
| **Web UI** | Access from phones and tablets on your LAN |
| **MCP Support** | External tool integration via Model Context Protocol |
| **i18n** | Japanese and English UI, switchable with one click |

---

## See it in action

### Multiple AIs collaborate on one task (mixAI Pipeline)

Claude plans, Mistral and Gemma execute, then results are merged and validated. One prompt does it all.

![mixAI Pipeline](docs/demo/best/README/readme_01_mixai_main.png)

### Chat with any model — cloud or local (soloAI)

Cloud AI (Claude, GPT, Gemini) and local Ollama models are unified into a single soloAI tab. Switch models freely — your conversation continues.

![soloAI Chat](docs/demo/best/README/readme_02_soloai_unified_cloud.png)

### Run local LLMs offline, zero cost (soloAI + Ollama)

Select an Ollama model from the same soloAI tab. No internet, zero API cost.

![soloAI Local](docs/demo/best/README/readme_03_soloai_unified_ollama.png)

### Preview AI-built apps instantly (Virtual Desktop)

Apps run inside an isolated Virtual Desktop (Windows Sandbox by default, Docker optional). Your actual machine stays untouched.

![Virtual Desktop](docs/demo/best/README/readme_08_virtual_desktop.png)

---

## How the Pipeline Works

```
        YOUR PROMPT
             |
             v
   ┌─────────────────────────┐
   │   Phase 1: PLANNING     │  Cloud AI decides strategy and sub-tasks
   └─────────────────────────┘
             |
     ┌────┬──┴───┬────┐
     v    v      v    v
   ┌──────┐┌──────┐┌──────┐┌──────┐
   │ Code ││Research││Reason││Vision│  Phase 2: Agents work in parallel
   └──────┘└──────┘└──────┘└──────┘
          └──────┬──────┘
                 v
   ┌─────────────────────────┐
   │  Phase 3: VALIDATION    │  Merge outputs, run quality checks
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

## How Helix Compares

| What you want | Open WebUI | AnythingLLM | Dify | CrewAI | **Helix** |
|---|---|---|---|---|---|
| Multi-AI pipeline | — | — | Builder | Code | **GUI, one click** |
| AI agent teams | — | — | Plugins | Code required | **Configure in UI** |
| Desktop app | — | Yes | — | — | **Yes** |
| Mobile access | Yes | — | — | — | **Yes** |
| No Docker needed | Required | Optional | Required | pip | **Not required** |

> No other tool offers a GUI-based multi-AI pipeline.

---

## API Keys

**Using only local AI (Ollama)? No API key needed.** Start for free.

For cloud AIs:

| Provider | Get your key | Notes |
|----------|-------------|-------|
| Google | [aistudio.google.com](https://aistudio.google.com) | Gemini (**free tier**) |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude |
| OpenAI | [platform.openai.com](https://platform.openai.com) | GPT |

Enter keys in the **General Settings (一般設定)** tab after launch.

---

<details>
<summary>More Screenshots</summary>

| View | Screenshot |
|------|-----------|
| mixAI Pipeline | ![mixAI](docs/demo/best/README/readme_01_mixai_main.png) |
| soloAI (Cloud) | ![soloAI Cloud](docs/demo/best/README/readme_02_soloai_unified_cloud.png) |
| soloAI (Ollama) | ![soloAI Ollama](docs/demo/best/README/readme_03_soloai_unified_ollama.png) |
| CloudAI Settings | ![Cloud Settings](docs/demo/best/README/readme_04_cloud_settings.png) |
| Ollama Settings | ![Ollama Settings](docs/demo/best/README/readme_05_ollama_settings.png) |
| History | ![History](docs/demo/best/README/readme_06_history.png) |
| RAG Knowledge Base | ![RAG](docs/demo/best/README/readme_07_rag.png) |
| Virtual Desktop | ![Virtual Desktop](docs/demo/best/README/readme_08_virtual_desktop.png) |
| General Settings | ![Settings](docs/demo/best/README/readme_09_general_settings.png) |

</details>

<details>
<summary>Tech Stack</summary>

| Layer | Technology |
|-------|-----------|
| Desktop | PyQt6 |
| Web UI | React + Vite + Tailwind CSS |
| Server | FastAPI + Uvicorn (WebSocket) |
| Cloud AI | Anthropic / OpenAI / Google Gemini APIs |
| CLI | Claude Code CLI / Codex CLI |
| Local LLM | Ollama |
| Multi-Agent | CrewAI (Sequential / Hierarchical) |
| Sandbox | Windows Sandbox (default) / Docker + noVNC (optional) |
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
| **v12.8.0** | soloAI Unification — cloudAI + localAI merged into a single soloAI tab, 8-tab layout, unified chat history |
| **v12.7.0** | Windows Sandbox default backend, backend abstraction layer |
| **v12.5.0** | CrewAI integration, MCP across all tabs, 3+1 Phase pipeline |
| **v12.0.0** | Virtual Desktop (sandbox), initial multi-tab layout |
| v11.9.4 | Helix Pilot v2.0 — autonomous Vision LLM GUI agent |
| v11.5.0 | Multi-provider API |
| v9.0.0 | Web UI (React + FastAPI) |

See [CHANGELOG.md](CHANGELOG.md) for details.

---

## Articles

| Article | Language | Link |
|---------|----------|------|
| Helix Pilot v2.0 Release | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n410331cef01b) |
| Multi-AI Orchestration Deep Dive | JP | [note.com](https://note.com/ai_tsunamayo_7/n/n5f06d14c77d7) |
| Use Multiple AIs for Free | JP | [note.com](https://note.com/ai_tsunamayo_7/n/na893b82e8e3a) |

---

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT — [LICENSE](LICENSE)

**Author**: tsunamayo7 ([@tsunamayo7](https://github.com/tsunamayo7))

---

<div align="center">

**If Helix is useful to you, a ⭐ star helps others find it.**

</div>
