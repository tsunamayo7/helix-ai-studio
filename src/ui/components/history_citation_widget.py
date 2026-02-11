# -*- coding: utf-8 -*-
"""
History Citation Widget - 履歴引用ウィジェット
v3.1.0: チャット履歴の検索・引用機能

過去のチャット履歴を検索し、選択した内容をプロンプトに引用できる
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLabel, QComboBox,
    QDialog, QDialogButtonBox, QSplitter, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...data.chat_history_manager import get_chat_history_manager, ChatEntry

import logging

logger = logging.getLogger(__name__)


class HistoryCitationWidget(QWidget):
    """
    履歴引用ウィジェット

    - 検索フィルター（AIソース、期間、キーワード）
    - 検索結果リスト
    - プレビュー表示
    - 引用挿入ボタン
    """

    # 引用テキストを挿入するシグナル
    citationInserted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_manager = get_chat_history_manager()
        self._selected_item = None
        self._init_ui()
        self._connect_signals()
        self._refresh_list()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # フィルターバー
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(4, 4, 4, 4)

        # AIソースフィルター
        filter_layout.addWidget(QLabel("AI:"))
        self.ai_filter = QComboBox()
        self.ai_filter.addItems(["すべて", "Claude", "Gemini", "Trinity", "Ollama"])
        self.ai_filter.setMaximumWidth(100)
        filter_layout.addWidget(self.ai_filter)

        # 期間フィルター
        filter_layout.addWidget(QLabel("期間:"))
        self.period_filter = QComboBox()
        self.period_filter.addItems(["すべて", "今日", "1週間", "1ヶ月"])
        self.period_filter.setMaximumWidth(100)
        filter_layout.addWidget(self.period_filter)

        # 検索キーワード
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("検索キーワード...")
        filter_layout.addWidget(self.search_input)

        # 検索ボタン
        self.search_btn = QPushButton("🔍 検索")
        self.search_btn.setMaximumWidth(80)
        filter_layout.addWidget(self.search_btn)

        layout.addWidget(filter_frame)

        # 結果リストとプレビュー
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 結果リスト
        self.result_list = QListWidget()
        self.result_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.result_list.setAlternatingRowColors(True)
        self.result_list.setMinimumHeight(100)
        splitter.addWidget(self.result_list)

        # プレビュー
        preview_frame = QGroupBox("プレビュー")
        preview_layout = QVBoxLayout(preview_frame)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("履歴を選択するとここにプレビューが表示されます")
        self.preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_text)
        splitter.addWidget(preview_frame)

        layout.addWidget(splitter)

        # 引用挿入ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.insert_btn = QPushButton("📋 引用を挿入")
        self.insert_btn.setEnabled(False)
        self.insert_btn.setMinimumWidth(120)
        btn_layout.addWidget(self.insert_btn)

        layout.addLayout(btn_layout)

        # 統計表示
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.stats_label)

    def _connect_signals(self):
        """シグナルを接続"""
        self.search_btn.clicked.connect(self._on_search)
        self.search_input.returnPressed.connect(self._on_search)
        self.ai_filter.currentTextChanged.connect(self._on_filter_changed)
        self.period_filter.currentTextChanged.connect(self._on_filter_changed)
        self.result_list.currentItemChanged.connect(self._on_item_selected)
        self.insert_btn.clicked.connect(self._on_insert)

    def _on_search(self):
        """検索実行"""
        self._refresh_list()

    def _on_filter_changed(self):
        """フィルター変更時"""
        self._refresh_list()

    def _refresh_list(self):
        """リストを更新"""
        self.result_list.clear()
        self.preview_text.clear()
        self.insert_btn.setEnabled(False)
        self._selected_item = None

        # フィルター条件を取得
        ai_source = self.ai_filter.currentText()
        if ai_source == "すべて":
            ai_source = None

        period_text = self.period_filter.currentText()
        period_map = {"すべて": None, "今日": "today", "1週間": "week", "1ヶ月": "month"}
        period = period_map.get(period_text)

        query = self.search_input.text().strip()

        try:
            # 検索実行
            entries = self.history_manager.search_entries(
                query=query,
                ai_source=ai_source,
                period=period,
                limit=100
            )

            for entry in entries:
                item = QListWidgetItem(entry.format_for_display())
                item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self.result_list.addItem(item)

            self.stats_label.setText(f"検索結果: {len(entries)} 件")

        except Exception as e:
            logger.error(f"[HistoryCitationWidget] Search error: {e}")
            self.stats_label.setText(f"検索エラー: {e}")

    def _on_item_selected(self, current, previous):
        """アイテム選択時"""
        if not current:
            self.preview_text.clear()
            self.insert_btn.setEnabled(False)
            self._selected_item = None
            return

        entry_id = current.data(Qt.ItemDataRole.UserRole)
        entry = self.history_manager.get_entry_by_id(entry_id)

        if entry:
            self._selected_item = ("entry", entry_id)

            # プレビュー表示
            preview = (
                f"<div style='color: #a0c8ff;'><b>📝 プロンプト:</b></div>"
                f"<div style='margin-left: 10px;'>{entry.prompt}</div><br>"
                f"<div style='color: #dcdcdc;'><b>🤖 応答 ({entry.ai_source}):</b></div>"
                f"<div style='margin-left: 10px;'>{entry.response[:500]}{'...' if len(entry.response) > 500 else ''}</div>"
            )
            self.preview_text.setHtml(preview)
            self.insert_btn.setEnabled(True)
        else:
            self.preview_text.clear()
            self.insert_btn.setEnabled(False)
            self._selected_item = None

    def _on_insert(self):
        """引用を挿入"""
        if not self._selected_item:
            return

        item_type, item_id = self._selected_item
        citation_text = self.history_manager.get_citation_text(item_type, item_id)

        if citation_text:
            self.citationInserted.emit(citation_text)


class HistoryCitationDialog(QDialog):
    """
    履歴引用ダイアログ

    モーダルダイアログとして履歴を検索・引用
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("チャット履歴から引用")
        self.setMinimumSize(600, 500)

        self._citation_text = None
        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)

        # 説明
        desc_label = QLabel(
            "過去のチャット履歴を検索し、選択した内容をプロンプトに引用できます。\n"
            "検索してアイテムを選択し、「引用を挿入」を押してください。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888; margin-bottom: 8px;")
        layout.addWidget(desc_label)

        # 引用ウィジェット
        self.citation_widget = HistoryCitationWidget()
        self.citation_widget.citationInserted.connect(self._on_citation_inserted)
        layout.addWidget(self.citation_widget)

        # ボタンバー
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_citation_inserted(self, text: str):
        """引用テキストが挿入された"""
        self._citation_text = text
        self.accept()

    def get_citation_text(self) -> str:
        """引用テキストを取得"""
        return self._citation_text or ""

    @staticmethod
    def get_citation(parent=None) -> str:
        """
        引用ダイアログを表示して引用テキストを取得

        Args:
            parent: 親ウィジェット

        Returns:
            引用テキスト（キャンセル時は空文字列）
        """
        dialog = HistoryCitationDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_citation_text()
        return ""
