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

from ..utils.subprocess_utils import run_hidden
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QTextEdit, QPlainTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QCheckBox, QSpinBox, QFrame,
    QScrollArea, QFormLayout, QLineEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QSizePolicy,
    QFileDialog  # v5.1: ファイル添付用
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QKeyEvent

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
    COLORS, SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN, DANGER_BTN,
    OUTPUT_AREA_STYLE, INPUT_AREA_STYLE, TAB_BAR_STYLE,
    SCROLLBAR_STYLE, COMBO_BOX_STYLE, PROGRESS_BAR_STYLE,
    SPINBOX_STYLE,
    USER_MESSAGE_STYLE, AI_MESSAGE_STYLE,
)
from ..utils.style_helpers import SS
# VRAM Simulator
# v11.0.0: VRAMCompactWidget removed from settings UI
# v8.0.0: BIBLE notification (panel removed in v11.0.0)
from ..widgets.bible_notification import BibleNotificationWidget
from ..widgets.chat_widgets import ExecutionIndicator, InterruptionBanner
from ..bible.bible_discovery import BibleDiscovery
from ..bible.bible_injector import BibleInjector
from ..utils.i18n import t
from ..utils.error_translator import translate_error
from ..widgets.section_save_button import create_section_save_button
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox

logger = logging.getLogger(__name__)


