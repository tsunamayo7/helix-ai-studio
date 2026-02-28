# r/selfhosted Post

**Title:** Helix AI Studio - self-hosted multi-AI orchestration with built-in Web UI (PyQt6 + React)

---

**Body:**

I have been building a self-hosted AI orchestration app and thought this community might find it useful. It runs entirely on your own hardware, has a built-in web interface for remote access, and can operate with zero cloud dependencies if you use only local models.

## What is it

**Helix AI Studio** is a PyQt6 desktop application that orchestrates multiple AI models (Claude, GPT, Gemini, and local Ollama models) through a multi-phase pipeline. It includes a built-in React Web UI served by FastAPI, so you can access it from any device on your network.

## The self-hosted angle

**Everything runs on your machine.** The app itself, the database, the AI execution -- all local. Here is what the setup looks like:

```
Your Workstation
  +-- Helix AI Studio (PyQt6 desktop app)
  |     +-- FastAPI server (port configurable)
  |     +-- SQLite database (shared)
  |     +-- Ollama backend (local LLMs)
  |     +-- Cloud API calls (optional, outbound only)
  +-- React Web UI
        +-- Accessible from phone/tablet/laptop on LAN
        +-- Same chat history, same settings
        +-- WebSocket streaming (/ws/cloud, /ws/mix, /ws/local)
```

**No external server needed.** No Docker container phoning home. No SaaS subscription. The FastAPI backend starts alongside the desktop app and serves the React frontend.

## Privacy-first pipeline

The app's marquee feature is a 3+1 Phase pipeline:

1. **Phase 1 (Cloud, optional)**: Claude/GPT/Gemini analyzes your prompt, produces structured instructions
2. **Phase 2 (100% Local)**: Ollama models execute -- coding, research, reasoning, translation, vision. Your data never leaves your machine during this phase
3. **Phase 3 (Cloud, optional)**: Claude validates the output against acceptance criteria
4. **Phase 4 (Optional)**: Apply file changes to your codebase

If you want full local-only operation, you can skip Phases 1/3 and use just the **localAI tab** -- a direct Ollama chat with tool use support (filesystem access, code execution). No cloud calls at all.

## Web UI details

The built-in web UI is a React + Tailwind CSS frontend. It connects to the desktop app's FastAPI backend via WebSocket and supports:

- **3 chat modes**: cloudAI (cloud models), mixAI (the pipeline), localAI (Ollama direct)
- **Streaming responses** in real time
- **Chat history** with the same SQLite database the desktop uses
- **File management** (upload, browse)
- **Mobile-friendly** layout
- **JWT authentication** for security

For remote access from outside your LAN, the recommended approach is Tailscale VPN rather than exposing ports. No HTTPS/reverse proxy configuration required.

## Tech stack

| Component | Technology |
|---|---|
| Desktop GUI | PyQt6 |
| Web Backend | FastAPI + Uvicorn |
| Web Frontend | React + Tailwind CSS |
| Local LLMs | Ollama (httpx streaming) |
| Cloud AI | Claude CLI / Anthropic / OpenAI / Gemini (all optional) |
| Database | SQLite (WAL mode) |
| Auth | JWT (Web UI) |
| Notifications | Discord Webhook (opt-in) |
| i18n | Japanese + English |

## What about Docker?

Docker support is planned and tracked at [Issue #8](https://github.com/tsunamayo7/helix-ai-studio/issues/8). The main consideration is GPU passthrough for the Ollama integration. Currently the app runs as a standard Python application -- install dependencies, run `python HelixAIStudio.py`.

## Additional features

- **4-layer memory system**: Thread / Episodic (session summaries) / Semantic (knowledge graph) / Procedural (learned patterns)
- **RAG pipeline**: Document chunking + vector search for local knowledge bases
- **BIBLE documentation injection**: Auto-discovers your project spec and injects relevant context into prompts
- **MCP support**: Model Context Protocol servers (filesystem, git, web search)
- **GPU monitoring**: VRAM usage tracking, budget simulator
- **No telemetry**: Zero analytics, zero tracking, no data sent anywhere you do not control

## Getting started

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
install.bat          # interactive installer
# or: pip install -r requirements.txt
python HelixAIStudio.py
```

Install Ollama separately: https://ollama.com/download

## Links

- **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
- **Setup Guide**: https://github.com/tsunamayo7/helix-ai-studio/blob/main/SETUP_GUIDE.md
- **Docker tracking issue**: https://github.com/tsunamayo7/helix-ai-studio/issues/8

v11.9.4 "Helix Pilot", MIT licensed, Windows, Python 3.12+.

**New in v11.9.4**: Helix Pilot -- autonomous GUI operation powered by local Vision LLMs. The app can now operate your desktop apps and browser with zero cloud dependency for the automation layer. Safety-first design with action whitelisting, hotkey blocking, and URL/domain restrictions.

Feedback and stars appreciated. Happy to answer questions about the architecture or self-hosting setup.

---

## Posting Notes

- r/selfhosted cares about: self-contained deployments, no cloud dependency, Docker support, security model, resource usage
- Be ready to answer about: Docker timeline, Linux support, resource requirements (RAM/VRAM), reverse proxy setup
- Flair: likely "AI" or "Software"
- If asked about Linux: "Desktop GUI is PyQt6 which works on Linux, but testing has been Windows-only so far. PRs for Linux packaging welcome."
