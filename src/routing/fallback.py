"""
Fallback Manager - Phase 2.4

Backend失敗時の自動フォールバック機能
"""

import logging
from typing import Optional, List
from .task_types import TaskType

logger = logging.getLogger(__name__)


class FallbackManager:
    """
    フォールバック管理器

    Backend失敗時に、自動的に別のBackendに切り替える
    """

    def __init__(self):
        """初期化"""
        # フォールバックチェーン（Phase 2.4 初期実装）
        self.fallback_chains = {
            "local": ["claude-sonnet-4-5", "claude-opus-4-5"],
            "gemini-3-pro": ["claude-sonnet-4-5", "claude-opus-4-5"],
            "gemini-3-flash": ["claude-sonnet-4-5", "claude-opus-4-5"],
            "claude-sonnet-4-5": ["claude-opus-4-5"],
            "claude-haiku-4-5": ["claude-sonnet-4-5", "claude-opus-4-5"],
            "claude-opus-4-5": None,  # Opus はフォールバック先なし
        }

    def next_backend(
        self, current_backend: str, task_type: TaskType
    ) -> Optional[str]:
        """
        次のフォールバック先を取得

        Args:
            current_backend: 現在のBackend名
            task_type: タスク種別

        Returns:
            次のBackend名（Noneの場合はフォールバック不可）
        """
        chain = self.fallback_chains.get(current_backend, None)

        if chain is None or len(chain) == 0:
            logger.info(
                f"[FallbackManager] No fallback available for: {current_backend}"
            )
            return None

        # チェーンの最初を返す
        next_backend = chain[0]

        logger.info(
            f"[FallbackManager] Fallback: {current_backend} → {next_backend} "
            f"(task={task_type})"
        )

        return next_backend

    def get_full_chain(self, backend: str) -> List[str]:
        """
        フォールバックチェーン全体を取得

        Args:
            backend: Backend名

        Returns:
            フォールバックチェーン（現在のBackendを含む）
        """
        chain = [backend]
        current = backend

        while True:
            next_backend = self.next_backend(current, TaskType.CHAT)
            if next_backend is None:
                break
            chain.append(next_backend)
            current = next_backend

        return chain