class ManageModelsDialog(QMessageBox):
    """v10.0.0: カスタムモデル表示管理ダイアログ

    Ollama検出済み/カスタムサーバー検出済み/手動登録モデルの
    表示・非表示を切り替えるダイアログ。
    設定は config/custom_models.json に保存される。
    """

    def __init__(self, phase_key: str, parent=None):
        super().__init__(parent)
        self.phase_key = phase_key
        self.setWindowTitle(t('desktop.mixAI.manageModelsTitle'))
        self.setStyleSheet(f"background-color: {COLORS['bg_elevated']}; color: {COLORS['text_primary']};")
        self._models = self._load_custom_models()
        self._build_ui()

    def _load_custom_models(self) -> dict:
        """custom_models.jsonからモデル設定を読み込み"""
        config_path = os.path.join("config", "custom_models.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"custom_models.json load failed: {e}")
        return {"models": [], "phase_visibility": {}}

    def _save_custom_models(self):
        """custom_models.jsonにモデル設定を保存"""
        config_path = os.path.join("config", "custom_models.json")
        try:
            os.makedirs("config", exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._models, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"custom_models.json save failed: {e}")

    def _build_ui(self):
        """ダイアログUIを構築"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel
        # ManageModelsDialogを実質QDialogとして動作させる
        self.dlg = QDialog(self.parent())
        self.dlg.setWindowTitle(t('desktop.mixAI.manageModelsTitle'))
        self.dlg.setMinimumWidth(400)
        self.dlg.setStyleSheet(f"background-color: {COLORS['bg_elevated']}; color: {COLORS['text_primary']};")
        layout = QVBoxLayout(self.dlg)

        desc = QLabel(t('desktop.mixAI.manageModelsDesc'))
        desc.setWordWrap(True)
        desc.setStyleSheet(SS.muted("11px"))
        layout.addWidget(desc)

        # モデルリスト
        self.model_list = QListWidget()
        self.model_list.setStyleSheet(f"""
            QListWidget {{ background-color: {COLORS['bg_card']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border_strong']}; }}
            QListWidget::item {{ padding: 4px; }}
        """)
        phase_vis = self._models.get("phase_visibility", {}).get(self.phase_key, {})

        # Ollama検出モデル
        try:
            import ollama
            tags = ollama.list()
            ollama_models = [m.get("name", m.get("model", "")) for m in tags.get("models", [])]
            for name in ollama_models:
                item = QListWidgetItem(f"[Ollama] {name}")
                item.setCheckState(Qt.CheckState.Checked if phase_vis.get(name, True) else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.model_list.addItem(item)
        except Exception:
            pass

        # v11.0.0: カスタムサーバー検出を削除 (openai_compat_backend.py 削除済み)

        # 手動登録モデル
        for m in self._models.get("models", []):
            name = m.get("name", "")
            if name:
                item = QListWidgetItem(f"[Manual] {name}")
                item.setCheckState(Qt.CheckState.Checked if phase_vis.get(name, True) else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.model_list.addItem(item)

        layout.addWidget(self.model_list)

        # 手動追加行
        add_row = QHBoxLayout()
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText(t('desktop.mixAI.manageModelsAddPlaceholder'))
        self.add_edit.setStyleSheet(f"background-color: {COLORS['bg_card']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border_strong']}; padding: 4px;")
        add_row.addWidget(self.add_edit)
        add_btn = QPushButton(t('desktop.mixAI.manageModelsAddBtn'))
        add_btn.setStyleSheet(f"background-color: {COLORS['success_bg']}; color: white; padding: 4px 12px; border-radius: 4px;")
        add_btn.clicked.connect(self._add_manual_model)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # OK/Cancel
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(f"background-color: {COLORS['border_strong']}; color: white; padding: 6px 16px; border-radius: 4px;")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton(t('common.cancel'))
        cancel_btn.setStyleSheet(f"background-color: {COLORS['border_strong']}; color: white; padding: 6px 16px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _add_manual_model(self):
        """手動モデル追加"""
        name = self.add_edit.text().strip()
        if not name:
            return
        # 重複チェック
        for i in range(self.model_list.count()):
            if self.model_list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                return
        item = QListWidgetItem(f"[Manual] {name}")
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.model_list.addItem(item)
        # modelsリストに追加
        if "models" not in self._models:
            self._models["models"] = []
        self._models["models"].append({"name": name, "enabled": True})
        self.add_edit.clear()

    def _on_ok(self):
        """OK押下時: 表示設定を保存"""
        phase_vis = {}
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            phase_vis[name] = (item.checkState() == Qt.CheckState.Checked)
        if "phase_visibility" not in self._models:
            self._models["phase_visibility"] = {}
        self._models["phase_visibility"][self.phase_key] = phase_vis
        self._save_custom_models()
        self.dlg.accept()

    def exec(self):
        """ダイアログ表示"""
        return self.dlg.exec()






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
        self.setStyleSheet(f"""
            MixAIAttachmentWidget {{
                background-color: {COLORS['bg_elevated']};
                border: 1px solid {COLORS['border_strong']};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            MixAIAttachmentWidget:hover {{
                border-color: {COLORS['accent_bright']};
            }}
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
        name_label.setStyleSheet(SS.primary("10px"))
        name_label.setMaximumWidth(150)
        name_label.setToolTip(filepath)

        # ×ボタン (v5.2.0: 視認性大幅向上 - 常に赤背景で目立たせる)
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setToolTip(t('desktop.mixAI.removeAttachTip'))
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['error']};
                color: #ffffff;
                border: 2px solid {COLORS['error']};
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['error_bg']};
                color: #ffffff;
                border-color: {COLORS['error']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['error_bg']};
            }}
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
                self.error.emit(t('desktop.mixAI.ollamaConnFailedFull'))
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
                    "error": t('common.errors.claude.notFound'),
                }

            # プロンプトをファイル経由で渡す（長いプロンプト対応）
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(prompt)
                prompt_file = f.name

            try:
                # v5.0.0: Claude CLI実行（--dangerously-skip-permissions で自動許可）
                result = run_hidden(
                    [claude_cmd, "-p", "--dangerously-skip-permissions", prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
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
                    raw_error = result.stderr.strip() or f"Exit code: {result.returncode}"
                    return {
                        "success": False,
                        "output": result.stdout.strip(),
                        "error": translate_error(raw_error, source="claude"),
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
                "error": t('common.errors.claude.timeout', seconds=timeout_seconds),
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": translate_error(str(e), source="claude"),
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


class _ContinueTextEdit(QPlainTextEdit):
    """会話継続パネル用テキスト入力 (v11.9.2: enter_to_send設定対応)"""
    def __init__(self, send_callback, parent=None):
        super().__init__(parent)
        self._send_cb = send_callback

    def keyPressEvent(self, e):
        from PyQt6.QtCore import Qt as _Qt
        if e.key() in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter):
            has_shift = bool(e.modifiers() & _Qt.KeyboardModifier.ShiftModifier)
            from ..widgets.chat_input import _is_enter_to_send
            if _is_enter_to_send():
                if not has_shift:
                    self._send_cb()
                    return
            else:
                if has_shift:
                    self._send_cb()
                    return
            super().keyPressEvent(e)
            return
        super().keyPressEvent(e)


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

        # v9.7.0: ChatStore integration
        self._active_chat_id = None
        self._chat_store = None
        try:
            from ..web.chat_store import ChatStore
            self._chat_store = ChatStore()
        except Exception as e:
            logger.warning(f"ChatStore init failed for mixAI: {e}")

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
        self._populate_phase2_combos()  # v10.1.0: custom_models.json → コンボ動的反映

        # v9.5.0: Web実行ロックオーバーレイ
        from ..widgets.web_lock_overlay import WebLockOverlay
        self.web_lock_overlay = WebLockOverlay(self)

    def _restore_ui_from_config(self):
        """v8.4.2/v9.9.1: 保存済み設定値をUIウィジェットに反映"""
        # Restore from orchestrator config object
        if hasattr(self, 'max_retries_spin') and hasattr(self.config, 'max_phase2_retries'):
            self.max_retries_spin.setValue(self.config.max_phase2_retries)

        # v9.9.1: Restore additional fields from config.json
        try:
            config_path = Path("config/config.json")
            if not config_path.exists():
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # p1p3_timeout_spin
            if hasattr(self, 'p1p3_timeout_spin'):
                timeout_val = config_data.get("p1p3_timeout_minutes", 30)
                self.p1p3_timeout_spin.setValue(int(timeout_val))

            # v11.0.0: effort_combo loading removed (read from config in backend)

            # v11.0.0: search_mode loading removed (read from config in backend)

            # phase35_model_combo (v10.0.0)
            if hasattr(self, 'phase35_model_combo'):
                phase35_val = config_data.get("phase35_model", "")
                if phase35_val:
                    for i in range(self.phase35_model_combo.count()):
                        if self.phase35_model_combo.itemText(i) == phase35_val:
                            self.phase35_model_combo.setCurrentIndex(i)
                            break

            # phase4_model_combo
            if hasattr(self, 'phase4_model_combo'):
                phase4_val = config_data.get("phase4_model", "")
                if phase4_val:
                    for i in range(self.phase4_model_combo.count()):
                        if self.phase4_model_combo.itemText(i) == phase4_val:
                            self.phase4_model_combo.setCurrentIndex(i)
                            break

            # model_assignments combos
            model_assignments = config_data.get("model_assignments", {})
            if isinstance(model_assignments, dict):
                combo_map = {
                    "coding": "coding_model_combo",
                    "research": "research_model_combo",
                    "reasoning": "reasoning_model_combo",
                    "translation": "translation_model_combo",
                    "vision": "vision_model_combo",
                }
                for key, attr in combo_map.items():
                    if key in model_assignments and hasattr(self, attr):
                        combo = getattr(self, attr)
                        idx = combo.findText(model_assignments[key])
                        if idx >= 0:
                            combo.setCurrentIndex(idx)

            # max_phase2_retries
            if hasattr(self, 'max_retries_spin'):
                self.max_retries_spin.setValue(int(config_data.get("max_phase2_retries", 2)))

        except Exception as e:
            logger.warning(f"_restore_ui_from_config extended restore failed: {e}")

    def _get_claude_timeout_sec(self) -> int:
        """v8.4.3: タイムアウト値を取得（秒）

        P1/P3設定タブのp1p3_timeout_spinを優先参照し、
        なければgeneral_settings.json の timeout_minutes を読み取り秒数に変換して返す。
        設定が見つからない場合は DefaultSettings.CLAUDE_TIMEOUT_MIN (30分) をフォールバックとして使用。
        """
        from ..utils.constants import DefaultSettings
        default_min = DefaultSettings.CLAUDE_TIMEOUT_MIN  # 30分

        # 自タブのP1/P3タイムアウトSpinBoxを優先参照
        if hasattr(self, 'p1p3_timeout_spin'):
            return self.p1p3_timeout_spin.value() * 60

        # main_window経由で一般設定タブのtimeout_spinを参照（後方互換）
        if self.main_window and hasattr(self.main_window, 'settings_tab'):
            settings_tab = self.main_window.settings_tab
            if hasattr(settings_tab, 'timeout_spin'):
                return settings_tab.timeout_spin.value() * 60

        # フォールバック: general_settings.json から読み込み
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "general_settings.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get("timeout_minutes", default_min) * 60
        except Exception as e:
            logger.debug(f"general_settings.json read failed: {e}")

        return default_min * 60

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
        self.sub_tabs.addTab(chat_panel, t('desktop.mixAI.chatTab'))

        # 設定タブ
        settings_panel = self._create_settings_panel()
        self.sub_tabs.addTab(settings_panel, t('desktop.mixAI.settingsTab'))

        layout.addWidget(self.sub_tabs)

    def _on_new_session(self):
        """v9.7.0: 新規セッション開始"""
        self._active_chat_id = None
        self._conversation_history.clear()
        self._attached_files.clear()
        if hasattr(self, 'chat_display'):
            self.chat_display.clear()
        if hasattr(self, 'attachment_bar'):
            self.attachment_bar.clear_all()
        # v10.1.0: モニターリセット
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.reset()
        self.statusChanged.emit(t('desktop.mixAI.newSessionStarted'))

    def _on_continue_conversation(self):
        """v9.7.1: P1/P3実行中にClaudeに会話継続(continue)を送信"""
        self._on_continue_with_message(t('desktop.mixAI.quickContinueMsg'))

    def _on_continue_with_message(self, message: str):
        """v10.1.0: 指定メッセージで会話継続"""
        if not message.strip():
            return
        # chat_displayにユーザー発言バブルを追加
        if hasattr(self, 'chat_display'):
            self.chat_display.append(
                f"<div style='{USER_MESSAGE_STYLE}'>"
                f"<b style='color:{COLORS['accent']};'>You:</b> {message}"
                f"</div>"
            )
        if hasattr(self, 'input_text'):
            self.input_text.setPlainText(message)
            self._on_execute()

    def _on_continue_send(self):
        """v10.1.0: 会話継続パネルの送信"""
        if hasattr(self, 'mixai_continue_input'):
            message = self.mixai_continue_input.toPlainText().strip()
            if message:
                self.mixai_continue_input.clear()
                self._on_continue_with_message(message)

    # =========================================================================
    # v9.7.0: Chat History integration
    # =========================================================================

    def _toggle_history_panel(self):
        """チャット履歴パネルの表示切替"""
        if self.main_window and hasattr(self.main_window, 'toggle_chat_history'):
            self.main_window.toggle_chat_history(tab="mixAI")

    def _save_chat_to_history(self, role: str, content: str):
        """チャットメッセージを履歴に保存"""
        if not self._chat_store:
            return
        try:
            if not self._active_chat_id:
                chat = self._chat_store.create_chat(tab="mixAI")
                self._active_chat_id = chat["id"]
            self._chat_store.add_message(self._active_chat_id, role, content)
            chat = self._chat_store.get_chat(self._active_chat_id)
            if chat and chat.get("message_count", 0) == 1:
                self._chat_store.auto_generate_title(self._active_chat_id)
            if self.main_window and hasattr(self.main_window, 'chat_history_panel'):
                self.main_window.chat_history_panel.refresh_chat_list()
        except Exception as e:
            logger.debug(f"Failed to save chat to history: {e}")

    def load_chat_from_history(self, chat_id: str):
        """チャット履歴からチャットを読み込んで表示"""
        if not self._chat_store:
            return
        try:
            chat = self._chat_store.get_chat(chat_id)
            if not chat:
                return
            messages = self._chat_store.get_messages(chat_id)
            self._active_chat_id = chat_id
            if hasattr(self, 'chat_display'):
                self.chat_display.clear()
                for msg in messages:
                    if msg["role"] == "user":
                        self.chat_display.append(f'<div style="background:{COLORS["bg_elevated"]}; border-left:3px solid {COLORS["accent"]}; padding:8px; margin:4px 40px 4px 4px; border-radius:4px;"><b>You:</b> {msg["content"]}</div>')
                    elif msg["role"] == "assistant":
                        self.chat_display.append(f'<div style="background:{COLORS["bg_card"]}; border-left:3px solid {COLORS["success"]}; padding:8px; margin:4px 4px 4px 40px; border-radius:4px;"><b>AI:</b> {msg["content"]}</div>')
            self.statusChanged.emit(t('desktop.mixAI.chatLoaded', title=chat.get("title", "")))
        except Exception as e:
            logger.warning(f"Failed to load chat from history: {e}")

    def retranslateUi(self):
        """Update all translatable text on all widgets (called on language switch)."""

        # === Sub-tabs ===
        self.sub_tabs.setTabText(0, t('desktop.mixAI.chatTab'))
        self.sub_tabs.setTabText(1, t('desktop.mixAI.settingsTab'))

        # === Chat panel ===
        self.chat_title_label.setText(t('desktop.mixAI.title'))
        self.input_text.setPlaceholderText(t('desktop.mixAI.inputPlaceholder'))
        self.execute_btn.setText(t('desktop.mixAI.executeBtn'))
        self.execute_btn.setToolTip(t('desktop.mixAI.executeTip'))
        self.cancel_btn.setText(t('desktop.mixAI.cancelBtn'))

        # v11.0.0: Chat panel buttons (cloudAI統一レイアウト)
        self.mixai_attach_btn.setText(t('desktop.mixAI.attachBtn'))
        self.mixai_attach_btn.setToolTip(t('desktop.mixAI.attachTip'))
        self.mixai_snippet_btn.setText(t('desktop.mixAI.snippetBtn'))
        self.mixai_snippet_btn.setToolTip(t('desktop.mixAI.snippetTip'))
        # v12.1.0: Pilot checkbox
        if hasattr(self, '_pilot_checkbox'):
            self._pilot_checkbox.setText(t('common.pilotCheckbox'))
            self._pilot_checkbox.setToolTip(t('common.pilotCheckboxTooltip'))

        # Tool log group (state-dependent title)
        if self.tool_log_group.isChecked():
            self.tool_log_group.setTitle(t('desktop.mixAI.toolLogCollapse'))
        else:
            self.tool_log_group.setTitle(t('desktop.mixAI.toolLogExpand'))

        # Tool log tree headers
        self.tool_log_tree.setHeaderLabels(t('desktop.mixAI.toolLogHeaders'))

        # Output placeholder
        self.chat_display.setPlaceholderText(t('desktop.mixAI.outputPlaceholder'))

        # v10.1.0: 会話継続パネル
        if hasattr(self, 'mixai_continue_header'):
            self.mixai_continue_header.setText(t('desktop.mixAI.continueHeader'))
            self.mixai_continue_sub.setText(t('desktop.mixAI.continueSub'))
            self.mixai_quick_yes.setText(t('desktop.mixAI.continueYes'))
            self.mixai_quick_continue.setText(t('desktop.mixAI.continueContinue'))
            self.mixai_quick_execute.setText(t('desktop.mixAI.continueExecute'))
            self.mixai_continue_send_btn.setText(t('desktop.mixAI.continueSend'))
            self.mixai_continue_input.setPlaceholderText(t('desktop.mixAI.continuePlaceholder'))

        # v10.1.0: monitor widget retranslation
        if hasattr(self, 'monitor_widget') and hasattr(self.monitor_widget, 'retranslateUi'):
            self.monitor_widget.retranslateUi()

        # === Settings panel ===

        # P1/P3設定グループ (v10.0.0)
        self.claude_group.setTitle(t('desktop.mixAI.phase13GroupLabel'))
        self.p1p3_engine_label.setText(t('desktop.mixAI.p1p3ModelLabel'))

        # Engine combo (preserve selection, update display names)
        engine_idx = self.engine_combo.currentIndex()
        # v11.5.0: cloud_models.json から動的取得（ハードコード廃止）
        from ..utils.model_catalog import get_cloud_models
        cloud_models = get_cloud_models()
        if cloud_models:
            self._engine_options = [
                (m.get("model_id", ""), m.get("name", m.get("model_id", "")))
                for m in cloud_models
            ]
        else:
            # cloud_models.json が空の場合はフォールバック表示なし
            self._engine_options = []
        self._add_ollama_engines()
        self.engine_combo.blockSignals(True)
        self.engine_combo.clear()
        for engine_id, display_name in self._engine_options:
            self.engine_combo.addItem(display_name, engine_id)
        if 0 <= engine_idx < self.engine_combo.count():
            self.engine_combo.setCurrentIndex(engine_idx)
        self.engine_combo.blockSignals(False)
        self.engine_combo.setToolTip(t('desktop.mixAI.engineTip'))

        # v9.7.1: claude_model_combo is hidden (merged into engine_combo)

        # v11.0.0: effort retranslateUi removed

        # v11.0.0: search_mode retranslateUi removed

        self.p1p3_timeout_label.setText(t('desktop.mixAI.p1p3TimeoutLabel'))
        # v9.8.1: Refresh timeout suffix for i18n
        if hasattr(self, 'p1p3_timeout_spin'):
            self.p1p3_timeout_spin.setSuffix(t('common.timeoutSuffix'))

        # Ollama group
        self.ollama_group.setTitle(t('desktop.mixAI.ollamaGroup'))
        self.ollama_url_label.setText(t('desktop.mixAI.ollamaUrl'))
        self.ollama_test_btn.setText(t('desktop.mixAI.ollamaTest'))
        self.ollama_test_btn.setToolTip(t('desktop.mixAI.ollamaTestTip'))
        self.ollama_status_label.setText(t('desktop.mixAI.ollamaStatus'))

        # Resident models group
        self.always_load_group.setTitle(t('desktop.mixAI.residentGroup'))
        self.control_ai_label.setText(t('desktop.mixAI.controlAi'))
        self.total_vram_label.setText(t('desktop.mixAI.totalVramLabel'))

        # Phase 2 group (v10.0.0)
        self.phase_group.setTitle(t('desktop.mixAI.phase2GroupLabel'))
        self.phase_desc_label.setText(t('desktop.mixAI.phaseDesc'))
        self.category_label.setText(t('desktop.mixAI.categoryLabel'))
        self.retry_label.setText(t('desktop.mixAI.retryLabel'))
        self.max_retries_label.setText(t('desktop.mixAI.maxRetries'))
        self.max_retries_spin.setToolTip(t('desktop.mixAI.maxRetriesTip'))
        # v10.0.0: Manage models button
        if hasattr(self, 'manage_models_btn'):
            self.manage_models_btn.setText(t('desktop.mixAI.manageModelsBtn'))

        # Phase 3.5 group (v10.0.0)
        if hasattr(self, 'phase35_group'):
            self.phase35_group.setTitle(t('desktop.mixAI.phase35GroupLabel'))
            self.phase35_desc_label.setText(t('desktop.mixAI.phase35Desc'))
            self.phase35_model_label.setText(t('desktop.mixAI.phase35ModelLabel'))
            # Refresh combo items (preserve selection)
            p35_idx = self.phase35_model_combo.currentIndex()
            self.phase35_model_combo.blockSignals(True)
            self.phase35_model_combo.setItemText(0, t('desktop.mixAI.phase35None'))
            self.phase35_model_combo.blockSignals(False)
            if 0 <= p35_idx < self.phase35_model_combo.count():
                self.phase35_model_combo.setCurrentIndex(p35_idx)

        # Phase 4 group (v10.0.0)
        if hasattr(self, 'phase4_group'):
            self.phase4_group.setTitle(t('desktop.mixAI.phase4GroupLabel'))
            self.phase4_label.setText(t('desktop.mixAI.phase4Model'))
            self.phase4_model_combo.setToolTip(t('desktop.mixAI.phase4ModelTip'))
            # Refresh first item text (preserve selection)
            p4_idx = self.phase4_model_combo.currentIndex()
            self.phase4_model_combo.blockSignals(True)
            self.phase4_model_combo.setItemText(0, t('desktop.mixAI.phase4Disabled'))
            self.phase4_model_combo.blockSignals(False)
            if 0 <= p4_idx < self.phase4_model_combo.count():
                self.phase4_model_combo.setCurrentIndex(p4_idx)

        # v11.0.0: VRAM group removed

        # RAG threshold combo (hidden, preserve index)
        rag_idx = self.rag_threshold_combo.currentIndex()
        self.rag_threshold_combo.blockSignals(True)
        self.rag_threshold_combo.clear()
        self.rag_threshold_combo.addItems([
            t('desktop.mixAI.filterLowPlus'),
            t('desktop.mixAI.filterMedPlus'),
            t('desktop.mixAI.filterHighOnly'),
        ])
        if 0 <= rag_idx < self.rag_threshold_combo.count():
            self.rag_threshold_combo.setCurrentIndex(rag_idx)
        self.rag_threshold_combo.blockSignals(False)

        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        # v11.1.0: Browser Use settings
        if hasattr(self, 'mixai_browser_use_group'):
            self.mixai_browser_use_group.setTitle(t('desktop.mixAI.browserUseGroup'))
        if hasattr(self, 'mixai_browser_use_cb'):
            self.mixai_browser_use_cb.setText(t('desktop.mixAI.browserUseLabel'))
            self.mixai_browser_use_cb.setToolTip(t('desktop.mixAI.browserUseTip'))

    def _create_chat_panel(self) -> QWidget:
        """チャットパネルを作成 (v11.0.0: cloudAI風レイアウトに統一)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # ヘッダー（タイトルのみ）
        header_layout = QHBoxLayout()
        self.chat_title_label = QLabel(t('desktop.mixAI.title'))
        self.chat_title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.chat_title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # v10.1.0: ExecutionMonitorWidget - LLM実行状態モニター
        from ..widgets.execution_monitor_widget import ExecutionMonitorWidget
        self.monitor_widget = ExecutionMonitorWidget()
        layout.addWidget(self.monitor_widget)

        # v8.0.0: BIBLE検出通知バー
        self.bible_notification = BibleNotificationWidget()
        self.bible_notification.add_clicked.connect(self._on_bible_add_context)
        layout.addWidget(self.bible_notification)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # === 上部: チャット表示エリア（メイン領域） ===
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Yu Gothic UI", 10))  # v11.5.2: 統一
        self.chat_display.setPlaceholderText(t('desktop.mixAI.outputPlaceholder'))
        self.chat_display.setStyleSheet(
            f"QTextEdit {{ background-color: {COLORS['bg_base']}; border: none; "
            f"padding: 10px; color: {COLORS['text_primary']}; }}" + SCROLLBAR_STYLE
        )
        self.chat_display.textChanged.connect(self._auto_scroll_chat)
        layout.addWidget(self.chat_display, stretch=1)

        # 後方互換: output_text は chat_display のエイリアス
        self.output_text = self.chat_display

        # ツール実行ログ（折りたたみ可能）
        self.tool_log_group = QGroupBox(t('desktop.mixAI.toolLogExpand'))
        self.tool_log_group.setCheckable(True)
        self.tool_log_group.setChecked(False)
        self.tool_log_group.toggled.connect(self._on_tool_log_toggled)
        self.tool_log_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {COLORS['border_strong']};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: {COLORS['text_secondary']};
            }}
        """)

        tool_log_layout = QVBoxLayout()
        self.tool_log_tree = QTreeWidget()
        self.tool_log_tree.setHeaderLabels(t('desktop.mixAI.toolLogHeaders'))
        self.tool_log_tree.setColumnWidth(0, 200)
        self.tool_log_tree.setColumnWidth(1, 200)
        self.tool_log_tree.setColumnWidth(2, 80)
        self.tool_log_tree.setColumnWidth(3, 100)
        self.tool_log_tree.header().setStretchLastSection(True)
        self.tool_log_tree.setStyleSheet(f"""
            QTreeWidget {{ font-size: 11px; }}
            QTreeWidget::item {{ padding: 2px 4px; }}
            QHeaderView::section {{
                background-color: {COLORS['bg_elevated']}; color: {COLORS['text_secondary']};
                padding: 4px 6px; border: 1px solid {COLORS['border']}; font-size: 11px;
            }}
        """)
        self.tool_log_tree.setMinimumHeight(80)
        self.tool_log_tree.setMaximumHeight(150)
        self.tool_log_tree.setVisible(False)
        tool_log_layout.addWidget(self.tool_log_tree)
        self.tool_log_group.setLayout(tool_log_layout)
        layout.addWidget(self.tool_log_group)

        # === 下部: 入力エリア(左) + 会話継続パネル(右) ===
        bottom_frame = QFrame()
        bottom_frame.setObjectName("inputFrame")
        bottom_frame.setStyleSheet(f"#inputFrame {{ border-top: 1px solid {COLORS['border']}; }}")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(10, 5, 10, 5)
        bottom_layout.setSpacing(10)

        # --- 左側: 入力欄 + ボタン行 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        # 添付ファイルバー
        self.attachment_bar = MixAIAttachmentBar()
        self.attachment_bar.attachments_changed.connect(self._on_attachments_changed)
        left_layout.addWidget(self.attachment_bar)

        # メッセージ入力欄
        self.input_text = MixAIEnhancedInput()
        self.input_text.setFont(QFont("Yu Gothic UI", 11))  # v11.5.2: 統一
        self.input_text.setPlaceholderText(t('desktop.mixAI.inputPlaceholder'))
        self.input_text.setMinimumHeight(40)
        self.input_text.setMaximumHeight(150)
        self.input_text.file_dropped.connect(self.attachment_bar.add_files)
        left_layout.addWidget(self.input_text)

        # ボタン行: [添付][スニペット][BIBLE]  ... [キャンセル][実行]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        # ファイル添付ボタン
        self.mixai_attach_btn = QPushButton(t('desktop.mixAI.attachBtn'))
        self.mixai_attach_btn.setFixedHeight(32)
        self.mixai_attach_btn.setStyleSheet(SECONDARY_BTN)
        self.mixai_attach_btn.setToolTip(t('desktop.mixAI.attachTip'))
        self.mixai_attach_btn.clicked.connect(self._on_attach_file)
        btn_layout.addWidget(self.mixai_attach_btn)

        # スニペットボタン（追加機能統合済み）
        self.mixai_snippet_btn = QPushButton(t('desktop.mixAI.snippetBtn'))
        self.mixai_snippet_btn.setFixedHeight(32)
        self.mixai_snippet_btn.setStyleSheet(SECONDARY_BTN)
        self.mixai_snippet_btn.setToolTip(t('desktop.mixAI.snippetTip'))
        self.mixai_snippet_btn.clicked.connect(self._on_snippet_menu)
        btn_layout.addWidget(self.mixai_snippet_btn)

        # v12.1.0: Helix Pilot チェックボックス（送信時にPilotコンテキスト注入）
        from PyQt6.QtWidgets import QCheckBox
        self._pilot_checkbox = QCheckBox(t('common.pilotCheckbox'))
        self._pilot_checkbox.setFixedHeight(32)
        self._pilot_checkbox.setChecked(False)
        self._pilot_checkbox.setToolTip(t('common.pilotCheckboxTooltip'))
        self._pilot_checkbox.setStyleSheet(f"""
            QCheckBox {{ color: {COLORS['text_secondary']}; font-size: 11px; spacing: 4px; }}
            QCheckBox:hover {{ color: {COLORS['text_primary']}; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; }}
        """)
        btn_layout.addWidget(self._pilot_checkbox)

        btn_layout.addStretch()

        # キャンセルボタン
        self.cancel_btn = QPushButton(t('desktop.mixAI.cancelBtn'))
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setStyleSheet(DANGER_BTN)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        # 実行ボタン
        self.execute_btn = QPushButton(t('desktop.mixAI.executeBtn'))
        self.execute_btn.setFixedHeight(32)
        self.execute_btn.setStyleSheet(PRIMARY_BTN)
        self.execute_btn.setToolTip(t('desktop.mixAI.executeTip'))
        self.execute_btn.clicked.connect(self._on_execute)
        btn_layout.addWidget(self.execute_btn)

        left_layout.addLayout(btn_layout)
        bottom_layout.addWidget(left_widget, stretch=2)

        # --- 右側: 会話継続パネル ---
        continue_frame = self._create_mixai_continue_panel()
        bottom_layout.addWidget(continue_frame, stretch=1)

        layout.addWidget(bottom_frame)

        # v11.0.0: 後方互換用の非表示属性（削除されたボタンを参照するコード用）
        self.new_session_btn = QPushButton()
        self.new_session_btn.setVisible(False)
        self.history_btn = QPushButton()
        self.history_btn.setVisible(False)
        self.mixai_history_btn = QPushButton()
        self.mixai_history_btn.setVisible(False)
        self.clear_btn = QPushButton()
        self.clear_btn.setVisible(False)
        self.mixai_continue_btn = QPushButton()
        self.mixai_continue_btn.setVisible(False)
        self.mixai_snippet_add_btn = QPushButton()
        self.mixai_snippet_add_btn.setVisible(False)

        return panel

    def _create_mixai_continue_panel(self) -> QFrame:
        """v11.0.0: mixAI 会話継続パネル (cloudAIと統一スタイル)"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # ヘッダ
        self.mixai_continue_header = QLabel(t('desktop.mixAI.continueHeader'))
        self.mixai_continue_header.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 11px; border: none;")
        layout.addWidget(self.mixai_continue_header)

        self.mixai_continue_sub = QLabel(t('desktop.mixAI.continueSub'))
        self.mixai_continue_sub.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; border: none;")
        self.mixai_continue_sub.setWordWrap(True)
        layout.addWidget(self.mixai_continue_sub)

        # テキスト入力
        self.mixai_continue_input = _ContinueTextEdit(self._on_continue_send)
        self.mixai_continue_input.setPlaceholderText(t('desktop.mixAI.continuePlaceholder'))
        self.mixai_continue_input.setMinimumHeight(60)
        self.mixai_continue_input.setMaximumHeight(90)
        self.mixai_continue_input.setStyleSheet(f"""
            QPlainTextEdit {{ background: {COLORS['bg_elevated']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border']};
                        border-radius: 4px; padding: 4px 8px; font-size: 11px; }}
            QPlainTextEdit:focus {{ border-color: {COLORS['accent_dim']}; }}
        """)
        layout.addWidget(self.mixai_continue_input)

        # クイックボタン行 (cloudAIと同一スタイル)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)

        self.mixai_quick_yes = QPushButton(t('desktop.mixAI.continueYes'))
        self.mixai_quick_yes.setFixedHeight(26)
        self.mixai_quick_yes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mixai_quick_yes.setStyleSheet(f"""
            QPushButton {{ background-color: {COLORS['success_bg']}; color: white; border: none;
                          border-radius: 4px; padding: 3px 10px; font-size: 10px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {COLORS['success_bg']}; }}
        """)
        self.mixai_quick_yes.clicked.connect(lambda: self._on_continue_with_message("Yes"))

        self.mixai_quick_continue = QPushButton(t('desktop.mixAI.continueContinue'))
        self.mixai_quick_continue.setFixedHeight(26)
        self.mixai_quick_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mixai_quick_continue.setStyleSheet(f"""
            QPushButton {{ background-color: {COLORS['accent_muted']}; color: white; border: none;
                          border-radius: 4px; padding: 3px 10px; font-size: 10px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {COLORS['accent_dim']}; }}
        """)
        self.mixai_quick_continue.clicked.connect(lambda: self._on_continue_with_message("Continue"))

        self.mixai_quick_execute = QPushButton(t('desktop.mixAI.continueExecute'))
        self.mixai_quick_execute.setFixedHeight(26)
        self.mixai_quick_execute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mixai_quick_execute.setStyleSheet(f"""
            QPushButton {{ background-color: {COLORS['info']}; color: white; border: none;
                          border-radius: 4px; padding: 3px 10px; font-size: 10px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {COLORS['info']}; }}
        """)
        self.mixai_quick_execute.clicked.connect(lambda: self._on_continue_with_message("Execute"))

        quick_row.addWidget(self.mixai_quick_yes)
        quick_row.addWidget(self.mixai_quick_continue)
        quick_row.addWidget(self.mixai_quick_execute)
        layout.addLayout(quick_row)

        # 送信ボタン (cloudAIと同一スタイル)
        self.mixai_continue_send_btn = QPushButton(t('desktop.mixAI.continueSend'))
        self.mixai_continue_send_btn.setFixedHeight(32)
        self.mixai_continue_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mixai_continue_send_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {COLORS['accent_dim']}; color: white; border: none;
                          border-radius: 4px; padding: 4px; font-size: 11px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {COLORS['accent']}; }}
        """)
        self.mixai_continue_send_btn.clicked.connect(self._on_continue_send)
        layout.addWidget(self.mixai_continue_send_btn)

        return frame

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

        # === P1/P3設定 (v10.0.0: Phase番号ベースのタイトルに変更) ===
        self.claude_group = QGroupBox(t('desktop.mixAI.phase13GroupLabel'))
        claude_layout = QFormLayout()

        # v11.0.0: P1/P3エンジン選択 — cloudAI登録済みモデル全表示
        from ..utils.model_catalog import get_cloud_models
        self.engine_combo = NoScrollComboBox()
        self.engine_combo.setMinimumWidth(350)
        self.engine_combo.setToolTip(t('desktop.mixAI.engineTip'))
        self._populate_engine_combo()
        saved_engine_id = self._load_engine_setting()
        restored_engine = False
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemData(i) == saved_engine_id:
                self.engine_combo.setCurrentIndex(i)
                restored_engine = True
                break
        if not restored_engine and self.engine_combo.count() > 0:
            self.engine_combo.setCurrentIndex(0)
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        self.p1p3_engine_label = QLabel(t('desktop.mixAI.p1p3ModelLabel'))
        engine_combo_row = QHBoxLayout()
        engine_combo_row.addWidget(self.engine_combo, 1)
        claude_layout.addRow(self.p1p3_engine_label, engine_combo_row)

        # v11.3.0: エンジン説明ラベル
        self.engine_desc_label = QLabel("")
        self.engine_desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; padding: 2px 0;")
        self.engine_desc_label.setWordWrap(True)
        claude_layout.addRow("", self.engine_desc_label)

        # v11.0.0: engine_type_label removed

        # v9.7.1: Claudeモデル選択は engine_combo (P1/P3モデル) に統合済み
        # 後方互換用に非表示の属性を保持
        self.claude_model_combo = NoScrollComboBox()
        self.claude_model_combo.setVisible(False)
        for i, model_def in enumerate(CLAUDE_MODELS):
            self.claude_model_combo.addItem(model_def["display_name"], userData=model_def["id"])
        self.claude_model_label = QLabel("")
        self.claude_model_label.setVisible(False)

        # v11.0.0: effort_combo and gpt_effort_combo removed from settings UI
        # Effort levels are now read directly from config.json in the backend

        # v11.0.0: search_mode_combo removed from settings UI

        # タイムアウト（分）(v9.7.0: 10分刻み、i18n suffix)
        self.p1p3_timeout_spin = NoScrollSpinBox()
        self.p1p3_timeout_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.p1p3_timeout_spin.setRange(10, 120)
        self.p1p3_timeout_spin.setValue(30)
        self.p1p3_timeout_spin.setSingleStep(10)
        self.p1p3_timeout_spin.setStyleSheet(SPINBOX_STYLE)
        self.p1p3_timeout_spin.setSuffix(t('common.timeoutSuffix'))
        self.p1p3_timeout_spin.setToolTip(t('common.timeoutTip'))
        self.p1p3_timeout_label = QLabel(t('desktop.mixAI.p1p3TimeoutLabel'))
        claude_layout.addRow(self.p1p3_timeout_label, self.p1p3_timeout_spin)
        claude_layout.addRow(create_section_save_button(self._save_all_settings_section))

        self.claude_group.setLayout(claude_layout)
        scroll_layout.addWidget(self.claude_group)

        # v11.0.0: Phase 3.5 (Review) — 説明文はツールチップ化、候補は動的
        from ..utils.model_catalog import get_phase35_candidates, get_phase4_candidates, populate_combo
        self.phase35_group = QGroupBox(t('desktop.mixAI.phase35GroupLabel'))
        self.phase35_group.setToolTip(t('desktop.mixAI.phase35Desc'))
        phase35_layout = QFormLayout()
        # v11.0.0: 説明文QLabel廃止（ツールチップに移行）
        self.phase35_desc_label = QLabel("")
        self.phase35_desc_label.setVisible(False)
        self.phase35_model_combo = NoScrollComboBox()
        populate_combo(self.phase35_model_combo,
                       get_phase35_candidates(skip_label=t('desktop.mixAI.phase35None')))
        self.phase35_model_label = QLabel(t('desktop.mixAI.phase35ModelLabel'))
        phase35_layout.addRow(self.phase35_model_label, self.phase35_model_combo)
        phase35_layout.addRow(create_section_save_button(self._save_all_settings_section))
        self.phase35_group.setLayout(phase35_layout)

        # v11.0.0: Phase 4 (Implementation) — 候補は動的
        self.phase4_group = QGroupBox(t('desktop.mixAI.phase4GroupLabel'))
        self.phase4_group.setToolTip(t('desktop.mixAI.phase4ModelTip'))
        phase4_layout = QFormLayout()
        self.phase4_model_combo = NoScrollComboBox()
        populate_combo(self.phase4_model_combo,
                       get_phase4_candidates(skip_label=t('desktop.mixAI.phase4Disabled')),
                       current_value="")
        self.phase4_label = QLabel(t('desktop.mixAI.phase4Model'))
        phase4_layout.addRow(self.phase4_label, self.phase4_model_combo)
        phase4_layout.addRow(create_section_save_button(self._save_all_settings_section))
        self.phase4_group.setLayout(phase4_layout)

        # 初期エンジン状態に合わせてClaudeモデル/思考モードを有効/無効化
        initial_engine_id = self.engine_combo.currentData() or ""
        self._update_claude_controls_availability(initial_engine_id.startswith("claude-"))
        self._update_engine_desc(initial_engine_id)
        self._update_engine_desc(initial_engine_id)

        # === Ollama接続設定 ===
        self.ollama_group = QGroupBox(t('desktop.mixAI.ollamaGroup'))
        ollama_layout = QVBoxLayout()

        url_layout = QHBoxLayout()
        self.ollama_url_label = QLabel(t('desktop.mixAI.ollamaUrl'))
        url_layout.addWidget(self.ollama_url_label)
        self.ollama_url_edit = QLineEdit(self.config.ollama_url)
        url_layout.addWidget(self.ollama_url_edit)
        self.ollama_test_btn = QPushButton(t('desktop.mixAI.ollamaTest'))
        self.ollama_test_btn.setToolTip(t('desktop.mixAI.ollamaTestTip'))
        self.ollama_test_btn.clicked.connect(self._test_ollama_connection)
        url_layout.addWidget(self.ollama_test_btn)
        ollama_layout.addLayout(url_layout)

        self.ollama_status_label = QLabel(t('desktop.mixAI.ollamaStatus'))
        self.ollama_status_label.setStyleSheet(SS.muted())
        ollama_layout.addWidget(self.ollama_status_label)

        self.ollama_group.setLayout(ollama_layout)
        scroll_layout.addWidget(self.ollama_group)
        self.ollama_group.setVisible(False)  # v9.7.0: Moved to General Settings

        # === v7.0.0: 常駐モデル（GPU割り当て） ===
        self.always_load_group = QGroupBox(t('desktop.mixAI.residentGroup'))
        always_load_layout = QVBoxLayout()

        # 制御AI (ministral-3:8b)
        image_row = QHBoxLayout()
        self.control_ai_label = QLabel(t('desktop.mixAI.controlAi'))
        image_row.addWidget(self.control_ai_label)
        self.image_model_combo = NoScrollComboBox()
        self.image_model_combo.setEditable(True)
        self.image_model_combo.addItems([
            "ministral-3:8b",
            "ministral-3:14b",
        ])
        self.image_model_combo.setCurrentText(self.config.image_analyzer_model)
        image_row.addWidget(self.image_model_combo)
        image_gpu = QLabel("→ 5070 Ti (6.0GB)")
        image_gpu.setStyleSheet(SS.ok("10px"))
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
        embedding_gpu.setStyleSheet(SS.ok("10px"))
        embedding_row.addWidget(embedding_gpu)
        self.embedding_status = QLabel("🟢")
        embedding_row.addWidget(self.embedding_status)
        embedding_row.addStretch()
        always_load_layout.addLayout(embedding_row)

        self.total_vram_label = QLabel(t('desktop.mixAI.totalVramLabel'))
        self.total_vram_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; margin-top: 5px;")
        always_load_layout.addWidget(self.total_vram_label)

        self.always_load_group.setLayout(always_load_layout)
        scroll_layout.addWidget(self.always_load_group)
        self.always_load_group.setVisible(False)  # v9.8.0: Moved to General Settings

        # === v11.0.0: Phase 2設定 — 説明文ツールチップ化、候補は動的、editable=False ===
        from ..utils.model_catalog import (
            get_phase2_candidates, get_phase2_vision_candidates,
            populate_combo as _populate,
        )
        self.phase_group = QGroupBox(t('desktop.mixAI.phase2GroupLabel'))
        phase_layout = QVBoxLayout()

        # v11.0.0: 説明文QLabel廃止（ツールチップに移行）
        self.phase_desc_label = QLabel("")
        self.phase_desc_label.setVisible(False)

        # カテゴリ別担当モデル
        self.category_label = QLabel(t('desktop.mixAI.categoryLabel'))
        self.category_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        phase_layout.addWidget(self.category_label)

        # v11.0.0: 全Phase2コンボを動的候補で生成（固定addItems全廃）
        _p2_candidates = get_phase2_candidates(
            skip_label=t('desktop.mixAI.unselected'))
        _defaults = {
            "coding": "devstral-2:123b",
            "research": "command-a:latest",
            "reasoning": "gpt-oss:120b",
            "translation": "translategemma:27b",
            "vision": "gemma3:27b",
        }
        # v11.6.0: vision カテゴリは vision capability フィルタ付き候補を使用
        _vision_candidates = get_phase2_vision_candidates(
            skip_label=t('desktop.mixAI.unselected'))
        self._phase2_combos = {}
        for cat, default in _defaults.items():
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{cat}:"))
            combo = NoScrollComboBox()
            if cat == "vision":
                _populate(combo, _vision_candidates, current_value=default)
            else:
                _populate(combo, _p2_candidates, current_value=default)
            row.addWidget(combo)
            phase_layout.addLayout(row)
            self._phase2_combos[cat] = combo
            setattr(self, f'{cat}_model_combo', combo)

        # 品質検証設定（ローカルLLM再実行）
        self.retry_label = QLabel(t('desktop.mixAI.retryLabel'))
        self.retry_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        phase_layout.addWidget(self.retry_label)

        retry_row = QHBoxLayout()
        self.max_retries_label = QLabel(t('desktop.mixAI.maxRetries'))
        retry_row.addWidget(self.max_retries_label)
        self.max_retries_spin = NoScrollSpinBox()
        self.max_retries_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.max_retries_spin.setStyleSheet(SPINBOX_STYLE)
        self.max_retries_spin.setRange(0, 5)
        self.max_retries_spin.setValue(2)
        self.max_retries_spin.setToolTip(t('desktop.mixAI.maxRetriesTip'))
        retry_row.addWidget(self.max_retries_spin)
        retry_row.addStretch()
        phase_layout.addLayout(retry_row)

        # v11.0.0: モデル管理ボタン削除 (後方互換)
        self.manage_models_btn = QPushButton()
        self.manage_models_btn.setVisible(False)
        phase_layout.addWidget(create_section_save_button(self._save_all_settings_section))

        self.phase_group.setLayout(phase_layout)
        scroll_layout.addWidget(self.phase_group)

        # v10.0.0: Phase順整列 — Phase 3.5 と Phase 4 を Phase 2 の後に配置
        scroll_layout.addWidget(self.phase35_group)
        scroll_layout.addWidget(self.phase4_group)

        # v11.0.0: モデル一覧更新ボタン（cloudAI/localAI変更を反映）
        self.refresh_phase_models_btn = QPushButton(t('desktop.mixAI.refreshPhaseModelsBtn'))
        self.refresh_phase_models_btn.setToolTip(t('desktop.mixAI.refreshPhaseModelsTip'))
        self.refresh_phase_models_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_elevated']}; color: {COLORS['accent']}; border: 1px solid {COLORS['accent']}; "
            f"border-radius: 4px; padding: 8px 16px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {COLORS['border_strong']}; }}"
        )
        self.refresh_phase_models_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_phase_models_btn.clicked.connect(self._refresh_all_phase_combos)
        scroll_layout.addWidget(self.refresh_phase_models_btn)

        # v11.0.0: BIBLE Manager UI removed (backend BibleInjector retained)
        # Auto-discover BIBLE on startup for backend injection
        self._auto_discover_bible_on_startup()

        # v8.1.0: MCP設定は一般設定タブに統合済み
        self.mcp_status_label = QLabel("")  # 互換性用ダミー

        # v11.0.0: VRAM Budget Simulator UI removed from settings

        # v8.1.0: RAG設定は一般設定タブ「記憶・知識管理」に統合済み
        # 互換性用ダミーウィジェット
        self.rag_enabled_check = QCheckBox()
        self.rag_enabled_check.setChecked(True)
        self.rag_enabled_check.setVisible(False)
        self.rag_auto_save_check = QCheckBox()
        self.rag_auto_save_check.setChecked(True)
        self.rag_auto_save_check.setVisible(False)
        self.rag_threshold_combo = NoScrollComboBox()
        self.rag_threshold_combo.addItems([t('desktop.mixAI.filterLowPlus'), t('desktop.mixAI.filterMedPlus'), t('desktop.mixAI.filterHighOnly')])
        self.rag_threshold_combo.setCurrentIndex(1)
        self.rag_threshold_combo.setVisible(False)

        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        # === v11.1.0: Browser Use Settings for mixAI search agent ===
        from ..widgets.section_save_button import create_section_save_button as _csb
        self.mixai_browser_use_group = QGroupBox(t('desktop.mixAI.browserUseGroup'))
        self.mixai_browser_use_group.setStyleSheet(SECTION_CARD_STYLE)
        browser_use_layout = QVBoxLayout()
        self.mixai_browser_use_cb = QCheckBox(t('desktop.mixAI.browserUseLabel'))
        # v11.3.0: httpxベースのため常時有効（browser_use パッケージ不要）
        self.mixai_browser_use_cb.setEnabled(True)
        self.mixai_browser_use_cb.setToolTip(t('desktop.mixAI.browserUseTip'))
        browser_use_layout.addWidget(self.mixai_browser_use_cb)
        browser_use_layout.addWidget(_csb(self._save_all_settings_section))
        self.mixai_browser_use_group.setLayout(browser_use_layout)
        scroll_layout.addWidget(self.mixai_browser_use_group)
        self._load_mixai_browser_use_setting()

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

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
            self.tool_log_group.setTitle(t('desktop.mixAI.toolLogCollapse'))
        else:
            self.tool_log_group.setTitle(t('desktop.mixAI.toolLogExpand'))

    def _on_execute(self):
        """実行開始"""
        # v8.5.0: RAG構築中ロック判定
        if hasattr(self, 'main_window') and self.main_window:
            rag_lock = getattr(self.main_window, '_rag_lock', None)
            if rag_lock and rag_lock.is_locked:
                QMessageBox.information(
                    self, t('desktop.mixAI.ragBuildingTitle'),
                    t('desktop.mixAI.ragBuildingMsg')
                )
                return

        prompt = self.input_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, t('desktop.mixAI.inputError'), t('desktop.mixAI.inputRequired'))
            return

        # UI更新
        self.execute_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.mixai_continue_btn.setEnabled(True)  # v9.7.1: 会話継続を有効化
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.tool_log_tree.clear()
        # v9.7.2: 実行中はBIBLE通知バーを非表示
        self.bible_notification.setVisible(False)

        # v10.1.0: ユーザー発言バブルを追加（chat_display）
        if hasattr(self, 'chat_display'):
            self.chat_display.append(
                f"<div style='{USER_MESSAGE_STYLE}'>"
                f"<b style='color:{COLORS['accent']};'>You:</b> {prompt}"
                f"</div>"
            )

        # v5.0.0: 会話履歴にユーザーメッセージを追加
        self._conversation_history.append({
            "role": "user",
            "content": prompt,
        })

        # 設定を更新
        self._update_config_from_ui()

        # プロンプトから画像パスを抽出 (v4.4)
        image_path = self._extract_image_path(prompt)

        # v7.0.0: 新3Phase MixAIOrchestrator を使用
        model_assignments = self._get_model_assignments()
        # v7.1.0: claude_model_id を優先使用
        claude_model_id = getattr(self.config, 'claude_model_id', None) or getattr(self.config, 'claude_model', DEFAULT_CLAUDE_MODEL_ID)
        # v9.3.0: エンジン切替
        engine_id = self.engine_combo.currentData() if hasattr(self, 'engine_combo') else claude_model_id
        orchestrator_config = {
            "claude_model": claude_model_id,
            "claude_model_id": claude_model_id,
            "orchestrator_engine": engine_id,
            "timeout": self._get_claude_timeout_sec(),
            "auto_knowledge": True,
            "project_dir": os.getcwd(),
            "max_phase2_retries": self.max_retries_spin.value() if hasattr(self, 'max_retries_spin') else 2,
            "local_agent_tools": self._load_local_agent_tools_config(),
            "phase35_model": self.phase35_model_combo.currentText() if hasattr(self, 'phase35_model_combo') else "",
            "phase4_model": self.phase4_model_combo.currentText() if hasattr(self, 'phase4_model_combo') else "",
            "search_mode": self._load_config_value("mixai_search_mode", 0),  # v11.0.0: read from config.json
            "browser_use_enabled": self._load_config_value("mixai_browser_use_enabled", False),  # v11.1.0
        }
        attached_files = []
        if image_path:
            attached_files.append(image_path)

        # v8.0.0: プロンプトからもBIBLE検索
        try:
            prompt_bibles = BibleDiscovery.discover_from_prompt(prompt)
            if prompt_bibles and not getattr(self, '_current_bible', None):
                self._current_bible = prompt_bibles[0]
                logger.info(f"[BIBLE] Discovered from prompt: {prompt_bibles[0].project_name}")
        except Exception as e:
            logger.debug(f"[BIBLE] Prompt discovery error: {e}")

        # v12.1.0: BIBLE の自動注入は廃止 → ユニペット（snippets/）に移行

        # v12.1.0: Helix Pilot — チェックボックスON時のみ注入
        if getattr(self, '_pilot_checkbox', None) and self._pilot_checkbox.isChecked():
            try:
                from ..tools.pilot_response_processor import get_system_prompt_addition
                from ..tools.helix_pilot_tool import HelixPilotTool
                pilot = HelixPilotTool.get_instance()
                if pilot.is_available:
                    config = pilot._load_config()
                    window = config.get("default_window", "")
                    screen_ctx = pilot.get_screen_context(window)
                    lang = "ja" if t('desktop.mixAI.executeBtn') != "Execute" else "en"
                    pilot_prompt = get_system_prompt_addition(screen_ctx, lang)
                    prompt = pilot_prompt + "\n\n" + prompt
            except Exception as e:
                logger.warning(f"[Pilot] Context injection failed: {e}")

        self.worker = MixAIOrchestrator(
            user_prompt=prompt,
            attached_files=attached_files,
            model_assignments=model_assignments,
            config=orchestrator_config,
        )

        # v8.0.0: BIBLE コンテキスト注入 (v11.0.0: use _current_bible instead of panel)
        if getattr(self, '_current_bible', None):
            self.worker.set_bible_context(self._current_bible)

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
        # v10.1.0: ExecutionMonitorWidget接続
        if hasattr(self.worker, 'monitor_event'):
            self.worker.monitor_event.connect(self._on_monitor_event)
        # v10.1.0: モニターリセット
        if hasattr(self, 'monitor_widget'):
            self.monitor_widget.reset()
        self.worker.start()

        # v7.1.0: 選択モデル名をステータスに表示
        model_display = self.claude_model_combo.currentText() if hasattr(self, 'claude_model_combo') else claude_model_id
        self.statusChanged.emit(t('desktop.mixAI.processing3Phase', model=model_display))

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

    # ═══ v9.3.0: P1/P3エンジン切替 ═══

    def _populate_engine_combo(self):
        """v11.2.2: cloudAI登録済みモデル + localAIインストール済みモデルをengine_comboに動的設定"""
        from ..utils.model_catalog import get_cloud_models, get_ollama_installed_models
        self.engine_combo.blockSignals(True)
        saved = self.engine_combo.currentData()
        self.engine_combo.clear()

        # ── Cloud AI ──
        for m in get_cloud_models():
            self.engine_combo.addItem(m.get("name", ""), m.get("model_id", ""))

        # ── Local LLM ──
        ollama_models = get_ollama_installed_models()
        if ollama_models:
            sep_idx = self.engine_combo.count()
            self.engine_combo.addItem("── Local LLM ──", "")
            # セパレーターを選択不可にする
            sep_item = self.engine_combo.model().item(sep_idx)
            if sep_item:
                sep_item.setEnabled(False)
            for model_name in ollama_models:
                self.engine_combo.addItem(model_name, model_name)

        # 保存値を復元
        if saved:
            for i in range(self.engine_combo.count()):
                if self.engine_combo.itemData(i) == saved:
                    self.engine_combo.setCurrentIndex(i)
                    break
        self.engine_combo.blockSignals(False)

    def _refresh_all_phase_combos(self):
        """v11.6.0: cloudAI/localAI変更時に全Phaseコンボを再読み込み"""
        from ..utils.model_catalog import (
            get_phase2_candidates, get_phase2_vision_candidates,
            get_phase35_candidates, get_phase4_candidates, populate_combo
        )
        # Phase 1/3
        self._populate_engine_combo()
        # Phase 2
        p2_items = get_phase2_candidates(skip_label=t('desktop.mixAI.unselected'))
        vision_items = get_phase2_vision_candidates(skip_label=t('desktop.mixAI.unselected'))
        for cat, combo in self._phase2_combos.items():
            current = combo.currentText()
            if cat == "vision":
                populate_combo(combo, vision_items, current_value=current)
            else:
                populate_combo(combo, p2_items, current_value=current)
        # Phase 3.5
        p35_items = get_phase35_candidates(skip_label=t('desktop.mixAI.phase35None'))
        current_35 = self.phase35_model_combo.currentText()
        populate_combo(self.phase35_model_combo, p35_items, current_value=current_35)
        # Phase 4
        p4_items = get_phase4_candidates(skip_label=t('desktop.mixAI.phase4Disabled'))
        current_4 = self.phase4_model_combo.currentText()
        populate_combo(self.phase4_model_combo, p4_items, current_value=current_4)
        self.statusChanged.emit("Model lists refreshed")

    def _add_ollama_engines(self):
        """v11.2.2: _populate_engine_combo() に統合（後方互換エイリアス）"""
        self._populate_engine_combo()

    def _on_engine_changed(self, index):
        """エンジン変更時の処理"""
        engine_id = self.engine_combo.currentData()
        # セパレーター（data=""）が選択された場合はスキップ
        if not engine_id:
            return
        self._save_engine_setting(engine_id)
        # v9.9.0: is_claude excludes gpt-5.3-codex (not a Claude engine)
        is_claude = engine_id.startswith("claude-")
        self._update_claude_controls_availability(is_claude)
        self._update_engine_desc(engine_id)

    def _update_engine_desc(self, engine_id: str):
        """エンジン説明ラベルを更新（v11.9.3: provider-based判定）"""
        if not hasattr(self, 'engine_desc_label'):
            return
        if not engine_id:
            self.engine_desc_label.setText("")
            return
        from ..utils.model_catalog import get_provider_for_engine
        provider = get_provider_for_engine(engine_id)
        if provider:
            if "cli" in provider:
                if "anthropic" in provider:
                    desc = t('desktop.mixAI.engineDescClaudeCli')
                elif "openai" in provider:
                    desc = t('desktop.mixAI.engineDescCodex')
                else:
                    desc = t('desktop.mixAI.engineDescCloud')
            else:
                if "anthropic" in provider:
                    desc = t('desktop.mixAI.engineDescClaude')
                elif "google" in provider:
                    desc = t('desktop.mixAI.engineDescGemini')
                elif "openai" in provider:
                    desc = t('desktop.mixAI.engineDescOpenAI')
                else:
                    desc = t('desktop.mixAI.engineDescCloud')
        else:
            desc = t('desktop.mixAI.engineDescLocal')
        self.engine_desc_label.setText(desc)

    def _update_claude_controls_availability(self, is_claude: bool):
        """Claudeエンジン選択時のみモデル/タイムアウトを有効化 (v11.0.0: effort/engine_type removed)"""
        self.claude_model_combo.setEnabled(is_claude)
        self.p1p3_timeout_spin.setEnabled(is_claude)

    def _load_engine_setting(self) -> str:
        """config.jsonからエンジン設定を読み込み（v11.3.0: get_default_claude_model()使用）"""
        from ..utils.constants import get_default_claude_model
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("orchestrator_engine", get_default_claude_model())
        except Exception:
            pass
        return get_default_claude_model()

    def _load_config_value(self, key: str, default=None):
        """v11.0.0: config.jsonから任意のキーを読み込むヘルパー"""
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get(key, default)
        except Exception:
            pass
        return default

    # v11.0.0: _load_gpt_effort_setting removed (UI combo no longer exists)

    def _save_engine_setting(self, engine_id: str):
        """config.jsonにエンジン設定を保存"""
        try:
            config_path = Path("config/config.json")
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            config["orchestrator_engine"] = engine_id
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Engine setting save failed: {e}")

    def _load_local_agent_tools_config(self) -> dict:
        """config.jsonからlocal_agent_tools設定を読み込み"""
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("local_agent_tools", {})
        except Exception:
            pass
        return {}

    def _on_phase_changed(self, phase_num: int, description: str):
        """v7.0.0: Phase変更シグナルハンドラ"""
        percentage = {1: 10, 2: 40, 3: 70}.get(phase_num, 50)
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {description}")

        # v10.1.0: Phase開始バブルをchat_displayに追加
        if hasattr(self, 'chat_display'):
            phase_colors = {1: COLORS["accent"], 2: COLORS["info"], 3: COLORS["success"]}
            color = phase_colors.get(phase_num, "#888")
            self.chat_display.append(
                f"<div style='background:{COLORS['bg_card']}; border-left:3px solid {color}; "
                f"padding:8px; margin:4px; border-radius:4px;'>"
                f"<b style='color:{color};'>Phase {phase_num}:</b> {description}"
                f"</div>"
            )

        # ツール実行ログにPhase開始を記録
        phase_item = QTreeWidgetItem(self.tool_log_tree)
        phase_item.setText(0, description)
        phase_item.setText(1, t('desktop.mixAI.phaseRunning'))
        phase_item.setText(2, "")

    def _on_local_llm_started(self, category: str, model: str):
        """v7.0.0: ローカルLLM実行開始"""
        self.statusChanged.emit(t('desktop.mixAI.phase2Running', category=category, model=model))

    def _on_local_llm_finished(self, category: str, success: bool, elapsed: float):
        """v7.0.0: ローカルLLM実行完了"""
        status = t('desktop.mixAI.llmDone') if success else t('desktop.mixAI.llmFailed')
        item = QTreeWidgetItem(self.tool_log_tree)
        item.setText(0, f"  Phase 2: {category}")
        item.setText(1, status)
        item.setText(2, f"{elapsed:.1f}s")

    def _on_phase2_progress(self, completed: int, total: int):
        """v7.0.0: Phase 2進捗"""
        pct = 40 + int((completed / max(total, 1)) * 30)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(t('desktop.mixAI.phase2Progress', pct=pct, completed=completed, total=total))

    def _on_cancel(self):
        """キャンセル"""
        if self.worker:
            self.worker.cancel()
            self.statusChanged.emit(t('desktop.mixAI.cancelled'))

    def _on_clear(self):
        """クリア"""
        self.chat_display.clear()
        self.tool_log_tree.clear()
        self.input_text.clear()
        # v5.1: 添付ファイルもクリア
        self.attachment_bar.clear_all()
        self._attached_files.clear()

    # =========================================================================
    # v5.1: ファイル添付・スニペット関連メソッド
    # =========================================================================

    def _on_attach_file(self):
        """ファイル添付ボタンクリック"""
        files, _ = QFileDialog.getOpenFileNames(
            self, t('desktop.mixAI.fileSelectTitle'), "",
            t('desktop.mixAI.fileFilter')
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
                self._current_bible = best
                logger.info(
                    f"[BIBLE] Startup auto-discovered: {best.project_name} "
                    f"v{best.version} at {best.file_path}"
                )
            else:
                self._current_bible = None
                logger.info("[BIBLE] Startup auto-discovery: no BIBLE found")
        except Exception as e:
            self._current_bible = None
            logger.debug(f"[BIBLE] Startup discovery error: {e}")


    def _discover_bible_from_files(self, files: List[str]):
        """添付ファイルからBIBLE自動検出"""
        try:
            for f in files:
                bibles = BibleDiscovery.discover(f)
                if bibles:
                    best = bibles[0]
                    self._current_bible = best
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
        self._current_bible = bible
        logger.info(f"[BIBLE] Context added: {bible.project_name} v{bible.version}")


    def _on_bible_action_proposed(self, action, reason):
        """Post-Phase: BIBLE自律管理アクション提案"""
        try:
            from ..bible.bible_lifecycle import BibleAction
            if action == BibleAction.NONE:
                return
            reply = QMessageBox.question(
                self, t('desktop.mixAI.bibleUpdateProposal'),
                t('desktop.mixAI.bibleUpdateConfirm', reason=reason),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                from ..bible.bible_lifecycle import BibleLifecycleManager
                bible = getattr(self, '_current_bible', None)
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
                        self._current_bible = updated
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
            QMessageBox.information(self, t('desktop.mixAI.historyNotReady'), t('desktop.mixAI.historyNotReadyMsg'))

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
        unipet_dir = app_dir / "snippets"

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
                no_snippet_action = menu.addAction(t('desktop.mixAI.noSnippets'))
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
                        action = cat_menu.addAction(snippet.get("name", t('desktop.mixAI.untitled')))
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

                # カテゴリなしスニペット
                if uncategorized:
                    if categories:
                        menu.addSeparator()
                    for snippet in uncategorized:
                        action = menu.addAction(f"📋 {snippet.get('name', t('desktop.mixAI.untitled'))}")
                        action.setData(snippet)
                        action.triggered.connect(lambda checked, s=snippet: self._insert_snippet(s))

            menu.addSeparator()
            # v11.0.0: 追加アクションをメニュー内に統合
            add_action = menu.addAction(t('desktop.mixAI.snippetAddBtn'))
            add_action.triggered.connect(self._on_snippet_add)

            open_folder_action = menu.addAction(t('desktop.mixAI.openSnippetFolder'))
            open_folder_action.triggered.connect(lambda: snippet_manager.open_unipet_folder())

            # ボタンの下に表示
            btn_pos = self.mixai_snippet_btn.mapToGlobal(QPoint(0, self.mixai_snippet_btn.height()))
            menu.exec(btn_pos)

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_menu] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.mixAI.snippetMenuError', error=e))

    def _insert_snippet(self, snippet: dict):
        """スニペットを入力欄に挿入 (v5.1.1)"""
        content = snippet.get("content", "")
        name = snippet.get("name", t('desktop.mixAI.untitled'))

        current_text = self.input_text.toPlainText()
        if current_text:
            new_text = f"{current_text}\n\n{content}"
        else:
            new_text = content

        self.input_text.setPlainText(new_text)
        self.statusChanged.emit(t('desktop.mixAI.snippetInserted', name=name))
        logger.info(f"[MixAI] Snippet inserted: {name}")

    def _on_snippet_add(self):
        """スニペット追加 (v5.1.1: soloAIと共通化)"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(t('desktop.mixAI.snippetAddTitle'))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.mixAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit()
            name_input.setPlaceholderText(t('desktop.mixAI.snippetNamePlaceholder'))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.mixAI.snippetCategoryLabel'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit()
            cat_input.setPlaceholderText(t('desktop.mixAI.snippetCategoryPlaceholder'))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.mixAI.snippetContentLabel'))
            layout.addWidget(content_label)
            content_input = QTextEdit()
            content_input.setPlaceholderText(t('desktop.mixAI.snippetContentPlaceholder'))
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
                    QMessageBox.warning(self, t('desktop.mixAI.snippetInputError'), t('desktop.mixAI.snippetInputRequired'))
                    return

                category = cat_input.text().strip()
                snippet_manager = self._get_snippet_manager()
                snippet_manager.add(name=name, content=content, category=category)

                self.statusChanged.emit(t('desktop.mixAI.snippetAdded', name=name))
                logger.info(f"[MixAI] Snippet added: {name}")

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_add] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.mixAI.snippetAddError', error=e))

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
            edit_menu = menu.addMenu(t('desktop.mixAI.snippetEditMenu'))
            for snippet in snippets:
                action = edit_menu.addAction(snippet.get("name", t('desktop.mixAI.untitled')))
                action.triggered.connect(lambda checked, s=snippet: self._edit_snippet(s))

            # 削除メニュー (v5.2.0: ユニペットも削除可能に)
            delete_menu = menu.addMenu(t('desktop.mixAI.snippetDeleteMenu'))
            for snippet in snippets:
                source = snippet.get("source", "json")
                if source == "unipet":
                    action = delete_menu.addAction(f"🗂️ {snippet.get('name', t('desktop.mixAI.untitled'))} ({t('desktop.mixAI.snippetFileDelete')})")
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))
                else:
                    action = delete_menu.addAction(snippet.get("name", t('desktop.mixAI.untitled')))
                    action.triggered.connect(lambda checked, s=snippet: self._delete_snippet(s))

            menu.addSeparator()
            reload_action = menu.addAction(t('desktop.mixAI.snippetReload'))
            reload_action.triggered.connect(lambda: (self._get_snippet_manager().reload(), self.statusChanged.emit(t('desktop.mixAI.snippetReloaded'))))

            menu.exec(self.mixai_snippet_add_btn.mapToGlobal(pos))

        except Exception as e:
            logger.error(f"[MixAI._on_snippet_context_menu] Error: {e}", exc_info=True)

    def _edit_snippet(self, snippet: dict):
        """スニペット編集ダイアログ (v5.1.1)"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QDialogButtonBox

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(t('desktop.mixAI.snippetEditTitle', name=snippet.get('name', t('desktop.mixAI.untitled'))))
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout(dialog)

            # 名前入力
            name_label = QLabel(t('desktop.mixAI.snippetNameLabel'))
            layout.addWidget(name_label)
            name_input = QLineEdit(snippet.get("name", ""))
            layout.addWidget(name_input)

            # カテゴリ入力
            cat_label = QLabel(t('desktop.mixAI.snippetCategoryLabel'))
            layout.addWidget(cat_label)
            cat_input = QLineEdit(snippet.get("category", ""))
            layout.addWidget(cat_input)

            # 内容入力
            content_label = QLabel(t('desktop.mixAI.snippetContentLabel'))
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
                self.statusChanged.emit(t('desktop.mixAI.snippetUpdated', name=name_input.text()))
                logger.info(f"[MixAI] Snippet updated: {name_input.text()}")

        except Exception as e:
            logger.error(f"[MixAI._edit_snippet] Error: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'), t('desktop.mixAI.snippetEditError', error=e))

    def _delete_snippet(self, snippet: dict):
        """スニペット削除 (v5.2.0: ユニペットファイル削除対応)"""
        name = snippet.get("name", t('desktop.mixAI.untitled'))
        is_unipet = snippet.get("source") == "unipet"

        # ユニペットの場合は警告を追加
        if is_unipet:
            file_path = snippet.get("file_path", "")
            msg = t('desktop.mixAI.snippetDeleteUnipet', name=name, path=file_path)
        else:
            msg = t('desktop.mixAI.snippetDeleteConfirm', name=name)

        reply = QMessageBox.question(
            self,
            t('desktop.mixAI.snippetDeleteTitle'),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                snippet_manager = self._get_snippet_manager()
                # ユニペットの場合はdelete_file=Trueを渡す
                if snippet_manager.delete(snippet.get("id"), delete_file=is_unipet):
                    self.statusChanged.emit(t('desktop.mixAI.snippetDeleted', name=name))
                    logger.info(f"[MixAI] Snippet deleted: {name}")
                else:
                    QMessageBox.warning(self, t('desktop.mixAI.snippetDeleteFailed'), t('desktop.mixAI.snippetDeleteFailedMsg', name=name))
            except Exception as e:
                logger.error(f"[MixAI._delete_snippet] Error: {e}", exc_info=True)
                QMessageBox.warning(self, t('common.error'), t('desktop.mixAI.snippetDeleteError', error=e))

    def _on_progress(self, message: str, percentage: int):
        """進捗更新"""
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {message}")

    def _on_tool_executed(self, result: dict):
        """ツール実行完了"""
        model_name_full = result.get("model", "")

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
            item.setForeground(2, QColor(COLORS["success"]))  # ステータス列のインデックスを更新
        else:
            item.setForeground(2, QColor(COLORS["error"]))

        # モデル名列に色を付ける（識別しやすくするため）
        item.setForeground(1, QColor(COLORS["accent_bright"]))  # 青系

        self.tool_log_tree.addTopLevelItem(item)

    def _on_finished(self, result: str):
        """完了"""
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.mixai_continue_btn.setEnabled(False)  # v9.7.1
        self.progress_bar.setVisible(False)

        # v10.1.0: 最終回答バブルをchat_displayに追加
        rendered = markdown_to_html(result)
        if hasattr(self, 'chat_display'):
            self.chat_display.append(
                f"<div style='{AI_MESSAGE_STYLE}'>"
                f"<b style='color:{COLORS['success']};'>{t('desktop.mixAI.phase3FinalBubbleTitle')}</b><br>"
                f"{rendered}"
                f"</div>"
            )
        self.statusChanged.emit(t('desktop.mixAI.completed'))
        self.worker = None

        # v5.0.0: 会話履歴にAI応答を追加
        self._conversation_history.append({
            "role": "assistant",
            "content": result,
        })

        # v11.0.0: Historyタブへの自動記録
        try:
            from ..utils.chat_logger import get_chat_logger
            chat_logger = get_chat_logger()
            engine = self.engine_combo.currentData() if hasattr(self, 'engine_combo') else "mixAI"
            chat_logger.log_message(tab="mixAI", model=str(engine), role="assistant", content=result[:2000])
        except Exception:
            pass

        # v5.0.0: 自動ナレッジ管理（バックグラウンド実行）
        self._start_knowledge_processing()

    def _auto_scroll_chat(self):
        """v10.1.0: チャット表示のオートスクロール（新メッセージ追加時に最下部へ）"""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_monitor_event(self, event_type: str, model_name: str, detail: str):
        """v10.1.0: ExecutionMonitorWidget イベントハンドラ"""
        if not hasattr(self, 'monitor_widget'):
            return
        if event_type == "start":
            self.monitor_widget.start_model(model_name, detail)
        elif event_type == "output":
            self.monitor_widget.update_output(model_name, detail)
        elif event_type == "finish":
            self.monitor_widget.finish_model(model_name, success=True)
        elif event_type == "error":
            self.monitor_widget.finish_model(model_name, success=False)
        elif event_type == "heartbeat":
            self.monitor_widget.update_output(model_name, "__heartbeat__")

    def _on_error(self, error: str):
        """エラー"""
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.mixai_continue_btn.setEnabled(False)  # v9.7.1
        self.progress_bar.setVisible(False)

        # v10.1.0: エラーバブルをchat_displayに追加
        translated = translate_error(error)
        if hasattr(self, 'chat_display'):
            self.chat_display.append(
                f"<div style='background:{COLORS['error_bg']}; border-left:3px solid {COLORS['error']}; "
                f"padding:8px; margin:4px; border-radius:4px;'>"
                f"<b style='color:{COLORS['error']};'>{t('common.error')}:</b> {translated}"
                f"</div>"
            )
        self.statusChanged.emit(t('desktop.mixAI.errorStatus', error=translated[:50]))
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
        topic = knowledge.get("topic", t('desktop.mixAI.knowledgeUnknown'))
        models_used = knowledge.get("ondemand_models_used", [])
        model_info = t('desktop.mixAI.knowledgeVerify', models=', '.join(models_used)) if models_used else ""
        self.statusChanged.emit(t('desktop.mixAI.knowledgeSaved', topic=topic, model_info=model_info))
        logger.info(f"[mixAI v5.0] ナレッジ保存完了: {topic}")
        self._knowledge_worker = None

    def _on_knowledge_error(self, error: str):
        """v5.0.0: ナレッジ保存エラー（ユーザーの操作には影響しない）"""
        logger.warning(f"[mixAI v5.0] ナレッジ保存エラー: {error}")
        self._knowledge_worker = None

    def _update_config_from_ui(self):
        """UIから設定を更新 (v9.9.1: use engine_combo instead of hidden claude_model_combo)"""
        # Claude設定 — engine_combo を使用（ユーザー向けの可視コンボ）
        selected_model_id = self.engine_combo.currentData() if hasattr(self, 'engine_combo') else None
        if selected_model_id:
            self.config.claude_model_id = selected_model_id
            self.config.claude_model = selected_model_id
        else:
            self.config.claude_model_id = DEFAULT_CLAUDE_MODEL_ID
            self.config.claude_model = DEFAULT_CLAUDE_MODEL_ID

        self.config.claude_auth_mode = "cli"

        # P1/P3タイムアウト設定
        if hasattr(self, 'p1p3_timeout_spin'):
            self.config.p1p3_timeout_minutes = self.p1p3_timeout_spin.value()

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

    def _save_all_settings_section(self):
        """v11.0.0: Save all settings (per-section wrapper)"""
        self._on_save_settings()

    def _load_mixai_browser_use_setting(self):
        """v11.1.0: Load Browser Use setting for mixAI from config.json"""
        try:
            config_data = {}
            if Path("config/config.json").exists():
                with open(Path("config/config.json"), 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            enabled = config_data.get("mixai_browser_use_enabled", False)
            if hasattr(self, 'mixai_browser_use_cb'):
                self.mixai_browser_use_cb.setChecked(enabled)
        except Exception as e:
            logger.debug(f"[MixAI] Browser Use setting load: {e}")

    def _on_save_settings(self):
        """設定保存（v9.9.2: 差分ダイアログ廃止、即時保存）"""
        # UIから新しい設定を収集
        self._update_config_from_ui()

        # config.json に保存する全設定を統合（Phase2/Phase4/エンジン含む）
        config_json_path = Path("config/config.json")

        new_model_assignments = self._get_model_assignments()

        # v11.6.0: research カテゴリにクラウドモデルが割り当てられた場合の警告
        research_model = new_model_assignments.get("research", "")
        if research_model:
            from ..utils.model_catalog import get_cloud_model_names
            cloud_names = get_cloud_model_names()
            if research_model in cloud_names:
                reply = QMessageBox.warning(
                    self,
                    t('desktop.mixAI.researchCloudWarningTitle'),
                    t('desktop.mixAI.researchCloudWarningText')
                    + "\n\n"
                    + t('desktop.mixAI.researchCloudWarningInfo'),
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return

        # v11.5.0: ハードコードフォールバック廃止
        from ..utils.constants import get_default_claude_model
        engine_id = self.engine_combo.currentData() or get_default_claude_model() or ""
        gpt_effort_val = self._load_config_value("gpt_reasoning_effort", "default")
        phase35_model = self.phase35_model_combo.currentText() if hasattr(self, 'phase35_model_combo') else ""
        phase4_model = self.phase4_model_combo.currentText() if hasattr(self, 'phase4_model_combo') else ""

        max_retries = self.config.max_phase2_retries if hasattr(self.config, 'max_phase2_retries') else 2
        p1p3_timeout = self.p1p3_timeout_spin.value() if hasattr(self, 'p1p3_timeout_spin') else 30

        # orchestrator独自config保存
        self._save_config()

        # config.jsonに全設定を保存
        try:
            config_data = {}
            if config_json_path.exists():
                with open(config_json_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            config_data["model_assignments"] = new_model_assignments
            config_data["orchestrator_engine"] = engine_id
            config_data["phase35_model"] = phase35_model
            config_data["phase4_model"] = phase4_model
            config_data["mixai_search_mode"] = config_data.get("mixai_search_mode", 0)  # v11.0.0: preserved from existing config
            config_data["mixai_browser_use_enabled"] = self.mixai_browser_use_cb.isChecked() if hasattr(self, 'mixai_browser_use_cb') else False
            config_data["gpt_reasoning_effort"] = gpt_effort_val
            config_data["max_phase2_retries"] = max_retries
            config_data["p1p3_timeout_minutes"] = p1p3_timeout
            with open(config_json_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"config.json save failed: {e}")

        self.statusChanged.emit(t('desktop.mixAI.savedStatus'))

    def _open_manage_models(self, phase_key: str):
        """v10.0.0: モデル管理ダイアログを開く"""
        dlg = ManageModelsDialog(phase_key, parent=self)
        dlg.exec()
        # v10.1.0: ダイアログ閉じた後にコンボを動的更新
        self._populate_phase2_combos()

    def _populate_phase2_combos(self):
        """v10.1.0: custom_models.json の phase_visibility に基づき Phase 2 コンボを動的更新"""
        config_path = os.path.join("config", "custom_models.json")
        try:
            if not os.path.exists(config_path):
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"_populate_phase2_combos: load failed: {e}")
            return

        phase_vis = data.get("phase_visibility", {}).get("phase2", {})
        if not phase_vis:
            return

        # チェック ON のモデル名一覧
        visible_models = [name for name, checked in phase_vis.items() if checked]
        if not visible_models:
            return

        combo_map = {
            "coding": self.coding_model_combo if hasattr(self, 'coding_model_combo') else None,
            "research": self.research_model_combo if hasattr(self, 'research_model_combo') else None,
            "reasoning": self.reasoning_model_combo if hasattr(self, 'reasoning_model_combo') else None,
            "translation": self.translation_model_combo if hasattr(self, 'translation_model_combo') else None,
            "vision": self.vision_model_combo if hasattr(self, 'vision_model_combo') else None,
        }

        for _cat, combo in combo_map.items():
            if combo is None:
                continue
            # 既存アイテムのテキスト一覧
            existing = {combo.itemText(i) for i in range(combo.count())}
            for model_name in visible_models:
                if model_name not in existing:
                    combo.addItem(model_name)

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
                    status = t('desktop.mixAI.ollamaLoaded')
                    vram_text = f"{vram_mb:,}MB" if vram_mb else "-"
                elif is_installed:
                    icon = "🟡"
                    status = t('desktop.mixAI.ollamaStandby')
                    vram_text = "-"
                else:
                    icon = "🔴"
                    status = t('desktop.mixAI.ollamaNotDL')
                    vram_text = "-"

                type_label = t('desktop.mixAI.ollamaResident') if model_type == "resident" else t('desktop.mixAI.ollamaOD')
                status_lines.append(f"{icon} {name:<26} {status:<8} {vram_text:<10} [{type_label}]")

            # 結果を表示
            header = t('desktop.mixAI.ollamaConnected', latency=f"{latency:.2f}")
            self.ollama_status_label.setText(header + "\n".join(status_lines))
            self.ollama_status_label.setStyleSheet(SS.ok())

            # モデルリストを更新
            self._update_model_combos(response)

        except ImportError:
            self.ollama_status_label.setText(t('desktop.mixAI.ollamaNoLibrary'))
            self.ollama_status_label.setStyleSheet(SS.err())
        except Exception as e:
            self.ollama_status_label.setText(t('desktop.mixAI.ollamaConnFailed', error=str(e)[:50]))
            self.ollama_status_label.setStyleSheet(SS.err())

    def _check_claude_cli_mcp(self):
        """v7.0.0: Claude Code CLIのMCPサーバー設定を確認"""
        try:
            # Claude CLIの存在確認
            from ..backends.claude_cli_backend import find_claude_command
            claude_cmd = find_claude_command()

            if not claude_cmd:
                self.mcp_status_label.setText(f"  {t('desktop.mixAI.mcpClaudeNotFound')}")
                self.mcp_status_label.setStyleSheet(SS.err("10px"))
                return

            # claude mcp list でMCPサーバー一覧を取得
            result = run_hidden(
                [claude_cmd, "mcp", "list"],
                capture_output=True, text=True, timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                status_text = f"  {t('desktop.mixAI.mcpStatus', cmd=claude_cmd, count=len(lines))}"
                for line in lines:
                    status_text += f"    {line}\n"
                self.mcp_status_label.setText(status_text.rstrip())
                self.mcp_status_label.setStyleSheet(SS.ok("10px"))
            elif result.returncode == 0:
                self.mcp_status_label.setText(
                    f"  {t('desktop.mixAI.mcpNotConfigured', cmd=claude_cmd)}"
                )
                self.mcp_status_label.setStyleSheet(SS.warn("10px"))
            else:
                self.mcp_status_label.setText(
                    f"  {t('desktop.mixAI.mcpCheckFailed', cmd=claude_cmd, error=result.stderr[:100])}"
                )
                self.mcp_status_label.setStyleSheet(SS.warn("10px"))

        except subprocess.TimeoutExpired:
            self.mcp_status_label.setText(f"  {t('desktop.mixAI.mcpTimeout')}")
            self.mcp_status_label.setStyleSheet(SS.warn("10px"))
        except Exception as e:
            self.mcp_status_label.setText(f"  {t('desktop.mixAI.mcpError', error=str(e)[:80])}")
            self.mcp_status_label.setStyleSheet(SS.err("10px"))

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

