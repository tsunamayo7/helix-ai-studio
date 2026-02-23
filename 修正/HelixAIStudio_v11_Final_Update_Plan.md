# Helix AI Studio v11.0.0 最終アップデートプラン

**作成日**: 2026-02-23
**検証ベース**: Before(1-10 日本語UI) / After(11-20 英語UI) 全20枚のスクリーンショット比較
**検証結果**: Before→Afterの変更は言語切替のみ。①-⑨の要件はUIに一切反映されていない。

> **Claude Codeへの最重要指示**:
> このドキュメントに記載された修正を**上から順番に1つずつ**実行してください。
> 各タスクの末尾にある「検証」を実行し、期待結果を確認してから次に進んでください。
> **既に実装済みの機能には触れないでください。**

---

# ==========================================
# BATCH 1: 全タブ共通の削除・修正（小規模）
# ==========================================

## タスク1-1: 全チャットタブからv11.0.0バージョンバッジを削除

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`, `src/tabs/claude_tab.py`, `src/tabs/local_ai_tab.py`

**理由**: ウィンドウタイトルバーに `v11.0.0` が既に表示されているため、各タブ内での重複表示は不要。

**作業**: 各ファイルで `v11.0.0` バッジのQLabel/ウィジェットを検索し、そのウィジェットと`addWidget`行を削除する。

```python
# 検索キーワード（各ファイルで以下を検索）:
# "version" + "label" or "badge"
# "v11.0.0" or "APP_VERSION"
# QPushButton/QLabel で version を表示している箇所
```

**検証**: アプリ起動 → mixAI/cloudAI/localAI各チャットタブにv11.0.0バッジが表示されないこと

---

## タスク1-2: NoScrollウィジェットのローカル定義を共通importに統一

**対象ファイル**: 5ファイル

**作業**: 以下の表に従い、各ファイルのローカルクラス定義を削除し、共通importを追加する。

| ファイル | 削除するクラス定義 | 追加するimport |
|---------|-----------------|--------------|
| `src/tabs/information_collection_tab.py` | `class NoScrollSpinBox(QSpinBox)` + `class _NoScrollComboBox(QComboBox)` | `from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox` |
| `src/tabs/helix_orchestrator_tab.py` | `class NoScrollComboBox(QComboBox)` + `class NoScrollSpinBox(QSpinBox)` | `from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox` |
| `src/tabs/local_ai_tab.py` | `class _NoScrollComboBox(QComboBox)` | `from ..widgets.no_scroll_widgets import NoScrollComboBox` |
| `src/tabs/claude_tab.py` | `class _NoScrollSpinBox(QSpinBox)` | `from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox` |
| `src/tabs/settings_cortex_tab.py` | `class _NoScrollComboBox(QComboBox)` + `class _NoScrollSpinBox(QSpinBox)` | `from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox` |

各ファイル内の `_NoScrollComboBox` → `NoScrollComboBox`、`_NoScrollSpinBox` → `NoScrollSpinBox` を一括置換する。

**検証**:
```bash
grep -rn "class _NoScrollComboBox\|class _NoScrollSpinBox" src/tabs/
# 期待: 0件
```

---

## タスク1-3: build_bundle.py にファイル追加

**対象ファイル**: `scripts/build_bundle.py`

**作業**: ファイルリストに以下を追加:
```
src/widgets/no_scroll_widgets.py
src/widgets/section_save_button.py
src/tabs/history_tab.py
src/utils/chat_logger.py
src/memory/model_config.py
src/mixins/__init__.py
src/mixins/bible_context_mixin.py
config/cloud_models.json
```

**検証**: `python scripts/build_bundle.py` が正常終了すること

---

# ==========================================
# BATCH 2: mixAIチャットタブ改修（①）
# ==========================================

## タスク2-1: mixAI ヘッダー文言変更

**対象ファイル**: `i18n/ja.json`, `i18n/en.json`

**作業**: mixAIタイトルのi18nキー値を変更:
- ja: `"3Phase統合オーケストレーション"` → `"統合オーケストレーション"` （"3Phase"を削除）
- en: `"3Phase Orchestration"` → `"Integrated Orchestration"` （"3Phase"を削除）

**検証**: アプリ起動 → mixAIチャットタブのヘッダーに"3Phase"が含まれないこと

---

## タスク2-2: mixAI チャットタブからボタン・UI要素を削除

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**以下のUI要素を削除する（変数名で特定）:**

| # | 削除対象 | 変数名/検索キー | 削除理由 |
|---|---------|---------------|---------|
| 1 | ヘッダー「新規セッション」ボタン | `self.new_session_btn` | Historyタブへ移行済み |
| 2 | ヘッダー「履歴」ボタン | `self.history_btn` (ヘッダー行のもの) | Historyタブへ移行済み |
| 3 | チャット記入欄下「履歴」ボタン | `self.mixai_history_btn` | Historyタブへ移行済み |
| 4 | チャット記入欄下「クリア」ボタン | `self.clear_btn`, `_on_clear` メソッド | 機能不要 |
| 5 | チャット記入欄下「会話継続」ボタン | ボタン行内の `continue` ボタン（「会話継続」パネルとは別） | 下部パネルで代替 |
| 6 | チャット記入欄下「追加」独立ボタン | `self.mixai_snippet_add_btn` | スニペットメニュー内に統合(タスク2-3) |
| 7 | サイドバー「チャット履歴」パネル | `_toggle_history_panel` メソッド, `chat_history_panel` 参照 | Historyタブへ移行済み |

**各削除作業の手順**:
1. 変数名でファイル内を検索
2. ウィジェット生成行（`QPushButton(...)` etc）を削除
3. `addWidget()` / `addLayout()` 行を削除
4. `clicked.connect()` 行を削除
5. 接続先のメソッド（`_on_new_session`, `_on_clear`, `_toggle_history_panel` 等）を削除
6. `retranslateUi` 内の対応する `setText()` / `setToolTip()` 行を削除

**検証**: アプリ起動 → mixAIチャットタブで上記ボタンが表示されないこと

---

## タスク2-3: 「追加」機能をスニペットメニュー内に統合

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**作業**: `_on_snippet_menu()` メソッド内のQMenuに以下のアクションを追加:

```python
menu.addSeparator()
add_action = menu.addAction(t('desktop.mixAI.snippetAddBtn'))  # "＋ 追加"
add_action.triggered.connect(self._on_add_snippet)
```

**検証**: アプリ起動 → スニペットボタン押下 → メニュー最下部に「＋ 追加」が表示されること

---

## タスク2-4: mixAI チャット入力欄をcloudAIと同じレイアウトに変更

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**現状** (After 11):
```
上部: [メッセージ入力欄（大きいテキストエリア）]
      [▶実行][■キャンセル][▶会話継続] [📎添付][📜履歴][📋スニペット▼][＋追加][📖BIBLE]  [🗑クリア]
