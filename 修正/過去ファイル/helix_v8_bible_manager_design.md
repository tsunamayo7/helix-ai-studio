# Helix AI Studio — BIBLE Manager 機能設計書 & 実装プロンプト

**バージョン**: v8.0.0 "Living Bible"
**作成日**: 2026-02-09
**作成者**: Claude Opus 4.6

---

## 第1部: コンセプト

### 「BIBLEをアプリの第一級オブジェクトにする」

現状のBIBLEは「人間が手動で管理するMarkdownファイル」に過ぎない。
v8.0.0ではBIBLEを**アプリが自律的に認識・読み込み・検証・更新・新規作成する
構造化ドキュメント**として昇格させる。

```
現状:  ユーザー → 手動でBIBLE作成 → 手動でClaude Codeに渡す → 手動で更新
v8.0:  ユーザー → ファイル/ディレクトリ指定 → アプリがBIBLE自動検出 →
       Phase 1でBIBLEコンテキスト自動注入 → 実行後にBIBLE自動更新提案
```

### 3つの柱

| 柱 | 機能 | トリガー |
|----|------|---------|
| **Auto-Discovery** | ファイル/ディレクトリ指定時にBIBLEを自動検索・読み込み | ファイル添付、--cwd指定 |
| **Schema Enforcement** | BIBLE書式をアプリ内で定義し、検証・補完 | BIBLE読み込み時、BIBLE生成時 |
| **Autonomous Lifecycle** | 実行結果に基づきBIBLEの更新/新規作成を自律提案・実行 | Phase 3完了後 |

---

## 第2部: 詳細設計

### 2.1 BIBLE Auto-Discovery（自動検索）

#### トリガーポイント

```
(A) mixAIタブ: ユーザーがファイルを添付 → 添付ファイルの親ディレクトリを探索
(B) mixAIタブ: プロンプトにパスが含まれる → パスの祖先ディレクトリを探索
(C) soloAIタブ: --cwd がCLI実行時に指定される → cwdから探索
(D) 設定: 「プロジェクトルート」を明示指定 → そのディレクトリから探索
```

#### 検索アルゴリズム

```python
# src/bible/bible_discovery.py

import os
import glob
from pathlib import Path
from typing import Optional, List

# BIBLEファイル名パターン（優先順位順）
BIBLE_PATTERNS = [
    "BIBLE_*.md",                    # 標準パターン: BIBLE_ProjectName_X.Y.Z.md
    "BIBLE.md",                      # 簡易パターン
    "PROJECT_BIBLE.md",              # 代替パターン
    "**/BIBLE/*.md",                  # BIBLE/ディレクトリ内
    "docs/BIBLE*.md",                # docs/配下
]

# 最大探索深度（親ディレクトリ方向）
MAX_PARENT_DEPTH = 5

# 最大探索深度（子ディレクトリ方向）
MAX_CHILD_DEPTH = 3

class BibleDiscovery:
    """BIBLEファイルの自動検出エンジン"""

    @staticmethod
    def discover(start_path: str) -> List["BibleInfo"]:
        """
        指定パスからBIBLEファイルを検索する。

        検索順序:
        1. start_path自身（ファイルならその親ディレクトリ）
        2. 子ディレクトリ（MAX_CHILD_DEPTH階層まで）
        3. 親ディレクトリ（MAX_PARENT_DEPTH階層まで遡上）

        Returns:
            BibleInfoのリスト（バージョン降順ソート = 最新が先頭）
        """
        results = []
        base_dir = Path(start_path)
        if base_dir.is_file():
            base_dir = base_dir.parent

        # Phase 1: カレントディレクトリ + 子ディレクトリ
        for pattern in BIBLE_PATTERNS:
            for match in base_dir.glob(pattern):
                if match.is_file():
                    info = BibleParser.parse_header(match)
                    if info:
                        results.append(info)

        # Phase 2: 親ディレクトリを遡上
        if not results:
            current = base_dir.parent
            for _ in range(MAX_PARENT_DEPTH):
                if current == current.parent:
                    break
                for pattern in BIBLE_PATTERNS:
                    for match in current.glob(pattern):
                        if match.is_file():
                            info = BibleParser.parse_header(match)
                            if info:
                                results.append(info)
                if results:
                    break
                current = current.parent

        # バージョン降順ソート
        results.sort(key=lambda b: b.version_tuple, reverse=True)
        return results

    @staticmethod
    def discover_from_prompt(prompt_text: str) -> List["BibleInfo"]:
        """
        プロンプト内のパス文字列からBIBLEを検索する。

        対応パターン:
        - "C:\\Users\\...\\project\\" (Windows絶対パス)
        - "/home/user/project/" (Unix絶対パス)
        - ファイルパス内の親ディレクトリを探索
        """
        import re
        # Windowsパス
        paths = re.findall(r'[A-Z]:\\[^\s"\']+', prompt_text)
        # Unixパス
        paths += re.findall(r'/(?:home|Users|mnt|opt)/[^\s"\']+', prompt_text)

        all_results = []
        seen = set()
        for p in paths:
            p = p.rstrip('\\/"\'')
            if os.path.exists(p) and p not in seen:
                seen.add(p)
                all_results.extend(BibleDiscovery.discover(p))

        # 重複除去（パスベース）
        unique = {}
        for b in all_results:
            if str(b.file_path) not in unique:
                unique[str(b.file_path)] = b
        return list(unique.values())
```

