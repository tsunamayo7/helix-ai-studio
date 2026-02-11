"""
Helix AI Studio - Knowledge Worker (v5.0.0)
バックグラウンドでナレッジ処理を行うワーカー
"""

import logging
from typing import List, Dict, Any

from PyQt6.QtCore import QThread, pyqtSignal

from .knowledge_manager import KnowledgeManager, get_knowledge_manager

logger = logging.getLogger(__name__)


class KnowledgeWorker(QThread):
    """会話完了後の自動ナレッジ処理ワーカー"""
    progress = pyqtSignal(str)        # 進捗メッセージ
    completed = pyqtSignal(dict)      # 処理結果
    error = pyqtSignal(str)           # エラー

    def __init__(
        self,
        conversation: List[Dict[str, str]],
        knowledge_manager: KnowledgeManager = None,
    ):
        super().__init__()
        self.conversation = conversation
        self.km = knowledge_manager or get_knowledge_manager()
        self._cancelled = False

    def run(self):
        """ナレッジ処理を実行"""
        try:
            self.progress.emit("ナレッジ処理を開始...")

            if not self.conversation:
                self.error.emit("空の会話データです")
                return

            if self._cancelled:
                return

            self.progress.emit("会話を分析中...")
            result = self.km.process_conversation(self.conversation)

            if self._cancelled:
                return

            if "error" in result:
                self.error.emit(result["error"])
            else:
                self.progress.emit("ナレッジを保存しました")
                self.completed.emit(result)

        except Exception as e:
            logger.exception("KnowledgeWorker error")
            self.error.emit(str(e))

    def cancel(self):
        """キャンセル"""
        self._cancelled = True
