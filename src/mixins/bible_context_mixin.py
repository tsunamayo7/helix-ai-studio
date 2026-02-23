"""v11.0.0: BIBLE クロスタブ統合 Mixin

全タブ共通のBIBLE連携ロジック。
BIBLEボタン(トグル)がONの場合、送信プロンプトにBIBLE規則コンテキストを注入する。

使用方法:
    class ClaudeTab(QWidget, BibleContextMixin):
        ...
        if self.bible_btn.isChecked():
            processed_message = self._inject_bible_to_prompt(processed_message)
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BibleContextMixin:
    """全タブ共通のBIBLE連携ミックスイン"""

    BIBLE_RULES_PROMPT = """
あなたはBIBLE（Build Information Base for Lifecycle Engineering）の管理を担当します。

## BIBLEの記載規則
- ファイル名: BIBLE_<プロジェクト名>_<バージョン>.md
- 構成: プロジェクト概要、タブ構成図、Phase一覧、新規ファイル一覧、Changelog、設定ファイル構成、技術スタック
- バージョニング: セマンティックバージョニング準拠
- 更新タイミング: 機能追加・変更・削除のたびに更新

## 自律的な判断基準
以下の場合、BIBLEの新規作成または更新を実行してください:
1. 既存のBIBLEファイルが存在する場合 → 変更内容を反映して更新
2. UI表示物（アプリ等）を新規作成する場合 → 新しいBIBLEを作成
3. 上記以外 → BIBLEの作成・更新は不要
"""

    def _get_bible_path(self) -> Optional[Path]:
        """BIBLEフォルダ内の最新BIBLEファイルを取得"""
        bible_dir = Path("BIBLE")
        if not bible_dir.exists():
            return None
        bible_files = sorted(bible_dir.glob("BIBLE_*.md"), reverse=True)
        return bible_files[0] if bible_files else None

    def _build_bible_rules_context(self) -> str:
        """BIBLEの記載規則コンテキストを構築（全文ではなく規則のみ）"""
        context = self.BIBLE_RULES_PROMPT

        bible_path = self._get_bible_path()
        if bible_path:
            try:
                with open(bible_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                headings = [line.strip() for line in lines if line.startswith('#')]
                context += f"\n\n## 既存BIBLE構造 ({bible_path.name})\n"
                context += "\n".join(headings)
            except Exception as e:
                logger.warning(f"Failed to read BIBLE headings: {e}")

        return context

    def _inject_bible_to_prompt(self, prompt: str) -> str:
        """プロンプトにBIBLE規則コンテキストを注入"""
        bible_context = self._build_bible_rules_context()
        return f"<bible_context>\n{bible_context}\n</bible_context>\n\n{prompt}"