中部: [ツール実行ログ]
      [実行結果表示エリア]
下部: [● 会話継続パネル]
```

**目標** (cloudAI After 13 と同じ):
```
上部: [チャット表示エリア（大きな表示領域）]
下部左: [メッセージ入力欄]
        [📎添付][📋スニペット▼][📖BIBLE]  [▶実行]
下部右: [● 会話継続]
        [入力欄]
        [はい][続行][実行]
        [送信]
```

**具体的な変更**:

1. **メッセージ入力欄を画面下部に移動**: 現在 `_create_chat_sub_tab()` 内で上部に配置されている `self.input_text`（QPlainTextEdit）を、チャット表示エリアの下に移動する。

2. **ボタン行を再構成**: 入力欄の下に以下のボタンのみ配置:
   - `📎 ファイルを添付` (既存の `self.mixai_attach_btn`)
   - `📋 スニペット▼` (既存の `self.mixai_snippet_btn`)
   - `📖 BIBLE` (既存の `self.bible_btn`)
   - `▶ 実行` (既存の `self.execute_btn`)

3. **会話継続パネルを入力欄の右側に配置**: 現在の `_create_mixai_continue_panel()` を、入力欄＋ボタンの右側に配置する（QHBoxLayout）。

4. **ボタンのスタイルをcloudAIと統一**: 以下のプロパティを cloudAI (`claude_tab.py`) から複製:
   - フォントサイズ
   - ボタン高さ (`setFixedHeight`)
   - ボタン色・スタイルシート
   - BIBLEボタンの高さを他と揃える

5. **「ツール実行ログ」と「実行結果表示エリア」**: チャット表示エリア内にインライン表示する（折りたたみ可能なQGroupBox等で）。

**レイアウト構造（コード）**:
```python
# チャットサブタブのメインレイアウト
main_layout = QVBoxLayout()

