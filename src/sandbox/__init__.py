"""Helix AI Studio — Sandbox パッケージ

Windows Sandbox / Docker コンテナベースの隔離実行環境を提供する。
"""

from .sandbox_config import SandboxConfig, SandboxInfo, SandboxStatus, WindowsSandboxConfig
from .backend_base import BackendCapability, SandboxBackend
from .backend_factory import BackendFactory

__all__ = [
    "SandboxConfig", "SandboxInfo", "SandboxStatus", "WindowsSandboxConfig",
    "BackendCapability", "SandboxBackend", "BackendFactory",
]
