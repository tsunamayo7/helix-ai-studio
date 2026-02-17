"""
Settings / General Tab - 一般設定
v3.9.0: 大幅簡略化（スクリーンキャプチャ、予算管理、Local接続、Gemini関連を削除）
v8.1.0: Claudeモデル設定・MCPサーバー管理をsoloAIから移設、記憶・知識管理セクション追加
v9.6.0: i18n対応（t()による多言語化）+ 言語切替UIセクション追加

一般設定: モデル・CLI・MCP・記憶知識・表示・自動化
"""

import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QFrame, QTextEdit, QScrollArea,
    QSizePolicy, QMessageBox, QApplication, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

try:
    from ..utils.styles import SPINBOX_STYLE
except ImportError:
    SPINBOX_STYLE = ""

from ..utils.i18n import t, set_language, get_language

logger = logging.getLogger(__name__)


class _NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events unless focused."""
    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class _NoScrollSpinBox(QSpinBox):
    """QSpinBox that ignores wheel events unless focused."""
    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class SettingsCortexTab(QWidget):
    """
    一般設定タブ (v8.1.0)

    Features:
    - Claudeモデル設定（soloAIから移設）
    - Claude CLI 状態
    - MCPサーバー管理（soloAIから移設）
    - 記憶・知識管理（4層メモリ + RAG + Knowledge + Encyclopedia）
    - 表示とテーマ設定
    - 自動化設定
    """

    # シグナル
    settingsChanged = pyqtSignal()

    def __init__(self, workflow_state=None, main_window=None, parent=None):
        super().__init__(parent)
        self.workflow_state = workflow_state
        self.main_window = main_window

        # v8.1.0: メモリマネージャー
        self._memory_manager = None
        try:
            from ..memory.memory_manager import HelixMemoryManager
            self._memory_manager = HelixMemoryManager()
            logger.info("HelixMemoryManager initialized for SettingsCortexTab")
        except Exception as e:
            logger.warning(f"Memory manager init failed for SettingsCortexTab: {e}")

        self._init_ui()
        self._connect_signals()
        self._load_settings()

        # WorkflowStateの更新を監視
        if self.main_window:
            self.main_window.workflowStateChanged.connect(self._on_workflow_state_changed)

    def _on_workflow_state_changed(self, workflow_state):
        """ワークフロー状態が変更されたときの処理"""
        pass

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # 0. 言語切替 (v9.6.0)
        self.lang_group = self._create_language_group()
        content_layout.addWidget(self.lang_group)

        # 1. Claudeモデル設定（soloAIから移設）
        self.model_group = self._create_model_group()
        content_layout.addWidget(self.model_group)

        # 2. Claude CLI 状態
        self.cli_group = self._create_cli_status_group()
        content_layout.addWidget(self.cli_group)

        # 3. MCPサーバー管理（soloAIから移設）
        self.mcp_group = self._create_mcp_group()
        content_layout.addWidget(self.mcp_group)

        # 4. 記憶・知識管理
        self.memory_group = self._create_memory_knowledge_group()
        content_layout.addWidget(self.memory_group)

        # 5. 表示とテーマ
        self.display_group = self._create_display_group()
        content_layout.addWidget(self.display_group)

        # 6. 自動化
        self.auto_group = self._create_auto_group()
        content_layout.addWidget(self.auto_group)

        # 7. Web UIサーバー
        self.webui_group = self._create_web_ui_section()
        content_layout.addWidget(self.webui_group)

        # 8. 保存ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_settings_btn = QPushButton(t('desktop.settings.saveButton'))
        self.save_settings_btn.setToolTip(t('desktop.settings.saveButtonTip'))
        btn_layout.addWidget(self.save_settings_btn)
        content_layout.addLayout(btn_layout)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    # ========================================
    # 0. 言語切替 (v9.6.0)
    # ========================================

    def _create_language_group(self) -> QGroupBox:
        """v9.6.0: 言語切替セクション"""
        group = QGroupBox(t('desktop.settings.language'))
        layout = QHBoxLayout(group)

        self.lang_ja_btn = QPushButton(t('desktop.settings.langJa'))
        self.lang_en_btn = QPushButton(t('desktop.settings.langEn'))

        current_lang = get_language()
        self._update_lang_button_styles(current_lang)

        self.lang_ja_btn.clicked.connect(lambda: self._on_language_changed('ja'))
        self.lang_en_btn.clicked.connect(lambda: self._on_language_changed('en'))

        layout.addWidget(self.lang_ja_btn)
        layout.addWidget(self.lang_en_btn)
        layout.addStretch()

        return group

    def _on_language_changed(self, lang: str):
        """言語変更時の処理"""
        set_language(lang)
        self._update_lang_button_styles(lang)
        # 全UIテキストを更新
        self.retranslateUi()
        # メインウィンドウにも通知
        if self.main_window and hasattr(self.main_window, 'retranslateUi'):
            self.main_window.retranslateUi()

    def _update_lang_button_styles(self, current_lang: str):
        """言語ボタンのスタイルを更新"""
        active_style = "background-color: #059669; color: white; font-weight: bold; padding: 8px 20px; border-radius: 6px; border: none;"
        inactive_style = "background-color: #2d2d2d; color: #888; padding: 8px 20px; border-radius: 6px;"
        self.lang_ja_btn.setStyleSheet(active_style if current_lang == 'ja' else inactive_style)
        self.lang_en_btn.setStyleSheet(active_style if current_lang == 'en' else inactive_style)

    # ========================================
    # 1. Claudeモデル設定（soloAIから移設）
    # ========================================

    def _create_model_group(self) -> QGroupBox:
        """v8.1.0: Claudeモデル設定（soloAIから移設）"""
        group = QGroupBox(t('desktop.settings.claudeModel'))
        layout = QFormLayout(group)

        # デフォルトモデル
        self.default_model_combo = _NoScrollComboBox()
        self.default_model_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.default_model_combo.setToolTip(t('desktop.settings.defaultModelTip'))
        try:
            from ..utils.constants import CLAUDE_MODELS
            for model_def in CLAUDE_MODELS:
                display = t(model_def["i18n_display"]) if "i18n_display" in model_def else model_def["display_name"]
                self.default_model_combo.addItem(
                    display, userData=model_def["id"]
                )
        except ImportError:
            self.default_model_combo.addItem(t('desktop.settings.sonnetFallback'))
        self.default_model_label = QLabel(t('desktop.settings.defaultModel'))
        layout.addRow(self.default_model_label, self.default_model_combo)

        # タイムアウト
        self.timeout_spin = _NoScrollSpinBox()
        self.timeout_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.timeout_spin.setStyleSheet(SPINBOX_STYLE)
        self.timeout_spin.setRange(10, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(t('desktop.settings.timeoutSuffix'))
        self.timeout_spin.setSingleStep(10)
        self.timeout_spin.setToolTip(t('desktop.settings.timeoutTip'))
        self.timeout_label = QLabel(t('desktop.settings.timeout'))
        layout.addRow(self.timeout_label, self.timeout_spin)

        return group

    # ========================================
    # 2. Claude CLI 状態
    # ========================================

    def _create_cli_status_group(self) -> QGroupBox:
        """v8.1.0: Claude CLI状態表示（説明文削除、ボタンのみ）"""
        group = QGroupBox(t('desktop.settings.cliStatus'))
        layout = QVBoxLayout(group)

        # Claude CLI 状態 + ボタン
        cli_layout = QHBoxLayout()
        self.cli_label = QLabel(t('desktop.settings.cliLabel'))
        cli_layout.addWidget(self.cli_label)
        self.cli_test_btn = QPushButton(t('desktop.settings.cliTest'))
        self.cli_test_btn.setToolTip(t('desktop.settings.cliTestTip'))
        self.cli_test_btn.clicked.connect(self._test_cli_connection)
        cli_layout.addWidget(self.cli_test_btn)
        cli_layout.addStretch()
        layout.addLayout(cli_layout)

        # CLI状態ラベル
        self.cli_status_label = QLabel("")
        self.cli_status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.cli_status_label)

        # 初期状態でCLIをチェック
        self._check_cli_status()

        return group

    def _test_cli_connection(self):
        """CLI接続テスト"""
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, message = check_claude_cli_available()
            if available:
                self.cli_status_label.setText(f"✅ {message}")
                self.cli_status_label.setStyleSheet("color: #4CAF50;")
                QMessageBox.information(self, t('desktop.settings.cliSuccessTitle'),
                                        t('desktop.settings.cliSuccessMsg', message=message))
            else:
                self.cli_status_label.setText("❌ " + t('desktop.settings.cliUnavailable'))
                self.cli_status_label.setStyleSheet("color: #f44336;")
                QMessageBox.warning(self, t('desktop.settings.cliErrorTitle'),
                                    t('desktop.settings.cliErrorMsg', message=message))
        except Exception as e:
            self.cli_status_label.setText(t('desktop.settings.cliError'))
            QMessageBox.warning(self, t('desktop.settings.cliErrorTitle'),
                                t('desktop.settings.cliCheckError', message=str(e)))

    def _check_cli_status(self):
        """CLI状態を確認"""
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, message = check_claude_cli_available()
            if available:
                self.cli_status_label.setText(t('desktop.settings.cliAvailable'))
                self.cli_status_label.setStyleSheet("color: #4CAF50;")
            else:
                self.cli_status_label.setText(t('desktop.settings.cliUnavailable'))
                self.cli_status_label.setStyleSheet("color: #ffa500;")
        except Exception:
            self.cli_status_label.setText("")

    # ========================================
    # 3. MCPサーバー管理（soloAIから移設）
    # ========================================

    def _create_mcp_group(self) -> QGroupBox:
        """v8.1.0: MCPサーバー管理（soloAIから移設）"""
        group = QGroupBox(t('desktop.settings.mcp'))
        layout = QVBoxLayout(group)

        # チェックボックス形式
        self.mcp_filesystem_cb = QCheckBox(t('desktop.settings.mcpFilesystem'))
        self.mcp_filesystem_cb.setToolTip(t('desktop.settings.mcpFilesystemTip'))
        self.mcp_filesystem_cb.setChecked(True)
        layout.addWidget(self.mcp_filesystem_cb)

        self.mcp_git_cb = QCheckBox(t('desktop.settings.mcpGit'))
        self.mcp_git_cb.setToolTip(t('desktop.settings.mcpGitTip'))
        self.mcp_git_cb.setChecked(True)
        layout.addWidget(self.mcp_git_cb)

        self.mcp_brave_cb = QCheckBox(t('desktop.settings.mcpBrave'))
        self.mcp_brave_cb.setToolTip(t('desktop.settings.mcpBraveTip'))
        self.mcp_brave_cb.setChecked(True)
        layout.addWidget(self.mcp_brave_cb)

        # 一括ボタン
        btn_layout = QHBoxLayout()
        self.enable_all_btn = QPushButton(t('desktop.settings.mcpEnableAll'))
        self.enable_all_btn.setToolTip(t('desktop.settings.mcpEnableAllTip'))
        self.enable_all_btn.clicked.connect(lambda: self._set_all_mcp(True))
        btn_layout.addWidget(self.enable_all_btn)
        self.disable_all_btn = QPushButton(t('desktop.settings.mcpDisableAll'))
        self.disable_all_btn.setToolTip(t('desktop.settings.mcpDisableAllTip'))
        self.disable_all_btn.clicked.connect(lambda: self._set_all_mcp(False))
        btn_layout.addWidget(self.disable_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    def _set_all_mcp(self, enabled: bool):
        """全MCPサーバーの有効/無効を一括設定"""
        self.mcp_filesystem_cb.setChecked(enabled)
        self.mcp_git_cb.setChecked(enabled)
        self.mcp_brave_cb.setChecked(enabled)

    # ========================================
    # 4. 記憶・知識管理
    # ========================================

    def _create_memory_knowledge_group(self) -> QGroupBox:
        """v8.1.0: 記憶・知識管理セクション"""
        group = QGroupBox(t('desktop.settings.memory'))
        layout = QVBoxLayout(group)

        # 記憶統計
        self.stats_title_label = QLabel(t('desktop.settings.memoryStats'))
        self.stats_title_label.setStyleSheet("font-weight: bold; color: #00d4ff;")
        layout.addWidget(self.stats_title_label)

        self.memory_stats_label = QLabel(t('desktop.settings.memoryStatsDefault'))
        self.memory_stats_label.setToolTip(t('desktop.settings.memoryStatsTip'))
        self.memory_stats_label.setStyleSheet("color: #aaa; padding-left: 10px;")
        layout.addWidget(self.memory_stats_label)

        # RAG有効化
        self.rag_enabled_cb = QCheckBox(t('desktop.settings.ragEnabled'))
        self.rag_enabled_cb.setToolTip(t('desktop.settings.ragEnabledTip'))
        self.rag_enabled_cb.setChecked(True)
        layout.addWidget(self.rag_enabled_cb)

        # 記憶の自動保存
        self.memory_auto_save_cb = QCheckBox(t('desktop.settings.memoryAutoSave'))
        self.memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        self.memory_auto_save_cb.setChecked(True)
        layout.addWidget(self.memory_auto_save_cb)

        # 保存閾値
        threshold_layout = QHBoxLayout()
        self.threshold_label = QLabel(t('desktop.settings.saveThreshold'))
        threshold_layout.addWidget(self.threshold_label)
        self.threshold_combo = QComboBox()
        self.threshold_combo.setToolTip(t('desktop.settings.saveThresholdTip'))
        self.threshold_combo.addItems([
            t('desktop.settings.thresholdLow'),
            t('desktop.settings.thresholdMid'),
            t('desktop.settings.thresholdHigh')
        ])
        self.threshold_combo.setCurrentIndex(1)
        threshold_layout.addWidget(self.threshold_combo)
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)

        # Memory Risk Gate
        self.risk_gate_toggle = QCheckBox(t('desktop.settings.riskGate'))
        self.risk_gate_toggle.setToolTip(t('desktop.settings.riskGateTip'))
        self.risk_gate_toggle.setChecked(True)
        layout.addWidget(self.risk_gate_toggle)

        # Knowledge有効化
        self.knowledge_enabled_cb = QCheckBox(t('desktop.settings.knowledgeEnabled'))
        self.knowledge_enabled_cb.setChecked(True)
        layout.addWidget(self.knowledge_enabled_cb)

        # Knowledge保存先
        path_layout = QHBoxLayout()
        self.knowledge_path_label = QLabel(t('desktop.settings.knowledgePath'))
        path_layout.addWidget(self.knowledge_path_label)
        self.knowledge_path_edit = QLineEdit("data/knowledge")
        path_layout.addWidget(self.knowledge_path_edit)
        layout.addLayout(path_layout)

        # Encyclopedia有効化
        self.encyclopedia_enabled_cb = QCheckBox(t('desktop.settings.encyclopediaEnabled'))
        self.encyclopedia_enabled_cb.setChecked(True)
        layout.addWidget(self.encyclopedia_enabled_cb)

        # ボタン
        btn_layout = QHBoxLayout()
        self.refresh_stats_btn = QPushButton(t('desktop.settings.refreshStats'))
        self.refresh_stats_btn.setToolTip(t('desktop.settings.refreshStatsTip'))
        self.refresh_stats_btn.clicked.connect(self._refresh_memory_stats)
        btn_layout.addWidget(self.refresh_stats_btn)
        self.cleanup_btn = QPushButton(t('desktop.settings.cleanupMemory'))
        self.cleanup_btn.setToolTip(t('desktop.settings.cleanupMemoryTip'))
        self.cleanup_btn.clicked.connect(self._cleanup_old_memories)
        btn_layout.addWidget(self.cleanup_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 初回統計取得
        QTimer.singleShot(500, self._refresh_memory_stats)

        return group

    def _refresh_memory_stats(self):
        """記憶統計を更新"""
        try:
            # 4層メモリ統計
            mem_stats = {"episodes": 0, "semantic_nodes": 0, "procedures": 0}
            if self._memory_manager:
                mem_stats = self._memory_manager.get_stats()

            # Knowledge統計
            knowledge_count = 0
            try:
                from ..knowledge.knowledge_manager import get_knowledge_manager
                km = get_knowledge_manager()
                km_stats = km.get_stats()
                knowledge_count = km_stats.get("count", 0)
            except Exception:
                pass

            # Encyclopedia統計
            encyclopedia_count = 0

            self.memory_stats_label.setText(
                t('desktop.settings.memoryStatsFormat',
                  episodes=mem_stats.get('episodes', 0),
                  semantic=mem_stats.get('semantic_nodes', 0),
                  procedures=mem_stats.get('procedures', 0),
                  knowledge=knowledge_count,
                  encyclopedia=encyclopedia_count)
            )
        except Exception as e:
            self.memory_stats_label.setText(
                t('desktop.settings.memoryStatsError', error=str(e)[:40]))

    def _cleanup_old_memories(self):
        """古い記憶の整理"""
        if self._memory_manager:
            try:
                deleted = self._memory_manager.cleanup_old_memories(days=90)
                QMessageBox.information(
                    self, t('desktop.settings.cleanupDoneTitle'),
                    t('desktop.settings.cleanupDoneMsg', count=deleted)
                )
                self._refresh_memory_stats()
            except Exception as e:
                QMessageBox.warning(self, t('desktop.settings.cleanupErrorTitle'),
                                    t('desktop.settings.cleanupErrorMsg', message=str(e)))
        else:
            QMessageBox.warning(self, t('desktop.settings.cleanupErrorTitle'),
                                t('desktop.settings.cleanupNoManager'))

    # ========================================
    # 5. 表示とテーマ
    # ========================================

    def _create_display_group(self) -> QGroupBox:
        """表示とテーマ設定グループを作成"""
        group = QGroupBox(t('desktop.settings.display'))
        layout = QVBoxLayout(group)

        # ダークモード
        self.dark_mode_cb = QCheckBox(t('desktop.settings.darkMode'))
        self.dark_mode_cb.setToolTip(t('desktop.settings.darkModeTip'))
        self.dark_mode_cb.setChecked(True)
        layout.addWidget(self.dark_mode_cb)

        # フォントサイズ
        font_layout = QHBoxLayout()
        self.font_size_label = QLabel(t('desktop.settings.fontSize'))
        font_layout.addWidget(self.font_size_label)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setStyleSheet(SPINBOX_STYLE)
        self.font_size_spin.setToolTip(t('desktop.settings.fontSizeTip'))
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setValue(10)
        font_layout.addWidget(self.font_size_spin)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        return group

    # ========================================
    # 6. 自動化
    # ========================================

    def _create_auto_group(self) -> QGroupBox:
        """自動化設定グループを作成"""
        group = QGroupBox(t('desktop.settings.automation'))
        layout = QVBoxLayout(group)

        self.auto_save_cb = QCheckBox(t('desktop.settings.autoSave'))
        self.auto_save_cb.setChecked(True)
        layout.addWidget(self.auto_save_cb)

        self.auto_context_cb = QCheckBox(t('desktop.settings.autoContext'))
        self.auto_context_cb.setChecked(True)
        layout.addWidget(self.auto_context_cb)

        return group

    # ========================================
    # 7. Web UIサーバー
    # ========================================

    def _create_web_ui_section(self) -> QGroupBox:
        """Web UIサーバー設定セクション（v9.3.0拡張）"""
        group = QGroupBox(t('desktop.settings.webUI'))
        layout = QVBoxLayout(group)

        # 起動/停止トグルボタン
        toggle_row = QHBoxLayout()
        self.web_ui_toggle = QPushButton(t('desktop.settings.webStart'))
        self.web_ui_toggle.setCheckable(True)
        self.web_ui_toggle.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white;
                padding: 10px 20px; border-radius: 8px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:checked {
                background-color: #dc2626;
            }
        """)
        self.web_ui_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.web_ui_toggle.clicked.connect(self._toggle_web_server)
        toggle_row.addWidget(self.web_ui_toggle)

        self.web_ui_status_label = QLabel(t('desktop.settings.webStopped'))
        self.web_ui_status_label.setStyleSheet("color: #888; font-size: 12px;")
        toggle_row.addWidget(self.web_ui_status_label)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # アクセスURL表示
        self.web_ui_url_label = QLabel("")
        self.web_ui_url_label.setStyleSheet("color: #00d4ff; font-size: 12px;")
        self.web_ui_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.web_ui_url_label)

        # v9.3.0: 自動起動チェックボックス
        auto_row = QHBoxLayout()
        self.web_auto_start_cb = QCheckBox(t('desktop.settings.webAutoStart'))
        self.web_auto_start_cb.setStyleSheet("color: #e5e7eb; font-size: 12px;")
        self.web_auto_start_cb.setChecked(self._load_auto_start_setting())
        self.web_auto_start_cb.stateChanged.connect(self._save_auto_start_setting)
        auto_row.addWidget(self.web_auto_start_cb)
        auto_row.addStretch()
        layout.addLayout(auto_row)

        # ポート番号
        port_row = QHBoxLayout()
        self.port_label = QLabel(t('desktop.settings.webPort'))
        self.port_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        port_row.addWidget(self.port_label)
        self.web_port_spin = QSpinBox()
        self.web_port_spin.setRange(1024, 65535)
        self.web_port_spin.setValue(self._load_port_setting())
        self.web_port_spin.setFixedWidth(80)
        port_row.addWidget(self.web_port_spin)
        port_row.addStretch()
        layout.addLayout(port_row)

        return group

    def _toggle_web_server(self):
        """サーバー起動/停止"""
        if self.web_ui_toggle.isChecked():
            try:
                from ..web.launcher import start_server_background
                port = self.web_port_spin.value()
                self._web_server_thread = start_server_background(port=port)
                self.web_ui_toggle.setText(t('desktop.settings.webStop'))
                self.web_ui_status_label.setText(t('desktop.settings.webRunning', port=port))
            except Exception as e:
                self.web_ui_toggle.setChecked(False)
                self.web_ui_toggle.setText(t('desktop.settings.webStart'))
                self.web_ui_status_label.setText(t('desktop.settings.webStartFailed', error=e))
                return

            # Tailscale IP取得（失敗してもサーバー起動は成功扱い）
            ip = "localhost"
            try:
                import subprocess as _sp
                tailscale_cmds = [
                    [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"],
                    ["tailscale", "ip", "-4"],
                ]
                for cmd in tailscale_cmds:
                    try:
                        result = _sp.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0 and result.stdout.strip():
                            ip = result.stdout.strip()
                            break
                    except (FileNotFoundError, _sp.TimeoutExpired):
                        continue
            except Exception:
                pass
            self.web_ui_url_label.setText(f"📱 http://{ip}:{port}")
        else:
            if hasattr(self, '_web_server_thread') and self._web_server_thread:
                self._web_server_thread.stop()
                self._web_server_thread = None
            self.web_ui_toggle.setText(t('desktop.settings.webStart'))
            self.web_ui_status_label.setText(t('desktop.settings.webStopped'))
            self.web_ui_url_label.setText("")

    def _load_auto_start_setting(self) -> bool:
        """自動起動設定を読み込み"""
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("web_server", {}).get("auto_start", False)
        except Exception:
            return False

    def _save_auto_start_setting(self, state):
        """自動起動設定を保存"""
        try:
            config_path = Path("config/config.json")
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            if "web_server" not in config:
                config["web_server"] = {}
            config["web_server"]["auto_start"] = bool(state)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Auto-start setting save failed: {e}")

    def _load_port_setting(self) -> int:
        """ポート設定を読み込み"""
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("web_server", {}).get("port", 8500)
        except Exception:
            return 8500

    # ========================================
    # シグナル接続 + 設定保存/読み込み
    # ========================================

    def _connect_signals(self):
        """シグナルを接続"""
        self.save_settings_btn.clicked.connect(self._on_save_settings)

    def _on_save_settings(self):
        """設定保存 (v8.1.0: モデル/MCP/記憶設定を追加)"""
        import json
        from pathlib import Path

        try:
            config_dir = Path(__file__).parent.parent.parent / "config"
            config_dir.mkdir(exist_ok=True)
            config_path = config_dir / "general_settings.json"

            settings_data = {
                # Claudeモデル設定
                "default_model": self.default_model_combo.currentText(),
                "default_model_id": self.default_model_combo.currentData() or "",
                "timeout_minutes": self.timeout_spin.value(),
                # MCPサーバー
                "mcp_servers": {
                    "filesystem": self.mcp_filesystem_cb.isChecked(),
                    "git": self.mcp_git_cb.isChecked(),
                    "brave-search": self.mcp_brave_cb.isChecked(),
                },
                # 記憶・知識管理
                "rag_enabled": self.rag_enabled_cb.isChecked(),
                "memory_auto_save": self.memory_auto_save_cb.isChecked(),
                "save_threshold": self.threshold_combo.currentText(),
                "risk_gate_enabled": self.risk_gate_toggle.isChecked(),
                "knowledge_enabled": self.knowledge_enabled_cb.isChecked(),
                "knowledge_path": self.knowledge_path_edit.text(),
                "encyclopedia_enabled": self.encyclopedia_enabled_cb.isChecked(),
                # 表示
                "dark_mode": self.dark_mode_cb.isChecked(),
                "font_size": self.font_size_spin.value(),
                # 自動化
                "auto_save": self.auto_save_cb.isChecked(),
                "auto_context": self.auto_context_cb.isChecked(),
            }

            # 既存データを読み込んでマージ（language等を保持）
            existing = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except Exception:
                    pass
            existing.update(settings_data)

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

            # v8.1.0: app_settings.json にも memory セクションを追加
            try:
                app_settings_path = config_dir / "app_settings.json"
                app_settings = {}
                if app_settings_path.exists():
                    with open(app_settings_path, 'r', encoding='utf-8') as f:
                        app_settings = json.load(f)
                app_settings["memory"] = {
                    "auto_save": self.memory_auto_save_cb.isChecked(),
                    "risk_gate_enabled": self.risk_gate_toggle.isChecked(),
                    "save_threshold": self.threshold_combo.currentText(),
                }
                with open(app_settings_path, 'w', encoding='utf-8') as f:
                    json.dump(app_settings, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"app_settings.json update failed: {e}")

            self.settingsChanged.emit()

            # 視覚フィードバック
            sender = self.sender()
            if sender:
                original_text = sender.text()
                sender.setText(t('desktop.settings.saveSuccess'))
                sender.setEnabled(False)
                QTimer.singleShot(2000, lambda: (
                    sender.setText(original_text), sender.setEnabled(True)))

        except Exception as e:
            QMessageBox.warning(self, t('common.error'),
                                t('desktop.settings.saveError', message=str(e)))

    def _load_settings(self):
        """保存済み設定を読み込み"""
        import json
        from pathlib import Path

        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "general_settings.json"
            if not config_path.exists():
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Claudeモデル設定
            if "default_model" in data:
                idx = self.default_model_combo.findText(data["default_model"])
                if idx >= 0:
                    self.default_model_combo.setCurrentIndex(idx)
            if "timeout_minutes" in data:
                self.timeout_spin.setValue(data["timeout_minutes"])

            # MCP
            mcp = data.get("mcp_servers", {})
            if "filesystem" in mcp:
                self.mcp_filesystem_cb.setChecked(mcp["filesystem"])
            if "git" in mcp:
                self.mcp_git_cb.setChecked(mcp["git"])
            if "brave-search" in mcp:
                self.mcp_brave_cb.setChecked(mcp["brave-search"])

            # 記憶・知識
            if "rag_enabled" in data:
                self.rag_enabled_cb.setChecked(data["rag_enabled"])
            if "memory_auto_save" in data:
                self.memory_auto_save_cb.setChecked(data["memory_auto_save"])
            if "save_threshold" in data:
                idx = self.threshold_combo.findText(data["save_threshold"])
                if idx >= 0:
                    self.threshold_combo.setCurrentIndex(idx)
            if "risk_gate_enabled" in data:
                self.risk_gate_toggle.setChecked(data["risk_gate_enabled"])
            if "knowledge_enabled" in data:
                self.knowledge_enabled_cb.setChecked(data["knowledge_enabled"])
            if "knowledge_path" in data:
                self.knowledge_path_edit.setText(data["knowledge_path"])
            if "encyclopedia_enabled" in data:
                self.encyclopedia_enabled_cb.setChecked(data["encyclopedia_enabled"])

            # 表示
            if "dark_mode" in data:
                self.dark_mode_cb.setChecked(data["dark_mode"])
            if "font_size" in data:
                self.font_size_spin.setValue(data["font_size"])

            # 自動化
            if "auto_save" in data:
                self.auto_save_cb.setChecked(data["auto_save"])
            if "auto_context" in data:
                self.auto_context_cb.setChecked(data["auto_context"])

        except Exception as e:
            logger.warning(f"Settings load failed: {e}")

    # ========================================
    # v9.6.0: retranslateUi — 言語変更時に全テキスト更新
    # ========================================

    def retranslateUi(self):
        """言語変更時に全UIテキストを再適用"""
        # 言語ボタンスタイル更新
        self._update_lang_button_styles(get_language())

        # GroupBox titles
        self.lang_group.setTitle(t('desktop.settings.language'))
        self.model_group.setTitle(t('desktop.settings.claudeModel'))
        self.cli_group.setTitle(t('desktop.settings.cliStatus'))
        self.mcp_group.setTitle(t('desktop.settings.mcp'))
        self.memory_group.setTitle(t('desktop.settings.memory'))
        self.display_group.setTitle(t('desktop.settings.display'))
        self.auto_group.setTitle(t('desktop.settings.automation'))
        self.webui_group.setTitle(t('desktop.settings.webUI'))

        # Model group
        self.default_model_label.setText(t('desktop.settings.defaultModel'))
        self.timeout_label.setText(t('desktop.settings.timeout'))
        self.default_model_combo.setToolTip(t('desktop.settings.defaultModelTip'))
        # Update model combo display names for current language
        try:
            from ..utils.constants import CLAUDE_MODELS
            model_idx = self.default_model_combo.currentIndex()
            self.default_model_combo.blockSignals(True)
            for i, model_def in enumerate(CLAUDE_MODELS):
                if i < self.default_model_combo.count():
                    display = t(model_def["i18n_display"]) if "i18n_display" in model_def else model_def["display_name"]
                    self.default_model_combo.setItemText(i, display)
            if 0 <= model_idx < self.default_model_combo.count():
                self.default_model_combo.setCurrentIndex(model_idx)
            self.default_model_combo.blockSignals(False)
        except ImportError:
            pass
        self.timeout_spin.setSuffix(t('desktop.settings.timeoutSuffix'))
        self.timeout_spin.setToolTip(t('desktop.settings.timeoutTip'))

        # CLI group
        self.cli_label.setText(t('desktop.settings.cliLabel'))
        self.cli_test_btn.setText(t('desktop.settings.cliTest'))
        self.cli_test_btn.setToolTip(t('desktop.settings.cliTestTip'))
        # Re-check CLI status to update status label in current language
        self._check_cli_status()

        # MCP group
        self.mcp_filesystem_cb.setText(t('desktop.settings.mcpFilesystem'))
        self.mcp_filesystem_cb.setToolTip(t('desktop.settings.mcpFilesystemTip'))
        self.mcp_git_cb.setText(t('desktop.settings.mcpGit'))
        self.mcp_git_cb.setToolTip(t('desktop.settings.mcpGitTip'))
        self.mcp_brave_cb.setText(t('desktop.settings.mcpBrave'))
        self.mcp_brave_cb.setToolTip(t('desktop.settings.mcpBraveTip'))
        self.enable_all_btn.setText(t('desktop.settings.mcpEnableAll'))
        self.enable_all_btn.setToolTip(t('desktop.settings.mcpEnableAllTip'))
        self.disable_all_btn.setText(t('desktop.settings.mcpDisableAll'))
        self.disable_all_btn.setToolTip(t('desktop.settings.mcpDisableAllTip'))

        # Memory group
        self.stats_title_label.setText(t('desktop.settings.memoryStats'))
        self.memory_stats_label.setToolTip(t('desktop.settings.memoryStatsTip'))
        self.rag_enabled_cb.setText(t('desktop.settings.ragEnabled'))
        self.rag_enabled_cb.setToolTip(t('desktop.settings.ragEnabledTip'))
        self.memory_auto_save_cb.setText(t('desktop.settings.memoryAutoSave'))
        self.memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        self.threshold_label.setText(t('desktop.settings.saveThreshold'))
        self.threshold_combo.setToolTip(t('desktop.settings.saveThresholdTip'))
        # Update threshold combo items preserving selection
        old_idx = self.threshold_combo.currentIndex()
        self.threshold_combo.clear()
        self.threshold_combo.addItems([
            t('desktop.settings.thresholdLow'),
            t('desktop.settings.thresholdMid'),
            t('desktop.settings.thresholdHigh')
        ])
        self.threshold_combo.setCurrentIndex(old_idx)
        self.risk_gate_toggle.setText(t('desktop.settings.riskGate'))
        self.risk_gate_toggle.setToolTip(t('desktop.settings.riskGateTip'))
        self.knowledge_enabled_cb.setText(t('desktop.settings.knowledgeEnabled'))
        self.knowledge_path_label.setText(t('desktop.settings.knowledgePath'))
        self.encyclopedia_enabled_cb.setText(t('desktop.settings.encyclopediaEnabled'))
        self.refresh_stats_btn.setText(t('desktop.settings.refreshStats'))
        self.refresh_stats_btn.setToolTip(t('desktop.settings.refreshStatsTip'))
        self.cleanup_btn.setText(t('desktop.settings.cleanupMemory'))
        self.cleanup_btn.setToolTip(t('desktop.settings.cleanupMemoryTip'))
        # Refresh memory stats (re-fetch updates labels with current language)
        self._refresh_memory_stats()

        # Display group
        self.dark_mode_cb.setText(t('desktop.settings.darkMode'))
        self.dark_mode_cb.setToolTip(t('desktop.settings.darkModeTip'))
        self.font_size_label.setText(t('desktop.settings.fontSize'))
        self.font_size_spin.setToolTip(t('desktop.settings.fontSizeTip'))

        # Auto group
        self.auto_save_cb.setText(t('desktop.settings.autoSave'))
        self.auto_context_cb.setText(t('desktop.settings.autoContext'))

        # Web UI group
        if not self.web_ui_toggle.isChecked():
            self.web_ui_toggle.setText(t('desktop.settings.webStart'))
            self.web_ui_status_label.setText(t('desktop.settings.webStopped'))
        else:
            self.web_ui_toggle.setText(t('desktop.settings.webStop'))
            # Update the running status text with current port
            port = self.web_port_spin.value() if hasattr(self, 'web_port_spin') else 8500
            self.web_ui_status_label.setText(t('desktop.settings.webRunning', port=port))
        self.web_auto_start_cb.setText(t('desktop.settings.webAutoStart'))
        self.port_label.setText(t('desktop.settings.webPort'))

        # Save button
        self.save_settings_btn.setText(t('desktop.settings.saveButton'))
        self.save_settings_btn.setToolTip(t('desktop.settings.saveButtonTip'))

    # ========================================
    # 互換性のためのプロパティ/メソッド
    # ========================================

    @property
    def gemini_timeout_spin(self):
        """Gemini関連は削除されたが、互換性のためダミーを返す"""
        class DummySpinBox:
            def value(self):
                return 5
        return DummySpinBox()
