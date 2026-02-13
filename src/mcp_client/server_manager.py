"""
MCP Server Manager - GUI for managing MCP servers
MCPサーバーの有効/無効を切り替えるGUI用マネージャー

v2.4.0 更新 (2026-01-24):
- shlex.split()によるコマンドインジェクション対策
- エラー処理の改善
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum
import shlex
import json
import logging
from pathlib import Path

from ..utils.subprocess_utils import run_hidden

logger = logging.getLogger(__name__)


class ServerStatus(Enum):
    """サーバーステータス"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ServerInfo:
    """サーバー情報"""
    name: str
    type: str
    status: ServerStatus
    enabled: bool
    description: str
    install_command: Optional[str] = None


class MCPServerManager:
    """
    MCP Server Manager

    Features:
    - サーバー一覧表示
    - サーバー有効/無効切り替え
    - サーバーインストールガイド
    - ステータス監視
    """

    # 利用可能なMCPサーバー定義
    AVAILABLE_SERVERS = {
        'filesystem': {
            'description': 'ファイルシステムアクセス（読み書き、一覧）',
            'install': 'npm install -g @anthropic/mcp-server-filesystem',
            'command': 'npx',
            'args': ['-y', '@anthropic/mcp-server-filesystem']
        },
        'git': {
            'description': 'Git操作（status, diff, commit等）',
            'install': 'npm install -g @anthropic/mcp-server-git',
            'command': 'npx',
            'args': ['-y', '@anthropic/mcp-server-git']
        },
        'brave-search': {
            'description': 'Brave Search API経由のWeb検索',
            'install': 'npm install -g @anthropic/mcp-server-brave-search',
            'command': 'npx',
            'args': ['-y', '@anthropic/mcp-server-brave-search'],
            'env_required': ['BRAVE_API_KEY']
        },
        'github': {
            'description': 'GitHub API（Issues, PRs, Repos）',
            'install': 'npm install -g @anthropic/mcp-server-github',
            'command': 'npx',
            'args': ['-y', '@anthropic/mcp-server-github'],
            'env_required': ['GITHUB_TOKEN']
        },
        'postgres': {
            'description': 'PostgreSQLデータベース操作',
            'install': 'npm install -g @anthropic/mcp-server-postgres',
            'command': 'npx',
            'args': ['-y', '@anthropic/mcp-server-postgres'],
            'env_required': ['DATABASE_URL']
        }
    }

    def __init__(self, config_path: str = "config/mcp_servers.json"):
        self.config_path = Path(config_path)
        self.enabled_servers: Dict[str, bool] = {}
        self.server_status: Dict[str, ServerStatus] = {}
        self._load_config()

    def _load_config(self) -> None:
        """設定を読み込み"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.enabled_servers = data.get('enabled', {})
                logger.info(f"[MCPServerManager] Loaded config")
            except json.JSONDecodeError as e:
                logger.error(f"[MCPServerManager] Invalid JSON in config: {e}")
            except Exception as e:
                logger.error(f"[MCPServerManager] Failed to load config: {e}")

        # デフォルトでfilesystemとgitを有効化
        if not self.enabled_servers:
            self.enabled_servers = {
                'filesystem': True,
                'git': True
            }
            self._save_config()

    def _save_config(self) -> None:
        """設定を保存"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {'enabled': self.enabled_servers}
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_server_list(self) -> List[ServerInfo]:
        """
        サーバー一覧を取得

        Returns:
            サーバー情報のリスト
        """
        servers = []
        for name, info in self.AVAILABLE_SERVERS.items():
            enabled = self.enabled_servers.get(name, False)
            status = self.server_status.get(name, ServerStatus.STOPPED)

            servers.append(ServerInfo(
                name=name,
                type=name,
                status=status,
                enabled=enabled,
                description=info['description'],
                install_command=info['install']
            ))
        return servers

    def enable_server(self, name: str, enabled: bool = True) -> bool:
        """
        サーバーを有効/無効化

        Args:
            name: サーバー名
            enabled: 有効にするかどうか

        Returns:
            成功かどうか
        """
        if name not in self.AVAILABLE_SERVERS:
            return False

        self.enabled_servers[name] = enabled
        self._save_config()
        return True

    def is_server_installed(self, name: str) -> bool:
        """
        サーバーがインストールされているかチェック

        Args:
            name: サーバー名

        Returns:
            インストール済みかどうか
        """
        if name not in self.AVAILABLE_SERVERS:
            return False

        info = self.AVAILABLE_SERVERS[name]
        try:
            result = run_hidden(
                ['npx', '-y', f'@anthropic/mcp-server-{name}', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def install_server(
        self,
        name: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        サーバーをインストール

        Args:
            name: サーバー名
            progress_callback: 進捗コールバック

        Returns:
            成功かどうか
        """
        if name not in self.AVAILABLE_SERVERS:
            return False

        info = self.AVAILABLE_SERVERS[name]
        install_cmd = info['install']

        if progress_callback:
            progress_callback(f"Installing {name}...")

        try:
            # shlex.split()でコマンドインジェクション対策
            result = run_hidden(
                shlex.split(install_cmd),
                capture_output=True,
                text=True,
                timeout=300,  # 5分タイムアウト
                shell=False  # シェルを経由しない
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback(f"Successfully installed {name}")
                return True
            else:
                if progress_callback:
                    progress_callback(f"Failed to install {name}: {result.stderr}")
                return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error installing {name}: {e}")
            return False

    def get_enabled_servers(self) -> List[str]:
        """
        有効なサーバー一覧を取得

        Returns:
            有効なサーバー名のリスト
        """
        return [name for name, enabled in self.enabled_servers.items() if enabled]

    def get_server_config(self, name: str) -> Optional[Dict]:
        """
        サーバー設定を取得

        Args:
            name: サーバー名

        Returns:
            サーバー設定辞書
        """
        if name in self.AVAILABLE_SERVERS:
            return self.AVAILABLE_SERVERS[name].copy()
        return None
