"""
Helix AI Studio - mixAI Tab (v7.0.0)
3Phase実行パイプライン: Claude Code + ローカルLLMチームによる高精度オーケストレーション

v7.0.0 "Orchestrated Intelligence": 旧5Phase→新3Phase化
- Phase 1: Claude計画立案（--cwdオプション付き、ツール使用指示）
- Phase 2: ローカルLLM順次実行（coding/research/reasoning/vision/translation）
- Phase 3: Claude比較統合（2回目呼び出し、品質検証ループあり）
- Neural Flow Visualizerの3Phase化
- 設定タブのカテゴリ刷新（5カテゴリ + MCP設定）
"""

import json
import logging
import time
import subprocess
import shutil
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QTextEdit, QPlainTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QCheckBox, QSpinBox, QFrame,
    QScrollArea, QFormLayout, QLineEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QSlider,
    QFileDialog  # v5.1: ファイル添付用
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QRect
from PyQt6.QtGui import QFont, QColor, QTextCursor, QPainter, QPen, QBrush, QPainterPath, QKeyEvent

from ..backends.tool_orchestrator import (
    ToolOrchestrator, ToolType, ToolResult,
    OrchestratorConfig, get_tool_orchestrator
)
# v7.0.0: 3Phase実行パイプライン
from ..backends.mix_orchestrator import MixAIOrchestrator
# v6.1.1: バージョン表記の動的取得
# v7.1.0: Claudeモデル動的選択
from ..utils.constants import APP_VERSION, CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL_ID
from ..utils.markdown_renderer import markdown_to_html
from ..utils.styles import (
    SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    OUTPUT_AREA_STYLE, INPUT_AREA_STYLE, TAB_BAR_STYLE,
    SCROLLBAR_STYLE, COMBO_BOX_STYLE, PROGRESS_BAR_STYLE,
    SPINBOX_STYLE,
)
# Neural Flow Visualizer & VRAM Simulator
from ..widgets.neural_visualizer import NeuralFlowCompactWidget, PhaseState
from ..widgets.vram_simulator import VRAMBudgetSimulator, VRAMCompactWidget
# v8.0.0: BIBLE Manager
from ..widgets.bible_panel import BibleStatusPanel
from ..widgets.bible_notification import BibleNotificationWidget
from ..widgets.chat_widgets import PhaseIndicator, ExecutionIndicator, InterruptionBanner
from ..bible.bible_discovery import BibleDiscovery
from ..bible.bible_injector import BibleInjector

logger = logging.getLogger(__name__)


class NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox"""
    def wheelEvent(self, event):
        event.ignore()


# =============================================================================
# v5.1: mixAI用強化入力クラス
# =============================================================================

class MixAIEnhancedInput(QPlainTextEdit):
    """
    mixAI用強化入力ウィジェット (v5.1.1)

    機能:
    - 上下キーによるカーソル移動
    - 先頭行+上キー -> テキスト先頭へ
    - 最終行+下キー -> テキスト末尾へ
    - ファイルドロップサポート
    - Ctrl+Vでクリップボードからファイル添付 (v5.1.1)
    """
    file_dropped = pyqtSignal(list)  # ファイルドロップ時のシグナル

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def keyPressEvent(self, event: QKeyEvent):
        """キーイベント処理"""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+V: クリップボードからファイル添付をチェック (v5.1.1)
        if key == Qt.Key.Key_V and modifiers == Qt.KeyboardModifier.ControlModifier:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()

            # クリップボードにファイルURLがある場合
            if mime_data.hasUrls():
                files = [url.toLocalFile() for url in mime_data.urls()
                         if url.toLocalFile() and os.path.exists(url.toLocalFile())]
                if files:
                    self.file_dropped.emit(files)
                    return  # ファイル添付した場合はテキスト貼り付けしない

            # クリップボードに画像がある場合、一時ファイルとして保存
            if mime_data.hasImage():
                import tempfile
                from PyQt6.QtGui import QImage
                image = clipboard.image()
                if not image.isNull():
                    temp_dir = tempfile.gettempdir()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_path = os.path.join(temp_dir, f"clipboard_image_{timestamp}.png")
                    if image.save(temp_path, "PNG"):
                        self.file_dropped.emit([temp_path])
                        return

            # 通常のテキスト貼り付け
            super().keyPressEvent(event)
            return

        # 上キー処理: 先頭行にいる場合 -> テキスト先頭へ
        if key == Qt.Key.Key_Up:
            cursor = self.textCursor()
            cursor_block = cursor.block()
            first_block = self.document().firstBlock()
            if cursor_block == first_block:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
                return
            super().keyPressEvent(event)
            return

        # 下キー処理: 最終行にいる場合 -> テキスト末尾へ
        if key == Qt.Key.Key_Down:
            cursor = self.textCursor()
            cursor_block = cursor.block()
            last_block = self.document().lastBlock()
            if cursor_block == last_block:
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                return
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        """ドラッグ進入イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        """ドロップイベント"""
        if event.mimeData().hasUrls():
            files = [url.toLocalFile() for url in event.mimeData().urls()
                     if url.toLocalFile()]
            if files:
                self.file_dropped.emit(files)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class MixAIAttachmentWidget(QFrame):
    """mixAI用個別添付ファイルウィジェット"""
    removed = pyqtSignal(str)  # ファイルパス

    FILE_ICONS = {
        ".py": "🐍", ".js": "📜", ".ts": "📘",
        ".html": "🌐", ".css": "🎨", ".json": "📋",
        ".md": "📝", ".txt": "📄", ".pdf": "📕",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️",
        ".gif": "🖼️", ".svg": "🖼️", ".webp": "🖼️",
        ".zip": "📦", ".csv": "📊", ".xlsx": "📊",
    }

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            MixAIAttachmentWidget {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 2px 6px;
            }
            MixAIAttachmentWidget:hover {
                border-color: #63b3ed;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # ファイルアイコン + 名前
        import os
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        icon = self.FILE_ICONS.get(ext, "📎")

        icon_label = QLabel(icon)
        name_label = QLabel(filename)
        name_label.setStyleSheet("color: #e2e8f0; font-size: 10px;")
        name_label.setMaximumWidth(150)
        name_label.setToolTip(filepath)

        # ×ボタン (v5.2.0: 視認性大幅向上 - 常に赤背景で目立たせる)
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setToolTip("添付を解除")
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #e53e3e;
                color: #ffffff;
                border: 2px solid #fc8181;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #c53030;
                color: #ffffff;
                border-color: #feb2b2;
            }
            QPushButton:pressed {
                background-color: #9b2c2c;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(remove_btn)


class MixAIAttachmentBar(QWidget):
    """mixAI用添付ファイルバー"""
    attachments_changed = pyqtSignal(list)  # ファイルパスリスト

    def __init__(self, parent=None):
        super().__init__(parent)
        import os
        self._files: List[str] = []
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMaximumHeight(36)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.container = QWidget()
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def add_files(self, filepaths: List[str]):
        """ファイルを追加"""
        import os
        for fp in filepaths:
            if fp not in self._files and os.path.exists(fp):
                self._files.append(fp)
                widget = MixAIAttachmentWidget(fp)
                widget.removed.connect(self.remove_file)
                self.container_layout.insertWidget(
                    self.container_layout.count() - 1, widget)

        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def remove_file(self, filepath: str):
        """ファイルを削除"""
        if filepath in self._files:
            self._files.remove(filepath)
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, MixAIAttachmentWidget) and w.filepath == filepath:
                    w.deleteLater()
                    break
        self.setVisible(bool(self._files))
        self.attachments_changed.emit(self._files.copy())

    def clear_all(self):
        """全ファイル削除"""
        self._files.clear()
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setVisible(False)
        self.attachments_changed.emit([])

    def get_files(self) -> List[str]:
        """添付ファイルリストを取得"""
        return self._files.copy()


class GPUUsageGraph(QWidget):
    """GPU使用量の動的グラフ表示ウィジェット（時間軸選択・シークバー対応）"""

    # 時間範囲定義（秒）
    TIME_RANGES = {
        "60秒": 60,
        "5分": 300,
        "15分": 900,
        "30分": 1800,
        "1時間": 3600,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)

        # データ保存用（最大3600サンプル = 1時間分）
        self.max_samples = 3600
        self.gpu_data: Dict[int, List[Dict[str, Any]]] = {}  # GPU index -> [{timestamp, vram_used, vram_total, event}]
        self.events: List[Dict[str, Any]] = []  # LLM起動イベント

        # 時間軸設定
        self.time_range = 60  # デフォルト60秒
        self.view_offset = 0  # シークバーオフセット（秒）: 0 = 現在、正の値 = 過去

        # 色定義
        self.gpu_colors = [
            QColor("#22c55e"),  # GPU 0: 緑
            QColor("#3b82f6"),  # GPU 1: 青
            QColor("#f59e0b"),  # GPU 2: オレンジ
            QColor("#ef4444"),  # GPU 3: 赤
        ]

    def set_time_range(self, seconds: int):
        """時間範囲を設定"""
        self.time_range = seconds
        self.view_offset = 0  # 時間範囲変更時はオフセットをリセット
        self.update()

    def set_view_offset(self, offset_seconds: int):
        """表示オフセットを設定（シークバー用）"""
        self.view_offset = max(0, offset_seconds)
        self.update()

    def get_data_duration(self) -> float:
        """記録データの全期間（秒）を取得"""
        if not self.gpu_data:
            return 0
        all_timestamps = []
        for data_points in self.gpu_data.values():
            if data_points:
                all_timestamps.extend([dp["timestamp"] for dp in data_points])
        if not all_timestamps:
            return 0
        return time.time() - min(all_timestamps)

    def add_data_point(self, gpu_index: int, vram_used_mb: int, vram_total_mb: int, event: str = ""):
        """データポイントを追加"""
        if gpu_index not in self.gpu_data:
            self.gpu_data[gpu_index] = []

        self.gpu_data[gpu_index].append({
            "timestamp": time.time(),
            "vram_used": vram_used_mb,
            "vram_total": vram_total_mb,
            "event": event,
        })

        # 古いデータを削除（1時間以上前）
        cutoff = time.time() - 3600
        self.gpu_data[gpu_index] = [dp for dp in self.gpu_data[gpu_index] if dp["timestamp"] > cutoff]

        self.update()

    def add_event(self, event_name: str):
        """LLM起動イベントを記録"""
        self.events.append({
            "timestamp": time.time(),
            "name": event_name,
        })
        # 古いイベントを削除（1時間以上前）
        cutoff = time.time() - 3600
        self.events = [e for e in self.events if e["timestamp"] > cutoff]
        self.update()

    def clear_data(self):
        """データをクリア"""
        self.gpu_data.clear()
        self.events.clear()
        self.view_offset = 0
        self.update()

    def paintEvent(self, event):
        """グラフを描画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor("#1f2937"))

        # マージン
        margin_left = 50
        margin_right = 10
        margin_top = 20
        margin_bottom = 25

        graph_width = self.width() - margin_left - margin_right
        graph_height = self.height() - margin_top - margin_bottom

        if graph_width <= 0 or graph_height <= 0:
            return

        # グラフ領域の背景
        graph_rect = QRect(margin_left, margin_top, graph_width, graph_height)
        painter.fillRect(graph_rect, QColor("#111827"))

        # 軸を描画
        pen = QPen(QColor("#4b5563"))
        pen.setWidth(1)
        painter.setPen(pen)

        # Y軸
        painter.drawLine(margin_left, margin_top, margin_left, margin_top + graph_height)
        # X軸
        painter.drawLine(margin_left, margin_top + graph_height, margin_left + graph_width, margin_top + graph_height)

        # Y軸ラベル (0%, 50%, 100%)
        painter.setPen(QColor("#9ca3af"))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(5, margin_top + 5, "100%")
        painter.drawText(5, margin_top + graph_height // 2, "50%")
        painter.drawText(5, margin_top + graph_height, "0%")

        # X軸時間ラベル
        time_label_left = f"-{self._format_time(self.time_range + self.view_offset)}"
        time_label_right = f"-{self._format_time(self.view_offset)}" if self.view_offset > 0 else "現在"
        painter.drawText(margin_left, margin_top + graph_height + 15, time_label_left)
        painter.drawText(margin_left + graph_width - 30, margin_top + graph_height + 15, time_label_right)

        # 水平グリッド線
        pen.setColor(QColor("#374151"))
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.drawLine(margin_left, margin_top + graph_height // 2, margin_left + graph_width, margin_top + graph_height // 2)

        # データがない場合
        if not self.gpu_data:
            painter.setPen(QColor("#6b7280"))
            painter.drawText(graph_rect, Qt.AlignmentFlag.AlignCenter, "GPU使用量のデータがありません\n実行開始で記録が開始されます")
            return

        # 表示範囲を計算（シークバー対応）
        now = time.time()
        view_end = now - self.view_offset  # 表示終了時刻
        view_start = view_end - self.time_range  # 表示開始時刻

        # 各GPUのデータを描画
        for gpu_index, data_points in self.gpu_data.items():
            if not data_points:
                continue

            color = self.gpu_colors[gpu_index % len(self.gpu_colors)]
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)

            # パスを構築
            path = QPainterPath()
            first_point = True

            for dp in data_points:
                ts = dp["timestamp"]
                # 表示範囲内のデータのみ描画
                if ts < view_start or ts > view_end:
                    continue

                # X座標: 表示範囲内での位置
                x = margin_left + graph_width * ((ts - view_start) / self.time_range)
                usage_pct = dp["vram_used"] / dp["vram_total"] if dp["vram_total"] > 0 else 0
                y = margin_top + graph_height - (usage_pct * graph_height)

                if first_point:
                    path.moveTo(x, y)
                    first_point = False
                else:
                    path.lineTo(x, y)

            painter.drawPath(path)

        # イベントマーカーを描画
        for evt in self.events:
            ts = evt["timestamp"]
            if ts < view_start or ts > view_end:
                continue

            x = margin_left + graph_width * ((ts - view_start) / self.time_range)
            pen = QPen(QColor("#f59e0b"))
            pen.setWidth(1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(x), margin_top, int(x), margin_top + graph_height)

            # イベント名
            painter.setPen(QColor("#f59e0b"))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(int(x) - 30, margin_top - 3, evt["name"][:15])

        # 凡例
        legend_x = margin_left + 5
        legend_y = margin_top + 5
        for gpu_index in sorted(self.gpu_data.keys()):
            color = self.gpu_colors[gpu_index % len(self.gpu_colors)]
            painter.fillRect(legend_x, legend_y, 10, 10, color)
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(legend_x + 15, legend_y + 9, f"GPU {gpu_index}")
            legend_x += 60

    def _format_time(self, seconds: float) -> str:
        """秒数を読みやすい形式にフォーマット"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds / 60)}分"
        else:
            return f"{int(seconds / 3600)}時間"


