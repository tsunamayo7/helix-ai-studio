# Helix AI Studio — v10.0.0 → v10.1.0 実装依頼書

**作業対象:** `C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio`
**推奨モデル:** Claude Opus 4.6
**バージョン:** `APP_VERSION = "10.1.0"` / `APP_CODENAME = "Unified Studio"`

---

# ════════════════════════════════════════
# SECTION 1 — 実装作業
# ════════════════════════════════════════

## 【共通ルール】

1. **i18n 連動（全項目必須）:** 新規・変更するすべての UI 文字列を `i18n/ja.json` と
   `i18n/en.json` へ同時登録し、`retranslateUi()` / React `t()` で参照すること。
   ハードコード禁止。**英語キーは必ず設定すること（英語 UI 完全対応）。**
2. **確認→報告→修正:** 変更前に実ファイルの該当行番号を示すこと。推測での完了報告は禁止。
3. **後方互換:** 既存の日本語 UI は変更しない。英語は切替時のみ適用。
4. **NoScrollComboBox ルール（全項目に適用）:**
   アプリ内に存在する **1行表示のプルダウン（QComboBox）をすべて** `NoScrollComboBox` /
   `_NoScrollComboBox` に置き換えること。対象はモデル選択・常駐モデル設定・
   Phase 設定・情報収集設定・一般設定内のすべての QComboBox を含む。
   既に `NoScrollComboBox` になっているものはスキップ。
   確認コマンド: `grep -rn "QComboBox()" src/ --include="*.py"`
5. **進捗管理:** 作業開始時に `PROGRESS_v10.1.0.md` を作業ディレクトリに生成し、
   各項目完了時に `✅` でマークしながら進行すること。
   トークン不足で停止した場合は未完了項目がそのまま残るため、
   次セッション冒頭で `PROGRESS_v10.1.0.md` を読み込み未完了項目から再開する。

---

## 項目 0. チャット実行ロジック全体確認と常駐モデル確認（作業前に必ず実施）

### 0-A. 各タブのチャット実行ロジック確認

以下の各ファイルについて、送信→実行→結果表示の一連のフローを精査し、
不整合・未接続シグナル・デッドロックリスクを報告してから修正すること。

| ファイル | 確認対象 |
|---------|---------|
| `src/tabs/claude_tab.py` | `_on_send()` → `CLIWorkerThread` → `_on_cli_response()` の接続 |
| `src/tabs/helix_orchestrator_tab.py` | `_on_execute()` → `MixOrchestratorThread` → `_on_finished()` の接続 |
| `src/tabs/helix_orchestrator_tab.py` | `_on_continue_conversation()` → `ContinueWorkerThread` → チャット表示 の接続 |
| `src/web/server.py` | WebSocket `solo` / `mix` ハンドラの完了通知フロー |

**大規模な不整合が発見された場合の手順:**
1. `PROGRESS_v10.1.0.md` に発見した問題を列挙する
2. 影響範囲の小さいものから順に修正し、都度 ✅ マークを付ける
3. 停止した場合は次セッションで `PROGRESS_v10.1.0.md` から再開する

### 0-B. 常駐モデルの動作確認

`ministral-3:8b`（制御 AI）と `qwen3-embedding:0.6b`（Embedding）が
以下の各タブで適切に機能しているか確認し、不具合があれば修正すること。

| 確認箇所 | 期待動作 |
|---------|---------|
| cloudAI（旧 soloAI）チャット | 送信前に Memory Risk Gate が機能し記憶を品質チェックする |
| mixAI Phase 2 | カテゴリ分類・ルーティングに `ministral-3:8b` が使用される |
| 情報収集タブ | RAG 構築時に `ministral-3:8b` が品質チェック・`qwen3-embedding:0.6b` が Embedding 生成 |
| 一般設定 → 常駐モデル設定 | 変更した設定が各タブに即時反映される |

常駐モデルが使用されているかは以下で確認:
```bash
grep -rn "ministral\|embedding.*model\|resident.*model\|control.*model" src/ --include="*.py"
```

---

## 項目 1. 実行中モニターウィジェット（cloudAI・mixAI 共通）

### 1-A. 新規ファイル: `src/widgets/execution_monitor_widget.py`

**クラス:** `ExecutionMonitorWidget(QWidget)`

各 LLM 行の表示構成:
```
[状態アイコン] [モデル名] [(フェーズラベル)]  [経過時間]  [最終出力 末尾 40 文字]
```

状態アイコンと閾値:

| アイコン | 状態 | 条件 |
|---------|------|------|
| 🟢 | アクティブ | 直近 3 秒以内に stdout 出力あり |
| 🟡 | 待機中 | プロセス生存・出力なし 3〜30 秒 |
| 🔴 | ストール疑い | 出力なし 30 秒超、またはプロセス消滅 |
| ⬜ | 未開始 / 完了 | — |

`QTimer(interval=1000)` で毎秒 `_refresh()` を呼び出して状態を再計算する。
ストール検出時: `stallDetected = pyqtSignal(str)` を emit（ステータスバー警告に接続）。

公開メソッド:
- `start_model(name: str, label: str, pid: int = None)`
- `update_output(name: str, text: str)`
- `finish_model(name: str, success: bool = True)`
- `reset()`

スタイル: 背景 `#0d0d1f`、最大高さ 120px、ストール行背景 `#3a1515`。
実行中のみ `setVisible(True)`、完了 3 秒後に `setVisible(False)`。

