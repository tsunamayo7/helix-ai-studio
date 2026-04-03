"""MCP クライアント — stdio transport でローカル MCP サーバーを管理

settings DB に登録された MCP サーバーを起動し、
JSON-RPC over stdio でツール一覧取得・ツール実行を行う。

mcp SDK を使わず、最小限の JSON-RPC 実装で依存を抑える。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# JSON-RPC ID カウンタ
_next_id = 0


def _get_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


@dataclass
class MCPServerConfig:
    """MCP サーバー設定。"""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class MCPTool:
    """MCP ツール定義。"""
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""


class MCPSession:
    """1 つの MCP サーバーとの stdio セッション。"""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._tools: list[MCPTool] = []
        self._initialized = False

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> bool:
        """サーバープロセスを起動し initialize ハンドシェイクを行う。"""
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=None,  # 親プロセスの環境変数を継承
            )
        except FileNotFoundError:
            logger.warning("MCP server '%s' command not found: %s",
                           self.config.name, self.config.command)
            return False
        except Exception as e:
            logger.warning("MCP server '%s' failed to start: %s", self.config.name, e)
            return False

        # initialize handshake
        resp = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "helix-ai-studio", "version": "2.1.0"},
        })
        if resp is None:
            await self.stop()
            return False

        # initialized notification
        await self._send_notification("notifications/initialized", {})

        # ツール一覧取得
        tools_resp = await self._send_request("tools/list", {})
        if tools_resp and "tools" in tools_resp:
            self._tools = [
                MCPTool(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_name=self.config.name,
                )
                for t in tools_resp["tools"]
            ]

        self._initialized = True
        logger.info("MCP server '%s' started (%d tools)", self.config.name, len(self._tools))
        return True

    async def stop(self) -> None:
        """サーバープロセスを停止。"""
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
        self._process = None
        self._initialized = False
        self._tools = []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """ツールを呼び出す。"""
        if not self.is_running:
            return {"error": f"Server '{self.config.name}' is not running"}

        resp = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        return resp

    def get_tools(self) -> list[MCPTool]:
        """利用可能なツール一覧を返す。"""
        return list(self._tools)

    async def _send_request(self, method: str, params: dict) -> dict | None:
        """JSON-RPC リクエストを送信し応答を待つ。"""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None

        req_id = _get_id()
        msg = json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }) + "\n"

        try:
            self._process.stdin.write(msg.encode())
            await self._process.stdin.drain()

            # 応答を読む (タイムアウト付き)
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            if not line:
                return None

            data = json.loads(line.decode())

            # notification をスキップして次の行を読む
            while "id" not in data:
                line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=10.0
                )
                if not line:
                    return None
                data = json.loads(line.decode())

            if "error" in data:
                logger.warning("MCP error: %s", data["error"])
                return None
            return data.get("result")
        except asyncio.TimeoutError:
            logger.warning("MCP request timeout: %s.%s", self.config.name, method)
            return None
        except Exception as e:
            logger.warning("MCP communication error: %s", e)
            return None

    async def _send_notification(self, method: str, params: dict) -> None:
        """JSON-RPC notification を送信 (応答なし)。"""
        if not self._process or not self._process.stdin:
            return
        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }) + "\n"
        try:
            self._process.stdin.write(msg.encode())
            await self._process.stdin.drain()
        except Exception:
            pass


class MCPManager:
    """全 MCP サーバーセッションを管理するシングルトン。"""

    def __init__(self):
        self._sessions: dict[str, MCPSession] = {}

    async def start_server(self, config: MCPServerConfig) -> bool:
        """サーバーを起動してセッションを登録。"""
        if config.name in self._sessions:
            await self.stop_server(config.name)

        session = MCPSession(config)
        ok = await session.start()
        if ok:
            self._sessions[config.name] = session
        return ok

    async def stop_server(self, name: str) -> None:
        """サーバーを停止。"""
        session = self._sessions.pop(name, None)
        if session:
            await session.stop()

    async def stop_all(self) -> None:
        """全サーバーを停止。"""
        for name in list(self._sessions.keys()):
            await self.stop_server(name)

    def get_all_tools(self) -> list[MCPTool]:
        """全サーバーのツール一覧を返す。"""
        tools: list[MCPTool] = []
        for session in self._sessions.values():
            if session.is_running:
                tools.extend(session.get_tools())
        return tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """指定サーバーのツールを呼び出す。"""
        session = self._sessions.get(server_name)
        if not session:
            return {"error": f"Server '{server_name}' not found"}
        return await session.call_tool(tool_name, arguments)

    def get_server_status(self) -> list[dict[str, Any]]:
        """全サーバーのステータスを返す。"""
        return [
            {
                "name": name,
                "running": session.is_running,
                "tools_count": len(session.get_tools()),
            }
            for name, session in self._sessions.items()
        ]


# グローバルインスタンス
mcp_manager = MCPManager()
