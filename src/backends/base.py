"""
Backend Base Classes - Phase 2.0

LLM Backend の基底クラス定義
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable
from datetime import datetime


@dataclass
class BackendRequest:
    """
    Backend への送信リクエスト

    Attributes:
        session_id: セッションID
        phase: 現在のワークフローフェーズ (e.g. "S2", "S4")
        user_text: ユーザーの入力テキスト
        attachments: 添付ファイル情報
        toggles: UI トグル状態 (MCP, Diff, Context など)
        context: 追加コンテキスト情報
    """
    session_id: str
    phase: str
    user_text: str
    attachments: Optional[list] = None
    toggles: Optional[Dict[str, bool]] = field(default_factory=dict)
    context: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class BackendResponse:
    """
    Backend からの応答

    Attributes:
        success: 成功/失敗
        response_text: 応答テキスト
        duration_ms: 処理時間 (ミリ秒)
        tokens_used: 使用トークン数 (推定値でもOK)
        cost_est: コスト推定値 (USD)
        error_type: エラー種別 (失敗時のみ)
        metadata: その他メタデータ
    """
    success: bool
    response_text: str
    duration_ms: float
    tokens_used: Optional[int] = None
    cost_est: Optional[float] = None
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


class LLMBackend(ABC):
    """
    LLM Backend の基底クラス

    全ての Backend 実装はこのクラスを継承する
    """

    def __init__(self, name: str):
        """
        Args:
            name: Backend 名 (e.g. "claude-sonnet", "gemini-pro", "local")
        """
        self.name = name

    @abstractmethod
    def send(self, request: BackendRequest) -> BackendResponse:
        """
        同期的にメッセージを送信

        Args:
            request: Backend リクエスト

        Returns:
            Backend レスポンス
        """
        pass

    def stream(self, request: BackendRequest, on_token: Callable[[str], None]) -> None:
        """
        ストリーミング送信 (オプション)

        Args:
            request: Backend リクエスト
            on_token: トークン受信時のコールバック
        """
        # デフォルト実装: send() を呼び出して一括で返す
        response = self.send(request)
        if response.success:
            on_token(response.response_text)

    def supports_tools(self) -> bool:
        """
        ツール使用のサポート有無

        Returns:
            True: ツール使用可能, False: 不可
        """
        return False

    def get_name(self) -> str:
        """Backend 名を取得"""
        return self.name
