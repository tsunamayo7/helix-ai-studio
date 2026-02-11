"""
Approvals Store - 承認内容の永続化と監査ログ
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict

from .risk_gate import ApprovalState, ApprovalScope


class ApprovalsStore:
    """
    承認内容の保存・読み込み・監査ログ記録を管理

    - セッション単位の承認状態を session_state.json に保存
    - 承認変更の監査ログを logs/risk_audit.log に JSONL 形式で追記
    """

    def __init__(self, data_dir: str = "data", logs_dir: str = "logs"):
        """
        初期化

        Args:
            data_dir: データディレクトリパス
            logs_dir: ログディレクトリパス
        """
        self.data_dir = Path(data_dir)
        self.logs_dir = Path(logs_dir)
        self.audit_log_path = self.logs_dir / "risk_audit.log"
        self.logger = self._setup_logger()

        # ディレクトリを作成
        self._ensure_directories()

        # 現在の承認状態
        self.current_approval_state: Optional[ApprovalState] = None

    def _setup_logger(self) -> logging.Logger:
        """ロガーをセットアップ"""
        logger = logging.getLogger("ApprovalsStore")
        logger.setLevel(logging.INFO)
        return logger

    def _ensure_directories(self):
        """必要なディレクトリを作成"""
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.logger.info(f"Ensured directories: {self.data_dir}, {self.logs_dir}")

    def save_approval_state(
        self,
        approval_state: ApprovalState,
        session_id: str = "",
        reason: str = ""
    ) -> bool:
        """
        承認状態を保存（session_state.json内のapprovalsセクション）

        Args:
            approval_state: 承認状態
            session_id: セッションID（任意）
            reason: 理由（任意）

        Returns:
            成功した場合True
        """
        try:
            # session_state.jsonを読み込み
            session_state_path = self.data_dir / "session_state.json"

            if session_state_path.exists():
                with open(session_state_path, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
            else:
                session_data = {}

            # approvalsセクションを更新
            session_data["approvals"] = approval_state.to_dict()
            session_data["approvals"]["session_id"] = session_id
            session_data["approvals"]["last_updated"] = datetime.now().isoformat()

            # 保存
            with open(session_state_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            self.current_approval_state = approval_state
            self.logger.info(f"Approval state saved. Session: {session_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save approval state: {e}")
            return False

    def load_approval_state(self, session_id: str = "") -> ApprovalState:
        """
        承認状態を読み込み

        Args:
            session_id: セッションID（任意）

        Returns:
            ApprovalState インスタンス（存在しない場合は新規作成）
        """
        try:
            session_state_path = self.data_dir / "session_state.json"

            if not session_state_path.exists():
                self.logger.info("Session state file not found. Creating new approval state.")
                self.current_approval_state = ApprovalState()
                return self.current_approval_state

            with open(session_state_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            approvals_data = session_data.get("approvals", {})
            if not approvals_data:
                self.logger.info("No approvals section found. Creating new approval state.")
                self.current_approval_state = ApprovalState()
                return self.current_approval_state

            self.current_approval_state = ApprovalState.from_dict(approvals_data)
            self.logger.info(
                f"Approval state loaded. "
                f"Approved scopes: {len(self.current_approval_state.get_approved_scopes())}"
            )
            return self.current_approval_state

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode session state JSON: {e}")
            self.current_approval_state = ApprovalState()
            return self.current_approval_state

        except Exception as e:
            self.logger.error(f"Failed to load approval state: {e}")
            self.current_approval_state = ApprovalState()
            return self.current_approval_state

    def log_approval_event(
        self,
        event_type: str,
        scopes: list,
        session_id: str = "",
        phase: str = "",
        reason: str = "",
        user_action: str = ""
    ):
        """
        承認イベントを監査ログに記録（JSONL形式）

        Args:
            event_type: イベントタイプ（"approve", "revoke", "check_failed"等）
            scopes: 対象スコープのリスト
            session_id: セッションID
            phase: ワークフロー工程
            reason: 理由
            user_action: ユーザーアクション
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "session_id": session_id,
                "phase": phase,
                "scopes": [scope.value if isinstance(scope, ApprovalScope) else str(scope) for scope in scopes],
                "user_action": user_action,
                "reason": reason,
            }

            # JSONL形式で追記（1行1JSON）
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            self.logger.info(f"Audit log written: {event_type} - {scopes}")

        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")

    def approve_scopes(
        self,
        scopes: list,
        session_id: str = "",
        phase: str = "",
        reason: str = ""
    ) -> bool:
        """
        複数のスコープを一括承認

        Args:
            scopes: 承認するスコープのリスト
            session_id: セッションID
            phase: 現在の工程
            reason: 承認理由

        Returns:
            成功した場合True
        """
        if self.current_approval_state is None:
            self.current_approval_state = self.load_approval_state(session_id)

        # 各スコープを承認
        for scope in scopes:
            if isinstance(scope, ApprovalScope):
                self.current_approval_state.approve_scope(scope, reason)

        # 保存
        success = self.save_approval_state(
            self.current_approval_state,
            session_id=session_id,
            reason=reason
        )

        if success:
            # 監査ログに記録
            self.log_approval_event(
                event_type="approve",
                scopes=scopes,
                session_id=session_id,
                phase=phase,
                reason=reason,
                user_action="user_approved"
            )

        return success

    def revoke_scopes(
        self,
        scopes: list,
        session_id: str = "",
        phase: str = "",
        reason: str = ""
    ) -> bool:
        """
        複数のスコープの承認を取り消し

        Args:
            scopes: 取り消すスコープのリスト
            session_id: セッションID
            phase: 現在の工程
            reason: 取り消し理由

        Returns:
            成功した場合True
        """
        if self.current_approval_state is None:
            self.current_approval_state = self.load_approval_state(session_id)

        # 各スコープの承認を取り消し
        for scope in scopes:
            if isinstance(scope, ApprovalScope):
                self.current_approval_state.revoke_scope(scope)

        # 保存
        success = self.save_approval_state(
            self.current_approval_state,
            session_id=session_id,
            reason=reason
        )

        if success:
            # 監査ログに記録
            self.log_approval_event(
                event_type="revoke",
                scopes=scopes,
                session_id=session_id,
                phase=phase,
                reason=reason,
                user_action="user_revoked"
            )

        return success

    def log_check_failed(
        self,
        operation: str,
        missing_scopes: list,
        session_id: str = "",
        phase: str = ""
    ):
        """
        チェック失敗（承認不足）を監査ログに記録

        Args:
            operation: 実行しようとした操作
            missing_scopes: 不足しているスコープのリスト
            session_id: セッションID
            phase: 現在の工程
        """
        self.log_approval_event(
            event_type="check_failed",
            scopes=missing_scopes,
            session_id=session_id,
            phase=phase,
            reason=f"Operation blocked: {operation}",
            user_action="operation_rejected"
        )

    def get_current_state(self) -> ApprovalState:
        """現在の承認状態を取得"""
        if self.current_approval_state is None:
            self.current_approval_state = self.load_approval_state()
        return self.current_approval_state

    def reset_approvals(self, session_id: str = "", reason: str = "") -> bool:
        """
        全ての承認をリセット

        Args:
            session_id: セッションID
            reason: リセット理由

        Returns:
            成功した場合True
        """
        self.current_approval_state = ApprovalState()

        success = self.save_approval_state(
            self.current_approval_state,
            session_id=session_id,
            reason=reason
        )

        if success:
            # 監査ログに記録
            self.log_approval_event(
                event_type="reset",
                scopes=ApprovalScope.all_scopes(),
                session_id=session_id,
                phase="",
                reason=reason,
                user_action="approvals_reset"
            )

        return success


# グローバルインスタンス
_global_approvals_store: Optional[ApprovalsStore] = None


def get_approvals_store() -> ApprovalsStore:
    """
    グローバルなApprovalsStoreインスタンスを取得

    Returns:
        ApprovalsStore インスタンス
    """
    global _global_approvals_store
    if _global_approvals_store is None:
        _global_approvals_store = ApprovalsStore()
    return _global_approvals_store
