"""
Helix MCP Client - Model Context Protocol Integration
Reference: Anthropic MCP, Cline

v2.4.0 更新 (2026-01-24):
- パストラバーサル脆弱性の修正（セキュリティ強化）
- プロジェクトルート外へのアクセス禁止
- 非同期subprocess対応
- タイムスタンプの修正（datetime使用）
- MCP SDK v1.7.x 対応

参照:
- https://modelcontextprotocol.io/docs/develop/build-client
- https://github.com/modelcontextprotocol/python-sdk
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import json
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# プロジェクトルートの設定（セキュリティ）
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# 許可されたパス（プロジェクトルートを基準）
ALLOWED_PATHS: List[Path] = [
    PROJECT_ROOT,
]


class MCPServerType(Enum):
    """MCPサーバータイプ"""
    FILESYSTEM = "filesystem"
    GIT = "git"
    BRAVE_SEARCH = "brave-search"
    POSTGRES = "postgres"
    GITHUB = "github"
    CUSTOM = "custom"


@dataclass
class MCPServer:
    """MCPサーバー設定"""
    name: str
    type: MCPServerType
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    enabled: bool = True


@dataclass
class ToolCall:
    """ツール呼び出し"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """ツール実行結果"""
    call_id: str
    success: bool
    result: Any
    error: Optional[str] = None


def _validate_path(path: str, allowed_roots: Optional[List[Path]] = None) -> Path:
    """
    パストラバーサル攻撃を防ぐためのパス検証

    Args:
        path: 検証するパス
        allowed_roots: 許可されたルートパスのリスト

    Returns:
        解決済みの安全なパス

    Raises:
        PermissionError: パスがプロジェクト外の場合
        ValueError: パスが空または不正な場合
    """
    if not path:
        raise ValueError("パスが空です")

    # パスを解決
    target_path = Path(path).resolve()

    # 許可されたルートをチェック
    roots = allowed_roots or ALLOWED_PATHS
    for allowed_root in roots:
        try:
            target_path.relative_to(allowed_root)
            return target_path
        except ValueError:
            continue

    # どのルートにも属していない場合はエラー
    raise PermissionError(
        f"アクセス拒否: '{path}' はプロジェクト外のパスです。"
        f"許可されたパス: {[str(r) for r in roots]}"
    )


def set_allowed_paths(paths: List[str]) -> None:
    """
    許可されたパスのリストを設定

    Args:
        paths: 許可するパスのリスト
    """
    global ALLOWED_PATHS
    ALLOWED_PATHS = [Path(p).resolve() for p in paths if p]


class HelixMCPClient:
    """
    Helix MCP Client

    Features:
    - MCPサーバー管理（起動/停止）
    - ツール呼び出しルーティング
    - 権限管理・承認フロー
    - 監査ログ
    - パストラバーサル保護
    """

    def __init__(self, config_path: str = "config/mcp_servers.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, MCPServer] = {}
        self.active_processes: Dict[str, Any] = {}
        self.tool_registry: Dict[str, Callable] = {}
        self.audit_log: List[Dict] = []
        self._load_config()
        self._register_builtin_tools()

    def _load_config(self) -> None:
        """サーバー設定を読み込み"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, config in data.get('servers', {}).items():
                        self.servers[name] = MCPServer(
                            name=name,
                            type=MCPServerType(config['type']),
                            command=config['command'],
                            args=config.get('args', []),
                            env=config.get('env'),
                            enabled=config.get('enabled', True)
                        )
                logger.info(f"[HelixMCPClient] Loaded {len(self.servers)} servers")
            except json.JSONDecodeError as e:
                logger.error(f"[HelixMCPClient] Invalid JSON in config: {e}")
            except Exception as e:
                logger.error(f"[HelixMCPClient] Failed to load MCP config: {e}")

    def _save_config(self) -> None:
        """サーバー設定を保存"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {'servers': {}}
        for name, server in self.servers.items():
            data['servers'][name] = {
                'type': server.type.value,
                'command': server.command,
                'args': server.args,
                'env': server.env,
                'enabled': server.enabled
            }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _register_builtin_tools(self) -> None:
        """組み込みツールを登録"""
        # ファイルシステムツール
        self.tool_registry['read_file'] = self._tool_read_file
        self.tool_registry['write_file'] = self._tool_write_file
        self.tool_registry['list_directory'] = self._tool_list_directory

        # Gitツール
        self.tool_registry['git_status'] = self._tool_git_status
        self.tool_registry['git_diff'] = self._tool_git_diff

    async def _tool_read_file(self, path: str) -> str:
        """
        ファイル読み込みツール（パストラバーサル保護付き）

        Args:
            path: 読み込むファイルパス

        Returns:
            ファイル内容
        """
        # パス検証
        safe_path = _validate_path(path)

        if not safe_path.is_file():
            raise FileNotFoundError(f"ファイルが見つかりません: {path}")

        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"[MCP] read_file: {safe_path}")
            return content
        except Exception as e:
            logger.error(f"[MCP] read_file failed: {e}")
            raise Exception(f"ファイル読み込みに失敗: {e}")

    async def _tool_write_file(self, path: str, content: str) -> str:
        """
        ファイル書き込みツール（パストラバーサル保護付き）

        Args:
            path: 書き込むファイルパス
            content: 書き込む内容

        Returns:
            成功メッセージ
        """
        # パス検証（親ディレクトリも検証）
        target_path = Path(path).resolve()
        parent_path = target_path.parent

        # 親ディレクトリがプロジェクト内かチェック
        _validate_path(str(parent_path))

        try:
            parent_path.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"[MCP] write_file: {target_path}")
            return f"正常に書き込みました: {target_path}"
        except Exception as e:
            logger.error(f"[MCP] write_file failed: {e}")
            raise Exception(f"ファイル書き込みに失敗: {e}")

    async def _tool_list_directory(self, path: str) -> List[str]:
        """
        ディレクトリ一覧ツール（パストラバーサル保護付き）

        Args:
            path: 一覧を取得するディレクトリパス

        Returns:
            ファイル/ディレクトリ名のリスト
        """
        # パス検証
        safe_path = _validate_path(path)

        if not safe_path.is_dir():
            raise NotADirectoryError(f"ディレクトリではありません: {path}")

        try:
            entries = [f.name for f in safe_path.iterdir()]
            logger.info(f"[MCP] list_directory: {safe_path} ({len(entries)} entries)")
            return entries
        except Exception as e:
            logger.error(f"[MCP] list_directory failed: {e}")
            raise Exception(f"ディレクトリ一覧の取得に失敗: {e}")

    async def _tool_git_status(self, repo_path: str) -> str:
        """
        Git statusツール（非同期・パス検証付き）

        Args:
            repo_path: Gitリポジトリのパス

        Returns:
            git statusの出力
        """
        # パス検証
        safe_path = _validate_path(repo_path)

        try:
            process = await asyncio.create_subprocess_exec(
                'git', 'status', '--porcelain',
                cwd=str(safe_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"git status failed: {stderr.decode('utf-8')}")

            logger.info(f"[MCP] git_status: {safe_path}")
            return stdout.decode('utf-8')
        except Exception as e:
            logger.error(f"[MCP] git_status failed: {e}")
            raise Exception(f"git statusの取得に失敗: {e}")

    async def _tool_git_diff(self, repo_path: str, file: Optional[str] = None) -> str:
        """
        Git diffツール（非同期・パス検証付き）

        Args:
            repo_path: Gitリポジトリのパス
            file: 差分を取得するファイル（オプション）

        Returns:
            git diffの出力
        """
        # パス検証
        safe_repo = _validate_path(repo_path)

        # ファイルパスの検証
        cmd = ['git', 'diff']
        if file:
            safe_file = _validate_path(file)
            # ファイルがリポジトリ内にあるか確認
            try:
                safe_file.relative_to(safe_repo)
            except ValueError:
                raise PermissionError(f"ファイル '{file}' はリポジトリ外です")
            cmd.append(str(safe_file.relative_to(safe_repo)))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(safe_repo),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"git diff failed: {stderr.decode('utf-8')}")

            logger.info(f"[MCP] git_diff: {safe_repo}")
            return stdout.decode('utf-8')
        except Exception as e:
            logger.error(f"[MCP] git_diff failed: {e}")
            raise Exception(f"git diffの取得に失敗: {e}")

    def add_server(self, server: MCPServer) -> None:
        """
        MCPサーバーを追加

        Args:
            server: サーバー設定
        """
        self.servers[server.name] = server
        self._save_config()

    def remove_server(self, name: str) -> bool:
        """
        MCPサーバーを削除

        Args:
            name: サーバー名

        Returns:
            削除成功かどうか
        """
        if name in self.servers:
            del self.servers[name]
            self._save_config()
            return True
        return False

    def enable_server(self, name: str, enabled: bool = True) -> None:
        """
        サーバーの有効/無効を切り替え

        Args:
            name: サーバー名
            enabled: 有効にするかどうか
        """
        if name in self.servers:
            self.servers[name].enabled = enabled
            self._save_config()

    async def call_tool(
        self,
        tool_call: ToolCall,
        require_approval: bool = False,
        approval_callback: Optional[Callable[[ToolCall], bool]] = None
    ) -> ToolResult:
        """
        ツールを呼び出し

        Args:
            tool_call: ツール呼び出し情報
            require_approval: 承認が必要かどうか
            approval_callback: 承認コールバック

        Returns:
            ツール実行結果
        """
        # 監査ログに記録（datetime.now()を使用）
        self.audit_log.append({
            'timestamp': datetime.now().isoformat(),
            'tool': tool_call.name,
            'arguments': tool_call.arguments,
            'require_approval': require_approval
        })

        # 承認チェック
        if require_approval:
            if approval_callback:
                if not approval_callback(tool_call):
                    logger.warning(f"[MCP] Tool execution denied: {tool_call.name}")
                    return ToolResult(
                        call_id=tool_call.id,
                        success=False,
                        result=None,
                        error="ユーザーがツール実行を拒否しました"
                    )
            else:
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error="承認が必要ですがコールバックが提供されていません"
                )

        # ツール実行
        if tool_call.name in self.tool_registry:
            try:
                result = await self.tool_registry[tool_call.name](
                    **tool_call.arguments
                )
                logger.info(f"[MCP] Tool executed: {tool_call.name}")
                return ToolResult(
                    call_id=tool_call.id,
                    success=True,
                    result=result
                )
            except PermissionError as e:
                # セキュリティエラー
                logger.error(f"[MCP] Permission denied: {tool_call.name} - {e}")
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error=f"アクセス拒否: {e}"
                )
            except FileNotFoundError as e:
                logger.warning(f"[MCP] File not found: {tool_call.name} - {e}")
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error=f"ファイルが見つかりません: {e}"
                )
            except Exception as e:
                logger.error(f"[MCP] Tool execution failed: {tool_call.name} - {e}")
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error=str(e)
                )
        else:
            return ToolResult(
                call_id=tool_call.id,
                success=False,
                result=None,
                error=f"不明なツール: {tool_call.name}"
            )

    def get_available_tools(self) -> List[str]:
        """
        利用可能なツール一覧を取得

        Returns:
            ツール名のリスト
        """
        return list(self.tool_registry.keys())

    def get_tool_descriptions(self) -> List[Dict[str, str]]:
        """
        ツールの説明を取得

        Returns:
            ツール名と説明のリスト
        """
        descriptions = {
            'read_file': 'ファイルを読み込みます（プロジェクト内のみ）',
            'write_file': 'ファイルに書き込みます（プロジェクト内のみ）',
            'list_directory': 'ディレクトリの内容を一覧表示します',
            'git_status': 'Gitリポジトリのステータスを取得します',
            'git_diff': 'Gitの差分を取得します',
        }
        return [
            {'name': name, 'description': descriptions.get(name, '説明なし')}
            for name in self.tool_registry.keys()
        ]

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """
        監査ログを取得

        Args:
            limit: 取得する最大件数

        Returns:
            監査ログエントリのリスト
        """
        return self.audit_log[-limit:]

    def clear_audit_log(self) -> None:
        """監査ログをクリア"""
        self.audit_log.clear()
        logger.info("[MCP] Audit log cleared")
