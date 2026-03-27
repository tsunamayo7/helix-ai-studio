# Helix AI Studio v2.0 — Social Media Posts

> 各プラットフォーム向けの投稿テキスト集
> 最終更新: 2026-03-27

---

## 1. X (Twitter) — English

```
Launched Helix AI Studio v2.0 — an open-source AI chat platform with 7 providers in one UI.

Features a 3-step pipeline (Plan→Execute→Final Answer), CrewAI multi-agent, RAG, and Mem0 shared memory.

100% self-hosted, MIT licensed. Built with FastAPI + Python.

https://github.com/tsunamayo7/helix-ai-studio

#OpenSource #AI #LLM #SelfHosted #FastAPI
```

---

## 2. X (Twitter) — Japanese

```
Helix AI Studio v2.0 をリリースしました！

7つのAIプロバイダーを1つのUIで切り替え可能。3ステップパイプライン（Plan→Execute→Final Answer）とCrewAIマルチエージェントを搭載。

FastAPI + Python製、MIT License、完全セルフホスト対応。

https://github.com/tsunamayo7/helix-ai-studio

#OSS #AI #LLM #セルフホスト #FastAPI
```

---

## 3. Product Hunt — English

**Tagline** (60 chars):

```
7 AI providers, one UI — self-hosted, open-source chat studio
```

**Description** (260 chars):

```
Helix AI Studio unifies 7 AI providers (Ollama, Claude, OpenAI, vLLM, Claude Code CLI, Codex CLI, Gemini CLI) in a single web app. Features a 3-step pipeline (Plan→Execute→Final Answer), CrewAI multi-agent, RAG knowledge base, and Mem0 shared memory. 100% self-hosted, MIT licensed, built with FastAPI + Python.
```

---

## 4. Hashnode — English (Technical Blog)

**Title:**

```
Helix AI Studio v2.0: One UI for 7 AI Providers — Built with FastAPI and Python
```

**Body:**

---

If you work with LLMs, you probably have accounts on multiple platforms — Ollama running locally, maybe a Claude or OpenAI API key, perhaps a vLLM server for your fine-tuned models. Switching between them means juggling browser tabs, terminal windows, and separate configurations.

I built Helix AI Studio to solve this. It is an open-source, self-hosted web application that puts seven AI providers behind a single interface.

### What It Does

Helix AI Studio v2.0 connects to **Ollama, Claude API, OpenAI API, vLLM/llama.cpp, Claude Code CLI, Codex CLI, and Gemini CLI**. You pick a provider and model from a dropdown, type your prompt, and get a streaming response — all through one consistent UI with real-time WebSocket communication.

### The 3-Step Pipeline

Beyond simple chat, the app includes an automated pipeline that breaks complex tasks into three stages:

1. **Plan** — A planning model (typically a CLI-based model like Claude Code) analyzes the task and produces a structured plan.
2. **Execute** — A local model (Ollama) carries out the plan step by step.
3. **Final Answer** — The planning model reviews the output and delivers a verified, polished result.

This pattern is surprisingly effective for tasks that benefit from deliberate reasoning before execution.

### CrewAI Multi-Agent Mode

For tasks requiring multiple perspectives, Helix integrates CrewAI. You can define specialized agents — a researcher, a coder, a reviewer — and let them collaborate on a single task. The orchestration happens server-side, and results stream back to the browser.

### RAG and Persistent Memory

The knowledge base page lets you drag and drop documents. They get chunked, embedded, and stored in Qdrant for retrieval-augmented generation. Mem0 integration provides shared memory that persists across sessions and across different AI tools on your machine.

### Tech Stack

The backend is **FastAPI** with WebSocket support for real-time streaming. The frontend is vanilla HTML/CSS/JS with Tailwind CSS — no heavy framework. Everything runs in a single Python process, containerizable with Docker.

### Getting Started

