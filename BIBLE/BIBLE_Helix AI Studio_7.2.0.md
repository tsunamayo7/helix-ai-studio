# BIBLE — Helix AI Studio v7.2.0 "Polish"

**最終更新**: 2026-02-09
**バージョン**: 7.2.0 "Polish"
**前バージョン**: 7.1.0 "Adaptive Models"

> このドキュメントは Helix AI Studio の設計・構成・運用の全てを1ファイルで把握するための
> 「聖典（BIBLE）」です。新たなAIアシスタントやコントリビューターがプロジェクトに参加した際、
> このファイルを読むだけで全体像を理解できることを目指しています。

---

## 1. プロジェクト概要

### 1.1 名称・バージョン

| 項目 | 値 |
|------|-----|
| アプリケーション名 | Helix AI Studio |
| バージョン | 7.2.0 |
| コードネーム | "Polish" |
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

---

## 2. バージョン変遷サマリー

| バージョン | コードネーム | 主な変更 |
|-----------|------------|---------|
| v1.0.0 | — | 初期リリース。Claude API直接呼び出しの単一チャット |
| v3.7.0〜v3.9.6 | — | UIリファクタリング、タブ構成確立、Claude Codeタブ追加 |
| v4.0.0〜v4.6.0 | — | GPUモニター追加、ツールオーケストレーター、MCP対応 |
| v5.0.0〜v5.2.0 | — | ウィンドウサイズ永続化、Knowledge/RAG基盤 |
| v6.0.0 | — | **5Phase実行パイプライン導入**。Claude→ローカルLLM並列→品質検証→統合→保存 |
| v6.1.0 | — | Cyberpunk Minimalデザイン初期導入 |
| v6.2.0 | Crystal Cognition | Neural Flow Visualizer、VRAM Budget Simulator追加。Cyberpunk Minimal完成 |
| v6.3.0 | True Pipeline | 5Phase安定化、chain-of-thoughtフィルタリング、GPU動的検出 |
| v7.0.0 | Orchestrated Intelligence | **5Phase→3Phase移行**。SequentialExecutor導入、常駐モデル機構、--cwd対応 |
| v7.1.0 | Adaptive Models | Claude Opus 4.6対応、CLAUDE_MODELS動的選択、model_idパラメータ |
| **v7.2.0** | **Polish** | **UI整合性修正、旧バージョン番号除去、BIBLE統合版、GitHub公開準備** |

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
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  後処理: ナレッジ自動保存                                │
│  ・会話履歴をKnowledge DBに格納                          │
│  ・Embedding生成（qwen3-embedding:4b）                  │
└─────────────────────────────────────────────────────┘
```

### 3.2 常駐モデル機構

GPU 0（RTX 5070 Ti 16GB）に常時ロードされるモデル:

| モデル | 用途 | VRAM |
|--------|------|------|
| ministral-3:8b | 制御AI（タスク分類・ルーティング） | 約6GB |
| qwen3-embedding:4b | Embedding生成（RAG/Knowledge用） | 約2.5GB |

これらはPhase 2の順次実行とは独立して常時稼働し、
タスク分類やナレッジ保存時に即座に応答可能。

### 3.3 SequentialExecutor（Phase 2エンジン）

`src/backends/sequential_executor.py`

v7.0.0で `parallel_pool.py` を置き換え。
RTX PRO 6000（96GB）で120Bクラスモデルを1つずつ実行するための順次実行エンジン。

- **Ollama API**: `http://localhost:11434/api`
- **モデルロードタイムアウト**: 120秒
- **ロードチェック間隔**: 2秒
- **CoTフィルタリング**: v6.3.0から継承。モデルの内部推論テキストを除去

### 3.4 品質検証ループ

