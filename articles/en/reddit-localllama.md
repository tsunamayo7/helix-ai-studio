---
subreddit: LocalLLaMA
title: "I built a desktop app that uses Ollama for the heavy lifting and Claude/GPT only for planning+validation — ends up being ~80% local"
---

**Body:**
Most Ollama setups I've seen are either:
- Pure local chat (fast, free, but no smart orchestration)
- Or you manually copy-paste between Ollama and a cloud model

I wanted to automate the hybrid pattern that keeps showing up in research: use a frontier model for planning + final validation, and let local models do the actual heavy processing.

**What I built:**

Helix AI Studio runs a 3-phase pipeline:

1. **Phase 1 (Cloud AI)** — Claude/GPT/Gemini analyzes your prompt and generates structured task instructions for each local model
2. **Phase 2 (Local Ollama)** — Your local models (devstral, gemma3, ministral, etc.) run in parallel on your GPU
3. **Phase 3 (Cloud AI)** — Cloud model integrates the outputs and runs a PASS/FAIL quality check

Result: cloud API calls = 2, local processing = everything else. In practice ~80% of the compute is running on your hardware.

**Why this matters for Ollama users:**

- You get Claude-quality planning without paying Claude prices for bulk processing
- Sensitive data/code stays on your machine during Phase 2
- You can tune which models handle which roles (coding vs research vs reasoning vs vision)

**Local model support:**
Works with any Ollama model. Tested with:
- `devstral:latest` — coding tasks
- `gemma3:27b` / `gemma3:4b` — research, general reasoning
- `mistral-small3.2` — vision tasks
- `ministral:8b` — fast reasoning

**Tech stack:**
- PyQt6 (desktop)
- FastAPI + Uvicorn (embedded, starts automatically)
- React + Tailwind (pre-bundled frontend, no Node.js needed at runtime)
- SQLite (conversation history)
- Ollama via async httpx streaming
- MIT License

**Platform:** Windows 10/11 and macOS 12+ (Apple Silicon and Intel). On macOS, Ollama uses Metal/CPU inference — no NVIDIA GPU required.

**Also has:**
- Built-in Web UI at `localhost:8500` — access from phone/tablet on LAN, no Docker
- RAG builder (PDF, Markdown, CSV)
- Discord notifications when pipeline completes
- JWT-authenticated WebSocket endpoints

**Setup:**
```
git clone https://github.com/tsunamayo7/helix-ai-studio
pip install -r requirements.txt
python HelixAIStudio.py
```

GitHub: https://github.com/tsunamayo7/helix-ai-studio

Happy to answer questions about the Ollama integration or the pipeline architecture. Currently on v11.9.4.

## Posting Notes
- Audience: Ollama power users, local LLM enthusiasts
- Focus: How local Ollama does the heavy work, cloud AI is just planning/validation
- Emphasize: privacy, cost efficiency, no Docker required
- Tone: Technical but accessible, not marketing-heavy
- Note: karma threshold required to post in r/LocalLLaMA — retry when karma > 10