i18n キー（`ja.json` / `en.json` に追加）:
```
"widget.monitor.title":     ["実行中モニター",           "Execution Monitor"]
"widget.monitor.active":    ["アクティブ",               "Active"]
"widget.monitor.waiting":   ["待機中",                   "Waiting"]
"widget.monitor.stalled":   ["応答なし",                 "Not Responding"]
"widget.monitor.done":      ["完了",                     "Done"]
"widget.monitor.error":     ["エラー",                   "Error"]
"widget.monitor.stallWarn": ["{name} が {sec}秒間応答していません", "{name} has not responded for {sec}s"]
"widget.monitor.lastOutput":["最終出力",                 "Last Output"]
```

### 1-B. `src/backends/claude_cli_backend.py` の修正

`read_stdout()` 関数内: 既存の `_streaming_callback(line)` に加え
`self._monitor_callback(line)` を追加で呼び出す。
ポーリングループ（`elapsed += poll_interval` 付近）に 10 秒ごとのハートビートを追加:
```python
if self._monitor_callback and int(elapsed) % 10 == 0:
    self._monitor_callback("__heartbeat__")
```
`__init__` に `self._monitor_callback = None` を追加。
`set_monitor_callback(cb)` メソッドを追加。

### 1-C. `src/backends/local_agent.py` の修正

`_call_ollama_chat()` の前後に追加:
- 呼び出し直前: `if self.on_monitor_start: self.on_monitor_start(self.model_name)`
- 正常返却後:   `if self.on_monitor_finish: self.on_monitor_finish(self.model_name, True)`
- 例外時:       `if self.on_monitor_finish: self.on_monitor_finish(self.model_name, False)`
- Ollama ヘルスポーリング（5 秒間隔・別スレッド）: `GET /api/ps` で対象モデルが
  `running_models` に含まれる間はハートビートを送出する。

`ToolOrchestrator.__init__` に `self.on_monitor_start = None` / `self.on_monitor_finish = None` を追加。

### 1-D. `src/backends/mix_orchestrator.py` の修正

`MixOrchestratorThread` に新規シグナルを追加:
```python
monitor_event = pyqtSignal(str, str, str)
# (event_type, model_name, detail)
# event_type: "start" | "output" | "finish" | "error" | "heartbeat" | "stall"
```
各 Phase 実行メソッドの開始・完了時に `monitor_event.emit(...)` を追加。
Claude CLI バックエンドに `set_monitor_callback` で `monitor_event` を接続。

### 1-E. `src/tabs/helix_orchestrator_tab.py` の修正（mixAI）

- Phase インジケータの直下に `ExecutionMonitorWidget` を追加。
- `self._worker.monitor_event.connect(self._on_monitor_event)` を接続。
- `_on_monitor_event(event_type, model_name, detail)` を実装。
- `_on_new_session()` に `monitor_widget.reset()` を追加。

### 1-F. `src/tabs/claude_tab.py` の修正（cloudAI）

- `chat_display` と入力エリアの間に `ExecutionMonitorWidget` を追加。
- `CLIWorkerThread` 開始時に `monitor_widget.start_model(...)` を呼び出す。
- `_on_cli_response()` / `_on_cli_error()` 時に `monitor_widget.finish_model(...)` を呼び出す。
- `stallDetected` シグナルをステータスバーに接続。

---

## 項目 2. mixAI チャット表示 + 会話継続パネル

### 2-A. chat_display への置き換え

**`output_text`（最終結果のみ静的表示）を廃止し `chat_display` に置き換える。**

`chat_display` への表示ルール:

| タイミング | バブル内容 | 色 |
|-----------|-----------|-----|
| 実行ボタン押下時 | ユーザー発言（`USER_MESSAGE_STYLE` 流用） | — |
| Phase 1 完了時 | `📋 Phase 1 計画` | `#4fc3f7` |
| Phase 2 完了時 | `⚙️ Phase 2 実行結果`（カテゴリ別） | `#a78bfa` |
| Phase 3/4 完了時 | `✅ 最終統合回答`（`markdown_to_html` 適用） | `#00ff88` |
| エラー時 | エラーメッセージ | `#ef4444` |

シグナル連動:
- `_on_progress(message, percentage)` → Phase 名称を検出してバブル追加
- `_on_tool_executed(result)` → Phase 2 個別結果をバブル追加
- `_on_finished(result)` → 最終回答バブル追加（`output_text.setHtml` の代替）

レイアウト変更（`_create_chat_panel()` 内）:
```
├── chat_display（上部・60%）
├── Phase インジケータ
├── ExecutionMonitorWidget（項目1）
├── ツール実行ログ（折り畳み）
└── 入力エリア + ボタン行 + 会話継続パネル（下部・40%）
```

i18n キー追加:
```
"desktop.mixAI.phase1PlanBubbleTitle":   ["📋 Phase 1 計画",     "📋 Phase 1 Plan"]
"desktop.mixAI.phase2ResultBubbleTitle": ["⚙️ Phase 2 実行結果", "⚙️ Phase 2 Results"]
"desktop.mixAI.phase3FinalBubbleTitle":  ["✅ 最終統合回答",      "✅ Final Answer"]
```

### 2-B. 会話継続パネルの追加

`claude_tab.py` の `_create_continue_area()` を参考に移植する。

構成:
- ヘッダラベル、サブラベル（i18n）
- クイックボタン: 「Yes」「Continue」「Execute」（クリックで即実行）
- テキスト入力欄（QLineEdit）+ 送信ボタン

`_on_continue_with_message(message: str)` の実装:
1. `chat_display` にユーザー発言バブルを追加
2. `message` を Phase 1 への追加コンテキストとして渡し `_on_execute()` を呼び出す
3. 既存の `_on_continue_conversation()` を拡張して `message` 引数を受け取れるようにする

活性化制御: 実行中・完了後ともに有効（止まった際に「Yes」等を送れるようにするのが目的）。

