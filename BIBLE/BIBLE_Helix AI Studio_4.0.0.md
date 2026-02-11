# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.0.0
**アプリケーションバージョン**: 4.0.0 "Helix AI Studio - Claude中心型Tool Orchestrator, mixAI v4.0完全刷新"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.0.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.0.0 は以下の大規模アップデートを実装:

1. **Claude中心型Tool Orchestratorアーキテクチャ**の導入
2. **mixAI v4.0**の完全刷新（新UI/UX設計）
3. **3本柱構成**の実装（万能エージェント / コード特化 / 画像解析）
4. **不要コードの削除・軽量化**

### 設計思想の変更

**旧アーキテクチャ (v3.x: 7役割システム)**:
```
ユーザー → Supervisor → Router → Planner → Researcher → Executor → Reviewer → Summarizer
         (各役割に個別LLMを割り当て)
```

**新アーキテクチャ (v4.0: Claude中心型)**:
```
ユーザー ↔ Claude 4.5 (CLI/API)
              ├→ 万能エージェント (Nemotron-3-Nano 30B等) ← ツール実行・RAG管理
              ├→ コード特化 (Qwen3-Coder 30B等) ← コード検証・Web検索
              └→ 画像解析/軽量ツール (Gemma3 12B等) ← 画像理解・軽量タスク
```

**核心原則**: Claudeがユーザーの指示を受けて思考し、回答を生成する過程で、必要に応じてローカルLLMをツールとして呼び出す。ローカルLLMは「対話相手」ではなく「専門ツール」として機能する。

---

## 修正・追加内容詳細

| # | 要件 | 対策 |
|---|------|------|
| A | Claude中心型アーキテクチャ | `src/backends/tool_orchestrator.py` を新規作成。ToolOrchestrator クラスでClaude↔Ollama ブリッジを実装 |
| B | mixAI v4.0 UI刷新 | `src/tabs/helix_orchestrator_tab.py` を完全書き換え。折りたたみ可能なツール実行ログ、GPUモニター、RAG設定パネルを追加 |
| C | 3本柱モデル構成 | 万能Agent (Nemotron-3-Nano)、コード特化 (Qwen3-Coder)、画像解析 (Gemma3) の設定UIを実装 |
| D | 不要コード削除 | trinity_ai_tab.py, trinity_dashboard_tab.py, gemini_designer_tab.py, knowledge_dashboard_tab.py, encyclopedia_tab.py, cortex_audit_tab.py を削除 |
| E | バージョン更新 | constants.py: 3.9.6 → 4.0.0 |

---

## 新規ファイル一覧 (v4.0.0)

| ファイル | 説明 |
|----------|------|
| `src/backends/tool_orchestrator.py` | Claude中心型ツールオーケストレーター。ToolOrchestrator, ToolType, ToolResult, OrchestratorConfig クラスを定義 |

---

## 削除ファイル一覧 (v4.0.0)

| ファイル | 理由 |
|----------|------|
| `src/tabs/trinity_ai_tab.py` | 旧Trinity AIシステム、使用されていない |
| `src/tabs/trinity_dashboard_tab.py` | 旧Trinity AIダッシュボード、使用されていない |
| `src/tabs/gemini_designer_tab.py` | Gemini Designer機能、v3.9.0で削除済みだがファイル残存 |
| `src/tabs/knowledge_dashboard_tab.py` | Knowledge機能、使用されていない |
| `src/tabs/encyclopedia_tab.py` | Encyclopedia機能、使用されていない |
| `src/tabs/cortex_audit_tab.py` | Cortex監査機能、使用されていない |

---

## タブ構成 (v4.0.0)

### タブ構成 (4タブ)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.0** | チャット / 設定 | **Claude中心型マルチLLMオーケストレーション** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## mixAI v4.0 詳細設計

### ToolOrchestrator クラス

```python
class ToolOrchestrator:
    """
    Claude中心型ツールオーケストレーター

    主要メソッド:
    - initialize(): Ollamaクライアント初期化
    - get_available_models(): 利用可能モデル一覧取得
    - execute_tool(): ツール実行
    - get_execution_log(): 実行ログ取得
    """
```

