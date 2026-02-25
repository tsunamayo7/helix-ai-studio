# Changelog

All notable changes to Helix AI Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [11.8.0] - 2026-02-25 "Polished Dark"

### Added
- "Refined Obsidian" color system: 4-layer depth backgrounds (base/surface/card/elevated)
- Typography system: `FONT_FAMILY_UI`/`FONT_FAMILY_MONO`, `FONT_SCALE` (display/body/small/xs), `FONT_WEIGHT`
- `GLOBAL_APP_STYLESHEET` for one-shot application-wide QSS styling
- Japanese font stack priority: Noto Sans JP → Yu Gothic UI → Meiryo UI
- Inline style shortcuts: `STYLE_ACCENT_TEXT`, `STYLE_SUCCESS_TEXT`, etc.
- Semantic color tokens with background variants (success_bg, error_bg, warning_bg, info_bg)

### Changed
- Accent color: fluorescent cyan `#00d4ff` → sky blue `#38bdf8` (WCAG AA compliant)
- Success color: neon green `#00ff88` → emerald `#34d399`
- Error color: `#ff6666` → `#f87171`
- All 17 source files updated: inline color literals replaced with new palette
- Background hierarchy: flat `#1a1a2e` everywhere → layered `#080c14`/`#0d1117`/`#131921`/`#1a2233`
- Border colors: `#2a2a3e` → `#1e2d42` (standard) / `#2a3f5a` (strong)
- `main_window.py`: `create_application()` now selects best Japanese font + applies global stylesheet
- Button styles: gradient removed → flat with subtle hover states
- Scrollbar: slimmer (8px), transparent track, subtle handle

## [11.7.0] - 2026-02-25 "Resilient Core"

### Added
- Centralized crash.log utility `src/utils/error_utils.py` with `write_crash_log()` (Fix B)
- Phase 4 failure now emits UI notification via `phase_changed` signal (Fix D)
- Phase 3.5 JSON parse failure emits UI warning + sets `parse_failed` flag (Fix E)
- MAX_TOOL_LOOPS reached warning appended to localAI response (Fix F)
- New provider entries in fallback chains: `anthropic_cli`, `openai_cli`, `google_cli` → API fallback (Fix H)
- Ollama error distinction: timeout / connection / HTTP status in `_run_ollama_async` (Fix I)
- Top-level exception guard in `sequential_executor.execute_task()` prevents UI state lockup (Fix J)

### Changed
- `HelixAIStudio.py` startup migration: `except pass` → `logger.warning` with context (Fix A)
- `claude_tab.py` crash.log writing consolidated from 3 copy-paste blocks to `write_crash_log()` calls (Fix B)
- `claude_tab.py` unified `logger_local` → `logger` (Fix G)
- `local_agent.py` monitor callbacks: `except pass` → `logger.debug` (Fix C)
- `local_agent.py` file search, config load, PAT load: silent `except pass` → `logger.debug` (Scan)
- `snippet_manager.py` added module-level `logger` definition (Scan fix)
- Phase 3.5 JSON parse failure `quality_score` changed from hardcoded 0.8 → 0.0 (Fix E)

### Fixed
- Silent exception swallowing in 7+ locations across the codebase (Scan 1)
- `snippet_manager.py` `open_unipet_folder()` had unprotected `subprocess.run` (Scan 2)
- `sequential_executor.execute_task()` could leave UI buttons disabled on unexpected exception (Fix J)

## [11.6.0] - 2026-02-25 "Provider Aware"

### Added
- Dynamic cloud model detection in Phase 2 via `cloud_models.json` provider field (Fix ①)
- Full provider routing in `_execute_cloud_task()`: anthropic_api, openai_api, google_api, *_cli (Fix ①)
- Continue button provider-based routing: non-CLI providers routed to normal send (Fix ⑤)
- Phase 2 combo separator labels `── Cloud AI（コスト発生・要注意）──` with selection disabled (Fix ⑥)
- Research category cloud model cost warning dialog on settings save (Fix ③)
- Vision combo filtering: groups models by vision capability via Ollama `/api/show` (Fix ④)
- Web Phase 2 cloud model support via `asyncio.to_thread()` wrapper (Verification A)
- `LOCALAI_WEB_TOOL_GUIDE` injection for research category in web Phase 2 (Verification F)

