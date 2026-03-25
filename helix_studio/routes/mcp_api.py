"""MCP サーバー管理 API ルーター"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from helix_studio.services.mcp_client import MCPServerConfig, mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPServerStartRequest(BaseModel):
    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] | None = None


class MCPToolCallRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = {}


@router.get("/servers")
async def list_servers() -> list[dict[str, Any]]:
    """起動中の MCP サーバー一覧。"""
    return mcp_manager.get_server_status()


@router.post("/servers/start")
async def start_server(req: MCPServerStartRequest) -> dict[str, Any]:
    """MCP サーバーを起動。"""
    config = MCPServerConfig(
        name=req.name,
        command=req.command,
        args=req.args,
        env=req.env,
    )
    ok = await mcp_manager.start_server(config)
    if not ok:
        raise HTTPException(status_code=500, detail=f"サーバー '{req.name}' の起動に失敗しました")
    return {"ok": True, "name": req.name, "tools": len(mcp_manager.get_all_tools())}


@router.post("/servers/{name}/stop")
async def stop_server(name: str) -> dict[str, Any]:
    """MCP サーバーを停止。"""
    await mcp_manager.stop_server(name)
    return {"ok": True, "name": name}


@router.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """全サーバーのツール一覧。"""
    return [
        {
            "name": t.name,
            "description": t.description,
            "server": t.server_name,
            "input_schema": t.input_schema,
        }
        for t in mcp_manager.get_all_tools()
    ]


@router.post("/tools/call")
async def call_tool(req: MCPToolCallRequest) -> dict[str, Any]:
    """MCP ツールを実行。"""
    result = await mcp_manager.call_tool(req.server_name, req.tool_name, req.arguments)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True, "result": result}
