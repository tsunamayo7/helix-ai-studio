#!/usr/bin/env python3
"""
watch_bundle.py  --  helix_source_bundle.txt 自動更新ウォッチャー

対象ファイルが保存されるたびに build_bundle.py を自動実行します。
追加の依存なし（watchdog があればより高速・低CPU）。

使い方:
    python scripts/watch_bundle.py
    python scripts/watch_bundle.py --interval 2   # ポーリング間隔（秒、デフォルト: 1.5）
"""

import os
import sys
import time
import subprocess
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# パス解決
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SCRIPT = os.path.join(BASE, 'scripts', 'build_bundle.py')

# build_bundle.py と同じファイルリストを参照
WATCHED_FILES = [
    'src/utils/__init__.py',
    'src/utils/constants.py',
    'src/utils/styles.py',
    'src/utils/log_setup.py',
    'src/utils/model_capabilities.py',
    'src/backends/__init__.py',
    'src/backends/anthropic_api_backend.py',
    'src/backends/openai_api_backend.py',
    'src/backends/google_api_backend.py',
    'src/backends/api_priority_resolver.py',
    'src/backends/sequential_executor.py',
    'src/backends/local_agent.py',
    'src/backends/codex_cli_backend.py',
    'src/backends/claude_cli_backend.py',
    'src/backends/mix_orchestrator.py',
    'src/memory/memory_manager.py',
    'src/rag/rag_builder.py',
    'src/rag/rag_executor.py',
    'src/rag/rag_planner.py',
    'src/rag/rag_verifier.py',
    'src/tabs/information_collection_tab.py',
    'src/tabs/helix_orchestrator_tab.py',
    'src/tabs/claude_tab.py',
    'src/tabs/local_ai_tab.py',
    'src/tabs/settings_cortex_tab.py',
    'src/utils/discord_notifier.py',
    'src/utils/prompt_cache.py',
    'src/main_window.py',
    'src/widgets/chat_history_panel.py',
    'src/widgets/web_lock_overlay.py',
    'src/widgets/bible_notification.py',
    'src/widgets/bible_panel.py',
    'src/widgets/chat_widgets.py',
    'src/widgets/no_scroll_widgets.py',
    'src/widgets/section_save_button.py',
    'src/tabs/history_tab.py',
    'src/utils/chat_logger.py',
    'src/utils/model_catalog.py',
    'src/memory/model_config.py',
    'src/mixins/__init__.py',
    'src/mixins/bible_context_mixin.py',
    'src/web/server.py',
    'src/web/api_routes.py',
    'src/web/chat_store.py',
    'src/web/file_transfer.py',
    'src/web/launcher.py',
    'frontend/src/App.jsx',
    'frontend/src/components/InputBar.jsx',
    'frontend/src/components/FileManagerView.jsx',
    'frontend/src/components/SettingsView.jsx',
    'frontend/src/components/TabBar.jsx',
    'frontend/src/hooks/useWebSocket.js',
    'frontend/public/sw.js',
    'i18n/ja.json',
    'i18n/en.json',
]


def _ts():
    return datetime.now().strftime('%H:%M:%S')


def _get_mtimes():
    """監視対象ファイルの {path: mtime} マップを返す。存在しないファイルは 0。"""
    result = {}
    for rel in WATCHED_FILES:
        full = os.path.join(BASE, rel.replace('/', os.sep))
        result[full] = os.path.getmtime(full) if os.path.exists(full) else 0
    return result


def _rebuild(changed_file: str):
    rel = os.path.relpath(changed_file, BASE).replace(os.sep, '/')
    print(f'\n[{_ts()}] 変更検出: {rel}')
    print(f'[{_ts()}] bundle 再生成中...')
    result = subprocess.run(
        [sys.executable, BUILD_SCRIPT],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    # 最終行（サイズ行）だけ表示
    lines = [l for l in result.stdout.strip().splitlines() if l.startswith('Total') or l.startswith('Bundle')]
    for l in lines:
        print(f'[{_ts()}] {l}')
    if result.returncode != 0:
        print(f'[{_ts()}] ERROR: {result.stderr.strip()[:200]}')
    else:
        print(f'[{_ts()}] 完了 ✓')


def _poll_loop(interval: float):
    prev = _get_mtimes()
    print(f'[{_ts()}] ウォッチャー起動（ポーリング間隔: {interval}s）')
    print(f'[{_ts()}] 監視ファイル数: {len(WATCHED_FILES)}  |  Ctrl+C で停止')
    print()

    while True:
        time.sleep(interval)
        current = _get_mtimes()
        for path, mtime in current.items():
            if mtime != prev.get(path, 0) and mtime != 0:
                _rebuild(path)
                prev = _get_mtimes()  # rebuild 後の mtime で上書き
                break
        else:
            prev = current


def _watchdog_loop(interval: float):
    """watchdog ライブラリ使用（pip install watchdog でインストール可）。"""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    watched_set = {
        os.path.normcase(os.path.normpath(os.path.join(BASE, r.replace('/', os.sep))))
        for r in WATCHED_FILES
    }
    building = [False]

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory:
                return
            norm = os.path.normcase(os.path.normpath(event.src_path))
            if norm in watched_set and not building[0]:
                building[0] = True
                _rebuild(event.src_path)
                building[0] = False

    observer = Observer()
    observer.schedule(Handler(), BASE, recursive=True)
    observer.start()
    print(f'[{_ts()}] ウォッチャー起動（watchdog モード）')
    print(f'[{_ts()}] 監視ファイル数: {len(WATCHED_FILES)}  |  Ctrl+C で停止')
    print()
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


def main():
    parser = argparse.ArgumentParser(description='helix_source_bundle.txt 自動更新ウォッチャー')
    parser.add_argument('--interval', type=float, default=1.5,
                        help='ポーリング間隔（秒）。watchdog 使用時は無視。デフォルト: 1.5')
    args = parser.parse_args()

    try:
        import watchdog  # noqa: F401
        _watchdog_loop(args.interval)
    except ImportError:
        _poll_loop(args.interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n[{_ts()}] ウォッチャー停止')
