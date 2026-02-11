"""
MCP Tool Policy - MCPツール単位のポリシー定義
Phase 1.3: MCPツールごとにrequired_scopesと制約を定義
"""
import json
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .risk_gate import ApprovalScope


@dataclass
class MCPToolPolicy:
    """
    MCPツール単位のポリシー定義

    Attributes:
        tool_name: ツール名（例: filesystem.read, git.commit）
        required_scopes: 必要な承認スコープリスト
        allowed_paths: 許可されたパスのリスト（filesystem系のみ、空なら制限なし）
        allow_outside_project: プロジェクト外アクセスを許可するか
        max_files_touched: 最大変更ファイル数（Noneなら制限なし）
        notes: UI表示用の説明
    """
    tool_name: str
    required_scopes: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    allow_outside_project: bool = False
    max_files_touched: Optional[int] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPToolPolicy':
        """辞書から復元"""
        return cls(**data)

    def check_compliance(
        self,
        approved_scopes: Set[ApprovalScope],
        file_paths: Optional[List[str]] = None,
        is_outside_project: bool = False
    ) -> tuple[bool, str]:
        """
        ポリシー遵守をチェック

        Args:
            approved_scopes: 承認済みスコープセット
            file_paths: 操作対象ファイルパス（filesystem系のみ）
            is_outside_project: プロジェクト外アクセスか

        Returns:
            (遵守しているか, エラーメッセージ)
        """
        # required_scopesチェック
        required = {ApprovalScope(scope) for scope in self.required_scopes}
        missing = required - approved_scopes

        if missing:
            scope_names = [ApprovalScope.get_display_name(s) for s in missing]
            return False, f"必要な承認が不足: {', '.join(scope_names)}"

        # プロジェクト外アクセスチェック
        if is_outside_project and not self.allow_outside_project:
            return False, "プロジェクト外へのアクセスは許可されていません"

        # ファイル数制限チェック
        if file_paths and self.max_files_touched is not None:
            if len(file_paths) > self.max_files_touched:
                return False, f"ファイル数制限超過: {len(file_paths)} > {self.max_files_touched}"

        # 許可パスチェック（allowed_pathsが設定されている場合のみ）
        if file_paths and self.allowed_paths:
            for path in file_paths:
                path_obj = Path(path)
                allowed = False
                for allowed_path in self.allowed_paths:
                    allowed_path_obj = Path(allowed_path)
                    try:
                        path_obj.relative_to(allowed_path_obj)
                        allowed = True
                        break
                    except ValueError:
                        continue

                if not allowed:
                    return False, f"許可されていないパスへのアクセス: {path}"

        return True, ""


