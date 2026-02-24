"""
Helix AI Studio - OpenAI Direct API Backend (v11.4.0)

OpenAI SDK を使用した直接 API 接続バックエンド。
APIキーが設定されている場合に使用する。
アカウント資格情報・OAuthトークンは一切取り扱わない。

利用には `openai` パッケージが必要:
    pip install openai>=1.0.0
"""
import logging
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# v11.4.0: サポートモデル一覧
OPENAI_SUPPORTED_MODELS = {
    "gpt-4o": "GPT-4o (最高性能)",
    "gpt-4o-mini": "GPT-4o mini (高速・低コスト)",
    "gpt-4.1": "GPT-4.1",
    "gpt-4.1-mini": "GPT-4.1 mini",
    "o3": "o3 (推論特化)",
    "o4-mini": "o4-mini (推論・高速)",
}


def is_openai_sdk_available() -> bool:
    """openai パッケージがインストールされているか確認"""
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


def get_openai_api_key() -> Optional[str]:
    """
    general_settings.json から OpenAI API キーを読み込む。
    環境変数 OPENAI_API_KEY も参照する（環境変数優先）。
    """
    import os
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    try:
        from pathlib import Path
        import json
        settings_path = Path("config/general_settings.json")
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            key = data.get("openai_api_key", "").strip()
            if key:
                return key
    except Exception as e:
        logger.debug(f"[OpenAIAPI] API key load failed: {e}")
    return None


def call_openai_api_stream(
    prompt: str,
    model_id: str = "gpt-4o",
    system_prompt: str = "",
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> Iterator[str]:
    """
    OpenAI Chat Completions API をストリーミング呼び出しし、テキストチャンクを yield する。

    Args:
        prompt: ユーザープロンプト
        model_id: OpenAI モデル ID（例: "gpt-4o", "gpt-4o-mini"）
        system_prompt: システムプロンプト
        max_tokens: 最大トークン数
        api_key: API キー（None の場合は get_openai_api_key() を使用）

    Yields:
        テキストチャンク（str）
    """
    if not is_openai_sdk_available():
        raise ImportError(
            "openai パッケージが必要です: pip install openai>=1.0.0"
        )

    key = api_key or get_openai_api_key()
    if not key:
        raise ValueError(
            "OpenAI API キーが設定されていません。\n"
            "一般設定 → API Keys → OpenAI API Key に設定してください。\n"
            "または環境変数 OPENAI_API_KEY を設定してください。"
        )

    import openai

    client = openai.OpenAI(api_key=key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except openai.AuthenticationError:
        raise ValueError(
            "OpenAI API キーが無効です。\n"
            "一般設定 → API Keys で正しいキーを設定してください。"
        )
    except openai.RateLimitError:
        raise RuntimeError(
            "OpenAI API のレート制限に達しました。\n"
            "しばらく待ってから再試行してください。"
        )
    except Exception as e:
        logger.error(f"[OpenAIAPI] API call failed: {e}")
        raise


def call_openai_api(
    prompt: str,
    model_id: str = "gpt-4o",
    system_prompt: str = "",
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> str:
    """OpenAI API を非ストリーミング呼び出しし、完全なレスポンスを返す。"""
    chunks = list(call_openai_api_stream(
        prompt=prompt,
        model_id=model_id,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        api_key=api_key,
    ))
    return "".join(chunks)
