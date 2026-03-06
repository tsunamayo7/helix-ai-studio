"""Helix AI Studio — Virtual Desktop タブ

Docker Sandbox の仮想デスクトップを表示・操作する第7タブ。
NoVNC ビューア + Sandbox 設定 の2サブタブ構成。
"""

import json
import logging
import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..utils.i18n import t
from ..utils.styles import (
    COLORS,
    DANGER_BTN,
    PRIMARY_BTN,
    SCROLLBAR_STYLE,
    SECONDARY_BTN,
    SECTION_CARD_STYLE,
)
from ..utils.style_helpers import SS
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
from ..widgets.section_save_button import create_section_save_button

logger = logging.getLogger(__name__)

# QWebEngineView はオプション依存
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

# 設定ファイルパス
_SETTINGS_PATH = Path("config/general_settings.json")


class VirtualDesktopTab(QWidget):
    """Virtual Desktop タブ — sandbox 仮想デスクトップ"""

    statusChanged = pyqtSignal(str)

    def __init__(self, workflow_state=None, main_window=None, sandbox_manager=None, parent=None):
        super().__init__(parent)
        self._workflow_state = workflow_state
        self._main_window = main_window
        self._sandbox_manager = sandbox_manager
        self._promotion_engine = None

        # 状態追跡
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)

        self._setup_ui()
        self._load_settings()
        self._update_docker_status()

    def set_sandbox_manager(self, manager):
        """SandboxManager の参照を設定"""
        self._sandbox_manager = manager
        if manager:
            manager.statusChanged.connect(self._on_sandbox_status_changed)
            manager.errorOccurred.connect(self._on_sandbox_error)
            from ..sandbox.promotion_engine import PromotionEngine
            self._promotion_engine = PromotionEngine()
            # v12.0.1: SandboxManager設定後にDocker状態を再チェック
            self._update_docker_status()
            # Docker daemon 応答が遅い場合に備えて遅延リトライ
            QTimer.singleShot(3000, self._update_docker_status)
            QTimer.singleShot(8000, self._update_docker_status)

    # ─── UI 構築 ───

    def _setup_ui(self):
        """UI 全体を構築"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # サブタブ
        self._sub_tabs = QTabWidget()
        self._sub_tabs.setDocumentMode(True)
        layout.addWidget(self._sub_tabs)

        # Sub-tab 1: デスクトップ
        self._desktop_widget = self._create_desktop_tab()
        self._sub_tabs.addTab(self._desktop_widget, t("desktop.virtualDesktop.desktopSubTab"))

        # Sub-tab 2: 設定
        self._settings_widget = self._create_settings_tab()
        self._sub_tabs.addTab(self._settings_widget, t("desktop.virtualDesktop.settingsSubTab"))

        # サブタブショートカット
        QShortcut(QKeySequence("Ctrl+Shift+1"), self, lambda: self._sub_tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+Shift+2"), self, lambda: self._sub_tabs.setCurrentIndex(1))

    def _create_desktop_tab(self) -> QWidget:
        """デスクトップサブタブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- ツールバー ---
        toolbar = QHBoxLayout()

        self._start_btn = QPushButton(t("desktop.virtualDesktop.startBtn"))
        self._start_btn.setStyleSheet(PRIMARY_BTN)
        self._start_btn.setFixedHeight(32)
        self._start_btn.clicked.connect(self._on_start)
        toolbar.addWidget(self._start_btn)

        self._stop_btn = QPushButton(t("desktop.virtualDesktop.stopBtn"))
        self._stop_btn.setStyleSheet(SECONDARY_BTN)
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        toolbar.addWidget(self._stop_btn)

        self._screenshot_btn = QPushButton(t("desktop.virtualDesktop.screenshotBtn"))
        self._screenshot_btn.setStyleSheet(SECONDARY_BTN)
        self._screenshot_btn.setFixedHeight(32)
        self._screenshot_btn.setEnabled(False)
        self._screenshot_btn.clicked.connect(self._on_screenshot)
        toolbar.addWidget(self._screenshot_btn)

        self._promote_btn = QPushButton(t("desktop.virtualDesktop.promoteBtn"))
        self._promote_btn.setStyleSheet(PRIMARY_BTN)
        self._promote_btn.setFixedHeight(32)
        self._promote_btn.setEnabled(False)
        self._promote_btn.clicked.connect(self._on_promote)
        toolbar.addWidget(self._promote_btn)

        self._reset_btn = QPushButton(t("desktop.virtualDesktop.resetBtn"))
        self._reset_btn.setStyleSheet(DANGER_BTN)
        self._reset_btn.setFixedHeight(32)
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._on_reset)
        toolbar.addWidget(self._reset_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- ステータスバー ---
        status_layout = QHBoxLayout()
        self._status_label = QLabel(t("desktop.virtualDesktop.statusStopped"))
        self._status_label.setStyleSheet(SS.muted())
        status_layout.addWidget(self._status_label)

        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(SS.dim())
        status_layout.addWidget(self._stats_label)

        status_layout.addStretch()
        layout.addLayout(status_layout)

        # --- メインコンテンツ（スプリッター: ファイルブラウザ | NoVNC） ---
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 左パネル: ファイルブラウザ ──
        file_panel = QWidget()
        file_panel_layout = QVBoxLayout(file_panel)
        file_panel_layout.setContentsMargins(4, 4, 4, 4)
        file_panel_layout.setSpacing(4)

        file_header = QHBoxLayout()
        file_title = QLabel(t("desktop.virtualDesktop.fileBrowserTitle"))
        file_title.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        file_header.addWidget(file_title)

        self._file_refresh_btn = QPushButton("🔄")
        self._file_refresh_btn.setFixedSize(28, 28)
        self._file_refresh_btn.setToolTip(t("desktop.virtualDesktop.fileBrowserRefresh"))
        self._file_refresh_btn.clicked.connect(self._refresh_file_tree)
        self._file_refresh_btn.setEnabled(False)
        file_header.addWidget(self._file_refresh_btn)
        file_header.addStretch()
        file_panel_layout.addLayout(file_header)

        # パスバー
        self._file_path_label = QLabel("/workspace")
        self._file_path_label.setStyleSheet(f"color: #888; font-size: 11px; padding: 2px 4px; background: {COLORS['bg_surface']};")
        file_panel_layout.addWidget(self._file_path_label)

        # ファイルツリー
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels([
            t("desktop.virtualDesktop.fileColName"),
            t("desktop.virtualDesktop.fileColSize"),
        ])
        self._file_tree.setColumnWidth(0, 200)
        self._file_tree.setColumnWidth(1, 70)
        self._file_tree.setStyleSheet(SCROLLBAR_STYLE)
        self._file_tree.itemDoubleClicked.connect(self._on_file_tree_double_click)
        file_panel_layout.addWidget(self._file_tree, stretch=1)

        # 戻るボタン
        self._file_back_btn = QPushButton(t("desktop.virtualDesktop.fileBrowserBack"))
        self._file_back_btn.setStyleSheet(SECONDARY_BTN)
        self._file_back_btn.setFixedHeight(28)
        self._file_back_btn.clicked.connect(self._on_file_back)
        self._file_back_btn.setEnabled(False)
        file_panel_layout.addWidget(self._file_back_btn)

        file_panel.setMinimumWidth(200)
        file_panel.setMaximumWidth(400)
        self._main_splitter.addWidget(file_panel)

        # ── 右パネル: NoVNC ビューア / プレースホルダー ──
        self._viewer_stack = QWidget()
        viewer_layout = QVBoxLayout(self._viewer_stack)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        # プレースホルダー
        self._placeholder = QWidget()
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ph_icon = QLabel("🖥️")
        ph_icon.setFont(QFont("Segoe UI Emoji", 48))
        ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(ph_icon)

        self._ph_text = QLabel(t("desktop.virtualDesktop.placeholder"))
        self._ph_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ph_text.setStyleSheet(SS.muted(14))
        self._ph_text.setWordWrap(True)
        ph_layout.addWidget(self._ph_text)

        # Docker未検出メッセージ
        self._docker_missing_label = QLabel(t("desktop.virtualDesktop.placeholderDockerMissing"))
        self._docker_missing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._docker_missing_label.setStyleSheet(SS.warn())
        self._docker_missing_label.setWordWrap(True)
        self._docker_missing_label.setVisible(False)
        ph_layout.addWidget(self._docker_missing_label)

        # ブラウザで開くボタン（QWebEngineView 未利用時のフォールバック）
        self._open_browser_btn = QPushButton(t("desktop.virtualDesktop.openBrowserBtn"))
        self._open_browser_btn.setStyleSheet(SECONDARY_BTN)
        self._open_browser_btn.setFixedHeight(32)
        self._open_browser_btn.setVisible(False)
        self._open_browser_btn.clicked.connect(self._on_open_browser)
        ph_layout.addWidget(self._open_browser_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._placeholder.setStyleSheet(f"background: {COLORS['bg_surface']};")
        viewer_layout.addWidget(self._placeholder)

        # QWebEngineView (利用可能な場合)
        self._web_view = None
        if HAS_WEBENGINE:
            self._web_view = QWebEngineView()
            self._web_view.setVisible(False)
            viewer_layout.addWidget(self._web_view)

        self._main_splitter.addWidget(self._viewer_stack)

        # スプリッター初期比率: ファイルブラウザ 25% / NoVNC 75%
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)

        # 現在のファイルブラウザパス
        self._current_browse_path = "/workspace"

        layout.addWidget(self._main_splitter, stretch=1)

        # --- Promotion パネル (初期非表示) ---
        self._promotion_panel = self._create_promotion_panel()
        self._promotion_panel.setVisible(False)
        layout.addWidget(self._promotion_panel)

        return widget

    def _create_promotion_panel(self) -> QGroupBox:
        """本番適用パネル"""
        group = QGroupBox(t("desktop.virtualDesktop.promoteTitle"))
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # 変更ファイルツリー
        self._changes_tree = QTreeWidget()
        self._changes_tree.setHeaderLabels(["", t("desktop.virtualDesktop.filePath"),
                                            t("desktop.virtualDesktop.changeType"),
                                            t("desktop.virtualDesktop.changes")])
        self._changes_tree.setColumnWidth(0, 30)
        self._changes_tree.setColumnWidth(1, 400)
        self._changes_tree.setStyleSheet(SCROLLBAR_STYLE)
        self._changes_tree.setMaximumHeight(200)
        layout.addWidget(self._changes_tree)

        # ボタン行
        btn_layout = QHBoxLayout()

        self._diff_preview_btn = QPushButton(t("desktop.virtualDesktop.diffPreviewBtn"))
        self._diff_preview_btn.setStyleSheet(SECONDARY_BTN)
        self._diff_preview_btn.setFixedHeight(32)
        self._diff_preview_btn.clicked.connect(self._on_diff_preview)
        btn_layout.addWidget(self._diff_preview_btn)

        self._apply_btn = QPushButton(t("desktop.virtualDesktop.applyBtn"))
        self._apply_btn.setStyleSheet(PRIMARY_BTN)
        self._apply_btn.setFixedHeight(32)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        self._cancel_promote_btn = QPushButton(t("desktop.virtualDesktop.cancelBtn"))
        self._cancel_promote_btn.setStyleSheet(SECONDARY_BTN)
        self._cancel_promote_btn.setFixedHeight(32)
        self._cancel_promote_btn.clicked.connect(lambda: self._promotion_panel.setVisible(False))
        btn_layout.addWidget(self._cancel_promote_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    def _create_settings_tab(self) -> QWidget:
        """設定サブタブ"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLLBAR_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ─── バックエンド選択 ───
        backend_group = QGroupBox(t("desktop.virtualDesktop.backendGroup"))
        backend_group.setStyleSheet(SECTION_CARD_STYLE)
        backend_layout = QHBoxLayout(backend_group)
        backend_layout.addWidget(QLabel(t("desktop.virtualDesktop.backendLabel")))
        self._backend_combo = NoScrollComboBox()
        self._backend_combo.addItem(t("desktop.virtualDesktop.backendDocker"), "docker")
        self._backend_combo.addItem(t("desktop.virtualDesktop.backendGuacamole"), "guacamole")
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        backend_layout.addWidget(self._backend_combo)
        backend_layout.addStretch()
        layout.addWidget(backend_group)

        # ─── Docker 設定コンテナ（Docker 選択時のみ表示）───
        self._docker_settings_widget = QWidget()
        docker_settings_layout = QVBoxLayout(self._docker_settings_widget)
        docker_settings_layout.setContentsMargins(0, 0, 0, 0)
        docker_settings_layout.setSpacing(12)

        # --- 基本設定 ---
        basic_group = QGroupBox(t("desktop.virtualDesktop.settingsGroup"))
        basic_group.setStyleSheet(SECTION_CARD_STYLE)
        basic_layout = QVBoxLayout(basic_group)

        # Docker イメージ
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.dockerImage")))
        self._image_combo = NoScrollComboBox()
        self._image_combo.addItem("helix-sandbox:latest")
        self._image_combo.setEditable(True)
        row.addWidget(self._image_combo)
        basic_layout.addLayout(row)

        # CPU
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.cpuLimit")))
        self._cpu_spin = NoScrollSpinBox()
        self._cpu_spin.setRange(1, 16)
        self._cpu_spin.setValue(2)
        self._cpu_spin.setSuffix(" cores")
        row.addWidget(self._cpu_spin)
        row.addStretch()
        basic_layout.addLayout(row)

        # メモリ
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.memoryLimit")))
        self._memory_spin = NoScrollSpinBox()
        self._memory_spin.setRange(1, 32)
        self._memory_spin.setValue(2)
        self._memory_spin.setSuffix(" GB")
        row.addWidget(self._memory_spin)
        row.addStretch()
        basic_layout.addLayout(row)

        # 解像度
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.resolution")))
        self._resolution_combo = NoScrollComboBox()
        self._resolution_combo.addItems(["1280x720", "1920x1080", "1024x768"])
        row.addWidget(self._resolution_combo)
        row.addStretch()
        basic_layout.addLayout(row)

        # タイムアウト
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.timeout")))
        self._timeout_spin = NoScrollSpinBox()
        self._timeout_spin.setRange(5, 480)
        self._timeout_spin.setValue(60)
        self._timeout_spin.setSuffix(f" {t('desktop.virtualDesktop.minutes')}")
        row.addWidget(self._timeout_spin)
        row.addStretch()
        basic_layout.addLayout(row)

        docker_settings_layout.addWidget(basic_group)

        # --- ワークスペース設定 ---
        ws_group = QGroupBox(t("desktop.virtualDesktop.workspaceGroup"))
        ws_group.setStyleSheet(SECTION_CARD_STYLE)
        ws_layout = QVBoxLayout(ws_group)

        # プロジェクトパス
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.projectPath")))
        self._workspace_edit = QLineEdit()
        self._workspace_edit.setPlaceholderText("/path/to/project")
        row.addWidget(self._workspace_edit)
        browse_btn = QPushButton("📁")
        browse_btn.setFixedSize(32, 32)
        browse_btn.clicked.connect(self._browse_workspace)
        row.addWidget(browse_btn)
        ws_layout.addLayout(row)

        # マウントモード
        self._mount_readonly_radio = QRadioButton(t("desktop.virtualDesktop.mountReadonly"))
        self._mount_readonly_radio.setChecked(True)
        ws_layout.addWidget(self._mount_readonly_radio)

        self._mount_rw_radio = QRadioButton(t("desktop.virtualDesktop.mountReadwrite"))
        ws_layout.addWidget(self._mount_rw_radio)

        # 除外パターン
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.excludePatterns")))
        self._exclude_edit = QLineEdit(".git,__pycache__,node_modules,*.pyc,.env")
        row.addWidget(self._exclude_edit)
        ws_layout.addLayout(row)

        docker_settings_layout.addWidget(ws_group)

        # --- ネットワーク設定 ---
        net_group = QGroupBox(t("desktop.virtualDesktop.networkGroup"))
        net_group.setStyleSheet(SECTION_CARD_STYLE)
        net_layout = QVBoxLayout(net_group)

        self._net_isolated_radio = QRadioButton(t("desktop.virtualDesktop.networkIsolated"))
        self._net_isolated_radio.setChecked(True)
        net_layout.addWidget(self._net_isolated_radio)

        self._net_bridge_radio = QRadioButton(t("desktop.virtualDesktop.networkBridge"))
        net_layout.addWidget(self._net_bridge_radio)

        net_warn = QLabel(t("desktop.virtualDesktop.networkWarning"))
        net_warn.setStyleSheet(SS.warn())
        net_warn.setWordWrap(True)
        net_layout.addWidget(net_warn)

        docker_settings_layout.addWidget(net_group)

        # --- Docker 状態 ---
        docker_group = QGroupBox(t("desktop.virtualDesktop.dockerStatusGroup"))
        docker_group.setStyleSheet(SECTION_CARD_STYLE)
        docker_layout = QVBoxLayout(docker_group)

        self._docker_status_label = QLabel("Docker: ...")
        self._docker_status_label.setStyleSheet(SS.muted())
        docker_layout.addWidget(self._docker_status_label)

        self._image_status_label = QLabel("Image: ...")
        self._image_status_label.setStyleSheet(SS.muted())
        docker_layout.addWidget(self._image_status_label)

        docker_btn_row = QHBoxLayout()
        self._build_image_btn = QPushButton(t("desktop.virtualDesktop.buildImageBtn"))
        self._build_image_btn.setStyleSheet(PRIMARY_BTN)
        self._build_image_btn.setFixedHeight(32)
        self._build_image_btn.clicked.connect(self._on_build_image)
        docker_btn_row.addWidget(self._build_image_btn)

        self._delete_image_btn = QPushButton(t("desktop.virtualDesktop.deleteImageBtn"))
        self._delete_image_btn.setStyleSheet(DANGER_BTN)
        self._delete_image_btn.setFixedHeight(32)
        self._delete_image_btn.clicked.connect(self._on_delete_image)
        docker_btn_row.addWidget(self._delete_image_btn)

        self._refresh_btn = QPushButton(t("desktop.virtualDesktop.refreshBtn"))
        self._refresh_btn.setStyleSheet(SECONDARY_BTN)
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.clicked.connect(self._update_docker_status)
        docker_btn_row.addWidget(self._refresh_btn)

        docker_btn_row.addStretch()
        docker_layout.addLayout(docker_btn_row)

        docker_settings_layout.addWidget(docker_group)

        # Docker 設定コンテナをメインレイアウトに追加
        layout.addWidget(self._docker_settings_widget)

        # ─── Guacamole 設定コンテナ（Guacamole 選択時のみ表示）───
        self._guacamole_settings_widget = QWidget()
        guac_settings_layout = QVBoxLayout(self._guacamole_settings_widget)
        guac_settings_layout.setContentsMargins(0, 0, 0, 0)
        guac_settings_layout.setSpacing(12)

        guac_group = QGroupBox(t("desktop.virtualDesktop.guacamoleGroup"))
        guac_group.setStyleSheet(SECTION_CARD_STYLE)
        guac_layout = QVBoxLayout(guac_group)

        # URL
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.guacamoleUrl")))
        self._guac_url_edit = QLineEdit("http://localhost:8080/guacamole")
        row.addWidget(self._guac_url_edit)
        guac_layout.addLayout(row)

        # ユーザー名
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.guacamoleUser")))
        self._guac_user_edit = QLineEdit("guacadmin")
        row.addWidget(self._guac_user_edit)
        guac_layout.addLayout(row)

        # パスワード
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.guacamolePassword")))
        self._guac_pass_edit = QLineEdit("guacadmin")
        self._guac_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        row.addWidget(self._guac_pass_edit)
        guac_layout.addLayout(row)

        # 接続名コンボ
        row = QHBoxLayout()
        row.addWidget(QLabel(t("desktop.virtualDesktop.guacamoleConnection")))
        self._guac_conn_combo = NoScrollComboBox()
        self._guac_conn_combo.setEditable(True)
        row.addWidget(self._guac_conn_combo)
        guac_layout.addLayout(row)

        # ボタン行
        guac_btn_row = QHBoxLayout()
        self._guac_status_label = QLabel(t("desktop.virtualDesktop.guacamoleUnavailable"))
        self._guac_status_label.setStyleSheet(SS.err())
        guac_btn_row.addWidget(self._guac_status_label)
        guac_btn_row.addStretch()
        guac_refresh_btn = QPushButton(t("desktop.virtualDesktop.guacamoleRefreshBtn"))
        guac_refresh_btn.setFixedHeight(28)
        guac_refresh_btn.clicked.connect(self._refresh_guacamole_connections)
        guac_btn_row.addWidget(guac_refresh_btn)
        guac_layout.addLayout(guac_btn_row)

        # ヒント
        hint_label = QLabel(t("desktop.virtualDesktop.guacamoleHint"))
        hint_label.setStyleSheet(f"color: #888; font-size: 9pt;")
        hint_label.setWordWrap(True)
        guac_layout.addWidget(hint_label)

        guac_settings_layout.addWidget(guac_group)
        layout.addWidget(self._guacamole_settings_widget)

        # 初期状態は Docker モード
        self._guacamole_settings_widget.setVisible(False)

        # --- 保存ボタン ---
        save_btn = create_section_save_button(
            self._save_settings,
        )
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # ─── イベントハンドラ ───

    def _on_backend_changed(self, index: int):
        """バックエンド選択変更時にUIを切り替え"""
        backend = self._backend_combo.currentData()
        is_docker = (backend == "docker")
        self._docker_settings_widget.setVisible(is_docker)
        self._guacamole_settings_widget.setVisible(not is_docker)
        # Docker ツールバーボタン（起動/停止）はどちらのモードでも表示
        # Guacamole モード時は Docker の状態チェックをスキップ
        if not is_docker:
            self._update_guacamole_status()

    def _update_guacamole_status(self):
        """Guacamole サーバーの接続状態を更新"""
        from ..sandbox.guacamole_backend import GuacamoleManager
        mgr = GuacamoleManager(self._guac_url_edit.text().strip())
        if mgr.is_available():
            self._guac_status_label.setText(t("desktop.virtualDesktop.guacamoleAvailable"))
            self._guac_status_label.setStyleSheet(SS.ok())
            self._start_btn.setEnabled(True)
        else:
            self._guac_status_label.setText(t("desktop.virtualDesktop.guacamoleUnavailable"))
            self._guac_status_label.setStyleSheet(SS.err())
            self._start_btn.setEnabled(False)

    def _refresh_guacamole_connections(self):
        """Guacamole から接続一覧を取得してコンボボックスに反映"""
        from ..sandbox.guacamole_backend import GuacamoleManager
        url = self._guac_url_edit.text().strip()
        user = self._guac_user_edit.text().strip()
        password = self._guac_pass_edit.text()

        mgr = GuacamoleManager(url)
        if not mgr.is_available():
            self._guac_status_label.setText(t("desktop.virtualDesktop.guacamoleUnavailable"))
            self._guac_status_label.setStyleSheet(SS.err())
            self._start_btn.setEnabled(False)
            QMessageBox.warning(
                self, "Guacamole",
                mgr.get_unavailable_reason()
            )
            return

        token, ds = mgr.authenticate(user, password)
        if not token:
            QMessageBox.warning(
                self, "Guacamole",
                t("desktop.virtualDesktop.guacamoleAuthFailed")
            )
            return

        connections = mgr.list_connections(token, ds)
        self._guac_conn_combo.clear()
        for conn in connections:
            name = conn.get("name", conn.get("identifier", "?"))
            conn_id = conn.get("identifier", "")
            self._guac_conn_combo.addItem(name, conn_id)

        self._guac_status_label.setText(t("desktop.virtualDesktop.guacamoleAvailable"))
        self._guac_status_label.setStyleSheet(SS.ok())
        self._start_btn.setEnabled(True)

    def _on_start_guacamole(self):
        """Guacamole モードでの接続開始"""
        from ..sandbox.guacamole_backend import GuacamoleManager
        url = self._guac_url_edit.text().strip()
        user = self._guac_user_edit.text().strip()
        password = self._guac_pass_edit.text()

        if not url:
            QMessageBox.warning(self, "Guacamole", "Guacamole URL を入力してください。")
            return

        mgr = GuacamoleManager(url)

        # 接続名/IDが指定されていない場合はトップページを表示
        conn_text = self._guac_conn_combo.currentText().strip()
        conn_id = self._guac_conn_combo.currentData() or conn_text

        if not conn_id:
            # 接続指定なし → トップページを埋め込む（自分でログイン）
            client_url = mgr.get_base_url()
        else:
            # 認証してクライアント URL を取得
            token, ds = mgr.authenticate(user, password)
            if not token:
                QMessageBox.warning(
                    self, "Guacamole",
                    t("desktop.virtualDesktop.guacamoleAuthFailed")
                )
                return
            client_url = mgr.get_client_url(conn_id, token, ds)

        self._show_vnc(client_url)
        self._stop_btn.setEnabled(True)

    def _on_start(self):
        """sandbox 起動（Docker / Guacamole どちらのモードにも対応）"""
        # Guacamole モードに分岐
        backend = self._backend_combo.currentData() if hasattr(self, '_backend_combo') else "docker"
        if backend == "guacamole":
            self._on_start_guacamole()
            return

        if not self._sandbox_manager:
            return

        if not self._sandbox_manager.is_docker_available():
            reason = self._sandbox_manager.get_docker_unavailable_reason()
            QMessageBox.warning(
                self, "Docker Not Available",
                f"{t('desktop.virtualDesktop.dockerMissingDialog')}\n\n【詳細】\n{reason}"
            )
            return

        if not self._sandbox_manager.check_image_exists():
            QMessageBox.warning(self, "Image Not Built",
                                t("desktop.virtualDesktop.imageMissingBuild"))
            return

        config = self._build_config()
        self._start_btn.setEnabled(False)
        self._status_label.setText(t("desktop.virtualDesktop.statusCreating"))
        self._status_label.setStyleSheet(SS.warn())

        # コンテナ作成（ブロッキング — 将来的にスレッド化検討）
        info = self._sandbox_manager.create(config)
        if info:
            self._show_vnc(info.vnc_url)
            self._stop_btn.setEnabled(True)
            self._screenshot_btn.setEnabled(True)
            self._promote_btn.setEnabled(True)
            self._reset_btn.setEnabled(True)
            self._file_refresh_btn.setEnabled(True)
            self._file_back_btn.setEnabled(True)
            self._stats_timer.start(5000)
            # ファイルツリー初期表示
            self._refresh_file_tree()
        else:
            self._start_btn.setEnabled(True)

    def _on_stop(self):
        """sandbox 停止"""
        if self._sandbox_manager:
            self._sandbox_manager.destroy()
        self._hide_vnc()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._screenshot_btn.setEnabled(False)
        self._promote_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)
        self._file_refresh_btn.setEnabled(False)
        self._file_back_btn.setEnabled(False)
        self._file_tree.clear()
        self._current_browse_path = "/workspace"
        self._file_path_label.setText("/workspace")
        self._stats_timer.stop()
        self._stats_label.setText("")
        self._promotion_panel.setVisible(False)

    def _on_screenshot(self):
        """スクリーンショット取得"""
        if not self._sandbox_manager:
            return
        data = self._sandbox_manager.screenshot()
        if data:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save Screenshot", "sandbox_screenshot.png", "PNG (*.png)")
            if save_path:
                Path(save_path).write_bytes(data)
                self.statusChanged.emit(f"Screenshot saved: {save_path}")

    def _on_promote(self):
        """本番適用パネルを表示"""
        if not self._promotion_engine or not self._sandbox_manager:
            return

        diff = self._promotion_engine.generate_diff(self._sandbox_manager)
        changes = self._promotion_engine.preview_changes(diff)

        self._changes_tree.clear()
        if not changes:
            QMessageBox.information(self, "Promotion",
                                    t("desktop.virtualDesktop.noChanges"))
            return

        for change in changes:
            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setText(1, change.path)
            item.setText(2, change.change_type)
            item.setText(3, f"+{change.additions} -{change.deletions}")
            if change.is_binary:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setDisabled(True)
            if change.is_sensitive:
                item.setForeground(2, Qt.GlobalColor.yellow)
            self._changes_tree.addTopLevelItem(item)

        self._promotion_panel.setVisible(True)

    def _on_reset(self):
        """sandbox リセット (停止→再作成)"""
        reply = QMessageBox.question(
            self, "Reset",
            t("desktop.virtualDesktop.resetConfirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_stop()
            self._on_start()

    def _on_diff_preview(self):
        """差分プレビューダイアログ"""
        if not self._promotion_engine or not self._sandbox_manager:
            return

        diff = self._promotion_engine.generate_diff(self._sandbox_manager)
        dialog = QDialog(self)
        dialog.setWindowTitle(t("desktop.virtualDesktop.diffPreviewBtn"))
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)

        text_edit = QPlainTextEdit()
        text_edit.setPlainText(diff or "No diff available")
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(SS.code())
        layout.addWidget(text_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dialog.close)
        layout.addWidget(btn_box)

        dialog.exec()

    def _on_apply(self):
        """選択ファイルをホストに適用"""
        if not self._promotion_engine or not self._sandbox_manager:
            return

        # 選択ファイル取得
        selected = []
        for i in range(self._changes_tree.topLevelItemCount()):
            item = self._changes_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.text(1))

        if not selected:
            QMessageBox.warning(self, "Promotion",
                                t("desktop.virtualDesktop.noFilesSelected"))
            return

        # 確認ダイアログ
        reply = QMessageBox.question(
            self, "Promotion",
            t("desktop.virtualDesktop.promoteConfirm").replace("{count}", str(len(selected))),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        target = self._workspace_edit.text() or "."
        result = self._promotion_engine.apply(self._sandbox_manager, target, selected)

        if result.success:
            msg = t("desktop.virtualDesktop.promoteSuccess").replace("{count}", str(len(result.applied_files)))
            msg += f"\n{t('desktop.virtualDesktop.promoteBackupCreated').replace('{path}', result.backup_path)}"
            QMessageBox.information(self, "Promotion", msg)
            self._promotion_panel.setVisible(False)
            self.statusChanged.emit(msg)
        else:
            QMessageBox.critical(self, "Promotion Error", result.error or "Unknown error")

    def _on_open_browser(self):
        """ブラウザで NoVNC を開く"""
        if self._sandbox_manager:
            url = self._sandbox_manager.get_vnc_url()
            if url:
                webbrowser.open(url)

    def _on_build_image(self):
        """Docker イメージビルド"""
        if not self._sandbox_manager:
            return
        self._build_image_btn.setEnabled(False)
        self._build_image_btn.setText("Building...")
        success = self._sandbox_manager.build_image(
            progress_callback=lambda msg: logger.info(f"[Build] {msg}")
        )
        self._build_image_btn.setEnabled(True)
        self._build_image_btn.setText(t("desktop.virtualDesktop.buildImageBtn"))
        self._update_docker_status()
        if success:
            QMessageBox.information(self, "Build", "Image built successfully")
        else:
            QMessageBox.critical(self, "Build", "Image build failed")

    def _on_delete_image(self):
        """Docker イメージ削除"""
        if not self._sandbox_manager or not self._sandbox_manager.is_docker_available():
            return
        reply = QMessageBox.question(
            self, "Delete Image",
            "Delete helix-sandbox:latest image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not self._sandbox_manager.remove_image():
                QMessageBox.critical(self, "Error", "Failed to remove image")
            self._update_docker_status()

    def _browse_workspace(self):
        """ワークスペースパス選択"""
        path = QFileDialog.getExistingDirectory(self, "Select Workspace")
        if path:
            self._workspace_edit.setText(path)

    def _on_sandbox_status_changed(self, status_str: str):
        """SandboxManager からの状態変更通知"""
        status_map = {
            "none": (t("desktop.virtualDesktop.statusStopped"), SS.muted()),
            "creating": (t("desktop.virtualDesktop.statusCreating"), SS.warn()),
            "running": (t("desktop.virtualDesktop.statusRunning"), SS.ok()),
            "stopped": (t("desktop.virtualDesktop.statusStopped"), SS.muted()),
            "error": ("Error", SS.err()),
            "promoting": (t("desktop.virtualDesktop.promoteTitle"), SS.info()),
        }
        text, style = status_map.get(status_str, (status_str, SS.muted()))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(style)
        self.statusChanged.emit(f"Sandbox: {text}")

    # ─── ファイルブラウザ ───

    def _refresh_file_tree(self):
        """ファイルツリーを更新"""
        if not self._sandbox_manager:
            return

        self._file_tree.clear()
        result = self._sandbox_manager.list_dir(self._current_browse_path)

        if "error" in result:
            item = QTreeWidgetItem([f"Error: {result['error']}", ""])
            self._file_tree.addTopLevelItem(item)
            return

        entries = result.get("entries", [])
        if not entries and "listing" in result:
            # フォールバック: 生テキストから簡易パース
            item = QTreeWidgetItem([result["listing"][:100], ""])
            self._file_tree.addTopLevelItem(item)
            return

        for entry in entries:
            name = entry.get("name", "")
            etype = entry.get("type", "file")
            size = entry.get("size", 0)

            icon = "📁" if etype == "dir" else "📄"
            size_str = self._format_size(size) if etype == "file" else ""
            item = QTreeWidgetItem([f"{icon} {name}", size_str])
            item.setData(0, Qt.ItemDataRole.UserRole, {
                "name": name, "type": etype,
                "path": f"{self._current_browse_path.rstrip('/')}/{name}",
            })
            self._file_tree.addTopLevelItem(item)

        self._file_path_label.setText(self._current_browse_path)

    def _on_file_tree_double_click(self, item, column):
        """ファイルツリーのダブルクリック — ディレクトリなら中に入る"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data["type"] == "dir":
            self._current_browse_path = data["path"]
            self._refresh_file_tree()

    def _on_file_back(self):
        """ファイルブラウザで一階層上に戻る"""
        if self._current_browse_path in ("/", "/workspace"):
            return
        import posixpath
        parent = posixpath.dirname(self._current_browse_path)
        if not parent:
            parent = "/workspace"
        self._current_browse_path = parent
        self._refresh_file_tree()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """バイト数を読みやすい形式に変換"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _on_sandbox_error(self, error: str):
        """SandboxManager からのエラー通知"""
        QMessageBox.critical(self, "Sandbox Error", error)

    # ─── VNC ビューア ───

    def _show_vnc(self, url: str):
        """NoVNC ビューアを表示"""
        if self._web_view and HAS_WEBENGINE:
            from PyQt6.QtCore import QUrl
            self._placeholder.setVisible(False)
            self._web_view.setVisible(True)
            self._web_view.setUrl(QUrl(url))
        else:
            # QWebEngineView 未利用 → ブラウザフォールバック
            self._open_browser_btn.setVisible(True)
            self._ph_text.setText(f"NoVNC: {url}")
            webbrowser.open(url)

    def _hide_vnc(self):
        """NoVNC ビューアを非表示"""
        if self._web_view and HAS_WEBENGINE:
            self._web_view.setVisible(False)
            from PyQt6.QtCore import QUrl
            self._web_view.setUrl(QUrl("about:blank"))
        self._placeholder.setVisible(True)
        self._open_browser_btn.setVisible(False)
        self._ph_text.setText(t("desktop.virtualDesktop.placeholder"))

    # ─── 統計更新 ───

    def _update_stats(self):
        """コンテナリソース統計を更新"""
        if not self._sandbox_manager:
            return
        stats = self._sandbox_manager.get_container_stats()
        if stats:
            self._stats_label.setText(
                f"CPU: {stats['cpu_percent']}% | "
                f"RAM: {stats['memory_mb']:.0f}MB / {stats['memory_limit_mb']:.0f}MB"
            )
        else:
            self._stats_label.setText("")

    def _update_docker_status(self):
        """Docker 接続状態を更新（呼び出し毎にキャッシュリセットして再検出）"""
        # Guacamole モード時は Docker チェックをスキップして Guacamole 状態を更新
        backend = self._backend_combo.currentData() if hasattr(self, '_backend_combo') else "docker"
        if backend == "guacamole":
            self._update_guacamole_status()
            return

        if not self._sandbox_manager:
            self._docker_status_label.setText("Docker: N/A (SandboxManager not set)")
            self._docker_status_label.setStyleSheet(SS.muted())
            self._image_status_label.setText("Image: N/A")
            self._image_status_label.setStyleSheet(SS.muted())
            self._docker_missing_label.setVisible(True)
            self._start_btn.setEnabled(False)
            return

        # 毎回クライアントキャッシュをリセットして再接続を試みる
        self._sandbox_manager.reset_connection()

        _avail = self._sandbox_manager.is_docker_available()
        if _avail:
            self._docker_status_label.setText("Docker: ● Connected")
            self._docker_status_label.setStyleSheet(SS.ok())
            self._docker_missing_label.setVisible(False)
            self._start_btn.setEnabled(True)

            if self._sandbox_manager.check_image_exists():
                self._image_status_label.setText("Image: ● helix-sandbox:latest")
                self._image_status_label.setStyleSheet(SS.ok())
                self._docker_missing_label.setVisible(False)
            else:
                self._image_status_label.setText("Image: ✗ Not built")
                self._image_status_label.setStyleSheet(SS.warn())
                self._docker_missing_label.setText(t("desktop.virtualDesktop.imageMissingBuild"))
                self._docker_missing_label.setVisible(True)
                self._start_btn.setEnabled(False)
        else:
            reason = self._sandbox_manager.get_docker_unavailable_reason()
            self._docker_status_label.setText("Docker: ✗ Not detected")
            self._docker_status_label.setToolTip(reason)
            self._docker_status_label.setStyleSheet(SS.err())
            self._image_status_label.setText("Image: N/A")
            self._image_status_label.setStyleSheet(SS.muted())
            self._docker_missing_label.setText(
                t("desktop.virtualDesktop.placeholderDockerMissing") + f"\n\n{reason}"
            )
            self._docker_missing_label.setVisible(True)
            self._start_btn.setEnabled(False)

    # ─── 設定 I/O ───

    def _build_config(self):
        """UI からの設定値で SandboxConfig を構築"""
        from ..sandbox.sandbox_config import SandboxConfig
        return SandboxConfig(
            image_name=self._image_combo.currentText(),
            cpu_limit=float(self._cpu_spin.value()),
            memory_limit=f"{self._memory_spin.value()}g",
            workspace_path=self._workspace_edit.text(),
            timeout_minutes=self._timeout_spin.value(),
            network_mode="none" if self._net_isolated_radio.isChecked() else "bridge",
            resolution=self._resolution_combo.currentText(),
            mount_readonly=self._mount_readonly_radio.isChecked(),
            exclude_patterns=self._exclude_edit.text(),
        )

    def _save_settings(self):
        """設定を general_settings.json に保存"""
        try:
            data = {}
            if _SETTINGS_PATH.exists():
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)

            data["sandbox"] = {
                "image_name": self._image_combo.currentText(),
                "cpu_limit": self._cpu_spin.value(),
                "memory_limit": self._memory_spin.value(),
                "resolution": self._resolution_combo.currentText(),
                "timeout_minutes": self._timeout_spin.value(),
                "workspace_path": self._workspace_edit.text(),
                "mount_readonly": self._mount_readonly_radio.isChecked(),
                "network_mode": "none" if self._net_isolated_radio.isChecked() else "bridge",
                "exclude_patterns": self._exclude_edit.text(),
                # Guacamole 設定
                "backend": self._backend_combo.currentData(),
                "guacamole_url": self._guac_url_edit.text(),
                "guacamole_user": self._guac_user_edit.text(),
                "guacamole_connection": self._guac_conn_combo.currentText(),
            }

            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.statusChanged.emit("Sandbox settings saved")
        except Exception as e:
            logger.error(f"[VirtualDesktop] Save failed: {e}")

    def _load_settings(self):
        """general_settings.json から設定を読み込み"""
        try:
            if not _SETTINGS_PATH.exists():
                return
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            sandbox = data.get("sandbox", {})
            if not sandbox:
                return

            if "image_name" in sandbox:
                idx = self._image_combo.findText(sandbox["image_name"])
                if idx >= 0:
                    self._image_combo.setCurrentIndex(idx)
                else:
                    self._image_combo.setEditText(sandbox["image_name"])
            if "cpu_limit" in sandbox:
                self._cpu_spin.setValue(int(sandbox["cpu_limit"]))
            if "memory_limit" in sandbox:
                self._memory_spin.setValue(int(sandbox["memory_limit"]))
            if "resolution" in sandbox:
                idx = self._resolution_combo.findText(sandbox["resolution"])
                if idx >= 0:
                    self._resolution_combo.setCurrentIndex(idx)
            if "timeout_minutes" in sandbox:
                self._timeout_spin.setValue(sandbox["timeout_minutes"])
            if "workspace_path" in sandbox:
                self._workspace_edit.setText(sandbox["workspace_path"])
            if "mount_readonly" in sandbox:
                if sandbox["mount_readonly"]:
                    self._mount_readonly_radio.setChecked(True)
                else:
                    self._mount_rw_radio.setChecked(True)
            if "network_mode" in sandbox:
                if sandbox["network_mode"] == "bridge":
                    self._net_bridge_radio.setChecked(True)
                else:
                    self._net_isolated_radio.setChecked(True)
            if "exclude_patterns" in sandbox:
                self._exclude_edit.setText(sandbox["exclude_patterns"])
            # Guacamole 設定
            if "backend" in sandbox:
                idx = self._backend_combo.findData(sandbox["backend"])
                if idx >= 0:
                    self._backend_combo.setCurrentIndex(idx)
                    self._on_backend_changed(idx)
            if "guacamole_url" in sandbox:
                self._guac_url_edit.setText(sandbox["guacamole_url"])
            if "guacamole_user" in sandbox:
                self._guac_user_edit.setText(sandbox["guacamole_user"])
            if "guacamole_connection" in sandbox:
                idx = self._guac_conn_combo.findText(sandbox["guacamole_connection"])
                if idx >= 0:
                    self._guac_conn_combo.setCurrentIndex(idx)

        except Exception as e:
            logger.debug(f"[VirtualDesktop] Load settings: {e}")

    # ─── i18n ───

    def retranslateUi(self):
        """言語切替時のUI更新"""
        self._sub_tabs.setTabText(0, t("desktop.virtualDesktop.desktopSubTab"))
        self._sub_tabs.setTabText(1, t("desktop.virtualDesktop.settingsSubTab"))
        self._start_btn.setText(t("desktop.virtualDesktop.startBtn"))
        self._stop_btn.setText(t("desktop.virtualDesktop.stopBtn"))
        self._screenshot_btn.setText(t("desktop.virtualDesktop.screenshotBtn"))
        self._promote_btn.setText(t("desktop.virtualDesktop.promoteBtn"))
        self._reset_btn.setText(t("desktop.virtualDesktop.resetBtn"))
        self._ph_text.setText(t("desktop.virtualDesktop.placeholder"))
        self._docker_missing_label.setText(t("desktop.virtualDesktop.placeholderDockerMissing"))
        self._open_browser_btn.setText(t("desktop.virtualDesktop.openBrowserBtn"))
        self._build_image_btn.setText(t("desktop.virtualDesktop.buildImageBtn"))
        self._delete_image_btn.setText(t("desktop.virtualDesktop.deleteImageBtn"))
        self._refresh_btn.setText(t("desktop.virtualDesktop.refreshBtn"))
        self._file_refresh_btn.setToolTip(t("desktop.virtualDesktop.fileBrowserRefresh"))
        self._file_back_btn.setText(t("desktop.virtualDesktop.fileBrowserBack"))
        self._file_tree.setHeaderLabels([
            t("desktop.virtualDesktop.fileColName"),
            t("desktop.virtualDesktop.fileColSize"),
        ])
