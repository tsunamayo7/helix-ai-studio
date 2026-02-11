"""
Claude Backend Implementation - Phase 2.0

Claude APIを呼び出してBackendインターフェースに適合

Version: 2.1.0 - 実際のClaude API統合
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any
from .base import LLMBackend, BackendRequest, BackendResponse

logger = logging.getLogger(__name__)


class ClaudeBackend(LLMBackend):
    """
    Claude Backend 実装

    Anthropic Claude APIを使用した実際のAI応答生成
    """

    # モデルID マッピング (2026年1月更新)
    # 参照: https://platform.claude.com/docs/en/about-claude/models/overview
    MODEL_MAP = {
        # Claude Sonnet 4.5 (推奨) - $3/$15 per MTok
        "sonnet-4-5": "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
        # Claude Opus - $5/$25 per MTok
        "opus-4-5": "claude-opus-4-5-20251101",
        "claude-opus-4-5": "claude-opus-4-5-20251101",
        # Claude Haiku 4.5 (高速) - $1/$5 per MTok
        "haiku-4-5": "claude-haiku-4-5-20251001",
        "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    }

    def __init__(self, model: str = "claude-sonnet-4-5"):
        """
        Args:
            model: Claude モデル名
        """
        super().__init__(f"claude-{model}")
        self.model = model
        self._client = None
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._init_client()

    def _init_client(self):
        """Anthropicクライアントを初期化"""
        if not self._api_key:
            logger.warning("[ClaudeBackend] ANTHROPIC_API_KEY not set. API calls will fail.")
            return

        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self._api_key)
            logger.info(f"[ClaudeBackend] Initialized with model: {self.model}")
        except ImportError:
            logger.error("[ClaudeBackend] anthropic package not installed")
            self._client = None
        except Exception as e:
            logger.error(f"[ClaudeBackend] Failed to initialize client: {e}")
            self._client = None

    def _get_model_id(self) -> str:
        """モデルIDを取得"""
        return self.MODEL_MAP.get(self.model, self.model)

    def send(self, request: BackendRequest) -> BackendResponse:
        """
        Claude にメッセージを送信

        Args:
            request: Backend リクエスト

        Returns:
            Backend レスポンス
        """
        start_time = time.time()

        try:
            # APIクライアントが利用不可の場合
            if not self._client:
                if not self._api_key:
                    return BackendResponse(
                        success=False,
                        response_text="エラー: ANTHROPIC_API_KEY環境変数が設定されていません。\n\n"
                                     "【API従量課金の場合】\n"
                                     "1. Anthropicコンソール（https://console.anthropic.com）でAPIキーを取得\n"
                                     "2. 環境変数に設定: set ANTHROPIC_API_KEY=sk-ant-...\n"
                                     "3. アプリを再起動\n\n"
                                     "【Claude Max/Proプランをお持ちの方】\n"
                                     "⚠️ 重要: Max/ProプランのサブスクリプションはClaude Code CLIでのみ使用可能です。\n"
                                     "Helix AI StudioはAnthropic APIを直接呼び出すため、\n"
                                     "Maxプランの使用量にはカウントされません。\n\n"
                                     "【モデル切り替えについて】\n"
                                     "・Sonnet: $3/$15 per MTok - バランス重視\n"
                                     "・Opus: $5/$25 per MTok - 最高性能\n\n"
                                     "参照: https://support.claude.com/ja/articles/11145838",
                        duration_ms=0,
                        error_type="APIKeyMissing",
                        metadata={"model": self.model, "backend": self.name}
                    )
                else:
                    return BackendResponse(
                        success=False,
                        response_text="エラー: Anthropicクライアントの初期化に失敗しました。"
                                     "anthropicパッケージがインストールされているか確認してください。",
                        duration_ms=0,
                        error_type="ClientInitError",
                        metadata={"model": self.model, "backend": self.name}
                    )

            # システムプロンプトを構築
            system_prompt = self._build_system_prompt(request)

            # メッセージを構築
            messages = self._build_messages(request)

            # モデルIDを取得
            model_id = self._get_model_id()

            # API呼び出し
            logger.info(f"[ClaudeBackend] Calling API: model={model_id}, session={request.session_id}")

            response = self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )

            # 応答テキストを抽出
            response_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text

            duration_ms = (time.time() - start_time) * 1000

            # トークン数とコスト
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            tokens_used = input_tokens + output_tokens
            cost_est = self._estimate_cost(input_tokens, output_tokens)

            logger.info(
                f"[ClaudeBackend] API call completed: session={request.session_id}, "
                f"phase={request.phase}, duration={duration_ms:.2f}ms, "
                f"tokens={tokens_used} (in={input_tokens}, out={output_tokens}), "
                f"cost=${cost_est:.6f}"
            )

            # Phase 2.3: リクエストのcontextをmetadataにマージ
            metadata = {
                "model": self.model,
                "model_id": model_id,
                "backend": self.name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "stop_reason": response.stop_reason
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
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                f"[ClaudeBackend] send failed: session={request.session_id}, "
                f"error={str(e)}",
                exc_info=True
            )

            # エラータイプに応じたメッセージ
            error_message = f"Claude API呼び出し中にエラーが発生しました:\n\n{type(e).__name__}: {str(e)}"

            if "rate_limit" in str(e).lower():
                error_message += "\n\nAPIレート制限に達しました。しばらく待ってから再試行してください。"
            elif "authentication" in str(e).lower() or "api_key" in str(e).lower():
                error_message += "\n\nAPIキーが無効です。正しいキーが設定されているか確認してください。"
            elif "overloaded" in str(e).lower():
                error_message += "\n\nAPIサーバーが混雑しています。しばらく待ってから再試行してください。"

            # Phase 2.3: リクエストのcontextをmetadataにマージ
            metadata = {"model": self.model, "backend": self.name}
            if request.context:
                metadata.update(request.context)

            return BackendResponse(
                success=False,
                response_text=error_message,
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                metadata=metadata
            )

    def _build_system_prompt(self, request: BackendRequest) -> str:
        """システムプロンプトを構築"""
        system = f"""あなたはHelix AI Studioの論理設計・アーキテクチャ担当AIアシスタントです。