Phase 3でClaude が品質不足と判断した場合:
1. 再実行すべきカテゴリと指示を返却
2. Phase 2を該当カテゴリのみ再実行
3. 再度Phase 3を実行
4. 最大N回（設定: `max_phase2_retries`、デフォルト2）

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
7. 変更は全UI（mixAI/soloAI両方のドロップダウン）に自動反映

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
│  🔀 mixAI │  🤖 soloAI │  ⚙️ 一般設定 │
└───────────┴───────────┴──────────┘
```

### 5.2 mixAIタブ

**ファイル**: `src/tabs/helix_orchestrator_tab.py`

#### チャットサブタブ
- Neural Flow Visualizer（コンパクト版）: P1→P2→P3のリアルタイム進捗表示
- チャットログ: 3Phase実行の全ステップとツール実行結果を表示
- ステータスバー: バージョン、ナレッジ保存状態

#### 設定サブタブ
- **Claude設定**: モデル選択（CLAUDE_MODELSから動的生成）、認証方式、思考モード
- **Ollama接続**: ホストURL、接続テスト、モデル一覧取得
- **常駐モデル**: 制御AI + Embedding の割り当て確認
- **3Phase実行設定**: カテゴリ別担当モデル選択（5カテゴリ）
- **品質検証設定（ローカルLLM再実行）**: 最大再実行回数
- **ツール設定（MCP）**: Bash / Read・Write・Edit / WebFetch・WebSearch
- **VRAM Budget Simulator**: GPU別VRAM配置シミュレーション
- **GPUモニター**: リアルタイムGPU使用率グラフ（時間軸選択・シークバー対応）
- **RAG設定**: Knowledge/Encyclopediaの有効化・検索設定

### 5.3 soloAIタブ

**ファイル**: `src/tabs/claude_tab.py`

#### チャットサブタブ
- S0-S5ステージワークフロー（WorkflowPhase準拠だがS0〜S7の8段階）
- 会話継続機能
- Diff表示（差分ビューア）
- 自動コンテキスト

#### 設定サブタブ
- API/CLI認証方式選択
- Ollamaホスト設定
- MCPサーバー管理（ファイルシステム / Git / Brave検索）
- Claudeモデル選択（CLAUDE_MODELSから動的生成）
- デフォルトモデル設定

#### soloAIワークフロー（S0-S7ステージ）

```
S0: 依頼受領 (Intake)
  → S1: コンテキスト読込 (Context Load)
    → S2: 計画 (Plan)
      → S3: 危険判定・承認 (Risk Gate)
        → S4: 実装 (Implement)
          → S5: テスト/検証 (Verify)
            → S6: 差分レビュー (Review)
              → S7: 確定・記録 (Release)
```

定義元: `src/utils/constants.py` の `WorkflowPhase` クラス

### 5.4 一般設定タブ

**ファイル**: `src/tabs/settings_cortex_tab.py`

- Claude CLI状態表示
- Knowledge（知識ベース）: 有効化・件数・統計
- Encyclopedia（百科事典）: 有効化・件数
- 表示・テーマ設定
- 自動化設定

---

## 6. ローカルLLMモデル一覧

### 6.1 常駐モデル（GPU 0: RTX 5070 Ti 16GB）

| モデル | 役割 | VRAM | 常時ロード |
|--------|------|------|-----------|
| ministral-3:8b | 制御AI（タスク分類） | 約6GB | ✅ |
| qwen3-embedding:4b | Embedding生成 | 約2.5GB | ✅ |

### 6.2 カテゴリ別担当モデル（GPU 1: RTX PRO 6000 96GB）

Phase 2で順次実行される。1モデルずつロード→実行→アンロード。

| カテゴリ | デフォルトモデル | VRAM | 用途 |
|----------|-----------------|------|------|
| coding | devstral-2:123b | 75GB | コード生成・レビュー |
| research | command-a:111b | 67GB | 調査・情報収集・RAG |
| reasoning | gpt-oss:120b | 80GB | 推論・論理検証 |
| translation | translategemma:27b | 18GB | 翻訳 |
| vision | gemma3:27b | 18GB | 画像解析 |

### 6.3 モデル配置戦略

- **順次実行**: 120Bクラスモデルは1つで67-80GB消費するため、並列実行不可
- **GPU分離**: 常駐モデル（GPU 0）とオンデマンドモデル（GPU 1）を物理分離
- **VRAM効率**: SequentialExecutorが自動でロード/アンロードを管理

---

## 7. GPU環境要件

### 7.1 ハードウェア構成

| GPU | モデル | VRAM | 用途 |
|-----|--------|------|------|
| GPU 0 | NVIDIA RTX 5070 Ti | 16GB (16,376 MB) | 常駐モデル（制御AI + Embedding） |
| GPU 1 | NVIDIA RTX PRO 6000 | 96GB (97,814 MB) | Phase 2 オンデマンドモデル |
| **合計** | | **約114 GB** (114,190 MB) | |

### 7.2 VRAM使用量の目安

| 用途 | VRAM | GPU |
|------|------|-----|
| 常駐: ministral-3:8b | 約6GB | GPU 0 |
| 常駐: qwen3-embedding:4b | 約2.5GB | GPU 0 |
| Phase 2: 最大モデル (gpt-oss:120b) | 約80GB | GPU 1 |
| システム予約 | 約2GB/GPU | 両方 |

### 7.3 最低動作要件

- NVIDIA GPU（CUDA対応）: 最低8GB VRAM
- Ollama がインストール済みであること
- Claude Code CLI がインストール済みであること
- Python 3.12以上

---

## 8. デザインシステム — Cyberpunk Minimal

### 8.1 カラーパレット

| 用途 | カラー | HEX |
|------|--------|-----|
| 背景（メイン） | ダークグレー | `#1a1a1a` |
| 背景（サブ） | ダークグレー | `#252525` |
| テキスト（メイン） | ライトグレー | `#e5e7eb` |
| テキスト（サブ） | グレー | `#9ca3af` |
| アクセント（プライマリ） | ネオンシアン | `#00d4ff` |
| アクセント（セカンダリ） | ネオングリーン | `#00ff88` |
| エラー | レッド | `#ef4444` |
| 警告 | アンバー | `#f59e0b` |
| ボーダー | ダークグレー | `#374151` |

