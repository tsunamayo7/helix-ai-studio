"""
Web UI実行中のロックオーバーレイ (v9.5.0)。
半透明ダーク背景で親ウィジェットを覆い、入力をブロックする。
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..utils.i18n import t
from ..utils.style_helpers import SS
from ..utils.styles import COLORS


class WebLockOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("webLockOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.setStyleSheet("""
            #webLockOverlay {
                background-color: rgba(0, 0, 0, 180);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # スマホアイコン
        icon_label = QLabel("\U0001f4f1")
        icon_label.setFont(QFont("Segoe UI Emoji", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # メッセージ
        self.message_label = QLabel(t('desktop.widgets.webLock.lockMsg'))
        self.message_label.setStyleSheet(
            f"color: {COLORS['success']}; font-size: 16px; font-weight: bold; padding: 10px;")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # サブメッセージ
        self.sub_label = QLabel(t('desktop.widgets.webLock.subMsg'))
        self.sub_label.setStyleSheet(SS.dim("12px"))
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        self.hide()

    def show_lock(self, message: str = ""):
        if message:
            self.message_label.setText(message)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()

    def hide_lock(self):
        self.hide()

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
