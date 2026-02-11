"""
Helix AI Studio - BIBLE Schema Definition (v8.0.0)
BIBLEファイルのスキーマ定義: セクション型、データクラス、テンプレート、見出しマッピング
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
from pathlib import Path


class BibleSectionType(Enum):
    """BIBLEの必須/任意セクション定義"""
    # === 必須セクション (6) ===
    HEADER = "header"
    VERSION_HISTORY = "version_history"
    ARCHITECTURE = "architecture"
    CHANGELOG = "changelog"
    FILE_LIST = "file_list"
    DIRECTORY_STRUCTURE = "directory"

    # === 推奨セクション (6) ===
    DESIGN_PHILOSOPHY = "philosophy"
    TECH_STACK = "tech_stack"
    UI_ARCHITECTURE = "ui_architecture"
    MIGRATION_GUIDE = "migration"
    TROUBLESHOOTING = "troubleshooting"
    ROADMAP = "roadmap"

    # === 任意セクション (4) ===
    GPU_REQUIREMENTS = "gpu"
    MODEL_CONFIG = "model_config"
    BUILD_CONFIG = "build_config"
    CUSTOM = "custom"


# 必須セクション集合
REQUIRED_SECTIONS = {
    BibleSectionType.HEADER,
    BibleSectionType.VERSION_HISTORY,
    BibleSectionType.ARCHITECTURE,
    BibleSectionType.CHANGELOG,
    BibleSectionType.FILE_LIST,
    BibleSectionType.DIRECTORY_STRUCTURE,
}


@dataclass
class BibleSection:
    """BIBLEの1セクション"""
    type: BibleSectionType
    title: str
    content: str
    line_start: int
    line_end: int
    completeness: float  # 0.0-1.0


@dataclass
class BibleInfo:
    """パース済みBIBLE情報"""
    file_path: Path
    project_name: str
    version: str
    codename: str
    created_date: str
    updated_date: str
    sections: List[BibleSection] = field(default_factory=list)
    raw_content: str = ""
    line_count: int = 0

    @property
    def version_tuple(self):
        """バージョン比較用タプル"""
        try:
            return tuple(int(x) for x in self.version.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    @property
    def missing_required_sections(self) -> List[BibleSectionType]:
        """不足している必須セクション"""
        present = {s.type for s in self.sections}
        return list(REQUIRED_SECTIONS - present)

    @property
    def completeness_score(self) -> float:
        """
        BIBLE全体の完全性スコア (0.0-1.0)
        計算: 必須セクション存在率 * 0.6 + 内容充実度平均 * 0.4
        """
        if not self.sections:
            return 0.0

        present_required = len(
            {s.type for s in self.sections if s.type in REQUIRED_SECTIONS}
        )
        section_score = min(1.0, present_required / len(REQUIRED_SECTIONS))

        content_score = (
            sum(s.completeness for s in self.sections) / len(self.sections)
        )

        return section_score * 0.6 + content_score * 0.4


# =============================================================================
# BIBLE テンプレート（アプリ内蔵）
# =============================================================================

BIBLE_TEMPLATE = """# {project_name} - Project BIBLE (包括的マスター設計書)

**バージョン**: {version} "{codename}"
**アプリケーションバージョン**: {version}
**作成日**: {date}
**最終更新**: {date}
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## バージョン変遷サマリー

| バージョン | コードネーム | 主な変更 |
|-----------|------------|---------|
| {version} | {codename} | 初回作成 |

---

## v{version} "{codename}" 変更履歴

### コンセプト

（このバージョンのコンセプトを記述）

### 主な変更点

1. （変更点1）
2. （変更点2）

---

## アーキテクチャ概要

（システム全体のアーキテクチャ図・説明）

---

## 変更ファイル一覧 (v{version})

| ファイル | 変更内容 |
|----------|----------|
| （ファイル名） | （変更内容） |

---

## ディレクトリ構造

```
{project_name}/
├── （ディレクトリ構造）
```

---

## 技術スタック

| カテゴリ | 技術 | バージョン/詳細 |
|---------|------|----------------|
| （カテゴリ） | （技術） | （詳細） |

---

## 次期バージョン予定

（ロードマップ）

---

