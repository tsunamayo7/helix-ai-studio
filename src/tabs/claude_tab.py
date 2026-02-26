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
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QAction, QTextCursor, QKeyEvent
from ..utils.i18n import t
from ..utils.style_helpers import SS



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
from ..utils.constants import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL_ID, get_claude_model_by_id
from ..utils.markdown_renderer import markdown_to_html
from ..utils.styles import (
    COLORS, SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    INPUT_AREA_STYLE, SCROLLBAR_STYLE, TAB_BAR_STYLE,
    USER_MESSAGE_STYLE, AI_MESSAGE_STYLE, SPINBOX_STYLE,
)
from ..widgets.chat_widgets import CloudAIStatusBar, ExecutionIndicator, InterruptionBanner
from ..widgets.section_save_button import create_section_save_button
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox


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
                response_text=t('desktop.cloudAI.backendErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
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
                response_text=t('desktop.cloudAI.routingErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
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
                 working_dir: str = None,
                 resume_session_id: str = None, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._prompt = prompt
        self._model = model
        self._working_dir = working_dir
        self._resume_session_id = resume_session_id  # v11.0.0
        self._full_response = ""
        self._start_time = None

    def run(self):
        """CLI経由でプロンプトを実行"""
        import logging
        import time
        logger = logging.getLogger(__name__)

        self._start_time = time.time()

        try:
            # 作業ディレクトリを設定
            if self._working_dir:
                self._backend.working_dir = self._working_dir

            # ストリーミングコールバックを設定
            def on_chunk(chunk: str):
                self._full_response += chunk
                self.chunkReceived.emit(chunk)

            self._backend.set_streaming_callback(on_chunk)

            # BackendRequestを作成
            context = {}
            # v11.0.0: --resume session support
            if self._resume_session_id:
                context["resume_session_id"] = self._resume_session_id
            request = BackendRequest(
                session_id="cli_session",
                phase="S4",
                user_text=self._prompt,
                toggles={},
                context=context
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
                response_text=t('desktop.cloudAI.cliExecErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
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
# v5.1: cloudAI用添付ファイルウィジェット
# =============================================================================

class CloudAIAttachmentWidget(QFrame):
    """cloudAI用個別添付ファイルウィジェット"""
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
            CloudAIAttachmentWidget {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 2px 6px;
            }
            CloudAIAttachmentWidget:hover {
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
        name_label.setStyleSheet(SS.primary("10px"))
        name_label.setMaximumWidth(150)
        name_label.setToolTip(filepath)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: #e53e3e;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px 4px;
            }
            QPushButton:hover { background: #fc8181; }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(remove_btn)


class CloudAITextInput(QTextEdit):
    """
    cloudAI用チャット入力ウィジェット
    - 先頭行+上キー -> テキスト先頭(一番左)へ移動
    - 最終行+下キー -> テキスト末尾(一番右)へ移動
    - Ctrl+Enter で送信
    """
    send_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+Enter -> 送信
        if key == Qt.Key.Key_Return and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.send_requested.emit()
            return

        # 上キー処理
        if key == Qt.Key.Key_Up:
            cursor = self.textCursor()
            cursor_block = cursor.block()
            first_block = self.document().firstBlock()
            if cursor_block == first_block:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
                return
            super().keyPressEvent(event)
            return

        # 下キー処理
        if key == Qt.Key.Key_Down:
            cursor = self.textCursor()
            cursor_block = cursor.block()
            last_block = self.document().lastBlock()
            if cursor_block == last_block:
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                return
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)


class CloudAIContinueInput(QTextEdit):
    """
    cloudAI用会話継続入力ウィジェット
    - 先頭行+上キー -> テキスト先頭(一番左)へ移動
    - 最終行+下キー -> テキスト末尾(一番右)へ移動
    """
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Up:
            cursor = self.textCursor()
            if cursor.block() == self.document().firstBlock():
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
                return

        if key == Qt.Key.Key_Down:
            cursor = self.textCursor()
            if cursor.block() == self.document().lastBlock():
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                return

        super().keyPressEvent(event)


class CloudAIAttachmentBar(QWidget):
    """cloudAI用添付ファイルバー"""
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
                widget = CloudAIAttachmentWidget(fp)
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
                if isinstance(w, CloudAIAttachmentWidget) and w.filepath == filepath:
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

        # v11.0.0: Session management for Continue Send
        self._claude_session_id = None

        # v9.7.0: ChatStore integration
        self._active_chat_id = None
        self._chat_store = None
        try:
            from ..web.chat_store import ChatStore
            self._chat_store = ChatStore()
        except Exception as e:
            logger.warning(f"ChatStore init failed for cloudAI: {e}")

        # v8.1.0: メモリマネージャー
        self._memory_manager = None
        try:
            from ..memory.memory_manager import HelixMemoryManager
            self._memory_manager = HelixMemoryManager()
            logger.info("HelixMemoryManager initialized for cloudAI")
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

    # v11.0.0: CLI検出完了シグナル
    _cli_check_done = pyqtSignal(bool)

    def _init_backend(self):
        """v11.4.0: デフォルトを Auto モードに変更"""
        import threading

        self._cli_backend = None
        self.backend = ClaudeBackend(model="sonnet-4-5")
        self._use_cli_mode = False
        self._use_ollama_mode = False
        self._use_auto_mode = True  # v11.4.0: デフォルト Auto

        # シグナル接続（初回のみ）
        try:
            self._cli_check_done.connect(self._on_cli_check_done)
        except Exception:
            pass

        # CLI利用可否をバックグラウンドで確認（Auto/CLI Only モード向け）
        def _check_cli():
            try:
                cli_available, _ = check_claude_cli_available()
                self._cli_check_done.emit(cli_available)
            except Exception:
                self._cli_check_done.emit(False)

        threading.Thread(target=_check_cli, daemon=True).start()

    def _on_cli_check_done(self, available: bool):
        """UIスレッドでCLI検出結果を反映"""
        if available:
            self._cli_backend = get_claude_cli_backend()
            self.backend = self._cli_backend
            self._use_cli_mode = True

    def _on_auth_mode_changed(self, index: int):
        """v11.4.0: 0=Auto, 1=CLI Only, 2=API Only(廃止互換), 3=Ollama"""
        if index == 0:  # Auto（API優先 → CLI フォールバック）
            self._use_cli_mode = False
            self._use_ollama_mode = False
            self._use_auto_mode = True
            self._set_ollama_ui_disabled(False)
            self.statusChanged.emit(t('desktop.cloudAI.autoModeEnabled'))

        elif index == 1:  # CLI Only
            cli_available, message = check_claude_cli_available()
            if cli_available:
                self._cli_backend = get_claude_cli_backend()
                self.backend = self._cli_backend
                self._use_cli_mode = True
                self._use_ollama_mode = False
                self._use_auto_mode = False
                self._set_ollama_ui_disabled(False)
                self.statusChanged.emit(t('desktop.cloudAI.cliAuthSwitched'))
            else:
                QMessageBox.warning(
                    self,
                    t('desktop.cloudAI.cliAuthWarningTitle'),
                    t('desktop.cloudAI.cliNotAvailableDialogMsg', message=message)
                )
                self.auth_mode_combo.blockSignals(True)
                self.auth_mode_combo.setCurrentIndex(0)  # Auto に戻す
                self.auth_mode_combo.blockSignals(False)
                self._use_cli_mode = False
                self._use_auto_mode = True

        elif index == 2:  # API Only（廃止互換）
            self._use_cli_mode = False
            self._use_ollama_mode = False
            self._use_auto_mode = False
            self._set_ollama_ui_disabled(False)
            self.statusChanged.emit(t('desktop.cloudAI.apiAuthSwitched'))

        else:  # index == 3: Ollama
            self._use_cli_mode = False
            self._use_ollama_mode = True
            self._use_auto_mode = False
            self._configure_ollama_mode()
            self._set_ollama_ui_disabled(True)
            self.statusChanged.emit(t('desktop.cloudAI.ollamaSwitched', model=self._ollama_model))

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
                    t('desktop.cloudAI.ollamaModelTooltip', model=getattr(self, '_ollama_model', t('desktop.cloudAI.notConfigured')))
                )
            else:
                tooltip_lines = t('desktop.cloudAI.modelTooltipHtml')
                for model_def in CLAUDE_MODELS:
                    tooltip_lines += f"<b>{model_def['display_name']}:</b> {model_def['description']}<br>"
                self.model_combo.setToolTip(tooltip_lines
                )

        # v11.0.0: effort_combo removed (hidden setting in config.json)

    def _configure_ollama_mode(self):
        """Ollamaモードの設定 (v3.0.0, v3.9.2: 設定タブ参照を修正)"""
        import os

        # v3.9.2: cloudAI(Claude)タブの設定からOllama設定を取得
        ollama_url = "http://localhost:11434"
        self._ollama_model = ""

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

    def _auto_select_ollama_model(self) -> str:
        """v11.5.0: Ollama の最初のインストール済みモデルを自動選択"""
        try:
            import requests
            ollama_url = getattr(self, '_ollama_url', 'http://localhost:11434')
            resp = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    name = models[0].get("name", "")
                    logger.info(f"[ClaudeTab] Auto-selected Ollama model: {name}")
                    return name
        except Exception:
            pass
        return ""

    def _show_no_models_banner(self, visible: bool):
        """v11.5.0: モデル未設定バナーの表示/非表示"""
        if not hasattr(self, '_no_models_banner'):
            return
        self._no_models_banner.setVisible(visible)

    def _check_models_configured(self):
        """v11.5.0: 起動時とモデル追加/削除時に呼び出す"""
        try:
            from pathlib import Path
            import json
            config_path = Path("config/cloud_models.json")
            if not config_path.exists():
                self._show_no_models_banner(True)
                return
            data = json.loads(config_path.read_text(encoding='utf-8'))
            has_models = len(data.get("models", [])) > 0
            self._show_no_models_banner(not has_models)
        except Exception:
            self._show_no_models_banner(True)

    def _update_auth_status(self):
        """認証状態を更新表示 (v2.5.0, v3.0.0: Ollama追加)"""
        if hasattr(self, '_use_ollama_mode') and self._use_ollama_mode:
            # v3.0.0: Ollamaモード
            import os
            ollama_url = os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:11434")
            model_name = getattr(self, '_ollama_model', '')
            self.auth_status_label.setText("🖥️")
            self.auth_status_label.setStyleSheet(SS.info("12pt"))
            self.auth_status_label.setToolTip(
                t('desktop.cloudAI.ollamaAuthTooltip', url=ollama_url, model=model_name)
            )
        elif hasattr(self, '_use_cli_mode') and self._use_cli_mode:
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
            # v6.0.0: API認証は廃止、CLI専用化
            self.auth_status_label.setText("⚙️")
            self.auth_status_label.setStyleSheet(SS.warn("12pt"))
            self.auth_status_label.setToolTip(
                t('desktop.cloudAI.apiDeprecatedLongTooltip')
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
        self.sub_tabs.addTab(chat_tab, t('desktop.cloudAI.chatSubTab'))

        # 設定サブタブ
        settings_tab = self._create_settings_tab()
        self.sub_tabs.addTab(settings_tab, t('desktop.cloudAI.settingsSubTab'))

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

        # v11.5.0: モデル未設定バナー
        self._no_models_banner = QFrame()
        self._no_models_banner.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['warning']}; border-radius: 6px; padding: 4px; }}"
        )
        banner_layout = QHBoxLayout(self._no_models_banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_text = QLabel(t('desktop.cloudAI.noModelsConfigured'))
        banner_text.setStyleSheet(SS.warn("11px"))
        banner_text.setWordWrap(True)
        banner_layout.addWidget(banner_text, 1)
        banner_btn = QPushButton(t('desktop.cloudAI.goToModelSettings'))
        banner_btn.setStyleSheet("QPushButton { color: #3b82f6; font-size: 10px; border: none; }")
        banner_btn.clicked.connect(lambda: self.sub_tabs.setCurrentIndex(1))
        banner_layout.addWidget(banner_btn)
        chat_layout.addWidget(self._no_models_banner)
        self._no_models_banner.setVisible(False)
        self._check_models_configured()

        # メインスプリッター (チャット表示と入力エリア)
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # チャット表示エリア
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Yu Gothic UI", 10))
        self.chat_display.setPlaceholderText(t('desktop.cloudAI.chatReady'))
        self.chat_display.setStyleSheet(
            f"QTextEdit {{ background-color: {COLORS['bg_base']}; border: none; "
            f"padding: 10px; color: {COLORS['text_primary']}; }}" + SCROLLBAR_STYLE
        )
        # v10.1.0: Auto-scroll to bottom on new content
        self.chat_display.textChanged.connect(self._auto_scroll_chat)
        main_splitter.addWidget(self.chat_display)

        # v10.1.0: ExecutionMonitorWidget（chat_displayと入力エリアの間）
        from ..widgets.execution_monitor_widget import ExecutionMonitorWidget
        self.monitor_widget = ExecutionMonitorWidget()
        self.monitor_widget.stallDetected.connect(self._on_stall_detected)
        main_splitter.addWidget(self.monitor_widget)

        # 入力エリア
        input_frame = self._create_input_area()
        main_splitter.addWidget(input_frame)

        main_splitter.setSizes([600, 0, 200])
        main_splitter.setHandleWidth(2)
        chat_layout.addWidget(main_splitter)

        return chat_widget

    def _create_settings_tab(self) -> QWidget:
        """設定サブタブを作成 (v3.9.0: Claude関連設定を統合, v9.6: ツールバーから移設)"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(10, 10, 10, 10)

        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # === 🔑 認証方式 (旧ツールバー行1から移設) ===
        self.api_group = QGroupBox(t('desktop.cloudAI.authGroup'))
        api_layout = QFormLayout()

        # 認証方式コンボ
        self.auth_label = QLabel(t('desktop.cloudAI.authLabel2'))
        self.auth_mode_combo = NoScrollComboBox()
        self.auth_mode_combo.addItems([
            t('desktop.cloudAI.authAutoOption'),   # 0: Auto（API優先→CLI）
            t('desktop.cloudAI.authCliOption'),    # 1: CLI Only
            t('desktop.cloudAI.authApiOption'),    # 2: API Only（後方互換）
            t('desktop.cloudAI.authOllamaOption'), # 3: Ollama
        ])
        # v11.4.0: デフォルトを Auto に変更
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
        self.cli_status_label = QLabel(f"{t('desktop.cloudAI.cliEnabled') if cli_available else t('desktop.cloudAI.cliDisabled')}")
        self.cli_status_label.setToolTip(cli_msg)
        cli_status_layout.addWidget(self.cli_status_label)
        self.cli_check_btn = QPushButton(t('common.confirm'))
        self.cli_check_btn.clicked.connect(self._check_cli_status)
        cli_status_layout.addWidget(self.cli_check_btn)
        cli_status_layout.addStretch()
        # v11.5.0: CLI行を非表示（オブジェクトは他で参照されるため残す）
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
        scroll_layout.addWidget(self.api_group)
        self.api_group.setVisible(False)

        # === 🤖 モデル設定 (v11.0.0: モデル管理機能追加) ===
        self.model_settings_group = QGroupBox(t('desktop.cloudAI.modelSettingsGroup'))
        model_settings_layout = QVBoxLayout()

        # 登録済みモデルリスト
        self.cloud_model_list_label = QLabel(t('desktop.cloudAI.registeredModels'))
        self.cloud_model_list_label.setStyleSheet(f"font-weight: bold; color: {COLORS['text_primary']}; margin-bottom: 4px;")
        model_settings_layout.addWidget(self.cloud_model_list_label)

        self.cloud_model_list = QListWidget()
        self.cloud_model_list.setMaximumHeight(140)
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
        scroll_layout.addWidget(self.model_settings_group)

        # === ⚙️ 実行オプション (旧ツールバー行2から移設) ===
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

        # v11.3.0: Browser Use チェックボックス（httpxベースのため常時有効）
        self.browser_use_checkbox = QCheckBox(t('desktop.cloudAI.browserUseLabel'))
        self.browser_use_checkbox.setChecked(False)
        self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseTip'))
        self._browser_use_available = True
        self.browser_use_checkbox.setEnabled(True)
        mcp_options_layout.addWidget(self.browser_use_checkbox)
        mcp_options_layout.addWidget(create_section_save_button(self._save_all_cloudai_settings))

        self.mcp_options_group.setLayout(mcp_options_layout)
        scroll_layout.addWidget(self.mcp_options_group)

        # === Ollama設定 ===
        self.ollama_group = QGroupBox(t('desktop.cloudAI.ollamaSettingsGroup'))
        ollama_layout = QVBoxLayout(self.ollama_group)

        # Ollama URL
        ollama_url_layout = QHBoxLayout()
        self.ollama_url_label = QLabel(t('desktop.cloudAI.hostUrlLabel'))
        ollama_url_layout.addWidget(self.ollama_url_label)
        self.settings_ollama_url = QLineEdit("http://localhost:11434")
        ollama_url_layout.addWidget(self.settings_ollama_url)
        self.ollama_test_btn = QPushButton(t('desktop.cloudAI.connTestBtn'))
        self.ollama_test_btn.clicked.connect(self._test_ollama_settings)
        ollama_url_layout.addWidget(self.ollama_test_btn)
        ollama_layout.addLayout(ollama_url_layout)

        # Ollamaモデル
        ollama_model_layout = QHBoxLayout()
        self.ollama_model_label = QLabel(t('desktop.cloudAI.useModelLabel'))
        ollama_model_layout.addWidget(self.ollama_model_label)
        self.settings_ollama_model = NoScrollComboBox()
        self.settings_ollama_model.setEditable(False)
        self.settings_ollama_model.setPlaceholderText(t('desktop.cloudAI.ollamaModelPlaceholder'))
        self.settings_ollama_model.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.settings_ollama_model.installEventFilter(self)
        ollama_model_layout.addWidget(self.settings_ollama_model)
        self.refresh_models_btn = QPushButton(t('desktop.cloudAI.refreshModelsBtn'))
        self.refresh_models_btn.clicked.connect(self._refresh_ollama_models_settings)
        ollama_model_layout.addWidget(self.refresh_models_btn)
        ollama_layout.addLayout(ollama_model_layout)

        # ステータス
        self.settings_ollama_status = QLabel(t('desktop.cloudAI.ollamaStatusInit'))
        self.settings_ollama_status.setStyleSheet(SS.dim())
        ollama_layout.addWidget(self.settings_ollama_status)

        scroll_layout.addWidget(self.ollama_group)
        self.ollama_group.setVisible(False)

        # === v10.1.0: Claude CLI 連携セクション ===
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
        scroll_layout.addWidget(self.cli_section_group)
        self._check_cli_version_detail()

        # === v10.1.0: Codex CLI 連携セクション ===
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
        scroll_layout.addWidget(self.codex_section_group)
        self.codex_section_group.setVisible(False)  # v11.5.0: Codex CLIセクション非表示
        self._check_codex_version()

        # === v11.0.0: MCP Settings for cloudAI ===
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
        scroll_layout.addWidget(self.cloudai_mcp_group)

        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        settings_layout.addWidget(scroll)

        # 保存済み設定を復元
        self._load_claude_settings()

        # 認証状態の初期更新
        self._update_auth_status()

        return settings_widget

    def _check_cli_status(self):
        """CLI状態を確認"""
        cli_available, cli_msg = check_claude_cli_available()
        self.cli_status_label.setText(f"{t('desktop.cloudAI.cliEnabled') if cli_available else t('desktop.cloudAI.cliDisabled')}")
        self.cli_status_label.setToolTip(cli_msg)
        if cli_available:
            QMessageBox.information(self, t('desktop.cloudAI.cliAvailableTitle'), t('desktop.cloudAI.cliAvailableMsg', msg=cli_msg))
        else:
            QMessageBox.warning(self, t('desktop.cloudAI.cliAvailableTitle'), t('desktop.cloudAI.cliUnavailableMsg', msg=cli_msg))

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
        """v11.0.0: Codex CLI バージョン確認（Windows .cmd対応）"""
        self.codex_version_label.setText("⏳ checking...")
        self.codex_version_label.setStyleSheet(SS.warn("9pt"))
        self.codex_check_btn.setEnabled(False)
        # 短い遅延でバックグラウンド実行→結果をUI反映
        QTimer.singleShot(50, self._do_codex_check)

    def _do_codex_check(self):
        """Codex CLIを実際にチェック（QTimer経由でUIスレッドで実行）"""
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

    def _open_manage_models_from_cloud(self):
        """v10.1.0: cloudAI設定からManageModelsDialogを開く"""
        try:
            if self.main_window and hasattr(self.main_window, 'helix_tab'):
                helix_tab = self.main_window.helix_tab
                if hasattr(helix_tab, '_open_manage_models_dialog'):
                    helix_tab._open_manage_models_dialog()
                    return
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "mixAI Phase",
                t('desktop.cloudAI.mixaiPhaseOpenMixTab')
            )
        except Exception as e:
            logger.warning(f"ManageModelsDialog open failed: {e}")

    def _test_ollama_settings(self):
        """Ollama接続テスト（設定タブ用）"""
        try:
            import ollama
            url = self.settings_ollama_url.text().strip()
            client = ollama.Client(host=url)
            response = client.list()
            model_count = len(response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', []))
            self.settings_ollama_status.setText(t('desktop.cloudAI.ollamaConnSuccess', count=model_count))
            self.settings_ollama_status.setStyleSheet(SS.ok())
        except Exception as e:
            self.settings_ollama_status.setText(t('desktop.cloudAI.ollamaConnFailed', error=str(e)[:30]))
            self.settings_ollama_status.setStyleSheet(SS.err())

    # ========================================
    # v3.9.2: 接続テスト・動作確認機能
    # ========================================

    def _test_api_connection(self):
        """API接続テスト (v6.0.0: 廃止 - CLI専用化)"""
        # v6.0.0: API認証は廃止されました
        if hasattr(self, 'api_test_status'):
            self.api_test_status.setText(t('desktop.cloudAI.apiDeprecatedStatus'))
            self.api_test_status.setStyleSheet(SS.warn())
            self.api_test_status.setToolTip(
                t('desktop.cloudAI.apiDeprecatedDialogMsg')
            )

    def _run_unified_model_test(self):
        """統合モデルテスト: 現在の認証方式でテスト実行 (v3.9.2)"""
        import logging
        logger = logging.getLogger(__name__)

        auth_mode = self.auth_mode_combo.currentIndex()  # v11.4.0: 0=Auto, 1=CLI, 2=API, 3=Ollama
        auth_names = ["Auto (API→CLI)", "CLI (Max/Pro)", "API", "Ollama"]
        auth_name = auth_names[auth_mode] if auth_mode < len(auth_names) else t('desktop.cloudAI.unknownAuth')

        try:
            if auth_mode == 0:
                # v11.4.0: Auto モード — API 優先で接続テスト
                from ..backends.api_priority_resolver import resolve_anthropic_connection, ConnectionMode
                method, kwargs = resolve_anthropic_connection(ConnectionMode.AUTO)
                if method == "anthropic_api":
                    import time
                    from ..backends.anthropic_api_backend import is_anthropic_sdk_available
                    if not is_anthropic_sdk_available():
                        QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'),
                                            "anthropic SDK がインストールされていません。\npip install anthropic")
                        return
                    start = time.time()
                    # 簡易テスト: API key の有効性を確認
                    import anthropic
                    client = anthropic.Anthropic(api_key=kwargs["api_key"])
                    resp = client.messages.create(
                        model="claude-sonnet-4-5-20250929", max_tokens=5,
                        messages=[{"role": "user", "content": "Hi"}])
                    latency = time.time() - start
                    self._save_last_test_success("Anthropic API", latency)
                    QMessageBox.information(
                        self, t('desktop.cloudAI.testSuccessTitle'),
                        f"Auto → Anthropic API 接続成功\nLatency: {latency:.2f}s")
                elif method == "claude_cli":
                    from ..utils.subprocess_utils import run_hidden
                    import time
                    start = time.time()
                    result = run_hidden(["claude", "--version"], capture_output=True, text=True, timeout=10)
                    latency = time.time() - start
                    if result.returncode == 0:
                        self._save_last_test_success("CLI (Auto fallback)", latency)
                        QMessageBox.information(
                            self, t('desktop.cloudAI.testSuccessTitle'),
                            f"Auto → Claude CLI フォールバック接続成功\nLatency: {latency:.2f}s\nCLI: {result.stdout.strip()}")
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
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'), t('desktop.cloudAI.testFailedCliMsg'))
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
                        self, t('desktop.cloudAI.testSuccessTitle'),
                        t('desktop.cloudAI.testResultMsg', auth_name=auth_name, latency=f"{latency:.2f}")
                        + f"\nCLI Version: {result.stdout.strip()}"
                    )
                else:
                    QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'), t('desktop.cloudAI.testFailedCliError', error=result.stderr))

            elif auth_mode == 2:
                # API モード — v11.4.0: API直接接続テスト
                from ..backends.api_priority_resolver import resolve_anthropic_connection, ConnectionMode
                method, kwargs = resolve_anthropic_connection(ConnectionMode.API_ONLY)
                if method == "anthropic_api":
                    import time
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
                    self, t('desktop.cloudAI.testSuccessTitle'),
                    t('desktop.cloudAI.testResultMsgShort', auth_name=auth_name, model=model, latency=f"{latency:.2f}")
                )

        except Exception as e:
            logger.error(f"[Unified Model Test] Error: {e}")
            QMessageBox.warning(self, t('desktop.cloudAI.testFailedTitle'), t('desktop.cloudAI.testFailedAuth', auth=auth_name, error=str(e)))

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
                            t('desktop.cloudAI.lastTestSuccessLabel', auth=auth, timestamp=timestamp, latency=f"{latency:.2f}")
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
                t('desktop.cloudAI.lastTestSuccessLabel', auth=auth_type, timestamp=timestamp, latency=f"{latency:.2f}")
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
            self.settings_ollama_status.setText(t('desktop.cloudAI.modelListSuccess', count=len(model_names)))
            self.settings_ollama_status.setStyleSheet(SS.ok())
        except Exception as e:
            self.settings_ollama_status.setText(t('desktop.cloudAI.modelListFailed', error=str(e)[:30]))
            self.settings_ollama_status.setStyleSheet(SS.err())

    def _populate_mcp_servers(self):
        """MCPサーバーリストを初期化"""
        servers = [
            ("filesystem", t('desktop.cloudAI.mcpFilesystem'), True),
            ("git", "🔀 Git", True),
            ("brave-search", t('desktop.cloudAI.mcpBraveSearch'), False),
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

    def _load_claude_settings(self):
        """保存済みのClaude設定を読み込んでUIに反映 (v9.6)"""
        import json
        from pathlib import Path
        config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if 'ollama_url' in settings and hasattr(self, 'settings_ollama_url'):
                self.settings_ollama_url.setText(settings['ollama_url'])
            if 'auth_mode' in settings and hasattr(self, 'auth_mode_combo'):
                self.auth_mode_combo.blockSignals(True)
                self.auth_mode_combo.setCurrentIndex(int(settings['auth_mode']))
                self.auth_mode_combo.blockSignals(False)
            if 'model_index' in settings and hasattr(self, 'model_combo'):
                self.model_combo.setCurrentIndex(int(settings['model_index']))
            # v11.0.0: effort_level is now a hidden setting in config.json (effort_combo removed)
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
            # v10.1.0: browser_use_enabled (旧 search_mode / search_max_tokens は廃止)
            if 'browser_use_enabled' in settings and hasattr(self, 'browser_use_checkbox'):
                self.browser_use_checkbox.setChecked(bool(settings['browser_use_enabled']))
        except Exception as e:
            logger.debug(f"claude_settings.json load failed: {e}")

    def _save_all_cloudai_settings(self):
        """v11.0.0: Save all cloudAI settings"""
        self._save_claude_settings()

    def _save_claude_settings(self):
        """Claude設定を保存 (v9.9.2: 差分ダイアログ廃止、即時保存)"""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "config" / "claude_settings.json"
        config_path.parent.mkdir(exist_ok=True)

        settings = {
            "ollama_url": self.settings_ollama_url.text().strip(),
            "ollama_model": self.settings_ollama_model.currentText(),
            "auth_mode": self.auth_mode_combo.currentIndex(),
            "model_index": self.model_combo.currentIndex(),
            "timeout_minutes": self.solo_timeout_spin.value() if hasattr(self, 'solo_timeout_spin') else 30,
            "mcp_enabled": self.mcp_checkbox.isChecked(),
            "diff_enabled": self.diff_checkbox.isChecked(),
            "auto_context": self.context_checkbox.isChecked(),
            "permission_skip": self.permission_skip_checkbox.isChecked(),
            # v10.1.0: browser_use_enabled (旧 search_mode / search_max_tokens は廃止)
            "browser_use_enabled": self.browser_use_checkbox.isChecked() if hasattr(self, 'browser_use_checkbox') else False,
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        self.statusChanged.emit(t('desktop.cloudAI.savedStatus'))
        # v9.9.1: timer-based button feedback（settings_cortex_tab.py と統一）
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
        import json
        from pathlib import Path
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
            logger.info("[ClaudeTab] Saved cloudAI MCP settings")
            self.statusChanged.emit(t('desktop.cloudAI.savedStatus'))
        except Exception as e:
            logger.error(f"Failed to save MCP settings: {e}")

    def _create_workflow_bar(self) -> QFrame:
        """v8.0.0: ステータスバーを作成（旧ステージUI→CloudAIStatusBarに置換）"""
        frame = QFrame()
        frame.setObjectName("workflowFrame")
        frame.setStyleSheet(f"#workflowFrame {{ background-color: {COLORS['bg_card']}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # v8.0.0: CloudAIStatusBar（旧S0-S5ステージUIを置換）
        self.solo_status_bar = CloudAIStatusBar()
        self.solo_status_bar.new_session_clicked.connect(self._on_new_session)

        # v11.0.0: Header title label
        self.cloud_header_title = QLabel(t('desktop.cloudAI.headerTitle'))
        self.cloud_header_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.cloud_header_title.setStyleSheet(f"color: {COLORS['text_primary']}; margin-right: 12px;")

        # v11.0.0: Model label
        self.cloud_model_label = QLabel(t('desktop.cloudAI.modelLabel'))
        self.cloud_model_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; margin-right: 4px;")

        # v11.0.0: Model selector in chat header
        self.cloud_model_combo = NoScrollComboBox()
        self.cloud_model_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 4px;
                padding: 3px 8px; font-size: 11px; min-width: 160px;
            }}
            QComboBox:hover {{ border-color: {COLORS['accent']}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
                selection-background-color: {COLORS['accent_dim']};
            }}
        """)
        self._load_cloud_models_to_combo(self.cloud_model_combo)
        self.cloud_model_combo.currentIndexChanged.connect(self._on_cloud_model_changed)

        # v11.0.0: Refresh button
        self.cloud_refresh_btn = QPushButton(t('desktop.cloudAI.refreshBtn'))
        self.cloud_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cloud_refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']}; border-radius: 4px;
                padding: 4px 10px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {COLORS['text_primary']}; border-color: {COLORS['accent']}; }}
        """)
        self.cloud_refresh_btn.clicked.connect(lambda: self._load_cloud_models_to_combo(self.cloud_model_combo))

        # v11.0.0: 後方互換用 (hidden)
        self.advanced_settings_btn = QPushButton()
        self.advanced_settings_btn.setVisible(False)
        self.new_session_btn = QPushButton()
        self.new_session_btn.setVisible(False)
        self.history_btn = QPushButton()
        self.history_btn.setVisible(False)

        # v11.0.0: Header layout [Title] [Model:] [▼ combo] [🔄 Refresh]
        status_row = QHBoxLayout()
        status_row.addWidget(self.cloud_header_title)
        status_row.addWidget(self.cloud_model_label)
        status_row.addWidget(self.cloud_model_combo)
        status_row.addWidget(self.cloud_refresh_btn)
        status_row.addStretch()
        layout.addLayout(status_row)

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

    def _load_cloud_models_to_combo(self, combo):
        """v11.5.0: cloud_models.json からモデル一覧を読み込みコンボに設定"""
        combo.clear()
        try:
            from pathlib import Path
            import json
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for model in data.get("models", []):
                    provider = model.get("provider", "?")
                    badge = {"anthropic_api": "API", "openai_api": "OAI", "google_api": "Gemini", "anthropic_cli": "CLI", "openai_cli": "Codex", "google_cli": "G-CLI"}.get(provider, provider)
                    combo.addItem(f"{model['name']} [{badge}]", model["model_id"])
        except Exception as e:
            logger.warning(f"Failed to load cloud models: {e}")

    def _get_selected_model_provider(self) -> tuple:
        """v11.5.0: 現在選択モデルの (model_id, provider) を返す"""
        if hasattr(self, 'cloud_model_combo') and self.cloud_model_combo.count() > 0:
            model_id = self.cloud_model_combo.currentData() or ""
        else:
            model_id = self.model_combo.currentData() if hasattr(self, 'model_combo') else ""
            model_id = model_id or ""

        if not model_id:
            return "", "unknown"

        try:
            from pathlib import Path
            import json
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                data = json.loads(config_path.read_text(encoding='utf-8'))
                for m in data.get("models", []):
                    if m.get("model_id") == model_id:
                        return model_id, m.get("provider", "anthropic_api")
        except Exception:
            pass

        # v11.5.1: prefix fallback 撤廃 — cloud_models.json に provider が未設定の場合は unknown を返す
        return model_id, "unknown"

    def _get_first_model_by_provider(self, provider: str) -> str:
        """v11.5.0: cloud_models.json から指定プロバイダーの最初のモデル ID を返す"""
        try:
            from pathlib import Path
            import json
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                data = json.loads(config_path.read_text(encoding='utf-8'))
                for m in data.get("models", []):
                    if m.get("provider") == provider:
                        return m.get("model_id", "")
        except Exception:
            pass
        return ""

    def _on_cloud_model_changed(self, index: int):
        """v11.0.0: ヘッダーのモデル選択変更時に設定タブのmodel_comboも同期"""
        if not hasattr(self, 'cloud_model_combo') or not hasattr(self, 'model_combo'):
            return
        model_id = self.cloud_model_combo.currentData()
        if model_id:
            # 設定タブのmodel_comboで同じmodel_idを探して同期
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == model_id:
                    self.model_combo.blockSignals(True)
                    self.model_combo.setCurrentIndex(i)
                    self.model_combo.blockSignals(False)
                    break
            logger.info(f"[ClaudeTab] Cloud model changed to: {model_id}")

    def _refresh_cloud_model_list(self):
        """v11.5.0: cloud_models.json からリストウィジェットを更新（provider バッジ付き）"""
        if not hasattr(self, 'cloud_model_list'):
            return
        self.cloud_model_list.clear()
        try:
            from pathlib import Path
            import json
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
                    self.cloud_model_list.addItem(
                        f"{i}. {model['name']}  |  {model.get('model_id', '')}  [{provider_badge}]"
                    )
        except Exception as e:
            logger.warning(f"Failed to refresh cloud model list: {e}")
        # v11.5.0: banner check
        if hasattr(self, '_check_models_configured'):
            self._check_models_configured()

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
                "  gemini-2.5-flash          ← Recommended (stable)\n"
                "  gemini-2.5-pro            ← High performance\n"
                "  gemini-2.5-flash-lite     ← Low cost\n"
                "API Key: https://aistudio.google.com/app/apikey\n"
                "SDK: pip install google-genai"
            ),
            "google_cli": (
                "【Google Gemini CLI Model ID Examples】\n"
                "  gemini-2.5-flash          ← Recommended\n"
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
            from pathlib import Path
            import json
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
            self._load_cloud_models_to_combo(self.cloud_model_combo)
            self.statusChanged.emit(f"Model added: {name} ({provider})")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

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
            from pathlib import Path
            import json
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
                    self._load_cloud_models_to_combo(self.cloud_model_combo)
                    self.statusChanged.emit(f"Model removed: {removed.get('name', '')}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_edit_cloud_models_json(self):
        """v11.0.0: cloud_models.json をテキスト編集ダイアログで開く"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.cloudAI.editJsonTitle'))
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)

        editor = QTextEdit()
        editor.setStyleSheet(f"QTextEdit {{ background: {COLORS['bg_surface']}; color: {COLORS['text_primary']}; font-family: monospace; font-size: 11px; }}")
        try:
            from pathlib import Path
            config_path = Path("config/cloud_models.json")
            if config_path.exists():
                editor.setPlainText(config_path.read_text(encoding='utf-8'))
        except Exception:
            pass
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                import json
                from pathlib import Path
                text = editor.toPlainText()
                json.loads(text)  # validate
                Path("config/cloud_models.json").write_text(text, encoding='utf-8')
                self._refresh_cloud_model_list()
                self._load_cloud_models_to_combo(self.cloud_model_combo)
                self.statusChanged.emit("cloud_models.json updated")
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON Error", f"Invalid JSON: {e}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _on_reload_cloud_models(self):
        """v11.0.0: モデルリストとコンボを再読み込み"""
        self._refresh_cloud_model_list()
        self._load_cloud_models_to_combo(self.cloud_model_combo)
        self.statusChanged.emit("Cloud models reloaded")

    def _open_claude_code_settings(self):
        """v11.0.0: ~/.claude/settings.json をOSデフォルトエディタで開く"""
        import platform, subprocess, os
        from pathlib import Path
        settings_path = Path.home() / ".claude" / "settings.json"
        if not settings_path.exists():
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            default = {"permissions": {}, "env": {}}
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(default, f, indent=2, ensure_ascii=False)
        try:
            if platform.system() == "Windows":
                os.startfile(str(settings_path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(settings_path)])
            else:
                subprocess.run(["xdg-open", str(settings_path)])
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")
            QMessageBox.warning(self, t('common.error'),
                                t('desktop.cloudAI.settingsOpenFailed', error=str(e)))

    def _create_approval_panel(self) -> QGroupBox:
        """S3承認チェックリストパネルを作成（Phase 1.2）"""
        from ..security.risk_gate import ApprovalScope

        self.approval_group = QGroupBox(t('desktop.cloudAI.approvalScopesGroup'))
        group = self.approval_group
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {COLORS['accent_dim']};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: {COLORS['accent_dim']};
            }}
        """)

        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # 説明ラベル
        self.approval_desc_label = QLabel(
            t('desktop.cloudAI.approvalPanelDesc')
        )
        desc_label = self.approval_desc_label
        desc_label.setStyleSheet(SS.dim("9pt"))
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

        self.approve_all_btn = QPushButton(t('desktop.cloudAI.approveAllBtnLabel'))
        all_btn = self.approve_all_btn
        all_btn.setMaximumWidth(100)
        all_btn.clicked.connect(self._approve_all_scopes)
        button_layout.addWidget(all_btn)

        self.revoke_all_btn = QPushButton(t('desktop.cloudAI.revokeAllBtnLabel'))
        none_btn = self.revoke_all_btn
        none_btn.setMaximumWidth(100)
        none_btn.clicked.connect(self._revoke_all_scopes)
        button_layout.addWidget(none_btn)

        layout.addLayout(button_layout)

        return group

    # _create_toolbar() は v9.6 で廃止（設定タブへ移動）

    def _create_input_area(self) -> QFrame:
        """入力エリアを作成 (v3.4.0: 会話継続UIを追加, v5.1: 添付ファイルバー追加)"""
        frame = QFrame()
        frame.setObjectName("inputFrame")
        frame.setStyleSheet(f"#inputFrame {{ border-top: 1px solid {COLORS['border']}; }}")
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
        self.attachment_bar = CloudAIAttachmentBar()
        self.attachment_bar.attachments_changed.connect(self._on_attachments_changed)
        self.attachment_bar.setVisible(False)
        self.attachment_bar.setMaximumHeight(0)
        left_layout.addWidget(self.attachment_bar)

        # 入力フィールド (CloudAITextInput: 上下キーカーソル移動対応)
        self.input_field = CloudAITextInput()
        self.input_field.setPlaceholderText(t('desktop.cloudAI.inputPlaceholder'))
        self.input_field.setFont(QFont("Yu Gothic UI", 11))
        self.input_field.setMinimumHeight(40)
        self.input_field.setMaximumHeight(150)
        self.input_field.setStyleSheet(
            f"QTextEdit {{ background: {COLORS['bg_elevated']}; color: {COLORS['text_primary']}; border: none; "
            f"padding: 8px; }}" + SCROLLBAR_STYLE
        )
        self.input_field.setAcceptDrops(True)
        self.input_field.send_requested.connect(self._on_send)
        left_layout.addWidget(self.input_field)

        # ボタン行（v11.8.0: mixAI/localAI統一レイアウト）
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.attach_btn = QPushButton("📎 " + t('common.attach'))
        self.attach_btn.setFixedHeight(32)
        self.attach_btn.setStyleSheet(SECONDARY_BTN)
        self.attach_btn.setToolTip(t('desktop.cloudAI.attachTooltip'))
        btn_layout.addWidget(self.attach_btn)

        # v11.0.0: 履歴から引用ボタン → 削除(Historyタブで代替)、後方互換用
        self.citation_btn = QPushButton()
        self.citation_btn.setVisible(False)

        # v3.6.0: スニペットボタン（追加機能統合済み）
        from PyQt6.QtWidgets import QMenu
        self.snippet_btn = QPushButton(t('desktop.cloudAI.snippetBtnLabel'))
        self.snippet_btn.setFixedHeight(32)
        self.snippet_btn.setStyleSheet(SECONDARY_BTN)
        self.snippet_btn.setToolTip(t('desktop.cloudAI.snippetTooltip'))
        btn_layout.addWidget(self.snippet_btn)

        # v11.0.0: 追加ボタン → 削除(スニペットメニュー内に統合)、後方互換用
        self.snippet_add_btn = QPushButton()
        self.snippet_add_btn.setVisible(False)

        # v11.0.0: BIBLE toggle button (Phase 4) - 高さ統一
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
        btn_layout.addWidget(self.bible_btn)

        btn_layout.addStretch()

        # v11.0.0: Continue Send button (session retention)
        self.continue_send_btn_main = QPushButton(t('desktop.cloudAI.continueSendMain'))
        self.continue_send_btn_main.setFixedHeight(32)
        self.continue_send_btn_main.setToolTip(t('desktop.cloudAI.continueSendMainTooltip'))
        self.continue_send_btn_main.setEnabled(False)
        self.continue_send_btn_main.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success_bg']}; color: {COLORS['success']};
                border: 1px solid {COLORS['success']}; border-radius: 4px;
                padding: 4px 12px; font-weight: bold; font-size: 11px;
            }}
            QPushButton:hover {{ background: #2a4a3a; }}
            QPushButton:disabled {{ background: {COLORS['bg_card']}; color: {COLORS['text_muted']}; border-color: {COLORS['text_disabled']}; }}
        """)
        self.continue_send_btn_main.clicked.connect(self._on_continue_send_main)
        btn_layout.addWidget(self.continue_send_btn_main)

        self.send_btn = QPushButton(t('desktop.cloudAI.sendBtnMain'))  # v11.5.3: 統一ラベル
        self.send_btn.setDefault(True)
        self.send_btn.setFixedHeight(32)           # v11.5.2: localAI統一
        self.send_btn.setStyleSheet(PRIMARY_BTN)   # v11.5.2: localAI統一
        self.send_btn.setToolTip(t('desktop.cloudAI.sendTooltip'))
        btn_layout.addWidget(self.send_btn)

        left_layout.addLayout(btn_layout)
        h_layout.addWidget(left_frame, 2)  # 左側に2/3幅

        # --- 右側: 会話継続エリア (約1/3幅) v3.4.0 ---
        continue_frame = QFrame()
        continue_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        continue_layout = QVBoxLayout(continue_frame)
        continue_layout.setContentsMargins(8, 6, 8, 6)
        continue_layout.setSpacing(6)

        # ヘッダー
        self.continue_header = QLabel(t('desktop.cloudAI.conversationContinueLabel'))
        continue_header = self.continue_header
        continue_header.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 11px; border: none;")
        continue_layout.addWidget(continue_header)

        # 説明
        self.continue_desc = QLabel(t('desktop.cloudAI.continueDesc'))
        continue_desc = self.continue_desc
        continue_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; border: none;")
        continue_desc.setWordWrap(True)
        continue_layout.addWidget(continue_desc)

        # 継続入力フィールド (v9.6: CloudAIContinueInput - 上/下キーでカーソル先頭/末尾へ)
        self.continue_input = CloudAIContinueInput()
        self.continue_input.setPlaceholderText(t('desktop.cloudAI.continuePlaceholder'))
        self.continue_input.setMinimumHeight(60)
        self.continue_input.setMaximumHeight(90)
        self.continue_input.setStyleSheet(f"""
            QTextEdit {{ background: {COLORS['bg_elevated']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border']};
                        border-radius: 4px; padding: 4px 8px; font-size: 11px; }}
            QTextEdit:focus {{ border-color: {COLORS['accent_dim']}; }}
        """)
        continue_layout.addWidget(self.continue_input)

        # クイックボタン行
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(4)

        # 「はい」ボタン
        self.quick_yes_btn = QPushButton(t('desktop.cloudAI.quickYesLabel'))
        self.quick_yes_btn.setFixedHeight(26)
        self.quick_yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_yes_btn.setToolTip(t('desktop.cloudAI.quickYesTooltip'))
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
        self.quick_continue_btn = QPushButton(t('desktop.cloudAI.continueBtn'))
        self.quick_continue_btn.setFixedHeight(26)
        self.quick_continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_continue_btn.setToolTip(t('desktop.cloudAI.quickContinueTooltip'))
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
        self.quick_exec_btn = QPushButton(t('desktop.cloudAI.execBtn'))
        self.quick_exec_btn.setFixedHeight(26)
        self.quick_exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_exec_btn.setToolTip(t('desktop.cloudAI.quickExecTooltip'))
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
        self.continue_send_btn = QPushButton(t('desktop.cloudAI.sendBtnLabel'))
        self.continue_send_btn.setToolTip(t('desktop.cloudAI.continueSendTooltip'))
        self.continue_send_btn.setFixedHeight(32)
        self.continue_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent_dim']}; color: white; border: none;
                border-radius: 4px; padding: 4px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1088e4; }}
        """)
        continue_layout.addWidget(self.continue_send_btn)

        h_layout.addWidget(continue_frame, 1)  # 右側に1/3幅

        main_layout.addLayout(h_layout)
        return frame

    def _connect_signals(self):
        """シグナルを接続"""
        self.send_btn.clicked.connect(self._on_send)
        # v8.3.2: new_session_btn削除 → CloudAIStatusBar.new_session_clicked で接続済み

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
        self.quick_yes_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.cloudAI.quickYesMsg')))
        self.quick_continue_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.cloudAI.quickContinueMsg')))
        self.quick_exec_btn.clicked.connect(lambda: self._send_continue_message(t('desktop.cloudAI.quickExecMsg')))
        self.continue_send_btn.clicked.connect(self._send_continue_from_input)

        # TODO: self.input_field の Ctrl+Enter ショートカットを接続

    # =========================================================================
    # v9.7.0: Chat History integration
    # =========================================================================

    def _toggle_history_panel(self):
        """チャット履歴パネルの表示切替"""
        if self.main_window and hasattr(self.main_window, 'toggle_chat_history'):
            self.main_window.toggle_chat_history(tab="cloudAI")

    def _save_chat_to_history(self, role: str, content: str):
        """チャットメッセージを履歴に保存"""
        if not self._chat_store:
            return
        try:
            if not self._active_chat_id:
                chat = self._chat_store.create_chat(tab="cloudAI")
                self._active_chat_id = chat["id"]
            self._chat_store.add_message(self._active_chat_id, role, content)
            # 最初のメッセージでタイトル自動生成
            chat = self._chat_store.get_chat(self._active_chat_id)
            if chat and chat.get("message_count", 0) == 1:
                self._chat_store.auto_generate_title(self._active_chat_id)
            # 履歴パネルをリフレッシュ
            if self.main_window and hasattr(self.main_window, 'chat_history_panel'):
                self.main_window.chat_history_panel.refresh_chat_list()
        except Exception as e:
            logger.debug(f"Failed to save chat to history: {e}")

    def load_chat_from_history(self, chat_id: str):
        """チャット履歴からチャットを読み込んで表示"""
        if not self._chat_store:
            return
        try:
            chat = self._chat_store.get_chat(chat_id)
            if not chat:
                return
            messages = self._chat_store.get_messages(chat_id)
            self._active_chat_id = chat_id
            self.chat_display.clear()
            for msg in messages:
                if msg["role"] == "user":
                    self.chat_display.append(f'<div style="background:#1a2233; border-left:3px solid #38bdf8; padding:8px; margin:4px 40px 4px 4px; border-radius:4px;"><b>You:</b> {msg["content"]}</div>')
                elif msg["role"] == "assistant":
                    self.chat_display.append(f'<div style="background:#131921; border-left:3px solid #34d399; padding:8px; margin:4px 4px 4px 40px; border-radius:4px;"><b>AI:</b> {msg["content"]}</div>')
            self.statusChanged.emit(t('desktop.cloudAI.chatLoaded', title=chat.get("title", "")))
        except Exception as e:
            logger.warning(f"Failed to load chat from history: {e}")

    def retranslateUi(self):
        """言語変更時に全UIテキストを再適用"""
        # === Chat tab ===
        if hasattr(self, 'chat_display'):
            self.chat_display.setPlaceholderText(t('desktop.cloudAI.chatReady'))

        # === Sub tabs ===
        self.sub_tabs.setTabText(0, t('desktop.cloudAI.chatSubTab'))
        self.sub_tabs.setTabText(1, t('desktop.cloudAI.settingsSubTab'))

        # === Settings tab - GroupBox titles ===
        self.api_group.setTitle(t('desktop.cloudAI.authGroup'))
        self.model_settings_group.setTitle(t('desktop.cloudAI.modelSettingsGroup'))
        self.mcp_options_group.setTitle(t('desktop.cloudAI.mcpAndOptionsGroup'))
        self.ollama_group.setTitle(t('desktop.cloudAI.ollamaSettingsGroup'))
        self.approval_group.setTitle(t('desktop.cloudAI.approvalScopesGroup'))

        # === Settings tab - Auth section ===
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

        # === Settings tab - Model settings section ===
        self.model_label.setText(t('desktop.cloudAI.soloModelLabel'))
        self.model_combo.setToolTip(t('desktop.cloudAI.modelReadonlyTooltip'))
        # v9.8.1: Refresh model combo display names for i18n
        if hasattr(self, 'model_combo'):
            for i in range(self.model_combo.count()):
                model_id = self.model_combo.itemData(i)
                if model_id == "gpt-5.3-codex":
                    # v9.9.2: Codex is not in CLAUDE_MODELS, translate separately
                    self.model_combo.setItemText(i, t('desktop.cloudAI.modelCodex53'))
                    continue
                model_def = get_claude_model_by_id(model_id)
                if model_def and model_def.get("i18n_display"):
                    self.model_combo.setItemText(i, t(model_def["i18n_display"]))
        # v11.0.0: effort_combo removed (hidden setting in config.json)
        self.solo_timeout_label.setText(t('desktop.cloudAI.soloTimeoutLabel'))
        # v9.8.1: Refresh timeout suffix for i18n
        if hasattr(self, 'solo_timeout_spin'):
            self.solo_timeout_spin.setSuffix(t('common.timeoutSuffix'))
        # v10.1.0: Browser Use checkbox (旧 search_mode_combo は削除)
        if hasattr(self, 'browser_use_checkbox'):
            self.browser_use_checkbox.setText(t('desktop.cloudAI.browserUseLabel'))
            self.browser_use_checkbox.setToolTip(t('desktop.cloudAI.browserUseTip'))

        # === Settings tab - MCP & options section ===
        self.mcp_checkbox.setText(t('desktop.cloudAI.soloMcpLabel'))
        self.mcp_checkbox.setToolTip(t('desktop.cloudAI.mcpCheckboxTooltip'))
        self.diff_checkbox.setText(t('desktop.cloudAI.diffCheckLabel'))
        self.diff_checkbox.setToolTip(t('desktop.cloudAI.diffCheckboxTooltip'))
        self.context_checkbox.setText(t('desktop.cloudAI.autoContextLabel'))
        self.context_checkbox.setToolTip(t('desktop.cloudAI.contextCheckboxTooltip'))
        self.permission_skip_checkbox.setText(t('desktop.cloudAI.permissionLabel'))
        self.permission_skip_checkbox.setToolTip(t('desktop.cloudAI.permissionSkipTooltip'))

        # === Settings tab - Ollama section ===
        self.ollama_url_label.setText(t('desktop.cloudAI.hostUrlLabel'))
        self.ollama_test_btn.setText(t('desktop.cloudAI.connTestBtn'))
        self.ollama_model_label.setText(t('desktop.cloudAI.useModelLabel'))
        self.settings_ollama_model.setPlaceholderText(t('desktop.cloudAI.ollamaModelPlaceholder'))
        self.refresh_models_btn.setText(t('desktop.cloudAI.refreshModelsBtn'))

        # === Settings tab - v10.1.0 cloudAI sections ===
        if hasattr(self, 'cli_section_group'):
            self.cli_section_group.setTitle(t('desktop.cloudAI.cliSection'))
        if hasattr(self, 'codex_section_group'):
            self.codex_section_group.setTitle(t('desktop.cloudAI.codexSection'))
        # v11.0.0: mixai_phase_group removed

        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        # === Input area ===
        self.input_field.setPlaceholderText(t('desktop.cloudAI.inputPlaceholder'))
        self.attach_btn.setText("📎 " + t('common.attach'))
        self.attach_btn.setToolTip(t('desktop.cloudAI.attachTooltip'))
        self.snippet_btn.setText(t('desktop.cloudAI.snippetBtnLabel'))
        self.snippet_btn.setToolTip(t('desktop.cloudAI.snippetTooltip'))
        self.send_btn.setText(t('desktop.cloudAI.sendBtnMain'))
        self.send_btn.setToolTip(t('desktop.cloudAI.sendTooltip'))
        # v11.0.0: BIBLE toggle button
        if hasattr(self, 'bible_btn'):
            self.bible_btn.setToolTip(t('desktop.common.bibleToggleTooltip'))
        # v11.0.0: Header title + model label
        if hasattr(self, 'cloud_header_title'):
            self.cloud_header_title.setText(t('desktop.cloudAI.headerTitle'))
        if hasattr(self, 'cloud_model_label'):
            self.cloud_model_label.setText(t('desktop.cloudAI.modelLabel'))
        if hasattr(self, 'cloud_refresh_btn'):
            self.cloud_refresh_btn.setText(t('desktop.cloudAI.refreshBtn'))

        # === 登録済みモデル管理ボタン (設定タブ) ===
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

        # === Continue area ===
        self.continue_header.setText(t('desktop.cloudAI.conversationContinueLabel'))
        self.continue_desc.setText(t('desktop.cloudAI.continueDesc'))
        self.continue_input.setPlaceholderText(t('desktop.cloudAI.continuePlaceholder'))
        self.quick_yes_btn.setText(t('desktop.cloudAI.quickYesLabel'))
        self.quick_yes_btn.setToolTip(t('desktop.cloudAI.quickYesTooltip'))
        self.quick_continue_btn.setText(t('desktop.cloudAI.continueBtn'))
        self.quick_continue_btn.setToolTip(t('desktop.cloudAI.quickContinueTooltip'))
        self.quick_exec_btn.setText(t('desktop.cloudAI.execBtn'))
        self.quick_exec_btn.setToolTip(t('desktop.cloudAI.quickExecTooltip'))
        self.continue_send_btn.setText(t('desktop.cloudAI.sendBtnLabel'))
        self.continue_send_btn.setToolTip(t('desktop.cloudAI.continueSendTooltip'))

        # === Approval panel ===
        self.approval_desc_label.setText(t('desktop.cloudAI.approvalPanelDesc'))
        self.approve_all_btn.setText(t('desktop.cloudAI.approveAllBtnLabel'))
        self.revoke_all_btn.setText(t('desktop.cloudAI.revokeAllBtnLabel'))

        # risk_approval_btn - dynamic text based on panel visibility
        if self.approval_panel.isVisible():
            self.risk_approval_btn.setText(t('desktop.cloudAI.riskApprovalClose'))
        else:
            self.risk_approval_btn.setText(t('desktop.cloudAI.riskApprovalOpen'))

        # v11.0.0: Chat header buttons
        if hasattr(self, 'advanced_settings_btn'):
            self.advanced_settings_btn.setText(t('desktop.cloudAI.advancedSettings'))
            self.advanced_settings_btn.setToolTip(t('desktop.cloudAI.advancedSettingsTooltip'))
        if hasattr(self, 'new_session_btn'):
            self.new_session_btn.setText(t('desktop.cloudAI.newSessionBtn'))
            self.new_session_btn.setToolTip(t('desktop.cloudAI.newSessionBtnTip'))
        # v11.0.0: Continue Send button
        if hasattr(self, 'continue_send_btn_main'):
            # Only update text if no session is active
            if not hasattr(self, '_claude_session_id') or self._claude_session_id is None:
                self.continue_send_btn_main.setText(t('desktop.cloudAI.continueSendMain'))
            self.continue_send_btn_main.setToolTip(t('desktop.cloudAI.continueSendMainTooltip'))
        # v11.0.0: MCP settings retranslation
        if hasattr(self, 'cloudai_mcp_group'):
            self.cloudai_mcp_group.setTitle(t('desktop.cloudAI.mcpSettings'))
        if hasattr(self, 'cloudai_mcp_filesystem'):
            self.cloudai_mcp_filesystem.setText(t('desktop.settings.mcpFilesystem'))
        if hasattr(self, 'cloudai_mcp_git'):
            self.cloudai_mcp_git.setText(t('desktop.settings.mcpGit'))
        if hasattr(self, 'cloudai_mcp_brave'):
            self.cloudai_mcp_brave.setText(t('desktop.settings.mcpBrave'))

        # Child widget retranslation
        if hasattr(self, 'solo_status_bar') and hasattr(self.solo_status_bar, 'retranslateUi'):
            self.solo_status_bar.retranslateUi()
        # v10.1.0: monitor widget retranslation
        if hasattr(self, 'monitor_widget') and hasattr(self.monitor_widget, 'retranslateUi'):
            self.monitor_widget.retranslateUi()

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
                    t('desktop.cloudAI.sendBlockTitle'),
                    f"{guard_message}\n\n{t('desktop.cloudAI.proceedWorkflowRetry')}"
                )
                return

            self._send_message(message)
            self.input_field.clear()

        except Exception as e:
            # 例外発生時もアプリは落とさない
            error_msg = f"{type(e).__name__}: {str(e)}"

            # app.log に ERROR レベルで記録
            logger.error(f"[ClaudeTab._on_send] Exception occurred: {error_msg}", exc_info=True)

            # v11.7.0: crash.log に記録（共通ヘルパー）
            from ..utils.error_utils import write_crash_log
            write_crash_log("ClaudeTab._on_send", e)

            # UIにエラー表示
            QMessageBox.critical(
                self,
                t('desktop.cloudAI.sendErrorTitle'),
                t('desktop.cloudAI.sendErrorMsg', error=error_msg)
            )

            self.statusChanged.emit(t('desktop.cloudAI.sendError', error=type(e).__name__))

    def _on_new_session(self):
        """新規セッション開始"""
        self._active_chat_id = None
        self.chat_display.clear()
        self.statusChanged.emit(t('desktop.cloudAI.newSessionStarted'))
        self.chat_display.setPlaceholderText(t('desktop.cloudAI.chatReady'))
        # v5.1: 添付ファイルもクリア
        self.attachment_bar.clear_all()
        self._attached_files.clear()
        # v10.1.0: モニターリセット
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.reset()
        # v11.0.0: Reset session for Continue Send
        self._claude_session_id = None
        if hasattr(self, 'continue_send_btn_main'):
            self.continue_send_btn_main.setEnabled(False)
            self.continue_send_btn_main.setText(t('desktop.cloudAI.continueSendMain'))

    def _on_continue_send_main(self):
        """v11.0.0: Continue send with session retention"""
        message = self.input_field.toPlainText().strip()
        if not message:
            return
        # Reuse existing send logic but with resume_session_id
        self._send_message_with_session(message)
        self.input_field.clear()

    def _send_message_with_session(self, message: str):
        """v11.0.0: Send message while retaining the CLI session (--resume)"""
        if not self._claude_session_id:
            logger.warning("[ClaudeTab] No session to resume, falling back to normal send")
            self._send_message(message)
            return

        # v11.7.0: logger_local を廃止、モジュールレベルの logger を使用

        # Display user message
        self.chat_display.append(
            f"<div style='{USER_MESSAGE_STYLE}'>"
            f"<b style='color:#38bdf8;'>{t('desktop.cloudAI.userPrefix')}</b><br>"
            f"{message.replace(chr(10), '<br>')}"
            f"</div>"
        )
        self._pending_user_message = message

        # Get model from header combo
        selected_model = self.cloud_model_combo.currentData() or self.model_combo.currentData() or ""

        import os
        working_dir = os.getcwd()
        skip_permissions = self.permission_skip_checkbox.isChecked()

        self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions, model=selected_model)

        self.statusChanged.emit(t('desktop.cloudAI.cliGenerating'))
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"[CLI Mode --resume {self._claude_session_id[:8]}...]"
            f"</div>"
        )

        self._cli_worker = CLIWorkerThread(
            backend=self._cli_backend,
            prompt=message,
            model=selected_model,
            working_dir=working_dir,
            resume_session_id=self._claude_session_id
        )
        self._cli_worker.chunkReceived.connect(self._on_cli_chunk)
        self._cli_worker.completed.connect(self._on_cli_response)
        self._cli_worker.errorOccurred.connect(self._on_cli_error)
        self._cli_worker.start()

        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.start_model(selected_model or "Claude CLI", "CLI --resume")

        logger.info(f"[ClaudeTab] Sent with --resume session: {self._claude_session_id[:8]}...")

    def _on_session_captured(self, session_id: str):
        """v11.0.0: Session ID received from CLI"""
        self._claude_session_id = session_id
        if hasattr(self, 'continue_send_btn_main'):
            self.continue_send_btn_main.setEnabled(True)
            short_id = session_id[:8]
            self.continue_send_btn_main.setText(
                f"{t('desktop.cloudAI.continueSendMain')} ({short_id}...)"
            )
        logger.info(f"[ClaudeTab] Session captured: {session_id}")

    def _on_stall_detected(self, message: str):
        """v10.1.0: ストール検出時のステータスバー通知"""
        self.statusChanged.emit(message)

    def _auto_scroll_chat(self):
        """v10.1.0: チャット表示のオートスクロール（新メッセージ追加時に最下部へ）"""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # =========================================================================
    # v5.1: ファイル添付関連メソッド
    # =========================================================================

    def _on_attach_file(self):
        """ファイル添付ボタンクリック"""
        from PyQt6.QtWidgets import QFileDialog
        import logging
        logger = logging.getLogger(__name__)

        files, _ = QFileDialog.getOpenFileNames(
            self, t('desktop.cloudAI.selectFileTitle'), "",
            t('desktop.cloudAI.fileFilterAll')
        )
        if files:
            self.attachment_bar.add_files(files)
            logger.info(f"[ClaudeTab] Attached {len(files)} files")

    def _on_attachments_changed(self, files: list):
        """添付ファイルリストが変更された"""
        import logging
        logger = logging.getLogger(__name__)
        self._attached_files = files.copy()
        has_attachments = len(files) > 0
        self.attachment_bar.setVisible(has_attachments)
        self.attachment_bar.setMaximumHeight(16777215 if has_attachments else 0)
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
                self.statusChanged.emit(t('desktop.cloudAI.citationInserted'))
                logger.info("[ClaudeTab] Citation inserted from history")

        except Exception as e:
            logger.error(f"[ClaudeTab._on_citation] Error: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                t('desktop.cloudAI.citationErrorTitle'),
                t('desktop.cloudAI.citationErrorMsg', error=str(e))
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
        unipet_dir = app_dir / "snippets"

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
                no_snippet_action = menu.addAction(t('desktop.cloudAI.noSnippetsMsg'))
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
                        action = cat_menu.addAction(snippet.get("name", t('desktop.cloudAI.untitled')))
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

                # カテゴリなしスニペット
                if uncategorized:
                    if categories:
                        menu.addSeparator()
                    for snippet in uncategorized:
                        action = menu.addAction(f"📋 {snippet.get('name', t('desktop.cloudAI.untitled'))}")
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

            menu.addSeparator()
            # v11.0.0: 追加アクションをメニュー内に統合
            add_action = menu.addAction(t('desktop.cloudAI.snippetAddBtnLabel'))
            add_action.triggered.connect(self._on_snippet_add)

            open_folder_action = menu.addAction(t('desktop.cloudAI.openUnipetFolder'))
            open_folder_action.triggered.connect(lambda: snippet_manager.open_unipet_folder())

            # ボタンの下に表示
            btn_pos = self.snippet_btn.mapToGlobal(QPoint(0, self.snippet_btn.height()))
            menu.exec(btn_pos)

        except Exception as e:
            logger.error(f"[ClaudeTab._on_snippet_menu] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.cloudAI.snippetMenuError', error=str(e)))

    def _insert_snippet(self, snippet: dict):
        """スニペットを入力欄に挿入 (v3.7.0)"""
        import logging
        logger = logging.getLogger(__name__)

        content = snippet.get("content", "")
        name = snippet.get("name", t('desktop.cloudAI.untitled'))

        current_text = self.input_field.toPlainText()
        if current_text:
            new_text = f"{current_text}\n\n{content}"
        else:
            new_text = content

        self.input_field.setPlainText(new_text)
        self.statusChanged.emit(t('desktop.cloudAI.snippetInserted', name=name))
        logger.info(f"[ClaudeTab] Snippet inserted: {name}")

    def _on_snippet_add(self):
        """カスタムスニペット追加ダイアログ (v3.7.0)"""
        import logging
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox
        logger = logging.getLogger(__name__)

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(t('desktop.cloudAI.snippetAddDialogTitle'))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.cloudAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit()
            name_input.setPlaceholderText(t('desktop.cloudAI.snippetNamePlaceholder'))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.cloudAI.snippetCategoryLabel'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit()
            cat_input.setPlaceholderText(t('desktop.cloudAI.snippetCategoryPlaceholder'))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.cloudAI.snippetContentLabel'))
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlaceholderText(t('desktop.cloudAI.snippetContentPlaceholder'))
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
                    QMessageBox.warning(self, t('desktop.cloudAI.inputError'), t('desktop.cloudAI.nameContentRequired'))
                    return

                category = cat_input.text().strip()
                snippet_manager = self._get_snippet_manager()
                snippet_manager.add(name=name, content=content, category=category)

                self.statusChanged.emit(t('desktop.cloudAI.snippetAdded', name=name))
                logger.info(f"[ClaudeTab] Snippet added: {name}")

        except Exception as e:
            logger.error(f"[ClaudeTab._on_snippet_add] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.cloudAI.snippetAddError', error=str(e)))

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
            edit_menu = menu.addMenu(t('desktop.cloudAI.editMenuItem'))
            for snippet in snippets:
                action = edit_menu.addAction(snippet.get("name", t('desktop.cloudAI.untitled')))
                action.triggered.connect(lambda checked, s=snippet: self._edit_snippet(s))

            # 削除メニュー (v5.2.0: ユニペットも削除可能に)
            delete_menu = menu.addMenu(t('desktop.cloudAI.deleteMenuItem'))
            for snippet in snippets:
                source = snippet.get("source", "json")
                if source == "unipet":
                    action = delete_menu.addAction(f"🗂️ {snippet.get('name', t('desktop.cloudAI.untitled'))} {t('desktop.cloudAI.fileDeleteSuffix')}")
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))
                else:
                    action = delete_menu.addAction(snippet.get("name", t('desktop.cloudAI.untitled')))
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))

            menu.addSeparator()
            reload_action = menu.addAction(t('desktop.cloudAI.reloadMenuItem'))
            reload_action.triggered.connect(lambda: (self._get_snippet_manager().reload(), self.statusChanged.emit(t('desktop.cloudAI.snippetReloaded'))))

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
            dialog.setWindowTitle(t('desktop.cloudAI.snippetEditDialogTitle', name=snippet.get('name', t('desktop.cloudAI.untitled'))))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.cloudAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit(snippet.get("name", ""))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.cloudAI.categoryLabel2'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit(snippet.get("category", ""))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.cloudAI.snippetContentLabel'))
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
                self.statusChanged.emit(t('desktop.cloudAI.snippetUpdated', name=name_input.text()))
                logger.info(f"[ClaudeTab] Snippet updated: {name_input.text()}")

        except Exception as e:
            logger.error(f"[ClaudeTab._edit_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.cloudAI.snippetEditError', error=str(e)))

    def _delete_snippet(self, snippet: dict):
        """スニペット削除 (v5.2.0: ユニペットファイル削除対応)"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            name = snippet.get("name", t('desktop.cloudAI.untitled'))
            is_unipet = snippet.get("source") == "unipet"

            # ユニペットの場合は警告を追加
            if is_unipet:
                file_path = snippet.get("file_path", "")
                msg = t('desktop.cloudAI.deleteUnipetConfirm', name=name, file_path=file_path)
            else:
                msg = t('desktop.cloudAI.deleteSnippetConfirm', name=name)

            reply = QMessageBox.question(
                self, t('desktop.cloudAI.confirmTitle'),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                snippet_manager = self._get_snippet_manager()
                # ユニペットの場合はdelete_file=Trueを渡す
                if snippet_manager.delete(snippet.get("id"), delete_file=is_unipet):
                    self.statusChanged.emit(t('desktop.cloudAI.snippetDeleted', name=name))
                    logger.info(f"[ClaudeTab] Snippet deleted: {name}")
                else:
                    QMessageBox.warning(self, t('desktop.cloudAI.deleteFailed'), t('desktop.cloudAI.snippetDeleteError'))

        except Exception as e:
            logger.error(f"[ClaudeTab._delete_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.cloudAI.snippetDeleteGenericError', error=str(e)))

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
                    self, t('desktop.cloudAI.ragBuildTitle'),
                    t('desktop.cloudAI.ragBuildInProgressMsg')
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

            # v8.1.0: 記憶コンテキスト注入 (cloudAI)
            if self._memory_manager:
                try:
                    memory_ctx = self._memory_manager.build_context_for_solo(message)
                    if memory_ctx:
                        processed_message = f"<memory_context>\n{memory_ctx}\n</memory_context>\n\n{processed_message}"
                        logger.info("[ClaudeTab._send_message] Memory context injected for cloudAI")
                except Exception as mem_err:
                    logger.warning(f"[ClaudeTab._send_message] Memory context injection failed: {mem_err}")

            # v8.1.0: 送信時のユーザークエリを保持（Memory Risk Gate用）
            self._last_user_query = message

        except Exception as e:
            # 送信前の状態ガードで例外が発生した場合
            logger.error(f"[ClaudeTab._send_message] Exception during state guard: {e}", exc_info=True)

            # v11.7.0: crash.log に記録（共通ヘルパー）
            from ..utils.error_utils import write_crash_log
            write_crash_log("ClaudeTab._send_message:state_guard", e)

            # UIにエラー表示
            QMessageBox.critical(
                self,
                t('desktop.cloudAI.preSubmitErrorTitle'),
                t('desktop.cloudAI.preSubmitCheckError', error=f"{type(e).__name__}: {str(e)}")
            )

            self.statusChanged.emit(t('desktop.cloudAI.sendPrepError', error=type(e).__name__))
            return

        try:
            # テンプレが付与された場合は通知
            if template_applied:
                self.statusChanged.emit(t('desktop.cloudAI.templateApplied', name=template_name))
                self.chat_display.append(
                    f"<div style='color: #ffa500; font-size: 9pt;'>"
                    f"{t('desktop.cloudAI.templateAppliedMsg', template=template_name)}"
                    f"</div>"
                )

            # v8.0.0: ユーザーメッセージをバブルスタイルで表示（添付ファイル名付き）
            attachment_html = ""
            if hasattr(self, '_attached_files') and self._attached_files:
                file_chips = ''.join(
                    f'<span style="background:#1a2233;border:1px solid #38bdf8;'
                    f'border-radius:4px;padding:2px 8px;margin:2px 4px 2px 0;'
                    f'font-size:11px;color:#38bdf8;display:inline-block;">'
                    f'{os.path.basename(f)}</span>'
                    for f in self._attached_files
                )
                attachment_html = f'<div style="margin-bottom:6px;">{file_chips}</div>'
            self.chat_display.append(
                f"<div style='{USER_MESSAGE_STYLE}'>"
                f"<b style='color:#38bdf8;'>{t('desktop.cloudAI.userPrefix')}</b><br>"
                f"{attachment_html}"
                f"{message.replace(chr(10), '<br>')}"
                f"</div>"
            )

            # 履歴保存用に元のメッセージを保持
            self._pending_user_message = message

            # v11.0.0: JSONL logging (user message)
            try:
                from ..utils.chat_logger import get_chat_logger
                chat_logger = get_chat_logger()
                chat_logger.log_message(
                    tab="cloudAI",
                    model=self.model_combo.currentData() or "unknown",
                    role="user",
                    content=message[:2000],
                )
            except Exception:
                pass

            # v11.5.0: provider ベースルーティング
            auth_mode = self.auth_mode_combo.currentIndex()  # 0=Auto, 1=CLI, 2=API, 3=Ollama
            model_id, provider = self._get_selected_model_provider()

            # v10.1.0: Browser Use 事前収集
            if hasattr(self, 'browser_use_checkbox') and self.browser_use_checkbox.isChecked():
                processed_message = self._prepend_browser_use_results(processed_message)

            # v11.0.0: BIBLE context injection
            if hasattr(self, 'bible_btn') and self.bible_btn.isChecked():
                from ..mixins.bible_context_mixin import BibleContextMixin
                mixin = BibleContextMixin()
                processed_message = mixin._inject_bible_to_prompt(processed_message)

            # Ollama モード（auth_mode=3）
            if auth_mode == 3 and hasattr(self, '_use_ollama_mode') and self._use_ollama_mode:
                ollama_model = getattr(self, '_ollama_model', '') or self._auto_select_ollama_model()
                ollama_url = getattr(self, '_ollama_url', 'http://localhost:11434')
                if not ollama_model:
                    self.chat_display.append(
                        "<div style='color: #fbbf24; padding: 8px; border: 1px solid #fbbf24; "
                        "border-radius: 4px;'>" + t('desktop.cloudAI.noModelsConfigured') + "</div>"
                    )
                    return
                logger.info(f"[ClaudeTab._send_message] Ollama mode: model={ollama_model}")
                self._send_via_ollama(processed_message, ollama_url, ollama_model)
                return

            # モデル未設定チェック
            if not model_id:
                self.chat_display.append(
                    "<div style='color: #fbbf24; padding: 8px; border: 1px solid #fbbf24; "
                    "border-radius: 4px;'>" + t('desktop.cloudAI.noModelsConfigured') + "</div>"
                )
                return

            # provider 別ルーティング
            from ..backends.api_priority_resolver import (
                resolve_anthropic_connection, resolve_openai_connection, ConnectionMode
            )

            if provider == "anthropic_api":
                method, kwargs = resolve_anthropic_connection(ConnectionMode.API_ONLY)
                if method == "anthropic_api":
                    self._send_via_anthropic_api(processed_message, session_id, kwargs["api_key"], model_id=model_id)
                else:
                    self.chat_display.append(
                        f"<div style='color: #ef4444;'>&#10060; {kwargs.get('reason', 'Anthropic API key not configured')}</div>"
                    )

            elif provider == "openai_api":
                method, kwargs = resolve_openai_connection(ConnectionMode.API_ONLY)
                if method == "openai_api":
                    self._send_via_openai_api(processed_message, session_id, kwargs["api_key"], model_id=model_id)
                else:
                    self.chat_display.append(
                        f"<div style='color: #ef4444;'>&#10060; {kwargs.get('reason', 'OpenAI API key not configured')}</div>"
                    )

            elif provider == "anthropic_cli":
                self._send_via_cli(processed_message, session_id, phase)

            elif provider == "google_api":
                from ..backends.api_priority_resolver import resolve_google_connection
                method, kwargs = resolve_google_connection(ConnectionMode.API_ONLY)
                if method == "google_api":
                    self._send_via_google_api(processed_message, session_id, kwargs["api_key"], model_id=model_id)
                else:
                    self.chat_display.append(
                        f"<div style='color: #ef4444;'>&#10060; {kwargs.get('reason', 'Google API key not configured')}</div>"
                    )

            elif provider == "openai_cli":
                self._send_via_codex(processed_message, session_id)

            elif provider == "google_cli":
                self._send_via_google_cli(processed_message, session_id, model_id=model_id)

            else:
                # v11.5.1: unknown provider → ユーザーガイド表示
                guide_msg = t('desktop.cloudAI.unknownProviderGuide').format(model_id=model_id)
                self.chat_display.append(
                    f"<div style='color: #fbbf24; padding: 8px; border: 1px solid #fbbf24; "
                    f"border-radius: 4px;'>&#9888; {guide_msg}</div>"
                )

        except Exception as e:
            # 送信処理中に例外が発生した場合
            error_msg = f"{type(e).__name__}: {str(e)}"

            logger.error(f"[ClaudeTab._send_message] Exception during send: {error_msg}", exc_info=True)

            # v11.7.0: crash.log に記録（共通ヘルパー）
            from ..utils.error_utils import write_crash_log
            write_crash_log("ClaudeTab._send_message:send", e)

            # UIにエラー表示
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.cloudAI.sendErrorHtml')}</b><br>"
                f"{error_msg}<br><br>"
                f"{t('desktop.cloudAI.crashLogDetail')}"
                f"</div>"
            )

            self.statusChanged.emit(t('desktop.cloudAI.sendError', error=type(e).__name__))

    # =========================================================================
    # v9.9.1: Codex CLI モード
    # =========================================================================

    # =========================================================================
    # v11.5.0 L-G: Google Gemini 送信
    # =========================================================================

    def _send_via_google_api(self, prompt: str, session_id: str, api_key: str, model_id: str = None):
        """v11.5.0 L-G: Google Gemini API 経由でストリーミング送信"""
        import threading
        from ..backends.google_api_backend import call_google_api_stream, is_google_genai_sdk_available

        if not is_google_genai_sdk_available():
            self.chat_display.append(
                "<div style='color: #ef4444;'>google-genai SDK not installed.<br>"
                "Run: <code>pip install google-genai</code></div>"
            )
            return

        if not model_id:
            model_id = self._get_first_model_by_provider("google_api") or "gemini-2.5-flash"

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ClaudeTab._send_via_google_api] model={model_id}")
        self.statusChanged.emit(f"Google Gemini API ({model_id})...")
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>[Gemini API: {model_id}]</div>"
        )

        def _on_done(full_text, error, sid):
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("idle")
            if error:
                self.chat_display.append(
                    f"<div style='color: #ef4444;'><b>Gemini API Error:</b> {error}</div>"
                )
            else:
                self._display_ai_response(full_text, model_id, "google_api")

        def _thread_run():
            full_text = ""
            error = ""
            try:
                for chunk in call_google_api_stream(
                    prompt=prompt,
                    model_id=model_id,
                    api_key=api_key,
                ):
                    full_text += chunk
                    if self._streaming_callback_enabled and hasattr(self, '_on_cli_chunk'):
                        from PyQt6.QtCore import QMetaObject, Qt
                        QMetaObject.invokeMethod(
                            self.chat_display, "append",
                            Qt.ConnectionType.QueuedConnection,
                        )
            except Exception as e:
                error = str(e)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _on_done(full_text, error, session_id))

        self._streaming_callback_enabled = False  # Gemini はバッチ表示
        threading.Thread(target=_thread_run, daemon=True).start()

    def _send_via_google_cli(self, prompt: str, session_id: str, model_id: str = None):
        """v11.5.0 L-G: Google Gemini CLI 経由で送信（非対話モード）"""
        import threading
        import shutil

        if not shutil.which("gemini"):
            self.chat_display.append(
                "<div style='color: #ef4444;'>"
                "Gemini CLI not found.<br>"
                "Install: <code>npm install -g @google/gemini-cli</code>"
                "</div>"
            )
            return

        if not model_id:
            model_id = self._get_first_model_by_provider("google_cli") or "gemini-2.5-flash"

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ClaudeTab._send_via_google_cli] model={model_id}")
        self.statusChanged.emit(f"Gemini CLI ({model_id})...")
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        timeout_sec = self.solo_timeout_spin.value() * 60 if hasattr(self, 'solo_timeout_spin') else 300

        def _thread_run():
            import subprocess, json as _json, os as _os
            full_text = ""
            error = ""
            try:
                env = _os.environ.copy()
                if not env.get("GEMINI_API_KEY") and not env.get("GOOGLE_API_KEY"):
                    from ..backends.google_api_backend import get_google_api_key
                    key = get_google_api_key()
                    if key:
                        env["GEMINI_API_KEY"] = key

                cmd = ["gemini", "-p", prompt, "--model", model_id, "--yolo"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_sec, env=env,
                )
                full_text = result.stdout.strip()
                if result.returncode != 0 and not full_text:
                    error = result.stderr or f"Gemini CLI returned code {result.returncode}"
            except subprocess.TimeoutExpired:
                error = f"Gemini CLI timeout ({timeout_sec}s)"
            except Exception as e:
                error = str(e)

            def _on_done():
                if hasattr(self, 'solo_status_bar'):
                    self.solo_status_bar.set_status("idle" if not error else "error")
                if error:
                    self.chat_display.append(
                        f"<div style='color: #ef4444;'><b>Gemini CLI Error:</b> {error}</div>"
                    )
                elif full_text:
                    self._display_ai_response(full_text, model_id, "google_cli")

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, _on_done)

        threading.Thread(target=_thread_run, daemon=True).start()

    _codex_response_ready = pyqtSignal(str, str)   # (response_text, session_id)
    _codex_error_ready = pyqtSignal(str)            # (error_message)

    def _send_via_codex(self, prompt: str, session_id: str):
        """v9.9.1: GPT-5.3-Codex CLI経由で送信 (v11.0.0: Windows .cmd対応)"""
        import threading

        # Codex CLI可用性チェック（v11.0.0: check_codex_cli_available使用）
        from ..backends.codex_cli_backend import check_codex_cli_available
        codex_available, _ = check_codex_cli_available()

        if not codex_available:
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:#ef4444;'>{t('desktop.cloudAI.codexUnavailableTitle')}</b><br>"
                f"{t('desktop.cloudAI.codexUnavailableMsg')}"
                f"</div>"
            )
            self.statusChanged.emit(t('desktop.cloudAI.codexUnavailable'))
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("error")
            return

        self.statusChanged.emit(t('desktop.cloudAI.codexGenerating'))
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        gpt_effort = "default"
        import os
        working_dir = os.getcwd()
        timeout_sec = self.solo_timeout_spin.value() * 60 if hasattr(self, 'solo_timeout_spin') else 600

        # シグナルが未接続の場合は接続
        try:
            self._codex_response_ready.disconnect()
        except Exception:
            pass
        try:
            self._codex_error_ready.disconnect()
        except Exception:
            pass
        self._codex_response_ready.connect(self._on_codex_response)
        self._codex_error_ready.connect(self._on_codex_error)
        self._codex_current_session_id = session_id

        def _run():
            try:
                from ..backends.codex_cli_backend import run_codex_cli
                output = run_codex_cli(prompt, effort=gpt_effort, run_cwd=working_dir, timeout=timeout_sec)
                self._codex_response_ready.emit(output, session_id)
            except Exception as e:
                self._codex_error_ready.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_codex_response(self, response_text: str, session_id: str):
        """v9.9.1: Codex CLI応答処理"""
        rendered = markdown_to_html(response_text)
        self.chat_display.append(
            f"<div style='{AI_MESSAGE_STYLE}'>"
            f"<b style='color:#fbbf24;'>GPT-5.3-Codex (CLI):</b><br>"
            f"{rendered}"
            f"</div>"
        )
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("idle")
        self.statusChanged.emit(t('desktop.cloudAI.codexComplete'))

    def _on_codex_error(self, error_msg: str):
        """v9.9.1: Codex CLIエラー処理"""
        self.chat_display.append(
            f"<div style='{AI_MESSAGE_STYLE}'>"
            f"<b style='color:#ef4444;'>Codex Error:</b><br>"
            f"{error_msg[:500]}"
            f"</div>"
        )
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("error")
        self.statusChanged.emit(t('desktop.cloudAI.codexError'))

    def _prepend_browser_use_results(self, prompt: str) -> str:
        """v11.3.0: URL自動取得（httpx ベース）。プロンプト先頭に URL 内容を注入。

        browser_use パッケージ不要。Claude CLI / Codex CLI / Ollama すべてで動作する。
        JS レンダリングが必要なページには localAI の browser_use ツールを使用すること。
        """
        try:
            import re
            import httpx
            urls = re.findall(r'https?://[^\s\'"<>]+', prompt)
            if not urls:
                return prompt
            results = []
            max_chars = getattr(self, '_search_max_chars', 6000)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; HelixAI/1.0)"}
            for url in urls[:3]:
                try:
                    resp = httpx.get(url, timeout=15, follow_redirects=True, headers=headers)
                    resp.raise_for_status()
                    text = resp.text
                    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<[^>]+>', '', text)
                    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text:
                        results.append(f"[{url}]\n{text[:2000]}")
                except Exception as e:
                    logger.debug(f"URL fetch failed for {url}: {e}")
            if results:
                combined = "\n\n".join(results)
                if len(combined) > max_chars:
                    combined = combined[:max_chars] + "\n\n... [truncated]"
                return f"<url_contents>\n{combined}\n</url_contents>\n\n{prompt}"
        except Exception as e:
            logger.warning(f"URL fetch failed: {e}")
        return prompt

    # =========================================================================

    def _send_via_anthropic_api(self, prompt: str, session_id: str, api_key: str, model_id: str = None):
        """v11.5.0: Anthropic Direct API 経由で送信（ストリーミング）"""
        import threading
        from ..backends.anthropic_api_backend import call_anthropic_api_stream, is_anthropic_sdk_available

        if not is_anthropic_sdk_available():
            logger.warning("[ClaudeTab] anthropic SDK not installed")
            self.chat_display.append(
                "<div style='color: #ef4444;'>Anthropic SDK not installed. Run: pip install anthropic</div>"
            )
            return

        if not model_id:
            model_id = self._get_first_model_by_provider("anthropic_api")
        logger.info(f"[ClaudeTab._send_via_anthropic_api] model={model_id}")

        self.statusChanged.emit(f"Anthropic API ({model_id})...")
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>[API Mode: {model_id}]</div>"
        )

        def _on_done(full_text, error, sid):
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("idle")
            if error:
                self.chat_display.append(
                    f"<div style='color: #ef4444;'><b>API Error:</b> {error}</div>"
                )
            else:
                if hasattr(self, '_chat_logger') and self._chat_logger:
                    try:
                        self._chat_logger.log_exchange(
                            user_msg=getattr(self, '_last_user_message', ''),
                            ai_msg=full_text,
                            model=model_id,
                            method="anthropic_api",
                        )
                    except Exception:
                        pass

        def _thread_run():
            full_text = ""
            error = ""
            try:
                for chunk in call_anthropic_api_stream(
                    prompt=prompt,
                    model_id=model_id,
                    api_key=api_key,
                ):
                    full_text += chunk
                    # CLI chunk handler を流用してストリーミング表示
                    if hasattr(self, '_on_cli_chunk'):
                        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                        QMetaObject.invokeMethod(
                            self, "_on_cli_chunk_invoke",
                            Qt.ConnectionType.QueuedConnection,
                            Q_ARG(str, chunk)
                        )
            except Exception as e:
                error = str(e)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _on_done(full_text, error, session_id))

        threading.Thread(target=_thread_run, daemon=True).start()

    def _send_via_openai_api(self, prompt: str, session_id: str, api_key: str, model_id: str = None):
        """v11.5.0: OpenAI Direct API 経由で送信（ストリーミング）"""
        import threading
        from ..backends.openai_api_backend import call_openai_api_stream, is_openai_sdk_available

        if not is_openai_sdk_available():
            logger.warning("[ClaudeTab] openai SDK not installed")
            self.chat_display.append(
                "<div style='color: #ef4444;'>OpenAI SDK not installed. Run: pip install openai</div>"
            )
            return

        if not model_id:
            model_id = self._get_first_model_by_provider("openai_api") or "gpt-4o"
        logger.info(f"[ClaudeTab._send_via_openai_api] model={model_id}")

        self.statusChanged.emit(f"OpenAI API ({model_id})...")
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>[OpenAI API Mode: {model_id}]</div>"
        )

        def _on_done(full_text, error, sid):
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("idle")
            if error:
                self.chat_display.append(
                    f"<div style='color: #ef4444;'><b>API Error:</b> {error}</div>"
                )
            else:
                if hasattr(self, '_chat_logger') and self._chat_logger:
                    try:
                        self._chat_logger.log_exchange(
                            user_msg=getattr(self, '_last_user_message', ''),
                            ai_msg=full_text,
                            model=model_id,
                            method="openai_api",
                        )
                    except Exception:
                        pass

        def _thread_run():
            full_text = ""
            error = ""
            try:
                for chunk in call_openai_api_stream(
                    prompt=prompt,
                    model_id=model_id,
                    api_key=api_key,
                ):
                    full_text += chunk
            except Exception as e:
                error = str(e)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _on_done(full_text, error, session_id))

        threading.Thread(target=_thread_run, daemon=True).start()

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
            error_msg = t('desktop.cloudAI.cliUnavailableInstructions')
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.cloudAI.cliUnavailableHtml')}</b><br>"
                f"{error_msg}"
                f"</div>"
            )
            self.statusChanged.emit(t('desktop.cloudAI.cliUnavailable'))
            logger.error(f"[ClaudeTab._send_via_cli] CLI not available: {self._cli_backend.get_availability_message() if self._cli_backend else 'Backend is None'}")
            return

        # v7.1.0: モデル選択とフォールバック準備
        model_text = self.model_combo.currentText()
        selected_model = self.model_combo.currentData() or model_text
        self._cli_selected_model = model_text  # フォールバック用に保存
        self._cli_prompt = prompt  # フォールバック用に保存
        self._cli_session_id = session_id
        self._cli_phase = phase

        # 作業ディレクトリを取得（プロジェクトディレクトリ）
        import os
        working_dir = os.getcwd()

        # ステータス表示
        self.statusChanged.emit(t('desktop.cloudAI.cliGenerating'))
        # v8.0.0: CloudAIStatusBar更新
        if hasattr(self, 'solo_status_bar'):
            self.solo_status_bar.set_status("running")

        # 認証モード情報をチャットに表示
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"[CLI Mode]"
            f"</div>"
        )

        # v3.5.0: 権限スキップ設定を取得
        skip_permissions = self.permission_skip_checkbox.isChecked()

        # v7.1.0: selected_model は currentData() で取得済み
        logger.info(f"[ClaudeTab._send_via_cli] Starting CLI request: model={selected_model}, working_dir={working_dir}, skip_permissions={skip_permissions}")

        # CLIバックエンドへの参照を取得 (v3.5.0: 権限スキップ設定, v3.9.4: モデル選択を渡す)
        self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions, model=selected_model)

        # CLIWorkerThreadで非同期実行
        self._cli_worker = CLIWorkerThread(
            backend=self._cli_backend,
            prompt=prompt,
            model=selected_model,  # v3.9.4: モデルを渡す
            working_dir=working_dir,
        )
        self._cli_worker.chunkReceived.connect(self._on_cli_chunk)
        self._cli_worker.completed.connect(self._on_cli_response)
        self._cli_worker.errorOccurred.connect(self._on_cli_error)
        self._cli_worker.start()

        # v10.1.0: モニター開始
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.start_model(selected_model or "Claude CLI", "CLI")

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
                f"<b style='color:#34d399;'>Claude CLI (Max/Pro):</b><br>"
                f"{rendered}"
                f"</div>"
            )

            # v11.0.0: Capture session ID for Continue Send
            if response.metadata and response.metadata.get("session_id"):
                self._on_session_captured(response.metadata["session_id"])

            logger.info(
                f"[ClaudeTab._on_cli_response] CLI response: "
                f"duration={response.duration_ms:.2f}ms, tokens={response.tokens_used}"
            )

            # コスト表示（Max/Proプランは基本無料、Extra Usage超過時のみ課金）
            self.statusChanged.emit(
                t('desktop.cloudAI.cliResponseComplete', duration=f"{response.duration_ms:.0f}")
            )

            # v11.0.0: JSONL logging (assistant response)
            try:
                from ..utils.chat_logger import get_chat_logger
                chat_logger = get_chat_logger()
                chat_logger.log_message(
                    tab="cloudAI",
                    model=self.model_combo.currentData() or "unknown",
                    role="assistant",
                    content=response.response_text[:2000],
                    duration_ms=response.duration_ms,
                )
            except Exception:
                pass

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
                            "auth_mode": t('desktop.cloudAI.authModeCli')
                        }
                    )
                    logger.info(f"[ClaudeTab._on_cli_response] Chat history saved: entry_id={entry.id}")
                    self._pending_user_message = None
                except Exception as hist_error:
                    logger.error(f"[ClaudeTab._on_cli_response] Failed to save chat history: {hist_error}", exc_info=True)

            # v8.1.0: Memory Risk Gate (cloudAI CLI応答後)
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
                    logger.info("[ClaudeTab._on_cli_response] Memory Risk Gate completed (cloudAI-CLI)")
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

            # v8.0.0: CloudAIStatusBar - 完了
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("completed")

            # v10.1.0: モニター完了
            if hasattr(self, 'monitor_widget'):
                self.monitor_widget.finish_model(
                    self._cli_selected_model if hasattr(self, '_cli_selected_model') else "Claude CLI",
                    success=True)

        else:
            # 失敗時: エラーメッセージを表示
            error_type = response.error_type or "CLIError"
            error_text = response.response_text.lower()
            # v8.0.0: CloudAIStatusBar - エラー
            if hasattr(self, 'solo_status_bar'):
                self.solo_status_bar.set_status("error")

            # v10.1.0: モニターエラー
            if hasattr(self, 'monitor_widget'):
                self.monitor_widget.finish_model(
                    self._cli_selected_model if hasattr(self, '_cli_selected_model') else "Claude CLI",
                    success=False)

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
                    f"<b>{t('desktop.cloudAI.haikuUnavailableHtml')}</b><br>"
                    f"{t('desktop.cloudAI.modelNotAvailableMsg').replace(chr(10), '<br>')}"
                    f"</div>"
                )

                self.statusChanged.emit(t('desktop.cloudAI.fallbackSonnet'))

                # 再送信
                if hasattr(self, '_cli_prompt') and self._cli_prompt:
                    self._send_via_cli(self._cli_prompt, self._cli_session_id, self._cli_phase)
                return

            # フォールバック対象外のエラー
            self._pending_user_message = None

            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.cloudAI.cliErrorHtml', error_type=error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"[ClaudeTab._on_cli_response] CLI error: type={error_type}, "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(t('desktop.cloudAI.cliError', error=error_type))

    def _on_cli_error(self, error_msg: str):
        """CLI実行エラー発生時"""
        import logging
        logger = logging.getLogger(__name__)

        logger.error(f"[ClaudeTab._on_cli_error] {error_msg}")

        self.chat_display.append(
            f"<div style='color: #ef4444; margin-top: 10px;'>"
            f"<b>{t('desktop.cloudAI.cliExecErrorHtml')}</b><br>"
            f"{error_msg}"
            f"</div>"
        )

        self.statusChanged.emit(t('desktop.cloudAI.cliError', error=error_msg[:50]))

        # v10.1.0: モニターエラー
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.finish_model(
                self._cli_selected_model if hasattr(self, '_cli_selected_model') else "Claude CLI",
                success=False)

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
        self.statusChanged.emit(t('desktop.cloudAI.ollamaGenerating', model=ollama_model, mcp=mcp_status))

        # 認証モード情報をチャットに表示
        mcp_tools = []
        if mcp_enabled:
            if mcp_settings.get("filesystem"):
                mcp_tools.append(t('desktop.cloudAI.fileOps'))
            if mcp_settings.get("brave-search"):
                mcp_tools.append(t('desktop.cloudAI.webSearch'))

        tools_text = t('desktop.cloudAI.toolsPrefix', tools=', '.join(mcp_tools)) if mcp_tools else ""
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
        self.statusChanged.emit(t('desktop.cloudAI.toolExecution', tool=tool_name, status=status))

    def _on_ollama_response(self, response_text: str, duration_ms: float):
        """Ollama応答受信時 (v3.9.2)"""
        import logging
        logger = logging.getLogger(__name__)

        ollama_model = getattr(self, '_ollama_model', 'ollama')

        # 応答を表示（Markdown→HTMLレンダリング + バブルスタイル）
        rendered = markdown_to_html(response_text)
        self.chat_display.append(
            f"<div style='{AI_MESSAGE_STYLE}'>"
            f"<b style='color:#34d399;'>{ollama_model} (Ollama):</b><br>"
            f"{rendered}"
            f"</div>"
        )

        logger.info(f"[ClaudeTab._on_ollama_response] Ollama response: duration={duration_ms:.2f}ms")

        self.statusChanged.emit(t('desktop.cloudAI.ollamaComplete', duration=f"{duration_ms:.0f}", model=ollama_model))

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
                        "auth_mode": t('desktop.cloudAI.authModeOllama')
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
            f"<b>{t('desktop.cloudAI.ollamaErrorHtml')}</b><br>"
            f"{error_msg}"
            f"</div>"
        )

        self.statusChanged.emit(t('desktop.cloudAI.ollamaError', error=error_msg[:50]))

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
                f"<b style='color:#34d399;'>{self.backend.get_name()}:</b><br>"
                f"{rendered}"
                f"</div>"
            )

            # メタ情報をログに記録
            logger.info(
                f"Backend response: duration={response.duration_ms:.2f}ms, "
                f"tokens={response.tokens_used}, cost=${response.cost_est:.6f}"
            )

            self.statusChanged.emit(
                t('desktop.cloudAI.responseCompleteStatus', duration=f"{response.duration_ms:.0f}", cost=f"{response.cost_est:.6f}")
            )

        else:
            # 失敗時: エラーメッセージを表示
            self.chat_display.append(
                f"<div style='color: #ef4444; margin-top: 10px;'>"
                f"<b>{t('desktop.cloudAI.errorHtml', error_type=response.error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"Backend error: type={response.error_type}, "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(t('desktop.cloudAI.errorStatus', error=response.error_type))

    def _on_executor_response(self, response: BackendResponse, execution_info: dict):
        """RoutingExecutor からの応答を処理 (Phase 2.x: CP1-CP10統合)"""
        import logging
        logger = logging.getLogger(__name__)

        # 実行情報を取得
        task_type = execution_info.get("task_type", "UNKNOWN")
        selected_backend = execution_info.get("selected_backend", "unknown")
        reason_codes = execution_info.get("reason_codes", [])
        fallback_chain = execution_info.get("fallback_chain", [])
        prompt_pack = execution_info.get("prompt_pack")
        policy_blocked = execution_info.get("policy_blocked", False)
        budget_status = execution_info.get("budget_status")

        # タスク分類とBackend選択をUI通知
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"[Task: {task_type}] → Backend: {selected_backend}"
            f"{' [PromptPack: ' + prompt_pack + ']' if prompt_pack else ''}"
            f"</div>"
        )

        # フォールバックがあった場合
        if len(fallback_chain) > 1:
            self.chat_display.append(
                f"<div style='color: #fbbf24; font-size: 9pt;'>"
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
                f"<b style='color:#34d399;'>{selected_backend}:</b><br>"
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
                t('desktop.cloudAI.responseCompleteStatus', duration=f"{response.duration_ms:.0f}", cost=f"{response.cost_est:.6f}")
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

            # v8.1.0: Memory Risk Gate (cloudAI API応答後)
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
                    logger.info("[ClaudeTab._on_executor_response] Memory Risk Gate completed (cloudAI-API)")
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
                    f"<div style='color: #fbbf24; margin-top: 10px;'>"
                    f"<b>{t('desktop.cloudAI.policyBlockHtml')}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}<br><br>"
                    f"{t('desktop.cloudAI.getApprovalRetry')}"
                    f"</div>"
                )
                self.statusChanged.emit(t('desktop.cloudAI.policyBlock'))

            elif error_type == "BudgetExceeded":
                # 予算超過
                self.chat_display.append(
                    f"<div style='color: #ef4444; margin-top: 10px;'>"
                    f"<b>{t('desktop.cloudAI.budgetExceededHtml')}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}<br><br>"
                    f"{t('desktop.cloudAI.checkBudgetMsg')}"
                    f"</div>"
                )
                self.statusChanged.emit(t('desktop.cloudAI.budgetExceeded'))

            else:
                # その他のエラー
                self.chat_display.append(
                    f"<div style='color: #ef4444; margin-top: 10px;'>"
                    f"<b>{t('desktop.cloudAI.errorHtml', error_type=error_type)}</b><br>"
                    f"{response.response_text.replace(chr(10), '<br>')}"
                    f"</div>"
                )

                logger.error(
                    f"[ClaudeTab] Error: type={error_type}, "
                    f"duration={response.duration_ms:.2f}ms"
                )

                self.statusChanged.emit(t('desktop.cloudAI.errorStatus', error=error_type))

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
            self.next_btn.setToolTip(t('desktop.cloudAI.nextDisabledTooltip', msg=next_msg))
        else:
            self.next_btn.setToolTip(t('desktop.cloudAI.nextEnabledTooltip'))

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

            self.statusChanged.emit(t('desktop.cloudAI.phaseBack', phase=self.workflow_state.get_current_phase_info()['name']))
        except WorkflowTransitionError as e:
            self.workflow_logger.log_blocked(old_phase, str(e))
            self.history_manager.phase_blocked(old_phase, str(e))
            QMessageBox.warning(self, t('desktop.cloudAI.phaseTransitionError'), str(e))

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

            self.statusChanged.emit(t('desktop.cloudAI.phaseForward', phase=self.workflow_state.get_current_phase_info()['name']))
        except WorkflowTransitionError as e:
            self.workflow_logger.log_blocked(old_phase, str(e))
            self.history_manager.phase_blocked(old_phase, str(e))
            QMessageBox.warning(self, t('desktop.cloudAI.phaseTransitionError'), str(e))

    def _on_reset_workflow(self):
        """工程をリセット"""
        reply = QMessageBox.question(
            self,
            t('desktop.cloudAI.workflowResetTitle'),
            t('desktop.cloudAI.resetWorkflowConfirm'),
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

            self.statusChanged.emit(t('desktop.cloudAI.phaseResetDone'))

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
            self.statusChanged.emit(t('desktop.cloudAI.dangerApproved'))
        else:
            self.statusChanged.emit(t('desktop.cloudAI.approvalCancelled'))

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
                return False, t('desktop.cloudAI.s3ApprovalRequired')
            return True, ""

        # S5〜S7: 実装は完了しているので、基本的にブロック
        # （ただし、テンプレ付与などで対応可能）
        if current in [WorkflowPhase.S5_VERIFY, WorkflowPhase.S6_REVIEW, WorkflowPhase.S7_RELEASE]:
            return True, t('desktop.cloudAI.verificationPhaseMsg')

        return True, ""

    # ===================
    # Phase 1.2: 承認関連メソッド
    # ===================

    def _on_toggle_approval_panel(self):
        """承認パネルの表示/非表示を切り替え"""
        self.approval_panel.setVisible(not self.approval_panel.isVisible())

        if self.approval_panel.isVisible():
            self.risk_approval_btn.setText(t('desktop.cloudAI.riskApprovalClose'))
        else:
            self.risk_approval_btn.setText(t('desktop.cloudAI.riskApprovalOpen'))

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

        self.statusChanged.emit(t('desktop.cloudAI.allScopesApproved'))

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

        self.statusChanged.emit(t('desktop.cloudAI.allScopesRejected'))

    def _update_approval_status_label(self):
        """承認状態ラベルを更新"""
        approved_scopes = self.approval_state.get_approved_scopes()

        if len(approved_scopes) == 0:
            self.approval_status_label.setText(t('desktop.cloudAI.scopeUnapproved'))
            self.approval_status_label.setStyleSheet(SS.err(bold=True))
        else:
            self.approval_status_label.setText(t('desktop.cloudAI.scopeApprovedCount', count=len(approved_scopes)))
            self.approval_status_label.setStyleSheet(SS.ok(bold=True))

    # ===================
    # v3.4.0: 会話継続機能
    # ===================

    def _send_continue_message(self, message: str):
        """
        v11.6.0: プロバイダー対応会話継続。
        - anthropic_cli: --continue フラグ（従来通り）
        - その他: 通常送信として転送（セッション維持はAPIセッションIDで管理）
        """
        import logging
        logger = logging.getLogger(__name__)

        if not message or not message.strip():
            return

        # --- v11.6.0: プロバイダー判定 ---
        model_id, provider = self._get_selected_model_provider()

        # Claude CLI 以外は通常送信に転送
        if provider not in ("anthropic_cli",):
            logger.info(
                f"[ClaudeTab._send_continue_message] Non-CLI provider ({provider}), "
                f"routing to normal send"
            )
            self.chat_display.append(
                f"<div style='color: #888; font-size: 9pt;'>"
                f"[{t('desktop.cloudAI.continueRoutedNormal', provider=provider)}]"
                f"</div>"
            )
            self._send_message(message)
            if hasattr(self, 'continue_input'):
                self.continue_input.clear()
            return

        # --- 以下は Claude CLI 専用 (--continue) ---

        # CLIバックエンドの確認
        if not self._cli_backend or not self._cli_backend.is_available():
            QMessageBox.warning(
                self,
                t('desktop.cloudAI.cliUnavailableTitle2'),
                t('desktop.cloudAI.cliLoginRequired')
            )
            return

        logger.info(f"[ClaudeTab] Sending continue message via CLI: {message}")

        # チャットに表示
        self.chat_display.append(
            f"<div style='color: #4fc3f7;'><b>{t('desktop.cloudAI.continueMessageHtml')}</b> {message}</div>"
        )
        self.chat_display.append(
            f"<div style='color: #888; font-size: 9pt;'>"
            f"{t('desktop.cloudAI.continueModeActive')}"
            f"</div>"
        )

        # ステータス表示
        self.statusChanged.emit(t('desktop.cloudAI.continuationProcessing'))

        import os
        working_dir = os.getcwd()
        skip_permissions = self.permission_skip_checkbox.isChecked()

        self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions)

        session_id = self.session_manager.get_current_session_id() or "continue_session"
        request = BackendRequest(
            session_id=session_id,
            phase="S4",
            user_text=message,
            toggles={
                "mcp": self.mcp_checkbox.isChecked(),
                "diff": self.diff_checkbox.isChecked(),
                "context": self.context_checkbox.isChecked(),
            },
            context={"use_continue": True},
        )

        self._pending_user_message = t('desktop.cloudAI.continuePendingPrefix', message=message)

        self._continue_thread = ContinueWorkerThread(
            backend=self._cli_backend,
            request=request,
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
                t('desktop.cloudAI.enterMessagePrompt')
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
                f"<b style='color:#34d399;'>{t('desktop.cloudAI.cliContinueLabel')}</b><br>"
                f"{rendered}"
                f"</div>"
            )

            logger.info(
                f"[ClaudeTab._on_continue_response] Continue response: "
                f"duration={response.duration_ms:.2f}ms"
            )

            self.statusChanged.emit(
                t('desktop.cloudAI.continueCompleteStatus', duration=f"{response.duration_ms:.0f}")
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
                f"<b>{t('desktop.cloudAI.continueErrorHtml', error_type=error_type)}</b><br>"
                f"{response.response_text.replace(chr(10), '<br>')}"
                f"</div>"
            )

            logger.error(
                f"[ClaudeTab._on_continue_response] Continue error: type={error_type}"
            )

            self.statusChanged.emit(t('desktop.cloudAI.continuationError', error=error_type))


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
                response_text=t('desktop.cloudAI.continueErrorMsg', error=f"{type(e).__name__}: {str(e)}"),
                error_type=type(e).__name__,
                duration_ms=0,
                tokens_used=0,
                cost_est=0.0,
                metadata={"backend": "claude-cli", "continue_mode": True}
            )
            self.completed.emit(error_response)
