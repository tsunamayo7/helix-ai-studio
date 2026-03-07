"""
Helix AI Studio - History Tab (v12.8.0 "SoloAI Unification")
全タブのチャット履歴をJSONLから検索・表示・引用する統合Historyタブ。

Features:
  - JSONL (data/chat_history_log.jsonl) からの全文検索
  - タブフィルタ (soloAI / mixAI / RAG / All)
  - 日付グルーピング
  - ソート (新しい順 / 古い順)
  - メッセージコピー・他タブ引用
  - v12.8.0: soloAI フィルタは旧 cloudAI / localAI のログも包含
"""

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QSplitter,
    QScrollArea, QFrame, QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from ..utils.i18n import t
from ..utils.style_helpers import SS
from ..utils.chat_logger import get_chat_logger
from ..utils.styles import COLORS, SCROLLBAR_STYLE
from ..widgets.no_scroll_widgets import NoScrollComboBox

logger = logging.getLogger(__name__)

# v12.8.0: soloAI は旧 cloudAI / localAI のログも含む
_TAB_ALIASES = {
    "soloAI": ["soloAI", "cloudAI", "localAI"],
}


class HistoryTab(QWidget):
    """v11.0.0: 全タブ統合チャット履歴タブ"""

    statusChanged = pyqtSignal(str)
    quoteRequested = pyqtSignal(str, str)  # (tab_name, content) - 他タブに引用

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chat_logger = get_chat_logger()
        self._current_entries = []
        self._setup_ui()
        # 初回データ読み込みを遅延
        QTimer.singleShot(500, self._refresh_data)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # === フィルタバー ===
        filter_bar = QFrame()
        filter_bar.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['text_disabled']};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(8, 4, 8, 4)
        filter_layout.setSpacing(8)

        # 検索フィールド
        search_icon = QLabel("🔍")
        filter_layout.addWidget(search_icon)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t('desktop.history.searchPlaceholder'))
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_surface']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['text_disabled']}; border-radius: 4px;
                padding: 6px 10px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)
        self.search_input.returnPressed.connect(self._refresh_data)
        filter_layout.addWidget(self.search_input, stretch=2)

        # タブフィルタ
        self.tab_filter = NoScrollComboBox()
        self.tab_filter.addItem(t('desktop.history.filterAll'), "all")
        self.tab_filter.addItem("🤖 soloAI", "soloAI")
        self.tab_filter.addItem("🔀 mixAI", "mixAI")
        self.tab_filter.addItem("🧠 RAG", "rag")
        self.tab_filter.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_surface']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['text_disabled']}; border-radius: 4px;
                padding: 4px 8px; font-size: 11px; min-width: 100px;
            }}
        """)
        self.tab_filter.currentIndexChanged.connect(self._refresh_data)
        filter_layout.addWidget(self.tab_filter)

        # ソート順
        self.sort_combo = NoScrollComboBox()
        self.sort_combo.addItem(t('desktop.history.sortNewest'), "desc")
        self.sort_combo.addItem(t('desktop.history.sortOldest'), "asc")
        self.sort_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_surface']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['text_disabled']}; border-radius: 4px;
                padding: 4px 8px; font-size: 11px; min-width: 90px;
            }}
        """)
        self.sort_combo.currentIndexChanged.connect(self._refresh_data)
        filter_layout.addWidget(self.sort_combo)

        # 更新ボタン
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['accent']};
                border: 1px solid {COLORS['text_disabled']}; border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: rgba(0, 212, 255, 0.1); }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_data)
        filter_layout.addWidget(self.refresh_btn)

        layout.addWidget(filter_bar)

        # === メインスプリッター (チャット一覧 | 詳細) ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: チャット一覧
        self.chat_list_area = QScrollArea()
        self.chat_list_area.setWidgetResizable(True)
        self.chat_list_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_list_area.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_surface']}; border: 1px solid {COLORS['text_disabled']}; border-radius: 4px; }}"
            + SCROLLBAR_STYLE
        )
        self.chat_list_widget = QWidget()
        self.chat_list_layout = QVBoxLayout(self.chat_list_widget)
        self.chat_list_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_list_layout.setSpacing(4)
        self.chat_list_layout.addStretch()
        self.chat_list_area.setWidget(self.chat_list_widget)
        splitter.addWidget(self.chat_list_area)

        # 右: 詳細表示
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(4, 4, 4, 4)

        self.detail_display = QTextEdit()
        self.detail_display.setReadOnly(True)
        self.detail_display.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_surface']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['text_disabled']}; border-radius: 4px;
                padding: 12px; font-size: 13px;
            }}
        """ + SCROLLBAR_STYLE)
        self.detail_display.setPlaceholderText(t('desktop.history.selectMessage'))
        detail_layout.addWidget(self.detail_display, stretch=1)

        # アクションボタン
        action_layout = QHBoxLayout()
        self.copy_btn = QPushButton("📋 " + t('desktop.history.copyMessage'))
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}; border-radius: 4px;
                padding: 4px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background: rgba(0, 212, 255, 0.1); }}
        """)
        self.copy_btn.clicked.connect(self._copy_selected)
        action_layout.addWidget(self.copy_btn)

        self.quote_btn = QPushButton("📎 " + t('desktop.history.quoteToTab'))
        self.quote_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['success']};
                border: 1px solid {COLORS['success']}; border-radius: 4px;
                padding: 4px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background: rgba(0, 255, 136, 0.1); }}
        """)
        self.quote_btn.clicked.connect(self._quote_selected)
        action_layout.addWidget(self.quote_btn)
        action_layout.addStretch()
        detail_layout.addLayout(action_layout)

        splitter.addWidget(detail_widget)
        splitter.setSizes([400, 300])
        layout.addWidget(splitter, stretch=1)

    def _refresh_data(self):
        """フィルタに基づいてデータを再読み込み"""
        query = self.search_input.text().strip() or None
        tab = self.tab_filter.currentData() or "all"
        sort_order = self.sort_combo.currentData() or "desc"

        # v12.8.0: エイリアス解決（soloAI → soloAI/cloudAI/localAI）
        tab_filter_value = tab if tab != "all" else None
        entries = self._chat_logger.search(
            query=query,
            tab=tab_filter_value,
            limit=200
        )

        if sort_order == "asc":
            entries.sort(key=lambda x: x.get("timestamp", ""))

        self._current_entries = entries
        self._render_entries(entries)

    def _render_entries(self, entries: list):
        """エントリ一覧をレンダリング"""
        # 既存ウィジェットをクリア
        while self.chat_list_layout.count() > 1:
            item = self.chat_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not entries:
            no_results = QLabel(t('desktop.history.noResults'))
            no_results.setStyleSheet("color: #666; font-size: 12px; padding: 20px;")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.chat_list_layout.insertWidget(0, no_results)
            return

        # 日付ごとにグルーピング
        by_date = {}
        for entry in entries:
            ts = entry.get("timestamp", "")
            date_str = ts[:10] if len(ts) >= 10 else "unknown"
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append(entry)

        insert_idx = 0
        for date_str in sorted(by_date.keys(), reverse=True):
            # 日付ヘッダー
            date_label = QLabel(f"📅 {date_str}")
            date_label.setStyleSheet(
                f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: bold; "
                "padding: 6px 4px 2px 4px;"
            )
            self.chat_list_layout.insertWidget(insert_idx, date_label)
            insert_idx += 1

            for entry in by_date[date_str]:
                card = self._create_entry_card(entry)
                self.chat_list_layout.insertWidget(insert_idx, card)
                insert_idx += 1

    def _create_entry_card(self, entry: dict) -> QFrame:
        """メッセージカードを作成"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
            QFrame:hover {{
                border-color: {COLORS['accent']};
                background: {COLORS['bg_elevated']};
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(3)

        # ヘッダー行: タブ | モデル | 時刻
        header = QHBoxLayout()
        tab_name = entry.get("tab", "unknown")
        tab_icons = {
            "soloAI": "🤖", "cloudAI": "☁️", "mixAI": "🔀",
            "localAI": "🖥️", "rag": "🧠"
        }
        tab_icon = tab_icons.get(tab_name, "💬")
        model = entry.get("model", "")[:20]
        ts = entry.get("timestamp", "")
        time_str = ts[11:16] if len(ts) >= 16 else ""

        tab_label = QLabel(f"{tab_icon} {tab_name}")
        tab_label.setStyleSheet(SS.accent("10px", bold=True))
        header.addWidget(tab_label)

        if model:
            model_label = QLabel(f"| {model}")
            model_label.setStyleSheet(SS.muted("10px"))
            header.addWidget(model_label)

        header.addStretch()

        time_label = QLabel(time_str)
        time_label.setStyleSheet(SS.dim("10px"))
        header.addWidget(time_label)

        card_layout.addLayout(header)

        # コンテンツプレビュー
        role = entry.get("role", "user")
        content = entry.get("content", "")
        preview = content[:120].replace("\n", " ")
        if len(content) > 120:
            preview += "..."

        role_icon = "👤" if role == "user" else "🤖"
        content_label = QLabel(f"{role_icon} {preview}")
        content_label.setStyleSheet(SS.dim("11px"))
        content_label.setWordWrap(True)
        content_label.setMaximumHeight(40)
        card_layout.addWidget(content_label)

        # クリックイベント
        card.mousePressEvent = lambda event, e=entry: self._show_detail(e)

        return card

    def _show_detail(self, entry: dict):
        """メッセージ詳細を表示"""
        self._selected_entry = entry

        role = entry.get("role", "user")
        role_icon = "👤 User" if role == "user" else "🤖 Assistant"
        tab = entry.get("tab", "unknown")
        model = entry.get("model", "unknown")
        ts = entry.get("timestamp", "")
        content = entry.get("content", "")
        duration = entry.get("duration_ms")
        session = entry.get("session_id", "")

        html = f"""
        <div style="padding: 8px;">
            <div style="color: {COLORS['accent']}; font-size: 12px; margin-bottom: 8px;">
                <b>{role_icon}</b> | {tab} | {model} | {ts}
            </div>
        """

        if duration:
            html += f'<div style="color: {COLORS["text_secondary"]}; font-size: 10px; margin-bottom: 4px;">⏱ {duration:.0f}ms</div>'
        if session:
            html += f'<div style="color: {COLORS["text_secondary"]}; font-size: 10px; margin-bottom: 8px;">🔑 Session: {session[:16]}...</div>'

        html += f"""
            <div style="color: {COLORS['text_primary']}; font-size: 13px; line-height: 1.5;
                        white-space: pre-wrap; word-wrap: break-word;">
{content}
            </div>
        </div>
        """
        self.detail_display.setHtml(html)

    def _copy_selected(self):
        """選択メッセージをクリップボードにコピー"""
        entry = getattr(self, '_selected_entry', None)
        if entry:
            content = entry.get("content", "")
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            self.statusChanged.emit(t('desktop.history.copyMessage') + " ✓")

    def _quote_selected(self):
        """選択メッセージを他タブに引用"""
        entry = getattr(self, '_selected_entry', None)
        if entry:
            content = entry.get("content", "")[:500]
            tab = entry.get("tab", "soloAI")
            # v12.8.0: 旧タブ名を soloAI にマッピング
            if tab in ("cloudAI", "localAI"):
                tab = "soloAI"
            self.quoteRequested.emit(tab, content)
            self.statusChanged.emit(t('desktop.history.quoteToTab') + " ✓")

    def retranslateUi(self):
        """言語切替時のUI更新"""
        self.search_input.setPlaceholderText(t('desktop.history.searchPlaceholder'))
        self.tab_filter.setItemText(0, t('desktop.history.filterAll'))
        # v12.8.0: index 1=soloAI, 2=mixAI, 3=RAG（固定ラベルのため再設定不要）
        self.sort_combo.setItemText(0, t('desktop.history.sortNewest'))
        self.sort_combo.setItemText(1, t('desktop.history.sortOldest'))
        self.copy_btn.setText("📋 " + t('desktop.history.copyMessage'))
        self.quote_btn.setText("📎 " + t('desktop.history.quoteToTab'))
