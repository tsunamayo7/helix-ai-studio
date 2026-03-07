"""
claude_tab.py — 後方互換ラッパー (v12.8.0)

ClaudeTab は SoloAITab へ統合されました。
旧 import パスを維持するためのエイリアスモジュールです。
"""
from .solo_ai_tab import SoloAITab

# 後方互換エイリアス
ClaudeTab = SoloAITab
