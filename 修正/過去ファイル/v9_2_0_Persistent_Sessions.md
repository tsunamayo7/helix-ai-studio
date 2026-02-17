# Helix AI Studio v9.2.0 "Persistent Sessions"
## チャット履歴 + 3モードコンテキスト切替 + コピー機能
## 実装設計書（Claude Code CLI用）

**作成日**: 2026-02-16
**前提**: v9.1.0 "Connected Knowledge" 完了済み
**想定期間**: 3-4日
**原則**: 既存PyQt6コードへの変更ゼロ。Web UI側のみ拡張。

---

## 1. v9.2.0 の全体像

```
┌──────────────────────────────────────────────────────────────┐
│                    iPhone Safari / PWA                       │
├─────────┬─────────┬─────────┬─────────┬─────────────────────┤
│ soloAI  │ mixAI   │ ファイル │  設定   │                     │
├─────────┴─────────┴─────────┴─────────┤                     │
│                                        │                     │
│  ┌────────────────────────────────┐    │                     │
│  │ 📋 チャット一覧サイドパネル    │    │                     │
│  │  ├ 今日のコード質問 (soloAI)   │    │                     │
│  │  ├ API設計レビュー (mixAI)     │    │  ← v9.2.0 NEW      │
│  │  └ デバッグセッション (soloAI)  │    │                     │
│  └────────────────────────────────┘    │                     │
│                                        │                     │
│  ┌────────────────────────────────┐    │                     │
│  │ コンテキストモード切替          │    │                     │
│  │  [単発] [セッション] [フル]     │    │  ← v9.2.0 NEW      │
│  └────────────────────────────────┘    │                     │
│                                        │                     │
│  ┌────────────────────────────────┐    │                     │
│  │ コピーボタン                   │    │                     │
│  │  📋 コードブロック / 回答全体   │    │  ← v9.2.0 NEW      │
│  └────────────────────────────────┘    │                     │
└────────────────────────────────────────┘
```

### v9.2.0 で追加する3機能:

| # | 機能 | 概要 |
|---|------|------|
| A | チャット履歴 | 会話をセッション単位で永続保存・一覧・再開 |
| B | 3モードコンテキスト切替 | 単発/セッション/フルの3段階トークン消費制御 |
| C | コピー機能 | コードブロック + 回答全体のワンタップコピー |

---

## 2. データベース設計

### 2.1 新規テーブル: `data/web_chats.db`

既存の `helix_memory.db` とは別DBにする。理由:
- PyQt6側のDBロックと競合しない
- Web UI固有の機能のため分離が自然
- 容量管理が独立

```sql
-- チャットセッション
CREATE TABLE chats (
    id TEXT PRIMARY KEY,                    -- UUID
    tab TEXT NOT NULL CHECK(tab IN ('soloAI', 'mixAI')),
    title TEXT NOT NULL DEFAULT '新しいチャット',
    context_mode TEXT NOT NULL DEFAULT 'session'
        CHECK(context_mode IN ('single', 'session', 'full')),
    claude_model_id TEXT NOT NULL DEFAULT 'claude-opus-4-6',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    total_tokens_estimated INTEGER DEFAULT 0,  -- 累計推定トークン
    is_archived INTEGER DEFAULT 0              -- アーカイブ済みフラグ
);

-- 個別メッセージ
CREATE TABLE messages (
    id TEXT PRIMARY KEY,                    -- UUID
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'error')),
    content TEXT NOT NULL,
    token_estimate INTEGER DEFAULT 0,       -- このメッセージの推定トークン数
    metadata TEXT DEFAULT '{}',             -- JSON: {model, elapsed, phase_info, ...}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX idx_messages_chat ON messages(chat_id, created_at);
CREATE INDEX idx_chats_updated ON chats(updated_at DESC);
CREATE INDEX idx_chats_tab ON chats(tab);

-- 容量管理用ビュー
CREATE VIEW chat_storage_stats AS
SELECT
    COUNT(*) as total_chats,
    SUM(message_count) as total_messages,
    SUM(LENGTH(m.content)) as total_content_bytes
FROM chats c
LEFT JOIN messages m ON c.id = m.chat_id;
```

### 2.2 容量制限

