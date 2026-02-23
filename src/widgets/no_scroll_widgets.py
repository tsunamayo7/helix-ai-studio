"""v11.0.0: スクロール競合を防止するNoScrollウィジェット群

全タブ共通で使用する。各タブでの個別定義（_NoScrollComboBox 等）は
このモジュールからのimportに統一すること。

v11.0.0 Update:
- NoScrollComboBox: デフォルトeditable=False
  非editableモードではQtの標準動作で左クリック→ポップアップが開く。
  editableモードの場合のみmousePressEventでshowPopup()を補助。
"""
from PyQt6.QtWidgets import QComboBox, QSpinBox, QDoubleSpinBox
from PyQt6.QtCore import Qt


class NoScrollComboBox(QComboBox):
    """マウスホイール誤操作防止 + 統一挙動コンボボックス

    - デフォルトで編集不可（setEditable(False)）
    - ホイールイベントは常に無視
    - 非editableモード: Qtの標準動作で左クリック→ポップアップが開く（追加処理不要）
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(False)

    def wheelEvent(self, event):
        event.ignore()


class NoScrollSpinBox(QSpinBox):
    """マウスホイールで値が変わらないQSpinBox（v11.0.0 共通版）"""
    def wheelEvent(self, event):
        event.ignore()


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """マウスホイールで値が変わらないQDoubleSpinBox（v11.0.0 共通版）"""
    def wheelEvent(self, event):
        event.ignore()