i18n キー追加:
```
"desktop.mixAI.continueHeader":      ["💬 会話継続",                      "💬 Continue Conversation"]
"desktop.mixAI.continueSub":         ["停止中のプロセスに続きを送信",      "Send a message to continue a stopped process"]
"desktop.mixAI.continueYes":         ["Yes",                               "Yes"]
"desktop.mixAI.continueContinue":    ["Continue",                          "Continue"]
"desktop.mixAI.continueExecute":     ["Execute",                           "Execute"]
"desktop.mixAI.continueSend":        ["送信",                              "Send"]
"desktop.mixAI.continuePlaceholder": ['"はい"、"続けて"、"実行"など...',   '"Yes", "Continue", "Execute", etc...']
```

### 2-C. `--continue` 完了時に UI が固まる問題の修正

**確認手順（実施してから修正）:**
`claude_tab.py` の `ContinueWorkerThread.run()` と接続先シグナルを精査し、
`completed` シグナルが `_on_cli_response()` または同等のチャット表示メソッドに
接続されているかを行番号付きで報告すること。

修正要件:
- `ContinueWorkerThread` の `completed` シグナルが `chat_display.append()` 経由で
  チャットに表示されること
- 完了後にステータスバーを `"Ready"` / `t('mainWindow.ready')` に戻すこと
- 実行中フラグ（`execute_btn.setEnabled` 等）が正しくリセットされること

### 2-D. mixAI の `--dangerously-skip-permissions` 統一

確認手順: `mix_orchestrator.py` の `_execute_phase1/3/35()` および
`server.py` の `_run_claude_cli_async()` を精査し、
`--dangerously-skip-permissions` が渡されているかを行番号付きで報告すること。

修正要件:
- mixAI の全 Phase の Claude CLI 呼び出しに `--dangerously-skip-permissions` を統一付与
- `local_agent.py` の `require_write_confirmation` を mixAI 経由呼び出し時は
  `False` 固定にする（UI スレッドのないバックグラウンドでのデッドロック防止）

---

## 項目 3. タブ名変更: `soloAI` → `cloudAI`、新規 `localAI` タブ追加

### ⚠️ 影響範囲の注意

`"soloAI"` は DB スキーマ・WebSocket・i18n・Web UI・ChatStore の広範囲に存在する。
以下のコマンドで全箇所を列挙してから修正すること:
```bash
grep -rn "soloAI\|solo_ai\|\"solo\"" src/ frontend/ i18n/ config/ \
  --include="*.py" --include="*.jsx" --include="*.js" --include="*.json"
```

### 3-A. 変更箇所一覧

| 変更前 | 変更後 | 場所 |
|--------|--------|------|
| `"soloAI"` (DB/内部キー) | `"cloudAI"` | `chat_store.py` CHECK制約, `create_chat()`, `add_message()` |
| `/ws/solo` | `/ws/cloud` | `server.py` WebSocket endpoint |
| `endpoint = 'solo'` | `endpoint = 'cloud'` | `useWebSocket.js` |
| `t('desktop.mainWindow.soloAITab')` | `t('desktop.mainWindow.cloudAITab')` | `main_window.py` |
| `i18n` の `soloAI.*` キー群 | `cloudAI.*` に改名 | `ja.json`, `en.json` |
| `tab_widget.addTab(..., soloAI)` | `cloudAI` | `main_window.py` |
| `chat_store.create_chat(tab="soloAI")` | `"cloudAI"` | `claude_tab.py`, `server.py` |
| `toggle_chat_history(tab="soloAI")` | `"cloudAI"` | `main_window.py` |
| `badge_text = "soloAI"` | `"cloudAI"` | `chat_history_panel.py` |

**DB スキーマ移行（必須）:**
SQLite は ALTER TABLE で CHECK 制約を変更できないため、テーブル再作成が必要。
移行スクリプト `scripts/migrate_solo_to_cloud.py` を新規作成して実行すること:
```python
# 処理概要（スクリプト内に実装すること）
# 1. 既存 "soloAI" レコードを "cloudAI" に UPDATE
# 2. テーブルを再作成（CHECK 制約を変更）
# 3. データを新テーブルにコピー
# 4. バックアップを data/backup_before_migration/ に保存
```

### 3-B. タブ順と表示名

タブ順: `mixAI` → `cloudAI` → `localAI` → `情報収集` → `一般設定`

| タブ | i18n キー | 日本語 | English |
|------|-----------|--------|---------|
| mixAI | `desktop.mainWindow.mixAITab` | 🔀 mixAI | 🔀 mixAI |
| cloudAI（新） | `desktop.mainWindow.cloudAITab` | ☁️ cloudAI | ☁️ cloudAI |
| localAI（新規） | `desktop.mainWindow.localAITab` | 🖥️ localAI | 🖥️ localAI |
| 情報収集 | `desktop.mainWindow.infoTab` | 📚 情報収集 | 📚 Information |
| 一般設定 | `desktop.mainWindow.settingsTab` | ⚙️ 一般設定 | ⚙️ Settings |

### 3-C. cloudAI タブの設定タブへの追加

既存の `claude_tab.py` をベースに、**設定サブタブ**に以下を追加:

*① Claude CLI 連携セクション*（現 `一般設定` の `_create_cli_status_group()` を移設）
- Claude CLI バージョン表示・接続確認ボタン

*② Codex CLI 連携セクション*
- Codex CLI の接続確認ボタン・バージョン表示

*③ mixAI Phase 登録セクション*
- cloudAI で使用中のクラウドモデルを mixAI の各 Phase 選択肢に追加/削除できる UI
  （`ManageModelsDialog` と連動）

i18n キー追加:
```
"desktop.cloudAI.cliSection":        ["Claude CLI 連携",          "Claude CLI Integration"]
"desktop.cloudAI.codexSection":      ["Codex CLI 連携",           "Codex CLI Integration"]
"desktop.cloudAI.mixaiPhaseSection": ["mixAI Phase 登録",         "Register to mixAI Phases"]
```