### Changed
- `_is_cloud_model()` now checks both hardcoded list AND dynamic `cloud_models.json`
- `populate_combo()` disables separator items (starting with `──` or `---`)
- `get_phase2_candidates()` uses warning separator instead of plain `--- Cloud AI ---`
- Web server `_build_phase2_tasks()` injects web tool guide for research tasks

### Fixed
- Cloud models registered via cloud_models.json but not in hardcoded list were sent to Ollama and failed
- Continue button blocked all non-CLI providers instead of routing to API send

## [11.5.3] - 2026-02-25 "Web LocalAI + Discord"

### Added
- Web UI LocalAI tab: `/ws/local` WebSocket endpoint for Ollama chat via browser
- `LocalAIView.jsx` component with ModelSelector (auto-fetches Ollama models)
- `sendLocalMessage` callback in `useWebSocket.js` hook
- Discord notifications for all three AI tabs (cloudAI/mixAI/localAI): started, completed, error events
- `install.bat` now builds frontend with `npm install && npm run build` when Node.js is available

### Changed
- Default web tab changed from cloudAI to mixAI
- TabBar order: mixAI → cloudAI → localAI → Files
- `frontend/dist/` now tracked in git (pre-built for users without Node.js)
- cloudAI send button label uses i18n key `desktop.cloudAI.sendBtnMain`
- cloudAI continue panel style unified: bg `#1a1a2e`, border `#2a2a3e`, border-radius 6px
- localAI input area bottom border aligned with cloudAI

### Fixed
- `_handle_local_execute()` NameError: `settings` variable was conditionally defined, now always loaded

## [11.5.2] - 2026-02-25 "Visual Parity"

### Added
- Log rotation for web server logs
- RAG 2-step verification flow

### Changed
- Desktop cloudAI/localAI input area visual alignment (margins, spacing, borders)

### Fixed
- Path traversal vulnerability in file transfer API
- Brute-force login protection added to web auth
- Auto-cleanup of stale execution locks

## [11.5.1] - 2026-02-25 "Provider Pure"

### Changed
- `_get_selected_model_provider()` prefix fallback removed — models without provider in cloud_models.json now return "unknown" instead of guessing from model_id prefix
- Unknown provider sends user-friendly guide (i18n) instead of raw error message
- API key security warning label added to Settings > API Key Setup section
- `HelixAIStudio.py` docstring updated from v1.0.0 to v11.5.1
- README.md rewritten: version badges, Quick Start with API connection table, Tech Stack, Version History
- `install.bat` version updated to v11.5.1
- `.gitignore` fixed: `config/` → `config/*` to allow `!config/*.example.json` negation
- `requirements.txt` formalized: FastAPI/Uvicorn/Pydantic/httpx added as core dependencies, SDKs moved from optional to required
- CHANGELOG.md updated with v11.1.0–v11.5.1 entries

## [11.5.0] - 2026-02-24 "Model Agnostic"

### Added
- Multi-provider API support: Anthropic API, OpenAI API, Google Gemini API (direct SDK connections)
- `google-genai` SDK integration for Gemini models (Pro 3, Flash 3)
- Dynamic model catalog: `cloud_models.json` with per-model `provider` field
- Provider-based routing: 6 providers (anthropic_api, openai_api, google_api, anthropic_cli, openai_cli, google_cli)
- API Priority Resolver: AUTO/API_ONLY/CLI_ONLY connection modes with fallback
- Cloud model add dialog with provider selection dropdown
- Provider badge display in registered model list (`[Anthropic API]`, `[OpenAI API]`, etc.)
- Model capability registry (`model_capabilities.py`) for extra_env / context limits
- `config/cloud_models.example.json`, `config/general_settings.example.json` template files
- Gemini API key field in Settings > API Key Setup