### ToolType (ツールタイプ定義)

| タイプ | 説明 | 推奨モデル |
|--------|------|-----------|
| UNIVERSAL_AGENT | 万能エージェント | Nemotron-3-Nano 30B |
| CODE_SPECIALIST | コード特化 | Qwen3-Coder 30B |
| IMAGE_ANALYZER | 画像解析 | Gemma3 12B/27B |
| RAG_MANAGER | RAG管理 | Nemotron-3-Nano 30B |
| WEB_SEARCH | Web検索 | Qwen3-Coder 30B + Ollama web_search |
| LIGHT_TOOL | 軽量ツール | Gemma3 4B/12B |

### OrchestratorConfig (設定クラス)

```python
@dataclass
class OrchestratorConfig:
    # Ollama接続
    ollama_url: str = "http://localhost:11434"

    # 常時ロードモデル
    universal_agent_model: str = "nemotron-3-nano:30b"
    image_analyzer_model: str = "gemma3:12b"
    embedding_model: str = "bge-m3:latest"

    # オンデマンドモデル
    code_specialist_model: str = "qwen3-coder:30b"
    large_inference_model: str = "gpt-oss:120b"

    # Claude設定
    claude_model: str = "claude-opus-4-5"
    claude_auth_mode: str = "cli"
    thinking_mode: str = "Standard"

    # RAG設定
    rag_enabled: bool = True
    rag_auto_save: bool = True
```

---

## mixAI v4.0 UI設計

### チャットパネル

```
┌─────────────────────────────────────────┐
│ 🚀 mixAI v4.0 - Claude中心型オーケストレーション │
├─────────────────────────────────────────┤
│ [入力エリア]                             │
│ ▶️ 実行  ⏹️ キャンセル        🗑️ クリア  │
├─────────────────────────────────────────┤
│ ▶ ツール実行ログ (クリックで展開)         │
│ ┌─────────────────────────────────────┐│
│ │ ツール    │ステータス│実行時間│出力    ││
│ │ タスク分析 │ ✅      │ 1.2s  │ ...   ││
│ │ コード処理 │ ✅      │ 2.3s  │ ...   ││
│ └─────────────────────────────────────┘│
├─────────────────────────────────────────┤
│ [出力エリア - Markdown対応]              │
└─────────────────────────────────────────┘
```

### 設定パネル

```
┌─────────────────────────────────────────┐
│ 📌 Claude設定                           │
│  モデル: [Opus 4.5 ▼]                   │
│  認証:  [CLI ▼]                         │
│  思考:  [Standard ▼]                    │
├─────────────────────────────────────────┤
│ 🖥️ Ollama接続                           │
│  ホストURL: [http://localhost:11434]    │
│  [接続テスト]                           │
│  ステータス: ✅ 接続成功 (0.12秒, 5モデル) │
├─────────────────────────────────────────┤
│ 🔧 常時ロードモデル                      │
│  万能Agent: [nemotron-3-nano:30b ▼]     │
│  画像/軽量: [gemma3:12b ▼]              │
│  Embedding: [bge-m3:latest ▼]           │
├─────────────────────────────────────────┤
│ ⚡ オンデマンドモデル                     │
│  コード特化: [qwen3-coder:30b ▼]        │
│  大規模推論: [gpt-oss:120b ▼]           │
├─────────────────────────────────────────┤
│ 📊 GPUモニター                          │
│  GPU 0: NVIDIA RTX PRO 6000             │
│    VRAM: 26000/96000 MB (27.1%)         │
├─────────────────────────────────────────┤
│ 💾 RAG設定                              │
│  ☑ RAGを有効化                          │
│  ☑ 会話を自動保存                        │
│  保存閾値: [中優先度以上 ▼]              │
├─────────────────────────────────────────┤
│ [💾 設定を保存]                          │
└─────────────────────────────────────────┘
```

---

## 推奨モデル構成 (mixAI_Redesign_Proposal_v2準拠)

### 常時ロード構成

