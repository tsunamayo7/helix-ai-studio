# Helix AI Studio v11.0.0 UI設計ルール・i18nガイドライン

**作成日**: 2026-02-22
**適用範囲**: v11.0.0 Implementation Spec v3 の全Phase
**参照**: HelixAIStudio_v11_Implementation_Spec_v3.md

> このドキュメントはv11.0.0で新設・変更する全UIの設計ルールを定義する。
> Implementation Spec と併せて参照すること。

---

## 1. NoScrollウィジェット規則

### 1-1. 背景

QComboBox / QSpinBox のデフォルト動作では、ウィジェット上でのマウスホイール操作が「値の変更」として処理される。これはスクロール可能な設定画面で**画面スクロールと競合**し、意図しない設定変更を引き起こす。

### 1-2. 既存実装の確認

v10.1.0 時点で情報収集タブ（`information_collection_tab.py` 行7999-8008）に以下のクラスが存在:

```python
class NoScrollSpinBox(QSpinBox):
    """マウスホイールで値が変わらないQSpinBox"""
    def wheelEvent(self, event):
        event.ignore()

class _NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox"""
    def wheelEvent(self, event):
        event.ignore()
```

### 1-3. v11.0.0 ルール

**【必須】v11.0.0 で新設する全てのQComboBox / QSpinBox は NoScroll版を使用すること。**

#### 共有ウィジェットモジュールの新設

**新規ファイル**: `src/widgets/no_scroll_widgets.py`

```python
"""v11.0.0: スクロール競合を防止するNoScrollウィジェット群

全タブ共通で使用する。各タブでの個別定義（_NoScrollComboBox 等）は
このモジュールからのimportに統一すること。
"""
from PyQt6.QtWidgets import QComboBox, QSpinBox, QDoubleSpinBox


class NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox（v11.0.0 共通版）"""
    def wheelEvent(self, event):
        event.ignore()


class NoScrollSpinBox(QSpinBox):
    """マウスホイールで値が変わらないQSpinBox（v11.0.0 共通版）"""
    def wheelEvent(self, event):
        event.ignore()


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """マウスホイールで値が変わらないQDoubleSpinBox（v11.0.0 共通版）"""
    def wheelEvent(self, event):
        event.ignore()
```

#### 各タブでのimport統一

```python
# 旧（タブ内に個別定義 or 標準クラス直接使用）
from PyQt6.QtWidgets import QComboBox, QSpinBox
combo = QComboBox()
spin = QSpinBox()

# 新（共通モジュールからimport）
from src.widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
combo = NoScrollComboBox()
spin = NoScrollSpinBox()
```

#### 既存タブの移行対象

| ファイル | 旧クラス | 新import |
|---------|---------|---------|
| `src/tabs/rag_tab.py` | `_NoScrollComboBox` (ローカル定義) | `from ..widgets.no_scroll_widgets import NoScrollComboBox` |
| `src/tabs/helix_orchestrator_tab.py` | `QComboBox` (直接使用) | 同上 |
| `src/tabs/claude_tab.py` | `QComboBox` (直接使用) | 同上 |
| `src/tabs/local_ai_tab.py` | `QComboBox` (直接使用) | 同上 |
| `src/tabs/general_settings_tab.py` | `QComboBox` (直接使用) | 同上 |
| `src/tabs/history_tab.py` (新規) | — | 最初から `NoScrollComboBox` を使用 |

#### 禁止事項

```python
# ❌ 禁止: 標準QComboBox / QSpinBox の直接使用
from PyQt6.QtWidgets import QComboBox
self.model_combo = QComboBox()        # ← 禁止

# ❌ 禁止: タブ内でのNoScrollクラスのローカル再定義
class _NoScrollComboBox(QComboBox):   # ← 禁止（共通版を使う）
    def wheelEvent(self, event):
        event.ignore()

# ✅ 正しい: 共通NoScrollComboBoxを使用
from src.widgets.no_scroll_widgets import NoScrollComboBox
self.model_combo = NoScrollComboBox()  # ← 正しい
```

