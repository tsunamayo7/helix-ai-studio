"""
Helix AI Studio - Document Cleanup Manager (v8.5.0 Patch 1)
孤児検出・安全削除・ユーザー承認ベースのデータクリーンアップ

削除安全レベル:
  Level 1（完全孤児）: ソースファイルなし + semantic紐付けなし → 安全に削除可能
  Level 2（依存あり孤児）: ソースファイルなし + semantic紐付けあり → 要確認
  Level 3（ユーザー選択削除）: ユーザーが明示的に不要と判断 → 確認ダイアログ後削除
"""

import logging
import sqlite3
from pathlib import Path
from typing import List

from ..utils.constants import INFORMATION_FOLDER, SUPPORTED_DOC_EXTENSIONS

logger = logging.getLogger(__name__)


class DocumentCleanupManager:
    """Document Memory のクリーンアップ管理"""

    def __init__(self, db_path: str = "data/helix_memory.db",
                 information_folder: str = INFORMATION_FOLDER):
        self.db_path = db_path
        self.information_folder = information_folder

    def _get_conn(self) -> sqlite3.Connection:
        """DB接続を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def scan_orphans(self) -> list:
        """
        孤児データを検出する。

        Returns:
            list of {
                "source_file": str,
                "chunk_count": int,
                "semantic_links": int,
                "safety_level": 1 or 2,
                "safety_label": str,
                "last_built": str,
                "total_size_kb": float
            }
        """
        # 実ファイル一覧を取得
        folder = Path(self.information_folder)
        existing_files = set()
        if folder.exists():
            for f in folder.rglob('*'):
                if f.is_file() and f.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
                    existing_files.add(f.name)

        orphans = []
        try:
            conn = self._get_conn()
            try:
                # documentsテーブルからユニークなsource_fileを取得
                rows = conn.execute("""
                    SELECT source_file,
                           COUNT(*) as chunk_count,
                           MAX(created_at) as last_built,
                           SUM(LENGTH(content)) as total_bytes
                    FROM documents
                    GROUP BY source_file
                """).fetchall()

                for row in rows:
                    source_file = row["source_file"]
                    if source_file in existing_files:
                        continue  # ファイルが存在→孤児ではない

                    chunk_count = row["chunk_count"]
                    total_size_kb = round((row["total_bytes"] or 0) / 1024, 1)
                    last_built = row["last_built"] or ""

                    # semantic紐付け確認
                    sem_count = 0
                    try:
                        sem_row = conn.execute("""
                            SELECT COUNT(*) as cnt
                            FROM document_semantic_links
                            WHERE source_file = ?
                        """, (source_file,)).fetchone()
                        sem_count = sem_row["cnt"] if sem_row else 0
                    except Exception:
                        pass  # テーブルがない場合

                    if sem_count > 0:
                        safety_level = 2
                        safety_label = f"要確認（semantic紐付け {sem_count}件あり）"
                    else:
                        safety_level = 1
                        safety_label = "安全に削除可能"

                    orphans.append({
                        "source_file": source_file,
                        "chunk_count": chunk_count,
                        "semantic_links": sem_count,
                        "safety_level": safety_level,
                        "safety_label": safety_label,
                        "last_built": last_built,
                        "total_size_kb": total_size_kb,
                    })
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Orphan scan skipped: {e}")

        logger.info(f"Orphan scan: {len(orphans)} orphans detected")
        return orphans

    def delete_orphans(self, source_files: List[str],
                       delete_semantic_links: bool = False) -> dict:
        """
        指定された孤児データを削除する。

        Args:
            source_files: 削除対象のsource_file名リスト
            delete_semantic_links: Trueの場合、document_semantic_linksも削除

        Returns:
            {"deleted_chunks": int, "deleted_summaries": int,
             "deleted_links": int, "errors": list}
        """
        return self._delete_documents(source_files, delete_semantic_links)

    def delete_selected_documents(self, source_files: List[str]) -> dict:
        """
        ユーザーが選択したドキュメントのRAGデータを削除する。
        ファイル自体は削除せず、DBデータのみ削除。

        Args:
            source_files: 削除対象のsource_file名リスト

        Returns:
            {"deleted_chunks": int, "deleted_summaries": int,
             "deleted_links": int, "errors": list}
        """
        return self._delete_documents(source_files, delete_semantic_links=True)

    def _delete_documents(self, source_files: List[str],
                          delete_semantic_links: bool = False) -> dict:
        """ドキュメントデータの削除実行"""
        result = {
            "deleted_chunks": 0,
            "deleted_summaries": 0,
            "deleted_links": 0,
            "errors": [],
        }

        if not source_files:
            return result

        try:
            conn = self._get_conn()
            try:
                for sf in source_files:
                    try:
                        # documents テーブル
                        cur = conn.execute(
                            "DELETE FROM documents WHERE source_file = ?", (sf,))
                        result["deleted_chunks"] += cur.rowcount

                        # document_summaries テーブル
                        try:
                            cur = conn.execute(
                                "DELETE FROM document_summaries WHERE source_file = ?", (sf,))
                            result["deleted_summaries"] += cur.rowcount
                        except Exception:
                            pass  # テーブルがない場合

                        # document_semantic_links テーブル
                        if delete_semantic_links:
                            try:
                                cur = conn.execute(
                                    "DELETE FROM document_semantic_links WHERE source_file = ?", (sf,))
                                result["deleted_links"] += cur.rowcount
                            except Exception:
                                pass

                    except Exception as e:
                        result["errors"].append(f"{sf}: {e}")
                        logger.error(f"Failed to delete {sf}: {e}")

                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"Document cleanup failed: {e}")

        logger.info(
            f"Cleanup complete: {result['deleted_chunks']} chunks, "
            f"{result['deleted_summaries']} summaries, "
            f"{result['deleted_links']} links deleted"
        )
        return result

    def get_document_stats(self) -> dict:
        """Document Memory全体の統計情報を返す"""
        stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "total_summaries": 0,
            "total_semantic_links": 0,
            "orphan_count": 0,
            "last_build_date": "",
            "db_size_mb": 0.0,
        }

        # DBサイズ
        db_path = Path(self.db_path)
        if db_path.exists():
            stats["db_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

        try:
            conn = self._get_conn()
            try:
                # ドキュメント数・チャンク数
                row = conn.execute("""
                    SELECT COUNT(DISTINCT source_file) as docs,
                           COUNT(*) as chunks,
                           MAX(created_at) as last_build
                    FROM documents
                """).fetchone()
                if row:
                    stats["total_documents"] = row["docs"]
                    stats["total_chunks"] = row["chunks"]
                    stats["last_build_date"] = row["last_build"] or ""

                # 要約数
                try:
                    row = conn.execute("SELECT COUNT(*) as cnt FROM document_summaries").fetchone()
                    stats["total_summaries"] = row["cnt"] if row else 0
                except Exception:
                    pass

                # semantic紐付け数
                try:
                    row = conn.execute("SELECT COUNT(*) as cnt FROM document_semantic_links").fetchone()
                    stats["total_semantic_links"] = row["cnt"] if row else 0
                except Exception:
                    pass

            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Document stats unavailable: {e}")

        # 孤児数
        orphans = self.scan_orphans()
        stats["orphan_count"] = len(orphans)

        return stats
