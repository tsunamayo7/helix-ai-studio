"""
Routing Layer - Phase 2.1+ / 2.5 / 2.6 / 2.x

タスク分類、ルーティング、フォールバック機能
Phase 2.5: ルーティング決定ログ
Phase 2.6: ポリシー連動チェック
Phase 2.x: RoutingExecutor (CP1-CP10統合)
"""

from .task_types import TaskType
from .classifier import TaskClassifier
from .router import BackendRouter
from .fallback import FallbackManager
from .decision_logger import (
    RoutingDecision,
    RoutingDecisionLogger,
    get_routing_decision_logger,
)
from .policy_checker import (
    PolicyChecker,
    PolicyCheckResult,
    get_policy_checker,
)
from .model_presets import (
    ModelPreset,
    ModelPresetManager,
    get_preset_manager,
    BUILTIN_PRESETS,
)
from .routing_executor import (
    RoutingExecutor,
    get_routing_executor,
)

# Phase B: Hybrid Router
from .hybrid_router import (
    HybridRouter,
    RoutingStrategy,
    RoutingContext,
    RoutingDecision as HybridRoutingDecision,
    get_hybrid_router,
)

__all__ = [
    "TaskType",
    "TaskClassifier",
    "BackendRouter",
    "FallbackManager",
    "RoutingDecision",
    "RoutingDecisionLogger",
    "get_routing_decision_logger",
    "PolicyChecker",
    "PolicyCheckResult",
    "get_policy_checker",
    "ModelPreset",
    "ModelPresetManager",
    "get_preset_manager",
    "BUILTIN_PRESETS",
    "RoutingExecutor",
    "get_routing_executor",
    # Phase B
    "HybridRouter",
    "RoutingStrategy",
    "RoutingContext",
    "HybridRoutingDecision",
    "get_hybrid_router",
]