```python
# デフォルト制限
MAX_CHATS = 500              # 最大チャット数
MAX_MESSAGES_PER_CHAT = 200  # 1チャットの最大メッセージ数
MAX_DB_SIZE_MB = 100         # DB最大サイズ
AUTO_ARCHIVE_DAYS = 30       # 30日アクセスなしで自動アーカイブ
```

---

## 3. 機能A: チャット履歴

### 3.1 バックエンド: `src/web/chat_store.py` (新規)

```python
"""
Web UI チャット履歴ストア
SQLiteベースの会話永続化。v9.1.0のRAG連携(rag_bridge.py)と連携。
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
                tab TEXT NOT NULL CHECK(tab IN ('soloAI', 'mixAI')),
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
        """新規チャットセッション作成"""
        # 容量チェック
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
        """チャット一覧取得（更新日時降順）"""
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
        """チャット詳細取得"""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_chat_title(self, chat_id: str, title: str):
        """チャットタイトル更新"""
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                         (title, datetime.now().isoformat(), chat_id))
            conn.commit()
        finally:
            conn.close()

    def update_context_mode(self, chat_id: str, mode: str):
        """コンテキストモード変更"""
        if mode not in ('single', 'session', 'full'):
            raise ValueError(f"Invalid mode: {mode}")
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET context_mode = ? WHERE id = ?", (mode, chat_id))
            conn.commit()
        finally:
            conn.close()

    def delete_chat(self, chat_id: str):
        """チャット削除（メッセージもCASCADE削除）"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            conn.commit()
        finally:
            conn.close()

    def archive_chat(self, chat_id: str):
        """チャットをアーカイブ"""
        conn = self._get_conn()
        try:
            conn.execute("UPDATE chats SET is_archived = 1 WHERE id = ?", (chat_id,))
            conn.commit()
        finally:
            conn.close()

    # ═══ メッセージ CRUD ═══

    def add_message(self, chat_id: str, role: str, content: str,
                     metadata: dict = None) -> dict:
        """メッセージ追加"""
        msg_id = uuid.uuid4().hex[:12]
        token_est = len(content) // 3  # 簡易推定
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
        """メッセージ一覧取得（時系列順）"""
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
        """直近N件のメッセージ取得（セッションモード用）"""
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
        """
        コンテキストモードに応じてClaude CLIに送信するプロンプトを構築。

        Returns:
            {
                "prompt": "実際に送信するプロンプト",
                "mode": "single|session|full",
                "token_estimate": 推定トークン数,
                "messages_included": 含まれるメッセージ数,
            }
        """
        chat = self.get_chat(chat_id)
        if not chat:
            return {"prompt": current_prompt, "mode": "single",
                    "token_estimate": len(current_prompt) // 3, "messages_included": 0}

        mode = chat["context_mode"]

        if mode == "single":
            # ═══ 単発モード: RAGコンテキストのみ、過去会話なし ═══
            return {
                "prompt": current_prompt,
                "mode": "single",
                "token_estimate": len(current_prompt) // 3,
                "messages_included": 0,
            }

        elif mode == "session":
            # ═══ セッションモード: 直近5往復 + 古い会話はRAG要約 ═══
            recent = self.get_recent_messages(chat_id, n=10)  # 5往復 = 10メッセージ
            all_msgs = self.get_messages(chat_id)
            older_msgs = all_msgs[:-len(recent)] if len(all_msgs) > len(recent) else []

            # 直近メッセージをテキスト化
            recent_text = "\n".join(
                f"{'ユーザー' if m['role'] == 'user' else 'アシスタント'}: {m['content']}"
                for m in recent
            )

            # 古いメッセージの要約（ローカルで簡易生成）
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
            # ═══ フルモード: 全メッセージ送信（claude.ai方式） ═══
            all_msgs = self.get_messages(chat_id)

            parts = []
            for m in all_msgs:
                role_label = "ユーザー" if m["role"] == "user" else "アシスタント"
                parts.append(f"{role_label}: {m['content']}")
            parts.append(f"ユーザー: {current_prompt}")

            full_prompt = "\n\n".join(parts)
            token_est = len(full_prompt) // 3

            # 警告: 50,000トークン超えの場合
            warning = None
            if token_est > 50000:
                warning = f"⚠️ 推定{token_est:,}トークン。セッションモードへの切替を推奨します。"

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
        """メッセージ群の簡易要約（ローカル、API呼び出しなし）"""
        # トピック抽出ベースの簡易要約
        user_msgs = [m["content"][:200] for m in messages if m["role"] == "user"]
        if not user_msgs:
            return ""
        topics = user_msgs[-5:]  # 直近5件のユーザー発言
        summary = "議論されたトピック:\n" + "\n".join(f"- {t}" for t in topics)
        return summary[:max_chars]

    # ═══ タイトル自動生成 ═══

    def auto_generate_title(self, chat_id: str) -> str:
        """最初のユーザーメッセージからタイトルを自動生成"""
        msgs = self.get_messages(chat_id, limit=1)
        if not msgs:
            return "新しいチャット"
        first_msg = msgs[0]["content"]
        # 最初の30文字をタイトルに
        title = first_msg[:30].replace("\n", " ").strip()
        if len(first_msg) > 30:
            title += "..."
        self.update_chat_title(chat_id, title)
        return title

    # ═══ 容量管理 ═══

    def _enforce_limits(self):
        """容量制限の適用"""
        conn = self._get_conn()
        try:
            # 古いアーカイブの自動削除
            threshold = (datetime.now() - timedelta(days=AUTO_ARCHIVE_DAYS * 2)).isoformat()
            conn.execute("DELETE FROM chats WHERE is_archived = 1 AND updated_at < ?", (threshold,))

            # 未アーカイブの自動アーカイブ
            archive_threshold = (datetime.now() - timedelta(days=AUTO_ARCHIVE_DAYS)).isoformat()
            conn.execute("""
                UPDATE chats SET is_archived = 1
                WHERE is_archived = 0 AND updated_at < ?
            """, (archive_threshold,))

            # チャット数上限
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
        """ストレージ統計"""
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
```

