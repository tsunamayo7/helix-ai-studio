"""
Claude Tab - AIチャット＆設定統合タブ
Reference: Claude Code GUI v7.6.2

v3.9.0: Claude Codeタブを「Claude」に改名、チャット/設定のサブタブを追加
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel,
    QComboBox, QCheckBox, QFrame, QSizePolicy,
    QProgressBar, QMessageBox, QGroupBox, QScrollArea,
    QTabWidget, QLineEdit, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QFormLayout,
    QFileDialog  # v5.1: ファイル添付用
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QAction
from ..utils.i18n import t

logger = logging.getLogger(__name__)


# v8.3.1: RAPTOR要約をUIスレッド外で実行するワーカー
class RaptorWorker(QThread):
    """RAPTORセッション要約+週次要約+中間要約をバックグラウンド実行"""
    def __init__(self, memory_manager, session_id: str, messages: list,
                 mode: str = "session"):
        """
        Args:
            mode: "session" = セッション完了時（session要約+週次要約）
                  "mid_session" = セッション中間要約（v8.4.0）
        """
        super().__init__()
        self._mm = memory_manager
        self._session_id = session_id
        self._messages = messages
        self._mode = mode

    def run(self):
        try:
            if self._mode == "mid_session":
                self._mm.raptor_mid_session_summary(
                    self._session_id, self._messages)
            else:
                self._mm.raptor_summarize_session(self._session_id, self._messages)
                self._mm.raptor_try_weekly()
        except Exception as e:
            logger.warning(f"RAPTOR background task failed ({self._mode}): {e}")


# Phase 2.0: Backend統合
from ..backends import ClaudeBackend, BackendRequest, BackendResponse, get_backend_registry

# v2.5.0: Claude CLI Backend (Max/Proプラン対応)
from ..backends import ClaudeCLIBackend, check_claude_cli_available, get_claude_cli_backend

# Phase 2.1: Task分類
from ..routing import TaskClassifier

# Phase 2.2: Router
from ..routing import BackendRouter

# Phase 2.3: Metrics
from ..metrics import get_usage_metrics_recorder

# Phase 2.4: Fallback
from ..routing.fallback import FallbackManager
from ..routing.execution import execute_with_fallback

# Phase 2.x: RoutingExecutor (CP1-CP10統合)
from ..routing import get_routing_executor

# v7.1.0: Claudeモデル動的選択
from ..utils.constants import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL_ID
from ..utils.markdown_renderer import markdown_to_html
from ..utils.styles import (
    SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    INPUT_AREA_STYLE, SCROLLBAR_STYLE, TAB_BAR_STYLE,
    USER_MESSAGE_STYLE, AI_MESSAGE_STYLE, SPINBOX_STYLE,
)
from ..widgets.chat_widgets import SoloAIStatusBar, ExecutionIndicator, InterruptionBanner


# --- Backend呼び出しスレッド (Phase 2.0) ---
class BackendThread(QThread):
    """Backend経由でAI応答を取得するスレッド"""
    responseReady = pyqtSignal(BackendResponse)

    def __init__(self, backend, request: BackendRequest, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.request = request

    def run(self):
        """Backend経由でメッセージを送信"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            response = self.backend.send(self.request)
            self.responseReady.emit(response)
        except Exception as e:
            # Backend呼び出しで例外が発生した場合
            logger.error(f"[BackendThread] Exception in backend.send: {e}", exc_info=True)

            # エラーレスポンスを生成してemit
            error_response = BackendResponse(
                success=False,
                response_text=t('desktop.soloAI.backendErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
                error_type=type(e).__name__,
                duration_ms=0,
                tokens_used=0,
                cost_est=0.0,
                metadata={"error": str(e)}
            )
            self.responseReady.emit(error_response)


# --- RoutingExecutor呼び出しスレッド (Phase 2.x) ---
class RoutingExecutorThread(QThread):
    """RoutingExecutor経由でAI応答を取得するスレッド（CP1-CP10統合）"""
    responseReady = pyqtSignal(BackendResponse, dict)

    def __init__(self, executor, request: BackendRequest,
                 user_forced_backend=None, approval_snapshot=None, parent=None):
        super().__init__(parent)
        self.executor = executor
        self.request = request
        self.user_forced_backend = user_forced_backend
        self.approval_snapshot = approval_snapshot

    def run(self):
        """RoutingExecutor経由でメッセージを送信"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            response, execution_info = self.executor.execute(
                self.request,
                user_forced_backend=self.user_forced_backend,
                approval_snapshot=self.approval_snapshot,
            )
            self.responseReady.emit(response, execution_info)
        except Exception as e:
            # Executor呼び出しで例外が発生した場合
            logger.error(f"[RoutingExecutorThread] Exception: {e}", exc_info=True)

            # エラーレスポンスを生成してemit
            error_response = BackendResponse(
                success=False,
                response_text=t('desktop.soloAI.routingErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
                error_type=type(e).__name__,
                duration_ms=0,
                tokens_used=0,
                cost_est=0.0,
                metadata={"error": str(e)}
            )
            self.responseReady.emit(error_response, {})


# --- v3.2.0: CLI Backend呼び出しスレッド ---
class CLIWorkerThread(QThread):
    """Claude CLI経由でAI応答を取得するスレッド (v3.2.0: Max/Proプラン対応)"""
    chunkReceived = pyqtSignal(str)
    completed = pyqtSignal(BackendResponse)
    errorOccurred = pyqtSignal(str)

    def __init__(self, backend, prompt: str, model: str = None,
                 working_dir: str = None, thinking_level: str = "none", parent=None):
        super().__init__(parent)
        self._backend = backend
        self._prompt = prompt
        self._model = model
        self._working_dir = working_dir
        self._thinking_level = thinking_level
        self._full_response = ""
        self._start_time = None

    def run(self):
        """CLI経由でプロンプトを実行"""
        import logging
        import time
        logger = logging.getLogger(__name__)

        self._start_time = time.time()

        try:
            # CLIバックエンドの思考レベルを設定
            if self._thinking_level:
                self._backend.thinking_level = self._thinking_level

            # 作業ディレクトリを設定
            if self._working_dir:
                self._backend.working_dir = self._working_dir

            # ストリーミングコールバックを設定
            def on_chunk(chunk: str):
                self._full_response += chunk
                self.chunkReceived.emit(chunk)

            self._backend.set_streaming_callback(on_chunk)

            # BackendRequestを作成
            request = BackendRequest(
                session_id="cli_session",
                phase="S4",
                user_text=self._prompt,
                toggles={},
                context={}
            )

            # CLI経由で送信
            response = self._backend.send(request)

            # 成功時
            self.completed.emit(response)
            logger.info(f"[CLIWorkerThread] Completed: duration={response.duration_ms:.2f}ms")

        except Exception as e:
            duration_ms = (time.time() - self._start_time) * 1000
            logger.error(f"[CLIWorkerThread] Error: {e}", exc_info=True)

            # エラーレスポンスを生成
            error_response = BackendResponse(
                success=False,
                response_text=t('desktop.soloAI.cliExecErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                tokens_used=0,
                cost_est=0.0,
                metadata={"backend": "claude-cli", "error": str(e)}
            )
            self.completed.emit(error_response)
            self.errorOccurred.emit(str(e))


# --- v3.9.2: Ollama直接呼び出しスレッド (v3.9.3: MCPツール統合) ---
class OllamaWorkerThread(QThread):
    """Ollama経由でAI応答を取得するスレッド (v3.9.3: MCPツール統合)"""
    completed = pyqtSignal(str, float)  # response_text, duration_ms
    errorOccurred = pyqtSignal(str)
    toolExecuted = pyqtSignal(str, bool)  # tool_name, success

    def __init__(self, url: str, model: str, prompt: str,
                 mcp_enabled: bool = False, mcp_settings: dict = None,
                 working_dir: str = ".", parent=None):
        super().__init__(parent)
        self._url = url
        self._model = model
        self._prompt = prompt
        self._mcp_enabled = mcp_enabled
        self._mcp_settings = mcp_settings or {}
        self._working_dir = working_dir

    def run(self):
        """Ollama経由でプロンプトを実行 (v3.9.3: MCPツール対応)"""
        import logging
        import time
        logger = logging.getLogger(__name__)

        start_time = time.time()

        try:
            import ollama

            # v3.9.3: MCPツール統合
            tool_prompt_addition = ""
            tool_executor = None

            if self._mcp_enabled:
                try:
                    from ..mcp.ollama_tools import get_ollama_tool_executor
                    tool_executor = get_ollama_tool_executor(
                        enabled_tools=self._mcp_settings,
                        working_dir=self._working_dir
                    )
                    tool_prompt_addition = tool_executor.get_tools_system_prompt()
                    logger.info(f"[OllamaWorkerThread] MCP tools enabled: {self._mcp_settings}")
                except ImportError as e:
                    logger.warning(f"[OllamaWorkerThread] MCP tools not available: {e}")

            # プロンプトにツール情報を追加
            full_prompt = self._prompt
            if tool_prompt_addition:
                full_prompt = tool_prompt_addition + "\n\n" + self._prompt

            client = ollama.Client(host=self._url)
            response = client.generate(
                model=self._model,
                prompt=full_prompt,
            )

            duration_ms = (time.time() - start_time) * 1000

            # レスポンスからテキストを取得
            if isinstance(response, dict):
                response_text = response.get('response', '')
            else:
                response_text = getattr(response, 'response', str(response))

            # v3.9.3: MCPツール呼び出しを処理
            if tool_executor and self._mcp_enabled:
                response_text, executed_tools = tool_executor.process_response_with_tools(response_text)
                for tool_info in executed_tools:
                    self.toolExecuted.emit(tool_info["tool"], tool_info["success"])
                    logger.info(f"[OllamaWorkerThread] Tool executed: {tool_info['tool']} - {'Success' if tool_info['success'] else 'Failed'}")

            logger.info(f"[OllamaWorkerThread] Completed: model={self._model}, duration={duration_ms:.2f}ms")
            self.completed.emit(response_text, duration_ms)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[OllamaWorkerThread] Error: {e}", exc_info=True)
            self.errorOccurred.emit(f"{type(e).__name__}: {str(e)}")


# =============================================================================
# v5.1: soloAI用添付ファイルウィジェット
# =============================================================================

class SoloAIAttachmentWidget(QFrame):
    """soloAI用個別添付ファイルウィジェット"""
    removed = pyqtSignal(str)  # ファイルパス

    FILE_ICONS = {
        ".py": "🐍", ".js": "📜", ".ts": "📘",
        ".html": "🌐", ".css": "🎨", ".json": "📋",
        ".md": "📝", ".txt": "📄", ".pdf": "📕",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️",
        ".gif": "🖼️", ".svg": "🖼️", ".webp": "🖼️",
        ".zip": "📦", ".csv": "📊", ".xlsx": "📊",
    }

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        import os
        self.filepath = filepath
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            SoloAIAttachmentWidget {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 2px 6px;
            }
            SoloAIAttachmentWidget:hover {
                border-color: #63b3ed;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        icon = self.FILE_ICONS.get(ext, "📎")

        icon_label = QLabel(icon)
        name_label = QLabel(filename)
        name_label.setStyleSheet("color: #e2e8f0; font-size: 10px;")
        name_label.setMaximumWidth(150)
        name_label.setToolTip(filepath)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(16, 16)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a0aec0;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { color: #fc8181; }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(remove_btn)


class SoloAIAttachmentBar(QWidget):
    """soloAI用添付ファイルバー"""
    attachments_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        import os
        from typing import List
        self._files: List[str] = []
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMaximumHeight(36)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.container = QWidget()
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def add_files(self, filepaths):
        """ファイルを追加"""
        import os
        for fp in filepaths:
            if fp not in self._files and os.path.exists(fp):
                self._files.append(fp)
                widget = SoloAIAttachmentWidget(fp)
                widget.removed.connect(self.remove_file)
                self.container_layout.insertWidget(
                    self.container_layout.count() - 1, widget)

        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def remove_file(self, filepath: str):
        """ファイルを削除"""
        if filepath in self._files:
            self._files.remove(filepath)
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, SoloAIAttachmentWidget) and w.filepath == filepath:
                    w.deleteLater()
                    break
        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def clear_all(self):
        """全ファイル削除"""
        self._files.clear()
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setVisible(False)
        self.attachments_changed.emit([])

    def get_files(self):
        """添付ファイルリストを取得"""
        return self._files.copy()


class ClaudeTab(QWidget):
    """
    Claude Code Tab

    Features:
    - Native MCP Client統合
    - Aider-style Diff View
    - Autonomous Context Loading
    - TDDパイプライン
    """

    # シグナル
    statusChanged = pyqtSignal(str)
    diffProposed = pyqtSignal(str, str, str)

    def __init__(self, workflow_state=None, main_window=None, parent=None):
        super().__init__(parent)

        # ワークフロー状態とメインウィンドウへの参照
        from ..data.session_manager import get_session_manager
        from ..data.workflow_state import WorkflowTransitionError
        from ..data.workflow_logger import get_workflow_logger
        from ..data.history_manager import get_history_manager
        from ..data.chat_history_manager import get_chat_history_manager
        from ..claude.prompt_preprocessor import get_prompt_preprocessor
        from ..security.approvals_store import get_approvals_store
        from ..security.risk_gate import RiskGate

        self.session_manager = get_session_manager()
        self.workflow_state = workflow_state or self.session_manager.load_workflow_state()
        self.workflow_logger = get_workflow_logger()
        self.history_manager = get_history_manager()
        self.chat_history_manager = get_chat_history_manager()
        self.prompt_preprocessor = get_prompt_preprocessor()

        # 現在送信中のユーザーメッセージを保持（履歴保存用）
        self._pending_user_message = None
        self.main_window = main_window

        # Phase 1.2: ApprovalsStoreとRiskGate
        self.approvals_store = get_approvals_store()
        self.approval_state = self.approvals_store.load_approval_state()
        self.risk_gate = RiskGate(self.approval_state)

        # Phase 2.0: Backend統合
        self.backend = None  # 後でモデル選択に応じて初期化
        self._init_backend()

        # Phase 2.1: Task分類器
        self.task_classifier = TaskClassifier()

        # Phase 2.2: Router
        self.backend_router = BackendRouter()

        # Phase 2.3: Metrics
        self.metrics_recorder = get_usage_metrics_recorder()

        # Phase 2.4: Fallback
        self.fallback_manager = FallbackManager()

        # Phase 2.x: RoutingExecutor (CP1-CP10統合)
        self.routing_executor = get_routing_executor()
        self.backend_registry = get_backend_registry()

        # v5.1: 添付ファイルリスト
        self._attached_files: list = []

        # v8.1.0: メモリマネージャー
        self._memory_manager = None
        try:
            from ..memory.memory_manager import HelixMemoryManager
            self._memory_manager = HelixMemoryManager()
            logger.info("HelixMemoryManager initialized for soloAI")
        except Exception as e:
            logger.warning(f"Memory manager init failed: {e}")

        # v8.4.0: Mid-Session Summary用メッセージカウンター
        self._session_message_count = 0
        self._session_messages_for_summary: list = []
        try:
            from ..utils.constants import MID_SESSION_TRIGGER_COUNT
            self._mid_session_trigger = MID_SESSION_TRIGGER_COUNT
        except ImportError:
            self._mid_session_trigger = 5

        self._init_ui()
        self._connect_signals()
        self._update_workflow_ui()

        # v9.5.0: Web実行ロックオーバーレイ
        from ..widgets.web_lock_overlay import WebLockOverlay
        self.web_lock_overlay = WebLockOverlay(self)

    def eventFilter(self, obj, event):
        """v3.9.4: QComboBoxのマウスホイールイベントを無効化"""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Wheel:
            # settings_ollama_modelのホイールイベントを無視
            if obj == getattr(self, 'settings_ollama_model', None):
                return True  # イベントを消費（無効化）
        return super().eventFilter(obj, event)

    def _init_backend(self):
        """Backend を初期化 (Phase 2.0, v2.5.0: CLI/API両対応, v3.2.0: CLI分離)"""
        # v3.2.0: CLIバックエンドを常に初期化（利用不可でも参照用）
        self._cli_backend = None

        # v2.5.0: デフォルトはCLI (Max/Proプラン)、利用不可の場合はAPI
        cli_available, _ = check_claude_cli_available()
        if cli_available:
            self._cli_backend = get_claude_cli_backend()
            self.backend = self._cli_backend
            self._use_cli_mode = True
        else:
            self.backend = ClaudeBackend(model="sonnet-4-5")
            self._use_cli_mode = False

    def _on_auth_mode_changed(self, index: int):
        """認証モード変更時 (v2.5.0, v3.0.0: Ollama追加, v3.2.0: CLI Backend強化, v3.9.2: UI無効化)"""
        if index == 0:  # CLI (Max/Proプラン)
            cli_available, message = check_claude_cli_available()
            if cli_available:
                self._cli_backend = get_claude_cli_backend()
                self.backend = self._cli_backend
                self._use_cli_mode = True
                self._use_ollama_mode = False
                self.statusChanged.emit(t('desktop.soloAI.cliAuthSwitched'))
            else:
                # CLIが利用不可の場合は警告して元に戻す
                QMessageBox.warning(
                    self,
                    t('desktop.soloAI.cliAuthWarningTitle'),
                    t('desktop.soloAI.cliNotAvailableDialogMsg', message=message)
                )
                self.auth_mode_combo.blockSignals(True)
                self.auth_mode_combo.setCurrentIndex(1)
                self.auth_mode_combo.blockSignals(False)
                self._use_cli_mode = False
                self._use_ollama_mode = False
            # v3.9.2: CLI/APIモードではUIを有効化
            self._set_ollama_ui_disabled(False)
        elif index == 1:  # API (従量課金)
            # v7.1.0: userDataからmodel_idを取得
            model_id = self.model_combo.currentData() or DEFAULT_CLAUDE_MODEL_ID
            if "opus" in model_id:
                self.backend = ClaudeBackend(model="opus-4-5")
            elif "sonnet" in model_id:
                self.backend = ClaudeBackend(model="sonnet-4-5")
            else:
                self.backend = ClaudeBackend(model="sonnet-4-5")
            self._use_cli_mode = False
            self._use_ollama_mode = False
            self.statusChanged.emit(t('desktop.soloAI.apiAuthSwitched'))
            # v3.9.2: CLI/APIモードではUIを有効化
            self._set_ollama_ui_disabled(False)
        else:  # Ollama (ローカル) - v3.0.0
            self._use_cli_mode = False
            self._use_ollama_mode = True
            self._configure_ollama_mode()
            # v3.9.2: Ollamaモードでは使用モデル・思考を無効化
            self._set_ollama_ui_disabled(True)
            self.statusChanged.emit(t('desktop.soloAI.ollamaSwitched', model=self._ollama_model))

        self._update_auth_status()

    def _set_ollama_ui_disabled(self, disabled: bool):
        """v3.9.2: Ollamaモード時のUI無効化制御 (v3.9.4: グレーアウト視覚フィードバック追加)"""
        # v3.9.4: 無効化時のグレーアウトスタイル
        disabled_style = """
            QComboBox:disabled {
                background-color: #404040;
                color: #808080;
                border: 1px solid #505050;
            }
        """
        enabled_style = ""

        # 使用モデルドロップダウンを無効化
        if hasattr(self, 'model_combo'):
            self.model_combo.setEnabled(not disabled)
            # v3.9.4: 視覚的なグレーアウト
            self.model_combo.setStyleSheet(disabled_style if disabled else enabled_style)
            if disabled:
                self.model_combo.setToolTip(
                    t('desktop.soloAI.ollamaModelTooltip', model=getattr(self, '_ollama_model', t('desktop.soloAI.notConfigured')))
                )
            else:
                tooltip_lines = t('desktop.soloAI.modelTooltipHtml')
                for model_def in CLAUDE_MODELS:
                    tooltip_lines += f"<b>{model_def['display_name']}:</b> {model_def['description']}<br>"
                self.model_combo.setToolTip(tooltip_lines
                )

        # 思考モード選択を無効化
        if hasattr(self, 'thinking_combo'):
            self.thinking_combo.setEnabled(not disabled)
            # v3.9.4: 視覚的なグレーアウト
            self.thinking_combo.setStyleSheet(disabled_style if disabled else enabled_style)
            if disabled:
                self.thinking_combo.setCurrentIndex(0)  # OFFに戻す
                self.thinking_combo.setToolTip(
                    t('desktop.soloAI.thinkingDisabledTooltip')
                )

    def _configure_ollama_mode(self):
        """Ollamaモードの設定 (v3.0.0, v3.9.2: 設定タブ参照を修正)"""
        import os

        # v3.9.2: soloAI(Claude)タブの設定からOllama設定を取得
        ollama_url = "http://localhost:11434"
        self._ollama_model = "qwen3-coder"

        # 自身の設定タブ（サブタブ）から取得
        if hasattr(self, 'settings_ollama_url'):
            ollama_url = self.settings_ollama_url.text().strip() or ollama_url
        if hasattr(self, 'settings_ollama_model'):
            self._ollama_model = self.settings_ollama_model.currentText().strip() or self._ollama_model

        # Ollama URL と モデルを保存（送信時に参照）
        self._ollama_url = ollama_url

        # v6.0.0: API関連環境変数の設定を削除（CLI専用化）

        # LocalBackendを使用
        from ..backends import LocalBackend
        self.backend = LocalBackend()

    def _update_auth_status(self):
        """認証状態を更新表示 (v2.5.0, v3.0.0: Ollama追加)"""
        if hasattr(self, '_use_ollama_mode') and self._use_ollama_mode:
            # v3.0.0: Ollamaモード
            import os
            ollama_url = os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:11434")
            model_name = getattr(self, '_ollama_model', 'qwen3-coder')
            self.auth_status_label.setText("🖥️")
            self.auth_status_label.setStyleSheet("color: #3b82f6; font-size: 12pt;")
            self.auth_status_label.setToolTip(
                t('desktop.soloAI.ollamaAuthTooltip', url=ollama_url, model=model_name)
            )
        elif hasattr(self, '_use_cli_mode') and self._use_cli_mode:
            cli_available, _ = check_claude_cli_available()
            if cli_available:
                self.auth_status_label.setText("✅")
                self.auth_status_label.setStyleSheet("color: #22c55e; font-size: 12pt;")
                self.auth_status_label.setToolTip(
                    t('desktop.soloAI.cliAuthPrefix')
                    + t('desktop.soloAI.cliProTooltip')
                )
            else:
                self.auth_status_label.setText("⚠️")
                self.auth_status_label.setStyleSheet("color: #fbbf24; font-size: 12pt;")
                self.auth_status_label.setToolTip(t('desktop.soloAI.cliNotConnectedTooltip'))
        else:
            # v6.0.0: API認証は廃止、CLI専用化
            self.auth_status_label.setText("⚙️")
            self.auth_status_label.setStyleSheet("color: #fbbf24; font-size: 12pt;")
            self.auth_status_label.setToolTip(
                t('desktop.soloAI.apiDeprecatedLongTooltip')
            )

    def _init_ui(self):
        """UIを初期化 (v3.9.0: サブタブ構造に変更)"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # サブタブウィジェット
        self.sub_tabs = QTabWidget()

        # チャットサブタブ
        chat_tab = self._create_chat_tab()
        self.sub_tabs.addTab(chat_tab, t('desktop.soloAI.chatSubTab'))

        # 設定サブタブ
        settings_tab = self._create_settings_tab()
        self.sub_tabs.addTab(settings_tab, t('desktop.soloAI.settingsSubTab'))

        layout.addWidget(self.sub_tabs)

    def _create_chat_tab(self) -> QWidget:
        """チャットサブタブを作成（既存のチャットUI）"""
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # 工程バー
        workflow_bar = self._create_workflow_bar()
        chat_layout.addWidget(workflow_bar)

        # ツールバー
        toolbar = self._create_toolbar()
        chat_layout.addWidget(toolbar)

        # メインスプリッター (チャット表示と入力エリア)
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # チャット表示エリア
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Yu Gothic UI", 10))
        self.chat_display.setStyleSheet(
            "QTextEdit { background-color: #0a0a1a; border: none; "
            "padding: 10px; color: #e0e0e0; }" + SCROLLBAR_STYLE
        )
        main_splitter.addWidget(self.chat_display)

        # 入力エリア
        input_frame = self._create_input_area()
        main_splitter.addWidget(input_frame)

        main_splitter.setSizes([600, 200])
        main_splitter.setHandleWidth(2)
        chat_layout.addWidget(main_splitter)

        return chat_widget

    def _create_settings_tab(self) -> QWidget:
        """設定サブタブを作成 (v3.9.0: Claude関連設定を統合)"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(10, 10, 10, 10)

        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # === v8.1.0: CLI認証設定（API Key/MCP/モデル設定は一般設定に移設） ===
        self.api_group = QGroupBox(t('desktop.soloAI.cliAuthGroup'))
        api_group = self.api_group
        api_layout = QFormLayout()

        # CLIステータス
        cli_status_layout = QHBoxLayout()
        cli_available, cli_msg = check_claude_cli_available()
        self.cli_status_label = QLabel(f"{t('desktop.soloAI.cliEnabled') if cli_available else t('desktop.soloAI.cliDisabled')}")
        self.cli_status_label.setToolTip(cli_msg)
        cli_status_layout.addWidget(self.cli_status_label)
        self.cli_check_btn = QPushButton(t('common.confirm'))
        cli_check_btn = self.cli_check_btn
        cli_check_btn.clicked.connect(self._check_cli_status)
        cli_status_layout.addWidget(cli_check_btn)
        cli_status_layout.addStretch()
        api_layout.addRow("Claude CLI:", cli_status_layout)

        # === v3.9.2: 統合接続テスト ===
        test_group_layout = QHBoxLayout()
        self.unified_test_btn = QPushButton(t('desktop.soloAI.testBtnLabel'))
        self.unified_test_btn.setToolTip(t('desktop.soloAI.testBtnTooltip'))
        self.unified_test_btn.clicked.connect(self._run_unified_model_test)
        test_group_layout.addWidget(self.unified_test_btn)
        api_layout.addRow("", test_group_layout)

        # 最終テスト成功表示 (v3.9.2)
        self.last_test_success_label = QLabel("")
        self.last_test_success_label.setStyleSheet("color: #22c55e; font-size: 9pt;")
        api_layout.addRow("", self.last_test_success_label)
        self._load_last_test_success()

        api_group.setLayout(api_layout)
        scroll_layout.addWidget(api_group)

        # === Ollama設定 ===
        self.ollama_group = QGroupBox(t('desktop.soloAI.ollamaSettingsGroup'))
        ollama_group = self.ollama_group
        ollama_layout = QVBoxLayout(ollama_group)

        # Ollama URL
        ollama_url_layout = QHBoxLayout()
        self.ollama_url_label = QLabel(t('desktop.soloAI.hostUrlLabel'))
        ollama_url_layout.addWidget(self.ollama_url_label)
        self.settings_ollama_url = QLineEdit("http://localhost:11434")
        ollama_url_layout.addWidget(self.settings_ollama_url)
        self.ollama_test_btn = QPushButton(t('desktop.soloAI.connTestBtn'))
        self.ollama_test_btn.clicked.connect(self._test_ollama_settings)
        ollama_url_layout.addWidget(self.ollama_test_btn)
        ollama_layout.addLayout(ollama_url_layout)

        # Ollamaモデル (v3.9.4: 初期状態空、モデル一覧更新に名称変更、スクロール無効)
        ollama_model_layout = QHBoxLayout()
        self.ollama_model_label = QLabel(t('desktop.soloAI.useModelLabel'))
        ollama_model_layout.addWidget(self.ollama_model_label)
        self.settings_ollama_model = QComboBox()
        self.settings_ollama_model.setEditable(False)  # v3.9.4: プルダウンのみ
        # v3.9.4: 初期状態は空（モデル一覧更新ボタンを押すまで）
        self.settings_ollama_model.setPlaceholderText(t('desktop.soloAI.ollamaModelPlaceholder'))
        # v3.9.4: スクロールで変更されないようにフォーカスポリシーを設定
        self.settings_ollama_model.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.settings_ollama_model.installEventFilter(self)
        ollama_model_layout.addWidget(self.settings_ollama_model)
        self.refresh_models_btn = QPushButton(t('desktop.soloAI.refreshModelsBtn'))  # v3.9.4: 名称変更
        refresh_models_btn = self.refresh_models_btn
        refresh_models_btn.clicked.connect(self._refresh_ollama_models_settings)
        ollama_model_layout.addWidget(refresh_models_btn)
        ollama_layout.addLayout(ollama_model_layout)

        # ステータス
        self.settings_ollama_status = QLabel(t('desktop.soloAI.ollamaStatusInit'))
        self.settings_ollama_status.setStyleSheet("color: #888;")
        ollama_layout.addWidget(self.settings_ollama_status)

        scroll_layout.addWidget(ollama_group)

        # v8.1.0: MCPサーバー管理・Claudeモデル設定は一般設定タブに移設

        # 保存ボタン
        save_btn_layout = QHBoxLayout()
        save_btn_layout.addStretch()
        self.save_settings_btn = QPushButton(t('desktop.soloAI.saveSettingsBtnLabel'))
        save_settings_btn = self.save_settings_btn
        save_settings_btn.setToolTip(t('desktop.soloAI.saveBtnTooltip'))
        save_settings_btn.clicked.connect(self._save_claude_settings)
        save_btn_layout.addWidget(save_settings_btn)
        scroll_layout.addLayout(save_btn_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        settings_layout.addWidget(scroll)

        return settings_widget

    def _check_cli_status(self):
        """CLI状態を確認"""
        cli_available, cli_msg = check_claude_cli_available()
        self.cli_status_label.setText(f"{t('desktop.soloAI.cliEnabled') if cli_available else t('desktop.soloAI.cliDisabled')}")
        self.cli_status_label.setToolTip(cli_msg)
        if cli_available:
            QMessageBox.information(self, t('desktop.soloAI.cliAvailableTitle'), t('desktop.soloAI.cliAvailableMsg', msg=cli_msg))
        else:
            QMessageBox.warning(self, t('desktop.soloAI.cliAvailableTitle'), t('desktop.soloAI.cliUnavailableMsg', msg=cli_msg))

    def _test_ollama_settings(self):
        """Ollama接続テスト（設定タブ用）"""
        try:
            import ollama
            url = self.settings_ollama_url.text().strip()
            client = ollama.Client(host=url)
            response = client.list()
            model_count = len(response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', []))
            self.settings_ollama_status.setText(t('desktop.soloAI.ollamaConnSuccess', count=model_count))
            self.settings_ollama_status.setStyleSheet("color: #22c55e;")
        except Exception as e:
            self.settings_ollama_status.setText(t('desktop.soloAI.ollamaConnFailed', error=str(e)[:30]))
            self.settings_ollama_status.setStyleSheet("color: #ef4444;")

    # ========================================
    # v3.9.2: 接続テスト・動作確認機能
    # ========================================

    def _test_api_connection(self):
        """API接続テスト (v6.0.0: 廃止 - CLI専用化)"""
        # v6.0.0: API認証は廃止されました
        if hasattr(self, 'api_test_status'):
            self.api_test_status.setText(t('desktop.soloAI.apiDeprecatedStatus'))
            self.api_test_status.setStyleSheet("color: #fbbf24;")
            self.api_test_status.setToolTip(
                t('desktop.soloAI.apiDeprecatedDialogMsg')
            )

    def _run_unified_model_test(self):
        """統合モデルテスト: 現在の認証方式でテスト実行 (v3.9.2)"""
        import logging
        logger = logging.getLogger(__name__)

        auth_mode = self.auth_mode_combo.currentIndex()  # 0: CLI, 1: API, 2: Ollama
        auth_names = ["CLI (Max/Pro)", "API", "Ollama"]
        auth_name = auth_names[auth_mode] if auth_mode < len(auth_names) else t('desktop.soloAI.unknownAuth')

        try:
            if auth_mode == 0:
                # CLI モード
                cli_available, _ = check_claude_cli_available()
                if not cli_available:
                    QMessageBox.warning(self, t('desktop.soloAI.testFailedTitle'), t('desktop.soloAI.testFailedCliMsg'))
                    return

                # CLI テスト（簡易）
                from ..utils.subprocess_utils import run_hidden
                import time
                start = time.time()
                result = run_hidden(
                    ["claude", "--version"],
                    capture_output=True, text=True, timeout=10
                )
                latency = time.time() - start

                if result.returncode == 0:
                    self._save_last_test_success("CLI", latency)
                    QMessageBox.information(
                        self, t('desktop.soloAI.testSuccessTitle'),
                        t('desktop.soloAI.testResultMsg', auth_name=auth_name, latency=f"{latency:.2f}")
                        + f"\nCLI Version: {result.stdout.strip()}"
                    )
                else:
                    QMessageBox.warning(self, t('desktop.soloAI.testFailedTitle'), t('desktop.soloAI.testFailedCliError', error=result.stderr))

            elif auth_mode == 1:
                # API モード (v8.1.0: 廃止済み)
                QMessageBox.warning(self, t('desktop.soloAI.apiDeprecatedTitle'), t('desktop.soloAI.apiDeprecatedFullMsg'))

            else:
                # Ollama モード
                import ollama
                import time

                url = self.settings_ollama_url.text().strip()
                model = self.settings_ollama_model.currentText()
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
                    self, t('desktop.soloAI.testSuccessTitle'),
                    t('desktop.soloAI.testResultMsgShort', auth_name=auth_name, model=model, latency=f"{latency:.2f}")
                )

        except Exception as e:
            logger.error(f"[Unified Model Test] Error: {e}")
            QMessageBox.warning(self, t('desktop.soloAI.testFailedTitle'), t('desktop.soloAI.testFailedAuth', auth=auth_name, error=str(e)))

    def _load_last_test_success(self):
        """最終テスト成功情報を読み込み (v3.9.2)"""
        import json
        from pathlib import Path

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
                            t('desktop.soloAI.lastTestSuccessLabel', auth=auth, timestamp=timestamp, latency=f"{latency:.2f}")
                        )
        except Exception:
            pass

    def _save_last_test_success(self, auth_type: str, latency: float):
        """最終テスト成功情報を保存 (v3.9.2)"""
        import json
        from pathlib import Path
        from datetime import datetime

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
                t('desktop.soloAI.lastTestSuccessLabel', auth=auth_type, timestamp=timestamp, latency=f"{latency:.2f}")
            )
        except Exception:
            pass

    def _refresh_ollama_models_settings(self):
        """Ollamaモデル一覧を更新（設定タブ用）"""
        try:
            import ollama
            url = self.settings_ollama_url.text().strip()
            client = ollama.Client(host=url)
            response = client.list()

            models = response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', [])
            model_names = []
            for m in models:
                if isinstance(m, dict):
                    name = m.get('model') or m.get('name', '')
                else:
                    name = getattr(m, 'model', None) or getattr(m, 'name', '')
                if name:
                    model_names.append(name)

            self.settings_ollama_model.clear()
            self.settings_ollama_model.addItems(model_names)
            self.settings_ollama_status.setText(t('desktop.soloAI.modelListSuccess', count=len(model_names)))
            self.settings_ollama_status.setStyleSheet("color: #22c55e;")
        except Exception as e:
            self.settings_ollama_status.setText(t('desktop.soloAI.modelListFailed', error=str(e)[:30]))
            self.settings_ollama_status.setStyleSheet("color: #ef4444;")

    def _populate_mcp_servers(self):
        """MCPサーバーリストを初期化"""
        servers = [
            ("filesystem", t('desktop.soloAI.mcpFilesystem'), True),
            ("git", "🔀 Git", True),
            ("brave-search", t('desktop.soloAI.mcpBraveSearch'), False),
            ("github", "🐙 GitHub", False),
            ("slack", "💬 Slack", False),
        ]
        for server_id, name, default_enabled in servers:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, server_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default_enabled else Qt.CheckState.Unchecked)
            self.mcp_server_list.addItem(item)

    def _set_all_mcp_servers(self, enabled: bool):
        """全MCPサーバーを有効/無効"""
        for i in range(self.mcp_server_list.count()):
            item = self.mcp_server_list.item(i)
            item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)

    def _save_claude_settings(self):
        """Claude設定を保存 (v6.0.0: API認証設定削除)"""
        import json
        from pathlib import Path

        # v6.0.0: API Key設定を削除（CLI専用化）

        # 設定ファイルに保存
        config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
        config_path.parent.mkdir(exist_ok=True)

        settings = {
            "ollama_url": self.settings_ollama_url.text().strip(),
            "ollama_model": self.settings_ollama_model.currentText(),
        }
        # v8.1.0: default_model/timeout/mcp_servers は一般設定タブで管理

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        QMessageBox.information(self, t('desktop.soloAI.saveCompleteTitle'), t('desktop.soloAI.saveCompleteMsg'))
        self.statusChanged.emit(t('desktop.soloAI.savedStatus'))

    def _create_workflow_bar(self) -> QFrame:
        """v8.0.0: ステータスバーを作成（旧ステージUI→SoloAIStatusBarに置換）"""
        frame = QFrame()
        frame.setObjectName("workflowFrame")
        frame.setStyleSheet("#workflowFrame { background-color: #1a1a2e; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # v8.0.0: SoloAIStatusBar（旧S0-S5ステージUIを置換）
        self.solo_status_bar = SoloAIStatusBar()
        self.solo_status_bar.new_session_clicked.connect(self._on_new_session)
        layout.addWidget(self.solo_status_bar)

        # 互換用: phase_label, progress_bar, prev_btn, next_btn等を
        # 非表示の属性として保持（既存コードの参照を壊さないため）
        self.phase_label = QLabel("")
        self.phase_label.setVisible(False)
        self.phase_desc_label = QLabel("")
        self.phase_desc_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.prev_btn = QPushButton()
        self.prev_btn.setVisible(False)
        self.next_btn = QPushButton()
        self.next_btn.setVisible(False)
        self.risk_approval_btn = QPushButton()
        self.risk_approval_btn.setVisible(False)
        self.approval_status_label = QLabel("")
        self.approval_status_label.setVisible(False)
        self.reset_workflow_btn = QPushButton()
        self.reset_workflow_btn.setVisible(False)

        # S3承認チェックリストパネル（機能は保持）
        self.approval_panel = self._create_approval_panel()
        self.approval_panel.setVisible(False)
        layout.addWidget(self.approval_panel)

        return frame

    def _create_approval_panel(self) -> QGroupBox:
        """S3承認チェックリストパネルを作成（Phase 1.2）"""
        from ..security.risk_gate import ApprovalScope

        self.approval_group = QGroupBox(t('desktop.soloAI.approvalScopesGroup'))
        group = self.approval_group
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #0078d4;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #0078d4;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # 説明ラベル
        self.approval_desc_label = QLabel(
            t('desktop.soloAI.approvalPanelDesc')
        )
        desc_label = self.approval_desc_label
        desc_label.setStyleSheet("color: #b0b0b0; font-size: 9pt; font-weight: normal;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # チェックボックスを格納する辞書
        self.approval_checkboxes = {}

        # 各ApprovalScopeのチェックボックスを作成
        for scope in ApprovalScope.all_scopes():
            checkbox = QCheckBox(ApprovalScope.get_display_name(scope))
            checkbox.setToolTip(ApprovalScope.get_description(scope))
            checkbox.setStyleSheet("font-weight: normal;")

            # チェック状態を復元
            checkbox.setChecked(self.approval_state.is_approved(scope))

            # チェック変更時のシグナル
            checkbox.stateChanged.connect(
                lambda state, s=scope: self._on_approval_scope_changed(s, state)
            )

            self.approval_checkboxes[scope] = checkbox
            layout.addWidget(checkbox)

        # 一括操作ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.approve_all_btn = QPushButton(t('desktop.soloAI.approveAllBtnLabel'))
        all_btn = self.approve_all_btn
        all_btn.setMaximumWidth(100)
        all_btn.clicked.connect(self._approve_all_scopes)
        button_layout.addWidget(all_btn)

        self.revoke_all_btn = QPushButton(t('desktop.soloAI.revokeAllBtnLabel'))
        none_btn = self.revoke_all_btn
        none_btn.setMaximumWidth(100)
        none_btn.clicked.connect(self._revoke_all_scopes)
        button_layout.addWidget(none_btn)

        layout.addLayout(button_layout)

        return group

    def _create_toolbar(self) -> QFrame:
        """v8.0.0: オプションバー（2行レイアウト）を作成"""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #0f0f1a;
                border-bottom: 1px solid #2a2a3e;
            }
            QLabel { color: #888; font-size: 11px; }
            QComboBox { font-size: 11px; max-height: 24px; }
            QCheckBox { font-size: 11px; color: #ccc; spacing: 4px; }
        """)
        main_layout = QVBoxLayout(toolbar)
        main_layout.setContentsMargins(10, 4, 10, 4)
        main_layout.setSpacing(2)

        # === 行1: 認証 | モデル | 思考 ===
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.auth_label = QLabel(t('desktop.soloAI.authLabel2'))
        row1.addWidget(self.auth_label)
        self.auth_mode_combo = QComboBox()
        self.auth_mode_combo.addItems([
            t('desktop.soloAI.authCliOption'),
            t('desktop.soloAI.authApiOption'),
            t('desktop.soloAI.authOllamaOption'),
        ])
        self.auth_mode_combo.setToolTip(
            t('desktop.soloAI.authComboTooltipFull')
        )
        self.auth_mode_combo.currentIndexChanged.connect(self._on_auth_mode_changed)
        row1.addWidget(self.auth_mode_combo)

        self.auth_status_label = QLabel("")
        self.auth_status_label.setStyleSheet("font-size: 9pt; margin-left: 3px;")
        row1.addWidget(self.auth_status_label)
        self._update_auth_status()

        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #333; font-size: 12px;")
        row1.addWidget(sep1)

        self.model_label = QLabel(t('desktop.soloAI.modelLabel2'))
        row1.addWidget(self.model_label)
        self.model_combo = QComboBox()
        for model_def in CLAUDE_MODELS:
            self.model_combo.addItem(model_def["display_name"], userData=model_def["id"])
        tooltip_lines = t('desktop.soloAI.modelTooltipHtml')
        for model_def in CLAUDE_MODELS:
            tooltip_lines += f"<b>{model_def['display_name']}:</b> {model_def['description']}<br>"
        self.model_combo.setToolTip(t('desktop.soloAI.modelReadonlyTooltip'))
        row1.addWidget(self.model_combo)

        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #333; font-size: 12px;")
        row1.addWidget(sep2)

        self.thinking_label = QLabel(t('desktop.soloAI.thinkingLabel2'))
        row1.addWidget(self.thinking_label)
        self.thinking_combo = QComboBox()
        self.thinking_combo.addItems(["OFF", "Standard", "Deep"])
        self.thinking_combo.setToolTip(t('desktop.soloAI.thinkingShortTooltip'))
        row1.addWidget(self.thinking_combo)

        row1.addStretch()
        main_layout.addLayout(row1)

        # === 行2: MCP | 差分表示 | 自動コンテキスト | 許可 | 新規セッション ===
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.mcp_checkbox = QCheckBox("MCP")
        self.mcp_checkbox.setChecked(True)
        self.mcp_checkbox.setToolTip(t('desktop.soloAI.mcpCheckboxTooltip'))
        row2.addWidget(self.mcp_checkbox)

        self.diff_checkbox = QCheckBox(t('desktop.soloAI.diffCheckLabel'))
        self.diff_checkbox.setChecked(True)
        self.diff_checkbox.setToolTip(t('desktop.soloAI.diffCheckboxTooltip'))
        row2.addWidget(self.diff_checkbox)

        self.context_checkbox = QCheckBox(t('desktop.soloAI.autoContextLabel'))
        self.context_checkbox.setChecked(True)
        self.context_checkbox.setToolTip(t('desktop.soloAI.contextCheckboxTooltip'))
        row2.addWidget(self.context_checkbox)

        self.permission_skip_checkbox = QCheckBox(t('desktop.soloAI.permissionLabel'))
        self.permission_skip_checkbox.setChecked(True)
        self.permission_skip_checkbox.setToolTip(t('desktop.soloAI.permissionSkipTooltip'))
        self.permission_skip_checkbox.setStyleSheet("""
            QCheckBox { padding: 2px 6px; border-radius: 3px; }
            QCheckBox:checked { background-color: #2d7d46; color: white; }
        """)
        row2.addWidget(self.permission_skip_checkbox)

        row2.addStretch()

        # v8.3.2: Row 2の新規セッションボタンを削除（SoloAIStatusBar側に統一）

        main_layout.addLayout(row2)

        return toolbar

    def _create_input_area(self) -> QFrame:
        """入力エリアを作成 (v3.4.0: 会話継続UIを追加, v5.1: 添付ファイルバー追加)"""
        frame = QFrame()
        frame.setObjectName("inputFrame")
        frame.setStyleSheet("#inputFrame { border-top: 1px solid #3d3d3d; }")
        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # === v3.4.0: 横分割レイアウト（左: 入力エリア, 右: 会話継続エリア） ===
        h_layout = QHBoxLayout()
        h_layout.setSpacing(10)

        # --- 左側: 入力エリア (約2/3幅) ---
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        # v5.1: 添付ファイルバー（入力フィールドの上に表示）
        self.attachment_bar = SoloAIAttachmentBar()
        self.attachment_bar.attachments_changed.connect(self._on_attachments_changed)
        left_layout.addWidget(self.attachment_bar)

        # 入力フィールド
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText(t('desktop.soloAI.inputPlaceholder'))
        self.input_field.setFont(QFont("Yu Gothic UI", 11))
        self.input_field.setMinimumHeight(40)
        self.input_field.setMaximumHeight(150)
        self.input_field.setStyleSheet("border: none; background-color: #252526;")
        self.input_field.setAcceptDrops(True)
        left_layout.addWidget(self.input_field)

        # ボタン行
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 0, 0)

        self.attach_btn = QPushButton("📎 " + t('common.attach'))
        self.attach_btn.setToolTip(t('desktop.soloAI.attachTooltip'))
        btn_layout.addWidget(self.attach_btn)

        # v3.1.0: 履歴から引用ボタン
        self.citation_btn = QPushButton(t('desktop.soloAI.citationBtnLabel'))
        self.citation_btn.setToolTip(t('desktop.soloAI.citationTooltip'))
        btn_layout.addWidget(self.citation_btn)

        # v3.6.0: スニペットボタン（ClaudeCodeから移植）→ v3.7.0: プルダウンメニュー形式に変更
        from PyQt6.QtWidgets import QMenu
        self.snippet_btn = QPushButton(t('desktop.soloAI.snippetBtnLabel'))
        self.snippet_btn.setToolTip(t('desktop.soloAI.snippetTooltip'))
        self.snippet_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.snippet_btn.customContextMenuRequested.connect(self._on_snippet_context_menu)
        btn_layout.addWidget(self.snippet_btn)

        # v5.1.1: スニペット管理ボタン（追加・編集・削除）
        self.snippet_add_btn = QPushButton(t('desktop.soloAI.snippetAddBtnLabel'))
        self.snippet_add_btn.setToolTip(t('desktop.soloAI.snippetAddTooltip'))
        self.snippet_add_btn.setMaximumWidth(60)
        self.snippet_add_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.snippet_add_btn.customContextMenuRequested.connect(self._on_snippet_context_menu)
        btn_layout.addWidget(self.snippet_add_btn)

        btn_layout.addStretch()

        self.send_btn = QPushButton(t('common.send') + " ▶")
        self.send_btn.setDefault(True)
        self.send_btn.setToolTip(t('desktop.soloAI.sendTooltip'))
        btn_layout.addWidget(self.send_btn)

        left_layout.addLayout(btn_layout)
        h_layout.addWidget(left_frame, 2)  # 左側に2/3幅

        # --- 右側: 会話継続エリア (約1/3幅) v3.4.0 ---
        continue_frame = QFrame()
        continue_frame.setObjectName("continueFrame")
        continue_frame.setStyleSheet("""
            #continueFrame {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        continue_layout = QVBoxLayout(continue_frame)
        continue_layout.setContentsMargins(8, 8, 8, 8)
        continue_layout.setSpacing(6)

        # ヘッダー
        self.continue_header = QLabel(t('desktop.soloAI.conversationContinueLabel'))
        continue_header = self.continue_header
        continue_header.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 11px;")
        continue_layout.addWidget(continue_header)

        # 説明
        self.continue_desc = QLabel(t('desktop.soloAI.continueDesc'))
        continue_desc = self.continue_desc
        continue_desc.setStyleSheet("color: #888; font-size: 10px;")
        continue_desc.setWordWrap(True)
        continue_layout.addWidget(continue_desc)

        # 継続入力フィールド
        self.continue_input = QTextEdit()
        self.continue_input.setPlaceholderText(t('desktop.soloAI.continuePlaceholder'))
        self.continue_input.setMaximumHeight(50)
        self.continue_input.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
                color: #dcdcdc;
                font-size: 11px;
            }
            QTextEdit:focus {
                border-color: #007acc;
            }
        """)
        continue_layout.addWidget(self.continue_input)

        # クイックボタン行
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(4)

        # 「はい」ボタン
        self.quick_yes_btn = QPushButton(t('desktop.soloAI.quickYesLabel'))
        self.quick_yes_btn.setMaximumHeight(24)
        self.quick_yes_btn.setToolTip(t('desktop.soloAI.quickYesTooltip'))
        self.quick_yes_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d8b4e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d9d56;
            }
        """)
        quick_btn_layout.addWidget(self.quick_yes_btn)

        # 「続行」ボタン
        self.quick_continue_btn = QPushButton(t('desktop.soloAI.continueBtn'))
        self.quick_continue_btn.setMaximumHeight(24)
        self.quick_continue_btn.setToolTip(t('desktop.soloAI.quickContinueTooltip'))
        self.quick_continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066aa;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        quick_btn_layout.addWidget(self.quick_continue_btn)

        # 「実行」ボタン
        self.quick_exec_btn = QPushButton(t('desktop.soloAI.execBtn'))
        self.quick_exec_btn.setMaximumHeight(24)
        self.quick_exec_btn.setToolTip(t('desktop.soloAI.quickExecTooltip'))
        self.quick_exec_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5ce7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d6ef8;
            }
        """)
        quick_btn_layout.addWidget(self.quick_exec_btn)

        continue_layout.addLayout(quick_btn_layout)

        # 送信ボタン
        self.continue_send_btn = QPushButton(t('desktop.soloAI.sendBtnLabel'))
        self.continue_send_btn.setToolTip(t('desktop.soloAI.continueSendTooltip'))
        self.continue_send_btn.setMaximumHeight(28)
        self.continue_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1088e4;
            }
        """)
        continue_layout.addWidget(self.continue_send_btn)

        h_layout.addWidget(continue_frame, 1)  # 右側に1/3幅

        main_layout.addLayout(h_layout)
        return frame

    def _connect_signals(self):
        """シグナルを接続"""
        self.send_btn.clicked.connect(self._on_send)
        # v8.3.2: new_session_btn削除 → SoloAIStatusBar.new_session_clicked で接続済み

        # v5.1: ファイル添付ボタン
        self.attach_btn.clicked.connect(self._on_attach_file)

        # v3.1.0: 履歴から引用ボタン
        self.citation_btn.clicked.connect(self._on_citation)

        # v3.6.0: スニペットボタン（ClaudeCodeから移植）→ v3.7.0: 強化
        self.snippet_btn.clicked.connect(self._on_snippet_menu)
        self.snippet_add_btn.clicked.connect(self._on_snippet_add)

        # 工程関連
        self.prev_btn.clicked.connect(self._on_prev_phase)
        self.next_btn.clicked.connect(self._on_next_phase)
        self.reset_workflow_btn.clicked.connect(self._on_reset_workflow)
        self.risk_approval_btn.clicked.connect(self._on_toggle_approval_panel)

        # v3.4.0: 会話継続ボタン
        self.quick_yes_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.soloAI.quickYesMsg')))
        self.quick_continue_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.soloAI.quickContinueMsg')))
        self.quick_exec_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.soloAI.quickExecMsg')))
        self.continue_send_btn.clicked.connect(self._send_continue_from_input)

        # TODO: self.input_field の Ctrl+Enter ショートカットを接続

    def retranslateUi(self):
        """言語変更時に全UIテキストを再適用"""
        # === Sub tabs ===
        self.sub_tabs.setTabText(0, t('desktop.soloAI.chatSubTab'))
        self.sub_tabs.setTabText(1, t('desktop.soloAI.settingsSubTab'))

        # === Settings tab - GroupBox titles ===
        self.api_group.setTitle(t('desktop.soloAI.cliAuthGroup'))
        self.ollama_group.setTitle(t('desktop.soloAI.ollamaSettingsGroup'))
        self.approval_group.setTitle(t('desktop.soloAI.approvalScopesGroup'))

        # === Settings tab - CLI auth section ===
        cli_available, _ = check_claude_cli_available()
        self.cli_status_label.setText(
            t('desktop.soloAI.cliEnabled') if cli_available else t('desktop.soloAI.cliDisabled')
        )
        self.cli_check_btn.setText(t('common.confirm'))
        self.unified_test_btn.setText(t('desktop.soloAI.testBtnLabel'))
        self.unified_test_btn.setToolTip(t('desktop.soloAI.testBtnTooltip'))

        # === Settings tab - Ollama section ===
        self.ollama_url_label.setText(t('desktop.soloAI.hostUrlLabel'))
        self.ollama_test_btn.setText(t('desktop.soloAI.connTestBtn'))
        self.ollama_model_label.setText(t('desktop.soloAI.useModelLabel'))
        self.settings_ollama_model.setPlaceholderText(t('desktop.soloAI.ollamaModelPlaceholder'))
        self.refresh_models_btn.setText(t('desktop.soloAI.refreshModelsBtn'))

        # === Settings tab - Save button ===
        self.save_settings_btn.setText(t('desktop.soloAI.saveSettingsBtnLabel'))
        self.save_settings_btn.setToolTip(t('desktop.soloAI.saveBtnTooltip'))

        # === Toolbar row 1: Auth / Model / Thinking ===
        self.auth_label.setText(t('desktop.soloAI.authLabel2'))

        # auth_mode_combo items (preserve selection)
        old_auth_idx = self.auth_mode_combo.currentIndex()
        self.auth_mode_combo.blockSignals(True)
        self.auth_mode_combo.clear()
        self.auth_mode_combo.addItems([
            t('desktop.soloAI.authCliOption'),
            t('desktop.soloAI.authApiOption'),
            t('desktop.soloAI.authOllamaOption'),
        ])
        self.auth_mode_combo.setCurrentIndex(old_auth_idx)
        self.auth_mode_combo.blockSignals(False)
        self.auth_mode_combo.setToolTip(t('desktop.soloAI.authComboTooltipFull'))

        self.model_label.setText(t('desktop.soloAI.modelLabel2'))
        self.model_combo.setToolTip(t('desktop.soloAI.modelReadonlyTooltip'))

        self.thinking_label.setText(t('desktop.soloAI.thinkingLabel2'))
        self.thinking_combo.setToolTip(t('desktop.soloAI.thinkingShortTooltip'))

        # === Toolbar row 2: Checkboxes ===
        self.mcp_checkbox.setToolTip(t('desktop.soloAI.mcpCheckboxTooltip'))
        self.diff_checkbox.setText(t('desktop.soloAI.diffCheckLabel'))
        self.diff_checkbox.setToolTip(t('desktop.soloAI.diffCheckboxTooltip'))
        self.context_checkbox.setText(t('desktop.soloAI.autoContextLabel'))
        self.context_checkbox.setToolTip(t('desktop.soloAI.contextCheckboxTooltip'))
        self.permission_skip_checkbox.setText(t('desktop.soloAI.permissionLabel'))
        self.permission_skip_checkbox.setToolTip(t('desktop.soloAI.permissionSkipTooltip'))

        # === Input area ===
        self.input_field.setPlaceholderText(t('desktop.soloAI.inputPlaceholder'))
        self.attach_btn.setText("📎 " + t('common.attach'))
        self.attach_btn.setToolTip(t('desktop.soloAI.attachTooltip'))
        self.citation_btn.setText(t('desktop.soloAI.citationBtnLabel'))
        self.citation_btn.setToolTip(t('desktop.soloAI.citationTooltip'))
        self.snippet_btn.setText(t('desktop.soloAI.snippetBtnLabel'))
        self.snippet_btn.setToolTip(t('desktop.soloAI.snippetTooltip'))
        self.snippet_add_btn.setText(t('desktop.soloAI.snippetAddBtnLabel'))
        self.snippet_add_btn.setToolTip(t('desktop.soloAI.snippetAddTooltip'))
        self.send_btn.setText(t('common.send') + " ▶")
        self.send_btn.setToolTip(t('desktop.soloAI.sendTooltip'))

        # === Continue area ===
        self.continue_header.setText(t('desktop.soloAI.conversationContinueLabel'))
        self.continue_desc.setText(t('desktop.soloAI.continueDesc'))
        self.continue_input.setPlaceholderText(t('desktop.soloAI.continuePlaceholder'))
        self.quick_yes_btn.setText(t('desktop.soloAI.quickYesLabel'))
        self.quick_yes_btn.setToolTip(t('desktop.soloAI.quickYesTooltip'))
        self.quick_continue_btn.setText(t('desktop.soloAI.continueBtn'))
        self.quick_continue_btn.setToolTip(t('desktop.soloAI.quickContinueTooltip'))
        self.quick_exec_btn.setText(t('desktop.soloAI.execBtn'))
        self.quick_exec_btn.setToolTip(t('desktop.soloAI.quickExecTooltip'))
        self.continue_send_btn.setText(t('desktop.soloAI.sendBtnLabel'))
        self.continue_send_btn.setToolTip(t('desktop.soloAI.continueSendTooltip'))

        # === Approval panel ===
        self.approval_desc_label.setText(t('desktop.soloAI.approvalPanelDesc'))
        self.approve_all_btn.setText(t('desktop.soloAI.approveAllBtnLabel'))
        self.revoke_all_btn.setText(t('desktop.soloAI.revokeAllBtnLabel'))

        # risk_approval_btn - dynamic text based on panel visibility
        if self.approval_panel.isVisible():
            self.risk_approval_btn.setText(t('desktop.soloAI.riskApprovalClose'))
        else:
            self.risk_approval_btn.setText(t('desktop.soloAI.riskApprovalOpen'))

        # Child widget retranslation
        if hasattr(self, 'solo_status_bar') and hasattr(self.solo_status_bar, 'retranslateUi'):
            self.solo_status_bar.retranslateUi()

    def _on_send(self):
        """送信ボタン押下時"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            message = self.input_field.toPlainText().strip()
            if not message:
                return

            # 送信ガードをチェック
            can_send, guard_message = self._check_send_guard()
            if not can_send:
                QMessageBox.warning(
                    self,
                    t('desktop.soloAI.sendBlockTitle'),
                    f"{guard_message}\n\n{t('desktop.soloAI.proceedWorkflowRetry')}"
                )
                return

            self._send_message(message)
            self.input_field.clear()

        except Exception as e:
            # 例外発生時もアプリは落とさない
            error_msg = f"{type(e).__name__}: {str(e)}"

            # app.log に ERROR レベルで記録
            logger.error(f"[ClaudeTab._on_send] Exception occurred: {error_msg}", exc_info=True)

            # crash.log にも記録
            import traceback
            from pathlib import Path
            crash_log_path = Path(__file__).parent.parent.parent / "logs" / "crash.log"
            crash_log_path.parent.mkdir(exist_ok=True)

            try:
                with open(crash_log_path, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[ERROR in _on_send] {timestamp}\n")
                    f.write(f"{'='*80}\n")
                    traceback.print_exc(file=f)
                    f.write(f"\n{'='*80}\n\n")
                    f.flush()
            except Exception as log_error:
                logger.error(f"Failed to write to crash.log: {log_error}")

            # UIにエラー表示
            QMessageBox.critical(
                self,
                t('desktop.soloAI.sendErrorTitle'),
                t('desktop.soloAI.sendErrorMsg', error=error_msg)
            )

            self.statusChanged.emit(t('desktop.soloAI.sendError', error=type(e).__name__))

    def _on_new_session(self):
        """新規セッション開始"""
        self.chat_display.clear()
        self.statusChanged.emit(t('desktop.soloAI.newSessionStarted'))
        self.chat_display.setPlaceholderText(t('desktop.soloAI.chatReady'))
        # v5.1: 添付ファイルもクリア
        self.attachment_bar.clear_all()
        self._attached_files.clear()

    # =========================================================================
    # v5.1: ファイル添付関連メソッド
    # =========================================================================

    def _on_attach_file(self):
        """ファイル添付ボタンクリック"""
        from PyQt6.QtWidgets import QFileDialog
        import logging
        logger = logging.getLogger(__name__)

        files, _ = QFileDialog.getOpenFileNames(
            self, t('desktop.soloAI.selectFileTitle'), "",
            t('desktop.soloAI.fileFilterAll')
        )
        if files:
            self.attachment_bar.add_files(files)
            logger.info(f"[ClaudeTab] Attached {len(files)} files")

    def _on_attachments_changed(self, files: list):
        """添付ファイルリストが変更された"""
        import logging
        logger = logging.getLogger(__name__)
        self._attached_files = files.copy()
        logger.info(f"[ClaudeTab] Attachments updated: {len(files)} files")

    def _on_citation(self):
        """履歴から引用ダイアログを開く (v3.1.0)"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            from ..ui.components.history_citation_widget import HistoryCitationDialog

            citation_text = HistoryCitationDialog.get_citation(self)
            if citation_text:
                # 現在の入力に引用を追加
                current_text = self.input_field.toPlainText()
                if current_text:
                    # 既存テキストがある場合は改行して追加
                    new_text = f"{current_text}\n\n{citation_text}"
                else:
                    new_text = citation_text

                self.input_field.setPlainText(new_text)
                self.statusChanged.emit(t('desktop.soloAI.citationInserted'))
                logger.info("[ClaudeTab] Citation inserted from history")

        except Exception as e:
            logger.error(f"[ClaudeTab._on_citation] Error: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                t('desktop.soloAI.citationErrorTitle'),
                t('desktop.soloAI.citationErrorMsg', error=str(e))
            )

    def _get_snippet_manager(self):
        """スニペットマネージャーを取得 (v5.1.1: PyInstaller対応)"""
        from ..claude.snippet_manager import SnippetManager
        from pathlib import Path
        import sys

        # PyInstallerでビルドされた場合とそうでない場合でパスを分岐
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた場合: exeと同じディレクトリを使用
            app_dir = Path(sys.executable).parent
        else:
            # 開発時: プロジェクトルートを使用
            app_dir = Path(__file__).parent.parent.parent

        data_dir = app_dir / "data"
        unipet_dir = app_dir / "ユニペット"

        # ユニペットフォルダがなければ作成
        data_dir.mkdir(parents=True, exist_ok=True)
        unipet_dir.mkdir(parents=True, exist_ok=True)

        return SnippetManager(data_dir=data_dir, unipet_dir=unipet_dir)

    def _on_snippet_menu(self):
        """スニペットプルダウンメニューを表示 (v3.7.0)"""
        import logging
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        logger = logging.getLogger(__name__)

        try:
            snippet_manager = self._get_snippet_manager()
            snippets = snippet_manager.get_all()

            menu = QMenu(self)

            if not snippets:
                no_snippet_action = menu.addAction(t('desktop.soloAI.noSnippetsMsg'))
                no_snippet_action.setEnabled(False)
            else:
                # カテゴリでグループ化
                categories = snippet_manager.get_categories()
                uncategorized = [s for s in snippets if not s.get("category")]

                # カテゴリがあるスニペット
                for category in categories:
                    cat_menu = menu.addMenu(f"📁 {category}")
                    cat_snippets = snippet_manager.get_by_category(category)
                    for snippet in cat_snippets:
                        action = cat_menu.addAction(snippet.get("name", t('desktop.soloAI.untitled')))
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

                # カテゴリなしスニペット
                if uncategorized:
                    if categories:
                        menu.addSeparator()
                    for snippet in uncategorized:
                        action = menu.addAction(f"📋 {snippet.get('name', t('desktop.soloAI.untitled'))}")
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

            menu.addSeparator()
            open_folder_action = menu.addAction(t('desktop.soloAI.openUnipetFolder'))
            open_folder_action.triggered.connect(lambda: snippet_manager.open_unipet_folder())

            # ボタンの下に表示
            btn_pos = self.snippet_btn.mapToGlobal(QPoint(0, self.snippet_btn.height()))
            menu.exec(btn_pos)

        except Exception as e:
            logger.error(f"[ClaudeTab._on_snippet_menu] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.soloAI.snippetMenuError', error=str(e)))

    def _insert_snippet(self, snippet: dict):
        """スニペットを入力欄に挿入 (v3.7.0)"""
        import logging
        logger = logging.getLogger(__name__)

        content = snippet.get("content", "")
        name = snippet.get("name", t('desktop.soloAI.untitled'))

        current_text = self.input_field.toPlainText()
        if current_text:
            new_text = f"{current_text}\n\n{content}"
        else:
            new_text = content

        self.input_field.setPlainText(new_text)
        self.statusChanged.emit(t('desktop.soloAI.snippetInserted', name=name))
        logger.info(f"[ClaudeTab] Snippet inserted: {name}")

    def _on_snippet_add(self):
        """カスタムスニペット追加ダイアログ (v3.7.0)"""
        import logging
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox
        logger = logging.getLogger(__name__)

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(t('desktop.soloAI.snippetAddDialogTitle'))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.soloAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit()
            name_input.setPlaceholderText(t('desktop.soloAI.snippetNamePlaceholder'))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.soloAI.snippetCategoryLabel'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit()
            cat_input.setPlaceholderText(t('desktop.soloAI.snippetCategoryPlaceholder'))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.soloAI.snippetContentLabel'))
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlaceholderText(t('desktop.soloAI.snippetContentPlaceholder'))
            content_input.setMinimumHeight(150)
            layout.addWidget(content_input)

            # ボタン
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                name = name_input.text().strip()
                content = content_input.toPlainText().strip()

                if not name or not content:
                    QMessageBox.warning(self, t('desktop.soloAI.inputError'), t('desktop.soloAI.nameContentRequired'))
                    return

                category = cat_input.text().strip()
                snippet_manager = self._get_snippet_manager()
                snippet_manager.add(name=name, content=content, category=category)

                self.statusChanged.emit(t('desktop.soloAI.snippetAdded', name=name))
                logger.info(f"[ClaudeTab] Snippet added: {name}")

        except Exception as e:
            logger.error(f"[ClaudeTab._on_snippet_add] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.soloAI.snippetAddError', error=str(e)))

    def _on_snippet_context_menu(self, pos):
        """スニペット右クリックメニュー（編集・削除）(v5.2.0: ユニペット削除対応)"""
        import logging
        from PyQt6.QtWidgets import QMenu, QInputDialog
        logger = logging.getLogger(__name__)

        try:
            snippet_manager = self._get_snippet_manager()
            snippets = snippet_manager.get_all()

            if not snippets:
                return

            menu = QMenu(self)

            # 編集メニュー
            edit_menu = menu.addMenu(t('desktop.soloAI.editMenuItem'))
            for snippet in snippets:
                action = edit_menu.addAction(snippet.get("name", t('desktop.soloAI.untitled')))
                action.triggered.connect(lambda checked, s=snippet: self._edit_snippet(s))

            # 削除メニュー (v5.2.0: ユニペットも削除可能に)
            delete_menu = menu.addMenu(t('desktop.soloAI.deleteMenuItem'))
            for snippet in snippets:
                source = snippet.get("source", "json")
                if source == "unipet":
                    action = delete_menu.addAction(f"🗂️ {snippet.get('name', t('desktop.soloAI.untitled'))} {t('desktop.soloAI.fileDeleteSuffix')}")
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))
                else:
                    action = delete_menu.addAction(snippet.get("name", t('desktop.soloAI.untitled')))
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))

            menu.addSeparator()
            reload_action = menu.addAction(t('desktop.soloAI.reloadMenuItem'))
            reload_action.triggered.connect(lambda: (self._get_snippet_manager().reload(), self.statusChanged.emit(t('desktop.soloAI.snippetReloaded'))))

            menu.exec(self.snippet_btn.mapToGlobal(pos))

        except Exception as e:
            logger.error(f"[ClaudeTab._on_snippet_context_menu] Error: {e}", exc_info=True)

    def _edit_snippet(self, snippet: dict):
        """スニペット編集ダイアログ (v3.7.0)"""
        import logging
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox
        logger = logging.getLogger(__name__)

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(t('desktop.soloAI.snippetEditDialogTitle', name=snippet.get('name', t('desktop.soloAI.untitled'))))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.soloAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit(snippet.get("name", ""))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.soloAI.categoryLabel2'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit(snippet.get("category", ""))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.soloAI.snippetContentLabel'))
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlainText(snippet.get("content", ""))
            content_input.setMinimumHeight(150)
            layout.addWidget(content_input)

            # ボタン
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                snippet_manager = self._get_snippet_manager()
                snippet_manager.update(
                    snippet.get("id"),
                    name=name_input.text().strip(),
                    content=content_input.toPlainText().strip(),
                    category=cat_input.text().strip()
                )
                self.statusChanged.emit(t('desktop.soloAI.snippetUpdated', name=name_input.text()))
                logger.info(f"[ClaudeTab] Snippet updated: {name_input.text()}")

        except Exception as e:
            logger.error(f"[ClaudeTab._edit_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.soloAI.snippetEditError', error=str(e)))

    def _delete_snippet(self, snippet: dict):
        """スニペット削除 (v5.2.0: ユニペットファイル削除対応)"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            name = snippet.get("name", t('desktop.soloAI.untitled'))
            is_unipet = snippet.get("source") == "unipet"

            # ユニペットの場合は警告を追加
            if is_unipet:
                file_path = snippet.get("file_path", "")
                msg = t('desktop.soloAI.deleteUnipetConfirm', name=name, file_path=file_path)
            else:
                msg = t('desktop.soloAI.deleteSnippetConfirm', name=name)

            reply = QMessageBox.question(
                self, t('desktop.soloAI.confirmTitle'),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                snippet_manager = self._get_snippet_manager()
                # ユニペットの場合はdelete_file=Trueを渡す
                if snippet_manager.delete(snippet.get("id"), delete_file=is_unipet):
                    self.statusChanged.emit(t('desktop.soloAI.snippetDeleted', name=name))
                    logger.info(f"[ClaudeTab] Snippet deleted: {name}")
                else:
                    QMessageBox.warning(self, t('desktop.soloAI.deleteFailed'), t('desktop.soloAI.snippetDeleteError'))

        except Exception as e:
            logger.error(f"[ClaudeTab._delete_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.soloAI.snippetDeleteGenericError', error=str(e)))

    def _send_message(self, message: str):
        """メッセージを送信 (Phase 2.0: Backend経由)"""
        import logging
        logger = logging.getLogger(__name__)

        # v8.5.0: RAG構築中ロック判定
        if hasattr(self, 'main_window') and self.main_window:
            rag_lock = getattr(self.main_window, '_rag_lock', None)
            if rag_lock and rag_lock.is_locked:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, t('desktop.soloAI.ragBuildTitle'),
                    t('desktop.soloAI.ragBuildInProgressMsg')
                )
                return

        try:
            # === 送信前の状態ガード (C: 状態のガード) ===
            # session_id の確保
            session_id = self.session_manager.get_current_session_id()
            if not session_id:
                logger.warning("[ClaudeTab._send_message] session_id is None, generating new session")
                session_id = self.session_manager.create_new_session()

            # phase の確保
            from ..utils.constants import WorkflowPhase
            phase_map = {
                WorkflowPhase.S0_INTAKE: "S0",
                WorkflowPhase.S1_CONTEXT: "S1",
                WorkflowPhase.S2_PLAN: "S2",
                WorkflowPhase.S3_RISK_GATE: "S3",
                WorkflowPhase.S4_IMPLEMENT: "S4",
                WorkflowPhase.S5_VERIFY: "S5",
                WorkflowPhase.S6_REVIEW: "S6",
                WorkflowPhase.S7_RELEASE: "S7",
            }

            current_phase_enum = self.workflow_state.current_phase if self.workflow_state else WorkflowPhase.S0_INTAKE
            phase = phase_map.get(current_phase_enum, "S0")

            # approvals のスナップショット
            approvals_snapshot = {}
            if self.approval_state:
                approvals_snapshot = {
                    "approved_scopes": [str(s) for s in self.approval_state.get_approved_scopes()],
                    "risk_approved": self.workflow_state.get_flag("risk_approved") if self.workflow_state else False
                }

            # selected_backend の確保
            selected_backend = self.backend.get_name() if self.backend else "claude-sonnet-4-5"

            # task_type の初期値（後で分類器で更新される）
            task_type = "UNKNOWN"

            # 状態を INFO レベルでログ出力
            logger.info(
                f"[ClaudeTab._send_message] Sending message - "
                f"session_id={session_id}, phase={phase}, backend={selected_backend}, "
                f"approvals={approvals_snapshot}"
            )

            # プロンプト前処理（テンプレ付与）
            processed_message, template_applied, template_name = self.prompt_preprocessor.process(
                message,
                self.workflow_state
            )

            # v8.1.0: 記憶コンテキスト注入 (soloAI)
            if self._memory_manager:
                try:
                    memory_ctx = self._memory_manager.build_context_for_solo(message)
                    if memory_ctx:
                        processed_message = f"<memory_context>\n{memory_ctx}\n</memory_context>\n\n{processed_message}"
                        logger.info("[ClaudeTab._send_message] Memory context injected for soloAI")
                except Exception as mem_err:
                    logger.warning(f"[ClaudeTab._send_message] Memory context injection failed: {mem_err}")

            # v8.1.0: 送信時のユーザークエリを保持（Memory Risk Gate用）
            self._last_user_query = message

        except Exception as e:
            # 送信前の状態ガードで例外が発生した場合
            logger.error(f"[ClaudeTab._send_message] Exception during state guard: {e}", exc_info=True)

            # crash.log にも記録
            import traceback
            from pathlib import Path
            crash_log_path = Path(__file__).parent.parent.parent / "logs" / "crash.log"
            crash_log_path.parent.mkdir(exist_ok=True)

            try:
                with open(crash_log_path, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[ERROR in _send_message:state_guard] {timestamp}\n")
                    f.write(f"{'='*80}\n")
                    traceback.print_exc(file=f)
                    f.write(f"\n{'='*80}\n\n")
                    f.flush()
            except Exception as log_error:
                logger.error(f"Failed to write to crash.log: {log_error}")

            # UIにエラー表示
            QMessageBox.critical(
                self,
                t('desktop.soloAI.preSubmitErrorTitle'),
                t('desktop.soloAI.preSubmitCheckError', error=f"{type(e).__name__}: {str(e)}")
            )

            self.statusChanged.emit(t('desktop.soloAI.sendPrepError', error=type(e).__name__))
            return

        try:
            # テンプレが付与された場合は通知
            if template_applied:
                self.statusChanged.emit(t('desktop.soloAI.templateApplied', name=template_name))
                self.chat_display.append(
                    f"<div style='color: #ffa500; font-size: 9pt;'>"
                    f"{t('desktop.soloAI.templateAppliedMsg', template=template_name)}"
                    f"</div>"
                )

            # v8.0.0: ユーザーメッセージをバブルスタイルで表示（添付ファイル名付き）
            attachment_html = ""
            if hasattr(self, '_attached_files') and self._attached_files:
                file_chips = ''.join(
                    f'<span style="background:#1a2a3e;border:1px solid #00d4ff;'
                    f'border-radius:4px;padding:2px 8px;margin:2px 4px 2px 0;'
                    f'font-size:11px;color:#00d4ff;display:inline-block;">'
                    f'{os.path.basename(f)}</span>'
                    for f in self._attached_files
                )
                attachment_html = f'<div style="margin-bottom:6px;">{file_chips}</div>'
            self.chat_display.append(
                f"<div style='{USER_MESSAGE_STYLE}'>"
                f"<b style='color:#00d4ff;'>{t('desktop.soloAI.userPrefix')}</b><br>"
                f"{attachment_html}"
                f"{message.replace(chr(10), '<br>')}"
                f"</div>"
            )

            # 履歴保存用に元のメッセージを保持
            self._pending_user_message = message

            # v3.2.0: 認証モードに応じてバックエンド選択
            # v3.9.2: Ollamaモード時は設定タブのモデルを強制使用
            auth_mode = self.auth_mode_combo.currentIndex()  # 0: CLI, 1: API, 2: Ollama

            if auth_mode == 0 and hasattr(self, '_use_cli_mode') and self._use_cli_mode:
                # === CLIモード (Max/Proプラン) ===
                # RoutingExecutorを経由せず、直接CLIバックエンドを使用
                logger.info("[ClaudeTab._send_message] Using CLI mode (Max/Pro plan)")
                self._send_via_cli(processed_message, session_id, phase)

            elif auth_mode == 2 and hasattr(self, '_use_ollama_mode') and self._use_ollama_mode:
                # === v3.9.2: Ollamaモード (ローカル) - 設定タブのモデルを強制使用 ===
                ollama_model = getattr(self, '_ollama_model', 'qwen3-coder')
                ollama_url = getattr(self, '_ollama_url', 'http://localhost:11434')
                logger.info(f"[ClaudeTab._send_message] Using Ollama mode: model={ollama_model}, url={ollama_url}")
                self._send_via_ollama(processed_message, ollama_url, ollama_model)

            else:
                # === APIモード ===
                # Phase 2.x: RoutingExecutorを使用した統合送信
                # ユーザーが明示的にモデルを選択している場合はそれを優先
                # v7.1.0: userDataからmodel_idを取得
                user_forced_backend = None
                model_id = self.model_combo.currentData()
                if model_id and model_id != DEFAULT_CLAUDE_MODEL_ID:
                    user_forced_backend = model_id

                # 承認状態のスナップショットを作成
                approval_snapshot_dict = {}
                if self.approval_state:
                    for scope in self.approval_state.get_approved_scopes():
                        approval_snapshot_dict[str(scope)] = True

                # リクエストを作成
                request = BackendRequest(
                    session_id=session_id,
                    phase=phase,
                    user_text=processed_message,
                    toggles={
                        "mcp": self.mcp_checkbox.isChecked(),
                        "diff": self.diff_checkbox.isChecked(),
                        "context": self.context_checkbox.isChecked(),
                    },
                    context={
                        "phase": phase,
                        "session_id": session_id,
                    }
                )

                # 承認状態をRoutingExecutorに更新
                self.routing_executor.update_approval_state(approval_snapshot_dict)

                # ステータス表示
                self.statusChanged.emit(t('desktop.soloAI.aiGenerating'))

                # RoutingExecutor経由で送信（スレッドで非同期実行）
                self.executor_thread = RoutingExecutorThread(
                    self.routing_executor,
                    request,
                    user_forced_backend,
                    approval_snapshot_dict
                )
                self.executor_thread.responseReady.connect(self._on_executor_response)
                self.executor_thread.start()

        except Exception as e:
            # 送信処理中に例外が発生した場合
            error_msg = f"{type(e).__name__}: {str(e)}"

            logger.error(f"[ClaudeTab._send_message] Exception during send: {error_msg}", exc_info=True)

            # crash.log にも記録
            import traceback
            from pathlib import Path
            crash_log_path = Path(__file__).parent.parent.parent / "logs" / "crash.log"
            crash_log_path.parent.mkdir(exist_ok=True)

            try:
                with open(crash_log_path, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[ERROR in _send_message:send] {timestamp}\n")
                    f.write(f"{'='*80}\n")
                    traceback.print_exc(file=f)
                    f.write(f"\n{'='*80}\n\n")
                    f.flush()
            except Exception as log_error:
                logger.error(f"Failed to write to crash.log: {log_error}")

            # UIにエラー表示
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.soloAI.sendErrorHtml')}</b><br>"
                f"{error_msg}<br><br>"
                f"{t('desktop.soloAI.crashLogDetail')}"
                f"</div>"
            )

            self.statusChanged.emit(t('desktop.soloAI.sendError', error=type(e).__name__))

    def _send_via_cli(self, prompt: str, session_id: str, phase: str):
        """
        v3.2.0: CLI経由で送信（Max/Proプラン）
        v3.9.2: E/F フォールバック対応

        Args:
            prompt: 送信するプロンプト
            session_id: セッションID
            phase: 現在の工程
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self._cli_backend or not self._cli_backend.is_available():
            error_msg = t('desktop.soloAI.cliUnavailableInstructions')
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.soloAI.cliUnavailableHtml')}</b><br>"
                f"{error_msg}"
                f"</div>"
            )
            self.statusChanged.emit(t('desktop.soloAI.cliUnavailable'))
            logger.error(f"[ClaudeTab._send_via_cli] CLI not available: {self._cli_backend.get_availability_message() if self._cli_backend else 'Backend is None'}")
            return

        # v7.1.0: モデル選択とフォールバック準備
        model_text = self.model_combo.currentText()
        selected_model = self.model_combo.currentData() or model_text
        self._cli_selected_model = model_text  # フォールバック用に保存
        self._cli_prompt = prompt  # フォールバック用に保存
        self._cli_session_id = session_id
        self._cli_phase = phase

        # v3.9.5: 思考モードの設定
        # Note: 全Claudeモデルでextended thinkingをサポート
        # エラー発生時は自動的にOFFにフォールバック
        thinking_text = self.thinking_combo.currentText()
        thinking_level = "none"

        if thinking_text == "Standard":
            thinking_level = "light"
        elif thinking_text == "Deep":
            thinking_level = "deep"

        # 思考モード有効時の情報ログ
        if thinking_level != "none":
            logger.info(f"[ClaudeTab._send_via_cli] Thinking mode: {thinking_text} (level={thinking_level})")

        # 作業ディレクトリを取得（プロジェクトディレクトリ）
        import os
        working_dir = os.getcwd()

        # ステータス表示
        self.statusChanged.emit(t('desktop.soloAI.cliGenerating'))
        # v8.0.0: SoloAIStatusBar更新
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        # 認証モード情報をチャットに表示
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"{t('desktop.soloAI.cliModeInfo', thinking=thinking_text)}"
            f"</div>"
        )

        # v3.5.0: 権限スキップ設定を取得
        skip_permissions = self.permission_skip_checkbox.isChecked()

        # v7.1.0: selected_model は currentData() で取得済み
        logger.info(f"[ClaudeTab._send_via_cli] Starting CLI request: model={selected_model}, thinking={thinking_level}, working_dir={working_dir}, skip_permissions={skip_permissions}")

        # CLIバックエンドへの参照を取得 (v3.5.0: 権限スキップ設定, v3.9.4: モデル選択を渡す)
        self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions, model=selected_model)

        # CLIWorkerThreadで非同期実行
        self._cli_worker = CLIWorkerThread(
            backend=self._cli_backend,
            prompt=prompt,
            model=selected_model,  # v3.9.4: モデルを渡す
            working_dir=working_dir,
            thinking_level=thinking_level
        )
        self._cli_worker.chunkReceived.connect(self._on_cli_chunk)
        self._cli_worker.completed.connect(self._on_cli_response)
        self._cli_worker.errorOccurred.connect(self._on_cli_error)
        self._cli_worker.start()

    def _on_cli_chunk(self, chunk: str):
        """CLIストリーミングチャンク受信時"""
        # ストリーミング表示（必要に応じて実装）
        pass

    def _on_cli_response(self, response: BackendResponse):
        """
        v3.2.0: CLI Backend からの応答を処理

        Args:
            response: CLIバックエンドからのレスポンス
        """
        import logging
        logger = logging.getLogger(__name__)

        if response.success:
            # 成功時: 応答を表示（Markdown→HTMLレンダリング）
            rendered = markdown_to_html(response.response_text)
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:#00ff88;'>Claude CLI (Max/Pro):</b><br>"
                f"{rendered}"
                f"</div>"
            )

            logger.info(
                f"[ClaudeTab._on_cli_response] CLI response: "
                f"duration={response.duration_ms:.2f}ms, tokens={response.tokens_used}"
            )

            # コスト表示（Max/Proプランは基本無料、Extra Usage超過時のみ課金）
            self.statusChanged.emit(
                t('desktop.soloAI.cliResponseComplete', duration=f"{response.duration_ms:.0f}")
            )

            # v3.2.0: チャット履歴を保存
            if self._pending_user_message:
                try:
                    entry = self.chat_history_manager.add_entry(
                        prompt=self._pending_user_message,
                        response=response.response_text,
                        ai_source="Claude-CLI",  # CLIモードを明示
                        metadata={
                            "backend": "claude-cli",
                            "duration_ms": response.duration_ms,
                            "tokens": response.tokens_used,
                            "cost_est": 0.0,  # Max/Proプランは基本無料
                            "source_tab": "ClaudeTab",
                            "auth_mode": t('desktop.soloAI.authModeCli')
                        }
                    )
                    logger.info(f"[ClaudeTab._on_cli_response] Chat history saved: entry_id={entry.id}")
                    self._pending_user_message = None
                except Exception as hist_error:
                    logger.error(f"[ClaudeTab._on_cli_response] Failed to save chat history: {hist_error}", exc_info=True)

            # v8.1.0: Memory Risk Gate (soloAI CLI応答後)
            if self._memory_manager and hasattr(self, '_last_user_query'):
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    session_id = self.session_manager.get_current_session_id() or "solo"
                    loop.run_until_complete(
                        self._memory_manager.evaluate_and_store(
                            session_id, response.response_text, self._last_user_query
                        )
                    )
                    loop.close()
                    logger.info("[ClaudeTab._on_cli_response] Memory Risk Gate completed (soloAI-CLI)")
                    # v8.3.1: RAPTOR非同期トリガー (QThread)
                    self._raptor_worker = RaptorWorker(
                        self._memory_manager, session_id,
                        [{"role": "user", "content": self._last_user_query},
                         {"role": "assistant", "content": response.response_text}]
                    )
                    self._raptor_worker.start()

                    # v8.4.0: Mid-Session Summary トリガー
                    self._session_message_count += 1
                    self._session_messages_for_summary.append(
                        {"role": "user", "content": self._last_user_query})
                    self._session_messages_for_summary.append(
                        {"role": "assistant", "content": response.response_text})
                    if (self._session_message_count % self._mid_session_trigger == 0
                            and self._session_message_count > 0):
                        self._mid_session_worker = RaptorWorker(
                            self._memory_manager, session_id,
                            list(self._session_messages_for_summary),
                            mode="mid_session"
                        )
                        self._mid_session_worker.start()
                        logger.info(
                            f"[ClaudeTab] Mid-session summary triggered at "
                            f"message #{self._session_message_count}"
                        )
                except Exception as mem_err:
                    logger.warning(f"[ClaudeTab._on_cli_response] Memory Risk Gate failed: {mem_err}")

            # v8.0.0: SoloAIStatusBar - 完了
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("completed")

        else:
            # 失敗時: エラーメッセージを表示
            error_type = response.error_type or "CLIError"
            error_text = response.response_text.lower()
            # v8.0.0: SoloAIStatusBar - エラー
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("error")

            # v3.9.2 E: Haiku使用時のモデル不正/権限不足エラーを検出してフォールバック
            haiku_errors = ["model not found", "permission denied", "unauthorized", "not available", "unsupported model"]
            is_haiku_error = any(err in error_text for err in haiku_errors)

            if is_haiku_error and hasattr(self, '_cli_selected_model') and "Haiku" in self._cli_selected_model:
                logger.warning("[ClaudeTab._on_cli_response] Haiku error detected, falling back to Sonnet")

                # Sonnetにフォールバック
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentIndex(0)  # Sonnet (推奨)
                self.model_combo.blockSignals(False)

                self.chat_display.append(
                    f"<div style='color: #ffa500; margin-top: 10px;'>"
                    f"<b>{t('desktop.soloAI.haikuUnavailableHtml')}</b><br>"
                    f"{t('desktop.soloAI.modelNotAvailableMsg').replace(chr(10), '<br>')}"
                    f"</div>"
                )

                self.statusChanged.emit(t('desktop.soloAI.fallbackSonnet'))

                # 再送信
                if hasattr(self, '_cli_prompt') and self._cli_prompt:
                    self._send_via_cli(self._cli_prompt, self._cli_session_id, self._cli_phase)
                return

            # v3.9.5: thinkingパラメータエラーを検出してフォールバック（パターン拡張）
            thinking_errors = [
                "thinking", "extended thinking", "not supported", "invalid parameter",
                "--think", "think hard", "ultrathink", "unsupported flag",
                "unknown option", "unrecognized option", "invalid option"
            ]
            is_thinking_error = any(err in error_text for err in thinking_errors)

            if is_thinking_error and self.thinking_combo.currentIndex() != 0:
                logger.warning(f"[ClaudeTab._on_cli_response] Thinking error detected: {error_text[:100]}")

                # 思考モードをOFFに戻す
                self.thinking_combo.blockSignals(True)
                self.thinking_combo.setCurrentIndex(0)  # OFF
                self.thinking_combo.blockSignals(False)

                self.chat_display.append(
                    f"<div style='color: #ffa500; margin-top: 10px;'>"
                    f"<b>{t('desktop.soloAI.thinkingErrorHtml')}</b><br>"
                    f"{t('desktop.soloAI.thinkingErrorMsg').replace(chr(10), '<br>')}"
                    f"</div>"
                )

                self.statusChanged.emit(t('desktop.soloAI.retryThinkingOff'))

                # 再送信
                if hasattr(self, '_cli_prompt') and self._cli_prompt:
                    self._send_via_cli(self._cli_prompt, self._cli_session_id, self._cli_phase)
                return

            # フォールバック対象外のエラー
            self._pending_user_message = None

            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.soloAI.cliErrorHtml', error_type=error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"[ClaudeTab._on_cli_response] CLI error: type={error_type}, "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(t('desktop.soloAI.cliError', error=error_type))

    def _on_cli_error(self, error_msg: str):
        """CLI実行エラー発生時"""
        import logging
        logger = logging.getLogger(__name__)

        logger.error(f"[ClaudeTab._on_cli_error] {error_msg}")

        self.chat_display.append(
            f"<div style='color: #ef4444; margin-top: 10px;'>"
            f"<b>{t('desktop.soloAI.cliExecErrorHtml')}</b><br>"
            f"{error_msg}"
            f"</div>"
        )

        self.statusChanged.emit(t('desktop.soloAI.cliError', error=error_msg[:50]))

    # ========================================
    # v3.9.2: Ollama直接送信 (C-1: 送信先固定化)
    # ========================================

    def _send_via_ollama(self, prompt: str, ollama_url: str, ollama_model: str):
        """
        v3.9.2: Ollama経由で直接送信（設定タブのモデルを強制使用）
        v3.9.3: MCPツール統合

        Args:
            prompt: 送信するプロンプト
            ollama_url: Ollama API URL
            ollama_model: 使用するモデル名
        """
        import logging
        import os
        logger = logging.getLogger(__name__)

        # v3.9.3: MCP設定を取得
        mcp_enabled = self.mcp_checkbox.isChecked() if hasattr(self, 'mcp_checkbox') else False
        mcp_settings = self._get_mcp_settings()

        # ステータス表示（実効モデルを表示）
        mcp_status = " + MCP" if mcp_enabled else ""
        self.statusChanged.emit(t('desktop.soloAI.ollamaGenerating', model=ollama_model, mcp=mcp_status))

        # 認証モード情報をチャットに表示
        mcp_tools = []
        if mcp_enabled:
            if mcp_settings.get("filesystem"):
                mcp_tools.append(t('desktop.soloAI.fileOps'))
            if mcp_settings.get("brave-search"):
                mcp_tools.append(t('desktop.soloAI.webSearch'))

        tools_text = t('desktop.soloAI.toolsPrefix', tools=', '.join(mcp_tools)) if mcp_tools else ""
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"[Ollama Mode] Local: {ollama_model} ({ollama_url}){tools_text}"
            f"</div>"
        )

        logger.info(f"[ClaudeTab._send_via_ollama] Sending to Ollama: model={ollama_model}, url={ollama_url}, mcp={mcp_enabled}")

        # 作業ディレクトリを取得
        working_dir = os.getcwd()

        # Ollamaワーカースレッドで非同期実行 (v3.9.3: MCP対応)
        self._ollama_worker = OllamaWorkerThread(
            url=ollama_url,
            model=ollama_model,
            prompt=prompt,
            mcp_enabled=mcp_enabled,
            mcp_settings=mcp_settings,
            working_dir=working_dir
        )
        self._ollama_worker.completed.connect(self._on_ollama_response)
        self._ollama_worker.errorOccurred.connect(self._on_ollama_error)
        self._ollama_worker.toolExecuted.connect(self._on_ollama_tool_executed)
        self._ollama_worker.start()

    def _get_mcp_settings(self) -> dict:
        """MCP設定を取得 (v8.1.0: 一般設定タブから読み込み)"""
        settings = {
            "filesystem": True,
            "git": True,
            "brave-search": True,
        }
        # v8.1.0: 一般設定タブのMCP設定を参照
        try:
            import json
            from pathlib import Path
            config_path = Path(__file__).parent.parent.parent / "config" / "general_settings.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                mcp = config.get("mcp_servers", {})
                for key in settings:
                    if key in mcp:
                        settings[key] = mcp[key]
        except Exception:
            pass
        return settings

    def _on_ollama_tool_executed(self, tool_name: str, success: bool):
        """Ollamaツール実行完了時 (v3.9.3)"""
        import logging
        logger = logging.getLogger(__name__)

        status = "✅" if success else "❌"
        logger.info(f"[ClaudeTab._on_ollama_tool_executed] {tool_name}: {status}")

        # ステータス更新（簡潔に）
        self.statusChanged.emit(t('desktop.soloAI.toolExecution', tool=tool_name, status=status))

    def _on_ollama_response(self, response_text: str, duration_ms: float):
        """Ollama応答受信時 (v3.9.2)"""
        import logging
        logger = logging.getLogger(__name__)

        ollama_model = getattr(self, '_ollama_model', 'ollama')

        # 応答を表示（Markdown→HTMLレンダリング + バブルスタイル）
        rendered = markdown_to_html(response_text)
        self.chat_display.append(
            f"<div style='{AI_MESSAGE_STYLE}'>"
            f"<b style='color:#00ff88;'>{ollama_model} (Ollama):</b><br>"
            f"{rendered}"
            f"</div>"
        )

        logger.info(f"[ClaudeTab._on_ollama_response] Ollama response: duration={duration_ms:.2f}ms")

        self.statusChanged.emit(t('desktop.soloAI.ollamaComplete', duration=f"{duration_ms:.0f}", model=ollama_model))

        # チャット履歴を保存
        if self._pending_user_message:
            try:
                entry = self.chat_history_manager.add_entry(
                    prompt=self._pending_user_message,
                    response=response_text,
                    ai_source=f"Ollama-{ollama_model}",
                    metadata={
                        "backend": "ollama",
                        "model": ollama_model,
                        "duration_ms": duration_ms,
                        "tokens": 0,
                        "cost_est": 0.0,
                        "source_tab": "ClaudeTab",
                        "auth_mode": t('desktop.soloAI.authModeOllama')
                    }
                )
                logger.info(f"[ClaudeTab._on_ollama_response] Chat history saved: entry_id={entry.id}")
                self._pending_user_message = None
            except Exception as hist_error:
                logger.error(f"[ClaudeTab._on_ollama_response] Failed to save chat history: {hist_error}", exc_info=True)

    def _on_ollama_error(self, error_msg: str):
        """Ollamaエラー発生時 (v3.9.2)"""
        import logging
        logger = logging.getLogger(__name__)

        self._pending_user_message = None
        logger.error(f"[ClaudeTab._on_ollama_error] {error_msg}")

        self.chat_display.append(
            f"<div style='color: #ef4444; margin-top: 10px;'>"
            f"<b>{t('desktop.soloAI.ollamaErrorHtml')}</b><br>"
            f"{error_msg}"
            f"</div>"
        )

        self.statusChanged.emit(t('desktop.soloAI.ollamaError', error=error_msg[:50]))

    def _update_backend_from_ui(self):
        """UIのモデル選択からBackendを更新 (v7.1.0: CLAUDE_MODELS対応)"""
        # v2.5.0: CLIモードの場合はCLI Backendを使用
        if hasattr(self, '_use_cli_mode') and self._use_cli_mode:
            self.backend = get_claude_cli_backend()
            return

        # v7.1.0: userDataからmodel_idを取得
        model_id = self.model_combo.currentData() or DEFAULT_CLAUDE_MODEL_ID
        if "opus" in model_id:
            self.backend = ClaudeBackend(model="opus-4-5")
        elif "sonnet" in model_id:
            self.backend = ClaudeBackend(model="sonnet-4-5")
        else:
            self.backend = ClaudeBackend(model="sonnet-4-5")

    def _update_backend_from_name(self, backend_name: str):
        """Backend名からBackendインスタンスを更新 (Phase 2.2, v2.5.0: CLI/API対応)"""
        from ..backends import GeminiBackend, LocalBackend

        # v2.5.0: CLIモードの場合はCLI Backendを使用
        if hasattr(self, '_use_cli_mode') and self._use_cli_mode and "claude" in backend_name:
            self.backend = get_claude_cli_backend()
            return

        if "claude-opus" in backend_name:
            self.backend = ClaudeBackend(model="opus-4-5")
        elif "claude-haiku" in backend_name:
            self.backend = ClaudeBackend(model="haiku-4-5")
        elif "claude-sonnet" in backend_name:
            self.backend = ClaudeBackend(model="sonnet-4-5")
        elif "gemini" in backend_name:
            self.backend = GeminiBackend(model="3-pro")
        elif "local" in backend_name:
            self.backend = LocalBackend()
        else:
            # デフォルトはSonnet
            self.backend = ClaudeBackend(model="sonnet-4-5")

    def _on_backend_response(self, response: BackendResponse):
        """Backend からの応答を処理 (Phase 2.3/2.4: メトリクス記録付き)"""
        import logging
        logger = logging.getLogger(__name__)

        # Phase 2.3: メトリクス記録
        session_id = self.session_manager.get_current_session_id()
        task_type = response.metadata.get("task_type", "UNKNOWN")
        phase = response.metadata.get("phase", "S0")
        selected_backend = response.metadata.get("backend", self.backend.get_name())

        self.metrics_recorder.record_call(
            session_id=session_id,
            backend=selected_backend,
            task_type=task_type,
            phase=phase,
            duration_ms=response.duration_ms,
            tokens_est=response.tokens_used,
            cost_est=response.cost_est,
            success=response.success,
            error_type=response.error_type,
            metadata=response.metadata,
        )

        if response.success:
            # 成功時: 応答を表示（Markdown→HTMLレンダリング）
            rendered = markdown_to_html(response.response_text)
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:#00ff88;'>{self.backend.get_name()}:</b><br>"
                f"{rendered}"
                f"</div>"
            )

            # メタ情報をログに記録
            logger.info(
                f"Backend response: duration={response.duration_ms:.2f}ms, "
                f"tokens={response.tokens_used}, cost=${response.cost_est:.6f}"
            )

            self.statusChanged.emit(
                t('desktop.soloAI.responseCompleteStatus', duration=f"{response.duration_ms:.0f}", cost=f"{response.cost_est:.6f}")
            )

        else:
            # 失敗時: エラーメッセージを表示
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.soloAI.errorHtml', error_type=response.error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"Backend error: type={response.error_type}, "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(t('desktop.soloAI.errorStatus', error=response.error_type))

    def _on_executor_response(self, response: BackendResponse, execution_info: dict):
        """RoutingExecutor からの応答を処理 (Phase 2.x: CP1-CP10統合)"""
        import logging
        logger = logging.getLogger(__name__)

        # 実行情報を取得
        task_type = execution_info.get("task_type", "UNKNOWN")
        selected_backend = execution_info.get("selected_backend", "unknown")
        reason_codes = execution_info.get("reason_codes", [])
        fallback_chain = execution_info.get("fallback_chain", [])
        preset_name = execution_info.get("preset_name")
        prompt_pack = execution_info.get("prompt_pack")
        policy_blocked = execution_info.get("policy_blocked", False)
        budget_status = execution_info.get("budget_status")

        # タスク分類とBackend選択をUI通知
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"[Task: {task_type}] → Backend: {selected_backend}"
            f"{' (Preset: ' + preset_name + ')' if preset_name else ''}"
            f"{' [PromptPack: ' + prompt_pack + ']' if prompt_pack else ''}"
            f"</div>"
        )

        # フォールバックがあった場合
        if len(fallback_chain) > 1:
            self.chat_display.append(
                f"<div style='color: #f59e0b; font-size: 9pt;'>"
                f"[Fallback] {' → '.join(fallback_chain)}"
                f"</div>"
            )

        # v1.0.1: ai_sourceを動的に決定（バックエンド名に基づく）
        ai_source = "Claude"  # デフォルト
        if selected_backend:
            backend_lower = selected_backend.lower()
            if "gemini" in backend_lower:
                ai_source = "Gemini"
            elif "ollama" in backend_lower or "local" in backend_lower:
                ai_source = "Ollama"
            elif "trinity" in backend_lower:
                ai_source = "Trinity"
            # claude系はデフォルトの "Claude" を使用

        if response.success:
            # 成功時: 応答を表示（Markdown→HTMLレンダリング）
            rendered = markdown_to_html(response.response_text)
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:#00ff88;'>{selected_backend}:</b><br>"
                f"{rendered}"
                f"</div>"
            )

            # メタ情報をログに記録
            logger.info(
                f"[ClaudeTab] Response: backend={selected_backend}, "
                f"duration={response.duration_ms:.2f}ms, "
                f"tokens={response.tokens_used}, cost=${response.cost_est:.6f}"
            )

            self.statusChanged.emit(
                t('desktop.soloAI.responseCompleteStatus', duration=f"{response.duration_ms:.0f}", cost=f"{response.cost_est:.6f}")
            )

            # v1.0.1: チャット履歴を保存（強化版）
            # _pending_user_messageの有無をログに記録
            logger.info(f"[ClaudeTab] Attempting to save history: pending_msg={bool(self._pending_user_message)}, ai_source={ai_source}")

            if self._pending_user_message:
                try:
                    entry = self.chat_history_manager.add_entry(
                        prompt=self._pending_user_message,
                        response=response.response_text,
                        ai_source=ai_source,
                        metadata={
                            "backend": selected_backend,
                            "task_type": task_type,
                            "duration_ms": response.duration_ms,
                            "tokens": response.tokens_used,
                            "cost_est": response.cost_est,
                            "source_tab": "ClaudeTab"
                        }
                    )
                    logger.info(f"[ClaudeTab] Chat history saved successfully: entry_id={entry.id}, ai_source={ai_source}")
                    self._pending_user_message = None
                except Exception as hist_error:
                    logger.error(f"[ClaudeTab] Failed to save chat history: {hist_error}", exc_info=True)
            else:
                logger.warning("[ClaudeTab] No pending user message to save")

            # v8.1.0: Memory Risk Gate (soloAI API応答後)
            if self._memory_manager and hasattr(self, '_last_user_query'):
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    session_id = self.session_manager.get_current_session_id() or "solo"
                    loop.run_until_complete(
                        self._memory_manager.evaluate_and_store(
                            session_id, response.response_text, self._last_user_query
                        )
                    )
                    loop.close()
                    logger.info("[ClaudeTab._on_executor_response] Memory Risk Gate completed (soloAI-API)")
                    # v8.3.1: RAPTOR非同期トリガー (QThread)
                    self._raptor_worker = RaptorWorker(
                        self._memory_manager, session_id,
                        [{"role": "user", "content": self._last_user_query},
                         {"role": "assistant", "content": response.response_text}]
                    )
                    self._raptor_worker.start()
                except Exception as mem_err:
                    logger.warning(f"[ClaudeTab._on_executor_response] Memory Risk Gate failed: {mem_err}")

        else:
            error_type = response.error_type or "UnknownError"
            self._pending_user_message = None  # エラー時もクリア

            if policy_blocked:
                # ポリシーブロック
                self.chat_display.append(
                    f"<div style='color: #f59e0b; margin-top: 10px;'>"
                    f"<b>{t('desktop.soloAI.policyBlockHtml')}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}<br><br>"
                    f"{t('desktop.soloAI.getApprovalRetry')}"
                    f"</div>"
                )
                self.statusChanged.emit(t('desktop.soloAI.policyBlock'))

            elif error_type == "BudgetExceeded":
                # 予算超過
                self.chat_display.append(
                    f"<div style='color: #ef4444; margin-top: 10px;'>"
                    f"<b>{t('desktop.soloAI.budgetExceededHtml')}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}<br><br>"
                    f"{t('desktop.soloAI.checkBudgetMsg')}"
                    f"</div>"
                )
                self.statusChanged.emit(t('desktop.soloAI.budgetExceeded'))

            else:
                # その他のエラー
                self.chat_display.append(
                    f"<div style='color: #ef4444; margin-top: 10px;'>"
                    f"<b>{t('desktop.soloAI.errorHtml', error_type=error_type)}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}"
                    f"</div>"
                )

                logger.error(
                    f"[ClaudeTab] Error: type={error_type}, "
                    f"duration={response.duration_ms:.2f}ms"
                )

                self.statusChanged.emit(t('desktop.soloAI.errorStatus', error=error_type))

    def show_diff(self, file_path: str, old_content: str, new_content: str):
        """
        Diff Viewを表示

        Args:
            file_path: ファイルパス
            old_content: 変更前
            new_content: 変更後
        """
        self.diffProposed.emit(file_path, old_content, new_content)
        # TODO: Diff View UIの実装

    # ========================================
    # 工程状態機械 関連メソッド
    # ========================================

    def _update_workflow_ui(self):
        """工程UIを更新"""
        from ..utils.constants import WorkflowPhase

        phase_info = self.workflow_state.get_current_phase_info()

        # 工程名と説明を更新
        self.phase_label.setText(phase_info["name"])
        self.phase_desc_label.setText(phase_info["description"])

        # 進捗バーを更新
        progress = self.workflow_state.get_progress_percentage()
        self.progress_bar.setValue(progress)

        # Prev/Nextボタンの有効/無効を更新
        can_prev, _ = self.workflow_state.can_transition_prev()
        self.prev_btn.setEnabled(can_prev)

        can_next, next_msg = self.workflow_state.can_transition_next()
        self.next_btn.setEnabled(can_next)
        if not can_next:
            self.next_btn.setToolTip(t('desktop.soloAI.nextDisabledTooltip', msg=next_msg))
        else:
            self.next_btn.setToolTip(t('desktop.soloAI.nextEnabledTooltip'))

        # S3承認UI の表示/非表示（Phase 1.2）
        if self.workflow_state.current_phase == WorkflowPhase.S3_RISK_GATE:
            self.risk_approval_btn.setVisible(True)
            self.approval_status_label.setVisible(True)
            self._update_approval_status_label()
        else:
            self.risk_approval_btn.setVisible(False)
            self.approval_status_label.setVisible(False)
            self.approval_panel.setVisible(False)

    def _on_prev_phase(self):
        """前の工程に戻る"""
        from ..data.workflow_state import WorkflowTransitionError

        old_phase = self.workflow_state.current_phase
        try:
            self.workflow_state.transition_prev(reason="User clicked Prev button")
            self.session_manager.save_workflow_state()

            # ログに記録
            self.workflow_logger.log_transition(
                old_phase,
                self.workflow_state.current_phase,
                "User clicked Prev button"
            )

            # 履歴に記録
            self.history_manager.phase_entered(
                self.workflow_state.current_phase,
                from_phase=old_phase
            )

            self._update_workflow_ui()

            # メインウィンドウに通知（他のタブの工程バーを更新）
            if self.main_window:
                self.main_window.notify_workflow_state_changed()

            self.statusChanged.emit(t('desktop.soloAI.phaseBack', phase=self.workflow_state.get_current_phase_info()['name']))
        except WorkflowTransitionError as e:
            self.workflow_logger.log_blocked(old_phase, str(e))
            self.history_manager.phase_blocked(old_phase, str(e))
            QMessageBox.warning(self, t('desktop.soloAI.phaseTransitionError'), str(e))

    def _on_next_phase(self):
        """次の工程に進む"""
        from ..data.workflow_state import WorkflowTransitionError

        old_phase = self.workflow_state.current_phase
        try:
            self.workflow_state.transition_next(reason="User clicked Next button")
            self.session_manager.save_workflow_state()

            # ログに記録
            self.workflow_logger.log_transition(
                old_phase,
                self.workflow_state.current_phase,
                "User clicked Next button"
            )

            # 履歴に記録
            self.history_manager.phase_entered(
                self.workflow_state.current_phase,
                from_phase=old_phase
            )

            self._update_workflow_ui()

            # メインウィンドウに通知（他のタブの工程バーを更新）
            if self.main_window:
                self.main_window.notify_workflow_state_changed()

            self.statusChanged.emit(t('desktop.soloAI.phaseForward', phase=self.workflow_state.get_current_phase_info()['name']))
        except WorkflowTransitionError as e:
            self.workflow_logger.log_blocked(old_phase, str(e))
            self.history_manager.phase_blocked(old_phase, str(e))
            QMessageBox.warning(self, t('desktop.soloAI.phaseTransitionError'), str(e))

    def _on_reset_workflow(self):
        """工程をリセット"""
        reply = QMessageBox.question(
            self,
            t('desktop.soloAI.workflowResetTitle'),
            t('desktop.soloAI.resetWorkflowConfirm'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            old_phase = self.workflow_state.current_phase
            self.session_manager.reset_workflow_state()
            self.workflow_state = self.session_manager.get_workflow_state()

            # ログに記録
            self.workflow_logger.log_reset(old_phase)

            # 履歴に記録
            self.history_manager.workflow_reset(old_phase)

            self._update_workflow_ui()

            # メインウィンドウに通知
            if self.main_window:
                self.main_window.notify_workflow_state_changed()

            self.statusChanged.emit(t('desktop.soloAI.phaseResetDone'))

    def _on_risk_approval_changed(self, state):
        """S3承認チェックボックスの状態変更"""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.workflow_state.set_flag(
            "risk_approved",
            is_checked,
            reason=f"User {'approved' if is_checked else 'revoked'} risk gate"
        )
        self.session_manager.save_workflow_state()

        # ログに記録
        self.workflow_logger.log_approval(
            self.workflow_state.current_phase,
            is_checked,
            f"User {'approved' if is_checked else 'revoked'} risk gate"
        )

        # 履歴に記録
        self.history_manager.approval_granted(
            self.workflow_state.current_phase,
            is_checked
        )

        self._update_workflow_ui()

        # メインウィンドウに通知
        if self.main_window:
            self.main_window.notify_workflow_state_changed()

        if is_checked:
            self.statusChanged.emit(t('desktop.soloAI.dangerApproved'))
        else:
            self.statusChanged.emit(t('desktop.soloAI.approvalCancelled'))

    def _check_send_guard(self) -> tuple[bool, str]:
        """
        送信ガード: 現在の工程で送信が許可されているかチェック

        Returns:
            (許可されているか, メッセージ)
        """
        from ..utils.constants import WorkflowPhase

        current = self.workflow_state.current_phase

        # S0〜S3: 計画作成や読み込みのための送信は許可
        if current in [WorkflowPhase.S0_INTAKE, WorkflowPhase.S1_CONTEXT,
                       WorkflowPhase.S2_PLAN, WorkflowPhase.S3_RISK_GATE]:
            return True, ""

        # S4: 実装工程なので送信OK
        if current == WorkflowPhase.S4_IMPLEMENT:
            # ただし、S3の承認が必要
            if not self.workflow_state.get_flag("risk_approved"):
                return False, t('desktop.soloAI.s3ApprovalRequired')
            return True, ""

        # S5〜S7: 実装は完了しているので、基本的にブロック
        # （ただし、テンプレ付与などで対応可能）
        if current in [WorkflowPhase.S5_VERIFY, WorkflowPhase.S6_REVIEW, WorkflowPhase.S7_RELEASE]:
            return True, t('desktop.soloAI.verificationPhaseMsg')

        return True, ""

    # ===================
    # Phase 1.2: 承認関連メソッド
    # ===================

    def _on_toggle_approval_panel(self):
        """承認パネルの表示/非表示を切り替え"""
        self.approval_panel.setVisible(not self.approval_panel.isVisible())

        if self.approval_panel.isVisible():
            self.risk_approval_btn.setText(t('desktop.soloAI.riskApprovalClose'))
        else:
            self.risk_approval_btn.setText(t('desktop.soloAI.riskApprovalOpen'))

        self._update_approval_status_label()

    def _on_approval_scope_changed(self, scope, state):
        """承認スコープのチェック状態が変更された時の処理"""
        from ..security.risk_gate import ApprovalScope, RiskGate
        from ..utils.constants import WorkflowPhase

        is_checked = (state == Qt.CheckState.Checked.value)

        if is_checked:
            # 承認
            self.approval_state.approve_scope(scope)
            self.approvals_store.log_approval_event(
                event_type="approve",
                scopes=[scope],
                session_id="",
                phase=self.workflow_state.current_phase,
                reason="User approved via UI",
                user_action="user_approved"
            )
        else:
            # 取り消し
            self.approval_state.revoke_scope(scope)
            self.approvals_store.log_approval_event(
                event_type="revoke",
                scopes=[scope],
                session_id="",
                phase=self.workflow_state.current_phase,
                reason="User revoked via UI",
                user_action="user_revoked"
            )

        # 保存
        self.approvals_store.save_approval_state(
            self.approval_state,
            session_id="",
            reason="Scope changed via UI"
        )

        # RiskGateインスタンスを更新
        self.risk_gate = RiskGate(self.approval_state)

        # ステータスラベル更新
        self._update_approval_status_label()

        # WorkflowStateのrisk_approvedフラグも更新
        # （FS_WRITEが承認されていれば基本的にOK）
        if self.approval_state.is_approved(ApprovalScope.FS_WRITE):
            self.workflow_state.set_flag("risk_approved", True)
        else:
            self.workflow_state.set_flag("risk_approved", False)

        # 変更を通知
        if self.main_window:
            self.main_window.notify_workflow_state_changed()

    def _approve_all_scopes(self):
        """全てのスコープを承認"""
        from ..security.risk_gate import ApprovalScope, RiskGate

        for scope in ApprovalScope.all_scopes():
            self.approval_state.approve_scope(scope)
            checkbox = self.approval_checkboxes.get(scope)
            if checkbox:
                checkbox.setChecked(True)

        # 保存
        self.approvals_store.approve_scopes(
            ApprovalScope.all_scopes(),
            session_id="",
            phase=self.workflow_state.current_phase,
            reason="User approved all scopes via UI"
        )

        # RiskGateインスタンスを更新
        self.risk_gate = RiskGate(self.approval_state)

        # ステータスラベル更新
        self._update_approval_status_label()

        # WorkflowStateのrisk_approvedフラグも更新
        self.workflow_state.set_flag("risk_approved", True)

        # 変更を通知
        if self.main_window:
            self.main_window.notify_workflow_state_changed()

        self.statusChanged.emit(t('desktop.soloAI.allScopesApproved'))

    def _revoke_all_scopes(self):
        """全てのスコープの承認を取り消し"""
        from ..security.risk_gate import ApprovalScope, RiskGate

        for scope in ApprovalScope.all_scopes():
            self.approval_state.revoke_scope(scope)
            checkbox = self.approval_checkboxes.get(scope)
            if checkbox:
                checkbox.setChecked(False)

        # 保存
        self.approvals_store.revoke_scopes(
            ApprovalScope.all_scopes(),
            session_id="",
            phase=self.workflow_state.current_phase,
            reason="User revoked all scopes via UI"
        )

        # RiskGateインスタンスを更新
        self.risk_gate = RiskGate(self.approval_state)

        # ステータスラベル更新
        self._update_approval_status_label()

        # WorkflowStateのrisk_approvedフラグも更新
        self.workflow_state.set_flag("risk_approved", False)

        # 変更を通知
        if self.main_window:
            self.main_window.notify_workflow_state_changed()

        self.statusChanged.emit(t('desktop.soloAI.allScopesRejected'))

    def _update_approval_status_label(self):
        """承認状態ラベルを更新"""
        approved_scopes = self.approval_state.get_approved_scopes()

        if len(approved_scopes) == 0:
            self.approval_status_label.setText(t('desktop.soloAI.scopeUnapproved'))
            self.approval_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.approval_status_label.setText(t('desktop.soloAI.scopeApprovedCount', count=len(approved_scopes)))
            self.approval_status_label.setStyleSheet("color: #22c55e; font-weight: bold;")

    # ===================
    # v3.4.0: 会話継続機能
    # ===================

    def _send_continue_message(self, message: str):
        """
        v3.4.0: 会話継続メッセージを送信

        Claudeの確認質問や続行確認に対して --continue フラグを使用して
        文脈を維持したまま応答します。

        Args:
            message: 継続メッセージ（例: "はい", "続行してください"）
        """
        import logging
        logger = logging.getLogger(__name__)

        if not message.strip():
            return

        # CLIモードのみサポート
        auth_mode = self.auth_mode_combo.currentIndex()  # 0: CLI, 1: API, 2: Ollama
        if auth_mode != 0 or not hasattr(self, '_use_cli_mode') or not self._use_cli_mode:
            QMessageBox.information(
                self,
                t('desktop.soloAI.conversationContinueTitle'),
                t('desktop.soloAI.continueModeCLIOnly')
            )
            return

        # CLIバックエンドの確認
        if not self._cli_backend or not self._cli_backend.is_available():
            QMessageBox.warning(
                self,
                t('desktop.soloAI.cliUnavailableTitle2'),
                t('desktop.soloAI.cliLoginRequired')
            )
            return

        logger.info(f"[ClaudeTab] Sending continue message: {message}")

        # チャットに表示
        self.chat_display.append(
            f"<div style='color: #4fc3f7;'><b>{t('desktop.soloAI.continueMessageHtml')}</b> {message}</div>"
        )
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"{t('desktop.soloAI.continueModeActive')}"
            f"</div>"
        )

        # ステータス表示
        self.statusChanged.emit(t('desktop.soloAI.continuationProcessing'))

        # 思考モード設定
        thinking_text = self.thinking_combo.currentText()
        thinking_level = "none"
        if thinking_text == "Standard":
            thinking_level = "light"
        elif thinking_text == "Deep":
            thinking_level = "deep"

        # 作業ディレクトリを取得
        import os
        working_dir = os.getcwd()

        # v3.5.0: 権限スキップ設定を取得
        skip_permissions = self.permission_skip_checkbox.isChecked()

        # CLIバックエンドを取得 (v3.5.0: 権限スキップ設定を渡す)
        self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions)
        self._cli_backend.thinking_level = thinking_level

        # BackendRequestを作成（use_continue フラグを設定）
        session_id = self.session_manager.get_current_session_id() or "continue_session"
        request = BackendRequest(
            session_id=session_id,
            phase="S4",  # 継続は通常実装フェーズ
            user_text=message,
            toggles={
                "mcp": self.mcp_checkbox.isChecked(),
                "diff": self.diff_checkbox.isChecked(),
                "context": self.context_checkbox.isChecked(),
            },
            context={
                "use_continue": True,  # 重要: --continue フラグを使用
            }
        )

        # 履歴保存用
        self._pending_user_message = t('desktop.soloAI.continuePendingPrefix', message=message)

        # CLIWorkerThreadで非同期実行
        self._cli_worker = CLIWorkerThread(
            backend=self._cli_backend,
            prompt=message,
            working_dir=working_dir,
            thinking_level=thinking_level
        )
        # CLIWorkerでは直接コマンドを実行するため、send_continueを使用するには
        # 別のアプローチが必要。ここではsend_continueを呼び出す専用スレッドを使用。
        self._continue_thread = ContinueWorkerThread(
            backend=self._cli_backend,
            request=request
        )
        self._continue_thread.completed.connect(self._on_continue_response)
        self._continue_thread.start()

    def _send_continue_from_input(self):
        """継続入力欄からメッセージを送信"""
        if not hasattr(self, 'continue_input'):
            return

        text = self.continue_input.toPlainText().strip()
        if text:
            self._send_continue_message(text)
            self.continue_input.clear()
        else:
            QMessageBox.information(
                self,
                t('common.input'),
                t('desktop.soloAI.enterMessagePrompt')
            )

    def _on_continue_response(self, response: BackendResponse):
        """
        v3.4.0: 会話継続応答を処理

        Args:
            response: CLIバックエンドからのレスポンス
        """
        import logging
        logger = logging.getLogger(__name__)

        if response.success:
            # 成功時: 応答を表示（Markdown→HTMLレンダリング）
            rendered = markdown_to_html(response.response_text)
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:#00ff88;'>{t('desktop.soloAI.cliContinueLabel')}</b><br>"
                f"{rendered}"
                f"</div>"
            )

            logger.info(
                f"[ClaudeTab._on_continue_response] Continue response: "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(
                t('desktop.soloAI.continueCompleteStatus', duration=f"{response.duration_ms:.0f}")
            )

            # チャット履歴を保存
            if self._pending_user_message:
                try:
                    entry = self.chat_history_manager.add_entry(
                        prompt=self._pending_user_message,
                        response=response.response_text,
                        ai_source="Claude-CLI-Continue",
                        metadata={
                            "backend": "claude-cli",
                            "continue_mode": True,
                            "duration_ms": response.duration_ms,
                            "source_tab": "ClaudeTab"
                        }
                    )
                    logger.info(f"[ClaudeTab._on_continue_response] History saved: entry_id={entry.id}")
                    self._pending_user_message = None
                except Exception as hist_error:
                    logger.error(f"[ClaudeTab._on_continue_response] Failed to save history: {hist_error}")
        else:
            # 失敗時
            self._pending_user_message = None
            error_type = response.error_type or "ContinueError"

            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.soloAI.continueErrorHtml', error_type=error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"[ClaudeTab._on_continue_response] Continue error: type={error_type}"
            )

            self.statusChanged.emit(t('desktop.soloAI.continuationError', error=error_type))


# --- v3.4.0: 会話継続用ワーカースレッド ---
class ContinueWorkerThread(QThread):
    """会話継続用のワーカースレッド (--continue フラグ使用)"""
    completed = pyqtSignal(BackendResponse)

    def __init__(self, backend, request: BackendRequest, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._request = request

    def run(self):
        """send_continue を呼び出して会話を継続"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info(f"[ContinueWorkerThread] Starting continue request")
            response = self._backend.send_continue(self._request)
            self.completed.emit(response)
        except Exception as e:
            logger.error(f"[ContinueWorkerThread] Error: {e}", exc_info=True)
            error_response = BackendResponse(
                success=False,
                response_text=t('desktop.soloAI.continueErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
                error_type=type(e).__name__,
                duration_ms=0,
                tokens_used=0,
                cost_est=0.0,
                metadata={"backend": "claude-cli", "continue_mode": True}
            )
            self.completed.emit(error_response)
