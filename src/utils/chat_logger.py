"""v11.0.0: 全タブ共通のJSONLチャットログ記録

全てのAIチャット（cloudAI/mixAI/localAI/RAG）の送受信を
追記専用のJSONLファイルに記録する。
Historyタブはこのファイルを読み込んで表示する。
"""
import json
import logging
import os
from collections import deque
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


def reset_chat_logger() -> None:
    """シングルトンをリセット（パス変更時・テスト用）"""
    global _instance
    _instance = None


class ChatLogger:
    """全タブ共通のJSONLチャットログ記録"""

    # v11.2.1: ファイルサイズ上限とアーカイブ設定
    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
    ARCHIVE_SUFFIX = ".bak"

    def __init__(self, log_path: str = None):
        self._log_path = Path(log_path or _DEFAULT_LOG_PATH)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # v11.2.1: ローテーション
    # ------------------------------------------------------------------

    def _rotate_if_needed(self) -> None:
        """ファイルサイズが上限を超えていればローテーションする。

        既存ファイルを .bak にリネームし、新しい空ファイルに書き込みを始める。
        .bak が既にあれば上書き（直近1世代のみ保持）。
        例外が発生してもログ記録を阻害しない。
        """
        try:
            if not self._log_path.exists():
                return
            if self._log_path.stat().st_size <= self.MAX_FILE_SIZE_BYTES:
                return

            bak_path = self._log_path.with_suffix(
                self._log_path.suffix + self.ARCHIVE_SUFFIX
            )
            self._log_path.replace(bak_path)
            logger.info(
                f"[ChatLogger] Rotated chat log: {self._log_path.name} → {bak_path.name} "
                f"(exceeded {self.MAX_FILE_SIZE_BYTES // 1024 // 1024} MB)"
            )
        except Exception as e:
            logger.warning(f"[ChatLogger] Rotation failed (continuing): {e}")

    # ------------------------------------------------------------------
    # ログ記録
    # ------------------------------------------------------------------

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
            # v11.2.1: 書き込み前にサイズチェック → 必要なら rotate
            self._rotate_if_needed()
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"Failed to write chat log: {e}")

    # ------------------------------------------------------------------
    # 検索
    # ------------------------------------------------------------------

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
        if not self._log_path.exists():
            return []

        # v11.2.1: フィルタなし → 末尾から limit+offset 件のみ読み込み（高速化）
        need = limit + offset
        if not query and (not tab or tab == "all"):
            tail: deque = deque(maxlen=need)
            try:
                with open(self._log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            tail.append(line)
            except Exception as e:
                logger.warning(f"Failed to read chat log: {e}")
                return []

            results = []
            for line in reversed(tail):  # 末尾 = 最新 → 新しい順
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return results[offset:offset + limit]

        # フィルタあり → 全件スキャン（既存動作を維持）
        results = []
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

    # ------------------------------------------------------------------
    # セッション一覧
    # ------------------------------------------------------------------

    def get_sessions(self, tab: str = None, limit: int = 50) -> list:
        """セッション一覧を取得（日付ごとにグルーピング）

        Returns:
            list[dict]: 日付ごとのセッション情報
        """
        # v11.2.1: limit=5000 → 500 に縮小
        entries = self.search(tab=tab, limit=500)
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

    # ------------------------------------------------------------------
    # コンテキスト構築
    # ------------------------------------------------------------------

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
