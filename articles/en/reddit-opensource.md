# r/opensource Post

**Title:** Helix AI Studio: Open-source desktop app that makes Claude, GPT, Gemini, and local LLMs work together (MIT)

---

**Body:**

I have been working on **Helix AI Studio** for about a year now, and I recently open-sourced it under the MIT license. It is a PyQt6 desktop application that orchestrates multiple AI models -- both cloud (Claude, GPT, Gemini) and local (Ollama) -- through a multi-phase pipeline. Figured this community might be interested in the project and potentially contributing.

## What it does

Instead of switching between different AI chat windows, Helix runs a pipeline where:

1. A cloud model (Claude/GPT/Gemini) analyzes your task and creates structured instructions
2. Local Ollama models execute the work across specialist categories (coding, research, reasoning, translation, vision)
3. The cloud model validates all outputs against acceptance criteria and produces an integrated response

Or you can just use each model directly through dedicated chat tabs -- no pipeline required.

## Why it is open source

I believe AI orchestration tools should be transparent. You should be able to see exactly what prompts are being sent, where your data goes, and how models are being selected. MIT means you can fork it, modify it, embed it in your own project, or build on top of it. No strings attached.

## Project status

- **Version**: v11.9.4 ("Helix Pilot")
- **License**: MIT
- **Releases**: 5 releases so far, actively developed
- **Languages**: Bilingual -- full Japanese and English UI via i18n system
- **Platform**: Windows, Python 3.12+
- **No telemetry**: Zero analytics or tracking of any kind

## Tech stack (for contributors)

```
Desktop GUI:     PyQt6
Web Backend:     FastAPI + Uvicorn + WebSocket
Web Frontend:    React + Tailwind CSS
Local LLMs:      Ollama (httpx streaming)
Cloud AI:        Claude CLI / Anthropic API / OpenAI API / Gemini API
Database:        SQLite
Memory:          4-layer adaptive memory (Thread/Episodic/Semantic/Procedural)
i18n:            Shared ja.json + en.json
Testing:         pytest (expanding coverage)
```

The codebase is pure Python on the backend with a React frontend. If you know PyQt6, FastAPI, or React, you can contribute.

## Good first issues

I have tagged several issues specifically for new contributors:

- **[#7 - Linux packaging](https://github.com/tsunamayo7/helix-ai-studio/issues/7)**: Create install scripts and test on major Linux distros
- **[#8 - Docker support](https://github.com/tsunamayo7/helix-ai-studio/issues/8)**: Dockerfile + docker-compose with GPU passthrough for Ollama
- **[#9 - Test coverage](https://github.com/tsunamayo7/helix-ai-studio/issues/9)**: Add pytest unit tests for core modules

These are well-scoped and have clear acceptance criteria in the issue descriptions.

## Contributing

The project has a [CONTRIBUTING.md](https://github.com/tsunamayo7/helix-ai-studio/blob/main/CONTRIBUTING.md) with guidelines on:

- Branch naming conventions (`feature/xxx`, `fix/xxx`)
- Commit message format
- i18n rules (both ja.json and en.json must be updated together)
- Code style (PyQt6 conventions, UI consistency rules)
- How to set up the development environment

All PRs go through review before merging into main. No direct commits to main.

## Key features

- **Multi-phase pipeline**: Cloud AI plans, local models execute, cloud AI validates
- **3 chat modes**: cloudAI (direct cloud chat), mixAI (the pipeline), localAI (direct Ollama)
- **Built-in Web UI**: React frontend accessible from any device on your network
- **4-layer memory**: Thread, Episodic (RAPTOR summaries), Semantic (knowledge graph), Procedural (learned patterns)
- **BIBLE documentation injection**: Auto-discovers and injects project specs into AI context
- **RAG pipeline**: Local document search with vector embeddings
- **MCP support**: Model Context Protocol for filesystem, git, web search integration
- **Sequential executor**: Runs multiple 32B+ models on a single GPU via load-run-unload cycles

## Links

- **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
- **Contributing guide**: https://github.com/tsunamayo7/helix-ai-studio/blob/main/CONTRIBUTING.md
- **Setup guide**: https://github.com/tsunamayo7/helix-ai-studio/blob/main/SETUP_GUIDE.md
- **Good first issues**: https://github.com/tsunamayo7/helix-ai-studio/labels/good%20first%20issue

If you are interested in AI orchestration, multi-model pipelines, or just want a project to contribute to, check it out. Stars and feedback are very welcome. Happy to answer any questions.

---

## Posting Notes

- r/opensource values: license clarity, contribution accessibility, transparent development
- Be ready to answer about: roadmap, Linux support timeline, test coverage status, how decisions are made
- Emphasize the MIT license explicitly -- this sub cares deeply about license choice
- If asked about governance: "Solo maintainer for now, but open to contributors taking ownership of subsystems (Web UI, Docker, Linux packaging)"
