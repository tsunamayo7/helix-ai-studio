# BIBLE v8.3.1 "Living Memory (Patch)" 検証レポート & v8.3.2 修正プラン

**検証日**: 2026-02-10
**検証対象**: BIBLE_Helix_AI_Studio_8_3_1.md（1299行）+ UIスクリーンショット2枚
**前回レポート**: v8.3.0 検証レポート（ChatGPT指摘6件 + 設計偏差3件）

---

## 第1部: ChatGPT指摘6件の修正状況

### ✅ 修正済み: 4件

| 指摘 | v8.3.1での対応 | 検証結果 |
|------|---------------|---------|
| **(2) O(n²)緩和** | MAX_LINK_FACTS=20、同一entity共有ペア、UNIQUE INDEX、INSERT OR IGNORE | ✅ BIBLE 85行・398行に明記。メソッド表にも反映 |
| **(3) 週次カレンダー対応** | カレンダー週（前週月曜〜日曜）区切り・最低3セッション | ✅ BIBLE 84行・393行に明記。period_start/endがカレンダー基準に |
| **(4) memory_context注入安全性** | 全3箇所のbuild_contextに安全性ガードテキスト追加 | ✅ 設計哲学10番目に新設。BIBLE 382-385行にガード文面も記載 |
| **(6) default_model不整合** | app_settings.jsonを`claude-opus-4-6`に修正 + 起動時自動修正ロジック | ✅ BIBLE 1030行で確認。1049行に修正経緯も記載 |

### ✅ 新規追加: 3件（設計偏差修正）

| 偏差 | v8.3.1での対応 | 検証結果 |
|------|---------------|---------|
| **version要約未実装** | raptor_summarize_version(version) 新規実装 | ✅ BIBLE 395行にメソッド記載。episode_summaries(level='version')で保存 |
| **リトライなし** | _call_resident_llm にretries=2 + statusカラム + retry_pending_summaries() | ✅ BIBLE 388行・396行に記載。episode_summariesにstatusカラム追加 |
| **非同期化** | soloAI→RaptorWorker(QThread)、mixAI→threading.Thread(daemon) | ✅ BIBLE 80行に修正H記載。464-465行にQThread実行記述 |

### ⚠️ 部分修正: 1件

| 指摘 | v8.3.1での対応 | 残課題 |
|------|---------------|-------|
| **(1) スキーマ記述の揺れ** | semantic_nodes/edgesのカラム名を統一 | **episode_summariesのダイアグラムが未修正（下記詳細）** |

### ❌ 未対応: 1件

| 指摘 | 状況 |
|------|------|
| **(5) _call_resident_llm タイムアウト + 未生成フラグ** | **リトライは追加されたが**、statusカラムの初期値や再試行ロジックの詳細記述が不十分（後述） |

---

## 第2部: BIBLE v8.3.1 残存不整合（3件）

### 不整合1【P0】: episode_summaries ダイアグラムが旧スキーマのまま

**Layer 2ダイアグラム（308-309行）**:
```
episode_summaries (id, session_id, summary_type, content, timestamp, status)
```

**SQLiteスキーマ表（356行）**:
```
episode_summaries | id, level, period_start, period_end, summary, summary_embedding, episode_ids, created_at, status
```

**問題**: ダイアグラムは**v8.2.0以前のカラム名**（session_id, summary_type, content, timestamp）を
使い続けている。v8.3.0で導入したlevel, period_start/end, summary_embedding, episode_idsに
更新されていない。statusだけはv8.3.1で追加されている。

**影響**: BIBLEを読んだ新AIアシスタントがepisode_summaries.session_idカラムを前提にコードを書き、
実DBにはsession_idが存在せずエラーとなる。

**修正**: ダイアグラムを以下に更新:
```
episode_summaries (id, level, period_start, period_end,
  summary, summary_embedding, episode_ids, created_at, status)
```

---

### 不整合2【P1】: semantic_nodes の source カラムが不明

**Layer 3ダイアグラム（322-323行）**:
```
semantic_nodes (id, entity, attribute, value, confidence, valid_from, valid_to, source)
```

**SQLiteスキーマ表（357行）**:
```
semantic_nodes | id, entity, attribute, value, confidence, valid_from, valid_to
```

