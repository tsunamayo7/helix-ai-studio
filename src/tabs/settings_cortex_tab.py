"""
Settings / General Tab - 一般設定
v3.9.0: 大幅簡略化（スクリーンキャプチャ、予算管理、Local接続、Gemini関連を削除）
v8.1.0: Claudeモデル設定・MCPサーバー管理をsoloAIから移設、記憶・知識管理セクション追加
v9.6.0: i18n対応（t()による多言語化）+ 言語切替UIセクション追加
v11.0.0 Phase 1-C: MCP管理・カスタムサーバー削除、記憶セクション簡略化
  - MCP管理はcloudAI/localAIタブに移設（Phase 2/5）
  - カスタムサーバー設定はcloudAI/localAIタブに移設
  - RAG有効化・Risk Gate・保存閾値はUI削除（バックエンド常時ON）

一般設定: AI状態確認・記憶知識・表示・自動化・Web UI
"""

import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QFrame, QTextEdit, QScrollArea,
    QSizePolicy, QMessageBox, QApplication, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

try:
    from ..utils.styles import SPINBOX_STYLE, SECTION_CARD_STYLE
except ImportError:
    SPINBOX_STYLE = ""
    SECTION_CARD_STYLE = ""

from ..utils.i18n import t, set_language, get_language
from ..widgets.section_save_button import create_section_save_button
from ..widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox

logger = logging.getLogger(__name__)






