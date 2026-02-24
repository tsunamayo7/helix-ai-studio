"""
Helix AI Studio - Application Logging Setup (v11.2.1)

アプリケーション全体のログを統一管理するセットアップ関数を提供する。
HelixAIStudio.py の main() から QApplication 生成より前に呼び出すこと。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_app_logging() -> None:
    """アプリケーションロギングを設定する（冪等）。

    - logs/helix_app.log へ RotatingFileHandler（5MB×3世代、utf-8）を追加
    - stdout へ StreamHandler（WARNING 以上のみ）を追加
    - httpx / httpcore / chromadb 等のノイジーなライブラリを WARNING に抑制
    - 2回呼んでもハンドラが重複しない
    """
    root_logger = logging.getLogger()

    # 冪等チェック: 既に RotatingFileHandler が設定済みならスキップ
    for handler in root_logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            return

    # logs/ ディレクトリを確保
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    root_logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- ファイルハンドラ（DEBUG 以上をすべて記録）---
    file_handler = RotatingFileHandler(
        logs_dir / "helix_app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # --- stdout ハンドラ（WARNING 以上のみ）---
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(fmt)
    root_logger.addHandler(stream_handler)

    # --- ノイジーな外部ライブラリを WARNING に抑制 ---
    _NOISY_LIBS = [
        "httpx",
        "httpcore",
        "chromadb",
        "urllib3",
        "asyncio",
        "multipart",
        "PIL",
        "matplotlib",
    ]
    for lib in _NOISY_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Application logging initialized: logs/helix_app.log"
    )
