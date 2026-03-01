---
subreddit: opensource
title: "Helix AI Studio: Open-source desktop app that makes Claude, GPT, Gemini, and local LLMs work together (MIT)"
---

**Body:**
**Helix AI Studio** is an open-source desktop application (MIT license) that orchestrates multiple AI models — cloud and local — in a coordinated pipeline.

**The core idea:**

Instead of picking one AI, you use them together. A single prompt triggers a multi-phase pipeline:

1. Claude/GPT designs the execution plan
2. Local Ollama models do the heavy processing (free, runs on your machine)
3. Claude/GPT synthesizes and quality-checks the results

This means ~60% of the work is handled locally at no API cost, while the cloud AI handles planning and final integration.

**Features:**
- **mixAI** — multi-phase AI pipeline (cloud + local collaboration)
- **cloudAI** — direct chat with Claude, GPT, Gemini with one-click model switching
- **localAI** — Ollama chat with model selector and async streaming
- **Web UI** — built-in React + FastAPI server, access from phone/tablet on LAN
- **RAG** — index your own documents (PDF, Markdown, CSV)
- **Discord notifications** — get pinged when long pipeline runs finish
- **i18n** — full Japanese and English UI

**Tech stack:**
- Python / PyQt6 (desktop)
- FastAPI + Uvicorn (embedded web server)
- React + Tailwind CSS (pre-bundled frontend)
- SQLite (conversation history)
- MIT License

**Platform:** Windows 10/11 and macOS 12+ (Apple Silicon and Intel). No Docker required on either platform.

**Links:**
- GitHub: https://github.com/tsunamayo7/helix-ai-studio
- Current version: v11.9.4

The project is actively maintained — v11.9.4 was just released, and macOS support was added in the latest update. Contributions and feedback welcome.

## Posting Notes
- Keep it high-level and welcoming for OSS community
- Emphasize MIT license and contribution welcome
