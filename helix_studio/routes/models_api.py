"""モデル一覧 API ルーター"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from helix_studio.config import get_setting
from helix_studio.models import ModelTestRequest
from helix_studio.services import cloud_ai, local_ai, cli_ai

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_all_models() -> dict:
    """全プロバイダのモデル一覧を統合して返す。"""
    results: dict[str, list] = {
        "ollama": [],
        "openai_compat": [],
        "claude": [],
        "openai": [],
    }

    # Ollama
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    results["ollama"] = await local_ai.list_ollama_models(ollama_url)

    # OpenAI互換
    compat_url = await get_setting("openai_compat_url") or ""
    compat_key = await get_setting("openai_compat_api_key") or ""
    if compat_url:
        results["openai_compat"] = await local_ai.list_openai_compat_models(compat_url, compat_key)

    # Claude
    claude_key = await get_setting("claude_api_key") or ""
    results["claude"] = await cloud_ai.list_claude_models(claude_key)

    # OpenAI
    openai_key = await get_setting("openai_api_key") or ""
    results["openai"] = await cloud_ai.list_openai_models(openai_key)

    # CLI（自動検出）
    cli_models = cli_ai.list_cli_models()
    for provider, models in cli_models.items():
        results[provider] = models

    return results


@router.post("/test")
async def test_connection(req: ModelTestRequest) -> dict:
    """指定プロバイダへの接続テスト。"""
    try:
        if req.provider == "ollama":
            url = req.url or await get_setting("ollama_url") or "http://localhost:11434"
            models = await local_ai.list_ollama_models(url)
            return {
                "success": True,
                "provider": "ollama",
                "message": f"接続成功 — {len(models)}モデル検出",
                "model_count": len(models),
            }

        elif req.provider == "openai_compat":
            url = req.url or await get_setting("openai_compat_url") or ""
            api_key = req.api_key or await get_setting("openai_compat_api_key") or ""
            if not url:
                return {"success": False, "provider": "openai_compat", "message": "URLが未設定です"}
            models = await local_ai.list_openai_compat_models(url, api_key)
            return {
                "success": True,
                "provider": "openai_compat",
                "message": f"接続成功 — {len(models)}モデル検出",
                "model_count": len(models),
            }

        elif req.provider == "claude":
            api_key = req.api_key or await get_setting("claude_api_key") or ""
            if not api_key:
                return {"success": False, "provider": "claude", "message": "APIキーが未設定です"}
            models = await cloud_ai.list_claude_models(api_key)
            return {
                "success": True,
                "provider": "claude",
                "message": f"接続成功 — {len(models)}モデル利用可能",
                "model_count": len(models),
            }

        elif req.provider == "openai":
            api_key = req.api_key or await get_setting("openai_api_key") or ""
            if not api_key:
                return {"success": False, "provider": "openai", "message": "APIキーが未設定です"}
            models = await cloud_ai.list_openai_models(api_key)
            return {
                "success": True,
                "provider": "openai",
                "message": f"接続成功 — {len(models)}モデル利用可能",
                "model_count": len(models),
            }

        else:
            return {"success": False, "message": f"未対応のプロバイダ: {req.provider}"}

    except Exception as e:
        logger.warning("接続テスト失敗 (%s): %s", req.provider, e)
        return {"success": False, "provider": req.provider, "message": f"接続失敗: {e}"}
