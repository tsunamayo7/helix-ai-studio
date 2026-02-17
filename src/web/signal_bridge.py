"""
Helix AI Studio - Signal Bridge (v9.0.0)

既存のpyqtSignal → WebSocket中継ブリッジ。
既存コードの変更ゼロで、PyQt6シグナルをWebクライアントに転送する。

動作原理:
  1. MixAIOrchestrator / ClaudeCLIBackend のインスタンスが生成されたら
     このブリッジにシグナルを接続する
  2. pyqtSignalが発火するたびにコールバックが呼ばれる
  3. コールバック内でasyncioイベントループにWebSocket送信をスケジュール
  4. WebSocketManagerが該当クライアントにJSON送信

重要な技術的考慮:
  - pyqtSignalはQtメインスレッド（またはQThread）で発火する
  - WebSocket送信はasyncioイベントループで実行する
  - スレッド間通信には asyncio.run_coroutine_threadsafe() を使用
"""

import asyncio
import json
import logging
from typing import Optional

from .ws_manager import WebSocketManager

logger = logging.getLogger(__name__)


class SignalBridge:
    """pyqtSignal → WebSocket ブリッジ"""

    def __init__(self, ws_manager: WebSocketManager, loop: asyncio.AbstractEventLoop):
        self._ws_manager = ws_manager
        self._loop = loop
        self._connections: list = []  # シグナル接続を追跡（切断用）

    def bridge_solo_ai(self, backend, client_id: str):
        """
        soloAI (Claude CLI) バックエンドのシグナルをWebSocketにブリッジ。

        接続するシグナル:
          - streaming_output(str)  → {"type": "streaming", "chunk": ..., "done": false}
          - all_finished(str)      → {"type": "streaming", "chunk": ..., "done": true}
          - error_occurred(str)    → {"type": "error", "error": ...}

        注: soloAIバックエンドの実装によってシグナル名が異なる場合があるので、
            claude_tab.pyのコード(_on_cli_response等)から実際のシグナル接続を確認する。
            Phase 1ではClaude CLIの非対話モード(`claude -p`)を直接呼び出し、
            結果をWebSocket経由で返す簡易実装とする。
        """

        def on_streaming(chunk: str):
            self._schedule_send(client_id, {
                "type": "streaming",
                "chunk": chunk,
                "done": False,
            })

        def on_finished(result: str):
            self._schedule_send(client_id, {
                "type": "streaming",
                "chunk": result,
                "done": True,
            })

        def on_error(error: str):
            self._schedule_send(client_id, {
                "type": "error",
                "error": error,
            })

        # シグナル接続（存在する場合のみ）
        if hasattr(backend, 'streaming_output'):
            backend.streaming_output.connect(on_streaming)
        if hasattr(backend, 'all_finished'):
            backend.all_finished.connect(on_finished)
        if hasattr(backend, 'error_occurred'):
            backend.error_occurred.connect(on_error)

        logger.info(f"Signal bridge connected for soloAI → client {client_id}")

    def bridge_mix_ai(self, orchestrator, client_id: str):
        """
        mixAIオーケストレーターのシグナルをWebSocketにブリッジ。
        （Phase 2で実装）

        接続するシグナル:
          - phase_changed(int, str)
          - streaming_output(str)
          - local_llm_started(str, str)
          - local_llm_finished(str, bool, float)
          - phase2_progress(int, int)
          - all_finished(str)
          - error_occurred(str)
        """
        # Phase 2 で実装
        pass

    def _schedule_send(self, client_id: str, message: dict):
        """
        asyncioイベントループにWebSocket送信をスケジュール。
        pyqtSignalのコールバック（Qtスレッド）からasyncio（別スレッド）へ安全に送信。
        """
        try:
            asyncio.run_coroutine_threadsafe(
                self._ws_manager.send_to(client_id, message),
                self._loop,
            )
        except Exception as e:
            logger.error(f"Signal bridge send error: {e}")