# 1. チャット表示エリア（上部、stretching）
main_layout.addWidget(self.chat_display, stretch=1)

# 2. 下部: 入力欄(左) + 会話継続(右)
bottom_layout = QHBoxLayout()

# 2a. 左側: 入力欄 + ボタン行
left_layout = QVBoxLayout()
left_layout.addWidget(self.input_text)  # 入力欄
btn_row = QHBoxLayout()
btn_row.addWidget(self.mixai_attach_btn)
btn_row.addWidget(self.mixai_snippet_btn)
btn_row.addWidget(self.bible_btn)
btn_row.addStretch()
btn_row.addWidget(self.execute_btn)
left_layout.addLayout(btn_row)
bottom_layout.addLayout(left_layout, stretch=2)

# 2b. 右側: 会話継続パネル
bottom_layout.addWidget(continue_panel, stretch=1)

main_layout.addLayout(bottom_layout)
```

**検証**: アプリ起動 → mixAIチャットタブが cloudAI (After 13) と同じレイアウトになっていること

---

## タスク2-5: 会話継続パネルのボタンスタイルをcloudAIと統一

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**作業**: `_create_mixai_continue_panel()` 内のボタン（Yes/Continue/Execute/送信）のスタイルを `claude_tab.py` の `_create_continue_panel()` と同じスタイルシートに変更。

- 「はい」ボタン: cloudAIの「Yes」と同じ色（紫系）
- 「続行」ボタン: cloudAIの「Continue」と同じ色（青系）
- 「実行」ボタン: cloudAIの「Execute」と同じ色（赤系）
- 「送信」ボタン: cloudAIの「送信」と同じ色（青帯）

**検証**: 色・サイズがcloudAIタブのものと一致すること

---

# ==========================================
# BATCH 3: cloudAIチャットタブ改修（③）
# ==========================================

## タスク3-1: cloudAI チャットヘッダーの再構成

**対象ファイル**: `src/tabs/claude_tab.py`

**現状** (After 13):
```
Model: [Claude Opus 4.6] [Advanced] [New]  ☁ cloudAI - Claude Code [New Session] [v11.0.0]
```

**目標** (localAI After 15 と同じ配置・フォント):
```
☁ cloudAI - クラウドAI  モデル: [Claude Opus 4.6 ▼]  [🔄 更新]
```

**削除するUI要素**:
| 要素 | 変数名 | 理由 |
|------|-------|------|
| 「Advanced」/「詳細設定」ボタン | `self.advanced_btn` 等 | 設定タブで設定する機能 |
| 「New」/「新規」ボタン | `self.new_btn` 等 | Historyタブへ移行済み |
| 「新規セッション」ボタン | `self.new_session_btn` 等 | Historyタブへ移行済み |
| v11.0.0バッジ | (タスク1-1で対応済み) | 重複表示 |

**変更するUI要素**:
- ヘッダータイトル: `"cloudAI - Claude Code"` → i18nキー `t('desktop.cloudAI.headerTitle')` = `"☁ cloudAI - クラウドAI"`
- 「Model:」表記: → i18nキー `t('desktop.cloudAI.modelLabel')` = `"モデル:"`
- 「更新」ボタン新設: `QPushButton(t('desktop.cloudAI.refreshBtn'))` — 押下時に設定タブで変更されたモデル一覧を再読み込み

**i18nキー追加**:
```json
// ja.json
"cloudAI": { "headerTitle": "☁ cloudAI - クラウドAI", "modelLabel": "モデル:", "refreshBtn": "🔄 更新" }
// en.json
"cloudAI": { "headerTitle": "☁ cloudAI - Cloud AI", "modelLabel": "Model:", "refreshBtn": "🔄 Refresh" }
```

**検証**: ヘッダーがlocalAIタブ (After 15) と同じフォント・サイズ・配置になっていること

---

## タスク3-2: cloudAI チャットタブからボタン削除

**対象ファイル**: `src/tabs/claude_tab.py`

**削除するUI要素**:
| 要素 | 変数名 | 理由 |
|------|-------|------|
| 「履歴から引用」ボタン | `self.history_cite_btn` 等 | Historyタブで代替 |
| 「追加」独立ボタン | `self.add_snippet_btn` 等 | スニペットメニュー内に統合 |

**「追加」をスニペットメニュー内に統合**: タスク2-3と同じ手法で `_on_snippet_menu()` にメニュー項目追加。

**BIBLEボタン高さ修正**: `self.bible_btn.setFixedHeight(32)` 等で他のボタンと同じ高さに設定。

**検証**: 「履歴から引用」「追加」ボタンが表示されないこと。BIBLEボタンの高さが他と揃っていること。

---

# ==========================================
# BATCH 4: localAIチャットタブ改修（⑤）
# ==========================================

## タスク4-1: localAI チャットタブからボタン削除・追加

**対象ファイル**: `src/tabs/local_ai_tab.py`

**削除**:
- 「新規セッション」ボタン（`self.new_session_btn` 等）

**追加** (チャット記入欄下のボタン行に):
- `📎 添付` ボタン — cloudAIの添付ボタンと同じスタイル・機能
- `📋 スニペット▼` ボタン — cloudAIのスニペットボタンと同じスタイル・機能

**BIBLEボタン高さ修正**: 他のボタンと同じ高さに設定。

---

## タスク4-2: localAI チャット入力欄をcloudAIと同じレイアウトに変更

**対象ファイル**: `src/tabs/local_ai_tab.py`

**現状** (After 15):
```
上部: [チャット表示エリア]
中部: [メッセージ入力欄]
      [▶送信][📖BIBLE]
