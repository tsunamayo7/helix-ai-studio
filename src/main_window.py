"""
Helix AI Studio - Main Window
メインウィンドウ: 4タブ構成 (v5.0.0: ウィンドウサイズ永続化・UI強化)
"""

import sys
import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QStatusBar, QToolBar, QLabel, QApplication, QPushButton,
)
from PyQt6.QtCore import Qt, QSize, QSettings, QByteArray, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction

from .tabs.claude_tab import ClaudeTab
# v3.9.0: Gemini Designer削除
# from .tabs.gemini_designer_tab import GeminiDesignerTab
from .tabs.settings_cortex_tab import SettingsCortexTab
# v3.9.0: Helix OrchestratorをLLMmixに改名
from .tabs.helix_orchestrator_tab import HelixOrchestratorTab
# v6.0.0: チャット作成タブを削除
# from .tabs.chat_creation_tab import ChatCreationTab
# v8.5.0: 情報収集タブ追加
from .tabs.information_collection_tab import InformationCollectionTab
# v10.1.0: localAIタブ追加
from .tabs.local_ai_tab import LocalAITab
# v11.0.0: Historyタブ追加
from .tabs.history_tab import HistoryTab
from .utils.constants import APP_NAME, APP_VERSION
from .utils.i18n import t, set_language, get_language
# v11.0.0: ChatHistoryPanel removed (replaced by History tab)