### Changed
- `CLAUDE_MODELS = []` and `DEFAULT_CLAUDE_MODEL_ID = ""` — app ships with no hardcoded models
- `get_default_claude_model()` and `resolve_claude_model_id()` now read from `cloud_models.json` dynamically
- `memory_manager.py` control/embedding models use dynamic getters instead of hardcoded constants
- `model_config.py` defaults changed to empty strings (no model assumptions)
- Local LLM category defaults (coding/research/reasoning/translation/vision) cleared to empty
- Web API `/api/models` endpoint reads from `cloud_models.json` dynamically
- `chat_store.py` SQLite model column DEFAULT changed to empty string

### Removed
- Hardcoded model ID string comparisons (`model_id == "gpt-5.3-codex"`) from routing logic
- Fixed model fallback chains that assumed specific model availability

## [11.4.0] - 2026-02-24 "API-First Connections"

### Added
- `src/backends/anthropic_api_backend.py`: Direct Anthropic API backend using official SDK (streaming support)
- `src/backends/openai_api_backend.py`: Direct OpenAI API backend using official SDK (streaming support)
- API key registration UI in Settings tab (Anthropic / OpenAI / Gemini keys)
- "Auto" connection mode (API-first → CLI fallback) for cloudAI
- API connection for mixAI Phase 1/3 (no longer CLI-only)

### Changed
- cloudAI routing refactored: provider-based dispatch instead of model name matching
- Settings tab: API key fields with masked input and connection test buttons

## [11.3.1] - 2026-02-24 "Browser Use Activation"

### Added
- Browser Use fully wired as active tool for localAI (`OllamaWorkerThread._execute_tool()` browser_use case)
- Optional tools status display + install UI in Settings > General
- `LOCALAI_WEB_TOOL_GUIDE` constant for LLM web tool usage guidance
- `install.bat` optional package installation prompts (browser-use, sentence-transformers, anthropic, openai)

### Fixed
- `_tool_browser_use()` return value structured with `fetched_at`/`final_url`/`title`/`notes`
- localAI `_send_message()` tools list now includes `BROWSER_USE_TOOL` when enabled

## [11.3.0] - 2026-02-24

### Added
- Cloud model dynamic registration (`cloud_models.json`)
- Model capability registry with `extra_env` support
- Local model pipeline wiring for all 5 categories

### Changed
- Effort level UI removed (moved to env variable)
- Browser Use / httpx separation for cloudAI and mixAI
- RAG GroupBox title corrected
- RAG Planner local model support with 2-step engine

## [11.1.0] - 2026-02-23 "Browser Use Integration"

### Added
- Browser Use settings integration in localAI tab
- Smart History full implementation with JSONL search

### Changed
- RAG chat fixes and improvements
- i18n updates for Browser Use and History features

## [11.0.0] - 2026-02-23 "Smart History"

### Added
- History tab (📜) with JSONL search, date grouping, tab filter, message copy & quote
- Continue Send button with `--resume` flag and auto session ID capture
- BIBLE cross-tab toggle (📖) on cloudAI/mixAI/localAI with context injection
- MCP server checkboxes distributed to cloudAI and localAI settings tabs
- Cloud model selector in cloudAI chat header (cloud_models.json)
- Advanced Settings button (opens ~/.claude/settings.json)
- Chat logger (JSONL append-only), Model config (model_config.py)
- Section save buttons, NoScroll widgets module, RAG auto-enhancement checkboxes

### Changed
- Version: 10.1.0 → 11.0.0
- 6-tab layout: mixAI / cloudAI / localAI / History / RAG / Settings
- RAG tab renamed from "情報収集" to "🧠 RAG", subtab "実行" → "チャット"
- cloudAI header: [Model ▼] [Advanced] [New] layout
- effort_level hidden in config.json (UI combo removed)
- P1/P3 engine: cloud-only (Ollama models removed)

### Removed
- PhaseIndicator, NeuralFlowCompactWidget, GPUUsageGraph (class + 12 methods)
- GPU Monitor section, VRAM Simulator (vram_simulator.py deleted)
- OpenAI compat backend (openai_compat_backend.py deleted), custom_server.json
- BIBLE Manager UI panel, Search mode combo, MCP from Settings tab
- Risk Gate UI, RAG enable UI, Save threshold combo, mixAI Phase Registration

## [10.1.0] - 2026-02-22 "Unified Studio"

