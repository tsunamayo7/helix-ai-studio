# Helix AI Studio — デスクトップ版 セッション・チャット履歴UI
## Claude Code CLI 実行指示書（Sonnet 4.5用）

**目的**: soloAIタブとmixAIタブに、Web版ChatListPanelと同等のチャット履歴サイドパネルをPyQt6で追加する。

---

## 前提: 既存インフラ

### データ層（既に存在）
- `src/web/chat_store.py` — SQLiteベースのチャットCRUD（Web UIで使用中）
  - `list_chats(tab=)` → チャット一覧
  - `create_chat(tab=, context_mode=)` → 新規チャット
  - `get_chat(chat_id)` → チャット詳細
  - `get_messages(chat_id)` → メッセージ一覧
  - `add_message(chat_id, role, content)` → メッセージ追加
  - `update_chat_title(chat_id, title)` → タイトル更新
  - `auto_generate_title(chat_id)` → 最初のメッセージからタイトル自動生成
  - `delete_chat(chat_id)` → チャット削除
  - `build_context_for_prompt(chat_id, prompt)` → コンテキストモード別プロンプト構築
  - `update_context_mode(chat_id, mode)` → single/session/full モード変更
- `src/data/session_manager.py` — セッション管理（ワークフロー状態）
- `src/data/chat_history_manager.py` — チャット履歴保存

### UI層（既に存在）
- soloAIタブ（`src/tabs/claude_tab.py`）に「新規セッション」ボタンあり
- mixAIタブ（`src/tabs/helix_orchestrator_tab.py`）にセッション管理あり
- Web版の `frontend/src/components/ChatListPanel.jsx` — 参考実装

### 共有方針
**Web版と同じ `ChatStore`（SQLite DB）を共有する。** これにより:
- デスクトップで作成したチャットがWeb UIでも閲覧可能
- Web UIで作成したチャットがデスクトップでも閲覧可能
- Cross-Device Sync のコンセプトに合致

---

## 実装内容

### 1. 新規ファイル: `src/widgets/chat_history_panel.py`

PyQt6サイドパネルウィジェット。以下の機能を持つ:

```
┌─────────────────────────┐
│ 📋 チャット履歴    [✕]  │
│─────────────────────────│
│ [🔍 検索...]            │
│ [＋ 新しいチャット]      │
│─────────────────────────│
│ ● タブフィルタ           │
│   [全て] [soloAI] [mixAI]│
│─────────────────────────│
│ ▼ 今日                  │
│ ┌─────────────────────┐ │
│ │ 📝 チャットタイトル    │ │
│ │ mixAI · 14:30 · 5msg  │ │
│ │ [✏ 名前変更] [🗑 削除] │ │
│ └─────────────────────┘ │
│ ┌─────────────────────┐ │
│ │ 📝 APIの設計について  │ │
│ │ soloAI · 12:15 · 3msg │ │
│ └─────────────────────┘ │
│─────────────────────────│
│ ▼ 昨日                  │
│ ...                     │
│─────────────────────────│
│ ▼ 今週                  │
│ ...                     │
└─────────────────────────┘
```

#### UI仕様

1. **パネル種別**: `QDockWidget` で左側にドッキング（フロート可能、閉じるボタンあり）
2. **サイズ**: 幅280px固定、高さはウィンドウに追従
3. **タブフィルタ**: QButtonGroup で「全て」「soloAI」「mixAI」の3ボタン。選択中のタブでフィルタ
4. **チャット一覧**: QListWidget または QScrollArea + カスタムウィジェット
5. **日付グループ**: 「今日」「昨日」「今週」「それ以前」でグループ化
6. **各チャットアイテム**:
   - タイトル（クリックでチャット切替）
   - タブ種別バッジ（soloAI=シアン / mixAI=パープル）
   - 最終更新時刻
   - メッセージ数
   - 右クリックコンテキストメニュー: 名前変更 / 削除
