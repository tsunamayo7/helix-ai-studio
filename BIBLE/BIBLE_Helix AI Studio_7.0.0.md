# Helix AI Studio - Project BIBLE (包括的マスター設計書)

**バージョン**: 7.0.0 "Orchestrated Intelligence"
**アプリケーションバージョン**: 7.0.0
**作成日**: 2026-02-09
**最終更新**: 2026-02-09
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v7.0.0 "Orchestrated Intelligence" 更新履歴

### コンセプト: "Orchestrated Intelligence" (統合知能)

v7.0.0は旧5Phase実行パイプラインを新3Phase実行パイプラインに全面刷新。Claude Code CLIの`--cwd`オプションによるツール自律利用、ローカルLLMの順次実行エンジン、Phase間の短期記憶システムを実装:

### 主な変更点

1. **旧5Phase→新3Phase実行パイプラインへの全面書き換え**
   - Phase 1: Claude CLI計画立案（`--cwd`オプション付き、ツール使用指示を明記）
   - Phase 2: ローカルLLM順次実行（Ollama APIで1モデルずつロード→実行→アンロード）
   - Phase 3: Claude CLI比較統合（2回目呼び出し、Phase 1+Phase 2全結果を渡す）
   - 旧Phase 3（品質検証ループ）→ Phase 3内の再実行ループに統合
   - 旧Phase 4（Claude統合）→ 新Phase 3に統合
   - 旧Phase 5（ナレッジ保存）→ 既存のKnowledge DBを継承

2. **Claude Code CLI `--cwd`オプション活性化**
   - `--cwd`でプロジェクトディレクトリを指定し、Claudeが自発的にRead/Write/Bash等のツールを使用
   - ファイル埋め込み方式を廃止（Claudeが自分でReadツールを使用）
   - `--dangerously-skip-permissions`で自動許可、`--output-format json`でJSON出力

3. **ローカルLLM順次実行エンジン（sequential_executor.py）**
   - 旧`parallel_pool.py`（ThreadPoolExecutor並列実行）を置き換え
   - RTX PRO 6000 (96GB) で大型モデル(67-80GB)を1つずつ動かす設計
   - Ollama API `/api/generate` で `keep_alive: "1m"` を指定し、次のモデルロードのためにすぐにアンロード可能
   - chain-of-thoughtフィルタリングを継承（v6.3.0の`filter_chain_of_thought()`）

4. **カテゴリ刷新（4カテゴリ→5カテゴリ）**
   - 旧: 検索 / レポート / アーキテクト / コーディング
   - 新: coding / research / reasoning / translation / vision
   - 各カテゴリに最適なモデルを割り当て

5. **UI全面刷新**
   - Neural Flow Visualizer: 5ノード→3ノード（P1:Claude計画, P2:ローカルLLM, P3:Claude統合）
   - 設定タブ: 5カテゴリ + MCP設定セクション追加
   - 常駐モデル: 制御AI (ministral-3:8b) + Embedding (qwen3-embedding:4b) の2モデルのみ
   - MixAIWorkerのStage表示をPhase表示に統一

6. **短期記憶（Session Memory）**
   - `data/sessions/{timestamp}/` にPhase間の中間結果をファイルとして保存
   - Phase 1計画JSON、Phase 2各タスク結果、Phase 3統合結果、メタデータ

---

## 削除ファイル一覧 (v7.0.0)

| ファイル | 理由 |
|----------|------|
| `src/backends/parallel_pool.py` | `sequential_executor.py`に置き換え |
| `src/backends/phase1_parser.py` | `mix_orchestrator.py`内に統合 |
| `src/backends/phase1_prompt.py` | `mix_orchestrator.py`内に統合 |
| `src/backends/phase4_prompt.py` | Phase 3統合プロンプトに置き換え |
| `src/backends/quality_verifier.py` | Phase 3再実行ループに置き換え |

---

## アーキテクチャ概要

