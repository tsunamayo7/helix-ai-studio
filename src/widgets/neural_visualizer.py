"""
Helix AI Studio - Neural Flow Visualizer (v7.0.0)
3Phase実行パイプラインのノードベース動的可視化ウィジェット

v7.0.0: 旧5Phase→新3Phase化
- Phase 1: Claude計画立案 → Phase 2: ローカルLLM順次実行 → Phase 3: Claude統合
- Phase 2ノードにサブステップ表示（各モデルの実行状態）
- 実行中のノードが「脈打つ（Pulsing）」アニメーション
- 各ノードクリックで中間生成テキスト・推論ログをポップアップ表示

Design: Cyberpunk Minimal - ダークグレー背景、ネオンブルー/グリーンのアクセント
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsScene, QGraphicsView,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsDropShadowEffect, QDialog, QTextEdit,
    QPushButton, QLabel, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QVariantAnimation, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QPainterPath,
    QRadialGradient, QLinearGradient, QTransform
)

from ..utils.i18n import t

logger = logging.getLogger(__name__)


class PhaseState(Enum):
    """Phase実行状態"""
    IDLE = "idle"           # 未実行（グレー）
    RUNNING = "running"     # 実行中（脈打つアニメーション）
    COMPLETED = "completed" # 完了（緑）
    FAILED = "failed"       # 失敗（赤）
    SKIPPED = "skipped"     # スキップ（黄色）


@dataclass
class PhaseData:
    """Phase情報データクラス"""
    phase_id: int
    name: str
    description: str
    state: PhaseState = PhaseState.IDLE
    output: str = ""
    model: str = ""
    execution_time_ms: float = 0
    error: str = ""


class PhaseNode(QGraphicsEllipseItem):
    """
    Phase表現ノード

    - 状態に応じた色変化
    - 実行中は脈打つアニメーション
    - クリックで詳細ポップアップ
    """

    # 状態別カラー定義（Cyberpunk Minimal）
    STATE_COLORS = {
        PhaseState.IDLE: QColor("#3d3d3d"),       # ダークグレー
        PhaseState.RUNNING: QColor("#00d4ff"),    # ネオンシアン
        PhaseState.COMPLETED: QColor("#00ff88"),  # ネオングリーン
        PhaseState.FAILED: QColor("#ff4757"),     # ネオンレッド
        PhaseState.SKIPPED: QColor("#ffa502"),    # ネオンオレンジ
    }

    GLOW_COLORS = {
        PhaseState.IDLE: QColor(61, 61, 61, 50),
        PhaseState.RUNNING: QColor(0, 212, 255, 150),
        PhaseState.COMPLETED: QColor(0, 255, 136, 100),
        PhaseState.FAILED: QColor(255, 71, 87, 100),
        PhaseState.SKIPPED: QColor(255, 165, 2, 80),
    }

    def __init__(self, phase_data: PhaseData, x: float, y: float, radius: float = 45):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.phase_data = phase_data
        self.radius = radius
        self._pulse_scale = 1.0
        self._glow_opacity = 0.5

        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable)

        self._update_appearance()

        # テキストラベル
        self._setup_labels()

    def _setup_labels(self):
        """ノードラベルを設定"""
        # Phase番号
        self.phase_label = QGraphicsTextItem(f"P{self.phase_data.phase_id}", self)
        self.phase_label.setDefaultTextColor(QColor("#ffffff"))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self.phase_label.setFont(font)

        # 中央揃え
        text_rect = self.phase_label.boundingRect()
        self.phase_label.setPos(-text_rect.width() / 2, -text_rect.height() / 2)

        # Phase名（ノード下部）
        self.name_label = QGraphicsTextItem(self.phase_data.name, self)
        self.name_label.setDefaultTextColor(QColor("#b0b0b0"))
        name_font = QFont("Segoe UI", 9)
        self.name_label.setFont(name_font)
        name_rect = self.name_label.boundingRect()
        self.name_label.setPos(-name_rect.width() / 2, self.radius + 5)

    def _update_appearance(self):
        """外観を状態に応じて更新"""
        state = self.phase_data.state
        color = self.STATE_COLORS.get(state, self.STATE_COLORS[PhaseState.IDLE])
        glow_color = self.GLOW_COLORS.get(state, self.GLOW_COLORS[PhaseState.IDLE])

        # グラデーション塗りつぶし
        gradient = QRadialGradient(0, 0, self.radius)
        gradient.setColorAt(0, color.lighter(130))
        gradient.setColorAt(0.7, color)
        gradient.setColorAt(1, color.darker(120))

        self.setBrush(QBrush(gradient))

        # 枠線
        pen = QPen(color.lighter(150), 2)
        if state == PhaseState.RUNNING:
            pen.setWidth(3)
        self.setPen(pen)

        # グロー効果
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(glow_color)
        shadow.setBlurRadius(20 if state == PhaseState.RUNNING else 10)
        shadow.setOffset(0, 0)
        # Note: QGraphicsItem doesn't directly support setGraphicsEffect
        # グロー効果は描画時に処理

    def set_state(self, state: PhaseState):
        """状態を更新"""
        self.phase_data.state = state
        self._update_appearance()

    def set_output(self, output: str, model: str = "", execution_time_ms: float = 0, error: str = ""):
        """出力データを設定"""
        self.phase_data.output = output
        self.phase_data.model = model
        self.phase_data.execution_time_ms = execution_time_ms
        self.phase_data.error = error

    def set_pulse_scale(self, scale: float):
        """パルスアニメーション用スケール設定"""
        self._pulse_scale = scale
        transform = QTransform()
        transform.scale(scale, scale)
        self.setTransform(transform)

    def get_pulse_scale(self) -> float:
        """現在のパルススケールを取得"""
        return self._pulse_scale

    def hoverEnterEvent(self, event):
        """ホバー時の効果"""
        self.setScale(1.1)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """ホバー解除時"""
        self.setScale(1.0)
        super().hoverLeaveEvent(event)


class ConnectionLine(QGraphicsPathItem):
    """
    ノード間接続線

    - ベジェ曲線で滑らかな接続
    - 状態に応じた色・アニメーション
    """

    def __init__(self, start_node: PhaseNode, end_node: PhaseNode):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self._flow_offset = 0.0

        self._update_path()
        self._update_appearance()

    def _update_path(self):
        """接続パスを更新"""
        start_pos = self.start_node.pos()
        end_pos = self.end_node.pos()

        # 開始/終了点をノード端に調整
        start_radius = self.start_node.radius
        end_radius = self.end_node.radius

        # 方向ベクトル計算
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        length = (dx**2 + dy**2)**0.5

        if length > 0:
            nx, ny = dx / length, dy / length
        else:
            nx, ny = 1, 0

        # 調整された開始/終了点
        start_x = start_pos.x() + nx * start_radius
        start_y = start_pos.y() + ny * start_radius
        end_x = end_pos.x() - nx * end_radius
        end_y = end_pos.y() - ny * end_radius

        # ベジェ曲線パス
        path = QPainterPath()
        path.moveTo(start_x, start_y)

        # 制御点（曲線の強さ）
        ctrl_offset = length * 0.3
        ctrl1_x = start_x + nx * ctrl_offset
        ctrl1_y = start_y + ny * ctrl_offset
        ctrl2_x = end_x - nx * ctrl_offset
        ctrl2_y = end_y - ny * ctrl_offset

        path.cubicTo(ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, end_x, end_y)

        self.setPath(path)

    def _update_appearance(self, active: bool = False):
        """外観を更新"""
        if active:
            # 活性化時（データフロー中）
            pen = QPen(QColor("#00d4ff"), 3)
            pen.setStyle(Qt.PenStyle.SolidLine)
        else:
            # 非活性時
            pen = QPen(QColor("#4a4a4a"), 2)
            pen.setStyle(Qt.PenStyle.DashLine)

        self.setPen(pen)

    def set_active(self, active: bool):
        """接続線のアクティブ状態を設定"""
        self._update_appearance(active)


class PhaseDetailDialog(QDialog):
    """
    Phase詳細ポップアップダイアログ

    - 中間生成テキスト表示
    - 推論ログ表示
    - 使用モデル・実行時間
    """

    def __init__(self, phase_data: PhaseData, parent=None):
        super().__init__(parent)
        self.phase_data = phase_data
        self.setWindowTitle(f"Phase {phase_data.phase_id}: {phase_data.name}")
        self.setMinimumSize(600, 400)
        self.setModal(False)

        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー
        header = QFrame()
        header.setStyleSheet("background-color: #2d2d2d; border-radius: 8px; padding: 12px;")
        header_layout = QHBoxLayout(header)

        # 状態インジケーター
        state_color = PhaseNode.STATE_COLORS.get(
            self.phase_data.state,
            PhaseNode.STATE_COLORS[PhaseState.IDLE]
        )
        state_indicator = QLabel("●")
        state_indicator.setStyleSheet(f"color: {state_color.name()}; font-size: 20px;")
        header_layout.addWidget(state_indicator)

        # Phase情報
        info_layout = QVBoxLayout()
        title = QLabel(f"Phase {self.phase_data.phase_id}: {self.phase_data.name}")
        title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        info_layout.addWidget(title)

        desc = QLabel(self.phase_data.description)
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        info_layout.addWidget(desc)
        header_layout.addLayout(info_layout)
        header_layout.addStretch()

        layout.addWidget(header)

        # メタ情報
        meta_frame = QFrame()
        meta_layout = QHBoxLayout(meta_frame)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        if self.phase_data.model:
            model_label = QLabel(f"🤖 {self.phase_data.model}")
            model_label.setStyleSheet("color: #00d4ff;")
            meta_layout.addWidget(model_label)

        if self.phase_data.execution_time_ms > 0:
            time_label = QLabel(f"⏱️ {self.phase_data.execution_time_ms:.0f}ms")
            time_label.setStyleSheet("color: #00ff88;")
            meta_layout.addWidget(time_label)

        state_text = self.phase_data.state.value.upper()
        state_label = QLabel(f"📊 {state_text}")
        state_label.setStyleSheet(f"color: {state_color.name()};")
        meta_layout.addWidget(state_label)

        meta_layout.addStretch()
        layout.addWidget(meta_frame)

        # 出力テキスト
        output_label = QLabel(t('desktop.widgets.neuralViz.outputLabel'))
        output_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(output_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setText(self.phase_data.output or t('desktop.widgets.neuralViz.noOutput'))
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px;
                font-family: "Consolas", "Cascadia Code", monospace;
            }
        """)
        layout.addWidget(self.output_text)

        # エラー表示（あれば）
        if self.phase_data.error:
            error_label = QLabel(t('desktop.widgets.neuralViz.errorLabel'))
            error_label.setStyleSheet("color: #ff4757; font-weight: bold;")
            layout.addWidget(error_label)

            error_text = QTextEdit()
            error_text.setReadOnly(True)
            error_text.setText(self.phase_data.error)
            error_text.setMaximumHeight(100)
            error_text.setStyleSheet("""
                QTextEdit {
                    background-color: #2d1f1f;
                    color: #ff6b6b;
                    border: 1px solid #ff4757;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            layout.addWidget(error_text)

        # 閉じるボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(t('desktop.widgets.neuralViz.closeBtn'))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _apply_style(self):
        """スタイルを適用"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #00d4ff;
            }
        """)


class NeuralFlowVisualizer(QWidget):
    """
    Neural Flow Visualizer メインウィジェット v7.0.0

    3Phase実行パイプラインをノードベースで可視化:
    - Phase 1: Claude計画立案（ツール使用あり）
    - Phase 2: ローカルLLM順次実行
    - Phase 3: Claude比較統合

    Signals:
        phaseClicked(int): Phaseノードがクリックされた時
        phaseStateChanged(int, str): Phase状態が変更された時
    """

    phaseClicked = pyqtSignal(int)
    phaseStateChanged = pyqtSignal(int, str)

    @staticmethod
    def _get_phase_definitions() -> List[PhaseData]:
        """Return phase definitions with current locale strings."""
        return [
            PhaseData(1, t('desktop.widgets.neuralViz.phase1Name'), t('desktop.widgets.neuralViz.phase1Desc')),
            PhaseData(2, t('desktop.widgets.neuralViz.phase2Name'), t('desktop.widgets.neuralViz.phase2Desc')),
            PhaseData(3, t('desktop.widgets.neuralViz.phase3Name'), t('desktop.widgets.neuralViz.phase3Desc')),
        ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        defs = self._get_phase_definitions()
        self._phases: List[PhaseData] = [
            PhaseData(p.phase_id, p.name, p.description) for p in defs
        ]
        self._nodes: Dict[int, PhaseNode] = {}
        self._connections: List[ConnectionLine] = []
        self._pulse_timers: Dict[int, QTimer] = {}
        self._pulse_states: Dict[int, float] = {}

        self._init_ui()
        self._create_nodes()
        self._create_connections()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # GraphicsView
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#1a1a1a")))

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setStyleSheet("""
            QGraphicsView {
                background-color: #1a1a1a;
                border: 1px solid #2d2d2d;
                border-radius: 8px;
            }
        """)

        layout.addWidget(self.view)

    def _create_nodes(self):
        """Phaseノードを作成"""
        # 3つのノードを横一列に配置
        spacing = 200
        start_x = 120
        y = 80

        for i, phase in enumerate(self._phases):
            x = start_x + i * spacing
            node = PhaseNode(phase, x, y)
            self._nodes[phase.phase_id] = node
            self.scene.addItem(node)

            # クリックイベント
            # Note: QGraphicsItem doesn't have clicked signal,
            # we'll handle this in mousePressEvent override

        # シーンサイズ調整
        self.scene.setSceneRect(0, 0, start_x + len(self._phases) * spacing + 50, 180)

    def _create_connections(self):
        """ノード間接続線を作成"""
        phase_ids = sorted(self._nodes.keys())

        for i in range(len(phase_ids) - 1):
            start_node = self._nodes[phase_ids[i]]
            end_node = self._nodes[phase_ids[i + 1]]

            connection = ConnectionLine(start_node, end_node)
            self._connections.append(connection)
            self.scene.addItem(connection)

            # ノードより下に表示
            connection.setZValue(-1)

    def set_phase_state(self, phase_id: int, state: PhaseState):
        """Phase状態を設定"""
        if phase_id not in self._nodes:
            return

        node = self._nodes[phase_id]
        old_state = node.phase_data.state
        node.set_state(state)

        # 接続線の更新
        self._update_connection_states()

        # パルスアニメーション制御
        if state == PhaseState.RUNNING:
            self._start_pulse_animation(phase_id)
        else:
            self._stop_pulse_animation(phase_id)

        # シグナル発火
        if old_state != state:
            self.phaseStateChanged.emit(phase_id, state.value)

    def set_phase_output(self, phase_id: int, output: str, model: str = "",
                         execution_time_ms: float = 0, error: str = ""):
        """Phase出力を設定"""
        if phase_id not in self._nodes:
            return

        node = self._nodes[phase_id]
        node.set_output(output, model, execution_time_ms, error)

    def _update_connection_states(self):
        """接続線の状態を更新"""
        phase_ids = sorted(self._nodes.keys())

        for i, connection in enumerate(self._connections):
            start_id = phase_ids[i]
            start_state = self._nodes[start_id].phase_data.state

            # 完了したPhaseからの接続線をアクティブに
            active = start_state == PhaseState.COMPLETED
            connection.set_active(active)

    def _start_pulse_animation(self, phase_id: int):
        """パルスアニメーション開始"""
        if phase_id in self._pulse_timers:
            return

        node = self._nodes[phase_id]
        self._pulse_states[phase_id] = 1.0

        timer = QTimer()
        timer.setInterval(50)  # 20 FPS

        def pulse():
            current = self._pulse_states.get(phase_id, 1.0)
            # サイン波でスケール変動 (0.95 ~ 1.05)
            import math
            t = timer.property("t") or 0
            t += 0.15
            timer.setProperty("t", t)
            scale = 1.0 + 0.05 * math.sin(t)
            node.set_pulse_scale(scale)

        timer.timeout.connect(pulse)
        timer.start()
        self._pulse_timers[phase_id] = timer

    def _stop_pulse_animation(self, phase_id: int):
        """パルスアニメーション停止"""
        if phase_id not in self._pulse_timers:
            return

        timer = self._pulse_timers.pop(phase_id)
        timer.stop()

        if phase_id in self._nodes:
            self._nodes[phase_id].set_pulse_scale(1.0)

    def reset_all(self):
        """全Phaseをリセット"""
        for phase_id in self._nodes:
            self.set_phase_state(phase_id, PhaseState.IDLE)
            self.set_phase_output(phase_id, "", "", 0, "")

    def show_phase_detail(self, phase_id: int):
        """Phase詳細ダイアログを表示"""
        if phase_id not in self._nodes:
            return

        phase_data = self._nodes[phase_id].phase_data
        dialog = PhaseDetailDialog(phase_data, self)
        dialog.show()

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        defs = self._get_phase_definitions()
        for d in defs:
            if d.phase_id in self._nodes:
                node = self._nodes[d.phase_id]
                node.phase_data.name = d.name
                node.phase_data.description = d.description
                # Update the visible name label below the node
                node.name_label.setPlainText(d.name)
                name_rect = node.name_label.boundingRect()
                node.name_label.setPos(-name_rect.width() / 2, node.radius + 5)

    def resizeEvent(self, event):
        """リサイズイベント"""
        super().resizeEvent(event)
        # ビューをシーンにフィット
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event):
        """マウスプレスイベント - ノードクリック検出"""
        super().mousePressEvent(event)

        # シーン座標に変換
        scene_pos = self.view.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, QTransform())

        if isinstance(item, PhaseNode):
            phase_id = item.phase_data.phase_id
            self.phaseClicked.emit(phase_id)
            self.show_phase_detail(phase_id)
        elif isinstance(item, QGraphicsTextItem):
            # テキストラベルの親ノードをチェック
            parent = item.parentItem()
            if isinstance(parent, PhaseNode):
                phase_id = parent.phase_data.phase_id
                self.phaseClicked.emit(phase_id)
                self.show_phase_detail(phase_id)


class NeuralFlowCompactWidget(QWidget):
    """
    コンパクト版Neural Flow表示 v7.0.0

    mixAIタブのログエリア上部に配置する軽量版
    3Phase: P1:Claude計画 → P2:ローカルLLM → P3:Claude統合
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)

        self._phase_states: Dict[int, PhaseState] = {i: PhaseState.IDLE for i in range(1, 4)}
        self._substep_labels: Dict[str, QLabel] = {}  # Phase 2サブステップ用

        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        self._phase_labels: Dict[int, QLabel] = {}

        phase_names = [t('desktop.widgets.neuralViz.p1Compact'), t('desktop.widgets.neuralViz.p2Compact'), t('desktop.widgets.neuralViz.p3Compact')]

        for i, name in enumerate(phase_names, 1):
            # Phase indicator
            label = QLabel(f"● {name}")
            label.setStyleSheet(self._get_label_style(PhaseState.IDLE))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._phase_labels[i] = label
            layout.addWidget(label)

            # Arrow (except last)
            if i < 3:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #4a4a4a; font-size: 14px;")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(arrow)

    def _get_label_style(self, state: PhaseState) -> str:
        """状態に応じたラベルスタイルを取得"""
        colors = {
            PhaseState.IDLE: "#6b6b6b",
            PhaseState.RUNNING: "#00d4ff",
            PhaseState.COMPLETED: "#00ff88",
            PhaseState.FAILED: "#ff4757",
            PhaseState.SKIPPED: "#ffa502",
        }
        color = colors.get(state, colors[PhaseState.IDLE])

        font_weight = "bold" if state == PhaseState.RUNNING else "normal"

        return f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                font-weight: {font_weight};
                padding: 4px 8px;
                background-color: {'#2d2d2d' if state != PhaseState.IDLE else 'transparent'};
                border-radius: 4px;
            }}
        """

    def set_phase_state(self, phase_id: int, state: PhaseState):
        """Phase状態を設定"""
        if phase_id not in self._phase_labels:
            return

        self._phase_states[phase_id] = state
        self._phase_labels[phase_id].setStyleSheet(self._get_label_style(state))

    def retranslateUi(self):
        """Update all translatable text (called on language switch)."""
        phase_names = [
            t('desktop.widgets.neuralViz.p1Compact'),
            t('desktop.widgets.neuralViz.p2Compact'),
            t('desktop.widgets.neuralViz.p3Compact'),
        ]
        for i, name in enumerate(phase_names, 1):
            if i in self._phase_labels:
                self._phase_labels[i].setText(f"● {name}")

    def reset_all(self):
        """全Phaseをリセット"""
        for phase_id in self._phase_labels:
            self.set_phase_state(phase_id, PhaseState.IDLE)
