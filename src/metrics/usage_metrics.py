"""
Usage Metrics Recorder - Phase 2.3

Backend呼び出しのメトリクス（コスト、時間、トークン数）を記録
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UsageMetricsRecorder:
    """
    使用メトリクスの記録器

    Backend呼び出しごとに、コスト、時間、トークン数などを記録し、
    logs/usage_metrics.jsonl に保存する
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Args:
            log_file: メトリクスログファイルのパス（デフォルト: logs/usage_metrics.jsonl）
        """
        if log_file is None:
            # プロジェクトルートのlogsディレクトリ
            project_root = Path(__file__).parent.parent.parent
            logs_dir = project_root / "logs"
            logs_dir.mkdir(exist_ok=True)
            log_file = logs_dir / "usage_metrics.jsonl"

        self.log_file = str(log_file)
        logger.info(f"[UsageMetricsRecorder] Initialized: log_file={self.log_file}")

    def record_call(
        self,
        session_id: str,
        backend: str,
        task_type: str,
        phase: str,
        duration_ms: float,
        tokens_est: Optional[int] = None,
        cost_est: Optional[float] = None,
        success: bool = True,
        error_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Backend呼び出しを記録

        Args:
            session_id: セッションID
            backend: Backend名
            task_type: タスク種別
            phase: フェーズ
            duration_ms: 処理時間（ミリ秒）
            tokens_est: トークン数（推定）
            cost_est: コスト（推定, USD）
            success: 成功/失敗
            error_type: エラー種別（失敗時）
            metadata: その他メタデータ
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "backend": backend,
            "task_type": task_type,
            "phase": phase,
            "duration_ms": duration_ms,
            "tokens_est": tokens_est,
            "cost_est": cost_est,
            "success": success,
            "error_type": error_type,
            "metadata": metadata or {},
        }

        try:
            # JSONLに追記
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            logger.info(
                f"[UsageMetricsRecorder] Recorded: backend={backend}, "
                f"task={task_type}, duration={duration_ms:.2f}ms, "
                f"cost=${cost_est:.6f}" if cost_est else f"cost=N/A"
            )

        except Exception as e:
            logger.error(f"[UsageMetricsRecorder] Failed to record: {e}")

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        セッションの集計サマリーを取得

        Args:
            session_id: セッションID

        Returns:
            集計結果
        """
        try:
            if not os.path.exists(self.log_file):
                return {
                    "total_calls": 0,
                    "total_duration_ms": 0,
                    "total_tokens_est": 0,
                    "total_cost_est": 0.0,
                    "success_count": 0,
                    "failure_count": 0,
                }

            # JSONLファイルを読み込み
            records = []
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if record.get("session_id") == session_id:
                            records.append(record)
                    except json.JSONDecodeError:
                        continue

            # 集計
            total_calls = len(records)
            total_duration_ms = sum(r.get("duration_ms", 0) for r in records)
            total_tokens_est = sum(r.get("tokens_est", 0) or 0 for r in records)
            total_cost_est = sum(r.get("cost_est", 0) or 0.0 for r in records)
            success_count = sum(1 for r in records if r.get("success", False))
            failure_count = total_calls - success_count

            return {
                "total_calls": total_calls,
                "total_duration_ms": total_duration_ms,
                "total_tokens_est": total_tokens_est,
                "total_cost_est": total_cost_est,
                "success_count": success_count,
                "failure_count": failure_count,
            }

        except Exception as e:
            logger.error(f"[UsageMetricsRecorder] Failed to get summary: {e}")
            return {}


# グローバルインスタンス（シングルトン）
_usage_metrics_recorder: Optional[UsageMetricsRecorder] = None


def get_usage_metrics_recorder() -> UsageMetricsRecorder:
    """
    UsageMetricsRecorder のグローバルインスタンスを取得

    Returns:
        UsageMetricsRecorder
    """
    global _usage_metrics_recorder
    if _usage_metrics_recorder is None:
        _usage_metrics_recorder = UsageMetricsRecorder()
    return _usage_metrics_recorder