### 3Phase実行パイプライン (v7.0.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                    3Phase Execution Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Claude CLI計画立案                                     │
│      - --cwdオプション付き、ツール使用指示を明記                   │
│      - JSON出力: claude_answer, local_llm_instructions,          │
│                  complexity, skip_phase2                          │
│      - complexity="low"またはskip_phase2=true → Phase 2-3スキップ │
│      ↓                                                          │
│  Phase 2: ローカルLLM順次実行                                    │
│      - SequentialExecutor: 1モデルずつロード→実行→アンロード     │
│      - カテゴリ: coding/research/reasoning/translation/vision     │
│      - chain-of-thoughtフィルタリング適用                         │
│      ↓                                                          │
│  Phase 3: Claude CLI比較統合                                     │
│      - Phase 1回答 + Phase 2全結果を渡す                         │
│      - 品質不足時: retry_tasks指示 → Phase 2再実行（最大2回）    │
│      - 最終回答(final_answer)をユーザーに表示                     │
└─────────────────────────────────────────────────────────────────┘
```

### ファイル依存関係

```
MixAIOrchestrator (mix_orchestrator.py)
    │
    ├── Phase 1 → Claude CLI (-p --output-format json --cwd)
    │       └── _build_phase1_system_prompt() (内蔵)
    │       └── _execute_phase1() → _run_claude_cli()
    │
    ├── Phase 2 → SequentialExecutor (sequential_executor.py)
    │       └── filter_chain_of_thought() [v6.3.0継承]
    │       └── save_phase2_results() → data/sessions/{id}/phase2/
    │
    ├── Phase 3 → Claude CLI (-p --output-format json)
    │       └── _build_phase3_system_prompt() (内蔵)
    │       └── _execute_phase3() → _run_claude_cli()
    │       └── _check_phase3_retry() → 再実行判定
    │
    └── Session Memory → data/sessions/{timestamp}/
            ├── phase1_plan.json
            ├── phase1_claude_answer.txt
            ├── phase2/ (各タスク結果)
            ├── phase3_integration.txt
            └── metadata.json
```

### カテゴリ別担当モデル (Phase 2)

| カテゴリ | 第1選択 | VRAM | 用途 |
|----------|---------|------|------|
| coding | devstral-2:123b | 75GB | コード生成・修正・レビュー |
| research | command-a:111b | 67GB | 調査・RAG検索・情報収集 |
| reasoning | gpt-oss:120b | 80GB | 推論・論理検証・品質チェック |
| translation | translategemma:27b | 18GB | 翻訳タスク |
| vision | gemma3:27b | 18GB | 画像解析・UI検証 |

### 常駐モデル

| モデル | GPU | VRAM | 用途 |
|--------|-----|------|------|
| ministral-3:8b | 5070 Ti | 6.0GB | 制御AI |
| qwen3-embedding:4b | 5070 Ti | 2.5GB | Embedding (RAG検索) |

---

## 変更ファイル一覧 (v7.0.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/mix_orchestrator.py` | 全面書き換え: 旧5Phase→新3Phase実行パイプライン、Claude CLI `--cwd`、短期記憶 |
| `src/backends/sequential_executor.py` | **新規作成**: Phase 2順次実行エンジン、SequentialTask/Result、filter_chain_of_thought |
| `src/backends/__init__.py` | 新モジュールのインポート追加 |
| `src/utils/constants.py` | APP_VERSION=7.0.0, APP_CODENAME="Orchestrated Intelligence" |
| `src/tabs/helix_orchestrator_tab.py` | 3Phase対応UI、設定タブ5カテゴリ化、MCP設定、Stage→Phase統一 |
| `src/widgets/neural_visualizer.py` | 5ノード→3ノード化（P1/P2/P3） |
| `src/widgets/vram_simulator.py` | MODEL_CATALOGを5カテゴリ対応に更新 |
| `HelixAIStudio.spec` | hiddenimports: 削除5モジュール除去、sequential_executor追加 |

---

## ディレクトリ構造 (v7.0.0)

```
Helix AI Studio/
├── HelixAIStudio.py          # エントリーポイント
├── HelixAIStudio.exe         # ビルド済み実行ファイル
├── HelixAIStudio.spec        # PyInstaller設定 (v7.0.0更新)
├── src/
│   ├── main_window.py        # メインウィンドウ
│   ├── backends/
│   │   ├── base.py               # LLMBackend基底クラス
│   │   ├── claude_backend.py     # Claude APIバックエンド
│   │   ├── claude_cli_backend.py # Claude CLIバックエンド
│   │   ├── cloud_adapter.py      # クラウド自動選択
│   │   ├── gemini_backend.py     # Gemini APIバックエンド
│   │   ├── local_backend.py      # ローカルLLMバックエンド
│   │   ├── local_connector.py    # Ollama接続管理
│   │   ├── local_llm_manager.py  # ローカルLLM管理
│   │   ├── mix_orchestrator.py   # v7.0.0: 3Phase実行エンジン
│   │   ├── model_repository.py   # モデルリポジトリ
│   │   ├── registry.py           # バックエンドレジストリ
│   │   ├── sequential_executor.py # v7.0.0: Phase 2順次実行エンジン (新規)
│   │   ├── thermal_monitor.py    # GPU温度監視
│   │   ├── thermal_policy.py     # サーマルポリシー
│   │   └── tool_orchestrator.py  # ツールオーケストレーター
│   ├── tabs/
│   │   ├── helix_orchestrator_tab.py  # mixAIタブ (v7.0.0: 3Phase対応)
│   │   ├── claude_tab.py              # Claude専用タブ
│   │   └── settings_cortex_tab.py     # 設定タブ
│   ├── widgets/
│   │   ├── neural_visualizer.py  # Neural Flow Visualizer (v7.0.0: 3ノード)
│   │   ├── vram_simulator.py     # VRAM Budget Simulator (v7.0.0: 5カテゴリ)
│   │   └── chat_input.py        # チャット入力ウィジェット
│   ├── knowledge/
│   │   ├── knowledge_manager.py  # Knowledge DB管理 (長期記憶)
│   │   └── knowledge_worker.py   # Knowledge非同期ワーカー
│   └── utils/
│       └── constants.py          # バージョン定数 (7.0.0)
├── config/                       # 設定ファイル
├── data/
│   ├── sessions/                 # v7.0.0: 短期記憶 (Phase間中間結果)
│   ├── knowledge/                # 長期記憶 (SQLite + Embedding)
│   └── chat_history/             # チャット履歴
├── logs/                         # ログファイル
├── dist/                         # ビルド出力
└── BIBLE/
    ├── BIBLE_Helix AI Studio_6.3.0.md  # v6.3.0 BIBLE (履歴)
    └── BIBLE_Helix AI Studio_7.0.0.md  # 本ファイル
```

