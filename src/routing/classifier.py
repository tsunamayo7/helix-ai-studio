"""
Task Classifier - Phase 2.1

ルールベースのタスク分類器
"""

import re
import logging
from typing import Optional
from .task_types import TaskType

logger = logging.getLogger(__name__)


class TaskClassifier:
    """
    ルールベースのタスク分類器

    ユーザーの入力テキストと現在のフェーズから、タスク種別を判定する
    """

    def __init__(self):
        """初期化"""
        # キーワードパターン (優先度順)
        self.patterns = {
            TaskType.PLAN: [
                r"計画",
                r"プラン",
                r"plan",
                r"設計",
                r"アーキテクチャ",
                r"構想",
                r"方針",
            ],
            TaskType.IMPLEMENT: [
                r"実装",
                r"修正",
                r"コード",
                r"プログラム",
                r"作成",
                r"変更",
                r"追加",
                r"削除",
                r"implement",
                r"code",
                r"fix",
                r"create",
                r"modify",
            ],
            TaskType.RESEARCH: [
                r"調査",
                r"比較",
                r"検索",
                r"調べ",
                r"search",
                r"research",
                r"compare",
                r"find",
                r"探",
            ],
            TaskType.REVIEW: [
                r"レビュー",
                r"diff",
                r"差分",
                r"確認",
                r"review",
                r"check",
                r"inspect",
            ],
            TaskType.VERIFY: [
                r"テスト",
                r"検証",
                r"試験",
                r"test",
                r"verify",
                r"validate",
                r"pytest",
                r"unittest",
            ],
        }

    def classify(self, phase: str, user_text: str) -> TaskType:
        """
        タスクを分類

        Args:
            phase: 現在のフェーズ (e.g. "S0", "S2", "S4")
            user_text: ユーザーの入力テキスト

        Returns:
            TaskType: 分類されたタスク種別
        """
        user_text_lower = user_text.lower()

        # 1. フェーズに基づく分類（優先度高）
        if phase == "S2":
            logger.info(f"[Classifier] Phase-based: S2 → PLAN")
            return TaskType.PLAN

        if phase == "S4":
            logger.info(f"[Classifier] Phase-based: S4 → IMPLEMENT")
            return TaskType.IMPLEMENT

        if phase == "S5":
            logger.info(f"[Classifier] Phase-based: S5 → VERIFY")
            return TaskType.VERIFY

        if phase == "S6":
            logger.info(f"[Classifier] Phase-based: S6 → REVIEW")
            return TaskType.REVIEW

        # 2. キーワードベースの分類（優先度順）
        for task_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_text_lower):
                    logger.info(
                        f"[Classifier] Keyword-based: '{pattern}' → {task_type}"
                    )
                    return task_type

        # 3. デフォルト: CHAT
        logger.info(f"[Classifier] Default: CHAT")
        return TaskType.CHAT

    def classify_with_confidence(
        self, phase: str, user_text: str
    ) -> tuple[TaskType, float]:
        """
        タスクを分類（信頼度付き）

        Args:
            phase: 現在のフェーズ
            user_text: ユーザーの入力テキスト

        Returns:
            (TaskType, confidence): 分類結果と信頼度 (0.0 ~ 1.0)
        """
        task_type = self.classify(phase, user_text)
        user_text_lower = user_text.lower()

        # 信頼度の計算
        confidence = 0.5  # デフォルト

        # フェーズベースの分類は高信頼度
        if phase in ["S2", "S4", "S5", "S6"]:
            confidence = 0.9

        # キーワードマッチがあれば信頼度を上げる
        if task_type in self.patterns:
            for pattern in self.patterns[task_type]:
                if re.search(pattern, user_text_lower):
                    confidence = max(confidence, 0.8)
                    break

        # CHATは低信頼度
        if task_type == TaskType.CHAT:
            confidence = 0.3

        return task_type, confidence
