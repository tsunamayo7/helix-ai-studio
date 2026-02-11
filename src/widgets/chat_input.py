"""
Helix AI Studio - Chat Input Widgets (v5.0.0)
チャット入力UI強化ウィジェット

機能:
- EnhancedChatInput: カーソル移動対応テキスト入力
- AttachmentWidget: 個別の添付ファイル表示
- AttachmentBar: 添付ファイルバー
- ChatInputArea: 入力エリア統合
"""

import os
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QTextCursor


class EnhancedChatInput(QTextEdit):
    """
    チャット入力ウィジェット (v5.0.0)

    機能:
    - 上下左右キーによるカーソル移動
    - 先頭行+上キー -> テキスト先頭へ
    - 最終行+下キー -> テキスト末尾へ
    - Shift+Enter で改行
    - Enter で送信
    - ファイルドロップサポート
    """
    send_requested = pyqtSignal()      # 送信リクエスト
    file_dropped = pyqtSignal(list)    # ファイルドロップ

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("メッセージを入力... (Enter: 送信, Shift+Enter: 改行)")
        self.setMaximumHeight(150)
        self.setMinimumHeight(40)

        # 3行分の高さをデフォルトに
        font_metrics = self.fontMetrics()
        self.setFixedHeight(font_metrics.height() * 3 + 20)

        # スタイル
        self.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px;
                font-size: 11pt;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent):
        """キーイベント処理"""
        key = event.key()
        modifiers = event.modifiers()

        # Enter（Shift無し）-> 送信
        if key == Qt.Key.Key_Return and not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self.send_requested.emit()
            return

        # 上キー処理
        if key == Qt.Key.Key_Up:
            cursor = self.textCursor()
            # 先頭行にいる場合 -> テキスト先頭へ移動
            cursor_block = cursor.block()
            first_block = self.document().firstBlock()
            if cursor_block == first_block:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
                return
            # それ以外は通常の上移動
            super().keyPressEvent(event)
            return

        # 下キー処理
        if key == Qt.Key.Key_Down:
            cursor = self.textCursor()
            # 最終行にいる場合 -> テキスト末尾へ移動
            cursor_block = cursor.block()
            last_block = self.document().lastBlock()
            if cursor_block == last_block:
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                return
            # それ以外は通常の下移動
            super().keyPressEvent(event)
            return

        # 左右キーは通常のQTextEdit動作（そのままでOK）
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        """ドラッグ進入イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        """ドロップイベント"""
        if event.mimeData().hasUrls():
            files = [url.toLocalFile() for url in event.mimeData().urls()
                     if url.toLocalFile()]
            if files:
                self.file_dropped.emit(files)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class AttachmentWidget(QFrame):
    """個別の添付ファイル表示ウィジェット"""
    removed = pyqtSignal(str)  # ファイルパス

    # ファイル拡張子別アイコン
    FILE_ICONS = {
        ".py": "🐍", ".js": "📜", ".ts": "📘",
        ".html": "🌐", ".css": "🎨", ".json": "📋",
        ".md": "📝", ".txt": "📄", ".pdf": "📕",
        ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼",
        ".gif": "🖼", ".svg": "🖼", ".webp": "🖼",
        ".zip": "📦", ".csv": "📊", ".xlsx": "📊",
        ".xml": "📰", ".yaml": "📰", ".yml": "📰",
    }

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            AttachmentWidget {
                background-color: #2d2d2d;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px 8px;
            }
            AttachmentWidget:hover {
                border-color: #0078d4;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        # ファイルアイコン + 名前
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        icon = self.FILE_ICONS.get(ext, "📎")

        icon_label = QLabel(icon)
        name_label = QLabel(filename)
        name_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        name_label.setMaximumWidth(200)
        name_label.setToolTip(filepath)

        # ×ボタン
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #999;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff6666;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(remove_btn)


class AttachmentBar(QWidget):
    """添付ファイルバー（チャット入力欄の上に表示）"""
    attachments_changed = pyqtSignal(list)  # ファイルパスリスト

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[str] = []
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # スクロールエリア（多数のファイル対応）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMaximumHeight(40)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.container = QWidget()
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def add_files(self, filepaths: List[str]):
        """ファイルを追加"""
        for fp in filepaths:
            if fp not in self._files and os.path.exists(fp):
                self._files.append(fp)
                widget = AttachmentWidget(fp)
                widget.removed.connect(self.remove_file)
                self.container_layout.insertWidget(
                    self.container_layout.count() - 1, widget)

        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def remove_file(self, filepath: str):
        """ファイルを削除"""
        if filepath in self._files:
            self._files.remove(filepath)
        # ウィジェットを削除
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, AttachmentWidget) and w.filepath == filepath:
                    w.deleteLater()
                    break
        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def clear_all(self):
        """全ファイル削除"""
        self._files.clear()
        while self.container_layout.count() > 1:  # stretchを残す
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setVisible(False)
        self.attachments_changed.emit([])

    def get_files(self) -> List[str]:
        """添付ファイルリストを取得"""
        return self._files.copy()


class ChatInputArea(QWidget):
    """チャット入力エリア全体（添付バー + テキスト入力 + ボタン）"""
    send_requested = pyqtSignal(str, list)  # (テキスト, ファイルリスト)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(2)

        # 添付ファイルバー
        self.attachment_bar = AttachmentBar()
        layout.addWidget(self.attachment_bar)

        # 入力行（テキスト + ボタン群）
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        # ファイル添付ボタン
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setFixedSize(36, 36)
        self.attach_btn.setToolTip("ファイルを添付")
        self.attach_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
        """)
        self.attach_btn.clicked.connect(self._on_attach_clicked)

        # テキスト入力
        self.text_input = EnhancedChatInput()
        self.text_input.send_requested.connect(self._on_send)
        self.text_input.file_dropped.connect(self.attachment_bar.add_files)

        # 送信ボタン
        self.send_btn = QPushButton("送信")
        self.send_btn.setFixedSize(60, 36)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5aa0e9; }
            QPushButton:disabled { background-color: #555; }
        """)
        self.send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self.attach_btn)
        input_row.addWidget(self.text_input, 1)
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

    def _on_attach_clicked(self):
        """添付ボタンクリック"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "ファイルを選択", "",
            "全ファイル (*);;Python (*.py);;テキスト (*.txt *.md);;画像 (*.png *.jpg *.jpeg *.gif)"
        )
        if files:
            self.attachment_bar.add_files(files)

    def _on_send(self):
        """送信"""
        text = self.text_input.toPlainText().strip()
        if text:
            files = self.attachment_bar.get_files()
            self.send_requested.emit(text, files)
            self.text_input.clear()
            self.attachment_bar.clear_all()

    def set_enabled(self, enabled: bool):
        """入力の有効/無効を切り替え"""
        self.text_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.attach_btn.setEnabled(enabled)

    def set_text(self, text: str):
        """テキストを設定"""
        self.text_input.setPlainText(text)

    def get_text(self) -> str:
        """テキストを取得"""
        return self.text_input.toPlainText()

    def focus_input(self):
        """入力欄にフォーカス"""
        self.text_input.setFocus()