### 3-D. 新規 localAI タブ: `src/tabs/local_ai_tab.py`

**localAI-チャットサブタブ:**
- `claude_tab.py` の `_create_chat_tab()` と同等の構成で実装
- バックエンド: 新規 `src/backends/ollama_direct_backend.py`
  - `OllamaDirectBackend` クラス: `POST /api/chat` でストリーミング実行
  - `OllamaWorkerThread(QThread)`: 非同期実行（`CLIWorkerThread` パターンを流用）
- モデル選択コンボ: `ollama.list()` でインストール済みモデルを動的取得・表示
  → `NoScrollComboBox` で実装（共通ルール 4 に準拠）
- 実行中モニター（項目 1）を接続
- 会話継続パネル（項目 2-B と同等）を追加

**localAI-設定サブタブ（3 セクション構成）:**

*① Ollama 管理セクション*
- 接続 URL 設定・接続テストボタン（現 `一般設定` の `Ollama接続設定` を移設）
- インストール確認ラベル（`shutil.which("ollama")` で確認）
- インストールボタン: `QDesktopServices.openUrl("https://ollama.com/download")`
  （アンインストールは OS 依存のため対象外）
- インストール済みモデル一覧テーブル（名前・サイズ・更新日）
- 「モデルを追加」: `ollama pull <model_name>` を `QThread` 化して実行
- 「モデルを削除」: `ollama rm <model_name>` を `QThread` 化して実行
- 「mixAI Phase 登録/解除」: `ManageModelsDialog` 経由で各 Phase 選択肢を更新

*② カスタムサーバー管理セクション*
- サーバー URL・API キー設定（現 `一般設定` の `カスタムサーバー設定` を移設）
- **サーバープロセス管理（新規）:**
  - 「サーバー実行コマンド」入力欄（例: `llama-server -m path/to/model.gguf --port 8080 -ngl 99`）
  - 「起動」ボタン: `subprocess.Popen` でバックグラウンド起動
    （`src/web/launcher.py` の `WebServerLauncher` パターンを流用）
  - 「停止」ボタン: `process.terminate()` で停止
  - 状態ラベル: 「停止中」/「起動中（PID: xxxx）」を 1 秒ポーリングで更新
  - 接続テストボタン: `GET /v1/models` でモデル一覧を取得・表示
  - サーバーコマンドと状態は `config/custom_server.json` に保存
  - Helix 終了時にプロセスを自動停止（`QApplication.aboutToQuit` シグナル接続）
- カスタムサーバーのモデル一覧・「mixAI Phase 登録/解除」

*③ 常駐モデル設定セクション*（現 `一般設定` の `常駐モデル設定` を移設）

i18n キー追加（主要なもの）:
```
"desktop.localAI.chatSubTab":             ["💬 チャット",               "💬 Chat"]
"desktop.localAI.settingsSubTab":         ["⚙️ 設定",                   "⚙️ Settings"]
"desktop.localAI.ollamaSection":          ["Ollama 管理",               "Ollama Management"]
"desktop.localAI.ollamaInstallStatus":    ["Ollama: インストール済み",   "Ollama: Installed"]
"desktop.localAI.ollamaNotInstalled":     ["Ollama: 未インストール",     "Ollama: Not Installed"]
"desktop.localAI.ollamaInstallBtn":       ["インストールページを開く",   "Open Install Page"]
"desktop.localAI.ollamaPullBtn":          ["モデルを追加",              "Add Model"]
"desktop.localAI.ollamaRmBtn":            ["モデルを削除",              "Remove Model"]
"desktop.localAI.customServerSection":    ["カスタムサーバー管理",      "Custom Server Management"]
"desktop.localAI.serverCmd":              ["サーバー実行コマンド",      "Server Command"]
"desktop.localAI.serverStart":            ["起動",                      "Start"]
"desktop.localAI.serverStop":             ["停止",                      "Stop"]
"desktop.localAI.serverStatusStopped":    ["停止中",                    "Stopped"]
"desktop.localAI.serverStatusRunning":    ["起動中 (PID: {pid})",       "Running (PID: {pid})"]
"desktop.localAI.residentSection":        ["常駐モデル設定",            "Resident Model Settings"]
"desktop.localAI.mixaiRegisterBtn":       ["mixAI Phase に登録",        "Register to mixAI Phase"]
"desktop.localAI.mixaiUnregisterBtn":     ["mixAI Phase から解除",      "Unregister from mixAI Phase"]
```

---

## 項目 4. 情報収集タブの 2 タブ構成化

`information_collection_tab.py` を `QTabWidget` でサブタブ化する。

### 4-A. 「実行」サブタブ（現状の UI を移植）

- 情報収集フォルダセクション（ファイル一覧・選択）
- 現在のプランセクション（「Claude にプランを作成させる」ボタン）
- 実行制御セクション（「RAG 構築開始」「停止」「リトライ」）
- RAG 統計セクション
- データ管理セクション（クリーンアップ）

### 4-B. 「設定」サブタブ（現状の「RAG 構築設定」セクションを移植・拡張）

- 推定実行時間 SpinBox（現状から移植）
- **使用モデル設定（新規）:** 現在ハードコードされているモデルをユーザーが変更できるようにする

  | 設定項目 | 現在の固定値 | UI |
  |---------|-------------|-----|
  | Claude モデル | Claude Opus 4.6 | `NoScrollComboBox`（`CLAUDE_MODELS` 定数から生成） |
  | 実行 LLM | command-a:latest | `NoScrollComboBox`（Ollama 検出済み + カスタムサーバーモデルから動的生成） |
  | 品質チェック LLM | ministral-3:8b | `NoScrollComboBox`（同上） |
  | Embedding モデル | qwen3-embedding:0.6b | `NoScrollComboBox`（同上） |

  各コンボのデフォルト値は現在の固定値に設定。設定は `config/app_settings.json` に保存。