---

## 2. 領域別「設定を保存」ボタン規則

### 2-1. 背景

現在の設定画面は画面最下部に1つの保存ボタンがあるのみで、画面上部の設定を変更した後に長いスクロールが必要。各設定領域（QGroupBox）ごとに保存ボタンを配置し、変更を即座に保存可能にする。

### 2-2. ルール

**【必須】各QGroupBox（設定領域）の末尾に「💾 保存」ボタンを配置すること。**

### 2-3. 共通の保存ボタンファクトリ

```python
# src/widgets/section_save_button.py（新規）

from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QWidget
from PyQt6.QtCore import QTimer
from src.i18n import t


def create_section_save_button(save_callback, parent=None) -> QWidget:
    """設定領域末尾に配置する保存ボタン付きコンテナを生成

    Args:
        save_callback: 保存処理のcallable
        parent: 親ウィジェット

    Returns:
        QWidget: 右寄せ保存ボタンを含むコンテナ
    """
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.addStretch()

    save_btn = QPushButton("💾 " + t('common.saveSection'))
    save_btn.setStyleSheet("""
        QPushButton {
            background: #1a3a2a; color: #00ff88;
            border: 1px solid #00ff88; border-radius: 4px;
            padding: 4px 16px; font-size: 11px; font-weight: bold;
        }
        QPushButton:hover { background: #2a4a3a; }
        QPushButton:pressed { background: #0a2a1a; }
        QPushButton:disabled { background: #1a1a2e; color: #555; border-color: #333; }
    """)

    def _on_click():
        try:
            save_callback()
            # 保存完了フィードバック
            original_text = save_btn.text()
            save_btn.setText("✅ " + t('common.saveSectionDone'))
            save_btn.setEnabled(False)
            QTimer.singleShot(1500, lambda: (
                save_btn.setText(original_text),
                save_btn.setEnabled(True)
            ))
        except Exception as e:
            save_btn.setText("❌ " + t('common.saveSectionFailed'))
            QTimer.singleShot(2000, lambda: (
                save_btn.setText("💾 " + t('common.saveSection')),
                save_btn.setEnabled(True)
            ))

    save_btn.clicked.connect(_on_click)
    layout.addWidget(save_btn)
    return container
```

### 2-4. 使用パターン

```python
from src.widgets.section_save_button import create_section_save_button

# --- Phase 1/3 設定グループ ---
self.claude_group = QGroupBox(t('desktop.mixAI.phase13GroupLabel'))
claude_layout = QVBoxLayout(self.claude_group)
# ... 設定項目 ...
claude_layout.addWidget(
    create_section_save_button(self._save_phase13_settings))

# --- Phase 2 設定グループ ---
self.phase2_group = QGroupBox(t('desktop.mixAI.phase2GroupLabel'))
phase2_layout = QVBoxLayout(self.phase2_group)
# ... 設定項目 ...
phase2_layout.addWidget(
    create_section_save_button(self._save_phase2_settings))
```

### 2-5. 保存ボタン配置対象（v11.0.0 全タブ）

#### mixAI 設定サブタブ
| 領域 | 保存コールバック | 保存先 |
|------|----------------|-------|
| Phase 1/3 設定 | `_save_phase13_settings()` | `config/config.json` → `mixai.phase13` |
| Phase 3.5 設定 | `_save_phase35_settings()` | `config/config.json` → `mixai.phase35` |
| Phase 4 設定 | `_save_phase4_settings()` | `config/config.json` → `mixai.phase4` |
| Ollama接続設定 | `_save_ollama_settings()` | `config/config.json` → `ollama` |
| 常駐モデル設定 | `_save_resident_settings()` | `config/config.json` → `resident_models` |
| Phase 2 設定 | `_save_phase2_settings()` | `config/config.json` → `mixai.phase2` |

