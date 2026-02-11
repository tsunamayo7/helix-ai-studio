"""
Backend Registry - Phase 2.0 CP1

全バックエンドインスタンスの管理
シングルトンパターンでグローバルにアクセス可能
"""

import logging
from typing import Optional, Dict
from .base import LLMBackend
from .claude_backend import ClaudeBackend
from .gemini_backend import GeminiBackend
from .local_backend import LocalBackend

logger = logging.getLogger(__name__)


class BackendRegistry:
    """
    バックエンドレジストリ

    全てのBackendインスタンスを管理し、名前で取得できるようにする
    """

    def __init__(self):
        """初期化"""
        self._backends: Dict[str, LLMBackend] = {}
        self._initialize_default_backends()

    def _initialize_default_backends(self):
        """デフォルトのバックエンドを初期化"""
        # Claude backends
        self._backends["claude-sonnet-4-5"] = ClaudeBackend(model="sonnet-4-5")
        self._backends["claude-opus-4-5"] = ClaudeBackend(model="opus-4-5")
        self._backends["claude-haiku-4-5"] = ClaudeBackend(model="haiku-4-5")

        # Gemini backends
        self._backends["gemini-3-pro"] = GeminiBackend(model="3-pro")
        self._backends["gemini-3-flash"] = GeminiBackend(model="3-flash")

        # Local backend
        self._backends["local"] = LocalBackend()

        logger.info(
            f"[BackendRegistry] Initialized with {len(self._backends)} backends: "
            f"{list(self._backends.keys())}"
        )

    def get(self, name: str) -> Optional[LLMBackend]:
        """
        名前でBackendを取得

        Args:
            name: Backend名

        Returns:
            LLMBackend or None
        """
        return self._backends.get(name)

    def get_all(self) -> Dict[str, LLMBackend]:
        """全Backendを取得"""
        return dict(self._backends)

    def register(self, name: str, backend: LLMBackend):
        """
        Backendを登録

        Args:
            name: Backend名
            backend: LLMBackendインスタンス
        """
        self._backends[name] = backend
        logger.info(f"[BackendRegistry] Registered backend: {name}")

    def get_available_backends(self) -> list:
        """利用可能なBackend名のリストを取得"""
        return list(self._backends.keys())

    def is_local_available(self) -> bool:
        """ローカルバックエンドが利用可能かどうか"""
        local = self._backends.get("local")
        if isinstance(local, LocalBackend):
            return local.is_available()
        return False

    def get_local_backend(self) -> Optional[LocalBackend]:
        """ローカルバックエンドを取得"""
        backend = self._backends.get("local")
        if isinstance(backend, LocalBackend):
            return backend
        return None


# グローバルインスタンス
_backend_registry: Optional[BackendRegistry] = None


def get_backend_registry() -> BackendRegistry:
    """BackendRegistryのグローバルインスタンスを取得"""
    global _backend_registry
    if _backend_registry is None:
        _backend_registry = BackendRegistry()
    return _backend_registry