7. **検索**: QLineEdit でタイトルのインクリメンタル検索（フロントエンド側フィルタ）
8. **新しいチャット**: ボタンクリックで新規チャットを作成し、アクティブタブのチャットをリセット
9. **選択状態**: 現在アクティブなチャットをハイライト表示

#### シグナル

```python
class ChatHistoryPanel(QDockWidget):
    """チャット履歴サイドパネル"""

    # シグナル定義
    chatSelected = pyqtSignal(str, str)    # (chat_id, tab) — チャット選択時
    newChatRequested = pyqtSignal(str)     # (tab) — 新規チャット要求
    chatDeleted = pyqtSignal(str)          # (chat_id) — チャット削除時

    def __init__(self, parent=None):
        ...

    def refresh_chat_list(self, tab_filter: str = None):
        """ChatStoreからチャット一覧を再取得して表示"""
        ...

    def set_active_chat(self, chat_id: str):
        """アクティブチャットのハイライトを更新"""
        ...

    def set_tab_filter(self, tab: str):
        """タブフィルタを変更（外部からの呼出し用）"""
        ...
```

#### スタイリング

既存のCyberpunk Minimalテーマに合わせる:
- 背景: `#0a0e14`（メインと同じダーク背景）
- チャットアイテム: `#111827` 背景、ホバー時 `#1f2937`、選択時 `#064e3b`（エメラルド系）
- テキスト: グレー系、タイトルは明るめ
- タブバッジ: soloAI=`#0891b2`、mixAI=`#7c3aed`

### 2. `src/main_window.py` の修正

```python
from .widgets.chat_history_panel import ChatHistoryPanel

class MainWindow(QMainWindow):
    def __init__(self):
        ...
        # チャット履歴パネル
        self.chat_history_panel = ChatHistoryPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.chat_history_panel)
        self.chat_history_panel.hide()  # 初期状態は非表示

        # シグナル接続
        self.chat_history_panel.chatSelected.connect(self._on_chat_selected)
        self.chat_history_panel.newChatRequested.connect(self._on_new_chat)
        self.chat_history_panel.chatDeleted.connect(self._on_chat_deleted)

    def _on_chat_selected(self, chat_id: str, tab: str):
        """チャット選択時: 該当タブに切替 → チャット読み込み"""
        # タブ切替
        tab_index = 0 if tab == 'mixAI' else 1  # mixAI=0, soloAI=1
        self.tab_widget.setCurrentIndex(tab_index)
        # 該当タブにチャット読み込みを通知
        current_tab = self._get_tab_by_name(tab)
        if current_tab and hasattr(current_tab, 'load_chat_from_history'):
            current_tab.load_chat_from_history(chat_id)

    def _on_new_chat(self, tab: str):
        """新規チャット作成"""
        current_tab = self._get_tab_by_name(tab)
        if current_tab and hasattr(current_tab, 'start_new_session'):
            current_tab.start_new_session()

    def _on_chat_deleted(self, chat_id: str):
        """チャット削除後の処理"""
        # 現在表示中のチャットが削除された場合、新規セッションに切替
        ...

    def toggle_chat_history(self):
        """チャット履歴パネルの表示/非表示切替"""
        if self.chat_history_panel.isVisible():
            self.chat_history_panel.hide()
        else:
            # 現在のタブに合わせてフィルタ
            tab_name = 'soloAI' if self.tab_widget.currentIndex() == 1 else 'mixAI'
            self.chat_history_panel.set_tab_filter(tab_name)
            self.chat_history_panel.refresh_chat_list()
            self.chat_history_panel.show()
```

### 3. soloAIタブ（`src/tabs/claude_tab.py`）の修正

#### 3.1 履歴ボタン追加

既存の「新規セッション」ボタンの横に「📋 履歴」ボタンを追加:

```python
self.history_btn = QPushButton("📋 履歴")
self.history_btn.setToolTip("チャット履歴を表示")
self.history_btn.clicked.connect(self._toggle_history_panel)
```

#### 3.2 ChatStore統合

soloAIタブでのClaude CLI実行時に、ChatStoreにもメッセージを保存する:

```python
from src.web.chat_store import ChatStore

class ClaudeTab:
    def __init__(self):
        ...
        self._chat_store = ChatStore()
        self._active_chat_id = None  # 現在のチャットID

    def start_new_session(self):
        """新規セッション開始"""
        # 既存のセッション管理に加え、ChatStoreにもチャット作成
        chat = self._chat_store.create_chat(tab="soloAI", context_mode="session")
        self._active_chat_id = chat["id"]
        self._clear_chat_display()
        # 履歴パネルに通知
        self._notify_history_refresh()

    def _on_execution_complete(self, prompt, response):
        """実行完了時にChatStoreに保存"""
        if self._active_chat_id:
            self._chat_store.add_message(self._active_chat_id, "user", prompt)
            self._chat_store.add_message(self._active_chat_id, "assistant", response)
            # 最初のメッセージならタイトル自動生成
            chat = self._chat_store.get_chat(self._active_chat_id)
            if chat and chat["message_count"] <= 2:
                self._chat_store.auto_generate_title(self._active_chat_id)

    def load_chat_from_history(self, chat_id: str):
        """履歴パネルからチャットを読み込み"""
        self._active_chat_id = chat_id
        messages = self._chat_store.get_messages(chat_id)
        self._clear_chat_display()
        for msg in messages:
            self._display_message(msg["role"], msg["content"])
```

#### 3.3 _toggle_history_panel

```python
def _toggle_history_panel(self):
    """メインウィンドウの履歴パネルを開閉"""
    main_window = self.window()
    if hasattr(main_window, 'toggle_chat_history'):
        main_window.toggle_chat_history()
```

### 4. mixAIタブ（`src/tabs/helix_orchestrator_tab.py`）の修正

soloAIと同様に:
- 「📋 履歴」ボタン追加
- ChatStore統合（tab="mixAI"で保存）
- `load_chat_from_history(chat_id)` メソッド追加

### 5. ChatStoreの軽微な修正

`src/web/chat_store.py` が `src/web/` 内にあるが、デスクトップからも参照する。
importパスの問題がある場合、`chat_store.py` を `src/data/` にコピーするか、
相対importを絶対importに修正する。

最小限の修正で済むよう、既存の `src/web/chat_store.py` をそのまま使用し、
デスクトップからは `from src.web.chat_store import ChatStore` でimportする。

---

## テスト項目

| # | テスト | 期待結果 |
|---|-------|---------|
| 1 | soloAIタブの「📋 履歴」ボタン | サイドパネルが開閉する |
| 2 | 新しいチャットボタン | 新規チャットが作成され一覧に追加 |
| 3 | チャット選択 | 選択したチャットのメッセージが表示領域に復元 |
| 4 | チャットタイトル | 最初の送信後にタイトルが自動生成 |
| 5 | タイトル編集 | 右クリック→名前変更でタイトル変更可能 |
| 6 | チャット削除 | 右クリック→削除で確認ダイアログ後に削除 |
| 7 | タブフィルタ | soloAI/mixAI/全てでフィルタが切り替わる |
| 8 | 日付グループ | 今日/昨日/今週/それ以前で正しくグループ化 |
| 9 | Web UIとの共有 | デスクトップで作成→Web UIで閲覧可能（逆も） |
| 10 | mixAIタブ | soloAIと同等の履歴機能が動作 |
| 11 | 検索 | テキスト入力でチャット一覧がフィルタ |
| 12 | パネル表示/非表示 | 状態が保持される（次回起動時は非表示） |

---

## 注意事項

1. **ChatStoreの共有**: Web版と同じSQLite DB（`data/web_chats.db`）を使用する。SQLiteの同時アクセスは読み取り並行OK、書き込みはロックで直列化されるため問題ない。
2. **既存のセッション管理**: `session_manager.py` / `history_manager.py` は既存のワークフロー状態管理に引き続き使用。ChatStoreはチャット履歴の永続化専用。両方を並行して使用する。
3. **スタイリング**: 既存の `_apply_stylesheet()` のCyberpunk Minimalテーマに合わせる。独自のスタイルを直書きせず、既存のカラー変数を参照。
4. **i18n対応**: v9.6.0のi18n基盤が導入済みの場合は `t()` を使用。未導入なら日本語ハードコードでOK（後でt()に置換可能）。