下部: [● 会話継続パネル（全幅）]
```

**目標** (cloudAI After 13 と同じ):
```
上部: [チャット表示エリア]
下部左: [メッセージ入力欄]
        [📎添付][📋スニペット▼][📖BIBLE]  [▶送信]
下部右: [● 会話継続パネル]
```

タスク2-4と同じレイアウト構造を適用。

**検証**: localAIチャットタブがcloudAI (After 13) と同じレイアウトになっていること

---

# ==========================================
# BATCH 5: mixAI設定タブ改修（②）
# ==========================================

## タスク5-1: Phase 1/3 モデル選択をプルダウンに変更

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**現状**: 固定テキスト表示 `"Claude Opus 4.6 (Top Performance)"` / `"Claude Opus 4.6 (最高性能)"`

**目標**: `config/cloud_models.json` から読み込んだモデル一覧のNoScrollComboBoxプルダウン

**作業**:
```python
# 固定テキスト/QLabel を NoScrollComboBox に置換
self.p1p3_model_combo = NoScrollComboBox()
self._load_cloud_models_to_combo(self.p1p3_model_combo)
# レイアウトに追加（既存のQLabelの位置）
```

`_load_cloud_models_to_combo()` メソッドは `claude_tab.py` に既存の同名メソッドを参考に実装。

---

## タスク5-2: Phase 2 の「▼ 変更」ボタンを全て削除

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**現状**: 各カテゴリ（coding/research/reasoning/translation/vision）に「▼ 変更」ボタン

**作業**: 5個の `change_btn` (`coding_change_btn`, `research_change_btn`, `reasoning_change_btn`, `translation_change_btn`, `vision_change_btn`) とその `clicked.connect()` 行を削除。

各モデル選択を、クリックでポップアップが開くNoScrollComboBoxに変更。Phase 1/3と同じプルダウン（ただしOllamaモデルも含む）。

**プルダウンの内容**:
- `config/cloud_models.json` の全モデル
- Ollama `GET /api/tags` のモデル一覧（ただしembeddingモデルは除外）

---

## タスク5-3: Phase 2 の「モデル管理」ボタン削除

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

**作業**: `ManageModelsDialog` への接続ボタンとその `clicked.connect()` を削除。

---

## タスク5-4: Phase 3.5, Phase 4 のプルダウン化

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`

