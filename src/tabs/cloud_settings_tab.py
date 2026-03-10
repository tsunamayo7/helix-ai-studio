"""
Helix AI Studio -- CloudSettingsTab (v12.8.0)

CloudAI 設定タブ。claude_tab.py の設定サブタブから抽出。
認証方式・モデル管理・実行オプション・CLI連携・MCP設定を管理する。
API キーは一般設定 (SettingsCortexTab) に残す。
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QCheckBox,
    QLineEdit, QListWidget, QListWidgetItem,
    QScrollArea, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ..utils.i18n import t, get_language
from ..utils.error_translator import translate_error
from ..utils.styles import COLORS, SPINBOX_STYLE
from ..utils.style_helpers import SS
from ..utils.constants import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL_ID, get_claude_model_by_id
from ..backends import check_claude_cli_available, get_claude_cli_backend
from ..widgets.section_save_button import create_section_save_button
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox

logger = logging.getLogger(__name__)


class CloudSettingsTab(QWidget):
    """CloudAI 設定タブ -- 認証方式・モデル管理・実行オプション・MCP設定"""

    statusChanged = pyqtSignal(str)
    settingsChanged = pyqtSignal()  # 設定変更通知 -> soloAI のモデルコンボを更新

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._init_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """UI構築"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # v12.8.1: タブ最上部に共通保存ボタンを配置
        main_layout.addWidget(create_section_save_button(self._save_all_cloudai_settings))

        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {COLORS['bg_surface']}; }}")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        # --- セクション構築 ---
        self._create_auth_section(scroll_layout)
        self._create_model_settings_section(scroll_layout)
        self._create_exec_options_section(scroll_layout)
        self._create_cli_section(scroll_layout)
        self._create_mcp_section(scroll_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # 保存済み設定を復元
        self._load_claude_settings()
        self._update_auth_status()

    # ------------------------------------------------------------------
    # Section: 認証方式 (Auth)
    # ------------------------------------------------------------------

    def _create_auth_section(self, parent_layout: QVBoxLayout):
        """認証方式セクション"""
        self.api_group = QGroupBox(t('desktop.cloudAI.authGroup'))
        api_layout = QFormLayout()

        # 認証方式コンボ
        self.auth_label = QLabel(t('desktop.cloudAI.authLabel2'))
        self.auth_mode_combo = NoScrollComboBox()
        self.auth_mode_combo.addItems([
            t('desktop.cloudAI.authAutoOption'),    # 0: Auto (API優先->CLI)
            t('desktop.cloudAI.authCliOption'),     # 1: CLI Only
            t('desktop.cloudAI.authApiOption'),     # 2: API Only (後方互換)
            t('desktop.cloudAI.authOllamaOption'),  # 3: Ollama
        ])
        self.auth_mode_combo.setCurrentIndex(0)
        self.auth_mode_combo.setToolTip(t('desktop.cloudAI.authComboTooltipFull'))
        self.auth_mode_combo.currentIndexChanged.connect(self._on_auth_mode_changed)

        self.auth_status_label = QLabel("")
        self.auth_status_label.setStyleSheet("font-size: 9pt; margin-left: 3px;")

        auth_combo_row = QHBoxLayout()
        auth_combo_row.addWidget(self.auth_mode_combo)
        auth_combo_row.addWidget(self.auth_status_label)
        auth_combo_row.addStretch()
        api_layout.addRow(self.auth_label, auth_combo_row)

        # CLIステータス
        cli_status_layout = QHBoxLayout()
        cli_available, cli_msg = check_claude_cli_available()
        self.cli_status_label = QLabel(
            f"{t('desktop.cloudAI.cliEnabled') if cli_available else t('desktop.cloudAI.cliDisabled')}"
        )
        self.cli_status_label.setToolTip(cli_msg)
        cli_status_layout.addWidget(self.cli_status_label)
        self.cli_check_btn = QPushButton(t('common.confirm'))
        self.cli_check_btn.clicked.connect(self._check_cli_status)
        cli_status_layout.addWidget(self.cli_check_btn)
        cli_status_layout.addStretch()
        # v11.5.0: CLI行を非表示 (オブジェクトは他で参照されるため残す)
        # api_layout.addRow("Claude CLI:", cli_status_layout)

        # 統合接続テスト
        test_group_layout = QHBoxLayout()
        self.unified_test_btn = QPushButton(t('desktop.cloudAI.testBtnLabel'))
        self.unified_test_btn.setToolTip(t('desktop.cloudAI.testBtnTooltip'))
        self.unified_test_btn.clicked.connect(self._run_unified_model_test)
        test_group_layout.addWidget(self.unified_test_btn)
        api_layout.addRow("", test_group_layout)

        # 最終テスト成功表示
        self.last_test_success_label = QLabel("")
        self.last_test_success_label.setStyleSheet(SS.ok("9pt"))
        api_layout.addRow("", self.last_test_success_label)
        self._load_last_test_success()

        self.api_group.setLayout(api_layout)
        parent_layout.addWidget(self.api_group)
        self.api_group.setVisible(False)

    # ------------------------------------------------------------------
    # Section: モデル設定
    # ------------------------------------------------------------------

    def _create_model_settings_section(self, parent_layout: QVBoxLayout):
        """モデル設定セクション (v11.0.0)"""
        self.model_settings_group = QGroupBox(t('desktop.cloudAI.modelSettingsGroup'))
        model_settings_layout = QVBoxLayout()

        # 登録済みモデルリスト
        self.cloud_model_list_label = QLabel(t('desktop.cloudAI.registeredModels'))
        self.cloud_model_list_label.setStyleSheet(
            f"font-weight: bold; color: {COLORS['text_primary']}; margin-bottom: 4px;"
        )
        model_settings_layout.addWidget(self.cloud_model_list_label)

        self.cloud_model_list = QListWidget()
        self.cloud_model_list.setMinimumHeight(170)
        self.cloud_model_list.setMaximumHeight(240)
        self.cloud_model_list.setStyleSheet(f"""
            QListWidget {{ background: {COLORS['bg_surface']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['text_disabled']};
                border-radius: 4px; padding: 4px; font-size: 11px; }}
            QListWidget::item {{ padding: 4px; }}
            QListWidget::item:selected {{ background: {COLORS['accent_dim']}; color: white; }}
        """)
        self._refresh_cloud_model_list()
        model_settings_layout.addWidget(self.cloud_model_list)

        # モデル管理ボタン行
        model_btn_row = QHBoxLayout()
        model_btn_row.setSpacing(4)

        _mgmt_btn_style = f"""
            QPushButton {{ background: {COLORS['bg_elevated']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border_strong']};
                border-radius: 4px; padding: 4px 10px; font-size: 11px; }}
            QPushButton:hover {{ background: {COLORS['border_strong']}; }}
        """

        self.cloud_add_model_btn = QPushButton(t('desktop.cloudAI.addModelBtn'))
        self.cloud_add_model_btn.setStyleSheet(_mgmt_btn_style)
        self.cloud_add_model_btn.clicked.connect(self._on_add_cloud_model)
        model_btn_row.addWidget(self.cloud_add_model_btn)

        self.cloud_del_model_btn = QPushButton(t('desktop.cloudAI.deleteModelBtn'))
        self.cloud_del_model_btn.setStyleSheet(_mgmt_btn_style)
        self.cloud_del_model_btn.clicked.connect(self._on_delete_cloud_model)
        model_btn_row.addWidget(self.cloud_del_model_btn)

        self.cloud_edit_json_btn = QPushButton(t('desktop.cloudAI.editJsonBtn'))
        self.cloud_edit_json_btn.setStyleSheet(_mgmt_btn_style)
        self.cloud_edit_json_btn.clicked.connect(self._on_edit_cloud_models_json)
        model_btn_row.addWidget(self.cloud_edit_json_btn)

        self.cloud_reload_btn = QPushButton(t('desktop.cloudAI.reloadModelsBtn'))
        self.cloud_reload_btn.setStyleSheet(_mgmt_btn_style)
        self.cloud_reload_btn.clicked.connect(self._on_reload_cloud_models)
        model_btn_row.addWidget(self.cloud_reload_btn)

        model_btn_row.addStretch()
        model_settings_layout.addLayout(model_btn_row)

        # 後方互換: model_combo (hidden)
        self.model_label = QLabel(t('desktop.cloudAI.soloModelLabel'))
        self.model_combo = NoScrollComboBox()
        for model_def in CLAUDE_MODELS:
            display = t(model_def["i18n_display"]) if model_def.get("i18n_display") else model_def["display_name"]
            self.model_combo.addItem(display, userData=model_def["id"])
        self.model_combo.addItem(t('desktop.cloudAI.modelCodex53'), userData="gpt-5.3-codex")
        self.model_combo.setVisible(False)
        self.model_label.setVisible(False)

        # タイムアウト
        timeout_row = QHBoxLayout()
        self.solo_timeout_label = QLabel(t('desktop.cloudAI.soloTimeoutLabel'))
        self.solo_timeout_spin = NoScrollSpinBox()
        self.solo_timeout_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.solo_timeout_spin.setRange(10, 120)
        self.solo_timeout_spin.setValue(30)
        self.solo_timeout_spin.setSingleStep(10)
        self.solo_timeout_spin.setStyleSheet(SPINBOX_STYLE)
        self.solo_timeout_spin.setSuffix(t('common.timeoutSuffix'))
        self.solo_timeout_spin.setToolTip(t('common.timeoutTip'))
        timeout_row.addWidget(self.solo_timeout_label)
        timeout_row.addWidget(self.solo_timeout_spin)
        timeout_row.addStretch()
        model_settings_layout.addLayout(timeout_row)

        model_settings_layout.addWidget(create_section_save_button(self._save_all_cloudai_settings))

        self.model_settings_group.setLayout(model_settings_layout)
        parent_layout.addWidget(self.model_settings_group)

    # ------------------------------------------------------------------
    # Section: 実行オプション
    # ------------------------------------------------------------------

    def _create_exec_options_section(self, parent_layout: QVBoxLayout):
        """実行オプションセクション"""
        self.mcp_options_group = QGroupBox(t('desktop.cloudAI.mcpAndOptionsGroup'))
        mcp_options_layout = QVBoxLayout()

        # v11.0.0: MCP checkbox removed (MCP設定セクションで詳細に設定可能)
        self.mcp_checkbox = QCheckBox()
        self.mcp_checkbox.setChecked(True)
        self.mcp_checkbox.setVisible(False)

        self.diff_checkbox = QCheckBox(t('desktop.cloudAI.diffCheckLabel'))
        self.diff_checkbox.setChecked(True)
        self.diff_checkbox.setToolTip(t('desktop.cloudAI.diffCheckboxTooltip'))
        mcp_options_layout.addWidget(self.diff_checkbox)

        self.context_checkbox = QCheckBox(t('desktop.cloudAI.autoContextLabel'))
        self.context_checkbox.setChecked(True)
        self.context_checkbox.setToolTip(t('desktop.cloudAI.contextCheckboxTooltip'))
        mcp_options_layout.addWidget(self.context_checkbox)

        self.permission_skip_checkbox = QCheckBox(t('desktop.cloudAI.permissionLabel'))
        self.permission_skip_checkbox.setChecked(True)
        self.permission_skip_checkbox.setToolTip(t('desktop.cloudAI.permissionSkipTooltip'))
        mcp_options_layout.addWidget(self.permission_skip_checkbox)

        # v11.3.0: Browser Use チェックボックス (httpxベースのため常時有効)
        self.browser_use_checkbox = QCheckBox(t('desktop.cloudAI.browserUseLabel'))
        self.browser_use_checkbox.setChecked(False)
        self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseTip'))
        self._browser_use_available = True
        self.browser_use_checkbox.setEnabled(True)
        mcp_options_layout.addWidget(self.browser_use_checkbox)
        mcp_options_layout.addWidget(create_section_save_button(self._save_all_cloudai_settings))

        self.mcp_options_group.setLayout(mcp_options_layout)
        parent_layout.addWidget(self.mcp_options_group)

    # ------------------------------------------------------------------
    # Section: CLI 連携
    # ------------------------------------------------------------------

    def _create_cli_section(self, parent_layout: QVBoxLayout):
        """Claude CLI / Codex CLI 連携セクション (v10.1.0)"""
        # === Claude CLI ===
        self.cli_section_group = QGroupBox(t('desktop.cloudAI.cliSection'))
        cli_section_layout = QFormLayout()
        cli_version_layout = QHBoxLayout()
        self.cli_version_label = QLabel("")
        self.cli_version_label.setStyleSheet(SS.muted("9pt"))
        cli_version_layout.addWidget(self.cli_version_label)
        self.cli_version_check_btn = QPushButton(t('common.confirm'))
        self.cli_version_check_btn.clicked.connect(self._check_cli_version_detail)
        cli_version_layout.addWidget(self.cli_version_check_btn)
        cli_version_layout.addStretch()
        cli_section_layout.addRow("Claude CLI:", cli_version_layout)
        self.cli_section_group.setLayout(cli_section_layout)
        parent_layout.addWidget(self.cli_section_group)
        self._check_cli_version_detail()

        # === Codex CLI ===
        self.codex_section_group = QGroupBox(t('desktop.cloudAI.codexSection'))
        codex_section_layout = QFormLayout()
        codex_status_layout = QHBoxLayout()
        self.codex_version_label = QLabel("")
        self.codex_version_label.setStyleSheet(SS.muted("9pt"))
        codex_status_layout.addWidget(self.codex_version_label)
        self.codex_check_btn = QPushButton(t('common.confirm'))
        self.codex_check_btn.clicked.connect(self._check_codex_version)
        codex_status_layout.addWidget(self.codex_check_btn)
        codex_status_layout.addStretch()
        codex_section_layout.addRow("Codex CLI:", codex_status_layout)
        self.codex_section_group.setLayout(codex_section_layout)
        parent_layout.addWidget(self.codex_section_group)
        self.codex_section_group.setVisible(False)  # v11.5.0: Codex CLIセクション非表示
        self._check_codex_version()

    # ------------------------------------------------------------------
    # Section: MCP Settings
    # ------------------------------------------------------------------

    def _create_mcp_section(self, parent_layout: QVBoxLayout):
        """MCP Settings for cloudAI (v11.0.0)"""
        self.cloudai_mcp_group = QGroupBox(t('desktop.cloudAI.mcpSettings'))
        cloudai_mcp_layout = QVBoxLayout()
        self.cloudai_mcp_filesystem = QCheckBox(t('desktop.settings.mcpFilesystem'))
        self.cloudai_mcp_git = QCheckBox(t('desktop.settings.mcpGit'))
        self.cloudai_mcp_brave = QCheckBox(t('desktop.settings.mcpBrave'))
        cloudai_mcp_layout.addWidget(self.cloudai_mcp_filesystem)
        cloudai_mcp_layout.addWidget(self.cloudai_mcp_git)
        cloudai_mcp_layout.addWidget(self.cloudai_mcp_brave)
        cloudai_mcp_layout.addWidget(create_section_save_button(self._save_cloudai_mcp_settings))
        self.cloudai_mcp_group.setLayout(cloudai_mcp_layout)
        parent_layout.addWidget(self.cloudai_mcp_group)

    # ==================================================================
    # Auth mode handlers
    # ==================================================================

    def _on_auth_mode_changed(self, index: int):
        """v11.4.0: 0=Auto, 1=CLI Only, 2=API Only(廃止互換), 3=Ollama
        NOTE: CloudSettingsTab では状態フラグの変更とステータス更新のみ行う。
        実際のバックエンド切り替えは claude_tab.py 側で行う。
        """
        if index == 0:  # Auto
            self.statusChanged.emit(t('desktop.cloudAI.autoModeEnabled'))
        elif index == 1:  # CLI Only
            cli_available, message = check_claude_cli_available()
            if not cli_available:
                QMessageBox.warning(
                    self,
                    t('desktop.cloudAI.cliAuthWarningTitle'),
                    t('desktop.cloudAI.cliNotAvailableDialogMsg', message=message)
                )
                self.auth_mode_combo.blockSignals(True)
                self.auth_mode_combo.setCurrentIndex(0)
                self.auth_mode_combo.blockSignals(False)
            else:
                self.statusChanged.emit(t('desktop.cloudAI.cliAuthSwitched'))
        elif index == 2:  # API Only
            self.statusChanged.emit(t('desktop.cloudAI.apiAuthSwitched'))
        else:  # index == 3: Ollama
            self.statusChanged.emit(t('desktop.cloudAI.ollamaSwitched', model=""))

        self._update_auth_status()
        self.settingsChanged.emit()

    def _update_auth_status(self):
        """認証状態を更新表示"""
        auth_index = self.auth_mode_combo.currentIndex()
        if auth_index == 3:
            # Ollama モード
            self.auth_status_label.setText("🖥️")
            self.auth_status_label.setStyleSheet(SS.info("12pt"))
            self.auth_status_label.setToolTip(
                t('desktop.cloudAI.ollamaAuthTooltip', url="http://localhost:11434", model="")
            )
        elif auth_index == 1:
            # CLI モード
            cli_available, _ = check_claude_cli_available()
            if cli_available:
                self.auth_status_label.setText("✅")
                self.auth_status_label.setStyleSheet(SS.ok("12pt"))
                self.auth_status_label.setToolTip(
                    t('desktop.cloudAI.cliAuthPrefix')
                    + t('desktop.cloudAI.cliProTooltip')
                )
            else:
                self.auth_status_label.setText("⚠️")
                self.auth_status_label.setStyleSheet(SS.warn("12pt"))
                self.auth_status_label.setToolTip(t('desktop.cloudAI.cliNotConnectedTooltip'))
        else:
            # Auto / API
            self.auth_status_label.setText("⚙️")
            self.auth_status_label.setStyleSheet(SS.warn("12pt"))
            self.auth_status_label.setToolTip(
                t('desktop.cloudAI.apiDeprecatedLongTooltip')
            )

    # ==================================================================
    # CLI Status checks
    # ==================================================================

    def _check_cli_status(self):
        """CLI状態を確認"""
        cli_available, cli_msg = check_claude_cli_available()
        self.cli_status_label.setText(
            f"{t('desktop.cloudAI.cliEnabled') if cli_available else t('desktop.cloudAI.cliDisabled')}"
        )
        self.cli_status_label.setToolTip(cli_msg)
        if cli_available:
            QMessageBox.information(self, t('desktop.cloudAI.cliAvailableTitle'),
                                    t('desktop.cloudAI.cliAvailableMsg', msg=cli_msg))
        else:
            QMessageBox.warning(self, t('desktop.cloudAI.cliAvailableTitle'),
                                t('desktop.cloudAI.cliUnavailableMsg', msg=cli_msg))

    def _check_cli_version_detail(self):
        """v10.1.0: Claude CLI バージョン詳細表示"""
        try:
            from ..utils.subprocess_utils import run_hidden
            result = run_hidden(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace'
            )
            version_str = (result.stdout or "").strip()
            if result.returncode == 0 and version_str:
                self.cli_version_label.setText(f"✓ {version_str}")
                self.cli_version_label.setStyleSheet(SS.ok("9pt"))
            else:
                self.cli_version_label.setText("✗ Not found")
                self.cli_version_label.setStyleSheet(SS.err("9pt"))
        except Exception:
            self.cli_version_label.setText("✗ Not found")
            self.cli_version_label.setStyleSheet(SS.err("9pt"))

    def _check_codex_version(self):
        """v11.0.0: Codex CLI バージョン確認 (Windows .cmd対応)"""
        self.codex_version_label.setText("⏳ checking...")
        self.codex_version_label.setStyleSheet(SS.warn("9pt"))
        self.codex_check_btn.setEnabled(False)
        QTimer.singleShot(50, self._do_codex_check)

    def _do_codex_check(self):
        """Codex CLIを実際にチェック (QTimer経由でUIスレッドで実行)"""
        try:
            from ..backends.codex_cli_backend import check_codex_cli_available
            available, msg = check_codex_cli_available()
            if available:
                display = msg.replace("Codex CLI found: ", "✓ ").split("(")[0].strip()
                self.codex_version_label.setText(display)
                self.codex_version_label.setStyleSheet(SS.ok("9pt"))
            else:
                self.codex_version_label.setText("✗ Not found")
                self.codex_version_label.setStyleSheet(SS.err("9pt"))
        except Exception:
            self.codex_version_label.setText("✗ Not found")
            self.codex_version_label.setStyleSheet(SS.err("9pt"))
        self.codex_check_btn.setEnabled(True)

    # ==================================================================
    # Unified Model Test
    # ==================================================================

    def _run_unified_model_test(self):
        """統合モデルテスト: 現在の認証方式でテスト実行 (v3.9.2)"""
        auth_mode = self.auth_mode_combo.currentIndex()  # 0=Auto, 1=CLI, 2=API, 3=Ollama
        auth_names = ["Auto (API->CLI)", "CLI (Max/Pro)", "API", "Ollama"]
        auth_name = auth_names[auth_mode] if auth_mode < len(auth_names) else t('desktop.cloudAI.unknownAuth')

        try:
            if auth_mode == 0:
                # Auto モード -- API 優先で接続テスト
                from ..backends.api_priority_resolver import resolve_anthropic_connection, ConnectionMode
                method, kwargs = resolve_anthropic_connection(ConnectionMode.AUTO)
                if method == "anthropic_api":
                    from ..backends.anthropic_api_backend import is_anthropic_sdk_available
                    if not is_anthropic_sdk_available():
                        QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                            "anthropic SDK がインストールされていません。\npip install anthropic")
                        return
                    start = time.time()
                    import anthropic
                    client = anthropic.Anthropic(api_key=kwargs["api_key"])
                    resp = client.messages.create(
                        model="claude-sonnet-4-5-20250929", max_tokens=5,
                        messages=[{"role": "user", "content": "Hi"}])
                    latency = time.time() - start
                    self._save_last_test_success("Anthropic API", latency)
                    QMessageBox.information(
                        self, t('desktop.cloudAI.testSuccessTitle'),
                        f"Auto -> Anthropic API 接続成功\nLatency: {latency:.2f}s")
                elif method == "claude_cli":
                    from ..utils.subprocess_utils import run_hidden
                    start = time.time()
                    result = run_hidden(["claude", "--version"],
                                        capture_output=True, text=True, timeout=10)
                    latency = time.time() - start
                    if result.returncode == 0:
                        self._save_last_test_success("CLI (Auto fallback)", latency)
                        QMessageBox.information(
                            self, t('desktop.cloudAI.testSuccessTitle'),
                            f"Auto -> Claude CLI フォールバック接続成功\nLatency: {latency:.2f}s\nCLI: {result.stdout.strip()}")
                    else:
                        QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                            f"CLI テスト失敗: {result.stderr}")
                else:
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                        kwargs.get("reason", "接続先が見つかりません"))

            elif auth_mode == 1:
                # CLI モード
                cli_available, _ = check_claude_cli_available()
                if not cli_available:
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                        t('desktop.cloudAI.testFailedCliMsg'))
                    return
                from ..utils.subprocess_utils import run_hidden
                start = time.time()
                result = run_hidden(
                    ["claude", "--version"],
                    capture_output=True, text=True, timeout=10
                )
                latency = time.time() - start
                if result.returncode == 0:
                    self._save_last_test_success("CLI", latency)
                    QMessageBox.information(
                        self, t('desktop.cloudAI.testSuccessTitle'),
                        t('desktop.cloudAI.testResultMsg', auth_name=auth_name, latency=f"{latency:.2f}")
                        + f"\nCLI Version: {result.stdout.strip()}"
                    )
                else:
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                        t('desktop.cloudAI.testFailedCliError', error=result.stderr))

            elif auth_mode == 2:
                # API モード
                from ..backends.api_priority_resolver import resolve_anthropic_connection, ConnectionMode
                method, kwargs = resolve_anthropic_connection(ConnectionMode.API_ONLY)
                if method == "anthropic_api":
                    from ..backends.anthropic_api_backend import is_anthropic_sdk_available
                    if not is_anthropic_sdk_available():
                        QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                            "anthropic SDK がインストールされていません。\npip install anthropic")
                        return
                    start = time.time()
                    import anthropic
                    client = anthropic.Anthropic(api_key=kwargs["api_key"])
                    resp = client.messages.create(
                        model="claude-sonnet-4-5-20250929", max_tokens=5,
                        messages=[{"role": "user", "content": "Hi"}])
                    latency = time.time() - start
                    self._save_last_test_success("Anthropic API", latency)
                    QMessageBox.information(
                        self, t('desktop.cloudAI.testSuccessTitle'),
                        f"Anthropic API 接続成功\nLatency: {latency:.2f}s")
                else:
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                        kwargs.get("reason", "API キーが設定されていません"))

            elif auth_mode == 3:
                # Ollama モード
                import ollama
                # Ollama URL / model を取得 (メインウィンドウ経由)
                url = "http://localhost:11434"
                model = ""
                if self.main_window and hasattr(self.main_window, 'claude_tab'):
                    ct = self.main_window.claude_tab
                    if hasattr(ct, 'settings_ollama_url'):
                        url = ct.settings_ollama_url.text().strip()
                    if hasattr(ct, 'settings_ollama_model'):
                        model = ct.settings_ollama_model.currentText()
                client = ollama.Client(host=url)
                start = time.time()
                response = client.generate(
                    model=model,
                    prompt="Hello",
                    options={"num_predict": 5}
                )
                latency = time.time() - start
                self._save_last_test_success("Ollama", latency)
                QMessageBox.information(
                    self, t('desktop.cloudAI.testSuccessTitle'),
                    t('desktop.cloudAI.testResultMsgShort', auth_name=auth_name,
                      model=model, latency=f"{latency:.2f}")
                )

        except Exception as e:
            logger.error(f"[Unified Model Test] Error: {e}")
            QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                t('desktop.cloudAI.testFailedAuth', auth=auth_name, error=str(e)))

    # ==================================================================
    # Last test success persistence
    # ==================================================================

    def _load_last_test_success(self):
        """最終テスト成功情報を読み込み (v3.9.2)"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    last_test = data.get("last_test_success", {})
                    if last_test:
                        auth = last_test.get("auth", "")
                        timestamp = last_test.get("timestamp", "")
                        latency = last_test.get("latency", 0)
                        self.last_test_success_label.setText(
                            t('desktop.cloudAI.lastTestSuccessLabel',
                              auth=auth, timestamp=timestamp, latency=f"{latency:.2f}")
                        )
        except Exception:
            pass

    def _save_last_test_success(self, auth_type: str, latency: float):
        """最終テスト成功情報を保存 (v3.9.2)"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
            config_path.parent.mkdir(exist_ok=True)

            data = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            data["last_test_success"] = {
                "auth": auth_type,
                "timestamp": timestamp,
                "latency": latency
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.last_test_success_label.setText(
                t('desktop.cloudAI.lastTestSuccessLabel',
                  auth=auth_type, timestamp=timestamp, latency=f"{latency:.2f}")
            )
        except Exception:
            pass

    # ==================================================================
    # Settings Load / Save
    # ==================================================================

    def _load_claude_settings(self):
        """保存済みのClaude設定を読み込んでUIに反映 (v9.6)"""
        config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if 'auth_mode' in settings and hasattr(self, 'auth_mode_combo'):
                self.auth_mode_combo.blockSignals(True)
                self.auth_mode_combo.setCurrentIndex(int(settings['auth_mode']))
                self.auth_mode_combo.blockSignals(False)
            if 'model_index' in settings and hasattr(self, 'model_combo'):
                self.model_combo.setCurrentIndex(int(settings['model_index']))
            if 'timeout_minutes' in settings and hasattr(self, 'solo_timeout_spin'):
                self.solo_timeout_spin.setValue(int(settings['timeout_minutes']))
            if 'mcp_enabled' in settings and hasattr(self, 'mcp_checkbox'):
                self.mcp_checkbox.setChecked(bool(settings['mcp_enabled']))
            if 'diff_enabled' in settings and hasattr(self, 'diff_checkbox'):
                self.diff_checkbox.setChecked(bool(settings['diff_enabled']))
            if 'auto_context' in settings and hasattr(self, 'context_checkbox'):
                self.context_checkbox.setChecked(bool(settings['auto_context']))
            if 'permission_skip' in settings and hasattr(self, 'permission_skip_checkbox'):
                self.permission_skip_checkbox.setChecked(bool(settings['permission_skip']))
            if 'browser_use_enabled' in settings and hasattr(self, 'browser_use_checkbox'):
                self.browser_use_checkbox.setChecked(bool(settings['browser_use_enabled']))
        except Exception as e:
            logger.debug(f"claude_settings.json load failed: {e}")

    def _save_all_cloudai_settings(self):
        """v11.0.0: Save all cloudAI settings"""
        self._save_claude_settings()

    def _save_claude_settings(self):
        """Claude設定を保存 (v9.9.2: 差分ダイアログ廃止、即時保存)"""
        config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
        config_path.parent.mkdir(exist_ok=True)

        # 既存設定を読み込んで差分更新 (last_test_success を失わないため)
        existing = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                pass

        settings = {
            **existing,
            "auth_mode": self.auth_mode_combo.currentIndex(),
            "model_index": self.model_combo.currentIndex(),
            "timeout_minutes": self.solo_timeout_spin.value() if hasattr(self, 'solo_timeout_spin') else 30,
            "mcp_enabled": self.mcp_checkbox.isChecked(),
            "diff_enabled": self.diff_checkbox.isChecked(),
            "auto_context": self.context_checkbox.isChecked(),
            "permission_skip": self.permission_skip_checkbox.isChecked(),
            "browser_use_enabled": self.browser_use_checkbox.isChecked() if hasattr(self, 'browser_use_checkbox') else False,
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        self.statusChanged.emit(t('desktop.cloudAI.savedStatus'))
        self.settingsChanged.emit()

        # timer-based button feedback
        btn = self.sender()
        if btn:
            original_text = btn.text()
            btn.setText(t('desktop.cloudAI.saveCompleteMsg'))
            btn.setEnabled(False)
            QTimer.singleShot(2000, lambda b=btn, orig=original_text: (
                b.setText(orig), b.setEnabled(True)
            ))

    def _save_cloudai_mcp_settings(self):
        """v11.0.0: cloudAI MCP設定を ~/.claude/settings.json に保存"""
        settings_path = Path.home() / ".claude" / "settings.json"
        try:
            settings = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

            # MCP servers configuration
            mcp_servers = settings.get("mcpServers", {})
            if hasattr(self, 'cloudai_mcp_filesystem') and self.cloudai_mcp_filesystem.isChecked():
                mcp_servers["filesystem"] = {"enabled": True}
            elif "filesystem" in mcp_servers:
                mcp_servers["filesystem"]["enabled"] = False
            if hasattr(self, 'cloudai_mcp_git') and self.cloudai_mcp_git.isChecked():
                mcp_servers["git"] = {"enabled": True}
            elif "git" in mcp_servers:
                mcp_servers["git"]["enabled"] = False
            if hasattr(self, 'cloudai_mcp_brave') and self.cloudai_mcp_brave.isChecked():
                mcp_servers["brave-search"] = {"enabled": True}
            elif "brave-search" in mcp_servers:
                mcp_servers["brave-search"]["enabled"] = False

            settings["mcpServers"] = mcp_servers
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            logger.info("[CloudSettingsTab] Saved cloudAI MCP settings")
            self.statusChanged.emit(t('desktop.cloudAI.savedStatus'))
            self.settingsChanged.emit()
        except Exception as e:
            logger.error(f"Failed to save MCP settings: {e}")

    # ==================================================================
    # Model list management
    # ==================================================================

    def _refresh_cloud_model_list(self):
        """v11.5.0: cloud_models.json からリストウィジェットを更新 (provider バッジ付き)"""
        if not hasattr(self, 'cloud_model_list'):
            return
        self.cloud_model_list.clear()
        try:
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                data = json.loads(config_path.read_text(encoding='utf-8'))
                for i, model in enumerate(data.get("models", []), 1):
                    provider = model.get("provider", "unknown")
                    provider_badge = {
                        "anthropic_api": "Anthropic API",
                        "openai_api":    "OpenAI API",
                        "google_api":    "Google API",
                        "anthropic_cli": "Anthropic CLI",
                        "openai_cli":    "OpenAI CLI",
                        "google_cli":    "Google CLI",
                    }.get(provider, f"? {provider}")
                    # v11.9.4: model_id の表示を短縮 (CLIコマンド引数を除去)
                    raw_id = model.get('model_id', '')
                    display_id = raw_id
                    if ' --model ' in raw_id:
                        display_id = raw_id.split('--model ')[-1].strip()
                    elif ' -m ' in raw_id:
                        display_id = raw_id.split('-m ')[-1].strip()
                    self.cloud_model_list.addItem(
                        f"{i}. {model['name']}  |  {display_id}  [{provider_badge}]"
                    )
        except Exception as e:
            logger.warning(f"Failed to refresh cloud model list: {e}")

    def _on_add_cloud_model(self):
        """v11.5.0: プロバイダー選択 + モデル ID 例示付き追加ダイアログ"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                      QLineEdit, QComboBox, QLabel,
                                      QDialogButtonBox, QFrame)
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.cloudAI.addModelTitle'))
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        # description
        desc_label = QLabel(t('desktop.cloudAI.addModelDesc'))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(SS.muted("11px"))
        layout.addWidget(desc_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['text_disabled']};")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(8)

        # provider combo
        provider_combo = QComboBox()
        provider_combo.addItem(t('desktop.cloudAI.providerAnthropicApi'), "anthropic_api")
        provider_combo.addItem(t('desktop.cloudAI.providerOpenaiApi'), "openai_api")
        provider_combo.addItem(t('desktop.cloudAI.providerGoogleApi'), "google_api")
        provider_combo.addItem(t('desktop.cloudAI.providerAnthropicCli'), "anthropic_cli")
        provider_combo.addItem(t('desktop.cloudAI.providerOpenaiCli'), "openai_cli")
        provider_combo.addItem(t('desktop.cloudAI.providerGoogleCli'), "google_cli")
        provider_combo.setToolTip(t('desktop.cloudAI.providerTooltip'))
        form.addRow(t('desktop.cloudAI.providerLabel'), provider_combo)

        # model ID input
        model_id_input = QLineEdit()
        model_id_input.setPlaceholderText("e.g. claude-sonnet-4-5-20250929")
        model_id_input.setToolTip(t('desktop.cloudAI.modelIdTooltip'))
        form.addRow(t('desktop.cloudAI.addModelCommand'), model_id_input)

        # example text
        EXAMPLES = {
            "anthropic_api": (
                "【Anthropic API Model ID Examples】\n"
                "  claude-opus-4-6\n"
                "  claude-sonnet-4-6\n"
                "  claude-haiku-4-5-20251001\n"
                "Docs: https://docs.anthropic.com/en/docs/about-claude/models"
            ),
            "openai_api": (
                "【OpenAI API Model ID Examples】\n"
                "  gpt-4o  /  gpt-4o-mini\n"
                "  gpt-4.1  /  o3  /  o4-mini\n"
                "Docs: https://platform.openai.com/docs/models"
            ),
            "anthropic_cli": (
                "【Claude CLI Model Examples】\n"
                "  claude-opus-4-6\n"
                "  claude-sonnet-4-6\n"
                "Requires: npm install -g @anthropic-ai/claude-code"
            ),
            "openai_cli": (
                "【Codex CLI Model Examples】\n"
                "  gpt-5.3-codex\n"
                "  gpt-4o\n"
                "Requires: npm install -g @openai/codex"
            ),
            "google_api": (
                "【Google Gemini API Model ID Examples】\n"
                "  gemini-2.5-flash          <- Recommended (stable)\n"
                "  gemini-2.5-pro            <- High performance\n"
                "  gemini-2.5-flash-lite     <- Low cost\n"
                "API Key: https://aistudio.google.com/app/apikey\n"
                "SDK: pip install google-genai"
            ),
            "google_cli": (
                "【Google Gemini CLI Model ID Examples】\n"
                "  gemini-2.5-flash          <- Recommended\n"
                "  gemini-2.5-pro\n"
                "Install: npm install -g @google/gemini-cli\n"
                "Auth: export GEMINI_API_KEY='AIza...'"
            ),
        }

        example_label = QLabel(EXAMPLES["anthropic_api"])
        example_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 10px; font-family: monospace; "
            f"background: {COLORS['bg_card']}; padding: 8px; border-radius: 4px;"
        )
        example_label.setWordWrap(True)

        def _update_example(index):
            key = provider_combo.currentData()
            example_label.setText(EXAMPLES.get(key, ""))
            placeholders = {
                "anthropic_api": "e.g. claude-sonnet-4-6",
                "openai_api": "e.g. gpt-4o",
                "anthropic_cli": "e.g. claude-opus-4-6",
                "openai_cli": "e.g. gpt-5.3-codex",
            }
            model_id_input.setPlaceholderText(placeholders.get(key, ""))

        provider_combo.currentIndexChanged.connect(_update_example)

        # display name input
        name_input = QLineEdit()
        name_input.setPlaceholderText(t('desktop.cloudAI.addModelNamePlaceholder'))
        name_input.setToolTip(t('desktop.cloudAI.addModelNameTooltip'))
        form.addRow(t('desktop.cloudAI.addModelName'), name_input)

        layout.addLayout(form)
        layout.addWidget(example_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        model_id = model_id_input.text().strip()
        name = name_input.text().strip()
        provider = provider_combo.currentData()

        if not model_id:
            QMessageBox.warning(self, t('desktop.cloudAI.addModelErrorTitle'),
                                t('desktop.cloudAI.addModelIdRequired'))
            return

        if not name:
            name = model_id

        try:
            config_path = Path("config/cloud_models.json")
            data = {"models": []}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["models"].append({
                "name": name,
                "model_id": model_id,
                "provider": provider,
                "builtin": False,
            })
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._refresh_cloud_model_list()
            self._notify_model_combo_refresh()
            self.statusChanged.emit(f"Model added: {name} ({provider})")
            self.settingsChanged.emit()
        except Exception as e:
            QMessageBox.warning(self, t('common.error'), str(e))

    def _on_delete_cloud_model(self):
        """v11.0.0: 選択モデルを削除"""
        row = self.cloud_model_list.currentRow()
        if row < 0:
            return
        from PyQt6.QtWidgets import QMessageBox as MB
        reply = MB.question(self, t('desktop.cloudAI.deleteModelConfirm'),
                           t('desktop.cloudAI.deleteModelConfirm'),
                           MB.StandardButton.Yes | MB.StandardButton.No)
        if reply != MB.StandardButton.Yes:
            return
        try:
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                models = data.get("models", [])
                if 0 <= row < len(models):
                    removed = models.pop(row)
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    self._refresh_cloud_model_list()
                    self._notify_model_combo_refresh()
                    self.statusChanged.emit(f"Model removed: {removed.get('name', '')}")
                    self.settingsChanged.emit()
        except Exception as e:
            QMessageBox.warning(self, t('common.error'), str(e))

    def _on_edit_cloud_models_json(self):
        """v11.0.0: cloud_models.json をテキスト編集ダイアログで開く"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.cloudAI.editJsonTitle'))
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)

        editor = QTextEdit()
        editor.setStyleSheet(
            f"QTextEdit {{ background: {COLORS['bg_surface']}; color: {COLORS['text_primary']}; "
            f"font-family: monospace; font-size: 11px; }}"
        )
        try:
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                editor.setPlainText(config_path.read_text(encoding='utf-8'))
        except Exception:
            pass
        layout.addWidget(editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                text = editor.toPlainText()
                json.loads(text)  # validate
                Path("config/cloud_models.json").write_text(text, encoding='utf-8')
                self._refresh_cloud_model_list()
                self._notify_model_combo_refresh()
                self.statusChanged.emit("cloud_models.json updated")
                self.settingsChanged.emit()
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON Error", f"Invalid JSON: {e}")
            except Exception as e:
                QMessageBox.warning(self, t('common.error'), str(e))

    def _on_reload_cloud_models(self):
        """v11.0.0: モデルリストとコンボを再読み込み"""
        self._refresh_cloud_model_list()
        self._notify_model_combo_refresh()
        self.statusChanged.emit("Cloud models reloaded")
        self.settingsChanged.emit()

    def _notify_model_combo_refresh(self):
        """メインウィンドウの claude_tab のモデルコンボを更新通知"""
        if self.main_window and hasattr(self.main_window, 'claude_tab'):
            ct = self.main_window.claude_tab
            if hasattr(ct, '_load_cloud_models_to_combo') and hasattr(ct, 'cloud_model_combo'):
                ct._load_cloud_models_to_combo(ct.cloud_model_combo)

    # ==================================================================
    # retranslateUi
    # ==================================================================

    def retranslateUi(self):
        """言語変更時に全UIテキストを再適用 (設定関連のみ)"""
        # === GroupBox titles ===
        self.api_group.setTitle(t('desktop.cloudAI.authGroup'))
        self.model_settings_group.setTitle(t('desktop.cloudAI.modelSettingsGroup'))
        self.mcp_options_group.setTitle(t('desktop.cloudAI.mcpAndOptionsGroup'))

        # === Auth section ===
        self.auth_label.setText(t('desktop.cloudAI.authLabel2'))
        old_auth_idx = self.auth_mode_combo.currentIndex()
        self.auth_mode_combo.blockSignals(True)
        self.auth_mode_combo.clear()
        self.auth_mode_combo.addItems([
            t('desktop.cloudAI.authAutoOption'),
            t('desktop.cloudAI.authCliOption'),
            t('desktop.cloudAI.authApiOption'),
            t('desktop.cloudAI.authOllamaOption'),
        ])
        self.auth_mode_combo.setCurrentIndex(old_auth_idx)
        self.auth_mode_combo.blockSignals(False)
        self.auth_mode_combo.setToolTip(t('desktop.cloudAI.authComboTooltipFull'))

        cli_available, _ = check_claude_cli_available()
        self.cli_status_label.setText(
            t('desktop.cloudAI.cliEnabled') if cli_available else t('desktop.cloudAI.cliDisabled')
        )
        self.cli_check_btn.setText(t('common.confirm'))
        self.unified_test_btn.setText(t('desktop.cloudAI.testBtnLabel'))
        self.unified_test_btn.setToolTip(t('desktop.cloudAI.testBtnTooltip'))

        # === Model settings section ===
        self.model_label.setText(t('desktop.cloudAI.soloModelLabel'))
        self.model_combo.setToolTip(t('desktop.cloudAI.modelReadonlyTooltip'))
        # Refresh model combo display names for i18n
        if hasattr(self, 'model_combo'):
            for i in range(self.model_combo.count()):
                model_id = self.model_combo.itemData(i)
                if model_id == "gpt-5.3-codex":
                    self.model_combo.setItemText(i, t('desktop.cloudAI.modelCodex53'))
                    continue
                model_def = get_claude_model_by_id(model_id)
                if model_def and model_def.get("i18n_display"):
                    self.model_combo.setItemText(i, t(model_def["i18n_display"]))
        self.solo_timeout_label.setText(t('desktop.cloudAI.soloTimeoutLabel'))
        if hasattr(self, 'solo_timeout_spin'):
            self.solo_timeout_spin.setSuffix(t('common.timeoutSuffix'))

        # === Registered model buttons ===
        if hasattr(self, 'cloud_model_list_label'):
            self.cloud_model_list_label.setText(t('desktop.cloudAI.registeredModels'))
        if hasattr(self, 'cloud_add_model_btn'):
            self.cloud_add_model_btn.setText(t('desktop.cloudAI.addModelBtn'))
        if hasattr(self, 'cloud_del_model_btn'):
            self.cloud_del_model_btn.setText(t('desktop.cloudAI.deleteModelBtn'))
        if hasattr(self, 'cloud_edit_json_btn'):
            self.cloud_edit_json_btn.setText(t('desktop.cloudAI.editJsonBtn'))
        if hasattr(self, 'cloud_reload_btn'):
            self.cloud_reload_btn.setText(t('desktop.cloudAI.reloadModelsBtn'))

        # === Exec options section ===
        self.mcp_checkbox.setText(t('desktop.cloudAI.soloMcpLabel'))
        self.mcp_checkbox.setToolTip(t('desktop.cloudAI.mcpCheckboxTooltip'))
        self.diff_checkbox.setText(t('desktop.cloudAI.diffCheckLabel'))
        self.diff_checkbox.setToolTip(t('desktop.cloudAI.diffCheckboxTooltip'))
        self.context_checkbox.setText(t('desktop.cloudAI.autoContextLabel'))
        self.context_checkbox.setToolTip(t('desktop.cloudAI.contextCheckboxTooltip'))
        self.permission_skip_checkbox.setText(t('desktop.cloudAI.permissionLabel'))
        self.permission_skip_checkbox.setToolTip(t('desktop.cloudAI.permissionSkipTooltip'))
        if hasattr(self, 'browser_use_checkbox'):
            self.browser_use_checkbox.setText(t('desktop.cloudAI.browserUseLabel'))
            self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseTip'))

        # === CLI sections ===
        if hasattr(self, 'cli_section_group'):
            self.cli_section_group.setTitle(t('desktop.cloudAI.cliSection'))
        if hasattr(self, 'codex_section_group'):
            self.codex_section_group.setTitle(t('desktop.cloudAI.codexSection'))

        # === MCP settings ===
        if hasattr(self, 'cloudai_mcp_group'):
            self.cloudai_mcp_group.setTitle(t('desktop.cloudAI.mcpSettings'))
        if hasattr(self, 'cloudai_mcp_filesystem'):
            self.cloudai_mcp_filesystem.setText(t('desktop.settings.mcpFilesystem'))
        if hasattr(self, 'cloudai_mcp_git'):
            self.cloudai_mcp_git.setText(t('desktop.settings.mcpGit'))
        if hasattr(self, 'cloudai_mcp_brave'):
            self.cloudai_mcp_brave.setText(t('desktop.settings.mcpBrave'))
