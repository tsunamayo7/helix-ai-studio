"""
Helix AI Studio - Knowledge Manager (v5.0.0)
自動ナレッジ管理マネージャー

会話完了後にローカルLLMが自動的にチャット内容を分析・整理し、知識として格納する。
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests

logger = logging.getLogger(__name__)


class KnowledgeManager:
    """自動ナレッジ管理マネージャー"""

    OLLAMA_API = "http://localhost:11434/api"
    SUMMARY_MODEL = "nemotron-3-nano:30b"
    EMBEDDING_MODEL = "qwen3-embedding:4b"

    def __init__(
        self,
        knowledge_db_path: str = None,
        ollama_url: str = None,
        summary_model: str = None,
        embedding_model: str = None,
    ):
        # デフォルトパス
        if knowledge_db_path is None:
            app_dir = Path(__file__).parent.parent.parent
            knowledge_db_path = str(app_dir / "data" / "knowledge.db")

        self.knowledge_db_path = knowledge_db_path
        self.ollama_api = ollama_url or self.OLLAMA_API
        self.summary_model = summary_model or self.SUMMARY_MODEL
        self.embedding_model = embedding_model or self.EMBEDDING_MODEL

        # データベース初期化
        self._init_database()

    def _init_database(self):
        """SQLiteデータベースを初期化"""
        Path(self.knowledge_db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                topic TEXT,
                summary TEXT,
                keywords TEXT,
                decisions TEXT,
                code_snippets TEXT,
                action_items TEXT,
                ondemand_models_used TEXT,
                conversation_length INTEGER,
                raw_json TEXT,
                embedding BLOB,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_timestamp ON knowledge(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge(topic)
        """)

        conn.commit()
        conn.close()

        logger.info(f"[KnowledgeManager] Database initialized: {self.knowledge_db_path}")

    def process_conversation(self, conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        会話を処理してナレッジを抽出・格納

        Args:
            conversation: [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            dict: 抽出されたナレッジ情報
        """
        if not conversation:
            return {"error": "Empty conversation"}

        # 会話をテキストに変換
        conv_text = "\n".join([
            f"{'ユーザー' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}"
            for m in conversation
        ])

        # ローカルLLMで要約・構造化
        summary_prompt = f"""以下の会話を分析し、JSONで要約してください。

会話内容:
{conv_text[:8000]}  # 長すぎる場合は切り詰め

以下のJSON形式で回答（日本語）:
{{
    "topic": "メイントピック",
    "keywords": ["キーワード1", "キーワード2"],
    "decisions": ["決定事項1"],
    "code_snippets": [
        {{"language": "python", "description": "説明", "code": "コード"}}
    ],
    "action_items": ["次のアクション"],
    "ondemand_models_used": ["使用されたオンデマンドモデル名"],
    "summary": "50字以内の要約"
}}

JSONのみを出力してください。"""

        try:
            response = requests.post(
                f"{self.ollama_api}/generate",
                json={
                    "model": self.summary_model,
                    "prompt": summary_prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=120,
            )

            if response.status_code != 200:
                logger.error(f"[KnowledgeManager] Ollama API error: {response.status_code}")
                return {"error": f"Ollama API error: {response.status_code}"}

            result = response.json()
            response_text = result.get("response", "{}")

            # JSONをパース
            try:
                knowledge = json.loads(response_text)
            except json.JSONDecodeError:
                # JSON解析失敗時はシンプルな構造で保存
                knowledge = {
                    "topic": "会話",
                    "summary": conv_text[:50] + "...",
                    "keywords": [],
                    "decisions": [],
                    "code_snippets": [],
                    "action_items": [],
                    "ondemand_models_used": [],
                }

            # メタデータ追加
            knowledge["timestamp"] = datetime.now().isoformat()
            knowledge["conversation_length"] = len(conversation)

            # ベクトル化（オプション）
            embedding = self._generate_embedding(knowledge)
            if embedding:
                knowledge["_embedding"] = embedding

            # SQLiteに保存
            self._save_to_db(knowledge)

            logger.info(f"[KnowledgeManager] Knowledge saved: {knowledge.get('topic', 'N/A')}")
            return knowledge

        except requests.Timeout:
            logger.error("[KnowledgeManager] Ollama timeout")
            return {"error": "Ollama timeout"}
        except Exception as e:
            logger.exception("[KnowledgeManager] Error processing conversation")
            return {"error": str(e)}

    def _generate_embedding(self, knowledge: Dict[str, Any]) -> Optional[List[float]]:
        """ナレッジのベクトル埋め込みを生成"""
        text_to_embed = f"{knowledge.get('topic', '')} {knowledge.get('summary', '')}"

        if not text_to_embed.strip():
            return None

        try:
            response = requests.post(
                f"{self.ollama_api}/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text_to_embed,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])

        except Exception as e:
            logger.warning(f"[KnowledgeManager] Embedding failed: {e}")

        return None

    def _save_to_db(self, knowledge: Dict[str, Any]):
        """SQLiteに保存"""
        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        # 埋め込みを取り出し（BLOBとして保存）
        embedding = knowledge.pop("_embedding", None)
        embedding_blob = json.dumps(embedding).encode() if embedding else None

        cursor.execute("""
            INSERT INTO knowledge (
                timestamp, topic, summary, keywords, decisions,
                code_snippets, action_items, ondemand_models_used,
                conversation_length, raw_json, embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            knowledge.get("timestamp", ""),
            knowledge.get("topic", ""),
            knowledge.get("summary", ""),
            json.dumps(knowledge.get("keywords", []), ensure_ascii=False),
            json.dumps(knowledge.get("decisions", []), ensure_ascii=False),
            json.dumps(knowledge.get("code_snippets", []), ensure_ascii=False),
            json.dumps(knowledge.get("action_items", []), ensure_ascii=False),
            json.dumps(knowledge.get("ondemand_models_used", []), ensure_ascii=False),
            knowledge.get("conversation_length", 0),
            json.dumps(knowledge, ensure_ascii=False),
            embedding_blob,
        ))

        conn.commit()
        conn.close()

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """ナレッジを検索"""
        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        # シンプルなテキスト検索
        cursor.execute("""
            SELECT id, timestamp, topic, summary, keywords, decisions, action_items
            FROM knowledge
            WHERE topic LIKE ? OR summary LIKE ? OR keywords LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "timestamp": row[1],
                "topic": row[2],
                "summary": row[3],
                "keywords": json.loads(row[4]) if row[4] else [],
                "decisions": json.loads(row[5]) if row[5] else [],
                "action_items": json.loads(row[6]) if row[6] else [],
            })

        conn.close()
        return results

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """最近のナレッジを取得"""
        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, topic, summary, conversation_length
            FROM knowledge
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "timestamp": row[1],
                "topic": row[2],
                "summary": row[3],
                "conversation_length": row[4],
            })

        conn.close()
        return results

    def get_by_id(self, knowledge_id: int) -> Optional[Dict[str, Any]]:
        """IDでナレッジを取得"""
        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT raw_json FROM knowledge WHERE id = ?
        """, (knowledge_id,))

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return json.loads(row[0])
        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        ナレッジDBの統計情報を取得 (v6.3.0: 問題7対策)

        Returns:
            dict: {"count": 件数, "last_updated": 最終更新日時}
        """
        conn = sqlite3.connect(self.knowledge_db_path)
        cursor = conn.cursor()

        try:
            # 総件数
            cursor.execute("SELECT COUNT(*) FROM knowledge")
            count = cursor.fetchone()[0]

            # 最終更新日時
            cursor.execute("SELECT MAX(timestamp) FROM knowledge")
            last_row = cursor.fetchone()
            last_updated = last_row[0] if last_row and last_row[0] else None

            conn.close()

            return {
                "count": count,
                "last_updated": last_updated,
            }

        except Exception as e:
            logger.error(f"[KnowledgeManager] Failed to get stats: {e}")
            conn.close()
            return {"count": 0, "last_updated": None}

    def get_count(self) -> int:
        """ナレッジの総件数を取得（互換性用ショートカット）"""
        return self.get_stats().get("count", 0)


# シングルトンインスタンス
_manager_instance = None


def get_knowledge_manager(knowledge_db_path: str = None) -> KnowledgeManager:
    """KnowledgeManagerのシングルトンインスタンスを取得"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = KnowledgeManager(knowledge_db_path)
    return _manager_instance