### Added
- cloudAI tab (renamed soloAI), localAI tab (Ollama direct chat)
- Execution Monitor Widget (real-time LLM monitoring with stall detection)
- mixAI chat bubble display + conversation continue panel
- Information Collection 2-tab layout (Execute/Settings with model combos)
- Language switcher on tab bar corner, AI Status Check section
- Phase 2 dynamic combo population, Web search tools (web_search/fetch_url)
- Browser Use checkbox, Chat auto-scroll for cloudAI/mixAI

### Changed
- soloAI → cloudAI full rename (DB/WebSocket/i18n/code)
- 5-tab layout: mixAI → cloudAI → localAI → Information → Settings
- All QComboBox → NoScrollComboBox, --dangerously-skip-permissions unified

### Removed
- Settings tab: Language/CLI/Ollama/Resident/CustomServer sections (moved to respective tabs)
- search_mode_combo (replaced by Browser Use checkbox)

## [9.5.0] - 2026-02-16

### Added - "Cross-Device Sync"
- **[Feature A] Web実行ロック**: Web UIからAI実行中にWindowsデスクトップ側にオーバーレイを表示し入力をブロック。ファイルベースのロック(`data/web_execution_lock.json`)をQTimerで2秒間隔ポーリング
- **`src/widgets/web_lock_overlay.py`** (new): 半透明ダーク背景のPyQt6オーバーレイウィジェット（`show_lock()`/`hide_lock()`）
- **`src/web/file_transfer.py`** (new): アップロードバリデーション（ホワイトリスト/ブラックリスト拡張子、10MBサイズ制限）
- **[Feature B] モバイルファイル添付**: `POST /api/files/upload`（ストリーミング64KB書き込み）、`GET /api/files/uploads`、`DELETE /api/files/uploads/{filename}`
- **[Feature C] デバイス間ファイル転送**: `GET /api/files/download`（パストラバーサル防止付き）、`POST /api/files/copy-to-project`（タイムスタンプ除去+コピー）
- **[Feature D] ログアウト後チャット閲覧**: `GET /api/chats/public-list`（認証不要、タイトル+50文字プレビュー）、`PreLoginView`コンポーネント
- **InputBar AttachMenu**: 「この端末からアップロード」+「サーバーのファイルを参照」の2段メニュー
- **FileManagerView TransferSection**: アップロード一覧、プロジェクトコピー、ダウンロードボタン

### Changed
- `server.py`: `_set_execution_lock()`/`_release_execution_lock()` 追加、soloAI/mixAI ハンドラにtry/finally
- `api_routes.py`: 6つの新エンドポイント追加（lock, upload, uploads, download, copy-to-project, public-list）
- `main_window.py`: QTimerによるWeb実行ロック監視（`_check_web_execution_lock`, `_activate_web_lock`, `_deactivate_web_lock`）
- `helix_orchestrator_tab.py`, `claude_tab.py`: `WebLockOverlay` 設置
- `App.jsx`: `PreLoginView` + `showLogin` 状態による認証フロー
- Updated version to 9.5.0 "Cross-Device Sync" in `constants.py`

## [9.4.0] - 2026-02-16

### Added - "Unified Timeout"
- **Timeout config helper**: New `_get_claude_timeout_sec()` in `server.py` reads timeout from config files with priority chain: `general_settings.json` > `config.json` > `app_settings.json` > default 90min
- **Web UI timeout editing**: `SettingsView.jsx` now has an editable dropdown (10/30/60/90/120/180 min) for Claude timeout, saved to `general_settings.json` via `PUT /api/settings`
- **`SettingsUpdate.claude_timeout_minutes`**: New field in the settings API model for timeout updates
- **`src/web/launcher.py`** (new): Lightweight subprocess-based web server launcher that avoids importing fastapi/PyQt6. Uses `_find_python()` to locate real python.exe in PyInstaller environments
- **`scripts/start_web_server.py`** (new): Standalone uvicorn launch script using string import path
- **Three-layer defense against double-window**: (1) `_find_python()` finds real python.exe, (2) `HELIX_WEB_SERVER_ONLY` env var guard in `HelixAIStudio.py`, (3) `CREATE_NO_WINDOW` + `DEVNULL` stdio

