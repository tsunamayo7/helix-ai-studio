"""
Local Backend Implementation - Phase 2.0 / 3.0

ローカルAI (Trinity, Ollama など) へのコネクタ
Phase 3.0: LocalConnector統合
"""

import time
import logging
from typing import Optional
from .base import LLMBackend, BackendRequest, BackendResponse
from .local_connector import get_local_connector, ConnectionStatus

logger = logging.getLogger(__name__)


class LocalBackend(LLMBackend):
    """
    Local Backend 実装

    Trinity や Ollama などのローカルLLMへの接続インターフェース
    Phase 3.0: LocalConnectorを使用
    """

    def __init__(self, endpoint: Optional[str] = None):
        """
        Args:
            endpoint: ローカルLLMのエンドポイント (未設定でもOK)
        """
        super().__init__("local")
        self.endpoint = endpoint
        self.is_connected = False
        self.connector = get_local_connector()

        # エンドポイントが指定されていれば設定
        if endpoint:
            self.connector.set_endpoint(endpoint)

    def send(self, request: BackendRequest) -> BackendResponse:
        """
        Local LLM にメッセージを送信

        Args:
            request: Backend リクエスト

        Returns:
            Backend レスポンス
        """
        start_time = time.time()

        # Phase 3.0: LocalConnectorのステータスを確認
        connector_status = self.connector.get_status()

        # 未設定の場合
        if connector_status == ConnectionStatus.NOT_CONFIGURED:
            duration_ms = (time.time() - start_time) * 1000

            logger.warning(
                f"[LocalBackend] not configured: session={request.session_id}"
            )

            metadata = {"backend": self.name, "endpoint": None, "local_available": False}
            if request.context:
                metadata.update(request.context)

            return BackendResponse(
                success=False,
                response_text="Local backend is not configured. Set endpoint in Settings > Local接続",
                duration_ms=duration_ms,
                error_type="NotConnectedError",
                metadata=metadata
            )

        # 接続確認
        if connector_status in [ConnectionStatus.NOT_CONNECTED, ConnectionStatus.HEALTHCHECK_FAILED]:
            ok, msg = self.connector.healthcheck()
            if not ok:
                duration_ms = (time.time() - start_time) * 1000

                logger.warning(
                    f"[LocalBackend] healthcheck failed: session={request.session_id}, msg={msg}"
                )

                metadata = {"backend": self.name, "endpoint": self.connector.config.endpoint, "local_available": False}
                if request.context:
                    metadata.update(request.context)

                return BackendResponse(
                    success=False,
                    response_text=f"Local backend healthcheck failed: {msg}",
                    duration_ms=duration_ms,
                    error_type="HealthcheckFailed",
                    metadata=metadata
                )

        try:
            # Phase 3.0: LocalConnector経由で生成
            success, response_text, gen_metadata = self.connector.generate(
                prompt=request.user_text,
                options={"max_tokens": 4096}
            )

            duration_ms = (time.time() - start_time) * 1000

            if success:
                # ローカルはコスト0
                tokens_used = len(request.user_text) // 4 + len(response_text) // 4
                cost_est = 0.0

                logger.info(
                    f"[LocalBackend] send completed: session={request.session_id}, "
                    f"phase={request.phase}, duration={duration_ms:.2f}ms, "
                    f"tokens={tokens_used}"
                )

                metadata = {"backend": self.name, "endpoint": self.connector.config.endpoint, "local_available": True}
                metadata.update(gen_metadata)
                if request.context:
                    metadata.update(request.context)

                return BackendResponse(
                    success=True,
                    response_text=response_text,
                    duration_ms=duration_ms,
                    tokens_used=tokens_used,
                    cost_est=cost_est,
                    metadata=metadata
                )
            else:
                # 生成失敗
                metadata = {"backend": self.name, "endpoint": self.connector.config.endpoint, "local_available": False}
                metadata.update(gen_metadata)
                if request.context:
                    metadata.update(request.context)

                return BackendResponse(
                    success=False,
                    response_text=response_text,
                    duration_ms=duration_ms,
                    error_type=gen_metadata.get("error_type", "GenerationFailed"),
                    metadata=metadata
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                f"[LocalBackend] send failed: session={request.session_id}, "
                f"error={str(e)}"
            )

            metadata = {"backend": self.name, "endpoint": self.connector.config.endpoint, "local_available": False}
            if request.context:
                metadata.update(request.context)

            return BackendResponse(
                success=False,
                response_text=f"ローカルバックエンドでエラーが発生しました: {str(e)}",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                metadata=metadata
            )

    def supports_tools(self) -> bool:
        """Local Backend のツール使用サポート状況 (CP9)"""
        # 将来的にはLocalConnectorの機能チェックを実施
        return self._check_tools_support()

    def _check_tools_support(self) -> bool:
        """
        ツールサポートをチェック (CP9)

        実際のLocalConnectorがtools callに対応しているかを確認
        現時点ではOllama互換APIのfunction calling対応を想定
        """
        # 現時点ではtools未対応として扱う
        # 将来的には /v1/models/{model}/capabilities などを確認
        return False

    def call_tool(self, tool_name: str, tool_args: dict) -> tuple[bool, str, dict]:
        """
        ツールを呼び出し (CP9: tools call対応)

        Args:
            tool_name: ツール名
            tool_args: ツール引数

        Returns:
            (success, result_text, metadata)
        """
        if not self.supports_tools():
            return False, "Local LLMはツール呼び出しに対応していません", {"error_type": "ToolsNotSupported"}

        # 将来的にはOpenAI互換のfunction callingを実装
        # 現時点ではダミー実装
        return False, "ツール呼び出し機能は未実装です", {"error_type": "NotImplemented"}

    def healthcheck(self) -> bool:
        """
        ヘルスチェック

        Returns:
            True: 接続OK, False: 接続失敗
        """
        # Phase 3.0: LocalConnector経由でヘルスチェック
        ok, msg = self.connector.healthcheck()
        return ok

    def is_available(self) -> bool:
        """利用可能かどうか"""
        return self.connector.is_available()

    def _generate_dummy_response(self, request: BackendRequest) -> str:
        """
        ダミー応答を生成 (接続までの一時的な処理)

        Args:
            request: Backend リクエスト

        Returns:
            ダミー応答テキスト
        """
        import random
        time.sleep(random.uniform(0.5, 1.0))  # ローカルなので速め

        response = "これは Local Backend のダミー応答です。\n\n"
        response += "Local LLM (Trinity, Ollama など) が接続されると、\n"
        response += "ここにローカルで生成された応答が表示されます。\n\n"
        response += f"エンドポイント: {self.endpoint or '未設定'}\n"
        response += f"現在のフェーズ: {request.phase}\n"

        return response