### 3.2 バックエンド: REST API (`src/web/api_routes.py` に追加)

```python
from .chat_store import ChatStore

chat_store = ChatStore()

# ═══ チャット一覧 ═══

@router.get("/api/chats")
async def list_chats(tab: str = None, payload: dict = Depends(verify_jwt)):
    """チャット一覧取得"""
    chats = chat_store.list_chats(tab=tab)
    return {"chats": chats}

@router.post("/api/chats")
async def create_chat(tab: str = "soloAI", context_mode: str = "session",
                       payload: dict = Depends(verify_jwt)):
    """新規チャット作成"""
    chat = chat_store.create_chat(tab=tab, context_mode=context_mode)
    return chat

@router.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str, payload: dict = Depends(verify_jwt)):
    """チャット詳細 + メッセージ取得"""
    chat = chat_store.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = chat_store.get_messages(chat_id)
    return {"chat": chat, "messages": messages}

@router.put("/api/chats/{chat_id}/title")
async def update_title(chat_id: str, title: str, payload: dict = Depends(verify_jwt)):
    """タイトル更新"""
    chat_store.update_chat_title(chat_id, title)
    return {"status": "ok"}

@router.put("/api/chats/{chat_id}/mode")
async def update_mode(chat_id: str, mode: str, payload: dict = Depends(verify_jwt)):
    """コンテキストモード変更"""
    chat_store.update_context_mode(chat_id, mode)
    return {"status": "ok", "mode": mode}

@router.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str, payload: dict = Depends(verify_jwt)):
    """チャット削除"""
    chat_store.delete_chat(chat_id)
    return {"status": "ok"}

@router.get("/api/chats/storage/stats")
async def storage_stats(payload: dict = Depends(verify_jwt)):
    """ストレージ統計"""
    return chat_store.get_storage_stats()
```

### 3.3 WebSocket統合 (`src/web/server.py` 修正)