#### UI連携

```python
# mixAIチャットタブへの統合

def _on_file_attached(self, file_path: str):
    """ファイル添付時のBIBLE自動検索"""
    bibles = BibleDiscovery.discover(file_path)
    if bibles:
        latest = bibles[0]
        self._show_bible_notification(latest)
        self._bible_context = latest

def _show_bible_notification(self, bible: BibleInfo):
    """BIBLE検出通知をチャットエリア上部に表示"""
    # 📖 BIBLE検出: ProjectName v7.1.0 "Adaptive Models"
    # [コンテキストに追加] [無視] [詳細を表示]
    notification = BibleNotificationWidget(bible)
    notification.add_clicked.connect(lambda: self._inject_bible_context(bible))
    self.chat_area.insert_notification(notification)
```

### 2.2 BIBLE Schema（書式規定）

#### スキーマ定義

```python
# src/bible/bible_schema.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

class BibleSectionType(Enum):
    """BIBLEの必須/任意セクション定義"""
    # === 必須セクション ===
    HEADER = "header"                    # メタ情報（バージョン、日付等）
    VERSION_HISTORY = "version_history"  # バージョン変遷サマリー
    ARCHITECTURE = "architecture"        # アーキテクチャ概要
    CHANGELOG = "changelog"             # 当該バージョンの変更点
    FILE_LIST = "file_list"             # 変更ファイル一覧
    DIRECTORY_STRUCTURE = "directory"    # ディレクトリ構造

    # === 推奨セクション ===
    DESIGN_PHILOSOPHY = "philosophy"    # 設計哲学・コンセプト
    TECH_STACK = "tech_stack"           # 技術スタック
    UI_ARCHITECTURE = "ui_architecture" # UI構成
    MIGRATION_GUIDE = "migration"       # 移行ガイド
    TROUBLESHOOTING = "troubleshooting" # トラブルシューティング
    ROADMAP = "roadmap"                 # ロードマップ

    # === 任意セクション（プロジェクト固有） ===
    GPU_REQUIREMENTS = "gpu"            # GPU環境要件
    MODEL_CONFIG = "model_config"       # モデル設定
    BUILD_CONFIG = "build_config"       # ビルド設定
    CUSTOM = "custom"                   # カスタムセクション


@dataclass
class BibleSection:
    """BIBLEの1セクション"""
    type: BibleSectionType
    title: str           # 日本語見出し
    content: str         # Markdownコンテンツ
    line_start: int      # 開始行番号
    line_end: int        # 終了行番号
    completeness: float  # 0.0-1.0 内容充実度（AI判定）


@dataclass
class BibleInfo:
    """パース済みBIBLE情報"""
    file_path: Path
    project_name: str
    version: str              # "7.1.0"
    codename: str             # "Adaptive Models"
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
        except:
            return (0, 0, 0)

    @property
    def missing_required_sections(self) -> List[BibleSectionType]:
        """不足している必須セクション"""
        required = {
            BibleSectionType.HEADER,
            BibleSectionType.VERSION_HISTORY,
            BibleSectionType.ARCHITECTURE,
            BibleSectionType.CHANGELOG,
            BibleSectionType.FILE_LIST,
            BibleSectionType.DIRECTORY_STRUCTURE,
        }
        present = {s.type for s in self.sections}
        return list(required - present)

    @property
    def completeness_score(self) -> float:
        """BIBLE全体の完全性スコア (0.0-1.0)"""
        if not self.sections:
            return 0.0
        required_count = 6
        present_required = sum(
            1 for s in self.sections
            if s.type in {
                BibleSectionType.HEADER,
                BibleSectionType.VERSION_HISTORY,
                BibleSectionType.ARCHITECTURE,
                BibleSectionType.CHANGELOG,
                BibleSectionType.FILE_LIST,
                BibleSectionType.DIRECTORY_STRUCTURE,
            }
        )
        section_score = present_required / required_count  # 必須セクション存在率
        content_score = (
            sum(s.completeness for s in self.sections) / len(self.sections)
            if self.sections else 0.0
        )
        return section_score * 0.6 + content_score * 0.4


# === BIBLEテンプレート（アプリ内蔵） ===

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


# === セクション検出用の見出しマッピング ===

SECTION_HEADING_MAP = {
    BibleSectionType.HEADER: [
        r"^#\s+.*BIBLE",
        r"^#\s+.*Project BIBLE",
        r"^\*\*バージョン\*\*",
    ],
    BibleSectionType.VERSION_HISTORY: [
        r"^##\s+バージョン変遷",
        r"^##\s+Version History",
        r"^##\s+変更履歴サマリー",
    ],
    BibleSectionType.ARCHITECTURE: [
        r"^##\s+アーキテクチャ",
        r"^##\s+Architecture",
        r"^##\s+.*Pipeline",
        r"^##\s+システム構成",
    ],
    BibleSectionType.CHANGELOG: [
        r"^##\s+v[\d.]+.*変更",
        r"^##\s+v[\d.]+.*更新",
        r"^##\s+主な変更",
        r"^###\s+主な変更点",
    ],
    BibleSectionType.FILE_LIST: [
        r"^##\s+変更ファイル",
        r"^##\s+Modified Files",
        r"^##\s+ファイル一覧",
    ],
    BibleSectionType.DIRECTORY_STRUCTURE: [
        r"^##\s+ディレクトリ",
        r"^##\s+Directory Structure",
        r"^##\s+プロジェクト構造",
    ],
    BibleSectionType.DESIGN_PHILOSOPHY: [
        r"^##\s+設計哲学",
        r"^##\s+デザイン",
        r"^##\s+Design",
        r"^##\s+コンセプト",
    ],
    BibleSectionType.TECH_STACK: [
        r"^##\s+技術スタック",
        r"^##\s+Tech Stack",
        r"^##\s+使用技術",
    ],
    BibleSectionType.UI_ARCHITECTURE: [
        r"^##\s+UI",
        r"^##\s+画面構成",
        r"^##\s+インターフェース",
    ],
    BibleSectionType.GPU_REQUIREMENTS: [
        r"^##\s+GPU",
        r"^##\s+ハードウェア",
        r"^##\s+環境要件",
    ],
    BibleSectionType.MODEL_CONFIG: [
        r"^##\s+モデル",
        r"^##\s+CLAUDE_MODELS",
        r"^##\s+ローカルLLM",
    ],
    BibleSectionType.BUILD_CONFIG: [
        r"^##\s+PyInstaller",
        r"^##\s+ビルド",
        r"^##\s+Build",
    ],
    BibleSectionType.MIGRATION_GUIDE: [
        r"^##\s+移行",
        r"^##\s+Migration",
        r"^##\s+アップグレード",
    ],
    BibleSectionType.ROADMAP: [
        r"^##\s+次期",
        r"^##\s+ロードマップ",
        r"^##\s+Roadmap",
        r"^##\s+予定",
    ],
}
```

