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

from ..utils.styles import BIBLE_NOTIFICATION_STYLE, COLORS
from ..bible.bible_schema import BibleInfo
from ..utils.i18n import t
from ..utils.style_helpers import SS

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
        self._added_to_context = False  # v9.8.0: コンテキスト追加済みフラグ
        self._setup_ui()
        self.setVisible(False)  # v9.7.2: 初期非表示（BIBLE検出時のみ表示）

    def _setup_ui(self):
        self.setStyleSheet(BIBLE_NOTIFICATION_STYLE)
        self.setMaximumHeight(44)
        self.setToolTip(t('desktop.widgets.bibleNotification.tooltip'))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # 情報ラベル
        self.info_label = QLabel("")
        self.info_label.setStyleSheet(SS.primary("12px"))
        layout.addWidget(self.info_label, stretch=1)

        # コンテキストに追加ボタン
        self.btn_add = QPushButton(t('desktop.widgets.bibleNotification.addToContext'))
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 212, 255, 0.15);
                color: {COLORS["accent"]};
                border: 1px solid {COLORS["accent"]};
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: rgba(0, 212, 255, 0.25);
            }}
        """)
        self.btn_add.clicked.connect(self._on_add)
        layout.addWidget(self.btn_add)

        # 無視ボタン
        self.btn_dismiss = QPushButton("x")
        self.btn_dismiss.setFixedSize(24, 24)
        self.btn_dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS["text_secondary"]};
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {COLORS["error"]};
            }}
        """)
        self.btn_dismiss.clicked.connect(self._on_dismiss)
        layout.addWidget(self.btn_dismiss)

    def show_bible(self, bible: BibleInfo):
        """BIBLE検出通知を表示（BIBLE検出 & 未追加の条件でのみ表示）"""
        # v9.8.0: 既にコンテキストに追加済みなら再表示しない
        if self._added_to_context and self._bible and self._bible.file_path == bible.file_path:
            return
        self._bible = bible
        self._added_to_context = False
        codename_str = f' "{bible.codename}"' if bible.codename else ""
        self.info_label.setText(
            t('desktop.widgets.bibleNotification.detected', project=bible.project_name, version=bible.version, codename=codename_str)
        )
        self.setVisible(True)
        logger.info(
            f"[BIBLE] Notification shown: {bible.project_name} v{bible.version}"
        )

    def _on_add(self):
        """コンテキスト追加ボタン"""
        if self._bible:
            self.add_clicked.emit(self._bible)
        self._added_to_context = True  # v9.8.0: 追加済みフラグ
        self.setVisible(False)

    def _on_dismiss(self):
        """無視ボタン"""
        self.dismiss_clicked.emit()
        self.setVisible(False)
