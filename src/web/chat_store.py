"""
Web UI チャット履歴ストア (v9.2.0)
SQLiteベースの会話永続化。3モードコンテキスト構築。
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "data/web_chats.db"
MAX_CHATS = 500
MAX_MESSAGES_PER_CHAT = 200
MAX_DB_SIZE_MB = 100
AUTO_ARCHIVE_DAYS = 30


class ChatStore:
    """チャット履歴の永続化管理"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                tab TEXT NOT NULL CHECK(tab IN ('soloAI', 'cloudAI', 'mixAI')),
                title TEXT NOT NULL DEFAULT '新しいチャット',
                context_mode TEXT NOT NULL DEFAULT 'session'
                    CHECK(context_mode IN ('single', 'session', 'full')),
                claude_model_id TEXT NOT NULL DEFAULT 'claude-opus-4-6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                total_tokens_estimated INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'error')),
                content TEXT NOT NULL,
                token_estimate INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_chats_tab ON chats(tab);
        """)
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ═══ チャット CRUD ═══

    def create_chat(self, tab: str, context_mode: str = "session",
                    model_id: str = "claude-opus-4-6") -> dict:
        self._enforce_limits()
        chat_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO chats (id, tab, context_mode, claude_model_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, tab, context_mode, model_id, now, now))
            conn.commit()
            return {"id": chat_id, "tab": tab, "title": "新しいチャット",
                    "context_mode": context_mode, "message_count": 0,
                    "created_at": now, "updated_at": now}
        finally:
            conn.close()

    def list_chats(self, tab: str = None, limit: int = 50,
                   include_archived: bool = False) -> list:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM chats WHERE 1=1"
            params = []
            if tab:
                query += " AND tab = ?"
                params.append(tab)
            if not include_archived:
                query += " AND is_archived = 0"
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_chat(self, chat_id: str) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_chat_title(self, chat_id: str, title: str):
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                         (title, datetime.now().isoformat(), chat_id))
            conn.commit()
        finally:
            conn.close()

    def update_context_mode(self, chat_id: str, mode: str):
        if mode not in ('single', 'session', 'full'):
            raise ValueError(f"Invalid mode: {mode}")
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET context_mode = ? WHERE id = ?", (mode, chat_id))
            conn.commit()
        finally:
            conn.close()

    def delete_chat(self, chat_id: str):
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            conn.commit()
        finally:
            conn.close()

    def archive_chat(self, chat_id: str):
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET is_archived = 1 WHERE id = ?", (chat_id,))
            conn.commit()
        finally:
            conn.close()

    # ═══ メッセージ CRUD ═══

    def add_message(self, chat_id: str, role: str, content: str,
                    metadata: dict = None) -> dict:
        msg_id = uuid.uuid4().hex[:12]
        token_est = len(content) // 3
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO messages (id, chat_id, role, content, token_estimate, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, chat_id, role, content, token_est,
                  json.dumps(metadata or {}, ensure_ascii=False), now))
            conn.execute("""
                UPDATE chats SET
                    message_count = message_count + 1,
                    total_tokens_estimated = total_tokens_estimated + ?,
                    updated_at = ?
                WHERE id = ?
            """, (token_est, now, chat_id))
            conn.commit()
            return {"id": msg_id, "role": role, "content": content,
                    "token_estimate": token_est, "created_at": now}
        finally:
            conn.close()

    def get_messages(self, chat_id: str, limit: int = None) -> list:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC"
            params = [chat_id]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_recent_messages(self, chat_id: str, n: int = 10) -> list:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM messages WHERE chat_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (chat_id, n)).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    # ═══ コンテキスト構築（3モード） ═══

    def build_context_for_prompt(self, chat_id: str, current_prompt: str) -> dict:
        chat = self.get_chat(chat_id)
        if not chat:
            return {"prompt": current_prompt, "mode": "single",
                    "token_estimate": len(current_prompt) // 3, "messages_included": 0}

        mode = chat["context_mode"]

        if mode == "single":
            return {
                "prompt": current_prompt,
                "mode": "single",
                "token_estimate": len(current_prompt) // 3,
                "messages_included": 0,
            }

        elif mode == "session":
            recent = self.get_recent_messages(chat_id, n=10)
            all_msgs = self.get_messages(chat_id)
            older_msgs = all_msgs[:-len(recent)] if len(all_msgs) > len(recent) else []

            recent_text = "\n".join(
                f"{'ユーザー' if m['role'] == 'user' else 'アシスタント'}: {m['content']}"
                for m in recent
            )

            older_summary = ""
            if older_msgs:
                older_summary = self._summarize_messages(older_msgs)

            parts = []
            if older_summary:
                parts.append(f"<conversation_summary>\n以前の会話の要約:\n{older_summary}\n</conversation_summary>")
            if recent_text:
                parts.append(f"<recent_conversation>\n直近の会話:\n{recent_text}\n</recent_conversation>")
            parts.append(f"<current_message>\n{current_prompt}\n</current_message>")

            full_prompt = "\n\n".join(parts)
            return {
                "prompt": full_prompt,
                "mode": "session",
                "token_estimate": len(full_prompt) // 3,
                "messages_included": len(recent) + (1 if older_summary else 0),
            }

        elif mode == "full":
            all_msgs = self.get_messages(chat_id)

            parts = []
            for m in all_msgs:
                role_label = "ユーザー" if m["role"] == "user" else "アシスタント"
                parts.append(f"{role_label}: {m['content']}")
            parts.append(f"ユーザー: {current_prompt}")

            full_prompt = "\n\n".join(parts)
            token_est = len(full_prompt) // 3

            warning = None
            if token_est > 50000:
                warning = f"推定{token_est:,}トークン。セッションモードへの切替を推奨します。"

            return {
                "prompt": full_prompt,
                "mode": "full",
                "token_estimate": token_est,
                "messages_included": len(all_msgs),
                "warning": warning,
            }

        return {"prompt": current_prompt, "mode": "single",
                "token_estimate": len(current_prompt) // 3, "messages_included": 0}

    def _summarize_messages(self, messages: list, max_chars: int = 1500) -> str:
        user_msgs = [m["content"][:200] for m in messages if m["role"] == "user"]
        if not user_msgs:
            return ""
        topics = user_msgs[-5:]
        summary = "議論されたトピック:\n" + "\n".join(f"- {t}" for t in topics)
        return summary[:max_chars]

    # ═══ タイトル自動生成 ═══

    def auto_generate_title(self, chat_id: str) -> str:
        msgs = self.get_messages(chat_id, limit=1)
        if not msgs:
            return "新しいチャット"
        first_msg = msgs[0]["content"]
        title = first_msg[:30].replace("\n", " ").strip()
        if len(first_msg) > 30:
            title += "..."
        self.update_chat_title(chat_id, title)
        return title

    # ═══ 容量管理 ═══

    def _enforce_limits(self):
        conn = self._get_conn()
        try:
            threshold = (datetime.now() - timedelta(days=AUTO_ARCHIVE_DAYS * 2)).isoformat()
            conn.execute("DELETE FROM chats WHERE is_archived = 1 AND updated_at < ?", (threshold,))

            archive_threshold = (datetime.now() - timedelta(days=AUTO_ARCHIVE_DAYS)).isoformat()
            conn.execute("""
                UPDATE chats SET is_archived = 1
                WHERE is_archived = 0 AND updated_at < ?
            """, (archive_threshold,))

            count = conn.execute("SELECT COUNT(*) FROM chats WHERE is_archived = 0").fetchone()[0]
            if count > MAX_CHATS:
                excess = count - MAX_CHATS
                conn.execute("""
                    DELETE FROM chats WHERE id IN (
                        SELECT id FROM chats WHERE is_archived = 0
                        ORDER BY updated_at ASC LIMIT ?
                    )
                """, (excess,))

            conn.commit()
        finally:
            conn.close()

    def get_storage_stats(self) -> dict:
        conn = self._get_conn()
        try:
            stats = conn.execute("""
                SELECT COUNT(*) as chats,
                       SUM(message_count) as messages,
                       SUM(total_tokens_estimated) as tokens
                FROM chats WHERE is_archived = 0
            """).fetchone()
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            return {
                "active_chats": stats["chats"] or 0,
                "total_messages": stats["messages"] or 0,
                "total_tokens": stats["tokens"] or 0,
                "db_size_mb": round(db_size / (1024 * 1024), 2),
                "max_chats": MAX_CHATS,
                "max_db_size_mb": MAX_DB_SIZE_MB,
            }
        finally:
            conn.close()
