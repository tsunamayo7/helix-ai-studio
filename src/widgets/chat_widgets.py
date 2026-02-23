"""
Helix AI Studio - Chat Enhancement Widgets (v9.8.0)
チャットUI強化ウィジェット群:
- PhaseIndicator: 4Phase実行状態の視覚的インジケーター
- CloudAIStatusBar: cloudAI実行状態のシンプルな表示
- ExecutionIndicator: チャットエリア内の実行中インジケーター
- InterruptionBanner: 中断時にチャットエリアに表示するバナー
"""

import time
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from ..utils.styles import (
    PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    phase_node_style, PHASE_ARROW_STYLE,
    PHASE_DOT_INACTIVE, PHASE_TEXT_INACTIVE,
)
from ..utils.i18n import t

logger = logging.getLogger(__name__)


# =============================================================================
# 改善C: PhaseIndicator — 4Phase実行状態の視覚的インジケーター (v9.8.0)
# =============================================================================

class PhaseIndicator(QWidget):
    """4Phase実行状態の視覚的インジケーター (v9.8.0: Phase 4追加)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phases = [
            ("P1", t('desktop.widgets.chatWidgets.p1Label'), "#00d4ff"),
            ("P2", t('desktop.widgets.chatWidgets.p2Label'), "#00ff88"),
            ("P3", t('desktop.widgets.chatWidgets.p3Label'), "#ff9800"),
            ("P4", t('desktop.widgets.chatWidgets.p4Label'), "#9b59b6"),
        ]
        self.current_phase = -1  # -1=未実行
        self._nodes = []
        self._dots = []
        self._texts = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        for i, (label, desc, color) in enumerate(self.phases):
            # Phase ノード
            node = QFrame()
            node.setFixedSize(180, 36)
            node.setStyleSheet(phase_node_style(active=False, color=color))
            node_layout = QHBoxLayout(node)
            node_layout.setContentsMargins(8, 0, 8, 0)
            node_layout.setSpacing(4)

            dot = QLabel("\u25cf")
            dot.setStyleSheet(PHASE_DOT_INACTIVE)
            dot.setFixedWidth(16)

            text = QLabel(f"{label}: {desc}")
            text.setStyleSheet(PHASE_TEXT_INACTIVE)

            node_layout.addWidget(dot)
            node_layout.addWidget(text)

            layout.addWidget(node)
            self._nodes.append(node)
            self._dots.append(dot)
            self._texts.append(text)

            # コネクタ矢印（最後以外）
            if i < len(self.phases) - 1:
                arrow = QLabel("\u2192")
                arrow.setStyleSheet(PHASE_ARROW_STYLE)
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setFixedWidth(30)
                layout.addWidget(arrow)

        layout.addStretch()

    def set_active_phase(self, phase_index: int):
        """アクティブフェーズを設定（0=P1, 1=P2, 2=P3, 3=P4）"""
        self.current_phase = phase_index

        for i, (_, _, color) in enumerate(self.phases):
            if i < phase_index:
                # 完了フェーズ
                self._nodes[i].setStyleSheet(phase_node_style(completed=True, color=color))
                self._dots[i].setText("\u2713")
                self._dots[i].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
                self._texts[i].setStyleSheet(f"color: {color}; font-size: 11px;")
            elif i == phase_index:
                # アクティブフェーズ
                self._nodes[i].setStyleSheet(phase_node_style(active=True, color=color))
                self._dots[i].setText("\u25cf")
                self._dots[i].setStyleSheet(f"color: {color}; font-size: 10px;")
                self._texts[i].setStyleSheet(f"color: #e0e0e0; font-size: 11px; font-weight: bold;")
            else:
                # 未実行フェーズ
                self._nodes[i].setStyleSheet(phase_node_style(active=False, color=color))
                self._dots[i].setText("\u25cf")
                self._dots[i].setStyleSheet(PHASE_DOT_INACTIVE)
                self._texts[i].setStyleSheet(PHASE_TEXT_INACTIVE)

    def set_all_completed(self):
        """全フェーズ完了状態にする"""
        for i, (_, _, color) in enumerate(self.phases):
            self._nodes[i].setStyleSheet(phase_node_style(completed=True, color=color))
            self._dots[i].setText("\u2713")
            self._dots[i].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
            self._texts[i].setStyleSheet(f"color: {color}; font-size: 11px;")
        self.current_phase = len(self.phases)

    def reset(self):
        """未実行状態にリセット"""
        self.current_phase = -1
        for i, (_, _, color) in enumerate(self.phases):
            self._nodes[i].setStyleSheet(phase_node_style(active=False, color=color))
            self._dots[i].setText("\u25cf")
            self._dots[i].setStyleSheet(PHASE_DOT_INACTIVE)
            self._texts[i].setStyleSheet(PHASE_TEXT_INACTIVE)

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        self.phases = [
            ("P1", t('desktop.widgets.chatWidgets.p1Label'), "#00d4ff"),
            ("P2", t('desktop.widgets.chatWidgets.p2Label'), "#00ff88"),
            ("P3", t('desktop.widgets.chatWidgets.p3Label'), "#ff9800"),
            ("P4", t('desktop.widgets.chatWidgets.p4Label'), "#9b59b6"),
        ]
        for i, (label, desc, _color) in enumerate(self.phases):
            self._texts[i].setText(f"{label}: {desc}")


# =============================================================================
# 改善J: CloudAIStatusBar — cloudAI実行状態のシンプルな表示
# =============================================================================

class CloudAIStatusBar(QWidget):
    """cloudAI実行状態の表示（v9.7.1: mixAI形式のヘッダーに統一）"""

    new_session_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        from ..utils.constants import APP_VERSION
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border-bottom: 1px solid #2a2a3e;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # v9.7.1: タイトルラベル（mixAI形式に統一 - 左寄せ）
        self.title_label = QLabel(t('desktop.cloudAI.title'))
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(self.title_label)

        # 新規セッションボタン（タイトルの直後 - mixAIと同じスタイル）
        self.btn_new_session = QPushButton(t('desktop.widgets.chatWidgets.newSession'))
        self.btn_new_session.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_session.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #00ff88;
                border: 1px solid #00ff88;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(0, 255, 136, 0.1);
            }
        """)
        self.btn_new_session.clicked.connect(self.new_session_clicked.emit)
        layout.addWidget(self.btn_new_session)

        # 非表示のステータス管理用（set_status互換）
        self.status_dot = QLabel()
        self.status_dot.setVisible(False)
        self.status_label = QLabel()
        self.status_label.setVisible(False)

    def set_status(self, status: str, color: str = ""):
        """
        ステータスを設定

        status: "waiting" / "running" / "completed" / "error" / "interrupted"
        """
        status_map = {
            "waiting": ("#888", t('desktop.widgets.chatWidgets.statusMap.idle')),
            "running": ("#00d4ff", t('desktop.widgets.chatWidgets.statusMap.running')),
            "completed": ("#00ff88", t('desktop.widgets.chatWidgets.statusMap.completed')),
            "error": ("#ff4444", t('desktop.widgets.chatWidgets.statusMap.error')),
            "interrupted": ("#ff8800", t('desktop.widgets.chatWidgets.statusMap.cancelled')),
        }
        c, text = status_map.get(status, ("#888", status))
        if color:
            c = color
        self.status_dot.setStyleSheet(f"color: {c}; font-size: 10px;")
        self.status_label.setStyleSheet(f"color: {c}; font-size: 12px;")
        self.status_label.setText(text)

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        self.title_label.setText(t('desktop.cloudAI.title'))
        self.status_label.setText(t('desktop.widgets.chatWidgets.statusWaiting'))
        self.btn_new_session.setText(t('desktop.widgets.chatWidgets.newSession'))


