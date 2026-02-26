"""v11.0.0: 領域別保存ボタンファクトリ

各設定QGroupBoxの末尾に配置する保存ボタンを生成する。
画面最下部の単一保存ボタンを廃止し、各領域で即座に保存可能にする。
"""
from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QWidget
from PyQt6.QtCore import QTimer
from ..utils.i18n import t
from ..utils.styles import COLORS

import logging
logger = logging.getLogger(__name__)


def create_section_save_button(save_callback, parent=None) -> QWidget:
    """設定領域末尾に配置する保存ボタン付きコンテナを生成

    Args:
        save_callback: 保存処理のcallable
        parent: 親ウィジェット

    Returns:
        QWidget: 右寄せ保存ボタンを含むコンテナ
    """
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.addStretch()

    save_btn = QPushButton("💾 " + t('common.saveSection'))
    save_btn._is_section_save_btn = True
    save_btn.setStyleSheet(f"""
        QPushButton {{
            background: {COLORS["success_bg"]}; color: {COLORS["success"]};
            border: 1px solid {COLORS["success"]}; border-radius: 4px;
            padding: 4px 16px; font-size: 11px; font-weight: bold;
        }}
        QPushButton:hover {{ background: {COLORS["success_bg"]}; }}
        QPushButton:pressed {{ background: {COLORS["success_bg"]}; }}
        QPushButton:disabled {{ background: {COLORS["bg_card"]}; color: {COLORS["text_muted"]}; border-color: {COLORS["text_disabled"]}; }}
    """)

    def _on_click():
        try:
            save_callback()
            # 保存完了フィードバック
            original_text = save_btn.text()
            save_btn.setText("✅ " + t('common.saveSectionDone'))
            save_btn.setEnabled(False)
            QTimer.singleShot(1500, lambda: (
                save_btn.setText(original_text),
                save_btn.setEnabled(True)
            ))
        except Exception as e:
            logger.error(f"Section save failed: {e}")
            save_btn.setText("❌ " + t('common.saveSectionFailed'))
            QTimer.singleShot(2000, lambda: (
                save_btn.setText("💾 " + t('common.saveSection')),
                save_btn.setEnabled(True)
            ))

    save_btn.clicked.connect(_on_click)
    layout.addWidget(save_btn)
    return container


def retranslate_section_save_buttons(root_widget):
    """ルートウィジェット以下のセクション保存ボタンのテキストを現在の言語に更新"""
    from PyQt6.QtWidgets import QWidget
    for btn in root_widget.findChildren(QWidget):
        if getattr(btn, '_is_section_save_btn', False):
            if btn.isEnabled():
                btn.setText("💾 " + t('common.saveSection'))
