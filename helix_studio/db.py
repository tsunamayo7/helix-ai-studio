"""SQLiteデータベース管理 (aiosqlite)"""

from __future__ import annotations

import os
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "helix_studio.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新しい会話',
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    system_prompt TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    duration_ms INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    input_text TEXT NOT NULL,
    step1_result TEXT,
    step2_result TEXT,
    step3_result TEXT,
    step1_model TEXT,
    step2_model TEXT,
    step3_model TEXT,
    current_step INTEGER DEFAULT 0,
    error_msg TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
"""

DEFAULT_SETTINGS: dict[str, str] = {
    "claude_api_key": "",
    "openai_api_key": "",
    "ollama_url": "http://localhost:11434",
    "openai_compat_url": "",
    "openai_compat_api_key": "",
    "mem0_url": "http://localhost:8080",
    "mem0_user_id": "tsunamayo7",
    "mem0_auto_inject": "true",
    "mcp_helix_pilot_cmd": "",
    "mcp_helix_sandbox_cmd": "",
    "default_cloud_provider": "claude",
    "default_cloud_model": "claude-sonnet-4-20250514",
    "default_local_model": "gemma3:27b",
    "pipeline_step1_model": "claude-sonnet-4-20250514",
    "pipeline_step2_model": "gemma3:27b",
    "pipeline_step3_model": "claude-sonnet-4-20250514",
    "theme": "dark",
    "language": "ja",
}


def _get_db_path() -> Path:
    """DB パスを返す。ディレクトリがなければ作成する。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


async def get_connection() -> aiosqlite.Connection:
    """DB接続を取得する。"""
    db = await aiosqlite.connect(str(_get_db_path()))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


ENV_OVERRIDE_MAP: dict[str, str] = {
    "ANTHROPIC_API_KEY": "claude_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "OLLAMA_URL": "ollama_url",
    "OPENAI_COMPAT_URL": "openai_compat_url",
    "OPENAI_COMPAT_API_KEY": "openai_compat_api_key",
    "MEM0_URL": "mem0_url",
    "MEM0_USER_ID": "mem0_user_id",
}


async def init_db() -> None:
    """テーブル作成とデフォルト設定の投入。環境変数があれば上書き。"""
    db = await get_connection()
    try:
        await db.executescript(SCHEMA)

        # デフォルト設定（環境変数があれば上書き）
        effective = dict(DEFAULT_SETTINGS)
        for env_key, setting_key in ENV_OVERRIDE_MAP.items():
            env_val = os.environ.get(env_key, "")
            if env_val:
                effective[setting_key] = env_val

        for key, value in effective.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        await db.commit()
    finally:
        await db.close()