class MixAIWorker(QThread):
    """mixAI v7.0.0 処理ワーカー - Claude主導型マルチフェーズパイプライン"""
    progress = pyqtSignal(str, int)
    tool_executed = pyqtSignal(dict)
    message_chunk = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt: str, config: OrchestratorConfig, image_path: str = None):
        super().__init__()
        self.prompt = prompt
        self.config = config
        self.image_path = image_path
        self._cancelled = False
        self.orchestrator = None
        self._stage_outputs: List[Dict[str, Any]] = []  # 各ステージの出力を蓄積

    def cancel(self):
        self._cancelled = True

    def run(self):
        """マルチフェーズパイプライン実行 (v7.0.0)"""
        try:
            self.orchestrator = ToolOrchestrator(self.config)
            if not self.orchestrator.initialize():
                self.error.emit("Ollamaへの接続に失敗しました。\n設定タブでOllama URLを確認してください。")
                return

            # フェーズパイプライン実行
            self._execute_phase_1_task_analysis()
            if self._cancelled:
                return

            # Phase 2: Claude CLI経由で実際のアクションを実行
            self._execute_phase_2_claude_execution()
            if self._cancelled:
                return

            self._execute_phase_3_image_analysis()
            if self._cancelled:
                return

            self._execute_phase_4_rag_search()
            if self._cancelled:
                return

            self._execute_phase_5_validation_report()

            self.progress.emit("完了", 100)

        except Exception as e:
            logger.exception("mixAI Worker error")
            self.error.emit(str(e))

    def _execute_claude_cli(self, prompt: str, timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Claude CLIを呼び出してMCPツールを実行

        Args:
            prompt: Claudeに送信するプロンプト
            timeout_seconds: タイムアウト（秒）

        Returns:
            Dict with 'success', 'output', 'error'
        """
        try:
            # Claude CLIの存在確認
            claude_cmd = shutil.which("claude")
            if claude_cmd is None:
                # Windows のデフォルトパスを確認
                possible_paths = [
                    os.path.expanduser("~/.claude/local/claude.exe"),
                    os.path.expanduser("~/AppData/Local/Programs/claude/claude.exe"),
                    "claude",
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        claude_cmd = path
                        break

            if claude_cmd is None:
                return {
                    "success": False,
                    "output": "",
                    "error": "Claude CLIが見つかりません。Claude Codeをインストールしてください。",
                }

            # Claude CLIを実行
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            # プロンプトをファイル経由で渡す（長いプロンプト対応）
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(prompt)
                prompt_file = f.name

            try:
                # v5.0.0: Claude CLI実行（--dangerously-skip-permissions で自動許可）
                result = subprocess.run(
                    [claude_cmd, "-p", "--dangerously-skip-permissions", prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    creationflags=creationflags,
                    encoding='utf-8',
                    errors='replace',
                )

                if result.returncode == 0:
                    return {
                        "success": True,
                        "output": result.stdout.strip(),
                        "error": "",
                    }
                else:
                    return {
                        "success": False,
                        "output": result.stdout.strip(),
                        "error": result.stderr.strip() or f"Exit code: {result.returncode}",
                    }
            finally:
                # 一時ファイルを削除
                try:
                    os.unlink(prompt_file)
                except:
                    pass

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"Claude CLIがタイムアウトしました（{timeout_seconds}秒）",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Claude CLI実行エラー: {str(e)}",
            }

    def _execute_phase_1_task_analysis(self):
        """Phase 1: タスク分析"""
        self.progress.emit("Phase 1: タスク分析中...", 10)

        analysis_prompt = f"""【重要】必ず日本語で回答してください。英語での回答は禁止です。

以下のタスクを分析し、実行計画を最大6行で簡潔にまとめてください。

【タスク】
{self.prompt}

【出力フォーマット】
- 行1-6: 設計・仮説・モデル割り当ての計画

必ず具体的なステップと使用するモデル候補を含めてください。すべて日本語で出力すること。"""

        result = self.orchestrator.execute_tool(
            ToolType.UNIVERSAL_AGENT,
            analysis_prompt,
            thinking_enabled=True,
        )

        # 出力末尾に使用モデルを自動追加
        model_name = result.metadata.get("model", self.config.universal_agent_model)
        output_with_model = f"{result.output}\n\n(自己申告) 使用モデル: {model_name}"
        result.output = output_with_model

        self._emit_tool_result(result, "タスク分析")
        self._stage_outputs.append({
            "stage": 1,
            "name": "タスク分析",
            "output": result.output,
            "model": model_name,
            "success": result.success,
        })
        self.progress.emit("Phase 1 完了", 20)

    def _execute_phase_2_claude_execution(self):
        """Phase 2: Claude CLI経由で実際のアクションを実行"""
        self.progress.emit("Phase 2: Claude実行中...", 30)

        # Phase 1の分析結果をコンテキストとして利用
        context = self._stage_outputs[0]["output"] if self._stage_outputs else ""

        # Claude CLIに送信するプロンプト（MCPツールを使って実際に実行）
        claude_prompt = f"""【重要】以下のタスクを実際に実行してください。計画を立てるだけでなく、MCPツールを使って実際にアクションを完了させてください。

【タスク】
{self.prompt}

【ローカルLLMによる分析結果】
{context}

【実行指示】
1. Web検索が必要な場合は、実際にWeb検索を実行して情報を取得してください
2. ファイル出力が必要な場合は、指定されたパスに実際にファイルを作成してください
3. すべての処理を完了したら、実行結果を日本語で報告してください

必ず日本語で回答してください。"""

        # Claude CLIを呼び出し
        start_time = time.time()
        claude_result = self._execute_claude_cli(claude_prompt, timeout_seconds=300)
        execution_time = (time.time() - start_time) * 1000

        if claude_result["success"]:
            output = claude_result["output"]
            model_name = "Claude CLI (MCP)"
            success = True
        else:
            # Claude CLI失敗時はローカルLLMにフォールバック
            self.progress.emit("Phase 2: ローカルLLMにフォールバック...", 35)

            fallback_prompt = f"""【重要】必ず日本語で回答してください。英語での回答は禁止です。

以下のタスクに対する処理計画を作成してください。
※注意: Claude CLIが利用できないため、ローカルLLMで計画を作成します。

【元タスク】
{self.prompt}

【分析結果】
{context}

【Claude CLIエラー】
{claude_result["error"]}

【出力フォーマット】
- 実行すべきアクションを具体的に記述
- 手動で実行する手順を日本語で説明"""

            result = self.orchestrator.execute_tool(
                ToolType.CODE_SPECIALIST,
                fallback_prompt,
                context=context,
            )
            output = f"[ローカルLLMフォールバック]\n{result.output}\n\n※Claude CLIエラー: {claude_result['error']}"
            model_name = result.metadata.get("model", self.config.code_specialist_model)
            execution_time = result.execution_time_ms
            success = result.success

        output_with_model = f"{output}\n\n(自己申告) 使用モデル: {model_name}"

        self.tool_executed.emit({
            "stage": "Claude実行",
            "tool_name": "claude_cli",
            "model": model_name,
            "success": success,
            "output": output_with_model[:500] if output_with_model else "",
            "execution_time_ms": execution_time,
            "error": "" if success else claude_result.get("error", ""),
        })

        self._stage_outputs.append({
            "stage": 2,
            "name": "Claude実行",
            "output": output_with_model,
            "model": model_name,
            "success": success,
        })
        self.progress.emit("Phase 2 完了", 45)

    def _execute_phase_3_image_analysis(self):
        """Phase 3: 画像解析"""
        self.progress.emit("Phase 3: 画像解析中...", 55)

        # 画像パスが指定されている場合のみ実行
        if self.image_path:
            image_prompt = f"""【重要】必ず日本語で回答してください。英語での回答は禁止です。

添付された画像を解析し、以下の情報をJSON形式で抽出してください。

【抽出項目】
- selected_claude_model: 選択されているClaudeモデル名
- auth_method: 認証方式
- thinking_setting: Thinking設定
- ollama_host: OllamaホストURL
- ollama_connection_status: 接続ステータス
- resident_models: 常駐モデル（万能Agent/画像/軽量/Embedding）とGPU割り当て
- gpu_monitor: GPU名、VRAM使用量

【出力フォーマット】
必ず有効なJSON形式で出力してください。JSONのキーは英語、値で日本語を含む場合は日本語で記述すること。"""

            result = self.orchestrator.execute_tool(
                ToolType.IMAGE_ANALYZER,
                image_prompt,
                image_path=self.image_path,
            )

            model_name = result.metadata.get("model", self.config.image_analyzer_model)
            output_with_model = f"{result.output}\n\n(自己申告) 使用モデル: {model_name}"
            result.output = output_with_model

            self._emit_tool_result(result, "画像解析")
            self._stage_outputs.append({
                "stage": 3,
                "name": "画像解析",
                "output": result.output,
                "model": model_name,
                "success": result.success,
            })
        else:
            # 画像なしの場合はスキップログを出力
            skip_output = "画像パスが指定されていないため、このステージはスキップされました。\n\n(自己申告) 使用モデル: なし (スキップ)"
            self.tool_executed.emit({
                "stage": "画像解析",
                "tool_name": "image_analyzer",
                "model": "スキップ",
                "success": True,
                "output": skip_output[:500],
                "execution_time_ms": 0,
                "error": "",
            })
            self._stage_outputs.append({
                "stage": 3,
                "name": "画像解析",
                "output": skip_output,
                "model": "スキップ",
                "success": True,
            })

        self.progress.emit("Phase 3 完了", 65)

    def _execute_phase_4_rag_search(self):
        """Phase 4: RAG/Embedding検索"""
        self.progress.emit("Phase 4: RAG検索中...", 75)

        if self.config.rag_enabled:
            # Phase 1-3の結果を参考にRAG検索を実行
            search_context = "\n".join([s["output"][:200] for s in self._stage_outputs])

            rag_prompt = f"""【最重要ルール】
1. 必ず日本語で回答してください。英語での回答は禁止です。
2. 最終的な検索結果のみを出力してください。
3. 思考過程・推論・内部メモ（「We should...」「Let me think...」「Might...」等）は一切出力禁止です。
4. 結果が0件の場合は「関連する情報は見つかりませんでした。」とのみ回答してください。

以下のコンテキストに関連する情報をRAG検索してください。

【検索クエリ】
mixAI 動作検証 JSON を検索

【コンテキスト】
{search_context[:500]}

【出力フォーマット】
関連情報が見つかった場合のみ、以下の形式で日本語出力:
• [情報1の要約]
• [情報2の要約]
（見つからなければ空出力ではなく「関連する情報は見つかりませんでした。」と回答）"""

            result = self.orchestrator.execute_tool(
                ToolType.RAG_MANAGER,
                rag_prompt,
            )

            model_name = result.metadata.get("model", self.config.embedding_model)
            output_with_model = f"{result.output}\n\n(自己申告) 使用モデル: {model_name}"
            result.output = output_with_model

            self._emit_tool_result(result, "RAG検索")
            self._stage_outputs.append({
                "stage": 4,
                "name": "RAG検索",
                "output": result.output,
                "model": model_name,
                "success": result.success,
            })
        else:
            # RAG無効の場合はスキップ
            skip_output = "RAGが無効化されているため、このステージはスキップされました。理由: 設定でrag_enabled=False\n\n(自己申告) 使用モデル: なし (スキップ)"
            self.tool_executed.emit({
                "stage": "RAG検索",
                "tool_name": "rag_manager",
                "model": "スキップ",
                "success": True,
                "output": skip_output[:500],
                "execution_time_ms": 0,
                "error": "",
            })
            self._stage_outputs.append({
                "stage": 4,
                "name": "RAG検索",
                "output": skip_output,
                "model": "スキップ",
                "success": True,
            })

        self.progress.emit("Phase 4 完了", 85)

    def _execute_phase_5_validation_report(self):
        """Phase 5: 最終バリデーションレポート"""
        self.progress.emit("Phase 5: バリデーションレポート生成中...", 90)

        # 全ステージの結果を統合
        stage_summaries = []
        for stage in self._stage_outputs:
            status = "✅ PASS" if stage["success"] else "❌ FAIL"
            stage_summaries.append(f"Phase {stage['stage']} ({stage['name']}): {status} - Model: {stage['model']}")

        all_passed = all(s["success"] for s in self._stage_outputs)
        overall_status = "PASS" if all_passed else "FAIL"

        validation_prompt = f"""【重要】必ず日本語で回答してください。英語での回答は禁止です。

以下の全ステージ結果を基に、最終バリデーションレポートを生成してください。

【ステージ結果サマリー】
{chr(10).join(stage_summaries)}

【全体判定】
{overall_status}

【出力フォーマット】
## 最終バリデーションレポート

### 判定結果
(PASS/FAIL と理由を日本語の箇条書きで)

### ステージ別詳細
(各ステージの結果をテーブル形式で、すべて日本語)

### ユーザーへの確認事項
(ツール実行ログで確認すべきモデル名のテーブル、日本語で記述)"""

        result = self.orchestrator.execute_tool(
            ToolType.UNIVERSAL_AGENT,
            validation_prompt,
            thinking_enabled=True,
        )

        model_name = result.metadata.get("model", self.config.universal_agent_model)

        # 最終レポートを構築
        final_report = f"""## 最終バリデーションレポート

### 判定結果: **{overall_status}**

{result.output}

### ステージ実行ログ

| Phase | 名前 | モデル | 結果 |
|-------|------|--------|------|
"""
        for s in self._stage_outputs:
            status_icon = "✅" if s["success"] else "❌"
            final_report += f"| {s['stage']} | {s['name']} | {s['model']} | {status_icon} |\n"

        final_report += f"\n(自己申告) 使用モデル: {model_name}"

        result.output = final_report

        self._emit_tool_result(result, "バリデーション")
        self._stage_outputs.append({
            "stage": 5,
            "name": "バリデーション",
            "output": final_report,
            "model": model_name,
            "success": result.success,
        })

        # 最終結果を出力
        self.finished.emit(self._generate_final_response())

    def _emit_tool_result(self, result: ToolResult, stage: str):
        """ツール実行結果をシグナルで送信"""
        # metadataからモデル名を取得
        model_name = result.metadata.get("model", "") if result.metadata else ""
        self.tool_executed.emit({
            "stage": stage,
            "tool_name": result.tool_name,
            "model": model_name,  # モデル名を追加
            "success": result.success,
            "output": result.output[:500] if result.output else "",
            "execution_time_ms": result.execution_time_ms,
            "error": result.error_message,
        })

    def _generate_final_response(self) -> str:
        """最終回答を生成（v4.4: マルチステージ統合）"""
        if not self._stage_outputs:
            return "タスクを処理しましたが、出力がありませんでした。"

        # 全ステージの出力を統合
        sections = []
        for stage in self._stage_outputs:
            section = f"""---

## Phase {stage['stage']}: {stage['name']}

**使用モデル**: `{stage['model']}`

{stage['output']}
"""
            sections.append(section)

        return "\n".join(sections)


class HelixOrchestratorTab(QWidget):
    """
    mixAI v7.0.0 タブ
    3Phase実行パイプライン + Claude Code CLI + ローカルLLM順次実行
    """

    statusChanged = pyqtSignal(str)

    def __init__(self, workflow_state=None, main_window=None):
        super().__init__()
        self.workflow_state = workflow_state
        self.main_window = main_window
        self.worker: Optional[MixAIWorker] = None
        self.config = OrchestratorConfig()

        # v5.0.0: 会話履歴（ナレッジ管理用）
        self._conversation_history: List[Dict[str, str]] = []
        self._attached_files: List[str] = []

        # v5.0.0: ナレッジワーカー
        self._knowledge_worker = None

        # v8.1.0: メモリマネージャー
        self._memory_manager = None
        try:
            from ..memory.memory_manager import HelixMemoryManager
            self._memory_manager = HelixMemoryManager()
            logger.info("HelixMemoryManager initialized for mixAI")
        except Exception as e:
            logger.warning(f"Memory manager init failed for mixAI: {e}")

        self._load_config()
        self._init_ui()
        self._restore_ui_from_config()

    def _restore_ui_from_config(self):
        """v8.4.2: 保存済み設定値をUIウィジェットに反映"""
        if hasattr(self, 'max_retries_spin') and hasattr(self.config, 'max_phase2_retries'):
            self.max_retries_spin.setValue(self.config.max_phase2_retries)

    def _get_config_path(self) -> Path:
        """設定ファイルのパスを取得（PyInstaller対応）"""
        # ユーザーのホームディレクトリに保存（永続化のため）
        config_dir = Path.home() / ".helix_ai_studio"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "tool_orchestrator.json"

    def _load_config(self):
        """設定を読み込み"""
        config_path = self._get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = OrchestratorConfig.from_dict(data)
                logger.info(f"[mixAI v5.1] 設定を読み込みました: {config_path}")
            except Exception as e:
                logger.warning(f"[mixAI v5.1] 設定読み込み失敗: {e}")
        else:
            # 旧パスからの移行を試みる
            old_config_path = Path(__file__).parent.parent.parent / "config" / "tool_orchestrator.json"
            if old_config_path.exists():
                try:
                    with open(old_config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.config = OrchestratorConfig.from_dict(data)
                    # 新パスにコピー
                    self._save_config()
                    logger.info(f"[mixAI v5.1] 旧設定を新パスに移行しました: {config_path}")
                except Exception as e:
                    logger.warning(f"[mixAI v5.1] 旧設定移行失敗: {e}")

    def _save_config(self):
        """設定を保存"""
        config_path = self._get_config_path()
        config_path.parent.mkdir(exist_ok=True)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"[mixAI v5.1] 設定を保存しました: {config_path}")
        except Exception as e:
            logger.error(f"[mixAI v5.1] 設定保存失敗: {e}")

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # サブタブウィジェット
        self.sub_tabs = QTabWidget()

        # チャットタブ
        chat_panel = self._create_chat_panel()
        self.sub_tabs.addTab(chat_panel, "💬 チャット")

        # 設定タブ
        settings_panel = self._create_settings_panel()
        self.sub_tabs.addTab(settings_panel, "⚙️ 設定")

        layout.addWidget(self.sub_tabs)

    def _create_chat_panel(self) -> QWidget:
        """チャットパネルを作成 (v4.0 新UI)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # ヘッダー
        header_layout = QHBoxLayout()
        title = QLabel(f"🚀 mixAI v{APP_VERSION} - 3Phase統合オーケストレーション")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)

        # バージョンバッジ
        version_badge = QLabel(f"v{APP_VERSION}")
        version_badge.setStyleSheet("""
            QLabel {
                background-color: #f0a030;
                color: white;
                padding: 4px 10px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        header_layout.addWidget(version_badge)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # メインコンテンツ（スプリッター）
        splitter = QSplitter(Qt.Orientation.Vertical)

        # === 入力エリア (v5.1: 強化入力 + 添付ファイル対応) ===
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 10, 0, 5)

        # v5.1: 添付ファイルバー（入力欄の上に表示）
        self.attachment_bar = MixAIAttachmentBar()
        self.attachment_bar.attachments_changed.connect(self._on_attachments_changed)
        input_layout.addWidget(self.attachment_bar)

        # v5.1: 強化チャット入力（上下キー対応、ドロップ対応）
        self.input_text = MixAIEnhancedInput()
        self.input_text.setPlaceholderText("メッセージを入力...")
        self.input_text.setMaximumHeight(120)
        self.input_text.file_dropped.connect(self.attachment_bar.add_files)
        input_layout.addWidget(self.input_text)

        # ボタン行
        btn_layout = QHBoxLayout()

        self.execute_btn = QPushButton("▶ 実行")
        self.execute_btn.setStyleSheet(PRIMARY_BTN)
        self.execute_btn.setToolTip("3Phase実行パイプラインを開始します\n(Phase 1: Claude計画 → Phase 2: ローカルLLM → Phase 3: Claude統合)")
        self.execute_btn.clicked.connect(self._on_execute)
        btn_layout.addWidget(self.execute_btn)

        self.cancel_btn = QPushButton("⏹ キャンセル")
        self.cancel_btn.setStyleSheet(DANGER_BTN)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        # v5.1: soloAIと同様のボタン群を追加
        btn_layout.addWidget(QLabel("  "))  # スペーサー

        # ファイル添付ボタン
        self.mixai_attach_btn = QPushButton("📎 ファイルを添付")
        self.mixai_attach_btn.setStyleSheet(SECONDARY_BTN)
        self.mixai_attach_btn.setToolTip("Claude CLIに渡すファイルを添付します\nコード、ドキュメント、画像などを指定できます")
        self.mixai_attach_btn.clicked.connect(self._on_attach_file)
        btn_layout.addWidget(self.mixai_attach_btn)

        # 履歴から引用ボタン
        self.mixai_history_btn = QPushButton("📜 履歴から引用")
        self.mixai_history_btn.setStyleSheet(SECONDARY_BTN)
        self.mixai_history_btn.setToolTip("過去のmixAI会話履歴を検索し、引用として挿入します。")
        self.mixai_history_btn.clicked.connect(self._on_cite_history)
        btn_layout.addWidget(self.mixai_history_btn)

        # スニペットボタン
        self.mixai_snippet_btn = QPushButton("📋 スニペット ▼")
        self.mixai_snippet_btn.setStyleSheet(SECONDARY_BTN)
        self.mixai_snippet_btn.setToolTip("保存済みのテキストスニペットを挿入します。")
        self.mixai_snippet_btn.clicked.connect(self._on_snippet_menu)
        btn_layout.addWidget(self.mixai_snippet_btn)

        # 追加ボタン (v5.1.1: 右クリックで編集・削除メニュー)
        self.mixai_snippet_add_btn = QPushButton("➕ 追加")
        self.mixai_snippet_add_btn.setToolTip("クリックで追加、右クリックで編集・削除メニュー")
        self.mixai_snippet_add_btn.setMaximumWidth(60)
        self.mixai_snippet_add_btn.clicked.connect(self._on_snippet_add)
        self.mixai_snippet_add_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mixai_snippet_add_btn.customContextMenuRequested.connect(self._on_snippet_context_menu)
        btn_layout.addWidget(self.mixai_snippet_add_btn)

        btn_layout.addStretch()

        # クリアボタン
        clear_btn = QPushButton("🗑️ クリア")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)

        input_layout.addLayout(btn_layout)
        splitter.addWidget(input_widget)

        # === 出力エリア（チャット形式） ===
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 5, 0, 0)

        # v8.0.0: PhaseIndicator - 3Phase実行状態インジケーター
        self.phase_indicator = PhaseIndicator()
        output_layout.addWidget(self.phase_indicator)

        # v7.0.0: Neural Flow Compact Widget - 3Phase可視化
        self.neural_flow = NeuralFlowCompactWidget()
        self.neural_flow.setToolTip("3Phase実行パイプラインの進捗をリアルタイムで表示します")
        self.neural_flow.setStyleSheet("""
            NeuralFlowCompactWidget {
                background-color: #1a1a1a;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
        """)
        output_layout.addWidget(self.neural_flow)

        # v8.0.0: BIBLE検出通知バー
        self.bible_notification = BibleNotificationWidget()
        self.bible_notification.add_clicked.connect(self._on_bible_add_context)
        output_layout.addWidget(self.bible_notification)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        # ツール実行ログ（折りたたみ可能）
        self.tool_log_group = QGroupBox("▶ ツール実行ログ (クリックで展開)")
        self.tool_log_group.setCheckable(True)
        self.tool_log_group.setChecked(False)
        self.tool_log_group.toggled.connect(self._on_tool_log_toggled)
        self.tool_log_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #4b5563;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #9ca3af;
            }
        """)

        tool_log_layout = QVBoxLayout()
        self.tool_log_tree = QTreeWidget()
        self.tool_log_tree.setHeaderLabels(["ツール", "モデル", "ステータス", "実行時間", "出力"])
        self.tool_log_tree.setColumnWidth(0, 100)
        self.tool_log_tree.setColumnWidth(1, 180)  # モデル名用に広め
        self.tool_log_tree.setColumnWidth(2, 70)
        self.tool_log_tree.setColumnWidth(3, 80)
        # v5.1: 固定高さを削除し、ウィンドウ拡張時に表示行数が増えるように
        self.tool_log_tree.setMinimumHeight(80)
        self.tool_log_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tool_log_tree.setVisible(False)
        tool_log_layout.addWidget(self.tool_log_tree)
        self.tool_log_group.setLayout(tool_log_layout)
        # v5.1: GroupBox自体もExpandingに設定
        self.tool_log_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        output_layout.addWidget(self.tool_log_group)

        # 出力テキストエリア
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("実行結果がここに表示されます...")
        self.output_text.setStyleSheet(OUTPUT_AREA_STYLE + SCROLLBAR_STYLE)
        output_layout.addWidget(self.output_text)

        splitter.addWidget(output_widget)
        splitter.setSizes([150, 450])

        layout.addWidget(splitter)

        return panel

    def _create_settings_panel(self) -> QWidget:
        """設定パネルを作成 (v4.0 新UI)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLLBAR_STYLE)
        scroll_content = QWidget()
        scroll_content.setStyleSheet(SECTION_CARD_STYLE + COMBO_BOX_STYLE)
        scroll_layout = QVBoxLayout(scroll_content)

        # === Claude設定 ===
        claude_group = QGroupBox("📌 Claude設定")
        claude_layout = QFormLayout()

        # モデル選択 (v7.1.0: CLAUDE_MODELSから動的生成)
        self.claude_model_combo = NoScrollComboBox()
        self.claude_model_combo.setToolTip("mixAI実行時に使用するClaudeモデルを選択します")
        default_idx = 0
        for i, model_def in enumerate(CLAUDE_MODELS):
            self.claude_model_combo.addItem(model_def["display_name"], userData=model_def["id"])
            self.claude_model_combo.setItemData(i, model_def["description"], Qt.ItemDataRole.ToolTipRole)
            if model_def["is_default"]:
                default_idx = i
        # 保存済みmodel_idから復元、なければデフォルト
        saved_model_id = getattr(self.config, 'claude_model_id', None) or getattr(self.config, 'claude_model', '')
        restored = False
        for i in range(self.claude_model_combo.count()):
            if self.claude_model_combo.itemData(i) == saved_model_id:
                self.claude_model_combo.setCurrentIndex(i)
                restored = True
                break
        if not restored:
            self.claude_model_combo.setCurrentIndex(default_idx)
        claude_layout.addRow("モデル:", self.claude_model_combo)

        # v6.0.0: 認証方式はCLI専用（API廃止）
        self.auth_mode_combo = NoScrollComboBox()
        self.auth_mode_combo.addItems(["CLI (Claude Max専用)"])
        self.auth_mode_combo.setCurrentIndex(0)
        self.auth_mode_combo.setEnabled(False)  # 変更不可
        claude_layout.addRow("認証方式:", self.auth_mode_combo)

        # 思考モード
        self.thinking_combo = NoScrollComboBox()
        self.thinking_combo.addItems(["OFF", "Standard", "Deep"])
        self.thinking_combo.setToolTip("Claudeの推論プロセスの深さ\nOFF: 通常 / Standard: 基本推論 / Deep: 詳細推論")
        self._set_combo_value(self.thinking_combo, self.config.thinking_mode)
        claude_layout.addRow("思考モード:", self.thinking_combo)

        claude_group.setLayout(claude_layout)
        scroll_layout.addWidget(claude_group)

        # === Ollama接続設定 ===
        ollama_group = QGroupBox("🖥️ Ollama接続")
        ollama_layout = QVBoxLayout()

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("ホストURL:"))
        self.ollama_url_edit = QLineEdit(self.config.ollama_url)
        url_layout.addWidget(self.ollama_url_edit)
        test_btn = QPushButton("接続テスト")
        test_btn.setToolTip("Ollamaサーバーへの接続を確認します")
        test_btn.clicked.connect(self._test_ollama_connection)
        url_layout.addWidget(test_btn)
        ollama_layout.addLayout(url_layout)

        self.ollama_status_label = QLabel("ステータス: 未確認")
        self.ollama_status_label.setStyleSheet("color: #9ca3af;")
        ollama_layout.addWidget(self.ollama_status_label)

        ollama_group.setLayout(ollama_layout)
        scroll_layout.addWidget(ollama_group)

        # === v7.0.0: 常駐モデル（GPU割り当て） ===
        always_load_group = QGroupBox("🔧 常駐モデル")
        always_load_layout = QVBoxLayout()

        # 制御AI (ministral-3:8b)
        image_row = QHBoxLayout()
        image_row.addWidget(QLabel("制御AI:"))
        self.image_model_combo = NoScrollComboBox()
        self.image_model_combo.setEditable(True)
        self.image_model_combo.addItems([
            "ministral-3:8b",
            "ministral-3:14b",
        ])
        self.image_model_combo.setCurrentText(self.config.image_analyzer_model)
        image_row.addWidget(self.image_model_combo)
        image_gpu = QLabel("→ 5070 Ti (6.0GB)")
        image_gpu.setStyleSheet("color: #22c55e; font-size: 10px;")
        image_row.addWidget(image_gpu)
        self.image_status = QLabel("🟢")
        image_row.addWidget(self.image_status)
        image_row.addStretch()
        always_load_layout.addLayout(image_row)

        # Embedding (qwen3-embedding:4b)
        embedding_row = QHBoxLayout()
        embedding_row.addWidget(QLabel("Embedding:"))
        self.embedding_model_combo = NoScrollComboBox()
        self.embedding_model_combo.setEditable(True)
        self.embedding_model_combo.addItems([
            "qwen3-embedding:4b",
            "qwen3-embedding:8b",
            "qwen3-embedding:0.6b",
            "bge-m3:latest",
        ])
        self.embedding_model_combo.setCurrentText(self.config.embedding_model)
        embedding_row.addWidget(self.embedding_model_combo)
        embedding_gpu = QLabel("→ 5070 Ti (2.5GB)")
        embedding_gpu.setStyleSheet("color: #22c55e; font-size: 10px;")
        embedding_row.addWidget(embedding_gpu)
        self.embedding_status = QLabel("🟢")
        embedding_row.addWidget(self.embedding_status)
        embedding_row.addStretch()
        always_load_layout.addLayout(embedding_row)

        total_label = QLabel("合計: ~8.5GB (常時ロード) / 5070 Ti: 8.5GB")
        total_label.setStyleSheet("color: #9ca3af; font-size: 10px; margin-top: 5px;")
        always_load_layout.addWidget(total_label)

        always_load_group.setLayout(always_load_layout)
        scroll_layout.addWidget(always_load_group)

        # === v7.0.0: 3Phase実行設定 ===
        phase_group = QGroupBox("🔄 3Phase実行設定")
        phase_layout = QVBoxLayout()

        phase_desc = QLabel(
            "3Phase: Phase 1(Claude計画立案) → Phase 2(ローカルLLM順次実行) → "
            "Phase 3(Claude比較統合)"
        )
        phase_desc.setStyleSheet("color: #9ca3af; font-size: 10px;")
        phase_desc.setWordWrap(True)
        phase_layout.addWidget(phase_desc)

        # カテゴリ別担当モデル
        cat_label = QLabel("■ カテゴリ別担当モデル（Phase 2で順次実行）")
        cat_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        phase_layout.addWidget(cat_label)

        # coding: コード生成・修正・レビュー
        coding_row = QHBoxLayout()
        coding_row.addWidget(QLabel("coding:"))
        self.coding_model_combo = NoScrollComboBox()
        self.coding_model_combo.setEditable(True)
        self.coding_model_combo.addItems([
            "devstral-2:123b",          # 75GB, SWE-bench最高 (推奨)
            "qwen3-coder-next:80b",     # 50GB, 軽量代替
            "qwen3-coder:30b",
        ])
        self.coding_model_combo.setCurrentText("devstral-2:123b")
        coding_row.addWidget(self.coding_model_combo)
        coding_vram = QLabel("(75GB)")
        coding_vram.setStyleSheet("color: #22c55e; font-size: 10px;")
        coding_row.addWidget(coding_vram)
        coding_row.addStretch()
        phase_layout.addLayout(coding_row)

        # research: 調査・RAG検索・情報収集
        research_row = QHBoxLayout()
        research_row.addWidget(QLabel("research:"))
        self.research_model_combo = NoScrollComboBox()
        self.research_model_combo.setEditable(True)
        self.research_model_combo.addItems([
            "command-a:111b",           # 67GB, 調査・RAG向き (推奨)
            "nemotron-3-nano:30b",      # 24GB, 代替
            "qwen3:30b",
        ])
        self.research_model_combo.setCurrentText("command-a:111b")
        research_row.addWidget(self.research_model_combo)
        research_vram = QLabel("(67GB)")
        research_vram.setStyleSheet("color: #22c55e; font-size: 10px;")
        research_row.addWidget(research_vram)
        research_row.addStretch()
        phase_layout.addLayout(research_row)

        # reasoning: 推論・論理検証・品質チェック
        reasoning_row = QHBoxLayout()
        reasoning_row.addWidget(QLabel("reasoning:"))
        self.reasoning_model_combo = NoScrollComboBox()
        self.reasoning_model_combo.setEditable(True)
        self.reasoning_model_combo.addItems([
            "gpt-oss:120b",            # 80GB, 推論最強 (推奨)
            "phi4-reasoning:14b",       # 9GB, 軽量代替
            "qwen3:30b",
        ])
        self.reasoning_model_combo.setCurrentText("gpt-oss:120b")
        reasoning_row.addWidget(self.reasoning_model_combo)
        reasoning_vram = QLabel("(80GB)")
        reasoning_vram.setStyleSheet("color: #22c55e; font-size: 10px;")
        reasoning_row.addWidget(reasoning_vram)
        reasoning_row.addStretch()
        phase_layout.addLayout(reasoning_row)

        # translation: 翻訳タスク
        translation_row = QHBoxLayout()
        translation_row.addWidget(QLabel("translation:"))
        self.translation_model_combo = NoScrollComboBox()
        self.translation_model_combo.setEditable(True)
        self.translation_model_combo.addItems([
            "translategemma:27b",       # 18GB, 翻訳専用
        ])
        self.translation_model_combo.setCurrentText("translategemma:27b")
        translation_row.addWidget(self.translation_model_combo)
        translation_vram = QLabel("(18GB)")
        translation_vram.setStyleSheet("color: #22c55e; font-size: 10px;")
        translation_row.addWidget(translation_vram)
        translation_row.addStretch()
        phase_layout.addLayout(translation_row)

        # vision: 画像解析・UI検証
        vision_row = QHBoxLayout()
        vision_row.addWidget(QLabel("vision:"))
        self.vision_model_combo = NoScrollComboBox()
        self.vision_model_combo.setEditable(True)
        self.vision_model_combo.addItems([
            "gemma3:27b",               # 18GB, 画像解析 (推奨)
            "mistral-small3.2:24b",     # 15GB, 代替
        ])
        self.vision_model_combo.setCurrentText("gemma3:27b")
        vision_row.addWidget(self.vision_model_combo)
        vision_vram = QLabel("(18GB)")
        vision_vram.setStyleSheet("color: #22c55e; font-size: 10px;")
        vision_row.addWidget(vision_vram)
        vision_row.addStretch()
        phase_layout.addLayout(vision_row)

        # 品質検証設定（ローカルLLM再実行）
        retry_label = QLabel("■ 品質検証設定（ローカルLLM再実行）")
        retry_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        phase_layout.addWidget(retry_label)

        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("最大再実行回数:"))
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setStyleSheet(SPINBOX_STYLE)
        self.max_retries_spin.setRange(0, 3)
        self.max_retries_spin.setValue(2)
        self.max_retries_spin.setToolTip("Phase 3で品質不足時にPhase 2を再実行する最大回数（0で再実行なし）")
        retry_row.addWidget(self.max_retries_spin)
        retry_row.addStretch()
        phase_layout.addLayout(retry_row)

        phase_group.setLayout(phase_layout)
        scroll_layout.addWidget(phase_group)

        # === v8.0.0: BIBLE Manager ===
        bible_group = QGroupBox("BIBLE Manager")
        bible_group.setToolTip("プロジェクトBIBLEの自動検出・解析・注入状態を表示します")
        bible_layout = QVBoxLayout()
        self.bible_panel = BibleStatusPanel()
        self.bible_panel.create_requested.connect(self._on_bible_create)
        self.bible_panel.update_requested.connect(self._on_bible_update)
        self.bible_panel.detail_requested.connect(self._on_bible_detail)
        self.bible_panel.path_submitted.connect(self._on_bible_path_submitted)
        bible_layout.addWidget(self.bible_panel)
        bible_group.setLayout(bible_layout)
        scroll_layout.addWidget(bible_group)

        # v8.3.1: 起動時BIBLE自動検出（カレントディレクトリから3段階探索）
        self._auto_discover_bible_on_startup()

        # v8.1.0: MCP設定は一般設定タブに統合済み
        self.mcp_status_label = QLabel("")  # 互換性用ダミー

        # === VRAM Budget Simulator ===
        vram_group = QGroupBox("🖥️ VRAM Budget Simulator")
        vram_group.setToolTip("各GPUのVRAM使用量をシミュレーションするツールです")
        vram_layout = QVBoxLayout()

        vram_desc = QLabel(
            "モデルを選択してGPUに配置し、VRAM使用量をシミュレーション。\n"
            "ドラッグ&ドロップでGPU間のモデル移動が可能です。"
        )
        vram_desc.setStyleSheet("color: #9ca3af; font-size: 10px;")
        vram_desc.setWordWrap(True)
        vram_layout.addWidget(vram_desc)

        # VRAM Compact Widget
        self.vram_compact = VRAMCompactWidget()
        vram_layout.addWidget(self.vram_compact)

        # VRAM Simulatorへのリンクボタン
        open_simulator_btn = QPushButton("📊 詳細シミュレーターを開く")
        open_simulator_btn.clicked.connect(self._open_vram_simulator)
        vram_layout.addWidget(open_simulator_btn)

        vram_group.setLayout(vram_layout)
        scroll_layout.addWidget(vram_group)

        # === GPUモニター ===
        gpu_group = QGroupBox("📊 GPUモニター")
        gpu_group.setToolTip("GPU使用率とVRAM消費をリアルタイムモニタリング\nLLM実行時に自動で記録を開始します")
        gpu_layout = QVBoxLayout()

        # GPU使用量グラフ
        self.gpu_graph = GPUUsageGraph()
        gpu_layout.addWidget(self.gpu_graph)

        # 時間軸選択行
        time_control_layout = QHBoxLayout()
        time_control_layout.addWidget(QLabel("時間範囲:"))
        self.gpu_time_range_combo = NoScrollComboBox()
        self.gpu_time_range_combo.addItems(list(GPUUsageGraph.TIME_RANGES.keys()))
        self.gpu_time_range_combo.setCurrentText("60秒")
        self.gpu_time_range_combo.currentTextChanged.connect(self._on_gpu_time_range_changed)
        time_control_layout.addWidget(self.gpu_time_range_combo)

        time_control_layout.addWidget(QLabel("  "))

        # シークバー（過去のデータ参照用）
        time_control_layout.addWidget(QLabel("過去を表示:"))
        self.gpu_seekbar = QSlider(Qt.Orientation.Horizontal)
        self.gpu_seekbar.setMinimum(0)
        self.gpu_seekbar.setMaximum(0)  # データがない時は0
        self.gpu_seekbar.setValue(0)
        self.gpu_seekbar.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gpu_seekbar.setTickInterval(60)
        self.gpu_seekbar.valueChanged.connect(self._on_gpu_seekbar_changed)
        self.gpu_seekbar.setMinimumWidth(150)
        time_control_layout.addWidget(self.gpu_seekbar)

        self.gpu_seekbar_label = QLabel("現在")
        self.gpu_seekbar_label.setMinimumWidth(50)
        time_control_layout.addWidget(self.gpu_seekbar_label)

        time_control_layout.addStretch()
        gpu_layout.addLayout(time_control_layout)

        # GPU情報テキスト
        self.gpu_info_label = QLabel("GPU情報を取得中...")
        self.gpu_info_label.setStyleSheet("color: #9ca3af;")
        gpu_layout.addWidget(self.gpu_info_label)

        # ボタン行
        gpu_btn_layout = QHBoxLayout()

        # 更新ボタン
        refresh_gpu_btn = QPushButton("🔄 GPU情報更新")
        refresh_gpu_btn.setToolTip("Ollamaにインストール済みのモデル一覧を取得します")
        refresh_gpu_btn.clicked.connect(self._refresh_gpu_info)
        gpu_btn_layout.addWidget(refresh_gpu_btn)

        # 記録開始/停止ボタン
        self.gpu_record_btn = QPushButton("▶ 記録開始")
        self.gpu_record_btn.clicked.connect(self._toggle_gpu_recording)
        gpu_btn_layout.addWidget(self.gpu_record_btn)

        # グラフクリアボタン
        clear_graph_btn = QPushButton("🗑️ クリア")
        clear_graph_btn.clicked.connect(self._clear_gpu_graph)
        gpu_btn_layout.addWidget(clear_graph_btn)

        # 現在に戻るボタン
        goto_now_btn = QPushButton("⏩ 現在")
        goto_now_btn.clicked.connect(self._on_gpu_goto_now)
        goto_now_btn.setToolTip("シークバーを現在に戻す")
        gpu_btn_layout.addWidget(goto_now_btn)

        gpu_btn_layout.addStretch()
        gpu_layout.addLayout(gpu_btn_layout)

        # 説明ラベル
        gpu_desc = QLabel("💡 LLM実行時に自動で5秒後にGPU使用量を記録します / スライダーで過去のデータを参照できます")
        gpu_desc.setStyleSheet("color: #6b7280; font-size: 9px;")
        gpu_layout.addWidget(gpu_desc)

        gpu_group.setLayout(gpu_layout)
        scroll_layout.addWidget(gpu_group)

        # GPU記録用タイマー
        self._gpu_recording = False
        self._gpu_timer = QTimer()
        self._gpu_timer.timeout.connect(self._record_gpu_usage)

        # v8.1.0: RAG設定は一般設定タブ「記憶・知識管理」に統合済み
        # 互換性用ダミーウィジェット
        self.rag_enabled_check = QCheckBox()
        self.rag_enabled_check.setChecked(True)
        self.rag_enabled_check.setVisible(False)
        self.rag_auto_save_check = QCheckBox()
        self.rag_auto_save_check.setChecked(True)
        self.rag_auto_save_check.setVisible(False)
        self.rag_threshold_combo = NoScrollComboBox()
        self.rag_threshold_combo.addItems(["低優先度以上", "中優先度以上", "高優先度のみ"])
        self.rag_threshold_combo.setCurrentIndex(1)
        self.rag_threshold_combo.setVisible(False)

        # === 保存ボタン (v8.4.2: soloAI/一般設定と統一 — 右寄せ小型) ===
        save_btn_layout = QHBoxLayout()
        save_btn_layout.addStretch()
        save_btn = QPushButton("💾 設定を保存")
        save_btn.setToolTip("mixAIタブの全設定をconfig/config.jsonに保存します")
        save_btn.clicked.connect(self._on_save_settings)
        save_btn_layout.addWidget(save_btn)
        scroll_layout.addLayout(save_btn_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # GPU情報を遅延読み込み
        QTimer.singleShot(500, self._refresh_gpu_info)

        return panel

    def _set_combo_value(self, combo: QComboBox, value: str):
        """ComboBoxの値を設定"""
        for i in range(combo.count()):
            if value.lower() in combo.itemText(i).lower():
                combo.setCurrentIndex(i)
                return
        combo.setCurrentText(value)

    def _set_combo_by_index(self, combo: QComboBox, index: int):
        """ComboBoxのインデックスを設定"""
        if 0 <= index < combo.count():
            combo.setCurrentIndex(index)

    def _on_tool_log_toggled(self, checked: bool):
        """ツールログの展開/折りたたみ"""
        self.tool_log_tree.setVisible(checked)
        if checked:
            self.tool_log_group.setTitle("▼ ツール実行ログ (クリックで折りたたみ)")
        else:
            self.tool_log_group.setTitle("▶ ツール実行ログ (クリックで展開)")

    def _on_execute(self):
        """実行開始"""
        prompt = self.input_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "入力エラー", "タスクを入力してください。")
            return

        # UI更新
        self.execute_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.tool_log_tree.clear()
        self.output_text.clear()

        # v5.0.0: 会話履歴にユーザーメッセージを追加
        self._conversation_history.append({
            "role": "user",
            "content": prompt,
        })

        # 設定を更新
        self._update_config_from_ui()

        # プロンプトから画像パスを抽出 (v4.4)
        image_path = self._extract_image_path(prompt)

        # v4.5: GPU記録を自動開始
        if not self._gpu_recording:
            self._start_gpu_recording()
        self._record_gpu_with_event("実行開始")

        # v7.0.0: 新3Phase MixAIOrchestrator を使用
        model_assignments = self._get_model_assignments()
        # v7.1.0: claude_model_id を優先使用
        claude_model_id = getattr(self.config, 'claude_model_id', None) or getattr(self.config, 'claude_model', DEFAULT_CLAUDE_MODEL_ID)
        orchestrator_config = {
            "claude_model": claude_model_id,
            "claude_model_id": claude_model_id,
            "timeout": self.config.claude_timeout_sec if hasattr(self.config, 'claude_timeout_sec') else 600,
            "auto_knowledge": True,
            "project_dir": os.getcwd(),
            "max_phase2_retries": self.max_retries_spin.value() if hasattr(self, 'max_retries_spin') else 2,
        }
        attached_files = []
        if image_path:
            attached_files.append(image_path)

        # v8.0.0: プロンプトからもBIBLE検索
        try:
            prompt_bibles = BibleDiscovery.discover_from_prompt(prompt)
            if prompt_bibles and not self.bible_panel.current_bible:
                self.bible_panel.update_bible(prompt_bibles[0])
                logger.info(f"[BIBLE] Discovered from prompt: {prompt_bibles[0].project_name}")
        except Exception as e:
            logger.debug(f"[BIBLE] Prompt discovery error: {e}")

        self.worker = MixAIOrchestrator(
            user_prompt=prompt,
            attached_files=attached_files,
            model_assignments=model_assignments,
            config=orchestrator_config,
        )

        # v8.0.0: BIBLE コンテキスト注入
        if self.bible_panel.current_bible:
            self.worker.set_bible_context(self.bible_panel.current_bible)

        # v8.1.0: メモリマネージャー注入
        if hasattr(self, '_memory_manager') and self._memory_manager:
            self.worker.set_memory_manager(self._memory_manager)

        self.worker.phase_changed.connect(self._on_phase_changed)
        self.worker.local_llm_started.connect(self._on_local_llm_started)
        self.worker.local_llm_finished.connect(self._on_local_llm_finished)
        self.worker.phase2_progress.connect(self._on_phase2_progress)
        self.worker.all_finished.connect(self._on_finished)
        self.worker.error_occurred.connect(self._on_error)
        # v8.0.0: BIBLE自律管理シグナル
        if hasattr(self.worker, 'bible_action_proposed'):
            self.worker.bible_action_proposed.connect(self._on_bible_action_proposed)
        self.worker.start()

        # v7.1.0: 選択モデル名をステータスに表示
        model_display = self.claude_model_combo.currentText() if hasattr(self, 'claude_model_combo') else claude_model_id
        self.statusChanged.emit(f"mixAI v7.1: 3Phase処理中... ({model_display})")

    def _extract_image_path(self, prompt: str) -> Optional[str]:
        """プロンプトから画像パスを抽出 (v4.4)"""
        import re
        import os

        # 画像ファイルの拡張子パターン
        image_extensions = r'\.(png|jpg|jpeg|gif|bmp|webp|PNG|JPG|JPEG|GIF|BMP|WEBP)'

        # パターン1: 引用符で囲まれたパス
        quoted_patterns = [
            r'"([^"]+' + image_extensions + r')"',
            r"'([^']+' + image_extensions + r')",
        ]

        for pattern in quoted_patterns:
            matches = re.findall(pattern, prompt)
            for match in matches:
                if isinstance(match, tuple):
                    path = match[0]
                else:
                    path = match
                if os.path.exists(path):
                    logger.info(f"[mixAI v4.4] 画像パス検出: {path}")
                    return path

        # パターン2: Windows絶対パス (C:\... or D:\...)
        win_pattern = r'([A-Za-z]:\\[^\s"\'<>|]+' + image_extensions + r')'
        matches = re.findall(win_pattern, prompt)
        for match in matches:
            if os.path.exists(match):
                logger.info(f"[mixAI v4.4] 画像パス検出(Windows): {match}")
                return match

        # パターン3: Unix絶対パス (/home/... or /Users/...)
        unix_pattern = r'(/[^\s"\'<>|]+' + image_extensions + r')'
        matches = re.findall(unix_pattern, prompt)
        for match in matches:
            if os.path.exists(match):
                logger.info(f"[mixAI v4.4] 画像パス検出(Unix): {match}")
                return match

        return None

    def _get_model_assignments(self) -> dict[str, str]:
        """v7.0.0: 設定UIからカテゴリ別モデル割り当てを取得"""
        assignments = {}
        if hasattr(self, 'coding_model_combo'):
            assignments["coding"] = self.coding_model_combo.currentText()
        if hasattr(self, 'research_model_combo'):
            assignments["research"] = self.research_model_combo.currentText()
        if hasattr(self, 'reasoning_model_combo'):
            assignments["reasoning"] = self.reasoning_model_combo.currentText()
        if hasattr(self, 'translation_model_combo'):
            assignments["translation"] = self.translation_model_combo.currentText()
        if hasattr(self, 'vision_model_combo'):
            assignments["vision"] = self.vision_model_combo.currentText()
        return assignments

    def _on_phase_changed(self, phase_num: int, description: str):
        """v7.0.0: Phase変更シグナルハンドラ"""
        percentage = {1: 10, 2: 40, 3: 70}.get(phase_num, 50)
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {description}")
        self._update_neural_flow_from_progress(description, percentage)
        # v8.0.0: PhaseIndicator更新
        if hasattr(self, 'phase_indicator'):
            self.phase_indicator.set_active_phase(phase_num - 1)

        # ツール実行ログにPhase開始を記録
        phase_item = QTreeWidgetItem(self.tool_log_tree)
        phase_item.setText(0, description)
        phase_item.setText(1, "実行中")
        phase_item.setText(2, "")

    def _on_local_llm_started(self, category: str, model: str):
        """v7.0.0: ローカルLLM実行開始"""
        self.statusChanged.emit(f"Phase 2: {category} ({model}) 実行中...")

    def _on_local_llm_finished(self, category: str, success: bool, elapsed: float):
        """v7.0.0: ローカルLLM実行完了"""
        status = "完了" if success else "失敗"
        item = QTreeWidgetItem(self.tool_log_tree)
        item.setText(0, f"  Phase 2: {category}")
        item.setText(1, status)
        item.setText(2, f"{elapsed:.1f}s")

    def _on_phase2_progress(self, completed: int, total: int):
        """v7.0.0: Phase 2進捗"""
        pct = 40 + int((completed / max(total, 1)) * 30)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{pct}% - Phase 2: {completed}/{total} 完了")

    def _on_cancel(self):
        """キャンセル"""
        if self.worker:
            self.worker.cancel()
            self.statusChanged.emit("処理をキャンセルしました")

    def _on_clear(self):
        """クリア"""
        self.output_text.clear()
        self.tool_log_tree.clear()
        self.input_text.clear()
        # v5.1: 添付ファイルもクリア
        self.attachment_bar.clear_all()
        self._attached_files.clear()
        # Neural Flowをリセット
        if hasattr(self, 'neural_flow'):
            self.neural_flow.reset_all()
        # v8.0.0: PhaseIndicatorリセット
        if hasattr(self, 'phase_indicator'):
            self.phase_indicator.reset()

    # =========================================================================
    # v5.1: ファイル添付・スニペット関連メソッド
    # =========================================================================

    def _on_attach_file(self):
        """ファイル添付ボタンクリック"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "ファイルを選択", "",
            "全ファイル (*);;Python (*.py);;テキスト (*.txt *.md);;画像 (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if files:
            self.attachment_bar.add_files(files)

    def _on_attachments_changed(self, files: List[str]):
        """添付ファイルが変更された"""
        self._attached_files = files.copy()
        logger.info(f"[mixAI v5.1] 添付ファイル更新: {len(files)}件")

        # v8.0.0: 添付ファイルからBIBLE自動検出
        if files:
            self._discover_bible_from_files(files)

    # =========================================================================
    # v8.0.0: BIBLE Manager メソッド
    # =========================================================================

    def _auto_discover_bible_on_startup(self):
        """v8.3.1: 起動時にカレントディレクトリからBIBLE自動検出"""
        try:
            cwd = os.getcwd()
            logger.info(f"[BIBLE] Startup auto-discovery from: {cwd}")
            bibles = BibleDiscovery.discover(cwd)
            if bibles:
                best = bibles[0]
                self.bible_panel.update_bible(best)
                logger.info(
                    f"[BIBLE] Startup auto-discovered: {best.project_name} "
                    f"v{best.version} at {best.file_path}"
                )
            else:
                logger.info("[BIBLE] Startup auto-discovery: no BIBLE found")
        except Exception as e:
            logger.debug(f"[BIBLE] Startup discovery error: {e}")

    def _on_bible_path_submitted(self, path: str):
        """v8.3.1: パス入力欄からのBIBLE検索"""
        try:
            logger.info(f"[BIBLE] Manual path search: {path}")
            bibles = BibleDiscovery.discover(path)
            if bibles:
                best = bibles[0]
                self.bible_panel.update_bible(best)
                self.bible_notification.show_bible(best)
                logger.info(
                    f"[BIBLE] Found from manual path: {best.project_name} "
                    f"v{best.version}"
                )
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "BIBLE検索",
                    f"指定パスからBIBLEファイルが見つかりませんでした:\n{path}\n\n"
                    "3段階探索（カレント→子→親）を実行しましたが、"
                    "BIBLEファイルが存在しません。"
                )
                logger.info(f"[BIBLE] No BIBLE found at manual path: {path}")
        except Exception as e:
            logger.error(f"[BIBLE] Manual path discovery error: {e}")

    def _discover_bible_from_files(self, files: List[str]):
        """添付ファイルからBIBLE自動検出"""
        try:
            for f in files:
                bibles = BibleDiscovery.discover(f)
                if bibles:
                    best = bibles[0]
                    self.bible_panel.update_bible(best)
                    self.bible_notification.show_bible(best)
                    logger.info(
                        f"[BIBLE] Auto-discovered: {best.project_name} "
                        f"v{best.version} from {f}"
                    )
                    return
        except Exception as e:
            logger.debug(f"[BIBLE] Discovery from files error: {e}")

    def _on_bible_add_context(self, bible):
        """通知バーの「コンテキストに追加」ボタン"""
        self.bible_panel.update_bible(bible)
        logger.info(f"[BIBLE] Context added: {bible.project_name} v{bible.version}")

    def _on_bible_create(self):
        """BIBLE新規作成"""
        try:
            from ..bible.bible_lifecycle import BibleLifecycleManager, BibleAction
            project_dir = os.getcwd()
            result = {"changed_files": [], "app_version": APP_VERSION}
            content = BibleLifecycleManager.execute_action(
                BibleAction.CREATE_NEW, None, result, project_dir
            )
            if content:
                from pathlib import Path
                bible_path = Path(project_dir) / "BIBLE.md"
                bible_path.write_text(content, encoding="utf-8")
                # 再検出してパネル更新
                bibles = BibleDiscovery.discover(str(bible_path))
                if bibles:
                    self.bible_panel.update_bible(bibles[0])
                logger.info(f"[BIBLE] Created new BIBLE at {bible_path}")
                QMessageBox.information(
                    self, "BIBLE作成完了",
                    f"BIBLE.md を作成しました:\n{bible_path}"
                )
        except Exception as e:
            logger.error(f"[BIBLE] Create error: {e}")
            QMessageBox.warning(self, "エラー", f"BIBLE作成に失敗しました: {e}")

    def _on_bible_update(self):
        """BIBLE更新"""
        bible = self.bible_panel.current_bible
        if not bible:
            return
        try:
            from ..bible.bible_lifecycle import BibleLifecycleManager, BibleAction
            result = {"changed_files": [], "app_version": APP_VERSION}
            action, reason = BibleLifecycleManager.determine_action(
                bible, result, {}
            )
            if action != BibleAction.NONE:
                content = BibleLifecycleManager.execute_action(
                    action, bible, result, str(bible.file_path.parent)
                )
                if content:
                    bible.file_path.write_text(content, encoding="utf-8")
                    # 再パースしてパネル更新
                    from ..bible.bible_parser import BibleParser
                    updated = BibleParser.parse_full(bible.file_path)
                    if updated:
                        self.bible_panel.update_bible(updated)
                    logger.info(f"[BIBLE] Updated: {action.value} - {reason}")
            else:
                QMessageBox.information(
                    self, "BIBLE", "現在更新が必要な項目はありません。"
                )
        except Exception as e:
            logger.error(f"[BIBLE] Update error: {e}")

    def _on_bible_detail(self):
        """BIBLE詳細表示"""
        bible = self.bible_panel.current_bible
        if not bible:
            return
        missing = bible.missing_required_sections
        missing_str = (
            "\n不足セクション: " + ", ".join(s.value for s in missing)
            if missing else "\n全必須セクションあり"
        )
        sections_str = "\n".join(
            f"  - {s.title} ({s.type.value}, 充実度{s.completeness:.0%})"
            for s in bible.sections
        )
        detail = (
            f"プロジェクト: {bible.project_name}\n"
            f"バージョン: {bible.version}\n"
            f"コードネーム: {bible.codename or '(なし)'}\n"
            f"ファイル: {bible.file_path}\n"
            f"行数: {bible.line_count}\n"
            f"セクション数: {len(bible.sections)}\n"
            f"完全性スコア: {bible.completeness_score:.0%}"
            f"{missing_str}\n\n"
            f"セクション一覧:\n{sections_str}"
        )
        QMessageBox.information(self, "BIBLE詳細", detail)

    def _on_bible_action_proposed(self, action, reason):
        """Post-Phase: BIBLE自律管理アクション提案"""
        try:
            from ..bible.bible_lifecycle import BibleAction
            if action == BibleAction.NONE:
                return
            reply = QMessageBox.question(
                self, "BIBLE更新提案",
                f"{reason}\n\nこの操作を実行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                from ..bible.bible_lifecycle import BibleLifecycleManager
                bible = self.bible_panel.current_bible
                result = {"changed_files": [], "app_version": APP_VERSION}
                project_dir = os.getcwd()
                content = BibleLifecycleManager.execute_action(
                    action, bible, result, project_dir
                )
                if content and bible:
                    bible.file_path.write_text(content, encoding="utf-8")
                    from ..bible.bible_parser import BibleParser
                    updated = BibleParser.parse_full(bible.file_path)
                    if updated:
                        self.bible_panel.update_bible(updated)
                    logger.info(f"[BIBLE] Action executed: {action.value}")
        except Exception as e:
            logger.error(f"[BIBLE] Action execution error: {e}")

    def _on_cite_history(self):
        """履歴から引用ボタンクリック"""
        try:
            from ..ui.components.history_citation_widget import HistoryCitationDialog
            dialog = HistoryCitationDialog(storage_key="mixai_history", parent=self)
            if dialog.exec():
                citation = dialog.get_selected_citation()
                if citation:
                    current = self.input_text.toPlainText()
                    if current:
                        self.input_text.setPlainText(current + "\n\n" + citation)
                    else:
                        self.input_text.setPlainText(citation)
        except ImportError:
            QMessageBox.information(self, "機能未実装", "履歴引用機能は準備中です。")

    def _get_snippet_manager(self):
        """スニペットマネージャーを取得 (v5.1.1: soloAIと共通化)"""
        from ..claude.snippet_manager import SnippetManager
        from pathlib import Path
        import sys

        # PyInstallerでビルドされた場合とそうでない場合でパスを分岐
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた場合: exeと同じディレクトリを使用
            app_dir = Path(sys.executable).parent
        else:
            # 開発時: プロジェクトルートを使用
            app_dir = Path(__file__).parent.parent.parent

        data_dir = app_dir / "data"
        unipet_dir = app_dir / "ユニペット"

        # フォルダがなければ作成
        data_dir.mkdir(parents=True, exist_ok=True)
        unipet_dir.mkdir(parents=True, exist_ok=True)

        return SnippetManager(data_dir=data_dir, unipet_dir=unipet_dir)

    def _on_snippet_menu(self):
        """スニペットメニュー表示 (v5.1.1: soloAIと共通化)"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint

        try:
            snippet_manager = self._get_snippet_manager()
            snippets = snippet_manager.get_all()

            menu = QMenu(self)

            if not snippets:
                no_snippet_action = menu.addAction("スニペットがありません")
                no_snippet_action.setEnabled(False)
            else:
                # カテゴリでグループ化
                categories = snippet_manager.get_categories()
                uncategorized = [s for s in snippets if not s.get("category")]

                # カテゴリがあるスニペット
                for category in categories:
                    cat_menu = menu.addMenu(f"📁 {category}")
                    cat_snippets = snippet_manager.get_by_category(category)
                    for snippet in cat_snippets:
                        action = cat_menu.addAction(snippet.get("name", "無題"))
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

                # カテゴリなしスニペット
                if uncategorized:
                    if categories:
                        menu.addSeparator()
                    for snippet in uncategorized:
                        action = menu.addAction(f"📋 {snippet.get('name', '無題')}")
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

            menu.addSeparator()
            open_folder_action = menu.addAction("📂 ユニペットフォルダを開く")
            open_folder_action.triggered.connect(lambda: snippet_manager.open_unipet_folder())

            # ボタンの下に表示
            btn_pos = self.mixai_snippet_btn.mapToGlobal(QPoint(0, self.mixai_snippet_btn.height()))
            menu.exec(btn_pos)

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_menu] Error: {e}", exc_info=True)
            QMessageBox.warning(self, "エラー", f"スニペットメニュー表示中にエラー:\n{e}")

    def _insert_snippet(self, snippet: dict):
        """スニペットを入力欄に挿入 (v5.1.1)"""
        content = snippet.get("content", "")
        name = snippet.get("name", "無題")

        current_text = self.input_text.toPlainText()
        if current_text:
            new_text = f"{current_text}\n\n{content}"
        else:
            new_text = content

        self.input_text.setPlainText(new_text)
        self.statusChanged.emit(f"📋 スニペット「{name}」を挿入しました")
        logger.info(f"[MixAI] Snippet inserted: {name}")

    def _on_snippet_add(self):
        """スニペット追加 (v5.1.1: soloAIと共通化)"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("スニペット追加")
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel("スニペット名:")
            layout.addWidget(name_label)
            name_input = QLineEdit()
            name_input.setPlaceholderText("例: コードレビュー依頼")
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel("カテゴリ (任意):")
            layout.addWidget(cat_label)
            cat_input = QLineEdit()
            cat_input.setPlaceholderText("例: 開発依頼")
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel("内容:")
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlaceholderText("スニペットの内容を入力...")
            content_input.setMinimumHeight(150)
            layout.addWidget(content_input)

            # ボタン
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                name = name_input.text().strip()
                content = content_input.toPlainText().strip()

                if not name or not content:
                    QMessageBox.warning(self, "入力エラー", "名前と内容は必須です。")
                    return

                category = cat_input.text().strip()
                snippet_manager = self._get_snippet_manager()
                snippet_manager.add(name=name, content=content, category=category)

                self.statusChanged.emit(f"📋 スニペット「{name}」を追加しました")
                logger.info(f"[MixAI] Snippet added: {name}")

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_add] Error: {e}", exc_info=True)
            QMessageBox.warning(self, "エラー", f"スニペット追加中にエラー:\n{e}")

    def _on_snippet_context_menu(self, pos):
        """スニペット右クリックメニュー（編集・削除）(v5.2.0: ユニペット削除対応)"""
        from PyQt6.QtWidgets import QMenu

        try:
            snippet_manager = self._get_snippet_manager()
            snippets = snippet_manager.get_all()

            if not snippets:
                return

            menu = QMenu(self)

            # 編集メニュー
            edit_menu = menu.addMenu("✏️ 編集")
            for snippet in snippets:
                action = edit_menu.addAction(snippet.get("name", "無題"))
                action.triggered.connect(lambda checked, s=snippet: self._edit_snippet(s))

            # 削除メニュー (v5.2.0: ユニペットも削除可能に)
            delete_menu = menu.addMenu("🗑️ 削除")
            for snippet in snippets:
                source = snippet.get("source", "json")
                if source == "unipet":
                    action = delete_menu.addAction(f"🗂️ {snippet.get('name', '無題')} (ファイル削除)")
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))
                else:
                    action = delete_menu.addAction(snippet.get("name", "無題"))
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))

            menu.addSeparator()
            reload_action = menu.addAction("🔄 再読み込み")
            reload_action.triggered.connect(lambda: (self._get_snippet_manager().reload(), self.statusChanged.emit("📋 スニペットを再読み込みしました")))

            menu.exec(self.mixai_snippet_add_btn.mapToGlobal(pos))

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_context_menu] Error: {e}", exc_info=True)

    def _edit_snippet(self, snippet: dict):
        """スニペット編集ダイアログ (v5.1.1)"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"スニペット編集: {snippet.get('name', '無題')}")
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel("スニペット名:")
            layout.addWidget(name_label)
            name_input = QLineEdit(snippet.get("name", ""))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel("カテゴリ:")
            layout.addWidget(cat_label)
            cat_input = QLineEdit(snippet.get("category", ""))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel("内容:")
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlainText(snippet.get("content", ""))
            content_input.setMinimumHeight(150)
            layout.addWidget(content_input)

            # ボタン
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                snippet_manager = self._get_snippet_manager()
                snippet_manager.update(
                    snippet.get("id"),
                    name=name_input.text().strip(),
                    content=content_input.toPlainText().strip(),
                    category=cat_input.text().strip()
                )
                self.statusChanged.emit(f"📋 スニペット「{name_input.text()}」を更新しました")
                logger.info(f"[MixAI] Snippet updated: {name_input.text()}")

        except Exception as e:
            logger.error(f"[MixAI._edit_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, "エラー", f"スニペット編集中にエラー:\n{e}")

    def _delete_snippet(self, snippet: dict):
        """スニペット削除 (v5.2.0: ユニペットファイル削除対応)"""
        name = snippet.get("name", "無題")
        is_unipet = snippet.get("source") == "unipet"

        # ユニペットの場合は警告を追加
        if is_unipet:
            file_path = snippet.get("file_path", "")
            msg = f"ユニペット「{name}」を削除しますか？\n\nファイルも削除されます:\n{file_path}"
        else:
            msg = f"スニペット「{name}」を削除しますか？"

        reply = QMessageBox.question(
            self,
            "スニペット削除",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                snippet_manager = self._get_snippet_manager()
                # ユニペットの場合はdelete_file=Trueを渡す
                if snippet_manager.delete(snippet.get("id"), delete_file=is_unipet):
                    self.statusChanged.emit(f"🗑️ スニペット「{name}」を削除しました")
                    logger.info(f"[MixAI] Snippet deleted: {name}")
                else:
                    QMessageBox.warning(self, "削除失敗", f"スニペット「{name}」の削除に失敗しました。")
            except Exception as e:
                logger.error(f"[MixAI._delete_snippet] Error: {e}", exc_info=True)
                QMessageBox.warning(self, "エラー", f"スニペット削除中にエラー:\n{e}")

    def _on_progress(self, message: str, percentage: int):
        """進捗更新"""
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {message}")

        # Neural Flow Visualizerの状態更新
        self._update_neural_flow_from_progress(message, percentage)

    def _update_neural_flow_from_progress(self, message: str, percentage: int):
        """v7.0.0: プログレスメッセージからNeural Flowの状態を更新（3Phase対応）"""
        if not hasattr(self, 'neural_flow'):
            return

        # v7.0.0: 3Phase マッピング
        stage_to_phase = {
            "phase 1": 1, "claude計画": 1, "計画立案": 1,
            "phase 2": 2, "ローカルllm": 2, "順次実行": 2, "再実行": 2,
            "phase 3": 3, "claude統合": 3, "比較統合": 3, "再統合": 3,
            "完了": 3,
        }

        msg_lower = message.lower()

        for key, phase_id in stage_to_phase.items():
            if key in msg_lower:
                if "完了" in message or percentage >= 100:
                    self.neural_flow.set_phase_state(phase_id, PhaseState.COMPLETED)
                elif "中" in message or "実行" in message or "開始" in message:
                    # 前のPhaseを完了状態に
                    for prev_phase in range(1, phase_id):
                        self.neural_flow.set_phase_state(prev_phase, PhaseState.COMPLETED)
                    self.neural_flow.set_phase_state(phase_id, PhaseState.RUNNING)
                break

    def _on_tool_executed(self, result: dict):
        """ツール実行完了"""
        # v4.5: GPU使用量を記録（5秒後にも記録）
        stage_name = result.get("stage", "Tool")
        model_name_full = result.get("model", "")
        self._schedule_gpu_record_after_llm(stage_name)

        # モデル名を取得（長い場合は短縮表示）
        model_name = model_name_full
        if len(model_name) > 25:
            model_name = model_name[:22] + "..."

        output_text = result.get("output", "")
        output_display = output_text[:40] + "..." if len(output_text) > 40 else output_text

        item = QTreeWidgetItem([
            result.get("stage", ""),
            model_name,  # モデル名列を追加
            "✅" if result.get("success") else "❌",
            f"{result.get('execution_time_ms', 0):.0f}ms",
            output_display,
        ])

        if result.get("success"):
            item.setForeground(2, QColor("#22c55e"))  # ステータス列のインデックスを更新
        else:
            item.setForeground(2, QColor("#ef4444"))

        # モデル名列に色を付ける（識別しやすくするため）
        item.setForeground(1, QColor("#60a5fa"))  # 青系

        self.tool_log_tree.addTopLevelItem(item)

    def _on_finished(self, result: str):
        """完了"""
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        # v7.0.0: Neural Flow - 全Phase完了（3Phase）
        if hasattr(self, 'neural_flow'):
            for phase_id in range(1, 4):
                self.neural_flow.set_phase_state(phase_id, PhaseState.COMPLETED)
        # v8.0.0: PhaseIndicator全完了
        if hasattr(self, 'phase_indicator'):
            self.phase_indicator.set_all_completed()

        # 結果を表示（Markdown→HTMLレンダリング）
        self.output_text.setHtml(markdown_to_html(result))
        self.statusChanged.emit("mixAI v8.0: 完了")
        self.worker = None

        # v5.0.0: 会話履歴にAI応答を追加
        self._conversation_history.append({
            "role": "assistant",
            "content": result,
        })

        # v5.0.0: 自動ナレッジ管理（バックグラウンド実行）
        self._start_knowledge_processing()

    def _on_error(self, error: str):
        """エラー"""
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        # v7.0.0: Neural Flow - エラー状態表示（3Phase）
        if hasattr(self, 'neural_flow'):
            # 現在実行中のPhaseを失敗状態に
            for phase_id in range(1, 4):
                from ..widgets.neural_visualizer import PhaseState
                state = self.neural_flow._phase_states.get(phase_id, PhaseState.IDLE)
                if state == PhaseState.RUNNING:
                    self.neural_flow.set_phase_state(phase_id, PhaseState.FAILED)
                    break

        self.output_text.setPlainText(f"❌ エラー:\n\n{error}")
        self.statusChanged.emit(f"エラー: {error[:50]}...")
        self.worker = None

    # =========================================================================
    # v5.0.0: 自動ナレッジ管理
    # =========================================================================

    def _start_knowledge_processing(self):
        """v5.0.0: 自動ナレッジ処理を開始（バックグラウンド）"""
        if not self._conversation_history:
            return

        try:
            from ..knowledge import KnowledgeWorker, get_knowledge_manager

            km = get_knowledge_manager()
            self._knowledge_worker = KnowledgeWorker(
                conversation=self._conversation_history.copy(),
                knowledge_manager=km,
            )
            self._knowledge_worker.completed.connect(self._on_knowledge_saved)
            self._knowledge_worker.error.connect(self._on_knowledge_error)
            self._knowledge_worker.start()

            logger.info("[mixAI v5.0] ナレッジ処理をバックグラウンドで開始")

        except ImportError as e:
            logger.warning(f"[mixAI v5.0] ナレッジモジュールが利用できません: {e}")
        except Exception as e:
            logger.warning(f"[mixAI v5.0] ナレッジ処理開始エラー: {e}")

    def _on_knowledge_saved(self, knowledge: dict):
        """v5.0.0: ナレッジ保存完了"""
        topic = knowledge.get("topic", "不明")
        models_used = knowledge.get("ondemand_models_used", [])
        model_info = f" (検証: {', '.join(models_used)})" if models_used else ""
        self.statusChanged.emit(f"💾 ナレッジ保存: {topic}{model_info}")
        logger.info(f"[mixAI v5.0] ナレッジ保存完了: {topic}")
        self._knowledge_worker = None

    def _on_knowledge_error(self, error: str):
        """v5.0.0: ナレッジ保存エラー（ユーザーの操作には影響しない）"""
        logger.warning(f"[mixAI v5.0] ナレッジ保存エラー: {error}")
        self._knowledge_worker = None

    def _update_config_from_ui(self):
        """UIから設定を更新"""
        # Claude設定 (v7.1.0: model_id直接保存)
        selected_model_id = self.claude_model_combo.currentData()
        if selected_model_id:
            self.config.claude_model_id = selected_model_id
            self.config.claude_model = selected_model_id
        else:
            self.config.claude_model_id = DEFAULT_CLAUDE_MODEL_ID
            self.config.claude_model = DEFAULT_CLAUDE_MODEL_ID

        self.config.claude_auth_mode = "cli" if self.auth_mode_combo.currentIndex() == 0 else "api"
        self.config.thinking_mode = self.thinking_combo.currentText()

        # Ollama設定
        self.config.ollama_url = self.ollama_url_edit.text().strip()

        # 常駐モデル設定 (v7.0.0: 制御AI + Embedding)
        self.config.image_analyzer_model = self.image_model_combo.currentText()
        self.config.embedding_model = self.embedding_model_combo.currentText()

        # RAG設定
        self.config.rag_enabled = self.rag_enabled_check.isChecked()
        self.config.rag_auto_save = self.rag_auto_save_check.isChecked()
        threshold_map = {0: "low", 1: "medium", 2: "high"}
        self.config.rag_save_threshold = threshold_map.get(self.rag_threshold_combo.currentIndex(), "medium")

        # v8.4.2: 品質検証設定（Phase 2再実行回数）
        if hasattr(self, 'max_retries_spin'):
            self.config.max_phase2_retries = self.max_retries_spin.value()

    def _on_save_settings(self):
        """設定保存"""
        self._update_config_from_ui()
        self._save_config()
        QMessageBox.information(self, "保存完了", "設定を保存しました。")
        self.statusChanged.emit("設定を保存しました")

    def _test_ollama_connection(self):
        """Ollama接続テスト（モデル別ステータス確認）"""
        try:
            import ollama
            import httpx
            url = self.ollama_url_edit.text().strip()
            client = ollama.Client(host=url)

            start = time.time()
            response = client.list()
            latency = time.time() - start

            # インストール済みモデル一覧
            installed_models = {}
            if hasattr(response, 'models'):
                raw_models = response.models
            elif isinstance(response, dict) and 'models' in response:
                raw_models = response['models']
            else:
                raw_models = []

            for model in raw_models:
                if isinstance(model, dict):
                    name = model.get('model') or model.get('name', '')
                    size = model.get('size', 0)
                else:
                    name = getattr(model, 'model', None) or getattr(model, 'name', '')
                    size = getattr(model, 'size', 0)
                if name:
                    installed_models[name] = {"size_gb": size / 1e9 if isinstance(size, int) else 0}

            # ロード中のモデル一覧を取得
            loaded_models = {}
            try:
                with httpx.Client(timeout=5) as http_client:
                    ps_resp = http_client.get(f"{url}/api/ps")
                    if ps_resp.status_code == 200:
                        ps_data = ps_resp.json()
                        for m in ps_data.get("models", []):
                            loaded_models[m.get("name", "")] = {
                                "size_vram": m.get("size_vram", 0),
                            }
            except Exception:
                pass  # ロード中モデル取得失敗は無視

            # 設定モデルのステータスを確認
            configured_models = self._get_configured_models()
            status_lines = []

            for model_info in configured_models:
                name = model_info["name"]
                role = model_info["role"]
                model_type = model_info["type"]

                # ステータス判定
                is_loaded = self._match_model_name(name, loaded_models)
                is_installed = self._match_model_name(name, installed_models)

                if is_loaded:
                    vram_info = loaded_models.get(name, {}).get("size_vram", 0)
                    vram_mb = vram_info // (1024 * 1024) if vram_info else 0
                    icon = "🟢"
                    status = "ロード中"
                    vram_text = f"{vram_mb:,}MB" if vram_mb else "-"
                elif is_installed:
                    icon = "🟡"
                    status = "待機中"
                    vram_text = "-"
                else:
                    icon = "🔴"
                    status = "未DL"
                    vram_text = "-"

                type_label = "常時" if model_type == "resident" else "OD"
                status_lines.append(f"{icon} {name:<26} {status:<8} {vram_text:<10} [{type_label}]")

            # 結果を表示
            header = f"✅ 接続成功 ({latency:.2f}秒)\n\nモデルステータス:\n"
            self.ollama_status_label.setText(header + "\n".join(status_lines))
            self.ollama_status_label.setStyleSheet("color: #22c55e;")

            # モデルリストを更新
            self._update_model_combos(response)

        except ImportError:
            self.ollama_status_label.setText("❌ ollamaライブラリがインストールされていません")
            self.ollama_status_label.setStyleSheet("color: #ef4444;")
        except Exception as e:
            self.ollama_status_label.setText(f"❌ 接続失敗: {str(e)[:50]}")
            self.ollama_status_label.setStyleSheet("color: #ef4444;")

    def _check_claude_cli_mcp(self):
        """v7.0.0: Claude Code CLIのMCPサーバー設定を確認"""
        try:
            # Claude CLIの存在確認
            from ..backends.claude_cli_backend import find_claude_command
            claude_cmd = find_claude_command()

            if not claude_cmd:
                self.mcp_status_label.setText("  ❌ Claude CLIが見つかりません")
                self.mcp_status_label.setStyleSheet("color: #ef4444; font-size: 10px;")
                return

            # claude mcp list でMCPサーバー一覧を取得
            result = subprocess.run(
                [claude_cmd, "mcp", "list"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                status_text = f"  ✅ Claude CLI: {claude_cmd}\n  MCPサーバー ({len(lines)}件):\n"
                for line in lines:
                    status_text += f"    {line}\n"
                self.mcp_status_label.setText(status_text.rstrip())
                self.mcp_status_label.setStyleSheet("color: #22c55e; font-size: 10px;")
            elif result.returncode == 0:
                self.mcp_status_label.setText(
                    f"  ✅ Claude CLI: {claude_cmd}\n  MCPサーバー: 未設定"
                )
                self.mcp_status_label.setStyleSheet("color: #f59e0b; font-size: 10px;")
            else:
                self.mcp_status_label.setText(
                    f"  ⚠️ Claude CLI: {claude_cmd}\n  MCP確認失敗: {result.stderr[:100]}"
                )
                self.mcp_status_label.setStyleSheet("color: #f59e0b; font-size: 10px;")

        except subprocess.TimeoutExpired:
            self.mcp_status_label.setText("  ⚠️ Claude CLI応答タイムアウト")
            self.mcp_status_label.setStyleSheet("color: #f59e0b; font-size: 10px;")
        except Exception as e:
            self.mcp_status_label.setText(f"  ❌ エラー: {str(e)[:80]}")
            self.mcp_status_label.setStyleSheet("color: #ef4444; font-size: 10px;")

    def _get_configured_models(self) -> List[Dict[str, Any]]:
        """設定済みモデル一覧を取得 (v7.0.0: 3Phase設定UI対応)"""
        models = []

        # 常駐モデル（基本機能用）
        if hasattr(self, 'image_model_combo'):
            models.append({"name": self.image_model_combo.currentText(), "role": "制御AI", "type": "resident"})
        if hasattr(self, 'embedding_model_combo'):
            models.append({"name": self.embedding_model_combo.currentText(), "role": "Embedding", "type": "resident"})

        # 3Phase カテゴリ別モデル（Phase 2で順次実行）
        if hasattr(self, 'coding_model_combo'):
            models.append({"name": self.coding_model_combo.currentText(), "role": "coding", "type": "phase2"})
        if hasattr(self, 'research_model_combo'):
            models.append({"name": self.research_model_combo.currentText(), "role": "research", "type": "phase2"})
        if hasattr(self, 'reasoning_model_combo'):
            models.append({"name": self.reasoning_model_combo.currentText(), "role": "reasoning", "type": "phase2"})
        if hasattr(self, 'translation_model_combo'):
            models.append({"name": self.translation_model_combo.currentText(), "role": "translation", "type": "phase2"})
        if hasattr(self, 'vision_model_combo'):
            models.append({"name": self.vision_model_combo.currentText(), "role": "vision", "type": "phase2"})

        return models

    def _match_model_name(self, name: str, model_dict: Dict[str, Any]) -> bool:
        """モデル名のマッチング（タグ省略対応）"""
        if name in model_dict:
            return True
        for key in model_dict:
            if key.startswith(name.split(":")[0]) or name.startswith(key.split(":")[0]):
                return True
        return False

    # =========================================================================
    # GPU動的記録・グラフ表示機能（時間軸選択・シークバー対応）
    # =========================================================================

    def _toggle_gpu_recording(self):
        """GPU記録の開始/停止"""
        if self._gpu_recording:
            self._stop_gpu_recording()
        else:
            self._start_gpu_recording()

    def _start_gpu_recording(self):
        """GPU記録を開始"""
        self._gpu_recording = True
        self.gpu_record_btn.setText("⏹ 記録停止")
        self.gpu_record_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self._gpu_timer.start(1000)  # 1秒間隔で記録
        self.statusChanged.emit("GPU記録を開始しました")

    def _stop_gpu_recording(self):
        """GPU記録を停止"""
        self._gpu_recording = False
        self._gpu_timer.stop()
        self.gpu_record_btn.setText("▶ 記録開始")
        self.gpu_record_btn.setStyleSheet("")
        self.statusChanged.emit("GPU記録を停止しました")

    def _clear_gpu_graph(self):
        """GPUグラフをクリア"""
        self.gpu_graph.clear_data()
        self.gpu_seekbar.setMaximum(0)
        self.gpu_seekbar.setValue(0)
        self.gpu_seekbar_label.setText("現在")
        self.statusChanged.emit("GPUグラフをクリアしました")

    def _on_gpu_time_range_changed(self, text: str):
        """時間範囲が変更された"""
        seconds = GPUUsageGraph.TIME_RANGES.get(text, 60)
        self.gpu_graph.set_time_range(seconds)
        self._update_gpu_seekbar_range()
        self.statusChanged.emit(f"GPU時間範囲を{text}に変更しました")

    def _on_gpu_seekbar_changed(self, value: int):
        """シークバーの値が変更された"""
        self.gpu_graph.set_view_offset(value)
        if value == 0:
            self.gpu_seekbar_label.setText("現在")
        elif value < 60:
            self.gpu_seekbar_label.setText(f"-{value}秒")
        elif value < 3600:
            self.gpu_seekbar_label.setText(f"-{value // 60}分")
        else:
            self.gpu_seekbar_label.setText(f"-{value // 3600}時間")

    def _on_gpu_goto_now(self):
        """現在に戻る"""
        self.gpu_seekbar.setValue(0)
        self.gpu_graph.set_view_offset(0)
        self.gpu_seekbar_label.setText("現在")

    def _update_gpu_seekbar_range(self):
        """シークバーの範囲を更新"""
        data_duration = int(self.gpu_graph.get_data_duration())
        current_time_range = self.gpu_graph.time_range
        # シークバーの最大値 = データ期間 - 現在の表示範囲（0未満にならないように）
        max_offset = max(0, data_duration - current_time_range)
        self.gpu_seekbar.setMaximum(max_offset)
        if self.gpu_seekbar.value() > max_offset:
            self.gpu_seekbar.setValue(max_offset)

    def _record_gpu_usage(self):
        """GPU使用量を記録（タイマーから呼び出し）"""
        try:
            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi is None:
                default_paths = [
                    r"C:\Windows\System32\nvidia-smi.exe",
                    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                ]
                for path in default_paths:
                    if os.path.exists(path):
                        nvidia_smi = path
                        break

            if nvidia_smi is None:
                return

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [nvidia_smi,
                 "--query-gpu=index,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
            )

            if result.returncode != 0:
                return

            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    try:
                        idx = int(parts[0])
                        used_mb = int(parts[1])
                        total_mb = int(parts[2])
                        self.gpu_graph.add_data_point(idx, used_mb, total_mb)
                    except ValueError:
                        continue

            # シークバーの範囲を更新
            self._update_gpu_seekbar_range()

        except Exception as e:
            logger.debug(f"[GPU Record] Error: {e}")

    def _record_gpu_with_event(self, event_name: str):
        """イベント付きでGPU使用量を記録"""
        self.gpu_graph.add_event(event_name)
        self._record_gpu_usage()

    def _schedule_gpu_record_after_llm(self, stage_name: str):
        """LLM起動後5秒後にGPU使用量を記録するスケジュール"""
        # 即座に記録（起動時）
        self._record_gpu_with_event(f"{stage_name}開始")

        # 5秒後に記録
        QTimer.singleShot(5000, lambda: self._record_gpu_with_event(f"{stage_name}+5s"))

    def _update_model_combos(self, response):
        """利用可能なモデルでComboBoxを更新"""
        models = []
        if hasattr(response, 'models'):
            raw_models = response.models
        elif isinstance(response, dict) and 'models' in response:
            raw_models = response['models']
        else:
            return

        for model in raw_models:
            if isinstance(model, dict):
                name = model.get('model') or model.get('name', '')
            else:
                name = getattr(model, 'model', None) or getattr(model, 'name', '')
            if name:
                models.append(name)

        # 各コンボボックスにモデルを追加（v7.0.0: 常駐 + 5カテゴリ）
        all_combos = [
            self.image_model_combo, self.embedding_model_combo,
            self.coding_model_combo, self.research_model_combo,
            self.reasoning_model_combo, self.translation_model_combo,
            self.vision_model_combo,
        ]
        for combo in all_combos:
            current = combo.currentText()
            for model in models:
                if combo.findText(model) == -1:
                    combo.addItem(model)
            combo.setCurrentText(current)

    def _open_vram_simulator(self):
        """VRAM Budget Simulatorダイアログを開く"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("VRAM Budget Simulator")
        dialog.setMinimumSize(900, 600)

        layout = QVBoxLayout(dialog)
        simulator = VRAMBudgetSimulator()

        # オーバーフロー警告
        simulator.overflowDetected.connect(
            lambda gpu_idx, overflow: QMessageBox.warning(
                dialog, "VRAM警告",
                f"GPU {gpu_idx} で VRAM が {overflow:.1f} GB オーバーしています。"
            ) if overflow > 0 else None
        )

        layout.addWidget(simulator)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)
        dialog.exec()

    def _refresh_gpu_info(self):
        """GPU情報を安全に更新（PyInstaller環境対応）"""
        try:
            import subprocess
            import shutil
            import os

            # nvidia-smi のフルパスを探索
            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi is None:
                # Windows のデフォルトパスを直接指定
                default_paths = [
                    r"C:\Windows\System32\nvidia-smi.exe",
                    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                ]
                for path in default_paths:
                    if os.path.exists(path):
                        nvidia_smi = path
                        break

            if nvidia_smi is None:
                self.gpu_info_label.setText("nvidia-smiが見つかりません\n(NVIDIAドライバが必要です)")
                self.gpu_info_label.setStyleSheet("color: #9ca3af;")
                return

            # CREATE_NO_WINDOW フラグでコンソール非表示（Windows）
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [nvidia_smi,
                 "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=creationflags,
            )

            if result.returncode != 0:
                self.gpu_info_label.setText(f"nvidia-smiエラー: {result.stderr.strip()[:50]}")
                self.gpu_info_label.setStyleSheet("color: #f59e0b;")
                return

            lines = result.stdout.strip().split('\n')
            info_text = ""
            total_vram_used = 0
            total_vram_total = 0

            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    idx, name, used, total, util = parts[:5]
                    try:
                        used_mb = int(used)
                        total_mb = int(total)
                        util_pct = int(util)
                        usage_pct = (used_mb / total_mb) * 100 if total_mb > 0 else 0

                        total_vram_used += used_mb
                        total_vram_total += total_mb

                        # プログレスバー風表示
                        bar_len = 20
                        filled = int(usage_pct / 100 * bar_len)
                        bar = "█" * filled + "░" * (bar_len - filled)

                        info_text += f"GPU {idx}: {name}\n"
                        info_text += f"  VRAM: [{bar}] {used_mb:,}/{total_mb:,} MB ({usage_pct:.1f}%)\n"
                        info_text += f"  GPU使用率: {util_pct}%\n"
                    except ValueError:
                        continue

            if total_vram_total > 0:
                info_text += f"\n合計VRAM: {total_vram_used:,}/{total_vram_total:,} MB"

            self.gpu_info_label.setText(info_text.strip() or "GPU情報を取得できませんでした")
            self.gpu_info_label.setStyleSheet("color: #22c55e;")

        except subprocess.TimeoutExpired:
            self.gpu_info_label.setText("nvidia-smi タイムアウト (10秒)")
            self.gpu_info_label.setStyleSheet("color: #f59e0b;")
        except FileNotFoundError:
            self.gpu_info_label.setText("nvidia-smiが見つかりません\n(NVIDIAドライバが必要です)")
            self.gpu_info_label.setStyleSheet("color: #9ca3af;")
        except Exception as e:
            self.gpu_info_label.setText(f"GPU情報取得エラー: {str(e)[:40]}")
            self.gpu_info_label.setStyleSheet("color: #ef4444;")