#### BIBLEパーサー

```python
# src/bible/bible_parser.py

import re
from pathlib import Path
from .bible_schema import *

class BibleParser:
    """BIBLEファイルの構造化パーサー"""

    @staticmethod
    def parse_header(file_path: Path) -> Optional[BibleInfo]:
        """BIBLEファイルのヘッダー情報のみ高速パース"""
        try:
            content = file_path.read_text(encoding="utf-8")
            first_lines = content[:2000]  # ヘッダーは先頭2000文字以内

            # プロジェクト名
            name_match = re.search(r"^#\s+(.+?)\s*[-–—]\s*Project BIBLE", first_lines, re.MULTILINE)
            project_name = name_match.group(1).strip() if name_match else file_path.stem

            # バージョン
            ver_match = re.search(r"\*\*バージョン\*\*:\s*([\d.]+)", first_lines)
            version = ver_match.group(1) if ver_match else "0.0.0"

            # コードネーム
            code_match = re.search(r'"([^"]+)"', first_lines[:500])
            codename = code_match.group(1) if code_match else ""

            # 日付
            date_match = re.search(r"\*\*(?:作成日|最終更新)\*\*:\s*(.+)", first_lines)
            date_str = date_match.group(1).strip() if date_match else ""

            return BibleInfo(
                file_path=file_path,
                project_name=project_name,
                version=version,
                codename=codename,
                created_date=date_str,
                updated_date=date_str,
                raw_content=content,
                line_count=content.count("\n") + 1,
            )
        except Exception:
            return None

    @staticmethod
    def parse_full(file_path: Path) -> Optional[BibleInfo]:
        """BIBLEファイルの完全パース（セクション分割含む）"""
        info = BibleParser.parse_header(file_path)
        if not info:
            return None

        lines = info.raw_content.split("\n")
        sections = []
        current_section = None
        current_lines = []
        current_start = 0

        for i, line in enumerate(lines):
            # 見出し行を検出
            detected_type = BibleParser._detect_section_type(line)
            if detected_type:
                # 前のセクションを保存
                if current_section:
                    sections.append(BibleSection(
                        type=current_section,
                        title=lines[current_start].lstrip("#").strip(),
                        content="\n".join(current_lines),
                        line_start=current_start + 1,
                        line_end=i,
                        completeness=BibleParser._estimate_completeness(
                            current_section, "\n".join(current_lines)
                        ),
                    ))
                current_section = detected_type
                current_lines = [line]
                current_start = i
            elif current_section:
                current_lines.append(line)

        # 最後のセクション
        if current_section:
            sections.append(BibleSection(
                type=current_section,
                title=lines[current_start].lstrip("#").strip(),
                content="\n".join(current_lines),
                line_start=current_start + 1,
                line_end=len(lines),
                completeness=BibleParser._estimate_completeness(
                    current_section, "\n".join(current_lines)
                ),
            ))

        info.sections = sections
        return info

    @staticmethod
    def _detect_section_type(line: str) -> Optional[BibleSectionType]:
        """行がどのセクション見出しかを判定"""
        for section_type, patterns in SECTION_HEADING_MAP.items():
            for pattern in patterns:
                if re.match(pattern, line):
                    return section_type
        return None

    @staticmethod
    def _estimate_completeness(section_type: BibleSectionType, content: str) -> float:
        """セクションの内容充実度を簡易推定"""
        line_count = content.count("\n")
        char_count = len(content)

        # セクションごとの最低期待行数
        min_lines = {
            BibleSectionType.HEADER: 5,
            BibleSectionType.VERSION_HISTORY: 8,
            BibleSectionType.ARCHITECTURE: 15,
            BibleSectionType.CHANGELOG: 10,
            BibleSectionType.FILE_LIST: 5,
            BibleSectionType.DIRECTORY_STRUCTURE: 10,
        }
        expected = min_lines.get(section_type, 5)
        line_score = min(1.0, line_count / expected)

        # コードブロック・テーブルの存在をボーナスとして加算
        has_code = "```" in content
        has_table = "|" in content and "---" in content
        bonus = 0.1 * has_code + 0.1 * has_table

        return min(1.0, line_score + bonus)
