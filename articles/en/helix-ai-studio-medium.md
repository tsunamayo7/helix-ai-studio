# Multi-AI Orchestration: How I Built a 5-Phase Pipeline That Combines Claude, GPT, and Local LLMs

*A deep dive into the architecture decisions behind Helix AI Studio -- from the planning/execution split to the 4-layer memory system and dual-interface design.*

---

## The Thesis: Separate Planning From Execution

Most AI applications today treat a language model as a monolith. You send a prompt, you get a response. If the response is not good enough, you tweak the prompt and try again. This works, but it leaves significant quality and cost improvements on the table.

The core architectural insight behind Helix AI Studio is that **planning and execution are fundamentally different cognitive tasks**, and they benefit from different models. Cloud models like Claude Opus excel at reasoning, decomposition, and quality evaluation. Local models running on Ollama -- even at 24-32B parameters -- are surprisingly capable at focused, well-structured execution tasks. The trick is giving them the right instructions.

This separation has three consequences:

1. **Precision increases** because multiple models cross-validate each other against explicit acceptance criteria.
2. **API costs decrease** because you make exactly 2 cloud calls (plan + validate) while the bulk execution runs free on local hardware.
3. **Privacy improves** because sensitive data only touches the local execution phase -- it never reaches any external API.

## The Pipeline: 3+1 Phases in Detail

### Phase 1: Structured Planning (Cloud)

The orchestrator sends your prompt -- along with injected BIBLE documentation context -- to Claude (or GPT, or Gemini; the engine is switchable). But it does not just ask for a response. It asks for a structured planning artifact with three components:

- **Design analysis**: A decomposition of the task into sub-problems, with dependency ordering.
- **Acceptance criteria**: A machine-evaluable checklist of what "done" looks like. These become the evaluation rubric in Phase 3.
- **Per-category instructions**: Specific, tailored prompts for each local model category. A coding model gets implementation instructions. A research model gets fact-checking queries. A reasoning model gets logic validation tasks.

This structured output is the critical differentiator. Instead of giving a local model a vague "write a function that does X," Phase 1 produces something like: "Implement a sequential executor class with these specific methods, these error handling patterns, and these edge cases to cover."

The BIBLE injection system automatically discovers your project's specification document, parses its sections, and includes the relevant portions. This means Phase 1 always has access to your project's ground truth -- naming conventions, architecture patterns, constraints.

### Phase 2: Local Execution (Private, Free)

Phase 2 dispatches work to up to five specialist categories of Ollama models:

| Category | Purpose | Example Models |
|---|---|---|
| Coding | Implementation, refactoring, debugging | `devstral:24b`, `qwen2.5-coder:32b` |
| Research | Fact-checking, analysis, information gathering | `qwen3:32b`, `gemma3:27b` |
| Reasoning | Logic validation, edge case analysis | `qwq:32b`, `deepseek-r1:32b` |
| Translation | i18n, documentation, localization | `qwen3:32b` |
| Vision | Image understanding, diagram analysis | `llava:34b`, `gemma3:27b` |

Each category can be independently toggled on or off. If you only need coding and reasoning for a particular task, the other categories are skipped entirely.

The **SequentialExecutor** is a critical piece of infrastructure here. Running 32B+ models requires substantial VRAM. Instead of trying to load multiple models simultaneously, the executor follows a strict load-run-unload cycle. It requests Ollama to load a model, sends the Phase 1 instructions, collects the response, and then unloads the model before moving to the next category. This means you can run five different 32B models on a single GPU with 24GB VRAM -- just not at the same time.

All Phase 2 execution happens entirely on your local machine. The prompts, responses, and intermediate data never touch an external API. This is particularly valuable for proprietary code, internal documentation, or any scenario where data sovereignty matters.

### Phase 3: Validation and Integration (Cloud)

Phase 3 is where the quality gate lives. Claude receives all Phase 2 outputs along with the original acceptance criteria from Phase 1. It produces:

- A **PASS/FAIL evaluation** for each acceptance criterion, with explanations for failures.
- An **integrated final response** that synthesizes the best elements from each local model's output.
- If any criteria fail and the quality loop is enabled, the pipeline can retry Phase 2 with refined instructions (configurable retry cap via `max_phase2_retries`).

This validation step is what turns a collection of independent model outputs into a coherent, quality-checked result. It catches the kinds of errors that any single model -- cloud or local -- would miss on its own.

### Phase 4: Apply Changes (Optional)

