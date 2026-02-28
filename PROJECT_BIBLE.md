# PROJECT_BIBLE.md - Helix AI Studio

## Overview

Helix AI Studio is a PyQt6-based desktop application that orchestrates multiple AI models (Claude, GPT, Gemini, local LLMs via Ollama) through a unified interface. It is designed as a **model-agnostic** platform where users register their own models and API keys.

- **Version**: 11.9.4 "Helix Pilot"
- **Framework**: PyQt6 (desktop GUI) + FastAPI (web API) + WebSocket
- **Language**: Python 3.11+
- **i18n**: Japanese / English bilingual

## Architecture

```
HelixAIStudio.py          # Entry point
src/
  main_window.py           # QMainWindow with tab-based UI
  tabs/                    # UI tabs (cloudAI, mixAI, localAI, settings, etc.)
  backends/                # LLM connection layer (22 modules)
  rag/                     # RAG pipeline (chunking, embedding, summarization)
  web/                     # REST API + WebSocket server
  routing/                 # Intelligent request routing (11 modules)
  bible/                   # PROJECT_BIBLE injection system
  memory/                  # Model config + memory management
  utils/                   # Constants, i18n, styles, logging
  widgets/                 # Custom PyQt6 widgets
  prompts/                 # Prompt templates
config/                    # User config files (git-ignored)
i18n/                      # ja.json / en.json translation files
frontend/                  # React web UI (mobile-accessible)
```

## Key Design Principles (v11.5.0)

1. **Model Agnostic**: Zero hardcoded model dependencies. `CLAUDE_MODELS = []`, `DEFAULT_CLAUDE_MODEL_ID = ""`. Users register models in `config/cloud_models.json` with explicit `provider` field.
2. **Provider-Based Routing**: Send routing uses `provider` (`anthropic_api`, `openai_api`, `google_api`, `anthropic_cli`, `openai_cli`, `google_cli`) instead of model_id string matching.
3. **Dynamic Model Resolution**: `get_default_claude_model()` reads `cloud_models.json` at runtime. No static model lists.
4. **API-Key Security**: All config files in `config/` are git-ignored except `*.example.json` templates.

## Provider System

| Provider | Backend | Auth |
|----------|---------|------|
| `anthropic_api` | Anthropic SDK | API Key in settings |
| `openai_api` | OpenAI SDK | API Key in settings |
| `google_api` | google-genai SDK | API Key in settings |
| `anthropic_cli` | Claude Code CLI | `claude login` |
| `openai_cli` | Codex CLI | `codex login` |
| `google_cli` | Gemini CLI | `GEMINI_API_KEY` env |
| (Ollama) | Local HTTP API | localhost:11434 |

## Tab Structure

| Tab | File | Purpose |
|-----|------|---------|
| cloudAI | `claude_tab.py` | Cloud AI chat (all providers) |
| mixAI | `helix_orchestrator_tab.py` | Multi-phase orchestration (P1-P4) |
| localAI | `local_ai_tab.py` | Local model management (Ollama) |
| Info Collection | `information_collection_tab.py` | RAG data gathering |
| Settings | `settings_cortex_tab.py` | API keys, model config, memory |
| History | `history_tab.py` | Chat history browser |

## RAG Pipeline

1. **Planner** (`rag_planner.py`): Analyzes documents and creates build plan
2. **Executor** (`rag_executor.py`): Chunking, embedding, summarization, KG extraction
3. **Verifier** (`rag_verifier.py`): Quality verification via cloud AI
4. Models are dynamically resolved via `model_config.py` getters

## Config Files

| File | Purpose | Git Status |
|------|---------|------------|
| `config/general_settings.json` | API keys, font, timeout | Ignored |
| `config/cloud_models.json` | Registered models with provider | Ignored |
| `config/config.json` | mixAI orchestration settings | Ignored |
| `config/*.example.json` | Templates for new users | Tracked |

## i18n

- All UI strings use `t('key.path')` from `src/utils/i18n.py`
- Translation files: `i18n/ja.json`, `i18n/en.json`
- Language switching is live (no restart required)

## Dependencies

- **Required**: PyQt6, networkx, numpy, pandas, aiohttp, requests, PyMuPDF, google-genai
- **Optional (unlocks features)**: anthropic SDK, openai SDK, browser-use, sentence-transformers

## Development Rules

- Never commit `config/` files (API keys)
- All model references must use dynamic resolution (`get_default_claude_model()`, `cloud_models.json`)
- New providers must be added to: provider combo, EXAMPLES dict, badge dict, routing switch, i18n keys
- UI text must use `t()` for both Japanese and English
- Local LLM models use dynamic getters (`_get_rag_ctrl_model()`, etc.) with fallbacks
