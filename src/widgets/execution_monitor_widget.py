"""
Helix AI Studio - Execution Monitor Widget (v10.1.0)
LLM実行状態のリアルタイムモニター。
各モデルの状態（アクティブ/待機/ストール/完了）を視覚的に表示する。
cloudAI・mixAI 共通ウィジェット。
"""

import time
import logging
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from ..utils.i18n import t
from ..utils.style_helpers import SS

logger = logging.getLogger(__name__)


# 状態定数
_STATE_IDLE = 0       # 未開始 / 完了
_STATE_ACTIVE = 1     # アクティブ（3秒以内に出力あり）
_STATE_WAITING = 2    # 待機中（3〜30秒出力なし）
_STATE_STALLED = 3    # ストール疑い（30秒超出力なし）

_STALL_THRESHOLD_SEC = 30
_WAITING_THRESHOLD_SEC = 3


class _ModelRow(QFrame):
    """1行分のモデル状態表示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._layout = None
        self._icon_label = None
        self._name_label = None
        self._phase_label = None
        self._time_label = None
        self._output_label = None
        self._setup_ui()

    def _setup_ui(self):
        self._layout = __import__('PyQt6.QtWidgets', fromlist=['QHBoxLayout']).QHBoxLayout(self)
        self._layout.setContentsMargins(8, 0, 8, 0)
        self._layout.setSpacing(8)

        self._icon_label = QLabel("\u2b1c")  # ⬜
        self._icon_label.setFixedWidth(20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._name_label = QLabel("")
        self._name_label.setFixedWidth(200)
        self._name_label.setStyleSheet(SS.primary(bold=True))

        self._phase_label = QLabel("")
        self._phase_label.setFixedWidth(120)
        self._phase_label.setStyleSheet(SS.muted())

        self._time_label = QLabel("")
        self._time_label.setFixedWidth(60)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_label.setStyleSheet("color: #94a3b8; font-family: monospace;")

        self._output_label = QLabel("")
        self._output_label.setStyleSheet(SS.dim("11px"))
        self._output_label.setMinimumWidth(100)

        self._layout.addWidget(self._icon_label)
        self._layout.addWidget(self._name_label)
        self._layout.addWidget(self._phase_label)
        self._layout.addWidget(self._time_label)
        self._layout.addWidget(self._output_label, 1)

    def update_display(self, state: int, name: str, label: str,
                       elapsed_sec: float, last_output: str, success: Optional[bool] = None):
        """表示を更新"""
        # 状態アイコン
        if state == _STATE_ACTIVE:
            self._icon_label.setText("\U0001f7e2")  # 🟢
            self.setStyleSheet("background-color: transparent;")
        elif state == _STATE_WAITING:
            self._icon_label.setText("\U0001f7e1")  # 🟡
            self.setStyleSheet("background-color: transparent;")
        elif state == _STATE_STALLED:
            self._icon_label.setText("\U0001f534")  # 🔴
            self.setStyleSheet("background-color: #3a1515;")
        else:  # IDLE
            if success is True:
                self._icon_label.setText("\u2705")  # ✅
            elif success is False:
                self._icon_label.setText("\u274c")  # ❌
            else:
                self._icon_label.setText("\u2b1c")  # ⬜
            self.setStyleSheet("background-color: transparent;")

        self._name_label.setText(name)
        self._phase_label.setText(f"({label})" if label else "")

        # 経過時間
        if elapsed_sec > 0:
            mins = int(elapsed_sec) // 60
            secs = int(elapsed_sec) % 60
            self._time_label.setText(f"{mins}:{secs:02d}")
        else:
            self._time_label.setText("")

        # 最終出力（末尾40文字）
        if last_output:
            truncated = last_output.strip().replace('\n', ' ')[-40:]
            self._output_label.setText(truncated)
        else:
            self._output_label.setText("")


class ExecutionMonitorWidget(QWidget):
    """
    LLM実行状態のリアルタイムモニターウィジェット (v10.1.0)

    使用方法:
        monitor = ExecutionMonitorWidget()
        monitor.start_model("claude-opus-4-6", "Phase 1")
        monitor.update_output("claude-opus-4-6", "計画を作成中...")
        monitor.finish_model("claude-opus-4-6", success=True)
    """

    stallDetected = pyqtSignal(str)  # モデル名を含む警告メッセージ

    def __init__(self, parent=None):
        super().__init__(parent)
        self._models = {}  # name -> {label, start_time, last_output_time, last_output, pid, finished, success}
        self._rows = {}    # name -> _ModelRow
        self._setup_ui()

        # 1秒ごとの更新タイマー
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)

        # 完了後の自動非表示タイマー
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)

        self.setVisible(False)

    def _setup_ui(self):
        self.setMaximumHeight(120)
        self.setStyleSheet("""
            ExecutionMonitorWidget {
                background-color: #0d0d1f;
                border: 1px solid #1e2d42;
                border-radius: 4px;
            }
        """)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(1)

        # ヘッダー
        header = QLabel(t('widget.monitor.title'))
        header.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px;")
        self._main_layout.addWidget(header)
        self._header = header

    # =========================================================================
    # 公開メソッド
    # =========================================================================

    def start_model(self, name: str, label: str = "", pid: int = None):
        """モデルの実行開始を記録"""
        now = time.time()
        self._models[name] = {
            "label": label,
            "start_time": now,
            "last_output_time": now,
            "last_output": "",
            "pid": pid,
            "finished": False,
            "success": None,
        }

        # 行ウィジェットを追加
        if name not in self._rows:
            row = _ModelRow(self)
            self._rows[name] = row
            self._main_layout.addWidget(row)

        self.setVisible(True)
        self._hide_timer.stop()
        if not self._timer.isActive():
            self._timer.start()
        self._refresh()

    def update_output(self, name: str, text: str):
        """モデルの出力を更新"""
        if name not in self._models:
            return
        if text == "__heartbeat__":
            self._models[name]["last_output_time"] = time.time()
            return
        self._models[name]["last_output_time"] = time.time()
        self._models[name]["last_output"] = text

    def finish_model(self, name: str, success: bool = True):
        """モデルの実行完了を記録"""
        if name not in self._models:
            return
        self._models[name]["finished"] = True
        self._models[name]["success"] = success

        # 全モデル完了チェック
        if all(m["finished"] for m in self._models.values()):
            self._hide_timer.start(3000)

        self._refresh()

    def reset(self):
        """全状態をリセット"""
        self._models.clear()
        self._timer.stop()
        self._hide_timer.stop()

        # 行ウィジェットを削除
        for row in self._rows.values():
            self._main_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        self.setVisible(False)

    # =========================================================================
    # 内部メソッド
    # =========================================================================

    def _refresh(self):
        """状態を再計算して表示更新"""
        now = time.time()
        any_active = False

        for name, info in self._models.items():
            if name not in self._rows:
                continue

            row = self._rows[name]

            if info["finished"]:
                state = _STATE_IDLE
                elapsed = (info.get("finish_time", now) - info["start_time"])
                info.setdefault("finish_time", now)
            else:
                any_active = True
                elapsed = now - info["start_time"]
                time_since_output = now - info["last_output_time"]

                if time_since_output <= _WAITING_THRESHOLD_SEC:
                    state = _STATE_ACTIVE
                elif time_since_output <= _STALL_THRESHOLD_SEC:
                    state = _STATE_WAITING
                else:
                    state = _STATE_STALLED
                    # ストール警告
                    stall_sec = int(time_since_output)
                    warn_msg = t('widget.monitor.stallWarn',
                                 name=name, sec=str(stall_sec))
                    self.stallDetected.emit(warn_msg)

            row.update_display(
                state=state,
                name=name,
                label=info["label"],
                elapsed_sec=elapsed,
                last_output=info["last_output"],
                success=info["success"],
            )

        if not any_active and self._models:
            self._timer.stop()

    def _auto_hide(self):
        """完了後に自動非表示"""
        self.setVisible(False)

    def retranslateUi(self):
        """i18n再翻訳"""
        self._header.setText(t('widget.monitor.title'))
