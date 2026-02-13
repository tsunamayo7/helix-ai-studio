"""
Helix AI Studio - RAG Lock Overlay (v8.5.0)
RAG構築中にmixAI/soloAIタブに表示するロックオーバーレイ
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..utils.styles import COLORS, PROGRESS_BAR_STYLE, SECONDARY_BTN


class RAGLockOverlay(QWidget):
    """RAG構築中のロックオーバーレイ"""

    navigate_to_rag = pyqtSignal()  # 情報収集タブへ移動シグナル

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.hide()  # 初期非表示

    def _init_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(10, 10, 26, 220);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ロックアイコン + メッセージ
        card = QFrame()
        card.setFixedSize(400, 280)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border: 2px solid {COLORS['accent_cyan']};
                border-radius: 12px;
                padding: 24px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(16)

        # ロックアイコン
        lock_icon = QLabel("RAG構築更新中")
        lock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_icon.setStyleSheet(f"""
            color: {COLORS['accent_cyan']};
            font-size: 18px;
            font-weight: bold;
        """)
        card_layout.addWidget(lock_icon)

        # メッセージ
        self.message_label = QLabel(
            "情報収集タブでRAG構築が進行中です。\n"
            "完了するまでこの機能は使用できません。"
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 13px;
            line-height: 1.5;
        """)
        card_layout.addWidget(self.message_label)

        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self.progress_bar.setMinimumHeight(22)
        card_layout.addWidget(self.progress_bar)

        # 残り時間
        self.remaining_label = QLabel("残り推定: --:--")
        self.remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remaining_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        card_layout.addWidget(self.remaining_label)

        # 情報収集タブへ移動ボタン
        nav_btn = QPushButton("情報収集タブへ移動")
        nav_btn.setStyleSheet(SECONDARY_BTN)
        nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_btn.clicked.connect(self.navigate_to_rag.emit)
        card_layout.addWidget(nav_btn)

        layout.addWidget(card)

    def show_lock(self, progress: int = 0, remaining_text: str = ""):
        """ロック表示"""
        self.progress_bar.setValue(progress)
        if remaining_text:
            self.remaining_label.setText(f"残り推定: {remaining_text}")
        self.show()
        self.raise_()

    def hide_lock(self):
        """ロック解除"""
        self.hide()

    def update_progress(self, progress: int, remaining_text: str = ""):
        """進捗更新"""
        self.progress_bar.setValue(progress)
        if remaining_text:
            self.remaining_label.setText(f"残り推定: {remaining_text}")

    def resizeEvent(self, event):
        """親ウィジェットにフィット"""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