#### cloudAI 設定サブタブ
| 領域 | 保存コールバック | 保存先 |
|------|----------------|-------|
| MCP設定 | `_save_cloudai_mcp_settings()` | `config/config.json` → `mcp_settings.cloudAI` |

#### localAI 設定サブタブ
| 領域 | 保存コールバック | 保存先 |
|------|----------------|-------|
| MCP設定 | `_save_localai_mcp_settings()` | `config/config.json` → `mcp_settings.localAI` |

#### 🧠 RAG 設定サブタブ
| 領域 | 保存コールバック | 保存先 |
|------|----------------|-------|
| チャットAI設定 | `_save_rag_chat_ai_settings()` | `config/app_settings.json` → `rag.claude_model` |
| ローカルLLMロール設定 | `_save_rag_llm_roles()` | `config/app_settings.json` → `rag.exec_llm/quality_llm/embedding_model` |
| RAG構築パラメータ | `_save_rag_build_params()` | `config/app_settings.json` → `rag.time_limit/chunk_size/chunk_overlap` |
| RAG自動強化 | `_save_rag_enhance_settings()` | `config/app_settings.json` → `rag.auto_kg_update/hype_enabled/reranker_enabled` |
| 対象フォルダ | `_save_rag_folder_settings()` | `config/app_settings.json` → `rag.folder_path` |

#### 一般設定タブ
| 領域 | 保存コールバック | 保存先 |
|------|----------------|-------|
| AI状態確認 | なし（表示のみ） | — |
| メモリ & ナレッジ | `_save_memory_settings()` | `config/config.json` → `memory` |
| Web UI サーバー | `_save_webui_settings()` | `config/config.json` → `webui` |

### 2-6. 旧「画面最下部の保存ボタン」の扱い

- **mixAI**: 既存の `self.save_btn`（行12218）は**削除**する。各領域のボタンが代替。
- **cloudAI**: 既存の設定保存は各領域ボタンに分散。
- **RAG**: 既存の `self.save_settings_btn`（行8433）は**削除**する。各領域のボタンが代替。
- **一般設定**: 既存の保存ボタンは**削除**する。各領域のボタンが代替。

---

## 3. i18n完全対応規則（日英バイリンガル）

### 3-1. ルール

**【必須】v11.0.0 で新設する全てのUI表示テキスト（ラベル、ボタン、ツールチップ、プレースホルダー、ポップアップタイトル、ポップアップ本文、エラーメッセージ）は `t()` 関数経由で取得し、ja.json / en.json の両方にキーを定義すること。**

### 3-2. 禁止パターン

```python
# ❌ 禁止: ハードコード文字列
QMessageBox.warning(self, "エラー", f"保存に失敗: {e}")
QPushButton("再構築")
QLabel("実行LLM")

# ❌ 禁止: f-string内でのt()不使用
QMessageBox.warning(self, "Error", f"BIBLE create failed: {e}")

# ✅ 正しい: 全てt()経由
QMessageBox.warning(self, t('common.error'), t('desktop.ragTab.saveFailed', error=str(e)))
QPushButton(t('desktop.ragTab.rebuild'))
QLabel(t('desktop.ragTab.execLlm'))
```

### 3-3. i18n キー命名規則

```
{scope}.{tab/area}.{element}

scope    = common | desktop | web
tab/area = ragTab | cloudAI | localAI | mixAI | history | settings
element  = キャメルCase（例: execLlmHint, rebuildStarting）
```

### 3-4. v11.0.0 全追加キー一覧（日英対照）

#### common（全タブ共通）

| キー | ja | en |
|------|-----|-----|
| `common.send` | 送信 | Send |
| `common.cancel` | キャンセル | Cancel |
| `common.error` | エラー | Error |
| `common.success` | 成功 | Success |
| `common.confirm` | 確認 | Confirm |
| `common.close` | 閉じる | Close |
| `common.saveSection` | 保存 | Save |
| `common.saveSectionDone` | 保存完了 | Saved |
| `common.saveSectionFailed` | 保存失敗 | Save Failed |

#### desktop.tabs（タブ名）

