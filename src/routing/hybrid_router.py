"""
Hybrid Router - Phase B

Local/Cloud ハイブリッド運用のための統合ルーター

Features:
- task_type + budget + resource + policy から backend を選択
- ModelRepository との連携
- CloudAdapter との連携
- RoutingDecision JSON への記録
"""

import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """ルーティング戦略"""
    LOCAL_FIRST = "local_first"       # ローカル優先
    CLOUD_FIRST = "cloud_first"       # クラウド優先
    COST_OPTIMIZED = "cost_optimized" # コスト最適化
    QUALITY_FIRST = "quality_first"   # 品質優先
    BALANCED = "balanced"             # バランス


@dataclass
class RoutingContext:
    """ルーティングコンテキスト"""
    task_type: str                    # タスク種別
    prompt: str                       # プロンプト
    estimated_tokens: int = 1000      # 推定トークン数
    require_vision: bool = False      # 画像認識が必要か
    require_code: bool = False        # コード生成が必要か
    max_latency_ms: Optional[int] = None  # 最大レイテンシ（ミリ秒）
    budget_limit: Optional[float] = None  # 予算上限（USD）
    user_preference: Optional[str] = None # ユーザー指定のバックエンド

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoutingDecision:
    """ルーティング決定結果"""
    selected_backend: str             # 選択されたバックエンド
    model_id: str                     # 選択されたモデルID
    reason: str                       # 選択理由
    fallback_chain: List[str]         # フォールバックチェーン
    estimated_cost: float             # 推定コスト（USD）
    estimated_latency_ms: int         # 推定レイテンシ（ミリ秒）
    strategy_used: str                # 使用した戦略
    context: Dict[str, Any]           # コンテキスト情報

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HybridRouter:
    """
    Hybrid Router

    Local/Cloud ハイブリッド運用を実現する統合ルーター

    選択ロジック:
    1. ユーザー指定があればそれを使用
    2. 予算制約をチェック
    3. タスク種別に基づく最適モデル選択
    4. リソース状況（温度/VRAM）を考慮
    5. フォールバックチェーン構築
    """

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
        self._model_repository = None
        self._cloud_adapter = None
        self._thermal_policy = None
        self._budget_breaker = None

        # 設定
        self.default_strategy = RoutingStrategy.BALANCED

        # タスク→ドメインマッピング
        self.task_domain_map = {
            "code_generation": "coding",
            "code_review": "coding",
            "bug_fix": "coding",
            "refactoring": "coding",
            "text_generation": "creative",
            "summarization": "general",
            "translation": "multilingual",
            "analysis": "analysis",
            "image_analysis": "vision",
            "embedding": "embedding",
            "general": "general",
        }

        # ログ設定
        self._setup_logging()

        logger.info("[HybridRouter] Initialized")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "hybrid_router.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)

    def set_model_repository(self, model_repository):
        """ModelRepository を設定"""
        self._model_repository = model_repository

    def set_cloud_adapter(self, cloud_adapter):
        """CloudAdapter を設定"""
        self._cloud_adapter = cloud_adapter

    def set_thermal_policy(self, thermal_policy):
        """ThermalPolicy を設定"""
        self._thermal_policy = thermal_policy

    def set_budget_breaker(self, budget_breaker):
        """BudgetBreaker を設定"""
        self._budget_breaker = budget_breaker

    # ========================================
    # ルーティング実行
    # ========================================

    def route(
        self,
        context: RoutingContext,
        strategy: Optional[RoutingStrategy] = None,
    ) -> RoutingDecision:
        """
        リクエストをルーティング

        Args:
            context: ルーティングコンテキスト
            strategy: ルーティング戦略（省略時はデフォルト）

        Returns:
            RoutingDecision: ルーティング決定
        """
        strategy = strategy or self.default_strategy

        # 1. ユーザー指定チェック
        if context.user_preference:
            return self._route_by_user_preference(context)

        # 2. 予算チェック
        budget_ok, budget_info = self._check_budget(context.estimated_tokens)
        if not budget_ok:
            return self._route_budget_constrained(context, budget_info)

        # 3. リソース状況チェック
        local_available = self._is_local_available()

        # 4. 戦略に基づくルーティング
        if strategy == RoutingStrategy.LOCAL_FIRST:
            return self._route_local_first(context, local_available)
        elif strategy == RoutingStrategy.CLOUD_FIRST:
            return self._route_cloud_first(context)
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._route_cost_optimized(context, local_available)
        elif strategy == RoutingStrategy.QUALITY_FIRST:
            return self._route_quality_first(context)
        else:  # BALANCED
            return self._route_balanced(context, local_available)

    def _route_by_user_preference(self, context: RoutingContext) -> RoutingDecision:
        """ユーザー指定に基づくルーティング"""
        preference = context.user_preference

        # モデルID直接指定
        if self._model_repository:
            model = self._model_repository.get_model(preference)
            if model:
                return RoutingDecision(
                    selected_backend=model.source,
                    model_id=model.model_id,
                    reason="user_preference",
                    fallback_chain=self._build_fallback_chain(model.source),
                    estimated_cost=self._estimate_cost(model.model_id, context.estimated_tokens),
                    estimated_latency_ms=self._estimate_latency(model.source),
                    strategy_used="user_preference",
                    context=context.to_dict(),
                )

        # バックエンド名指定
        if preference in ["local", "claude", "gemini"]:
            backend_map = {
                "local": "local",
                "claude": "cloud_claude",
                "gemini": "cloud_gemini",
            }
            backend = backend_map[preference]
            model_id = self._get_default_model_for_backend(backend)

            return RoutingDecision(
                selected_backend=backend,
                model_id=model_id,
                reason="user_preference",
                fallback_chain=self._build_fallback_chain(backend),
                estimated_cost=self._estimate_cost(model_id, context.estimated_tokens),
                estimated_latency_ms=self._estimate_latency(backend),
                strategy_used="user_preference",
                context=context.to_dict(),
            )

        # 不明な指定はデフォルトルーティング
        return self._route_balanced(context, self._is_local_available())

    def _route_budget_constrained(
        self,
        context: RoutingContext,
        budget_info: Dict[str, Any],
    ) -> RoutingDecision:
        """予算制約下でのルーティング"""
        # ローカルが使えればローカル
        if self._is_local_available():
            return RoutingDecision(
                selected_backend="local",
                model_id="local-default",
                reason=f"budget_constraint: {budget_info.get('message', '')}",
                fallback_chain=["local"],
                estimated_cost=0.0,
                estimated_latency_ms=500,
                strategy_used="budget_constrained",
                context=context.to_dict(),
            )

        # 最安クラウドモデル
        return RoutingDecision(
            selected_backend="cloud_gemini",
            model_id="gemini-3-flash",
            reason=f"budget_constraint_cheapest_cloud: {budget_info.get('message', '')}",
            fallback_chain=["gemini-3-flash"],
            estimated_cost=self._estimate_cost("gemini-3-flash", context.estimated_tokens),
            estimated_latency_ms=1000,
            strategy_used="budget_constrained",
            context=context.to_dict(),
        )

    def _route_local_first(
        self,
        context: RoutingContext,
        local_available: bool,
    ) -> RoutingDecision:
        """ローカル優先ルーティング"""
        if local_available:
            return RoutingDecision(
                selected_backend="local",
                model_id="local-default",
                reason="local_first_strategy",
                fallback_chain=["local", "claude-sonnet-4.5", "claude-opus-4.5"],
                estimated_cost=0.0,
                estimated_latency_ms=500,
                strategy_used="local_first",
                context=context.to_dict(),
            )

        return self._route_cloud_first(context)

    def _route_cloud_first(self, context: RoutingContext) -> RoutingDecision:
        """クラウド優先ルーティング"""
        domain = self.task_domain_map.get(context.task_type, "general")

        # ドメインに応じたモデル選択
        if domain == "coding":
            model_id = "claude-sonnet-4.5"
        elif domain == "vision":
            model_id = "gemini-3-pro"
        elif domain == "analysis":
            model_id = "claude-opus-4.5"
        else:
            model_id = "claude-sonnet-4.5"

        return RoutingDecision(
            selected_backend="cloud_claude" if "claude" in model_id else "cloud_gemini",
            model_id=model_id,
            reason=f"cloud_first_strategy_domain_{domain}",
            fallback_chain=[model_id, "claude-opus-4.5", "local"],
            estimated_cost=self._estimate_cost(model_id, context.estimated_tokens),
            estimated_latency_ms=2000,
            strategy_used="cloud_first",
            context=context.to_dict(),
        )

    def _route_cost_optimized(
        self,
        context: RoutingContext,
        local_available: bool,
    ) -> RoutingDecision:
        """コスト最適化ルーティング"""
        # 1. ローカルが使えれば最優先
        if local_available:
            return RoutingDecision(
                selected_backend="local",
                model_id="local-default",
                reason="cost_optimized_local",
                fallback_chain=["local", "gemini-3-flash", "claude-haiku-4.5"],
                estimated_cost=0.0,
                estimated_latency_ms=500,
                strategy_used="cost_optimized",
                context=context.to_dict(),
            )

        # 2. 最安クラウドモデル
        return RoutingDecision(
            selected_backend="cloud_gemini",
            model_id="gemini-3-flash",
            reason="cost_optimized_cheapest",
            fallback_chain=["gemini-3-flash", "claude-haiku-4.5", "claude-sonnet-4.5"],
            estimated_cost=self._estimate_cost("gemini-3-flash", context.estimated_tokens),
            estimated_latency_ms=1000,
            strategy_used="cost_optimized",
            context=context.to_dict(),
        )

    def _route_quality_first(self, context: RoutingContext) -> RoutingDecision:
        """品質優先ルーティング"""
        domain = self.task_domain_map.get(context.task_type, "general")

        # 最高品質モデル選択
        if domain == "vision" or context.require_vision:
            model_id = "gemini-3-pro"
            backend = "cloud_gemini"
        else:
            model_id = "claude-opus-4.5"
            backend = "cloud_claude"

        return RoutingDecision(
            selected_backend=backend,
            model_id=model_id,
            reason="quality_first_strategy",
            fallback_chain=[model_id, "claude-sonnet-4.5", "gemini-3-pro"],
            estimated_cost=self._estimate_cost(model_id, context.estimated_tokens),
            estimated_latency_ms=3000,
            strategy_used="quality_first",
            context=context.to_dict(),
        )

    def _route_balanced(
        self,
        context: RoutingContext,
        local_available: bool,
    ) -> RoutingDecision:
        """バランス型ルーティング"""
        domain = self.task_domain_map.get(context.task_type, "general")

        # シンプルなタスクはローカルまたは高速モデル
        simple_tasks = ["summarization", "translation", "general"]
        complex_tasks = ["code_generation", "analysis", "bug_fix"]

        if context.task_type in simple_tasks:
            if local_available:
                return RoutingDecision(
                    selected_backend="local",
                    model_id="local-default",
                    reason="balanced_simple_task_local",
                    fallback_chain=["local", "claude-haiku-4.5", "gemini-3-flash"],
                    estimated_cost=0.0,
                    estimated_latency_ms=500,
                    strategy_used="balanced",
                    context=context.to_dict(),
                )
            else:
                return RoutingDecision(
                    selected_backend="cloud_claude",
                    model_id="claude-haiku-4.5",
                    reason="balanced_simple_task_cloud",
                    fallback_chain=["claude-haiku-4.5", "gemini-3-flash", "claude-sonnet-4.5"],
                    estimated_cost=self._estimate_cost("claude-haiku-4.5", context.estimated_tokens),
                    estimated_latency_ms=1000,
                    strategy_used="balanced",
                    context=context.to_dict(),
                )

        # 複雑なタスクは高性能モデル
        if context.require_vision:
            model_id = "gemini-3-pro"
            backend = "cloud_gemini"
        elif context.require_code or domain == "coding":
            model_id = "claude-sonnet-4.5"
            backend = "cloud_claude"
        else:
            model_id = "claude-sonnet-4.5"
            backend = "cloud_claude"

        return RoutingDecision(
            selected_backend=backend,
            model_id=model_id,
            reason=f"balanced_complex_task_{domain}",
            fallback_chain=[model_id, "claude-opus-4.5", "local"],
            estimated_cost=self._estimate_cost(model_id, context.estimated_tokens),
            estimated_latency_ms=2000,
            strategy_used="balanced",
            context=context.to_dict(),
        )

    # ========================================
    # ヘルパーメソッド
    # ========================================

    def _check_budget(self, estimated_tokens: int) -> Tuple[bool, Dict[str, Any]]:
        """予算をチェック"""
        if self._budget_breaker is None:
            return True, {"message": "BudgetBreaker not configured"}

        # Sonnetのコストで概算
        estimated_cost = (estimated_tokens / 1000) * 0.003 * 2  # in+out

        can_proceed = self._budget_breaker.check_budget(estimated_cost)
        if not can_proceed:
            usage = self._budget_breaker.get_current_usage()
            return False, {
                "message": f"Budget exceeded: session ${usage.get('session_cost', 0):.4f}/${usage.get('session_budget', 0):.2f}",
                "remaining": max(0, usage.get('session_budget', 0) - usage.get('session_cost', 0)),
            }

        return True, {"message": "OK"}

    def _is_local_available(self) -> bool:
        """ローカルLLMが利用可能か"""
        if self._thermal_policy:
            if self._thermal_policy.is_throttled():
                return False

        if self._cloud_adapter and hasattr(self._cloud_adapter, '_llm_manager'):
            llm_manager = self._cloud_adapter._llm_manager
            if llm_manager:
                return llm_manager.is_available() or llm_manager.get_state().value == "idle"

        return False

    def _build_fallback_chain(self, primary_backend: str) -> List[str]:
        """フォールバックチェーンを構築"""
        chains = {
            "local": ["local", "claude-sonnet-4.5", "claude-opus-4.5"],
            "cloud_claude": ["claude-sonnet-4.5", "claude-opus-4.5", "local"],
            "cloud_gemini": ["gemini-3-pro", "gemini-3-flash", "claude-sonnet-4.5"],
        }
        return chains.get(primary_backend, ["claude-sonnet-4.5", "local"])

    def _get_default_model_for_backend(self, backend: str) -> str:
        """バックエンドのデフォルトモデルを取得"""
        defaults = {
            "local": "local-default",
            "cloud_claude": "claude-sonnet-4.5",
            "cloud_gemini": "gemini-3-pro",
        }
        return defaults.get(backend, "claude-sonnet-4.5")

    def _estimate_cost(self, model_id: str, tokens: int) -> float:
        """コストを概算"""
        # 簡易コスト表（USD per 1K tokens, in+out平均）
        cost_table = {
            "local-default": 0.0,
            "claude-haiku-4.5": 0.00075,
            "claude-sonnet-4.5": 0.009,
            "claude-opus-4.5": 0.045,
            "gemini-3-flash": 0.00019,
            "gemini-3-pro": 0.003125,
        }
        rate = cost_table.get(model_id, 0.009)
        return (tokens / 1000) * rate

    def _estimate_latency(self, backend: str) -> int:
        """レイテンシを概算（ミリ秒）"""
        latency_table = {
            "local": 500,
            "cloud_claude": 2000,
            "cloud_gemini": 1500,
        }
        return latency_table.get(backend, 2000)

    def log_decision(self, decision: RoutingDecision, session_id: str = ""):
        """ルーティング決定をログに記録"""
        logs_dir = self.data_dir.parent / "logs"
        log_file = logs_dir / "routing_decisions.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "source": "HybridRouter",
            "selected_backend": decision.selected_backend,
            "model_id": decision.model_id,
            "reason_code": decision.reason,
            "strategy": decision.strategy_used,
            "fallback_chain": decision.fallback_chain,
            "estimated_cost": decision.estimated_cost,
            "estimated_latency_ms": decision.estimated_latency_ms,
            "task_type": decision.context.get("task_type", ""),
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[HybridRouter] Failed to log decision: {e}")


# ========================================
# グローバルインスタンス
# ========================================

_hybrid_router: Optional[HybridRouter] = None


def get_hybrid_router() -> HybridRouter:
    """HybridRouterのグローバルインスタンスを取得"""
    global _hybrid_router
    if _hybrid_router is None:
        _hybrid_router = HybridRouter()
    return _hybrid_router
