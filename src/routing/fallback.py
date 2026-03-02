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
        # v11.9.5: プロバイダーベースのフォールバック（特定モデル名への依存を排除）
        # CLI系 → 同プロバイダーのAPI系 へフォールバック
        # API系はフォールバックなし（APIキー未設定なら即失敗で明確に）
        # ローカル / クラウドモデル名は動的解決に委ねる
        self.fallback_chains = {
            "local": None,  # ローカルからクラウドへの自動切替はしない（意図しない課金防止）
            "anthropic_cli": ["anthropic_api"],
            "openai_cli": ["openai_api"],
            "google_cli": ["google_api"],
            "anthropic_api": None,
            "openai_api": None,
            "google_api": None,
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