### 8.2 フォント

- **本文**: システム等幅フォント
- **コード**: monospace
- **見出し**: bold、アクセントカラー使用

### 8.3 コンポーネントスタイル

- **グループボックス**: `border: 1px solid #374151`, `border-radius: 8px`
- **ボタン**: `background: #374151` → ホバー `#4b5563`
- **入力フィールド**: `background: #1f2937`, `border: 1px solid #4b5563`
- **Neural Flowノード**: 円形、実行中は脈打つアニメーション、完了で緑色

---

## 9. ディレクトリ構造

```
Helix AI Studio/
├── HelixAIStudio.py              # エントリポイント
├── HelixAIStudio.spec            # PyInstaller設定
├── requirements.txt              # pip依存関係
├── BIBLE/                        # BIBLEドキュメント群
│   └── BIBLE_Helix AI Studio_7.2.0.md
├── config/                       # 設定ファイル（.gitignore対象）
│   └── config.json
├── data/                         # ランタイムデータ
│   ├── sessions/                 # Phase実行結果
│   └── phase2/                   # Phase 2中間出力
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
│   │   ├── mix_orchestrator.py   # 3Phaseオーケストレーター
│   │   ├── model_repository.py   # モデルリポジトリ
│   │   ├── registry.py           # バックエンドレジストリ
│   │   ├── sequential_executor.py # Phase 2順次実行エンジン
│   │   ├── thermal_monitor.py    # GPU温度モニター
│   │   ├── thermal_policy.py     # サーマルポリシー
│   │   └── tool_orchestrator.py  # ツールオーケストレーター
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
│   │   ├── claude_tab.py         # soloAIタブ
│   │   ├── helix_orchestrator_tab.py # mixAIタブ
│   │   ├── routing_log_widget.py # ルーティングログ
│   │   ├── screenshot_capturer.py # スクリーンショット
│   │   └── settings_cortex_tab.py # 一般設定タブ
│   ├── ui/
│   │   └── components/
│   │       ├── history_citation_widget.py # 履歴引用
│   │       └── workflow_bar.py    # ワークフローバー
│   ├── ui_designer/
│   │   ├── layout_analyzer.py    # レイアウト分析
│   │   ├── qss_generator.py      # QSS生成
│   │   └── ui_refiner.py         # UIリファイナー
│   ├── utils/
│   │   ├── constants.py          # 定数定義
│   │   ├── diagnostics.py        # 診断ユーティリティ
│   │   └── diff_risk.py          # Diffリスク分析
│   └── widgets/
│       ├── chat_input.py         # チャット入力ウィジェット
│       ├── neural_visualizer.py  # Neural Flow Visualizer
│       └── vram_simulator.py     # VRAM Budget Simulator
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

`config/config.json` の主要キー:

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
    # Utils
    'src.utils.constants',
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
| v7.3.0 | ベンチマーク機能（Phase 1のみ vs 3Phase統合の品質比較） |
| v8.0.0 | プラグインアーキテクチャ（カスタムPhase 2ワーカー追加） |
| v8.0.0 | Docker Compose対応（Ollama + Helix の統合デプロイ） |
| 将来 | Web UI対応（Gradio/Streamlit経由のリモートアクセス） |
| 将来 | マルチユーザー対応 |

---

## 付録A: v7.2.0 変更履歴

### 修正内容

| # | 修正 | 対象ファイル |
|---|------|------------|
| 1 | APP_VERSION → "7.2.0", APP_CODENAME → "Polish" | `constants.py` |
| 2 | VRAM Budget Simulator見出しから "(v6.2.0)" を除去 | `helix_orchestrator_tab.py` |
| 3 | GPUモニター見出しから "(v4.6: 時間軸選択・シークバー対応)" を除去 | `helix_orchestrator_tab.py` |
| 4 | mixAIツールチップを5Phase→3Phaseに修正 | `main_window.py` |
| 5 | "Phase 3 再実行設定" → "品質検証設定（ローカルLLM再実行）" | `helix_orchestrator_tab.py` |
| 6 | widgets/__init__.py の "5Phase" → "3Phase" 修正 | `widgets/__init__.py` |
| 7 | スタイルシートコメントから "v6.2.0" を除去 | `main_window.py` |
| 8 | BIBLE v7.2.0 統合版を生成（本ドキュメント） | `BIBLE/` |
| 9 | GitHub公開準備ファイル生成 (README.md, .gitignore等) | ルート |

### 未変更（実装済み確認済み）

- CLAUDE_MODELS定数（`constants.py:45`） — v7.1.0で実装済み
- model_idパラメータ（`mix_orchestrator.py:524`） — v7.1.0で実装済み
- Neural Visualizer 3ノード（`neural_visualizer.py:636`） — v7.0.0で実装済み

---

*この BIBLE は Claude Opus 4.6 により、過去の全BIBLE（v1.0.0〜v7.1.0）、ソースコード、
UIスクリーンショット、検証レポートに基づいて生成されました。*