| キー | ja | en |
|------|-----|-----|
| `desktop.tabs.mixAI` | 🔀 mixAI | 🔀 mixAI |
| `desktop.tabs.cloudAI` | ☁️ cloudAI | ☁️ cloudAI |
| `desktop.tabs.localAI` | 🖥️ localAI | 🖥️ localAI |
| `desktop.tabs.history` | 📜 History | 📜 History |
| `desktop.tabs.rag` | 🧠 RAG | 🧠 RAG |
| `desktop.tabs.settings` | ⚙️ 設定 | ⚙️ Settings |

#### desktop.cloudAI

| キー | ja | en |
|------|-----|-----|
| `desktop.cloudAI.continueSendMain` | 継続送信 | Continue |
| `desktop.cloudAI.continueSendMainTooltip` | 同一セッション内で追加質問を送信（トークン節約） | Send follow-up in the same session (saves tokens) |
| `desktop.cloudAI.sessionCaptured` | セッション確立: {id} | Session captured: {id} |
| `desktop.cloudAI.advancedSettings` | 詳細設定 | Advanced |
| `desktop.cloudAI.advancedSettingsTooltip` | Claude Code settings.json を開く | Open Claude Code settings.json |
| `desktop.cloudAI.modelManage` | 管理 | Manage |
| `desktop.cloudAI.modelManageTooltip` | モデルの追加・削除・並び替え | Add, remove, or reorder models |
| `desktop.cloudAI.mcpSettings` | MCP サーバー設定 | MCP Server Settings |
| `desktop.cloudAI.sendBlockTitle` | 送信ブロック | Send Blocked |
| `desktop.cloudAI.modelManageTitle` | モデル管理 | Manage Models |
| `desktop.cloudAI.modelManageAddName` | モデル名 | Model Name |
| `desktop.cloudAI.modelManageAddCmd` | コマンド | Command |
| `desktop.cloudAI.modelManageAdd` | 追加 | Add |
| `desktop.cloudAI.modelManageDelete` | 削除 | Delete |
| `desktop.cloudAI.modelManageBuiltinProtected` | ビルトインモデルは削除できません | Built-in models cannot be deleted |
| `desktop.cloudAI.settingsSaved` | cloudAI設定を保存しました | cloudAI settings saved |
| `desktop.cloudAI.settingsSaveFailed` | 保存失敗: {error} | Save failed: {error} |

#### desktop.localAI

| キー | ja | en |
|------|-----|-----|
| `desktop.localAI.mcpSettings` | MCP サーバー設定 | MCP Server Settings |
| `desktop.localAI.modelCapTools` | Tools | Tools |
| `desktop.localAI.modelCapVision` | Vision | Vision |
| `desktop.localAI.modelCapThinking` | Thinking | Thinking |
| `desktop.localAI.modelCapContext` | Context | Context |
| `desktop.localAI.deleteSelected` | 選択削除 | Delete Selected |
| `desktop.localAI.deleteConfirmTitle` | モデル削除確認 | Confirm Model Deletion |
| `desktop.localAI.deleteConfirmMsg` | {count}個のモデルを削除しますか？ | Delete {count} model(s)? |
| `desktop.localAI.settingsSaved` | localAI設定を保存しました | localAI settings saved |

#### desktop.common

| キー | ja | en |
|------|-----|-----|
| `desktop.common.bibleToggleTooltip` | BIBLE管理モードON: AIが自律的にBIBLEを作成・更新します | BIBLE mode ON: AI will autonomously create/update BIBLE |

#### desktop.history

| キー | ja | en |
|------|-----|-----|
| `desktop.history.tabTitle` | 📜 History | 📜 History |
| `desktop.history.searchPlaceholder` | チャット履歴を検索... | Search chat history... |
| `desktop.history.filterAll` | 全タブ | All Tabs |
| `desktop.history.sortNewest` | 新しい順 | Newest First |
| `desktop.history.sortOldest` | 古い順 | Oldest First |
| `desktop.history.copyMessage` | コピー | Copy |
| `desktop.history.quoteToTab` | 他タブに引用 | Quote to Tab |
| `desktop.history.noResults` | 該当するチャットが見つかりません | No matching chats found |
| `desktop.history.dateLabel` | 📅 {date} | 📅 {date} |