### Fixed
- **[P0] Double Helix window on server start**: PyInstaller's `sys.executable` pointed to `HelixAIStudio.exe`, causing `subprocess.Popen` to relaunch the entire app. Fixed with `_find_python()` + env var guard
- **[P0] Desktop/Web timeout discrepancy**: Desktop used 90min (from `general_settings.json`), Web hardcoded 600s (10min). All hardcoded 600s values replaced with `_get_claude_timeout_sec()`
- **[P1] PyQt6 import chain leak**: `server.py → backends/__init__.py → mix_orchestrator.py → PyQt6` chain caused QApplication creation in web server subprocess. Fixed with try/except stub in `mix_orchestrator.py` + `importlib.util` direct loading in `server.py`
- **[P1] Tailscale IP timeout**: Separated Tailscale IP lookup into independent try block with 10s timeout and full path search (`C:\Program Files\Tailscale\tailscale.exe` fallback)
- **[P2] `_load_merged_settings()` missing general_settings.json**: GET `/api/settings` now reads from `general_settings.json` (highest priority for timeout)

### Changed
- `server.py` soloAI/mixAI handlers: `data.get("timeout", 600)` → `data.get("timeout") or _get_claude_timeout_sec()`
- `server.py` `_run_claude_cli_async()`: default `timeout=600` → `timeout=0` with config resolution
- `api_routes.py` `SoloExecuteRequest.timeout`: default `600` → `0`
- `api_routes.py` `SettingsResponse.claude_timeout_minutes`: default `30` → `90`
- `settings_cortex_tab.py`: import from `..web.launcher` instead of `..web.server`
- `main_window.py`: import from `.web.launcher` instead of `.web.server`
- `mix_orchestrator.py`: PyQt6 import wrapped in try/except with threading-based stubs
- Updated version to 9.4.0 "Unified Timeout" in `constants.py`

## [9.3.0] - 2026-02-16

### Added - "Switchable Engine"
- **P1/P3 engine switching**: Dropdown in mixAI tab to switch between Claude CLI and local LLM (Ollama Agent) for Phase 1/3 execution
- **`src/backends/local_agent.py`** (new): LocalAgentRunner with 5 tools (read_file, list_dir, search_files, write_file, create_file), max 15 agent loops, path traversal prevention
- **Server auto-start**: Toggle button, auto-start checkbox, and port number in settings tab. `main_window.py` auto-starts on boot if `web_server.auto_start=true`
- **`config.json` extensions**: `orchestrator_engine`, `local_agent_tools`, `web_server` sections

## [8.4.2] - 2026-02-11

### Fixed
- **[P0] BibleParser root cause fix**: Changed `BibleDiscovery.discover()` to call `parse_full()` instead of `parse_header()`. This resolves the issue where sections were always detected as 0 count across 3 versions. Now all 32 BIBLEs show proper section detection with the latest v8.4.1 showing 23 sections / 89.0% completeness.
- **[P0] Settings persistence bug**: Added `max_phase2_retries` to `OrchestratorConfig` dataclass, implemented full lifecycle (to_dict, from config restoration, UI update). Settings are now properly persisted across restarts.
- **[P1] UI consistency**: Changed mixAI save button from full-width cyan `PRIMARY_BTN` to right-aligned small button matching soloAI/general settings style using `QHBoxLayout` + `addStretch()` pattern.

### Changed
- Updated version to 8.4.2 in `constants.py` and `app_settings.json`

## [8.4.1] - 2026-02-11

### Fixed
- **[P0] BibleParser section identification**: Added `_NUM_` pattern to `SECTION_HEADING_MAP` to support numbered headings like `## 3. アーキテクチャ概要`. Applied rf-string `_NUM_` to all 16 section types.
- **[P1] BIBLE documentation corrections**:
  - Fixed Section 6.4 timeout settings placement (moved from Display & Theme to Claude Model Settings)
  - Corrected GPU 1 name: NVIDIA RTX PRO 6000 → NVIDIA RTX PRO 6000 Blackwell Workstation Edition

### Added
- Additional patterns to HEADER (`プロジェクト概要`), ARCHITECTURE (`RAPTOR`), CHANGELOG (`付録`)

## [8.4.0] - 2026-02-10