- Phase 3.5: `cloud_models.json` からのプルダウン + 「なし（スキップ）」選択肢
- Phase 4: `cloud_models.json` + Ollamaモデル一覧のプルダウン

---

# ==========================================
# BATCH 6: cloudAI設定タブ改修（④）
# ==========================================

## タスク6-1: モデル設定セクションのモデル管理機能追加

**対象ファイル**: `src/tabs/claude_tab.py`

**現状** (After 14): モデルプルダウン + タイムアウトのみ

**目標**: モデルの追加/削除/並び替え/JSON編集ができるUI

```
┌─ 🤖 モデル設定 ──────────────────────────────────┐
│  登録済みモデル:                                   │
│  ┌───────────────────────────────────────────┐    │
│  │ 1. Claude Opus 4.6  | claude --model ...  │    │
│  │ 2. Claude Sonnet 4.6| claude --model ...  │    │
│  └───────────────────────────────────────────┘    │
│  [＋追加] [🗑削除] [↕並び替え] [📝JSON編集] [🔄更新] │
│  タイムアウト: [120 分 ▼▲]                         │
│                                           [💾保存] │
└───────────────────────────────────────────────────┘
```

**「＋追加」ボタン**: QDialogポップアップ
- 入力欄1: 表示名 (例: `Claude Opus 4.6`)
- 入力欄2: 呼び出し方法 (例: `claude --model claude-opus-4-6`)
- OKで `config/cloud_models.json` に追記

**「🗑削除」ボタン**: リストで選択中のモデルを確認ダイアログ表示後に削除

**「↕並び替え」ボタン**: リスト内の選択アイテムを上下移動（QToolButton + ↑↓）

**「📝JSON編集」ボタン**: `config/cloud_models.json` の内容をQTextEditダイアログで直接編集

**「🔄更新」ボタン**: 変更を保存し、cloudAIチャットヘッダーとmixAI設定の全Phaseプルダウンを再読み込み

---

## タスク6-2: 実行オプション内のMCPチェックボックス削除

**対象ファイル**: `src/tabs/claude_tab.py`

**作業**: `self.mcp_options_group` 内の「MCP」チェックボックスウィジェットを削除。MCP設定セクションで詳細に設定可能なため不要。

---

## タスク6-3: Codex CLI検出ロジック修正

**対象ファイル**: `src/backends/codex_cli_backend.py`

**現状**: `check_codex_cli_available()` が `Not found` を返す

**作業**:
1. `shutil.which("codex")` の結果を確認
2. 見つからない場合、以下のパスも検索:
   - `~/.npm-global/bin/codex`
   - `/usr/local/bin/codex`
   - `npm list -g --depth=0` で codex パッケージの存在確認
3. `npx codex --version` も試行
4. PATHに含まれていない場合のfallback検索を追加

---

# ==========================================
# BATCH 7: localAI設定タブ改修（⑥）
# ==========================================

## タスク7-1: インストール済みモデルリストにcapability列追加

**対象ファイル**: `src/tabs/local_ai_tab.py`

**現状**: テーブルヘッダー = Name | Size | Modified

**目標**: テーブルヘッダー = Name | Size | Modified | Tools | Embed | Vision | Think

**作業**:
1. QTableWidget の列数を7に増加
2. ヘッダーラベル追加
3. モデル一覧取得時に Ollama API `POST /api/show` で各モデルのcapabilityを取得
4. 各行に ✅/❌ で表示

```python
# capability取得例
resp = requests.post(f"{ollama_url}/api/show", json={"name": model_name})
data = resp.json()
capabilities = data.get("capabilities", [])
has_tools = "tools" in capabilities
has_embed = "embed" in capabilities or "embedding" in capabilities
has_vision = "vision" in capabilities
has_thinking = "thinking" in capabilities or model_name contains "think"
```

---

## タスク7-2: モデル追加方法の変更

**対象ファイル**: `src/tabs/local_ai_tab.py`

**削除**: モデル名テキストボックス（`モデル名 (例: llama3.2:3b)`）

