# Tabs - v12.8.0: soloAI統合 + CloudAI設定/Ollama設定分離
# mixAI, soloAI, CloudAI設定, Ollama設定, 一般設定

from .solo_ai_tab import SoloAITab
from .claude_tab import ClaudeTab  # 後方互換エイリアス
from .helix_orchestrator_tab import HelixOrchestratorTab
from .settings_cortex_tab import SettingsCortexTab
from .cloud_settings_tab import CloudSettingsTab
from .ollama_settings_tab import OllamaSettingsTab

__all__ = [
    'SoloAITab',
    'ClaudeTab',
    'HelixOrchestratorTab',
    'SettingsCortexTab',
    'CloudSettingsTab',
    'OllamaSettingsTab',
]
