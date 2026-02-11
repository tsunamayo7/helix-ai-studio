"""
Helix AI Studio - Main Window
メインウィンドウ: 4タブ構成 (v5.0.0: ウィンドウサイズ永続化・UI強化)
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QStatusBar, QToolBar, QLabel, QApplication
)
from PyQt6.QtCore import Qt, QSize, QSettings, QByteArray
from PyQt6.QtGui import QFont, QIcon, QAction

from .tabs.claude_tab import ClaudeTab
# v3.9.0: Gemini Designer削除
# from .tabs.gemini_designer_tab import GeminiDesignerTab
from .tabs.settings_cortex_tab import SettingsCortexTab
# v3.9.0: Helix OrchestratorをLLMmixに改名
from .tabs.helix_orchestrator_tab import HelixOrchestratorTab
# v6.0.0: チャット作成タブを削除
# from .tabs.chat_creation_tab import ChatCreationTab
from .utils.constants import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """
    Helix AI Studio メインウィンドウ

    3タブ構成 (v6.0.0):
    1. mixAI - 3Phase実行アーキテクチャ・Claude中心型オーケストレーション
    2. soloAI - Claude単体チャット (旧Claude Code)
    3. 一般設定 - アプリ全体の設定

    v6.0.0変更: チャット作成タブ削除、mixAIを先頭に配置
    """

    VERSION = APP_VERSION
    APP_NAME = APP_NAME

    # ワークフロー状態更新シグナル
    from PyQt6.QtCore import pyqtSignal
    workflowStateChanged = pyqtSignal(object)  # WorkflowStateMachine インスタンスを渡す

    def __init__(self):
        super().__init__()

        # v5.0.0: QSettings for window size persistence
        self.settings = QSettings("HelixAIStudio", "MainWindow")

        # Session Managerを初期化
        from .data.session_manager import get_session_manager
        from .data.history_manager import get_history_manager
        self.session_manager = get_session_manager()
        self.workflow_state = self.session_manager.load_workflow_state()
        self.history_manager = get_history_manager()

        self._init_ui()
        self._init_statusbar()
        self._apply_stylesheet()

        # v5.0.0: ウィンドウサイズ復元
        self._restore_window_geometry()

    def _restore_window_geometry(self):
        """v5.0.0: 前回のウィンドウサイズ・位置を復元"""
        geometry = self.settings.value("geometry")
        if geometry and isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        else:
            # デフォルトサイズ（既に_init_uiで設定済み）
            self._center_on_screen()

        state = self.settings.value("windowState")
        if state and isinstance(state, QByteArray):
            self.restoreState(state)

    def _center_on_screen(self):
        """v5.0.0: 画面中央に配置"""
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    def _init_ui(self):
        """UIを初期化"""
        self.setWindowTitle(f"{self.APP_NAME} v{self.VERSION}")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # ウィンドウアイコンを設定 (v3.3.0)
        self._set_window_icon()

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # タブウィジェット
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        # タブを追加（workflow_stateを渡す）
        # v6.0.0: タブ順序を変更: mixAI → soloAI → 一般設定（チャット作成削除）

        # 1. mixAI タブ (3Phase実行アーキテクチャ)
        self.llmmix_tab = HelixOrchestratorTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.llmmix_tab, "🔀 mixAI")
        self.tab_widget.setTabToolTip(0,
            "<b>mixAI - 3Phase実行アーキテクチャ</b><br><br>"
            "Claude Code + ローカルLLMチームによる高精度オーケストレーション<br><br>"
            "<b>3Phase:</b><br>"
            "・Phase 1: Claude計画立案（回答+LLM指示生成）<br>"
            "・Phase 2: ローカルLLM順次実行<br>"
            "・Phase 3: Claude比較統合<br><br>"
            "<b>Ctrl+Enter</b> でメッセージ送信"
        )

        # 2. soloAI タブ (Claude単体チャット)
        self.claude_tab = ClaudeTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.claude_tab, "🤖 soloAI")
        self.tab_widget.setTabToolTip(1,
            "<b>soloAI - Claude単体チャット＆設定</b><br><br>"
            "Claude CLIとの直接対話、MCPサーバー管理を統合。<br><br>"
            "<b>サブタブ:</b><br>"
            "・チャット: AIとの対話<br>"
            "・設定: CLI/Ollama設定、MCPサーバー管理<br><br>"
            "<b>Ctrl+Enter</b> でメッセージ送信"
        )

        # 3. 一般設定 タブ (v6.0.0: APIキー設定削除)
        self.settings_tab = SettingsCortexTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.settings_tab, "⚙️ 一般設定")
        self.tab_widget.setTabToolTip(2,
            "<b>一般設定 - アプリ全体の設定</b><br><br>"
            "表示設定、自動化オプションなど。<br><br>"
            "<b>主要機能:</b><br>"
            "・テーマ・フォント設定<br>"
            "・自動保存設定<br>"
            "・Knowledge/Encyclopedia"
        )

        layout.addWidget(self.tab_widget)

        # シグナル接続
        self._connect_signals()

    def _set_window_icon(self):
        """ウィンドウアイコンを設定 (v3.3.0: タスクバー・タイトルバー両方に反映)"""
        import sys
        from pathlib import Path

        # アプリケーションパスを取得（PyInstaller対応）
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            app_path = Path(sys.executable).parent
        else:
            app_path = Path(__file__).parent.parent

        # アイコンファイルを検索 (.ico優先、.pngフォールバック)
        icon_paths = [
            app_path / "icon.ico",
            app_path / "icon.png",
        ]

        for icon_path in icon_paths:
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.setWindowIcon(icon)
                # アプリケーション全体にも設定（タスクバー用）
                QApplication.instance().setWindowIcon(icon)
                break

    def _init_statusbar(self):
        """ステータスバーを初期化"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # 左側: 一般メッセージ
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label)

        # 右側: バージョン情報
        version_label = QLabel(f"v{self.VERSION}")
        self.statusbar.addPermanentWidget(version_label)

    def _connect_signals(self):
        """シグナルを接続"""
        # ClaudeタブのステータスをステータスバーへClaude
        self.claude_tab.statusChanged.connect(self._update_status)

        # v3.9.0: Gemini Designer削除

        # LLMmixタブのステータス
        self.llmmix_tab.statusChanged.connect(self._update_status)

        # 設定変更の反映
        self.settings_tab.settingsChanged.connect(self._on_settings_changed)

    def _update_status(self, message: str):
        """ステータスを更新"""
        self.status_label.setText(message)

    # v3.9.0: _on_style_applied削除（Gemini Designer削除のため）

    def _on_settings_changed(self):
        """設定変更時"""
        self._update_status("⚙️ 設定を保存しました。(一部設定は再起動後に反映されます)")

        # v3.9.0: Gemini関連削除

        # TODO: スタイルシート再適用などのリアルタイム反映処理

    def notify_workflow_state_changed(self):
        """
        ワークフロー状態が変更されたことを全タブに通知

        Claude Codeタブから呼び出される
        """
        self.workflowStateChanged.emit(self.workflow_state)
        self.session_manager.save_workflow_state()

    def _apply_stylesheet(self):
        """スタイルシートを適用 (Cyberpunk Minimalテーマ)"""
        stylesheet = """
/* Helix AI Studio - Cyberpunk Minimal Theme */
/* ダークグレー背景 + ネオンシアン/グリーン アクセント */

QMainWindow {
    background-color: #1a1a1a;
}

QWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 10pt;
}

/* Tab Widget - Cyberpunk Style */
QTabWidget::pane {
    border: 1px solid #2d2d2d;
    background-color: #1a1a1a;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #252525;
    color: #888888;
    padding: 12px 24px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    border: 1px solid #2d2d2d;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #1a1a1a;
    color: #00d4ff;
    border-color: #00d4ff;
    border-bottom: 2px solid #00d4ff;
}

QTabBar::tab:hover:!selected {
    background-color: #2d2d2d;
    color: #00ff88;
}

/* Buttons - Neon Accent */
QPushButton {
    background-color: #2d2d2d;
    color: #00d4ff;
    border: 1px solid #00d4ff;
    padding: 8px 16px;
    border-radius: 6px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #00d4ff;
    color: #1a1a1a;
}

QPushButton:pressed {
    background-color: #00a0c0;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #252525;
    color: #555555;
    border-color: #3d3d3d;
}

/* Primary Action Button */
QPushButton[cssClass="primary"] {
    background-color: #00ff88;
    color: #1a1a1a;
    border: none;
    font-weight: bold;
}

QPushButton[cssClass="primary"]:hover {
    background-color: #00cc6a;
}

/* Input Fields - Subtle Glow on Focus */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: #00d4ff;
    selection-color: #1a1a1a;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #00d4ff;
    background-color: #2a2a2a;
}

/* ComboBox */
QComboBox {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 8px 12px;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #00d4ff;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
    background: transparent;
}

QComboBox QAbstractItemView {
    background-color: #252525;
    color: #e0e0e0;
    selection-background-color: #00d4ff;
    selection-color: #1a1a1a;
    border: 1px solid #00d4ff;
    border-radius: 4px;
}

/* CheckBox */
QCheckBox {
    spacing: 10px;
    color: #b0b0b0;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #3d3d3d;
    background-color: #252525;
}

QCheckBox::indicator:hover {
    border-color: #00d4ff;
}

QCheckBox::indicator:checked {
    background-color: #00d4ff;
    border-color: #00d4ff;
}

/* GroupBox - Neon Border */
QGroupBox {
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    padding-top: 24px;
    background-color: #1e1e1e;
}

QGroupBox::title {
    color: #00d4ff;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background-color: #1e1e1e;
    border-radius: 4px;
}

/* List/Tree Widget */
QListWidget, QTreeWidget {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #2d2d2d;
    border-radius: 6px;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #00d4ff;
    color: #1a1a1a;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #2d2d2d;
}

QTreeWidget::branch:selected {
    background-color: #00d4ff;
}

/* Scrollbar - Minimal */
QScrollBar:vertical {
    background-color: #1a1a1a;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #3d3d3d;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #00d4ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1a1a1a;
    height: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #3d3d3d;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #00d4ff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ToolBar */
QToolBar {
    background-color: #1e1e1e;
    border: none;
    padding: 6px;
    spacing: 10px;
}

/* StatusBar - Neon Accent */
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d4ff, stop:1 #00ff88);
    color: #1a1a1a;
    font-weight: bold;
}

/* SpinBox */
QSpinBox {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 6px;
}

QSpinBox:focus {
    border-color: #00d4ff;
}

/* ProgressBar - Neon Glow Effect */
QProgressBar {
    border: 1px solid #2d2d2d;
    border-radius: 6px;
    background-color: #252525;
    text-align: center;
    color: #e0e0e0;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d4ff, stop:1 #00ff88);
    border-radius: 5px;
}

/* Splitter */
QSplitter::handle {
    background-color: #2d2d2d;
}

QSplitter::handle:hover {
    background-color: #00d4ff;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* Slider */
QSlider::groove:horizontal {
    background-color: #2d2d2d;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #00d4ff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background-color: #00ff88;
}

/* ToolTip */
QToolTip {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #00d4ff;
    border-radius: 4px;
    padding: 6px;
}

/* Menu */
QMenu {
    background-color: #252525;
    border: 1px solid #2d2d2d;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #00d4ff;
    color: #1a1a1a;
}

QMenu::separator {
    height: 1px;
    background-color: #3d3d3d;
    margin: 4px 8px;
}
"""
        self.setStyleSheet(stylesheet)

    def closeEvent(self, event):
        """ウィンドウクローズイベント (v5.0.0: ウィンドウサイズ永続化追加)"""
        # v5.0.0: ウィンドウサイズ・位置を保存
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        # ワーカースレッドを停止
        self._cleanup_workers()

        # セッション状態を保存
        try:
            self.session_manager.save_workflow_state()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save workflow state on close: {e}")

        event.accept()

    def _cleanup_workers(self):
        """v3.9.6: ワーカースレッドをクリーンアップ"""
        import logging
        logger = logging.getLogger(__name__)

        # mixAI (LLMmix) タブのワーカーを停止
        if hasattr(self, 'llmmix_tab') and hasattr(self.llmmix_tab, 'worker'):
            worker = self.llmmix_tab.worker
            if worker and worker.isRunning():
                logger.info("[MainWindow] Stopping mixAI worker...")
                worker.cancel()
                worker.wait(3000)  # 最大3秒待機
                if worker.isRunning():
                    worker.terminate()
                    worker.wait(1000)

        # soloAI (Claude) タブのワーカーを停止
        if hasattr(self, 'claude_tab'):
            # claude_tabに_workerがある場合
            if hasattr(self.claude_tab, '_worker'):
                worker = self.claude_tab._worker
                if worker and worker.isRunning():
                    logger.info("[MainWindow] Stopping soloAI worker...")
                    if hasattr(worker, 'stop'):
                        worker.stop()
                    worker.wait(3000)
                    if worker.isRunning():
                        worker.terminate()
                        worker.wait(1000)

        logger.info("[MainWindow] Worker cleanup completed")


def create_application():
    """アプリケーションを作成"""
    # High DPI対応 (インスタンス化の前に設定)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Helix AI Studio")
    app.setApplicationVersion(MainWindow.VERSION)

    return app


def main():
    """メイン関数"""
    app = create_application()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