- チャンクサイズ・オーバーラップ SpinBox（現状から移植）
- 「設定を保存」ボタン

i18n キー追加:
```
"desktop.infoTab.execSubTab":          ["▶ 実行",                     "▶ Execute"]
"desktop.infoTab.settingsSubTab":      ["⚙️ 設定",                    "⚙️ Settings"]
"desktop.infoTab.modelSettingsGroup":  ["使用モデル設定",             "Model Settings"]
"desktop.infoTab.claudeModelSelect":   ["Claude モデル",              "Claude Model"]
"desktop.infoTab.execLLMSelect":       ["実行 LLM",                   "Execution LLM"]
"desktop.infoTab.qualityLLMSelect":    ["品質チェック LLM",           "Quality Check LLM"]
"desktop.infoTab.embeddingSelect":     ["Embedding モデル",           "Embedding Model"]
```

---

## 項目 5. 一般設定タブの整理

### 5-A. 言語切替の移設（タブバー右端へ）

現在の `一般設定` タブの `言語/Language` セクションを削除し、
メインウィンドウのタブバー右端に常時表示する。

実装方法:
```python
# main_window.py
corner_widget = QWidget()
corner_layout = QHBoxLayout(corner_widget)
corner_layout.setContentsMargins(4, 2, 8, 2)
lang_ja_btn = QPushButton("日本語")
lang_en_btn = QPushButton("English")
corner_layout.addWidget(lang_ja_btn)
corner_layout.addWidget(lang_en_btn)
self.tab_widget.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)
```
既存の `_on_language_changed()` ロジックをそのまま流用。
`settings_cortex_tab.py` の `lang_group` / `lang_ja_btn` / `lang_en_btn` は削除。

### 5-B. 一般設定タブのセクション整理

| 現在のセクション | 対応 |
|----------------|------|
| `言語/Language` | **削除**（タブバー右端へ移設、5-A） |
| `Claude CLI 状態` | **削除**（cloudAI-設定へ移設、3-C） |
| `Ollama 接続設定` | **削除**（localAI-設定へ移設、3-D） |
| `常駐モデル設定` | **削除**（localAI-設定へ移設、3-D） |
| `カスタムサーバー設定` | **削除**（localAI-設定へ移設、3-D） |
| `MCP サーバー管理` | **残存** |
| `記憶・知識管理` | **残存** |
| `表示とテーマ` | **残存** |
| `自動化` | **残存** |
| `Web UI サーバー` | **残存** |

**「AI 状態確認」セクションを新設（削除した CLI 状態・Ollama 状態の代替）:**
- セクション名: `AI 状態確認` / `"AI Status"`（i18n key: `desktop.settings.aiStatusGroup`）
- 「接続確認」ボタン 1 つのみ配置（i18n key: `desktop.settings.aiStatusCheckBtn`）
- ボタン押下で Claude CLI / Codex CLI / Ollama を一括確認し、結果を 1 行で表示:
  例: `Claude CLI ✓ | Ollama ✓ (18 models) | Codex CLI ✗`
- Discord Webhook URL 設定を `Web UI サーバー` セクション内に移動

i18n キー追加:
```
"desktop.settings.aiStatusGroup":    ["AI 状態確認",     "AI Status"]
"desktop.settings.aiStatusCheckBtn": ["接続確認",         "Check Connections"]
"desktop.settings.aiStatusResult":   ["{statuses}",       "{statuses}"]
```

### 5-C. 残存セクションの動作確認と修正

以下の各セクションについて設定の保存・読み込みを確認し、不具合があれば修正すること:

| セクション | 確認項目 |
|-----------|---------|
| `記憶・知識管理` | `Enable RAG` / `Auto-save memories` / `Memory Risk Gate` の保存・復元 |
| `表示とテーマ` | 基本フォントサイズの変更が即時反映されるか |
| `自動化` | `セッションを自動保存する` / `コンテキストを自動読み込みする` の動作 |
| `Web UI サーバー` | ポート変更後の保存・再起動が正しく動作するか |

---

## 項目 6. custom_models.json → Phase コンボ動的反映の修正

**現状の問題:** `ManageModelsDialog` でチェックしても
Phase 2 コンボ（coding/research/reasoning 等）に反映されない。

修正要件（`helix_orchestrator_tab.py`）:

1. `_populate_phase2_combos()` メソッドを新規作成:
   - `custom_models.json` を読み込む
   - `phase_visibility[phase_key]` でチェック ON のモデルを取得
   - 各カテゴリのコンボボックスに固定リストに加えて動的追加
   - `ManageModelsDialog.exec()` 呼び出し後に `_populate_phase2_combos()` を呼び出す

2. アプリ起動時にも `_populate_phase2_combos()` を呼び出して保存済みモデルを復元

---

## 項目 7. バージョン更新

作業完了後に以下を更新すること:
- `src/utils/constants.py`: `APP_VERSION = "10.1.0"` / `APP_CODENAME = "Unified Studio"`
- `BIBLE/BIBLE_Helix AI Studio_10.1.0.md` を新規作成
  （タブ構成図・Phase 一覧・新規ファイル一覧・Changelog を含むこと）

BIBLE に記載すべき新規ファイル:
- `src/tabs/local_ai_tab.py`（新規）
- `src/backends/ollama_direct_backend.py`（新規）
- `src/widgets/execution_monitor_widget.py`（新規）
- `scripts/migrate_solo_to_cloud.py`（新規）
- `config/custom_server.json`（新規）
- `PROGRESS_v10.1.0.md`（作業進捗管理用）

---