**問題**: ダイアグラムには`source`カラムがあるが、スキーマ表にはない。
実DBにsourceカラムが存在するのか不明。

**修正**: 実DBを確認して統一。sourceが不要ならダイアグラムから削除。

---

### 不整合3【P2】: CREATE TABLE正規定義の欠如

v8.3.0の検証レポートで推奨した「CREATE TABLE文をBIBLEに正規定義として記載」が
v8.3.1でも実施されていない。カラム表とダイアグラムの2箇所記述は不整合の温床になるため、
**CREATE TABLE SQL文を唯一の正規定義（Source of Truth）として追加すべき**。

---

## 第3部: UIスクリーンショット検証

### 質問1: BIBLE Manager「新規作成」以外クリックできない

**スクリーンショット1の状況**:
- 「BIBLE未検出」ステータスが表示中
- 「新規作成」ボタンのみアクティブ（シアンボーダー）
- 「更新」「詳細」ボタンはグレーアウト

**検証結果: 正常動作（不具合ではない）**

BIBLEが未検出の状態では「更新」「詳細」ボタンは操作対象がないため、無効化されるのが正しい設計。
BibleDiscovery（3段階探索: カレント→子→親）がBIBLEファイルを発見すれば3ボタンとも有効化されるはず。

**ただし、以下のUX改善を推奨**:

| 改善点 | 現状 | 推奨 |
|--------|------|------|
| ボタン状態の視覚的区別 | グレーアウトだがボーダーは残る | `setEnabled(False)` + ツールチップ「BIBLEを検出または作成すると有効になります」 |
| 「ファイル添付またはパス指定で自動検索します」 | テキストのみ | プレースホルダーテキストを持つQLineEditにして、パス入力→自動検出を有効にする |
| 自動検出結果のフィードバック | 「BIBLE未検出」のみ | 探索済みパス一覧を表示（例: `./BIBLE/ → 未発見, ../BIBLE/ → 未発見`） |

**BIBLEへの追記推奨**: 6.6節「BIBLE UIウィジェット」に**ボタン状態遷移表**を追加:

```
BibleStatusPanel ボタン状態:
┌──────────┬──────────┬──────────┬──────────┐
│ 状態      │ 新規作成  │ 更新      │ 詳細     │
├──────────┼──────────┼──────────┼──────────┤
│ BIBLE未検出│ ✅ 有効  │ ❌ 無効  │ ❌ 無効  │
│ BIBLE検出済│ ❌ 無効  │ ✅ 有効  │ ✅ 有効  │
│ BIBLE読込中│ ❌ 無効  │ ❌ 無効  │ ❌ 無効  │
└──────────┴──────────┴──────────┴──────────┘
```

---

### 質問2: soloAI「新規セッション」ボタンが2つある

**スクリーンショット2の状況**:
- **上部右**: SoloAIStatusBar内の「新規セッション」ボタン
- **中段右**: ツールバーRow 2の「新規セッション」ボタン

**検証結果: 冗長。1つに統一すべき**

BIBLE記述の確認:
- 707行: `SoloAIStatusBar（v8.0.0）: 旧S0-S5ステージUIを置換。ステータスドット+テキスト+新規セッションボタン`
- 716行: `Row 2: MCP | 差分表示 | 自動コンテキスト | 許可 | 新規セッション`

**経緯の推定**: v8.0.0でSoloAIStatusBarに新規セッションボタンを追加した際、
v7.x以前のツールバーRow 2の新規セッションボタンを削除し忘れた。

**推奨修正**:

| 案 | 内容 | メリット |
|----|------|---------|
| **案A（推奨）** | **SoloAIStatusBar側を残し、Row 2側を削除** | ステータス表示の直下にあるため「今のセッションをリセット」が直感的 |
| 案B | Row 2側を残し、StatusBar側を削除 | ツールバーの機能が集約される |

案Aを推奨する理由: SoloAIStatusBarの「待機中」表示と「新規セッション」が同じ行にあることで、
「ステータスを見て→リセット判断→実行」の導線が1行で完結する。

**soloAIタブの機能一覧（スクリーンショットから確認）**:

