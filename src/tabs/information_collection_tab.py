"""
Helix AI Studio - Information Collection Tab (v8.5.0)
情報収集タブ: ドキュメントRAG自律構築パイプラインUI
"""

import json
import logging
import os
import platform
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QScrollArea, QFrame, QFileDialog,
    QMessageBox, QSplitter, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QTextEdit, QApplication, QTabWidget, QComboBox,
    QCheckBox, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor

from ..utils.constants import (
    INFORMATION_FOLDER, SUPPORTED_DOC_EXTENSIONS,
    DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, MAX_FILE_SIZE_MB,
    RAG_DEFAULT_TIME_LIMIT, RAG_MIN_TIME_LIMIT, RAG_MAX_TIME_LIMIT,
    RAG_TIME_STEP, RAG_CHUNK_STEP, RAG_OVERLAP_STEP,
    CLAUDE_MODELS,
)
from ..utils.styles import (
    COLORS, SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN,
    DANGER_BTN, PROGRESS_BAR_STYLE, SPINBOX_STYLE, COMBO_BOX_STYLE,
    SCROLLBAR_STYLE,
)
from ..rag.rag_builder import RAGBuilder, RAGBuildLock
from ..rag.diff_detector import DiffDetector
from ..rag.document_cleanup import DocumentCleanupManager
from ..widgets.rag_progress_widget import RAGProgressWidget
from ..utils.i18n import t
from ..memory.model_config import get_exec_llm, get_quality_llm, get_embedding_model
from ..widgets.section_save_button import create_section_save_button
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
from ..utils.style_helpers import SS

logger = logging.getLogger(__name__)