### Added - "Contextual Intelligence"
- **Context7 MCP Integration**: Phase 1 prompt now guides Claude to use Context7 MCP servers for accessing latest library documentation
- **Structured Phase 1 (2-stage prompts)**:
  - Stage 1: Design Analysis (requirements, tech elements, risks, task distribution)
  - Stage 2: Instruction Generation with acceptance_criteria, context, expected_output_format
- **Phase 3 AcceptanceCriteria Evaluation**: Automatic PASS/FAIL checklist injection and criteria_evaluation output field
- **Mid-Session Summary**: Automatically generates 1-2 sentence summaries every 5 messages (configurable via `MID_SESSION_TRIGGER_COUNT`) to maintain context quality in long sessions
  - New `raptor_mid_session_summary()` method in memory_manager.py
  - RaptorWorker mode parameter for background execution

### Changed
- Phase 1 JSON output now includes: `design_analysis`, `acceptance_criteria`, `context`, `expected_output_format`
- Phase 3 prompt dynamically includes AcceptanceCriteria PASS/FAIL checklist
- `episode_summaries.level` CHECK constraint now includes 'mid_session'
- `raptor_get_multi_level_context()` prioritizes mid_session summaries over weekly/session

## [8.3.1] - 2026-02-09

### Fixed
- **[P0] Configuration inconsistency**:
  - Updated `app_settings.json` claude.default_model to "claude-opus-4-6"
  - Added startup logic in `HelixAIStudio.py` to auto-correct claude.default_model if misconfigured

### Changed - "Living Memory" Quality & Performance
- **[P1] O(n²) mitigation in Temporal KG**:
  - `_auto_link_session_facts()` now caps at `MAX_LINK_FACTS=20` facts
  - Only links facts sharing the same entity (reduced from all-pairs)
  - Uses `INSERT OR IGNORE` + `UNIQUE INDEX idx_edge_unique` to prevent duplicates
- **[P1] Calendar-week alignment for RAPTOR**:
  - `raptor_try_weekly()` now uses ISO calendar week boundaries (Monday-Sunday)
  - Changed minimum session count from 5→3 for weekly summary generation
  - Added duplicate weekly summary prevention check
- **[P2] Memory injection safety**: Added guard text to all memory context injections to reduce prompt injection risk from stored memories
- **[P2] LLM robustness**: `_call_resident_llm()` now has `retries=2` with 2-second backoff
- **[P2] RAPTOR completeness tracking**:
  - Added `status` column to `episode_summaries` ('completed'/'pending')
  - New `raptor_summarize_version()` method to aggregate weekly summaries into version-level summaries
  - New `retry_pending_summaries()` method to retry failed summaries
- **[P2] Async RAPTOR execution**:
  - soloAI: New `RaptorWorker(QThread)` class for non-blocking summary generation
  - mixAI: Uses `threading.Thread(daemon=True)` for background RAPTOR execution

## [8.3.0] - 2026-02-08

### Added - "Living Memory" Core Features
- **RAPTOR multi-level summaries (実動化)**:
  - `raptor_summarize_session()`: Session completion triggers 1-2 sentence summary via ministral-3:8b
  - `raptor_try_weekly()`: Auto-generates weekly summaries when ≥5 session summaries exist
  - `raptor_get_multi_level_context()`: Vector search across session+weekly levels with priority merging
- **Temporal Knowledge Graph実動化**:
  - `_auto_link_session_facts()`: Auto-adds co_occurrence edges between facts in same session
  - `get_fact_neighbors()`: BFS traversal of semantic_edges subgraphs with configurable depth
- **GraphRAG community summaries**:
  - `graphrag_community_summary()`: Summarizes entity-centered subgraphs (depth=2) into 3-sentence abstracts via ministral-3:8b
- **Resident LLM helper**: `_call_resident_llm(prompt, max_tokens)` for synchronous ministral-3:8b calls (timeout=60s)

### Changed
- Phase 1 context now includes RAPTOR multi-level summary section
- RAPTOR triggers added to 3 locations: soloAI `_on_cli_response()`, `_on_executor_response()`, mixAI `_execute_pipeline()`

