"""
Settings / General Tab - 一般設定
v3.9.0: 大幅簡略化（スクリーンキャプチャ、予算管理、Local接続、Gemini関連を削除）
v8.1.0: Claudeモデル設定・MCPサーバー管理をsoloAIから移設、記憶・知識管理セクション追加

一般設定: モデル・CLI・MCP・記憶知識・表示・自動化
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QFrame, QTextEdit, QScrollArea,
    QSizePolicy, QMessageBox, QApplication, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

try:
    from ..utils.styles import SPINBOX_STYLE
except ImportError:
    SPINBOX_STYLE = ""

logger = logging.getLogger(__name__)


class SettingsCortexTab(QWidget):
    """
    一般設定タブ (v8.1.0)

    Features:
    - Claudeモデル設定（soloAIから移設）
    - Claude CLI 状態
    - MCPサーバー管理（soloAIから移設）
    - 記憶・知識管理（4層メモリ + RAG + Knowledge + Encyclopedia）
    - 表示とテーマ設定
    - 自動化設定
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

        # 1. Claudeモデル設定（soloAIから移設）
        model_group = self._create_model_group()
        content_layout.addWidget(model_group)

        # 2. Claude CLI 状態
        cli_group = self._create_cli_status_group()
        content_layout.addWidget(cli_group)

        # 3. MCPサーバー管理（soloAIから移設）
        mcp_group = self._create_mcp_group()
        content_layout.addWidget(mcp_group)

        # 4. 記憶・知識管理
        memory_group = self._create_memory_knowledge_group()
        content_layout.addWidget(memory_group)

        # 5. 表示とテーマ
        display_group = self._create_display_group()
        content_layout.addWidget(display_group)

        # 6. 自動化
        auto_group = self._create_auto_group()
        content_layout.addWidget(auto_group)

        # 7. 保存ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_settings_btn = QPushButton("🔒 設定を保存")
        self.save_settings_btn.setToolTip("全設定をconfig.json + app_settings.jsonに保存します")
        btn_layout.addWidget(self.save_settings_btn)
        content_layout.addLayout(btn_layout)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    # ========================================
    # 1. Claudeモデル設定（soloAIから移設）
    # ========================================

    def _create_model_group(self) -> QGroupBox:
        """v8.1.0: Claudeモデル設定（soloAIから移設）"""
        group = QGroupBox("🤖 Claudeモデル設定")
        layout = QFormLayout(group)

        # デフォルトモデル
        self.default_model_combo = QComboBox()
        self.default_model_combo.setToolTip("全タブのデフォルトClaudeモデルを選択します")
        try:
            from ..utils.constants import CLAUDE_MODELS
            for model_def in CLAUDE_MODELS:
                self.default_model_combo.addItem(
                    model_def["display_name"], userData=model_def["id"]
                )
        except ImportError:
            self.default_model_combo.addItem("Claude Sonnet 4.5 (推奨)")
        layout.addRow("デフォルトモデル:", self.default_model_combo)

        # タイムアウト
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setStyleSheet(SPINBOX_STYLE)
        self.timeout_spin.setRange(10, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 分")
        self.timeout_spin.setSingleStep(10)
        self.timeout_spin.setToolTip("Claude CLI応答待ちタイムアウト（分）\n10分単位で設定、直接入力で細かい値も可")
        layout.addRow("タイムアウト:", self.timeout_spin)

        return group

    # ========================================
    # 2. Claude CLI 状態
    # ========================================

    def _create_cli_status_group(self) -> QGroupBox:
        """v8.1.0: Claude CLI状態表示（説明文削除、ボタンのみ）"""
        group = QGroupBox("🖥️ Claude CLI 状態")
        layout = QVBoxLayout(group)

        # Claude CLI 状態 + ボタン
        cli_layout = QHBoxLayout()
        cli_layout.addWidget(QLabel("Claude CLI:"))
        self.cli_test_btn = QPushButton("接続確認")
        self.cli_test_btn.setToolTip("Claude Code CLIのインストール・認証状態を確認")
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
                QMessageBox.information(self, "成功", f"Claude CLI が利用可能です。\n{message}")
            else:
                self.cli_status_label.setText("❌ 利用不可")
                self.cli_status_label.setStyleSheet("color: #f44336;")
                QMessageBox.warning(self, "エラー", f"Claude CLI が利用できません:\n{message}")
        except Exception as e:
            self.cli_status_label.setText("❌ エラー")
            QMessageBox.warning(self, "エラー", f"CLIチェック中にエラー:\n{str(e)}")

    def _check_cli_status(self):
        """CLI状態を確認"""
        try:
            from ..backends.claude_cli_backend import check_claude_cli_available
            available, message = check_claude_cli_available()
            if available:
                self.cli_status_label.setText("✅ CLI利用可能")
                self.cli_status_label.setStyleSheet("color: #4CAF50;")
            else:
                self.cli_status_label.setText("⚠️ CLI利用不可")
                self.cli_status_label.setStyleSheet("color: #ffa500;")
        except Exception:
            self.cli_status_label.setText("")

    # ========================================
    # 3. MCPサーバー管理（soloAIから移設）
    # ========================================

    def _create_mcp_group(self) -> QGroupBox:
        """v8.1.0: MCPサーバー管理（soloAIから移設）"""
        group = QGroupBox("🔧 MCPサーバー管理")
        layout = QVBoxLayout(group)

        # チェックボックス形式
        self.mcp_filesystem_cb = QCheckBox("ファイルシステム")
        self.mcp_filesystem_cb.setToolTip("ローカルファイルの読み書きを許可")
        self.mcp_filesystem_cb.setChecked(True)
        layout.addWidget(self.mcp_filesystem_cb)

        self.mcp_git_cb = QCheckBox("Git")
        self.mcp_git_cb.setToolTip("Git操作を許可")
        self.mcp_git_cb.setChecked(True)
        layout.addWidget(self.mcp_git_cb)

        self.mcp_brave_cb = QCheckBox("Brave検索")
        self.mcp_brave_cb.setToolTip("Web検索を許可")
        self.mcp_brave_cb.setChecked(True)
        layout.addWidget(self.mcp_brave_cb)

        # 一括ボタン
        btn_layout = QHBoxLayout()
        enable_all_btn = QPushButton("全て有効")
        enable_all_btn.setToolTip("全MCPサーバーを一括で有効にします")
        enable_all_btn.clicked.connect(lambda: self._set_all_mcp(True))
        btn_layout.addWidget(enable_all_btn)
        disable_all_btn = QPushButton("全て無効")
        disable_all_btn.setToolTip("全MCPサーバーを一括で無効にします")
        disable_all_btn.clicked.connect(lambda: self._set_all_mcp(False))
        btn_layout.addWidget(disable_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    def _set_all_mcp(self, enabled: bool):
        """全MCPサーバーの有効/無効を一括設定"""
        self.mcp_filesystem_cb.setChecked(enabled)
        self.mcp_git_cb.setChecked(enabled)
        self.mcp_brave_cb.setChecked(enabled)

    # ========================================
    # 4. 記憶・知識管理
    # ========================================

    def _create_memory_knowledge_group(self) -> QGroupBox:
        """v8.1.0: 記憶・知識管理セクション"""
        group = QGroupBox("🧠 記憶・知識管理")
        layout = QVBoxLayout(group)

        # 記憶統計
        stats_label = QLabel("📊 記憶統計")
        stats_label.setStyleSheet("font-weight: bold; color: #00d4ff;")
        layout.addWidget(stats_label)

        self.memory_stats_label = QLabel(
            "Episode記憶: 0件  Semantic記憶: 0件\n"
            "手続き記憶: 0件\n"
            "Knowledge: 0件  Encyclopedia: 0件"
        )
        self.memory_stats_label.setToolTip("4層メモリシステムの現在の保存件数\nEpisodic=会話ログ Semantic=事実 Procedural=手順")
        self.memory_stats_label.setStyleSheet("color: #aaa; padding-left: 10px;")
        layout.addWidget(self.memory_stats_label)

        # RAG有効化
        self.rag_enabled_cb = QCheckBox("RAGを有効化")
        self.rag_enabled_cb.setToolTip("RAG（検索拡張生成）を有効化\n過去の記憶を活用した応答を生成します")
        self.rag_enabled_cb.setChecked(True)
        layout.addWidget(self.rag_enabled_cb)

        # 記憶の自動保存
        self.memory_auto_save_cb = QCheckBox("記憶の自動保存")
        self.memory_auto_save_cb.setToolTip("応答後にMemory Risk Gateで記憶品質を判定し\n有用な情報を自動的に4層メモリに保存します")
        self.memory_auto_save_cb.setChecked(True)
        layout.addWidget(self.memory_auto_save_cb)

        # 保存閾値
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("保存閾値:"))
        self.threshold_combo = QComboBox()
        self.threshold_combo.setToolTip("記憶保存の重要度閾値")
        self.threshold_combo.addItems(["低優先度以上", "中優先度以上", "高優先度のみ"])
        self.threshold_combo.setCurrentIndex(1)
        threshold_layout.addWidget(self.threshold_combo)
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)

        # Memory Risk Gate
        self.risk_gate_toggle = QCheckBox("Memory Risk Gate: 有効（ministral-3:8bで品質判定）")
        self.risk_gate_toggle.setToolTip("ministral-3:8bによる記憶品質判定\n重複/矛盾/揮発性をチェックして保存品質を担保")
        self.risk_gate_toggle.setChecked(True)
        layout.addWidget(self.risk_gate_toggle)

        # Knowledge有効化
        self.knowledge_enabled_cb = QCheckBox("Knowledge機能を有効化")
        self.knowledge_enabled_cb.setChecked(True)
        layout.addWidget(self.knowledge_enabled_cb)

        # Knowledge保存先
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Knowledge保存先:"))
        self.knowledge_path_edit = QLineEdit("data/knowledge")
        path_layout.addWidget(self.knowledge_path_edit)
        layout.addLayout(path_layout)

        # Encyclopedia有効化
        self.encyclopedia_enabled_cb = QCheckBox("Encyclopedia機能を有効化")
        self.encyclopedia_enabled_cb.setChecked(True)
        layout.addWidget(self.encyclopedia_enabled_cb)

        # ボタン
        btn_layout = QHBoxLayout()
        refresh_stats_btn = QPushButton("📊 統計を更新")
        refresh_stats_btn.setToolTip("全メモリの最新件数と統計を取得します")
        refresh_stats_btn.clicked.connect(self._refresh_memory_stats)
        btn_layout.addWidget(refresh_stats_btn)
        cleanup_btn = QPushButton("🗑 古い記憶の整理")
        cleanup_btn.setToolTip("使用頻度の低い記憶を整理・圧縮します\n（削除ではなく要約に変換）")
        cleanup_btn.clicked.connect(self._cleanup_old_memories)
        btn_layout.addWidget(cleanup_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 初回統計取得
        QTimer.singleShot(500, self._refresh_memory_stats)

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
                f"Episode記憶: {mem_stats.get('episodes', 0)}件  "
                f"Semantic記憶: {mem_stats.get('semantic_nodes', 0)}件\n"
                f"手続き記憶: {mem_stats.get('procedures', 0)}件\n"
                f"Knowledge: {knowledge_count}件  Encyclopedia: {encyclopedia_count}件"
            )
        except Exception as e:
            self.memory_stats_label.setText(f"統計取得エラー: {str(e)[:40]}")

    def _cleanup_old_memories(self):
        """古い記憶の整理"""
        if self._memory_manager:
            try:
                deleted = self._memory_manager.cleanup_old_memories(days=90)
                QMessageBox.information(
                    self, "整理完了",
                    f"90日以上未使用の記憶を整理しました。\n削除件数: {deleted}件"
                )
                self._refresh_memory_stats()
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"記憶の整理に失敗:\n{str(e)}")
        else:
            QMessageBox.warning(self, "エラー", "メモリマネージャーが初期化されていません。")

    # ========================================
    # 5. 表示とテーマ
    # ========================================

    def _create_display_group(self) -> QGroupBox:
        """表示とテーマ設定グループを作成"""
        group = QGroupBox("表示とテーマ")
        layout = QVBoxLayout(group)

        # ダークモード
        self.dark_mode_cb = QCheckBox("ダークテーマを使用する")
        self.dark_mode_cb.setToolTip("カラーテーマを切り替えます")
        self.dark_mode_cb.setChecked(True)
        layout.addWidget(self.dark_mode_cb)

        # フォントサイズ
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("基本フォントサイズ:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setStyleSheet(SPINBOX_STYLE)
        self.font_size_spin.setToolTip("全タブのフォントサイズを変更します")
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setValue(10)
        font_layout.addWidget(self.font_size_spin)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        return group

    # ========================================
    # 6. 自動化
    # ========================================

    def _create_auto_group(self) -> QGroupBox:
        """自動化設定グループを作成"""
        group = QGroupBox("自動化")
        layout = QVBoxLayout(group)

        self.auto_save_cb = QCheckBox("セッションを自動保存する")
        self.auto_save_cb.setChecked(True)
        layout.addWidget(self.auto_save_cb)

        self.auto_context_cb = QCheckBox("コンテキストを自動読み込みする")
        self.auto_context_cb.setChecked(True)
        layout.addWidget(self.auto_context_cb)

        return group

    # ========================================
    # シグナル接続 + 設定保存/読み込み
    # ========================================

    def _connect_signals(self):
        """シグナルを接続"""
        self.save_settings_btn.clicked.connect(self._on_save_settings)

    def _on_save_settings(self):
        """設定保存 (v8.1.0: モデル/MCP/記憶設定を追加)"""
        import json
        from pathlib import Path

        try:
            config_dir = Path(__file__).parent.parent.parent / "config"
            config_dir.mkdir(exist_ok=True)
            config_path = config_dir / "general_settings.json"

            settings_data = {
                # Claudeモデル設定
                "default_model": self.default_model_combo.currentText(),
                "default_model_id": self.default_model_combo.currentData() or "",
                "timeout_minutes": self.timeout_spin.value(),
                # MCPサーバー
                "mcp_servers": {
                    "filesystem": self.mcp_filesystem_cb.isChecked(),
                    "git": self.mcp_git_cb.isChecked(),
                    "brave-search": self.mcp_brave_cb.isChecked(),
                },
                # 記憶・知識管理
                "rag_enabled": self.rag_enabled_cb.isChecked(),
                "memory_auto_save": self.memory_auto_save_cb.isChecked(),
                "save_threshold": self.threshold_combo.currentText(),
                "risk_gate_enabled": self.risk_gate_toggle.isChecked(),
                "knowledge_enabled": self.knowledge_enabled_cb.isChecked(),
                "knowledge_path": self.knowledge_path_edit.text(),
                "encyclopedia_enabled": self.encyclopedia_enabled_cb.isChecked(),
                # 表示
                "dark_mode": self.dark_mode_cb.isChecked(),
                "font_size": self.font_size_spin.value(),
                # 自動化
                "auto_save": self.auto_save_cb.isChecked(),
                "auto_context": self.auto_context_cb.isChecked(),
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)

            # v8.1.0: app_settings.json にも memory セクションを追加
            try:
                app_settings_path = config_dir / "app_settings.json"
                app_settings = {}
                if app_settings_path.exists():
                    with open(app_settings_path, 'r', encoding='utf-8') as f:
                        app_settings = json.load(f)
                app_settings["memory"] = {
                    "auto_save": self.memory_auto_save_cb.isChecked(),
                    "risk_gate_enabled": self.risk_gate_toggle.isChecked(),
                    "save_threshold": self.threshold_combo.currentText(),
                }
                with open(app_settings_path, 'w', encoding='utf-8') as f:
                    json.dump(app_settings, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"app_settings.json update failed: {e}")

            self.settingsChanged.emit()

            # 視覚フィードバック
            sender = self.sender()
            if sender:
                original_text = sender.text()
                sender.setText("✅ 保存しました")
                sender.setEnabled(False)
                QTimer.singleShot(2000, lambda: (
                    sender.setText(original_text), sender.setEnabled(True)))

        except Exception as e:
            QMessageBox.warning(self, "エラー", f"設定の保存に失敗しました:\n{str(e)}")

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

            # Claudeモデル設定
            if "default_model" in data:
                idx = self.default_model_combo.findText(data["default_model"])
                if idx >= 0:
                    self.default_model_combo.setCurrentIndex(idx)
            if "timeout_minutes" in data:
                self.timeout_spin.setValue(data["timeout_minutes"])

            # MCP
            mcp = data.get("mcp_servers", {})
            if "filesystem" in mcp:
                self.mcp_filesystem_cb.setChecked(mcp["filesystem"])
            if "git" in mcp:
                self.mcp_git_cb.setChecked(mcp["git"])
            if "brave-search" in mcp:
                self.mcp_brave_cb.setChecked(mcp["brave-search"])

            # 記憶・知識
            if "rag_enabled" in data:
                self.rag_enabled_cb.setChecked(data["rag_enabled"])
            if "memory_auto_save" in data:
                self.memory_auto_save_cb.setChecked(data["memory_auto_save"])
            if "save_threshold" in data:
                idx = self.threshold_combo.findText(data["save_threshold"])
                if idx >= 0:
                    self.threshold_combo.setCurrentIndex(idx)
            if "risk_gate_enabled" in data:
                self.risk_gate_toggle.setChecked(data["risk_gate_enabled"])
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
    # 互換性のためのプロパティ/メソッド
    # ========================================

    @property
    def gemini_timeout_spin(self):
        """Gemini関連は削除されたが、互換性のためダミーを返す"""
        class DummySpinBox:
            def value(self):
                return 5
        return DummySpinBox()
