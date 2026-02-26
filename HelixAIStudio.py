#!/usr/bin/env python3
"""
Helix AI Studio v11.9.0 "Unified Obsidian"
Multi-provider AI orchestration platform with dual interface (Desktop + Web)

Tabs:
- mixAI: 3+1 Phase Pipeline (Cloud AI plans → Local LLM team → Cloud AI integrates → Apply)
- cloudAI: Direct cloud model chat (Anthropic / OpenAI / Google API, CLI fallback)
- localAI: Ollama direct chat with 5 specialized categories
- History: JSONL chat history with search, date grouping, tab filters
- RAG: Document chunking, vector search, knowledge graph
- Settings: API keys, model catalog, Ollama, MCP, memory, display

Architecture: API-first with CLI fallback, dynamic model catalog (cloud_models.json),
provider-based routing (anthropic_api / openai_api / google_api / *_cli)
"""

import sys
import os
import logging
import traceback
import threading
import atexit
import gc
from datetime import datetime
from pathlib import Path

_APP_USER_MODEL_ID = 'HelixAIStudio.HelixAIStudio.App'

if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"[Startup] AppUserModelID failed: {_e}")


def get_application_path() -> Path:
    """
    アプリケーションの実行パスを取得（PyInstaller対応）

    - PyInstaller EXE実行時: EXEファイルのディレクトリ
    - Python実行時: スクリプトのディレクトリ

    参考: https://pyinstaller.org/en/stable/runtime-information.html
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller EXE実行時
        # sys.executable はEXEファイルの絶対パス
        return Path(sys.executable).parent
    else:
        # Python実行時
        return Path(__file__).parent


# アプリケーションパスを取得
APP_PATH = get_application_path()

# v8.2.0: 作業ディレクトリをアプリケーションルートに固定
os.chdir(str(APP_PATH))
sys.path.insert(0, str(APP_PATH))

# v8.2.0: 必須ディレクトリの保証
for _d in ['data', 'logs', 'config']:
    os.makedirs(str(APP_PATH / _d), exist_ok=True)

# v8.3.1: app_settings.json claude.default_model 整合性チェック
try:
    import json as _json
    _settings_path = APP_PATH / 'config' / 'app_settings.json'
    if _settings_path.exists():
        with open(_settings_path, 'r', encoding='utf-8') as _f:
            _settings = _json.load(_f)
        _expected_model = "claude-opus-4-6"
        if _settings.get('claude', {}).get('default_model') != _expected_model:
            _settings.setdefault('claude', {})['default_model'] = _expected_model
            with open(_settings_path, 'w', encoding='utf-8') as _f:
                _json.dump(_settings, _f, ensure_ascii=False, indent=2)
except Exception as _e:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        f"[Startup] Settings migration failed (non-fatal): {_e}"
    )

# srcディレクトリをパスに追加
src_path = APP_PATH / 'src'
if src_path.exists():
    sys.path.insert(0, str(src_path))
else:
    # EXE内の場合、sys._MEIPASSから取得
    if hasattr(sys, '_MEIPASS'):
        sys.path.insert(0, os.path.join(sys._MEIPASS, 'src'))


def setup_crash_logging():
    """
    グローバル例外ハンドラを設定

    - sys.excepthook: メインスレッドの未処理例外をキャッチ
    - threading.excepthook: バックグラウンドスレッドの例外をキャッチ
    - logs/crash.log にスタックトレースを記録
    """
    # logs ディレクトリを確保（PyInstaller対応）
    logs_dir = APP_PATH / "logs"
    logs_dir.mkdir(exist_ok=True)

    crash_log_path = logs_dir / "crash.log"

    def log_exception_to_file(exc_type, exc_value, exc_traceback, thread_name="MainThread"):
        """例外をcrash.logに記録"""
        try:
            with open(crash_log_path, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n{'='*80}\n")
                f.write(f"[CRASH] {timestamp} - Thread: {thread_name}\n")
                f.write(f"{'='*80}\n")

                # スタックトレースを書き込み
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
                f.write(f"\n{'='*80}\n\n")
                f.flush()
        except Exception as log_error:
            # ログ記録自体が失敗した場合はstderrに出力
            print(f"Failed to write crash log: {log_error}", file=sys.stderr)

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        """sys.excepthook: メインスレッドの例外をキャッチ"""
        # crash.log に記録
        log_exception_to_file(exc_type, exc_value, exc_traceback, "MainThread")

        # app.log にも記録（存在する場合）
        logger = logging.getLogger(__name__)
        logger.critical(
            "Uncaught exception in main thread",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

        # デフォルトの動作も実行（stderrに出力）
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def custom_threading_excepthook(args):
        """threading.excepthook: バックグラウンドスレッドの例外をキャッチ"""
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread

        thread_name = thread.name if thread else "UnknownThread"

        # crash.log に記録
        log_exception_to_file(exc_type, exc_value, exc_traceback, thread_name)

        # app.log にも記録
        logger = logging.getLogger(__name__)
        logger.critical(
            f"Uncaught exception in thread: {thread_name}",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    # グローバル例外ハンドラを設定
    sys.excepthook = custom_excepthook
    threading.excepthook = custom_threading_excepthook

    # 初期化ログ
    logger = logging.getLogger(__name__)
    logger.info("Global exception handlers installed (sys.excepthook + threading.excepthook)")


def cleanup_on_exit():
    """
    v3.9.6: アプリケーション終了時のクリーンアップ処理

    PyInstallerの一時ディレクトリ削除エラーを防ぐため、
    残っているスレッドやプロセスを適切に終了させる
    """
    logger = logging.getLogger(__name__)
    logger.info("[Cleanup] Starting application cleanup...")

    # ガベージコレクションを実行
    gc.collect()

    # 残っているスレッドを確認（デーモンスレッド以外）
    active_threads = [t for t in threading.enumerate()
                      if t.is_alive() and not t.daemon and t != threading.main_thread()]

    if active_threads:
        logger.warning(f"[Cleanup] {len(active_threads)} non-daemon threads still active")
        for t in active_threads:
            logger.warning(f"[Cleanup] Active thread: {t.name}")
            # スレッドに終了を促す（強制終了はしない）
            if hasattr(t, 'stop'):
                try:
                    t.stop()
                except Exception:
                    pass

    logger.info("[Cleanup] Application cleanup completed")


def _create_splash_screen(app):
    """v11.9.0: スプラッシュスクリーンを作成して返す"""
    try:
        from PyQt6.QtWidgets import QSplashScreen
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
        from PyQt6.QtCore import Qt

        import sys
        from pathlib import Path

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            icon_path = Path(sys._MEIPASS) / "icon.png"
            if not icon_path.exists():
                icon_path = Path(sys.executable).parent / "icon.png"
        else:
            icon_path = Path(__file__).parent / "icon.png"

        pixmap = QPixmap(400, 200)
        pixmap.fill(QColor("#080c14"))

        painter = QPainter(pixmap)

        if icon_path.exists():
            icon_pixmap = QPixmap(str(icon_path))
            if not icon_pixmap.isNull():
                scaled = icon_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(30, 68, scaled)

        painter.setPen(QColor("#e2e8f0"))
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(110, 80, "Helix AI Studio")

        painter.setPen(QColor("#38bdf8"))
        ver_font = QFont("Segoe UI", 10)
        painter.setFont(ver_font)
        from src.utils.constants import APP_VERSION, APP_CODENAME
        painter.drawText(110, 105, f"v{APP_VERSION}  {APP_CODENAME}")

        painter.setPen(QColor("#475569"))
        small_font = QFont("Segoe UI", 9)
        painter.setFont(small_font)
        painter.drawText(110, 130, "Loading...")

        painter.end()

        splash = QSplashScreen(pixmap)
        splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        return splash

    except Exception as e:
        logging.getLogger(__name__).warning(f"[Startup] SplashScreen failed (non-fatal): {e}")
        return None


def main():
    """Helix AI Studio エントリーポイント v11.9.0"""
    setup_crash_logging()
    atexit.register(cleanup_on_exit)

    try:
        from src.utils.log_setup import setup_app_logging
        from src.utils.i18n import init_language

        setup_app_logging()
        init_language()

        from src.main_window import create_application
        app = create_application()
        app.aboutToQuit.connect(cleanup_on_exit)

        # v11.9.3: タスクバーアイコンを早期に設定
        from PyQt6.QtGui import QIcon
        _icon_path = Path(__file__).parent / "icon.ico"
        if not _icon_path.exists():
            _icon_path = Path(__file__).parent / "icon.png"
        if _icon_path.exists():
            app.setWindowIcon(QIcon(str(_icon_path)))

        # v11.9.0: SplashScreen 表示
        splash = _create_splash_screen(app)
        if splash:
            splash.show()
            app.processEvents()

        if splash:
            from PyQt6.QtGui import QColor
            splash.showMessage(
                "  Loading modules...",
                alignment=0x84,
                color=QColor("#475569")
            )
            app.processEvents()

        from src.main_window import MainWindow
        window = MainWindow()
        window.show()

        if splash:
            splash.finish(window)

        return app.exec()

    except ImportError as e:
        print(f"Import Error: {e}")
        print("\n依存パッケージをインストールしてください:")
        print("  pip install -r requirements.txt")
        logger = logging.getLogger(__name__)
        logger.critical(f"Import Error: {e}", exc_info=True)
        return 1

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        logger = logging.getLogger(__name__)
        logger.critical(f"Startup Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # HELIX_WEB_SERVER_ONLY=1 が設定されている場合、GUIを起動しない。
    # launcher.py がサブプロセスとしてEXEを誤って再起動した場合の安全弁。
    if os.environ.get("HELIX_WEB_SERVER_ONLY") == "1":
        sys.exit(0)
    sys.exit(main())
