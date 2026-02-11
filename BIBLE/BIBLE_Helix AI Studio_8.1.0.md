# BIBLE — Helix AI Studio v8.1.0 "Adaptive Memory"

**最終更新**: 2026-02-10
**バージョン**: 8.1.0 "Adaptive Memory"
**前バージョン**: 8.0.0 "Living Bible"

> このドキュメントは Helix AI Studio の設計・構成・運用の全てを1ファイルで把握するための
> 「聖典（BIBLE）」です。新たなAIアシスタントやコントリビューターがプロジェクトに参加した際、
> このファイルを読むだけで全体像を理解できることを目指しています。

---

## 1. プロジェクト概要

### 1.1 名称・バージョン

| 項目 | 値 |
|------|-----|
| アプリケーション名 | Helix AI Studio |
| バージョン | 8.1.0 |
| コードネーム | "Adaptive Memory" |
| エントリポイント | `HelixAIStudio.py` |
| 配布形式 | PyInstaller exe（Windows） |

### 1.2 コンセプト

**「Claude中心のマルチモデルオーケストレーション」**

Claude（Anthropic）を「頭脳」、ローカルLLM群を「専門チーム」として配置し、
3段階のパイプライン（3Phase）で協調動作させるデスクトップAIアプリケーション。

### 1.3 設計哲学

1. **精度最大化** — Claude単体よりも、ローカルLLMの多角的視点を統合することで回答品質を向上
2. **VRAM効率化** — 120Bクラスモデルを1つずつ順次実行し、96GB VRAMを最大活用
3. **透明性** — Neural Flow Visualizerにより、AIの思考過程をリアルタイム可視化
4. **動的構成** — モデル選択はconstants.pyの1箇所変更で全UIに自動反映
5. **BIBLEファースト** — プロジェクトBIBLEを第一級オブジェクトとして扱い、自動検出・注入・更新を行う（v8.0.0新設）
6. **記憶の品質管理** — Memory Risk Gateにより、AIが生成した回答から抽出される記憶の正確性・重複排除・鮮度を常駐LLMが自律的に担保する（v8.1.0新設）
7. **UIの自己文書化** — 全UI要素にsetToolTipを付与し、マウスホバーだけで機能・設定の説明が得られるセルフドキュメンティングUI（v8.1.0新設）

---

## 2. バージョン変遷サマリー

| バージョン | コードネーム | 主な変更 |
|-----------|------------|---------|
| v1.0.0 | — | 初期リリース。Claude API直接呼び出しの単一チャット |
| v3.7.0〜v3.9.6 | — | UIリファクタリング、タブ構成確立、Claude Codeタブ追加 |
| v4.0.0〜v4.6.0 | — | GPUモニター追加、ツールオーケストレーター、MCP対応 |
| v5.0.0〜v5.2.0 | — | ウィンドウサイズ永続化、Knowledge/RAG基盤 |
| v6.0.0 | — | **5Phase実行パイプライン導入** |
| v6.1.0 | — | Cyberpunk Minimalデザイン初期導入 |
| v6.2.0 | Crystal Cognition | Neural Flow Visualizer、VRAM Budget Simulator追加 |
| v6.3.0 | True Pipeline | 5Phase安定化、chain-of-thoughtフィルタリング、GPU動的検出 |
| v7.0.0 | Orchestrated Intelligence | **5Phase→3Phase移行**。SequentialExecutor導入、常駐モデル機構 |
| v7.1.0 | Adaptive Models | Claude Opus 4.6対応、CLAUDE_MODELS動的選択 |
| v7.2.0 | Polish | UI整合性修正、旧バージョン番号除去、BIBLE統合版、GitHub公開準備 |
| v8.0.0 | Living Bible | BIBLE Manager・Markdownレンダリング・Cyberpunk Minimal UI統一 |
| **v8.1.0** | **Adaptive Memory** | **4層メモリアーキテクチャ・Memory Risk Gate・UI構造再編・ツールチップ強化** |

### v8.1.0 "Adaptive Memory" 四本柱

1. **4層メモリアーキテクチャ** — Thread/Episodic/Semantic/Proceduralの4層構造で、セッション内短期記憶から長期的事実・手順記憶まで統合管理
2. **Memory Risk Gate** — ministral-3:8bによる記憶品質判定。AI応答から記憶候補を抽出し、ADD/UPDATE/DEPRECATE/SKIPの4段階で自律的に品質担保
3. **UI構造再編** — soloAI/mixAI設定の重複排除。API認証・MCP・モデル設定を一般設定タブに統合し、「記憶・知識管理」セクションを新設
4. **UXツールチップ強化** — 全UI要素にsetToolTip付与（40件以上）、全タブの「設定を保存」ボタン有効化

### v8.0.0 "Living Bible" 三本柱（継承）

1. **BIBLE Manager** — BIBLEファイルの自動検出・パース・Phase 1/3注入・自律更新管理
2. **Markdownレンダリング** — 純Python Markdown→HTML変換による応答テキストの美しい表示
3. **UI品質向上** — スタイル中央集権化、メッセージバブル、PhaseIndicator、SoloAIStatusBar

### なぜ5Phase→3Phaseに移行したか

v6.x系の5Phaseパイプラインでは:
- Phase 1: Claude初回実行
- Phase 2: ローカルLLM並列実行
- Phase 3: 品質検証ループ
- Phase 4: Claude最終統合
- Phase 5: ナレッジ自動保存

v7.0.0で以下の理由から3Phaseに再構成:
1. **Claude CLI --cwdオプション** — Claudeが自発的にファイル読み書きできるようになり、Phase 4（統合）をPhase 3に統合可能に
2. **SequentialExecutor** — 120Bクラスモデルの並列実行はVRAM不足。順次実行に切り替え
3. **品質検証のPhase 3統合** — Claude自身が統合時に品質判断し、必要に応じてPhase 2再実行を指示
4. **ナレッジ保存の非Phase化** — Phase 5（保存）はパイプライン完了後の後処理として分離

---

## 3. アーキテクチャ概要

### 3.1 3Phase実行パイプライン

