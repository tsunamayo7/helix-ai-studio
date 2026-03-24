"""設定 API ルーター"""

from __future__ import annotations

from fastapi import APIRouter

from helix_studio.config import get_all_settings, set_setting
from helix_studio.models import SettingResponse, SettingUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

# マスク対象のキー（APIキー系）
_MASK_KEYS = {
    "claude_api_key",
    "openai_api_key",
    "openai_compat_api_key",
}


def _mask_value(key: str, value: str) -> str:
    """APIキーは末尾4文字のみ表示し、残りをマスクする。"""
    if key not in _MASK_KEYS or not value:
        return value
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


@router.get("")
async def get_settings() -> SettingResponse:
    """全設定を返す（APIキーはマスク表示）。"""
    raw = await get_all_settings()
    masked = {k: _mask_value(k, v) for k, v in raw.items()}
    return SettingResponse(settings=masked)


@router.put("")
async def update_settings(req: SettingUpdate) -> dict:
    """設定を一括更新。マスクされた値（****含む）は更新しない。"""
    updated_keys: list[str] = []
    for key, value in req.settings.items():
        # マスクされたままの値は無視（ユーザーが変更していない）
        if "****" in value and key in _MASK_KEYS:
            continue
        await set_setting(key, value)
        updated_keys.append(key)
    return {"updated": updated_keys, "count": len(updated_keys)}
