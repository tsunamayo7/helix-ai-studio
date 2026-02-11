"""
Project Approval Profiles - プロジェクト別デフォルト承認セット
Phase 1.3: プロジェクトごとに安全な承認セットを管理
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .risk_gate import ApprovalScope


@dataclass
class ApprovalProfile:
    """
    承認プロファイル

    Attributes:
        profile_id: プロファイルID
        project_id: プロジェクトID
        name: プロファイル名（例: read-only, normal-dev, risky）
        approved_scopes: 承認スコープの辞書（scope.value: bool）
        description: 説明
    """
    profile_id: str
    project_id: str
    name: str
    approved_scopes: Dict[str, bool] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        """初期化後処理：全スコープを初期化"""
        if not self.approved_scopes:
            self.approved_scopes = {
                scope.value: False for scope in ApprovalScope
            }

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalProfile':
        """辞書から復元"""
        return cls(**data)

    def get_approved_scopes_list(self) -> List[ApprovalScope]:
        """承認されているスコープのリストを返す"""
        return [
            ApprovalScope(key)
            for key, value in self.approved_scopes.items()
            if value
        ]


class ProjectApprovalProfilesManager:
    """プロジェクト別承認プロファイルを管理するクラス"""

    def __init__(self, profiles_file: str = "data/project_profiles.json"):
        """
        初期化

        Args:
            profiles_file: プロファイル定義ファイルのパス
        """
        self.profiles_file = Path(profiles_file)
        self.profiles: List[ApprovalProfile] = []
        self._ensure_directory()
        self._load_profiles()

    def _ensure_directory(self):
        """ディレクトリを確保"""
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self):
        """プロファイルを読み込み"""
        if not self.profiles_file.exists():
            # デフォルトプロファイルを作成
            self._create_default_profiles()
            self._save_profiles()
        else:
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.profiles = [
                    ApprovalProfile.from_dict(profile_data)
                    for profile_data in data
                ]
            except Exception as e:
                print(f"Failed to load approval profiles: {e}")
                self._create_default_profiles()

    def _create_default_profiles(self):
        """デフォルトプロファイルを作成"""
        # グローバルデフォルトプロファイル（プロジェクト非依存）
        self.profiles = [
            # Read-Only プロファイル（安全）
            ApprovalProfile(
                profile_id=str(uuid.uuid4()),
                project_id="__global__",
                name="read-only",
                approved_scopes={
                    ApprovalScope.FS_READ.value: True,
                    ApprovalScope.FS_WRITE.value: False,
                    ApprovalScope.FS_DELETE.value: False,
                    ApprovalScope.GIT_READ.value: True,
                    ApprovalScope.GIT_WRITE.value: False,
                    ApprovalScope.NETWORK.value: True,
                    ApprovalScope.BULK_EDIT.value: False,
                    ApprovalScope.OUTSIDE_PROJECT.value: False,
                },
                description="読み取り専用モード。ファイルの読み取りとGit確認のみ許可。"
            ),

            # Normal Development プロファイル（標準）
            ApprovalProfile(
                profile_id=str(uuid.uuid4()),
                project_id="__global__",
                name="normal-dev",
                approved_scopes={
                    ApprovalScope.FS_READ.value: True,
                    ApprovalScope.FS_WRITE.value: True,
                    ApprovalScope.FS_DELETE.value: False,
                    ApprovalScope.GIT_READ.value: True,
                    ApprovalScope.GIT_WRITE.value: True,
                    ApprovalScope.NETWORK.value: True,
                    ApprovalScope.BULK_EDIT.value: False,
                    ApprovalScope.OUTSIDE_PROJECT.value: False,
                },
                description="通常開発モード。ファイル読み書き、Git操作、ネットワークアクセス許可。削除と大量編集は要承認。"
            ),

            # Risky Operations プロファイル（危険）
            ApprovalProfile(
                profile_id=str(uuid.uuid4()),
                project_id="__global__",
                name="risky",
                approved_scopes={
                    ApprovalScope.FS_READ.value: True,
                    ApprovalScope.FS_WRITE.value: True,
                    ApprovalScope.FS_DELETE.value: True,
                    ApprovalScope.GIT_READ.value: True,
                    ApprovalScope.GIT_WRITE.value: True,
                    ApprovalScope.NETWORK.value: True,
                    ApprovalScope.BULK_EDIT.value: True,
                    ApprovalScope.OUTSIDE_PROJECT.value: True,
                },
                description="全権限許可モード。ファイル削除、大量編集、プロジェクト外アクセスを含む全ての操作が可能。注意して使用。"
            ),

            # Custom プロファイル（カスタム可能）
            ApprovalProfile(
                profile_id=str(uuid.uuid4()),
                project_id="__global__",
                name="custom",
                approved_scopes={
                    ApprovalScope.FS_READ.value: True,
                    ApprovalScope.FS_WRITE.value: True,
                    ApprovalScope.FS_DELETE.value: False,
                    ApprovalScope.GIT_READ.value: True,
                    ApprovalScope.GIT_WRITE.value: False,
                    ApprovalScope.NETWORK.value: False,
                    ApprovalScope.BULK_EDIT.value: False,
                    ApprovalScope.OUTSIDE_PROJECT.value: False,
                },
                description="カスタマイズ用プロファイル。ユーザーが自由に編集可能。"
            ),
        ]

    def _save_profiles(self):
        """プロファイルを保存"""
        try:
            data = [profile.to_dict() for profile in self.profiles]

            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Failed to save approval profiles: {e}")

    def get_profile(self, profile_id: str) -> Optional[ApprovalProfile]:
        """
        プロファイルIDからプロファイルを取得

        Args:
            profile_id: プロファイルID

        Returns:
            ApprovalProfile（存在しない場合None）
        """
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def get_profiles_by_project(self, project_id: str) -> List[ApprovalProfile]:
        """
        プロジェクトIDからプロファイルのリストを取得

        Args:
            project_id: プロジェクトID（"__global__"でグローバルプロファイルを取得）

        Returns:
            ApprovalProfileのリスト
        """
        return [
            profile for profile in self.profiles
            if profile.project_id == project_id
        ]

    def get_global_profiles(self) -> List[ApprovalProfile]:
        """グローバルプロファイル（全プロジェクト共通）を取得"""
        return self.get_profiles_by_project("__global__")

    def get_all_profiles(self) -> List[ApprovalProfile]:
        """全てのプロファイルを取得"""
        return self.profiles.copy()

    def add_profile(self, profile: ApprovalProfile):
        """プロファイルを追加"""
        self.profiles.append(profile)
        self._save_profiles()

    def update_profile(self, profile: ApprovalProfile):
        """プロファイルを更新"""
        for i, p in enumerate(self.profiles):
            if p.profile_id == profile.profile_id:
                self.profiles[i] = profile
                self._save_profiles()
                return
        # 存在しない場合は追加
        self.add_profile(profile)

    def delete_profile(self, profile_id: str):
        """プロファイルを削除"""
        self.profiles = [p for p in self.profiles if p.profile_id != profile_id]
        self._save_profiles()

    def get_default_profile_for_project(self, project_id: str) -> Optional[ApprovalProfile]:
        """
        プロジェクトのデフォルトプロファイルを取得

        Args:
            project_id: プロジェクトID

        Returns:
            ApprovalProfile（見つからない場合はnormal-devグローバルプロファイルを返す）
        """
        # プロジェクト専用プロファイルを探す
        project_profiles = self.get_profiles_by_project(project_id)
        if project_profiles:
            # 最初のプロファイルをデフォルトとする
            return project_profiles[0]

        # なければグローバルのnormal-devを返す
        global_profiles = self.get_global_profiles()
        for profile in global_profiles:
            if profile.name == "normal-dev":
                return profile

        # それもなければ最初のグローバルプロファイル
        if global_profiles:
            return global_profiles[0]

        return None

    def create_project_profile(
        self,
        project_id: str,
        name: str,
        approved_scopes: Dict[str, bool],
        description: str = ""
    ) -> ApprovalProfile:
        """
        プロジェクト専用のプロファイルを作成

        Args:
            project_id: プロジェクトID
            name: プロファイル名
            approved_scopes: 承認スコープ辞書
            description: 説明

        Returns:
            作成したApprovalProfile
        """
        profile = ApprovalProfile(
            profile_id=str(uuid.uuid4()),
            project_id=project_id,
            name=name,
            approved_scopes=approved_scopes,
            description=description
        )
        self.add_profile(profile)
        return profile


# グローバルインスタンス
_global_profiles_manager: Optional[ProjectApprovalProfilesManager] = None


def get_approval_profiles_manager() -> ProjectApprovalProfilesManager:
    """
    グローバルなProjectApprovalProfilesManagerインスタンスを取得

    Returns:
        ProjectApprovalProfilesManager インスタンス
    """
    global _global_profiles_manager
    if _global_profiles_manager is None:
        _global_profiles_manager = ProjectApprovalProfilesManager()
    return _global_profiles_manager