**変更**: 「モデルを追加」ボタン → ポップアップダイアログ形式に変更:
```python
class AddModelDialog(QDialog):
    def __init__(self, parent=None):
        # 入力欄1: 表示名（自動補完あり）
        # 入力欄2: Ollamaモデル名（呼び出しコード）
        # OKボタン → `ollama pull <モデル名>` を実行
```

---

## タスク7-3: 削除対象の視覚的強調

**対象ファイル**: `src/tabs/local_ai_tab.py`

**作業**: テーブルの行選択時にハイライト表示を強化。「モデルを削除」ボタン押下時に選択行を赤色で強調し、確認ダイアログを表示:
```python
# 選択行のハイライト
self.model_table.setStyleSheet("""
    QTableWidget::item:selected { background-color: #7f1d1d; color: white; }
""")
```

---

## タスク7-4: プルダウン表示先の設定UI（後回し可）

**対象ファイル**: `src/tabs/local_ai_tab.py`

各モデルをどのタブのプルダウンに表示するかを設定するQGroupBoxを新設。

> **注意**: この機能は複雑度が高いため、BATCH 7の最後に実施。他のタスクを先に完了すること。

---

# ==========================================
# BATCH 8: RAGタブ改修（⑦⑧）
# ==========================================

## タスク8-1: RAG設定タブの修正

**対象ファイル**: `src/tabs/information_collection_tab.py`

### 8-1a: 「RAG構築設定」の外枠QGroupBox削除
外側の `QGroupBox("RAG Build Settings")` / `QGroupBox("RAG構築設定")` を削除し、中身を直接レイアウトに配置。

### 8-1b: 使用モデル設定をプルダウン化
現在の読み取り専用テキスト（`Claude Opus 4.6`, `command-a:latest` 等）を NoScrollComboBox に変更:
- Claude Model: `cloud_models.json` から読み込み
- Execution LLM: Ollamaモデル一覧
- Quality Check LLM: Ollamaモデル一覧
- Embedding Model: Ollamaモデル一覧（embedding対応のみ）

### 8-1c: チャンクサイズ/オーバーラップの説明追加
各SpinBoxの下にヒントテキストを追加:
```python
chunk_hint = QLabel(t('desktop.ragSettings.chunkSizeHint'))
chunk_hint.setStyleSheet("color: #9ca3af; font-size: 10px;")
# ja: "文書を分割する単位（トークン数）。推奨: 256〜1024"
# en: "Unit for splitting documents (in tokens). Recommended: 256-1024"
```

---

## タスク8-2: RAGチャットタブの全面改修（⑦）

**対象ファイル**: `src/tabs/information_collection_tab.py`

> **これは最大規模のタスクです。**

**現状**: フォルダ一覧 → プラン → 実行制御 → RAG統計 → データ管理

**目標**: cloudAI風チャットベースUI

```
┌─────────────────────────────────────────────────────┐
│  📁 7 files │ ✅ RAG 7/7 │ 🧠 749 nodes            │
├─────────────────────────────────────────────────────┤
│  [チャット表示エリア]                                │
│  AI: RAGの状態を確認しました。                       │
│  User: 新しいファイルを追加して                       │
│  AI: ファイルを追加しました。構築中...               │
│      [████████░░] 80%                               │
├─────────────────────┬───────────────────────────────┤
│  [メッセージ入力欄]  │                               │
├─────────────────────┤                               │
│  [📁追加][📊統計]    │                               │
│  [🔄再構築][📋プラン]│                               │
│  [▶送信]             │                               │
└─────────────────────┴───────────────────────────────┘
```

**実装方針**:
- 既存の `_create_exec_sub_tab()` を新しい `_create_chat_sub_tab_v2()` に置換
- フォルダ管理・プラン作成・実行制御のバックエンドロジックはそのまま活用
- フロントエンドのみ変更（チャットUI + クイックアクションボタン）
- ステータスバーにファイル数/RAG状態/KGノード数を常時表示
- プログレスバーはチャット内にインライン表示

**詳細設計**: `HelixAIStudio_v11_Implementation_Spec_v3.md` Phase 6-B を参照

---

# ==========================================
# BATCH 9: 一般設定タブ改修（⑨）
# ==========================================

## タスク9-1: 「記憶・知識管理」セクションをRAGタブ設定に移動

