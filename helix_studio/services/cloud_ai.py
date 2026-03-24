"""クラウドLLMクライアント — Claude API + OpenAI API"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import anthropic
import openai

logger = logging.getLogger(__name__)


async def stream_chat_claude(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system: str = "",
) -> AsyncIterator[str]:
    """Anthropic Claude API でストリーミングチャット。"""
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # systemメッセージをmessagesから分離
    filtered = [m for m in messages if m["role"] != "system"]
    system_text = system
    if not system_text:
        sys_msgs = [m for m in messages if m["role"] == "system"]
        if sys_msgs:
            system_text = sys_msgs[-1]["content"]

    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": filtered,
    }
    if system_text:
        kwargs["system"] = system_text

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


async def stream_chat_openai(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """OpenAI API でストリーミングチャット。"""
    client = openai.AsyncOpenAI(api_key=api_key)

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def stream_chat(
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system: str = "",
) -> AsyncIterator[str]:
    """プロバイダに応じたストリーミングチャット統合インターフェース。"""
    if provider == "claude":
        async for chunk in stream_chat_claude(api_key, model, messages, system):
            yield chunk
    elif provider == "openai":
        async for chunk in stream_chat_openai(api_key, model, messages):
            yield chunk
    else:
        raise ValueError(f"未対応のクラウドプロバイダ: {provider}")


async def chat_once(
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system: str = "",
) -> str:
    """非ストリーミングで1回だけ応答を取得（パイプライン用）。"""
    chunks: list[str] = []
    async for chunk in stream_chat(provider, api_key, model, messages, system):
        chunks.append(chunk)
    return "".join(chunks)


async def list_claude_models(api_key: str) -> list[dict]:
    """Claude の利用可能モデル一覧を取得。

    Anthropic APIにモデル一覧エンドポイントがあればそれを使い、
    なければ既知モデルのリストを返す。APIキーの有効性確認も兼ねる。
    """
    if not api_key:
        return []

    # 既知のClaude最新モデル（2026年3月時点）
    known_models = [
        {"name": "claude-opus-4-20250514", "description": "Opus 4 — 最高性能"},
        {"name": "claude-sonnet-4-20250514", "description": "Sonnet 4 — 高速・高性能バランス"},
        {"name": "claude-haiku-4-20250414", "description": "Haiku 4 — 最速・低コスト"},
        {"name": "claude-sonnet-4-6-20260320", "description": "Sonnet 4.6 — 最新"},
        {"name": "claude-opus-4-6-20260320", "description": "Opus 4.6 — 最新最高性能"},
        {"name": "claude-haiku-4-5-20251001", "description": "Haiku 4.5"},
    ]

    # APIキーの有効性確認（軽量なリクエスト）
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        # 最小限のリクエストでAPIキー確認
        await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
    except anthropic.AuthenticationError:
        logger.warning("Claude APIキーが無効です")
        return []
    except Exception:
        # 認証以外のエラー（レート制限等）はキーは有効と判断
        pass

    return [
        {"provider": "claude", "name": m["name"], "description": m["description"]}
        for m in known_models
    ]


async def list_openai_models(api_key: str) -> list[dict]:
    """OpenAI のモデル一覧を取得。"""
    if not api_key:
        return []
    try:
        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await client.models.list()
        return [
            {
                "provider": "openai",
                "name": m.id,
                "size": None,
                "modified_at": None,
            }
            for m in resp.data
            if m.id.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-"))
        ]
    except Exception as e:
        logger.warning("OpenAIモデル一覧の取得に失敗: %s", e)
        return []
