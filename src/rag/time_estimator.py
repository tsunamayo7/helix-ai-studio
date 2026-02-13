"""
Helix AI Studio - Time Estimator (v8.5.0)
RAG構築の所要時間を動的に推定する
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TimeEstimator:
    """RAG構築の所要時間を動的に推定"""

    # ベンチマーク値（分単位）
    BENCHMARKS = {
        "chunking_per_kb": 0.01,             # 分/KB
        "embedding_per_chunk": 0.02,          # 分/チャンク (qwen3-embedding:4b)
        "summary_per_chunk": 0.15,            # 分/チャンク (ministral-3:8b)
        "kg_per_chunk": 0.5,                  # 分/チャンク (command-a:111b)
        "model_load_time": {
            "command-a:111b": 2.0,            # 分（67GB VRAM ロード時間）
            "ministral-3:8b": 0.0,            # 常駐のためロード不要
            "qwen3-embedding:4b": 0.0,        # 常駐のためロード不要
        },
        "claude_plan": 1.5,                   # 分（プラン策定）
        "claude_verify": 1.0,                 # 分（品質検証）
    }

    def __init__(self):
        self.completed_steps: List[dict] = []
        self._actual_elapsed: float = 0.0

    def estimate_from_plan(self, plan: dict) -> float:
        """プランから総所要時間を推定（分）"""
        total = self.BENCHMARKS["claude_plan"]

        execution_plan = plan.get("execution_plan", {})
        steps = execution_plan.get("steps", [])

        for step in steps:
            total += step.get("estimated_minutes", 0)

        total += self.BENCHMARKS["claude_verify"]
        return total

    def estimate_simple(self, total_files: int, total_size_kb: float,
                        estimated_chunks: int) -> float:
        """ファイル統計からの簡易推定"""
        total = self.BENCHMARKS["claude_plan"]

        # チャンキング
        total += total_size_kb * self.BENCHMARKS["chunking_per_kb"]

        # Embedding
        total += estimated_chunks * self.BENCHMARKS["embedding_per_chunk"]

        # 要約・キーワード抽出
        total += estimated_chunks * self.BENCHMARKS["summary_per_chunk"]

        # KG生成（高優先度ファイルのみと仮定して半数）
        kg_chunks = max(estimated_chunks // 2, 1)
        total += kg_chunks * self.BENCHMARKS["kg_per_chunk"]
        total += self.BENCHMARKS["model_load_time"].get("command-a:111b", 2.0)

        # 多段要約
        total += total_files * 0.5  # ファイル単位要約

        total += self.BENCHMARKS["claude_verify"]
        return total

    def update_estimate(self, step_id: int, actual_elapsed: float,
                        remaining_steps: List[dict]) -> float:
        """実行中の実績値から残り時間を動的修正"""
        self._actual_elapsed = actual_elapsed

        plan_elapsed = sum(
            s.get("estimated_minutes", 0) for s in self.completed_steps
        )

        if plan_elapsed > 0:
            correction_ratio = actual_elapsed / plan_elapsed
        else:
            correction_ratio = 1.0

        remaining = sum(
            s.get("estimated_minutes", 0) * correction_ratio
            for s in remaining_steps
        )

        return remaining

    def mark_step_completed(self, step: dict):
        """ステップ完了を記録"""
        self.completed_steps.append(step)

    def reset(self):
        """リセット"""
        self.completed_steps.clear()
        self._actual_elapsed = 0.0