## 項目 8. mixAI Phase 2 research への Web 検索ツール追加

### 8-A. 現状確認（必須）

`src/backends/local_agent.py` の `AGENT_TOOLS` リストと `_execute_tool()` を精査し、
現在サポートされているツール名を行番号付きで報告すること。

**現状の確認ポイント:**
- `AGENT_TOOLS` に `web_search` や `fetch_url` が存在するか
- `_execute_tool()` でウェブ系のツールが処理されているか
- `command-a:latest` がツール呼び出し（function calling）をサポートしているか確認

確認コマンド:
```bash
# Ollama でツール対応モデル一覧
ollama list
# command-a のモデル情報
ollama show command-a:latest
```

### 8-B. `web_search` ツールの追加（`local_agent.py`）

**`AGENT_TOOLS` リストに以下のツール定義を追加する:**

```python
{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "ウェブを検索して最新情報を取得する。GitHub releases、公式ドキュメント、ニュース等に有効。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索クエリ（英語推奨、例: 'qwen3 coder latest release github'）"
                },
                "max_results": {
                    "type": "integer",
                    "description": "取得する結果の最大件数（デフォルト5、最大10）",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "指定URLのページ内容を取得する。GitHub releases page、ドキュメントページ等の詳細内容確認に使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "取得するURL（https://で始まること）"
                },
                "max_chars": {
                    "type": "integer",
                    "description": "取得する最大文字数（デフォルト3000）",
                    "default": 3000
                }
            },
            "required": ["url"]
        }
    }
}
```

**`_execute_tool()` に以下の分岐を追加する:**

```python
elif name == "web_search":
    return self._tool_web_search(args["query"], args.get("max_results", 5))
elif name == "fetch_url":
    return self._tool_fetch_url(args["url"], args.get("max_chars", 3000))
```

**ツール実装メソッドを追加する:**

```python
def _tool_web_search(self, query: str, max_results: int = 5) -> dict:
    """Brave Search API または DuckDuckGo でウェブ検索を実行"""
    # 優先順位: 1. Brave Search API (config/general_settings.json に BRAVE_API_KEY があれば使用)
    # 2. DuckDuckGo Instant Answer API (APIキー不要、フォールバック)
    import json
    from pathlib import Path

    # Brave Search API キーの確認
    brave_api_key = None
    try:
        settings_path = Path("config/general_settings.json")
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            brave_api_key = settings.get("brave_search_api_key", "")
    except Exception:
        pass

    try:
        if brave_api_key:
            # Brave Search API
            import httpx
            resp = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": brave_api_key},
                params={"q": query, "count": min(max_results, 10)},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            results = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
                for r in data.get("web", {}).get("results", [])[:max_results]
            ]
            return {"results": results, "source": "brave"}
        else:
            # DuckDuckGo フォールバック
            import httpx
            resp = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
                timeout=15,
                follow_redirects=True
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("Results", [])[:max_results]:
                results.append({"title": r.get("Text", ""), "url": r.get("FirstURL", ""), "snippet": ""})
            if not results and data.get("AbstractURL"):
                results.append({"title": data.get("Heading", ""), "url": data.get("AbstractURL", ""), "snippet": data.get("Abstract", "")})
            return {"results": results, "source": "duckduckgo"}
    except Exception as e:
        return {"error": f"Web search failed: {str(e)}"}

def _tool_fetch_url(self, url: str, max_chars: int = 3000) -> dict:
    """指定 URL のページ内容をテキストで取得（HTML タグ除去）"""
    if not url.startswith("https://"):
        return {"error": "https:// で始まる URL のみ許可されています"}
    try:
        import httpx
        import re
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; HelixAI/1.0)"})
        resp.raise_for_status()
        text = resp.text
        # 簡易 HTML タグ除去
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return {"content": text[:max_chars], "url": url, "truncated": len(text) > max_chars}
    except Exception as e:
        return {"error": f"URL fetch failed: {str(e)}"}
```

### 8-C. `tools_config` への反映

`config/config.json` の `local_agent_tools` に `web_search` と `fetch_url` を追加する:

```json
"local_agent_tools": {
    "read_file": true,
    "list_dir": true,
    "search_files": true,
    "write_file": true,
    "create_file": true,
    "web_search": true,
    "fetch_url": true,
    "require_write_confirmation": true
}
```

### 8-D. Brave Search API キー設定 UI の追加

**localAI-設定タブ → Ollama 管理セクション** 内に以下を追加する:

```
[Brave Search API キー] [____________________] [取得ページを開く]
```

- 「取得ページを開く」: `QDesktopServices.openUrl("https://brave.com/search/api")`
- 空欄の場合は DuckDuckGo にフォールバック（無料・APIキー不要）
- 設定は `config/general_settings.json` の `brave_search_api_key` に保存

**一般設定タブ → MCP サーバー管理セクション** 内にも同じキーへのリンクを追加:
```
Web 検索: [Brave API キー設定は localAI-設定タブで行います]
```

### 8-E. mixAI Phase 2 研究タスクのシステムプロンプト更新

`mix_orchestrator.py` の Phase 2 research カテゴリ向けシステムプロンプトに
ウェブ検索の使用を促す指示を追加する:

```python
# research カテゴリのシステムプロンプトへ追記
"""
あなたは情報収集の専門家です。
利用可能なツール:
- web_search: ウェブ検索（GitHub releases、公式ドキュメント等の最新情報収集に積極的に使用）
- fetch_url: URL の内容取得（検索結果の詳細確認に使用）
- read_file, list_dir, search_files: ローカルファイル操作

指示: 最新情報が必要な場合は積極的に web_search を呼び出し、
      GitHub の releases ページや公式ドキュメントの最新版を確認してください。
"""
```

