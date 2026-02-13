"""
Helix AI Studio - RAG Builder (v8.5.0 Patch 1)
RAG構築パイプラインの統括エンジン
Step 1 (Claude プラン) → Step 2 (ローカルLLM実行 A-H) → Step 3 (Claude検証)

v8.5.0 Patch 1 修正:
- P0-1: Sub-step A-H の8段階実行に拡張
- P0-2: _run_step で step_completed シグナル発行
- P1-1: _finish() で進捗100%に更新
- P2-2: RAG専用ログハンドラ設定
"""

import json
import logging
import time
import uuid
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .rag_planner import RAGPlanner
from .rag_executor import RAGExecutor
from .rag_verifier import RAGVerifier
from .time_estimator import TimeEstimator
from .diff_detector import DiffDetector
from ..utils.constants import INFORMATION_FOLDER

logger = logging.getLogger(__name__)


# =============================================================================
# RAGBuildLock: mixAI/soloAIロック管理
# =============================================================================

class RAGBuildLock:
    """RAG構築中のmixAI/soloAIロック管理"""

    def __init__(self):
        self._locked = False
        self._lock_reason = ""
        self._progress = 0
        self._remaining_seconds = 0

    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def lock_reason(self) -> str:
        return self._lock_reason

    @property
    def progress(self) -> int:
        return self._progress

    @property
    def remaining_seconds(self) -> int:
        return self._remaining_seconds

    def acquire(self, reason: str = "RAG構築中"):
        self._locked = True
        self._lock_reason = reason
        logger.info(f"mixAI/soloAI locked: {reason}")

    def release(self):
        self._locked = False
        self._lock_reason = ""
        self._progress = 0
        self._remaining_seconds = 0
        logger.info("mixAI/soloAI unlocked")

    def update_progress(self, progress: int, remaining_seconds: int = 0):
        self._progress = progress
        self._remaining_seconds = remaining_seconds


# =============================================================================
# RAGBuildSignals: Qt シグナル
# =============================================================================

class RAGBuildSignals(QObject):
    """RAG構築進捗のQtシグナル"""

    # 全体進捗
    progress_updated = pyqtSignal(int, int, str)     # current, total, message
    time_updated = pyqtSignal(float, float)           # elapsed_min, remaining_min

    # ステップ進捗
    step_started = pyqtSignal(int, str)               # step_id, step_name
    step_progress = pyqtSignal(int, int, int, str)    # step_id, current, total, file
    step_completed = pyqtSignal(int, str)             # step_id, result_summary

    # 状態変更
    status_changed = pyqtSignal(str)                  # pending/running/verifying/...
    lock_changed = pyqtSignal(bool)                   # True=ロック / False=解除

    # エラー
    error_occurred = pyqtSignal(str, str)             # step_name, error_message

    # 検証結果
    verification_result = pyqtSignal(dict)            # Claude検証結果JSON

    # 完了
    build_completed = pyqtSignal(bool, str)           # success, message


# =============================================================================
# Sub-step定義: 8段階実行パイプライン
# =============================================================================

# Sub-step A-H: 実際のRAG構築処理単位
SUBSTEP_DEFINITIONS = [
    {"id": "A", "name": "チャンキング", "index": 0},
    {"id": "B", "name": "Embedding生成", "index": 1},
    {"id": "C", "name": "要約・キーワード抽出", "index": 2},
    {"id": "D", "name": "エンティティ抽出・TKGエッジ構築", "index": 3},
    {"id": "E", "name": "RAPTOR階層要約生成", "index": 4},
    {"id": "F", "name": "GraphRAGコミュニティ検出・要約", "index": 5},
    {"id": "G", "name": "要約Embedding生成・永続化", "index": 6},
    {"id": "H", "name": "検証クエリ品質チェック", "index": 7},
]

# total_steps = 8 (A-H) + 1 (plan) + 1 (verify) = 10
TOTAL_SUBSTEPS = len(SUBSTEP_DEFINITIONS)  # 8


# =============================================================================
# RAGBuilder: 統括エンジン
# =============================================================================

