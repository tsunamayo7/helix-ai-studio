"""
Policy Checker - Phase 2.6

RiskGate/MCP承認との連動チェック
Routerが選んでも"承認不足なら止まる"を徹底
"""

import logging
from typing import Optional, Dict, Any, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PolicyCheckResult:
    """ポリシーチェック結果"""
    allowed: bool
    reason: Optional[str] = None
    missing_scopes: Optional[list] = None
    blocked_by: Optional[str] = None  # "risk_gate" | "mcp_policy" | None


class PolicyChecker:
    """
    ポリシーチェッカー

    ルーティング時に承認状態をチェックし、
    実行可否を判定する
    """

    # タスク種別と必要なスコープのマッピング
    TASK_SCOPE_REQUIREMENTS = {
        "IMPLEMENT": ["FS_WRITE"],
        "REVIEW": ["FS_READ", "GIT_READ"],
        "VERIFY": ["FS_READ"],
        "RESEARCH": ["NETWORK"],
        "PLAN": [],
        "CHAT": [],
    }

    # Backend別の追加要件
    BACKEND_REQUIREMENTS = {
        "gemini-3-pro": ["NETWORK"],
        "gemini-3-flash": ["NETWORK"],
        # Claude/Localはネットワーク不要
    }

    def __init__(self, approval_state: Optional[Dict[str, bool]] = None):
        """
        Args:
            approval_state: 現在の承認状態 {scope: bool}
        """
        self.approval_state = approval_state or {}

    def update_approval_state(self, approval_state: Dict[str, bool]):
        """承認状態を更新"""
        self.approval_state = approval_state
        logger.debug(f"[PolicyChecker] Approval state updated: {approval_state}")

    def check_task_execution(
        self,
        task_type: str,
        backend: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyCheckResult:
        """
        タスク実行のポリシーチェック

        Args:
            task_type: タスク種別
            backend: 選択されたBackend
            context: 追加コンテキスト

        Returns:
            PolicyCheckResult
        """
        missing_scopes = []

        # 1. タスク種別の要件をチェック
        task_requirements = self.TASK_SCOPE_REQUIREMENTS.get(task_type, [])
        for scope in task_requirements:
            if not self.approval_state.get(scope, False):
                missing_scopes.append(scope)

        # 2. Backend固有の要件をチェック
        backend_requirements = self.BACKEND_REQUIREMENTS.get(backend, [])
        for scope in backend_requirements:
            if not self.approval_state.get(scope, False) and scope not in missing_scopes:
                missing_scopes.append(scope)

        # 3. コンテキストベースの追加チェック
        if context:
            # 大量ファイル変更
            file_count = context.get("file_count", 0)
            if file_count > 5 and not self.approval_state.get("BULK_EDIT", False):
                if "BULK_EDIT" not in missing_scopes:
                    missing_scopes.append("BULK_EDIT")

            # プロジェクト外パス
            if context.get("outside_project", False):
                if not self.approval_state.get("OUTSIDE_PROJECT", False):
                    if "OUTSIDE_PROJECT" not in missing_scopes:
                        missing_scopes.append("OUTSIDE_PROJECT")

            # Git書き込み
            if context.get("git_write", False):
                if not self.approval_state.get("GIT_WRITE", False):
                    if "GIT_WRITE" not in missing_scopes:
                        missing_scopes.append("GIT_WRITE")

        if missing_scopes:
            reason = self._format_missing_scopes_reason(missing_scopes)
            logger.warning(
                f"[PolicyChecker] Blocked: task={task_type}, backend={backend}, "
                f"missing_scopes={missing_scopes}"
            )
            return PolicyCheckResult(
                allowed=False,
                reason=reason,
                missing_scopes=missing_scopes,
                blocked_by="risk_gate",
            )

        logger.info(f"[PolicyChecker] Allowed: task={task_type}, backend={backend}")
        return PolicyCheckResult(allowed=True)

    def _format_missing_scopes_reason(self, missing_scopes: list) -> str:
        """不足スコープの理由文を生成"""
        scope_names = {
            "FS_READ": "ファイル読み取り",
            "FS_WRITE": "ファイル書き込み",
            "FS_DELETE": "ファイル削除",
            "GIT_READ": "Git読み取り",
            "GIT_WRITE": "Git書き込み",
            "NETWORK": "ネットワークアクセス",
            "BULK_EDIT": "大量編集",
            "OUTSIDE_PROJECT": "プロジェクト外アクセス",
        }

        readable_scopes = [scope_names.get(s, s) for s in missing_scopes]

        if len(readable_scopes) == 1:
            return f"{readable_scopes[0]} not approved"
        else:
            return f"{', '.join(readable_scopes)} not approved"

    def get_approval_snapshot(self) -> Dict[str, bool]:
        """現在の承認状態のスナップショットを取得"""
        return dict(self.approval_state)

    def check_mcp_tool_execution(
        self,
        tool_name: str,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> PolicyCheckResult:
        """
        MCPツール実行のポリシーチェック

        Args:
            tool_name: ツール名
            tool_args: ツール引数

        Returns:
            PolicyCheckResult
        """
        # ツール名から必要なスコープを推定
        required_scopes = self._infer_tool_scopes(tool_name, tool_args)

        missing_scopes = []
        for scope in required_scopes:
            if not self.approval_state.get(scope, False):
                missing_scopes.append(scope)

        if missing_scopes:
            reason = self._format_missing_scopes_reason(missing_scopes)
            logger.warning(
                f"[PolicyChecker] MCP blocked: tool={tool_name}, "
                f"missing_scopes={missing_scopes}"
            )
            return PolicyCheckResult(
                allowed=False,
                reason=reason,
                missing_scopes=missing_scopes,
                blocked_by="mcp_policy",
            )

        return PolicyCheckResult(allowed=True)

    def _infer_tool_scopes(
        self,
        tool_name: str,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> list:
        """ツール名から必要なスコープを推定"""
        scopes = []

        tool_lower = tool_name.lower()

        # ファイル操作
        if any(w in tool_lower for w in ["read_file", "list_directory", "get_file"]):
            scopes.append("FS_READ")
        if any(w in tool_lower for w in ["write_file", "create_file", "edit_file"]):
            scopes.append("FS_WRITE")
        if any(w in tool_lower for w in ["delete_file", "remove_file"]):
            scopes.append("FS_DELETE")

        # Git操作
        if any(w in tool_lower for w in ["git_status", "git_diff", "git_log"]):
            scopes.append("GIT_READ")
        if any(w in tool_lower for w in ["git_commit", "git_push", "git_checkout", "git_branch"]):
            scopes.append("GIT_WRITE")

        # ネットワーク
        if any(w in tool_lower for w in ["search", "fetch", "http", "web", "api"]):
            scopes.append("NETWORK")

        return scopes


# グローバルインスタンス
_policy_checker: Optional[PolicyChecker] = None


def get_policy_checker() -> PolicyChecker:
    """PolicyCheckerのグローバルインスタンスを取得"""
    global _policy_checker
    if _policy_checker is None:
        _policy_checker = PolicyChecker()
    return _policy_checker