The project is MIT licensed and designed for self-hosting. Clone the repo, install dependencies with `uv` or `pip`, and start the server:

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
uv sync
python run.py
```

A live demo is available at [helix-ai-studio.onrender.com](https://helix-ai-studio.onrender.com).

If you are managing multiple LLM providers and want a single interface to unify them, give it a try. Feedback and contributions are welcome.

**GitHub:** [github.com/tsunamayo7/helix-ai-studio](https://github.com/tsunamayo7/helix-ai-studio)

---

## 5. Hacker News — English (Show HN)

**Title:**

```
Show HN: Helix AI Studio – 7 AI providers in one self-hosted web UI
```

**Comment:**

I built Helix AI Studio because I was tired of switching between Ollama, Claude, OpenAI, and various CLI tools to talk to different models. It is a FastAPI + Python web app that puts seven AI providers behind a single chat interface with real-time WebSocket streaming.

The part I find most useful is the 3-step pipeline: a planning model breaks down a complex task, a local model executes it, and the planner verifies the result. This Plan-Execute-Final Answer loop produces noticeably better output than single-shot prompting for anything non-trivial.

It also includes CrewAI multi-agent support for tasks where you want multiple specialized agents collaborating, a RAG knowledge base backed by Qdrant, and Mem0 shared memory that persists across sessions.

The whole thing is MIT licensed and designed for self-hosting. No external services required — you can run it entirely on localhost with Ollama. There is also a live demo on Render if you want to try it without installing anything.

Tech stack: FastAPI backend, vanilla JS + Tailwind frontend, WebSocket streaming, Docker-ready.

Live demo: https://helix-ai-studio.onrender.com
GitHub: https://github.com/tsunamayo7/helix-ai-studio

Would love to hear feedback, especially on the pipeline architecture.

---

## 6. Reddit — English

### r/selfhosted

**Title:**

```
Helix AI Studio v2.0 — Self-hosted web app that unifies 7 AI providers in one UI (MIT, FastAPI + Python)
```

**Body:**

I have been working on Helix AI Studio, an open-source web application that connects to seven AI providers through a single interface: Ollama, Claude API, OpenAI API, vLLM/llama.cpp, Claude Code CLI, Codex CLI, and Gemini CLI.

**Key features:**

- **7 providers, one UI** — Switch between local and cloud models with a dropdown. Real-time streaming via WebSocket.
- **3-step pipeline** — Plan → Execute → Final Answer. A planning model structures the task, a local model executes it, and the planner verifies the output.
- **CrewAI multi-agent** — Define specialized agents (researcher, coder, reviewer) that collaborate on tasks.
- **RAG knowledge base** — Drag-and-drop documents, chunked and stored in Qdrant for retrieval-augmented generation.
- **Mem0 shared memory** — Persistent memory across sessions and tools.
- **100% self-hosted** — Runs entirely on localhost with Ollama. No cloud dependency required.

**Tech:** FastAPI + Python backend, vanilla JS + Tailwind CSS frontend, Docker-ready.

**License:** MIT

**Live demo:** https://helix-ai-studio.onrender.com
**GitHub:** https://github.com/tsunamayo7/helix-ai-studio

Happy to answer questions about the setup or architecture.

---

### r/LocalLLaMA

**Title:**

```
Helix AI Studio v2.0 — Open-source web UI for Ollama + 6 other providers, with a 3-step pipeline and CrewAI multi-agent
```

**Body:**

Built a web UI focused on making local LLMs more useful alongside cloud APIs. Helix AI Studio v2.0 supports seven providers: **Ollama, Claude, OpenAI, vLLM/llama.cpp, Claude Code CLI, Codex CLI, and Gemini CLI**.

The feature I want to highlight for this community is the **3-step pipeline**:

1. A capable model (e.g., Claude Code CLI) creates a structured plan.
2. Your **local Ollama model** executes the plan.
3. The planning model reviews and verifies the output.

This lets you use a smaller local model for the heavy lifting while a stronger model handles planning and quality assurance. I have found it works well for coding tasks, research synthesis, and structured writing.

**Other features:**

- CrewAI multi-agent orchestration
- RAG knowledge base with Qdrant vector search
- Mem0 persistent shared memory
- Real-time WebSocket streaming
- Docker support
- MIT licensed, 100% self-hostable

**Tech stack:** FastAPI + Python, vanilla JS + Tailwind CSS.

For those running Ollama locally, this should just work out of the box. Point it at `localhost:11434` in settings and you are good to go.

**Live demo:** https://helix-ai-studio.onrender.com
**GitHub:** https://github.com/tsunamayo7/helix-ai-studio

Feedback welcome — especially on what local LLM workflows you would want to see supported.
