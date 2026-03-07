"""Helix AI Studio — Docker バックエンド（任意 / アダプター）

Docker 互換ランタイム (Docker Desktop / Rancher Desktop) 用のバックエンド。
既存の SandboxManager をラップして SandboxBackend インターフェースに適合させる。
"""

import logging
from typing import Optional

from .backend_base import BackendCapability, SandboxBackend
from .sandbox_config import SandboxConfig, SandboxInfo, SandboxStatus
from .sandbox_manager import SandboxManager

logger = logging.getLogger(__name__)


class DockerBackend(SandboxBackend):
    """SandboxManager ラッパー — SandboxBackend インターフェースに適合

    Docker 互換ランタイム (Docker Desktop / Rancher Desktop) 向けの任意バックエンド。
    全 capability（埋め込みビュー、ファイル閲覧、コマンド実行、スクリーンショット、
    Promotion、リソース統計、ネットワーク設定）を提供する。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = SandboxManager(parent=self)

        # SandboxManager のシグナルを転送
        self._manager.statusChanged.connect(self.statusChanged)
        self._manager.errorOccurred.connect(self.errorOccurred)
        self._manager.outputReceived.connect(self.outputReceived)

    @property
    def manager(self) -> SandboxManager:
        """内部 SandboxManager への直接参照（互換性用）"""
        return self._manager

    # ─── 必須メソッド ───

    def backend_type(self) -> str:
        return "docker"

    def capabilities(self) -> BackendCapability:
        return (
            BackendCapability.EMBED_VIEW
            | BackendCapability.FILE_BROWSE
            | BackendCapability.EXEC_COMMAND
            | BackendCapability.SCREENSHOT
            | BackendCapability.DIFF_PROMOTE
            | BackendCapability.STATS
            | BackendCapability.NETWORKING
        )

    def is_available(self) -> bool:
        return self._manager.is_docker_available()

    def get_unavailable_reason(self) -> str:
        return self._manager.get_docker_unavailable_reason()

    def create(self, config) -> Optional[SandboxInfo]:
        return self._manager.create(config)

    def destroy(self) -> bool:
        return self._manager.destroy()

    def get_status(self) -> SandboxStatus:
        return self._manager.get_status()

    # ─── オプションメソッド（SandboxManager に委譲）───

    def get_diff(self) -> str:
        return self._manager.get_diff()

    def screenshot(self) -> Optional[bytes]:
        return self._manager.screenshot()

    def list_files(self, path: str = "/workspace") -> list:
        result = self._manager.list_dir(path)
        if result.get("ok") and "entries" in result:
            return result["entries"]
        return []

    def read_file(self, path: str) -> bytes:
        result = self._manager.read_file(path)
        if "content" in result:
            return result["content"].encode("utf-8")
        return b""

    def get_container_stats(self) -> Optional[dict]:
        return self._manager.get_container_stats()

    def get_vnc_url(self) -> str:
        url = self._manager.get_vnc_url()
        return url or ""

    def reset_connection(self):
        self._manager.reset_connection()

    # ─── Docker 固有メソッド ───

    def check_image_exists(self) -> bool:
        return self._manager.check_image_exists()

    def build_image(self, progress_callback=None) -> bool:
        return self._manager.build_image(progress_callback)

    def remove_image(self, force: bool = True) -> bool:
        return self._manager.remove_image(force)

    def exec_in_sandbox(self, command: str) -> Optional[str]:
        result = self._manager.execute(command)
        if result.get("exit_code") == 0:
            return result.get("stdout", "")
        return None

    def get_workspace_path(self) -> str:
        info = self._manager.get_info()
        if info:
            return info.workspace_path
        return ""
