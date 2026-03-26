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


_BOOL_KEYS = {"mem0_auto_inject", "rag_auto_inject"}


@router.get("")
async def get_settings() -> SettingResponse:
    """全設定を返す（APIキーはマスク表示、bool値は変換）。"""
    raw = await get_all_settings()
    result: dict[str, str | bool | int | float] = {}
    for k, v in raw.items():
        if k in _BOOL_KEYS:
            result[k] = v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)
        else:
            result[k] = _mask_value(k, v)
    return SettingResponse(settings=result)


@router.put("")
async def update_settings(req: SettingUpdate) -> dict:
    """設定を一括更新。マスクされた値（****含む）は更新しない。"""
    updated_keys: list[str] = []
    for key, value in req.settings.items():
        str_value = str(value) if not isinstance(value, str) else value
        # マスクされたままの値は無視（ユーザーが変更していない）
        if "****" in str_value and key in _MASK_KEYS:
            continue
        await set_setting(key, str_value)
        updated_keys.append(key)
    return {"updated": updated_keys, "count": len(updated_keys)}
