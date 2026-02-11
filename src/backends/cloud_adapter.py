"""
CloudAI Adapter - CP5

LocalLLM が負荷/温度問題または budget 制約時に Cloud AI へフェールオーバー

Features:
- バックエンド選択（local/cloud）
- コスト見積もり
- 予算チェック
- フォールバック戦略
"""

import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """バックエンドタイプ"""
    LOCAL = "local"
    CLAUDE_SONNET = "claude_sonnet"
    CLAUDE_OPUS = "claude_opus"
    CLAUDE_HAIKU = "claude_haiku"
    GEMINI_PRO = "gemini_pro"
    GEMINI_FLASH = "gemini_flash"


class SelectionReason(Enum):
    """バックエンド選択理由"""
    USER_PREFERENCE = "user_preference"
    BUDGET_CONSTRAINT = "budget_constraint"
    LOCAL_UNAVAILABLE = "local_unavailable"
    THERMAL_THROTTLE = "thermal_throttle"
    TASK_COMPLEXITY = "task_complexity"
    FALLBACK = "fallback"
    DEFAULT = "default"


@dataclass
class CostEstimate:
    """コスト見積もり"""
    backend: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    model_name: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BackendSelection:
    """バックエンド選択結果"""
    backend: BackendType
    reason: SelectionReason
    reason_detail: str
    estimated_cost: Optional[CostEstimate] = None
    fallback_chain: List[str] = None

    def __post_init__(self):
        if self.fallback_chain is None:
            self.fallback_chain = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend.value,
            "reason": self.reason.value,
            "reason_detail": self.reason_detail,
            "estimated_cost": self.estimated_cost.to_dict() if self.estimated_cost else None,
            "fallback_chain": self.fallback_chain,
        }