i18n キー追加:
```
"desktop.localAI.braveApiKeyLabel":  ["Brave Search API キー",    "Brave Search API Key"]
"desktop.localAI.braveApiKeyBtn":    ["取得ページを開く",          "Get API Key"]
"desktop.localAI.braveApiKeyTip":    ["空欄の場合は DuckDuckGo を使用（無料・APIキー不要）",
                                      "Leave blank to use DuckDuckGo (free, no API key required)"]
```

---

## 項目 9. cloudAI の Browser Use UI 改修

### 9-A. 「モデル設定」から削除する項目

`claude_tab.py` の `_create_settings_tab()` → `model_settings_group` 内から以下を削除:

| 削除対象ウィジェット | 変数名 |
|-------------------|----|
| 検索/ブラウズ方式 コンボ | `search_mode_combo`, `search_mode_label` |
| 検索結果上限 SpinBox | `search_max_tokens_spin`, `search_max_tokens_label` |

削除に伴い以下も対応すること:
- `_save_claude_settings()` から `search_mode` / `search_max_tokens` キーを削除
- `_load_claude_settings()` から `search_mode` / `search_max_tokens` の読み込み処理を削除
- `retranslateUi()` から `search_mode_combo.setItemText()` の行を削除

### 9-B. 「実行オプション」へ Browser Use チェックボックスを追加

`_create_settings_tab()` → `実行オプション` GroupBox（`mcp_options_layout`）内に以下を追加:

```python
self.browser_use_checkbox = QCheckBox(t('desktop.cloudAI.browserUseLabel'))
self.browser_use_checkbox.setChecked(False)
self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseTip'))

# browser_use 未インストール時はグレーアウト
try:
    import browser_use  # noqa: F401
    self._browser_use_available = True
except ImportError:
    self._browser_use_available = False
    self.browser_use_checkbox.setEnabled(False)
    self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseNotInstalled'))

mcp_options_layout.addWidget(self.browser_use_checkbox)
```

### 9-C. `_on_send()` の実行ロジック更新

削除した `search_mode_combo` の条件分岐を、新しいチェックボックスに置き換える:

```python
# 変更前（削除）
if hasattr(self, 'search_mode_combo') and self.search_mode_combo.currentIndex() == 2:
    processed_message = self._prepend_browser_use_results(processed_message)
if hasattr(self, 'search_mode_combo') and self.search_mode_combo.currentIndex() == 1:
    ...  # WebSearch プレフィックス注入（削除）

# 変更後（追加）
if hasattr(self, 'browser_use_checkbox') and self.browser_use_checkbox.isChecked():
    processed_message = self._prepend_browser_use_results(processed_message)
```

### 9-D. GPT（Codex CLI）モードへの Browser Use 適用

`_send_via_codex()` の呼び出し前に、Browser Use チェックボックスの状態を確認して
`_prepend_browser_use_results()` を適用する:

```python
# _on_send() の Codex 分岐を変更
if selected_model_id == "gpt-5.3-codex":
    # Browser Use が有効な場合は事前にページ内容を取得
    if hasattr(self, 'browser_use_checkbox') and self.browser_use_checkbox.isChecked():
        processed_message = self._prepend_browser_use_results(processed_message)
    self._send_via_codex(processed_message, session_id)
    return
```

### 9-E. 設定の保存・読み込み更新

`_save_claude_settings()` と `_load_claude_settings()` に以下を追加:
```python
# save
"browser_use_enabled": self.browser_use_checkbox.isChecked() if hasattr(self, 'browser_use_checkbox') else False,

# load
if 'browser_use_enabled' in settings and hasattr(self, 'browser_use_checkbox'):
    self.browser_use_checkbox.setChecked(bool(settings['browser_use_enabled']))
```

i18n キー追加:
```
"desktop.cloudAI.browserUseLabel":        ["Browser Use",                              "Browser Use"]
"desktop.cloudAI.browserUseTip":          ["URL を事前スクレイピングしてプロンプトに挿入",
                                            "Pre-scrape URLs and inject content into prompt"]
"desktop.cloudAI.browserUseNotInstalled": ["browser_use 未インストール (pip install browser-use)",
                                            "browser_use not installed (pip install browser-use)"]
```

---

## 項目 10. localAI チャットへの検索・ファイル操作機能追加

### 10-A. localAI チャットの Web 検索機能

`OllamaDirectBackend`（項目 3-D で新規作成）に、
`LocalAgentRunner` と同様のツール呼び出しループを実装する。

**具体的には:**
- `OllamaDirectBackend` の `chat()` メソッドで `tools` パラメータに
  項目 8-B で追加した `web_search` / `fetch_url` / ファイル操作ツールを渡す
- ツール呼び出しが返ってきた場合は `_execute_tool()` で処理し、結果を messages に追加
- ツール実行結果を `OllamaWorkerThread` の `toolExecuted = pyqtSignal(str, bool)` で
  UI に通知する（mixAI と同様のフロー）

**localAI チャット UI への追加:**
- ツール実行ログの表示エリア（折り畳み可能、mixAI の tool log 区画を参考に実装）
- ステータスバーへのツール実行状況表示:
  `🔍 web_search: "qwen3 coder latest release"...`

### 10-B. localAI での GitHub 操作（MCP GitHub サーバー経由）

**前提確認:** Ollama モデルはネイティブな MCP クライアント機能を持たないため、
Helix 側で GitHub MCP サーバーを HTTP プロセスとして起動し、
ツール呼び出しを仲介する方式を採用する。

**実現可能性の確認（作業前に必ず実施）:**

```bash
# GitHub MCP サーバーのインストール確認
npx @modelcontextprotocol/server-github --version 2>/dev/null || echo "not installed"

# 利用可能な場合の起動コマンド例
GITHUB_PERSONAL_ACCESS_TOKEN=<token> npx @modelcontextprotocol/server-github
```

