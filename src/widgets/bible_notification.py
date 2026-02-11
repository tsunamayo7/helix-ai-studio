"""
Helix AI Studio - BIBLE Notification Widget (v8.0.0)
BIBLE検出時にチャットエリア上部に表示する通知バー
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from ..utils.styles import BIBLE_NOTIFICATION_STYLE
from ..bible.bible_schema import BibleInfo

logger = logging.getLogger(__name__)


class BibleNotificationWidget(QFrame):
    """
    BIBLE検出通知ウィジェット（チャットエリア上部に表示）

    表示:
    - 「BIBLE検出: {name} v{version} "{codename}"」
    - [コンテキストに追加] [無視] ボタン
    """

    add_clicked = pyqtSignal(object)    # BibleInfo を通知
    dismiss_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bible: Optional[BibleInfo] = None
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        self.setStyleSheet(BIBLE_NOTIFICATION_STYLE)
        self.setMaximumHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # 情報ラベル
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        layout.addWidget(self.info_label, stretch=1)

        # コンテキストに追加ボタン
        self.btn_add = QPushButton("コンテキストに追加")
        self.btn_add.setStyleSheet("""
            QPushButton {
                background: rgba(0, 212, 255, 0.15);
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.25);
            }
        """)
        self.btn_add.clicked.connect(self._on_add)
        layout.addWidget(self.btn_add)

        # 無視ボタン
        self.btn_dismiss = QPushButton("x")
        self.btn_dismiss.setFixedSize(24, 24)
        self.btn_dismiss.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff6666;
            }
        """)
        self.btn_dismiss.clicked.connect(self._on_dismiss)
        layout.addWidget(self.btn_dismiss)

    def show_bible(self, bible: BibleInfo):
        """BIBLE検出通知を表示"""
        self._bible = bible
        codename_str = f' "{bible.codename}"' if bible.codename else ""
        self.info_label.setText(
            f"BIBLE検出: {bible.project_name} v{bible.version}{codename_str}"
        )
        self.setVisible(True)
        logger.info(
            f"[BIBLE] Notification shown: {bible.project_name} v{bible.version}"
        )

    def _on_add(self):
        """コンテキスト追加ボタン"""
        if self._bible:
            self.add_clicked.emit(self._bible)
        self.setVisible(False)

    def _on_dismiss(self):
        """無視ボタン"""
        self.dismiss_clicked.emit()
        self.setVisible(False)