**対象ファイル**: `src/tabs/settings_cortex_tab.py`, `src/tabs/information_collection_tab.py`

**作業**:
1. `settings_cortex_tab.py` から Memory Knowledge の QGroupBox と関連メソッドを削除
2. `information_collection_tab.py` の設定サブタブ末尾に同じUIを追加
3. 保存コールバックも移動

---

## タスク9-2: 「自動化」セクションに説明追加

**対象ファイル**: `src/tabs/settings_cortex_tab.py`

**作業**: 各チェックボックスの下にヒントテキストを追加:
```python
# セッション自動保存
auto_save_hint = QLabel(t('desktop.settings.autoSaveHint'))
auto_save_hint.setStyleSheet("color: #9ca3af; font-size: 10px;")
# ja: "チャットのやり取りを自動的にファイルに保存します"
# en: "Automatically saves chat interactions to files"

# コンテキスト自動読み込み
auto_context_hint = QLabel(t('desktop.settings.autoContextHint'))
auto_context_hint.setStyleSheet("color: #9ca3af; font-size: 10px;")
# ja: "前回のチャット内容を自動的に読み込みます"
# en: "Automatically loads previous chat content"
```

---

## タスク9-3: Web UIサーバー自動起動の修正

**対象ファイル**: `src/main_window.py`, `src/tabs/settings_cortex_tab.py`

**作業**:
1. `main_window.py` の `__init__()` 末尾で自動起動ロジックを確認/追加:
```python
def _init_auto_start_web_server(self):
    try:
        config = json.load(open("config/config.json"))
        if config.get("web_server", {}).get("auto_start", False):
            port = config.get("web_server", {}).get("port", 8500)
            from .web.launcher import start_server_background
            self._web_server_thread = start_server_background(port=port)
            # settings_cortex_tab にも通知
            if hasattr(self, 'settings_tab'):
                self.settings_tab._update_server_status_display(port)
    except Exception as e:
        logger.warning(f"Web UI auto-start failed: {e}")
```
2. `settings_cortex_tab.py` の `_update_server_status_display()` でURL表示を修正:
   - `http://localhost:{port}` のみ表示（文字列ベースのURLは削除）

---

## タスク9-4: Web UIパスワード設定UI追加

**対象ファイル**: `src/tabs/settings_cortex_tab.py`

**作業**: Web UIセクションに「🔑 パスワード設定」ボタンを追加。押下時にQDialog:
```
新しいパスワード: [________]
確認:             [________]
        [キャンセル] [設定]
```
OKで `config/config.json` の `web_server.pin_code` を更新。

---

## タスク9-5: Discord通知イベント選択UI追加

**対象ファイル**: `src/tabs/settings_cortex_tab.py`, `src/utils/discord_notifier.py`

**作業**:
1. Web UIセクションのDiscord Webhook URL行の下にチェックボックスを追加:
```
通知するイベント:
☑ チャット開始
☑ チャット完了
☑ エラー発生
```

2. `config/config.json` に保存:
```json
"discord_notify_start": true,
"discord_notify_complete": true,
"discord_notify_error": true
```

3. `discord_notifier.py` の `notify_discord()` を修正して設定を参照:
```python
def notify_discord(tab, status, message, ...):
    config = _load_config()
    events = config.get("web_server", {})
    if status == "started" and not events.get("discord_notify_start", True):
        return False
    # ... 同様にcompleted, errorも
```

---

## タスク9-6: Historyタブへの自動記録確認・追加

**対象ファイル**: `src/tabs/helix_orchestrator_tab.py`, `src/tabs/local_ai_tab.py`

**現状**: `chat_logger` は `claude_tab.py` でのみ使用（2箇所）

**作業**:
- `helix_orchestrator_tab.py`: `_on_final_result()` 完了時に追加:
```python
from ..utils.chat_logger import get_chat_logger
chat_logger = get_chat_logger()
chat_logger.log_message(tab="mixAI", role="assistant", content=result_text)
```

- `local_ai_tab.py`: user送信時と応答完了時に追加:
```python
from ..utils.chat_logger import get_chat_logger
chat_logger = get_chat_logger()
chat_logger.log_message(tab="localAI", role="user", content=user_message)
# ... 応答完了時
chat_logger.log_message(tab="localAI", role="assistant", content=response_text)
```