現在のワークフローフェーズ: {request.phase}
セッションID: {request.session_id}

あなたの役割:
- アプリケーションの論理設計とバックエンド構築を支援
- コード品質とベストプラクティスを重視
- 明確で実行可能な提案を行う
- 日本語で回答する

回答時の注意点:
- 具体的で実装可能なコードを提示
- 変更の影響範囲を説明
- 潜在的なリスクや注意点を指摘
"""

        # コンテキスト情報を追加
        if request.context:
            if request.context.get("project_bible"):
                system += f"\n\nプロジェクト情報:\n{request.context['project_bible'][:2000]}"
            if request.context.get("current_files"):
                system += f"\n\n関連ファイル:\n{request.context['current_files'][:1000]}"

        return system

    def _build_messages(self, request: BackendRequest) -> List[Dict[str, Any]]:
        """メッセージリストを構築"""
        messages = []

        # 会話履歴があれば追加
        if request.context and request.context.get("history"):
            for msg in request.context["history"][-10:]:  # 最新10件
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # 現在のユーザーメッセージ
        messages.append({
            "role": "user",
            "content": request.user_text
        })

        return messages

    def supports_tools(self) -> bool:
        """Claude はツール使用をサポート"""
        return True

    def is_available(self) -> bool:
        """APIが利用可能かどうか"""
        return self._client is not None

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        コスト推定

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数

        Returns:
            推定コスト (USD)
        """
        # Claude API 料金体系 (2026年1月時点)
        # https://platform.claude.com/docs/en/about-claude/models/overview
        if "sonnet" in self.model.lower():
            # Claude Sonnet 4.5: $3/$15 per MTok (in/out)
            input_cost_per_1m = 3.0
            output_cost_per_1m = 15.0
        elif "opus" in self.model.lower():
            # Claude Opus: $5/$25 per MTok (in/out)
            input_cost_per_1m = 5.0
            output_cost_per_1m = 25.0
        elif "haiku" in self.model.lower():
            # Claude Haiku 4.5: $1/$5 per MTok (in/out)
            input_cost_per_1m = 1.0
            output_cost_per_1m = 5.0
        else:
            # デフォルトはSonnet相当
            input_cost_per_1m = 3.0
            output_cost_per_1m = 15.0

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m

        return input_cost + output_cost
