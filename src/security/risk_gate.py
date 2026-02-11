"""
Risk Gate - S3承認ゲート管理
ApprovalScopeの定義と判定ロジック
"""
from enum import Enum
from typing import Set, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging


class ApprovalScope(Enum):
    """承認スコープ定義（8項目）"""
    FS_READ = "FS_READ"                      # ファイル読み取り
    FS_WRITE = "FS_WRITE"                    # ファイル書き込み
    FS_DELETE = "FS_DELETE"                  # ファイル削除
    GIT_READ = "GIT_READ"                    # Git読み取り（status/diff/log等）
    GIT_WRITE = "GIT_WRITE"                  # Git書き込み（commit/checkout/branch等）
    NETWORK = "NETWORK"                      # 外部アクセス/検索
    BULK_EDIT = "BULK_EDIT"                  # 大量置換・多数ファイル変更
    OUTSIDE_PROJECT = "OUTSIDE_PROJECT"      # プロジェクト外パスアクセス

    @classmethod
    def all_scopes(cls) -> list:
        """全てのスコープをリストで返す"""
        return [scope for scope in cls]

    @classmethod
    def get_display_name(cls, scope: 'ApprovalScope') -> str:
        """スコープの表示名を返す"""
        display_names = {
            cls.FS_READ: "ファイル読み取り",
            cls.FS_WRITE: "ファイル書き込み",
            cls.FS_DELETE: "ファイル削除",
            cls.GIT_READ: "Git読み取り (status/diff/log)",
            cls.GIT_WRITE: "Git書き込み (commit/checkout/branch)",
            cls.NETWORK: "外部ネットワークアクセス",
            cls.BULK_EDIT: "大量編集（多数ファイル変更）",
            cls.OUTSIDE_PROJECT: "プロジェクト外パスアクセス",
        }
        return display_names.get(scope, scope.value)

    @classmethod
    def get_description(cls, scope: 'ApprovalScope') -> str:
        """スコープの説明を返す"""
        descriptions = {
            cls.FS_READ: "プロジェクト内のファイルを読み取る操作を許可します。",
            cls.FS_WRITE: "プロジェクト内のファイルへの書き込みを許可します。",
            cls.FS_DELETE: "ファイルの削除を許可します。慎重に使用してください。",
            cls.GIT_READ: "Gitリポジトリの状態確認、差分表示、ログ閲覧を許可します。",
            cls.GIT_WRITE: "コミット、チェックアウト、ブランチ作成などのGit操作を許可します。",
            cls.NETWORK: "外部APIへのアクセスや検索機能の使用を許可します。",
            cls.BULK_EDIT: "多数のファイルに対する一括変更を許可します。影響範囲が大きいため注意が必要です。",
            cls.OUTSIDE_PROJECT: "プロジェクトディレクトリ外へのアクセスを許可します。セキュリティリスクがあります。",
        }
        return descriptions.get(scope, "")


@dataclass
class ApprovalState:
    """承認状態を管理するデータクラス"""
    # 承認されたスコープ（Enumの値をキーとする）
    approved_scopes: Dict[str, bool] = field(default_factory=dict)
    # 承認日時
    approved_at: str = ""
    # セッションID（任意）
    session_id: str = ""
    # 理由（任意）
    reason: str = ""

    def __post_init__(self):
        """初期化後処理：全スコープをFalseで初期化"""
        if not self.approved_scopes:
            self.approved_scopes = {
                scope.value: False for scope in ApprovalScope
            }

    def approve_scope(self, scope: ApprovalScope, reason: str = ""):
        """スコープを承認"""
        self.approved_scopes[scope.value] = True
        self.approved_at = datetime.now().isoformat()
        if reason:
            self.reason = reason

    def revoke_scope(self, scope: ApprovalScope):
        """スコープの承認を取り消し"""
        self.approved_scopes[scope.value] = False

    def is_approved(self, scope: ApprovalScope) -> bool:
        """スコープが承認されているか確認"""
        return self.approved_scopes.get(scope.value, False)

    def has_all_scopes(self, required_scopes: Set[ApprovalScope]) -> bool:
        """必要な全てのスコープが承認されているか確認"""
        return all(self.is_approved(scope) for scope in required_scopes)

    def get_approved_scopes(self) -> list:
        """承認されているスコープのリストを返す"""
        return [
            ApprovalScope(key)
            for key, value in self.approved_scopes.items()
            if value
        ]

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "approved_scopes": self.approved_scopes,
            "approved_at": self.approved_at,
            "session_id": self.session_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalState':
        """辞書から復元"""
        return cls(
            approved_scopes=data.get("approved_scopes", {}),
            approved_at=data.get("approved_at", ""),
            session_id=data.get("session_id", ""),
            reason=data.get("reason", ""),
        )


