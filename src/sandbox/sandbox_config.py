"""Helix AI Studio — Sandbox 設定・データクラス定義"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SandboxStatus(Enum):
    """Sandbox の状態"""
    NONE = "none"               # sandbox 未起動
    CREATING = "creating"       # 作成中
    RUNNING = "running"         # 稼働中
    STOPPED = "stopped"         # 停止
    ERROR = "error"             # エラー
    PROMOTING = "promoting"     # 本番適用中


@dataclass
class SandboxConfig:
    """Sandbox コンテナの設定"""
    image_name: str = "helix-sandbox:latest"
    cpu_limit: float = 2.0          # CPUs
    memory_limit: str = "2g"        # RAM
    workspace_path: str = ""        # ホスト側プロジェクトパス
    vnc_password: str = ""          # 空なら認証なし
    timeout_minutes: int = 60       # 自動タイムアウト
    network_mode: str = "none"      # none / bridge / host
    resolution: str = "1280x720"    # 仮想ディスプレイ解像度
    auto_cleanup: bool = True       # タイムアウト時に自動削除
    mount_readonly: bool = True     # 読み取り専用マウント
    exclude_patterns: str = ".git,__pycache__,node_modules,*.pyc,.env"


@dataclass
class SandboxInfo:
    """稼働中の Sandbox コンテナ情報"""
    sandbox_id: str                 # Docker コンテナ ID（短縮形）
    container_name: str             # helix-sandbox-{timestamp}
    status: SandboxStatus = SandboxStatus.NONE
    vnc_url: str = ""               # http://localhost:{port}/vnc.html
    vnc_port: int = 0               # 動的割り当て
    novnc_port: int = 0             # NoVNC ポート
    created_at: datetime = field(default_factory=datetime.now)
    workspace_path: str = ""
    config: Optional[SandboxConfig] = None
