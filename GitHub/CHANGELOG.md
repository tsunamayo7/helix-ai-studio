# Changelog

All notable changes to Helix AI Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

For full architectural details, see `BIBLE_Helix AI Studio_8.4.2.md`.
