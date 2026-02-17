"""
Helix AI Studio - BIBLE Status Panel (v8.3.1)
BIBLE管理UIパネル: 設定タブ内に配置、状態表示・操作ボタン提供
v8.3.1: パス入力欄を常時有効化、手動パス指定によるBIBLE検索をサポート
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QLineEdit,
)
from PyQt6.QtCore import pyqtSignal

from ..utils.styles import (
    BIBLE_PANEL_STYLE, BIBLE_HEADER_STYLE,
    BIBLE_STATUS_FOUND_STYLE, BIBLE_STATUS_NOT_FOUND_STYLE,
    PRIMARY_BTN, SECONDARY_BTN, SCROLLBAR_STYLE,
    score_color, score_bar_style,
)
from ..bible.bible_schema import BibleInfo
from ..utils.i18n import t

logger = logging.getLogger(__name__)


class BibleStatusPanel(QWidget):
    """
    BIBLE状態表示パネル（mixAI設定タブ内に配置）

    表示内容:
    - BIBLE検出状態
    - プロジェクト名・バージョン
    - 完全性スコア（プログレスバー）
    - 不足セクション一覧
    - アクションボタン（新規作成 / 更新 / 詳細表示）
    """

    # シグナル: ボタン押下時に外部へ通知
    create_requested = pyqtSignal()
    update_requested = pyqtSignal()
    detail_requested = pyqtSignal()
    path_submitted = pyqtSignal(str)  # v8.3.1: パス入力確定時

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bible: Optional[BibleInfo] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # メインフレーム（BIBLE_PANEL_STYLEを適用）
        self.frame = QFrame()
        self.frame.setStyleSheet(BIBLE_PANEL_STYLE)
        frame_layout = QVBoxLayout(self.frame)

        # ヘッダー
        header = QLabel(t('desktop.widgets.biblePanel.header'))
        header.setStyleSheet(BIBLE_HEADER_STYLE)
        frame_layout.addWidget(header)

        # ステータス行
        self.status_label = QLabel(t('desktop.widgets.biblePanel.notFound'))
        self.status_label.setStyleSheet(BIBLE_STATUS_NOT_FOUND_STYLE)
        frame_layout.addWidget(self.status_label)

        # プロジェクト情報
        self.info_label = QLabel(
            t('desktop.widgets.biblePanel.infoLabel')
        )
        self.info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.info_label.setWordWrap(True)
        frame_layout.addWidget(self.info_label)

        # v8.3.1: パス入力欄（常時有効 — 未検出時こそ手動指定が必要）
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(
            t('desktop.widgets.biblePanel.pathPlaceholder')
        )
        self.path_input.setStyleSheet(
            "QLineEdit {"
            "  background: #0a0a1a; border: 1px solid #2a2a3e;"
            "  border-radius: 4px; padding: 4px 8px;"
            "  color: #e0e0e0; font-size: 12px;"
            "}"
            "QLineEdit:focus { border: 1px solid #00d4ff; }"
        )
        self.path_input.setToolTip(
            t('desktop.widgets.biblePanel.pathTooltip')
        )
        self.path_input.returnPressed.connect(self._on_path_submitted)
        path_row.addWidget(self.path_input)

        self.btn_browse = QPushButton(t('desktop.widgets.biblePanel.searchBtn'))
        self.btn_browse.setStyleSheet(SECONDARY_BTN)
        self.btn_browse.setMaximumHeight(28)
        self.btn_browse.setMaximumWidth(60)
        self.btn_browse.setToolTip(t('desktop.widgets.biblePanel.searchTooltip'))
        self.btn_browse.clicked.connect(self._on_path_submitted)
        path_row.addWidget(self.btn_browse)

        frame_layout.addLayout(path_row)

        # 完全性スコア
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setFormat(t('desktop.widgets.biblePanel.completenessFormat'))
        self.score_bar.setMaximumHeight(18)
        self.score_bar.setVisible(False)
        frame_layout.addWidget(self.score_bar)

        # 不足セクション
        self.missing_label = QLabel("")
        self.missing_label.setWordWrap(True)
        self.missing_label.setStyleSheet("color: #ff8800; font-size: 11px;")
        self.missing_label.setVisible(False)
        frame_layout.addWidget(self.missing_label)

        # ボタン行
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self.btn_create = QPushButton(t('desktop.widgets.biblePanel.createBtn'))
        self.btn_create.setStyleSheet(SECONDARY_BTN)
        self.btn_create.setMaximumHeight(28)
        self.btn_create.setToolTip(t('desktop.widgets.biblePanel.createTooltip'))
        self.btn_create.clicked.connect(self.create_requested.emit)
        btn_layout.addWidget(self.btn_create)

        self.btn_update = QPushButton(t('desktop.widgets.biblePanel.updateBtn'))
        self.btn_update.setStyleSheet(SECONDARY_BTN)
        self.btn_update.setMaximumHeight(28)
        self.btn_update.setEnabled(False)
        self.btn_update.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
        self.btn_update.clicked.connect(self.update_requested.emit)
        btn_layout.addWidget(self.btn_update)

        self.btn_detail = QPushButton(t('desktop.widgets.biblePanel.detailBtn'))
        self.btn_detail.setStyleSheet(SECONDARY_BTN)
        self.btn_detail.setMaximumHeight(28)
        self.btn_detail.setEnabled(False)
        self.btn_detail.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
        self.btn_detail.clicked.connect(self.detail_requested.emit)
        btn_layout.addWidget(self.btn_detail)

        frame_layout.addLayout(btn_layout)

        layout.addWidget(self.frame)

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        # Header is re-set via stylesheet in _setup_ui; refresh label text
        # Status label - re-apply based on current bible state
        if self._bible is None:
            self.status_label.setText(t('desktop.widgets.biblePanel.notFound'))
            self.info_label.setText(t('desktop.widgets.biblePanel.infoLabel'))
        else:
            self.status_label.setText(t('desktop.widgets.biblePanel.foundStatus'))
        self.path_input.setPlaceholderText(t('desktop.widgets.biblePanel.pathPlaceholder'))
        self.path_input.setToolTip(t('desktop.widgets.biblePanel.pathTooltip'))
        self.btn_browse.setText(t('desktop.widgets.biblePanel.searchBtn'))
        self.btn_browse.setToolTip(t('desktop.widgets.biblePanel.searchTooltip'))
        self.score_bar.setFormat(t('desktop.widgets.biblePanel.completenessFormat'))
        self.btn_create.setText(t('desktop.widgets.biblePanel.createBtn'))
        self.btn_create.setToolTip(t('desktop.widgets.biblePanel.createTooltip'))
        self.btn_update.setText(t('desktop.widgets.biblePanel.updateBtn'))
        self.btn_detail.setText(t('desktop.widgets.biblePanel.detailBtn'))
        if self._bible is None:
            self.btn_update.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
            self.btn_detail.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
        else:
            self.btn_update.setToolTip(t('desktop.widgets.biblePanel.updateTooltip'))
            self.btn_detail.setToolTip(t('desktop.widgets.biblePanel.detailTooltip'))

    def update_bible(self, bible: Optional[BibleInfo]):
        """BIBLE情報でパネルを更新"""
        self._bible = bible

        if bible is None:
            self.status_label.setText(t('desktop.widgets.biblePanel.notFound'))
            self.status_label.setStyleSheet(BIBLE_STATUS_NOT_FOUND_STYLE)
            self.info_label.setText(
                t('desktop.widgets.biblePanel.infoLabel')
            )
            self.info_label.setStyleSheet("color: #888; font-size: 11px;")
            self.score_bar.setVisible(False)
            self.missing_label.setVisible(False)
            self.btn_update.setEnabled(False)
            self.btn_update.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
            self.btn_detail.setEnabled(False)
            self.btn_detail.setToolTip(t('desktop.widgets.biblePanel.disabledTooltip'))
            return

        # 検出済み表示
        self.status_label.setText(t('desktop.widgets.biblePanel.foundStatus'))
        self.status_label.setStyleSheet(BIBLE_STATUS_FOUND_STYLE)

        # v8.3.1: 検出パスをパス入力欄に表示
        if bible.file_path:
            self.path_input.setText(str(bible.file_path))

        self.info_label.setText(
            f"{bible.project_name} v{bible.version}"
            + (f' "{bible.codename}"' if bible.codename else "")
            + f"\n{t('desktop.widgets.biblePanel.infoFormat', line_count=bible.line_count, sections=len(bible.sections))}"
        )
        self.info_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")

        # 完全性スコア
        score = bible.completeness_score
        score_pct = int(score * 100)
        self.score_bar.setValue(score_pct)
        self.score_bar.setStyleSheet(score_bar_style(score))
        self.score_bar.setVisible(True)

        # 不足セクション
        missing = bible.missing_required_sections
        if missing:
            self.missing_label.setText(
                t('desktop.widgets.biblePanel.missingSections', sections=', '.join(s.value for s in missing))
            )
            self.missing_label.setVisible(True)
        else:
            self.missing_label.setVisible(False)

        self.btn_update.setEnabled(True)
        self.btn_update.setToolTip(t('desktop.widgets.biblePanel.updateTooltip'))
        self.btn_detail.setEnabled(True)
        self.btn_detail.setToolTip(t('desktop.widgets.biblePanel.detailTooltip'))

    def _on_path_submitted(self):
        """v8.3.1: パス入力確定時 — BibleDiscovery検索をトリガー"""
        path = self.path_input.text().strip()
        if path:
            logger.debug(f"[BIBLE Panel] Path submitted: {path}")
            self.path_submitted.emit(path)

    @property
    def current_bible(self) -> Optional[BibleInfo]:
        """現在表示中のBIBLE情報"""
        return self._bible
