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
        header = QLabel("BIBLE Manager")
        header.setStyleSheet(BIBLE_HEADER_STYLE)
        frame_layout.addWidget(header)

        # ステータス行
        self.status_label = QLabel("BIBLE未検出")
        self.status_label.setStyleSheet(BIBLE_STATUS_NOT_FOUND_STYLE)
        frame_layout.addWidget(self.status_label)

        # プロジェクト情報
        self.info_label = QLabel(
            "ファイル添付またはパス指定で自動検索します"
        )
        self.info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.info_label.setWordWrap(True)
        frame_layout.addWidget(self.info_label)

        # v8.3.1: パス入力欄（常時有効 — 未検出時こそ手動指定が必要）
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(
            "BIBLEファイルまたはプロジェクトディレクトリのパスを入力..."
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
            "BIBLEファイルのパスまたはプロジェクトディレクトリを入力してEnter\n"
            "カレント→子→親の3段階探索でBIBLEを自動検出します"
        )
        self.path_input.returnPressed.connect(self._on_path_submitted)
        path_row.addWidget(self.path_input)

        self.btn_browse = QPushButton("検索")
        self.btn_browse.setStyleSheet(SECONDARY_BTN)
        self.btn_browse.setMaximumHeight(28)
        self.btn_browse.setMaximumWidth(60)
        self.btn_browse.setToolTip("入力パスからBIBLEを検索します")
        self.btn_browse.clicked.connect(self._on_path_submitted)
        path_row.addWidget(self.btn_browse)

        frame_layout.addLayout(path_row)

        # 完全性スコア
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setFormat("完全性: %p%")
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

        self.btn_create = QPushButton("新規作成")
        self.btn_create.setStyleSheet(SECONDARY_BTN)
        self.btn_create.setMaximumHeight(28)
        self.btn_create.setToolTip("新しいBIBLEファイルをテンプレートから作成します")
        self.btn_create.clicked.connect(self.create_requested.emit)
        btn_layout.addWidget(self.btn_create)

        self.btn_update = QPushButton("更新")
        self.btn_update.setStyleSheet(SECONDARY_BTN)
        self.btn_update.setMaximumHeight(28)
        self.btn_update.setEnabled(False)
        self.btn_update.setToolTip("BIBLEを検出または作成すると有効になります")
        self.btn_update.clicked.connect(self.update_requested.emit)
        btn_layout.addWidget(self.btn_update)

        self.btn_detail = QPushButton("詳細")
        self.btn_detail.setStyleSheet(SECONDARY_BTN)
        self.btn_detail.setMaximumHeight(28)
        self.btn_detail.setEnabled(False)
        self.btn_detail.setToolTip("BIBLEを検出または作成すると有効になります")
        self.btn_detail.clicked.connect(self.detail_requested.emit)
        btn_layout.addWidget(self.btn_detail)

        frame_layout.addLayout(btn_layout)

        layout.addWidget(self.frame)

    def update_bible(self, bible: Optional[BibleInfo]):
        """BIBLE情報でパネルを更新"""
        self._bible = bible

        if bible is None:
            self.status_label.setText("BIBLE未検出")
            self.status_label.setStyleSheet(BIBLE_STATUS_NOT_FOUND_STYLE)
            self.info_label.setText(
                "ファイル添付またはパス指定で自動検索します"
            )
            self.info_label.setStyleSheet("color: #888; font-size: 11px;")
            self.score_bar.setVisible(False)
            self.missing_label.setVisible(False)
            self.btn_update.setEnabled(False)
            self.btn_update.setToolTip("BIBLEを検出または作成すると有効になります")
            self.btn_detail.setEnabled(False)
            self.btn_detail.setToolTip("BIBLEを検出または作成すると有効になります")
            return

        # 検出済み表示
        self.status_label.setText("BIBLE検出済み")
        self.status_label.setStyleSheet(BIBLE_STATUS_FOUND_STYLE)

        # v8.3.1: 検出パスをパス入力欄に表示
        if bible.file_path:
            self.path_input.setText(str(bible.file_path))

        self.info_label.setText(
            f"{bible.project_name} v{bible.version}"
            + (f' "{bible.codename}"' if bible.codename else "")
            + f"\n{bible.line_count}行 | {len(bible.sections)}セクション"
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
                f"不足セクション: {', '.join(s.value for s in missing)}"
            )
            self.missing_label.setVisible(True)
        else:
            self.missing_label.setVisible(False)

        self.btn_update.setEnabled(True)
        self.btn_update.setToolTip("BIBLEの内容を最新のコード変更に基づいて更新します")
        self.btn_detail.setEnabled(True)
        self.btn_detail.setToolTip("BIBLEの全セクション詳細を表示します")

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
