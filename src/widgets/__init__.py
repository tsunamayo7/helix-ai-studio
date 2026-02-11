"""
Helix AI Studio - Widgets
UI強化ウィジェット群

- NeuralFlowVisualizer: 3Phase実行パイプラインのノードベース可視化
- VRAMBudgetSimulator: インタラクティブGPUリソース管理盤
- BibleStatusPanel: BIBLE管理UIパネル
- BibleNotificationWidget: BIBLE検出通知バー
"""

from .chat_input import (
    EnhancedChatInput,
    AttachmentWidget,
    AttachmentBar,
    ChatInputArea,
)

from .neural_visualizer import (
    NeuralFlowVisualizer,
    NeuralFlowCompactWidget,
    PhaseState,
    PhaseData,
    PhaseNode,
)

from .vram_simulator import (
    VRAMBudgetSimulator,
    VRAMCompactWidget,
    GPUInfo,
    ModelInfo,
    MODEL_CATALOG,
    DEFAULT_GPUS,
)

from .bible_panel import BibleStatusPanel
from .bible_notification import BibleNotificationWidget
from .chat_widgets import (
    PhaseIndicator,
    SoloAIStatusBar,
    ExecutionIndicator,
    InterruptionBanner,
)

__all__ = [
    # chat_input
    "EnhancedChatInput",
    "AttachmentWidget",
    "AttachmentBar",
    "ChatInputArea",
    # neural_visualizer
    "NeuralFlowVisualizer",
    "NeuralFlowCompactWidget",
    "PhaseState",
    "PhaseData",
    "PhaseNode",
    # vram_simulator
    "VRAMBudgetSimulator",
    "VRAMCompactWidget",
    "GPUInfo",
    "ModelInfo",
    "MODEL_CATALOG",
    "DEFAULT_GPUS",
    # bible
    "BibleStatusPanel",
    "BibleNotificationWidget",
    # chat_widgets (v8.0.0)
    "PhaseIndicator",
    "SoloAIStatusBar",
    "ExecutionIndicator",
    "InterruptionBanner",
]