---

## GPU環境要件

### 推奨構成 (開発者環境)

- **GPU 0**: RTX PRO 6000 Blackwell (96GB VRAM) — Phase 2大型モデル用
- **GPU 1**: RTX 5070 Ti (16GB VRAM) — 常駐モデル用
- **合計VRAM**: 112GB

### GPU使用パターン (v7.0.0)

```
RTX PRO 6000 (96GB):
  Phase 2で順次使用:
    devstral-2:123b (75GB) → アンロード
    command-a:111b (67GB) → アンロード
    gpt-oss:120b (80GB) → アンロード
    ※ 1モデルずつロード→実行→アンロードの順次実行

RTX 5070 Ti (16GB):
  常時ロード:
    ministral-3:8b (6.0GB) — 制御AI
    qwen3-embedding:4b (2.5GB) — Embedding
    合計: ~8.5GB
```

---

## 技術スタック (v7.0.0)

| カテゴリ | 技術 | バージョン/詳細 |
|---------|------|----------------|
| 言語 | Python | 3.12.7 |
| GUI | PyQt6 | 6.x |
| グラフィックス | QGraphicsScene | ノードベース可視化 (3ノード) |
| Claude連携 | Claude Code CLI | `-p --output-format json --cwd` |
| ローカルLLM | Ollama API | HTTP REST (`/api/generate`) |
| ビルド | PyInstaller | 6.17.0 |
| データベース | SQLite3 | Knowledge管理 (長期記憶) |
| 記憶システム | ファイルベース | 短期: data/sessions/, 長期: SQLite |

---

## 記憶システム (v7.0.0)

### 二層記憶アーキテクチャ

| 層 | 保存先 | 用途 | 実装 |
|----|--------|------|------|
| 短期記憶 | `data/sessions/{timestamp}/` | Phase間の中間成果物保持 | `MixAIOrchestrator._save_session_*()` |
| 長期記憶 | `data/knowledge/knowledge.db` | 重要情報の永続保存、RAG検索 | `KnowledgeManager` (v6.3.0継承) |

### 短期記憶のファイル構造

```
data/sessions/{timestamp}/
├── phase1_plan.json         # Phase 1の計画JSON (claude_answer, local_llm_instructions等)
├── phase1_claude_answer.txt # Phase 1のClaude初回回答テキスト
├── phase2/
│   ├── task_1_devstral-2_123b.txt  # Phase 2各タスクの成果物
│   ├── task_2_command-a_111b.txt
│   └── task_3_gpt-oss_120b.txt
├── phase3_integration.txt   # Phase 3の統合結果
└── metadata.json            # セッションメタデータ (実行時間、タスク数等)
```

---

## v6.3.0 → v7.0.0 移行ガイド

### 破壊的変更

1. **バックエンド完全書き換え**: `mix_orchestrator.py`が全面刷新されたため、旧5Phase APIに依存するコードは動作しない
2. **5ファイル削除**: `parallel_pool.py`, `phase1_parser.py`, `phase1_prompt.py`, `phase4_prompt.py`, `quality_verifier.py`
3. **カテゴリ名変更**: 検索→research, レポート→research, アーキテクト→reasoning, コーディング→coding
4. **常駐モデル変更**: nemotron-3-nano:30bが常駐から外れ、Phase 2のresearchカテゴリで順次実行に移行

### 互換性

- v6.3.0の設定ファイルはそのまま使用可能（旧設定値はデフォルトにフォールバック）
- Knowledge DB (SQLite) スキーマ変更なし
- チャット履歴の互換性維持

---

*このBIBLEは Claude Opus 4 により生成されました*