### Removed
- **helix_core module complete removal**: Deleted entire `src/helix_core/` directory (12 files) including deprecated modules (memory_store, vector_store, light_rag, rag_pipeline, hybrid_search_engine)

## [8.2.0] - 2026-02-07

### Added - "Memory as the Exoskeleton"
- **Phase 2 RAG context injection**:
  - New `build_context_for_phase2()` method with 5-category support (coding/research/reasoning/translation/vision)
  - Category-specific memory retrieval: `search_episodic_by_text()`, `search_semantic_by_text()`, `search_procedural_by_text()`
  - Synchronous embedding helper: `_get_embedding_sync()`
- Phase 2 loop in `mix_orchestrator.py` now injects RAG context at both initial execution and retry loops

### Deprecated
- 5 helix_core modules marked DEPRECATED: memory_store, vector_store, light_rag, rag_pipeline, hybrid_search_engine
- These modules will be removed in v8.3.0

## [8.1.0] - 2026-02-06

### Added - Memory Architecture Overhaul
- **4-layer memory system** (HelixMemoryManager):
  - Layer 1: Thread Memory (in-memory, session-scoped)
  - Layer 2: Episodic Memory (SQLite, RAPTOR multi-level summaries: session→weekly→version)
  - Layer 3: Semantic Memory (Temporal Knowledge Graph with valid_from/valid_to)
  - Layer 4: Procedural Memory (reusable workflows with use_count tracking)
- **Memory Risk Gate**:
  - AI response → ministral-3:8b extracts memory candidates → validates with ADD/UPDATE/DEPRECATE/SKIP judgments
  - Integrated into post-processing for both mixAI and soloAI tabs
- **Memory context injection**:
  - Phase 1/3 (mixAI), soloAI: Automatic memory context blocks injected before LLM calls
  - Format: `<memory_context>...</memory_context>` with episodic/semantic/procedural sections

### Changed - UI Reorganization
- **soloAI settings cleanup**:
  - Removed: API key input, connection test, MCP server management, Claude model selection
  - Kept: Model selection dropdown (backend), execution config
- **General settings consolidation**:
  - New sections: "Claude Model Settings" (top), "MCP Server Management" (all servers enabled by default), "Memory & Knowledge Management"
  - Absorbed: Tool settings (MCP) from mixAI, RAG settings from mixAI
- **mixAI settings**: Removed Tool Settings (MCP) and RAG Settings → consolidated into General Settings

## [8.0.0] - 2026-02-05

### Added - "BIBLE-first" System
- **BIBLE Manager** (5-module system):
  - `bible_schema.py`: 16 section types, BibleInfo dataclass, completeness scoring
  - `bible_parser.py`: Markdown section classifier + completeness calculator
  - `bible_discovery.py`: 3-phase discovery (current→child→parent) with 5 filename patterns
  - `bible_injector.py`: Context builders for phase1/phase3/update modes
  - `bible_lifecycle.py`: Autonomous lifecycle manager (NONE/UPDATE/ADD_SECTIONS/CREATE_NEW/VERSION_UP)
- **BIBLE UI widgets**:
  - `bible_panel.py`: Status panel with 6 action buttons (検出/作成/表示/更新/差分/バージョンアップ)
  - `bible_notification.py`: Auto-discovery notification bar
- **Markdown renderer** (`markdown_renderer.py`): Pure Python Markdown→HTML converter (PyInstaller compatible)

### Changed
- Phase 1/3 prompts now receive BIBLE context injection (architecture, changelog, directory structure, tech stack)
- `chat_widgets.py`: Enhanced chat components with BIBLE markdown rendering support

## [7.2.0] and earlier

See `BIBLE_Helix AI Studio_7.2.0.md` for detailed historical changes including:
- v7.0.0: SequentialExecutor introduction (96GB VRAM support)
- v6.3.0: Chain-of-thought filtering
- v6.0.0: Claude CLI-only migration (removed Anthropic SDK)

---

## Version Naming Convention

Since v8.0.0, versions follow this pattern:
- **Major.Minor.Patch** (e.g., 8.4.2)
- **Codename** reflecting the version theme (e.g., "Contextual Intelligence")

---

For full architectural details, see `PROJECT_BIBLE.md`.
