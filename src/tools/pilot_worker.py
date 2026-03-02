"""
Pilot Worker — QThread ワーカー（UIスレッドブロック防止）

HelixPilotTool のコマンド実行と画面コンテキスト取得を
バックグラウンドスレッドで行う。
"""

import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class PilotWorkerThread(QThread):
    """Pilot コマンド実行用ワーカースレッド"""

    resultReady = pyqtSignal(dict)
    errorOccurred = pyqtSignal(str)

    def __init__(self, pilot_tool, command: str, params: dict, parent=None):
        super().__init__(parent)
        self._pilot_tool = pilot_tool
        self._command = command
        self._params = params

    def run(self):
        try:
            result = self._pilot_tool.execute(self._command, self._params)
            self.resultReady.emit(result)
        except Exception as e:
            logger.error(f"[PilotWorker] Command error: {self._command} — {e}")
            self.errorOccurred.emit(str(e))


class PilotContextWorkerThread(QThread):
    """画面コンテキスト取得用ワーカースレッド"""

    contextReady = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, pilot_tool, window: str = "", parent=None):
        super().__init__(parent)
        self._pilot_tool = pilot_tool
        self._window = window

    def run(self):
        try:
            context = self._pilot_tool.get_screen_context(self._window)
            self.contextReady.emit(context)
        except Exception as e:
            logger.error(f"[PilotContextWorker] Context error: {e}")
            self.errorOccurred.emit(str(e))


class PilotResponseWorkerThread(QThread):
    """応答テキスト中の Pilot マーカー実行用ワーカースレッド"""

    resultReady = pyqtSignal(str, list)  # (processed_response, executed_list)
    errorOccurred = pyqtSignal(str)

    def __init__(self, pilot_tool, response: str, parent=None):
        super().__init__(parent)
        self._pilot_tool = pilot_tool
        self._response = response

    def run(self):
        try:
            from src.tools.pilot_response_processor import execute_and_replace
            processed, executed = execute_and_replace(
                self._response, self._pilot_tool
            )
            self.resultReady.emit(processed, executed)
        except Exception as e:
            logger.error(f"[PilotResponseWorker] Process error: {e}")
            self.errorOccurred.emit(str(e))
