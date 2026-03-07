"""
local_ai_tab.py — 後方互換ラッパー (v12.8.0)

LocalAITab のチャット機能は SoloAITab に統合されました。
設定は OllamaSettingsTab に移動しました。
旧 import パスを維持するためのエイリアスモジュールです。
"""
from .solo_ai_tab import SoloAITab

# 後方互換エイリアス
LocalAITab = SoloAITab
