"""
Backend Router - Phase 2.2 / 2.5 / 2.6 / 2.7

タスク種別に応じて最適なBackendを自動選択
Phase 2.5: ルーティング決定ログ追加
Phase 2.6: ポリシー連動ルーティング
Phase 2.7: Project別ModelPreset対応
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from .task_types import TaskType

logger = logging.getLogger(__name__)


class BackendRouter:
    """
    Backend ルーター

    タスク種別、フェーズ、設定、承認状況に応じて最適なBackendを選択
    Phase 2.5: 決定ログ記録
    Phase 2.6: ポリシー連動（承認チェック）
    Phase 2.7: ModelPreset対応
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """
        Args:
            settings: ルーティング設定（オプション）
        """
        self.settings = settings or {}

        # デフォルトルール（Phase 2.2 初期実装）
        self.default_rules = {
            TaskType.PLAN: "claude-opus-4-5",       # 計画はOpus優先（設定で変更可）
            TaskType.IMPLEMENT: "claude-sonnet-4-5", # 実装はSonnet
            TaskType.RESEARCH: "gemini-3-pro",       # 調査はGemini（無ければSonnet）
            TaskType.REVIEW: "claude-sonnet-4-5",    # レビューはSonnet
            TaskType.VERIFY: "local",                # 検証はLocal（フォールバック前提）
            TaskType.CHAT: "claude-sonnet-4-5",      # 通常対話はSonnet
        }

        # Phase 2.7: アクティブなPreset
        self.active_preset: Optional[Dict[str, str]] = None
        self.active_preset_name: Optional[str] = None

    def select_backend(
        self,
        task_type: TaskType,
        phase: str,
        user_forced_backend: Optional[str] = None,
        approvals: Optional[Dict[str, Any]] = None,
        approval_snapshot: Optional[Dict[str, bool]] = None,
        env_flags: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str], bool]:
        """
        Backend を選択

        Args:
            task_type: タスク種別
            phase: 現在のフェーズ (e.g. "S2", "S4")
            user_forced_backend: ユーザーが明示的に指定したBackend（優先）
            approvals: 承認状態（旧）
            approval_snapshot: Phase 2.6 承認スナップショット
            env_flags: 環境フラグ

        Returns:
            (backend_name, reason_codes, user_forced):
            選択されたBackend名、理由コード、ユーザー指定かどうか
        """
        reason_codes = []
        task_key = task_type.name if isinstance(task_type, TaskType) else str(task_type)
        reason_codes.append(f"task={task_key}")
        reason_codes.append(f"phase={phase}")

        # 1. ユーザーが明示的に指定した場合は優先
        if user_forced_backend:
            logger.info(
                f"[Router] User forced backend: {user_forced_backend} "
                f"(task={task_type}, phase={phase})"
            )
            reason_codes.append("user_forced=true")
            return user_forced_backend, reason_codes, True

        # 2. Phase 2.7: Presetを適用
        if self.active_preset:
            preset_task_key = task_type.name if isinstance(task_type, TaskType) else str(task_type)
            preset_backend = self.active_preset.get(preset_task_key)
            if preset_backend:
                logger.info(
                    f"[Router] Preset-based: {preset_backend} "
                    f"(preset={self.active_preset_name}, task={task_type})"
                )
                reason_codes.append(f"preset={self.active_preset_name}")
                return preset_backend, reason_codes, False

        # 3. 設定によるルールをチェック
        settings_backend = self.settings.get(task_type, None)
        if settings_backend:
            logger.info(
                f"[Router] Settings-based: {settings_backend} "
                f"(task={task_type}, phase={phase})"
            )
            reason_codes.append("policy=settings")
            return settings_backend, reason_codes, False

        # 4. デフォルトルールを適用
        default_backend = self.default_rules.get(task_type, "claude-sonnet-4-5")

        logger.info(
            f"[Router] Default rule: {default_backend} "
            f"(task={task_type}, phase={phase})"
        )
        reason_codes.append("policy=default")

        return default_backend, reason_codes, False

    def set_preset(self, preset_name: str, preset_config: Dict[str, str]):
        """
        Phase 2.7: ModelPresetを設定

        Args:
            preset_name: プリセット名 (e.g. "economy", "quality")
            preset_config: タスク種別→Backend名のマッピング
        """
        self.active_preset_name = preset_name
        self.active_preset = preset_config
        logger.info(f"[Router] Preset set: {preset_name}")

    def clear_preset(self):
        """Phase 2.7: Presetをクリア"""
        self.active_preset = None
        self.active_preset_name = None
        logger.info("[Router] Preset cleared")

    def get_reason_codes(
        self,
        task_type: TaskType,
        phase: str,
        user_forced_backend: Optional[str] = None,
    ) -> list:
        """
        ルーティングの理由コードを取得（監査用）

        Args:
            task_type: タスク種別
            phase: フェーズ
            user_forced_backend: ユーザー固定Backend

        Returns:
            理由コードのリスト
        """
        reasons = []

        reasons.append(f"task={task_type}")
        reasons.append(f"phase={phase}")

        if user_forced_backend:
            reasons.append("user_forced=true")
        else:
            reasons.append("policy=default")

        return reasons

    def update_settings(self, new_settings: Dict[str, Any]):
        """
        ルーティング設定を更新

        Args:
            new_settings: 新しい設定
        """
        self.settings.update(new_settings)
        logger.info(f"[Router] Settings updated: {self.settings}")