#### desktop.ragTab（旧 infoTab を置換・大幅拡張）

| キー | ja | en |
|------|-----|-----|
| `desktop.ragTab.chatSubTab` | チャット | Chat |
| `desktop.ragTab.settingsSubTab` | 設定 | Settings |
| `desktop.ragTab.inputPlaceholder` | RAGに質問する / コマンドを入力... | Ask RAG a question / enter a command... |
| `desktop.ragTab.addFiles` | 追加 | Add |
| `desktop.ragTab.stats` | 統計 | Stats |
| `desktop.ragTab.rebuild` | 再構築 | Rebuild |
| `desktop.ragTab.plan` | プラン | Plan |
| `desktop.ragTab.searching` | RAGコンテキストを検索中... | Searching RAG context... |
| `desktop.ragTab.rebuildStarting` | RAG構築を開始します... | Starting RAG build... |
| `desktop.ragTab.rebuildComplete` | RAG構築が完了しました: {nodes}ノード, {edges}エッジ, {communities}コミュニティ | RAG build complete: {nodes} nodes, {edges} edges, {communities} communities |
| `desktop.ragTab.rebuildFailed` | RAG構築に失敗しました: {error} | RAG build failed: {error} |
| `desktop.ragTab.quickStats` | 現在のRAG統計を表示して | Show current RAG statistics |
| `desktop.ragTab.quickRebuild` | RAGを再構築して | Rebuild RAG |
| `desktop.ragTab.quickPlan` | RAG構築プランを作成して | Create RAG build plan |
| `desktop.ragTab.chatAiSettings` | チャットAI設定 | Chat AI Settings |
| `desktop.ragTab.claudeModel` | Claude モデル | Claude Model |
| `desktop.ragTab.localLlmRoles` | ローカルLLMロール設定 | Local LLM Role Settings |
| `desktop.ragTab.execLlm` | 実行LLM（要約・KG構築） | Execution LLM (Summary / KG Build) |
| `desktop.ragTab.execLlmHint` | 推奨: 32B以上、長コンテキスト対応モデル | Recommended: 32B+, long context model |
| `desktop.ragTab.qualityLlm` | 品質チェックLLM（検証・分類） | Quality Check LLM (Validation / Classification) |
| `desktop.ragTab.qualityLlmHint` | 推奨: 8B程度の軽量高速モデル | Recommended: ~8B lightweight fast model |
| `desktop.ragTab.embeddingModel` | Embeddingモデル | Embedding Model |
| `desktop.ragTab.embeddingHint` | 推奨: embedding専用モデル | Recommended: embedding-dedicated model |
| `desktop.ragTab.refreshModels` | Ollamaモデル再読込 | Refresh Ollama Models |
| `desktop.ragTab.refreshSuccess` | {count}個のモデルを読み込みました | Loaded {count} model(s) |
| `desktop.ragTab.refreshFailed` | Ollamaモデル読込失敗: {error} | Failed to load Ollama models: {error} |
| `desktop.ragTab.autoEnhance` | RAG自動強化 | RAG Auto-Enhancement |
| `desktop.ragTab.autoKgUpdate` | 応答後に自動KG更新（LightRAG式） | Auto KG update after responses (LightRAG) |
| `desktop.ragTab.autoKgUpdateTip` | 各タブでのAI応答後にエンティティ間関係を自動抽出してKGに追加 | Automatically extract entity relations after AI responses and add to KG |
| `desktop.ragTab.hypeEnabled` | 仮想質問事前生成（HyPE） | Hypothetical Prompt Embeddings (HyPE) |
| `desktop.ragTab.hypeEnabledTip` | 保存されたfactに対して仮想質問を生成し検索精度を向上 | Generate hypothetical questions for saved facts to improve search accuracy |
| `desktop.ragTab.rerankerEnabled` | 検索結果リランキング | Search Result Reranking |
| `desktop.ragTab.rerankerEnabledTip` | RAG検索結果をLLMで再ランキングして最も関連性の高い結果を返す | Rerank RAG search results with LLM to return the most relevant results |
| `desktop.ragTab.autoEnhanceInfo` | 全機能はバックグラウンドで自動実行されます | All features run automatically in the background |
| `desktop.ragTab.buildParams` | RAG構築パラメータ | RAG Build Parameters |
| `desktop.ragTab.timeLimit` | 制限時間（分） | Time Limit (min) |
| `desktop.ragTab.chunkSize` | チャンクサイズ | Chunk Size |
| `desktop.ragTab.chunkOverlap` | オーバーラップ | Overlap |
| `desktop.ragTab.folderSettings` | 対象フォルダ | Target Folder |
| `desktop.ragTab.folderChange` | 変更 | Change |
| `desktop.ragTab.folderFileList` | ファイル一覧 | File List |
| `desktop.ragTab.saveFailed` | RAG設定の保存に失敗: {error} | Failed to save RAG settings: {error} |
| `desktop.ragTab.statusBar` | 📁 {files}ファイル ({size}) │ {ragStatus} │ 🧠 {nodes}ノード | 📁 {files} file(s) ({size}) │ {ragStatus} │ 🧠 {nodes} node(s) |
| `desktop.ragTab.addFilesTitle` | ファイルを追加 | Add Files |
| `desktop.ragTab.addFilesFilter` | サポートファイル ({ext}) | Supported files ({ext}) |
| `desktop.ragTab.fileSizeOverTitle` | ファイルサイズ超過 | File Size Exceeded |
| `desktop.ragTab.fileSizeExceeded` | {name}: {size}MB (最大{max}MB) | {name}: {size}MB (max {max}MB) |
| `desktop.ragTab.filesAdded` | {count}ファイルを追加しました | {count} file(s) added |
| `desktop.ragTab.planCreated` | RAG構築プランを作成しました | RAG build plan created |
| `desktop.ragTab.planFailed` | プラン作成に失敗: {error} | Failed to create plan: {error} |

