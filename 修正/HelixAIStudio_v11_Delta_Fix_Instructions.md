# v11.0.0 未実装修正指示書（Claude Code用）

**重要**: これは「現状のv11.0.0コードに対する差分修正」のみを記載した指示書です。
既に実装済みのPhase 1-6の基本機能には触れません。**ここに書かれていることだけを実行してください。**

参照ドキュメント:
- `HelixAIStudio_v11_UI_Design_Rules.md`（UIルール詳細）
- `HelixAIStudio_v11_Implementation_Spec_v3.md`（全体仕様書、必要に応じて参照）

---

## 修正A: build_bundle.py にファイル追加

`scripts/build_bundle.py` のファイルリストに以下の7ファイルを追加してください:

```
src/widgets/no_scroll_widgets.py
src/widgets/section_save_button.py
src/tabs/history_tab.py
src/utils/chat_logger.py
src/memory/model_config.py
src/mixins/__init__.py
src/mixins/bible_context_mixin.py
```

---

## 修正B: NoScrollウィジェットのローカル定義を共通importに置換

### 目的
5ファイルにローカル定義されている `_NoScrollComboBox` / `NoScrollComboBox` / `NoScrollSpinBox` / `_NoScrollSpinBox` を削除し、`src/widgets/no_scroll_widgets.py` からのimportに統一する。

### 対象ファイルと作業

#### B-1. `src/tabs/information_collection_tab.py`

**削除**: 以下の2クラス定義を削除
```python
class NoScrollSpinBox(QSpinBox):
    """マウスホイールで値が変わらないQSpinBox（v9.7.1: スクロール操作との重複回避）"""
    def wheelEvent(self, event):
        event.ignore()

class _NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox（v10.1.0）"""
    def wheelEvent(self, event):
        event.ignore()
```

**追加**: ファイル先頭のimportブロックに追加
```python
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
```

**置換**: ファイル内の全ての `_NoScrollComboBox` → `NoScrollComboBox`

#### B-2. `src/tabs/helix_orchestrator_tab.py`

**削除**: 以下の2クラス定義を削除
```python
class NoScrollComboBox(QComboBox):
    """v11.0.0: マウスホイールで値が変わらないQComboBox"""
    def wheelEvent(self, event):
        event.ignore()

class NoScrollSpinBox(QSpinBox):
    """v11.0.0: マウスホイールで値が変わらないQSpinBox"""
    def wheelEvent(self, event):
        event.ignore()
```

**追加**: ファイル先頭のimportブロックに追加
```python
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
```

#### B-3. `src/tabs/local_ai_tab.py`

**削除**: 以下のクラス定義を削除
```python
class _NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox"""
    def wheelEvent(self, event):
        event.ignore()
```

**追加**: ファイル先頭のimportブロックに追加
```python
from ..widgets.no_scroll_widgets import NoScrollComboBox
```

**置換**: ファイル内の全ての `_NoScrollComboBox` → `NoScrollComboBox`

#### B-4. `src/tabs/claude_tab.py`

**削除**: 以下のクラス定義を削除（インデントされたネスト定義の場合あり）
```python
class _NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()
```

**追加**: ファイル先頭のimportブロックに追加（NoScrollComboBoxは既にimport済み）
```python
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
```

**置換**: ファイル内の全ての `_NoScrollSpinBox` → `NoScrollSpinBox`

#### B-5. `src/tabs/settings_cortex_tab.py`

**削除**: 以下の2クラス定義を削除
```python
class _NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox（v10.1.0）"""
    def wheelEvent(self, event):
        event.ignore()

class _NoScrollSpinBox(QSpinBox):
    """マウスホイールで値が変わらないQSpinBox"""
    def wheelEvent(self, event):
        event.ignore()
```

**追加**: ファイル先頭のimportブロックに追加
```python
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
```

**置換**: ファイル内の全ての `_NoScrollComboBox` → `NoScrollComboBox`、`_NoScrollSpinBox` → `NoScrollSpinBox`