*このBIBLEは {generator} により生成されました*
"""


# =============================================================================
# セクション検出用の見出しマッピング
# v8.4.1: 番号プレフィックス付き見出し対応 ("## N. タイトル" 形式)
#   _NUM_ は _detect_section_type() で展開される番号オプショナルパターン
#   例: "^##\s+(?:\d+\.\s*)?アーキテクチャ" → "## 3. アーキテクチャ概要" にマッチ
# =============================================================================

# 番号プレフィックスのオプショナルパターン: "N. " or "N.N " or なし
_NUM_ = r"(?:\d+(?:\.\d+)?\s*\.?\s*)?"

SECTION_HEADING_MAP: Dict[BibleSectionType, List[str]] = {
    BibleSectionType.HEADER: [
        r"^#\s+.*BIBLE",
        r"^#\s+.*Project BIBLE",
        r"^\*\*バージョン\*\*",
        rf"^##\s+{_NUM_}プロジェクト概要",
    ],
    BibleSectionType.VERSION_HISTORY: [
        rf"^##\s+{_NUM_}バージョン変遷",
        rf"^##\s+{_NUM_}Version History",
        rf"^##\s+{_NUM_}変更履歴サマリー",
    ],
    BibleSectionType.ARCHITECTURE: [
        rf"^##\s+{_NUM_}アーキテクチャ",
        rf"^##\s+{_NUM_}Architecture",
        rf"^##\s+{_NUM_}.*Pipeline",
        rf"^##\s+{_NUM_}システム構成",
        rf"^##\s+{_NUM_}3Phase",
        rf"^##\s+{_NUM_}RAPTOR",
    ],
    BibleSectionType.CHANGELOG: [
        r"^##\s+v[\d.]+.*変更",
        r"^##\s+v[\d.]+.*更新",
        rf"^##\s+{_NUM_}主な変更",
        r"^###\s+主な変更点",
        rf"^##\s+付録[A-Z]",
    ],
    BibleSectionType.FILE_LIST: [
        rf"^##\s+{_NUM_}変更ファイル",
        rf"^##\s+{_NUM_}Modified Files",
        rf"^##\s+{_NUM_}ファイル一覧",
        rf"^###\s+変更ファイル一覧",  # v8.4.2: ###レベルの見出しにも対応
    ],
    BibleSectionType.DIRECTORY_STRUCTURE: [
        rf"^##\s+{_NUM_}ディレクトリ",
        rf"^##\s+{_NUM_}Directory Structure",
        rf"^##\s+{_NUM_}プロジェクト構造",
    ],
    BibleSectionType.DESIGN_PHILOSOPHY: [
        rf"^##\s+{_NUM_}設計哲学",
        rf"^##\s+{_NUM_}デザインシステム",
        rf"^##\s+{_NUM_}Design",
        rf"^##\s+{_NUM_}コンセプト",
    ],
    BibleSectionType.TECH_STACK: [
        rf"^##\s+{_NUM_}技術スタック",
        rf"^##\s+{_NUM_}Tech Stack",
        rf"^##\s+{_NUM_}使用技術",
    ],
    BibleSectionType.UI_ARCHITECTURE: [
        rf"^##\s+{_NUM_}UI",
        rf"^##\s+{_NUM_}画面構成",
        rf"^##\s+{_NUM_}インターフェース",
    ],
    BibleSectionType.GPU_REQUIREMENTS: [
        rf"^##\s+{_NUM_}GPU",
        rf"^##\s+{_NUM_}ハードウェア",
        rf"^##\s+{_NUM_}環境要件",
    ],
    BibleSectionType.MODEL_CONFIG: [
        rf"^##\s+{_NUM_}CLAUDE_MODELS",
        rf"^##\s+{_NUM_}ローカルLLM",
        rf"^##\s+{_NUM_}モデル一覧",
    ],
    BibleSectionType.BUILD_CONFIG: [
        rf"^##\s+{_NUM_}PyInstaller",
        rf"^##\s+{_NUM_}ビルド",
        rf"^##\s+{_NUM_}Build",
        rf"^##\s+{_NUM_}設定ファイル",
        rf"^##\s+{_NUM_}MCP",
    ],
    BibleSectionType.MIGRATION_GUIDE: [
        rf"^##\s+{_NUM_}移行",
        rf"^##\s+{_NUM_}Migration",
        rf"^##\s+{_NUM_}アップグレード",
    ],
    BibleSectionType.ROADMAP: [
        rf"^##\s+{_NUM_}次期",
        rf"^##\s+{_NUM_}ロードマップ",
        rf"^##\s+{_NUM_}Roadmap",
        rf"^##\s+{_NUM_}予定",
    ],
    BibleSectionType.TROUBLESHOOTING: [
        rf"^##\s+{_NUM_}トラブル",
        rf"^##\s+{_NUM_}Troubleshooting",
        rf"^##\s+{_NUM_}FAQ",
    ],
}
