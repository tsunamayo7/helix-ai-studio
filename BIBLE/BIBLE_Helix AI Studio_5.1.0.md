# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 5.1.0
**アプリケーションバージョン**: 5.1.0 "Helix AI Studio - UI強化・ファイル添付対応・設定永続化修正"
**作成日**: 2026-02-05
**最終更新**: 2026-02-05
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v5.1.0 更新履歴 (2026-02-05)

### 主な変更点

**概要**:
v5.1.0 はUI/UX改善とバグ修正に焦点を当てたアップデート。ユーザーからのフィードバックに基づき、以下を実装:

1. **mixAIツール実行ログ表示改善**: ウィンドウ拡張時に複数行表示可能に
2. **mixAIチャット入力強化**: 上下キーカーソル移動、ファイル添付ボタン群追加
3. **soloAIファイル添付機能修正**: 動作しないボタンを修正、添付ファイルバー追加
4. **mixAI設定永続化修正**: PyInstaller対応でユーザーホームディレクトリに保存
5. **画像添付対応**: 添付ファイルバーでサムネイル表示、×ボタンで個別削除可能

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | ツール実行ログが1行しか表示されない | `setMaximumHeight(150)`を削除し、`SizePolicy.Expanding`に変更 | ウィンドウ拡張で行数増加 |
| 2 | mixAIチャット入力のカーソル移動 | `MixAIEnhancedInput`クラス追加、上下キーで先頭/末尾移動 | 上キー→先頭、下キー→末尾 |
| 3 | mixAIにファイル添付ボタンがない | soloAIと同様のボタン群を追加（添付・履歴・スニペット・追加） | 画像も添付可能 |
| 4 | soloAIのファイル添付が機能しない | `attach_btn.clicked`シグナル接続追加、添付バー追加 | ファイル選択ダイアログが開く |
| 5 | mixAI設定が保存されない | 保存先を`~/.helix_ai_studio/`に変更（PyInstaller対応） | 次回起動時に設定が復元 |

---

## ファイル変更一覧 (v5.1.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | バージョン 5.0.0 → 5.1.0、APP_DESCRIPTION更新 |
| `src/tabs/helix_orchestrator_tab.py` | 入力強化クラス追加、ツールログ表示改善、設定永続化修正 |
| `src/tabs/claude_tab.py` | 添付ファイルウィジェット追加、`attach_btn`シグナル接続追加 |
| `BIBLE/BIBLE_Helix AI Studio_5.1.0.md` | 本ファイル追加 |

---

## UI改善詳細 (v5.1.0)

### ツール実行ログ改善

```python
# 変更前
self.tool_log_tree.setMaximumHeight(150)

# 変更後
self.tool_log_tree.setMinimumHeight(80)
self.tool_log_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
self.tool_log_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
```

### MixAIEnhancedInput

```python
class MixAIEnhancedInput(QPlainTextEdit):
    """mixAI用強化入力ウィジェット"""
    file_dropped = pyqtSignal(list)

    def keyPressEvent(self, event):
        key = event.key()

        # 上キー: 先頭行 → テキスト先頭へ
        if key == Qt.Key.Key_Up:
            cursor = self.textCursor()
            if cursor.block() == self.document().firstBlock():
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
                return

        # 下キー: 最終行 → テキスト末尾へ
        if key == Qt.Key.Key_Down:
            cursor = self.textCursor()
            if cursor.block() == self.document().lastBlock():
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                return

        super().keyPressEvent(event)
```

### MixAIAttachmentBar

```python
class MixAIAttachmentBar(QWidget):
    """mixAI用添付ファイルバー"""
    attachments_changed = pyqtSignal(list)

    FILE_ICONS = {
        ".py": "🐍", ".png": "🖼️", ".jpg": "🖼️", ...
    }

    def add_files(self, filepaths: List[str]):
        """ファイルを追加（×ボタン付きウィジェット）"""

    def remove_file(self, filepath: str):
        """ファイルを削除"""

    def clear_all(self):
        """全ファイル削除"""
```

---

## 設定永続化 (v5.1.0)

### 問題

v5.0.0では設定を `config/tool_orchestrator.json` に保存していたが、PyInstallerでパッケージ化すると一時ディレクトリ（`_MEIPASS`）に展開されるため、アプリ終了時に設定が消失。

### 解決策

```python
def _get_config_path(self) -> Path:
    """設定ファイルのパスを取得（PyInstaller対応）"""
    # ユーザーのホームディレクトリに保存
    config_dir = Path.home() / ".helix_ai_studio"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "tool_orchestrator.json"
```

### 旧設定の自動移行

```python
def _load_config(self):
    config_path = self._get_config_path()
    if config_path.exists():
        # 新パスから読み込み
        ...
    else:
        # 旧パスからの移行を試みる
        old_config_path = Path(__file__).parent.parent.parent / "config" / "tool_orchestrator.json"
        if old_config_path.exists():
            # 読み込んで新パスにコピー
            self.config = OrchestratorConfig.from_dict(data)
            self._save_config()
```

---

## 新規追加ボタン (mixAIタブ)

| ボタン | 機能 |
|--------|------|
| 📎 ファイルを添付 | QFileDialogでファイル選択、添付バーに表示 |
| 📜 履歴から引用 | 過去の会話履歴を検索・挿入 |
| 📋 スニペット ▼ | 保存済みスニペットをメニュー表示 |
| ➕ 追加 | 新規スニペットを登録 |

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | 84.5 MB |
| exe (root) | `HelixAIStudio.exe` | 84.5 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_5.1.0.md` | 本ファイル |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude CLI / Claude API / Ollama
- **Database**: SQLite (ナレッジストア)
- **Embedding**: qwen3-embedding:4b
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## v5.0.0からの改善

- [x] ツール実行ログ表示改善（ウィンドウ拡張対応）
- [x] mixAIチャット入力強化（カーソル移動・ファイル添付）
- [x] soloAIファイル添付機能修正
- [x] mixAI設定永続化修正（PyInstaller対応）
- [x] 添付ファイルバー（×ボタン個別削除対応）

---

## 参考文献

- BIBLE_Helix AI Studio_5.0.0.md (前バージョン)
- 修正依頼書（修正.md）
