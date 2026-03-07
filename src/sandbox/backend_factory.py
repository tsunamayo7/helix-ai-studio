"""Helix AI Studio — バックエンドファクトリー

Auto モード: Windows Sandbox → Docker → None の順に自動選択。
手動指定: "windows_sandbox" / "docker" で明示的に選択。
"""

import logging
from typing import Optional

from .backend_base import SandboxBackend

logger = logging.getLogger(__name__)


class BackendFactory:
    """Sandbox バックエンドのファクトリー"""

    @staticmethod
    def auto_select(parent=None) -> Optional[SandboxBackend]:
        """利用可能なバックエンドを自動選択

        優先順位:
        1. Windows Sandbox（追加ランタイム不要）
        2. Docker（Docker Desktop / Rancher Desktop 必要）
        3. None（どちらも利用不可）
        """
        # 1. Windows Sandbox
        try:
            from .windows_sandbox_backend import WindowsSandboxBackend
            wsb = WindowsSandboxBackend(parent=parent)
            if wsb.is_available():
                logger.info("[BackendFactory] Auto-selected: Windows Sandbox")
                return wsb
            logger.debug("[BackendFactory] Windows Sandbox not available, trying Docker...")
        except Exception as e:
            logger.debug(f"[BackendFactory] Windows Sandbox check failed: {e}")

        # 2. Docker
        try:
            from .docker_backend import DockerBackend
            docker = DockerBackend(parent=parent)
            if docker.is_available():
                logger.info("[BackendFactory] Auto-selected: Docker")
                return docker
            logger.debug("[BackendFactory] Docker not available")
        except Exception as e:
            logger.debug(f"[BackendFactory] Docker check failed: {e}")

        # 3. どちらも不可
        logger.warning("[BackendFactory] No sandbox backend available")
        return None

    @staticmethod
    def create(backend_type: str, parent=None) -> Optional[SandboxBackend]:
        """指定タイプのバックエンドを生成

        Args:
            backend_type: "auto" / "windows_sandbox" / "docker"
            parent: QObject 親

        Returns:
            SandboxBackend インスタンス、または None
        """
        if backend_type == "auto":
            return BackendFactory.auto_select(parent=parent)

        if backend_type == "windows_sandbox":
            from .windows_sandbox_backend import WindowsSandboxBackend
            backend = WindowsSandboxBackend(parent=parent)
            if backend.is_available():
                return backend
            logger.warning("[BackendFactory] Windows Sandbox requested but not available")
            return backend  # 利用不可でもインスタンスは返す（理由表示のため）

        if backend_type == "docker":
            from .docker_backend import DockerBackend
            backend = DockerBackend(parent=parent)
            return backend  # Docker は接続遅延があるので利用可否は後でチェック

        logger.warning(f"[BackendFactory] Unknown backend type: {backend_type}")
        return None
