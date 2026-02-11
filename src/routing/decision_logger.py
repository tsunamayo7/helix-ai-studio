"""
Routing Decision Logger - Phase 2.5

ルーティング決定の記録・追跡機能
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """
    ルーティング決定のデータクラス

    送信1回につき1レコード生成される
    """
    timestamp: str
    session_id: str
    phase: str
    task_type: str
    selected_backend: str
    user_forced_backend: bool = False
    reason_codes: List[str] = field(default_factory=list)
    fallback_attempted: bool = False
    fallback_chain: List[str] = field(default_factory=list)
    final_status: str = "pending"  # "success" | "error" | "blocked"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    # Phase 2.6追加
    approval_snapshot: Optional[Dict[str, bool]] = None
    policy_blocked: bool = False
    policy_block_reason: Optional[str] = None
    # Phase 2.7追加
    preset_name: Optional[str] = None
    # Phase 2.9追加
    prompt_pack: Optional[str] = None
    # Phase 3.0追加
    local_available: Optional[bool] = None
    # メタデータ
    duration_ms: Optional[float] = None
    tokens_est: Optional[int] = None
    cost_est: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（機密マスク済み）"""
        data = asdict(self)
        # 機密情報をマスク（必要に応じて追加）
        return data


class RoutingDecisionLogger:
    """
    ルーティング決定の記録器

    logs/routing_decisions.jsonl に追記形式で保存
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Args:
            log_file: ログファイルのパス（デフォルト: logs/routing_decisions.jsonl）
        """
        if log_file is None:
            project_root = Path(__file__).parent.parent.parent
            logs_dir = project_root / "logs"
            logs_dir.mkdir(exist_ok=True)
            log_file = logs_dir / "routing_decisions.jsonl"

        self.log_file = str(log_file)
        logger.info(f"[RoutingDecisionLogger] Initialized: log_file={self.log_file}")

    def log_decision(self, decision: RoutingDecision):
        """
        ルーティング決定を記録

        Args:
            decision: RoutingDecision インスタンス
        """
        try:
            record = decision.to_dict()

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            logger.info(
                f"[RoutingDecisionLogger] Logged: backend={decision.selected_backend}, "
                f"status={decision.final_status}, fallback={decision.fallback_attempted}"
            )

        except Exception as e:
            logger.error(f"[RoutingDecisionLogger] Failed to log: {e}")

    def create_decision(
        self,
        session_id: str,
        phase: str,
        task_type: str,
        selected_backend: str,
        user_forced_backend: bool = False,
        reason_codes: Optional[List[str]] = None,
    ) -> RoutingDecision:
        """
        新しいルーティング決定を作成（まだ記録しない）

        Args:
            session_id: セッションID
            phase: フェーズ
            task_type: タスク種別
            selected_backend: 選択されたBackend
            user_forced_backend: ユーザーが明示的に指定したか
            reason_codes: 理由コードのリスト

        Returns:
            RoutingDecision インスタンス
        """
        return RoutingDecision(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            phase=phase,
            task_type=task_type,
            selected_backend=selected_backend,
            user_forced_backend=user_forced_backend,
            reason_codes=reason_codes or [],
        )

    def finalize_decision(
        self,
        decision: RoutingDecision,
        final_status: str,
        fallback_chain: Optional[List[str]] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        tokens_est: Optional[int] = None,
        cost_est: Optional[float] = None,
    ):
        """
        ルーティング決定を確定して記録

        Args:
            decision: RoutingDecision インスタンス
            final_status: 最終ステータス
            fallback_chain: フォールバックチェーン
            error_type: エラー種別
            error_message: エラーメッセージ（短文）
            duration_ms: 処理時間
            tokens_est: トークン数（推定）
            cost_est: コスト（推定）
        """
        decision.final_status = final_status
        decision.fallback_chain = fallback_chain or [decision.selected_backend]
        decision.fallback_attempted = len(decision.fallback_chain) > 1
        decision.error_type = error_type

        # エラーメッセージは短文に制限（機密マスク）
        if error_message:
            decision.error_message = self._mask_and_truncate(error_message, max_len=200)

        decision.duration_ms = duration_ms
        decision.tokens_est = tokens_est
        decision.cost_est = cost_est

        # 記録
        self.log_decision(decision)

    def _mask_and_truncate(self, text: str, max_len: int = 200) -> str:
        """機密情報をマスクして短縮"""
        import re

        # APIキーなどをマスク
        patterns = [
            (r'(api[_-]?key|apikey|token|secret|password)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{8,})["\']?', r'\1=***MASKED***'),
            (r'sk-[a-zA-Z0-9]{20,}', '***API_KEY_MASKED***'),
        ]

        masked = text
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)

        # 長さ制限
        if len(masked) > max_len:
            masked = masked[:max_len] + "..."

        return masked

    def log_local_connection_error(
        self,
        session_id: str,
        phase: str,
        task_type: str,
        error_type: str,
        error_message: str,
    ):
        """
        Local未接続エラーを記録（CP1: final_status="error"で残す）

        Args:
            session_id: セッションID
            phase: フェーズ
            task_type: タスク種別
            error_type: エラー種別（NotConnectedError, HealthcheckFailed等）
            error_message: エラーメッセージ
        """
        decision = RoutingDecision(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            phase=phase,
            task_type=task_type,
            selected_backend="local",
            user_forced_backend=False,
            reason_codes=["local_connection_error"],
            fallback_attempted=False,
            fallback_chain=["local"],
            final_status="error",
            error_type=error_type,
            error_message=self._mask_and_truncate(error_message, max_len=200),
            local_available=False,
        )
        self.log_decision(decision)

    def read_recent_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        直近のルーティング決定を読み込み

        Args:
            limit: 最大件数

        Returns:
            決定レコードのリスト（新しい順）
        """
        try:
            if not os.path.exists(self.log_file):
                return []

            records = []
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        records.append(record)
                    except json.JSONDecodeError:
                        continue

            # 新しい順に並べ替え
            records.reverse()

            # 件数制限
            return records[:limit]

        except Exception as e:
            logger.error(f"[RoutingDecisionLogger] Failed to read: {e}")
            return []

    def get_decisions_by_session(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        セッション別のルーティング決定を取得

        Args:
            session_id: セッションID
            limit: 最大件数

        Returns:
            決定レコードのリスト
        """
        all_decisions = self.read_recent_decisions(limit=1000)

        session_decisions = [
            d for d in all_decisions
            if d.get("session_id") == session_id
        ]

        return session_decisions[:limit]

    def get_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        統計情報を取得

        Args:
            session_id: セッションID（Noneの場合は全体）

        Returns:
            統計情報
        """
        if session_id:
            decisions = self.get_decisions_by_session(session_id, limit=1000)
        else:
            decisions = self.read_recent_decisions(limit=1000)

        total = len(decisions)
        success_count = sum(1 for d in decisions if d.get("final_status") == "success")
        error_count = sum(1 for d in decisions if d.get("final_status") == "error")
        blocked_count = sum(1 for d in decisions if d.get("final_status") == "blocked")
        fallback_count = sum(1 for d in decisions if d.get("fallback_attempted"))

        # Backend別カウント
        backend_counts = {}
        for d in decisions:
            backend = d.get("selected_backend", "unknown")
            backend_counts[backend] = backend_counts.get(backend, 0) + 1

        return {
            "total": total,
            "success_count": success_count,
            "error_count": error_count,
            "blocked_count": blocked_count,
            "fallback_count": fallback_count,
            "backend_counts": backend_counts,
        }


# グローバルインスタンス
_routing_decision_logger: Optional[RoutingDecisionLogger] = None


def get_routing_decision_logger() -> RoutingDecisionLogger:
    """
    RoutingDecisionLogger のグローバルインスタンスを取得

    Returns:
        RoutingDecisionLogger
    """
    global _routing_decision_logger
    if _routing_decision_logger is None:
        _routing_decision_logger = RoutingDecisionLogger()
    return _routing_decision_logger
