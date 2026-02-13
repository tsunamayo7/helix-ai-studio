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
        self.elapsed_label = QLabel("経過: --:--")
        self.elapsed_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.remaining_label = QLabel("残り推定: --:--")
        self.remaining_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 11px;")
        time_row.addWidget(self.elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self.remaining_label)
        progress_layout.addLayout(time_row)

        # 現在のステップ
        self.step_label = QLabel("待機中...")
        self.step_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        progress_layout.addWidget(self.step_label)

        layout.addWidget(progress_frame)

        # ステップ詳細ツリー
        self.step_tree = QTreeWidget()
        self.step_tree.setHeaderLabels(["ステップ", "ステータス", "詳細"])
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

    def setup_steps(self, steps: list):
        """ステップ一覧を設定"""
        self.step_tree.clear()
        self._step_items.clear()

        # Step 0: プラン策定
        item0 = QTreeWidgetItem(["Step 0: Claude プラン策定", "待機中", ""])
        self.step_tree.addTopLevelItem(item0)
        self._step_items[0] = item0

        for step in steps:
            step_id = step.get("step_id", 0)
            name = step.get("name", f"Step {step_id}")
            model = step.get("model", "")
            est = step.get("estimated_minutes", 0)

            item = QTreeWidgetItem([
                f"Step {step_id}: {name}",
                "待機中",
                f"モデル: {model} / 推定: {est:.1f}分"
            ])
            self.step_tree.addTopLevelItem(item)
            self._step_items[step_id] = item

        # Step N+1: 検証
        verify_id = len(steps) + 1
        item_verify = QTreeWidgetItem([f"Step {verify_id}: Claude 品質検証", "待機中", ""])
        self.step_tree.addTopLevelItem(item_verify)
        self._step_items[verify_id] = item_verify

    @pyqtSlot(int, str)
    def on_step_started(self, step_id: int, step_name: str):
        """ステップ開始"""
        self.step_label.setText(f"{step_name}...")
        if step_id in self._step_items:
            self._step_items[step_id].setText(1, "実行中")
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
            self._step_items[step_id].setText(1, "完了")
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
        self.elapsed_label.setText(f"経過: {elapsed_str}")
        self.remaining_label.setText(f"残り推定: {remaining_str}")

    def reset(self):
        """リセット"""
        self.progress_bar.setValue(0)
        self.elapsed_label.setText("経過: --:--")
        self.remaining_label.setText("残り推定: --:--")
        self.step_label.setText("待機中...")
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
