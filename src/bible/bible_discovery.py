"""
Helix AI Studio - BIBLE Discovery Engine (v8.4.2)
BIBLEファイルの自動検出: カレント→子→親の3段階探索
v8.4.2: parse_header → parse_full に変更（セクション検出・完全性スコア修正）
"""

import os
import re
import logging
from pathlib import Path
from typing import List

from .bible_parser import BibleParser
from .bible_schema import BibleInfo

logger = logging.getLogger(__name__)

# BIBLEファイル名パターン（優先順位順）
BIBLE_PATTERNS = [
    "BIBLE_*.md",
    "BIBLE.md",
    "PROJECT_BIBLE.md",
    "**/BIBLE/*.md",
    "docs/BIBLE*.md",
]

# 最大探索深度
MAX_PARENT_DEPTH = 5
MAX_CHILD_DEPTH = 3


class BibleDiscovery:
    """BIBLEファイルの自動検出エンジン"""

    @staticmethod
    def discover(start_path: str) -> List[BibleInfo]:
        """
        指定パスからBIBLEファイルを検索する。

        検索順序:
        1. start_path自身（ファイルならその親ディレクトリ）
        2. 子ディレクトリ（MAX_CHILD_DEPTH階層まで）
        3. 親ディレクトリ（MAX_PARENT_DEPTH階層まで遡上）

        Args:
            start_path: 検索開始パス

        Returns:
            BibleInfoのリスト（バージョン降順ソート = 最新が先頭）
        """
        results = []
        seen_paths = set()

        try:
            base_dir = Path(start_path).resolve()
            if base_dir.is_file():
                base_dir = base_dir.parent

            if not base_dir.exists():
                return []

            # Phase 1: カレントディレクトリ + 子ディレクトリ
            # v8.4.2: parse_header → parse_full（セクション検出のため）
            for pattern in BIBLE_PATTERNS:
                try:
                    for match in base_dir.glob(pattern):
                        if match.is_file() and str(match) not in seen_paths:
                            seen_paths.add(str(match))
                            info = BibleParser.parse_full(match)
                            if info:
                                results.append(info)
                except (OSError, PermissionError):
                    continue

            # Phase 2: 親ディレクトリを遡上（結果が空の場合のみ）
            if not results:
                current = base_dir.parent
                for _ in range(MAX_PARENT_DEPTH):
                    if current == current.parent:
                        break
                    for pattern in BIBLE_PATTERNS:
                        try:
                            for match in current.glob(pattern):
                                if match.is_file() and str(match) not in seen_paths:
                                    seen_paths.add(str(match))
                                    info = BibleParser.parse_full(match)
                                    if info:
                                        results.append(info)
                        except (OSError, PermissionError):
                            continue
                    if results:
                        break
                    current = current.parent

        except Exception as e:
            logger.warning(f"BIBLE discovery error for {start_path}: {e}")

        # バージョン降順ソート（最新が先頭）
        results.sort(key=lambda b: b.version_tuple, reverse=True)

        if results:
            logger.info(
                f"BIBLE discovered: {len(results)} file(s) from {start_path} "
                f"- latest: v{results[0].version}"
            )

        return results

    @staticmethod
    def discover_from_prompt(prompt_text: str) -> List[BibleInfo]:
        """
        プロンプト内のパス文字列からBIBLEを検索する。

        対応パターン:
        - "C:\\Users\\...\\project\\" (Windows絶対パス)
        - "/home/user/project/" (Unix絶対パス)

        Args:
            prompt_text: ユーザーのプロンプトテキスト

        Returns:
            BibleInfoのリスト（重複除去済み）
        """
        # Windowsパス
        paths = re.findall(r'[A-Z]:\\[^\s"\'<>|]+', prompt_text)
        # Unixパス
        paths += re.findall(r'/(?:home|Users|mnt|opt)/[^\s"\'<>|]+', prompt_text)

        all_results = []
        seen_files = set()

        for p in paths:
            p = p.rstrip('\\/"\' ')
            if os.path.exists(p) and p not in seen_files:
                seen_files.add(p)
                discovered = BibleDiscovery.discover(p)
                for b in discovered:
                    file_key = str(b.file_path)
                    if file_key not in seen_files:
                        seen_files.add(file_key)
                        all_results.append(b)

        return all_results
