# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 5.2.0
**アプリケーションバージョン**: 5.2.0 "Helix AI Studio - ユニペット削除対応・×ボタン視認性向上・ファイル内容読み込み修正"
**作成日**: 2026-02-05
**最終更新**: 2026-02-05
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v5.2.0 更新履歴 (2026-02-05)

### 主な変更点

**概要**:
v5.2.0 はユーザーからのフィードバックに基づく機能改善とバグ修正を実施。以下を実装:

1. **ユニペット削除機能追加**: アプリ内からユニペットファイルの削除が可能に
2. **×ボタン視認性向上**: 添付ファイルの削除ボタンを赤背景で常時表示
3. **ファイル内容読み込み改善**: Claude CLI実行時に添付ファイルの内容をプロンプトに含める
4. **DATA_DIR/UNIPET_DIRデフォルト値追加**: PyInstaller対応の堅牢なパス設定

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | ユニペットの削除ができない | `SnippetManager.delete()`に`delete_file`パラメータ追加 | 右クリックメニューからユニペット削除可能 |
| 2 | 添付ファイルの×ボタンが見えない | スタイルシートを赤背景・白文字に変更 | ×ボタンが常時赤色で視認可能 |
| 3 | ファイル閲覧指示が実行されない | `claude_executor.py`でファイル内容をプロンプトに埋め込む | ファイル参照指示が正しく動作 |
| 4 | DATA_DIR/UNIPET_DIR未定義 | `snippet_manager.py`にデフォルト値追加 | PyInstaller/開発環境両方で動作 |

---

## ファイル変更一覧 (v5.2.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | バージョン 5.1.1 → 5.2.0、APP_DESCRIPTION更新 |
| `src/claude/snippet_manager.py` | DATA_DIR/UNIPET_DIRデフォルト値追加、delete()にdelete_fileパラメータ追加 |
| `src/tabs/helix_orchestrator_tab.py` | ×ボタンスタイル改善、ユニペット削除対応 |
| `src/tabs/claude_tab.py` | ユニペット削除対応 |
| `src/backends/claude_executor.py` | 添付ファイル内容をプロンプトに含める |
| `BIBLE/BIBLE_Helix AI Studio_5.2.0.md` | 本ファイル追加 |

---

## コード変更詳細 (v5.2.0)

### 1. ユニペット削除機能

**snippet_manager.py**:
```python
def delete(self, snippet_id: str, delete_file: bool = False) -> bool:
    """Delete snippet

    Args:
        snippet_id: 削除するスニペットのID
        delete_file: Trueの場合、ユニペットファイルも削除する (v5.2.0)
    """
    for i, s in enumerate(self.snippets):
        if s["id"] == snippet_id:
            if s.get("source") == "unipet":
                if delete_file:
                    file_path = Path(s.get("file_path", ""))
                    if file_path.exists():
                        file_path.unlink()
                    del self.snippets[i]
                    return True
                else:
                    return False
            del self.snippets[i]
            self._save()
            return True
    return False
```

### 2. ×ボタン視認性向上

**helix_orchestrator_tab.py**:
```python
remove_btn.setStyleSheet("""
    QPushButton {
        background-color: #e53e3e;    /* 赤背景 */
        color: #ffffff;               /* 白文字 */
        border: 2px solid #fc8181;    /* ピンク境界線 */
        border-radius: 10px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #c53030;    /* ホバー時は暗い赤 */
    }
""")
```

### 3. ファイル内容読み込み

**claude_executor.py**:
```python
# プロンプト構築（添付ファイルがある場合はファイル内容を含める v5.2.0）
full_prompt = prompt
if attached_files:
    file_contents = []
    for f in attached_files:
        if os.path.exists(f):
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']:
                file_contents.append(f"[画像ファイル: {f}]")
            else:
                with open(f, 'r', encoding='utf-8', errors='replace') as fp:
                    content = fp.read()
                if len(content) > 50000:
                    content = content[:50000] + "\n\n... (ファイルが大きいため省略されました)"
                file_contents.append(f"--- ファイル: {f} ---\n{content}\n--- ファイル終了 ---")
    if file_contents:
        full_prompt = "\n\n".join(file_contents) + "\n\n" + prompt
```

### 4. DATA_DIR/UNIPET_DIRデフォルト値

**snippet_manager.py**:
```python
import sys
from pathlib import Path

def _get_default_app_dir() -> Path:
    """アプリケーションディレクトリを取得"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent  # PyInstaller
    else:
        return Path(__file__).parent.parent.parent  # 開発時

_APP_DIR = _get_default_app_dir()
DATA_DIR = _APP_DIR / "data"
UNIPET_DIR = _APP_DIR / "ユニペット"
```

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | 84.5 MB |
| exe (root) | `HelixAIStudio.exe` | 84.5 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_5.2.0.md` | 本ファイル |

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

## v5.1.0からの改善

- [x] ユニペット削除機能追加（ファイル削除対応）
- [x] ×ボタン視認性向上（赤背景・白文字）
- [x] ファイル内容読み込み（Claude CLI実行時）
- [x] DATA_DIR/UNIPET_DIRデフォルト値追加

---

## 既知の制限事項

1. **画像ファイル**: 現時点ではパス参照のみ（base64埋め込みは未対応）
2. **大きなファイル**: 50KB超のファイルは先頭50KBのみ読み込み

---

## 参考文献

- BIBLE_Helix AI Studio_5.1.0.md (前バージョン)
- 修正指示文.md