```

### 2.3 BIBLE Autonomous Lifecycle（自律管理）

#### Phase 1へのBIBLEコンテキスト注入

```python
# src/backends/bible_injector.py

class BibleInjector:
    """Phase 1/Phase 3のClaudeプロンプトにBIBLEコンテキストを注入"""

    @staticmethod
    def build_context(bible: BibleInfo, mode: str = "phase1") -> str:
        """
        BIBLEからClaudeプロンプト用のコンテキストブロックを構築。

        mode:
            "phase1" - 計画立案用（全体概要 + アーキテクチャ + 変更履歴）
            "phase3" - 統合用（全体概要 + 変更ファイル一覧）
            "update" - BIBLE更新用（現在のBIBLE全文 + 不足セクション情報）
        """
        if mode == "phase1":
            sections = [
                BibleSectionType.HEADER,
                BibleSectionType.ARCHITECTURE,
                BibleSectionType.CHANGELOG,
                BibleSectionType.DIRECTORY_STRUCTURE,
                BibleSectionType.TECH_STACK,
            ]
        elif mode == "phase3":
            sections = [
                BibleSectionType.HEADER,
                BibleSectionType.FILE_LIST,
                BibleSectionType.ARCHITECTURE,
            ]
        elif mode == "update":
            return BibleInjector._build_update_context(bible)
        else:
            sections = [s.type for s in bible.sections]

        context_parts = []
        context_parts.append(f"=== PROJECT BIBLE: {bible.project_name} v{bible.version} ===")
        for s in bible.sections:
            if s.type in sections:
                context_parts.append(s.content)

        return "\n\n".join(context_parts)

    @staticmethod
    def _build_update_context(bible: BibleInfo) -> str:
        """BIBLE更新用の特殊コンテキスト"""
        missing = bible.missing_required_sections
        score = bible.completeness_score

        ctx = f"""=== BIBLE UPDATE CONTEXT ===
Project: {bible.project_name}
Current Version: {bible.version}
Completeness Score: {score:.0%}
Missing Required Sections: {', '.join(s.value for s in missing) if missing else 'None'}
Line Count: {bible.line_count}

=== CURRENT BIBLE CONTENT ===
{bible.raw_content}

=== UPDATE INSTRUCTIONS ===
"""
        if missing:
            ctx += "以下の必須セクションを追加してください:\n"
            for s in missing:
                ctx += f"  - {s.value}\n"
        if score < 0.7:
            ctx += "全体の内容充実度が低いです。各セクションをより詳細に記述してください。\n"

        return ctx


# === mix_orchestrator.py への統合ポイント ===

class MixAIOrchestrator:
    def _build_phase1_prompt(self, user_prompt: str, attachments: list) -> str:
        """Phase 1用プロンプト構築（BIBLE自動注入対応）"""
        prompt_parts = []

        # BIBLE コンテキスト注入
        if self._bible_context:
            bible_ctx = BibleInjector.build_context(self._bible_context, mode="phase1")
            prompt_parts.append(f"<project_context>\n{bible_ctx}\n</project_context>")

        # ユーザープロンプト
        prompt_parts.append(user_prompt)

        return "\n\n".join(prompt_parts)
