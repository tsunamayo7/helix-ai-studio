"""
Helix AI Studio — Feature Flags

app_settings.json からグローバル機能フラグを読み取るヘルパー。
各タブから共通で参照される。
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_APP_SETTINGS_PATH = Path("config/app_settings.json")


def _load_app_settings() -> dict:
    """app_settings.json を読み込む（失敗時は空dict）"""
    try:
        if _APP_SETTINGS_PATH.exists():
            with open(_APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"[feature_flags] app_settings load: {e}")
    return {}


def is_bible_enabled() -> bool:
    """BIBLE コンテキスト注入が有効かどうか"""
    data = _load_app_settings()
    return bool(data.get("bible", {}).get("enabled", False))


def is_pilot_enabled() -> bool:
    """Helix Pilot (GUI自動操作) が有効かどうか"""
    data = _load_app_settings()
    return bool(data.get("pilot", {}).get("enabled", False))


def is_sandbox_enabled() -> bool:
    """Docker Sandbox (Virtual Desktop) が有効かどうか"""
    data = _load_app_settings()
    return bool(data.get("sandbox", {}).get("enabled", True))
