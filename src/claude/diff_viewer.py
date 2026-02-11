"""
Diff Viewer - Diff表示と危険度評価
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter

from ..utils.diff_risk import DiffRiskReport, analyze_diff
from ..security.risk_gate import RiskGate, ApprovalScope


class DiffSyntaxHighlighter(QSyntaxHighlighter):
    """Diff表示用のシンタックスハイライター"""

    def highlightBlock(self, text: str):
        """ブロックごとのハイライト処理"""
        # 追加行（緑）
        if text.startswith('+') and not text.startswith('+++'):
            format = QTextCharFormat()
            format.setForeground(QColor("#22c55e"))
            self.setFormat(0, len(text), format)

        # 削除行（赤）
        elif text.startswith('-') and not text.startswith('---'):
            format = QTextCharFormat()
            format.setForeground(QColor("#ef4444"))
            self.setFormat(0, len(text), format)

        # ファイルヘッダ（青）
        elif text.startswith('diff --git') or text.startswith('+++') or text.startswith('---'):
            format = QTextCharFormat()
            format.setForeground(QColor("#3b82f6"))
            format.setFontWeight(QFont.Weight.Bold)
            self.setFormat(0, len(text), format)

        # ハンク情報（シアン）
        elif text.startswith('@@'):
            format = QTextCharFormat()
            format.setForeground(QColor("#06b6d4"))
            self.setFormat(0, len(text), format)


class DiffViewerDialog(QDialog):
    """
    Diff表示ダイアログ

    - Diffのプレビュー
    - 危険度サマリ表示
    - Risk Gate承認チェック
    - 適用確認
    """

    applyRequested = pyqtSignal(str)  # Diffテキストを送信

    def __init__(
        self,
        diff_text: str,
        risk_gate: RiskGate,
        project_root: str = ".",
        parent=None
    ):
        """
        初期化

        Args:
            diff_text: Unified Diff形式のテキスト
            risk_gate: RiskGateインスタンス
            project_root: プロジェクトルートパス
            parent: 親ウィジェット
        """
        super().__init__(parent)
        self.diff_text = diff_text
        self.risk_gate = risk_gate
        self.project_root = project_root

        # 危険度解析
        self.risk_report = analyze_diff(diff_text, project_root)

        self.setWindowTitle("Diff プレビュー - 危険度評価")
        self.setMinimumSize(900, 700)
        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 危険度サマリセクション
        risk_group = self._create_risk_summary_section()
        layout.addWidget(risk_group)

        # Diffプレビューセクション
        diff_group = self._create_diff_preview_section()
        layout.addWidget(diff_group, stretch=1)

        # ボタンセクション
        button_layout = self._create_button_section()
        layout.addLayout(button_layout)

    def _create_risk_summary_section(self) -> QGroupBox:
        """危険度サマリセクションを作成"""
        group = QGroupBox("危険度サマリ")
        layout = QVBoxLayout(group)

        # リスクレベル表示
        risk_level_label = QLabel()
        risk_level_label.setFont(QFont("Yu Gothic UI", 12, QFont.Weight.Bold))

        if self.risk_report.risk_level == "HIGH":
            risk_level_label.setText(f"⚠️ リスクレベル: HIGH (スコア: {self.risk_report.risk_score}/100)")
            risk_level_label.setStyleSheet("color: #ef4444; background-color: #fee2e2; padding: 8px; border-radius: 4px;")
        elif self.risk_report.risk_level == "MEDIUM":
            risk_level_label.setText(f"⚠️ リスクレベル: MEDIUM (スコア: {self.risk_report.risk_score}/100)")
            risk_level_label.setStyleSheet("color: #f59e0b; background-color: #fef3c7; padding: 8px; border-radius: 4px;")
        else:
            risk_level_label.setText(f"✓ リスクレベル: LOW (スコア: {self.risk_report.risk_score}/100)")
            risk_level_label.setStyleSheet("color: #22c55e; background-color: #dcfce7; padding: 8px; border-radius: 4px;")

        layout.addWidget(risk_level_label)

        # 統計情報
        stats_text = (
            f"変更ファイル数: {self.risk_report.files_changed} | "
            f"追加: +{self.risk_report.lines_added}行 | "
            f"削除: -{self.risk_report.lines_deleted}行"
        )
        if self.risk_report.files_deleted:
            stats_text += f" | ファイル削除: {len(self.risk_report.deleted_files)}件"

        stats_label = QLabel(stats_text)
        stats_label.setFont(QFont("Yu Gothic UI", 10))
        layout.addWidget(stats_label)

        # リスク要因
        if self.risk_report.reasons:
            reasons_label = QLabel("【リスク要因】")
            reasons_label.setFont(QFont("Yu Gothic UI", 10, QFont.Weight.Bold))
            layout.addWidget(reasons_label)

            reasons_text = "\n".join(f"• {reason}" for reason in self.risk_report.reasons[:5])
            reasons_display = QLabel(reasons_text)
            reasons_display.setFont(QFont("Yu Gothic UI", 9))
            reasons_display.setWordWrap(True)
            layout.addWidget(reasons_display)

        # センシティブファイル警告
        if self.risk_report.touches_sensitive:
            sensitive_label = QLabel("⚠️ センシティブなファイルへの変更が含まれています")
            sensitive_label.setStyleSheet("color: #dc2626; font-weight: bold;")
            layout.addWidget(sensitive_label)

            if self.risk_report.sensitive_files:
                files_text = ", ".join(self.risk_report.sensitive_files[:3])
                if len(self.risk_report.sensitive_files) > 3:
                    files_text += f" 他{len(self.risk_report.sensitive_files) - 3}件"
                files_label = QLabel(f"対象: {files_text}")
                files_label.setFont(QFont("Yu Gothic UI", 9))
                files_label.setWordWrap(True)
                layout.addWidget(files_label)

        return group

    def _create_diff_preview_section(self) -> QGroupBox:
        """Diffプレビューセクションを作成"""
        group = QGroupBox("差分プレビュー")
        layout = QVBoxLayout(group)

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Consolas", 9))
        self.diff_view.setPlainText(self.diff_text)

        # シンタックスハイライトを適用
        self.highlighter = DiffSyntaxHighlighter(self.diff_view.document())

        layout.addWidget(self.diff_view)

        return group

    def _create_button_section(self) -> QHBoxLayout:
        """ボタンセクションを作成"""
        layout = QHBoxLayout()
        layout.addStretch()

        # キャンセルボタン
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        # 適用ボタン
        self.apply_btn = QPushButton("適用する")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._on_apply)

        # HIGH判定の場合、警告スタイル
        if self.risk_report.risk_level == "HIGH":
            self.apply_btn.setStyleSheet(
                "background-color: #dc2626; color: white; font-weight: bold; padding: 8px 16px;"
            )
            self.apply_btn.setText("⚠️ 適用する（HIGH RISK）")

        layout.addWidget(self.apply_btn)

        return layout

    def _on_apply(self):
        """適用ボタン押下時の処理"""
        # Risk Gateチェック
        allowed, message = self._check_risk_gate()

        if not allowed:
            # 承認不足の場合、エラーダイアログを表示
            QMessageBox.critical(
                self,
                "承認不足",
                f"この操作には承認が必要です。\n\n{message}\n\n"
                "S3 Risk Gateで必要な承認を行ってから再度お試しください。"
            )
            return

        # HIGH判定の場合、再確認
        if self.risk_report.risk_level == "HIGH":
            reply = QMessageBox.warning(
                self,
                "高リスク操作の確認",
                f"この操作は高リスクと判定されました。\n\n"
                f"リスクスコア: {self.risk_report.risk_score}/100\n\n"
                f"主な要因:\n" + "\n".join(f"• {r}" for r in self.risk_report.reasons[:3]) + "\n\n"
                f"本当に適用しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        # 適用シグナルを送信
        self.applyRequested.emit(self.diff_text)
        self.accept()

    def _check_risk_gate(self) -> tuple:
        """
        Risk Gateチェックを実行

        Returns:
            (許可されるか, エラーメッセージ)
        """
        required_scopes = set()

        # 基本的な書き込み権限
        required_scopes.add(ApprovalScope.FS_WRITE)

        # ファイル削除
        if self.risk_report.files_deleted:
            required_scopes.add(ApprovalScope.FS_DELETE)

        # 大量編集
        if self.risk_report.bulk_edit:
            required_scopes.add(ApprovalScope.BULK_EDIT)

        # プロジェクト外アクセス
        if self.risk_report.outside_project_paths:
            required_scopes.add(ApprovalScope.OUTSIDE_PROJECT)

        # Risk Gateでチェック
        return self.risk_gate.check_operation(
            "Diff適用",
            required_scopes,
            {"risk_report": self.risk_report.to_dict()}
        )


def show_diff_viewer(
    diff_text: str,
    risk_gate: RiskGate,
    project_root: str = ".",
    parent=None
) -> tuple:
    """
    Diff Viewerダイアログを表示

    Args:
        diff_text: Unified Diff形式のテキスト
        risk_gate: RiskGateインスタンス
        project_root: プロジェクトルートパス
        parent: 親ウィジェット

    Returns:
        (承認されたか, DiffRiskReport)
    """
    dialog = DiffViewerDialog(diff_text, risk_gate, project_root, parent)
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted, dialog.risk_report