```

#### BIBLE更新判定ロジック

```python
# src/bible/bible_lifecycle.py

from enum import Enum
from typing import Optional, Tuple

class BibleAction(Enum):
    NONE = "none"                  # 何もしない
    UPDATE_CHANGELOG = "update"    # 変更履歴セクションを更新
    ADD_SECTIONS = "add_sections"  # 不足セクションを追加
    CREATE_NEW = "create_new"      # 新規BIBLE作成
    VERSION_UP = "version_up"      # 新バージョンBIBLE作成


class BibleLifecycleManager:
    """BIBLE自律管理エンジン"""

    @staticmethod
    def determine_action(
        bible: Optional[BibleInfo],
        execution_result: dict,
        config: dict,
    ) -> Tuple[BibleAction, str]:
        """
        Phase 3完了後に実行すべきBIBLEアクションを判定。

        Returns:
            (アクション種別, 理由メッセージ)
        """
        # BIBLEが存在しない場合
        if bible is None:
            # ファイル変更が5個以上 → 新規作成を提案
            changed_files = execution_result.get("changed_files", [])
            if len(changed_files) >= 5:
                return (
                    BibleAction.CREATE_NEW,
                    f"{len(changed_files)}個のファイルが変更されました。"
                    f"プロジェクトBIBLEの作成を推奨します。"
                )
            return (BibleAction.NONE, "")

        # BIBLEが存在する場合
        score = bible.completeness_score
        missing = bible.missing_required_sections

        # 必須セクション不足 → セクション追加
        if missing:
            return (
                BibleAction.ADD_SECTIONS,
                f"必須セクションが{len(missing)}個不足しています: "
                f"{', '.join(s.value for s in missing)}"
            )

        # バージョン変更の検出
        app_version = execution_result.get("app_version")
        if app_version and app_version != bible.version:
            return (
                BibleAction.VERSION_UP,
                f"アプリバージョンが {bible.version} → {app_version} に"
                f"変更されています。新バージョンBIBLEの作成を推奨します。"
            )

        # ファイル変更あり → CHANGELOG更新
        changed_files = execution_result.get("changed_files", [])
        if changed_files:
            return (
                BibleAction.UPDATE_CHANGELOG,
                f"{len(changed_files)}個のファイルが変更されました。"
                f"変更履歴の更新を推奨します。"
            )

        return (BibleAction.NONE, "")

    @staticmethod
    def execute_action(
        action: BibleAction,
        bible: Optional[BibleInfo],
        execution_result: dict,
        project_dir: str,
    ) -> Optional[str]:
        """
        BIBLEアクションを実行し、生成/更新されたBIBLEの内容を返す。

        Claude CLIを呼び出してBIBLEの生成/更新を行う。
        """
        if action == BibleAction.NONE:
            return None

        if action == BibleAction.CREATE_NEW:
            return BibleLifecycleManager._create_new_bible(
                execution_result, project_dir
            )

        if action == BibleAction.ADD_SECTIONS:
            return BibleLifecycleManager._add_missing_sections(
                bible, execution_result
            )

        if action == BibleAction.UPDATE_CHANGELOG:
            return BibleLifecycleManager._update_changelog(
                bible, execution_result
            )

        if action == BibleAction.VERSION_UP:
            return BibleLifecycleManager._version_up_bible(
                bible, execution_result, project_dir
            )

        return None

    @staticmethod
    def _create_new_bible(result: dict, project_dir: str) -> str:
        """新規BIBLE生成（Claude CLIで生成）"""
        from .bible_schema import BIBLE_TEMPLATE
        from datetime import date

        # テンプレートベースで基本構造を生成
        project_name = Path(project_dir).name
        today = date.today().isoformat()

        content = BIBLE_TEMPLATE.format(
            project_name=project_name,
            version="1.0.0",
            codename="Genesis",
            date=today,
            generator="Helix AI Studio BIBLE Manager",
        )

        # Claude CLIで内容を充実化するプロンプトを構築
        # （実際の実行はOrchestrator経由）
        return content
```

#### UI: BIBLE管理パネル

```python
# src/widgets/bible_panel.py