| モデル | VRAM | 役割 |
|--------|------|------|
| Nemotron-3-Nano 30B | 24GB | 万能エージェント/RAG管理 |
| Gemma3 12B | 8.1GB | 画像解析/軽量ツール |
| BGE-M3 Embedding | 2GB | RAGベクトル生成 |
| **合計** | **~34GB** | |

### オンデマンド切替構成

| パターン | モデル | VRAM | トリガー |
|---------|--------|------|---------|
| コード集中 | Qwen3-Coder 30B | +19GB | コード検証・リファクタリング |
| 超高精度コード | Devstral 2 123B | +75GB | SWE-Benchレベルのバグ修正 |
| 大規模推論 | GPT-OSS 120B | +65GB | 複雑な推論タスク |
| 高精度画像 | Gemma3 27B | +17GB | 詳細な画像解析 |

---

## ワークフロー例 (v4.0)

### 例1: コードバグ修正

```
1. ユーザー: 「このコードのバグを修正して」
2. mixAI: タスク分析 (Nemotron-3-Nano)
   → 「コードタスク」と判定
3. mixAI: コード処理 (Qwen3-Coder)
   → バグ検出・修正案生成
4. mixAI: 最終回答を統合・表示
5. ツール実行ログに処理詳細を記録
```

### 例2: 画像解析

```
1. ユーザー: 「このスクリーンショットの内容を分析して」
2. mixAI: タスク分析 (Nemotron-3-Nano)
   → 「画像タスク」と判定
3. mixAI: 画像解析 (Gemma3 12B)
   → テキスト抽出・レイアウト理解
4. mixAI: 最終回答を統合・表示
```

---

## 認証方式×モデル×機能の対応マトリクス (v4.0.0)

| 認証方式 | モデル | 思考モード | MCPツール | mixAI対応 | 備考 |
|----------|--------|------------|-----------|-----------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ | ✅ | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ | ✅ | 推奨 |
| CLI | Haiku 4.5 | OFF/Standard/Deep | ✅ | ✅ | 高速 |
| API | Opus 4.5 | OFF/Standard/Deep | ❌ | ✅ | MCPなし |
| API | Sonnet 4.5 | OFF/Standard/Deep | ❌ | ✅ | MCPなし |
| API | Haiku 4.5 | OFF/Standard/Deep | ❌ | ✅ | MCPなし |
| Ollama | (設定依存) | OFF固定 | ✅ | ✅ | ローカルLLM |

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | 81 MB |
| exe (root) | `HelixAIStudio.exe` | 81 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.0.0.md` | - |

---

## ファイル変更一覧 (v4.0.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/tool_orchestrator.py` | **新規作成** - Claude中心型ツールオーケストレーター |
| `src/tabs/helix_orchestrator_tab.py` | **完全書き換え** - mixAI v4.0 UI/ロジック |
| `src/tabs/__init__.py` | 不要インポートを削除、新構成に更新 |
| `src/main_window.py` | mixAIタブのツールチップを更新 |
| `src/utils/constants.py` | バージョン 3.9.6 → 4.0.0 |
| `HelixAIStudio.spec` | hidden_importsから削除ファイルを除外 |
| `BIBLE/BIBLE_Helix AI Studio_4.0.0.md` | 本ファイル追加 |

---

## v3.9.6からの継承課題

- [x] PyInstaller終了時エラー → v3.9.6で解決済み
- [x] API接続エラーメッセージ改善 → v3.9.6で解決済み
- [x] mixAIアーキテクチャ刷新 → **v4.0で解決**
- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.1以降)

1. **RAG本格統合**: FAISS + SQLiteによるベクトルストア、自動会話保存
2. **オンデマンドモデル切替**: 動的ロード/アンロード機能
3. **Web検索統合**: Ollama web_search/web_fetch機能の統合
4. **GPU使用率モニター**: リアルタイムVRAM使用量のプログレスバー表示

---

## 参考文献

- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Anthropic Claude Documentation
- Ollama API Documentation
- NVIDIA Nemotron-3-Nano Model Card
- Google Gemma3 Technical Report
- Alibaba Qwen3-Coder Benchmark Results
