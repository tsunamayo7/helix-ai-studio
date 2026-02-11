"""
Gemini Backend Implementation - Phase 2.0 / v2.4.0

Gemini API をラップして Backend インターフェースに適合

v2.4.0 更新 (2026-01-24):
- google-generativeai (EOL 2025-11-30) から google-genai に移行
- ストリーミング応答対応
- 実API呼び出し実装

参照:
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/libraries
"""

import os
import time
import logging
from typing import Optional, Generator, Callable

from .base import LLMBackend, BackendRequest, BackendResponse

logger = logging.getLogger(__name__)

# google-genai ライブラリのインポート
_genai_available = False
_genai_client = None

try:
    from google import genai
    from google.genai import types
    _genai_available = True
except ImportError:
    logger.warning("[GeminiBackend] google-genai not installed. Install with: pip install google-genai")


def _get_genai_client():
    """Gemini APIクライアントを取得（遅延初期化）"""
    global _genai_client
    if _genai_client is None and _genai_available:
        # 環境変数からAPIキーを取得
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            _genai_client = genai.Client(api_key=api_key)
        else:
            logger.warning("[GeminiBackend] GEMINI_API_KEY not set")
    return _genai_client


class GeminiBackend(LLMBackend):
    """
    Gemini Backend 実装

    google-genai ライブラリを使用した実API呼び出し
    ストリーミング応答対応
    """

    # モデル名マッピング (内部名 -> API名)
    MODEL_MAPPING = {
        "gemini-3-pro": "gemini-2.5-pro",       # 最新Pro
        "gemini-3-flash": "gemini-2.5-flash",   # 最新Flash (高速)
        "gemini-2-pro": "gemini-2.0-pro",       # Gemini 2.0 Pro
        "gemini-2-flash": "gemini-2.0-flash",   # Gemini 2.0 Flash
        "gemini-1.5-pro": "gemini-1.5-pro",     # 旧世代
    }

    def __init__(self, model: str = "gemini-3-flash"):
        """
        Args:
            model: Gemini モデル名 (内部名またはAPI名)
        """
        super().__init__(f"gemini-{model}")
        self.model = model
        self._api_model = self.MODEL_MAPPING.get(model, model)
        self._streaming_callback: Optional[Callable[[str], None]] = None

    def set_streaming_callback(self, callback: Optional[Callable[[str], None]]):
        """ストリーミングコールバックを設定"""
        self._streaming_callback = callback

    def send(self, request: BackendRequest) -> BackendResponse:
        """
        Gemini にメッセージを送信

        Args:
            request: Backend リクエスト

        Returns:
            Backend レスポンス
        """
        start_time = time.time()

        try:
            # google-genaiが利用可能かチェック
            if not _genai_available:
                return self._create_error_response(
                    request, start_time,
                    "google-genai がインストールされていません。pip install google-genai を実行してください。",
                    "ImportError"
                )

            client = _get_genai_client()
            if client is None:
                return self._create_error_response(
                    request, start_time,
                    "Gemini API キーが設定されていません。環境変数 GEMINI_API_KEY を設定してください。",
                    "AuthenticationError"
                )

            # ストリーミングで応答を取得
            response_text = ""
            input_tokens = 0
            output_tokens = 0

            if self._streaming_callback:
                # ストリーミングモード
                for chunk in client.models.generate_content_stream(
                    model=self._api_model,
                    contents=[request.user_text],
                ):
                    if chunk.text:
                        response_text += chunk.text
                        self._streaming_callback(chunk.text)
                    # トークン情報を取得
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        input_tokens = getattr(chunk.usage_metadata, 'prompt_token_count', 0) or 0
                        output_tokens = getattr(chunk.usage_metadata, 'candidates_token_count', 0) or 0
            else:
                # 非ストリーミングモード
                response = client.models.generate_content(
                    model=self._api_model,
                    contents=[request.user_text],
                )
                response_text = response.text or ""
                # トークン情報を取得
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0

            duration_ms = (time.time() - start_time) * 1000

            # トークン数とコストの推定
            tokens_used = input_tokens + output_tokens
            if tokens_used == 0:
                tokens_used = len(request.user_text) // 4 + len(response_text) // 4
            cost_est = self._estimate_cost(input_tokens, output_tokens)

            logger.info(
                f"[GeminiBackend] send completed: session={request.session_id}, "
                f"phase={request.phase}, duration={duration_ms:.2f}ms, "
                f"tokens={tokens_used}, cost=${cost_est:.6f}, model={self._api_model}"
            )

            metadata = {
                "model": self._api_model,
                "backend": self.name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
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

        except Exception as e:
            return self._create_error_response(request, start_time, str(e), type(e).__name__)

    def _create_error_response(
        self,
        request: BackendRequest,
        start_time: float,
        error_msg: str,
        error_type: str
    ) -> BackendResponse:
        """エラーレスポンスを生成"""
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            f"[GeminiBackend] send failed: session={request.session_id}, "
            f"error={error_msg}"
        )

        metadata = {"model": self._api_model, "backend": self.name}
        if request.context:
            metadata.update(request.context)

        return BackendResponse(
            success=False,
            response_text=f"Gemini APIエラー: {error_msg}",
            duration_ms=duration_ms,
            error_type=error_type,
            metadata=metadata
        )

    def supports_tools(self) -> bool:
        """Gemini はツール使用をサポート"""
        return True

    def generate_stream(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Generator[str, None, None]:
        """
        ストリーミング生成（ジェネレータ版）

        Args:
            prompt: 入力プロンプト
            on_token: トークン受信時のコールバック

        Yields:
            生成されたテキストチャンク
        """
        if not _genai_available:
            yield "エラー: google-genai がインストールされていません"
            return

        client = _get_genai_client()
        if client is None:
            yield "エラー: GEMINI_API_KEY が設定されていません"
            return

        try:
            for chunk in client.models.generate_content_stream(
                model=self._api_model,
                contents=[prompt],
            ):
                if chunk.text:
                    if on_token:
                        on_token(chunk.text)
                    yield chunk.text
        except Exception as e:
            logger.error(f"[GeminiBackend] Stream error: {e}")
            yield f"エラー: {e}"

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        コスト推定 (2026年1月時点の料金表)

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数

        Returns:
            推定コスト (USD)
        """
        # Gemini 2.5 Pro / Flash の料金 (2026年1月時点、推定)
        # Pro: $0.00125 / 1K input, $0.005 / 1K output
        # Flash: $0.000075 / 1K input, $0.0003 / 1K output
        if "pro" in self._api_model.lower():
            input_cost = (input_tokens / 1000) * 0.00125
            output_cost = (output_tokens / 1000) * 0.005
        else:
            input_cost = (input_tokens / 1000) * 0.000075
            output_cost = (output_tokens / 1000) * 0.0003

        return input_cost + output_cost

    def is_available(self) -> bool:
        """APIが利用可能かどうか"""
        return _genai_available and _get_genai_client() is not None

    def get_model_info(self) -> dict:
        """モデル情報を取得"""
        return {
            "internal_name": self.model,
            "api_name": self._api_model,
            "available": self.is_available(),
            "supports_streaming": True,
            "supports_tools": True,
        }
