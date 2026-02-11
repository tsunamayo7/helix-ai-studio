"""
UI Refiner - Gemini UI Refinement Pipeline
Reference: Gemini CLI Agent Mode

作成されたアプリのUI調整、QSS生成、レイアウト修正を自動化
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum


class RefinerMode(Enum):
    """Refinerモード"""
    ANALYSIS = "analysis"
    VISUALIZATION = "visualization"
    PROPOSAL = "proposal"
    APPLICATION = "application"


@dataclass
class UIIssue:
    """UI問題点"""
    file_path: str
    line_number: Optional[int]
    issue_type: str  # "layout", "style", "accessibility", "consistency"
    description: str
    severity: str  # "low", "medium", "high"
    suggestion: str


@dataclass
class UIProposal:
    """UI修正提案"""
    file_path: str
    original_content: str
    proposed_content: str
    description: str
    issues_addressed: List[str]


class UIRefiner:
    """
    UI Refiner Pipeline

    Process:
    1. Analysis - GUI関連ファイルを読み込み
    2. Visualization - スクリーンショット認識でレイアウト崩れを特定
    3. Proposal - QSS修正案やレイアウト変更を提案
    4. Application - ユーザー承認後、スタイルファイルを書き換え
    """

    # GUI関連ファイルパターン
    GUI_FILE_PATTERNS = [
        'main_window.py',
        '*_tab.py',
        '*_widget.py',
        '*_dialog.py',
        'styles.py',
        '*.qss',
        'styles/*.qss'
    ]

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issues: List[UIIssue] = []
        self.proposals: List[UIProposal] = []
        self.gui_files: List[str] = []

    def scan_gui_files(self) -> List[str]:
        """
        GUI関連ファイルをスキャン

        Returns:
            GUI関連ファイルパスのリスト
        """
        self.gui_files = []

        for pattern in self.GUI_FILE_PATTERNS:
            for file_path in self.project_path.rglob(pattern):
                rel_path = str(file_path.relative_to(self.project_path))
                if '__pycache__' not in rel_path:
                    self.gui_files.append(rel_path)

        return self.gui_files

    def analyze(self) -> List[UIIssue]:
        """
        Phase 1: Analysis
        GUI関連ファイルを分析して問題点を検出

        Returns:
            検出した問題点リスト
        """
        self.issues = []

        for file_path in self.gui_files:
            full_path = self.project_path / file_path
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 簡易的なUIパターン検出
                issues = self._analyze_file(file_path, content)
                self.issues.extend(issues)

            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")

        return self.issues

    def _analyze_file(self, file_path: str, content: str) -> List[UIIssue]:
        """
        ファイルを分析して問題点を検出

        Args:
            file_path: ファイルパス
            content: ファイル内容

        Returns:
            検出した問題点リスト
        """
        issues = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # ハードコードされたサイズ
            if 'setFixedSize' in line or 'setMinimumSize' in line:
                issues.append(UIIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="layout",
                    description="Fixed size detected - may cause layout issues on different screens",
                    severity="medium",
                    suggestion="Consider using layouts with stretch factors instead"
                ))

            # ハードコードされた色
            if '#' in line and ('setStyleSheet' in line or 'background' in line.lower()):
                if not 'qss' in file_path.lower():
                    issues.append(UIIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="style",
                        description="Hardcoded color in Python file",
                        severity="low",
                        suggestion="Move color definitions to QSS file for easier theming"
                    ))

            # マジックナンバー（余白等）
            import re
            margin_pattern = r'setContentsMargins\s*\(\s*(\d+)'
            if re.search(margin_pattern, line):
                issues.append(UIIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="consistency",
                    description="Hardcoded margins detected",
                    severity="low",
                    suggestion="Define margin constants for consistency"
                ))

        return issues

    def generate_proposals(self) -> List[UIProposal]:
        """
        Phase 3: Proposal
        問題点に対する修正提案を生成

        Returns:
            修正提案リスト
        """
        self.proposals = []

        # 問題点をファイルごとにグループ化
        issues_by_file: Dict[str, List[UIIssue]] = {}
        for issue in self.issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue)

        # 各ファイルの修正提案を生成
        for file_path, file_issues in issues_by_file.items():
            proposal = self._generate_file_proposal(file_path, file_issues)
            if proposal:
                self.proposals.append(proposal)

        return self.proposals

    def _generate_file_proposal(
        self,
        file_path: str,
        issues: List[UIIssue]
    ) -> Optional[UIProposal]:
        """
        ファイルの修正提案を生成

        Args:
            file_path: ファイルパス
            issues: このファイルの問題点リスト

        Returns:
            修正提案、問題がなければNone
        """
        full_path = self.project_path / file_path
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                original = f.read()

            # 簡易的な修正提案（実際にはGeminiが生成）
            descriptions = [f"- {i.description}" for i in issues]
            description = "Proposed changes:\n" + "\n".join(descriptions)

            return UIProposal(
                file_path=file_path,
                original_content=original,
                proposed_content=original,  # 実際にはGeminiが修正版を生成
                description=description,
                issues_addressed=[i.description for i in issues]
            )
        except Exception:
            return None

    def apply_proposal(
        self,
        proposal: UIProposal,
        backup: bool = True
    ) -> bool:
        """
        Phase 4: Application
        修正提案を適用

        Args:
            proposal: 適用する提案
            backup: バックアップを作成するか

        Returns:
            成功かどうか
        """
        full_path = self.project_path / proposal.file_path

        try:
            # バックアップ作成
            if backup:
                backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                with open(full_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)

            # 修正を適用
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(proposal.proposed_content)

            return True
        except Exception as e:
            print(f"Error applying proposal: {e}")
            return False

    def get_summary(self) -> Dict[str, Any]:
        """
        分析サマリーを取得

        Returns:
            サマリー辞書
        """
        severity_counts = {'low': 0, 'medium': 0, 'high': 0}
        type_counts: Dict[str, int] = {}

        for issue in self.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1

        return {
            'total_files': len(self.gui_files),
            'total_issues': len(self.issues),
            'severity_breakdown': severity_counts,
            'type_breakdown': type_counts,
            'proposals_count': len(self.proposals)
        }