```python
from .chat_store import ChatStore

chat_store = ChatStore()

# soloAI WebSocketハンドラ修正
async def _handle_solo_execute(client_id: str, data: dict):
    prompt = data.get("prompt", "")
    chat_id = data.get("chat_id")  # v9.2.0: チャットID
    model_id = data.get("model_id", "claude-opus-4-6")
    enable_rag = data.get("enable_rag", True)

    # v9.2.0: チャットIDがない場合は新規作成
    if not chat_id:
        chat = chat_store.create_chat(tab="soloAI")
        chat_id = chat["id"]
        await ws_manager.send_to(client_id, {
            "type": "chat_created",
            "chat_id": chat_id,
        })

    # ユーザーメッセージ保存
    chat_store.add_message(chat_id, "user", prompt)

    # タイトル自動生成（最初のメッセージ時）
    chat = chat_store.get_chat(chat_id)
    if chat and chat["message_count"] == 1:
        title = chat_store.auto_generate_title(chat_id)
        await ws_manager.send_to(client_id, {
            "type": "chat_title_updated",
            "chat_id": chat_id,
            "title": title,
        })

    # v9.2.0: コンテキストモードに応じたプロンプト構築
    context_result = chat_store.build_context_for_prompt(chat_id, prompt)
    full_prompt = context_result["prompt"]

    # トークン警告
    if context_result.get("warning"):
        await ws_manager.send_to(client_id, {
            "type": "token_warning",
            "message": context_result["warning"],
            "token_estimate": context_result["token_estimate"],
        })

    # v9.1.0: RAGコンテキスト注入（単発/セッションモード時のみ有効に）
    if enable_rag and context_result["mode"] != "full":
        try:
            rag_context = await rag_bridge.build_context(prompt, tab="soloAI")
            if rag_context:
                full_prompt = f"{rag_context}\n\n{full_prompt}"
        except Exception as e:
            logger.warning(f"RAG context failed: {e}")

    # Claude CLI実行
    response = await _run_claude_cli_async(
        prompt=full_prompt, model_id=model_id, ...)

    # アシスタント応答保存
    chat_store.add_message(chat_id, "assistant", response,
                            metadata={"model": model_id, "mode": context_result["mode"],
                                      "tokens_estimated": context_result["token_estimate"]})

    # v9.1.0: RAGへのエピソード保存
    # ... 既存のrag_bridge.save_conversation()

    await ws_manager.send_streaming(client_id, response, done=True)
```

---

## 4. フロントエンド: チャット一覧サイドパネル

### 4.1 新規: `frontend/src/components/ChatListPanel.jsx`

```jsx
import React, { useState, useEffect } from 'react';

export default function ChatListPanel({ token, activeTab, activeChatId,
                                         onSelectChat, onNewChat, onClose }) {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    fetchChats();
  }, [activeTab]);

  async function fetchChats() {
    setLoading(true);
    try {
      const res = await fetch(`/api/chats?tab=${activeTab}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setChats(data.chats || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function handleNewChat() {
    try {
      const res = await fetch(`/api/chats?tab=${activeTab}&context_mode=session`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const chat = await res.json();
        onNewChat(chat);
        fetchChats();
      }
    } catch (e) { console.error(e); }
  }

  async function handleDelete(chatId, e) {
    e.stopPropagation();
    if (!confirm('このチャットを削除しますか？')) return;
    try {
      await fetch(`/api/chats/${chatId}`, { method: 'DELETE', headers });
      fetchChats();
      if (activeChatId === chatId) onNewChat(null);
    } catch (e) { console.error(e); }
  }

  function formatDate(iso) {
    const d = new Date(iso);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' });
  }

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* オーバーレイ */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* パネル */}
      <div className="relative w-72 bg-gray-900 h-full flex flex-col border-r border-gray-800 z-50">
        {/* ヘッダー */}
        <div className="shrink-0 flex items-center justify-between p-4 border-b border-gray-800">
          <h2 className="text-gray-100 font-medium">チャット履歴</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">✕</button>
        </div>

        {/* 新規チャットボタン */}
        <button
          onClick={handleNewChat}
          className="shrink-0 mx-3 mt-3 px-4 py-2.5 bg-emerald-700 hover:bg-emerald-600
                     text-white rounded-lg text-sm font-medium transition-colors"
        >
          + 新しいチャット
        </button>

        {/* チャット一覧 */}
        <div className="flex-1 overflow-y-auto mt-2 min-h-0">
          {chats.map(chat => (
            <button
              key={chat.id}
              onClick={() => { onSelectChat(chat); onClose(); }}
              className={`w-full text-left px-4 py-3 flex items-start gap-2 hover:bg-gray-800/50
                border-b border-gray-800/30 group
                ${activeChatId === chat.id ? 'bg-emerald-900/20' : ''}`}
            >
              <div className="flex-1 min-w-0">
                <p className={`text-sm truncate ${
                  activeChatId === chat.id ? 'text-emerald-300' : 'text-gray-300'
                }`}>
                  {chat.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-gray-600">{formatDate(chat.updated_at)}</span>
                  <span className="text-[10px] text-gray-600">{chat.message_count}件</span>
                  <span className={`text-[10px] px-1 rounded ${
                    chat.context_mode === 'full' ? 'bg-amber-900/50 text-amber-400' :
                    chat.context_mode === 'session' ? 'bg-emerald-900/50 text-emerald-400' :
                    'bg-gray-800 text-gray-500'
                  }`}>
                    {chat.context_mode === 'full' ? 'フル' :
                     chat.context_mode === 'session' ? 'セッション' : '単発'}
                  </span>
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(chat.id, e)}
                className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 text-xs p-1"
              >
                🗑
              </button>
            </button>
          ))}
          {chats.length === 0 && !loading && (
            <p className="text-gray-600 text-sm text-center py-8">チャットなし</p>
          )}
        </div>

        {/* ストレージ情報 */}
        <div className="shrink-0 px-4 py-2 border-t border-gray-800 text-[10px] text-gray-600">
          {chats.length} / {MAX_CHATS} チャット
        </div>
      </div>
    </div>
  );
}