| UIエリア | 要素 | 機能 |
|---------|------|------|
| SoloAIStatusBar | ● 待機中 | 現在の実行状態（待機中/実行中/完了/エラー） |
| SoloAIStatusBar | 新規セッション | セッションリセット（会話履歴クリア + 新session_id生成） |
| Row 1 | 認証: CLI (Max/Proプラン) | Claude認証方式の選択 |
| Row 1 | ✅ | 認証成功インジケーター |
| Row 1 | モデル: Claude Opus 4.6 (最高知能) | 使用するClaudeモデル |
| Row 1 | 思考: OFF | Extended Thinking（深い推論モード）の切替 |
| Row 2 | MCP | MCPサーバー有効/無効 |
| Row 2 | 差分表示 (Diff) | コード変更の差分ビュー |
| Row 2 | 自動コンテキスト | build_context_for_solo()による記憶注入の自動実行 |
| Row 2 | 🔴 許可 | ツール実行の自動承認（--allowlist設定） |
| Row 2 | 新規セッション | ← **★ 重複。削除推奨** |

---

### 質問3: soloAI「認証」プルダウンは不要では？

**スクリーンショット2の状況**:
- ドロップダウン表示: `CLI (Max/Proプラン)` / `API (従量課金)` / `Ollama (ローカル)`

**BIBLE記述との矛盾**:
- 721行: `~~API認証~~: v8.1.0で削除（CLI認証に統一）`

**検証結果: BIBLEと実装が乖離している**

BIBLE v8.1.0の設計哲学では「API認証をCLI認証に統一」と記載されているが、
実UIには3つの認証方式ドロップダウンが残存している。

**分析**: この3つの認証方式は機能的に異なるため、完全削除は不適切かもしれない:

| 認証方式 | 用途 | 実行バックエンド |
|---------|------|----------------|
| CLI (Max/Proプラン) | AnthropicサブスクリプションのCLI | `claude --model ... -p` |
| API (従量課金) | Anthropic API直接呼び出し | `anthropic.Client().messages.create()` |
| Ollama (ローカル) | ローカルLLMでの実行 | `http://localhost:11434/api/generate` |

**推奨対応（2段階）**:

**段階1（v8.3.2 BIBLE修正）**: BIBLEの「~~API認証~~: v8.1.0で削除」記述を修正。
実態に合わせて3認証方式が存在することを明記:

```
#### soloAI認証方式（v8.3.2修正）
| 方式 | 対象ユーザー | バックエンド |
|------|------------|------------|
| CLI (Max/Proプラン) | Anthropicサブスクリプション利用者 | Claude Code CLI |
| API (従量課金) | APIキー利用者 | Anthropic Python SDK |
| Ollama (ローカル) | ローカルLLM利用者 | Ollama REST API |
```

**段階2（v8.4.0検討）**: 認証方式の統合検討。
CLIとAPIは実質同じClaudeを使うため統一可能だが、Ollamaは別バックエンドのため残す必要がある。

```
統合案: CLI/API → 「Claude」に統合、認証詳細は一般設定タブで設定
        Ollama   → 「ローカルLLM」として独立維持
```

---

## 第4部: v8.3.2 修正プラン

### 優先度別修正一覧

| # | 優先度 | 種別 | 修正内容 | 対象 |
|---|--------|------|---------|------|
| 1 | P0 | スキーマ | episode_summariesダイアグラム（308-309行）を正しいカラム名に更新 | BIBLE |
| 2 | P1 | スキーマ | semantic_nodesダイアグラムのsourceカラム: 実DB確認→不要なら削除 | BIBLE + DB確認 |
| 3 | P1 | スキーマ | CREATE TABLE SQL文をBIBLEセクション3.7に正規定義として追加 | BIBLE |
| 4 | P1 | UI | soloAI Row 2の「新規セッション」ボタン削除（StatusBar側を残す） | claude_tab.py |
| 5 | P1 | BIBLE | soloAI認証方式の記述修正（「~~API認証~~削除」→3方式共存を明記） | BIBLE |
| 6 | P2 | UX | BIBLE Manager: ボタン状態遷移表をBIBLE 6.6節に追加 | BIBLE |
| 7 | P2 | UX | BIBLE Manager: disabled時ツールチップ「BIBLEを検出すると有効」追加 | bible_panel.py |
| 8 | P2 | BIBLE | soloAIタブの機能一覧をBIBLE 6.3節に追加（全ボタン・トグルの用途） | BIBLE |

### BIBLE v8.3.2 episode_summaries ダイアグラム修正案