For code-generation tasks, Phase 4 uses Sonnet to parse the structured output from Phase 3 and apply file changes directly to your codebase. This bridges the gap between "the AI produced good code" and "the code is actually in your project."

## The Memory Architecture: 4 Layers

A pipeline is only as good as its context. Helix implements a 4-layer adaptive memory system that gives the pipeline access to relevant history without overwhelming the context window:

**Thread Memory** -- the current conversation. Standard chat history with configurable context modes: single message, full session, or selective.

**Episodic Memory** -- session-level summaries generated by the RAPTOR system. When a conversation ends, a background worker (QThread in the desktop app, asyncio task in the web backend) generates a structured summary. These summaries roll up into weekly summaries, creating a hierarchical compression of your interaction history.

**Semantic Memory** -- a knowledge graph with temporal edges. Facts, entities, and relationships extracted from conversations are stored with timestamps and confidence scores. GraphRAG community summaries provide cluster-level understanding. This layer answers questions like "What do I know about this codebase's authentication system?"

**Procedural Memory** -- learned patterns and preferences. If you consistently prefer certain coding styles, reject certain approaches, or follow specific workflows, the procedural layer captures these as reusable patterns. A **Memory Risk Gate** uses a resident local model to quality-check memory candidates before they are committed (ADD / UPDATE / DEPRECATE / SKIP).

## Dual Interface: Desktop + Web

Helix runs as a PyQt6 desktop application, but it includes a full React Web UI served by a FastAPI backend. Both interfaces share the same SQLite database, the same configuration files, and the same AI backends.

The architectural motivation is practical: GPU workstations are often stationary. You want to start a pipeline run from your desk, then check the results from your phone while making coffee. The Web UI connects via WebSocket (`/ws/cloud`, `/ws/mix`, `/ws/local`) and supports the same streaming, chat history, and file management as the desktop app.

Security is handled by JWT authentication and an execution lock system -- only one client can run a pipeline at a time, preventing resource conflicts. For remote access, the recommended setup is Tailscale VPN rather than exposing ports to the internet.

The desktop app adds features that make less sense in a mobile browser: a VRAM Budget Simulator, a GPU Monitor with timeline recording, MCP server management, and a full settings UI with per-section save buttons.

## The BIBLE-First Approach

Most AI tools treat project documentation as optional context. Helix inverts this: the BIBLE (your project's specification document) is the primary context source. The BIBLE Manager auto-discovers Markdown files matching common spec-document patterns, parses them into sections, scores their completeness, and injects relevant sections into Phase 1 and Phase 3 prompts.

This means the pipeline always operates with awareness of your project's constraints, conventions, and architecture. The result is outputs that are consistent with your existing codebase rather than generic solutions that require heavy adaptation.

## Technology Decisions and Tradeoffs

**Why PyQt6 instead of Electron?** Native performance and lower memory footprint. A desktop AI orchestration app is already memory-intensive due to model management; adding Chromium overhead felt wasteful. PyQt6 also provides better integration with system-level resources (GPU monitoring, process management).

**Why FastAPI for the Web UI backend?** Async-native, WebSocket support out of the box, and it coexists naturally with the httpx-based Ollama client. The entire web layer is async, which matters when you are streaming responses from multiple sources.

**Why SQLite instead of PostgreSQL?** Single-user desktop app. SQLite is embedded, zero-config, and handles concurrent read/write from desktop + web gracefully with WAL mode. The shared database means zero synchronization logic between interfaces.

**Why sequential execution instead of parallel for Phase 2?** VRAM. A single 32B model at Q4 quantization needs roughly 18-20GB VRAM. Running two simultaneously is impractical on consumer GPUs. The sequential executor (load-run-unload) trades latency for accessibility -- anyone with a single GPU can run the full pipeline.

## Current State and What Is Next

Helix AI Studio is at v11.9.1, MIT licensed, and actively developed. The app runs on Windows with Python 3.12+. Japanese and English UI are fully supported via a shared i18n system.

The development journey has been documented in Japanese on [note.com](https://note.com/) and [Zenn](https://zenn.dev/), covering both the technical decisions and the product design thinking.

**GitHub**: [github.com/tsunamayo7/helix-ai-studio](https://github.com/tsunamayo7/helix-ai-studio)

---

The fundamental bet behind Helix is that the future of AI tooling is not about finding the single best model -- it is about orchestrating multiple models, each contributing what it does best, with explicit quality gates that catch what any individual model would miss. If that thesis resonates with you, I would love to hear your thoughts.
