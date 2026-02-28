# Hacker News "Show HN" Post

---

## Title

Show HN: Helix AI Studio -- Multi-AI orchestration desktop app (Claude + Ollama + GPT)

## URL

https://github.com/tsunamayo7/helix-ai-studio

## Text (Comment)

Helix AI Studio is a PyQt6 desktop app that orchestrates cloud and local LLMs in a 3+1 Phase pipeline.

The core idea: Claude (or GPT/Gemini) handles planning and validation (Phase 1 and 3), while local Ollama models handle execution (Phase 2) across five specialist categories -- coding, research, reasoning, translation, and vision. An optional Phase 4 lets Sonnet apply file changes to your codebase.

This means you make exactly 2 cloud API calls per run, the heavy execution is free and fully private on your own GPU, and multi-model cross-validation catches errors that any single model would miss.

Tech stack: PyQt6 (desktop), FastAPI + WebSocket (backend), React + Tailwind (web UI), Ollama via httpx, Claude CLI / Anthropic API / OpenAI API / Gemini API, SQLite.

Beyond the pipeline, the app includes a 4-layer adaptive memory system, RAPTOR multi-level summaries, RAG with vector search, BIBLE-first documentation injection, and a dual interface (desktop + web -- same DB, accessible from phone).

Free, MIT licensed, v11.9.4. Windows, Python 3.12+. Japanese and English UI.

I have been building this for about a year. The architecture was inspired by the observation that LLMs are better at specific tasks when given structured instructions vs. open-ended prompts -- so the pipeline splits "thinking" from "doing."

Happy to discuss architecture decisions, local model performance tradeoffs, or the memory system design.

---

## Posting Notes

- HN titles are limited to 80 characters. The title above is 76 characters.
- The "Show HN" prefix is required for project showcases.
- Keep the comment factual and technical. HN readers respond well to architectural reasoning and tradeoff discussions.
- Avoid superlatives and marketing language. Let the technical decisions speak for themselves.
- Best posting times: weekday mornings US Eastern (9-11 AM ET).
- If the post gains traction, be ready to answer questions about: why not just use a single model, VRAM requirements, how the quality loop works, comparison to agent frameworks like CrewAI/LangGraph.