class MCPPolicyManager:
    """MCPツールポリシーを管理するクラス"""

    def __init__(self, policy_file: str = "data/mcp_policies.json"):
        """
        初期化

        Args:
            policy_file: ポリシー定義ファイルのパス
        """
        self.policy_file = Path(policy_file)
        self.policies: Dict[str, MCPToolPolicy] = {}
        self._ensure_directory()
        self._load_policies()

    def _ensure_directory(self):
        """ディレクトリを確保"""
        self.policy_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_policies(self):
        """ポリシーを読み込み"""
        if not self.policy_file.exists():
            # 初期ポリシーを作成
            self._create_default_policies()
            self._save_policies()
        else:
            try:
                with open(self.policy_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.policies = {
                    tool_name: MCPToolPolicy.from_dict(policy_data)
                    for tool_name, policy_data in data.items()
                }
            except Exception as e:
                print(f"Failed to load MCP policies: {e}")
                self._create_default_policies()

    def _create_default_policies(self):
        """デフォルトポリシーを作成（Phase 1.3初期セット）"""
        self.policies = {
            # ============= Filesystem系 =============
            "filesystem.read": MCPToolPolicy(
                tool_name="filesystem.read",
                required_scopes=[ApprovalScope.FS_READ.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="ファイルの読み取り操作。プロジェクト内に制限。"
            ),
            "filesystem.write": MCPToolPolicy(
                tool_name="filesystem.write",
                required_scopes=[ApprovalScope.FS_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=5,
                notes="ファイルへの書き込み操作。最大5ファイルまで。"
            ),
            "filesystem.delete": MCPToolPolicy(
                tool_name="filesystem.delete",
                required_scopes=[ApprovalScope.FS_DELETE.value, ApprovalScope.FS_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=3,
                notes="ファイルの削除操作。最大3ファイルまで。"
            ),
            "filesystem.list": MCPToolPolicy(
                tool_name="filesystem.list",
                required_scopes=[ApprovalScope.FS_READ.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="ディレクトリ一覧表示。"
            ),
            "filesystem.move": MCPToolPolicy(
                tool_name="filesystem.move",
                required_scopes=[ApprovalScope.FS_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=5,
                notes="ファイル移動操作。"
            ),

            # ============= Git系 =============
            "git.read_status": MCPToolPolicy(
                tool_name="git.read_status",
                required_scopes=[ApprovalScope.GIT_READ.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Gitステータス確認。"
            ),
            "git.diff": MCPToolPolicy(
                tool_name="git.diff",
                required_scopes=[ApprovalScope.GIT_READ.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Git差分表示。"
            ),
            "git.log": MCPToolPolicy(
                tool_name="git.log",
                required_scopes=[ApprovalScope.GIT_READ.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Gitログ確認。"
            ),
            "git.commit": MCPToolPolicy(
                tool_name="git.commit",
                required_scopes=[ApprovalScope.GIT_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Gitコミット作成。"
            ),
            "git.push": MCPToolPolicy(
                tool_name="git.push",
                required_scopes=[ApprovalScope.GIT_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Gitプッシュ実行。"
            ),
            "git.checkout": MCPToolPolicy(
                tool_name="git.checkout",
                required_scopes=[ApprovalScope.GIT_WRITE.value],
                allowed_paths=[],
                allow_outside_project=False,
                max_files_touched=None,
                notes="Gitチェックアウト操作。"
            ),

            # ============= Network系 =============
            "browser.search": MCPToolPolicy(
                tool_name="browser.search",
                required_scopes=[ApprovalScope.NETWORK.value],
                allowed_paths=[],
                allow_outside_project=True,
                max_files_touched=None,
                notes="Web検索実行。"
            ),
            "brave.search": MCPToolPolicy(
                tool_name="brave.search",
                required_scopes=[ApprovalScope.NETWORK.value],
                allowed_paths=[],
                allow_outside_project=True,
                max_files_touched=None,
                notes="Brave検索実行。"
            ),
            "fetch.url": MCPToolPolicy(
                tool_name="fetch.url",
                required_scopes=[ApprovalScope.NETWORK.value],
                allowed_paths=[],
                allow_outside_project=True,
                max_files_touched=None,
                notes="URL取得操作。"
            ),

            # ============= その他 =============
            "slack.post": MCPToolPolicy(
                tool_name="slack.post",
                required_scopes=[ApprovalScope.NETWORK.value],
                allowed_paths=[],
                allow_outside_project=True,
                max_files_touched=None,
                notes="Slackメッセージ投稿。"
            ),
            "github.create_issue": MCPToolPolicy(
                tool_name="github.create_issue",
                required_scopes=[ApprovalScope.NETWORK.value],
                allowed_paths=[],
                allow_outside_project=True,
                max_files_touched=None,
                notes="GitHub Issue作成。"
            ),
        }

    def _save_policies(self):
        """ポリシーを保存"""
        try:
            data = {
                tool_name: policy.to_dict()
                for tool_name, policy in self.policies.items()
            }

            with open(self.policy_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Failed to save MCP policies: {e}")

    def get_policy(self, tool_name: str) -> Optional[MCPToolPolicy]:
        """
        ツール名からポリシーを取得

        Args:
            tool_name: ツール名

        Returns:
            MCPToolPolicy（存在しない場合None）
        """
        return self.policies.get(tool_name)

    def get_all_policies(self) -> Dict[str, MCPToolPolicy]:
        """全てのポリシーを取得"""
        return self.policies.copy()

    def add_policy(self, policy: MCPToolPolicy):
        """ポリシーを追加"""
        self.policies[policy.tool_name] = policy
        self._save_policies()

    def update_policy(self, tool_name: str, policy: MCPToolPolicy):
        """ポリシーを更新"""
        if tool_name in self.policies:
            self.policies[tool_name] = policy
            self._save_policies()

    def delete_policy(self, tool_name: str):
        """ポリシーを削除"""
        if tool_name in self.policies:
            del self.policies[tool_name]
            self._save_policies()

    def check_tool_execution(
        self,
        tool_name: str,
        approved_scopes: Set[ApprovalScope],
        file_paths: Optional[List[str]] = None,
        is_outside_project: bool = False
    ) -> tuple[bool, str]:
        """
        ツール実行可否をチェック

        Args:
            tool_name: ツール名
            approved_scopes: 承認済みスコープセット
            file_paths: 操作対象ファイルパス
            is_outside_project: プロジェクト外アクセスか

        Returns:
            (実行可能か, エラーメッセージ)
        """
        policy = self.get_policy(tool_name)

        if policy is None:
            # ポリシーが未定義の場合は慎重に拒否
            return False, f"ツール '{tool_name}' のポリシーが未定義です"

        return policy.check_compliance(approved_scopes, file_paths, is_outside_project)


# グローバルインスタンス
_global_policy_manager: Optional[MCPPolicyManager] = None


def get_mcp_policy_manager() -> MCPPolicyManager:
    """
    グローバルなMCPPolicyManagerインスタンスを取得

    Returns:
        MCPPolicyManager インスタンス
    """
    global _global_policy_manager
    if _global_policy_manager is None:
        _global_policy_manager = MCPPolicyManager()
    return _global_policy_manager