# =============================================================================
# 改善K: ExecutionIndicator — チャットエリア内の実行中インジケーター
# =============================================================================

class ExecutionIndicator(QFrame):
    """チャットエリア内の実行中インジケーター"""

    def __init__(self, task_description: str = "", parent=None):
        if not task_description:
            task_description = t('desktop.widgets.chatWidgets.cliRunning')
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #1a1a2e;
                border: 1px solid #00d4ff;
                border-radius: 8px;
                padding: 8px 12px;
                margin: 4px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # アニメーションドット
        self.dots = QLabel("\u25cf \u25cb \u25cb")
        self.dots.setStyleSheet("color: #00d4ff; font-size: 14px;")
        self.dots.setFixedWidth(50)
        layout.addWidget(self.dots)

        # タスク説明
        self.task_label = QLabel(task_description)
        self.task_label.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(self.task_label)

        layout.addStretch()

        # 経過時間
        self.time_label = QLabel("0:00")
        self.time_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.time_label)

        # タイマー
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._start_time: Optional[float] = None
        self._dot_index = 0

    def start(self):
        """タイマー開始"""
        self._start_time = time.time()
        self._timer.start(500)

    def stop(self):
        """タイマー停止"""
        self._timer.stop()

    def _update(self):
        """経過時間とドットアニメーション更新"""
        if self._start_time:
            elapsed = int(time.time() - self._start_time)
            minutes, seconds = divmod(elapsed, 60)
            self.time_label.setText(f"{minutes}:{seconds:02d}")

        dots_patterns = ["\u25cf \u25cb \u25cb", "\u25cb \u25cf \u25cb", "\u25cb \u25cb \u25cf"]
        self._dot_index = (self._dot_index + 1) % 3
        self.dots.setText(dots_patterns[self._dot_index])