---

## CLI実行コマンド

```powershell
claude -p "以下の実装を行ってください。

【目的】
デスクトップ版（PyQt6）にチャット履歴サイドパネルを追加する。
Web版の ChatListPanel.jsx と同等の機能を PyQt6 QDockWidget で実現する。
データ層は既存の src/web/chat_store.py (ChatStore) を共有し、デスクトップとWeb UIで同じチャット履歴を閲覧・操作できるようにする。

【実装手順】

1. src/widgets/chat_history_panel.py を新規作成
   - QDockWidget ベースの左サイドパネル
   - 幅280px、既存Cyberpunk Minimalテーマに準拠
   - ChatStore (src/web/chat_store.py) をimportしてチャットCRUD
   - 機能: チャット一覧（日付グループ化: 今日/昨日/今週/それ以前）、タブフィルタ（全て/soloAI/mixAI）、検索フィルタ、新規チャット、チャット選択・切替、右クリック→名前変更/削除
   - シグナル: chatSelected(str, str), newChatRequested(str), chatDeleted(str)
   - set_active_chat(chat_id) でハイライト更新
   - refresh_chat_list(tab_filter) でChatStoreから再取得・表示

2. src/main_window.py を修正
   - ChatHistoryPanel を左ドッキングウィジェットとして追加（初期非表示）
   - シグナル接続: chatSelected → タブ切替+チャット読み込み, newChatRequested → 新規セッション, chatDeleted → 表示更新
   - toggle_chat_history() メソッド追加
   - タブ切替時に自動でフィルタ同期

3. src/tabs/claude_tab.py (soloAIタブ) を修正
   - 既存の「新規セッション」ボタンの横に「📋 履歴」ボタン追加 → main_window.toggle_chat_history() を呼ぶ
   - ChatStore統合: 実行完了時に add_message() でユーザー入力と応答を保存
   - _active_chat_id を管理し、新規セッション時に create_chat(tab='soloAI') で作成
   - 最初のメッセージ送信後にauto_generate_title()でタイトル自動生成
   - load_chat_from_history(chat_id) メソッド追加: ChatStoreからメッセージ取得→チャット表示領域に復元

4. src/tabs/helix_orchestrator_tab.py (mixAIタブ) を修正
   - soloAIと同様: 「📋 履歴」ボタン追加、ChatStore統合（tab='mixAI'）
   - 3Phase実行完了時の最終結果をChatStoreに保存
   - load_chat_from_history(chat_id) メソッド追加

【重要な注意】
- ChatStoreのimport: from src.web.chat_store import ChatStore（相対importで問題が出る場合は from ..web.chat_store import ChatStore を試す）
- SQLite DBパス: ChatStoreのデフォルト（data/web_chats.db等）をそのまま使用
- 既存のセッション管理（session_manager, history_manager）は変更しない。ChatStoreは追加のチャット永続化層として並行動作
- スタイリング: 既存の _apply_stylesheet() テーマに合わせる。背景 #0a0e14、チャットアイテム #111827、ホバー #1f2937、選択 #064e3b、soloAIバッジ #0891b2、mixAIバッジ #7c3aed
- チャットアイテムの日付グループ化: 今日/昨日/今週/それ以前の4グループ
- 右クリックメニュー: QMenu で「名前変更」「削除」
- 削除時は QMessageBox.question で確認ダイアログ
- 名前変更は QInputDialog.getText で入力
- setToolTip を全UIに付与（自己文書化UI哲学）

【確認事項】
- まず src/web/chat_store.py を読んでChatStoreのAPIを確認してから実装に着手すること
- soloAIタブ（claude_tab.py）の既存のセッション管理コードを読んで、_active_chat_id の管理場所を特定すること
- mixAIタブの実行完了ハンドラを特定し、適切な場所にChatStore保存を追加すること" --dangerously-skip-permissions
```
