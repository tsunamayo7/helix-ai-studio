"""
Task Types - Phase 2.1

タスク種別の定義
"""

from enum import Enum, auto


class TaskType(Enum):
    """
    タスク種別

    ルールベース分類器がユーザーの入力とフェーズから判定する
    """

    PLAN = auto()       # 計画策定 (S2)
    IMPLEMENT = auto()  # 実装・修正 (S4)
    RESEARCH = auto()   # 調査・比較
    REVIEW = auto()     # レビュー・Diff確認 (S6)
    VERIFY = auto()     # 検証・テスト (S5)
    CHAT = auto()       # 通常の対話

    @classmethod
    def all_types(cls):
        """全タスク種別を取得"""
        return [cls.PLAN, cls.IMPLEMENT, cls.RESEARCH, cls.REVIEW, cls.VERIFY, cls.CHAT]

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"TaskType.{self.name}"
