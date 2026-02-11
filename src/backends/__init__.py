"""
Backend Abstraction Layer v7.0.0

LLM Backend の抽象化インターフェース
Claude, Gemini, Local を統一的に扱うための基底クラスと実装
v7.0.0: 3Phase実行パイプライン + SequentialExecutor追加
"""

from .base import LLMBackend, BackendRequest, BackendResponse
from .claude_backend import ClaudeBackend
from .claude_cli_backend import (
    ClaudeCLIBackend,
    find_claude_command,
    check_claude_cli_available,
    get_claude_cli_backend,
)
from .gemini_backend import GeminiBackend
from .local_backend import LocalBackend
from .local_connector import (
    LocalConnector,
    LocalConnectorConfig,
    ConnectionStatus,
    OllamaModel,
    RECOMMENDED_MODELS,
    ENDPOINT_PRESETS,
    get_local_connector,
)
from .registry import BackendRegistry, get_backend_registry

# v7.0.0: 3Phase実行パイプライン
from .sequential_executor import (
    SequentialExecutor,
    SequentialTask,
    SequentialResult,
    filter_chain_of_thought,
)
from .mix_orchestrator import MixAIOrchestrator

# Local LLM Management & Thermal Control
from .local_llm_manager import (
    LocalLLMManager,
    LLMManagerConfig,
    LLMState,
    get_llm_manager,
)
from .thermal_monitor import (
    ThermalMonitor,
    ThermalReading,
    ThermalThresholds,
    ThermalStatus,
    get_thermal_monitor,
)
from .thermal_policy import (
    ThermalPolicyController,
    ThermalPolicyConfig,
    ThermalPolicyState,
    get_thermal_policy,
)
from .cloud_adapter import (
    CloudAdapter,
    BackendType,
    SelectionReason,
    CostEstimate,
    BackendSelection,
    get_cloud_adapter,
)

# Model Repository
from .model_repository import (
    ModelRepository,
    ModelMetadata,
    ModelDomain,
    ModelSource,
    get_model_repository,
)

__all__ = [
    "LLMBackend",
    "BackendRequest",
    "BackendResponse",
    "ClaudeBackend",
    "ClaudeCLIBackend",
    "find_claude_command",
    "check_claude_cli_available",
    "get_claude_cli_backend",
    "GeminiBackend",
    "LocalBackend",
    "LocalConnector",
    "LocalConnectorConfig",
    "ConnectionStatus",
    "OllamaModel",
    "RECOMMENDED_MODELS",
    "ENDPOINT_PRESETS",
    "get_local_connector",
    "BackendRegistry",
    "get_backend_registry",
    # v7.0.0: 3Phase
    "SequentialExecutor",
    "SequentialTask",
    "SequentialResult",
    "filter_chain_of_thought",
    "MixAIOrchestrator",
    # Thermal & LLM Management
    "LocalLLMManager",
    "LLMManagerConfig",
    "LLMState",
    "get_llm_manager",
    "ThermalMonitor",
    "ThermalReading",
    "ThermalThresholds",
    "ThermalStatus",
    "get_thermal_monitor",
    "ThermalPolicyController",
    "ThermalPolicyConfig",
    "ThermalPolicyState",
    "get_thermal_policy",
    "CloudAdapter",
    "BackendType",
    "SelectionReason",
    "CostEstimate",
    "BackendSelection",
    "get_cloud_adapter",
    # Model Repository
    "ModelRepository",
    "ModelMetadata",
    "ModelDomain",
    "ModelSource",
    "get_model_repository",
]
