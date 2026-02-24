"""
Helix AI Studio - Discord Webhook Notifier (v10.0.0)

Discord Webhook経由で実行完了/エラー通知を送信。
設定は config/config.json → web_server.discord_webhook_url で管理。

使い方:
    from ..utils.discord_notifier import notify_discord
    notify_discord("cloudAI", "completed", "Claude Opus 4.6 応答完了", elapsed=12.5)
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/config.json")


def _get_webhook_url() -> str:
    """config.json → web_server.discord_webhook_url から取得"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("web_server", {}).get("discord_webhook_url", "").strip()
    except Exception:
        pass
    return ""


def _is_valid_webhook(url: str) -> bool:
    """Webhook URLが有効なDiscord形式か簡易チェック"""
    return url.startswith("https://discord.com/api/webhooks/") or \
           url.startswith("https://discordapp.com/api/webhooks/")


def notify_discord(
    tab: str,
    status: str,
    message: str,
    elapsed: float = 0.0,
    error: str = "",
) -> bool:
    """Discord Webhookで通知を送信する（非ブロッキング）

    Args:
        tab: 実行元タブ ("cloudAI" / "mixAI")
        status: ステータス ("completed" / "error" / "timeout")
        message: 通知メッセージ
        elapsed: 経過時間（秒）
        error: エラー詳細（ステータスがerrorの場合）

    Returns:
        True: 通知送信が開始された, False: 設定なしまたは無効
    """
    # v11.2.1: config.json を1回だけ読み込み（url と status_map を両方取得）
    try:
        config_data = json.loads(CONFIG_PATH.read_text(encoding='utf-8')) if CONFIG_PATH.exists() else {}
    except Exception:
        config_data = {}
    ws = config_data.get("web_server", {})
    url = ws.get("discord_webhook_url", "").strip()
    if not url or not _is_valid_webhook(url):
        return False

    # Discord通知イベント設定を参照
    status_map = {
        "started": ws.get("discord_notify_start", True),
        "completed": ws.get("discord_notify_complete", True),
        "error": ws.get("discord_notify_error", True),
        "timeout": ws.get("discord_notify_error", True),
    }
    if not status_map.get(status, True):
        return False

    # 色設定（Discordの embed color は10進数）
    color_map = {
        "completed": 0x4CAF50,  # 緑
        "error": 0xEF4444,      # 赤
        "timeout": 0xFFA500,    # オレンジ
    }
    color = color_map.get(status, 0x6B7280)

    # Embed構築
    embed = {
        "title": f"Helix AI Studio — {tab}",
        "description": message[:2000],
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [],
    }

    if elapsed > 0:
        embed["fields"].append({
            "name": "Elapsed",
            "value": f"{elapsed:.1f}s",
            "inline": True,
        })

    embed["fields"].append({
        "name": "Status",
        "value": status.upper(),
        "inline": True,
    })

    if error:
        embed["fields"].append({
            "name": "Error",
            "value": error[:500],
            "inline": False,
        })

    payload = {
        "username": "Helix AI Studio",
        "embeds": [embed],
    }

    # 非ブロッキング送信
    def _send():
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code not in (200, 204):
                logger.warning(f"[Discord] Webhook returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"[Discord] Webhook send failed: {e}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    return True