#### desktop.mixAI（v11.0.0 追加分）

| キー | ja | en |
|------|-----|-----|
| `desktop.mixAI.phase13Saved` | Phase 1/3 設定を保存しました | Phase 1/3 settings saved |
| `desktop.mixAI.phase2Saved` | Phase 2 設定を保存しました | Phase 2 settings saved |
| `desktop.mixAI.phase35Saved` | Phase 3.5 設定を保存しました | Phase 3.5 settings saved |
| `desktop.mixAI.phase4Saved` | Phase 4 設定を保存しました | Phase 4 settings saved |
| `desktop.mixAI.ollamaSaved` | Ollama接続設定を保存しました | Ollama connection settings saved |
| `desktop.mixAI.residentSaved` | 常駐モデル設定を保存しました | Resident model settings saved |

#### desktop.settings（一般設定 v11.0.0 追加分）

| キー | ja | en |
|------|-----|-----|
| `desktop.settings.mcpFilesystem` | Filesystem (MCP) | Filesystem (MCP) |
| `desktop.settings.mcpGit` | Git (MCP) | Git (MCP) |
| `desktop.settings.mcpBrave` | Brave Search (MCP) | Brave Search (MCP) |
| `desktop.settings.memorySaved` | メモリ設定を保存しました | Memory settings saved |
| `desktop.settings.webuiSaved` | Web UI設定を保存しました | Web UI settings saved |
| `desktop.settings.memorySettingsGroup` | メモリ & ナレッジ | Memory & Knowledge |
| `desktop.settings.webuiSettingsGroup` | Web UI サーバー | Web UI Server |

### 3-5. ポップアップ・ダイアログのi18n規則