---

## タスク9-7: ChatHistoryPanel（サイドバー）の完全削除

**対象ファイル**: `src/main_window.py`, `src/tabs/helix_orchestrator_tab.py`, `src/tabs/claude_tab.py`

**作業**:
- `main_window.py` から:
  - `from .widgets.chat_history_panel import ChatHistoryPanel` 削除
  - `self.chat_history_panel = ChatHistoryPanel(...)` 一式削除
  - `addDockWidget(...)` 削除
  - `chatSelected`, `newChatRequested`, `chatDeleted` シグナル接続削除
  - `_on_chat_selected`, `_on_new_chat_from_history`, `_on_chat_deleted_from_history` メソッド削除

- `helix_orchestrator_tab.py` から: `_toggle_history_panel()` メソッド削除（タスク2-2で対応済み）
- `claude_tab.py` から: `_toggle_history_panel()` メソッド削除

---

# ==========================================
# BATCH 10: i18nキー追加（全バッチと並行）
# ==========================================

## タスク10-1: 新規i18nキーの追加

**対象ファイル**: `i18n/ja.json`, `i18n/en.json`

各バッチで必要になるi18nキーを追加。主なキー:

```json
// ja.json に追加
{
  "desktop": {
    "cloudAI": {
      "headerTitle": "☁ cloudAI - クラウドAI",
      "modelLabel": "モデル:",
      "refreshBtn": "🔄 更新",
      "addModelTitle": "モデル追加",
      "addModelName": "表示名",
      "addModelCommand": "呼び出し方法",
      "deleteModelConfirm": "このモデルを削除しますか？",
      "editJsonTitle": "cloud_models.json 編集",
      "reorderTitle": "モデル並び替え"
    },
    "ragSettings": {
      "chunkSizeHint": "文書を分割する単位（トークン数）。推奨: 256〜1024",
      "overlapHint": "隣接チャンク間の重複トークン数。推奨: チャンクサイズの10〜20%"
    },
    "settings": {
      "autoSaveHint": "チャットのやり取りを自動的にファイルに保存します",
      "autoContextHint": "前回のチャット内容を自動的に読み込みます",
      "webPasswordBtn": "🔑 パスワード設定",
      "webPasswordTitle": "Web UI パスワード設定",
      "webPasswordNew": "新しいパスワード",
      "webPasswordConfirm": "確認",
      "discordNotifyLabel": "通知するイベント:",
      "discordNotifyStart": "チャット開始",
      "discordNotifyComplete": "チャット完了",
      "discordNotifyError": "エラー発生"
    },
    "localAI": {
      "addModelTitle": "モデル追加",
      "addModelDisplayName": "表示名",
      "addModelOllamaName": "Ollamaモデル名",
      "capabilityTools": "Tools",
      "capabilityEmbed": "Embed",
      "capabilityVision": "Vision",
      "capabilityThink": "Think"
    }
  }
}
```

en.json にも対応する英語テキストを追加。

---

# ==========================================
# 実行順序と優先度
# ==========================================

| バッチ | 内容 | 工数 | 優先度 |
|--------|------|------|--------|
| BATCH 1 | 共通修正（バッジ削除/NoScroll/bundle） | 小 | 最優先 |
| BATCH 2 | mixAIチャット全面改修 | 大 | 高 |
| BATCH 3 | cloudAIチャット改修 | 中 | 高 |
| BATCH 4 | localAIチャット改修 | 中 | 高 |
| BATCH 5 | mixAI設定改修 | 中 | 中 |
| BATCH 6 | cloudAI設定改修 | 大 | 中 |
| BATCH 7 | localAI設定改修 | 大 | 中 |
| BATCH 8 | RAGタブ改修 | 最大 | 低（最後に） |
| BATCH 9 | 一般設定改修 | 中 | 中 |
| BATCH 10 | i18nキー追加 | 小 | 並行実施 |

**推奨**: BATCH 1 → 2 → 3 → 4 → 5 → 6 → 9 → 7 → 8 → 10 の順で実施。
各バッチ完了後にアプリを起動して動作確認し、`git commit` してから次へ進む。
