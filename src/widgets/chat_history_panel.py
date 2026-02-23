"""
Helix AI Studio - Chat History Side Panel (v9.7.0)
デスクトップ版チャット履歴サイドパネル。
Web版ChatListPanelと同等の機能をPyQt6 QDockWidgetで実現。
ChatStore (SQLite) を共有し、デスクトップとWeb UIで同じ履歴を閲覧・操作可能。
"""

import logging
from datetime import datetime, date, timedelta

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QFrame, QMenu,
    QInputDialog, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QAction

from ..utils.i18n import t

logger = logging.getLogger(__name__)

# ─── カラー定数 ───
BG_DARK = "#0a0e14"
BG_ITEM = "#111827"
BG_HOVER = "#1f2937"
BG_SELECTED = "#064e3b"
BADGE_SOLO = "#0891b2"
BADGE_MIX = "#7c3aed"
TEXT_PRIMARY = "#e5e7eb"
TEXT_SECONDARY = "#9ca3af"
TEXT_MUTED = "#6b7280"
BORDER_COLOR = "#1f2937"
ACCENT_CYAN = "#00d4ff"


class ChatItemWidget(QFrame):
    """個別チャットアイテムウィジェット"""

    clicked = pyqtSignal(str, str)       # (chat_id, tab)
    renameRequested = pyqtSignal(str)     # (chat_id)
    deleteRequested = pyqtSignal(str)     # (chat_id)

    def __init__(self, chat_data: dict, parent=None):
        super().__init__(parent)
        self.chat_data = chat_data
        self.chat_id = chat_data["id"]
        self.tab = chat_data.get("tab", "soloAI")
        self._selected = False
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_ui(self):
        self.setFixedHeight(58)
        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # タイトル行
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        self.title_label = QLabel(self.chat_data.get("title", t('common.untitled')))
        self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold; background: transparent;")
        self.title_label.setWordWrap(False)
        title_row.addWidget(self.title_label, 1)

        layout.addLayout(title_row)

        # メタ行: タブバッジ + 時刻 + メッセージ数
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        badge_color = BADGE_SOLO if self.tab in ("soloAI", "cloudAI") else BADGE_MIX
        badge_text = "cloudAI" if self.tab in ("soloAI", "cloudAI") else "mixAI"
        self.badge_label = QLabel(badge_text)
        self.badge_label.setStyleSheet(
            f"color: white; background-color: {badge_color}; "
            f"border-radius: 3px; padding: 1px 6px; font-size: 9px; font-weight: bold;"
        )
        self.badge_label.setFixedHeight(16)
        meta_row.addWidget(self.badge_label)

        # 時刻
        updated_at = self.chat_data.get("updated_at", "")
        time_str = self._format_time(updated_at)
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
        meta_row.addWidget(self.time_label)

        # メッセージ数
        msg_count = self.chat_data.get("message_count", 0)
        self.count_label = QLabel(f"{msg_count}msg")
        self.count_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
        meta_row.addWidget(self.count_label)

        meta_row.addStretch()
        layout.addLayout(meta_row)

    def _format_time(self, iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%H:%M")
        except Exception:
            return ""

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                ChatItemWidget {{
                    background-color: {BG_SELECTED};
                    border: 1px solid #10b981;
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ChatItemWidget {{
                    background-color: {BG_ITEM};
                    border: 1px solid transparent;
                    border-radius: 6px;
                }}
                ChatItemWidget:hover {{
                    background-color: {BG_HOVER};
                    border: 1px solid {BORDER_COLOR};
                }}
            """)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.chat_id, self.tab)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        rename_action = QAction(t('desktop.chatHistory.rename'), self)
        rename_action.triggered.connect(lambda: self.renameRequested.emit(self.chat_id))
        menu.addAction(rename_action)

        delete_action = QAction(t('desktop.chatHistory.delete'), self)
        delete_action.triggered.connect(lambda: self.deleteRequested.emit(self.chat_id))
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))


class ChatHistoryPanel(QDockWidget):
    """チャット履歴サイドパネル (v9.7.0)"""

    chatSelected = pyqtSignal(str, str)    # (chat_id, tab)
    newChatRequested = pyqtSignal(str)     # (tab)
    chatDeleted = pyqtSignal(str)          # (chat_id)

    def __init__(self, parent=None):
        super().__init__(t('desktop.chatHistory.title'), parent)
        self._chat_store = None
        self._active_chat_id = None
        self._current_filter = None  # None = all, "soloAI", "mixAI"
        self._search_text = ""
        self._chat_items: list[ChatItemWidget] = []

        self._init_chat_store()
        self._setup_ui()
        self._apply_style()

        # DockWidget設定
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setMinimumWidth(280)
        self.setMaximumWidth(350)

    def _init_chat_store(self):
        try:
            from ..web.chat_store import ChatStore
            self._chat_store = ChatStore()
            logger.info("ChatStore initialized for ChatHistoryPanel")
        except Exception as e:
            logger.warning(f"ChatStore init failed: {e}")

    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 検索バー
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t('desktop.chatHistory.searchPlaceholder'))
        self.search_input.setToolTip(t('desktop.chatHistory.searchTip'))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_ITEM};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_CYAN};
            }}
        """)
        layout.addWidget(self.search_input)

        # 新しいチャットボタン
        self.new_chat_btn = QPushButton(t('desktop.chatHistory.newChat'))
        self.new_chat_btn.setToolTip(t('desktop.chatHistory.newChatTip'))
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.clicked.connect(self._on_new_chat_clicked)
        self.new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #047857;
            }}
        """)
        layout.addWidget(self.new_chat_btn)

        # タブフィルタ
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)

        self.filter_all_btn = QPushButton(t('desktop.chatHistory.filterAll'))
        self.filter_solo_btn = QPushButton("cloudAI")
        self.filter_mix_btn = QPushButton("mixAI")

        for btn in [self.filter_all_btn, self.filter_solo_btn, self.filter_mix_btn]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.filter_all_btn.clicked.connect(lambda: self._set_filter(None))
        self.filter_solo_btn.clicked.connect(lambda: self._set_filter("cloudAI"))
        self.filter_mix_btn.clicked.connect(lambda: self._set_filter("mixAI"))

        filter_row.addWidget(self.filter_all_btn)
        filter_row.addWidget(self.filter_solo_btn)
        filter_row.addWidget(self.filter_mix_btn)
        layout.addLayout(filter_row)

        self._update_filter_styles()

        # チャット一覧スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {BG_DARK};
            }}
            QScrollBar:vertical {{
                background: {BG_DARK};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #333;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT_CYAN};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area, 1)

        # 統計ラベル
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stats_label)

        self.setWidget(container)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDockWidget {{
                background-color: {BG_DARK};
                color: {TEXT_PRIMARY};
                titlebar-close-icon: url(none);
            }}
            QDockWidget::title {{
                background-color: #111827;
                color: {ACCENT_CYAN};
                padding: 8px;
                font-weight: bold;
                text-align: left;
            }}
        """)

    # ─── フィルタ操作 ───

    def _set_filter(self, tab_filter: str | None):
        self._current_filter = tab_filter
        self._update_filter_styles()
        self.refresh_chat_list()

    def set_tab_filter(self, tab: str):
        self._current_filter = tab
        self._update_filter_styles()

    def _update_filter_styles(self):
        active = "background-color: #059669; color: white; border: none; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 4px 8px;"
        inactive = f"background-color: {BG_ITEM}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_COLOR}; border-radius: 4px; font-size: 11px; padding: 4px 8px;"

        self.filter_all_btn.setStyleSheet(active if self._current_filter is None else inactive)
        self.filter_solo_btn.setStyleSheet(active if self._current_filter in ("soloAI", "cloudAI") else inactive)
        self.filter_mix_btn.setStyleSheet(active if self._current_filter == "mixAI" else inactive)

    # ─── 検索 ───

    def _on_search_changed(self, text: str):
        self._search_text = text.strip().lower()
        self._apply_search_filter()

    def _apply_search_filter(self):
        for item in self._chat_items:
            if not self._search_text:
                item.setVisible(True)
            else:
                title = item.chat_data.get("title", "").lower()
                item.setVisible(self._search_text in title)

    # ─── チャット一覧の更新 ───

    def refresh_chat_list(self, tab_filter: str = None):
        if tab_filter is not None:
            self._current_filter = tab_filter
            self._update_filter_styles()

        if not self._chat_store:
            return

        try:
            chats = self._chat_store.list_chats(tab=self._current_filter, limit=100)
        except Exception as e:
            logger.warning(f"Failed to list chats: {e}")
            return

        # 既存アイテムをクリア
        self._clear_chat_items()

        if not chats:
            empty_label = QLabel(t('desktop.chatHistory.noChats'))
            empty_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; padding: 20px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.insertWidget(0, empty_label)
            self.stats_label.setText("")
            return

        # 日付グループ化
        groups = self._group_by_date(chats)

        insert_idx = 0
        for group_name, group_chats in groups:
            if not group_chats:
                continue

            # グループヘッダー
            header = QLabel(f"  {group_name}")
            header.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 10px; font-weight: bold; "
                f"padding: 8px 0 2px 0; background: transparent;"
            )
            header.setObjectName("groupHeader")
            self.list_layout.insertWidget(insert_idx, header)
            insert_idx += 1

            for chat in group_chats:
                item = ChatItemWidget(chat)
                item.clicked.connect(self._on_item_clicked)
                item.renameRequested.connect(self._on_rename_requested)
                item.deleteRequested.connect(self._on_delete_requested)

                if chat["id"] == self._active_chat_id:
                    item.set_selected(True)

                self.list_layout.insertWidget(insert_idx, item)
                self._chat_items.append(item)
                insert_idx += 1

        # 統計更新
        self.stats_label.setText(
            t('desktop.chatHistory.chatCount', count=len(chats))
        )

        # 検索フィルタ適用
        self._apply_search_filter()

    def _clear_chat_items(self):
        self._chat_items.clear()
        while self.list_layout.count() > 0:
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.list_layout.addStretch()

    def _group_by_date(self, chats: list) -> list:
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())

        groups = {
            "today": [],
            "yesterday": [],
            "this_week": [],
            "older": [],
        }

        for chat in chats:
            try:
                dt = datetime.fromisoformat(chat.get("updated_at", "")).date()
                if dt == today:
                    groups["today"].append(chat)
                elif dt == yesterday:
                    groups["yesterday"].append(chat)
                elif dt >= week_start:
                    groups["this_week"].append(chat)
                else:
                    groups["older"].append(chat)
            except Exception:
                groups["older"].append(chat)

        result = []
        if groups["today"]:
            result.append((t('desktop.chatHistory.groupToday'), groups["today"]))
        if groups["yesterday"]:
            result.append((t('desktop.chatHistory.groupYesterday'), groups["yesterday"]))
        if groups["this_week"]:
            result.append((t('desktop.chatHistory.groupThisWeek'), groups["this_week"]))
        if groups["older"]:
            result.append((t('desktop.chatHistory.groupOlder'), groups["older"]))

        return result

    # ─── アクティブチャット ───

    def set_active_chat(self, chat_id: str):
        self._active_chat_id = chat_id
        for item in self._chat_items:
            item.set_selected(item.chat_id == chat_id)

    # ─── イベントハンドラ ───

    def _on_item_clicked(self, chat_id: str, tab: str):
        self.set_active_chat(chat_id)
        self.chatSelected.emit(chat_id, tab)

    def _on_new_chat_clicked(self):
        tab = self._current_filter or "cloudAI"
        self.newChatRequested.emit(tab)

    def _on_rename_requested(self, chat_id: str):
        if not self._chat_store:
            return
        chat = self._chat_store.get_chat(chat_id)
        if not chat:
            return

        new_title, ok = QInputDialog.getText(
            self,
            t('desktop.chatHistory.renameTitle'),
            t('desktop.chatHistory.renamePrompt'),
            text=chat.get("title", ""),
        )
        if ok and new_title.strip():
            self._chat_store.update_chat_title(chat_id, new_title.strip())
            self.refresh_chat_list()

    def _on_delete_requested(self, chat_id: str):
        if not self._chat_store:
            return

        reply = QMessageBox.question(
            self,
            t('desktop.chatHistory.deleteTitle'),
            t('desktop.chatHistory.deleteConfirm'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._chat_store.delete_chat(chat_id)
            if self._active_chat_id == chat_id:
                self._active_chat_id = None
            self.chatDeleted.emit(chat_id)
            self.refresh_chat_list()

    # ─── retranslateUi ───

    def retranslateUi(self):
        self.setWindowTitle(t('desktop.chatHistory.title'))
        self.search_input.setPlaceholderText(t('desktop.chatHistory.searchPlaceholder'))
        self.search_input.setToolTip(t('desktop.chatHistory.searchTip'))
        self.new_chat_btn.setText(t('desktop.chatHistory.newChat'))
        self.new_chat_btn.setToolTip(t('desktop.chatHistory.newChatTip'))
        self.filter_all_btn.setText(t('desktop.chatHistory.filterAll'))
        self.refresh_chat_list()
