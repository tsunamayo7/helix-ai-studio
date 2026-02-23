"""v11.0.0: 全タブ共通のJSONLチャットログ記録

全てのAIチャット（cloudAI/mixAI/localAI/RAG）の送受信を
追記専用のJSONLファイルに記録する。
Historyタブはこのファイルを読み込んで表示する。
"""
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_LOG_PATH = "data/chat_history_log.jsonl"
_instance = None


def get_chat_logger(log_path: str = None) -> 'ChatLogger':
    """ChatLoggerのシングルトンインスタンスを取得"""
    global _instance
    if _instance is None:
        _instance = ChatLogger(log_path or _DEFAULT_LOG_PATH)
    return _instance


class ChatLogger:
    """全タブ共通のJSONLチャットログ記録"""

    def __init__(self, log_path: str = None):
        self._log_path = Path(log_path or _DEFAULT_LOG_PATH)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_message(self, tab: str, model: str, role: str, content: str,
                    session_id: str = None, duration_ms: float = None,
                    extra: dict = None):
        """メッセージを1行のJSONとしてログファイルに追記

        Args:
            tab: タブ名 ("cloudAI" / "mixAI" / "localAI" / "rag")
            model: 使用モデル名
            role: "user" / "assistant" / "system"
            content: メッセージ内容
            session_id: セッションID（任意）
            duration_ms: 応答時間ms（任意、assistant応答時）
            extra: 追加メタデータ（任意）
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tab": tab,
            "model": model,
            "role": role,
            "content": content,
        }
        if session_id:
            entry["session_id"] = session_id
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 2)
        if extra:
            entry.update(extra)

        try:
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"Failed to write chat log: {e}")

    def search(self, query: str = None, tab: str = None,
               limit: int = 50, offset: int = 0) -> list:
        """ログ検索（キーワード・タブフィルタ対応）

        Args:
            query: 検索キーワード（部分一致、大文字小文字無視）
            tab: タブフィルタ ("cloudAI" / "mixAI" / "localAI" / "rag" / None=全て)
            limit: 返却件数上限
            offset: スキップ件数

        Returns:
            list[dict]: マッチしたエントリのリスト（新しい順）
        """
        results = []
        if not self._log_path.exists():
            return results

        try:
            with open(self._log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if tab and tab != "all" and entry.get("tab") != tab:
                            continue
                        if query and query.lower() not in entry.get("content", "").lower():
                            continue
                        results.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to read chat log: {e}")

        # 新しい順にソート
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results[offset:offset + limit]

    def get_sessions(self, tab: str = None, limit: int = 50) -> list:
        """セッション一覧を取得（日付ごとにグルーピング）

        Returns:
            list[dict]: 日付ごとのセッション情報
        """
        entries = self.search(tab=tab, limit=5000)
        sessions_by_date = {}

        for entry in entries:
            ts = entry.get("timestamp", "")
            date_str = ts[:10] if len(ts) >= 10 else "unknown"
            if date_str not in sessions_by_date:
                sessions_by_date[date_str] = []
            sessions_by_date[date_str].append(entry)

        result = []
        for date_str in sorted(sessions_by_date.keys(), reverse=True)[:limit]:
            result.append({
                "date": date_str,
                "entries": sessions_by_date[date_str],
                "count": len(sessions_by_date[date_str]),
            })
        return result

    def build_history_context(self, query: str, max_entries: int = 5) -> str:
        """過去チャットから関連コンテキストを構築（AI参照用）"""
        results = self.search(query=query, limit=max_entries)
        if not results:
            return ""

        context_parts = ["<past_chat_history>"]
        for entry in results:
            context_parts.append(
                f"[{entry['timestamp']}] [{entry['tab']}] [{entry.get('model', 'unknown')}]\n"
                f"{entry['role']}: {entry['content'][:500]}"
            )
        context_parts.append("</past_chat_history>")
        return "\n".join(context_parts)
