"""
Helix AI Studio - WebSocket接続管理 (v9.0.0)

WebSocket接続のライフサイクル管理:
  - 接続プール管理
  - 認証済み接続のみ保持
  - ブロードキャスト / ユニキャスト送信
  - 自動切断 (ping/pong)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """WebSocket接続クライアント"""
    websocket: WebSocket
    client_id: str
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    active_task: Optional[str] = None  # "soloAI" / "mixAI" / None


class WebSocketManager:
    """WebSocket接続プールマネージャー"""

    def __init__(self, max_connections: int = 3):
        self._clients: dict[str, WebSocketClient] = {}
        self._max_connections = max_connections
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """
        WebSocket接続を受け入れ。
        最大接続数を超える場合はFalseを返す。
        """
        async with self._lock:
            if len(self._clients) >= self._max_connections:
                logger.warning(f"Max WebSocket connections reached ({self._max_connections})")
                return False

            await websocket.accept()
            self._clients[client_id] = WebSocketClient(
                websocket=websocket,
                client_id=client_id,
            )
            logger.info(f"WebSocket connected: {client_id} (total: {len(self._clients)})")
            return True

    async def disconnect(self, client_id: str):
        """WebSocket切断"""
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"WebSocket disconnected: {client_id} (total: {len(self._clients)})")

    async def send_to(self, client_id: str, message: dict):
        """特定クライアントにJSON送信"""
        client = self._clients.get(client_id)
        if client:
            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket send error to {client_id}: {e}")
                await self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: str = None):
        """全クライアントにブロードキャスト"""
        disconnected = []
        for cid, client in self._clients.items():
            if cid == exclude:
                continue
            try:
                await client.websocket.send_json(message)
            except Exception:
                disconnected.append(cid)

        for cid in disconnected:
            await self.disconnect(cid)

    async def send_streaming(self, client_id: str, chunk: str, done: bool = False):
        """ストリーミングチャンク送信"""
        await self.send_to(client_id, {
            "type": "streaming",
            "chunk": chunk,
            "done": done,
        })

    async def send_status(self, client_id: str, status: str, detail: str = ""):
        """ステータス更新送信"""
        await self.send_to(client_id, {
            "type": "status",
            "status": status,
            "detail": detail,
        })

    async def send_error(self, client_id: str, error: str):
        """エラー送信"""
        await self.send_to(client_id, {
            "type": "error",
            "error": error,
        })

    def set_active_task(self, client_id: str, task: str | None):
        """クライアントのアクティブタスクを設定"""
        if client_id in self._clients:
            self._clients[client_id].active_task = task

    def get_client(self, client_id: str) -> WebSocketClient | None:
        """クライアント情報取得"""
        return self._clients.get(client_id)
