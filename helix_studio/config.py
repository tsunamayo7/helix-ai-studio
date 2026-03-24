"""設定ヘルパー — DBから設定を読み書きする。"""

from __future__ import annotations

from helix_studio.db import get_connection


async def get_setting(key: str) -> str | None:
    """指定キーの設定値を取得。存在しなければ None。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None
    finally:
        await db.close()


async def set_setting(key: str, value: str) -> None:
    """設定値を更新（なければ挿入）。"""
    db = await get_connection()
    try:
        await db.execute(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                              updated_at = excluded.updated_at""",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()


async def get_all_settings() -> dict[str, str]:
    """全設定をdict形式で返す。"""
    db = await get_connection()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        await db.close()
