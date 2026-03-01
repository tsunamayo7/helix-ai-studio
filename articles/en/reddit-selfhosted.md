---
subreddit: selfhosted
title: "Helix AI Studio - self-hosted multi-AI orchestration with built-in Web UI (PyQt6 + React)"
---

**Body:**
I built a self-hosted AI orchestration app that combines a PyQt6 desktop interface with a built-in FastAPI + React web server, so you can use it from your desktop or any device on your local network.

**What it does:**

Helix AI Studio lets you run multiple AI models in a coordinated pipeline:
- **Cloud AIs** (Claude, GPT, Gemini) handle planning and synthesis
- **Local Ollama models** handle the heavy processing for free
- The built-in Web UI makes it accessible from phones/tablets on the same network

**Self-hosted highlights:**

- **Zero external dependencies for the UI** — React frontend is pre-built and served by the FastAPI backend
- **Web UI runs on port 8500** — access from any device on your LAN
- **JWT-authenticated WebSockets** — /ws/cloud, /ws/mix, /ws/local endpoints
- **SQLite conversation history** — all data stays local
- **RAG support** — index your own PDFs, Markdown, CSV files
- **Ollama integration** — auto-detects locally running models

**Tech stack:**
- PyQt6 (desktop shell)
- FastAPI + Uvicorn (web server, runs embedded)
- React + Tailwind CSS (frontend, pre-bundled)
- SQLite (ChatStore)
- Ollama via async httpx streaming
- MIT license

**Setup is 3 commands:**
```
git clone https://github.com/tsunamayo7/helix-ai-studio.git
pip install -r requirements.txt
python HelixAIStudio.py
```

The web server starts automatically when you launch the desktop app. No Docker, no separate server process to manage.

**GitHub:** https://github.com/tsunamayo7/helix-ai-studio

Currently v11.9.4. Happy to answer questions about the architecture or self-hosting setup.

## Posting Notes
- Keep it technical, focus on self-hosting aspects
- Mention LAN access and JWT auth