---

## 修正C: 領域別保存ボタンの全面展開

### 目的
各設定QGroupBoxの末尾に `create_section_save_button()` を追加し、画面最下部の単一保存ボタンを削除する。

### 共通パターン
```python
from ..widgets.section_save_button import create_section_save_button

# QGroupBox内のlayoutの末尾に追加:
layout.addWidget(create_section_save_button(self._save_xxx_settings))
```

保存コールバック `_save_xxx_settings()` は、既存の `_on_save_settings()` から該当領域の設定保存ロジックを分離して作成する。

### C-1. mixAI 設定タブ (`src/tabs/helix_orchestrator_tab.py`)

**削除**: 画面最下部の単一保存ボタン（`self.save_btn` と `save_btn_layout` 一式）

**追加**: 以下の6つのQGroupBox末尾にそれぞれ保存ボタンを配置

| 変数名 | i18nキー | 保存コールバック |
|--------|---------|----------------|
| `self.claude_group` | `desktop.mixAI.phase13GroupLabel` | `self._save_phase13_settings` |
| `self.phase35_group` | `desktop.mixAI.phase35GroupLabel` | `self._save_phase35_settings` |
| `self.phase4_group` | `desktop.mixAI.phase4GroupLabel` | `self._save_phase4_settings` |
| `self.ollama_group` | `desktop.mixAI.ollamaGroup` | `self._save_ollama_settings` |
| `self.always_load_group` | `desktop.mixAI.residentGroup` | `self._save_resident_settings` |
| `self.phase_group` | `desktop.mixAI.phase2GroupLabel` | `self._save_phase2_settings` |

各 `_save_xxx_settings()` メソッドは、既存の `_on_save_settings()` 内の対応する設定項目の保存ロジックを抽出して作成する。

### C-2. cloudAI 設定タブ (`src/tabs/claude_tab.py`)

**削除**: 画面最下部の `self.save_settings_btn` と `save_btn_layout` 一式

**追加**: 以下のQGroupBox末尾にそれぞれ保存ボタンを配置

| 変数名 | 保存コールバック |
|--------|----------------|
| `self.model_settings_group` | `self._save_model_settings` |
| `self.mcp_options_group` | `self._save_execution_options` |
| `self.cli_section_group` | `self._save_cli_settings` |
| `self.codex_section_group` | `self._save_codex_settings` |
| `self.cloudai_mcp_group` | ✅ 既に実装済み（`self._save_cloudai_mcp_settings`） |

**注意**: `self.api_group` と `self.ollama_group` は表示のみのため保存ボタン不要。

### C-3. RAG 設定サブタブ (`src/tabs/information_collection_tab.py`)

**削除**: 既存の `self.save_settings_btn` 一式

**追加**: 以下のQGroupBox末尾にそれぞれ保存ボタンを配置

| 変数名 | 保存コールバック |
|--------|----------------|
| `self.model_settings_group` | `self._save_rag_model_settings` |
| `auto_enhance_group` | `self._save_rag_enhance_settings` |

各 `_save_rag_xxx_settings()` メソッドは、既存の `_save_rag_settings()` から対応する設定項目を抽出して作成する。

### C-4. 一般設定タブ (`src/tabs/settings_cortex_tab.py`)

**削除**: 画面最下部の `self.save_settings_btn` 一式

**追加**: 以下のQGroupBox末尾にそれぞれ保存ボタンを配置

| QGroupBox (i18nキー) | 保存コールバック |
|---------------------|----------------|
| `desktop.settings.memory` | `self._save_memory_settings` |
| `desktop.settings.display` | `self._save_display_settings` |
| `desktop.settings.automation` | `self._save_automation_settings` |
| `desktop.settings.webUI` | `self._save_webui_settings` |

**注意**: AI状態確認(`aiStatusGroup`)、CLI Status(`cliStatus`)、常駐モデル(`residentGroup`)、言語設定(`language`)は表示/アクション専用のため保存ボタン不要。

