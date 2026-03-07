"""Helix AI Studio — Sandbox パッケージ

Virtual Desktop 用バックエンド群。
BackendFactory が Windows Sandbox (標準) → Docker 互換ランタイム (任意) の順に自動選択する。
"""

from .sandbox_config import SandboxConfig, SandboxInfo, SandboxStatus, WindowsSandboxConfig
from .backend_base import BackendCapability, SandboxBackend
from .backend_factory import BackendFactory

__all__ = [
    "SandboxConfig", "SandboxInfo", "SandboxStatus", "WindowsSandboxConfig",
    "BackendCapability", "SandboxBackend", "BackendFactory",
]
