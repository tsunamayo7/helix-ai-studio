"""
Helix AI Studio - localAI Tab (v10.1.0)
ローカルLLM (Ollama) との直接チャット。

サブタブ構成:
  - チャット: Ollama API経由のストリーミングチャット
  - 設定: Ollama管理、カスタムサーバー設定、常駐モデル設定
"""

import json
import logging
import shutil
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QComboBox,
    QFrame, QTabWidget, QLineEdit, QGroupBox,
    QScrollArea, QFormLayout, QMessageBox, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from ..utils.i18n import t
from ..utils.constants import APP_VERSION
from ..utils.styles import (
    SCROLLBAR_STYLE, PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    USER_MESSAGE_STYLE, AI_MESSAGE_STYLE, SECTION_CARD_STYLE,
)
from ..utils.markdown_renderer import markdown_to_html
from ..widgets.no_scroll_widgets import NoScrollComboBox

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"




class OllamaWorkerThread(QThread):
    """Ollama APIでストリーミングチャットを実行するワーカー（v10.1.0: ツール対応）"""
    chunkReceived = pyqtSignal(str)
    completed = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    toolExecuted = pyqtSignal(str, bool)  # v10.1.0: (tool_name, success)

    MAX_TOOL_LOOPS = 15  # v10.1.0: ツールループ上限

    def __init__(self, host: str, model: str, messages: list,
                 tools: list = None, project_dir: str = None,
                 timeout: int = 300, parent=None):
        super().__init__(parent)
        self._host = host
        self._model = model
        self._messages = list(messages)
        self._tools = tools
        self._project_dir = project_dir or "."
        self._timeout = timeout
        self._full_response = ""

    def run(self):
        import httpx
        try:
            for _loop in range(self.MAX_TOOL_LOOPS):
                payload = {
                    "model": self._model,
                    "messages": self._messages,
                    "stream": False,
                }
                if self._tools:
                    payload["tools"] = self._tools

                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        f"{self._host}/api/chat",
                        json=payload,
                        timeout=self._timeout,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                msg = data.get("message", {})
                tool_calls = msg.get("tool_calls")

                if tool_calls and self._tools:
                    # ツール呼び出しを処理
                    self._messages.append(msg)
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        tool_name = fn.get("name", "")
                        tool_args = fn.get("arguments", {})
                        try:
                            result = self._execute_tool(tool_name, tool_args)
                            self.toolExecuted.emit(tool_name, True)
                        except Exception as e:
                            result = {"error": str(e)}
                            self.toolExecuted.emit(tool_name, False)
                        self._messages.append({
                            "role": "tool",
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                    continue  # 次のループでLLMに再問い合わせ
                else:
                    # 通常テキスト応答
                    content = msg.get("content", "")
                    self._full_response = content
                    self.chunkReceived.emit(content)
                    break

            self.completed.emit(self._full_response)

        except Exception as e:
            logger.error(f"[OllamaWorkerThread] Error: {e}", exc_info=True)
            self.errorOccurred.emit(str(e))

    def _execute_tool(self, name: str, args: dict) -> dict:
        """v10.1.0: LocalAgentRunner と同じツール群を実行"""
        from ..backends.local_agent import LocalAgentRunner
        runner = LocalAgentRunner.__new__(LocalAgentRunner)
        from pathlib import Path
        runner.project_dir = Path(self._project_dir)
        runner.require_write_confirmation = False
        runner.on_write_confirm = None
        if name == "read_file":
            return runner._tool_read_file(args.get("path", ""))
        elif name == "list_dir":
            return runner._tool_list_dir(args.get("path", ""))
        elif name == "search_files":
            return runner._tool_search_files(args.get("query", ""), args.get("search_content", False))
        elif name == "write_file":
            return runner._tool_write_file(args.get("path", ""), args.get("content", ""))
        elif name == "create_file":
            return runner._tool_create_file(args.get("path", ""), args.get("content", ""))
        elif name == "web_search":
            return runner._tool_web_search(args.get("query", ""), args.get("max_results", 5))
        elif name == "fetch_url":
            return runner._tool_fetch_url(args.get("url", ""), args.get("max_chars", 3000))
        else:
            return {"error": f"Unknown tool: {name}"}


class LocalAITab(QWidget):
    """localAI - ローカルLLMチャットタブ (v10.1.0)"""

    statusChanged = pyqtSignal(str)

    def __init__(self, workflow_state=None, main_window=None, parent=None):
        super().__init__(parent)
        self.workflow_state = workflow_state
        self.main_window = main_window

        self._ollama_host = OLLAMA_HOST
        self._messages = []  # チャット履歴
        self._worker = None
        self._streaming_div_open = False

        self._setup_ui()
        # v11.0.0: capability取得完了シグナル接続
        self._caps_ready.connect(self._apply_capabilities)
        # 初回モデル一覧取得
        QTimer.singleShot(500, self._refresh_models)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # サブタブ
        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._create_chat_tab(), t('desktop.localAI.chatSubTab'))
        self.sub_tabs.addTab(self._create_settings_tab(), t('desktop.localAI.settingsSubTab'))
        layout.addWidget(self.sub_tabs)

    # =========================================================================
    # チャットサブタブ
    # =========================================================================

    def _create_chat_tab(self) -> QWidget:
        """v11.0.0: cloudAI風レイアウトに統一"""
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # ヘッダー行: [タイトル] [モデル:] [▼combo] [更新]
        header = QHBoxLayout()

        self.local_title = QLabel(t('desktop.localAI.title'))
        self.local_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.addWidget(self.local_title)

        self.model_label = QLabel(t('desktop.localAI.modelLabel'))
        self.model_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.model_label)

        self.model_combo = NoScrollComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.setToolTip(t('desktop.localAI.modelTip'))
        header.addWidget(self.model_combo)

        self.refresh_btn = QPushButton(t('desktop.localAI.refreshModelsBtn'))
        self.refresh_btn.setToolTip(t('desktop.localAI.refreshModelsTip'))
        self.refresh_btn.clicked.connect(self._refresh_models)
        header.addWidget(self.refresh_btn)

        # 後方互換用
        self.new_session_btn = QPushButton()
        self.new_session_btn.setVisible(False)

        header.addStretch()
        chat_layout.addLayout(header)

        # ExecutionMonitorWidget
        from ..widgets.execution_monitor_widget import ExecutionMonitorWidget
        self.monitor_widget = ExecutionMonitorWidget()
        chat_layout.addWidget(self.monitor_widget)

        # === 上部: チャット表示エリア（メイン領域） ===
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Yu Gothic UI", 10))
        self.chat_display.setPlaceholderText(t('desktop.localAI.chatReady'))
        self.chat_display.setStyleSheet(
            "QTextEdit { background-color: #0a0a1a; border: none; "
            "padding: 10px; color: #e0e0e0; }" + SCROLLBAR_STYLE
        )
        chat_layout.addWidget(self.chat_display, stretch=1)

        # === 下部: 入力欄(左) + 会話継続(右) ===
        bottom_layout = QHBoxLayout()

        # --- 左側: 入力欄 + ボタン行 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 4, 8, 4)
        left_layout.setSpacing(4)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText(t('desktop.localAI.inputPlaceholder'))
        self.input_field.setMaximumHeight(100)
        self.input_field.setStyleSheet(
            "QTextEdit { background: #0d0d1f; color: #e0e0e0; border: 1px solid #333; "
            "border-radius: 4px; padding: 8px; }" + SCROLLBAR_STYLE
        )
        left_layout.addWidget(self.input_field)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        # v11.0.0: 添付ボタン追加
        self.local_attach_btn = QPushButton(t('desktop.localAI.attachBtn'))
        self.local_attach_btn.setFixedHeight(32)
        self.local_attach_btn.setStyleSheet(SECONDARY_BTN)
        self.local_attach_btn.setToolTip(t('desktop.localAI.attachTip'))
        self.local_attach_btn.clicked.connect(self._on_attach_file)
        btn_row.addWidget(self.local_attach_btn)

        # v11.0.0: スニペットボタン追加
        self.local_snippet_btn = QPushButton(t('desktop.localAI.snippetBtn'))
        self.local_snippet_btn.setFixedHeight(32)
        self.local_snippet_btn.setStyleSheet(SECONDARY_BTN)
        self.local_snippet_btn.setToolTip(t('desktop.localAI.snippetTip'))
        self.local_snippet_btn.clicked.connect(self._on_snippet_menu)
        btn_row.addWidget(self.local_snippet_btn)

        # BIBLE toggle button (高さ統一)
        self.bible_btn = QPushButton("📖 BIBLE")
        self.bible_btn.setCheckable(True)
        self.bible_btn.setChecked(False)
        self.bible_btn.setFixedHeight(32)
        self.bible_btn.setToolTip(t('desktop.common.bibleToggleTooltip'))
        self.bible_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #ffa500;
                border: 1px solid #ffa500; border-radius: 4px;
                padding: 4px 12px; font-size: 11px; }
            QPushButton:checked { background: rgba(255, 165, 0, 0.2);
                border: 2px solid #ffa500; font-weight: bold; }
            QPushButton:hover { background: rgba(255, 165, 0, 0.1); }
        """)
        btn_row.addWidget(self.bible_btn)

        btn_row.addStretch()

        self.send_btn = QPushButton(t('desktop.localAI.sendBtn'))
        self.send_btn.setFixedHeight(32)
        self.send_btn.setStyleSheet(PRIMARY_BTN)
        self.send_btn.setToolTip(t('desktop.localAI.sendTip'))
        self.send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(self.send_btn)

        left_layout.addLayout(btn_row)
        bottom_layout.addWidget(left_widget, stretch=2)

        # --- 右側: 会話継続パネル ---
        continue_frame = self._create_continue_panel()
        bottom_layout.addWidget(continue_frame, stretch=1)

        chat_layout.addLayout(bottom_layout)

        return chat_widget

    def _create_continue_panel(self) -> QFrame:
        """v11.0.0: 会話継続パネル (cloudAIと統一スタイル)"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border: 1px solid #2a2a3e;
                border-radius: 6px; padding: 4px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.continue_header = QLabel(t('desktop.localAI.continueHeader'))
        self.continue_header.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 11px; border: none;")
        layout.addWidget(self.continue_header)

        self.continue_sub = QLabel(t('desktop.localAI.continueSub'))
        self.continue_sub.setStyleSheet("color: #888; font-size: 10px; border: none;")
        self.continue_sub.setWordWrap(True)
        layout.addWidget(self.continue_sub)

        # テキスト入力
        self.continue_input = QLineEdit()
        self.continue_input.setPlaceholderText(t('desktop.localAI.continuePlaceholder'))
        self.continue_input.setStyleSheet("""
            QLineEdit { background: #252526; color: #dcdcdc; border: 1px solid #3c3c3c;
                        border-radius: 4px; padding: 4px 8px; font-size: 11px; }
            QLineEdit:focus { border-color: #007acc; }
        """)
        self.continue_input.returnPressed.connect(self._on_continue_send)
        layout.addWidget(self.continue_input)

        # クイックボタン行 (cloudAIと同一スタイル)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)

        styles = [
            ("continueYes", "Yes", "#2d8b4e", "#3d9d56"),
            ("continueContinue", "Continue", "#0066aa", "#1177bb"),
            ("continueExecute", "Execute", "#6c5ce7", "#7d6ef8"),
        ]
        for label_key, msg, bg, bg_hover in styles:
            btn = QPushButton(t(f'desktop.localAI.{label_key}'))
            btn.setMaximumHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {bg}; color: white; border: none;
                    border-radius: 4px; padding: 3px 10px; font-size: 10px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {bg_hover}; }}
            """)
            btn.clicked.connect(lambda checked, m=msg: self._send_message(m))
            quick_row.addWidget(btn)
            setattr(self, f'quick_{label_key}_btn', btn)
        layout.addLayout(quick_row)

        # 送信ボタン (cloudAIと同一スタイル)
        self.continue_send_btn = QPushButton(t('desktop.localAI.continueSend'))
        self.continue_send_btn.setMaximumHeight(28)
        self.continue_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_send_btn.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; border: none;
                          border-radius: 4px; padding: 4px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #1088e4; }
        """)
        self.continue_send_btn.clicked.connect(self._on_continue_send)
        layout.addWidget(self.continue_send_btn)

        return frame

    # =========================================================================
    # 設定サブタブ
    # =========================================================================

    def _create_settings_tab(self) -> QWidget:
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLLBAR_STYLE)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # === Ollama管理セクション ===
        self.ollama_group = QGroupBox(t('desktop.localAI.ollamaSection'))
        ollama_group = self.ollama_group
        ollama_layout = QVBoxLayout()

        # インストール状態
        ollama_installed = shutil.which("ollama") is not None
        self.ollama_status_label = QLabel(
            t('desktop.localAI.ollamaInstallStatus') if ollama_installed
            else t('desktop.localAI.ollamaNotInstalled')
        )
        self.ollama_status_label.setStyleSheet(
            "color: #00ff88; font-weight: bold;" if ollama_installed
            else "color: #ef4444; font-weight: bold;"
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
        self.rm_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #ef4444;
                border: 1px solid #ef4444; border-radius: 4px;
                padding: 6px 14px; font-weight: bold; }
            QPushButton:hover { background: rgba(239, 68, 68, 0.15); }
        """)
        self.rm_btn.clicked.connect(self._on_remove_model)
        model_mgmt_row.addWidget(self.rm_btn)

        model_mgmt_row.addStretch()
        ollama_layout.addLayout(model_mgmt_row)

        # v10.1.0: Brave Search API キー設定
        brave_row = QHBoxLayout()
        self.brave_api_label = QLabel(t('desktop.localAI.braveApiKeyLabel'))
        brave_row.addWidget(self.brave_api_label)
        self.brave_api_input = QLineEdit()
        self.brave_api_input.setPlaceholderText(t('desktop.localAI.braveApiKeyPlaceholder'))
        self.brave_api_input.setEchoMode(QLineEdit.EchoMode.Password)
        brave_row.addWidget(self.brave_api_input, 1)
        self.brave_api_page_btn = QPushButton(t('desktop.localAI.braveApiPageBtn'))
        self.brave_api_page_btn.setStyleSheet(SECONDARY_BTN)
        self.brave_api_page_btn.clicked.connect(self._open_brave_api_page)
        brave_row.addWidget(self.brave_api_page_btn)
        self.brave_api_save_btn = QPushButton(t('common.save'))
        self.brave_api_save_btn.setStyleSheet(PRIMARY_BTN)
        self.brave_api_save_btn.clicked.connect(self._save_brave_api_key)
        brave_row.addWidget(self.brave_api_save_btn)
        ollama_layout.addLayout(brave_row)
        # 保存済みキーを復元
        self._load_brave_api_key()

        ollama_group.setLayout(ollama_layout)
        scroll_layout.addWidget(ollama_group)

        # v11.0.0: カスタムサーバーセクション削除（openai_compat_backend削除済み）

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
        from ..widgets.section_save_button import create_section_save_button
        mcp_layout.addWidget(create_section_save_button(self._save_localai_mcp_settings))
        self.localai_mcp_group.setLayout(mcp_layout)
        scroll_layout.addWidget(self.localai_mcp_group)
        self._load_localai_mcp_settings()

        # === v11.1.0: Browser Use Settings for localAI ===
        self.localai_browser_use_group = QGroupBox(t('desktop.localAI.browserUseGroup'))
        self.localai_browser_use_group.setStyleSheet(SECTION_CARD_STYLE)
        browser_use_layout = QVBoxLayout()
        self.localai_browser_use_cb = QCheckBox(t('desktop.localAI.browserUseLabel'))
        try:
            import browser_use  # noqa: F401
            self.localai_browser_use_cb.setEnabled(True)
            self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseTip'))
        except ImportError:
            self.localai_browser_use_cb.setEnabled(False)
            self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseNotInstalled'))
        browser_use_layout.addWidget(self.localai_browser_use_cb)
        browser_use_layout.addWidget(create_section_save_button(self._save_localai_browser_use_setting))
        self.localai_browser_use_group.setLayout(browser_use_layout)
        scroll_layout.addWidget(self.localai_browser_use_group)
        self._load_localai_browser_use_setting()

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        settings_layout.addWidget(scroll)

        return settings_widget

    # =========================================================================
    # チャットロジック
    # =========================================================================

    def _on_send(self):
        """送信ボタン"""
        message = self.input_field.toPlainText().strip()
        if not message:
            return
        self.input_field.clear()
        self._send_message(message)

    def _on_continue_send(self):
        """継続パネルから送信"""
        message = self.continue_input.text().strip()
        if message:
            self.continue_input.clear()
            self._send_message(message)

    def _on_attach_file(self):
        """v11.0.0: ファイル添付（入力欄にパスを追加）"""
        from PyQt6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(self, t('common.attach'), "", "All Files (*)")
        if files:
            current = self.input_field.toPlainText()
            paths = "\n".join([f"[File: {f}]" for f in files])
            self.input_field.setPlainText(f"{current}\n{paths}" if current else paths)

    def _on_snippet_menu(self):
        """v11.0.0: スニペットメニュー表示"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        try:
            # cloudAI/mixAIと同じスニペットマネージャーを使用
            import os, json
            snippet_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', 'snippets')
            os.makedirs(snippet_dir, exist_ok=True)
            menu = QMenu(self)
            snippet_files = [f for f in os.listdir(snippet_dir) if f.endswith('.json')] if os.path.exists(snippet_dir) else []
            if not snippet_files:
                no_action = menu.addAction(t('desktop.localAI.noSnippets'))
                no_action.setEnabled(False)
            else:
                for sf in snippet_files:
                    try:
                        with open(os.path.join(snippet_dir, sf), 'r', encoding='utf-8') as f:
                            snippet = json.load(f)
                        name = snippet.get('name', sf)
                        action = menu.addAction(f"📋 {name}")
                        action.triggered.connect(lambda checked, s=snippet: self.input_field.setPlainText(
                            self.input_field.toPlainText() + "\n" + s.get('content', '') if self.input_field.toPlainText() else s.get('content', '')))
                    except Exception:
                        pass
            btn_pos = self.local_snippet_btn.mapToGlobal(QPoint(0, self.local_snippet_btn.height()))
            menu.exec(btn_pos)
        except Exception as e:
            logger.error(f"[LocalAI._on_snippet_menu] Error: {e}")

    def _send_message(self, message: str):
        """メッセージを送信してOllamaで応答を取得"""
        if self._worker and self._worker.isRunning():
            return

        model = self.model_combo.currentText()
        if not model:
            QMessageBox.warning(self, "Error", t('desktop.localAI.noModels'))
            return

        # ユーザーメッセージ表示
        self.chat_display.append(
            f"<div style='{USER_MESSAGE_STYLE}'>"
            f"<b style='color:#00d4ff;'>You:</b> {message}"
            f"</div>"
        )

        # v11.0.0: Historyタブへのuser記録
        try:
            from ..utils.chat_logger import get_chat_logger
            get_chat_logger().log_message(tab="localAI", model=model, role="user", content=message[:2000])
        except Exception:
            pass

        # v11.0.0: BIBLE context injection (Phase 4)
        if hasattr(self, 'bible_btn') and self.bible_btn.isChecked():
            from ..mixins.bible_context_mixin import BibleContextMixin
            mixin = BibleContextMixin()
            message = mixin._inject_bible_to_prompt(message)

        # 履歴に追加
        self._messages.append({"role": "user", "content": message})

        # UI更新
        self.send_btn.setEnabled(False)
        self.statusChanged.emit(t('desktop.localAI.generating'))

        # モニター開始
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.start_model(model, "Chat")

        # ストリーミングバブル開始
        self.chat_display.append(
            f"<div style='{AI_MESSAGE_STYLE}'>"
            f"<b style='color:#00ff88;'>{model}:</b> "
        )
        self._streaming_div_open = True

        # v10.1.0: ツール定義を取得
        from ..backends.local_agent import AGENT_TOOLS
        project_dir = "."
        try:
            from pathlib import Path as _P
            cfg_path = _P("config/config.json")
            if cfg_path.exists():
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                project_dir = cfg.get("project_dir", ".")
        except Exception:
            pass

        # v11.0.1: モデルのcapabilityを確認してtoolsを条件付きで渡す
        caps_data = getattr(self, '_pending_caps', {})
        model_supports_tools = caps_data.get(model, {}).get("tools", False)
        tools_to_use = AGENT_TOOLS if model_supports_tools else None

        # ワーカー開始
        self._worker = OllamaWorkerThread(
            host=self._ollama_host,
            model=model,
            messages=list(self._messages),
            tools=tools_to_use,
            project_dir=project_dir,
        )
        self._worker.chunkReceived.connect(self._on_chunk)
        self._worker.completed.connect(self._on_completed)
        self._worker.errorOccurred.connect(self._on_error)
        self._worker.toolExecuted.connect(self._on_tool_executed)
        self._worker.start()

    def _on_chunk(self, chunk: str):
        """ストリーミングチャンク"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _on_completed(self, full_response: str):
        """応答完了"""
        # ストリーミングdivを閉じる
        if self._streaming_div_open:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml("</div>")
            self._streaming_div_open = False

        self._messages.append({"role": "assistant", "content": full_response})
        self.send_btn.setEnabled(True)
        self.statusChanged.emit(t('desktop.localAI.completed'))

        # v11.0.0: Historyタブへの自動記録
        model = self.model_combo.currentText()
        try:
            from ..utils.chat_logger import get_chat_logger
            chat_logger = get_chat_logger()
            chat_logger.log_message(tab="localAI", model=model, role="assistant", content=full_response[:2000])
        except Exception:
            pass

        # モニター完了
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.finish_model(model, success=True)

    def _on_error(self, error: str):
        """エラー"""
        if self._streaming_div_open:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml("</div>")
            self._streaming_div_open = False

        self.chat_display.append(
            f"<div style='background:#2a1515; border-left:3px solid #ef4444; "
            f"padding:8px; margin:4px; border-radius:4px;'>"
            f"<b style='color:#ef4444;'>Error:</b> {error}"
            f"</div>"
        )
        self.send_btn.setEnabled(True)
        self.statusChanged.emit(t('desktop.localAI.error', error=error[:50]))

        model = self.model_combo.currentText()
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.finish_model(model, success=False)

    def _on_tool_executed(self, tool_name: str, success: bool):
        """v10.1.0: ツール実行通知"""
        icon = "✅" if success else "❌"
        self.statusChanged.emit(f"🔧 {tool_name} {icon}")
        self.chat_display.append(
            f"<div style='background:#1a2332; border-left:3px solid #3b82f6; "
            f"padding:4px 8px; margin:2px; border-radius:4px; font-size:11px; color:#94a3b8;'>"
            f"🔧 Tool: <b>{tool_name}</b> {icon}"
            f"</div>"
        )

    def _on_new_session(self):
        """新規セッション"""
        self._messages.clear()
        self.chat_display.clear()
        self.chat_display.setPlaceholderText(t('desktop.localAI.chatReady'))
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.reset()
        self.statusChanged.emit(t('desktop.localAI.newSessionStarted'))

    # =========================================================================
    # モデル管理
    # =========================================================================

    def _refresh_models(self):
        """Ollamaインストール済みモデルを取得（v11.0.0: 高速表示+遅延capability取得）"""
        try:
            import httpx
            resp = httpx.get(f"{self._ollama_host}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])

            self.model_combo.clear()
            self.models_table.setRowCount(0)

            for m in models:
                name = m.get("name", "")
                self.model_combo.addItem(name)
                row = self.models_table.rowCount()
                self.models_table.insertRow(row)
                self.models_table.setItem(row, 0, QTableWidgetItem(name))
                size_gb = m.get("size", 0) / (1024 ** 3)
                self.models_table.setItem(row, 1, QTableWidgetItem(f"{size_gb:.1f} GB"))
                self.models_table.setItem(row, 2, QTableWidgetItem(
                    m.get("modified_at", "")[:19]))
                # capability列は初期値（後で非同期更新）
                for col in range(3, 7):
                    item = QTableWidgetItem("—")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.models_table.setItem(row, col, item)

            if not models:
                self.model_combo.addItem(t('desktop.localAI.noModels'))

            # capability情報を遅延で非同期取得
            if models:
                import threading
                model_names = [m.get("name", "") for m in models]
                threading.Thread(target=self._fetch_capabilities_bg, args=(model_names,), daemon=True).start()

        except Exception as e:
            logger.warning(f"[LocalAITab] Failed to fetch models: {e}")
            self.model_combo.clear()
            self.model_combo.addItem(t('desktop.localAI.noModels'))

    def _fetch_capabilities_bg(self, model_names: list):
        """バックグラウンドでcapability情報を取得し、完了後UIに反映"""
        results = {}
        for name in model_names:
            results[name] = self._get_model_capabilities(name)
        self._pending_caps = results
        # UIスレッドで更新（QTimerはメインスレッドからしか使えないのでsignal使用）
        self._caps_ready.emit()

    # capability取得完了シグナル
    _caps_ready = pyqtSignal()

    def _apply_capabilities(self):
        """UIスレッドでcapability列を更新"""
        caps_data = getattr(self, '_pending_caps', {})
        for row in range(self.models_table.rowCount()):
            name_item = self.models_table.item(row, 0)
            if name_item:
                name = name_item.text()
                caps = caps_data.get(name, {})
                for col, key in enumerate(["tools", "embed", "vision", "think"], 3):
                    item = QTableWidgetItem("✅" if caps.get(key) else "❌")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.models_table.setItem(row, col, item)

    def _test_ollama_connection(self):
        """Ollama接続テスト"""
        host = self.ollama_host_input.text().strip() or OLLAMA_HOST
        self._ollama_host = host
        try:
            import httpx
            resp = httpx.get(f"{host}/api/tags", timeout=5)
            resp.raise_for_status()
            QMessageBox.information(self, "OK", t('desktop.localAI.ollamaTestSuccess'))
            self._refresh_models()
        except Exception as e:
            QMessageBox.warning(self, "Error",
                                t('desktop.localAI.ollamaTestFailed', error=str(e)))

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
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.localAI.addModelTitle'))
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(t('desktop.localAI.addModelOllamaName')))
        name_input = QLineEdit()
        name_input.setPlaceholderText("例: llama3.2:3b")
        layout.addWidget(name_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
            QMessageBox.information(self, "OK", f"Model '{model_name}' pulled successfully.")
            self._refresh_models()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to pull model: {e}")
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
            self, "Confirm",
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
            QMessageBox.warning(self, "Error", f"Failed to remove model: {e}")

    def _open_ollama_install(self):
        """Ollamaインストールページを開く"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://ollama.com/download"))

    # =========================================================================
    # v11.0.0: カスタムサーバー管理メソッド削除（openai_compat_backend削除済み）

    # =========================================================================
    # i18n
    # =========================================================================

    def retranslateUi(self):
        """言語変更時にUIテキストを再適用"""
        self.sub_tabs.setTabText(0, t('desktop.localAI.chatSubTab'))
        self.sub_tabs.setTabText(1, t('desktop.localAI.settingsSubTab'))
        self.local_title.setText(t('desktop.localAI.title'))
        self.new_session_btn.setText(t('desktop.localAI.newSessionBtn'))
        self.new_session_btn.setToolTip(t('desktop.localAI.newSessionBtnTip'))
        self.model_label.setText(t('desktop.localAI.modelLabel'))
        self.model_combo.setToolTip(t('desktop.localAI.modelTip'))
        self.refresh_btn.setText(t('desktop.localAI.refreshModelsBtn'))
        self.refresh_btn.setToolTip(t('desktop.localAI.refreshModelsTip'))
        self.input_field.setPlaceholderText(t('desktop.localAI.inputPlaceholder'))
        self.send_btn.setText(t('desktop.localAI.sendBtn'))
        self.send_btn.setToolTip(t('desktop.localAI.sendTip'))
        # v11.0.0: BIBLE toggle button
        if hasattr(self, 'bible_btn'):
            self.bible_btn.setToolTip(t('desktop.common.bibleToggleTooltip'))
        # チャットタブ: 添付・スニペットボタン
        if hasattr(self, 'local_attach_btn'):
            self.local_attach_btn.setText(t('desktop.localAI.attachBtn'))
            self.local_attach_btn.setToolTip(t('desktop.localAI.attachTip'))
        if hasattr(self, 'local_snippet_btn'):
            self.local_snippet_btn.setText(t('desktop.localAI.snippetBtn'))
            self.local_snippet_btn.setToolTip(t('desktop.localAI.snippetTip'))
        # 設定タブ: Ollama管理セクション
        if hasattr(self, 'ollama_group'):
            self.ollama_group.setTitle(t('desktop.localAI.ollamaSection'))
        if hasattr(self, 'ollama_status_label'):
            import shutil
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
            try:
                import browser_use  # noqa: F401
                self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseTip'))
            except ImportError:
                self.localai_browser_use_cb.setToolTip(t('desktop.localAI.browserUseNotInstalled'))
        # Continue panel
        if hasattr(self, 'continue_header'):
            self.continue_header.setText(t('desktop.localAI.continueHeader'))
            self.continue_sub.setText(t('desktop.localAI.continueSub'))
            self.continue_send_btn.setText(t('desktop.localAI.continueSend'))
            self.continue_input.setPlaceholderText(t('desktop.localAI.continuePlaceholder'))
        # Monitor
        if hasattr(self, 'monitor_widget') and hasattr(self.monitor_widget, 'retranslateUi'):
            self.monitor_widget.retranslateUi()
        # v10.1.0: Brave Search API
        if hasattr(self, 'brave_api_label'):
            self.brave_api_label.setText(t('desktop.localAI.braveApiKeyLabel'))
            self.brave_api_input.setPlaceholderText(t('desktop.localAI.braveApiKeyPlaceholder'))
            self.brave_api_page_btn.setText(t('desktop.localAI.braveApiPageBtn'))
            self.brave_api_save_btn.setText(t('common.save'))
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

    def _open_brave_api_page(self):
        """v10.1.0: Brave Search API 取得ページを開く"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://brave.com/search/api/"))

    def _save_brave_api_key(self):
        """v10.1.0: Brave Search API キーを general_settings.json に保存"""
        from pathlib import Path
        key = self.brave_api_input.text().strip()
        settings_path = Path("config/general_settings.json")
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["brave_search_api_key"] = key
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.brave_api_save_btn.setText("✅")
            QTimer.singleShot(1500, lambda: self.brave_api_save_btn.setText(t('common.save')))
        except Exception as e:
            logger.warning(f"Brave API key save failed: {e}")

    def _load_brave_api_key(self):
        """v10.1.0: 保存済み Brave Search API キーを復元"""
        from pathlib import Path
        settings_path = Path("config/general_settings.json")
        try:
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                key = data.get("brave_search_api_key", "")
                if key:
                    self.brave_api_input.setText(key)
        except Exception:
            pass

    def _test_github_connection(self):
        """v10.1.0: GitHub API 接続テスト"""
        pat = self.github_pat_input.text().strip()
        if not pat:
            QMessageBox.warning(self, "Error", "Please enter a GitHub Personal Access Token.")
            return
        try:
            import httpx
            resp = httpx.get("https://api.github.com/user",
                             headers={"Authorization": f"Bearer {pat}"},
                             timeout=10)
            if resp.status_code == 200:
                user = resp.json().get("login", "")
                QMessageBox.information(self, "OK", f"GitHub connected: {user}")
            else:
                QMessageBox.warning(self, "Error", f"GitHub API error: HTTP {resp.status_code}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"GitHub connection failed: {e}")

    def _save_github_pat(self):
        """v10.1.0: GitHub PAT を general_settings.json に保存"""
        from pathlib import Path
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
            self.github_save_btn.setText("✅")
            QTimer.singleShot(1500, lambda: self.github_save_btn.setText(t('common.save')))
        except Exception as e:
            logger.warning(f"GitHub PAT save failed: {e}")

    def _load_github_pat(self):
        """v10.1.0: 保存済み GitHub PAT を復元"""
        from pathlib import Path
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
        from pathlib import Path
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
            logger.info("[LocalAITab] Saved MCP settings")
        except Exception as e:
            logger.error(f"Failed to save MCP settings: {e}")

    def _load_localai_mcp_settings(self):
        """v11.0.0: Load localAI MCP settings from config.json"""
        from pathlib import Path
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
            logger.debug(f"[LocalAITab] MCP settings load: {e}")

    # =========================================================================
    # v11.1.0: Browser Use Settings
    # =========================================================================

    def _save_localai_browser_use_setting(self):
        """v11.1.0: Save Browser Use setting for localAI to config.json"""
        from pathlib import Path
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
            logger.info("[LocalAITab] Saved Browser Use setting")
        except Exception as e:
            logger.error(f"Failed to save Browser Use setting: {e}")

    def _load_localai_browser_use_setting(self):
        """v11.1.0: Load Browser Use setting for localAI from config.json"""
        from pathlib import Path
        config_path = Path("config/config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                enabled = config.get("localai_browser_use_enabled", False)
                self.localai_browser_use_cb.setChecked(enabled)
        except Exception as e:
            logger.debug(f"[LocalAITab] Browser Use setting load: {e}")