```
┌─────────────────────────────────────────────────────┐
│                  ユーザー入力                          │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 1: Claude CLI 計画立案                         │
│  ・ユーザーの質問に対する初回回答を生成                    │
│  ・各ローカルLLMへの個別指示書をJSON形式で出力             │
│  ・--cwd でプロジェクトディレクトリを指定                  │
│  ・--model {CLAUDE_MODEL_ID} でモデル指定               │
│  ・★ BIBLEコンテキスト注入（v8.0.0）                    │
│  ・★ 記憶コンテキスト注入（v8.1.0）                      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 2: ローカルLLM順次実行（SequentialExecutor）     │
│  ・Ollama API で1モデルずつロード→実行→アンロード         │
│  ・5カテゴリ: coding / research / reasoning /            │
│    translation / vision                                │
│  ・各モデルの出力は data/sessions/ に保存                 │
│  ・chain-of-thoughtフィルタリング適用                     │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 3: Claude CLI 比較統合                          │
│  ・Phase 1の回答 + Phase 2全結果を入力                   │
│  ・品質判断: 不足があればPhase 2再実行を指示               │
│  ・最終統合回答を生成                                    │
│  ・再実行ループ: 最大N回（デフォルト2回）                  │
│  ・★ BIBLEコンテキスト注入（v8.0.0）                    │
│  ・★ 記憶コンテキスト注入（v8.1.0）                      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  後処理                                               │
│  ・ナレッジ自動保存（Embedding: qwen3-embedding:4b）    │
│  ・★ BIBLEライフサイクル管理（v8.0.0）                  │
│  ・★ Memory Risk Gate（v8.1.0）                       │
│    → AI応答から記憶候補を抽出                            │
│    → ministral-3:8bで品質判定（ADD/UPDATE/DEPRECATE）   │
│    → 4層メモリへの自動分類・保存                          │
└─────────────────────────────────────────────────────┘
```

### 3.2 BIBLE Manager（v8.0.0新規）

BIBLEファイルをアプリの第一級オブジェクトとして扱う5モジュール構成:

```
┌──────────────────┐    ┌──────────────────┐
│ BibleDiscovery   │───→│  BibleParser     │
│ 自動検出エンジン    │    │  ファイルパーサー   │
│ (3段階探索)        │    │  (セクション解析)   │
└──────────────────┘    └────────┬─────────┘
                                 ▼
                        ┌──────────────────┐
                        │  BibleInfo       │
                        │  (データクラス)     │
                        └────────┬─────────┘
                          ┌──────┴──────┐
                          ▼             ▼
                ┌───────────────┐ ┌──────────────────┐
                │ BibleInjector │ │ BibleLifecycle   │
                │ Phase 1/3注入  │ │ Manager          │
                │ (コンテキスト   │ │ 自律管理エンジン   │
                │  ビルド)       │ │ (判定+実行)       │
                └───────────────┘ └──────────────────┘
```

#### モジュール詳細

| モジュール | ファイル | 役割 |
|-----------|---------|------|
| BibleSchema | `src/bible/bible_schema.py` | BibleSectionType（16種）、BibleSection、BibleInfo、BIBLE_TEMPLATE |
| BibleParser | `src/bible/bible_parser.py` | Markdownパース、セクション分類、完全性スコア算出 |
| BibleDiscovery | `src/bible/bible_discovery.py` | カレント→子→親の3段階探索、5パターンのファイル名マッチ |
| BibleInjector | `src/bible/bible_injector.py` | phase1/phase3/updateモードのコンテキストブロック構築 |
| BibleLifecycleManager | `src/bible/bible_lifecycle.py` | BibleAction判定（NONE/UPDATE/ADD_SECTIONS/CREATE_NEW/VERSION_UP） |

#### BIBLEセクション型（BibleSectionType）

| カテゴリ | セクション | 識別子 |
|---------|----------|--------|
| 必須（6） | ヘッダー、バージョン履歴、アーキテクチャ、変更履歴、ファイル一覧、ディレクトリ構造 | header, version_history, architecture, changelog, file_list, directory |
| 推奨（6） | 設計哲学、技術スタック、UIアーキテクチャ、移行ガイド、トラブルシューティング、ロードマップ | philosophy, tech_stack, ui_architecture, migration, troubleshooting, roadmap |
| 任意（4） | GPU要件、モデル設定、ビルド設定、カスタム | gpu, model_config, build_config, custom |

#### BIBLEコンテキスト注入モード

| モード | 用途 | 注入セクション |
|-------|------|--------------|
| `phase1` | 計画立案 | ヘッダー + アーキテクチャ + 変更履歴 + ディレクトリ構造 + 技術スタック |
| `phase3` | 統合 | ヘッダー + ファイル一覧 + アーキテクチャ |
| `update` | BIBLE更新 | 現在の全文 + 不足セクション情報 |

### 3.3 常駐モデル機構

GPU 0（RTX 5070 Ti 16GB）に常時ロードされるモデル:

| モデル | 用途 | VRAM |
|--------|------|------|
| ministral-3:8b | 制御AI（タスク分類・ルーティング・**記憶品質判定**） | 約6GB |
| qwen3-embedding:4b | Embedding生成（RAG/Knowledge用・**メモリ検索用**） | 約2.5GB |

これらはPhase 2の順次実行とは独立して常時稼働し、
タスク分類・ナレッジ保存・**Memory Risk Gate記憶品質判定**時に即座に応答可能。

### 3.4 SequentialExecutor（Phase 2エンジン）

`src/backends/sequential_executor.py`

v7.0.0で `parallel_pool.py` を置き換え。
RTX PRO 6000（96GB）で120Bクラスモデルを1つずつ実行するための順次実行エンジン。

- **Ollama API**: `http://localhost:11434/api`
- **モデルロードタイムアウト**: 120秒
- **ロードチェック間隔**: 2秒
- **CoTフィルタリング**: v6.3.0から継承。モデルの内部推論テキストを除去

### 3.5 品質検証ループ

Phase 3でClaude が品質不足と判断した場合:
1. 再実行すべきカテゴリと指示を返却
2. Phase 2を該当カテゴリのみ再実行
3. 再度Phase 3を実行
4. 最大N回（設定: `max_phase2_retries`、デフォルト2）

### 3.6 Markdownレンダリング（v8.0.0新規）

`src/utils/markdown_renderer.py`

純Python実装のMarkdown→HTML変換。外部ライブラリ不要（PyInstaller互換）。

