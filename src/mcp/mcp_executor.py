"""
MCP Executor - MCP実行ガードと監査
Phase 1.3: MCPツール実行直前にポリシーと承認をチェック
"""
import json
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path

from ..security.mcp_policy import get_mcp_policy_manager, MCPToolPolicy
from ..security.risk_gate import ApprovalScope, ApprovalState
from ..security.approvals_store import get_approvals_store


class MCPAuditLogger:
    """MCP監査ロガー"""

    def __init__(self, log_file: str = "logs/mcp_audit.log"):
        """
        初期化

        Args:
            log_file: 監査ログファイルパス
        """
        self.log_file = Path(log_file)
        self._ensure_directory()
        self.logger = self._setup_logger()

    def _ensure_directory(self):
        """ディレクトリを確保"""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _setup_logger(self) -> logging.Logger:
        """ロガーをセットアップ"""
        logger = logging.getLogger("MCPAudit")
        logger.setLevel(logging.INFO)
        return logger

    def log_execution(
        self,
        tool_name: str,
        action: str,
        project_id: str = "",
        reason: str = "",
        scopes_snapshot: Optional[Dict[str, bool]] = None,
        files_touched: Optional[List[str]] = None,
        **kwargs
    ):
        """
        MCP実行イベントを監査ログに記録（JSONL形式）

        Args:
            tool_name: ツール名
            action: アクション（executed / blocked）
            project_id: プロジェクトID
            reason: 理由（blockedの場合）
            scopes_snapshot: 実行時の承認状態スナップショット
            files_touched: 操作対象ファイル
            **kwargs: その他の追加情報
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "action": action,
                "project_id": project_id,
                "reason": reason,
                "scopes_snapshot": scopes_snapshot or {},
                "files_touched": files_touched or [],
                **kwargs
            }

            # JSONL形式で追記（1行1JSON）
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            self.logger.info(f"MCP Audit: {action} - {tool_name}")

        except Exception as e:
            self.logger.error(f"Failed to write MCP audit log: {e}")

    def read_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        最近の監査ログを読み込み

        Args:
            limit: 最大読み込み件数

        Returns:
            監査ログエントリのリスト
        """
        if not self.log_file.exists():
            return []

        try:
            logs = []
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 最後からlimit件を取得
            for line in lines[-limit:]:
                try:
                    log_entry = json.loads(line.strip())
                    logs.append(log_entry)
                except json.JSONDecodeError:
                    continue

            # 最新が先頭になるように逆順
            logs.reverse()
            return logs

        except Exception as e:
            self.logger.error(f"Failed to read MCP audit log: {e}")
            return []