class RAGBuilder(QThread):
    """RAG構築パイプライン統括エンジン（QThread）"""

    def __init__(self, folder_path: str = INFORMATION_FOLDER,
                 db_path: str = "data/helix_memory.db",
                 time_limit_minutes: int = 30,
                 plan: Optional[dict] = None,
                 parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.db_path = db_path
        self.time_limit_minutes = time_limit_minutes
        self.existing_plan = plan

        self.signals = RAGBuildSignals()
        self.lock = RAGBuildLock()

        self.planner = RAGPlanner()
        self.executor = RAGExecutor(db_path=db_path)
        self.verifier = RAGVerifier(db_path=db_path)
        self.time_estimator = TimeEstimator()

        self._cancelled = False
        self._current_plan = None
        self._start_time = 0
        # P0-1: 実際の実行ステップ数に基づく total_steps
        self._total_steps = TOTAL_SUBSTEPS + 2  # +2 for plan + verify

        # P2-2: RAG専用ログハンドラ設定
        self._setup_rag_logging()

    def _setup_rag_logging(self):
        """RAG専用ログハンドラを設定"""
        rag_logger = logging.getLogger("src.rag")
        if not any(isinstance(h, RotatingFileHandler) for h in rag_logger.handlers):
            try:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)
                handler = RotatingFileHandler(
                    str(log_dir / "rag_pipeline.log"),
                    maxBytes=5 * 1024 * 1024,  # 5MB
                    backupCount=3,
                    encoding="utf-8",
                )
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                rag_logger.addHandler(handler)
                rag_logger.setLevel(logging.DEBUG)
                rag_logger.info("RAG pipeline logger initialized")
            except Exception as e:
                logger.warning(f"Failed to setup RAG logging: {e}")

    def cancel(self):
        """構築を中止"""
        self._cancelled = True
        self.executor.cancel()

    def run(self):
        """メインパイプライン実行"""
        self._cancelled = False
        self.executor.reset()
        self._start_time = time.time()
        self._completed_steps = 0
        self._build_log = {
            "build_id": str(uuid.uuid4()),
            "start_time": datetime.now().isoformat(),
            "steps_completed": [],
            "steps_failed": [],
            "status": "running",
        }

        try:
            # ロック取得
            self.lock.acquire("RAG構築中")
            self.signals.lock_changed.emit(True)
            self.signals.status_changed.emit("running")

            # DBスキーマ確認
            self._ensure_db_schema()

            # ----- Step 0: Claude プラン策定 -----
            self.signals.step_started.emit(0, "Claude プラン策定")
            if self.existing_plan:
                plan = self.existing_plan
                logger.info("Using existing plan")
            else:
                plan = self.planner.create_plan(
                    self.folder_path, self.time_limit_minutes
                )
            self._current_plan = plan
            file_count = len(plan.get('analysis', {}).get('file_classifications', []))
            self.signals.step_completed.emit(0, f"プラン作成完了: {file_count}ファイル")

            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            # プランをDBに記録
            self._save_plan_log(plan, "running")

            # 推定時間計算
            total_est = self.time_estimator.estimate_from_plan(plan)
            self.signals.time_updated.emit(0.0, total_est)

            steps = plan.get("execution_plan", {}).get("steps", [])

            # ----- Step 2: ローカルLLM自律実行 (Sub-step A-H) -----
            self.signals.status_changed.emit("running")

            # Sub-step A: チャンキング
            self._run_step(steps, 0, "チャンキング")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            chunks = self.executor.execute_chunking(
                plan, self.folder_path,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(1, cur, tot, f)
            )

            if not chunks:
                self._finish(False, "チャンクが生成されませんでした")
                return

            self.signals.step_completed.emit(1, f"{len(chunks)}チャンク生成")
            self._completed_steps += 1

            # 古いデータをクリア（差分更新対応）
            self.executor.clear_all_chunks()

            # Sub-step B: Embedding生成
            self._run_step(steps, 1, "Embedding生成")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            chunks = self.executor.execute_embeddings(
                chunks,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(2, cur, tot, f)
            )

            embedded_count = sum(1 for c in chunks if c.embedding)
            self.signals.step_completed.emit(2, f"Embedding完了: {embedded_count}/{len(chunks)}")
            self._completed_steps += 1

            # DBに保存
            self.executor.save_chunks_to_db(chunks)

            # Sub-step C: 要約・キーワード抽出 (ministral-3:8b)
            self._run_step(steps, 2, "要約・キーワード抽出")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            chunks = self.executor.execute_summarization(
                chunks,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(3, cur, tot, f)
            )

            summarized_count = sum(1 for c in chunks if c.summary)
            self.signals.step_completed.emit(3, f"要約完了: {summarized_count}/{len(chunks)}")
            self._completed_steps += 1

            # 要約結果をDBに反映
            self._update_chunk_metadata(chunks)

            # Sub-step D: エンティティ抽出・TKGエッジ構築 (command-a:111b)
            self._run_step(steps, 3, "エンティティ抽出・TKGエッジ構築")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            kg_model = "command-a:111b"
            for step in steps:
                if "Semantic" in step.get("name", "") or "TKG" in step.get("name", ""):
                    kg_model = step.get("model", kg_model)
                    break

            kg_result = self.executor.execute_kg_generation(
                chunks, model=kg_model,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(4, cur, tot, f)
            )

            if isinstance(kg_result, dict):
                nodes_added = kg_result.get("nodes_added", 0)
                edges_added = kg_result.get("edges_added", 0)
                self.signals.step_completed.emit(
                    4, f"TKG構築完了: {nodes_added}ノード, {edges_added}エッジ"
                )
            else:
                self.signals.step_completed.emit(4, f"TKG構築完了: {kg_result}ノード")
            self._completed_steps += 1

            # Sub-step E: RAPTOR階層要約生成 (command-a:111b)
            self._run_step(steps, 4, "RAPTOR階層要約生成")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            raptor_result = self.executor.execute_raptor_summaries(
                chunks,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(5, cur, tot, f)
            )

            raptor_count = raptor_result if isinstance(raptor_result, int) else 0
            self.signals.step_completed.emit(5, f"RAPTOR要約完了: {raptor_count}件")
            self._completed_steps += 1

            # Sub-step F: GraphRAGコミュニティ検出・要約 (command-a:111b)
            self._run_step(steps, 5, "GraphRAGコミュニティ検出・要約")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            community_result = self.executor.execute_graphrag_communities(
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(6, cur, tot, f)
            )

            community_count = community_result if isinstance(community_result, int) else 0
            self.signals.step_completed.emit(
                6, f"GraphRAGコミュニティ完了: {community_count}件"
            )
            self._completed_steps += 1

            # Sub-step G: 要約Embedding生成・永続化 (qwen3-embedding:4b)
            self._run_step(steps, 6, "要約Embedding生成・永続化")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            summary_emb_result = self.executor.execute_summary_embeddings(
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(7, cur, tot, f)
            )

            summary_emb_count = summary_emb_result if isinstance(summary_emb_result, int) else 0
            self.signals.step_completed.emit(
                7, f"要約Embedding完了: {summary_emb_count}件"
            )
            self._completed_steps += 1

            # Sub-step H: 検証クエリ品質チェック (ministral-3:8b)
            self._run_step(steps, 7, "検証クエリ品質チェック")
            if self._cancelled:
                self._finish(False, "ユーザーにより中止されました")
                return

            verification_queries_result = self.executor.execute_verification_queries(
                chunks,
                progress_callback=lambda name, cur, tot, f:
                    self.signals.step_progress.emit(8, cur, tot, f)
            )

            vq_score = 0
            if isinstance(verification_queries_result, dict):
                vq_score = verification_queries_result.get("avg_score", 0)
            self.signals.step_completed.emit(
                8, f"品質チェック完了: スコア {vq_score}"
            )
            self._completed_steps += 1

            # ----- Step 3: Claude 品質検証 -----
            self.signals.status_changed.emit("verifying")
            verify_step_id = TOTAL_SUBSTEPS + 1  # = 9
            self.signals.step_started.emit(verify_step_id, "Claude 品質検証")

            verification = self.verifier.verify(plan, self.folder_path)
            self.signals.verification_result.emit(verification)

            verdict = verification.get("overall_verdict", "FAIL")
            score = verification.get("score", 0)

            self.signals.step_completed.emit(
                verify_step_id,
                f"検証結果: {verdict} (スコア: {score})"
            )

            # 検証結果をDBに保存（P2-1: PASS時も保存）
            verification_json = json.dumps(verification, ensure_ascii=False)

            if verdict == "PASS":
                self._save_plan_log(plan, "completed",
                                    error_details=verification_json)
                self._finish(True, f"RAG構築完了 (品質スコア: {score})")
            elif verdict == "SKIP":
                self._save_plan_log(plan, "completed",
                                    error_details=verification_json)
                self._finish(True, "RAG構築完了（品質検証スキップ）")
            else:
                # FAIL時: 修正ステップを記録
                remediation = verification.get("remediation_steps", [])
                self._save_plan_log(plan, "failed",
                                    error_details=verification_json)
                self._finish(False,
                             f"品質検証FAIL (スコア: {score}). "
                             f"修正ステップ: {len(remediation)}件")

        except Exception as e:
            logger.error(f"RAG build failed: {e}", exc_info=True)
            self.signals.error_occurred.emit("build", str(e))
            self._finish(False, f"エラー: {str(e)[:200]}")

    def _run_step(self, steps: list, step_index: int, step_name: str):
        """ステップ開始処理（P0-2修正版）"""
        step_id = step_index + 1
        self.signals.step_started.emit(step_id, step_name)

        elapsed = (time.time() - self._start_time) / 60
        progress = int(((step_id) / self._total_steps) * 100)
        self.lock.update_progress(progress)

        # 残り時間更新
        if step_index < len(steps):
            remaining = self.time_estimator.update_estimate(
                step_id, elapsed, steps[step_index:]
            )
            self.signals.time_updated.emit(elapsed, remaining)

        self.signals.progress_updated.emit(step_id, self._total_steps, step_name)

    def _finish(self, success: bool, message: str):
        """構築完了処理（P1-1: 進捗100%に更新）"""
        elapsed = (time.time() - self._start_time) / 60
        self.signals.time_updated.emit(elapsed, 0)

        # P1-1: 進捗を100%に更新
        self.signals.progress_updated.emit(
            self._total_steps, self._total_steps, "RAG構築完了"
        )

        self.signals.status_changed.emit("completed" if success else "failed")
        self.lock.release()
        self.signals.lock_changed.emit(False)
        self.signals.build_completed.emit(success, message)
        logger.info(f"RAG build finished: success={success}, elapsed={elapsed:.1f}min, "
                    f"completed_steps={self._completed_steps}/{TOTAL_SUBSTEPS}, {message}")

    def _update_chunk_metadata(self, chunks):
        """チャンクの要約・キーワード・エンティティをDBに反映"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            for chunk in chunks:
                if chunk.summary or chunk.keywords:
                    tags_json = json.dumps(chunk.keywords or [], ensure_ascii=False)
                    conn.execute(
                        "UPDATE documents SET tags = ?, updated_at = CURRENT_TIMESTAMP "
                        "WHERE source_file = ? AND chunk_index = ?",
                        (tags_json, chunk.source_file, chunk.chunk_index)
                    )
            conn.commit()
        finally:
            conn.close()

    def _ensure_db_schema(self):
        """v8.5.0 DBスキーマを確認・作成"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                title TEXT,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                chunk_embedding BLOB,
                metadata TEXT,
                category TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS document_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                level TEXT NOT NULL CHECK(level IN ('chunk', 'document', 'collection')),
                summary TEXT NOT NULL,
                summary_embedding BLOB,
                entity_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS rag_build_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'verifying',
                                     'completed', 'failed', 'cancelled')),
                total_steps INTEGER DEFAULT 0,
                completed_steps INTEGER DEFAULT 0,
                estimated_minutes FLOAT,
                actual_minutes FLOAT,
                error_details TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS document_semantic_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER REFERENCES documents(id),
                semantic_node_id INTEGER REFERENCES semantic_nodes(id),
                link_type TEXT DEFAULT 'extracted',
                confidence REAL DEFAULT 1.0,
                UNIQUE(document_id, semantic_node_id)
            )
        """)

        # マイグレーション: 旧スキーマ(relation_type)から新スキーマ(link_type/confidence)へ
        try:
            cols = [row[1] for row in c.execute(
                "PRAGMA table_info(document_semantic_links)"
            ).fetchall()]
            if "relation_type" in cols and "link_type" not in cols:
                logger.info("Migrating document_semantic_links: relation_type -> link_type/confidence")
                c.execute("ALTER TABLE document_semantic_links RENAME TO _dsl_old")
                c.execute("""
                    CREATE TABLE document_semantic_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER REFERENCES documents(id),
                        semantic_node_id INTEGER REFERENCES semantic_nodes(id),
                        link_type TEXT DEFAULT 'extracted',
                        confidence REAL DEFAULT 1.0,
                        UNIQUE(document_id, semantic_node_id)
                    )
                """)
                c.execute("""
                    INSERT OR IGNORE INTO document_semantic_links
                        (document_id, semantic_node_id, link_type, confidence)
                    SELECT document_id, semantic_node_id, relation_type, 1.0
                    FROM _dsl_old
                """)
                c.execute("DROP TABLE _dsl_old")
                logger.info("Migration complete: document_semantic_links")
        except Exception as e:
            logger.debug(f"document_semantic_links migration check: {e}")

        # インデックス
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_file)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(source_hash)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_doc_summaries_file ON document_summaries(source_file)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_rag_logs_status ON rag_build_logs(status)")

        conn.commit()
        conn.close()
        logger.info("v8.5.0 database schema ensured")

    def _save_plan_log(self, plan: dict, status: str, error_details: str = None):
        """プランをrag_build_logsに保存（completed_stepsを正しく更新）"""
        conn = sqlite3.connect(self.db_path)
        try:
            plan_id = plan.get("plan_id", str(uuid.uuid4()))
            steps = plan.get("execution_plan", {}).get("steps", [])
            est_minutes = plan.get("execution_plan", {}).get("total_estimated_minutes", 0)
            elapsed = (time.time() - self._start_time) / 60 if self._start_time else 0

            # 既存レコードを更新 or 新規挿入
            existing = conn.execute(
                "SELECT id FROM rag_build_logs WHERE plan_id = ?", (plan_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE rag_build_logs SET status = ?, actual_minutes = ?, "
                    "completed_steps = ?, error_details = ?, completed_at = ? "
                    "WHERE plan_id = ?",
                    (status, round(elapsed, 2), self._completed_steps,
                     error_details,
                     datetime.now().isoformat() if status in ("completed", "failed") else None,
                     plan_id)
                )
            else:
                conn.execute(
                    "INSERT INTO rag_build_logs "
                    "(plan_id, plan_json, status, total_steps, completed_steps, "
                    "estimated_minutes, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (plan_id, json.dumps(plan, ensure_ascii=False),
                     status, TOTAL_SUBSTEPS, self._completed_steps,
                     est_minutes, datetime.now().isoformat())
                )
            conn.commit()
        finally:
            conn.close()

    def get_rag_stats(self) -> dict:
        """現在のRAG統計を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            self._ensure_db_schema()
            total_chunks = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
            embedded = conn.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE chunk_embedding IS NOT NULL"
            ).fetchone()["cnt"]
            nodes = conn.execute(
                "SELECT COUNT(*) as cnt FROM semantic_nodes WHERE valid_to IS NULL"
            ).fetchone()["cnt"]
            summaries = conn.execute(
                "SELECT COUNT(*) as cnt FROM document_summaries"
            ).fetchone()["cnt"]
            builds = conn.execute(
                "SELECT COUNT(*) as cnt FROM rag_build_logs WHERE status = 'completed'"
            ).fetchone()["cnt"]
            last_build = conn.execute(
                "SELECT completed_at FROM rag_build_logs WHERE status = 'completed' "
                "ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()

            return {
                "total_chunks": total_chunks,
                "total_embeddings": embedded,
                "semantic_nodes": nodes,
                "document_summaries": summaries,
                "build_count": builds,
                "last_build": last_build["completed_at"] if last_build else None,
            }
        except Exception as e:
            logger.debug(f"RAG stats query error: {e}")
            return {
                "total_chunks": 0, "total_embeddings": 0, "semantic_nodes": 0,
                "document_summaries": 0, "build_count": 0, "last_build": None,
            }
        finally:
            conn.close()
