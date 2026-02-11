"""
Helix AI Studio - BIBLE Context Injector (v8.0.0)
Phase 1/Phase 3のClaudeプロンプトにBIBLEコンテキストを注入する
"""

import logging
from typing import Optional

from .bible_schema import BibleSectionType, BibleInfo

logger = logging.getLogger(__name__)


class BibleInjector:
    """Phase 1/Phase 3のClaudeプロンプトにBIBLEコンテキストを注入"""

    @staticmethod
    def build_context(bible: BibleInfo, mode: str = "phase1") -> str:
        """
        BIBLEからClaudeプロンプト用のコンテキストブロックを構築。

        Args:
            bible: パース済みBIBLE情報
            mode:
                "phase1" - 計画立案用（概要 + アーキテクチャ + 変更履歴 + 構造 + 技術）
                "phase3" - 統合用（概要 + 変更ファイル一覧 + アーキテクチャ）
                "update" - BIBLE更新用（現在の全文 + 不足セクション情報）

        Returns:
            コンテキストブロック文字列
        """
        if mode == "phase1":
            target_types = {
                BibleSectionType.HEADER,
                BibleSectionType.ARCHITECTURE,
                BibleSectionType.CHANGELOG,
                BibleSectionType.DIRECTORY_STRUCTURE,
                BibleSectionType.TECH_STACK,
            }
        elif mode == "phase3":
            target_types = {
                BibleSectionType.HEADER,
                BibleSectionType.FILE_LIST,
                BibleSectionType.ARCHITECTURE,
            }
        elif mode == "update":
            return BibleInjector._build_update_context(bible)
        else:
            # 全セクション
            target_types = {s.type for s in bible.sections}

        context_parts = []
        context_parts.append(
            f"=== PROJECT BIBLE: {bible.project_name} v{bible.version} "
            f'"{bible.codename}" ==='
        )

        for s in bible.sections:
            if s.type in target_types:
                context_parts.append(s.content)

        context = "\n\n".join(context_parts)
        logger.info(
            f"BIBLE context built: mode={mode}, "
            f"sections={len([s for s in bible.sections if s.type in target_types])}, "
            f"length={len(context)}"
        )
        return context

    @staticmethod
    def _build_update_context(bible: BibleInfo) -> str:
        """BIBLE更新用の特殊コンテキスト"""
        missing = bible.missing_required_sections
        score = bible.completeness_score

        ctx = f"""=== BIBLE UPDATE CONTEXT ===
Project: {bible.project_name}
Current Version: {bible.version}
Completeness Score: {score:.0%}
Missing Required Sections: {', '.join(s.value for s in missing) if missing else 'None'}
Line Count: {bible.line_count}

=== CURRENT BIBLE CONTENT ===
{bible.raw_content}

=== UPDATE INSTRUCTIONS ===
"""
        if missing:
            ctx += "以下の必須セクションを追加してください:\n"
            for s in missing:
                ctx += f"  - {s.value}\n"
        if score < 0.7:
            ctx += "全体の内容充実度が低いです。各セクションをより詳細に記述してください。\n"

        return ctx
