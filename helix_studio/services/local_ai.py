"""ローカルLLMクライアント — Ollama + OpenAI互換API (vLLM / llama.cpp / LM Studio)"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# タイムアウト設定
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


# ── Ollama ────────────────────────────────────────────


async def list_ollama_models(url: str) -> list[dict[str, Any]]:
    """Ollama GET /api/tags でモデル一覧を取得。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{url.rstrip('/')}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return [
                {
                    "provider": "ollama",
                    "name": m.get("name", ""),
                    "size": _format_size(m.get("size", 0)),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in models
            ]
    except Exception as e:
        logger.warning("Ollamaモデル一覧の取得に失敗: %s", e)
        return []


async def stream_ollama_chat(
    url: str,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Ollama POST /api/chat でストリーミングチャット。"""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{url.rstrip('/')}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


# ── OpenAI互換API ────────────────────────────────────


async def list_openai_compat_models(url: str, api_key: str = "") -> list[dict[str, Any]]:
    """OpenAI互換 GET /v1/models でモデル一覧を取得。"""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/v1/models", headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            return [
                {
                    "provider": "openai_compat",
                    "name": m.get("id", ""),
                    "size": None,
                    "modified_at": None,
                }
                for m in models
            ]
    except Exception as e:
        logger.warning("OpenAI互換モデル一覧の取得に失敗: %s", e)
        return []


async def stream_openai_compat_chat(
    url: str,
    model: str,
    messages: list[dict[str, str]],
    api_key: str = "",
) -> AsyncIterator[str]:
    """OpenAI互換 POST /v1/chat/completions でストリーミングチャット。"""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{url.rstrip('/')}/v1/chat/completions",
            json=payload,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError):
                    continue


# ── 統合インターフェース ──────────────────────────────


async def list_models(
    provider: str,
    url: str,
    api_key: str = "",
) -> list[dict[str, Any]]:
    """プロバイダに応じたモデル一覧を返す。"""
    if provider == "ollama":
        return await list_ollama_models(url)
    elif provider == "openai_compat":
        return await list_openai_compat_models(url, api_key)
    return []


async def stream_chat(
    provider: str,
    url: str,
    model: str,
    messages: list[dict[str, str]],
    api_key: str = "",
) -> AsyncIterator[str]:
    """プロバイダに応じたストリーミングチャットを返す。"""
    if provider == "ollama":
        async for chunk in stream_ollama_chat(url, model, messages):
            yield chunk
    elif provider == "openai_compat":
        async for chunk in stream_openai_compat_chat(url, model, messages, api_key):
            yield chunk
    else:
        raise ValueError(f"未対応のローカルプロバイダ: {provider}")


# ── ユーティリティ ────────────────────────────────────


def _format_size(size_bytes: int) -> str:
    """バイト数を人間が読みやすい形式に変換。"""
    if size_bytes == 0:
        return "不明"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