class BibleStatusPanel(QWidget):
    """
    BIBLE状態表示パネル（mixAI設定タブ内に配置）

    表示内容:
    - BIBLE検出状態（📖 検出済み / ⚠️ 未検出）
    - プロジェクト名・バージョン
    - 完全性スコア（プログレスバー）
    - 不足セクション一覧
    - アクションボタン（更新 / 新規作成 / 詳細表示）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ヘッダー
        header = QLabel("📖 BIBLE Manager")
        header.setStyleSheet("color: #00d4ff; font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # ステータス行
        self.status_label = QLabel("⚠️ BIBLE未検出")
        self.status_label.setStyleSheet("color: #ff8800;")
        layout.addWidget(self.status_label)

        # プロジェクト情報
        self.info_label = QLabel("")
        layout.addWidget(self.info_label)

        # 完全性スコア
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setFormat("完全性: %p%")
        self.score_bar.setVisible(False)
        layout.addWidget(self.score_bar)

        # 不足セクション
        self.missing_label = QLabel("")
        self.missing_label.setWordWrap(True)
        self.missing_label.setVisible(False)
        layout.addWidget(self.missing_label)

        # ボタン行
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("📝 新規作成")
        self.btn_update = QPushButton("🔄 更新")
        self.btn_detail = QPushButton("📋 詳細")
        self.btn_create.clicked.connect(self._on_create)
        self.btn_update.clicked.connect(self._on_update)
        self.btn_detail.clicked.connect(self._on_detail)
        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_update)
        btn_layout.addWidget(self.btn_detail)
        layout.addLayout(btn_layout)

    def update_bible(self, bible: Optional[BibleInfo]):
        """BIBLE情報でパネルを更新"""
        if bible is None:
            self.status_label.setText("⚠️ BIBLE未検出")
            self.status_label.setStyleSheet("color: #ff8800;")
            self.info_label.setText("ファイル添付またはパス指定で自動検索します")
            self.score_bar.setVisible(False)
            self.missing_label.setVisible(False)
            self.btn_update.setEnabled(False)
            return

        self.status_label.setText(f"📖 BIBLE検出済み")
        self.status_label.setStyleSheet("color: #00ff88;")
        self.info_label.setText(
            f"{bible.project_name} v{bible.version} \"{bible.codename}\"\n"
            f"{bible.line_count}行 | {len(bible.sections)}セクション"
        )

        score = int(bible.completeness_score * 100)
        self.score_bar.setValue(score)
        self.score_bar.setVisible(True)
        if score >= 80:
            self.score_bar.setStyleSheet("QProgressBar::chunk { background: #00ff88; }")
        elif score >= 50:
            self.score_bar.setStyleSheet("QProgressBar::chunk { background: #ffaa00; }")
        else:
            self.score_bar.setStyleSheet("QProgressBar::chunk { background: #ff4444; }")

        missing = bible.missing_required_sections
        if missing:
            self.missing_label.setText(
                f"⚠️ 不足セクション: {', '.join(s.value for s in missing)}"
            )
            self.missing_label.setVisible(True)
        else:
            self.missing_label.setVisible(False)

        self.btn_update.setEnabled(True)
```

---

## 第3部: 実行フロー統合図

```
ユーザーのアクション
    │
    ├─ (A) ファイル添付 ──────────────────────┐
    ├─ (B) パス入力 ─────────────────────────┤
    ├─ (C) 設定でプロジェクトルート指定 ──────┤
    │                                         ▼
    │                              BibleDiscovery.discover()
    │                                         │
    │                                    BIBLEあり?
    │                                   ╱          ╲
    │                                 Yes            No
    │                                  │              │
    │                          BibleParser.parse_full()  状態: "未検出"
    │                                  │              │
    │                          BibleStatusPanel更新    「新規作成」ボタン有効化
    │                                  │
    │                          チャットに通知表示
    │                         「📖 BIBLE検出: XXX v7.1.0」
    │                         [コンテキストに追加]
    │                                  │
    ▼                                  ▼
 実行ボタン押下 ──────────── BIBLEコンテキスト保持
    │
    ├── Phase 1: Claude計画立案
    │     └── BibleInjector.build_context(mode="phase1")
    │         → <project_context>としてプロンプトに注入
    │
    ├── Phase 2: ローカルLLM順次実行
    │     （BIBLEの影響なし — ローカルLLMはBIBLE参照不要）
    │
    ├── Phase 3: Claude統合
    │     └── BibleInjector.build_context(mode="phase3")
    │         → 統合時にアーキテクチャ整合性チェック用
    │
    └── Post-Phase: BIBLE自律管理
          └── BibleLifecycleManager.determine_action()
              │
              ├─ CREATE_NEW → 「BIBLE新規作成しますか？」ダイアログ
              ├─ ADD_SECTIONS → 「不足セクションを追加しますか？」
              ├─ UPDATE_CHANGELOG → 「変更履歴を更新しますか？」
              ├─ VERSION_UP → 「新バージョンBIBLE作成しますか？」
              └─ NONE → 何もしない
                    │
                    ▼ ユーザー承認
              Claude CLI呼び出し（BIBLE更新専用プロンプト）
                    │
                    ▼
              BIBLEファイル書き出し + パネル更新
```

---

## 第4部: 新規ファイル一覧

| ファイル | 役割 |
|---------|------|
| `src/bible/__init__.py` | BIBLEモジュール初期化 |
| `src/bible/bible_schema.py` | スキーマ定義、テンプレート、セクション型 |
| `src/bible/bible_parser.py` | BIBLEファイルパーサー |
| `src/bible/bible_discovery.py` | BIBLE自動検索エンジン |
| `src/bible/bible_injector.py` | Phase 1/3へのコンテキスト注入 |
| `src/bible/bible_lifecycle.py` | 自律管理（更新判定・実行） |
| `src/widgets/bible_panel.py` | BIBLE管理UIパネル |
| `src/widgets/bible_notification.py` | BIBLE検出通知ウィジェット |

---

## 第5部: Claude Code 実装プロンプト

```
## Helix AI Studio v8.0.0 "Living Bible" — BIBLE Manager 実装

### 目標
BIBLEファイルをアプリの第一級オブジェクトとして扱う機能を追加。
ファイル添付時の自動検索、書式検証、Phase実行時のコンテキスト注入、
実行後の自律的な更新/新規作成を実装する。

### 事前調査（必須）
```bash
# 現在のファイル構成を確認
find src/ -type f -name "*.py" | sort
# BIBLEディレクトリの有無
ls -la BIBLE/ 2>/dev/null || echo "BIBLE dir not found"
# ファイル添付の現在の実装を確認
grep -rn "attach\|ファイルを添付\|file.*drop\|dropEvent" src/ --include="*.py"
# Phase 1プロンプト構築を確認
cat src/backends/phase1_prompt.py
# Orchestratorの実行フローを確認
cat src/backends/mix_orchestrator.py
# UIタブのファイル添付処理を確認
grep -rn "def.*attach\|def.*file\|def.*drop" src/tabs/ --include="*.py"
```

### Phase A: BIBLEモジュール作成

1. `src/bible/` ディレクトリを作成
2. `src/bible/__init__.py` を作成（公開API定義）
3. `src/bible/bible_schema.py` を作成:
   - BibleSectionType enum（必須6種 + 推奨7種 + 任意）
   - BibleSection dataclass
   - BibleInfo dataclass（version_tuple, missing_required_sections,
     completeness_score プロパティ付き）
   - BIBLE_TEMPLATE（日本語テンプレート文字列）
   - SECTION_HEADING_MAP（セクション検出用正規表現マッピング）

4. `src/bible/bible_parser.py` を作成:
   - BibleParser.parse_header(): ヘッダーのみ高速パース
   - BibleParser.parse_full(): 全セクション分割パース
   - BibleParser._detect_section_type(): 見出し→セクション型判定
   - BibleParser._estimate_completeness(): 内容充実度簡易推定

5. `src/bible/bible_discovery.py` を作成:
   - BIBLE_PATTERNS: ファイル名パターン（5種）
   - BibleDiscovery.discover(start_path): ディレクトリ探索
     → カレント→子→親の順で探索、バージョン降順ソート
   - BibleDiscovery.discover_from_prompt(text): プロンプト内パス抽出→探索

### Phase B: Phase実行への統合

6. `src/bible/bible_injector.py` を作成:
   - BibleInjector.build_context(bible, mode):
     mode="phase1" → 概要+アーキテクチャ+変更履歴+構造+技術
     mode="phase3" → 概要+ファイル一覧+アーキテクチャ
     mode="update" → 全文+不足セクション情報

7. `src/backends/mix_orchestrator.py` を修正:
   - __init__()に self._bible_context: Optional[BibleInfo] = None 追加
   - set_bible_context(bible) メソッド追加
   - _build_phase1_prompt() 内で:
     if self._bible_context:
         bible_ctx = BibleInjector.build_context(self._bible_context, "phase1")
         prompt = f"<project_context>\n{bible_ctx}\n</project_context>\n\n{prompt}"
   - Phase 3プロンプト構築でも同様にmode="phase3"で注入

### Phase C: 自律管理エンジン

8. `src/bible/bible_lifecycle.py` を作成:
   - BibleAction enum (NONE, UPDATE_CHANGELOG, ADD_SECTIONS, CREATE_NEW, VERSION_UP)
   - BibleLifecycleManager.determine_action(): 判定ロジック
     - BIBLEなし + ファイル変更5個以上 → CREATE_NEW
     - 必須セクション不足 → ADD_SECTIONS
     - APP_VERSION != bible.version → VERSION_UP
     - ファイル変更あり → UPDATE_CHANGELOG
   - BibleLifecycleManager.execute_action(): Claude CLI呼び出しでBIBLE生成/更新

9. mix_orchestrator.pyの_execute_pipeline()の末尾（Phase 3完了後）に追加:
   ```python
   # Post-Phase: BIBLE自律管理
   if self._bible_context and config.get("bible_auto_manage", True):
       action, reason = BibleLifecycleManager.determine_action(
           self._bible_context, execution_result, config
       )
       if action != BibleAction.NONE:
           self.bible_action_proposed.emit(action, reason)
   ```

### Phase D: UIパネル

10. `src/widgets/bible_panel.py` を作成:
    - BibleStatusPanel(QWidget):
      - 📖 BIBLE Manager ヘッダー（#00d4ff）
      - ステータスラベル（検出済み=#00ff88 / 未検出=#ff8800）
      - プロジェクト名・バージョン表示
      - 完全性スコアプログレスバー（80%以上=緑, 50%以上=黄, 未満=赤）
      - 不足セクション一覧
      - ボタン: [📝 新規作成] [🔄 更新] [📋 詳細]
    - Cyberpunk Minimalテーマ準拠のスタイリング

11. `src/widgets/bible_notification.py` を作成:
    - BibleNotificationWidget(QFrame):
      - チャットエリア上部に表示する通知バー
      - 「📖 BIBLE検出: {name} v{version}」
      - [コンテキストに追加] [無視] ボタン

12. helix_orchestrator_tab.py を修正:
    - 設定タブに BibleStatusPanel を追加（「🔧 ツール設定 (MCP)」の下）
    - ファイル添付時に BibleDiscovery.discover() を呼び出し
    - 結果を BibleStatusPanel.update_bible() で反映
    - チャットエリアに BibleNotificationWidget を表示

13. 「実行」ボタンのハンドラで:
    - プロンプトテキストから BibleDiscovery.discover_from_prompt() 実行
    - 検出されたBIBLEを orchestrator.set_bible_context() で設定

### Phase E: ファイル添付トリガー強化

14. ファイル添付処理を修正:
    - 添付ファイルの拡張子が .md の場合:
      → BibleParser.parse_header() を試行
      → BIBLEファイルなら自動でコンテキストに追加
    - 添付ファイルがソースコード(.py, .js, .ts等)の場合:
      → 親ディレクトリを BibleDiscovery.discover() で探索
    - 添付ファイルがディレクトリパスを含む場合:
      → そのディレクトリを BibleDiscovery.discover() で探索

15. ドラッグ&ドロップ対応:
    - .md ファイルドロップ時もBIBLE判定を実行

### Phase F: 設定・PyInstaller

16. config.json に追加:
    - "bible_auto_discover": true  (BIBLE自動検索有効/無効)
    - "bible_auto_manage": true    (BIBLE自律管理有効/無効)
    - "bible_project_root": ""     (明示的プロジェクトルート)

17. constants.py 更新:
    - APP_VERSION = "8.0.0"
    - APP_CODENAME = "Living Bible"

18. HelixAIStudio.spec の hiddenimports に追加:
    - 'src.bible'
    - 'src.bible.bible_schema'
    - 'src.bible.bible_parser'
    - 'src.bible.bible_discovery'
    - 'src.bible.bible_injector'
    - 'src.bible.bible_lifecycle'
    - 'src.widgets.bible_panel'
    - 'src.widgets.bible_notification'

### 受入条件
□ BIBLE/ディレクトリにBIBLE_*.mdを配置した状態でファイル添付 → 自動検出される
□ 検出通知がチャットエリアに表示される
□ 「コンテキストに追加」→ Phase 1プロンプトに<project_context>が注入される
□ 設定タブにBIBLE Managerパネルが表示される
□ 完全性スコアが正しく計算・表示される
□ 不足セクションが正しく検出・表示される
□ Phase 3完了後にBIBLE更新提案が表示される（ファイル変更時）
□ 「新規作成」ボタンでテンプレートベースのBIBLEが生成される
□ config.jsonのbible_auto_discover/bible_auto_manageで機能ON/OFFが可能
□ PyInstallerビルド成功
□ grep -rn "bible" src/ --include="*.py" | wc -l が50行以上（充分な統合度）
```

---

## 第6部: 将来拡張（v8.1.0以降）

### A. BIBLE差分表示（Diff View）
バージョン間のBIBLE差分をsoloAIの差分表示(Diff)機能と統合。
v7.1.0 BIBLE vs v8.0.0 BIBLEの変更点をハイライト表示。

### B. BIBLE × RAG統合
BIBLEのセクション内容をRAGベクトルDBに自動登録。
ユーザーの質問に対し、BIBLEの関連セクションを自動検索して回答に含める。

### C. マルチプロジェクトBIBLE
複数プロジェクトのBIBLEを同時管理。
プロジェクト切り替え時に自動でコンテキストを差し替え。

### D. BIBLE健全性チェック（CI統合）
GitHub Actionsでプッシュ時にBIBLE完全性スコアを自動計算。
スコアが閾値以下の場合PRにコメントで警告。

### E. BIBLE生成のローカルLLM活用
Phase 2のローカルLLMにBIBLE更新のドラフト作成を担当させ、
Phase 3のClaudeが品質チェック・統合する3Phase BIBLE管理。

---

*この設計書は Claude Opus 4.6 により作成されました*
