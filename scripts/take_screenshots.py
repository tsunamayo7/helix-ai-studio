"""
take_screenshots.py - Helix AI Studio 各タブのスクリーンショットを自動撮影

Usage:
    python scripts/take_screenshots.py [--output-dir screenshots/] [--tabs 0 1 2]
    python scripts/take_screenshots.py --list-tabs
"""

import sys
import os
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

TAB_NAMES = ["mixAI", "cloudAI", "localAI", "history", "rag", "settings"]


def main():
    parser = argparse.ArgumentParser(description="Helix AI Studio screenshot tool")
    parser.add_argument(
        "--output-dir", default="screenshots",
        help="Output directory for screenshots (default: screenshots/)"
    )
    parser.add_argument(
        "--tabs", nargs="*", type=int, default=None,
        help="Tab indices to capture (0-based). Default: all tabs"
    )
    parser.add_argument(
        "--list-tabs", action="store_true",
        help="List available tab names and exit"
    )
    parser.add_argument(
        "--delay", type=int, default=3000,
        help="Delay in ms before capturing (default: 3000)"
    )
    args = parser.parse_args()

    if args.list_tabs:
        for i, name in enumerate(TAB_NAMES):
            print(f"  {i}: {name}")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)

    from src.main_window import MainWindow
    window = MainWindow()
    window.show()

    tab_widget = window.tab_widget
    indices = args.tabs if args.tabs else list(range(tab_widget.count()))

    def capture():
        for idx in indices:
            if idx >= tab_widget.count():
                print(f"  SKIP: tab index {idx} out of range (max {tab_widget.count() - 1})")
                continue
            tab_widget.setCurrentIndex(idx)
            app.processEvents()
            # タブ切替後の描画待ち
            import time
            time.sleep(0.5)
            app.processEvents()

            name = TAB_NAMES[idx] if idx < len(TAB_NAMES) else f"tab_{idx}"
            screenshot = window.grab()
            filepath = output_dir / f"{name}.png"
            screenshot.save(str(filepath))
            print(f"  Saved: {filepath}")

        print(f"\nDone: {len(indices)} screenshots -> {output_dir}/")
        app.quit()

    QTimer.singleShot(args.delay, capture)
    app.exec()


if __name__ == "__main__":
    main()
