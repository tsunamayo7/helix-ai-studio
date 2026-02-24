"""
Helix AI Studio - Anthropic Direct API Backend (v11.4.0)

Anthropic SDK を使用した直接 API 接続バックエンド。
APIキーが設定されている場合に使用する。
OAuthトークンは一切取り扱わない。

利用には `anthropic` パッケージが必要:
    pip install anthropic>=0.40.0
"""
import logging
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


def is_anthropic_sdk_available() -> bool:
    """anthropic パッケージがインストールされているか確認"""
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def get_anthropic_api_key() -> Optional[str]:
    """
    general_settings.json から Anthropic API キーを読み込む。
    キーが空・未設定の場合は None を返す。
    環境変数 ANTHROPIC_API_KEY も参照する（環境変数優先）。
    """
    import os
    # 環境変数優先
    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_key:
        return env_key

    # general_settings.json から読み込み
    try:
        from pathlib import Path
        import json
        settings_path = Path("config/general_settings.json")
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            key = data.get("anthropic_api_key", "").strip()
            if key:
                return key
    except Exception as e:
        logger.debug(f"[AnthropicAPI] API key load failed: {e}")
    return None


def call_anthropic_api_stream(
    prompt: str,
    model_id: str = "",
    system_prompt: str = "",
    max_tokens: int = 8192,
    api_key: Optional[str] = None,
) -> Iterator[str]:
    """
    Anthropic API をストリーミング呼び出しし、テキストチャンクを yield する。

    Args:
        prompt: ユーザープロンプト
        model_id: Claude モデル ID（例: "claude-sonnet-4-6"）
        system_prompt: システムプロンプト（空文字列の場合はデフォルトなし）
        max_tokens: 最大トークン数
        api_key: API キー（None の場合は get_anthropic_api_key() を使用）

    Yields:
        テキストチャンク（str）

    Raises:
        ImportError: anthropic パッケージ未インストール
        ValueError: API キーが設定されていない
        Exception: API 呼び出し失敗
    """
    if not is_anthropic_sdk_available():
        raise ImportError(
            "anthropic パッケージが必要です: pip install anthropic>=0.40.0"
        )

    key = api_key or get_anthropic_api_key()
    if not key:
        raise ValueError(
            "Anthropic API キーが設定されていません。\n"
            "一般設定 → API Keys → Anthropic API Key に設定してください。\n"
            "または環境変数 ANTHROPIC_API_KEY を設定してください。"
        )

    import anthropic

    client = anthropic.Anthropic(api_key=key)

    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    try:
        with client.messages.stream(**kwargs) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk
    except anthropic.AuthenticationError:
        raise ValueError(
            "Anthropic API キーが無効です。\n"
            "一般設定 → API Keys で正しいキーを設定してください。"
        )
    except anthropic.RateLimitError:
        raise RuntimeError(
            "Anthropic API のレート制限に達しました。\n"
            "しばらく待ってから再試行してください。"
        )
    except Exception as e:
        logger.error(f"[AnthropicAPI] API call failed: {e}")
        raise


def call_anthropic_api(
    prompt: str,
    model_id: str = "",
    system_prompt: str = "",
    max_tokens: int = 8192,
    api_key: Optional[str] = None,
) -> str:
    """
    Anthropic API を非ストリーミング呼び出しし、完全なレスポンスを返す。
    RAG Planner等の同期バッチ処理向け。
    """
    chunks = list(call_anthropic_api_stream(
        prompt=prompt,
        model_id=model_id,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        api_key=api_key,
    ))
    return "".join(chunks)
