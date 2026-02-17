#!/usr/bin/env python3
"""
Helix AI Studio - Next-Gen Hybrid AI Development Platform
Version: 1.0.0

論理（Claude）と視覚（Gemini）の螺旋構造、ローカルAI（Trinity）による進化を象徴した
次世代ハイブリッドAI開発環境

Features:
- Claude Code Tab: Logic & Architecture (MCP統合, Diff View, Context Loading)
- Gemini Designer Tab: UI/UX Refinement (UI Refiner Pipeline)
- App Manager Tab: Project Hub (Knowledge Graph可視化)
- Settings/Cortex Tab: Knowledge & Local AI (LightRAG, MCP Server Manager)

Base: Claude Code GUI v7.6.2 + Trinity Exoskeleton v2.2.5
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
except Exception:
    pass

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


def main():
    """Helix AI Studio エントリーポイント"""
    # グローバル例外ハンドラを最初に設定
    setup_crash_logging()

    # v3.9.6: 終了時のクリーンアップ処理を登録
    atexit.register(cleanup_on_exit)

    try:
        from src.main_window import create_application, MainWindow
        from src.utils.i18n import init_language

        # v9.6.0: 言語設定を初期化（UIインスタンス化前）
        init_language()

        app = create_application()

        # v3.9.6: aboutToQuitシグナルでクリーンアップを事前実行
        app.aboutToQuit.connect(cleanup_on_exit)

        window = MainWindow()
        window.show()

        return app.exec()

    except ImportError as e:
        print(f"Import Error: {e}")
        print("\n依存パッケージをインストールしてください:")
        print("  pip install -r requirements.txt")

        # crash.log にも記録
        logger = logging.getLogger(__name__)
        logger.critical(f"Import Error: {e}", exc_info=True)
        return 1

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

        # crash.log にも記録
        logger = logging.getLogger(__name__)
        logger.critical(f"Startup Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # HELIX_WEB_SERVER_ONLY=1 が設定されている場合、GUIを起動しない。
    # launcher.py がサブプロセスとしてEXEを誤って再起動した場合の安全弁。
    if os.environ.get("HELIX_WEB_SERVER_ONLY") == "1":
        sys.exit(0)
    sys.exit(main())
