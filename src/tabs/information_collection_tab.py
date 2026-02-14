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
    QProgressBar, QTextEdit, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ..utils.constants import (
    INFORMATION_FOLDER, SUPPORTED_DOC_EXTENSIONS,
    DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, MAX_FILE_SIZE_MB,
    RAG_DEFAULT_TIME_LIMIT, RAG_MIN_TIME_LIMIT, RAG_MAX_TIME_LIMIT,
    RAG_TIME_STEP, RAG_CHUNK_STEP, RAG_OVERLAP_STEP,
)
from ..utils.styles import (
    COLORS, SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTN,
    DANGER_BTN, PROGRESS_BAR_STYLE, SPINBOX_STYLE, COMBO_BOX_STYLE,
)
from ..rag.rag_builder import RAGBuilder, RAGBuildLock
from ..rag.diff_detector import DiffDetector
from ..rag.document_cleanup import DocumentCleanupManager
from ..widgets.rag_progress_widget import RAGProgressWidget

logger = logging.getLogger(__name__)


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
        """UIを初期化"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # スクロールエリア
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
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # 1. 情報収集フォルダセクション
        content_layout.addWidget(self._create_folder_section())

        # 2. RAG構築設定セクション
        content_layout.addWidget(self._create_settings_section())

        # 3. プランセクション
        content_layout.addWidget(self._create_plan_section())

        # 4. 実行制御セクション
        content_layout.addWidget(self._create_execution_section())

        # 5. RAG統計セクション
        content_layout.addWidget(self._create_stats_section())

        # 6. データ管理セクション
        content_layout.addWidget(self._create_data_management_section())

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # =========================================================================
    # セクション生成
    # =========================================================================

    def _create_folder_section(self) -> QGroupBox:
        """情報収集フォルダセクション"""
        group = QGroupBox("情報収集フォルダ")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # パス表示 + ボタン
        path_row = QHBoxLayout()
        self.folder_path_label = QLabel(f"パス: {self._folder_path}")
        self.folder_path_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        path_row.addWidget(self.folder_path_label)
        path_row.addStretch()

        open_btn = QPushButton("フォルダを開く")
        open_btn.setStyleSheet(SECONDARY_BTN)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_folder)
        path_row.addWidget(open_btn)
        layout.addLayout(path_row)

        # 選択ボタン行
        select_row = QHBoxLayout()
        select_all_btn = QPushButton("全選択")
        select_all_btn.setStyleSheet(SECONDARY_BTN)
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.setToolTip("全ファイルを選択")
        select_all_btn.clicked.connect(self._select_all_files)
        select_row.addWidget(select_all_btn)

        select_none_btn = QPushButton("全解除")
        select_none_btn.setStyleSheet(SECONDARY_BTN)
        select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_none_btn.setToolTip("全ファイルの選択を解除")
        select_none_btn.clicked.connect(self._deselect_all_files)
        select_row.addWidget(select_none_btn)

        select_changed_btn = QPushButton("差分のみ選択")
        select_changed_btn.setStyleSheet(SECONDARY_BTN)
        select_changed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_changed_btn.setToolTip("新規・変更ありのファイルのみ選択します")
        select_changed_btn.clicked.connect(self._select_changed_only)
        select_row.addWidget(select_changed_btn)

        select_row.addStretch()
        layout.addLayout(select_row)

        # ファイル一覧
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["ファイル名", "サイズ", "更新日", "RAG状態"])
        self.file_tree.setColumnCount(4)
        self.file_tree.setColumnWidth(0, 300)
        self.file_tree.setColumnWidth(1, 80)
        self.file_tree.setColumnWidth(2, 130)
        self.file_tree.setColumnWidth(3, 100)
        self.file_tree.setMinimumHeight(120)
        self.file_tree.setMaximumHeight(200)
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

        # 合計 + ボタン行
        bottom_row = QHBoxLayout()
        self.total_label = QLabel("合計: 0ファイル (0 KB)")
        self.total_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        bottom_row.addWidget(self.total_label)
        bottom_row.addStretch()

        refresh_btn = QPushButton("更新")
        refresh_btn.setStyleSheet(SECONDARY_BTN)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_file_list)
        bottom_row.addWidget(refresh_btn)

        add_btn = QPushButton("ファイル追加")
        add_btn.setStyleSheet(SECONDARY_BTN)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_files)
        bottom_row.addWidget(add_btn)

        layout.addLayout(bottom_row)
        return group

    def _create_settings_section(self) -> QGroupBox:
        """RAG構築設定セクション"""
        group = QGroupBox("RAG構築設定")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # 想定実行時間
        time_row = QHBoxLayout()
        time_label = QLabel("想定実行時間:")
        time_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        time_row.addWidget(time_label)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(RAG_MIN_TIME_LIMIT, RAG_MAX_TIME_LIMIT)
        self.time_spin.setSingleStep(RAG_TIME_STEP)
        self.time_spin.setValue(RAG_DEFAULT_TIME_LIMIT)
        self.time_spin.setSuffix(" 分")
        self.time_spin.setToolTip("RAG構築の想定実行時間（10分刻み、最大24時間）")
        self.time_spin.setStyleSheet(SPINBOX_STYLE)
        time_row.addWidget(self.time_spin)
        time_row.addStretch()
        layout.addLayout(time_row)

        # モデル情報
        models_frame = QFrame()
        models_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        models_layout = QVBoxLayout(models_frame)
        models_layout.setSpacing(4)

        model_info = [
            ("Claudeモデル:", "Claude Opus 4.6 (最高知能)"),
            ("実行LLM:", "command-a:latest (research)"),
            ("品質判定:", "ministral-3:8b (常駐)"),
            ("Embedding:", "qwen3-embedding:4b (常駐)"),
        ]
        for label_text, value_text in model_info:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
            lbl.setFixedWidth(100)
            val = QLabel(value_text)
            val.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            models_layout.addLayout(row)

        layout.addWidget(models_frame)

        # チャンク設定
        chunk_row = QHBoxLayout()
        chunk_label = QLabel("チャンクサイズ:")
        chunk_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        chunk_row.addWidget(chunk_label)

        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(128, 2048)
        self.chunk_size_spin.setSingleStep(RAG_CHUNK_STEP)
        self.chunk_size_spin.setValue(DEFAULT_CHUNK_SIZE)
        self.chunk_size_spin.setSuffix(" トークン")
        self.chunk_size_spin.setToolTip("チャンク分割サイズ（64刻み）")
        self.chunk_size_spin.setStyleSheet(SPINBOX_STYLE)
        chunk_row.addWidget(self.chunk_size_spin)

        overlap_label = QLabel("オーバーラップ:")
        overlap_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        chunk_row.addWidget(overlap_label)

        self.overlap_spin = QSpinBox()
        self.overlap_spin.setRange(0, 256)
        self.overlap_spin.setSingleStep(RAG_OVERLAP_STEP)
        self.overlap_spin.setValue(DEFAULT_CHUNK_OVERLAP)
        self.overlap_spin.setSuffix(" トークン")
        self.overlap_spin.setToolTip("チャンク間の重複トークン数（8刻み）")
        self.overlap_spin.setStyleSheet(SPINBOX_STYLE)
        chunk_row.addWidget(self.overlap_spin)
        chunk_row.addStretch()
        layout.addLayout(chunk_row)

        # 設定保存ボタン
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_settings_btn = QPushButton("設定を保存")
        self.save_settings_btn.setStyleSheet(SECONDARY_BTN)
        self.save_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_settings_btn.setToolTip("RAG構築設定をconfig/app_settings.jsonに保存します")
        self.save_settings_btn.clicked.connect(self._save_rag_settings)
        save_row.addWidget(self.save_settings_btn)
        layout.addLayout(save_row)

        return group

    def _create_plan_section(self) -> QGroupBox:
        """現在のプランセクション"""
        group = QGroupBox("現在のプラン")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # ステータス
        status_row = QHBoxLayout()
        self.plan_status_label = QLabel("ステータス: 未作成")
        self.plan_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        status_row.addWidget(self.plan_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # プラン概要（QTextEdit 読み取り専用・コピー可能）
        summary_label = QLabel("プラン概要:")
        summary_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 11px; font-weight: bold;")
        layout.addWidget(summary_label)

        summary_row = QHBoxLayout()
        self.plan_summary_text = QTextEdit()
        self.plan_summary_text.setReadOnly(True)
        self.plan_summary_text.setMaximumHeight(120)
        self.plan_summary_text.setPlaceholderText("プランを作成すると、ここに概要が表示されます")
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

        self.copy_plan_btn = QPushButton("コピー")
        self.copy_plan_btn.setStyleSheet(SECONDARY_BTN)
        self.copy_plan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_plan_btn.setToolTip("プラン概要をクリップボードにコピー")
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
        self.create_plan_btn = QPushButton("Claudeにプラン作成を依頼")
        self.create_plan_btn.setStyleSheet(PRIMARY_BTN)
        self.create_plan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_plan_btn.clicked.connect(self._create_plan)
        layout.addWidget(self.create_plan_btn)

        return group

    def _create_execution_section(self) -> QGroupBox:
        """実行制御セクション"""
        group = QGroupBox("実行制御")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # ボタン行
        btn_row = QHBoxLayout()

        self.start_btn = QPushButton("RAG構築開始")
        self.start_btn.setStyleSheet(PRIMARY_BTN)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_build)
        self.start_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("中止")
        self.stop_btn.setStyleSheet(DANGER_BTN)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self._stop_build)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.rebuild_btn = QPushButton("再実行")
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

        return group

    def _create_stats_section(self) -> QGroupBox:
        """RAG統計セクション"""
        group = QGroupBox("RAG統計")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QHBoxLayout(group)

        self.stats_labels = {}
        stats = [
            ("total_chunks", "総チャンク数", "0"),
            ("total_embeddings", "総Embedding", "0"),
            ("semantic_nodes", "Semantic Nodes", "0"),
            ("last_build", "最終構築", "なし"),
            ("build_count", "構築回数", "0回"),
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
            layout.addWidget(frame)

        return group

    def _create_data_management_section(self) -> QGroupBox:
        """データ管理セクション"""
        group = QGroupBox("データ管理")
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # 孤児ステータス
        self.orphan_status_label = QLabel("データ健全性を確認中...")
        self.orphan_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.orphan_status_label)

        # 孤児リスト
        self.orphan_tree = QTreeWidget()
        self.orphan_tree.setHeaderLabels(["ファイル名", "チャンク数", "安全レベル"])
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
        self.scan_orphan_btn = QPushButton("孤児スキャン")
        self.scan_orphan_btn.setStyleSheet(SECONDARY_BTN)
        self.scan_orphan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_orphan_btn.setToolTip("削除されたファイルの孤児データを検出します")
        self.scan_orphan_btn.clicked.connect(self._scan_orphans)
        orphan_btn_row.addWidget(self.scan_orphan_btn)

        self.delete_orphan_btn = QPushButton("選択した孤児を削除")
        self.delete_orphan_btn.setStyleSheet(DANGER_BTN)
        self.delete_orphan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_orphan_btn.setToolTip("チェックした孤児データを削除します")
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
        manual_label = QLabel("構築済みドキュメントから不要なものを選択して削除:")
        manual_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(manual_label)

        self.doc_tree = QTreeWidget()
        self.doc_tree.setHeaderLabels(["ドキュメント名", "チャンク数"])
        self.doc_tree.setColumnCount(2)
        self.doc_tree.setColumnWidth(0, 350)
        self.doc_tree.setColumnWidth(1, 80)
        self.doc_tree.setMaximumHeight(120)
        self.doc_tree.setStyleSheet(f"""
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
        layout.addWidget(self.doc_tree)

        delete_doc_btn_row = QHBoxLayout()
        delete_doc_btn_row.addStretch()
        self.delete_doc_btn = QPushButton("選択したドキュメントを削除")
        self.delete_doc_btn.setStyleSheet(DANGER_BTN)
        self.delete_doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_doc_btn.setToolTip("選択したドキュメントのRAGデータを削除（ファイル自体は残ります）")
        self.delete_doc_btn.clicked.connect(self._delete_selected_documents)
        delete_doc_btn_row.addWidget(self.delete_doc_btn)
        layout.addLayout(delete_doc_btn_row)

        # 初期スキャン
        QTimer.singleShot(500, self._scan_orphans)
        QTimer.singleShot(600, self._refresh_doc_list)

        return group

    # =========================================================================
    # シグナル接続
    # =========================================================================

    def _connect_signals(self):
        """内部シグナルを接続"""
        pass  # ビルダーシグナルは_start_build()内で接続

    # =========================================================================
    # アクション
    # =========================================================================

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

    def _add_files(self):
        """ファイル追加ダイアログ"""
        extensions = " ".join(f"*{ext}" for ext in SUPPORTED_DOC_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "ファイルを追加",
            "", f"ドキュメント ({extensions});;全てのファイル (*)"
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
                        self, "ファイルサイズ超過",
                        f"{src_path.name} ({size_mb:.1f}MB) は最大サイズ "
                        f"({MAX_FILE_SIZE_MB}MB) を超えています。スキップします。"
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
                self.statusChanged.emit(f"{added}ファイルを追加しました")

    def _refresh_file_list(self):
        """ファイル一覧を更新し、RAG状態を表示"""
        self.file_tree.clear()
        folder = Path(self._folder_path)
        folder.mkdir(parents=True, exist_ok=True)

        # DiffDetectorで差分検出
        diff_detector = DiffDetector(db_conn_factory=self._get_db_conn)
        diff_result = diff_detector.detect_changes(self._folder_path)

        total_size = 0
        file_count = 0

        # 新規ファイル
        for fi in diff_result.new_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "new", checked=True)
            total_size += fi.size
            file_count += 1

        # 変更ファイル
        for fi in diff_result.modified_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "modified", checked=True)
            total_size += fi.size
            file_count += 1

        # 未変更ファイル
        for fi in diff_result.unchanged_files:
            self._add_file_tree_item(fi.name, fi.size, fi.modified, "unchanged", checked=False)
            total_size += fi.size
            file_count += 1

        # 削除済みファイル（DBにあるがフォルダにない）
        for name in diff_result.deleted_files:
            item = QTreeWidgetItem([name, "-", "-", "削除済み"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setForeground(3, QFont().defaultFamily() and item.foreground(0))
            self.file_tree.addTopLevelItem(item)

        total_str = self._format_size(total_size)
        diff_summary = diff_result.summary
        self.total_label.setText(f"合計: {file_count}ファイル ({total_str})  [{diff_summary}]")

    def _add_file_tree_item(self, name: str, size: int, mtime: float,
                            status: str, checked: bool):
        """ファイル一覧に1行追加"""
        size_str = self._format_size(size)
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

        status_labels = {
            "new": "★新規",
            "modified": "変更あり",
            "unchanged": "構築済み",
        }
        status_label = status_labels.get(status, status)

        item = QTreeWidgetItem([name, size_str, date_str, status_label])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

        # RAG状態に応じた色分け
        if status == "new":
            item.setForeground(3, item.foreground(0))  # デフォルト色
        elif status == "modified":
            item.setForeground(3, item.foreground(0))

        # データとしてステータスを保持
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
            self.stats_labels["build_count"].setText(f"{stats.get('build_count', 0)}回")

            last_build = stats.get("last_build")
            if last_build:
                try:
                    dt = datetime.fromisoformat(last_build)
                    self.stats_labels["last_build"].setText(dt.strftime("%m/%d %H:%M"))
                except Exception:
                    self.stats_labels["last_build"].setText("あり")
            else:
                self.stats_labels["last_build"].setText("なし")
        except Exception as e:
            logger.debug(f"RAG stats refresh error: {e}")

    def _create_plan(self):
        """Claudeにプラン作成を依頼"""
        selected = self._get_selected_files()
        if not selected:
            QMessageBox.information(
                self, "ファイル未選択",
                "プラン作成対象のファイルが選択されていません。\n"
                "チェックボックスでファイルを選択してください。"
            )
            return

        self.create_plan_btn.setEnabled(False)
        self.create_plan_btn.setText("プラン作成中...")
        self.plan_status_label.setText("ステータス: プラン作成中...")
        self.statusChanged.emit("Claude にプラン作成を依頼中...")

        # バックグラウンドで実行（UIをブロックしないためQTimerで遅延）
        QTimer.singleShot(100, self._do_create_plan)

    def _do_create_plan(self):
        """プラン作成の実行"""
        try:
            from ..rag.rag_planner import RAGPlanner
            planner = RAGPlanner()
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
                self.statusChanged.emit("⚠️ デフォルトプランで代替（Claude接続失敗）")
            else:
                self.statusChanged.emit("プラン作成完了")
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            QMessageBox.warning(self, "プラン作成失敗", f"エラー: {str(e)[:300]}")
            self.plan_status_label.setText("ステータス: プラン作成失敗")
            self.statusChanged.emit("プラン作成失敗")
        finally:
            self.create_plan_btn.setEnabled(True)
            self.create_plan_btn.setText("Claudeにプラン作成を依頼")

    def _display_plan(self, plan: dict):
        """プランをUIに表示"""
        analysis = plan.get("analysis", {})
        exec_plan = plan.get("execution_plan", {})
        steps = exec_plan.get("steps", [])

        total_files = analysis.get("total_files", 0)
        total_est = exec_plan.get("total_estimated_minutes", 0)

        if plan.get("fallback"):
            self.plan_status_label.setText("ステータス: デフォルトプラン（Claude接続失敗）")
        else:
            self.plan_status_label.setText("ステータス: プラン作成済み")

        # サマリー表示
        summary = plan.get("summary", "")
        if summary:
            self.plan_summary_text.setPlainText(summary)
        else:
            self.plan_summary_text.setPlainText("（概要情報なし）")
        self.copy_plan_btn.setEnabled(True)

        # プラン詳細
        classifications = analysis.get("file_classifications", [])
        detail_parts = [f"ファイル数: {total_files}  |  ステップ数: {len(steps)}  |  推定時間: {total_est:.1f}分"]
        for cls in classifications[:5]:
            detail_parts.append(
                f"  {cls['file']}: {cls.get('category', '?')} / "
                f"優先度: {cls.get('priority', '?')} / "
                f"推定チャンク: {cls.get('estimated_chunks', '?')}"
            )
        if len(classifications) > 5:
            detail_parts.append(f"  ...他 {len(classifications) - 5} ファイル")
        self.plan_detail_label.setText("\n".join(detail_parts))

        # 進捗ウィジェットにステップ設定
        self.progress_widget.setup_steps(steps)

    def _copy_plan_summary(self):
        """プラン概要をクリップボードにコピー"""
        clipboard = QApplication.clipboard()
        full_text = self._build_full_plan_text()
        clipboard.setText(full_text)
        self.statusChanged.emit("プラン概要をコピーしました")

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
            "【RAG構築プラン概要】",
            f"プラン作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"推定処理時間: {total_est:.1f}分",
            f"対象ファイル: {analysis.get('total_files', 0)}件",
        ]

        if plan.get("fallback"):
            lines.append("※ デフォルトプラン（Claude接続失敗）")

        if summary:
            lines.append(f"\n概要:\n{summary}")

        if classifications:
            lines.append("\nファイル別計画:")
            for i, cls in enumerate(classifications, 1):
                lines.append(
                    f"  {i}. {cls['file']}\n"
                    f"     分類: {cls.get('category', '?')} / "
                    f"優先度: {cls.get('priority', '?')} / "
                    f"推定チャンク: {cls.get('estimated_chunks', '?')}"
                )

        return "\n".join(lines)

    def _start_build(self):
        """RAG構築開始"""
        if not self._current_plan:
            QMessageBox.information(self, "プラン未作成",
                                     "先にプランを作成してください。")
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

        # UIを更新
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.rebuild_btn.setEnabled(False)
        self.create_plan_btn.setEnabled(False)

        # 開始
        self._builder.start()
        self.statusChanged.emit("RAG構築を開始しました")

    def _stop_build(self):
        """RAG構築中止"""
        if self._builder and self._builder.isRunning():
            self._builder.cancel()
            self.stop_btn.setEnabled(False)
            self.statusChanged.emit("RAG構築を中止中...")

    def _rebuild(self):
        """再実行"""
        if self._current_plan:
            self._start_build()
        else:
            self._create_plan()

    def _on_status_changed(self, status: str):
        """ステータス変更"""
        status_text = {
            "running": "RAG構築 実行中...",
            "verifying": "Claude 品質検証中...",
            "completed": "RAG構築 完了",
            "failed": "RAG構築 失敗",
            "cancelled": "RAG構築 中止",
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

    def _on_error(self, step_name: str, error_message: str):
        """エラー発生"""
        logger.error(f"RAG build error at {step_name}: {error_message}")
        self.statusChanged.emit(f"エラー: {step_name}")

    def _on_verification_result(self, result: dict):
        """検証結果受信"""
        verdict = result.get("overall_verdict", "UNKNOWN")
        score = result.get("score", 0)
        logger.info(f"Verification result: {verdict} (score={score})")

    def _on_build_completed(self, success: bool, message: str):
        """構築完了"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.rebuild_btn.setEnabled(True)
        self.create_plan_btn.setEnabled(True)

        self._refresh_rag_stats()

        if success:
            QMessageBox.information(self, "RAG構築完了", message)
        else:
            QMessageBox.warning(self, "RAG構築", message)

    # =========================================================================
    # データ管理
    # =========================================================================

    def _scan_orphans(self):
        """孤児データをスキャン"""
        try:
            orphans = self.cleanup_manager.scan_orphans()
            self.orphan_tree.clear()

            if not orphans:
                self.orphan_status_label.setText("データ健全")
                self.orphan_tree.setVisible(False)
                self.delete_orphan_btn.setEnabled(False)
                return

            self.orphan_status_label.setText(f"孤児データ: {len(orphans)}件検出")
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
            self.orphan_status_label.setText("データ健全性: 不明")

    def _delete_selected_orphans(self):
        """選択された孤児データを削除"""
        selected = []
        for i in range(self.orphan_tree.topLevelItemCount()):
            item = self.orphan_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.text(0))

        if not selected:
            QMessageBox.information(self, "未選択", "削除する孤児データを選択してください。")
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
            QMessageBox.information(self, "未選択", "削除するドキュメントを選択してください。")
            return

        self._confirm_and_delete(selected, is_orphan=False)

    def _confirm_and_delete(self, source_files: list, is_orphan: bool = False):
        """削除前の確認ダイアログ"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("データ削除の確認")

        count = len(source_files)
        if is_orphan:
            msg.setText(f"孤児データ {count}件 を削除します。この操作は元に戻せません。")
        else:
            msg.setText(
                f"選択された {count}件 のドキュメントデータを削除します。\n"
                f"ファイル自体は削除されません（data/information/ 内に残ります）。\n"
                f"この操作は元に戻せません。"
            )

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
                f"削除完了: {result['deleted_chunks']}チャンク, "
                f"{result['deleted_summaries']}要約, "
                f"{result['deleted_links']}リンク"
            )
            self._scan_orphans()
            self._refresh_doc_list()
            self._refresh_rag_stats()

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _save_rag_settings(self):
        """RAG構築設定をapp_settings.jsonに保存"""
        try:
            settings_path = Path("config/app_settings.json")
            settings = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

            settings["rag"] = {
                "time_limit_minutes": self.time_spin.value(),
                "chunk_size": self.chunk_size_spin.value(),
                "overlap": self.overlap_spin.value(),
            }

            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            self.statusChanged.emit("RAG構築設定を保存しました")
            logger.info(f"RAG settings saved: {settings['rag']}")
        except Exception as e:
            logger.error(f"Failed to save RAG settings: {e}")
            QMessageBox.warning(self, "保存失敗", f"設定の保存に失敗しました: {e}")

    def _load_rag_settings(self):
        """app_settings.jsonからRAG構築設定を読み込んでSpinBoxに反映"""
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
