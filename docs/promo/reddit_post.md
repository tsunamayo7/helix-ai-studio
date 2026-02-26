# Reddit Post Templates

---

## Primary Post: r/LocalLLaMA

**Title:** I built a PyQt6 app that orchestrates Claude + local Ollama models in a multi-phase pipeline -- precision goes up, API costs go down

**Body:**

I have been working on **Helix AI Studio**, an open-source desktop app that runs a 3+1 Phase pipeline combining cloud AI and local LLMs.

**How it works:**

1. **Phase 1 (Cloud)**: Claude/GPT/Gemini analyzes your prompt, produces structured instructions and acceptance criteria
2. **Phase 2 (Local)**: Ollama models execute sequentially across 5 categories -- coding, research, reasoning, translation, vision. All local, zero API cost, your data never leaves your machine
3. **Phase 3 (Cloud)**: Claude integrates all outputs, runs them against acceptance criteria (PASS/FAIL), produces final answer
4. **Phase 4 (Optional)**: Sonnet applies file changes to your codebase

**Why I built it:** I was tired of copy-pasting between AI chat windows. I wanted one app where Claude plans, local models execute, and Claude validates -- with the heavy lifting done by my own GPU.

**Tech stack:** PyQt6 desktop GUI + React Web UI (access from phone), FastAPI + WebSocket, SQLite, Ollama via httpx, Claude CLI / Anthropic API / OpenAI API / Gemini API.

**Key features beyond the pipeline:**
- 4-layer adaptive memory (thread / episodic / semantic / procedural)
- BIBLE-first documentation injection
- RAG pipeline with vector search
- Sequential executor handles 32B+ models on a single GPU (load-run-unload)
- Full Japanese + English i18n

Free, MIT licensed, v11.9.2. Windows, Python 3.12+.

**What makes this different from LangGraph/CrewAI/AutoGen?** Those are frameworks -- you write Python code to define agents and workflows. Helix is a GUI app. No YAML, no agent code, no framework boilerplate. You type a prompt, pick your models, and the pipeline runs. Settings panels, not config files.

**What makes this different from AnythingLLM/Ollama Web UI?** Those are single-model chat interfaces. Helix routes your prompt through multiple models with different specializations and synthesizes the results automatically.

**GitHub:** https://github.com/tsunamayo7/helix-ai-studio

Happy to answer any questions about the architecture or local model performance.

---

## Suggested Title Variations

### r/LocalLLaMA
> I built a PyQt6 app that orchestrates Claude + local Ollama models in a multi-phase pipeline -- precision goes up, API costs go down

### r/selfhosted
> Helix AI Studio: self-hosted multi-AI orchestration app -- Claude plans, your local Ollama models execute, Claude validates (PyQt6 + React Web UI, MIT)

### r/ollama
> Built a desktop app that uses Ollama models as specialized workers in a Claude-orchestrated pipeline -- 5 local model categories, zero API cost for execution

### r/Python
> I built a PyQt6 + FastAPI app that orchestrates Claude, GPT, Gemini, and Ollama local models in a single multi-phase pipeline

### r/MachineLearning
> [P] Helix AI Studio: Multi-AI orchestration platform combining cloud LLMs (planning/validation) with local LLMs (execution) in a 3+1 phase pipeline

### r/artificial
> Helix AI Studio: An open-source app that makes Claude, GPT, and local LLMs work together as a team instead of separate chat windows

---

## Posting Notes

- For r/LocalLLaMA: Emphasize the local execution, VRAM management, sequential executor, and that Phase 2 is fully private.
- For r/selfhosted: Emphasize the Web UI for remote access, SQLite shared DB, Tailscale VPN support, and that it runs on your own hardware.
- For r/ollama: Emphasize the Ollama integration, 5 specialist categories, model management, and tool use support.
- For r/Python: Emphasize the tech stack -- PyQt6, FastAPI, httpx streaming, SQLite, asyncio architecture.
- Include the demo GIF link if the subreddit allows images: `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/images/demo.gif`