const MAX_CHATS = 500;
```

### 4.2 App.jsx修正（チャット履歴統合）

```jsx
import ChatListPanel from './components/ChatListPanel';

export default function App() {
  // ... 既存state

  const [showChatList, setShowChatList] = useState(false);
  const [activeChatId, setActiveChatId] = useState(null);

  function handleSelectChat(chat) {
    setActiveChatId(chat.id);
    // WebSocket経由でメッセージ履歴を読み込み
    // ... loadChatMessages(chat.id)
  }

  function handleNewChat(chat) {
    if (chat) {
      setActiveChatId(chat.id);
      // メッセージをクリア
      soloAI.clearMessages();
    }
  }

  return (
    <div className="flex flex-col bg-gray-950" style={{ height: '100dvh' }}>
      <header className="shrink-0 flex items-center justify-between px-4 py-3 ...">
        <div className="flex items-center gap-2">
          {/* ハンバーガーメニュー → チャット一覧 */}
          <button onClick={() => setShowChatList(true)}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white">
            ☰
          </button>
          <span className="text-lg font-semibold text-gray-100">Helix AI Studio</span>
        </div>
        <StatusIndicator status={current.status} />
      </header>

      {/* チャット一覧パネル */}
      {showChatList && (
        <ChatListPanel
          token={token}
          activeTab={activeTab}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          onClose={() => setShowChatList(false)}
        />
      )}

      {/* ... 既存タブ + コンテンツ */}
    </div>
  );
}
```

---

## 5. 機能B: 3モードコンテキスト切替UI

### 5.1 新規: `frontend/src/components/ContextModeSelector.jsx`

```jsx
import React from 'react';

const MODES = [
  {
    id: 'single',
    label: '単発',
    desc: 'RAGのみ',
    icon: '•',
    color: 'gray',
    tokenHint: '~4K tokens',
  },
  {
    id: 'session',
    label: 'セッション',
    desc: '直近5往復+要約',
    icon: '◉',
    color: 'emerald',
    tokenHint: '~10K tokens',
  },
  {
    id: 'full',
    label: 'フル',
    desc: '全履歴送信',
    icon: '●',
    color: 'amber',
    tokenHint: '増加型',
  },
];

