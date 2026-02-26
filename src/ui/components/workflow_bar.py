"""
Workflow Bar - 全タブ共通の工程バー
工程状態を表示する共通UIコンポーネント
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...utils.constants import WorkflowPhase
from ...utils.i18n import t
from ...utils.styles import COLORS
from ...utils.style_helpers import SS


class WorkflowBar(QFrame):
    """
    全タブ共通の工程バーコンポーネント

    Features:
    - 現在工程の表示
    - 進捗バー
    - 成果物フラグのミニ表示
    - Claude Codeタブのみ: Prev/Nextボタン
    - 他タブ: 参照専用
    """

    # シグナル
    prevClicked = pyqtSignal()
    nextClicked = pyqtSignal()
    resetClicked = pyqtSignal()
    riskApprovalChanged = pyqtSignal(bool)

    def __init__(self, show_controls: bool = False, parent=None):
        """
        初期化

        Args:
            show_controls: Prev/Next/Resetボタンを表示するか（Claude Codeタブのみtrue）
            parent: 親ウィジェット
        """
        super().__init__(parent)
        self.show_controls = show_controls
        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        self.setObjectName("workflowFrame")
        self.setStyleSheet(f"#workflowFrame {{ background-color: {COLORS['bg_card']}; border-bottom: 2px solid {COLORS['accent_dim']}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 上段: 工程名と進捗バー
        top_layout = QHBoxLayout()

        # 工程名ラベル
        self.phase_label = QLabel(t('desktop.workflowBar.defaultPhase'))
        self.phase_label.setFont(QFont("Yu Gothic UI", 11, QFont.Weight.Bold))
        self.phase_label.setStyleSheet(SS.info())
        top_layout.addWidget(self.phase_label)

        top_layout.addStretch()

        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        top_layout.addWidget(self.progress_bar)

        layout.addLayout(top_layout)

        # 中段: 工程の説明と成果物フラグ
        middle_layout = QHBoxLayout()

        # 工程の説明
        self.phase_desc_label = QLabel(t('desktop.workflowBar.defaultDesc'))
        self.phase_desc_label.setStyleSheet(SS.dim("9pt"))
        middle_layout.addWidget(self.phase_desc_label)

        middle_layout.addStretch()

        # 成果物フラグのミニ表示
        self.flags_label = QLabel("")
        self.flags_label.setStyleSheet(SS.dim("9pt"))
        self.flags_label.setToolTip(t('desktop.workflowBar.flagsTooltip'))
        middle_layout.addWidget(self.flags_label)

        layout.addLayout(middle_layout)

        # 下段: コントロール（Claude Codeタブのみ）
        if self.show_controls:
            bottom_layout = QHBoxLayout()

            # Prevボタン
            self.prev_btn = QPushButton("◀ Prev")
            self.prev_btn.setToolTip(t('desktop.workflowBar.prevTooltip'))
            self.prev_btn.setMaximumWidth(100)
            self.prev_btn.clicked.connect(self.prevClicked.emit)
            bottom_layout.addWidget(self.prev_btn)

            # Nextボタン
            self.next_btn = QPushButton("Next ▶")
            self.next_btn.setToolTip(t('desktop.workflowBar.nextTooltip'))
            self.next_btn.setMaximumWidth(100)
            self.next_btn.clicked.connect(self.nextClicked.emit)
            bottom_layout.addWidget(self.next_btn)

            bottom_layout.addSpacing(20)

            # S3承認チェックボックス（S3のみ表示）
            self.risk_approval_checkbox = QCheckBox(t('desktop.workflowBar.riskApprovalLabel'))
            self.risk_approval_checkbox.setToolTip(t('desktop.workflowBar.riskApprovalTooltip'))
            self.risk_approval_checkbox.setVisible(False)
            self.risk_approval_checkbox.stateChanged.connect(self._on_risk_approval_changed)
            bottom_layout.addWidget(self.risk_approval_checkbox)

            bottom_layout.addStretch()

            # リセットボタン
            self.reset_workflow_btn = QPushButton(t('desktop.workflowBar.resetBtn'))
            self.reset_workflow_btn.setToolTip(t('desktop.workflowBar.resetTooltip'))
            self.reset_workflow_btn.setMaximumWidth(120)
            self.reset_workflow_btn.clicked.connect(self.resetClicked.emit)
            bottom_layout.addWidget(self.reset_workflow_btn)

            layout.addLayout(bottom_layout)

    def _on_risk_approval_changed(self, state):
        """S3承認チェックボックスの状態変更"""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.riskApprovalChanged.emit(is_checked)

    def update_workflow_state(self, workflow_state):
        """
        工程状態を更新

        Args:
            workflow_state: WorkflowStateMachine インスタンス
        """
        phase_info = workflow_state.get_current_phase_info()

        # 工程名と説明を更新
        self.phase_label.setText(phase_info["name"])
        self.phase_desc_label.setText(phase_info["description"])

        # 進捗バーを更新
        progress = workflow_state.get_progress_percentage()
        self.progress_bar.setValue(progress)

        # 成果物フラグを更新
        self._update_flags_display(workflow_state.flags)

        # コントロールがある場合のみボタンを更新
        if self.show_controls:
            # Prev/Nextボタンの有効/無効を更新
            can_prev, _ = workflow_state.can_transition_prev()
            self.prev_btn.setEnabled(can_prev)

            can_next, next_msg = workflow_state.can_transition_next()
            self.next_btn.setEnabled(can_next)
            if not can_next:
                self.next_btn.setToolTip(t('desktop.workflowBar.nextDisabledTooltip', msg=next_msg))
            else:
                self.next_btn.setToolTip(t('desktop.workflowBar.nextTooltip'))

            # S3承認チェックボックスの表示/非表示
            if workflow_state.current_phase == WorkflowPhase.S3_RISK_GATE:
                self.risk_approval_checkbox.setVisible(True)
                is_approved = workflow_state.get_flag("risk_approved")
                # stateChangedシグナルをブロックしてから更新
                self.risk_approval_checkbox.blockSignals(True)
                self.risk_approval_checkbox.setChecked(is_approved)
                self.risk_approval_checkbox.blockSignals(False)
            else:
                self.risk_approval_checkbox.setVisible(False)

    def _update_flags_display(self, flags: dict):
        """
        成果物フラグの表示を更新

        Args:
            flags: フラグの辞書
        """
        # 主要フラグのみ表示
        display_flags = []

        if flags.get("has_context"):
            display_flags.append("Context✅")
        if flags.get("has_plan"):
            display_flags.append("Plan✅")
        else:
            display_flags.append("Plan❌")

        if flags.get("risk_approved"):
            display_flags.append("Approval✅")
        else:
            display_flags.append("Approval❌")

        if flags.get("tests_passed"):
            display_flags.append("Tests✅")
        else:
            display_flags.append("Tests❌")

        self.flags_label.setText(" | ".join(display_flags))
