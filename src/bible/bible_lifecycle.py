"""
Helix AI Studio - BIBLE Lifecycle Manager (v8.0.0)
Phase 3完了後のBIBLE自律管理: 判定ロジックとアクション実行
"""

import os
import logging
from enum import Enum
from typing import Optional, Tuple
from pathlib import Path
from datetime import date

from .bible_schema import BibleInfo, BIBLE_TEMPLATE, REQUIRED_SECTIONS

logger = logging.getLogger(__name__)


class BibleAction(Enum):
    """BIBLE管理アクション"""
    NONE = "none"
    UPDATE_CHANGELOG = "update"
    ADD_SECTIONS = "add_sections"
    CREATE_NEW = "create_new"
    VERSION_UP = "version_up"


class BibleLifecycleManager:
    """BIBLE自律管理エンジン"""

    @staticmethod
    def determine_action(
        bible: Optional[BibleInfo],
        execution_result: dict,
        config: dict,
    ) -> Tuple[BibleAction, str]:
        """
        Phase 3完了後に実行すべきBIBLEアクションを判定。

        Args:
            bible: 現在のBIBLE情報（Noneの場合は未検出）
            execution_result: 実行結果の情報
                - changed_files: 変更されたファイルのリスト
                - app_version: 現在のアプリバージョン
            config: アプリ設定

        Returns:
            (アクション種別, 理由メッセージ)
        """
        # BIBLEが存在しない場合
        if bible is None:
            changed_files = execution_result.get("changed_files", [])
            if len(changed_files) >= 5:
                return (
                    BibleAction.CREATE_NEW,
                    f"{len(changed_files)}個のファイルが変更されました。"
                    f"プロジェクトBIBLEの作成を推奨します。"
                )
            return (BibleAction.NONE, "")

        # BIBLEが存在する場合
        missing = bible.missing_required_sections

        # 必須セクション不足 → セクション追加
        if missing:
            return (
                BibleAction.ADD_SECTIONS,
                f"必須セクションが{len(missing)}個不足しています: "
                f"{', '.join(s.value for s in missing)}"
            )

        # バージョン変更の検出
        app_version = execution_result.get("app_version")
        if app_version and app_version != bible.version:
            return (
                BibleAction.VERSION_UP,
                f"アプリバージョンが {bible.version} -> {app_version} に"
                f"変更されています。新バージョンBIBLEの作成を推奨します。"
            )

        # ファイル変更あり → CHANGELOG更新
        changed_files = execution_result.get("changed_files", [])
        if changed_files:
            return (
                BibleAction.UPDATE_CHANGELOG,
                f"{len(changed_files)}個のファイルが変更されました。"
                f"変更履歴の更新を推奨します。"
            )

        return (BibleAction.NONE, "")

    @staticmethod
    def execute_action(
        action: BibleAction,
        bible: Optional[BibleInfo],
        execution_result: dict,
        project_dir: str,
    ) -> Optional[str]:
        """
        BIBLEアクションを実行し、生成/更新されたBIBLEの内容を返す。

        Args:
            action: 実行するアクション
            bible: 現在のBIBLE情報
            execution_result: 実行結果
            project_dir: プロジェクトディレクトリ

        Returns:
            生成/更新されたBIBLEの内容、またはNone
        """
        if action == BibleAction.NONE:
            return None

        if action == BibleAction.CREATE_NEW:
            return BibleLifecycleManager._create_new_bible(
                execution_result, project_dir
            )

        if action == BibleAction.ADD_SECTIONS:
            return BibleLifecycleManager._add_missing_sections(
                bible, execution_result
            )

        if action == BibleAction.UPDATE_CHANGELOG:
            return BibleLifecycleManager._update_changelog(
                bible, execution_result
            )

        if action == BibleAction.VERSION_UP:
            return BibleLifecycleManager._version_up_bible(
                bible, execution_result, project_dir
            )

        return None

    @staticmethod
    def _create_new_bible(result: dict, project_dir: str) -> str:
        """新規BIBLE生成（テンプレートベース）"""
        project_name = Path(project_dir).name if project_dir else "Project"
        today = date.today().isoformat()

        content = BIBLE_TEMPLATE.format(
            project_name=project_name,
            version="1.0.0",
            codename="Genesis",
            date=today,
            generator="Helix AI Studio BIBLE Manager",
        )

        logger.info(f"New BIBLE generated for {project_name}")
        return content

    @staticmethod
    def _add_missing_sections(
        bible: Optional[BibleInfo],
        result: dict,
    ) -> Optional[str]:
        """不足セクションを追加"""
        if not bible:
            return None

        missing = bible.missing_required_sections
        if not missing:
            return None

        content = bible.raw_content

        # 各不足セクションのスケルトンを末尾に追加
        for section_type in missing:
            section_name = section_type.value
            content += f"\n\n---\n\n## {section_name}\n\n（内容を記述してください）\n"

        logger.info(f"Added {len(missing)} missing sections to BIBLE")
        return content

    @staticmethod
    def _update_changelog(
        bible: Optional[BibleInfo],
        result: dict,
    ) -> Optional[str]:
        """変更履歴セクションを更新"""
        if not bible:
            return None

        changed_files = result.get("changed_files", [])
        if not changed_files:
            return None

        today = date.today().isoformat()
        changelog_entry = f"\n### {today} 変更\n\n"
        for f in changed_files[:20]:
            changelog_entry += f"- {f}\n"

        # CHANGELOG セクションの末尾に追記
        content = bible.raw_content + changelog_entry

        logger.info(f"Updated changelog with {len(changed_files)} files")
        return content

    @staticmethod
    def _version_up_bible(
        bible: Optional[BibleInfo],
        result: dict,
        project_dir: str,
    ) -> Optional[str]:
        """新バージョンBIBLE作成"""
        if not bible:
            return None

        app_version = result.get("app_version", bible.version)
        project_name = bible.project_name
        today = date.today().isoformat()

        content = BIBLE_TEMPLATE.format(
            project_name=project_name,
            version=app_version,
            codename="",
            date=today,
            generator="Helix AI Studio BIBLE Manager (version up)",
        )

        logger.info(f"Version up BIBLE: {bible.version} -> {app_version}")
        return content
