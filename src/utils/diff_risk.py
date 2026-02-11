"""
Diff Risk - Diff危険度の自動算出
差分を解析し、リスクスコアとレベルを算出する
"""
import re
import json
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path


# 危険度判定の閾値（安全側に倒す）
BULK_EDIT_FILE_THRESHOLD = 5      # ファイル数が5以上で大量編集
BULK_EDIT_LINES_THRESHOLD = 300   # 変更行数が300以上で大量編集

# センシティブなファイルパターン（正規表現）
SENSITIVE_PATTERNS = [
    r'\.env',
    r'\.env\.',
    r'config',
    r'auth',
    r'key',
    r'credential',
    r'secret',
    r'password',
    r'token',
    r'api[_-]?key',
    r'private',
    r'\.pem',
    r'\.key',
    r'\.cert',
]


@dataclass
class DiffRiskReport:
    """
    Diff危険度レポート

    Attributes:
        files_changed: 変更されたファイル数
        lines_added: 追加された行数
        lines_deleted: 削除された行数
        files_deleted: ファイル削除を含むか
        touches_sensitive: センシティブなファイルに触れるか
        outside_project_paths: プロジェクト外パスへのアクセスを含むか
        bulk_edit: 大量編集に該当するか
        risk_score: リスクスコア（0-100）
        risk_level: リスクレベル（LOW/MEDIUM/HIGH）
        reasons: リスク理由のリスト
        sensitive_files: センシティブと判定されたファイルのリスト
        deleted_files: 削除されたファイルのリスト
    """
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    files_deleted: bool = False
    touches_sensitive: bool = False
    outside_project_paths: bool = False
    bulk_edit: bool = False
    risk_score: int = 0
    risk_level: str = "LOW"
    reasons: List[str] = field(default_factory=list)
    sensitive_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiffRiskReport':
        """辞書から復元"""
        return cls(**data)

    def to_json(self) -> str:
        """JSON文字列に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def get_summary_text(self) -> str:
        """サマリーテキストを取得"""
        text = f"【危険度評価】\n"
        text += f"リスクレベル: {self.risk_level} (スコア: {self.risk_score}/100)\n"
        text += f"変更ファイル数: {self.files_changed}\n"
        text += f"追加行数: +{self.lines_added} / 削除行数: -{self.lines_deleted}\n"

        if self.reasons:
            text += f"\n【リスク要因】\n"
            for i, reason in enumerate(self.reasons[:5], 1):  # 上位5つ
                text += f"{i}. {reason}\n"

        if self.sensitive_files:
            text += f"\n【センシティブファイル】\n"
            for f in self.sensitive_files[:3]:
                text += f"  - {f}\n"

        if self.deleted_files:
            text += f"\n【削除ファイル】\n"
            for f in self.deleted_files[:3]:
                text += f"  - {f}\n"

        return text


class DiffRiskAnalyzer:
    """
    Diff危険度解析クラス

    Unified Diff形式の差分を解析し、危険度を算出する
    """

    def __init__(self, project_root: str = "."):
        """
        初期化

        Args:
            project_root: プロジェクトルートパス
        """
        self.project_root = Path(project_root).resolve()

    def analyze_diff(self, diff_text: str) -> DiffRiskReport:
        """
        Diffテキストを解析し、危険度レポートを生成

        Args:
            diff_text: Unified Diff形式のテキスト

        Returns:
            DiffRiskReport インスタンス
        """
        report = DiffRiskReport()

        # ファイル単位で解析
        file_diffs = self._parse_unified_diff(diff_text)

        report.files_changed = len(file_diffs)

        for file_diff in file_diffs:
            file_path = file_diff["file_path"]
            lines_added = file_diff["lines_added"]
            lines_deleted = file_diff["lines_deleted"]
            is_deleted = file_diff["is_deleted"]

            report.lines_added += lines_added
            report.lines_deleted += lines_deleted

            # ファイル削除チェック
            if is_deleted:
                report.files_deleted = True
                report.deleted_files.append(file_path)

            # センシティブファイルチェック
            if self._is_sensitive_file(file_path):
                report.touches_sensitive = True
                report.sensitive_files.append(file_path)

            # プロジェクト外パスチェック
            if self._is_outside_project(file_path):
                report.outside_project_paths = True

        # 大量編集判定
        total_lines_changed = report.lines_added + report.lines_deleted
        if (report.files_changed >= BULK_EDIT_FILE_THRESHOLD or
            total_lines_changed >= BULK_EDIT_LINES_THRESHOLD):
            report.bulk_edit = True

        # リスクスコアとレベルを算出
        report.risk_score, report.risk_level, report.reasons = self._calculate_risk(report)

        return report

    def _parse_unified_diff(self, diff_text: str) -> List[Dict[str, Any]]:
        """
        Unified Diff形式のテキストを解析

        Returns:
            ファイル単位の差分情報リスト
        """
        file_diffs = []
        current_file = None
        lines_added = 0
        lines_deleted = 0

        for line in diff_text.split('\n'):
            # 新しいファイルの開始
            if line.startswith('diff --git') or line.startswith('--- '):
                # 前のファイル情報を保存
                if current_file:
                    file_diffs.append({
                        "file_path": current_file,
                        "lines_added": lines_added,
                        "lines_deleted": lines_deleted,
                        "is_deleted": lines_deleted > 0 and lines_added == 0,
                    })
                    lines_added = 0
                    lines_deleted = 0

                # ファイル名を抽出
                if line.startswith('diff --git'):
                    parts = line.split()
                    if len(parts) >= 4:
                        current_file = parts[2].lstrip('a/')
                elif line.startswith('---'):
                    current_file = line.split()[1].lstrip('a/')

            # 追加行
            elif line.startswith('+') and not line.startswith('+++'):
                lines_added += 1

            # 削除行
            elif line.startswith('-') and not line.startswith('---'):
                lines_deleted += 1

        # 最後のファイル情報を保存
        if current_file:
            file_diffs.append({
                "file_path": current_file,
                "lines_added": lines_added,
                "lines_deleted": lines_deleted,
                "is_deleted": lines_deleted > 0 and lines_added == 0,
            })

        return file_diffs

    def _is_sensitive_file(self, file_path: str) -> bool:
        """
        ファイルパスがセンシティブかどうか判定

        Args:
            file_path: ファイルパス

        Returns:
            センシティブな場合True
        """
        file_path_lower = file_path.lower()
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, file_path_lower):
                return True
        return False

    def _is_outside_project(self, file_path: str) -> bool:
        """
        ファイルパスがプロジェクト外かどうか判定

        Args:
            file_path: ファイルパス

        Returns:
            プロジェクト外の場合True
        """
        try:
            # 絶対パスに変換
            abs_path = Path(file_path).resolve()
            # プロジェクトルートとの相対パスを取得
            abs_path.relative_to(self.project_root)
            return False
        except (ValueError, Exception):
            # 相対パスが取得できない = プロジェクト外
            return True

    def _calculate_risk(self, report: DiffRiskReport) -> Tuple[int, str, List[str]]:
        """
        リスクスコアとレベルを算出

        Args:
            report: DiffRiskReport（算出前）

        Returns:
            (risk_score, risk_level, reasons)
        """
        score = 0
        reasons = []

        # ファイル削除（+30点）
        if report.files_deleted:
            score += 30
            reasons.append(f"ファイル削除を含む（{len(report.deleted_files)}ファイル）")

        # センシティブファイル（+25点）
        if report.touches_sensitive:
            score += 25
            reasons.append(f"センシティブなファイルへの変更（{len(report.sensitive_files)}ファイル）")

        # プロジェクト外アクセス（+30点）
        if report.outside_project_paths:
            score += 30
            reasons.append("プロジェクト外パスへのアクセス")

        # 大量編集（+20点）
        if report.bulk_edit:
            score += 20
            total_lines = report.lines_added + report.lines_deleted
            reasons.append(
                f"大量編集（{report.files_changed}ファイル、{total_lines}行変更）"
            )

        # ファイル数ボーナス（1ファイルあたり+2点、最大20点）
        file_score = min(report.files_changed * 2, 20)
        score += file_score

        # 行数ボーナス（100行あたり+5点、最大15点）
        total_lines = report.lines_added + report.lines_deleted
        lines_score = min((total_lines // 100) * 5, 15)
        score += lines_score

        if report.files_changed >= 3:
            reasons.append(f"複数ファイル変更（{report.files_changed}ファイル）")

        if total_lines >= 200:
            reasons.append(f"大規模な行変更（+{report.lines_added}/-{report.lines_deleted}行）")

        # スコアを0-100に制限
        score = min(score, 100)

        # レベル判定
        if score >= 60:
            level = "HIGH"
        elif score >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        return score, level, reasons

    def analyze_file_list(self, changed_files: List[str]) -> DiffRiskReport:
        """
        変更ファイルリストから簡易的な危険度を算出

        Args:
            changed_files: 変更されたファイルパスのリスト

        Returns:
            DiffRiskReport インスタンス
        """
        report = DiffRiskReport()
        report.files_changed = len(changed_files)

        for file_path in changed_files:
            # センシティブファイルチェック
            if self._is_sensitive_file(file_path):
                report.touches_sensitive = True
                report.sensitive_files.append(file_path)

            # プロジェクト外パスチェック
            if self._is_outside_project(file_path):
                report.outside_project_paths = True

        # 大量編集判定（ファイル数のみ）
        if report.files_changed >= BULK_EDIT_FILE_THRESHOLD:
            report.bulk_edit = True

        # リスクスコアとレベルを算出
        report.risk_score, report.risk_level, report.reasons = self._calculate_risk(report)

        return report


def analyze_diff(diff_text: str, project_root: str = ".") -> DiffRiskReport:
    """
    Diffテキストを解析する便利関数

    Args:
        diff_text: Unified Diff形式のテキスト
        project_root: プロジェクトルートパス

    Returns:
        DiffRiskReport インスタンス
    """
    analyzer = DiffRiskAnalyzer(project_root)
    return analyzer.analyze_diff(diff_text)


def analyze_file_list(changed_files: List[str], project_root: str = ".") -> DiffRiskReport:
    """
    変更ファイルリストを解析する便利関数

    Args:
        changed_files: 変更されたファイルパスのリスト
        project_root: プロジェクトルートパス

    Returns:
        DiffRiskReport インスタンス
    """
    analyzer = DiffRiskAnalyzer(project_root)
    return analyzer.analyze_file_list(changed_files)