class CloudAdapter:
    """
    Cloud AI Adapter

    LocalLLM が利用できない場合に Cloud AI へフェールオーバー

    選択ロジック:
    1. ユーザー指定があればそれを使用
    2. 予算制約をチェック
    3. Local LLM の状態をチェック
    4. タスク複雑度に基づいて選択
    5. フォールバック連鎖を実行
    """

    # コスト設定（USD per 1M tokens）
    COST_TABLE = {
        BackendType.LOCAL: {"input": 0.0, "output": 0.0},  # ローカルは無料
        BackendType.CLAUDE_HAIKU: {"input": 0.25, "output": 1.25},
        BackendType.CLAUDE_SONNET: {"input": 3.0, "output": 15.0},
        BackendType.CLAUDE_OPUS: {"input": 15.0, "output": 75.0},
        BackendType.GEMINI_FLASH: {"input": 0.075, "output": 0.30},
        BackendType.GEMINI_PRO: {"input": 1.25, "output": 5.0},
    }

    # デフォルトのフォールバック連鎖
    DEFAULT_FALLBACK_CHAIN = [
        BackendType.LOCAL,
        BackendType.CLAUDE_SONNET,
        BackendType.CLAUDE_OPUS,
    ]

    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # 依存モジュールの参照
        self._llm_manager = None
        self._thermal_policy = None
        self._budget_breaker = None

        # ログ設定
        self._setup_logging()

        logger.info("[CloudAdapter] Initialized")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "cloud_adapter.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)

    def set_llm_manager(self, llm_manager):
        """LLM Manager を設定"""
        self._llm_manager = llm_manager

    def set_thermal_policy(self, thermal_policy):
        """Thermal Policy を設定"""
        self._thermal_policy = thermal_policy

    def set_budget_breaker(self, budget_breaker):
        """Budget Breaker を設定"""
        self._budget_breaker = budget_breaker

    # ========================================
    # バックエンド選択
    # ========================================

    def select_backend(
        self,
        user_preference: Optional[BackendType] = None,
        task_complexity: str = "normal",  # "simple", "normal", "complex"
        estimated_tokens: int = 1000,
    ) -> BackendSelection:
        """
        最適なバックエンドを選択

        Args:
            user_preference: ユーザーが指定したバックエンド
            task_complexity: タスクの複雑度
            estimated_tokens: 推定トークン数

        Returns:
            BackendSelection: 選択結果
        """
        # 1. ユーザー指定があればそれを使用
        if user_preference:
            return BackendSelection(
                backend=user_preference,
                reason=SelectionReason.USER_PREFERENCE,
                reason_detail=f"User specified {user_preference.value}",
                estimated_cost=self.cost_estimate(user_preference, estimated_tokens),
            )

        # 2. 予算制約をチェック
        budget_result = self.budget_check(estimated_tokens)
        if budget_result["blocked"]:
            # 予算超過の場合はローカルを優先
            if self._is_local_available():
                return BackendSelection(
                    backend=BackendType.LOCAL,
                    reason=SelectionReason.BUDGET_CONSTRAINT,
                    reason_detail=f"Budget constraint: {budget_result['message']}",
                    estimated_cost=self.cost_estimate(BackendType.LOCAL, estimated_tokens),
                )
            else:
                # ローカルも使えない場合は最安のクラウドを選択
                return BackendSelection(
                    backend=BackendType.GEMINI_FLASH,
                    reason=SelectionReason.BUDGET_CONSTRAINT,
                    reason_detail=f"Budget constraint, using cheapest cloud: {budget_result['message']}",
                    estimated_cost=self.cost_estimate(BackendType.GEMINI_FLASH, estimated_tokens),
                )

        # 3. Local LLM の状態をチェック
        if not self._is_local_available():
            # ローカルが使えない理由を判定
            if self._is_thermal_throttled():
                reason = SelectionReason.THERMAL_THROTTLE
                reason_detail = "Local LLM throttled due to high temperature"
            else:
                reason = SelectionReason.LOCAL_UNAVAILABLE
                reason_detail = "Local LLM not available"

            # タスク複雑度に基づいてクラウドを選択
            cloud_backend = self._select_cloud_by_complexity(task_complexity)
            return BackendSelection(
                backend=cloud_backend,
                reason=reason,
                reason_detail=reason_detail,
                estimated_cost=self.cost_estimate(cloud_backend, estimated_tokens),
                fallback_chain=[b.value for b in self.DEFAULT_FALLBACK_CHAIN],
            )

        # 4. タスク複雑度に基づいて選択
        if task_complexity == "complex":
            # 複雑なタスクはクラウドを推奨
            return BackendSelection(
                backend=BackendType.CLAUDE_OPUS,
                reason=SelectionReason.TASK_COMPLEXITY,
                reason_detail="Complex task requires high-performance model",
                estimated_cost=self.cost_estimate(BackendType.CLAUDE_OPUS, estimated_tokens),
            )

        # 5. デフォルトはローカルを使用
        return BackendSelection(
            backend=BackendType.LOCAL,
            reason=SelectionReason.DEFAULT,
            reason_detail="Using local LLM as default",
            estimated_cost=self.cost_estimate(BackendType.LOCAL, estimated_tokens),
            fallback_chain=[b.value for b in self.DEFAULT_FALLBACK_CHAIN],
        )

    def _select_cloud_by_complexity(self, complexity: str) -> BackendType:
        """タスク複雑度に基づいてクラウドバックエンドを選択"""
        if complexity == "simple":
            return BackendType.CLAUDE_HAIKU
        elif complexity == "complex":
            return BackendType.CLAUDE_OPUS
        else:
            return BackendType.CLAUDE_SONNET

    def _is_local_available(self) -> bool:
        """Local LLM が利用可能か"""
        if self._llm_manager is None:
            return False
        return self._llm_manager.is_available()

    def _is_thermal_throttled(self) -> bool:
        """熱制御でスロットル中か"""
        if self._thermal_policy is None:
            return False
        return self._thermal_policy.is_throttled()

    # ========================================
    # コスト見積もり
    # ========================================

    def cost_estimate(
        self,
        backend: BackendType,
        estimated_tokens: int,
        input_ratio: float = 0.7,  # 入力:出力 の比率
    ) -> CostEstimate:
        """
        コストを見積もり

        Args:
            backend: バックエンドタイプ
            estimated_tokens: 推定総トークン数
            input_ratio: 入力トークンの比率

        Returns:
            CostEstimate: コスト見積もり
        """
        input_tokens = int(estimated_tokens * input_ratio)
        output_tokens = estimated_tokens - input_tokens

        cost_per_m = self.COST_TABLE.get(backend, {"input": 0, "output": 0})

        estimated_cost = (
            (input_tokens / 1_000_000) * cost_per_m["input"] +
            (output_tokens / 1_000_000) * cost_per_m["output"]
        )

        model_names = {
            BackendType.LOCAL: "Local LLM",
            BackendType.CLAUDE_HAIKU: "Claude Haiku",
            BackendType.CLAUDE_SONNET: "Claude Sonnet",
            BackendType.CLAUDE_OPUS: "Claude Opus",
            BackendType.GEMINI_FLASH: "Gemini 3 Flash",
            BackendType.GEMINI_PRO: "Gemini 3 Pro",
        }

        return CostEstimate(
            backend=backend.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            model_name=model_names.get(backend, backend.value),
        )

    # ========================================
    # 予算チェック
    # ========================================

    def budget_check(self, estimated_tokens: int = 1000) -> Dict[str, Any]:
        """
        予算をチェック

        Args:
            estimated_tokens: 推定トークン数

        Returns:
            {"blocked": bool, "message": str, "remaining": float}
        """
        if self._budget_breaker is None:
            return {"blocked": False, "message": "Budget breaker not configured", "remaining": float("inf")}

        # Sonnetのコストで見積もり
        estimate = self.cost_estimate(BackendType.CLAUDE_SONNET, estimated_tokens)

        # Budget Breakerでチェック
        can_proceed = self._budget_breaker.check_budget(estimate.estimated_cost_usd)

        if not can_proceed:
            usage = self._budget_breaker.get_current_usage()
            return {
                "blocked": True,
                "message": f"Budget exceeded: session ${usage['session_cost']:.4f}/${usage['session_budget']:.2f}, daily ${usage['daily_cost']:.4f}/${usage['daily_budget']:.2f}",
                "remaining": max(0, usage['session_budget'] - usage['session_cost']),
            }

        return {
            "blocked": False,
            "message": "Budget OK",
            "remaining": self._budget_breaker.get_current_usage().get("session_budget", 0) - self._budget_breaker.get_current_usage().get("session_cost", 0),
        }

    # ========================================
    # フォールバック実行
    # ========================================

    def fallback(
        self,
        prompt: str,
        fallback_chain: Optional[List[BackendType]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        フォールバック連鎖を実行

        Args:
            prompt: プロンプト
            fallback_chain: フォールバック連鎖（省略時はデフォルト）
            options: 生成オプション

        Returns:
            (success, response, metadata)
        """
        chain = fallback_chain or self.DEFAULT_FALLBACK_CHAIN
        errors = []

        for backend in chain:
            try:
                success, response, metadata = self._execute_backend(backend, prompt, options)
                if success:
                    metadata["fallback_chain_used"] = [b.value for b in chain[:chain.index(backend) + 1]]
                    self._log_decision(backend, "success", metadata)
                    return True, response, metadata
                else:
                    errors.append(f"{backend.value}: {response}")
            except Exception as e:
                errors.append(f"{backend.value}: {str(e)}")
                continue

        # すべて失敗
        error_msg = "All backends failed: " + "; ".join(errors)
        self._log_decision(chain[-1], "all_failed", {"errors": errors})
        return False, error_msg, {"error_type": "AllBackendsFailed", "errors": errors}

    def _execute_backend(
        self,
        backend: BackendType,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        指定バックエンドで実行

        Args:
            backend: バックエンドタイプ
            prompt: プロンプト
            options: オプション

        Returns:
            (success, response, metadata)
        """
        if backend == BackendType.LOCAL:
            if self._llm_manager:
                return self._llm_manager.request_llm(prompt, options)
            else:
                return False, "Local LLM Manager not configured", {"error_type": "NotConfigured"}

        # Cloud バックエンドは routing_executor 経由で実行
        # ここでは簡易的にエラーを返す（実際の実装は routing_executor と統合）
        return False, f"Cloud backend {backend.value} execution not implemented in CloudAdapter directly", {"error_type": "NotImplemented"}

    def _log_decision(self, backend: BackendType, status: str, metadata: Dict[str, Any]):
        """選択決定をログに記録"""
        logs_dir = self.data_dir.parent / "logs"
        log_file = logs_dir / "routing_decisions.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": "CloudAdapter",
            "selected_backend": backend.value,
            "final_status": status,
            "reason_code": metadata.get("reason", "fallback"),
            "metadata": metadata,
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[CloudAdapter] Failed to log decision: {e}")


# ========================================
# グローバルインスタンス
# ========================================

_cloud_adapter: Optional[CloudAdapter] = None


def get_cloud_adapter() -> CloudAdapter:
    """CloudAdapterのグローバルインスタンスを取得"""
    global _cloud_adapter
    if _cloud_adapter is None:
        _cloud_adapter = CloudAdapter()
    return _cloud_adapter
