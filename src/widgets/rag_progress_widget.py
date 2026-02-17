"""
Helix AI Studio - RAG Progress Widget (v8.5.0)
RAG構築進捗の詳細表示ウィジェット
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QTreeWidget, QTreeWidgetItem, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from ..utils.styles import COLORS, SECTION_CARD_STYLE, PROGRESS_BAR_STYLE
from ..utils.i18n import t


class RAGProgressWidget(QWidget):
    """RAG構築進捗の詳細表示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 全体進捗バー
        progress_frame = QFrame()
        progress_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setSpacing(6)

        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self.progress_bar.setMinimumHeight(24)
        progress_layout.addWidget(self.progress_bar)

        # 時間情報
        time_row = QHBoxLayout()
        self.elapsed_label = QLabel(t('desktop.widgets.ragProgress.elapsedDefault'))
        self.elapsed_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.remaining_label = QLabel(t('desktop.widgets.ragProgress.remainingDefault'))
        self.remaining_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 11px;")
        time_row.addWidget(self.elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self.remaining_label)
        progress_layout.addLayout(time_row)

        # 現在のステップ
        self.step_label = QLabel(t('desktop.widgets.ragProgress.waitingLabel'))
        self.step_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        progress_layout.addWidget(self.step_label)

        layout.addWidget(progress_frame)

        # ステップ詳細ツリー
        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderLabels(t('desktop.widgets.ragProgress.treeHeaders'))
        self.step_tree.setColumnCount(3)
        self.step_tree.setColumnWidth(0, 250)
        self.step_tree.setColumnWidth(1, 80)
        self.step_tree.setColumnWidth(2, 200)
        self.step_tree.setRootIsDecorated(True)
        self.step_tree.setMinimumHeight(150)
        self.step_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 11px;
            }}
            QTreeWidget::item {{
                padding: 4px;
            }}
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
        layout.addWidget(self.step_tree)

        # ステップ項目を初期化
        self._step_items = {}

    def retranslateUi(self):
        """言語切替時に全ウィジェットのテキストを更新"""
        # Update time labels (only if showing defaults, not active data)
        self.elapsed_label.setText(t('desktop.widgets.ragProgress.elapsedDefault'))
        self.remaining_label.setText(t('desktop.widgets.ragProgress.remainingDefault'))

        # Update step label if in waiting state
        self.step_label.setText(t('desktop.widgets.ragProgress.waitingLabel'))

        # Update tree headers
        self.step_tree.setHeaderLabels(t('desktop.widgets.ragProgress.treeHeaders'))

        # Update waiting status text in step items
        for step_id, item in self._step_items.items():
            current_status = item.text(1)
            # Only update status text for items still in "waiting" state
            # (Running/Completed items should keep their translated text from the signal)
            if current_status in (
                t('desktop.widgets.ragProgress.waitingLabel'),
                # Also match Japanese/English defaults that may still be in the items
                "待機中...", "Waiting...",
            ):
                item.setText(1, t('desktop.widgets.ragProgress.waitingLabel'))

    def setup_steps(self, steps: list):
        """ステップ一覧を設定

        RAGBuilder は Sub-step A-H(step_id 1-8) + plan(0) + verify(9) の
        計10ステップ固定で step_id を発行する。
        プランの steps リスト長とは無関係に step_id 1-8 を登録する。
        """
        from ..rag.rag_builder import SUBSTEP_DEFINITIONS, TOTAL_SUBSTEPS

        self.step_tree.clear()
        self._step_items.clear()

        # Step 0: プラン策定
        item0 = QTreeWidgetItem([t('desktop.widgets.ragProgress.step0Label'), t('desktop.widgets.ragProgress.waitingLabel'), ""])
        self.step_tree.addTopLevelItem(item0)
        self._step_items[0] = item0

        # Sub-step A-H (step_id 1-8)
        # プランの steps からモデル/推定時間を取得(あれば)
        plan_step_map = {}
        for step in steps:
            sid = step.get("step_id", 0)
            plan_step_map[sid] = step

        for sub in SUBSTEP_DEFINITIONS:
            step_id = sub["index"] + 1
            name = sub["name"]
            plan_step = plan_step_map.get(step_id, {})
            model = plan_step.get("model", "")
            est = plan_step.get("estimated_minutes", 0)

            detail = t('desktop.widgets.ragProgress.stepDetailFormat', model=model, est=f"{est:.1f}") if model else ""
            item = QTreeWidgetItem([
                f"Step {step_id}: {name}",
                t('desktop.widgets.ragProgress.waitingLabel'),
                detail,
            ])
            self.step_tree.addTopLevelItem(item)
            self._step_items[step_id] = item

        # Step 9: 検証 (TOTAL_SUBSTEPS + 1 = 9)
        verify_id = TOTAL_SUBSTEPS + 1
        item_verify = QTreeWidgetItem([t('desktop.widgets.ragProgress.stepVerifyLabel', id=verify_id), t('desktop.widgets.ragProgress.waitingLabel'), ""])
        self.step_tree.addTopLevelItem(item_verify)
        self._step_items[verify_id] = item_verify

    @pyqtSlot(int, str)
    def on_step_started(self, step_id: int, step_name: str):
        """ステップ開始"""
        self.step_label.setText(f"{step_name}...")
        if step_id in self._step_items:
            self._step_items[step_id].setText(1, t('desktop.widgets.ragProgress.statusRunning'))
            self._step_items[step_id].setForeground(1,
                self._step_items[step_id].treeWidget().palette().link().color()
                if self._step_items[step_id].treeWidget() else Qt.GlobalColor.cyan)

    @pyqtSlot(int, int, int, str)
    def on_step_progress(self, step_id: int, current: int, total: int, filename: str):
        """ステップ内進捗"""
        if step_id in self._step_items:
            item = self._step_items[step_id]
            item.setText(2, f"{filename} ({current}/{total})")

            # サブアイテムとして各ファイルの進捗を追加/更新
            found = False
            for i in range(item.childCount()):
                child = item.child(i)
                if child.text(0) == filename:
                    child.setText(1, f"{current}/{total}")
                    found = True
                    break
            if not found and filename:
                child = QTreeWidgetItem([filename, f"{current}/{total}", ""])
                item.addChild(child)

    @pyqtSlot(int, str)
    def on_step_completed(self, step_id: int, result_summary: str):
        """ステップ完了"""
        if step_id in self._step_items:
            self._step_items[step_id].setText(1, t('desktop.widgets.ragProgress.statusCompleted'))
            self._step_items[step_id].setText(2, result_summary)

    @pyqtSlot(int, int, str)
    def on_progress_updated(self, current: int, total: int, message: str):
        """全体進捗更新"""
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
        self.step_label.setText(message)

    @pyqtSlot(float, float)
    def on_time_updated(self, elapsed_min: float, remaining_min: float):
        """時間更新"""
        elapsed_str = self._format_time(elapsed_min)
        remaining_str = self._format_time(remaining_min)
        self.elapsed_label.setText(t('desktop.widgets.ragProgress.elapsedLabel', time=elapsed_str))
        self.remaining_label.setText(t('desktop.widgets.ragProgress.remainingLabel', time=remaining_str))

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        self.elapsed_label.setText(t('desktop.widgets.ragProgress.elapsedDefault'))
        self.remaining_label.setText(t('desktop.widgets.ragProgress.remainingDefault'))
        self.step_label.setText(t('desktop.widgets.ragProgress.waitingLabel'))
        self.step_tree.setHeaderLabels(t('desktop.widgets.ragProgress.treeHeaders'))

    def reset(self):
        """リセット"""
        self.progress_bar.setValue(0)
        self.elapsed_label.setText(t('desktop.widgets.ragProgress.elapsedDefault'))
        self.remaining_label.setText(t('desktop.widgets.ragProgress.remainingDefault'))
        self.step_label.setText(t('desktop.widgets.ragProgress.waitingLabel'))
        self.step_tree.clear()
        self._step_items.clear()

    @staticmethod
    def _format_time(minutes: float) -> str:
        """分を mm:ss 形式に変換"""
        if minutes <= 0:
            return "00:00"
        total_sec = int(minutes * 60)
        m, s = divmod(total_sec, 60)
        return f"{m:02d}:{s:02d}"