```
┌─────────────────────────────────────────────────────┐
│  Layer 2: Episodic Memory（中期・SQLite永続化）         │
│  ・テーブル: episodes (id, session_id, role, content,   │
│    summary, embedding BLOB, timestamp)                │
│  ・テーブル: episode_summaries (id, level,              │
│    period_start, period_end, summary,                 │
│    summary_embedding, episode_ids, created_at, status)│
│  ・qwen3-embedding:4b による768次元ベクトル検索           │
│  ・★ RAPTOR多段要約（v8.3.0 / v8.3.1品質強化）         │
└──────────────────────────────────────────────────────┘
```

### CREATE TABLE正規定義（BIBLE追加用）

```sql
-- ★ Source of Truth: 以下がhelix_memory.dbの正規スキーマ定義
-- memory_manager.py の _init_db() はこれと完全一致すること

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' or 'assistant'
    content TEXT NOT NULL,
    summary TEXT,
    embedding BLOB,              -- qwen3-embedding:4b 768次元
    timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS episode_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,          -- 'session', 'weekly', 'version'
    period_start TEXT NOT NULL,   -- ISO8601
    period_end TEXT NOT NULL,     -- ISO8601
    summary TEXT NOT NULL,
    summary_embedding BLOB,      -- qwen3-embedding:4b 768次元
    episode_ids TEXT,             -- JSON配列
    created_at TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'completed'  -- v8.3.1: 'completed' or 'pending'
);

CREATE TABLE IF NOT EXISTS semantic_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    valid_from TEXT DEFAULT (datetime('now')),
    valid_to TEXT                 -- NULLなら有効
);

CREATE TABLE IF NOT EXISTS semantic_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    relation TEXT NOT NULL,      -- 'co_occurrence', 'causes', etc.
    weight REAL DEFAULT 1.0,
    valid_from TEXT DEFAULT (datetime('now')),
    valid_to TEXT,
    FOREIGN KEY (source_node_id) REFERENCES semantic_nodes(id),
    FOREIGN KEY (target_node_id) REFERENCES semantic_nodes(id)
);
-- ★ v8.3.1: 重複防止インデックス
CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_unique
    ON semantic_edges(source_node_id, target_node_id, relation);

CREATE TABLE IF NOT EXISTS procedures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    steps TEXT,                   -- JSON配列
    tags TEXT,
    embedding BLOB,              -- qwen3-embedding:4b 768次元
    usage_count INTEGER DEFAULT 0,
    last_used TEXT,
    created TEXT DEFAULT (datetime('now'))
);
```

---

## 第5部: 総合評価

### v8.3.0 → v8.3.1 の修正達成率

| ChatGPT指摘6件 | 完全修正 4件 + 部分修正 1件 + 未完了 1件 = **83%** |
|設計偏差3件 | 完全修正 3件 = **100%** |
| 新規発見 | スキーマ不整合2件 + UI問題2件 + BIBLE記述乖離1件 |

### アーキテクチャ評価

v8.3.1はv8.3.0の実装品質を大幅に向上させた良いパッチリリース:

- **O(n²)緩和**: MAX_LINK_FACTS=20 + entity絞り込み + UNIQUE INDEXの3段構えは堅実
- **カレンダー週**: period_start/endがカレンダー基準になり時系列分析が可能に
- **注入安全性**: ガードテキストの全箇所適用は正しいアプローチ
- **QThread非同期化**: UIブロック防止の実装が完了

### 残タスクの規模感

| タスク | 工数 | 備考 |
|-------|------|------|
| ダイアグラム修正（BIBLE編集のみ） | 10分 | コード変更なし |
| CREATE TABLE追加（BIBLE編集のみ） | 15分 | 上記テンプレートをコピペ |
| soloAI重複ボタン削除 | 15分 | claude_tab.pyの1行コメントアウト |
| 認証方式記述修正 | 10分 | BIBLE 6.3節の取り消し線修正 |
| BIBLE Manager状態遷移表追加 | 10分 | BIBLE 6.6節に追記 |

**合計: 約1時間**（v8.3.2として軽微パッチ可能）

---

*この検証レポートは Claude Opus 4.6 により、BIBLE v8.3.1（1299行）+
UIスクリーンショット2枚の精読に基づいて作成されました。*
*2026-02-10*