export default function ContextModeSelector({ mode, onChange, tokenEstimate }) {
  return (
    <div className="flex items-center gap-1 px-1">
      {MODES.map(m => {
        const isActive = mode === m.id;
        const colorMap = {
          gray: isActive ? 'bg-gray-700 text-gray-200' : 'text-gray-600',
          emerald: isActive ? 'bg-emerald-800 text-emerald-200' : 'text-gray-600',
          amber: isActive ? 'bg-amber-800 text-amber-200' : 'text-gray-600',
        };
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            className={`px-2 py-1 rounded text-[11px] transition-colors ${colorMap[m.color]}
              hover:bg-gray-800`}
            title={`${m.desc} (${m.tokenHint})`}
          >
            {m.label}
          </button>
        );
      })}
      {tokenEstimate > 0 && (
        <span className={`text-[10px] ml-1 ${
          tokenEstimate > 50000 ? 'text-red-400' :
          tokenEstimate > 20000 ? 'text-amber-400' : 'text-gray-600'
        }`}>
          ~{(tokenEstimate / 1000).toFixed(1)}K
        </span>
      )}
    </div>
  );
}
```

### 5.2 InputBarへの統合

```jsx
// InputBar.jsx にContextModeSelectorとチャットIDを統合
import ContextModeSelector from './ContextModeSelector';

export default function InputBar({ onSend, disabled, placeholder,
                                    chatId, contextMode, onModeChange,
                                    tokenEstimate, ragEnabled, onRagToggle,
                                    attachedFiles, onAttach }) {
  return (
    <div className="shrink-0 border-t border-gray-800 bg-gray-900">
      {/* 添付ファイル表示 */}
      {attachedFiles?.length > 0 && (
        <div className="flex flex-wrap gap-1 px-4 py-1 bg-gray-900/50">
          {/* ... 既存 */}
        </div>
      )}

      {/* コンテキストモード + RAGトグル行 */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-gray-800/50">
        <ContextModeSelector mode={contextMode} onChange={onModeChange}
                              tokenEstimate={tokenEstimate} />
        <div className="flex items-center gap-2">
          <button onClick={onRagToggle}
            className={`px-2 py-0.5 rounded text-[10px] ${
              ragEnabled ? 'bg-emerald-800 text-emerald-300' : 'bg-gray-800 text-gray-500'
            }`}>
            RAG {ragEnabled ? 'ON' : 'OFF'}
          </button>
          <button onClick={onAttach}
            className="px-2 py-0.5 rounded text-[10px] bg-gray-800 text-gray-400 hover:text-gray-200">
            + 添付
          </button>
        </div>
      </div>

      {/* テキスト入力 + 送信ボタン */}
      <div className="flex items-end gap-2 px-4 py-3">
        {/* ... 既存のtextarea + sendボタン */}
      </div>
    </div>
  );
}
```

---

## 6. 機能C: コピー機能

### 6.1 MarkdownRenderer.jsx の修正

```jsx
// コードブロックにコピーボタン追加
function CodeBlock({ language, children }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="relative group my-2">
      {/* 言語ラベル + コピーボタン */}
      <div className="flex items-center justify-between px-3 py-1 bg-gray-800 rounded-t-lg">
        <span className="text-[10px] text-gray-500 uppercase">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="text-[10px] text-gray-500 hover:text-gray-200 transition-colors px-2 py-0.5"
        >
          {copied ? '✓ コピー済み' : '📋 コピー'}
        </button>
      </div>
      {/* コードブロック本体 */}
      <SyntaxHighlighter style={oneDark} language={language}
        customStyle={{ margin: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
        {children}
      </SyntaxHighlighter>
    </div>
  );
}
```

### 6.2 ChatView.jsx: メッセージ全体のコピーボタン

```jsx
// アシスタントメッセージのバブルにコピーボタン追加
function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false);
  const isAssistant = message.role === 'assistant';

  function handleCopyAll() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'} group`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${
        isAssistant ? 'bg-gray-800 text-gray-200' :
        message.role === 'error' ? 'bg-red-900/50 text-red-200' :
        'bg-emerald-700 text-white'
      }`}>
        {isAssistant ? (
          <>
            <MarkdownRenderer content={message.content} />
            {/* コピーボタン（ホバーで表示） */}
            <div className="flex justify-end mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleCopyAll}
                className="text-[10px] text-gray-500 hover:text-gray-300 px-2 py-0.5"
              >
                {copied ? '✓ コピー済み' : '📋 回答をコピー'}
              </button>
            </div>
          </>
        ) : (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        )}
      </div>
    </div>
  );
}
```

---

## 7. トークン消費モニター表示

### 7.1 ヘッダーに推定トークン表示