---

## 修正D: i18nハードコード文字列の修正

### D-1. History タブ (`src/tabs/history_tab.py`)

右パネルの初期テキスト `"Select a message to view details"` をi18n化:

```python
# 修正前
self.detail_label.setText("Select a message to view details")

# 修正後
self.detail_label.setText(t('desktop.history.selectMessage'))
```

i18nキー追加:

```json
// ja.json > desktop > history
"selectMessage": "メッセージを選択して詳細を表示"

// en.json > desktop > history
"selectMessage": "Select a message to view details"
```

### D-2. 既存ハードコード文字列の確認

History タブ内の他のハードコード英語/日本語テキストを確認し、全て `t()` 経由に修正してください。`history_tab.py` はバンドルに含まれていないため、実ファイルを直接確認してください。

---

## 修正E: i18nキー追加（ja.json / en.json）

以下のキーが不足している場合は追加してください:

```json
// ja.json
{
  "common": {
    "saveSection": "保存",
    "saveSectionDone": "保存完了",
    "saveSectionFailed": "保存失敗"
  },
  "desktop": {
    "history": {
      "selectMessage": "メッセージを選択して詳細を表示"
    },
    "mixAI": {
      "phase13Saved": "Phase 1/3 設定を保存しました",
      "phase2Saved": "Phase 2 設定を保存しました",
      "phase35Saved": "Phase 3.5 設定を保存しました",
      "phase4Saved": "Phase 4 設定を保存しました",
      "ollamaSaved": "Ollama接続設定を保存しました",
      "residentSaved": "常駐モデル設定を保存しました"
    },
    "settings": {
      "memorySaved": "メモリ設定を保存しました",
      "displaySaved": "表示設定を保存しました",
      "automationSaved": "自動化設定を保存しました",
      "webuiSaved": "Web UI設定を保存しました"
    }
  }
}

// en.json
{
  "common": {
    "saveSection": "Save",
    "saveSectionDone": "Saved",
    "saveSectionFailed": "Save Failed"
  },
  "desktop": {
    "history": {
      "selectMessage": "Select a message to view details"
    },
    "mixAI": {
      "phase13Saved": "Phase 1/3 settings saved",
      "phase2Saved": "Phase 2 settings saved",
      "phase35Saved": "Phase 3.5 settings saved",
      "phase4Saved": "Phase 4 settings saved",
      "ollamaSaved": "Ollama connection settings saved",
      "residentSaved": "Resident model settings saved"
    },
    "settings": {
      "memorySaved": "Memory settings saved",
      "displaySaved": "Display settings saved",
      "automationSaved": "Automation settings saved",
      "webuiSaved": "Web UI settings saved"
    }
  }
}
```

---

## 検証方法

修正完了後、以下のコマンドで確認:

```bash
# B: ローカルNoScroll定義が0件であること
grep -rn "class _NoScrollComboBox\|class _NoScrollSpinBox" src/tabs/ src/widgets/
# 期待: 0件（no_scroll_widgets.py内の定義は除く）

# C: 画面最下部の単一保存ボタンが削除されていること
grep -rn "self.save_btn\b" src/tabs/helix_orchestrator_tab.py
grep -rn "self.save_settings_btn" src/tabs/settings_cortex_tab.py
# 期待: 0件

# D: ハードコード英語が無いこと
grep -rn "Select a message" src/tabs/history_tab.py
# 期待: 0件

# E: i18nキーの存在確認
grep "saveSection\|phase13Saved\|selectMessage" i18n/ja.json
# 期待: 各キーが見つかること
```

---

## 実行順序

1. **修正A**（build_bundle.py）→ 独立作業
2. **修正B**（NoScroll共通化）→ 全5ファイル一括
3. **修正C**（領域別保存ボタン）→ 4タブ順次
4. **修正D + E**（i18n）→ 修正Cと同時可能

各修正完了後にアプリを起動して動作確認してからコミットしてください。
