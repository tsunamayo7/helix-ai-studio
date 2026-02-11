# -*- coding: utf-8 -*-
"""Snippet manager for quick text insertion (v2.7.1: ユニペット対応)
v3.7.0: Helix AI Studio用に依存関係を修正
v5.2.0: DATA_DIR/UNIPET_DIRのデフォルト値追加、ユニペットファイル削除機能追加
"""

import uuid
import re
import logging
import json
import sys
import os
from pathlib import Path
from typing import List, Optional

# デフォルトディレクトリ設定（PyInstaller対応）
def _get_default_app_dir() -> Path:
    """アプリケーションディレクトリを取得"""
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた場合: exeと同じディレクトリ
        return Path(sys.executable).parent
    else:
        # 開発時: プロジェクトルート（このファイルの3階層上）
        return Path(__file__).parent.parent.parent

_APP_DIR = _get_default_app_dir()
DATA_DIR = _APP_DIR / "data"
UNIPET_DIR = _APP_DIR / "ユニペット"


def load_json(path: Path, default=None):
    """JSONファイルを読み込む"""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load JSON from {path}: {e}")
    return default if default is not None else {}


def save_json(path: Path, data):
    """JSONファイルに保存"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save JSON to {path}: {e}")


class SnippetManager:
    """Manage text snippets for quick insertion

    v2.7.1: ユニペットフォルダからtxtファイルを読み込む機能を追加
    v2.7.2: 設定でユニペット機能を切り替え可能に
    """

    def __init__(self, data_dir: Path = None, unipet_dir: Path = None, unipet_enabled: bool = True):
        self.data_dir = data_dir or DATA_DIR
        self.unipet_dir = unipet_dir or UNIPET_DIR
        self.snippets_file = self.data_dir / "snippets.json"
        self.snippets: List[dict] = []
        self._unipet_enabled = unipet_enabled
        self._load()

    def set_unipet_enabled(self, enabled: bool):
        """ユニペット機能の有効/無効を設定して再読み込み"""
        self._unipet_enabled = enabled
        self.reload()

    def _load(self):
        """Load snippets from unipet folder (txt files)"""
        self.snippets = []

        # ユニペットが有効な場合のみフォルダから読み込む
        unipet_snippets = []
        if self._unipet_enabled:
            unipet_snippets = self._load_from_unipet_folder()
            self.snippets.extend(unipet_snippets)

        # JSONファイルからも追加で読み込む（後方互換性のため）
        data = load_json(self.snippets_file, {})
        json_snippets = data.get("snippets", [])

        # IDの重複を避けるため、既存のIDをチェック
        existing_ids = {s["id"] for s in self.snippets}
        for snippet in json_snippets:
            if snippet.get("id") not in existing_ids:
                self.snippets.append(snippet)

        if self._unipet_enabled:
            logging.info(f"Loaded {len(self.snippets)} snippets ({len(unipet_snippets)} from unipet folder)")
        else:
            logging.info(f"Loaded {len(self.snippets)} snippets (unipet disabled)")

    def _load_from_unipet_folder(self) -> List[dict]:
        """ユニペットフォルダからtxtファイルを読み込む"""
        snippets = []

        if not self.unipet_dir.exists():
            logging.info(f"Unipet folder does not exist: {self.unipet_dir}")
            return snippets

        # txtファイルを検索（_で始まるファイルは除外）
        for txt_file in sorted(self.unipet_dir.glob("*.txt")):
            if txt_file.name.startswith("_"):
                continue  # テンプレートファイルなどは除外

            try:
                snippet = self._parse_unipet_file(txt_file)
                if snippet:
                    snippets.append(snippet)
                    logging.debug(f"Loaded unipet: {snippet['name']}")
            except Exception as e:
                logging.error(f"Failed to parse unipet file {txt_file}: {e}")

        return snippets

    def _parse_unipet_file(self, file_path: Path) -> Optional[dict]:
        """ユニペットファイルをパースしてスニペットデータを生成

        フォーマット:
        名前: スニペット名
        カテゴリ: カテゴリ名
        ショートカット: Ctrl+1

        ---内容ここから---
        実際の内容
        ---内容ここまで---
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # UTF-8以外のエンコーディングを試行
            try:
                content = file_path.read_text(encoding="cp932")
            except Exception:
                logging.error(f"Cannot decode file: {file_path}")
                return None

        # メタデータをパース
        name = None
        category = ""
        shortcut = ""
        snippet_content = ""

        # 名前の抽出
        name_match = re.search(r'^名前[:：]\s*(.+)$', content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            # ファイル名をデフォルト名として使用
            name = file_path.stem

        # カテゴリの抽出
        category_match = re.search(r'^カテゴリ[:：]\s*(.+)$', content, re.MULTILINE)
        if category_match:
            category = category_match.group(1).strip()

        # ショートカットの抽出
        shortcut_match = re.search(r'^ショートカット[:：]\s*(.+)$', content, re.MULTILINE)
        if shortcut_match:
            shortcut = shortcut_match.group(1).strip()

        # 内容の抽出（---内容ここから--- と ---内容ここまで--- の間）
        content_match = re.search(
            r'---内容ここから---\s*\n(.*?)\n---内容ここまで---',
            content,
            re.DOTALL
        )
        if content_match:
            snippet_content = content_match.group(1)
        else:
            # マーカーがない場合は、メタデータ行以外の全てを内容とする
            lines = content.split('\n')
            content_lines = []
            for line in lines:
                if not re.match(r'^(名前|カテゴリ|ショートカット)[:：]', line):
                    content_lines.append(line)
            snippet_content = '\n'.join(content_lines).strip()

        if not name:
            return None

        # ファイルパスからユニークなIDを生成
        snippet_id = f"unipet_{file_path.stem}_{hash(str(file_path)) % 100000}"

        return {
            "id": snippet_id,
            "name": name,
            "content": snippet_content,
            "category": category,
            "shortcut": shortcut,
            "source": "unipet",  # ソースを識別
            "file_path": str(file_path),  # 元ファイルパス
        }

    def reload(self):
        """スニペットを再読み込み"""
        self._load()

    def _save(self):
        """Save snippets to file (JSON形式のスニペットのみ保存)"""
        # ユニペットソース以外のスニペットのみ保存
        json_snippets = [s for s in self.snippets if s.get("source") != "unipet"]
        save_json(self.snippets_file, {"snippets": json_snippets})

    def _get_default_snippets(self) -> List[dict]:
        """Get default snippets (v2.7.1: 空を返す)"""
        return []

    def get_all(self) -> List[dict]:
        """Get all snippets"""
        return self.snippets.copy()

    def get_by_id(self, snippet_id: str) -> Optional[dict]:
        """Get snippet by ID"""
        for s in self.snippets:
            if s["id"] == snippet_id:
                return s.copy()
        return None

    def get_by_shortcut(self, shortcut: str) -> Optional[dict]:
        """Get snippet by shortcut"""
        for s in self.snippets:
            if s.get("shortcut") == shortcut:
                return s.copy()
        return None

    def get_by_category(self, category: str) -> List[dict]:
        """Get snippets by category"""
        if not category:
            return self.snippets.copy()
        return [s.copy() for s in self.snippets if s.get("category") == category]

    def get_categories(self) -> List[str]:
        """Get list of categories"""
        categories = set()
        for s in self.snippets:
            if s.get("category"):
                categories.add(s["category"])
        return sorted(categories)

    def add(self, name: str, content: str, category: str = "", shortcut: str = "") -> dict:
        """Add new snippet (JSONファイルに追加)"""
        snippet = {
            "id": str(uuid.uuid4()),
            "name": name,
            "content": content,
            "category": category,
            "shortcut": shortcut,
            "source": "json",
        }
        self.snippets.append(snippet)
        self._save()
        return snippet

    def update(self, snippet_id: str, **kwargs) -> bool:
        """Update existing snippet"""
        for i, s in enumerate(self.snippets):
            if s["id"] == snippet_id:
                # ユニペットの場合はファイルを更新
                if s.get("source") == "unipet" and s.get("file_path"):
                    return self._update_unipet_file(s, kwargs)

                # JSONスニペットの場合
                for key, value in kwargs.items():
                    if key in ["name", "content", "category", "shortcut"]:
                        self.snippets[i][key] = value
                self._save()
                return True
        return False

    def _update_unipet_file(self, snippet: dict, updates: dict) -> bool:
        """ユニペットファイルを更新"""
        file_path = Path(snippet.get("file_path", ""))
        if not file_path.exists():
            return False

        try:
            name = updates.get("name", snippet["name"])
            category = updates.get("category", snippet.get("category", ""))
            shortcut = updates.get("shortcut", snippet.get("shortcut", ""))
            content = updates.get("content", snippet["content"])

            new_content = f"""名前: {name}
カテゴリ: {category}
ショートカット: {shortcut}

---内容ここから---
{content}
---内容ここまで---
"""
            file_path.write_text(new_content, encoding="utf-8")
            self.reload()  # 再読み込み
            return True
        except Exception as e:
            logging.error(f"Failed to update unipet file: {e}")
            return False

    def delete(self, snippet_id: str, delete_file: bool = False) -> bool:
        """Delete snippet

        Args:
            snippet_id: 削除するスニペットのID
            delete_file: Trueの場合、ユニペットファイルも削除する (v5.2.0)

        Returns:
            bool: 削除に成功したらTrue
        """
        for i, s in enumerate(self.snippets):
            if s["id"] == snippet_id:
                # ユニペットの場合
                if s.get("source") == "unipet":
                    if delete_file:
                        # ファイルを削除 (v5.2.0)
                        file_path = Path(s.get("file_path", ""))
                        if file_path.exists():
                            try:
                                file_path.unlink()
                                logging.info(f"Deleted unipet file: {file_path}")
                            except Exception as e:
                                logging.error(f"Failed to delete unipet file: {e}")
                                return False
                        del self.snippets[i]
                        return True
                    else:
                        logging.warning(f"Cannot delete unipet snippet without delete_file=True: {s.get('file_path')}")
                        return False

                # JSONスニペットの場合
                del self.snippets[i]
                self._save()
                return True
        return False

    def reset_to_defaults(self):
        """Reset to default snippets (ユニペットフォルダから再読み込み)"""
        self.snippets = []
        # JSONファイルをクリア
        save_json(self.snippets_file, {"snippets": []})
        # ユニペットフォルダから再読み込み
        self._load()

    def get_unipet_folder(self) -> Path:
        """ユニペットフォルダのパスを取得"""
        return self.unipet_dir

    def is_unipet_enabled(self) -> bool:
        """ユニペットが有効かどうかを取得"""
        return self._unipet_enabled

    def open_unipet_folder(self):
        """ユニペットフォルダをエクスプローラーで開く"""
        import subprocess
        import sys

        if sys.platform == "win32":
            subprocess.run(["explorer", str(self.unipet_dir)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(self.unipet_dir)])
        else:
            subprocess.run(["xdg-open", str(self.unipet_dir)])
