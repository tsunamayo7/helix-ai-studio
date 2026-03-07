"""
Helix AI Studio — OllamaSettingsTab (v12.8.0)

Ollama設定タブ。local_ai_tab.py の設定サブタブから抽出。
Ollama管理・GitHub連携・MCP設定・Browser Use設定を管理する。
"""
import json
import logging
import shutil
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QCheckBox,
    QLineEdit, QTableWidget, QTableWidgetItem,
    QScrollArea, QMessageBox, QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ..utils.i18n import t, get_language
from ..utils.error_translator import translate_error
from ..utils.styles import (
    COLORS, SCROLLBAR_STYLE, PRIMARY_BTN, SECONDARY_BTN,
    SECTION_CARD_STYLE,
)
from ..utils.style_helpers import SS
from ..widgets.section_save_button import (
    create_section_save_button, retranslate_section_save_buttons,
)

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"


class OllamaSettingsTab(QWidget):
    """Ollama設定タブ — ローカルLLM管理・接続設定"""

    statusChanged = pyqtSignal(str)
    settingsChanged = pyqtSignal()       # 設定変更通知 -> soloAI のモデルコンボを更新
    ollamaHostChanged = pyqtSignal(str)  # URL変更通知

    # capability取得完了シグナル
    _caps_ready = pyqtSignal()

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._ollama_host = OLLAMA_HOST
        self._pending_caps = {}
        self._init_ui()
        self._caps_ready.connect(self._apply_capabilities)

    # =========================================================================
    # UI構築
    # =========================================================================

    def _init_ui(self):
        """設定タブのUIを構築"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLLBAR_STYLE)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # === Ollama管理セクション ===
        self.ollama_group = QGroupBox(t('desktop.localAI.ollamaSection'))
        ollama_layout = QVBoxLayout()

        # インストール状態
        ollama_installed = shutil.which("ollama") is not None
        self.ollama_status_label = QLabel(
            t('desktop.localAI.ollamaInstallStatus') if ollama_installed
            else t('desktop.localAI.ollamaNotInstalled')
        )
        self.ollama_status_label.setStyleSheet(
            f"color: {COLORS['success']}; font-weight: bold;" if ollama_installed
            else f"color: {COLORS['error']}; font-weight: bold;"
        )
        ollama_layout.addWidget(self.ollama_status_label)

        if not ollama_installed:
            install_btn = QPushButton(t('desktop.localAI.ollamaInstallBtn'))
            install_btn.clicked.connect(self._open_ollama_install)
            ollama_layout.addWidget(install_btn)

        # 接続URL
        host_row = QHBoxLayout()
        host_row.addWidget(QLabel(t('desktop.localAI.ollamaHostLabel')))
        self.ollama_host_input = QLineEdit(self._ollama_host)
        host_row.addWidget(self.ollama_host_input, 1)
        self.ollama_test_btn = QPushButton(t('desktop.localAI.ollamaTestBtn'))
        self.ollama_test_btn.clicked.connect(self._test_ollama_connection)
        host_row.addWidget(self.ollama_test_btn)
        ollama_layout.addLayout(host_row)

        # v11.0.0: モデル一覧テーブル (capability列追加)
        self.ollama_models_table_label = QLabel(t('desktop.localAI.ollamaModelsTable'))
        ollama_layout.addWidget(self.ollama_models_table_label)
        self.models_table = QTableWidget(0, 7)
        self.models_table.setHorizontalHeaderLabels([
            "Name", "Size", "Modified", "Tools", "Embed", "Vision", "Think"
        ])
        # v11.0.0: Name列をStretch、capability列はResizeToContents
        header = self.models_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        self.models_table.setColumnWidth(1, 70)   # Size
        self.models_table.setColumnWidth(2, 120)  # Modified
        for col in range(3, 7):  # Tools/Embed/Vision/Think
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.models_table.setMaximumHeight(220)
        self.models_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.models_table.setStyleSheet("""
            QTableWidget::item:selected { background-color: #7f1d1d; color: white; }
        """)
        ollama_layout.addWidget(self.models_table)

        # v11.0.0: モデル追加はダイアログ形式 / 削除はハイライト付き
        model_mgmt_row = QHBoxLayout()

        # 後方互換用（hidden）
        self.pull_input = QLineEdit()
        self.pull_input.setVisible(False)

        self.pull_btn = QPushButton(t('desktop.localAI.ollamaPullBtn'))
        self.pull_btn.setStyleSheet(PRIMARY_BTN)
        self.pull_btn.clicked.connect(self._on_add_model_dialog)
        model_mgmt_row.addWidget(self.pull_btn)

        self.rm_btn = QPushButton(t('desktop.localAI.ollamaRmBtn'))
        self.rm_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {COLORS['error']};
                border: 1px solid {COLORS['error']}; border-radius: 4px;
                padding: 6px 14px; font-weight: bold; }}
            QPushButton:hover {{ background: rgba(239, 68, 68, 0.15); }}
        """)
        self.rm_btn.clicked.connect(self._on_remove_model)
        model_mgmt_row.addWidget(self.rm_btn)

        model_mgmt_row.addStretch()
        ollama_layout.addLayout(model_mgmt_row)

        self.ollama_group.setLayout(ollama_layout)
        scroll_layout.addWidget(self.ollama_group)

        # === v10.1.0: GitHub 連携セクション ===
        self.github_group = QGroupBox(t('desktop.localAI.githubSection'))
        self.github_group.setStyleSheet(SECTION_CARD_STYLE)
        github_layout = QVBoxLayout()
        pat_row = QHBoxLayout()
        self.github_pat_label = QLabel(t('desktop.localAI.githubPatLabel'))
        pat_row.addWidget(self.github_pat_label)
        self.github_pat_input = QLineEdit()
        self.github_pat_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_pat_input.setPlaceholderText("ghp_...")
        pat_row.addWidget(self.github_pat_input, 1)
        self.github_test_btn = QPushButton(t('desktop.localAI.githubTestBtn'))
        self.github_test_btn.setStyleSheet(SECONDARY_BTN)
        self.github_test_btn.clicked.connect(self._test_github_connection)
        pat_row.addWidget(self.github_test_btn)
        self.github_save_btn = QPushButton(t('common.save'))
        self.github_save_btn.setStyleSheet(PRIMARY_BTN)
        self.github_save_btn.clicked.connect(self._save_github_pat)
        pat_row.addWidget(self.github_save_btn)
        github_layout.addLayout(pat_row)
        self.github_group.setLayout(github_layout)
        scroll_layout.addWidget(self.github_group)
        self._load_github_pat()

        # === v11.0.0: MCP Settings for localAI (Phase 5) ===
        self.localai_mcp_group = QGroupBox(t('desktop.localAI.mcpSettings'))
        self.localai_mcp_group.setStyleSheet(SECTION_CARD_STYLE)
        mcp_layout = QVBoxLayout()
        self.localai_mcp_filesystem = QCheckBox(t('desktop.settings.mcpFilesystem'))
        self.localai_mcp_filesystem.setToolTip(t('desktop.settings.mcpFilesystemTip'))
        self.localai_mcp_git = QCheckBox(t('desktop.settings.mcpGit'))
        self.localai_mcp_git.setToolTip(t('desktop.settings.mcpGitTip'))
        self.localai_mcp_brave = QCheckBox(t('desktop.settings.mcpBrave'))
        self.localai_mcp_brave.setToolTip(t('desktop.settings.mcpBraveTip'))
        mcp_layout.addWidget(self.localai_mcp_filesystem)
        mcp_layout.addWidget(self.localai_mcp_git)
        mcp_layout.addWidget(self.localai_mcp_brave)
        mcp_layout.addWidget(create_section_save_button(self._save_localai_mcp_settings))
        self.localai_mcp_group.setLayout(mcp_layout)
        scroll_layout.addWidget(self.localai_mcp_group)
        self._load_localai_mcp_settings()

        # === v11.1.0: Browser Use Settings for localAI ===
        self.localai_browser_use_group = QGroupBox(t('desktop.localAI.browserUseGroup'))
        self.localai_browser_use_group.setStyleSheet(SECTION_CARD_STYLE)
        browser_use_layout = QVBoxLayout()
        self.localai_browser_use_cb = QCheckBox(t('desktop.localAI.browserUseLabel'))
        # v11.3.1: httpx フォールバックがあるため常時有効。インストール状況はツールチップで案内
        self.localai_browser_use_cb.setEnabled(True)
        try:
            import browser_use  # noqa: F401
            self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseTip'))
        except ImportError:
            self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseHttpxMode'))
        browser_use_layout.addWidget(self.localai_browser_use_cb)
        browser_use_layout.addWidget(create_section_save_button(self._save_localai_browser_use_setting))
        self.localai_browser_use_group.setLayout(browser_use_layout)
        scroll_layout.addWidget(self.localai_browser_use_group)
        self._load_localai_browser_use_setting()

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    # =========================================================================
    # Ollama接続・モデル管理
    # =========================================================================

    def _test_ollama_connection(self):
        """Ollama接続テスト"""
        host = self.ollama_host_input.text().strip() or OLLAMA_HOST
        old_host = self._ollama_host
        self._ollama_host = host
        try:
            import httpx
            resp = httpx.get(f"{host}/api/tags", timeout=5)
            resp.raise_for_status()
            QMessageBox.information(self, t('common.confirm'), t('desktop.localAI.ollamaTestSuccess'))
            self._refresh_models()
            # ホストが変わった場合はシグナル発行
            if host != old_host:
                self.ollamaHostChanged.emit(host)
                self.settingsChanged.emit()
        except Exception as e:
            QMessageBox.warning(self, t('common.error'),
                                t('desktop.localAI.ollamaTestFailed', error=translate_error(str(e), source="ollama")))

    def _refresh_models(self):
        """Ollamaインストール済みモデルを取得（v11.0.0: 高速表示+遅延capability取得）"""
        try:
            import httpx
            resp = httpx.get(f"{self._ollama_host}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])

            self.models_table.setRowCount(0)

            for m in models:
                name = m.get("name", "")
                row = self.models_table.rowCount()
                self.models_table.insertRow(row)
                self.models_table.setItem(row, 0, QTableWidgetItem(name))
                size_gb = m.get("size", 0) / (1024 ** 3)
                self.models_table.setItem(row, 1, QTableWidgetItem(f"{size_gb:.1f} GB"))
                self.models_table.setItem(row, 2, QTableWidgetItem(
                    m.get("modified_at", "")[:19]))
                # capability列は初期値（後で非同期更新）
                for col in range(3, 7):
                    item = QTableWidgetItem("\u2014")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.models_table.setItem(row, col, item)

            # capability情報を遅延で非同期取得
            if models:
                model_names = [m.get("name", "") for m in models]
                threading.Thread(
                    target=self._fetch_capabilities_bg,
                    args=(model_names,),
                    daemon=True,
                ).start()

            # 設定変更シグナルを発行（モデルリスト更新を通知）
            self.settingsChanged.emit()

        except Exception as e:
            logger.warning(f"[OllamaSettingsTab] Failed to fetch models: {e}")

    def get_model_names(self) -> list:
        """現在テーブルに表示されているモデル名のリストを返す"""
        names = []
        for row in range(self.models_table.rowCount()):
            item = self.models_table.item(row, 0)
            if item:
                names.append(item.text())
        return names

    def _fetch_capabilities_bg(self, model_names: list):
        """バックグラウンドでcapability情報を取得し、完了後UIに反映"""
        results = {}
        for name in model_names:
            results[name] = self._get_model_capabilities(name)
        self._pending_caps = results
        # UIスレッドで更新（signal使用）
        self._caps_ready.emit()

    def _apply_capabilities(self):
        """UIスレッドでcapability列を更新"""
        caps_data = getattr(self, '_pending_caps', {})
        for row in range(self.models_table.rowCount()):
            name_item = self.models_table.item(row, 0)
            if name_item:
                name = name_item.text()
                caps = caps_data.get(name, {})
                for col, key in enumerate(["tools", "embed", "vision", "think"], 3):
                    item = QTableWidgetItem("\u2705" if caps.get(key) else "\u274c")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.models_table.setItem(row, col, item)

    def _get_model_capabilities(self, model_name: str) -> dict:
        """v11.0.0: Ollama API /api/show でモデルのcapabilityを取得"""
        caps = {"tools": False, "embed": False, "vision": False, "think": False}
        try:
            import httpx
            resp = httpx.post(
                f"{self._ollama_host}/api/show",
                json={"name": model_name}, timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                capabilities = data.get("capabilities", [])
                caps["tools"] = "tools" in capabilities
                caps["embed"] = "embed" in capabilities or "embedding" in capabilities
                caps["vision"] = "vision" in capabilities
                caps["think"] = "thinking" in capabilities or "think" in model_name.lower()
        except Exception:
            pass
        return caps

    def _on_add_model_dialog(self):
        """v11.0.0: モデル追加ダイアログ"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.localAI.addModelTitle'))
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(t('desktop.localAI.addModelOllamaName')))
        name_input = QLineEdit()
        name_input.setPlaceholderText("例: llama3.2:3b")
        layout.addWidget(name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            model_name = name_input.text().strip()
            if not model_name:
                return
            self._on_pull_model_by_name(model_name)

    def _on_pull_model_by_name(self, model_name: str):
        """指定名でollama pull"""
        self.pull_btn.setEnabled(False)
        self.pull_btn.setText("Pulling...")
        from ..utils.subprocess_utils import run_hidden
        try:
            run_hidden(["ollama", "pull", model_name], timeout=600)
            QMessageBox.information(
                self, t('common.confirm'),
                f"Model '{model_name}' pulled successfully."
            )
            self._refresh_models()
        except Exception as e:
            QMessageBox.warning(self, t('common.error'), translate_error(str(e), source="ollama"))
        finally:
            self.pull_btn.setEnabled(True)
            self.pull_btn.setText(t('desktop.localAI.ollamaPullBtn'))

    def _on_pull_model(self):
        """モデルをpull (後方互換)"""
        model_name = self.pull_input.text().strip()
        if not model_name:
            return
        self._on_pull_model_by_name(model_name)

    def _on_remove_model(self):
        """選択中のモデルを削除"""
        row = self.models_table.currentRow()
        if row < 0:
            return
        model_name = self.models_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, t('common.confirm'),
            f"Remove model '{model_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from ..utils.subprocess_utils import run_hidden
            run_hidden(["ollama", "rm", model_name], timeout=30)
            self._refresh_models()
        except Exception as e:
            QMessageBox.warning(self, t('common.error'), translate_error(str(e), source="ollama"))

    def _open_ollama_install(self):
        """Ollamaインストールページを開く"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://ollama.com/download"))

    # =========================================================================
    # GitHub連携
    # =========================================================================

    def _test_github_connection(self):
        """v10.1.0: GitHub API 接続テスト"""
        pat = self.github_pat_input.text().strip()
        if not pat:
            QMessageBox.warning(self, t('common.error'), t('common.errors.unauthorized'))
            return
        try:
            import httpx
            resp = httpx.get("https://api.github.com/user",
                             headers={"Authorization": f"Bearer {pat}"},
                             timeout=10)
            if resp.status_code == 200:
                user = resp.json().get("login", "")
                QMessageBox.information(self, t('common.confirm'), f"GitHub connected: {user}")
            else:
                QMessageBox.warning(self, t('common.error'), translate_error(f"HTTP {resp.status_code}"))
        except Exception as e:
            QMessageBox.warning(self, t('common.error'), translate_error(str(e)))

    def _save_github_pat(self):
        """v10.1.0: GitHub PAT を general_settings.json に保存"""
        pat = self.github_pat_input.text().strip()
        settings_path = Path("config/general_settings.json")
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["github_pat"] = pat
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.github_save_btn.setText("\u2705")
            QTimer.singleShot(1500, lambda: self.github_save_btn.setText(t('common.save')))
            self.settingsChanged.emit()
        except Exception as e:
            logger.warning(f"GitHub PAT save failed: {e}")

    def _load_github_pat(self):
        """v10.1.0: 保存済み GitHub PAT を復元"""
        settings_path = Path("config/general_settings.json")
        try:
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                pat = data.get("github_pat", "")
                if pat:
                    self.github_pat_input.setText(pat)
        except Exception:
            pass

    # =========================================================================
    # v11.0.0: MCP Settings (Phase 5)
    # =========================================================================

    def _save_localai_mcp_settings(self):
        """v11.0.0: Save localAI MCP settings to config.json"""
        config_path = Path("config/config.json")
        try:
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            mcp_settings = config.get("mcp_settings", {})
            mcp_settings["localAI"] = {
                "filesystem": self.localai_mcp_filesystem.isChecked(),
                "git": self.localai_mcp_git.isChecked(),
                "brave": self.localai_mcp_brave.isChecked(),
            }
            config["mcp_settings"] = mcp_settings
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("[OllamaSettingsTab] Saved MCP settings")
            self.settingsChanged.emit()
        except Exception as e:
            logger.error(f"Failed to save MCP settings: {e}")

    def _load_localai_mcp_settings(self):
        """v11.0.0: Load localAI MCP settings from config.json"""
        config_path = Path("config/config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                mcp = config.get("mcp_settings", {}).get("localAI", {})
                self.localai_mcp_filesystem.setChecked(mcp.get("filesystem", False))
                self.localai_mcp_git.setChecked(mcp.get("git", False))
                self.localai_mcp_brave.setChecked(mcp.get("brave", False))
        except Exception as e:
            logger.debug(f"[OllamaSettingsTab] MCP settings load: {e}")

    # =========================================================================
    # v11.1.0: Browser Use Settings
    # =========================================================================

    def _save_localai_browser_use_setting(self):
        """v11.1.0: Save Browser Use setting for localAI to config.json"""
        config_path = Path("config/config.json")
        try:
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            config["localai_browser_use_enabled"] = self.localai_browser_use_cb.isChecked()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("[OllamaSettingsTab] Saved Browser Use setting")
            self.settingsChanged.emit()
        except Exception as e:
            logger.error(f"Failed to save Browser Use setting: {e}")

    def _load_localai_browser_use_setting(self):
        """v11.1.0: Load Browser Use setting for localAI from config.json"""
        config_path = Path("config/config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                enabled = config.get("localai_browser_use_enabled", False)
                self.localai_browser_use_cb.setChecked(enabled)
        except Exception as e:
            logger.debug(f"[OllamaSettingsTab] Browser Use setting load: {e}")

    # =========================================================================
    # プロパティ
    # =========================================================================

    @property
    def ollama_host(self) -> str:
        """現在のOllamaホストURLを返す"""
        return self._ollama_host

    @ollama_host.setter
    def ollama_host(self, value: str):
        """OllamaホストURLを設定"""
        self._ollama_host = value
        if hasattr(self, 'ollama_host_input'):
            self.ollama_host_input.setText(value)

    # =========================================================================
    # i18n
    # =========================================================================

    def retranslateUi(self):
        """言語変更時にUIテキストを再適用"""
        # Ollama管理セクション
        if hasattr(self, 'ollama_group'):
            self.ollama_group.setTitle(t('desktop.localAI.ollamaSection'))
        if hasattr(self, 'ollama_status_label'):
            ollama_installed = shutil.which("ollama") is not None
            self.ollama_status_label.setText(
                t('desktop.localAI.ollamaInstallStatus') if ollama_installed
                else t('desktop.localAI.ollamaNotInstalled')
            )
        if hasattr(self, 'ollama_models_table_label'):
            self.ollama_models_table_label.setText(t('desktop.localAI.ollamaModelsTable'))
        if hasattr(self, 'pull_btn'):
            self.pull_btn.setText(t('desktop.localAI.ollamaPullBtn'))
        if hasattr(self, 'rm_btn'):
            self.rm_btn.setText(t('desktop.localAI.ollamaRmBtn'))

        # Browser Use settings
        if hasattr(self, 'localai_browser_use_group'):
            self.localai_browser_use_group.setTitle(t('desktop.localAI.browserUseGroup'))
        if hasattr(self, 'localai_browser_use_cb'):
            self.localai_browser_use_cb.setText(t('desktop.localAI.browserUseLabel'))
            # v11.3.1: 常時有効。未インストール時は httpx フォールバックモードをツールチップで案内
            try:
                import browser_use  # noqa: F401
                self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseTip'))
            except ImportError:
                self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseHttpxMode'))

        # v10.1.0: GitHub
        if hasattr(self, 'github_group'):
            self.github_group.setTitle(t('desktop.localAI.githubSection'))
            self.github_pat_label.setText(t('desktop.localAI.githubPatLabel'))
            self.github_test_btn.setText(t('desktop.localAI.githubTestBtn'))
            self.github_save_btn.setText(t('common.save'))

        # v11.0.0: MCP Settings
        if hasattr(self, 'localai_mcp_group'):
            self.localai_mcp_group.setTitle(t('desktop.localAI.mcpSettings'))
            self.localai_mcp_filesystem.setText(t('desktop.settings.mcpFilesystem'))
            self.localai_mcp_filesystem.setToolTip(t('desktop.settings.mcpFilesystemTip'))
            self.localai_mcp_git.setText(t('desktop.settings.mcpGit'))
            self.localai_mcp_git.setToolTip(t('desktop.settings.mcpGitTip'))
            self.localai_mcp_brave.setText(t('desktop.settings.mcpBrave'))
            self.localai_mcp_brave.setToolTip(t('desktop.settings.mcpBraveTip'))

        # セクション保存ボタンのテキスト更新
        retranslate_section_save_buttons(self)