class RAGChatWorkerThread(QThread):
    """v11.0.0: RAGチャット用ワーカースレッド - RAG設定タブのCloudモデルを使用"""
    completed = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, messages: list, rag_context: str,
                 model_id: str = None, parent=None):
        super().__init__(parent)
        self._messages = messages
        self._rag_context = rag_context
        from ..utils.constants import get_default_claude_model
        self._model_id = model_id or get_default_claude_model()

    def run(self):
        try:
            from ..backends.claude_cli_backend import find_claude_command
            from ..utils.subprocess_utils import popen_hidden
            claude_cmd = find_claude_command()
            system_prompt = (
                "あなたはRAGナレッジベースのアシスタントです。"
                "ユーザーの質問に対して、提供された知識ベースの内容を基に回答してください。\n"
            )
            if self._rag_context:
                system_prompt += f"\n{self._rag_context}\n"
            history_parts = []
            for msg in self._messages:
                role = "Human" if msg["role"] == "user" else "Assistant"
                history_parts.append(f"{role}: {msg['content']}")
            full_prompt = system_prompt + "\n\n" + "\n\n".join(history_parts)
            model_flag = ["--model", self._model_id] if self._model_id else []
            proc = popen_hidden(
                [claude_cmd, '-p'] + model_flag,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            stdout, stderr = proc.communicate(input=full_prompt, timeout=180)
            if proc.returncode == 0:
                self.completed.emit(stdout.strip())
            else:
                self.errorOccurred.emit(
                    stderr.strip() or f"Claude CLIエラー (code {proc.returncode})"
                )
        except Exception as e:
            self.errorOccurred.emit(str(e))




class InformationCollectionTab(QWidget):
    """情報収集タブ"""

    statusChanged = pyqtSignal(str)

    def __init__(self, workflow_state=None, main_window=None, parent=None):
        super().__init__(parent)
        self.workflow_state = workflow_state
        self.main_window = main_window
        self.rag_lock = RAGBuildLock()
        self._builder: RAGBuilder = None
        self._current_plan: dict = None
        self._folder_path = self._resolve_folder_path()
        self.cleanup_manager = DocumentCleanupManager(
            information_folder=self._folder_path
        )
        # v11.0.0: RAGチャット
        self._rag_chat_messages: list = []
        self._rag_chat_worker: RAGChatWorkerThread = None

        self._init_ui()
        self._load_rag_settings()
        self._connect_signals()
        self._refresh_file_list()
        self._refresh_rag_stats()

    def _resolve_folder_path(self) -> str:
        """情報収集フォルダの絶対パスを解決"""
        # app_settings.jsonから読み込む
        try:
            settings_path = Path("config/app_settings.json")
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                folder = settings.get("information_collection", {}).get("folder_path", INFORMATION_FOLDER)
            else:
                folder = INFORMATION_FOLDER
        except Exception:
            folder = INFORMATION_FOLDER

        # フォルダ作成
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder

    def _init_ui(self):
        """UIを初期化（v10.1.0: 2タブ構成）"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        # QTabWidget（実行 / 設定）
        self.sub_tab_widget = QTabWidget()
        self.sub_tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_secondary']};
                padding: 8px 20px;
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['accent_cyan']};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                color: {COLORS['text_primary']};
            }}
        """)

        # ── v11.0.0: チャットサブタブ（新設：cloudAI風チャットUI） ──
        self.sub_tab_widget.addTab(
            self._create_rag_chat_sub_tab(), t('desktop.infoTab.chatSubTab')
        )

        # ── 構築サブタブ（旧:実行） ──
        self.sub_tab_widget.addTab(
            self._create_exec_sub_tab(), t('desktop.infoTab.buildSubTab')
        )

        # ── 設定サブタブ ──
        self.sub_tab_widget.addTab(
            self._create_settings_sub_tab(), t('desktop.infoTab.settingsSubTab')
        )

        main_layout.addWidget(self.sub_tab_widget)

    # =========================================================================
    # サブタブ生成
    # =========================================================================

    def _create_rag_chat_sub_tab(self) -> QWidget:
        """v11.0.0: RAGチャットサブタブ（CloudAI風チャットUI）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── ステータスバー ──
        self.rag_chat_status = QLabel(t('desktop.infoTab.ragStatusReady'))
        self.rag_chat_status.setStyleSheet(
            f"QLabel {{ background-color: {COLORS['bg_card']}; color: {COLORS['accent']}; padding: 6px 12px; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; font-weight: bold; }}"
        )
        self.rag_chat_status.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self.rag_chat_status)

        # ── チャット表示エリア ──
        self.rag_chat_display = QTextEdit()
        self.rag_chat_display.setReadOnly(True)
        self.rag_chat_display.setPlaceholderText(t('desktop.infoTab.ragChatPlaceholder'))
        self.rag_chat_display.setStyleSheet(
            f"QTextEdit {{ background-color: {COLORS['bg_dark']}; border: none; "
            f"padding: 10px; color: {COLORS['text_primary']}; }}" + SCROLLBAR_STYLE
        )
        layout.addWidget(self.rag_chat_display, stretch=1)

        # ── 進捗ウィジェット（構築中のみ表示） ──
        self.rag_progress_widget = RAGProgressWidget()
        self.rag_progress_widget.setVisible(False)
        layout.addWidget(self.rag_progress_widget)

        # ── 入力エリア（左: メイン入力 / 右: 会話継続） ──
        input_splitter = QSplitter(Qt.Orientation.Horizontal)
        input_splitter.setStyleSheet(
            f"QSplitter {{ background: {COLORS['bg_dark']}; }}"
            f"QSplitter::handle {{ background: {COLORS['border']}; width: 3px; }}"
        )
        input_splitter.setFixedHeight(140)

        # --- 左パネル: メイン入力 (cloudAIと同レイアウト: テキストエリア上・ボタン下) ---
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 4, 4, 4)
        left_layout.setSpacing(4)

        # テキスト入力エリア (上部)
        self.rag_chat_input = QTextEdit()
        self.rag_chat_input.setPlaceholderText(t('desktop.infoTab.ragChatInputPlaceholder'))
        self.rag_chat_input.setStyleSheet(
            f"QTextEdit {{ background: {COLORS['bg_base']}; color: {COLORS['text_primary']}; "
            f"border: 1px solid {COLORS['text_disabled']}; border-radius: 4px; padding: 8px; }}" + SCROLLBAR_STYLE
        )
        left_layout.addWidget(self.rag_chat_input, stretch=1)

        # ボタン行（アクション）cloudAI同様に下部配置・高さ32px
        action_row = QHBoxLayout()
        action_row.setSpacing(4)
        action_row.setContentsMargins(0, 2, 0, 0)

        self.rag_add_files_btn = QPushButton(t('desktop.infoTab.ragAddFilesBtn'))
        self.rag_add_files_btn.setStyleSheet(SECONDARY_BTN)
        self.rag_add_files_btn.setFixedHeight(32)
        self.rag_add_files_btn.setToolTip(t('desktop.infoTab.ragAddFilesTooltip'))
        self.rag_add_files_btn.clicked.connect(self._on_rag_add_files)
        action_row.addWidget(self.rag_add_files_btn)

        self.rag_plan_preview_btn = QPushButton(t('desktop.infoTab.ragPlanPreviewBtn'))
        self.rag_plan_preview_btn.setStyleSheet(SECONDARY_BTN)
        self.rag_plan_preview_btn.setFixedHeight(32)
        self.rag_plan_preview_btn.setToolTip(t('desktop.infoTab.ragBuildTooltip'))
        self.rag_plan_preview_btn.clicked.connect(self._on_rag_plan_preview_click)
        action_row.addWidget(self.rag_plan_preview_btn)

        self.rag_build_execute_btn = QPushButton(t('desktop.infoTab.ragBuildExecuteBtn'))
        self.rag_build_execute_btn.setStyleSheet(SECONDARY_BTN)
        self.rag_build_execute_btn.setFixedHeight(32)
        self.rag_build_execute_btn.setEnabled(False)
        self.rag_build_execute_btn.clicked.connect(self._on_rag_build_execute_click)
        action_row.addWidget(self.rag_build_execute_btn)

        self.rag_build_stop_btn = QPushButton(t('desktop.infoTab.ragBuildStopBtn'))
        self.rag_build_stop_btn.setStyleSheet(SECONDARY_BTN)
        self.rag_build_stop_btn.setFixedHeight(32)
        self.rag_build_stop_btn.setEnabled(False)
        self.rag_build_stop_btn.clicked.connect(self._on_rag_build_stop_click)
        action_row.addWidget(self.rag_build_stop_btn)

        self.rag_delete_btn = QPushButton(t('desktop.infoTab.ragDeleteBtn'))
        self.rag_delete_btn.setStyleSheet(SECONDARY_BTN)
        self.rag_delete_btn.setFixedHeight(32)
        self.rag_delete_btn.setToolTip(t('desktop.infoTab.ragDeleteTooltip'))
        self.rag_delete_btn.clicked.connect(self._on_rag_delete_click)
        action_row.addWidget(self.rag_delete_btn)

        action_row.addStretch()

        self.rag_chat_send_btn = QPushButton(t('desktop.infoTab.ragSendBtn'))
        self.rag_chat_send_btn.setStyleSheet(PRIMARY_BTN)
        self.rag_chat_send_btn.setFixedHeight(32)
        self.rag_chat_send_btn.clicked.connect(self._on_rag_chat_send)
        action_row.addWidget(self.rag_chat_send_btn)

        left_layout.addLayout(action_row)

        input_splitter.addWidget(left_panel)

        # --- 右パネル: 会話継続 ---
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 8, 4)
        right_layout.setSpacing(4)

        self.rag_continue_label = QLabel(t('desktop.infoTab.ragContinueLabel'))
        self.rag_continue_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;"
        )
        right_layout.addWidget(self.rag_continue_label)

        self.rag_continue_input = QTextEdit()
        self.rag_continue_input.setPlaceholderText(t('desktop.infoTab.ragContinuePlaceholder'))
        self.rag_continue_input.setStyleSheet(
            f"QTextEdit {{ background: {COLORS['bg_base']}; color: {COLORS['text_primary']}; "
            f"border: 1px solid {COLORS['text_disabled']}; border-radius: 4px; padding: 6px; font-size: 11px; }}"
            + SCROLLBAR_STYLE
        )
        right_layout.addWidget(self.rag_continue_input, stretch=1)

        # v11.8.0: cloudAI/localAI統一スタイルのコンパクトクイックボタン
        _quick_btn_style = lambda bg, bg_h: f"""
            QPushButton {{
                background-color: {bg}; color: white; border: none;
                border-radius: 4px; padding: 3px 10px;
                font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {bg_h}; }}
        """
        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)
        self.rag_quick_yes_btn = QPushButton(t('desktop.infoTab.ragQuickYes'))
        self.rag_quick_yes_btn.setStyleSheet(_quick_btn_style(COLORS['success_bg'], COLORS['success_bg']))
        self.rag_quick_yes_btn.setFixedHeight(26)
        self.rag_quick_yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rag_quick_yes_btn.clicked.connect(self._on_rag_quick_yes)
        quick_row.addWidget(self.rag_quick_yes_btn)

        self.rag_quick_continue_btn = QPushButton(t('desktop.infoTab.ragQuickContinue'))
        self.rag_quick_continue_btn.setStyleSheet(_quick_btn_style(COLORS['accent_muted'], COLORS['accent_dim']))
        self.rag_quick_continue_btn.setFixedHeight(26)
        self.rag_quick_continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rag_quick_continue_btn.clicked.connect(self._on_rag_quick_continue)
        quick_row.addWidget(self.rag_quick_continue_btn)

        self.rag_quick_exec_btn = QPushButton(t('desktop.infoTab.ragQuickExec'))
        self.rag_quick_exec_btn.setStyleSheet(_quick_btn_style(COLORS['info'], COLORS['info']))
        self.rag_quick_exec_btn.setFixedHeight(26)
        self.rag_quick_exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rag_quick_exec_btn.clicked.connect(self._on_rag_quick_exec)
        quick_row.addWidget(self.rag_quick_exec_btn)

        quick_row.addStretch()
        right_layout.addLayout(quick_row)

        self.rag_continue_send_btn = QPushButton(t('desktop.infoTab.ragContinueSend'))
        self.rag_continue_send_btn.setStyleSheet(PRIMARY_BTN)
        self.rag_continue_send_btn.setFixedHeight(32)
        self.rag_continue_send_btn.clicked.connect(self._on_rag_continue_send)
        right_layout.addWidget(self.rag_continue_send_btn)

        input_splitter.addWidget(right_panel)
        input_splitter.setSizes([600, 300])

        layout.addWidget(input_splitter)
        return tab

    def _create_exec_sub_tab(self) -> QWidget:
        """v11.0.0: 構築サブタブ（読み取り専用）: ファイル一覧 + 統計のみ"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 8, 0, 0)
        tab_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
        """)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 0, 8, 8)
        content_layout.setSpacing(10)

        # ── 表示セクションのみ追加 ──
        content_layout.addWidget(self._create_folder_section())
        content_layout.addWidget(self._create_stats_section())

        # ── 非表示でウィジェット参照を保持（後方互換） ──
        _plan_widget = self._create_plan_section()
        _plan_widget.setVisible(False)
        content_layout.addWidget(_plan_widget)

        _exec_widget = self._create_execution_section()
        _exec_widget.setVisible(False)
        content_layout.addWidget(_exec_widget)

        _data_widget = self._create_data_management_section()
        _data_widget.setVisible(False)
        content_layout.addWidget(_data_widget)

        content_layout.addStretch()
        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        return tab

    def _create_settings_sub_tab(self) -> QWidget:
        """設定サブタブ: モデル選択, 時間設定, チャンク設定, 保存"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 8, 0, 0)
        tab_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
        """)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(10)

        content_layout.addWidget(self._create_settings_section())

        content_layout.addStretch()
        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        return tab

    # =========================================================================
    # セクション生成
    # =========================================================================

    def _create_folder_section(self) -> QGroupBox:
        """v11.0.0: 情報収集フォルダセクション（読み取り専用 + カラーコーディング）"""
        self.folder_group = QGroupBox(t('desktop.infoTab.folderGroupTitle'))
        self.folder_group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(self.folder_group)

        # パス表示 + ボタン
        path_row = QHBoxLayout()
        self.folder_path_label = QLabel(t('desktop.infoTab.folderPath', path=self._folder_path))
        self.folder_path_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        path_row.addWidget(self.folder_path_label)
        path_row.addStretch()

        self.open_folder_btn = QPushButton(t('desktop.infoTab.openFolder'))
        self.open_folder_btn.setStyleSheet(SECONDARY_BTN)
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._open_folder)
        path_row.addWidget(self.open_folder_btn)
        layout.addLayout(path_row)

        # 凡例
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)
        self._legend_labels = []
        for color, key in [
            (COLORS['success'], "legendNew"),
            (COLORS['warning'], "legendModified"),
            (COLORS['text_secondary'], "legendUnchanged"),
            (COLORS['error'], "legendDeleted"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            lbl = QLabel(t(f'desktop.infoTab.{key}'))
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
            legend_row.addWidget(dot)
            legend_row.addWidget(lbl)
            self._legend_labels.append((lbl, key))
        legend_row.addStretch()
        layout.addLayout(legend_row)

        # ファイル一覧（読み取り専用）
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(t('desktop.infoTab.fileTreeHeaders'))
        self.file_tree.setColumnCount(4)
        self.file_tree.setColumnWidth(0, 300)
        self.file_tree.setColumnWidth(1, 80)
        self.file_tree.setColumnWidth(2, 130)
        self.file_tree.setColumnWidth(3, 100)
        self.file_tree.setMinimumHeight(200)
        self.file_tree.setMaximumHeight(320)
        self.file_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 12px;
            }}
            QTreeWidget::item {{ padding: 4px; }}
            QTreeWidget::item:selected {{
                background-color: {COLORS['accent_cyan']};
                color: {COLORS['bg_dark']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['accent_cyan']};
                padding: 6px;
                border: 1px solid {COLORS['border']};
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.file_tree)

        # 合計 + リフレッシュボタン
        bottom_row = QHBoxLayout()
        self.total_label = QLabel(t('desktop.infoTab.totalFilesDefault'))
        self.total_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        bottom_row.addWidget(self.total_label)
        bottom_row.addStretch()

        self.refresh_btn = QPushButton(t('desktop.infoTab.refresh'))
        self.refresh_btn.setStyleSheet(SECONDARY_BTN)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._refresh_file_list)
        bottom_row.addWidget(self.refresh_btn)

        layout.addLayout(bottom_row)
        return self.folder_group

    def _create_settings_section(self) -> QGroupBox:
        """RAG設定セクション（v11.0.0: 外枠タイトル削除）"""
        self.settings_group = QGroupBox(t('desktop.infoTab.ragSettingsGroupTitle'))
        self.settings_group.setStyleSheet(f"QGroupBox {{ border: none; margin-top: 16px; padding: 0; }} QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 2px 8px; color: {COLORS['text_secondary']}; font-size: 11px; }}")
        layout = QVBoxLayout(self.settings_group)

        # 想定実行時間
        time_row = QHBoxLayout()
        self.time_label = QLabel(t('desktop.infoTab.estimatedTime'))
        self.time_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        time_row.addWidget(self.time_label)

        self.time_spin = NoScrollSpinBox()
        self.time_spin.setRange(RAG_MIN_TIME_LIMIT, RAG_MAX_TIME_LIMIT)
        self.time_spin.setSingleStep(RAG_TIME_STEP)
        self.time_spin.setValue(RAG_DEFAULT_TIME_LIMIT)
        self.time_spin.setSuffix(t('desktop.infoTab.minuteSuffix'))
        self.time_spin.setToolTip(t('desktop.infoTab.timeLimitTip'))
        self.time_spin.setStyleSheet(SPINBOX_STYLE)
        time_row.addWidget(self.time_spin)
        time_row.addStretch()
        layout.addLayout(time_row)

        # ── 使用モデル設定 ──
        self.model_settings_group = QGroupBox(t('desktop.infoTab.modelSettingsGroup'))
        self.model_settings_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 12px;
                padding-top: 24px;
                margin-top: 8px;
                font-size: 12px;
                font-weight: bold;
                color: {COLORS['accent_cyan']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 2px 8px;
            }}
        """)
        models_layout = QVBoxLayout(self.model_settings_group)
        models_layout.setSpacing(8)

        # v11.0.0: モデル候補はModelCatalogから動的取得
        from ..utils.model_catalog import (
            get_rag_cloud_candidates, get_rag_local_candidates, populate_combo
        )
        self.model_combo_labels = []
        self.model_combos = []

        _label_style = f"color: {COLORS['text_secondary']}; font-size: 11px;"

        # Cloud モデル — cloudAI登録済みモデル全表示
        claude_row = QHBoxLayout()
        self.claude_model_label = QLabel(t('desktop.infoTab.claudeModelSelect'))
        self.claude_model_label.setStyleSheet(_label_style)
        self.claude_model_label.setFixedWidth(130)
        claude_row.addWidget(self.claude_model_label)
        self.claude_model_combo = NoScrollComboBox()
        self.claude_model_combo.setStyleSheet(COMBO_BOX_STYLE)
        populate_combo(self.claude_model_combo, get_rag_cloud_candidates())
        claude_row.addWidget(self.claude_model_combo)
        models_layout.addLayout(claude_row)
        self.model_combo_labels.append(self.claude_model_label)
        self.model_combos.append(self.claude_model_combo)

        # 実行モデル — localAIインストール済みモデル全表示
        exec_row = QHBoxLayout()
        self.exec_llm_label = QLabel(t('desktop.infoTab.execModelSelect'))
        self.exec_llm_label.setStyleSheet(_label_style)
        self.exec_llm_label.setFixedWidth(130)
        exec_row.addWidget(self.exec_llm_label)
        self.exec_llm_combo = NoScrollComboBox()
        self.exec_llm_combo.setStyleSheet(COMBO_BOX_STYLE)
        _exec_default = get_exec_llm()
        populate_combo(self.exec_llm_combo, get_rag_local_candidates(), current_value=_exec_default)
        exec_row.addWidget(self.exec_llm_combo)
        models_layout.addLayout(exec_row)
        self.model_combo_labels.append(self.exec_llm_label)
        self.model_combos.append(self.exec_llm_combo)

        # 品質チェックモデル — localAIインストール済みモデル全表示
        quality_row = QHBoxLayout()
        self.quality_llm_label = QLabel(t('desktop.infoTab.qualityModelSelect'))
        self.quality_llm_label.setStyleSheet(_label_style)
        self.quality_llm_label.setFixedWidth(130)
        quality_row.addWidget(self.quality_llm_label)
        self.quality_llm_combo = NoScrollComboBox()
        self.quality_llm_combo.setStyleSheet(COMBO_BOX_STYLE)
        _quality_default = get_quality_llm()
        populate_combo(self.quality_llm_combo, get_rag_local_candidates(), current_value=_quality_default)
        quality_row.addWidget(self.quality_llm_combo)
        models_layout.addLayout(quality_row)
        self.model_combo_labels.append(self.quality_llm_label)
        self.model_combos.append(self.quality_llm_combo)

        # Embedding モデル — localAIインストール済みモデル全表示
        embed_row = QHBoxLayout()
        self.embedding_label = QLabel(t('desktop.infoTab.embeddingSelect'))
        self.embedding_label.setStyleSheet(_label_style)
        self.embedding_label.setFixedWidth(130)
        embed_row.addWidget(self.embedding_label)
        self.embedding_combo = NoScrollComboBox()
        self.embedding_combo.setStyleSheet(COMBO_BOX_STYLE)
        _embed_default = get_embedding_model()
        populate_combo(self.embedding_combo, get_rag_local_candidates(), current_value=_embed_default)
        embed_row.addWidget(self.embedding_combo)
        models_layout.addLayout(embed_row)
        self.model_combo_labels.append(self.embedding_label)
        self.model_combos.append(self.embedding_combo)

        # 計画担当モデル — クラウド + ローカル全表示（v11.3.0）
        from ..utils.constants import get_default_claude_model
        planner_row = QHBoxLayout()
        self.planner_model_label = QLabel(t('desktop.infoTab.plannerModelSelect'))
        self.planner_model_label.setStyleSheet(_label_style)
        self.planner_model_label.setFixedWidth(130)
        planner_row.addWidget(self.planner_model_label)
        self.planner_model_combo = NoScrollComboBox()
        self.planner_model_combo.setStyleSheet(COMBO_BOX_STYLE)
        _all_candidates = get_rag_cloud_candidates() + get_rag_local_candidates()
        _planner_default = get_default_claude_model()
        populate_combo(self.planner_model_combo, _all_candidates, current_value=_planner_default)
        planner_row.addWidget(self.planner_model_combo)
        models_layout.addLayout(planner_row)
        self.model_combo_labels.append(self.planner_model_label)
        self.model_combos.append(self.planner_model_combo)

        # 計画担当モデル警告ラベル（ローカルLLM選択時）
        self.planner_model_warning = QLabel(t('desktop.infoTab.plannerModelWarning'))
        self.planner_model_warning.setStyleSheet(SS.warn("11px"))
        self.planner_model_warning.setVisible(False)
        models_layout.addWidget(self.planner_model_warning)
        self.planner_model_combo.currentTextChanged.connect(self._on_planner_model_changed)

        # モデル一覧更新ボタン
        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        self.refresh_ollama_btn = QPushButton(t('desktop.infoTab.refreshOllamaModels'))
        self.refresh_ollama_btn.setStyleSheet(SECONDARY_BTN)
        self.refresh_ollama_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_ollama_btn.clicked.connect(self._refresh_ollama_models)
        refresh_row.addWidget(self.refresh_ollama_btn)
        models_layout.addLayout(refresh_row)
        models_layout.addWidget(create_section_save_button(self._save_rag_settings))

        layout.addWidget(self.model_settings_group)

        # チャンク設定
        chunk_row = QHBoxLayout()
        self.chunk_label = QLabel(t('desktop.infoTab.chunkSizeLabel'))
        self.chunk_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        chunk_row.addWidget(self.chunk_label)

        self.chunk_size_spin = NoScrollSpinBox()
        self.chunk_size_spin.setRange(128, 2048)
        self.chunk_size_spin.setSingleStep(RAG_CHUNK_STEP)
        self.chunk_size_spin.setValue(DEFAULT_CHUNK_SIZE)
        self.chunk_size_spin.setSuffix(t('desktop.infoTab.tokenSuffix'))
        self.chunk_size_spin.setToolTip(t('desktop.infoTab.chunkSizeTip'))
        self.chunk_size_spin.setStyleSheet(SPINBOX_STYLE)
        chunk_row.addWidget(self.chunk_size_spin)

        self.overlap_label = QLabel(t('desktop.infoTab.overlapLabel'))
        self.overlap_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        chunk_row.addWidget(self.overlap_label)

        self.overlap_spin = NoScrollSpinBox()
        self.overlap_spin.setRange(0, 256)
        self.overlap_spin.setSingleStep(RAG_OVERLAP_STEP)
        self.overlap_spin.setValue(DEFAULT_CHUNK_OVERLAP)
        self.overlap_spin.setSuffix(t('desktop.infoTab.tokenSuffix'))
        self.overlap_spin.setToolTip(t('desktop.infoTab.overlapTip'))
        self.overlap_spin.setStyleSheet(SPINBOX_STYLE)
        chunk_row.addWidget(self.overlap_spin)
        chunk_row.addStretch()
        layout.addLayout(chunk_row)

        # v11.0.0: チャンクサイズ/オーバーラップの説明はツールチップに
        self.chunk_size_spin.setToolTip(t('desktop.infoTab.chunkSizeHint'))
        self.overlap_spin.setToolTip(t('desktop.infoTab.overlapHint'))

        # === v11.0.0: RAG Auto-Enhancement (Phase 6-E) ===
        auto_enhance_group = QGroupBox(t('desktop.infoTab.autoEnhance'))
        auto_enhance_group.setStyleSheet(SECTION_CARD_STYLE)
        auto_enhance_layout = QVBoxLayout()

        self.auto_kg_check = QCheckBox(t('desktop.infoTab.autoKgUpdate'))
        self.auto_kg_check.setChecked(True)
        self.auto_kg_check.setToolTip(t('desktop.infoTab.autoKgUpdateTip'))
        auto_enhance_layout.addWidget(self.auto_kg_check)

        self.hype_check = QCheckBox(t('desktop.infoTab.hypeEnabled'))
        self.hype_check.setChecked(True)
        self.hype_check.setToolTip(t('desktop.infoTab.hypeEnabledTip'))
        auto_enhance_layout.addWidget(self.hype_check)

        self.reranker_check = QCheckBox(t('desktop.infoTab.rerankerEnabled'))
        self.reranker_check.setChecked(True)
        self.reranker_check.setToolTip(t('desktop.infoTab.rerankerEnabledTip'))
        auto_enhance_layout.addWidget(self.reranker_check)

        # v11.0.0: 説明文はツールチップ化（UI直書き廃止）
        auto_enhance_group.setToolTip(t('desktop.infoTab.autoEnhanceInfo'))
        auto_enhance_layout.addWidget(create_section_save_button(self._save_rag_settings))

        auto_enhance_group.setLayout(auto_enhance_layout)
        self.auto_enhance_group = auto_enhance_group
        self.auto_enhance_info = QLabel("")  # 後方互換用
        layout.addWidget(auto_enhance_group)

        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        # v11.0.0: 記憶・知識管理セクション（一般設定から移動）
        self.rag_memory_group = QGroupBox(t('desktop.settings.memory'))
        memory_group = self.rag_memory_group
        memory_group.setStyleSheet(SECTION_CARD_STYLE)
        memory_layout = QVBoxLayout(memory_group)

        self.rag_memory_auto_save_cb = QCheckBox(t('desktop.settings.memoryAutoSave'))
        self.rag_memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        self.rag_memory_auto_save_cb.setChecked(True)
        memory_layout.addWidget(self.rag_memory_auto_save_cb)

        self.rag_knowledge_enabled_cb = QCheckBox(t('desktop.settings.knowledgeEnabled'))
        self.rag_knowledge_enabled_cb.setChecked(True)
        memory_layout.addWidget(self.rag_knowledge_enabled_cb)

        self.rag_encyclopedia_enabled_cb = QCheckBox(t('desktop.settings.encyclopediaEnabled'))
        self.rag_encyclopedia_enabled_cb.setChecked(True)
        memory_layout.addWidget(self.rag_encyclopedia_enabled_cb)

        memory_layout.addWidget(create_section_save_button(self._save_rag_settings))
        layout.addWidget(memory_group)

        return self.settings_group

    def _create_plan_section(self) -> QGroupBox:
        """現在のプランセクション"""
        self.plan_group = QGroupBox(t('desktop.infoTab.planGroupTitle'))
        self.plan_group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(self.plan_group)

        # ステータス
        status_row = QHBoxLayout()
        self.plan_status_label = QLabel(t('desktop.infoTab.planStatusDefault'))
        self.plan_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        status_row.addWidget(self.plan_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # プラン概要（QTextEdit 読み取り専用・コピー可能）
        self.plan_summary_label = QLabel(t('desktop.infoTab.planSummaryLabel'))
        self.plan_summary_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.plan_summary_label)

        summary_row = QHBoxLayout()
        self.plan_summary_text = QTextEdit()
        self.plan_summary_text.setReadOnly(True)
        self.plan_summary_text.setMaximumHeight(120)
        self.plan_summary_text.setPlaceholderText(t('desktop.infoTab.planPlaceholder'))
        self.plan_summary_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 11px;
                padding: 8px;
            }}
        """)
        summary_row.addWidget(self.plan_summary_text)

        self.copy_plan_btn = QPushButton(t('desktop.infoTab.copyPlan'))
        self.copy_plan_btn.setStyleSheet(SECONDARY_BTN)
        self.copy_plan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_plan_btn.setToolTip(t('desktop.infoTab.copyPlanTip'))
        self.copy_plan_btn.setFixedWidth(80)
        self.copy_plan_btn.clicked.connect(self._copy_plan_summary)
        self.copy_plan_btn.setEnabled(False)
        summary_row.addWidget(self.copy_plan_btn, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(summary_row)

        # プラン詳細
        self.plan_detail_label = QLabel("")
        self.plan_detail_label.setWordWrap(True)
        self.plan_detail_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")
        layout.addWidget(self.plan_detail_label)

        # プラン作成ボタン
        self.create_plan_btn = QPushButton(t('desktop.infoTab.createPlan'))
        self.create_plan_btn.setStyleSheet(PRIMARY_BTN)
        self.create_plan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_plan_btn.clicked.connect(self._create_plan)
        layout.addWidget(self.create_plan_btn)

        return self.plan_group

    def _create_execution_section(self) -> QGroupBox:
        """実行制御セクション"""
        self.execution_group = QGroupBox(t('desktop.infoTab.executionGroupTitle'))
        self.execution_group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(self.execution_group)

        # ボタン行
        btn_row = QHBoxLayout()

        self.start_btn = QPushButton(t('desktop.infoTab.startBuild'))
        self.start_btn.setStyleSheet(PRIMARY_BTN)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_build)
        self.start_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton(t('desktop.infoTab.stopBuild'))
        self.stop_btn.setStyleSheet(DANGER_BTN)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self._stop_build)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.rebuild_btn = QPushButton(t('desktop.infoTab.retryBuild'))
        self.rebuild_btn.setStyleSheet(SECONDARY_BTN)
        self.rebuild_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rebuild_btn.clicked.connect(self._rebuild)
        self.rebuild_btn.setEnabled(False)
        btn_row.addWidget(self.rebuild_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 進捗ウィジェット
        self.progress_widget = RAGProgressWidget()
        layout.addWidget(self.progress_widget)

        return self.execution_group

    def _create_stats_section(self) -> QGroupBox:
        """RAG統計セクション"""
        self.stats_group = QGroupBox(t('desktop.infoTab.statsGroupTitle'))
        self.stats_group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QHBoxLayout(self.stats_group)

        self.stats_labels = {}
        self.stats_name_labels = {}
        stats = [
            ("total_chunks", t('desktop.infoTab.totalChunks'), "0"),
            ("total_embeddings", t('desktop.infoTab.totalEmbeddings'), "0"),
            ("semantic_nodes", "Semantic Nodes", "0"),
            ("last_build", t('desktop.infoTab.lastBuild'), t('desktop.infoTab.lastBuildNone')),
            ("build_count", t('desktop.infoTab.buildCount'), t('desktop.infoTab.buildCountZero')),
        ]

        for key, label_text, default in stats:
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)
            f_layout = QVBoxLayout(frame)
            f_layout.setSpacing(2)

            val_label = QLabel(default)
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 16px; font-weight: bold;")
            f_layout.addWidget(val_label)

            name_label = QLabel(label_text)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
            f_layout.addWidget(name_label)

            self.stats_labels[key] = val_label
            self.stats_name_labels[key] = name_label
            layout.addWidget(frame)

        return self.stats_group

    def _create_data_management_section(self) -> QGroupBox:
        """データ管理セクション"""
        self.data_group = QGroupBox(t('desktop.infoTab.dataManageGroupTitle'))
        self.data_group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(self.data_group)

        # 孤児ステータス
        self.orphan_status_label = QLabel(t('desktop.infoTab.healthChecking'))
        self.orphan_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.orphan_status_label)

        # 孤児リスト
        self.orphan_tree = QTreeWidget()
        self.orphan_tree.setHeaderLabels(t('desktop.infoTab.orphanTreeHeaders'))
        self.orphan_tree.setColumnCount(3)
        self.orphan_tree.setColumnWidth(0, 280)
        self.orphan_tree.setColumnWidth(1, 80)
        self.orphan_tree.setColumnWidth(2, 200)
        self.orphan_tree.setMaximumHeight(120)
        self.orphan_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 11px;
            }}
            QTreeWidget::item {{ padding: 3px; }}
            QHeaderView::section {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['accent_cyan']};
                padding: 4px;
                border: 1px solid {COLORS['border']};
                font-size: 10px;
            }}
        """)
        self.orphan_tree.setVisible(False)
        layout.addWidget(self.orphan_tree)

        # 孤児操作ボタン
        orphan_btn_row = QHBoxLayout()
        self.scan_orphan_btn = QPushButton(t('desktop.infoTab.orphanScan'))
        self.scan_orphan_btn.setStyleSheet(SECONDARY_BTN)
        self.scan_orphan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_orphan_btn.setToolTip(t('desktop.infoTab.orphanScanTip'))
        self.scan_orphan_btn.clicked.connect(self._scan_orphans)
        orphan_btn_row.addWidget(self.scan_orphan_btn)

        self.delete_orphan_btn = QPushButton(t('desktop.infoTab.deleteOrphans'))
        self.delete_orphan_btn.setStyleSheet(DANGER_BTN)
        self.delete_orphan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_orphan_btn.setToolTip(t('desktop.infoTab.deleteOrphansTip'))
        self.delete_orphan_btn.clicked.connect(self._delete_selected_orphans)
        self.delete_orphan_btn.setEnabled(False)
        orphan_btn_row.addWidget(self.delete_orphan_btn)

        orphan_btn_row.addStretch()
        layout.addLayout(orphan_btn_row)

        # 区切り
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        # 手動削除セクション
        self.doc_delete_label = QLabel(t('desktop.infoTab.docDeleteLabel'))
        self.doc_delete_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(self.doc_delete_label)

        self.doc_tree = QTreeWidget()
        self.doc_tree.setHeaderLabels(t('desktop.infoTab.docTreeHeaders'))
        self.doc_tree.setColumnCount(2)
        self.doc_tree.setColumnWidth(0, 450)
        self.doc_tree.setColumnWidth(1, 100)
        self.doc_tree.setMinimumHeight(150)
        self.doc_tree.setMaximumHeight(300)
        self.doc_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.doc_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # マウスホイールを画面全体スクロールと分離（常にツリー内スクロールを優先）
        self.doc_tree.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.doc_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 12px;
            }}
            QTreeWidget::item {{ padding: 5px 3px; }}
            QHeaderView::section {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['accent_cyan']};
                padding: 5px;
                border: 1px solid {COLORS['border']};
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.doc_tree)

        delete_doc_btn_row = QHBoxLayout()
        delete_doc_btn_row.addStretch()
        self.delete_doc_btn = QPushButton(t('desktop.infoTab.deleteSelectedDocs'))
        self.delete_doc_btn.setStyleSheet(DANGER_BTN)
        self.delete_doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_doc_btn.setToolTip(t('desktop.infoTab.deleteSelectedDocsTip'))
        self.delete_doc_btn.clicked.connect(self._delete_selected_documents)
        delete_doc_btn_row.addWidget(self.delete_doc_btn)
        layout.addLayout(delete_doc_btn_row)

        # 初期スキャン
        QTimer.singleShot(500, self._scan_orphans)
        QTimer.singleShot(600, self._refresh_doc_list)

        return self.data_group

    # =========================================================================
    # 国際化
    # =========================================================================

    def retranslateUi(self):
        """v11.0.0: 言語切替時に全ウィジェットのテキストを更新"""

        # --- Sub-tab titles (chat=0, build=1, settings=2) ---
        self.sub_tab_widget.setTabText(0, t('desktop.infoTab.chatSubTab'))
        self.sub_tab_widget.setTabText(1, t('desktop.infoTab.buildSubTab'))
        self.sub_tab_widget.setTabText(2, t('desktop.infoTab.settingsSubTab'))

        # --- v11.0.0: チャットタブウィジェット ---
        if hasattr(self, 'rag_chat_display'):
            self.rag_chat_display.setPlaceholderText(t('desktop.infoTab.ragChatPlaceholder'))
        if hasattr(self, 'rag_chat_status'):
            self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))
        if hasattr(self, 'rag_chat_input'):
            self.rag_chat_input.setPlaceholderText(t('desktop.infoTab.ragChatInputPlaceholder'))
        if hasattr(self, 'rag_add_files_btn'):
            self.rag_add_files_btn.setText(t('desktop.infoTab.ragAddFilesBtn'))
            self.rag_add_files_btn.setToolTip(t('desktop.infoTab.ragAddFilesTooltip'))
        if hasattr(self, 'rag_plan_preview_btn'):
            self.rag_plan_preview_btn.setText(t('desktop.infoTab.ragPlanPreviewBtn'))
            self.rag_plan_preview_btn.setToolTip(t('desktop.infoTab.ragBuildTooltip'))
        if hasattr(self, 'rag_build_execute_btn'):
            self.rag_build_execute_btn.setText(t('desktop.infoTab.ragBuildExecuteBtn'))
        if hasattr(self, 'rag_build_stop_btn'):
            self.rag_build_stop_btn.setText(t('desktop.infoTab.ragBuildStopBtn'))
        if hasattr(self, 'rag_delete_btn'):
            self.rag_delete_btn.setText(t('desktop.infoTab.ragDeleteBtn'))
            self.rag_delete_btn.setToolTip(t('desktop.infoTab.ragDeleteTooltip'))
        if hasattr(self, 'rag_chat_send_btn'):
            self.rag_chat_send_btn.setText(t('desktop.infoTab.ragSendBtn'))
        # 会話継続パネル
        if hasattr(self, 'rag_continue_label'):
            self.rag_continue_label.setText(t('desktop.infoTab.ragContinueLabel'))
        if hasattr(self, 'rag_continue_input'):
            self.rag_continue_input.setPlaceholderText(t('desktop.infoTab.ragContinuePlaceholder'))
        if hasattr(self, 'rag_quick_yes_btn'):
            self.rag_quick_yes_btn.setText(t('desktop.infoTab.ragQuickYes'))
        if hasattr(self, 'rag_quick_continue_btn'):
            self.rag_quick_continue_btn.setText(t('desktop.infoTab.ragQuickContinue'))
        if hasattr(self, 'rag_quick_exec_btn'):
            self.rag_quick_exec_btn.setText(t('desktop.infoTab.ragQuickExec'))
        if hasattr(self, 'rag_continue_send_btn'):
            self.rag_continue_send_btn.setText(t('desktop.infoTab.ragContinueSend'))

        # --- QGroupBox titles ---
        self.folder_group.setTitle(t('desktop.infoTab.folderGroupTitle'))
        self.settings_group.setTitle(t('desktop.infoTab.ragSettingsGroupTitle'))
        self.model_settings_group.setTitle(t('desktop.infoTab.modelSettingsGroup'))
        if hasattr(self, 'plan_group'):
            self.plan_group.setTitle(t('desktop.infoTab.planGroupTitle'))
        if hasattr(self, 'execution_group'):
            self.execution_group.setTitle(t('desktop.infoTab.executionGroupTitle'))
        self.stats_group.setTitle(t('desktop.infoTab.statsGroupTitle'))
        if hasattr(self, 'data_group'):
            self.data_group.setTitle(t('desktop.infoTab.dataManageGroupTitle'))

        # --- Folder section ---
        self.folder_path_label.setText(t('desktop.infoTab.folderPath', path=self._folder_path))
        self.open_folder_btn.setText(t('desktop.infoTab.openFolder'))
        self.file_tree.setHeaderLabels(t('desktop.infoTab.fileTreeHeaders'))
        # 凡例ラベルを現在言語で再翻訳
        if hasattr(self, '_legend_labels'):
            for lbl, key in self._legend_labels:
                lbl.setText(t(f'desktop.infoTab.{key}'))
        # ファイルツリーのステータス列を現在言語で再翻訳
        _status_map = {
            "new": t('desktop.infoTab.ragStatusNew'),
            "modified": t('desktop.infoTab.ragStatusChanged'),
            "unchanged": t('desktop.infoTab.ragStatusBuilt'),
            "deleted": t('desktop.infoTab.ragStatusDeleted'),
        }
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            status_key = item.data(3, Qt.ItemDataRole.UserRole)
            if status_key in _status_map:
                item.setText(3, _status_map[status_key])
        self.refresh_btn.setText(t('desktop.infoTab.refresh'))

        # --- Settings section ---
        self.time_label.setText(t('desktop.infoTab.estimatedTime'))
        self.time_spin.setSuffix(t('desktop.infoTab.minuteSuffix'))
        self.time_spin.setToolTip(t('desktop.infoTab.timeLimitTip'))

        # Model combo labels
        self.claude_model_label.setText(t('desktop.infoTab.claudeModelSelect'))
        self.exec_llm_label.setText(t('desktop.infoTab.execLLMSelect'))
        self.quality_llm_label.setText(t('desktop.infoTab.qualityLLMSelect'))
        self.embedding_label.setText(t('desktop.infoTab.embeddingSelect'))
        self.refresh_ollama_btn.setText(t('desktop.infoTab.refreshOllamaModels'))

        # Update Claude model combo display names (i18n)
        for i in range(self.claude_model_combo.count()):
            model_id = self.claude_model_combo.itemData(i)
            for m in CLAUDE_MODELS:
                if m["id"] == model_id and m.get("i18n_display"):
                    self.claude_model_combo.setItemText(i, t(m["i18n_display"]))
                    break

        self.chunk_label.setText(t('desktop.infoTab.chunkSizeLabel'))
        self.chunk_size_spin.setSuffix(t('desktop.infoTab.tokenSuffix'))
        self.chunk_size_spin.setToolTip(t('desktop.infoTab.chunkSizeTip'))
        self.overlap_label.setText(t('desktop.infoTab.overlapLabel'))
        self.overlap_spin.setSuffix(t('desktop.infoTab.tokenSuffix'))
        self.overlap_spin.setToolTip(t('desktop.infoTab.overlapTip'))
        # v11.0.0: Bottom save button removed — per-section save buttons used instead

        # --- RAG Auto-Enhancement section (v11.0.0) ---
        if hasattr(self, 'auto_enhance_group'):
            self.auto_enhance_group.setTitle(t('desktop.infoTab.autoEnhance'))
        if hasattr(self, 'auto_kg_check'):
            self.auto_kg_check.setText(t('desktop.infoTab.autoKgUpdate'))
            self.auto_kg_check.setToolTip(t('desktop.infoTab.autoKgUpdateTip'))
        if hasattr(self, 'hype_check'):
            self.hype_check.setText(t('desktop.infoTab.hypeEnabled'))
            self.hype_check.setToolTip(t('desktop.infoTab.hypeEnabledTip'))
        if hasattr(self, 'reranker_check'):
            self.reranker_check.setText(t('desktop.infoTab.rerankerEnabled'))
            self.reranker_check.setToolTip(t('desktop.infoTab.rerankerEnabledTip'))
        if hasattr(self, 'auto_enhance_info'):
            self.auto_enhance_info.setText(t('desktop.infoTab.autoEnhanceInfo'))

        # --- 記憶・知識管理セクション (settings sub-tab) ---
        if hasattr(self, 'rag_memory_group'):
            self.rag_memory_group.setTitle(t('desktop.settings.memory'))
        if hasattr(self, 'rag_memory_auto_save_cb'):
            self.rag_memory_auto_save_cb.setText(t('desktop.settings.memoryAutoSave'))
            self.rag_memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        if hasattr(self, 'rag_knowledge_enabled_cb'):
            self.rag_knowledge_enabled_cb.setText(t('desktop.settings.knowledgeEnabled'))
        if hasattr(self, 'rag_encyclopedia_enabled_cb'):
            self.rag_encyclopedia_enabled_cb.setText(t('desktop.settings.encyclopediaEnabled'))

        # --- Plan section (hidden, hasattr guard) ---
        if hasattr(self, 'plan_summary_label'):
            self.plan_summary_label.setText(t('desktop.infoTab.planSummaryLabel'))
        if hasattr(self, 'plan_summary_text'):
            self.plan_summary_text.setPlaceholderText(t('desktop.infoTab.planPlaceholder'))
        if hasattr(self, 'copy_plan_btn'):
            self.copy_plan_btn.setText(t('desktop.infoTab.copyPlan'))
            self.copy_plan_btn.setToolTip(t('desktop.infoTab.copyPlanTip'))
        if hasattr(self, 'create_plan_btn'):
            self.create_plan_btn.setText(t('desktop.infoTab.createPlan'))

        # --- Execution section (hidden, hasattr guard) ---
        if hasattr(self, 'start_btn'):
            self.start_btn.setText(t('desktop.infoTab.startBuild'))
        if hasattr(self, 'stop_btn'):
            self.stop_btn.setText(t('desktop.infoTab.stopBuild'))
        if hasattr(self, 'rebuild_btn'):
            self.rebuild_btn.setText(t('desktop.infoTab.retryBuild'))

        # --- Stats section (name labels) ---
        stats_name_keys = {
            "total_chunks": 'desktop.infoTab.totalChunks',
            "total_embeddings": 'desktop.infoTab.totalEmbeddings',
            "semantic_nodes": None,  # "Semantic Nodes" is not a t() key
            "last_build": 'desktop.infoTab.lastBuild',
            "build_count": 'desktop.infoTab.buildCount',
        }
        for key, i18n_key in stats_name_keys.items():
            if i18n_key is not None:
                self.stats_name_labels[key].setText(t(i18n_key))

        # --- Data management section (hidden, hasattr guard) ---
        if hasattr(self, 'orphan_tree'):
            self.orphan_tree.setHeaderLabels(t('desktop.infoTab.orphanTreeHeaders'))
        if hasattr(self, 'scan_orphan_btn'):
            self.scan_orphan_btn.setText(t('desktop.infoTab.orphanScan'))
            self.scan_orphan_btn.setToolTip(t('desktop.infoTab.orphanScanTip'))
        if hasattr(self, 'delete_orphan_btn'):
            self.delete_orphan_btn.setText(t('desktop.infoTab.deleteOrphans'))
            self.delete_orphan_btn.setToolTip(t('desktop.infoTab.deleteOrphansTip'))
        if hasattr(self, 'doc_delete_label'):
            self.doc_delete_label.setText(t('desktop.infoTab.docDeleteLabel'))
        if hasattr(self, 'doc_tree'):
            self.doc_tree.setHeaderLabels(t('desktop.infoTab.docTreeHeaders'))
        if hasattr(self, 'delete_doc_btn'):
            self.delete_doc_btn.setText(t('desktop.infoTab.deleteSelectedDocs'))
            self.delete_doc_btn.setToolTip(t('desktop.infoTab.deleteSelectedDocsTip'))

        # --- RAG Progress Widgets ---
        if hasattr(self, 'progress_widget') and hasattr(self.progress_widget, 'retranslateUi'):
            self.progress_widget.retranslateUi()
        if hasattr(self, 'rag_progress_widget') and hasattr(self.rag_progress_widget, 'retranslateUi'):
            self.rag_progress_widget.retranslateUi()

        # --- Refresh dynamic content with new language ---
        self._refresh_file_list()
        self._refresh_rag_stats()
        if hasattr(self, 'orphan_tree'):
            self._scan_orphans()
        if hasattr(self, 'doc_tree'):
            self._refresh_doc_list()

        # Update plan status if no plan exists
        if not self._current_plan and hasattr(self, 'plan_status_label'):
            self.plan_status_label.setText(t('desktop.infoTab.planStatusDefault'))

    # =========================================================================
    # シグナル接続
    # =========================================================================

    def _connect_signals(self):
        """内部シグナルを接続"""
        pass  # ビルダーシグナルは_start_build()内で接続

    # =========================================================================
    # v11.0.0: RAGチャット アクション
    # =========================================================================

    def _append_rag_chat_msg(self, role: str, content: str):
        """チャット表示エリアにメッセージを追記"""
        import html as html_lib
        if role == "user":
            html = (
                f"<div style='margin: 8px 0; padding: 8px 12px; "
                f"background: rgba(0,212,255,0.1); border-radius: 6px;'>"
                f"<b style='color:{COLORS['accent']};'>You:</b> "
                f"{html_lib.escape(content).replace(chr(10), '<br>')}</div>"
            )
        elif role == "assistant":
            html = (
                f"<div style='margin: 8px 0; padding: 8px 12px; "
                f"background: rgba(0,255,136,0.05); border-radius: 6px;'>"
                f"<b style='color:{COLORS['success']};'>RAG:</b> "
                f"{html_lib.escape(content).replace(chr(10), '<br>')}</div>"
            )
        else:
            html = (
                f"<div style='margin: 4px 0; padding: 4px 12px; "
                f"color: {COLORS['text_secondary']}; font-size: 11px; font-style: italic;'>"
                f"{html_lib.escape(content)}</div>"
            )
        self.rag_chat_display.append(html)
        # スクロールを最下部へ
        sb = self.rag_chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_rag_chat_send(self):
        """RAGチャット送信"""
        message = self.rag_chat_input.toPlainText().strip()
        if not message:
            return
        if self._rag_chat_worker and self._rag_chat_worker.isRunning():
            return
        self.rag_chat_input.clear()
        self._rag_chat_messages.append({"role": "user", "content": message})
        self._append_rag_chat_msg("user", message)
        self._do_rag_chat_query(message)

    def _on_rag_continue_send(self):
        """会話継続送信"""
        message = self.rag_continue_input.toPlainText().strip()
        if not message:
            return
        self.rag_continue_input.clear()
        self._rag_chat_messages.append({"role": "user", "content": message})
        self._append_rag_chat_msg("user", message)
        self._do_rag_chat_query(message)

    def _on_rag_quick_yes(self):
        """はい クイックボタン"""
        self.rag_continue_input.setPlainText(t('desktop.infoTab.ragQuickYesMsg'))
        self._on_rag_continue_send()

    def _on_rag_quick_continue(self):
        """続行 クイックボタン"""
        self.rag_continue_input.setPlainText(t('desktop.infoTab.ragQuickContinueMsg'))
        self._on_rag_continue_send()

    def _on_rag_quick_exec(self):
        """実行 クイックボタン"""
        self.rag_continue_input.setPlainText(t('desktop.infoTab.ragQuickExecMsg'))
        self._on_rag_continue_send()

    def _do_rag_chat_query(self, query: str):
        """RAGコンテキストを付与してCloudAIに問い合わせ"""
        self.rag_chat_send_btn.setEnabled(False)
        self.rag_continue_send_btn.setEnabled(False)
        self.rag_chat_status.setText(t('desktop.infoTab.ragStatusQuerying'))

        # RAGコンテキスト取得 → ワーカー起動
        rag_context = ""
        try:
            from ..web.rag_bridge import RAGBridge
            bridge = RAGBridge()
            rag_context = bridge.build_context(query, tab="ragChat")
        except Exception as e:
            logger.debug(f"RAG context build skipped: {e}")

        from ..utils.constants import get_default_claude_model
        model_id = self.claude_model_combo.currentData() or get_default_claude_model()
        self._rag_chat_worker = RAGChatWorkerThread(
            messages=list(self._rag_chat_messages),
            rag_context=rag_context,
            model_id=model_id,
            parent=self,
        )
        self._rag_chat_worker.completed.connect(self._on_rag_chat_worker_done)
        self._rag_chat_worker.errorOccurred.connect(self._on_rag_chat_worker_error)
        self._rag_chat_worker.start()

    def _on_rag_chat_worker_done(self, response: str):
        """ワーカー正常完了"""
        self._rag_chat_messages.append({"role": "assistant", "content": response})
        self._append_rag_chat_msg("assistant", response)
        self.rag_chat_send_btn.setEnabled(True)
        self.rag_continue_send_btn.setEnabled(True)
        self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))

    def _on_rag_chat_worker_error(self, error: str):
        """ワーカーエラー"""
        self._append_rag_chat_msg("system", f"エラー: {error}")
        self.rag_chat_send_btn.setEnabled(True)
        self.rag_continue_send_btn.setEnabled(True)
        self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))

    def _on_rag_add_files(self):
        """チャットタブからファイルを追加"""
        extensions = " ".join(f"*{ext}" for ext in SUPPORTED_DOC_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self, t('desktop.infoTab.addFilesTitle'),
            "", t('desktop.infoTab.addFilesFilter', ext=extensions)
        )
        if files:
            folder = Path(self._folder_path)
            folder.mkdir(parents=True, exist_ok=True)
            added_names = []
            for src in files:
                src_path = Path(src)
                size_mb = src_path.stat().st_size / (1024 * 1024)
                if size_mb > MAX_FILE_SIZE_MB:
                    self._append_rag_chat_msg(
                        "system",
                        f"⚠️ {src_path.name} はサイズ超過でスキップ ({size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB)"
                    )
                    continue
                dest = folder / src_path.name
                try:
                    shutil.copy2(str(src_path), str(dest))
                    added_names.append(src_path.name)
                except Exception as e:
                    logger.error(f"File copy failed: {e}")
            if added_names:
                self._refresh_file_list()
                names_str = ", ".join(added_names)
                self._append_rag_chat_msg(
                    "system",
                    f"📄 ファイル追加: {names_str} (要再構築)"
                )

    def _on_rag_plan_preview_click(self):
        """チャットタブからプランプレビューを開始（v11.3.0）"""
        self._append_rag_chat_msg("system", "📋 プランを作成中...")
        if hasattr(self, 'rag_plan_preview_btn'):
            self.rag_plan_preview_btn.setEnabled(False)
        if hasattr(self, 'rag_chat_status'):
            self.rag_chat_status.setText(t('desktop.infoTab.ragStatusBuilding'))
        QTimer.singleShot(100, self._do_rag_build_plan_only)

    def _do_rag_build_plan(self):
        """構築プランを作成して実行"""
        try:
            from ..rag.rag_planner import RAGPlanner
            from ..memory.model_config import _load_rag_settings
            _planner_model = _load_rag_settings().get("planner_model") or ""
            if not _planner_model and hasattr(self, 'planner_model_combo'):
                _planner_model = self.planner_model_combo.currentText()
            planner = RAGPlanner(planner_engine=_planner_model or None)
            plan = planner.create_plan(
                self._folder_path,
                self.time_spin.value(),
            )
            self._current_plan = plan
            summary = plan.get("summary", "")
            self._append_rag_chat_msg(
                "system",
                f"✅ プラン完了: {summary[:80]}{'...' if len(summary) > 80 else ''}"
            )
            self._start_build()
        except Exception as e:
            logger.error(f"RAG build plan failed: {e}")
            self._append_rag_chat_msg("system", f"❌ プラン作成失敗: {str(e)[:200]}")
            self.rag_build_btn.setEnabled(True)
            self.rag_build_stop_btn.setEnabled(False)
            self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))

    def _do_rag_build_plan_only(self):
        """プランを作成してチャットに表示・構築実行ボタンを有効化（v11.3.0）"""
        try:
            from ..rag.rag_planner import RAGPlanner
            from ..memory.model_config import _load_rag_settings
            _planner_model = _load_rag_settings().get("planner_model") or ""
            if not _planner_model and hasattr(self, 'planner_model_combo'):
                _planner_model = self.planner_model_combo.currentText()
            planner = RAGPlanner(planner_engine=_planner_model or None)
            plan = planner.create_plan(
                self._folder_path,
                self.time_spin.value(),
            )
            self._current_plan = plan

            # プランサマリーをチャットに表示
            analysis = plan.get("analysis", {})
            exec_plan = plan.get("execution_plan", {})
            total_files = analysis.get("total_files", 0)
            total_kb = analysis.get("total_size_kb", 0)
            total_mb = round(total_kb / 1024, 1)
            total_min = round(exec_plan.get("total_estimated_minutes", 0), 1)

            classifications = analysis.get("file_classifications", [])
            file_lines = []
            for fc in classifications[:5]:
                file_lines.append(
                    f"  • {fc.get('file','')} → {fc.get('category','')} / {fc.get('priority','')}"
                )
            if len(classifications) > 5:
                file_lines.append(f"  他{len(classifications) - 5}件")
            file_section = "\n".join(file_lines) if file_lines else "  (なし)"

            steps = exec_plan.get("steps", [])
            step_lines = []
            for s in steps:
                step_lines.append(
                    f"  {s.get('step_id','?')}. {s.get('name','')} "
                    f"({s.get('model','')}) ~{round(s.get('estimated_minutes', 0), 1)}分"
                )
            step_section = "\n".join(step_lines) if step_lines else "  (なし)"

            msg = (
                f"📋 プラン策定完了\n"
                f"────────────────\n"
                f"ファイル数: {total_files}件 (合計 {total_mb}MB)\n"
                f"推定実行時間: 約 {total_min}分\n"
                f"\n[ファイル分類]\n{file_section}\n"
                f"\n[実行ステップ]\n{step_section}\n"
                f"\n「▶ 構築実行」ボタンで構築を開始してください。"
            )
            self._append_rag_chat_msg("system", msg)

            if hasattr(self, 'rag_build_execute_btn'):
                self.rag_build_execute_btn.setEnabled(True)
            if hasattr(self, 'rag_plan_preview_btn'):
                self.rag_plan_preview_btn.setEnabled(True)
            if hasattr(self, 'rag_chat_status'):
                self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))
        except Exception as e:
            logger.error(f"RAG plan preview failed: {e}")
            self._append_rag_chat_msg("system", f"❌ プラン作成失敗: {str(e)[:200]}")
            if hasattr(self, 'rag_plan_preview_btn'):
                self.rag_plan_preview_btn.setEnabled(True)
            if hasattr(self, 'rag_chat_status'):
                self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))

    def _on_rag_build_execute_click(self):
        """構築実行ボタンクリック（v11.3.0）"""
        if not getattr(self, '_current_plan', None):
            self._append_rag_chat_msg("system", f"⚠️ {t('desktop.infoTab.ragPlanPreviewHint')}")
            return
        if hasattr(self, 'rag_build_execute_btn'):
            self.rag_build_execute_btn.setEnabled(False)
        if hasattr(self, 'rag_plan_preview_btn'):
            self.rag_plan_preview_btn.setEnabled(False)
        if hasattr(self, 'rag_build_stop_btn'):
            self.rag_build_stop_btn.setEnabled(True)
        if hasattr(self, 'rag_chat_status'):
            self.rag_chat_status.setText(t('desktop.infoTab.ragStatusBuilding'))
        self._start_build()

    def _on_rag_build_stop_click(self):
        """チャットタブから構築停止"""
        self._stop_build()
        self._append_rag_chat_msg("system", "■ 構築を停止しました")

    def _on_rag_delete_click(self):
        """チャットタブからドキュメント削除ダイアログを表示"""
        try:
            import sqlite3
            db_path = Path("data/helix_memory.db")
            if not db_path.exists():
                self._append_rag_chat_msg("system", "⚠️ RAGデータベースが見つかりません")
                return
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT source_file, COUNT(*) as cnt FROM documents GROUP BY source_file ORDER BY source_file"
                ).fetchall()
            finally:
                conn.close()

            if not rows:
                self._append_rag_chat_msg("system", "⚠️ 構築済みドキュメントがありません")
                return

            # 選択ダイアログ
            dlg = QDialog(self)
            dlg.setWindowTitle(t('desktop.infoTab.ragDeleteDialogTitle'))
            dlg.resize(480, 360)
            dlg_layout = QVBoxLayout(dlg)
            dlg_layout.addWidget(QLabel(t('desktop.infoTab.ragDeleteDialogHint')))

            list_widget = QListWidget()
            for row in rows:
                item = QListWidgetItem(f"{row['source_file']}  ({row['cnt']} chunks)")
                item.setData(Qt.ItemDataRole.UserRole, row['source_file'])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                list_widget.addItem(item)
            dlg_layout.addWidget(list_widget)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            dlg_layout.addWidget(buttons)

            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            selected = [
                list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(list_widget.count())
                if list_widget.item(i).checkState() == Qt.CheckState.Checked
            ]
            if not selected:
                return

            result = self.cleanup_manager.delete_selected_documents(selected)
            self._refresh_doc_list()
            self._refresh_rag_stats()
            self._refresh_file_list()
            names_str = ", ".join(selected)
            self._append_rag_chat_msg(
                "system",
                f"🗑 削除完了: {names_str} "
                f"(chunks: {result['deleted_chunks']}, summaries: {result['deleted_summaries']})"
            )
        except Exception as e:
            logger.error(f"RAG delete failed: {e}")
            self._append_rag_chat_msg("system", f"❌ 削除エラー: {str(e)[:200]}")

    def _open_folder(self):
        """OSのファイルエクスプローラーでフォルダを開く"""
        folder = Path(self._folder_path)
        folder.mkdir(parents=True, exist_ok=True)

        abs_path = str(folder.resolve())
        try:
            if platform.system() == "Windows":
                os.startfile(abs_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", abs_path])
            else:
                subprocess.run(["xdg-open", abs_path])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def _refresh_ollama_models(self):
        """v11.0.0: ModelCatalog経由でモデル一覧を更新"""
        from ..utils.model_catalog import (
            get_rag_cloud_candidates, get_rag_local_candidates, populate_combo
        )
        try:
            # Cloudモデル更新
            cloud = get_rag_cloud_candidates()
            current_cloud = self.claude_model_combo.currentText()
            populate_combo(self.claude_model_combo, cloud, current_value=current_cloud)

            # ローカルモデル更新
            local = get_rag_local_candidates()
            for combo in [self.exec_llm_combo, self.quality_llm_combo, self.embedding_combo]:
                current = combo.currentText()
                populate_combo(combo, local, current_value=current)

            count = len(local)
            self.statusChanged.emit(f"Models refreshed: {len(cloud)} cloud + {count} local")
        except Exception as e:
            logger.debug(f"Model refresh failed: {e}")
            self.statusChanged.emit(f"Refresh failed: {e}")

    def _add_files(self):
        """ファイル追加ダイアログ"""
        extensions = " ".join(f"*{ext}" for ext in SUPPORTED_DOC_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self, t('desktop.infoTab.addFilesTitle'),
            "", t('desktop.infoTab.addFilesFilter', ext=extensions)
        )
        if files:
            folder = Path(self._folder_path)
            folder.mkdir(parents=True, exist_ok=True)
            added = 0
            for src in files:
                src_path = Path(src)
                # ファイルサイズチェック
                size_mb = src_path.stat().st_size / (1024 * 1024)
                if size_mb > MAX_FILE_SIZE_MB:
                    QMessageBox.warning(
                        self, t('desktop.infoTab.fileSizeOverTitle'),
                        t('desktop.infoTab.fileSizeExceeded', name=src_path.name, size=f"{size_mb:.1f}", max=MAX_FILE_SIZE_MB)
                    )
                    continue
                dest = folder / src_path.name
                try:
                    shutil.copy2(str(src_path), str(dest))
                    added += 1
                except Exception as e:
                    logger.error(f"Failed to copy {src_path.name}: {e}")

            if added > 0:
                self._refresh_file_list()
                self.statusChanged.emit(t('desktop.infoTab.filesAdded', count=added))

    def _refresh_file_list(self):
        """v11.0.0: ファイル一覧を更新（読み取り専用・カラーコーディング）"""
        self.file_tree.clear()
        folder = Path(self._folder_path)
        folder.mkdir(parents=True, exist_ok=True)

        diff_detector = DiffDetector(db_conn_factory=self._get_db_conn)
        diff_result = diff_detector.detect_changes(self._folder_path)

        total_size = 0
        file_count = 0

        for fi in diff_result.new_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "new")
            total_size += fi.size
            file_count += 1

        for fi in diff_result.modified_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "modified")
            total_size += fi.size
            file_count += 1

        for fi in diff_result.unchanged_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "unchanged")
            total_size += fi.size
            file_count += 1

        for name in diff_result.deleted_files:
            self._add_file_tree_item(name, 0, 0, "deleted")

        total_str = self._format_size(total_size)
        diff_summary = diff_result.summary
        self.total_label.setText(t('desktop.infoTab.totalFiles', count=file_count, size=total_str, diff=diff_summary))

    def _add_file_tree_item(self, name: str, size: int, mtime: float, status: str):
        """v11.0.0: ファイル一覧に1行追加（読み取り専用・カラーコーディング）"""
        size_str = self._format_size(size) if size > 0 else "-"
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime > 0 else "-"

        status_labels = {
            "new": t('desktop.infoTab.ragStatusNew'),
            "modified": t('desktop.infoTab.ragStatusChanged'),
            "unchanged": t('desktop.infoTab.ragStatusBuilt'),
            "deleted": t('desktop.infoTab.ragStatusDeleted'),
        }
        status_label = status_labels.get(status, status)

        item = QTreeWidgetItem([name, size_str, date_str, status_label])
        item.setData(3, Qt.ItemDataRole.UserRole, status)   # 言語切替時の再翻訳用
        # 読み取り専用（チェックボックスなし）
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

        # カラーコーディング
        color_map = {
            "new": QColor(COLORS["success"]),       # 緑
            "modified": QColor(COLORS["warning"]),   # 黄
            "unchanged": QColor(COLORS["text_secondary"]),  # グレー
            "deleted": QColor(COLORS["error"]),      # 赤
        }
        color = color_map.get(status)
        if color:
            for col in range(4):
                item.setForeground(col, color)

        item.setData(0, Qt.ItemDataRole.UserRole, status)
        self.file_tree.addTopLevelItem(item)

    def _get_db_conn(self):
        """helix_memory.db への接続を返す"""
        import sqlite3
        db_path = Path("data/helix_memory.db")
        if not db_path.exists():
            return sqlite3.connect(str(db_path))
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_selected_files(self) -> list:
        """チェック済みファイルの名前リストを返す"""
        selected = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.text(0))
        return selected

    def _select_all_files(self):
        """全ファイルを選択"""
        for i in range(self.file_tree.topLevelItemCount()):
            self.file_tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked)

    def _deselect_all_files(self):
        """全ファイルの選択を解除"""
        for i in range(self.file_tree.topLevelItemCount()):
            self.file_tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Unchecked)

    def _select_changed_only(self):
        """新規・変更ありのファイルのみ選択"""
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            status = item.data(0, Qt.ItemDataRole.UserRole)
            if status in ("new", "modified"):
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)

    def _refresh_rag_stats(self):
        """RAG統計を更新"""
        try:
            builder = RAGBuilder(folder_path=self._folder_path)
            stats = builder.get_rag_stats()

            self.stats_labels["total_chunks"].setText(str(stats.get("total_chunks", 0)))
            self.stats_labels["total_embeddings"].setText(str(stats.get("total_embeddings", 0)))
            self.stats_labels["semantic_nodes"].setText(str(stats.get("semantic_nodes", 0)))
            self.stats_labels["build_count"].setText(t('desktop.infoTab.buildCountFormat', count=stats.get('build_count', 0)))

            last_build = stats.get("last_build")
            if last_build:
                try:
                    dt = datetime.fromisoformat(last_build)
                    self.stats_labels["last_build"].setText(dt.strftime("%m/%d %H:%M"))
                except Exception:
                    self.stats_labels["last_build"].setText(t('desktop.infoTab.lastBuildExist'))
            else:
                self.stats_labels["last_build"].setText(t('desktop.infoTab.lastBuildNone'))
        except Exception as e:
            logger.debug(f"RAG stats refresh error: {e}")

    def _create_plan(self):
        """Claudeにプラン作成を依頼"""
        selected = self._get_selected_files()
        if not selected:
            QMessageBox.information(
                self, t('desktop.infoTab.noFileSelected'),
                t('desktop.infoTab.noFileSelectedMsg')
            )
            return

        self.create_plan_btn.setEnabled(False)
        self.create_plan_btn.setText(t('desktop.infoTab.planCreating'))
        self.plan_status_label.setText(t('desktop.infoTab.planStatusCreating'))
        self.statusChanged.emit(t('desktop.infoTab.planCreatingStatus'))

        # バックグラウンドで実行（UIをブロックしないためQTimerで遅延）
        QTimer.singleShot(100, self._do_create_plan)

    def _do_create_plan(self):
        """プラン作成の実行"""
        try:
            from ..rag.rag_planner import RAGPlanner
            from ..memory.model_config import _load_rag_settings
            _planner_model = _load_rag_settings().get("planner_model") or ""
            if not _planner_model and hasattr(self, 'planner_model_combo'):
                _planner_model = self.planner_model_combo.currentText()
            planner = RAGPlanner(planner_engine=_planner_model or None)
            selected = self._get_selected_files()
            plan = planner.create_plan(
                self._folder_path,
                self.time_spin.value(),
                selected_files=selected if selected else None,
            )
            self._current_plan = plan
            self._display_plan(plan)
            self.start_btn.setEnabled(True)
            if plan.get("fallback"):
                self.statusChanged.emit(t('desktop.infoTab.planFallback'))
            else:
                self.statusChanged.emit(t('desktop.infoTab.planCreated'))
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            QMessageBox.warning(self, t('desktop.infoTab.planFailedTitle'), t('desktop.infoTab.errorPrefix', error=str(e)[:300]))
            self.plan_status_label.setText(t('desktop.infoTab.planStatusFailed'))
            self.statusChanged.emit(t('desktop.infoTab.planFailedTitle'))
        finally:
            self.create_plan_btn.setEnabled(True)
            self.create_plan_btn.setText(t('desktop.infoTab.createPlanBtn'))

    def _display_plan(self, plan: dict):
        """プランをUIに表示"""
        analysis = plan.get("analysis", {})
        exec_plan = plan.get("execution_plan", {})
        steps = exec_plan.get("steps", [])

        total_files = analysis.get("total_files", 0)
        total_est = exec_plan.get("total_estimated_minutes", 0)

        if plan.get("fallback"):
            self.plan_status_label.setText(t('desktop.infoTab.planStatusFallback'))
        else:
            self.plan_status_label.setText(t('desktop.infoTab.planStatusDone'))

        # サマリー表示
        summary = plan.get("summary", "")
        if summary:
            self.plan_summary_text.setPlainText(summary)
        else:
            self.plan_summary_text.setPlainText(t('desktop.infoTab.planNoSummary'))
        self.copy_plan_btn.setEnabled(True)

        # プラン詳細
        classifications = analysis.get("file_classifications", [])
        detail_parts = [t('desktop.infoTab.planDetailFormat', files=total_files, steps=len(steps), time=f"{total_est:.1f}")]
        for cls in classifications[:5]:
            detail_parts.append(
                f"  {cls['file']}: {cls.get('category', '?')} / "
                f"{t('desktop.infoTab.priorityLabel', priority=cls.get('priority', '?'))} / "
                f"{t('desktop.infoTab.estimatedChunks', chunks=cls.get('estimated_chunks', '?'))}"
            )
        if len(classifications) > 5:
            detail_parts.append(t('desktop.infoTab.planMoreFiles', count=len(classifications) - 5))
        self.plan_detail_label.setText("\n".join(detail_parts))

        # 進捗ウィジェットにステップ設定
        self.progress_widget.setup_steps(steps)

    def _copy_plan_summary(self):
        """プラン概要をクリップボードにコピー"""
        clipboard = QApplication.clipboard()
        full_text = self._build_full_plan_text()
        clipboard.setText(full_text)
        self.statusChanged.emit(t('desktop.infoTab.planCopied'))

    def _build_full_plan_text(self) -> str:
        """コピー用のプラン全文テキストを生成"""
        if not self._current_plan:
            return ""

        plan = self._current_plan
        analysis = plan.get("analysis", {})
        exec_plan = plan.get("execution_plan", {})
        classifications = analysis.get("file_classifications", [])
        total_est = exec_plan.get("total_estimated_minutes", 0)
        summary = plan.get("summary", "")

        lines = [
            t('desktop.infoTab.planSummaryHeader'),
            t('desktop.infoTab.planCreatedAt', datetime=datetime.now().strftime('%Y-%m-%d %H:%M')),
            t('desktop.infoTab.planEstimatedTime', time=f"{total_est:.1f}"),
            t('desktop.infoTab.planTargetFiles', count=analysis.get('total_files', 0)),
        ]

        if plan.get("fallback"):
            lines.append(t('desktop.infoTab.planDefaultNote'))

        if summary:
            lines.append(f"\n{t('desktop.infoTab.planSummarySection')}\n{summary}")

        if classifications:
            lines.append(f"\n{t('desktop.infoTab.planFileSection')}")
            for i, cls in enumerate(classifications, 1):
                lines.append(
                    f"  {i}. {cls['file']}\n"
                    f"     {t('desktop.infoTab.categoryLabel', category=cls.get('category', '?'))} / "
                    f"{t('desktop.infoTab.priorityLabel', priority=cls.get('priority', '?'))} / "
                    f"{t('desktop.infoTab.estimatedChunks', chunks=cls.get('estimated_chunks', '?'))}"
                )

        return "\n".join(lines)

    def _start_build(self):
        """RAG構築開始"""
        if not self._current_plan:
            QMessageBox.information(self, t('desktop.infoTab.planNotCreatedTitle'),
                                     t('desktop.infoTab.planNotCreatedMsg'))
            return

        self._builder = RAGBuilder(
            folder_path=self._folder_path,
            time_limit_minutes=self.time_spin.value(),
            plan=self._current_plan,
        )

        # 共有ロックを設定
        self.rag_lock = self._builder.lock

        # メインウィンドウにロックを伝搬
        if self.main_window:
            self.main_window._rag_lock = self.rag_lock

        # シグナル接続
        signals = self._builder.signals
        signals.progress_updated.connect(self.progress_widget.on_progress_updated)
        signals.time_updated.connect(self.progress_widget.on_time_updated)
        signals.step_started.connect(self.progress_widget.on_step_started)
        signals.step_progress.connect(self.progress_widget.on_step_progress)
        signals.step_completed.connect(self.progress_widget.on_step_completed)
        signals.status_changed.connect(self._on_status_changed)
        signals.lock_changed.connect(self._on_lock_changed)
        signals.error_occurred.connect(self._on_error)
        signals.verification_result.connect(self._on_verification_result)
        signals.build_completed.connect(self._on_build_completed)

        # v11.0.0: チャット内進捗ウィジェットにも接続
        if hasattr(self, 'rag_progress_widget'):
            signals.progress_updated.connect(self.rag_progress_widget.on_progress_updated)
            signals.time_updated.connect(self.rag_progress_widget.on_time_updated)
            signals.step_started.connect(self.rag_progress_widget.on_step_started)
            signals.step_progress.connect(self.rag_progress_widget.on_step_progress)
            signals.step_completed.connect(self.rag_progress_widget.on_step_completed)
            signals.step_started.connect(self._on_build_step_started_chat)
            self.rag_progress_widget.setVisible(True)

        # UIを更新（旧ボタン）
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.rebuild_btn.setEnabled(False)
        self.create_plan_btn.setEnabled(False)

        # 開始
        self._builder.start()
        self.statusChanged.emit(t('desktop.infoTab.buildStarted'))

    def _stop_build(self):
        """RAG構築中止"""
        if self._builder and self._builder.isRunning():
            self._builder.cancel()
            self.stop_btn.setEnabled(False)
            self.statusChanged.emit(t('desktop.infoTab.buildStopping'))

    def _rebuild(self):
        """再実行"""
        if self._current_plan:
            self._start_build()
        else:
            self._create_plan()

    def _on_status_changed(self, status: str):
        """ステータス変更"""
        status_text = {
            "running": t('desktop.infoTab.statusRunning'),
            "verifying": t('desktop.infoTab.statusVerifying'),
            "completed": t('desktop.infoTab.statusComplete'),
            "failed": t('desktop.infoTab.statusFailed'),
            "cancelled": t('desktop.infoTab.statusAborted'),
        }.get(status, status)
        self.statusChanged.emit(status_text)

    def _on_lock_changed(self, locked: bool):
        """ロック状態変更"""
        if self.main_window:
            # mixAI/soloAIのオーバーレイを制御
            if hasattr(self.main_window, 'llmmix_tab'):
                tab = self.main_window.llmmix_tab
                if hasattr(tab, 'rag_lock_overlay'):
                    if locked:
                        tab.rag_lock_overlay.show_lock()
                    else:
                        tab.rag_lock_overlay.hide_lock()
            if hasattr(self.main_window, 'claude_tab'):
                tab = self.main_window.claude_tab
                if hasattr(tab, 'rag_lock_overlay'):
                    if locked:
                        tab.rag_lock_overlay.show_lock()
                    else:
                        tab.rag_lock_overlay.hide_lock()

    def _on_build_step_started_chat(self, step_name: str):
        """v11.0.0: 構築ステップ開始をチャットに表示"""
        if hasattr(self, 'rag_chat_display'):
            self._append_rag_chat_msg("system", f"🔧 {step_name}...")

    def _on_error(self, step_name: str, error_message: str):
        """エラー発生"""
        logger.error(f"RAG build error at {step_name}: {error_message}")
        self.statusChanged.emit(t('desktop.infoTab.errorStep', step=step_name))
        if hasattr(self, 'rag_chat_display'):
            self._append_rag_chat_msg("system", f"❌ エラー ({step_name}): {error_message[:120]}")

    def _on_verification_result(self, result: dict):
        """検証結果受信"""
        verdict = result.get("overall_verdict", "UNKNOWN")
        score = result.get("score", 0)
        logger.info(f"Verification result: {verdict} (score={score})")

    def _on_build_completed(self, success: bool, message: str):
        """v11.0.0: 構築完了"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.rebuild_btn.setEnabled(True)
        self.create_plan_btn.setEnabled(True)

        # v11.3.0: チャット用ボタン状態を更新
        if hasattr(self, 'rag_plan_preview_btn'):
            self.rag_plan_preview_btn.setEnabled(True)
        if hasattr(self, 'rag_build_execute_btn'):
            self.rag_build_execute_btn.setEnabled(False)
        if hasattr(self, 'rag_build_stop_btn'):
            self.rag_build_stop_btn.setEnabled(False)
        if hasattr(self, 'rag_progress_widget'):
            self.rag_progress_widget.setVisible(False)
        if hasattr(self, 'rag_chat_status'):
            self.rag_chat_status.setText(t('desktop.infoTab.ragStatusReady'))

        self._refresh_rag_stats()
        self._refresh_file_list()

        # v11.0.0: 結果をチャットに表示
        if hasattr(self, 'rag_chat_display'):
            if success:
                self._append_rag_chat_msg("system", f"✅ RAG構築完了! {message}")
            else:
                self._append_rag_chat_msg("system", f"⚠️ 構築結果: {message}")

    # =========================================================================
    # データ管理
    # =========================================================================

    def _scan_orphans(self):
        """孤児データをスキャン"""
        try:
            orphans = self.cleanup_manager.scan_orphans()
            self.orphan_tree.clear()

            if not orphans:
                self.orphan_status_label.setText(t('desktop.infoTab.healthOk'))
                self.orphan_tree.setVisible(False)
                self.delete_orphan_btn.setEnabled(False)
                return

            self.orphan_status_label.setText(t('desktop.infoTab.orphansFound', count=len(orphans)))
            self.orphan_tree.setVisible(True)
            self.delete_orphan_btn.setEnabled(True)

            for o in orphans:
                item = QTreeWidgetItem([
                    o["source_file"],
                    str(o["chunk_count"]),
                    o["safety_label"],
                ])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # 安全レベル1はデフォルトチェック、2はチェックなし
                if o["safety_level"] == 1:
                    item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                self.orphan_tree.addTopLevelItem(item)

        except Exception as e:
            logger.debug(f"Orphan scan error: {e}")
            self.orphan_status_label.setText(t('desktop.infoTab.healthUnknown'))

    def _delete_selected_orphans(self):
        """選択された孤児データを削除"""
        selected = []
        for i in range(self.orphan_tree.topLevelItemCount()):
            item = self.orphan_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.text(0))

        if not selected:
            QMessageBox.information(self, t('desktop.infoTab.noOrphansSelected'), t('desktop.infoTab.noOrphansSelectedMsg'))
            return

        self._confirm_and_delete(selected, is_orphan=True)

    def _refresh_doc_list(self):
        """構築済みドキュメント一覧を更新"""
        self.doc_tree.clear()
        try:
            import sqlite3
            db_path = Path("data/helix_memory.db")
            if not db_path.exists():
                return
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("""
                    SELECT source_file, COUNT(*) as chunk_count
                    FROM documents
                    GROUP BY source_file
                    ORDER BY source_file
                """).fetchall()
                for row in rows:
                    item = QTreeWidgetItem([row["source_file"], str(row["chunk_count"])])
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    self.doc_tree.addTopLevelItem(item)
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Doc list refresh error: {e}")

    def _delete_selected_documents(self):
        """選択したドキュメントのRAGデータを削除"""
        selected = []
        for i in range(self.doc_tree.topLevelItemCount()):
            item = self.doc_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.text(0))

        if not selected:
            QMessageBox.information(self, t('desktop.infoTab.noDocsSelected'), t('desktop.infoTab.noDocsSelectedMsg'))
            return

        self._confirm_and_delete(selected, is_orphan=False)

    def _confirm_and_delete(self, source_files: list, is_orphan: bool = False):
        """削除前の確認ダイアログ"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(t('desktop.infoTab.deleteConfirmTitle'))

        count = len(source_files)
        if is_orphan:
            msg.setText(t('desktop.infoTab.deleteOrphanConfirm', count=count))
        else:
            msg.setText(t('desktop.infoTab.docDeleteConfirmMsg', count=count))

        msg.setDetailedText("\n".join(source_files))
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)

        if msg.exec() == QMessageBox.StandardButton.Ok:
            if is_orphan:
                result = self.cleanup_manager.delete_orphans(source_files)
            else:
                result = self.cleanup_manager.delete_selected_documents(source_files)

            self.statusChanged.emit(
                t('desktop.infoTab.deleteComplete', chunks=result['deleted_chunks'], summaries=result['deleted_summaries'], links=result['deleted_links'])
            )
            self._scan_orphans()
            self._refresh_doc_list()
            self._refresh_rag_stats()

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _on_planner_model_changed(self, text: str):
        """計画担当モデル変更時の警告表示制御（v11.3.0）"""
        if hasattr(self, 'planner_model_warning'):
            is_local = text and not text.startswith("claude-") and "codex" not in text.lower()
            self.planner_model_warning.setVisible(is_local)

    def _save_rag_settings(self):
        """RAG構築設定をapp_settings.jsonに保存（v10.1.0: モデル選択含む）"""
        try:
            settings_path = Path("config/app_settings.json")
            settings = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

            # Claude model: userDataにIDが格納されている
            claude_model_id = self.claude_model_combo.currentData() or self.claude_model_combo.currentText()

            new_rag = {
                "time_limit_minutes": self.time_spin.value(),
                "chunk_size": self.chunk_size_spin.value(),
                "overlap": self.overlap_spin.value(),
                "claude_model": claude_model_id,
                "exec_llm": self.exec_llm_combo.currentText(),
                "quality_llm": self.quality_llm_combo.currentText(),
                "embedding_model": self.embedding_combo.currentText(),
                "planner_model": self.planner_model_combo.currentText() if hasattr(self, 'planner_model_combo') else "",
                # v11.0.0: RAG Auto-Enhancement (Phase 6-E)
                "auto_kg_update": self.auto_kg_check.isChecked() if hasattr(self, 'auto_kg_check') else True,
                "hype_enabled": self.hype_check.isChecked() if hasattr(self, 'hype_check') else True,
                "reranker_enabled": self.reranker_check.isChecked() if hasattr(self, 'reranker_check') else True,
            }

            settings["rag"] = new_rag

            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            self.statusChanged.emit(t('desktop.infoTab.ragSettingsSaved'))
            logger.info(f"RAG settings saved: {settings['rag']}")
        except Exception as e:
            logger.error(f"Failed to save RAG settings: {e}")
            QMessageBox.warning(self, t('desktop.infoTab.ragSettingsSaveFailedTitle'), t('desktop.infoTab.ragSettingsSaveError', error=str(e)))

    def _load_rag_settings(self):
        """app_settings.jsonからRAG構築設定を読み込んでUI反映（v10.1.0: モデル選択含む）"""
        try:
            settings_path = Path("config/app_settings.json")
            if not settings_path.exists():
                return
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            rag = settings.get("rag", {})
            if "time_limit_minutes" in rag:
                self.time_spin.setValue(rag["time_limit_minutes"])
            if "chunk_size" in rag:
                self.chunk_size_spin.setValue(rag["chunk_size"])
            if "overlap" in rag:
                self.overlap_spin.setValue(rag["overlap"])

            # モデル選択復元
            if "claude_model" in rag:
                idx = self.claude_model_combo.findData(rag["claude_model"])
                if idx >= 0:
                    self.claude_model_combo.setCurrentIndex(idx)
            if "exec_llm" in rag:
                self.exec_llm_combo.setCurrentText(rag["exec_llm"])
            if "quality_llm" in rag:
                self.quality_llm_combo.setCurrentText(rag["quality_llm"])
            if "embedding_model" in rag:
                self.embedding_combo.setCurrentText(rag["embedding_model"])
            if "planner_model" in rag and hasattr(self, 'planner_model_combo') and rag["planner_model"]:
                self.planner_model_combo.setCurrentText(rag["planner_model"])

            # v11.0.0: RAG Auto-Enhancement (Phase 6-E)
            if hasattr(self, 'auto_kg_check'):
                self.auto_kg_check.setChecked(rag.get("auto_kg_update", True))
            if hasattr(self, 'hype_check'):
                self.hype_check.setChecked(rag.get("hype_enabled", True))
            if hasattr(self, 'reranker_check'):
                self.reranker_check.setChecked(rag.get("reranker_enabled", True))

            logger.debug(f"RAG settings loaded: {rag}")
        except Exception as e:
            logger.debug(f"RAG settings load skipped: {e}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """バイト数を読みやすい形式に変換"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