class MainWindow(QMainWindow):
    """
    Helix AI Studio メインウィンドウ

    6タブ構成 (v11.0.0):
    1. mixAI - 3Phase実行アーキテクチャ・Claude中心型オーケストレーション
    2. cloudAI - クラウドAI単体チャット (旧soloAI / Claude Code)
    3. localAI - ローカルLLMチャット (Ollama直接実行)
    4. History - 全タブ統合チャット履歴 (JSONL検索・引用)
    5. RAG - AI知識ベース管理・RAGコンテキスト構築
    6. 一般設定 - アプリ全体の設定

    v11.0.0変更: Historyタブ追加 (Tab 3)
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

        # v11.8.0: retranslateUi() が _init_ui() 内で呼ばれるため、先に初期化
        self._web_locked = False

        self._init_ui()
        self._init_statusbar()
        # v11.9.0: _apply_stylesheet() 廃止。スタイルはcreate_application()のGLOBAL_APP_STYLESHEETで一元管理

        # v5.0.0: ウィンドウサイズ復元
        self._restore_window_geometry()

        # v9.3.0: Web UIサーバー自動起動
        self._auto_start_web_server()

        # v9.5.0: Web実行ロック監視タイマー（2秒間隔）
        self._web_lock_timer = QTimer(self)
        self._web_lock_timer.setInterval(2000)
        self._web_lock_timer.timeout.connect(self._check_web_execution_lock)
        self._web_lock_timer.start()
        self._web_locked = False

        # v11.2.1: 週次自動クリーンアップタイマー
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setSingleShot(False)
        self._cleanup_timer.setInterval(7 * 24 * 60 * 60 * 1000)
        self._cleanup_timer.timeout.connect(self._auto_cleanup)
        QTimer.singleShot(30_000, self._auto_cleanup)
        self._cleanup_timer.start()

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

    def _auto_start_web_server(self):
        """v9.3.0: config.jsonのweb_server.auto_start=trueならサーバーを自動起動"""
        try:
            import json
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            if config.get("web_server", {}).get("auto_start", False):
                from .web.launcher import start_server_background
                port = config.get("web_server", {}).get("port", 8500)
                self._web_server_thread = start_server_background(port=port)

                # settings_cortex_tabのUIを更新（手動起動と同じURL表示に統一）
                if hasattr(self, 'settings_tab'):
                    tab = self.settings_tab
                    if hasattr(tab, 'web_ui_toggle'):
                        tab.web_ui_toggle.setChecked(True)
                        tab.web_ui_toggle.setText(t('desktop.settings.webStop'))
                        tab.web_ui_status_label.setText(t('desktop.settings.webRunning', port=port))
                        tab._web_server_thread = self._web_server_thread
                    # v11.0.0: Tailscale IP + マシン名URL表示
                    if hasattr(tab, 'web_ui_url_label'):
                        ip = "localhost"
                        try:
                            import subprocess as _sp
                            for cmd in [
                                [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"],
                                ["tailscale", "ip", "-4"],
                            ]:
                                try:
                                    result = _sp.run(cmd, capture_output=True, text=True, timeout=5)
                                    if result.returncode == 0 and result.stdout.strip():
                                        ip = result.stdout.strip()
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                        import socket
                        machine = ""
                        try:
                            machine = socket.gethostname().lower()
                        except Exception:
                            pass
                        url_ip = f"http://{ip}:{port}"
                        if machine and ip != "localhost":
                            url_name = f"http://{machine}:{port}"
                            tab.web_ui_url_label.setText(f"📱 {url_ip}\n📱 {url_name}")
                        else:
                            tab.web_ui_url_label.setText(f"📱 {url_ip}")
                logger.info(f"[MainWindow] Web UI auto-started on port {port}")
        except Exception as e:
            logger.warning(f"Web UI auto-start failed: {e}")

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
        # v11.0.0: タブ順序: mixAI → cloudAI → localAI → History → RAG → 一般設定

        # 1. mixAI タブ (3Phase実行アーキテクチャ)
        self.llmmix_tab = HelixOrchestratorTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.llmmix_tab, t('desktop.mainWindow.mixAITab'))
        self.tab_widget.setTabToolTip(0, t('desktop.mainWindow.mixAITip'))

        # 2. cloudAI タブ (v10.1.0: 旧soloAI → cloudAI改名)
        self.claude_tab = ClaudeTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.claude_tab, t('desktop.mainWindow.cloudAITab'))
        self.tab_widget.setTabToolTip(1, t('desktop.mainWindow.cloudAITip'))

        # 3. localAI タブ (v10.1.0: 新規追加)
        self.local_ai_tab = LocalAITab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.local_ai_tab, t('desktop.mainWindow.localAITab'))
        self.tab_widget.setTabToolTip(2, t('desktop.mainWindow.localAITip'))

        # 4. History タブ (v11.0.0: 全タブ統合チャット履歴)
        self.history_tab = HistoryTab()
        self.history_tab.statusChanged.connect(self._update_status)
        self.tab_widget.addTab(self.history_tab, t('desktop.mainWindow.historyTab'))
        self.tab_widget.setTabToolTip(3, t('desktop.mainWindow.historyTip'))

        # 5. RAG タブ (v8.5.0: 自律RAG構築 → v11.0.0: RAGに改名)
        self.info_tab = InformationCollectionTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.info_tab, t('desktop.mainWindow.ragTab'))
        self.tab_widget.setTabToolTip(4, t('desktop.mainWindow.ragTip'))

        # 6. 一般設定 タブ (v6.0.0: APIキー設定削除)
        self.settings_tab = SettingsCortexTab(workflow_state=self.workflow_state, main_window=self)
        self.tab_widget.addTab(self.settings_tab, t('desktop.mainWindow.settingsTab'))
        self.tab_widget.setTabToolTip(5, t('desktop.mainWindow.settingsTip'))

        # v10.1.0: 言語切替ボタン（タブバー右端に常時表示）
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(4, 2, 8, 2)
        corner_layout.setSpacing(4)
        self.lang_ja_btn = QPushButton("日本語")
        self.lang_en_btn = QPushButton("English")
        self.lang_ja_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_en_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_ja_btn.clicked.connect(lambda: self._on_language_changed('ja'))
        self.lang_en_btn.clicked.connect(lambda: self._on_language_changed('en'))
        self._update_lang_button_styles(get_language())
        corner_layout.addWidget(self.lang_ja_btn)
        corner_layout.addWidget(self.lang_en_btn)
        self.tab_widget.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        layout.addWidget(self.tab_widget)

        # v11.0.0: ChatHistoryPanel removed (replaced by History tab)

        # シグナル接続
        self._connect_signals()

        # v11.5.3: 起動時に保存済み言語を全タブに適用（init_language() で読んだ言語を確定反映）
        self.retranslateUi()

    def _set_window_icon(self):
        """v11.9.0: ウィンドウアイコンを設定 (PyInstaller _MEIPASS対応強化)"""
        import sys
        from pathlib import Path

        icon_paths = []

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            exe_dir = Path(sys.executable).parent
            icon_paths = [
                meipass / "icon.ico",
                meipass / "icon.png",
                exe_dir / "icon.ico",
                exe_dir / "icon.png",
            ]
        else:
            script_dir = Path(__file__).parent.parent
            icon_paths = [
                script_dir / "icon.ico",
                script_dir / "icon.png",
            ]

        for icon_path in icon_paths:
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    QApplication.instance().setWindowIcon(icon)
                    logger.info(f"[MainWindow] Icon loaded: {icon_path}")
                    return

        logger.warning("[MainWindow] icon.ico/icon.png not found")

    def _init_statusbar(self):
        """ステータスバーを初期化"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # 左側: 一般メッセージ
        self.status_label = QLabel(t('desktop.mainWindow.ready'))
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

        # v8.5.0: 情報収集タブのステータス
        self.info_tab.statusChanged.connect(self._update_status)

        # 設定変更の反映
        self.settings_tab.settingsChanged.connect(self._on_settings_changed)

    def _update_status(self, message: str):
        """ステータスを更新"""
        self.status_label.setText(message)

    # v3.9.0: _on_style_applied削除（Gemini Designer削除のため）

    def _on_settings_changed(self):
        """設定変更時 - フォントサイズ・テーマを即時反映"""
        self._update_status(t('desktop.mainWindow.settingsSaved'))
        self._apply_font_and_theme()

    def _apply_font_and_theme(self):
        """設定ファイルからフォントサイズ・ダークモードを読み込んでアプリ全体に反映"""
        import json
        from pathlib import Path
        config_path = Path("config/general_settings.json")
        font_size = 10
        try:
            if config_path.exists():
                data = json.loads(config_path.read_text(encoding='utf-8'))
                font_size = int(data.get("font_size", 10))
                font_size = max(8, min(20, font_size))
        except Exception:
            pass

        # フォントサイズをアプリ全体に反映
        app = QApplication.instance()
        if app:
            font = app.font()
            font.setPointSize(font_size)
            app.setFont(font)

        # v11.9.0: GLOBAL_APP_STYLESHEETを再適用（フォントサイズ変更反映）
        from .utils.styles import GLOBAL_APP_STYLESHEET
        if app:
            app.setStyleSheet(GLOBAL_APP_STYLESHEET)

    def notify_workflow_state_changed(self):
        """
        ワークフロー状態が変更されたことを全タブに通知

        Claude Codeタブから呼び出される
        """
        self.workflowStateChanged.emit(self.workflow_state)
        self.session_manager.save_workflow_state()

    # =========================================================================
    # v9.5.0: Web実行ロック監視
    # =========================================================================

    def _check_web_execution_lock(self):
        """Web実行ロックファイルを監視"""
        import json
        from pathlib import Path
        lock_file = Path("data/web_execution_lock.json")
        try:
            if lock_file.exists():
                data = json.loads(lock_file.read_text(encoding='utf-8'))
                is_locked = data.get("locked", False)
            else:
                is_locked = False
        except Exception:
            is_locked = False
            data = {}

        if is_locked and not self._web_locked:
            self._activate_web_lock(data)
        elif not is_locked and self._web_locked:
            self._deactivate_web_lock()

    def _activate_web_lock(self, lock_data: dict):
        """Webロック有効化 -- オーバーレイ表示"""
        self._web_locked = True
        tab = lock_data.get("tab", "Web")
        client = lock_data.get("client_info", "")
        preview = lock_data.get("prompt_preview", "")

        for tab_widget in [self.llmmix_tab, self.claude_tab]:
            if hasattr(tab_widget, 'web_lock_overlay'):
                tab_widget.web_lock_overlay.show_lock(
                    t('desktop.mainWindow.webLockMsg', tab=tab, client=client, preview=preview)
                )
        self.status_label.setText(t('desktop.mainWindow.webExecuting', tab=tab, preview=preview))

    def _deactivate_web_lock(self):
        """Webロック解除"""
        self._web_locked = False
        for tab_widget in [self.llmmix_tab, self.claude_tab]:
            if hasattr(tab_widget, 'web_lock_overlay'):
                tab_widget.web_lock_overlay.hide_lock()
        self.status_label.setText(t('desktop.mainWindow.ready'))

    # v11.0.0: ChatHistoryPanel handlers removed (replaced by History tab)

    def toggle_chat_history(self, tab: str = None):
        """v11.0.0: 後方互換スタブ (Historyタブへリダイレクト)"""
        # Historyタブに切り替え
        if hasattr(self, 'history_tab'):
            self.tab_widget.setCurrentWidget(self.history_tab)

    def retranslateUi(self):
        """v9.6.0: 言語切替時にUIテキストを更新"""
        # タブ名 (v11.0.0: History追加、インデックス変更)
        self.tab_widget.setTabText(0, t('desktop.mainWindow.mixAITab'))
        self.tab_widget.setTabText(1, t('desktop.mainWindow.cloudAITab'))
        self.tab_widget.setTabText(2, t('desktop.mainWindow.localAITab'))
        self.tab_widget.setTabText(3, t('desktop.mainWindow.historyTab'))
        self.tab_widget.setTabText(4, t('desktop.mainWindow.ragTab'))
        self.tab_widget.setTabText(5, t('desktop.mainWindow.settingsTab'))
        # タブツールチップ
        self.tab_widget.setTabToolTip(0, t('desktop.mainWindow.mixAITip'))
        self.tab_widget.setTabToolTip(1, t('desktop.mainWindow.cloudAITip'))
        self.tab_widget.setTabToolTip(2, t('desktop.mainWindow.localAITip'))
        self.tab_widget.setTabToolTip(3, t('desktop.mainWindow.historyTip'))
        self.tab_widget.setTabToolTip(4, t('desktop.mainWindow.ragTip'))
        self.tab_widget.setTabToolTip(5, t('desktop.mainWindow.settingsTip'))
        # ステータスバー（_init_statusbar() 完了前は属性未存在）
        if hasattr(self, 'status_label') and not self._web_locked:
            self.status_label.setText(t('desktop.mainWindow.ready'))

        # 子タブにも通知 (v11.0.0: history_tab追加)
        for tab in [self.llmmix_tab, self.claude_tab, self.local_ai_tab, self.history_tab, self.info_tab, self.settings_tab]:
            if hasattr(tab, 'retranslateUi'):
                tab.retranslateUi()

        # v11.0.0: ChatHistoryPanel removed (History tab handles retranslation via tab loop above)

        # セクション保存ボタンのテキストを一括更新
        from .widgets.section_save_button import retranslate_section_save_buttons
        retranslate_section_save_buttons(self)

        # v10.1.0: 言語ボタンスタイル更新
        if hasattr(self, 'lang_ja_btn'):
            self._update_lang_button_styles(get_language())

    def _on_language_changed(self, lang: str):
        """v10.1.0: 言語変更（タブバー右端ボタンから呼び出し）"""
        set_language(lang)
        self._update_lang_button_styles(lang)
        self.retranslateUi()

    def _update_lang_button_styles(self, current_lang: str):
        """v11.9.0: 言語ボタンをobjectName + dynamic propertyで制御（GLOBAL QSS参照）"""
        self.lang_ja_btn.setObjectName("langBtn")
        self.lang_en_btn.setObjectName("langBtn")
        self.lang_ja_btn.setProperty("active", current_lang == 'ja')
        self.lang_en_btn.setProperty("active", current_lang == 'en')
        # プロパティ変更をQSSに反映
        self.lang_ja_btn.style().unpolish(self.lang_ja_btn)
        self.lang_ja_btn.style().polish(self.lang_ja_btn)
        self.lang_en_btn.style().unpolish(self.lang_en_btn)
        self.lang_en_btn.style().polish(self.lang_en_btn)

    # v11.9.0: _apply_stylesheet() を完全削除 (旧L458-L813, 約355行)
    # スタイルは全て create_application() 内の GLOBAL_APP_STYLESHEET で一元管理

    def closeEvent(self, event):
        """ウィンドウクローズイベント (v5.0.0: ウィンドウサイズ永続化追加)"""
        # v5.0.0: ウィンドウサイズ・位置を保存
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        # v11.5.3: 終了時に現在の言語設定を確実に保存
        try:
            set_language(get_language())
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save language on close: {e}")

        # ワーカースレッドを停止
        self._cleanup_workers()

        # セッション状態を保存
        try:
            self.session_manager.save_workflow_state()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save workflow state on close: {e}")

        event.accept()

    def _auto_cleanup(self):
        """v11.2.1: 週次自動クリーンアップ（サイレント実行）"""
        import logging
        import time
        from pathlib import Path
        _logger = logging.getLogger(__name__)

        # 孤立メモリのクリーンアップ
        try:
            if hasattr(self, 'settings_tab') and hasattr(self.settings_tab, '_memory_manager'):
                mm = self.settings_tab._memory_manager
                if hasattr(mm, 'cleanup_orphaned_memories'):
                    mm.cleanup_orphaned_memories()
                    _logger.info("[AutoCleanup] Orphaned memory cleanup done")
        except Exception as e:
            _logger.warning(f"[AutoCleanup] Memory cleanup failed: {e}")

        # web_uploads の 30日以上前のファイルを削除
        try:
            uploads_dir = Path("data/web_uploads")
            if uploads_dir.exists():
                cutoff = time.time() - 30 * 24 * 60 * 60
                removed = 0
                for f in uploads_dir.iterdir():
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                if removed:
                    _logger.info(f"[AutoCleanup] Removed {removed} old upload file(s)")
        except Exception as e:
            _logger.warning(f"[AutoCleanup] Upload cleanup failed: {e}")

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

        # cloudAI (Claude) タブのワーカーを停止
        if hasattr(self, 'claude_tab'):
            # claude_tabに_workerがある場合
            if hasattr(self.claude_tab, '_worker'):
                worker = self.claude_tab._worker
                if worker and worker.isRunning():
                    logger.info("[MainWindow] Stopping cloudAI worker...")
                    if hasattr(worker, 'stop'):
                        worker.stop()
                    worker.wait(3000)
                    if worker.isRunning():
                        worker.terminate()
                        worker.wait(1000)

        if hasattr(self, '_cleanup_timer'):
            self._cleanup_timer.stop()

        logger.info("[MainWindow] Worker cleanup completed")


def create_application():
    """v11.9.0: 高速化版 create_application"""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Helix AI Studio")
    app.setApplicationVersion(MainWindow.VERSION)

    # v11.9.0: OS別決め打ちフォント（QFontDatabase.families()スキャン廃止で高速化）
    from PyQt6.QtGui import QFont
    import platform

    os_name = platform.system()
    if os_name == "Windows":
        chosen_font = "Yu Gothic UI"
    elif os_name == "Darwin":
        chosen_font = "Hiragino Sans"
    else:
        chosen_font = "Noto Sans JP"

    default_font = QFont(chosen_font, 10)
    default_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(default_font)

    # v11.9.0: グローバルQSSを適用
    from .utils.styles import GLOBAL_APP_STYLESHEET
    app.setStyleSheet(GLOBAL_APP_STYLESHEET)

    return app


def main():
    """メイン関数"""
    app = create_application()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