対応構文:
- 見出し (`# ## ###`)
- コードブロック (` ``` `)
- リスト (`- * 1.`)
- 太字 (`**bold**`)、斜体 (`*italic*`)
- インラインコード (`` `code` ``)
- テーブル (`| col | col |`)
- 水平線 (`---`)

### 3.7 4層メモリアーキテクチャ（v8.1.0新規）

`src/memory/memory_manager.py` — **HelixMemoryManager**

MemGPT/Letta着想の短期↔長期メモリ転送とRAPTOR風多段要約を統合した4層記憶システム。

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Thread Memory（短期・セッション内）           │
│  ・Python dict による in-memory 保存                   │
│  ・session_id → List[Dict] のマッピング                │
│  ・セッション終了時に自動クリア                           │
│  ・直近の会話コンテキストを高速に提供                      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2: Episodic Memory（中期・SQLite永続化）         │
│  ・テーブル: episodes (id, session_id, role, content,   │
│    summary, embedding BLOB, timestamp)                │
│  ・テーブル: episode_summaries (id, session_id,         │
│    summary_type, content, timestamp)                  │
│  ・qwen3-embedding:4b による768次元ベクトル検索           │
│  ・RAPTOR風多段要約: session→weekly→version            │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 3: Semantic Memory（長期・Temporal KG）          │
│  ・テーブル: semantic_nodes (id, subject, predicate,    │
│    object, confidence, valid_from, valid_to, source)  │
│  ・テーブル: semantic_edges (id, from_node, to_node,    │
│    relation, weight)                                  │
│  ・networkxベースの時系列知識グラフ                       │
│  ・valid_from/valid_to による事実の鮮度管理               │
│  ・古い事実の自動DEPRECATE（valid_to設定）               │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 4: Procedural Memory（長期・手順記憶）            │
│  ・テーブル: procedures (id, title, steps JSON, tags,   │
│    embedding BLOB, usage_count, last_used, created)   │
│  ・タグ + ベクトルハイブリッド検索                        │
│  ・usage_countによる利用頻度追跡                         │
│  ・手順の再利用・更新を自動管理                           │
└─────────────────────────────────────────────────────┘
```

#### SQLiteスキーマ（data/helix_memory.db）

| テーブル | 主要カラム | 用途 |
|---------|-----------|------|
| `episodes` | id, session_id, role, content, summary, embedding, timestamp | エピソード記憶の永続化 |
| `episode_summaries` | id, session_id, summary_type, content, timestamp | RAPTOR風多段要約 |
| `semantic_nodes` | id, subject, predicate, object, confidence, valid_from, valid_to | 時系列知識グラフノード |
| `semantic_edges` | id, from_node, to_node, relation, weight | 知識グラフエッジ |
| `procedures` | id, title, steps, tags, embedding, usage_count, last_used | 手順記憶 |

#### 記憶コンテキスト注入フロー

```
ユーザー入力
    │
    ├─→ [mixAI] build_context_for_phase1() → Phase 1 プロンプトに注入
    │         build_context_for_phase3() → Phase 3 プロンプトに注入
    │
    └─→ [soloAI] build_context_for_solo() → processed_message に <memory_context> 注入
```

- **mixAI**: `mix_orchestrator.py` の Phase 1/3 実行前に記憶コンテキストを挿入
- **soloAI**: `claude_tab.py` の `_send_message()` で processed_message 生成直後に挿入
- 注入形式: `<memory_context>...</memory_context>` ブロック

### 3.8 Memory Risk Gate（v8.1.0新規）

`src/memory/memory_manager.py` — **MemoryRiskGate**

AI応答から記憶候補を抽出し、常駐LLM（ministral-3:8b）で品質判定を行うゲートキーパー。

```
AI応答テキスト
    │
    ▼
┌────────────────────────────────┐
│  MemoryRiskGate.extract_memories()  │
│  ・ministral-3:8bに応答を送信        │
│  ・JSON形式で記憶候補を抽出           │
│    - facts: [{subject, predicate, object}]  │
│    - procedures: [{title, steps, tags}]     │
│    - tags: [string]                         │
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐
│  MemoryRiskGate.validate_memories()  │
│  ・既存記憶との重複チェック           │
│  ・ministral-3:8bで判定:             │
│    - ADD: 新規記憶として追加           │
│    - UPDATE: 既存記憶を更新           │
│    - DEPRECATE: 古い記憶を無効化      │
│    - SKIP: 保存不要                  │
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐
│  HelixMemoryManager.evaluate_and_store()  │
│  ・判定結果に基づき4層メモリに保存    │
│  ・Episodic: 全応答を要約保存         │
│  ・Semantic: factsをKGノードに変換    │
│  ・Procedural: 手順を保存・更新       │
└────────────────────────────────┘
```

#### mixAI / soloAI 共通フロー

- **mixAI**: Phase 3完了後の後処理で `evaluate_and_store()` を非同期実行
- **soloAI**: `_on_cli_response()` / `_on_executor_response()` で `evaluate_and_store()` を実行
- 両タブとも Memory Risk Gate の実行失敗時は `logger.warning()` で記録し、メイン処理には影響しない

---

## 4. CLAUDE_MODELS定数

`src/utils/constants.py` で定義。全UIのモデル選択はこの定数から動的生成される。

### 4.1 現在のモデル定義

```python
CLAUDE_MODELS = [
    {
        "id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6 (最高知能)",
        "description": "最も高度で知的なモデル。複雑な推論・計画立案に最適",
        "tier": "opus",
        "is_default": True
    },
    {
        "id": "claude-opus-4-5-20250929",
        "display_name": "Claude Opus 4.5 (高品質)",
        "description": "高品質でバランスの取れた応答。安定性重視",
        "tier": "opus",
        "is_default": False
    },
    {
        "id": "claude-sonnet-4-5-20250929",
        "display_name": "Claude Sonnet 4.5 (高速)",
        "description": "高速応答とコスト効率。日常タスク向き",
        "tier": "sonnet",
        "is_default": False
    },
]
DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"
```

### 4.2 モデル追加手順

1. `CLAUDE_MODELS` リストに新しいdictを追加
2. `id`: Anthropic APIのモデルID
3. `display_name`: UIに表示される名前
4. `description`: ツールチップに表示される説明
5. `tier`: "opus" または "sonnet"
6. `is_default`: デフォルトモデルの場合 True（1つのみ）
7. 変更は全UI（mixAI/soloAI両方のドロップダウン + 一般設定）に自動反映

### 4.3 ヘルパー関数

- `get_claude_model_by_id(model_id)` — IDからモデル定義を取得
- `get_default_claude_model()` — デフォルトモデル定義を取得
- `ClaudeModels.all_models()` — 全表示名リストを返す（後方互換）

---

## 5. UIアーキテクチャ

### 5.1 タブ構成

アプリケーションは3つのメインタブで構成:

```
┌───────────┬───────────┬──────────┐
│  mixAI    │  soloAI   │  一般設定  │
└───────────┴───────────┴──────────┘
```

### 5.2 mixAIタブ

**ファイル**: `src/tabs/helix_orchestrator_tab.py`

#### チャットサブタブ
- **PhaseIndicator（v8.0.0）**: P1→P2→P3の3ノード状態インジケーター。アクティブ/完了/未実行を色分け表示
- Neural Flow Visualizer（コンパクト版）: 3Phaseパイプラインのリアルタイム進捗表示
- チャットログ: 3Phase実行の全ステップとツール実行結果を表示
- ステータスバー: バージョン、ナレッジ保存状態

#### 設定サブタブ
- **Claude設定**: モデル選択（CLAUDE_MODELSから動的生成）、認証方式、思考モード
- **Ollama接続**: ホストURL、接続テスト、モデル一覧取得
- **常駐モデル**: 制御AI + Embedding の割り当て確認
- **3Phase実行設定**: カテゴリ別担当モデル選択（5カテゴリ）
- **品質検証設定（ローカルLLM再実行）**: 最大再実行回数
- ~~ツール設定（MCP）~~: v8.1.0で一般設定タブに統合
- **VRAM Budget Simulator**: GPU別VRAM配置シミュレーション
- **GPUモニター**: リアルタイムGPU使用率グラフ（時間軸選択・シークバー対応）
- ~~RAG設定~~: v8.1.0で一般設定タブ「記憶・知識管理」に統合

#### v8.1.0変更点
- ツール設定(MCP)セクション → 一般設定タブへ移設（互換性用ダミーラベル残置）
- RAG設定セクション → 一般設定タブ「記憶・知識管理」へ移設（互換性用不可視ダミーウィジェット残置）
- 記憶コンテキスト: Phase 1/3に `build_context_for_phase1/phase3()` で自動注入
- 全UI要素にsetToolTip追加（12件以上）

### 5.3 soloAIタブ

**ファイル**: `src/tabs/claude_tab.py`

#### チャットサブタブ
- **メッセージバブル（v8.0.0）**: ユーザー/AI応答をカード型バブルで表示。ユーザー＝シアン左ボーダー、AI＝グリーン左ボーダー
- **添付ファイルチップ（v8.0.0）**: ユーザーメッセージ内に添付ファイル名をチップ形式で表示
- **SoloAIStatusBar（v8.0.0）**: 旧S0-S5ステージUIを置換。ステータスドット+テキスト+新規セッションボタン
- **記憶コンテキスト自動注入（v8.1.0）**: `build_context_for_solo()` で `<memory_context>` ブロックを自動挿入
- 会話継続機能
- Diff表示（差分ビューア）
- 自動コンテキスト

#### ツールバー（v8.0.0で2行化）
- **Row 1**: モデル | 思考モード
- **Row 2**: MCP | 差分表示 | 自動コンテキスト | 許可 | 新規セッション

#### 設定サブタブ（v8.1.0で簡素化）
- **CLI認証設定**: CLI認証方式の確認（APIキー入力は削除）
- **Ollamaホスト設定**: ホストURL
- ~~API認証~~: v8.1.0で削除（CLI認証に統一）
- ~~MCPサーバー管理~~: v8.1.0で一般設定タブに移設
- ~~Claudeモデル選択~~: v8.1.0で一般設定タブに移設

#### v8.1.0変更点
- APIキー入力・接続テストボタン削除
- MCPサーバー管理 → 一般設定タブへ移設
- Claudeモデル設定 → 一般設定タブへ移設
- Memory Risk Gate: `_on_cli_response()` / `_on_executor_response()` で応答後に自動実行
- 全UI要素にsetToolTip追加（10件以上）

### 5.4 一般設定タブ（v8.1.0大幅更新）

**ファイル**: `src/tabs/settings_cortex_tab.py`

v8.1.0で7セクション構成に拡充:

| # | セクション | 内容 |
|---|----------|------|
| 1 | **Claudeモデル設定** | CLAUDE_MODELSから動的生成されるドロップダウン。全タブ共通のモデル選択 |
| 2 | **Claude CLI 状態** | CLI認証状態の表示（バージョン・認証状況） |
| 3 | **MCPサーバー管理** | ファイルシステム/Git/Brave検索の有効化チェックボックス（全ON初期値） |
| 4 | **記憶・知識管理** | RAG有効化、記憶自動保存、検索閾値、Memory Risk Gateトグル、統計表示 |
| 5 | **表示とテーマ** | フォントサイズ、タイムアウト |
| 6 | **自動化** | 自動保存、自動コンテキスト |
| 7 | **保存ボタン** | 全設定をgeneral_settings.json + app_settings.jsonに保存 |

#### 記憶・知識管理セクション詳細
- **RAG有効化**: Knowledge/RAG検索の有効・無効
- **記憶自動保存**: Memory Risk Gate後の自動保存トグル
- **検索閾値**: 類似度しきい値（High/Medium/Low）
- **Memory Risk Gateトグル**: 記憶品質判定の有効・無効
- **統計表示**: エピソード数・事実数・手順数のリアルタイム表示
- **古い記憶のクリーンアップ**: 90日以上前の記憶を自動整理

### 5.5 チャット強化ウィジェット（v8.0.0新規）

**ファイル**: `src/widgets/chat_widgets.py`

| ウィジェット | クラス名 | 用途 |
|------------|---------|------|
| PhaseIndicator | `PhaseIndicator` | 3Phase状態の視覚的インジケーター（P1/P2/P3ノード） |
| SoloAIStatusBar | `SoloAIStatusBar` | soloAI実行状態のシンプル表示（旧ステージUI置換） |
| ExecutionIndicator | `ExecutionIndicator` | チャットエリア内の実行中インジケーター（アニメーションドット+経過時間） |
| InterruptionBanner | `InterruptionBanner` | 中断時バナー（続行/再実行/キャンセル ボタン） |

### 5.6 BIBLE UIウィジェット（v8.0.0新規）

| ウィジェット | ファイル | 用途 |
|------------|---------|------|
| BibleStatusPanel | `src/widgets/bible_panel.py` | BIBLE管理UIパネル。検出状態・セクション一覧・完全性スコア表示 |
| BibleNotificationWidget | `src/widgets/bible_notification.py` | BIBLE検出時の通知バー。プロジェクト名・バージョン表示 |

---

## 6. デザインシステム — Cyberpunk Minimal（v8.0.0統一）

### 6.1 スタイル中央集権化

**ファイル**: `src/utils/styles.py`

v8.0.0で全UIスタイルを `styles.py` に集約。各タブ/ウィジェットからimportして使用する。

提供スタイル定数:

| 定数名 | 用途 |
|--------|------|
| `COLORS` | カラーパレットdict |
| `SECTION_CARD_STYLE` | QGroupBoxのセクションカード |
| `PRIMARY_BTN` | プライマリボタン（実行、送信、保存） |
| `SECONDARY_BTN` | セカンダリボタン（ファイル添付、履歴） |
| `DANGER_BTN` | デンジャーボタン（クリア、リセット） |
| `USER_MESSAGE_STYLE` | ユーザーメッセージバブル |
| `AI_MESSAGE_STYLE` | AI応答メッセージバブル |
| `INPUT_AREA_STYLE` | テキスト入力エリア |
| `OUTPUT_AREA_STYLE` | 出力テキストエリア |
| `TAB_BAR_STYLE` | タブバー |
| `SCROLLBAR_STYLE` | スクロールバー |
| `PROGRESS_BAR_STYLE` | プログレスバー |
| `COMBO_BOX_STYLE` | コンボボックス |
| `BIBLE_PANEL_STYLE` | BIBLE管理パネル |
| `BIBLE_HEADER_STYLE` | BIBLEヘッダーテキスト |
| `BIBLE_NOTIFICATION_STYLE` | BIBLE通知バー |
| `SPINBOX_STYLE` | **v8.1.0新規**: QSpinBox拡大スタイル（上下ボタン28px、シアン矢印） |
| `phase_node_style()` | Phaseノード動的スタイル関数 |
| `score_color()` / `score_bar_style()` | 完全性スコア表示用 |

### 6.2 カラーパレット

| 用途 | カラー | HEX |
|------|--------|-----|
| 背景（最暗） | ディープダーク | `#0a0a1a` |
| 背景（カード） | ダークブルーグレー | `#1a1a2e` |
| 背景（入力） | ダークグレー | `#1f2937` |
| ボーダー | ダークパープルグレー | `#2a2a3e` |
| ボーダー（ライト） | グレー | `#374151` |
| アクセント（プライマリ） | ネオンシアン | `#00d4ff` |
| アクセント（セカンダリ） | ネオングリーン | `#00ff88` |
| アクセント（ターシャリ） | オレンジ | `#ff9800` |
| エラー | コーラルレッド | `#ff6666` |
| テキスト（プライマリ） | ライトグレー | `#e0e0e0` |
| テキスト（セカンダリ） | グレー | `#888` |
| テキスト（ミュート） | ダークグレー | `#555` |

### 6.3 メッセージバブルデザイン（v8.0.0新規）

- **ユーザーメッセージ**: 背景 `#1a2a3e`、左ボーダー 3px `#00d4ff`（シアン）、右マージン大
- **AI応答**: 背景 `#1a1a2e`、左ボーダー 3px `#00ff88`（グリーン）、左マージン大

### 6.4 PhaseIndicatorカラー

| Phase | カラー | 表示 |
|-------|--------|------|
| P1: Claude計画 | `#00d4ff`（シアン） | アクティブ時はノード枠が光る |
| P2: ローカルLLM | `#00ff88`（グリーン） | 完了時はチェックマーク表示 |
| P3: Claude統合 | `#ff9800`（オレンジ） | 未実行時はグレーアウト |

### 6.5 SPINBOX_STYLE（v8.1.0新規）

```css
QSpinBox {
    padding: 6px 12px; font-size: 14px;
    min-height: 32px; min-width: 100px;
    background: #1f2937; border: 1px solid #4b5563;
    border-radius: 6px; color: #e5e7eb;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 28px; border: none; background: #2a2a3e;
}
QSpinBox::up-arrow {
    border-bottom: 9px solid #00d4ff;  /* シアン上矢印 */
}
QSpinBox::down-arrow {
    border-top: 9px solid #00d4ff;     /* シアン下矢印 */
}
```

全タブのQSpinBox（タイムアウト、フォントサイズ、最大再実行回数）に統一適用。

---

## 7. ローカルLLMモデル一覧

### 7.1 常駐モデル（GPU 0: RTX 5070 Ti 16GB）

| モデル | 役割 | VRAM | 常時ロード |
|--------|------|------|-----------|
| ministral-3:8b | 制御AI（タスク分類・**記憶品質判定**） | 約6GB | Yes |
| qwen3-embedding:4b | Embedding生成（**メモリ検索含む**） | 約2.5GB | Yes |

### 7.2 カテゴリ別担当モデル（GPU 1: RTX PRO 6000 96GB）

Phase 2で順次実行される。1モデルずつロード→実行→アンロード。

| カテゴリ | デフォルトモデル | VRAM | 用途 |
|----------|-----------------|------|------|
| coding | devstral-2:123b | 75GB | コード生成・レビュー |
| research | command-a:111b | 67GB | 調査・情報収集・RAG |
| reasoning | gpt-oss:120b | 80GB | 推論・論理検証 |
| translation | translategemma:27b | 18GB | 翻訳 |
| vision | gemma3:27b | 18GB | 画像解析 |

### 7.3 モデル配置戦略

- **順次実行**: 120Bクラスモデルは1つで67-80GB消費するため、並列実行不可
- **GPU分離**: 常駐モデル（GPU 0）とオンデマンドモデル（GPU 1）を物理分離
- **VRAM効率**: SequentialExecutorが自動でロード/アンロードを管理

---

## 8. GPU環境要件

### 8.1 ハードウェア構成

| GPU | モデル | VRAM | 用途 |
|-----|--------|------|------|
| GPU 0 | NVIDIA RTX 5070 Ti | 16GB (16,376 MB) | 常駐モデル（制御AI + Embedding） |
| GPU 1 | NVIDIA RTX PRO 6000 | 96GB (97,814 MB) | Phase 2 オンデマンドモデル |
| **合計** | | **約114 GB** (114,190 MB) | |

### 8.2 VRAM使用量の目安

| 用途 | VRAM | GPU |
|------|------|-----|
| 常駐: ministral-3:8b | 約6GB | GPU 0 |
| 常駐: qwen3-embedding:4b | 約2.5GB | GPU 0 |
| Phase 2: 最大モデル (gpt-oss:120b) | 約80GB | GPU 1 |
| システム予約 | 約2GB/GPU | 両方 |

### 8.3 最低動作要件

- NVIDIA GPU（CUDA対応）: 最低8GB VRAM
- Ollama がインストール済みであること
- Claude Code CLI がインストール済みであること
- Python 3.12以上

---

## 9. ディレクトリ構造

```
Helix AI Studio/
├── HelixAIStudio.py              # エントリポイント
├── HelixAIStudio.spec            # PyInstaller設定
├── requirements.txt              # pip依存関係
├── BIBLE/                        # BIBLEドキュメント群
│   ├── BIBLE_Helix AI Studio_7.2.0.md
│   ├── BIBLE_Helix AI Studio_8.0.0.md
│   └── BIBLE_Helix AI Studio_8.1.0.md   # ★ 本ファイル
├── config/                       # 設定ファイル
│   ├── app_settings.json         # ★ v8.1.0: memoryセクション更新
│   └── general_settings.json     # ★ v8.1.0: MCP/モデル設定統合先
├── data/                         # ランタイムデータ
│   ├── sessions/                 # Phase実行結果
│   ├── phase2/                   # Phase 2中間出力
│   └── helix_memory.db           # ★ v8.1.0: 4層メモリSQLite DB
├── logs/                         # ログファイル
├── src/
│   ├── __init__.py
│   ├── main_window.py            # メインウィンドウ（3タブ構成）
│   ├── backends/
│   │   ├── base.py               # バックエンド基底クラス
│   │   ├── claude_backend.py     # Claude API バックエンド
│   │   ├── claude_cli_backend.py # Claude CLI バックエンド
│   │   ├── cloud_adapter.py      # クラウドアダプター
│   │   ├── gemini_backend.py     # Gemini バックエンド
│   │   ├── local_backend.py      # ローカルLLM バックエンド
│   │   ├── local_connector.py    # Ollama接続
│   │   ├── local_llm_manager.py  # ローカルLLM管理
│   │   ├── mix_orchestrator.py   # 3Phaseオーケストレーター ★ v8.1.0: 記憶注入+Risk Gate統合
│   │   ├── model_repository.py   # モデルリポジトリ
│   │   ├── registry.py           # バックエンドレジストリ
│   │   ├── sequential_executor.py # Phase 2順次実行エンジン
│   │   ├── thermal_monitor.py    # GPU温度モニター
│   │   ├── thermal_policy.py     # サーマルポリシー
│   │   └── tool_orchestrator.py  # ツールオーケストレーター
│   ├── bible/                    # v8.0.0: BIBLE Manager モジュール群
│   │   ├── __init__.py           # Public API exports
│   │   ├── bible_schema.py       # スキーマ定義（16セクション型、データクラス）
│   │   ├── bible_parser.py       # BIBLEファイルパーサー
│   │   ├── bible_discovery.py    # 自動検出エンジン（3段階探索）
│   │   ├── bible_injector.py     # Phase 1/3コンテキスト注入
│   │   └── bible_lifecycle.py    # 自律管理エンジン（判定+実行）
│   ├── claude/
│   │   ├── diff_viewer.py        # Diff表示
│   │   ├── prompt_preprocessor.py # プロンプト前処理
│   │   └── snippet_manager.py    # スニペット管理
│   ├── data/
│   │   ├── chat_history_manager.py # チャット履歴
│   │   ├── history_manager.py    # 履歴管理
│   │   ├── project_manager.py    # プロジェクト管理
│   │   ├── session_manager.py    # セッション管理
│   │   ├── workflow_logger.py    # ワークフローログ
│   │   ├── workflow_state.py     # ワークフロー状態機械
│   │   └── workflow_templates.py # ワークフローテンプレート
│   ├── helix_core/
│   │   ├── auto_collector.py     # 自動データ収集
│   │   ├── feedback_collector.py # フィードバック収集
│   │   ├── graph_rag.py          # Graph RAG
│   │   ├── hybrid_search_engine.py # ハイブリッド検索
│   │   ├── light_rag.py          # Light RAG
│   │   ├── memory_store.py       # 記憶ストア
│   │   ├── mother_ai.py          # Mother AI
│   │   ├── perception.py         # 知覚モジュール
│   │   ├── rag_pipeline.py       # RAGパイプライン
│   │   ├── vector_store.py       # ベクトルストア
│   │   └── web_search_engine.py  # Web検索
│   ├── knowledge/
│   │   ├── knowledge_manager.py  # ナレッジDB管理
│   │   └── knowledge_worker.py   # ナレッジワーカー
│   ├── mcp/
│   │   ├── mcp_executor.py       # MCP実行
│   │   └── ollama_tools.py       # Ollamaツール
│   ├── mcp_client/
│   │   ├── helix_mcp_client.py   # MCPクライアント
│   │   └── server_manager.py     # MCPサーバー管理
│   ├── memory/                   # ★ v8.1.0: 4層メモリシステム
│   │   ├── __init__.py           # HelixMemoryManager, MemoryRiskGate exports
│   │   └── memory_manager.py     # 4層メモリ統合マネージャー + Memory Risk Gate
│   ├── metrics/
│   │   ├── budget_breaker.py     # 予算管理
│   │   └── usage_metrics.py      # 使用量メトリクス
│   ├── prompts/
│   │   └── prompt_packs.py       # プロンプトパック
│   ├── routing/
│   │   ├── classifier.py         # タスク分類器
│   │   ├── decision_logger.py    # 決定ログ
│   │   ├── execution.py          # 実行
│   │   ├── fallback.py           # フォールバック
│   │   ├── hybrid_router.py      # ハイブリッドルーター
│   │   ├── model_presets.py      # モデルプリセット
│   │   ├── policy_checker.py     # ポリシーチェッカー
│   │   ├── router.py             # ルーター
│   │   ├── routing_executor.py   # ルーティング実行
│   │   └── task_types.py         # タスク種別
│   ├── security/
│   │   ├── approvals_store.py    # 承認ストア
│   │   ├── mcp_policy.py         # MCPポリシー
│   │   ├── project_approval_profiles.py # プロジェクト承認プロファイル
│   │   └── risk_gate.py          # リスクゲート
│   ├── tabs/
│   │   ├── claude_tab.py         # soloAIタブ ★ v8.1.0: 設定簡素化+記憶注入
│   │   ├── helix_orchestrator_tab.py # mixAIタブ ★ v8.1.0: MCP/RAG移設+記憶注入
│   │   └── settings_cortex_tab.py # 一般設定タブ ★ v8.1.0: 7セクション大幅拡充
│   ├── ui/
│   │   └── components/
│   │       ├── history_citation_widget.py # 履歴引用
│   │       └── workflow_bar.py    # ワークフローバー
│   ├── ui_designer/
│   │   ├── layout_analyzer.py    # レイアウト分析
│   │   ├── qss_generator.py      # QSS生成
│   │   └── ui_refiner.py         # UIリファイナー
│   ├── utils/
│   │   ├── constants.py          # 定数定義 ★ v8.1.0: APP_VERSION="8.1.0"
│   │   ├── diagnostics.py        # 診断ユーティリティ
│   │   ├── diff_risk.py          # Diffリスク分析
│   │   ├── markdown_renderer.py  # v8.0.0: Markdown→HTMLレンダラー
│   │   └── styles.py             # ★ v8.1.0: SPINBOX_STYLE追加
│   └── widgets/
│       ├── __init__.py           # v8.0.0: chat_widgets/bible exports追加
│       ├── chat_input.py         # チャット入力ウィジェット
│       ├── chat_widgets.py       # v8.0.0: チャット強化ウィジェット群
│       ├── neural_visualizer.py  # Neural Flow Visualizer
│       ├── vram_simulator.py     # VRAM Budget Simulator
│       ├── bible_panel.py        # v8.0.0: BIBLE管理UIパネル
│       └── bible_notification.py # v8.0.0: BIBLE検出通知バー
```

---

## 10. 技術スタック

| カテゴリ | 技術 | バージョン |
|----------|------|-----------|
| 言語 | Python | 3.12.7 |
| GUIフレームワーク | PyQt6 | 6.6+ |
| Webエンジン | PyQt6-WebEngine | 6.6+ |
| Claude連携 | Claude Code CLI | `claude -p` コマンド |
| ローカルLLM | Ollama API | HTTP (`localhost:11434`) |
| Gemini連携 | google-genai | 0.4+ |
| MCP | mcp | 1.0+ |
| Knowledge Graph | networkx + pyvis | 3.2+ |
| データ処理 | numpy, pandas | — |
| 非同期 | aiohttp, aiofiles | — |
| ブラウザ自動化 | playwright | 1.40+ |
| ビルド | PyInstaller | 6.17.0 |
| DB | SQLite3 | 組み込み |

---

## 11. 設定ファイル仕様

### 11.1 config/config.json（ランタイム設定）

| キー | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `claude_model_id` | string | `"claude-opus-4-6"` | 使用するClaudeモデルID |
| `claude_model` | string | — | 表示名（後方互換） |
| `auth_method` | string | `"cli"` | Claude認証方式 (cli/api) |
| `thinking_mode` | string | `"OFF"` | 思考モード (OFF/Standard/Deep) |
| `ollama_host` | string | `"http://localhost:11434"` | OllamaホストURL |
| `project_dir` | string | — | Claude CLIの作業ディレクトリ |
| `max_phase2_retries` | int | `2` | Phase 2再実行の最大回数 |
| `timeout` | int | `600` | Claude CLIタイムアウト（秒） |
| `rag_enabled` | bool | `true` | RAG機能の有効/無効 |
| `embedding_model` | string | `"qwen3-embedding:4b"` | Embeddingモデル |
| `resident_control_model` | string | `"ministral-3:8b"` | 常駐制御AIモデル |
| `coding_model` | string | `"devstral-2:123b"` | コーディング担当モデル |
| `research_model` | string | `"command-a:111b"` | リサーチ担当モデル |
| `reasoning_model` | string | `"gpt-oss:120b"` | 推論担当モデル |
| `translation_model` | string | `"translategemma:27b"` | 翻訳担当モデル |
| `vision_model` | string | `"gemma3:27b"` | 画像解析担当モデル |

### 11.2 config/app_settings.json（アプリ設定）

v8.1.0で `memory` セクションを更新:

```json
{
  "general": { "dark_mode": true, "font_size": 10, "auto_save": true, "auto_context": true },
  "claude": { "default_model": "claude-opus-4-5-20251101", "timeout_minutes": 30, "mcp_enabled": true, "diff_view_enabled": true, "auto_context_enabled": true },
  "gemini": { "default_model": "gemini-2.5-pro", "yolo_mode": false, "sandbox_mode": true },
  "memory": {
    "lightrag_enabled": true,
    "index_path": "data/lightrag_index",
    "max_entries": 10000,
    "auto_save": true,
    "risk_gate_enabled": true,
    "search_threshold": "medium"
  },
  "bible": {
    "auto_discover": true,
    "auto_manage": true,
    "project_root": ""
  },
  "app_manager": { "base_directory": "", "show_hidden": false }
}
```

| キー | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `bible.auto_discover` | bool | `true` | BIBLE自動検出の有効/無効 |
| `bible.auto_manage` | bool | `true` | BIBLE自律管理（自動更新）の有効/無効 |
| `bible.project_root` | string | `""` | BIBLE検出の起点ディレクトリ（空=project_dir） |
| `memory.lightrag_enabled` | bool | `true` | RAG機能の有効/無効 |
| `memory.auto_save` | bool | `true` | 記憶の自動保存の有効/無効（v8.1.0新規） |
| `memory.risk_gate_enabled` | bool | `true` | Memory Risk Gateの有効/無効（v8.1.0新規） |
| `memory.search_threshold` | string | `"medium"` | 記憶検索の類似度閾値（v8.1.0新規） |

### 11.3 config/general_settings.json（v8.1.0新規）

一般設定タブから保存される統合設定ファイル:

| キー | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `claude_model_id` | string | `"claude-opus-4-6"` | 選択中のClaudeモデルID |
| `mcp_filesystem` | bool | `true` | ファイルシステムMCPの有効/無効 |
| `mcp_git` | bool | `true` | Git MCPの有効/無効 |
| `mcp_brave_search` | bool | `true` | Brave検索MCPの有効/無効 |
| `font_size` | int | `10` | フォントサイズ |
| `timeout_minutes` | int | `30` | Claudeタイムアウト（分） |
| `auto_save` | bool | `true` | 自動保存 |
| `auto_context` | bool | `true` | 自動コンテキスト |

---

## 12. PyInstaller設定

**ファイル**: `HelixAIStudio.spec`

### 12.1 hiddenimports（主要）

```python
hiddenimports = [
    # PyQt6
    'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip',
    # Backends
    'src.backends.mix_orchestrator',
    'src.backends.sequential_executor',
    'src.backends.claude_cli_backend',
    'src.backends.claude_backend',
    'src.backends.local_backend',
    'src.backends.local_connector',
    'src.backends.local_llm_manager',
    'src.backends.tool_orchestrator',
    'src.backends.model_repository',
    # Tabs
    'src.tabs.helix_orchestrator_tab',
    'src.tabs.claude_tab',
    'src.tabs.settings_cortex_tab',
    # Widgets
    'src.widgets.neural_visualizer',
    'src.widgets.vram_simulator',
    'src.widgets.chat_input',
    'src.widgets.bible_panel',           # v8.0.0
    'src.widgets.bible_notification',    # v8.0.0
    'src.widgets.chat_widgets',          # v8.0.0
    # BIBLE Manager
    'src.bible',                         # v8.0.0
    'src.bible.bible_schema',            # v8.0.0
    'src.bible.bible_parser',            # v8.0.0
    'src.bible.bible_discovery',         # v8.0.0
    'src.bible.bible_injector',          # v8.0.0
    'src.bible.bible_lifecycle',         # v8.0.0
    # Memory System
    'src.memory',                        # v8.1.0
    'src.memory.memory_manager',         # v8.1.0
    # Utils
    'src.utils.constants',
    'src.utils.markdown_renderer',       # v8.0.0
    'src.utils.styles',                  # v8.0.0
    # Knowledge & RAG
    'src.knowledge.knowledge_manager',
    'src.knowledge.knowledge_worker',
    'src.helix_core.graph_rag',
    'src.helix_core.light_rag',
    'src.helix_core.rag_pipeline',
    # Routing
    'src.routing.classifier',
    'src.routing.router',
    'src.routing.hybrid_router',
    # External
    'networkx', 'numpy', 'pandas', 'aiohttp', 'aiofiles',
    'google.genai', 'mcp', 'cryptography', 'yaml', 'dotenv',
]
```

### 12.2 ビルドコマンド

```bash
pyinstaller HelixAIStudio.spec --noconfirm
```

### 12.3 v7.0.0で削除されたモジュール

以下はv7.0.0の3Phase移行で削除:
- `src.backends.parallel_pool` → `sequential_executor` に置き換え
- `src.backends.quality_verifier` → Phase 3に統合
- `src.backends.phase1_parser` → `mix_orchestrator` に統合
- `src.backends.phase1_prompt` → `mix_orchestrator` に統合
- `src.backends.phase4_prompt` → Phase 3に統合

---

## 13. MCP（Model Context Protocol）設定

### 13.1 mixAI側のツール

Claude CLI のネイティブツールとして利用:
- `Bash` — シェルコマンド実行
- `Read` / `Write` / `Edit` — ファイル操作
- `WebFetch` / `WebSearch` — Web情報取得

### 13.2 soloAI側のMCPサーバー

外部MCPサーバーとして接続:
- **ファイルシステム** — ファイル読み書き
- **Git** — Git操作
- **Brave検索** — Web検索（オプション）

定義: `src/utils/constants.py` の `MCPServers` クラス

### 13.3 MCP設定の管理（v8.1.0更新）

v8.1.0で各タブ個別のMCP設定を一般設定タブに統合:
- **一般設定タブ**: MCP有効/無効のマスター設定（`config/general_settings.json`）
- **soloAI**: `_get_mcp_settings()` が `general_settings.json` を参照
- **mixAI**: ツール設定セクションを削除、互換性用ダミーラベル残置

---

## 14. chain-of-thoughtフィルタリング

`src/backends/sequential_executor.py` の `filter_chain_of_thought()` 関数。

ローカルLLMが出力する内部推論テキスト（"We should..."、"Let me think..."等）を
自動除去し、最終回答のみを抽出する。

v6.3.0で導入、v7.0.0以降も維持。

---

## 15. 次期バージョンロードマップ

| バージョン | 構想 |
|-----------|------|
| v8.2.0 | ベンチマーク機能（Phase 1のみ vs 3Phase統合の品質比較） |
| v9.0.0 | プラグインアーキテクチャ（カスタムPhase 2ワーカー追加） |
| 将来 | Docker Compose対応（Ollama + Helix の統合デプロイ） |
| 将来 | Web UI対応（Gradio/Streamlit経由のリモートアクセス） |
| 将来 | マルチユーザー対応 |

---

## 付録A: v8.1.0 変更履歴

### 記憶アーキテクチャ刷新

| # | 変更 | 対象 |
|---|------|------|
| 1 | 4層メモリ統合マネージャー(HelixMemoryManager)新規実装 | src/memory/memory_manager.py |
| 2 | SQLite 4層スキーマ(episodes/semantic_nodes/semantic_edges/procedures)設計 | data/helix_memory.db |
| 3 | Memory Risk Gate実装（ministral-3:8b常駐活用） | src/memory/memory_manager.py |
| 4 | Temporal Knowledge Graph（valid_from/to）をgraph_rag.pyに拡張 | src/helix_core/graph_rag.py |
| 5 | Phase 1/3への記憶コンテキスト注入統合 | src/backends/mix_orchestrator.py |
| 6 | soloAIへの記憶コンテキスト自動注入 | src/tabs/claude_tab.py |
| 7 | Episodic Memory多段要約（RAPTOR風：session→weekly→version） | src/memory/memory_manager.py |
| 8 | 後処理にMemory Risk Gate組み込み（mixAI/soloAI共通） | mix_orchestrator.py, claude_tab.py |

### UI構造再編

| # | 変更 | 対象 |
|---|------|------|
| 9 | soloAI設定からAPIキー入力・接続テスト削除 | claude_tab.py |
| 10 | soloAI設定からMCPサーバー管理を一般設定に移設 | claude_tab.py → settings_cortex_tab.py |
| 11 | soloAI設定からClaudeモデル設定を一般設定に移設 | claude_tab.py → settings_cortex_tab.py |
| 12 | mixAI設定からツール設定(MCP)を一般設定に統合 | helix_orchestrator_tab.py → settings_cortex_tab.py |
| 13 | mixAI設定からRAG設定を一般設定に統合 | helix_orchestrator_tab.py → settings_cortex_tab.py |
| 14 | 一般設定に「記憶・知識管理」セクション新設 | settings_cortex_tab.py |
| 15 | 一般設定最上部に「Claudeモデル設定」配置 | settings_cortex_tab.py |
| 16 | 一般設定に「MCPサーバー管理」配置（全ON初期値） | settings_cortex_tab.py |

### UIポリッシュ

| # | 変更 | 対象 |
|---|------|------|
| 17 | 全QSpinBoxの上下ボタン拡大（SPINBOX_STYLE） | styles.py + 全タブ |
| 18 | mixAIチャット入力欄プレースホルダー簡素化 | helix_orchestrator_tab.py |
| 19 | soloAI「新規セッション」ボタンを1つに統合 | claude_tab.py |
| 20 | soloAI認証バーから「認証: CLI」表示削除 | claude_tab.py |
| 21 | 一般設定Claude CLI説明文削除 | settings_cortex_tab.py |

### UX強化

| # | 変更 | 対象 |
|---|------|------|
| 22 | 全UI要素にsetToolTip()追加（40件以上） | 全タブ・ウィジェット |
| 23 | 全3タブ「設定を保存」ボタン有効化 + 視覚フィードバック | 全タブ |

### 定数更新

| # | 変更 | 対象 |
|---|------|------|
| 24 | APP_VERSION→"8.1.0", APP_CODENAME→"Adaptive Memory" | constants.py |
| 25 | BIBLE v8.1.0生成（500行以上） | BIBLE/BIBLE_Helix AI Studio_8.1.0.md |

---

*この BIBLE は Claude Opus 4 により、v8.0.0 BIBLE、v8.1.0実装コード、
依頼文（修正/依頼文.txt）に基づいて生成されました。*