class SettingsCortexTab(QWidget):
    """
    一般設定タブ (v11.0.0)

    Features:
    - AI状態確認（Claude CLI / Codex CLI / Ollama）
    - 記憶・知識管理（4層メモリ + Knowledge + Encyclopedia）
    - 表示とテーマ設定
    - 自動化設定
    - Web UIサーバー（ポート・Discord webhook）
    """

    # シグナル
    settingsChanged = pyqtSignal()

    def __init__(self, workflow_state=None, main_window=None, parent=None):
        super().__init__(parent)
        self.workflow_state = workflow_state
        self.main_window = main_window

        # v8.1.0: メモリマネージャー
        self._memory_manager = None
        try:
            from ..memory.memory_manager import HelixMemoryManager
            self._memory_manager = HelixMemoryManager()
            logger.info("HelixMemoryManager initialized for SettingsCortexTab")
        except Exception as e:
            logger.warning(f"Memory manager init failed for SettingsCortexTab: {e}")

        self._init_ui()
        self._connect_signals()
        self._load_settings()

        # WorkflowStateの更新を監視
        if self.main_window:
            self.main_window.workflowStateChanged.connect(self._on_workflow_state_changed)

    def _on_workflow_state_changed(self, workflow_state):
        """ワークフロー状態が変更されたときの処理"""
        pass

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # v10.1.0: 言語切替はメインウィンドウのタブバー右端に移設済み
        # v10.1.0: CLI状態/Ollama/常駐モデル/カスタムサーバーはcloudAI/localAIに移設済み

        # 0. AI 状態確認セクション（v10.1.0: CLI/Ollama一括確認の代替）
        self.ai_status_group = self._create_ai_status_group()
        content_layout.addWidget(self.ai_status_group)

        # v11.0.0: MCP管理はcloudAI/localAIタブに移設（Phase 2/5）

        # 4. 記憶・知識管理 → v11.0.0: RAGタブ設定に移動（非表示化）
        self.memory_group = self._create_memory_knowledge_group()
        self.memory_group.setVisible(False)
        content_layout.addWidget(self.memory_group)

        # 5. 表示とテーマ
        self.display_group = self._create_display_group()
        content_layout.addWidget(self.display_group)

        # 6. 自動化
        self.auto_group = self._create_auto_group()
        content_layout.addWidget(self.auto_group)

        # 7. Web UIサーバー
        self.webui_group = self._create_web_ui_section()
        content_layout.addWidget(self.webui_group)

        # v11.0.0 C-4: 画面下部の単一保存ボタンを廃止（各セクション内に移設済み）

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    # ========================================
    # 0. 言語切替 (v9.6.0)
    # ========================================

    def _create_language_group(self) -> QGroupBox:
        """v9.6.0: 言語切替セクション"""
        group = QGroupBox(t('desktop.settings.language'))
        layout = QHBoxLayout(group)

        self.lang_ja_btn = QPushButton(t('desktop.settings.langJa'))
        self.lang_en_btn = QPushButton(t('desktop.settings.langEn'))

        current_lang = get_language()
        self._update_lang_button_styles(current_lang)

        self.lang_ja_btn.clicked.connect(lambda: self._on_language_changed('ja'))
        self.lang_en_btn.clicked.connect(lambda: self._on_language_changed('en'))

        layout.addWidget(self.lang_ja_btn)
        layout.addWidget(self.lang_en_btn)
        layout.addStretch()

        return group

    def _on_language_changed(self, lang: str):
        """言語変更時の処理"""
        set_language(lang)
        self._update_lang_button_styles(lang)
        # 全UIテキストを更新
        self.retranslateUi()
        # メインウィンドウにも通知
        if self.main_window and hasattr(self.main_window, 'retranslateUi'):
            self.main_window.retranslateUi()

    def _update_lang_button_styles(self, current_lang: str):
        """言語ボタンのスタイルを更新"""
        active_style = "background-color: #059669; color: white; font-weight: bold; padding: 8px 20px; border-radius: 6px; border: none;"
        inactive_style = "background-color: #2d2d2d; color: #888; padding: 8px 20px; border-radius: 6px;"
        self.lang_ja_btn.setStyleSheet(active_style if current_lang == 'ja' else inactive_style)
        self.lang_en_btn.setStyleSheet(active_style if current_lang == 'en' else inactive_style)

    # ========================================
    # 0. AI 状態確認（v10.1.0: CLI/Ollama/Codex一括確認）
    # ========================================

    def _create_ai_status_group(self) -> QGroupBox:
        """v10.1.0: AI接続状態を一括確認するセクション"""
        group = QGroupBox(t('desktop.settings.aiStatusGroup'))
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        status_row = QHBoxLayout()
        self.ai_status_result_label = QLabel("")
        self.ai_status_result_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.ai_status_result_label.setWordWrap(True)
        status_row.addWidget(self.ai_status_result_label)
        status_row.addStretch()

        self.ai_status_check_btn = QPushButton(t('desktop.settings.aiStatusCheckBtn'))
        self.ai_status_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_status_check_btn.clicked.connect(self._check_all_ai_status)
        status_row.addWidget(self.ai_status_check_btn)
        layout.addLayout(status_row)

        # 初期チェック
        QTimer.singleShot(500, self._check_all_ai_status)

        return group

    def _check_all_ai_status(self):
        """Claude CLI / Codex CLI / Ollama を一括確認（v11.0.0: QTimer遅延で確実にUI更新）"""
        # 即座にUI反応（確認中表示）
        self.ai_status_result_label.setText("⏳ " + t('desktop.settings.aiStatusChecking'))
        self.ai_status_result_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self.ai_status_check_btn.setEnabled(False)
        # 50ms遅延で実行（UIスレッドで同期実行 — 各チェックは内部でタイムアウト制御）
        QTimer.singleShot(50, self._do_ai_status_check)

    def _do_ai_status_check(self):
        """AI状態チェック本体"""
        statuses = []

        # Claude CLI
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, msg = check_claude_cli_available()
            statuses.append(f"Claude CLI {'✓' if available else '✗'}")
        except Exception:
            statuses.append("Claude CLI ✗")

        # Codex CLI
        try:
            from ..backends.codex_cli_backend import check_codex_cli_available
            codex_ok, _ = check_codex_cli_available()
            statuses.append(f"Codex CLI {'✓' if codex_ok else '✗'}")
        except Exception:
            statuses.append("Codex CLI ✗")

        # Ollama
        try:
            import requests
            ollama_url = "http://localhost:11434"
            try:
                import json
                from pathlib import Path
                settings_path = Path("config/app_settings.json")
                if settings_path.exists():
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    ollama_url = settings.get("ollama", {}).get("url", ollama_url)
            except Exception:
                pass
            resp = requests.get(f"{ollama_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                model_count = len(resp.json().get("models", []))
                statuses.append(f"Ollama ✓ ({model_count} models)")
            else:
                statuses.append("Ollama ✗")
        except Exception:
            statuses.append("Ollama ✗")

        result_text = " | ".join(statuses)
        self.ai_status_result_label.setText(
            t('desktop.settings.aiStatusResult', statuses=result_text))
        self.ai_status_result_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.ai_status_check_btn.setEnabled(True)

    # ========================================
    # 1. Claude CLI 状態（v10.1.0: cloudAIに移設済み、後方互換のため残存）
    # ========================================

    def _create_cli_status_group(self) -> QGroupBox:
        """v8.1.0: Claude CLI状態表示（説明文削除、ボタンのみ）"""
        group = QGroupBox(t('desktop.settings.cliStatus'))
        layout = QVBoxLayout(group)

        # Claude CLI 状態 + ボタン
        cli_layout = QHBoxLayout()
        self.cli_label = QLabel(t('desktop.settings.cliLabel'))
        cli_layout.addWidget(self.cli_label)
        self.cli_test_btn = QPushButton(t('desktop.settings.cliTest'))
        self.cli_test_btn.setToolTip(t('desktop.settings.cliTestTip'))
        self.cli_test_btn.clicked.connect(self._test_cli_connection)
        cli_layout.addWidget(self.cli_test_btn)
        cli_layout.addStretch()
        layout.addLayout(cli_layout)

        # CLI状態ラベル
        self.cli_status_label = QLabel("")
        self.cli_status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.cli_status_label)

        # 初期状態でCLIをチェック
        self._check_cli_status()

        return group

    def _test_cli_connection(self):
        """CLI接続テスト"""
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, message = check_claude_cli_available()
            if available:
                self.cli_status_label.setText(f"✅ {message}")
                self.cli_status_label.setStyleSheet("color: #4CAF50;")
                QMessageBox.information(self, t('desktop.settings.cliSuccessTitle'),
                                        t('desktop.settings.cliSuccessMsg', message=message))
            else:
                self.cli_status_label.setText("❌ " + t('desktop.settings.cliUnavailable'))
                self.cli_status_label.setStyleSheet("color: #f44336;")
                QMessageBox.warning(self, t('desktop.settings.cliErrorTitle'),
                                    t('desktop.settings.cliErrorMsg', message=message))
        except Exception as e:
            self.cli_status_label.setText(t('desktop.settings.cliError'))
            QMessageBox.warning(self, t('desktop.settings.cliErrorTitle'),
                                t('desktop.settings.cliCheckError', message=str(e)))

    def _check_cli_status(self):
        """CLI状態を確認（v10.0.0: Claude + Ollama + Codex 3ツール対応）"""
        status_parts = []

        # Claude CLI
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, message = check_claude_cli_available()
            if available:
                status_parts.append("Claude CLI ✓")
            else:
                status_parts.append("Claude CLI ✗")
        except Exception:
            status_parts.append("Claude CLI ?")

        # Ollama
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                model_count = len(resp.json().get("models", []))
                status_parts.append(f"Ollama ✓ ({model_count} models)")
            else:
                status_parts.append("Ollama ✗")
        except Exception:
            status_parts.append("Ollama ✗")

        # Codex CLI
        try:
            from ..backends.codex_cli_backend import check_codex_cli_available
            codex_ok, _ = check_codex_cli_available()
            status_parts.append("Codex CLI ✓" if codex_ok else "Codex CLI ✗")
        except Exception:
            status_parts.append("Codex CLI ✗")

        all_ok = all("✓" in p for p in status_parts)
        self.cli_status_label.setText(" | ".join(status_parts))
        if all_ok:
            self.cli_status_label.setStyleSheet("color: #4CAF50;")
        elif any("✓" in p for p in status_parts):
            self.cli_status_label.setStyleSheet("color: #ffa500;")
        else:
            self.cli_status_label.setStyleSheet("color: #ef4444;")

        # ツールチップに詳細インストール手順
        self.cli_status_label.setToolTip(t('desktop.settings.cliInstallInstructions'))

    # ========================================
    # 1.6 v9.8.0: 常駐モデル設定（mixAIから移設）
    # ========================================

    def _create_resident_model_group(self) -> QGroupBox:
        """v9.8.0: 常駐モデル設定（mixAIタブから一般設定へ移設）"""
        group = QGroupBox(t('desktop.settings.residentGroup'))
        group.setStyleSheet(SECTION_CARD_STYLE)
        layout = QVBoxLayout(group)

        # GPU検出情報
        self.gpu_detect_label = QLabel(t('desktop.settings.noGpuDetected'))
        self.gpu_detect_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(self.gpu_detect_label)
        self._detect_gpu_info()

        # 制御AIモデル
        control_row = QHBoxLayout()
        self.resident_control_label = QLabel(t('desktop.settings.residentControlAi'))
        control_row.addWidget(self.resident_control_label)
        self.resident_control_combo = NoScrollComboBox()
        self.resident_control_combo.addItems([
            "ministral-3:8b",
            "ministral-3:14b",
            "qwen3-vl:2b",
        ])
        self.resident_control_combo.setToolTip(t('desktop.settings.residentControlAiTip'))
        control_row.addWidget(self.resident_control_combo)
        self.resident_control_change_btn = QPushButton(t('desktop.settings.residentChangeBtn'))
        self.resident_control_change_btn.setFixedWidth(80)
        self.resident_control_change_btn.clicked.connect(lambda: self.resident_control_combo.showPopup())
        control_row.addWidget(self.resident_control_change_btn)
        layout.addLayout(control_row)

        # Embeddingモデル
        embed_row = QHBoxLayout()
        self.resident_embed_label = QLabel(t('desktop.settings.residentEmbedding'))
        embed_row.addWidget(self.resident_embed_label)
        self.resident_embed_combo = NoScrollComboBox()
        self.resident_embed_combo.addItems([
            "qwen3-embedding:4b",
            "qwen3-embedding:8b",
            "qwen3-embedding:0.6b",
            "bge-m3:latest",
        ])
        self.resident_embed_combo.setToolTip(t('desktop.settings.residentEmbeddingTip'))
        embed_row.addWidget(self.resident_embed_combo)
        self.resident_embed_change_btn = QPushButton(t('desktop.settings.residentChangeBtn'))
        self.resident_embed_change_btn.setFixedWidth(80)
        self.resident_embed_change_btn.clicked.connect(lambda: self.resident_embed_combo.showPopup())
        embed_row.addWidget(self.resident_embed_change_btn)
        layout.addLayout(embed_row)

        # VRAM合計表示
        self.resident_vram_label = QLabel(t('desktop.settings.residentVramTotal', vram="8.5"))
        self.resident_vram_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(self.resident_vram_label)

        # GPU2枚以上の場合: 実行先GPU選択（初期非表示）
        gpu_target_row = QHBoxLayout()
        self.resident_gpu_target_label = QLabel(t('desktop.settings.residentGpuTarget'))
        gpu_target_row.addWidget(self.resident_gpu_target_label)
        self.resident_gpu_target_combo = NoScrollComboBox()
        self.resident_gpu_target_combo.setToolTip(t('desktop.settings.residentGpuTargetTip'))
        gpu_target_row.addWidget(self.resident_gpu_target_combo)
        gpu_target_row.addStretch()
        layout.addLayout(gpu_target_row)
        # GPU1枚の場合は非表示
        self.resident_gpu_target_label.setVisible(False)
        self.resident_gpu_target_combo.setVisible(False)

        # 設定復元
        self._load_resident_settings()

        return group

    def _detect_gpu_info(self):
        """nvidia-smiでGPU情報を動的検出"""
        try:
            import subprocess as _sp
            result = _sp.run(
                ['nvidia-smi', '--query-gpu=index,name,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                gpus = []
                for line in result.stdout.strip().split('\n'):
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        idx, name, vram_mb = parts[0], parts[1], parts[2]
                        vram_gb = round(int(vram_mb) / 1024, 1)
                        gpus.append((idx, name, vram_gb))

                if gpus:
                    gpu_texts = [t('desktop.settings.gpuDetected', name=g[1], vram=g[2]) for g in gpus]
                    self.gpu_detect_label.setText("\n".join(gpu_texts))
                    self.gpu_detect_label.setStyleSheet("color: #00ff88; font-size: 11px;")

                    # GPU2枚以上の場合: 実行先選択を表示
                    if len(gpus) >= 2:
                        self.resident_gpu_target_combo.clear()
                        for g in gpus:
                            self.resident_gpu_target_combo.addItem(f"GPU {g[0]}: {g[1]} ({g[2]}GB)")
                        self.resident_gpu_target_label.setVisible(True)
                        self.resident_gpu_target_combo.setVisible(True)
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")

    def _load_resident_settings(self):
        """常駐モデル設定を読み込み"""
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                resident = config.get("resident_models", {})
                if "control_ai" in resident:
                    idx = self.resident_control_combo.findText(resident["control_ai"])
                    if idx >= 0:
                        self.resident_control_combo.setCurrentIndex(idx)
                if "embedding" in resident:
                    idx = self.resident_embed_combo.findText(resident["embedding"])
                    if idx >= 0:
                        self.resident_embed_combo.setCurrentIndex(idx)
                if "gpu_target" in resident:
                    idx = self.resident_gpu_target_combo.findText(resident["gpu_target"])
                    if idx >= 0:
                        self.resident_gpu_target_combo.setCurrentIndex(idx)

            # v9.8.0: マイグレーション - 旧tool_orchestrator.jsonからの移行
            old_config_paths = [
                Path.home() / ".helix_ai_studio" / "tool_orchestrator.json",
                Path("config/tool_orchestrator.json"),
            ]
            for old_path in old_config_paths:
                if old_path.exists():
                    try:
                        with open(old_path, 'r', encoding='utf-8') as f:
                            old_config = json.load(f)
                        if "image_analyzer_model" in old_config and not config.get("resident_models", {}).get("control_ai"):
                            idx = self.resident_control_combo.findText(old_config["image_analyzer_model"])
                            if idx >= 0:
                                self.resident_control_combo.setCurrentIndex(idx)
                        if "embedding_model" in old_config and not config.get("resident_models", {}).get("embedding"):
                            idx = self.resident_embed_combo.findText(old_config["embedding_model"])
                            if idx >= 0:
                                self.resident_embed_combo.setCurrentIndex(idx)
                    except Exception:
                        pass
                    break
        except Exception as e:
            logger.warning(f"Resident model settings load failed: {e}")

    # v11.0.0: MCP管理はcloudAI/localAIタブに移設（Phase 2/5）

    # ========================================
    # 4. 記憶・知識管理
    # ========================================

    def _create_memory_knowledge_group(self) -> QGroupBox:
        """v8.1.0: 記憶・知識管理セクション"""
        group = QGroupBox(t('desktop.settings.memory'))
        layout = QVBoxLayout(group)

        # 記憶統計
        self.stats_title_label = QLabel(t('desktop.settings.memoryStats'))
        self.stats_title_label.setStyleSheet("font-weight: bold; color: #00d4ff;")
        layout.addWidget(self.stats_title_label)

        self.memory_stats_label = QLabel(t('desktop.settings.memoryStatsDefault'))
        self.memory_stats_label.setToolTip(t('desktop.settings.memoryStatsTip'))
        self.memory_stats_label.setStyleSheet("color: #aaa; padding-left: 10px;")
        layout.addWidget(self.memory_stats_label)

        # v11.0.0: RAG有効化はRAGタブで制御（ここでは常にON）
        # v11.0.0: Memory Risk Gateは常にON（UI削除、バックエンド維持）

        # 記憶の自動保存
        self.memory_auto_save_cb = QCheckBox(t('desktop.settings.memoryAutoSave'))
        self.memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        self.memory_auto_save_cb.setChecked(True)
        layout.addWidget(self.memory_auto_save_cb)

        # Knowledge有効化
        self.knowledge_enabled_cb = QCheckBox(t('desktop.settings.knowledgeEnabled'))
        self.knowledge_enabled_cb.setChecked(True)
        layout.addWidget(self.knowledge_enabled_cb)

        # Knowledge保存先
        path_layout = QHBoxLayout()
        self.knowledge_path_label = QLabel(t('desktop.settings.knowledgePath'))
        path_layout.addWidget(self.knowledge_path_label)
        self.knowledge_path_edit = QLineEdit("data/knowledge")
        path_layout.addWidget(self.knowledge_path_edit)
        layout.addLayout(path_layout)

        # Encyclopedia有効化
        self.encyclopedia_enabled_cb = QCheckBox(t('desktop.settings.encyclopediaEnabled'))
        self.encyclopedia_enabled_cb.setChecked(True)
        layout.addWidget(self.encyclopedia_enabled_cb)

        # ボタン
        btn_layout = QHBoxLayout()
        self.refresh_stats_btn = QPushButton(t('desktop.settings.refreshStats'))
        self.refresh_stats_btn.setToolTip(t('desktop.settings.refreshStatsTip'))
        self.refresh_stats_btn.clicked.connect(self._refresh_memory_stats)
        btn_layout.addWidget(self.refresh_stats_btn)
        self.cleanup_btn = QPushButton(t('desktop.settings.cleanupMemory'))
        self.cleanup_btn.setToolTip(t('desktop.settings.cleanupMemoryTip'))
        self.cleanup_btn.clicked.connect(self._cleanup_old_memories)
        btn_layout.addWidget(self.cleanup_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 初回統計取得
        QTimer.singleShot(500, self._refresh_memory_stats)

        # v11.0.0 C-4: セクション保存ボタン
        layout.addWidget(create_section_save_button(self._save_memory_settings))

        return group

    def _refresh_memory_stats(self):
        """記憶統計を更新"""
        try:
            # 4層メモリ統計
            mem_stats = {"episodes": 0, "semantic_nodes": 0, "procedures": 0}
            if self._memory_manager:
                mem_stats = self._memory_manager.get_stats()

            # Knowledge統計
            knowledge_count = 0
            try:
                from ..knowledge.knowledge_manager import get_knowledge_manager
                km = get_knowledge_manager()
                km_stats = km.get_stats()
                knowledge_count = km_stats.get("count", 0)
            except Exception:
                pass

            # Encyclopedia統計
            encyclopedia_count = 0

            self.memory_stats_label.setText(
                t('desktop.settings.memoryStatsFormat',
                  episodes=mem_stats.get('episodes', 0),
                  semantic=mem_stats.get('semantic_nodes', 0),
                  procedures=mem_stats.get('procedures', 0),
                  knowledge=knowledge_count,
                  encyclopedia=encyclopedia_count)
            )
        except Exception as e:
            self.memory_stats_label.setText(
                t('desktop.settings.memoryStatsError', error=str(e)[:40]))

    def _cleanup_old_memories(self):
        """古い記憶の整理"""
        if self._memory_manager:
            try:
                deleted = self._memory_manager.cleanup_old_memories(days=90)
                QMessageBox.information(
                    self, t('desktop.settings.cleanupDoneTitle'),
                    t('desktop.settings.cleanupDoneMsg', count=deleted)
                )
                self._refresh_memory_stats()
            except Exception as e:
                QMessageBox.warning(self, t('desktop.settings.cleanupErrorTitle'),
                                    t('desktop.settings.cleanupErrorMsg', message=str(e)))
        else:
            QMessageBox.warning(self, t('desktop.settings.cleanupErrorTitle'),
                                t('desktop.settings.cleanupNoManager'))

    # ========================================
    # 5. 表示とテーマ
    # ========================================

    def _create_display_group(self) -> QGroupBox:
        """表示とテーマ設定グループを作成"""
        group = QGroupBox(t('desktop.settings.display'))
        layout = QVBoxLayout(group)

        # ダークモード (v9.7.0: 機能未実装のため非表示)
        self.dark_mode_cb = QCheckBox(t('desktop.settings.darkMode'))
        self.dark_mode_cb.setToolTip(t('desktop.settings.darkModeTip'))
        self.dark_mode_cb.setChecked(True)
        self.dark_mode_cb.setVisible(False)
        layout.addWidget(self.dark_mode_cb)

        # フォントサイズ
        font_layout = QHBoxLayout()
        self.font_size_label = QLabel(t('desktop.settings.fontSize'))
        font_layout.addWidget(self.font_size_label)
        self.font_size_spin = NoScrollSpinBox()
        self.font_size_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.font_size_spin.setStyleSheet(SPINBOX_STYLE)
        self.font_size_spin.setToolTip(t('desktop.settings.fontSizeTip'))
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setFixedWidth(130)
        font_layout.addWidget(self.font_size_spin)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        return group

    # ========================================
    # 6. 自動化
    # ========================================

    def _create_auto_group(self) -> QGroupBox:
        """自動化設定グループを作成"""
        group = QGroupBox(t('desktop.settings.automation'))
        layout = QVBoxLayout(group)

        self.auto_save_cb = QCheckBox(t('desktop.settings.autoSave'))
        self.auto_save_cb.setChecked(True)
        self.auto_save_cb.setToolTip(t('desktop.settings.autoSaveHint'))
        layout.addWidget(self.auto_save_cb)

        self.auto_context_cb = QCheckBox(t('desktop.settings.autoContext'))
        self.auto_context_cb.setChecked(True)
        self.auto_context_cb.setToolTip(t('desktop.settings.autoContextHint'))
        layout.addWidget(self.auto_context_cb)

        return group

    # ========================================
    # 7. Web UIサーバー
    # ========================================

    def _create_web_ui_section(self) -> QGroupBox:
        """Web UIサーバー設定セクション（v9.3.0拡張）"""
        group = QGroupBox(t('desktop.settings.webUI'))
        layout = QVBoxLayout(group)

        # 起動/停止トグルボタン
        toggle_row = QHBoxLayout()
        self.web_ui_toggle = QPushButton(t('desktop.settings.webStart'))
        self.web_ui_toggle.setCheckable(True)
        self.web_ui_toggle.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white;
                padding: 10px 20px; border-radius: 8px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:checked {
                background-color: #dc2626;
            }
        """)
        self.web_ui_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.web_ui_toggle.clicked.connect(self._toggle_web_server)
        toggle_row.addWidget(self.web_ui_toggle)

        self.web_ui_status_label = QLabel(t('desktop.settings.webStopped'))
        self.web_ui_status_label.setStyleSheet("color: #888; font-size: 12px;")
        toggle_row.addWidget(self.web_ui_status_label)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # アクセスURL表示
        self.web_ui_url_label = QLabel("")
        self.web_ui_url_label.setStyleSheet("color: #00d4ff; font-size: 12px;")
        self.web_ui_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.web_ui_url_label)

        # v9.3.0: 自動起動チェックボックス
        auto_row = QHBoxLayout()
        self.web_auto_start_cb = QCheckBox(t('desktop.settings.webAutoStart'))
        self.web_auto_start_cb.setStyleSheet("color: #e5e7eb; font-size: 12px;")
        self.web_auto_start_cb.setChecked(self._load_auto_start_setting())
        self.web_auto_start_cb.stateChanged.connect(self._save_auto_start_setting)
        auto_row.addWidget(self.web_auto_start_cb)
        auto_row.addStretch()
        layout.addLayout(auto_row)

        # ポート番号
        port_row = QHBoxLayout()
        self.port_label = QLabel(t('desktop.settings.webPort'))
        self.port_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        port_row.addWidget(self.port_label)
        self.web_port_spin = NoScrollSpinBox()
        self.web_port_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.web_port_spin.setStyleSheet(SPINBOX_STYLE)
        self.web_port_spin.setRange(1024, 65535)
        self.web_port_spin.setValue(self._load_port_setting())
        self.web_port_spin.setFixedWidth(150)
        port_row.addWidget(self.web_port_spin)
        port_row.addStretch()
        layout.addLayout(port_row)

        # v11.0.0: パスワード設定ボタン
        self.web_password_btn = QPushButton(t('desktop.settings.webPasswordBtn'))
        self.web_password_btn.setStyleSheet("""
            QPushButton { background: #2d3748; color: #e0e0e0; border: 1px solid #4a5568;
                border-radius: 4px; padding: 6px 14px; font-size: 11px; margin-top: 6px; }
            QPushButton:hover { background: #4a5568; }
        """)
        self.web_password_btn.clicked.connect(self._on_set_web_password)
        layout.addWidget(self.web_password_btn)

        # v9.7.2: Discord Webhook送信
        discord_label = QLabel(t('desktop.settings.discordWebhook'))
        discord_label.setStyleSheet("color: #9ca3af; font-size: 11px; margin-top: 8px;")
        layout.addWidget(discord_label)

        discord_row = QHBoxLayout()
        self.discord_webhook_edit = QLineEdit()
        self.discord_webhook_edit.setPlaceholderText(t('desktop.settings.discordWebhookPlaceholder'))
        self.discord_webhook_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 11px;
            }
        """)
        discord_row.addWidget(self.discord_webhook_edit)

        self.discord_send_btn = QPushButton(t('desktop.settings.discordSendBtn'))
        self.discord_send_btn.setToolTip(t('desktop.settings.discordSendBtnTip'))
        self.discord_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
            QPushButton:disabled {
                background-color: #3d3d5c;
                color: #888;
            }
        """)
        self.discord_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discord_send_btn.clicked.connect(self._send_discord_webhook)
        discord_row.addWidget(self.discord_send_btn)
        layout.addLayout(discord_row)

        self.discord_status_label = QLabel("")
        self.discord_status_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        layout.addWidget(self.discord_status_label)

        # Discord Webhook URLを設定から復元
        self._load_discord_webhook_setting()

        # v11.0.0: Discord通知イベント選択
        self.discord_event_label = QLabel(t('desktop.settings.discordNotifyLabel'))
        self.discord_event_label.setStyleSheet("color: #9ca3af; font-size: 11px; margin-top: 6px;")
        layout.addWidget(self.discord_event_label)

        self.discord_notify_start_cb = QCheckBox(t('desktop.settings.discordNotifyStart'))
        self.discord_notify_start_cb.setChecked(True)
        layout.addWidget(self.discord_notify_start_cb)

        self.discord_notify_complete_cb = QCheckBox(t('desktop.settings.discordNotifyComplete'))
        self.discord_notify_complete_cb.setChecked(True)
        layout.addWidget(self.discord_notify_complete_cb)

        self.discord_notify_error_cb = QCheckBox(t('desktop.settings.discordNotifyError'))
        self.discord_notify_error_cb.setChecked(True)
        layout.addWidget(self.discord_notify_error_cb)

        self._load_discord_notify_events()

        # v11.0.0 C-4: セクション保存ボタン
        layout.addWidget(create_section_save_button(self._save_webui_settings))

        return group

    def _toggle_web_server(self):
        """サーバー起動/停止"""
        if self.web_ui_toggle.isChecked():
            try:
                from ..web.launcher import start_server_background
                port = self.web_port_spin.value()
                self._web_server_thread = start_server_background(port=port)
                self.web_ui_toggle.setText(t('desktop.settings.webStop'))
                self.web_ui_status_label.setText(t('desktop.settings.webRunning', port=port))
            except Exception as e:
                self.web_ui_toggle.setChecked(False)
                self.web_ui_toggle.setText(t('desktop.settings.webStart'))
                self.web_ui_status_label.setText(t('desktop.settings.webStartFailed', error=e))
                return

            # Tailscale IP取得（失敗してもサーバー起動は成功扱い）
            ip = "localhost"
            try:
                import subprocess as _sp
                tailscale_cmds = [
                    [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"],
                    ["tailscale", "ip", "-4"],
                ]
                for cmd in tailscale_cmds:
                    try:
                        result = _sp.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0 and result.stdout.strip():
                            ip = result.stdout.strip()
                            break
                    except (FileNotFoundError, _sp.TimeoutExpired):
                        continue
            except Exception:
                pass
            # v10.0.0: IP + マシン名ベースURL両方を表示
            machine_name = ""
            try:
                import socket
                machine_name = socket.gethostname().lower()
            except Exception:
                pass

            url_ip = f"http://{ip}:{port}"
            if machine_name and ip != "localhost":
                url_name = f"http://{machine_name}:{port}"
                self.web_ui_url_label.setText(f"📱 {url_ip}\n📱 {url_name}")
            else:
                self.web_ui_url_label.setText(f"📱 {url_ip}")
        else:
            if hasattr(self, '_web_server_thread') and self._web_server_thread:
                self._web_server_thread.stop()
                self._web_server_thread = None
            self.web_ui_toggle.setText(t('desktop.settings.webStart'))
            self.web_ui_status_label.setText(t('desktop.settings.webStopped'))
            self.web_ui_url_label.setText("")

    def _load_discord_webhook_setting(self):
        """Discord Webhook URLを設定から読み込み"""
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            url = config.get("web_server", {}).get("discord_webhook_url", "")
            self.discord_webhook_edit.setText(url)
        except Exception:
            pass

    def _save_discord_webhook_setting(self):
        """Discord Webhook URLを設定に保存"""
        try:
            config_path = Path("config/config.json")
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            if "web_server" not in config:
                config["web_server"] = {}
            config["web_server"]["discord_webhook_url"] = self.discord_webhook_edit.text().strip()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save Discord webhook URL: {e}")

    def _send_discord_webhook(self):
        """Web UIのURLとQRコードをDiscordに送信"""
        url_text = self.web_ui_url_label.text()
        if not url_text:
            self.discord_status_label.setText(t('desktop.settings.discordNoUrl'))
            self.discord_status_label.setStyleSheet("color: #f59e0b; font-size: 10px;")
            return

        webhook_url = self.discord_webhook_edit.text().strip()
        if not webhook_url:
            self.discord_status_label.setText(t('desktop.settings.discordNoWebhook'))
            self.discord_status_label.setStyleSheet("color: #f59e0b; font-size: 10px;")
            return

        # Webhook URLを保存
        self._save_discord_webhook_setting()

        # URLからアドレス部分を抽出（📱プレフィックス除去）
        server_url = url_text.replace("📱 ", "").strip()

        self.discord_send_btn.setEnabled(False)
        self.discord_status_label.setText(t('desktop.settings.discordSending'))
        self.discord_status_label.setStyleSheet("color: #9ca3af; font-size: 10px;")

        # 別スレッドで送信
        from PyQt6.QtCore import QThread

        class DiscordSendThread(QThread):
            finished = pyqtSignal(bool, str)

            def __init__(self, webhook_url, server_url, parent=None):
                super().__init__(parent)
                self._webhook_url = webhook_url
                self._server_url = server_url

            def run(self):
                try:
                    import io
                    # QRコード生成
                    try:
                        import qrcode
                        qr = qrcode.QRCode(version=1, box_size=10, border=2)
                        qr.add_data(self._server_url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        has_qr = True
                    except ImportError:
                        has_qr = False
                        img_bytes = None

                    import urllib.request
                    import urllib.error

                    boundary = "----HelixDiscordBoundary"
                    body_parts = []

                    # JSON payload part (message content)
                    payload = json.dumps({
                        "embeds": [{
                            "title": "Helix AI Studio - Web UI",
                            "description": f"**Server URL:** {self._server_url}",
                            "color": 0x00d4ff,
                            "footer": {"text": "Helix AI Studio"}
                        }]
                    })
                    body_parts.append(
                        f"--{boundary}\r\n"
                        f"Content-Disposition: form-data; name=\"payload_json\"\r\n"
                        f"Content-Type: application/json\r\n\r\n"
                        f"{payload}\r\n"
                    )

                    # QR code image part
                    if has_qr and img_bytes:
                        body_parts.append(
                            f"--{boundary}\r\n"
                            f"Content-Disposition: form-data; name=\"files[0]\"; filename=\"helix_webui_qr.png\"\r\n"
                            f"Content-Type: image/png\r\n\r\n"
                        )

                    body_end = f"\r\n--{boundary}--\r\n"

                    # Build multipart body
                    body = b""
                    for part in body_parts:
                        body += part.encode('utf-8')

                    if has_qr and img_bytes:
                        body += img_bytes.read()

                    body += body_end.encode('utf-8')

                    req = urllib.request.Request(
                        self._webhook_url,
                        data=body,
                        method='POST',
                        headers={
                            'Content-Type': f'multipart/form-data; boundary={boundary}',
                            'User-Agent': 'Helix-AI-Studio'
                        }
                    )

                    with urllib.request.urlopen(req, timeout=15) as resp:
                        if resp.status in (200, 204):
                            self.finished.emit(True, "")
                        else:
                            self.finished.emit(False, f"HTTP {resp.status}")

                except urllib.error.HTTPError as e:
                    self.finished.emit(False, f"HTTP {e.code}")
                except Exception as e:
                    self.finished.emit(False, str(e))

        self._discord_thread = DiscordSendThread(webhook_url, server_url, self)
        self._discord_thread.finished.connect(self._on_discord_send_finished)
        self._discord_thread.start()

    def _on_discord_send_finished(self, success: bool, error: str):
        """Discord送信完了コールバック"""
        self.discord_send_btn.setEnabled(True)
        if success:
            self.discord_status_label.setText(t('desktop.settings.discordSent'))
            self.discord_status_label.setStyleSheet("color: #22c55e; font-size: 10px;")
        else:
            self.discord_status_label.setText(t('desktop.settings.discordFailed', error=error))
            self.discord_status_label.setStyleSheet("color: #ef4444; font-size: 10px;")

    # v11.0.0: カスタムサーバー管理はcloudAI/localAIタブに移設

    def _load_auto_start_setting(self) -> bool:
        """自動起動設定を読み込み"""
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("web_server", {}).get("auto_start", False)
        except Exception:
            return False

    def _save_auto_start_setting(self, state):
        """自動起動設定を保存"""
        try:
            config_path = Path("config/config.json")
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            if "web_server" not in config:
                config["web_server"] = {}
            config["web_server"]["auto_start"] = bool(state)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Auto-start setting save failed: {e}")

    def _load_port_setting(self) -> int:
        """ポート設定を読み込み"""
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("web_server", {}).get("port", 8500)
        except Exception:
            return 8500

    # ========================================
    # v9.7.0: Ollama接続テスト (一般設定)
    # ========================================

    def _test_ollama_general(self):
        """v9.7.0: Ollama接続テスト (一般設定)"""
        url = self.ollama_conn_url_edit.text().strip()
        if not url:
            self.ollama_conn_status.setText(t('desktop.settings.ollamaNoUrl'))
            self.ollama_conn_status.setStyleSheet("color: #ff6666; font-size: 11px;")
            return
        try:
            import httpx
            resp = httpx.get(f"{url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "?") for m in models[:5]]
                self.ollama_conn_status.setText(t('desktop.settings.ollamaConnected', count=len(models), models=", ".join(model_names)))
                self.ollama_conn_status.setStyleSheet("color: #00ff88; font-size: 11px;")
            else:
                self.ollama_conn_status.setText(t('desktop.settings.ollamaFailed', status=resp.status_code))
                self.ollama_conn_status.setStyleSheet("color: #ff6666; font-size: 11px;")
        except Exception as e:
            self.ollama_conn_status.setText(t('desktop.settings.ollamaError', error=str(e)[:80]))
            self.ollama_conn_status.setStyleSheet("color: #ff6666; font-size: 11px;")

    # ========================================
    # シグナル接続 + 設定保存/読み込み
    # ========================================

    def _connect_signals(self):
        """シグナルを接続
        v11.0.0 C-4: 画面下部の単一保存ボタン廃止。各セクション内の保存ボタンは
        create_section_save_button() 内で接続済み。
        """
        pass

    def _on_save_settings(self):
        """設定保存 (v9.9.2: 差分ダイアログ廃止、即時保存)"""
        import json
        from pathlib import Path

        try:
            config_dir = Path(__file__).parent.parent.parent / "config"
            config_dir.mkdir(exist_ok=True)
            config_path = config_dir / "general_settings.json"

            # --- general_settings.json 用データ（フラットなプリミティブ値のみ） ---
            # NOTE: resident_models は config.json にのみ保存する（nested dict 排除）
            settings_data = {
                "language": get_language(),
                # v11.0.0: MCP設定はcloudAI/localAIタブに移設
                "rag_enabled": True,  # v11.0.0: always ON, controlled from RAG tab
                "memory_auto_save": bool(self.memory_auto_save_cb.isChecked()),
                "risk_gate_enabled": True,  # v11.0.0: always ON in backend
                "knowledge_enabled": bool(self.knowledge_enabled_cb.isChecked()),
                "knowledge_path": str(self.knowledge_path_edit.text()),
                "encyclopedia_enabled": bool(self.encyclopedia_enabled_cb.isChecked()),
                "dark_mode": bool(self.dark_mode_cb.isChecked()),
                "font_size": int(self.font_size_spin.value()),
                "auto_save": bool(self.auto_save_cb.isChecked()),
                "auto_context": bool(self.auto_context_cb.isChecked()),
            }

            # --- 常駐モデル設定（config.json 専用） ---
            resident_models_data = {
                "control_ai": str(self.resident_control_combo.currentText()) if hasattr(self, 'resident_control_combo') else "ministral-3:8b",
                "embedding": str(self.resident_embed_combo.currentText()) if hasattr(self, 'resident_embed_combo') else "qwen3-embedding:4b",
                "gpu_target": str(self.resident_gpu_target_combo.currentText()) if hasattr(self, 'resident_gpu_target_combo') and self.resident_gpu_target_combo.isVisible() else "",
            }

            # 既存データを読み込んでマージ（language等を保持）
            existing = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}
            # 旧バージョンで保存された resident_models を general_settings.json から除去
            existing.pop("resident_models", None)
            existing.update(settings_data)

            # JSON書き込み前に全値がシリアライズ可能か検証
            json.dumps(existing, ensure_ascii=False)

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

            # v8.1.0: app_settings.json にも memory セクションを追加
            try:
                app_settings_path = config_dir / "app_settings.json"
                app_settings = {}
                if app_settings_path.exists():
                    with open(app_settings_path, 'r', encoding='utf-8') as f:
                        app_settings = json.load(f)
                app_settings["memory"] = {
                    "auto_save": bool(self.memory_auto_save_cb.isChecked()),
                    "risk_gate_enabled": True,  # v11.0.0: always ON
                }
                with open(app_settings_path, 'w', encoding='utf-8') as f:
                    json.dump(app_settings, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"app_settings.json update failed: {e}")

            # v9.8.0: Save resident models to config.json (唯一の保存先)
            try:
                config_json_path = config_dir / "config.json"
                config_data = {}
                if config_json_path.exists():
                    with open(config_json_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                config_data["resident_models"] = resident_models_data
                with open(config_json_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"config.json resident model save failed: {e}")

            self.settingsChanged.emit()

            # 視覚フィードバック
            sender = self.sender()
            if sender:
                original_text = sender.text()
                sender.setText(t('desktop.settings.saveSuccess'))
                sender.setEnabled(False)
                QTimer.singleShot(2000, lambda: (
                    sender.setText(original_text), sender.setEnabled(True)))

        except Exception as e:
            logger.error(f"Settings save failed: {e}", exc_info=True)
            QMessageBox.warning(self, t('common.error'),
                                t('desktop.settings.saveError', message=str(e)))

    # ========================================
    # v11.0.0 C-4: セクション別保存メソッド
    # ========================================

    def _save_memory_settings(self):
        """v11.0.0: Save memory settings only"""
        try:
            import json
            from pathlib import Path
            # Save to app_settings.json
            settings_path = Path("config/app_settings.json")
            data = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["memory"] = {
                "auto_save": bool(self.memory_auto_save_cb.isChecked()),
                "risk_gate_enabled": True,
            }
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save memory settings: {e}")

    def _save_webui_settings(self):
        """v11.0.0: Save web UI settings only"""
        try:
            import json
            from pathlib import Path
            config_path = Path("config/config.json")
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            config["web_server"] = config.get("web_server", {})
            config["web_server"]["port"] = self.web_port_spin.value()
            config["web_server"]["auto_start"] = self.web_auto_start_cb.isChecked()
            if hasattr(self, 'discord_webhook_edit'):
                config["web_server"]["discord_webhook_url"] = self.discord_webhook_edit.text().strip()
            # v11.0.0: Discord通知イベント設定を保存
            if hasattr(self, 'discord_notify_start_cb'):
                config["web_server"]["discord_notify_start"] = self.discord_notify_start_cb.isChecked()
                config["web_server"]["discord_notify_complete"] = self.discord_notify_complete_cb.isChecked()
                config["web_server"]["discord_notify_error"] = self.discord_notify_error_cb.isChecked()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save web UI settings: {e}")

    def _load_discord_notify_events(self):
        """v11.0.0: Discord通知イベント設定を読み込み"""
        try:
            import json
            from pathlib import Path
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                ws = config.get("web_server", {})
                self.discord_notify_start_cb.setChecked(ws.get("discord_notify_start", True))
                self.discord_notify_complete_cb.setChecked(ws.get("discord_notify_complete", True))
                self.discord_notify_error_cb.setChecked(ws.get("discord_notify_error", True))
        except Exception:
            pass

    def _on_set_web_password(self):
        """v11.0.0: Web UIパスワード設定ダイアログ"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(t('desktop.settings.webPasswordTitle'))
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(t('desktop.settings.webPasswordNew')))
        pw_input = QLineEdit()
        pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(pw_input)

        layout.addWidget(QLabel(t('desktop.settings.webPasswordConfirm')))
        pw_confirm = QLineEdit()
        pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(pw_confirm)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            pw = pw_input.text()
            confirm = pw_confirm.text()
            if pw != confirm:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, t('common.error'), "Passwords do not match")
                return
            if not pw:
                return
            try:
                import json
                from pathlib import Path
                config_path = Path("config/config.json")
                config = {}
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                config["web_server"] = config.get("web_server", {})
                config["web_server"]["pin_code"] = pw
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "OK", "Password updated successfully")
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", str(e))

    def _load_settings(self):
        """保存済み設定を読み込み"""
        import json
        from pathlib import Path

        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "general_settings.json"
            if not config_path.exists():
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # v11.0.0: MCP設定はcloudAI/localAIタブに移設

            # 記憶・知識
            # v11.0.0: rag_enabled, save_threshold, risk_gate_enabled は常にON（UI削除）
            if "memory_auto_save" in data:
                self.memory_auto_save_cb.setChecked(data["memory_auto_save"])
            if "knowledge_enabled" in data:
                self.knowledge_enabled_cb.setChecked(data["knowledge_enabled"])
            if "knowledge_path" in data:
                self.knowledge_path_edit.setText(data["knowledge_path"])
            if "encyclopedia_enabled" in data:
                self.encyclopedia_enabled_cb.setChecked(data["encyclopedia_enabled"])

            # 表示
            if "dark_mode" in data:
                self.dark_mode_cb.setChecked(data["dark_mode"])
            if "font_size" in data:
                self.font_size_spin.setValue(data["font_size"])

            # 自動化
            if "auto_save" in data:
                self.auto_save_cb.setChecked(data["auto_save"])
            if "auto_context" in data:
                self.auto_context_cb.setChecked(data["auto_context"])

        except Exception as e:
            logger.warning(f"Settings load failed: {e}")

    # ========================================
    # v9.6.0: retranslateUi — 言語変更時に全テキスト更新
    # ========================================

    def retranslateUi(self):
        """言語変更時に全UIテキストを再適用（v10.1.0: 整理後）"""

        # GroupBox titles
        self.ai_status_group.setTitle(t('desktop.settings.aiStatusGroup'))
        self.memory_group.setTitle(t('desktop.settings.memory'))
        self.display_group.setTitle(t('desktop.settings.display'))
        self.auto_group.setTitle(t('desktop.settings.automation'))
        self.webui_group.setTitle(t('desktop.settings.webUI'))

        # AI Status group
        self.ai_status_check_btn.setText(t('desktop.settings.aiStatusCheckBtn'))

        # v10.1.0: 後方互換 - lang_group/cli_groupが存在する場合のみ更新
        if hasattr(self, 'lang_group'):
            self.lang_group.setTitle(t('desktop.settings.language'))
            self._update_lang_button_styles(get_language())
        if hasattr(self, 'cli_group'):
            self.cli_group.setTitle(t('desktop.settings.cliStatus'))
            self.cli_label.setText(t('desktop.settings.cliLabel'))
            self.cli_test_btn.setText(t('desktop.settings.cliTest'))
            self.cli_test_btn.setToolTip(t('desktop.settings.cliTestTip'))
            self._check_cli_status()

        # v11.0.0: MCP retranslate removed (moved to cloudAI/localAI tabs)

        # Memory group
        self.stats_title_label.setText(t('desktop.settings.memoryStats'))
        self.memory_stats_label.setToolTip(t('desktop.settings.memoryStatsTip'))
        # v11.0.0: rag_enabled_cb, threshold_combo, risk_gate_toggle removed
        self.memory_auto_save_cb.setText(t('desktop.settings.memoryAutoSave'))
        self.memory_auto_save_cb.setToolTip(t('desktop.settings.memoryAutoSaveTip'))
        self.knowledge_enabled_cb.setText(t('desktop.settings.knowledgeEnabled'))
        self.knowledge_path_label.setText(t('desktop.settings.knowledgePath'))
        self.encyclopedia_enabled_cb.setText(t('desktop.settings.encyclopediaEnabled'))
        self.refresh_stats_btn.setText(t('desktop.settings.refreshStats'))
        self.refresh_stats_btn.setToolTip(t('desktop.settings.refreshStatsTip'))
        self.cleanup_btn.setText(t('desktop.settings.cleanupMemory'))
        self.cleanup_btn.setToolTip(t('desktop.settings.cleanupMemoryTip'))
        # Refresh memory stats (re-fetch updates labels with current language)
        self._refresh_memory_stats()

        # Display group
        self.dark_mode_cb.setText(t('desktop.settings.darkMode'))
        self.dark_mode_cb.setToolTip(t('desktop.settings.darkModeTip'))
        self.font_size_label.setText(t('desktop.settings.fontSize'))
        self.font_size_spin.setToolTip(t('desktop.settings.fontSizeTip'))

        # Auto group
        self.auto_save_cb.setText(t('desktop.settings.autoSave'))
        self.auto_context_cb.setText(t('desktop.settings.autoContext'))

        # Web UI group
        if not self.web_ui_toggle.isChecked():
            self.web_ui_toggle.setText(t('desktop.settings.webStart'))
            self.web_ui_status_label.setText(t('desktop.settings.webStopped'))
        else:
            self.web_ui_toggle.setText(t('desktop.settings.webStop'))
            # Update the running status text with current port
            port = self.web_port_spin.value() if hasattr(self, 'web_port_spin') else 8500
            self.web_ui_status_label.setText(t('desktop.settings.webRunning', port=port))
        self.web_auto_start_cb.setText(t('desktop.settings.webAutoStart'))
        self.port_label.setText(t('desktop.settings.webPort'))
        # Web UI: パスワード設定ボタン
        if hasattr(self, 'web_password_btn'):
            self.web_password_btn.setText(t('desktop.settings.webPasswordBtn'))

        # v9.7.2: Discord
        self.discord_send_btn.setText(t('desktop.settings.discordSendBtn'))
        self.discord_send_btn.setToolTip(t('desktop.settings.discordSendBtnTip'))
        self.discord_webhook_edit.setPlaceholderText(t('desktop.settings.discordWebhookPlaceholder'))
        if hasattr(self, 'discord_event_label'):
            self.discord_event_label.setText(t('desktop.settings.discordNotifyLabel'))
        if hasattr(self, 'discord_notify_start_cb'):
            self.discord_notify_start_cb.setText(t('desktop.settings.discordNotifyStart'))
        if hasattr(self, 'discord_notify_complete_cb'):
            self.discord_notify_complete_cb.setText(t('desktop.settings.discordNotifyComplete'))
        if hasattr(self, 'discord_notify_error_cb'):
            self.discord_notify_error_cb.setText(t('desktop.settings.discordNotifyError'))

        # v11.0.0: Custom server retranslate removed (moved to cloudAI/localAI tabs)

        # v9.7.0: Ollama connection
        if hasattr(self, 'ollama_conn_group'):
            self.ollama_conn_group.setTitle(t('desktop.settings.ollamaConnGroup'))
            self.ollama_conn_url_label.setText(t('desktop.settings.ollamaUrl'))
            self.ollama_conn_test_btn.setText(t('desktop.settings.ollamaTest'))
            self.ollama_conn_test_btn.setToolTip(t('desktop.settings.ollamaTestTip'))
            # Reset status label to initial text in current language
            self.ollama_conn_status.setText(t('desktop.settings.ollamaStatusInit'))

        # v9.8.0: Resident models
        if hasattr(self, 'resident_group'):
            self.resident_group.setTitle(t('desktop.settings.residentGroup'))
            self.resident_control_label.setText(t('desktop.settings.residentControlAi'))
            self.resident_embed_label.setText(t('desktop.settings.residentEmbedding'))
            self.resident_control_change_btn.setText(t('desktop.settings.residentChangeBtn'))
            self.resident_embed_change_btn.setText(t('desktop.settings.residentChangeBtn'))
            self.resident_gpu_target_label.setText(t('desktop.settings.residentGpuTarget'))
            # Update VRAM total label in current language
            self.resident_vram_label.setText(t('desktop.settings.residentVramTotal', vram="8.5"))
            # Re-detect GPU info so gpuDetected strings use current language
            self._detect_gpu_info()

        # v11.0.0 C-4: 画面下部の単一保存ボタン廃止（各セクション内に移設済み）

    # ========================================
    # 互換性のためのプロパティ/メソッド
    # ========================================

    @property
    def gemini_timeout_spin(self):
        """Gemini関連は削除されたが、互換性のためダミーを返す"""
        class DummySpinBox:
            def value(self):
                return 5
        return DummySpinBox()
