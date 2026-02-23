"""
Routing Log Widget - Phase 2.5

Cortex用ルーティング決定ログ閲覧ウィジェット
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QComboBox,
    QGroupBox, QLineEdit, QHeaderView, QMessageBox,
    QDialog, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ..routing.decision_logger import get_routing_decision_logger
from ..utils.i18n import t
from ..widgets.no_scroll_widgets import NoScrollComboBox


# v11.0.0: _NoScrollComboBox → NoScrollComboBox (共通importに統一)
_NoScrollComboBox = NoScrollComboBox


class RoutingLogDetailDialog(QDialog):
    """ルーティング決定の詳細ダイアログ"""

    def __init__(self, log_entry: dict, parent=None):
        super().__init__(parent)
        self.log_entry = log_entry
        self.setWindowTitle(t('desktop.routingLog.detailDialogTitle'))
        self.setMinimumSize(500, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 詳細テキスト
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))

        detail_content = self._format_detail()
        self.detail_text.setText(detail_content)

        layout.addWidget(self.detail_text)

        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _format_detail(self) -> str:
        """詳細を整形"""
        lines = [t('desktop.routingLog.detailHeader') + "\n"]

        fields = [
            ("timestamp", t('desktop.routingLog.fieldTimestamp')),
            ("session_id", t('desktop.routingLog.fieldSessionId')),
            ("phase", t('desktop.routingLog.fieldPhase')),
            ("task_type", t('desktop.routingLog.fieldTaskType')),
            ("selected_backend", t('desktop.routingLog.fieldSelectedBackend')),
            ("user_forced_backend", t('desktop.routingLog.fieldUserForced')),
            ("final_status", t('desktop.routingLog.fieldFinalStatus')),
            ("fallback_attempted", t('desktop.routingLog.fieldFallbackAttempted')),
            ("preset_name", t('desktop.routingLog.fieldPreset')),
            ("prompt_pack", t('desktop.routingLog.fieldPromptPack')),
            ("local_available", t('desktop.routingLog.fieldLocalAvailable')),
            ("duration_ms", t('desktop.routingLog.fieldDurationMs')),
            ("tokens_est", t('desktop.routingLog.fieldTokensEst')),
            ("cost_est", t('desktop.routingLog.fieldCostEst')),
            ("error_type", t('desktop.routingLog.fieldErrorType')),
            ("error_message", t('desktop.routingLog.fieldErrorMessage')),
            ("policy_blocked", t('desktop.routingLog.fieldPolicyBlocked')),
            ("policy_block_reason", t('desktop.routingLog.fieldBlockReason')),
        ]

        for key, label in fields:
            value = self.log_entry.get(key)
            if value is not None:
                if isinstance(value, float):
                    value = f"{value:.4f}"
                lines.append(f"{label}: {value}")

        # 理由コード
        reason_codes = self.log_entry.get("reason_codes", [])
        if reason_codes:
            lines.append(f"\n{t('desktop.routingLog.reasonCodesLabel')}")
            for code in reason_codes:
                lines.append(f"  - {code}")

        # フォールバックチェーン
        fallback_chain = self.log_entry.get("fallback_chain", [])
        if fallback_chain:
            lines.append(f"\n{t('desktop.routingLog.fallbackChainLabel')}")
            lines.append(f"  {' → '.join(fallback_chain)}")

        # 承認スナップショット
        approval_snapshot = self.log_entry.get("approval_snapshot", {})
        if approval_snapshot:
            lines.append(f"\n{t('desktop.routingLog.approvalSnapshotLabel')}")
            for scope, approved in approval_snapshot.items():
                status = "✓" if approved else "✗"
                lines.append(f"  {status} {scope}")

        return "\n".join(lines)


class RoutingLogWidget(QWidget):
    """
    ルーティング決定ログ閲覧ウィジェット

    Features:
    - 直近100件のルーティング決定を表示
    - フィルタ: backend / status
    - 詳細表示（展開 or モーダル）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.decision_logger = get_routing_decision_logger()
        self.current_logs = []
        self._init_ui()
        self._load_logs()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ヘッダー
        header_layout = QHBoxLayout()
        title_label = QLabel(t('desktop.routingLog.title'))
        title_label.setFont(QFont("Yu Gothic UI", 12, QFont.Weight.Bold))
        title_label.setToolTip(t('desktop.routingLog.titleTooltip'))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 更新ボタン
        self.refresh_btn = QPushButton(t('desktop.routingLog.refreshBtn'))
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.setToolTip(t('desktop.routingLog.refreshTooltip'))
        self.refresh_btn.clicked.connect(self._load_logs)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # フィルタセクション
        filter_group = QGroupBox(t('desktop.routingLog.filterGroup'))
        filter_layout = QHBoxLayout(filter_group)

        # Statusフィルタ
        filter_layout.addWidget(QLabel(t('desktop.routingLog.statusLabel')))
        self.status_filter = _NoScrollComboBox()
        self.status_filter.addItems([t('desktop.routingLog.statusAll'), "success", "error", "blocked"])
        self.status_filter.setToolTip(t('desktop.routingLog.statusFilterTooltip'))
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter)

        # Backendフィルタ
        filter_layout.addWidget(QLabel(t('desktop.routingLog.backendLabel')))
        self.backend_filter = _NoScrollComboBox()
        self.backend_filter.addItems([
            t('desktop.routingLog.backendAll'),
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "gemini-3-pro",
            "gemini-3-flash",
            "local"
        ])
        self.backend_filter.setToolTip(t('desktop.routingLog.backendFilterTooltip'))
        self.backend_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.backend_filter)

        # セッションフィルタ
        filter_layout.addWidget(QLabel(t('desktop.routingLog.sessionLabel')))
        self.session_filter = QLineEdit()
        self.session_filter.setPlaceholderText(t('desktop.routingLog.sessionPlaceholder'))
        self.session_filter.setToolTip(t('desktop.routingLog.sessionFilterTooltip'))
        self.session_filter.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.session_filter)

        layout.addWidget(filter_group)

        # テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(t('desktop.routingLog.tableHeaders'))

        # カラム幅調整
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._show_detail)

        layout.addWidget(self.table)

        # ステータスバー
        status_layout = QHBoxLayout()
        self.status_label = QLabel(t('desktop.routingLog.loadingStatus'))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        # 統計表示
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #888;")
        status_layout.addWidget(self.stats_label)

        self.detail_btn = QPushButton(t('desktop.routingLog.detailBtn'))
        self.detail_btn.setEnabled(False)
        self.detail_btn.setToolTip(t('desktop.routingLog.detailTooltip'))
        self.detail_btn.clicked.connect(self._show_detail)
        status_layout.addWidget(self.detail_btn)

        layout.addLayout(status_layout)

        # 選択変更時に詳細ボタンを有効化
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_logs(self, limit: int = 100):
        """ログを読み込み"""
        try:
            self.current_logs = self.decision_logger.read_recent_decisions(limit)
            self._populate_table(self.current_logs)
            self._update_stats()
            self.status_label.setText(t('desktop.routingLog.logCount', count=len(self.current_logs)))
        except Exception as e:
            self.status_label.setText(t('desktop.routingLog.errorStatus', error=e))
            QMessageBox.warning(self, t('desktop.routingLog.loadErrorTitle'), t('desktop.routingLog.loadErrorMsg', error=e))

    def _populate_table(self, logs: list):
        """テーブルにログを表示"""
        self.table.setRowCount(0)

        for log_entry in logs:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # タイムスタンプ
            timestamp = log_entry.get("timestamp", "")
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    timestamp_str = dt.strftime("%m-%d %H:%M:%S")
                except:
                    timestamp_str = timestamp[:19]
            else:
                timestamp_str = ""

            self.table.setItem(row, 0, QTableWidgetItem(timestamp_str))

            # Backend
            backend = log_entry.get("selected_backend", "")
            backend_short = backend.replace("claude-", "").replace("gemini-", "")
            self.table.setItem(row, 1, QTableWidgetItem(backend_short))

            # ステータス
            status = log_entry.get("final_status", "")
            status_item = QTableWidgetItem(status)

            if status == "success":
                status_item.setForeground(QColor("#22c55e"))  # 緑
            elif status == "error":
                status_item.setForeground(QColor("#ef4444"))  # 赤
            elif status == "blocked":
                status_item.setForeground(QColor("#f59e0b"))  # オレンジ

            self.table.setItem(row, 2, status_item)

            # タスク種別
            task_type = log_entry.get("task_type", "")
            self.table.setItem(row, 3, QTableWidgetItem(task_type))

            # フォールバック
            fallback = log_entry.get("fallback_attempted", False)
            fallback_text = "⚠ Yes" if fallback else "-"
            fallback_item = QTableWidgetItem(fallback_text)
            if fallback:
                fallback_item.setForeground(QColor("#f59e0b"))
            self.table.setItem(row, 4, fallback_item)

            # 理由
            reason_codes = log_entry.get("reason_codes", [])
            # presetやuser_forcedを優先表示
            reason_text = ""
            for code in reason_codes:
                if "user_forced" in code or "preset" in code:
                    reason_text = code
                    break
            if not reason_text and reason_codes:
                reason_text = reason_codes[-1]  # 最後の理由コード

            self.table.setItem(row, 5, QTableWidgetItem(reason_text))

    def _apply_filters(self):
        """フィルタを適用"""
        status_filter = self.status_filter.currentText()
        backend_filter = self.backend_filter.currentText()
        session_filter = self.session_filter.text().lower()

        filtered_logs = []

        for log in self.current_logs:
            # ステータスフィルタ
            if status_filter != t('desktop.routingLog.statusAll') and log.get("final_status", "") != status_filter:
                continue

            # Backendフィルタ
            if backend_filter != t('desktop.routingLog.backendAll') and log.get("selected_backend", "") != backend_filter:
                continue

            # セッションフィルタ
            if session_filter and session_filter not in log.get("session_id", "").lower():
                continue

            filtered_logs.append(log)

        self._populate_table(filtered_logs)
        self.status_label.setText(t('desktop.routingLog.filteredLogCount', count=len(filtered_logs)))

    def _update_stats(self):
        """統計情報を更新"""
        stats = self.decision_logger.get_statistics()
        total = stats.get("total", 0)
        success = stats.get("success_count", 0)
        error = stats.get("error_count", 0)
        blocked = stats.get("blocked_count", 0)
        fallback = stats.get("fallback_count", 0)

        if total > 0:
            success_rate = (success / total) * 100
            self.stats_label.setText(
                t('desktop.routingLog.statsFormat',
                  rate=f"{success_rate:.1f}", success=success,
                  error=error, blocked=blocked, fallback=fallback)
            )
        else:
            self.stats_label.setText(t('desktop.routingLog.noStats'))

    def _on_selection_changed(self):
        """選択変更時の処理"""
        self.detail_btn.setEnabled(len(self.table.selectedItems()) > 0)

    def _show_detail(self):
        """詳細を表示"""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return

        # タイムスタンプから対応するログを検索
        timestamp_item = self.table.item(selected_row, 0)
        if not timestamp_item:
            return

        timestamp_str = timestamp_item.text()

        # 対応するログエントリを検索
        log_entry = None
        for log in self.current_logs:
            timestamp = log.get("timestamp", "")
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    if dt.strftime("%m-%d %H:%M:%S") == timestamp_str:
                        log_entry = log
                        break
                except:
                    pass

        if not log_entry:
            # フォールバック: 行番号で取得
            if selected_row < len(self.current_logs):
                log_entry = self.current_logs[selected_row]

        if log_entry:
            dialog = RoutingLogDetailDialog(log_entry, self)
            dialog.exec()