# =============================================================================
# 改善L: InterruptionBanner — 中断時にチャットエリアに表示するバナー
# =============================================================================

class InterruptionBanner(QFrame):
    """中断時にチャットエリアに表示するバナー"""

    continue_clicked = pyqtSignal()
    retry_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()

    def __init__(self, reason: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #2a1a0a;
                border: 1px solid #ff8800;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 中断ヘッダー
        header = QLabel(t('desktop.widgets.chatWidgets.interruptedHeader'))
        header.setStyleSheet("color: #ff8800; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        # 中断理由
        self.reason_label = QLabel(reason)
        self.reason_label.setStyleSheet("color: #ccc; font-size: 12px;")
        self.reason_label.setWordWrap(True)
        layout.addWidget(self.reason_label)

        # アクションボタン
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_continue = QPushButton(t('desktop.widgets.chatWidgets.continueBtn'))
        btn_continue.setStyleSheet(PRIMARY_BTN + "QPushButton { padding: 5px 16px; font-size: 12px; }")
        btn_continue.setToolTip(t('desktop.widgets.chatWidgets.continueBtnTip'))
        btn_continue.clicked.connect(self.continue_clicked.emit)
        btn_layout.addWidget(btn_continue)

        btn_retry = QPushButton(t('desktop.widgets.chatWidgets.retryBtn'))
        btn_retry.setStyleSheet(SECONDARY_BTN + "QPushButton { padding: 5px 16px; font-size: 12px; }")
        btn_retry.setToolTip(t('desktop.widgets.chatWidgets.retryBtnTip'))
        btn_retry.clicked.connect(self.retry_clicked.emit)
        btn_layout.addWidget(btn_retry)

        btn_cancel = QPushButton(t('desktop.widgets.chatWidgets.cancelBtn'))
        btn_cancel.setStyleSheet(DANGER_BTN + "QPushButton { padding: 5px 16px; font-size: 12px; }")
        btn_cancel.setToolTip(t('desktop.widgets.chatWidgets.cancelBtnTip'))
        btn_cancel.clicked.connect(self.cancel_clicked.emit)
        btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_reason(self, reason: str):
        """中断理由を更新"""
        self.reason_label.setText(reason)