**【必須】全てのQMessageBox呼び出しはタイトル・本文ともt()経由。パラメータは名前付きプレースホルダを使用。**

```python
# ✅ 正しい: 全てi18n対応
QMessageBox.warning(
    self,
    t('common.error'),
    t('desktop.ragTab.saveFailed', error=str(e)[:200])
)

QMessageBox.information(
    self,
    t('common.success'),
    t('desktop.ragTab.rebuildComplete', nodes=842, edges=475, communities=28)
)

# ✅ 正しい: 確認ダイアログもi18n対応
reply = QMessageBox.question(
    self,
    t('common.confirm'),
    t('desktop.localAI.deleteConfirmMsg', count=len(selected)),
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
)
```

### 3-6. 既存ハードコード文字列の修正（v11.0.0 対象）

Implementation Spec に記載されたv11.0.0新規コード内で、以下のハードコード箇所をt()に修正:

| 箇所 | 旧（ハードコード） | 新（i18n） |
|------|-------------------|-----------|
| Phase 4 BIBLE失敗 | `f"BIBLE create failed: {e}"` | `t('desktop.mixAI.bibleCreateFailed', error=str(e))` |
| cloudAI settings.json | `"Error"` / `"Cannot open settings file:"` | `t('common.error')` / `t('desktop.cloudAI.settingsOpenFailed', error=str(e))` |

---

## 4. UI整合性ルール

### 4-1. カラーパレット

v11.0.0新設UIは既存のダークテーマに従う:

| 用途 | カラーコード | 使用例 |
|------|------------|-------|
| 背景（メイン） | `#0d1117` | チャットエリア背景 |
| 背景（カード） | `#1a1a2e` | QGroupBox背景、ステータスバー |
| ボーダー | `#333` | QGroupBox/入力フィールド枠線 |
| テキスト（通常） | `#e6edf3` | 通常のラベル・入力テキスト |
| テキスト（薄） | `#888` | ヒントテキスト、説明文 |
| アクセント（青） | `#00d4ff` | ステータス表示、リンク |
| アクセント（緑） | `#00ff88` | 保存ボタン、成功表示 |
| アクセント（橙） | `#ffa500` | BIBLEボタン、警告 |
| 無効状態 | `#555` | disabled テキスト |

### 4-2. フォントサイズ

| 用途 | サイズ |
|------|--------|
| チャットテキスト | 13px |
| ラベル（通常） | 12px (デフォルト) |
| ヒントテキスト | 10px |
| ボタン（小） | 11px |
| ステータスバー | 11px |

### 4-3. QGroupBoxスタイル（設定画面）

```python
SECTION_CARD_STYLE = """
    QGroupBox {
        background: #1a1a2e;
        border: 1px solid #333;
        border-radius: 8px;
        margin-top: 12px;
        padding: 16px 12px 8px 12px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: #00d4ff;
    }
"""
```

---

## 5. Implementation Spec v2 → v3 変更点サマリ

v2からv3への変更はこのガイドラインに基づく以下の通り:

| カテゴリ | 変更内容 | 影響範囲 |
|---------|---------|---------|
| NoScrollウィジェット | 全 `QComboBox()` → `NoScrollComboBox()` | Phase 2, 3, 5, 6 の全コード例 |
| NoScrollウィジェット | 全 `QSpinBox()` → `NoScrollSpinBox()` | Phase 6 RAG設定 |
| NoScrollウィジェット | `src/widgets/no_scroll_widgets.py` 新設 | 新規ファイル追加 |
| 領域別保存ボタン | `create_section_save_button()` 追加 | 全設定サブタブ |
| 領域別保存ボタン | 画面最下部の単一保存ボタン削除 | mixAI, RAG, 一般設定 |
| i18n | 全新規テキストにja/enキー定義 | i18nセクション全面更新 |
| i18n | QMessageBox全箇所をt()化 | 全Phase |
| 新規ファイル | `src/widgets/no_scroll_widgets.py` | — |
| 新規ファイル | `src/widgets/section_save_button.py` | — |
