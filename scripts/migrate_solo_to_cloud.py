"""
Helix AI Studio v10.1.0 - DB Migration Script
soloAI → cloudAI のタブ名移行

SQLite の CHECK 制約変更は ALTER TABLE では不可能なため、
テーブル再作成 + データコピーで実施する。

使い方:
    python scripts/migrate_solo_to_cloud.py
"""

import sqlite3
import shutil
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("data/web_chats.db")
BACKUP_DIR = Path("data/backup_before_migration")


def migrate():
    if not DB_PATH.exists():
        logger.info("Database not found at %s - nothing to migrate.", DB_PATH)
        return

    # ── 1. バックアップ ──
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"web_chats_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    logger.info("Backup created: %s", backup_path)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        # ── 2. 既存 soloAI レコードを cloudAI に UPDATE ──
        updated = conn.execute(
            "UPDATE chats SET tab = 'cloudAI' WHERE tab = 'soloAI'"
        ).rowcount
        logger.info("Updated %d chat records: soloAI -> cloudAI", updated)

        # ── 3. テーブル再作成（CHECK 制約を変更）──
        conn.executescript("""
            -- chats テーブルを再作成
            CREATE TABLE IF NOT EXISTS chats_new (
                id TEXT PRIMARY KEY,
                tab TEXT NOT NULL CHECK(tab IN ('cloudAI', 'mixAI')),
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

            -- データコピー
            INSERT OR IGNORE INTO chats_new
                SELECT * FROM chats;

            -- 旧テーブル削除 & リネーム
            DROP TABLE IF EXISTS chats;
            ALTER TABLE chats_new RENAME TO chats;

            -- インデックス再作成
            CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_chats_tab ON chats(tab);
        """)
        logger.info("Table 'chats' recreated with new CHECK constraint (cloudAI, mixAI)")

        # messages テーブルの外部キーは ON DELETE CASCADE なので、
        # chats テーブルが再作成されても messages は参照整合性を保持する。
        # ただし PRAGMA foreign_keys=OFF の間に実行しているため問題なし。

        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        # ── 4. 整合性チェック ──
        chat_count = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        logger.info("Migration complete. Chats: %d, Messages: %d", chat_count, msg_count)

        # FK 整合性チェック
        fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_check:
            logger.warning("Foreign key violations found: %s", fk_check)
        else:
            logger.info("Foreign key integrity check passed.")

    except Exception as e:
        logger.error("Migration failed: %s", e)
        logger.info("Restoring from backup: %s", backup_path)
        conn.close()
        shutil.copy2(backup_path, DB_PATH)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