```jsx
// App.jsx のヘッダー内に追加
{activeChatId && (
  <span className={`text-[10px] px-2 py-0.5 rounded ${
    tokenEstimate > 50000 ? 'bg-red-900/50 text-red-400' :
    tokenEstimate > 20000 ? 'bg-amber-900/50 text-amber-400' :
    'bg-gray-800 text-gray-500'
  }`}>
    ~{(tokenEstimate / 1000).toFixed(1)}K tokens
  </span>
)}
```

---

## 8. テスト項目チェックリスト

### 機能A: チャット履歴
| # | テスト | 期待結果 |
|---|-------|---------|
| 1 | ☰ ボタンタップ | チャット一覧サイドパネル表示 |
| 2 | 「+ 新しいチャット」タップ | 新規チャット作成、メッセージクリア |
| 3 | メッセージ送信 | タイトル自動生成（最初のメッセージの30文字） |
| 4 | チャット一覧から選択 | 過去メッセージが復元表示 |
| 5 | チャット削除 | 確認ダイアログ→削除 |
| 6 | soloAI/mixAIタブ切替 | タブごとのチャット一覧に切替 |

### 機能B: 3モード切替
| # | テスト | 期待結果 |
|---|-------|---------|
| 7 | 「単発」モード選択 | RAGのみ注入、過去会話なし (~4K tokens) |
| 8 | 「セッション」モード（デフォルト） | 直近5往復 + 古い会話要約 (~10K tokens) |
| 9 | 「フル」モードで10往復 | 全メッセージ送信、トークン数増加表示 |
| 10 | 「フル」モードで50K超 | ⚠️ 警告表示「セッションモード推奨」 |
| 11 | モード切替が即座に反映 | トークン推定値がリアルタイム更新 |

### 機能C: コピー機能
| # | テスト | 期待結果 |
|---|-------|---------|
| 12 | コードブロックの「コピー」タップ | クリップボードにコードコピー、「✓ コピー済み」表示 |
| 13 | 回答バブルの「📋 回答をコピー」タップ | 全文コピー |
| 14 | iPhoneでコピー→メモアプリにペースト | テキストが正しく貼り付け |

---

## 9. 新規/変更ファイルサマリー

| 種別 | ファイル | 内容 |
|------|---------|------|
| **新規** | `src/web/chat_store.py` | チャット履歴SQLiteストア + 3モードコンテキスト構築 |
| **新規** | `frontend/src/components/ChatListPanel.jsx` | チャット一覧サイドパネル |
| **新規** | `frontend/src/components/ContextModeSelector.jsx` | 単発/セッション/フル切替UI |
| **修正** | `src/web/api_routes.py` | チャットCRUD API追加 |
| **修正** | `src/web/server.py` | WebSocketにchat_id統合 + コンテキスト構築 |
| **修正** | `frontend/src/App.jsx` | ☰ メニュー + ChatListPanel統合 |
| **修正** | `frontend/src/components/InputBar.jsx` | ContextModeSelector + RAGトグル統合 |
| **修正** | `frontend/src/components/ChatView.jsx` | メッセージコピーボタン |
| **修正** | `frontend/src/components/MarkdownRenderer.jsx` | コードブロックコピーボタン |
| **修正** | `frontend/src/hooks/useWebSocket.js` | chat_id送受信対応 |

**既存PyQt6コードへの変更: ゼロ**

---

## 10. 3モードのトークン消費比較（20往復会話時）

```
                  1回の送信    20往復の累計      月100会話
単発モード:      ~4,000 tk    ~80,000 tk       ~8M tk
セッション:     ~10,000 tk   ~200,000 tk      ~20M tk
フルモード:     ~30,000 tk   ~500,000 tk      ~50M tk
                 (平均)

セッション vs フル = 約60%節約
単発 vs フル = 約84%節約
```

※ Maxプラン($150/月)はレート制限があるため、
  セッションモードをデフォルトにすることでAPIコスト面でも安全。

---

## 11. v9.3.0 への橋渡し（将来構想）

- サイドバー常時表示（タブレット横向き対応）
- チャット検索（キーワード/日付フィルタ）
- チャットエクスポート（Markdown形式でダウンロード）
- ministral-3:8b による自動要約の高品質化
- チャットのピン留め/お気に入り機能