**実装条件:** GitHub MCP サーバーが利用可能な場合のみ実装する。
インストール不可の場合は以下の `fetch_url` ベースの代替案を採用:

```python
# 代替案: GitHub API を fetch_url ツール経由で直接呼び出し
# 例: https://api.github.com/repos/ollama/ollama/releases/latest
# ユーザーが GitHub Personal Access Token を設定している場合はヘッダーに付与
```

**GitHub 連携設定 UI（localAI-設定タブ → GitHub セクションとして新設）:**
- GitHub Personal Access Token 入力欄（パスワードマスク表示）
- 「接続テスト」ボタン: `GET https://api.github.com/user` で確認
- GitHub MCP サーバー有効/無効チェックボックス
  （インストール未確認の場合はグレーアウト＋インストール手順リンク）
- 設定は `config/general_settings.json` の `github_pat` / `github_mcp_enabled` に保存

**`_tool_fetch_url()` の GitHub API 対応:**
`fetch_url` が `api.github.com` ドメインにアクセスする場合、
`config/general_settings.json` から `github_pat` を読み込み、
`Authorization: Bearer <token>` ヘッダーを自動付与する。

### 10-C. localAI でのファイル操作

`OllamaDirectBackend` には `LocalAgentRunner` と同等のファイル操作ツール
（`read_file` / `list_dir` / `search_files` / `write_file` / `create_file`）を
標準で有効にする。

作業ディレクトリは `config/config.json` の `project_dir` を使用する。

i18n キー追加:
```
"desktop.localAI.githubSection":       ["GitHub 連携",                         "GitHub Integration"]
"desktop.localAI.githubPatLabel":      ["Personal Access Token",               "Personal Access Token"]
"desktop.localAI.githubTestBtn":       ["接続テスト",                           "Test Connection"]
"desktop.localAI.githubMcpLabel":      ["GitHub MCP サーバー",                 "GitHub MCP Server"]
"desktop.localAI.githubMcpNotInstalled":["未インストール（npm 必要）",           "Not installed (requires npm)"]
"desktop.localAI.toolLogHeader":       ["🛠️ ツール実行ログ",                    "🛠️ Tool Execution Log"]
"desktop.localAI.webSearchStatus":     ["🔍 検索中: {query}",                   "🔍 Searching: {query}"]
"desktop.localAI.fetchUrlStatus":      ["🌐 取得中: {url}",                     "🌐 Fetching: {url}"]
```

---

# ════════════════════════════════════════
# SECTION 2 — 完了後作業
# ════════════════════════════════════════

*SECTION 1 の全項目完了後に実施すること。*

## S2-1. `helix_source_bundle.txt` の再生成

```bash
python scripts/build_bundle.py
```

再生成後のファイルサイズと含まれるファイル数を報告すること。

## S2-2. `GitHub/CHANGELOG.md` の更新

v10.1.0 のセクションを追加し、以下の変更を記載すること:

```markdown
## v10.1.0 "Unified Studio" — YYYY-MM-DD

### 新機能
- cloudAI タブ（旧 soloAI）+ localAI タブ新設
- 実行中モニターウィジェット（cloudAI・mixAI 共通）
- mixAI チャット吹き出し表示 + 会話継続パネル
- 情報収集タブの 2 サブタブ構成（実行 / 設定）
- localAI: Ollama 管理・カスタムサーバープロセス管理
- 言語切替をタブバー右端に常時表示

### 改善
- 全 QComboBox の NoScrollComboBox 化
- ManageModelsDialog → Phase 2 コンボへの動的反映
- --dangerously-skip-permissions の mixAI 全 Phase 統一
- --continue 完了時の UI フリーズ修正

### 変更
- soloAI → cloudAI（DB・WebSocket・i18n 含む全体移行）
- Claude CLI 状態 → cloudAI-設定タブへ移設
- Ollama 接続設定・常駐モデル設定 → localAI-設定タブへ移設
```

## S2-3. 動作確認ログ

以下の全項目を確認し、結果（✅ OK / ❌ NG + 内容）を記録すること:

| # | 確認項目 |
|---|---------|
| 1 | cloudAI タブでチャット送受信 → DB に `cloudAI` で保存されること |
| 2 | localAI タブで Ollama 直接チャットが動作すること |
| 3 | localAI-設定でカスタムサーバーの起動・停止が動作すること |
| 4 | 情報収集タブの設定タブでモデルを変更して RAG 構築できること |
| 5 | 言語切替がタブバー右端で日本語 ↔ English を正しく切替できること |
| 6 | ManageModelsDialog でチェックした後 Phase 2 コンボに反映されること |
| 7 | mixAI 実行中に実行中モニターウィジェットが表示されること |
| 8 | `--continue` 完了後にチャットに結果が表示されること |
| 9 | mixAI Phase 実行中に `--dangerously-skip-permissions` が渡されること |
| 10 | すべてのプルダウンがマウスホイールで変更されないこと |
| 11 | 常駐モデルが各タブで適切に機能すること |
| 12 | 英語 UI に切替えた際にすべての項目が英語表示されること |
| 13 | mixAI Phase 2 research で `web_search` ツールが呼ばれること（GitHub releases 検索等） |
| 14 | cloudAI で Browser Use チェックボックスが「実行オプション」内に表示されること |
| 15 | cloudAI で Browser Use ON + URL 含むプロンプト送信時に内容が事前取得されること |
| 16 | GPT（Codex）モードでも Browser Use が機能すること |
| 17 | localAI チャットで `web_search` / `fetch_url` ツールが呼べること |
| 18 | localAI で GitHub API へのアクセスが機能すること（PAT 設定時） |
| 19 | DuckDuckGo フォールバック（Brave API キー未設定時）が機能すること |
