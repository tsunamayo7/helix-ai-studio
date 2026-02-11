"""
Helix AI Studio - BIBLE Parser (v8.0.0)
BIBLEファイルの構造化パーサー: ヘッダー高速パース、完全セクション分割
"""

import re
import logging
from pathlib import Path
from typing import Optional

from .bible_schema import (
    BibleSectionType, BibleSection, BibleInfo,
    SECTION_HEADING_MAP, REQUIRED_SECTIONS,
)

logger = logging.getLogger(__name__)


class BibleParser:
    """BIBLEファイルの構造化パーサー"""

    @staticmethod
    def parse_header(file_path: Path) -> Optional[BibleInfo]:
        """
        BIBLEファイルのヘッダー情報のみ高速パース。
        セクション分割は行わず、メタ情報のみ抽出する。

        Args:
            file_path: BIBLEファイルのパス

        Returns:
            BibleInfo（セクション未分割）or None
        """
        try:
            file_path = Path(file_path)
            content = file_path.read_text(encoding="utf-8")
            first_lines = content[:2000]

            # プロジェクト名
            name_match = re.search(
                r"^#\s+(.+?)\s*[-\u2013\u2014]\s*Project BIBLE",
                first_lines, re.MULTILINE
            )
            project_name = name_match.group(1).strip() if name_match else file_path.stem

            # バージョン
            ver_match = re.search(r"\*\*バージョン\*\*:\s*([\d.]+)", first_lines)
            if not ver_match:
                ver_match = re.search(r"\*\*アプリケーションバージョン\*\*:\s*([\d.]+)", first_lines)
            version = ver_match.group(1) if ver_match else "0.0.0"

            # コードネーム（最初の引用符で囲まれた文字列）
            code_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', first_lines[:500])
            codename = code_match.group(1) if code_match else ""

            # 日付
            date_match = re.search(
                r"\*\*(?:作成日|最終更新)\*\*:\s*(.+)",
                first_lines
            )
            date_str = date_match.group(1).strip() if date_match else ""

            return BibleInfo(
                file_path=file_path,
                project_name=project_name,
                version=version,
                codename=codename,
                created_date=date_str,
                updated_date=date_str,
                raw_content=content,
                line_count=content.count("\n") + 1,
            )
        except Exception as e:
            logger.debug(f"BIBLE header parse failed for {file_path}: {e}")
            return None

    @staticmethod
    def parse_full(file_path: Path) -> Optional[BibleInfo]:
        """
        BIBLEファイルの完全パース（セクション分割含む）。

        Args:
            file_path: BIBLEファイルのパス

        Returns:
            BibleInfo（セクション分割済み）or None
        """
        info = BibleParser.parse_header(file_path)
        if not info:
            return None

        lines = info.raw_content.split("\n")
        sections = []
        current_section = None
        current_lines = []
        current_start = 0

        for i, line in enumerate(lines):
            detected_type = BibleParser._detect_section_type(line)
            if detected_type:
                # 前のセクションを保存
                if current_section:
                    content = "\n".join(current_lines)
                    sections.append(BibleSection(
                        type=current_section,
                        title=lines[current_start].lstrip("#").strip(),
                        content=content,
                        line_start=current_start + 1,
                        line_end=i,
                        completeness=BibleParser._estimate_completeness(
                            current_section, content
                        ),
                    ))
                current_section = detected_type
                current_lines = [line]
                current_start = i
            elif current_section:
                current_lines.append(line)

        # 最後のセクション
        if current_section:
            content = "\n".join(current_lines)
            sections.append(BibleSection(
                type=current_section,
                title=lines[current_start].lstrip("#").strip(),
                content=content,
                line_start=current_start + 1,
                line_end=len(lines),
                completeness=BibleParser._estimate_completeness(
                    current_section, content
                ),
            ))

        info.sections = sections
        logger.debug(
            f"BIBLE parsed: {info.file_path.name} - "
            f"v{info.version} - {len(sections)} sections - "
            f"completeness {info.completeness_score:.0%}"
        )
        return info

    @staticmethod
    def _detect_section_type(line: str) -> Optional[BibleSectionType]:
        """行がどのセクション見出しかを判定"""
        for section_type, patterns in SECTION_HEADING_MAP.items():
            for pattern in patterns:
                if re.match(pattern, line):
                    return section_type
        return None

    @staticmethod
    def _estimate_completeness(section_type: BibleSectionType, content: str) -> float:
        """
        セクションの内容充実度を簡易推定。

        Args:
            section_type: セクション型
            content: セクション内容テキスト

        Returns:
            0.0-1.0 の充実度スコア
        """
        line_count = content.count("\n")

        # セクションごとの最低期待行数
        min_lines = {
            BibleSectionType.HEADER: 5,
            BibleSectionType.VERSION_HISTORY: 8,
            BibleSectionType.ARCHITECTURE: 15,
            BibleSectionType.CHANGELOG: 10,
            BibleSectionType.FILE_LIST: 5,
            BibleSectionType.DIRECTORY_STRUCTURE: 10,
        }
        expected = min_lines.get(section_type, 5)
        line_score = min(1.0, line_count / expected)

        # コードブロック・テーブルの存在をボーナスとして加算
        has_code = "```" in content
        has_table = "|" in content and "---" in content
        bonus = 0.1 * has_code + 0.1 * has_table

        return min(1.0, line_score + bonus)
