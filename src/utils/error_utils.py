"""
v11.7.0: エラー処理ユーティリティ

crash.log への書き込みを一元管理する。
"""
import logging
import traceback
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_CRASH_LOG_PATH = Path(__file__).parent.parent.parent / "logs" / "crash.log"


def write_crash_log(context: str, exc: Exception | None = None) -> None:
    """
    crash.log に例外情報を記録する。

    Args:
        context: どこで発生したか（例: "ClaudeTab._send_message:state_guard"）
        exc: 例外オブジェクト（None の場合は現在のスタックトレースを記録）
    """
    try:
        _CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*80}\n")
            f.write(f"[ERROR in {context}] {timestamp}\n")
            f.write(f"{'='*80}\n")
            if exc is not None:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
            else:
                traceback.print_exc(file=f)
            f.write(f"\n{'='*80}\n\n")
            f.flush()
    except Exception as log_err:
        logger.error(f"[write_crash_log] Failed to write crash log: {log_err}")
