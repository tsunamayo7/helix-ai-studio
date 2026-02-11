"""
Helix AI Studio - BIBLE Module (v8.0.0)
BIBLEファイルをアプリの第一級オブジェクトとして扱うモジュール群

Public API:
    - BibleDiscovery: BIBLE自動検出エンジン
    - BibleParser: BIBLEファイルパーサー
    - BibleInfo: パース済みBIBLE情報
    - BibleInjector: Phase 1/3コンテキスト注入
    - BibleLifecycleManager: 自律管理エンジン
"""

from .bible_schema import (
    BibleSectionType,
    BibleSection,
    BibleInfo,
    BIBLE_TEMPLATE,
    REQUIRED_SECTIONS,
)
from .bible_parser import BibleParser
from .bible_discovery import BibleDiscovery

# 遅延import（循環参照防止）
def _get_injector():
    from .bible_injector import BibleInjector
    return BibleInjector

def _get_lifecycle():
    from .bible_lifecycle import BibleLifecycleManager, BibleAction
    return BibleLifecycleManager, BibleAction

__all__ = [
    "BibleSectionType",
    "BibleSection",
    "BibleInfo",
    "BibleParser",
    "BibleDiscovery",
    "BIBLE_TEMPLATE",
    "REQUIRED_SECTIONS",
]