class RiskGate:
    """
    Risk Gate判定クラス

    操作の実行可否を判定し、必要なスコープをチェックする
    """

    def __init__(self, approval_state: ApprovalState):
        """
        初期化

        Args:
            approval_state: 承認状態
        """
        self.approval_state = approval_state
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """ロガーをセットアップ"""
        logger = logging.getLogger("RiskGate")
        logger.setLevel(logging.INFO)
        return logger

    def check_operation(
        self,
        operation_type: str,
        required_scopes: Set[ApprovalScope],
        context: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        """
        操作の実行可否を判定

        Args:
            operation_type: 操作タイプ（説明用）
            required_scopes: 必要なスコープセット
            context: コンテキスト情報（任意）

        Returns:
            (実行可能か, 理由メッセージ)
        """
        if not required_scopes:
            return True, ""

        # 承認されていないスコープを検出
        missing_scopes = [
            scope for scope in required_scopes
            if not self.approval_state.is_approved(scope)
        ]

        if missing_scopes:
            scope_names = [ApprovalScope.get_display_name(s) for s in missing_scopes]
            message = (
                f"操作「{operation_type}」には以下の承認が必要です：\n"
                + "\n".join(f"  - {name}" for name in scope_names)
                + "\n\nS3 Risk Gateで承認を行ってください。"
            )
            self.logger.warning(f"Operation blocked: {operation_type}. Missing scopes: {scope_names}")
            return False, message

        self.logger.info(f"Operation allowed: {operation_type}")
        return True, ""

    def check_file_write(self, file_path: str = "") -> Tuple[bool, str]:
        """ファイル書き込み操作のチェック"""
        return self.check_operation(
            "ファイル書き込み",
            {ApprovalScope.FS_WRITE},
            {"file_path": file_path}
        )

    def check_file_delete(self, file_path: str = "") -> Tuple[bool, str]:
        """ファイル削除操作のチェック"""
        return self.check_operation(
            "ファイル削除",
            {ApprovalScope.FS_DELETE, ApprovalScope.FS_WRITE},
            {"file_path": file_path}
        )

    def check_bulk_edit(self, file_count: int = 0) -> Tuple[bool, str]:
        """大量編集操作のチェック"""
        return self.check_operation(
            f"大量編集 ({file_count}ファイル)",
            {ApprovalScope.BULK_EDIT, ApprovalScope.FS_WRITE},
            {"file_count": file_count}
        )

    def check_git_write(self, operation: str = "") -> Tuple[bool, str]:
        """Git書き込み操作のチェック"""
        return self.check_operation(
            f"Git操作 ({operation})",
            {ApprovalScope.GIT_WRITE},
            {"git_operation": operation}
        )

    def check_network_access(self, url: str = "") -> Tuple[bool, str]:
        """ネットワークアクセスのチェック"""
        return self.check_operation(
            "外部ネットワークアクセス",
            {ApprovalScope.NETWORK},
            {"url": url}
        )

    def check_outside_project(self, path: str = "") -> Tuple[bool, str]:
        """プロジェクト外アクセスのチェック"""
        return self.check_operation(
            "プロジェクト外パスアクセス",
            {ApprovalScope.OUTSIDE_PROJECT, ApprovalScope.FS_WRITE},
            {"path": path}
        )