class MCPExecutor:
    """
    MCP実行管理クラス

    実行直前にポリシーと承認をチェックし、監査ログに記録する
    """

    def __init__(
        self,
        approval_state: ApprovalState,
        project_id: str = "",
        project_root: str = "."
    ):
        """
        初期化

        Args:
            approval_state: 現在の承認状態
            project_id: プロジェクトID
            project_root: プロジェクトルートパス
        """
        self.approval_state = approval_state
        self.project_id = project_id
        self.project_root = Path(project_root).resolve()

        self.policy_manager = get_mcp_policy_manager()
        self.audit_logger = MCPAuditLogger()
        self.approvals_store = get_approvals_store()

    def _get_approved_scopes(self) -> Set[ApprovalScope]:
        """現在の承認済みスコープセットを取得"""
        return set(self.approval_state.get_approved_scopes())

    def _is_outside_project(self, file_path: str) -> bool:
        """ファイルパスがプロジェクト外かどうか判定"""
        try:
            path = Path(file_path).resolve()
            path.relative_to(self.project_root)
            return False
        except (ValueError, Exception):
            return True

    def check_execution_permission(
        self,
        tool_name: str,
        file_paths: Optional[List[str]] = None,
        **kwargs
    ) -> tuple[bool, str]:
        """
        MCP実行前の統一チェック（最重要関数）

        Args:
            tool_name: ツール名
            file_paths: 操作対象ファイルパス（filesystem系の場合）
            **kwargs: その他のコンテキスト情報

        Returns:
            (実行可能か, エラーメッセージ)
        """
        # 1. ツールのポリシーを取得
        policy = self.policy_manager.get_policy(tool_name)
        if policy is None:
            reason = f"ツール '{tool_name}' のポリシーが未定義です"
            self._log_blocked(tool_name, reason, file_paths)
            return False, reason

        # 2. 承認済みスコープを取得
        approved_scopes = self._get_approved_scopes()

        # 3. プロジェクト外アクセスチェック
        is_outside_project = False
        if file_paths:
            is_outside_project = any(
                self._is_outside_project(path) for path in file_paths
            )

        # 4. ポリシー遵守チェック
        compliant, error_message = policy.check_compliance(
            approved_scopes,
            file_paths,
            is_outside_project
        )

        if not compliant:
            self._log_blocked(tool_name, error_message, file_paths)
            return False, error_message

        # 5. 実行許可
        self._log_executed(tool_name, file_paths)
        return True, ""

    def _log_executed(self, tool_name: str, file_paths: Optional[List[str]]):
        """実行許可をログに記録"""
        scopes_snapshot = self.approval_state.to_dict()["approved_scopes"]

        self.audit_logger.log_execution(
            tool_name=tool_name,
            action="executed",
            project_id=self.project_id,
            reason="",
            scopes_snapshot=scopes_snapshot,
            files_touched=file_paths or []
        )

    def _log_blocked(self, tool_name: str, reason: str, file_paths: Optional[List[str]]):
        """実行拒否をログに記録"""
        scopes_snapshot = self.approval_state.to_dict()["approved_scopes"]

        self.audit_logger.log_execution(
            tool_name=tool_name,
            action="blocked",
            project_id=self.project_id,
            reason=reason,
            scopes_snapshot=scopes_snapshot,
            files_touched=file_paths or []
        )

        # approvals_storeにも記録（既存の監査システムとの連携）
        missing_scopes = self._extract_missing_scopes(reason)
        if missing_scopes:
            self.approvals_store.log_check_failed(
                operation=f"MCP Tool: {tool_name}",
                missing_scopes=missing_scopes,
                session_id="",
                phase=""
            )

    def _extract_missing_scopes(self, reason: str) -> List[str]:
        """エラーメッセージから不足しているスコープを抽出"""
        # 簡易的な実装（将来改善可能）
        scopes = []
        for scope in ApprovalScope:
            if ApprovalScope.get_display_name(scope) in reason:
                scopes.append(scope)
        return scopes

    # ==========================================
    # 便利メソッド（特定ツールカテゴリ向け）
    # ==========================================

    def execute_filesystem_read(self, file_path: str) -> tuple[bool, str]:
        """ファイル読み取り実行チェック"""
        return self.check_execution_permission(
            tool_name="filesystem.read",
            file_paths=[file_path]
        )

    def execute_filesystem_write(self, file_paths: List[str]) -> tuple[bool, str]:
        """ファイル書き込み実行チェック"""
        return self.check_execution_permission(
            tool_name="filesystem.write",
            file_paths=file_paths
        )

    def execute_filesystem_delete(self, file_paths: List[str]) -> tuple[bool, str]:
        """ファイル削除実行チェック"""
        return self.check_execution_permission(
            tool_name="filesystem.delete",
            file_paths=file_paths
        )

    def execute_git_command(self, command: str) -> tuple[bool, str]:
        """Git操作実行チェック"""
        # コマンドに応じてツール名を判定
        if command in ["status", "diff", "log"]:
            tool_name = f"git.{command}" if command == "log" else f"git.{command}"
            if command == "diff":
                tool_name = "git.diff"
            elif command == "status":
                tool_name = "git.read_status"
            else:
                tool_name = "git.log"
        elif command in ["commit", "push", "checkout"]:
            tool_name = f"git.{command}"
        else:
            tool_name = "git.read_status"  # デフォルトはread扱い

        return self.check_execution_permission(tool_name=tool_name)

    def execute_network_request(self, url: str, tool_type: str = "browser.search") -> tuple[bool, str]:
        """ネットワーク操作実行チェック"""
        return self.check_execution_permission(
            tool_name=tool_type,
            url=url
        )


# グローバルインスタンス（セッション単位で更新）
_global_mcp_executor: Optional[MCPExecutor] = None


def get_mcp_executor(
    approval_state: Optional[ApprovalState] = None,
    project_id: str = "",
    project_root: str = "."
) -> MCPExecutor:
    """
    グローバルなMCPExecutorインスタンスを取得

    Args:
        approval_state: 承認状態（Noneの場合は既存インスタンスを返す）
        project_id: プロジェクトID
        project_root: プロジェクトルートパス

    Returns:
        MCPExecutor インスタンス
    """
    global _global_mcp_executor

    if approval_state is not None:
        # 新しいインスタンスを作成
        _global_mcp_executor = MCPExecutor(approval_state, project_id, project_root)

    if _global_mcp_executor is None:
        # デフォルトのインスタンスを作成（承認なし状態）
        from ..security.risk_gate import ApprovalState
        _global_mcp_executor = MCPExecutor(ApprovalState(), project_id, project_root)

    return _global_mcp_executor


def get_mcp_audit_logger() -> MCPAuditLogger:
    """
    MCPAuditLoggerインスタンスを取得

    Returns:
        MCPAuditLogger インスタンス
    """
    return MCPAuditLogger()
