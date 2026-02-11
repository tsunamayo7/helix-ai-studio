"""
Layout Analyzer - UI Layout Analysis
レイアウトの問題を検出し、改善提案を行う
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import re


@dataclass
class LayoutIssue:
    """レイアウト問題"""
    file_path: str
    line_number: int
    issue_type: str
    description: str
    current_code: str
    suggested_code: str


@dataclass
class LayoutInfo:
    """レイアウト情報"""
    file_path: str
    layout_type: str  # "QVBoxLayout", "QHBoxLayout", "QGridLayout", etc.
    line_number: int
    children_count: int
    has_stretch: bool
    has_spacing: bool


class LayoutAnalyzer:
    """
    Layout Analyzer

    Features:
    - レイアウト構造分析
    - 問題点検出
    - 改善提案生成
    - ベストプラクティスチェック
    """

    # レイアウトタイプのパターン
    LAYOUT_PATTERNS = {
        'QVBoxLayout': r'QVBoxLayout\s*\(',
        'QHBoxLayout': r'QHBoxLayout\s*\(',
        'QGridLayout': r'QGridLayout\s*\(',
        'QFormLayout': r'QFormLayout\s*\(',
        'QStackedLayout': r'QStackedLayout\s*\('
    }

    # 問題パターン
    ISSUE_PATTERNS = {
        'nested_layouts': r'layout\s*=\s*Q[VH]BoxLayout.*\n.*layout\.addLayout',
        'fixed_size': r'\.setFixedSize\s*\(\s*\d+',
        'no_stretch': r'addWidget.*\n(?!.*addStretch)',
        'magic_numbers': r'setContentsMargins\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)'
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.layouts: List[LayoutInfo] = []
        self.issues: List[LayoutIssue] = []

    def analyze_file(self, file_path: str) -> Tuple[List[LayoutInfo], List[LayoutIssue]]:
        """
        ファイルのレイアウトを分析

        Args:
            file_path: ファイルパス

        Returns:
            (レイアウト情報リスト, 問題リスト)
        """
        full_path = self.project_path / file_path
        layouts = []
        issues = []

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # レイアウト検出
            for layout_type, pattern in self.LAYOUT_PATTERNS.items():
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count('\n') + 1
                    layouts.append(LayoutInfo(
                        file_path=file_path,
                        layout_type=layout_type,
                        line_number=line_num,
                        children_count=0,  # TODO: 詳細分析
                        has_stretch='addStretch' in content,
                        has_spacing='setSpacing' in content
                    ))

            # 問題検出
            issues.extend(self._detect_fixed_sizes(file_path, lines))
            issues.extend(self._detect_magic_numbers(file_path, lines))
            issues.extend(self._detect_missing_stretch(file_path, content))

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")

        return layouts, issues

    def _detect_fixed_sizes(self, file_path: str, lines: List[str]) -> List[LayoutIssue]:
        """固定サイズの問題を検出"""
        issues = []
        for i, line in enumerate(lines, 1):
            if 'setFixedSize' in line or 'setFixedWidth' in line or 'setFixedHeight' in line:
                issues.append(LayoutIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="fixed_size",
                    description="固定サイズは異なる画面サイズでレイアウト崩れの原因になります",
                    current_code=line.strip(),
                    suggested_code="setMinimumSize() と setSizePolicy() の組み合わせを検討してください"
                ))
        return issues

    def _detect_magic_numbers(self, file_path: str, lines: List[str]) -> List[LayoutIssue]:
        """マジックナンバーを検出"""
        issues = []
        margin_pattern = r'setContentsMargins\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'

        for i, line in enumerate(lines, 1):
            match = re.search(margin_pattern, line)
            if match:
                values = [int(match.group(j)) for j in range(1, 5)]
                if len(set(values)) > 2:  # 2種類以上の値
                    issues.append(LayoutIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="inconsistent_margins",
                        description="マージン値が不統一です。定数を使用することを推奨します",
                        current_code=line.strip(),
                        suggested_code=f"setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)  # MARGIN = {max(values)}"
                    ))
        return issues

    def _detect_missing_stretch(self, file_path: str, content: str) -> List[LayoutIssue]:
        """ストレッチ不足を検出"""
        issues = []

        # VBoxLayoutがあるがaddStretchがない
        if 'QVBoxLayout' in content and 'addStretch' not in content:
            # ファイル全体に対して1つの警告
            issues.append(LayoutIssue(
                file_path=file_path,
                line_number=0,
                issue_type="missing_stretch",
                description="QVBoxLayoutにaddStretch()がありません。ウィジェットが画面全体に広がる可能性があります",
                current_code="",
                suggested_code="layout.addStretch()  # 最後に追加"
            ))

        return issues

    def analyze_project(self) -> Dict[str, any]:
        """
        プロジェクト全体を分析

        Returns:
            分析結果サマリー
        """
        self.layouts = []
        self.issues = []

        py_files = list(self.project_path.rglob('*.py'))

        for py_file in py_files:
            if '__pycache__' in str(py_file):
                continue

            rel_path = str(py_file.relative_to(self.project_path))
            layouts, issues = self.analyze_file(rel_path)
            self.layouts.extend(layouts)
            self.issues.extend(issues)

        return {
            'total_files': len(py_files),
            'total_layouts': len(self.layouts),
            'total_issues': len(self.issues),
            'layout_types': self._count_layout_types(),
            'issue_types': self._count_issue_types()
        }

    def _count_layout_types(self) -> Dict[str, int]:
        """レイアウトタイプをカウント"""
        counts: Dict[str, int] = {}
        for layout in self.layouts:
            counts[layout.layout_type] = counts.get(layout.layout_type, 0) + 1
        return counts

    def _count_issue_types(self) -> Dict[str, int]:
        """問題タイプをカウント"""
        counts: Dict[str, int] = {}
        for issue in self.issues:
            counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
        return counts

    def get_recommendations(self) -> List[str]:
        """
        改善推奨事項を取得

        Returns:
            推奨事項リスト
        """
        recommendations = []

        issue_counts = self._count_issue_types()

        if issue_counts.get('fixed_size', 0) > 0:
            recommendations.append(
                "固定サイズの使用を避け、レイアウトとサイズポリシーを活用してください"
            )

        if issue_counts.get('inconsistent_margins', 0) > 0:
            recommendations.append(
                "マージン値を定数化して一貫性を保ってください"
            )

        if issue_counts.get('missing_stretch', 0) > 0:
            recommendations.append(
                "VBoxLayoutの最後にaddStretch()を追加して、ウィジェットの配置を制御してください"
            )

        layout_counts = self._count_layout_types()
        if layout_counts.get('QGridLayout', 0) == 0 and len(self.layouts) > 5:
            recommendations.append(
                "複雑なレイアウトにはQGridLayoutの使用を検討してください"
            )

        return recommendations
