"""
Helix AI Studio - VRAM Budget Simulator (v6.3.0)
インタラクティブなGPUリソース管理盤ウィジェット

Feature B: "VRAM Budget Simulator" - 設定画面刷新
- GPU動的検出（nvidia-smi / pynvml対応）
- モデル選択時にVRAMブロックがスタック表示
- オーバーフロー警告をリアルタイム表示
- ドラッグ&ドロップでGPU間モデル移動

Design: Cyberpunk Minimal - ダークグレー背景、ネオンブルー/グリーンのアクセント

v6.3.0: GPU動的検出機能追加、実際のハードウェア構成を自動認識
"""

import logging
import os
from typing import Optional, Dict, Any, List, Tuple

from ..utils.subprocess_utils import run_hidden
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QScrollArea, QSizePolicy,
    QGraphicsDropShadowEffect, QToolTip, QMenu, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, pyqtSignal, QMimeData,
    QPropertyAnimation, QEasingCurve, QSize
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QDrag, QPixmap, QCursor
)

from ..utils.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """モデル情報データクラス"""
    name: str
    vram_gb: float
    category: str  # search, report, architect, coding, verifier
    description: str = ""
    color: str = "#3d3d3d"


@dataclass
class GPUInfo:
    """GPU情報データクラス"""
    index: int
    name: str
    total_vram_gb: float
    color: str = "#00d4ff"


# 利用可能なモデルカタログ
MODEL_CATALOG: Dict[str, ModelInfo] = {
    # coding: コード生成・修正・レビュー
    "devstral-2:123b": ModelInfo("devstral-2:123b", 75, "coding", t('desktop.widgets.vramSim.modelDescriptions.codestral'), "#ff6b9d"),
    "qwen3-coder-next:80b": ModelInfo("qwen3-coder-next:80b", 50, "coding", t('desktop.widgets.vramSim.modelDescriptions.codestralAlt'), "#ff8fab"),
    "qwen3-coder:30b": ModelInfo("qwen3-coder:30b", 19, "coding", t('desktop.widgets.vramSim.modelDescriptions.qwen3'), "#ffadc6"),

    # research: 調査・RAG検索・情報収集
    "command-a:latest": ModelInfo("command-a:latest", 67, "research", t('desktop.widgets.vramSim.modelDescriptions.ministral'), "#6bc5ff"),
    "nemotron-3-nano:30b": ModelInfo("nemotron-3-nano:30b", 24, "research", t('desktop.widgets.vramSim.modelDescriptions.gemma3'), "#8bd5ff"),
    "qwen3:30b": ModelInfo("qwen3:30b", 19, "research", t('desktop.widgets.vramSim.modelDescriptions.phi4'), "#aae5ff"),

    # reasoning: 推論・論理検証・品質チェック
    "gpt-oss:120b": ModelInfo("gpt-oss:120b", 80, "reasoning", t('desktop.widgets.vramSim.modelDescriptions.qwq'), "#6bffb8"),
    "phi4-reasoning:14b": ModelInfo("phi4-reasoning:14b", 9, "reasoning", t('desktop.widgets.vramSim.modelDescriptions.qwqSmall'), "#8bffcc"),

    # translation: 翻訳タスク
    "translategemma:27b": ModelInfo("translategemma:27b", 18, "translation", t('desktop.widgets.vramSim.modelDescriptions.aya'), "#ffd66b"),

    # vision: 画像解析・UI検証
    "gemma3:27b": ModelInfo("gemma3:27b", 18, "vision", t('desktop.widgets.vramSim.modelDescriptions.llava'), "#e06bff"),
    "mistral-small3.2:24b": ModelInfo("mistral-small3.2:24b", 15, "vision", t('desktop.widgets.vramSim.modelDescriptions.minicpm'), "#e08bff"),
}

# フォールバック用のデフォルトGPU構成
_FALLBACK_GPUS = [
    GPUInfo(0, t('desktop.widgets.vramSim.gpuFallback0'), 96, "#00ff88"),
    GPUInfo(1, t('desktop.widgets.vramSim.gpuFallback1'), 16, "#00d4ff"),
]


def detect_gpus() -> List[GPUInfo]:
    """
    システムのGPU情報を動的に検出する。

    検出優先順位:
    1. pynvml（推奨、最も正確）
    2. nvidia-smi コマンド（フォールバック）
    3. ハードコードされたデフォルト値（検出失敗時）

    Returns:
        GPUInfoのリスト（インデックス順）
    """
    gpus = []

    # GPU名→カラーマッピング
    color_map = {
        "pro 6000": "#00ff88",     # ネオングリーン（ハイエンド）
        "rtx 6000": "#00ff88",
        "blackwell": "#00ff88",
        "5090": "#00d4ff",          # ネオンシアン
        "5080": "#00d4ff",
        "5070": "#00b4d8",
        "4090": "#48cae4",
        "4080": "#48cae4",
        "3090": "#90e0ef",
        "3080": "#90e0ef",
    }

    # 方法1: pynvmlによる検出
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_vram_gb = mem_info.total / (1024 ** 3)

            # カラー選択
            name_lower = name.lower()
            color = "#00d4ff"  # デフォルト
            for key, c in color_map.items():
                if key in name_lower:
                    color = c
                    break

            gpus.append(GPUInfo(
                index=i,
                name=name,
                total_vram_gb=round(total_vram_gb, 1),
                color=color,
            ))

        pynvml.nvmlShutdown()
        if gpus:
            logger.info(f"[VRAM Simulator] pynvmlでGPU検出成功: {len(gpus)}台")
            for gpu in gpus:
                logger.info(f"  GPU {gpu.index}: {gpu.name} ({gpu.total_vram_gb:.1f}GB)")
            return gpus

    except ImportError:
        logger.debug("[VRAM Simulator] pynvmlがインストールされていません")
    except Exception as e:
        logger.debug(f"[VRAM Simulator] pynvml検出失敗: {e}")

    # 方法2: nvidia-smi コマンド
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total",
            "--format=csv,noheader,nounits"
        ]
        result = run_hidden(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    idx = int(parts[0])
                    name = parts[1]
                    vram_mb = float(parts[2])
                    vram_gb = vram_mb / 1024

                    # カラー選択
                    name_lower = name.lower()
                    color = "#00d4ff"
                    for key, c in color_map.items():
                        if key in name_lower:
                            color = c
                            break

                    gpus.append(GPUInfo(
                        index=idx,
                        name=name,
                        total_vram_gb=round(vram_gb, 1),
                        color=color,
                    ))

            if gpus:
                logger.info(f"[VRAM Simulator] nvidia-smiでGPU検出成功: {len(gpus)}台")
                for gpu in gpus:
                    logger.info(f"  GPU {gpu.index}: {gpu.name} ({gpu.total_vram_gb:.1f}GB)")
                return gpus

    except FileNotFoundError:
        logger.debug("[VRAM Simulator] nvidia-smiが見つかりません")
    except Exception as e:
        logger.debug(f"[VRAM Simulator] nvidia-smi検出失敗: {e}")

    # 方法3: フォールバック（ハードコード）
    logger.warning("[VRAM Simulator] GPU検出失敗、デフォルト値を使用")
    return _FALLBACK_GPUS.copy()


# 実行時にGPUを検出（モジュールロード時）
_detected_gpus: Optional[List[GPUInfo]] = None


def get_system_gpus() -> List[GPUInfo]:
    """
    システムGPU情報を取得する（キャッシュ対応）。

    Returns:
        GPUInfoのリスト
    """
    global _detected_gpus
    if _detected_gpus is None:
        _detected_gpus = detect_gpus()
    return _detected_gpus


def refresh_gpu_detection() -> List[GPUInfo]:
    """
    GPU検出をリフレッシュする。

    Returns:
        新しく検出されたGPUInfoのリスト
    """
    global _detected_gpus
    _detected_gpus = detect_gpus()
    return _detected_gpus


# 後方互換性のためのエイリアス（モジュール初期化時に検出）
def _get_default_gpus():
    """DEFAULT_GPUSとして使用するGPUリストを取得"""
    return get_system_gpus()


# 注意: 外部からDEFAULT_GPUSを直接参照している場合は get_system_gpus() を使用してください
DEFAULT_GPUS = None  # 初期化時にNone、実際に必要な場合は get_system_gpus() を使用


class VRAMBlock(QFrame):
    """
    VRAM使用量を表すブロックウィジェット

    - ドラッグ可能
    - ホバーで詳細表示
    - カテゴリ別カラー
    """

    removed = pyqtSignal(str)  # モデル名
    moved = pyqtSignal(str, int)  # モデル名, 移動先GPU index

    # カテゴリ別カラー
    CATEGORY_COLORS = {
        "coding": "#ff6b9d",
        "report": "#6bffb8",
        "search": "#6bc5ff",
        "verifier": "#ffd66b",
        "architect": "#b56bff",
    }

    def __init__(self, model_info: ModelInfo, parent=None):
        super().__init__(parent)
        self.model_info = model_info
        self.setAcceptDrops(False)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        """UIを初期化"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # モデル名
        name_label = QLabel(self.model_info.name)
        name_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        layout.addWidget(name_label)

        layout.addStretch()

        # VRAM使用量
        vram_label = QLabel(f"{self.model_info.vram_gb:.0f}GB")
        vram_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(vram_label)

        # 削除ボタン
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4757;
                color: #ffffff;
                border: none;
                border-radius: 9px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6b7a;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.model_info.name))
        layout.addWidget(remove_btn)

    def _apply_style(self):
        """スタイルを適用"""
        color = self.CATEGORY_COLORS.get(
            self.model_info.category,
            "#3d3d3d"
        )

        self.setStyleSheet(f"""
            VRAMBlock {{
                background-color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                min-height: 32px;
            }}
            VRAMBlock:hover {{
                border: 2px solid #ffffff;
            }}
        """)

        self.setToolTip(
            f"<b>{self.model_info.name}</b><br>"
            f"VRAM: {self.model_info.vram_gb:.1f} GB<br>"
            f"{t('desktop.widgets.vramSim.categoryTooltip', category=self.model_info.category)}<br>"
            f"{self.model_info.description}"
        )

    def mousePressEvent(self, event):
        """ドラッグ開始"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """ドラッグ終了"""
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """ドラッグ中"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            # ドラッグ開始
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.model_info.name)
            drag.setMimeData(mime_data)

            # ドラッグ画像
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            drag.exec(Qt.DropAction.MoveAction)


class GPUBar(QFrame):
    """
    GPU VRAMバー ウィジェット

    - VRAMブロックのスタック表示
    - 使用量/空き容量のビジュアル表示
    - ドロップ受け入れ
    - オーバーフロー警告
    """

    modelDropped = pyqtSignal(str, int)  # モデル名, GPU index
    modelRemoved = pyqtSignal(str, int)  # モデル名, GPU index
    overflowChanged = pyqtSignal(int, float)  # GPU index, overflow GB

    def __init__(self, gpu_info: GPUInfo, parent=None):
        super().__init__(parent)
        self.gpu_info = gpu_info
        self._models: List[ModelInfo] = []
        self._used_vram: float = 0

        self.setAcceptDrops(True)
        self.setMinimumHeight(180)

        self._init_ui()
        self._update_display()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ヘッダー
        header_layout = QHBoxLayout()

        # GPU名
        gpu_label = QLabel(f"GPU {self.gpu_info.index}: {self.gpu_info.name}")
        gpu_label.setStyleSheet(f"""
            color: {self.gpu_info.color};
            font-size: 13px;
            font-weight: bold;
        """)
        header_layout.addWidget(gpu_label)

        header_layout.addStretch()

        # VRAM表示
        self.vram_label = QLabel(f"0 / {self.gpu_info.total_vram_gb:.0f} GB")
        self.vram_label.setStyleSheet("color: #888888; font-size: 11px;")
        header_layout.addWidget(self.vram_label)

        layout.addLayout(header_layout)

        # VRAMプログレスバー
        self.progress_frame = QFrame()
        self.progress_frame.setFixedHeight(24)
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_frame)

        # モデルブロックコンテナ
        self.blocks_container = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_container)
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(4)
        self.blocks_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(self.blocks_container)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        layout.addWidget(scroll)

        # オーバーフロー警告
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #ff4757; font-size: 11px;")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        self._apply_style()

    def _apply_style(self):
        """スタイルを適用"""
        self.setStyleSheet(f"""
            GPUBar {{
                background-color: #1e1e1e;
                border: 2px solid {self.gpu_info.color};
                border-radius: 10px;
            }}
        """)

    def add_model(self, model_info: ModelInfo) -> bool:
        """モデルを追加"""
        # 既に追加されているかチェック
        if any(m.name == model_info.name for m in self._models):
            return False

        self._models.append(model_info)

        # ブロックウィジェット作成
        block = VRAMBlock(model_info)
        block.removed.connect(lambda name: self.remove_model(name))
        self.blocks_layout.insertWidget(self.blocks_layout.count() - 1, block)

        self._update_display()
        return True

    def remove_model(self, model_name: str) -> bool:
        """モデルを削除"""
        for i, model in enumerate(self._models):
            if model.name == model_name:
                self._models.pop(i)
                break
        else:
            return False

        # ブロックウィジェットを削除
        for i in range(self.blocks_layout.count()):
            item = self.blocks_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, VRAMBlock) and widget.model_info.name == model_name:
                    widget.deleteLater()
                    break

        self._update_display()
        self.modelRemoved.emit(model_name, self.gpu_info.index)
        return True

    def get_models(self) -> List[ModelInfo]:
        """現在のモデルリストを取得"""
        return self._models.copy()

    def get_used_vram(self) -> float:
        """使用VRAM量を取得"""
        return self._used_vram

    def get_free_vram(self) -> float:
        """空きVRAM量を取得"""
        return max(0, self.gpu_info.total_vram_gb - self._used_vram)

    def get_overflow(self) -> float:
        """オーバーフロー量を取得"""
        return max(0, self._used_vram - self.gpu_info.total_vram_gb)

    def _update_display(self):
        """表示を更新"""
        # VRAM計算
        self._used_vram = sum(m.vram_gb for m in self._models)
        overflow = self.get_overflow()

        # ラベル更新
        self.vram_label.setText(
            f"{self._used_vram:.1f} / {self.gpu_info.total_vram_gb:.0f} GB"
        )

        # プログレスバー更新
        self._update_progress_bar()

        # オーバーフロー警告
        if overflow > 0:
            self.warning_label.setText(t('desktop.widgets.vramSim.vramOverWarning', overflow=f"{overflow:.1f}"))
            self.warning_label.setVisible(True)
            self.overflowChanged.emit(self.gpu_info.index, overflow)
        else:
            self.warning_label.setVisible(False)
            self.overflowChanged.emit(self.gpu_info.index, 0)

    def _update_progress_bar(self):
        """プログレスバーを更新（paintEventで描画）"""
        self.progress_frame.update()

    def paintEvent(self, event):
        """描画イベント"""
        super().paintEvent(event)

        # プログレスバーの描画
        if not hasattr(self, 'progress_frame'):
            return

        painter = QPainter(self.progress_frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.progress_frame.rect()
        margin = 2
        inner_rect = QRectF(
            margin, margin,
            rect.width() - margin * 2,
            rect.height() - margin * 2
        )

        # 使用量の割合
        usage_ratio = min(1.0, self._used_vram / self.gpu_info.total_vram_gb)
        overflow = self.get_overflow() > 0

        # 塗りつぶし
        if usage_ratio > 0:
            fill_width = inner_rect.width() * usage_ratio

            # グラデーション
            gradient = QLinearGradient(0, 0, fill_width, 0)
            if overflow:
                gradient.setColorAt(0, QColor("#ff4757"))
                gradient.setColorAt(1, QColor("#ff6b7a"))
            else:
                gradient.setColorAt(0, QColor(self.gpu_info.color))
                gradient.setColorAt(1, QColor(self.gpu_info.color).lighter(120))

            fill_rect = QRectF(inner_rect.x(), inner_rect.y(), fill_width, inner_rect.height())

            path = QPainterPath()
            path.addRoundedRect(fill_rect, 2, 2)
            painter.fillPath(path, QBrush(gradient))

        painter.end()

    def dragEnterEvent(self, event):
        """ドラッグ進入"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                GPUBar {{
                    background-color: #252525;
                    border: 3px solid {self.gpu_info.color};
                    border-radius: 10px;
                }}
            """)

    def dragLeaveEvent(self, event):
        """ドラッグ離脱"""
        self._apply_style()

    def dropEvent(self, event):
        """ドロップ"""
        model_name = event.mimeData().text()
        if model_name in MODEL_CATALOG:
            model_info = MODEL_CATALOG[model_name]
            if self.add_model(model_info):
                self.modelDropped.emit(model_name, self.gpu_info.index)
        self._apply_style()
        event.acceptProposedAction()


class ModelSelector(QFrame):
    """
    モデル選択パネル

    - カテゴリ別モデル一覧
    - クリックでGPUに追加
    - VRAM使用量表示
    """

    modelSelected = pyqtSignal(str)  # モデル名

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ヘッダー
        header = QLabel(t('desktop.widgets.vramSim.catalogHeader'))
        header.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(t('desktop.widgets.vramSim.catalogDesc'))
        desc.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(desc)

        # カテゴリ別モデルボタン
        categories = {
            "coding": t('desktop.widgets.vramSim.catCoding'),
            "report": t('desktop.widgets.vramSim.catReport'),
            "search": t('desktop.widgets.vramSim.catSearch'),
            "verifier": t('desktop.widgets.vramSim.catVerify'),
        }

        for cat_id, cat_name in categories.items():
            cat_label = QLabel(cat_name)
            cat_label.setStyleSheet("color: #b0b0b0; font-size: 11px; margin-top: 8px;")
            layout.addWidget(cat_label)

            for model_name, model_info in MODEL_CATALOG.items():
                if model_info.category == cat_id:
                    btn = QPushButton(f"{model_info.name} ({model_info.vram_gb:.0f}GB)")
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {VRAMBlock.CATEGORY_COLORS.get(cat_id, '#3d3d3d')};
                            color: #ffffff;
                            border: none;
                            border-radius: 6px;
                            padding: 6px 12px;
                            text-align: left;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{
                            background-color: {QColor(VRAMBlock.CATEGORY_COLORS.get(cat_id, '#3d3d3d')).lighter(120).name()};
                        }}
                    """)
                    btn.setToolTip(model_info.description)
                    btn.clicked.connect(lambda checked, n=model_name: self.modelSelected.emit(n))
                    layout.addWidget(btn)

        layout.addStretch()

        self.setStyleSheet("""
            ModelSelector {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 10px;
            }
        """)


class VRAMBudgetSimulator(QWidget):
    """
    VRAM Budget Simulator メインウィジェット

    インタラクティブなGPUリソース管理盤:
    - 複数GPU対応（デフォルト: RTX PRO 6000 96GB + RTX 5070 Ti 16GB）
    - モデル選択でVRAMスタック表示
    - オーバーフロー警告
    - ドラッグ&ドロップでGPU間移動

    Signals:
        configurationChanged: GPU構成が変更された時
        overflowDetected(int, float): オーバーフロー検出時（GPU index, overflow GB）
    """

    configurationChanged = pyqtSignal()
    overflowDetected = pyqtSignal(int, float)

    def __init__(self, gpus: List[GPUInfo] = None, parent=None):
        super().__init__(parent)

        # v6.3.0: GPU動的検出
        self._gpus = gpus if gpus is not None else get_system_gpus()
        self._gpu_bars: Dict[int, GPUBar] = {}

        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ヘッダー
        header_layout = QHBoxLayout()
        title = QLabel(t('desktop.widgets.vramSim.simTitle'))
        title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 合計VRAM表示
        total_vram = sum(g.total_vram_gb for g in self._gpus)
        self.total_label = QLabel(t('desktop.widgets.vramSim.totalVram', used="0", total=f"{total_vram:.0f}"))
        self.total_label.setStyleSheet("color: #888888; font-size: 12px;")
        header_layout.addWidget(self.total_label)

        # リセットボタン
        reset_btn = QPushButton(t('desktop.widgets.vramSim.resetBtn'))
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        reset_btn.clicked.connect(self.reset_all)
        header_layout.addWidget(reset_btn)

        layout.addLayout(header_layout)

        # メインコンテンツ
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # GPUバー
        gpu_layout = QVBoxLayout()
        gpu_layout.setSpacing(12)

        for gpu in self._gpus:
            gpu_bar = GPUBar(gpu)
            gpu_bar.modelDropped.connect(self._on_model_dropped)
            gpu_bar.modelRemoved.connect(self._on_model_removed)
            gpu_bar.overflowChanged.connect(self._on_overflow_changed)
            self._gpu_bars[gpu.index] = gpu_bar
            gpu_layout.addWidget(gpu_bar)

        content_layout.addLayout(gpu_layout, stretch=3)

        # モデルセレクター
        self.model_selector = ModelSelector()
        self.model_selector.modelSelected.connect(self._on_model_selected)
        content_layout.addWidget(self.model_selector, stretch=1)

        layout.addLayout(content_layout)

        # サマリー
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        summary_layout = QHBoxLayout(self.summary_frame)

        self.summary_label = QLabel(t('desktop.widgets.vramSim.emptyState'))
        self.summary_label.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        summary_layout.addWidget(self.summary_label)

        layout.addWidget(self.summary_frame)

    def _on_model_selected(self, model_name: str):
        """モデルが選択された時"""
        if model_name not in MODEL_CATALOG:
            return

        model_info = MODEL_CATALOG[model_name]

        # GPU 0に追加を試みる
        if 0 in self._gpu_bars:
            success = self._gpu_bars[0].add_model(model_info)
            if success:
                self._update_summary()
                self.configurationChanged.emit()

    def _on_model_dropped(self, model_name: str, gpu_index: int):
        """モデルがドロップされた時"""
        # 他のGPUから削除
        for idx, bar in self._gpu_bars.items():
            if idx != gpu_index:
                bar.remove_model(model_name)

        self._update_summary()
        self.configurationChanged.emit()

    def _on_model_removed(self, model_name: str, gpu_index: int):
        """モデルが削除された時"""
        self._update_summary()
        self.configurationChanged.emit()

    def _on_overflow_changed(self, gpu_index: int, overflow_gb: float):
        """オーバーフロー状態が変更された時"""
        if overflow_gb > 0:
            self.overflowDetected.emit(gpu_index, overflow_gb)

    def _update_summary(self):
        """サマリーを更新"""
        total_used = sum(bar.get_used_vram() for bar in self._gpu_bars.values())
        total_vram = sum(g.total_vram_gb for g in self._gpus)

        self.total_label.setText(t('desktop.widgets.vramSim.totalVram', used=f"{total_used:.1f}", total=f"{total_vram:.0f}"))

        # モデル一覧
        all_models = []
        for bar in self._gpu_bars.values():
            for model in bar.get_models():
                all_models.append(f"{model.name} (GPU{bar.gpu_info.index})")

        if all_models:
            self.summary_label.setText(t('desktop.widgets.vramSim.placedSummary', summary=", ".join(all_models)))
        else:
            self.summary_label.setText(t('desktop.widgets.vramSim.emptyState'))

        # オーバーフローチェック
        has_overflow = any(bar.get_overflow() > 0 for bar in self._gpu_bars.values())
        if has_overflow:
            self.summary_frame.setStyleSheet("""
                QFrame {
                    background-color: #3d1f1f;
                    border: 1px solid #ff4757;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
        else:
            self.summary_frame.setStyleSheet("""
                QFrame {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)

    def reset_all(self):
        """全てリセット"""
        for bar in self._gpu_bars.values():
            for model in bar.get_models().copy():
                bar.remove_model(model.name)

        self._update_summary()
        self.configurationChanged.emit()

    def add_model_to_gpu(self, model_name: str, gpu_index: int) -> bool:
        """指定GPUにモデルを追加"""
        if model_name not in MODEL_CATALOG:
            return False
        if gpu_index not in self._gpu_bars:
            return False

        model_info = MODEL_CATALOG[model_name]
        success = self._gpu_bars[gpu_index].add_model(model_info)
        if success:
            self._update_summary()
            self.configurationChanged.emit()
        return success

    def get_configuration(self) -> Dict[int, List[str]]:
        """現在の構成を取得"""
        config = {}
        for idx, bar in self._gpu_bars.items():
            config[idx] = [m.name for m in bar.get_models()]
        return config

    def set_configuration(self, config: Dict[int, List[str]]):
        """構成を設定"""
        self.reset_all()
        for gpu_idx, model_names in config.items():
            for model_name in model_names:
                self.add_model_to_gpu(model_name, gpu_idx)

    def get_total_overflow(self) -> float:
        """合計オーバーフロー量を取得"""
        return sum(bar.get_overflow() for bar in self._gpu_bars.values())

    def is_valid_configuration(self) -> bool:
        """有効な構成かどうか"""
        return self.get_total_overflow() == 0


class VRAMCompactWidget(QWidget):
    """
    コンパクト版VRAM表示

    mixAI設定エリアに配置する軽量版
    """

    def __init__(self, gpus: List[GPUInfo] = None, parent=None):
        super().__init__(parent)
        # v6.3.0: GPU動的検出
        self._gpus = gpus if gpus is not None else get_system_gpus()
        self._usage: Dict[int, float] = {g.index: 0 for g in self._gpus}

        self._init_ui()

    def _init_ui(self):
        """UIを初期化"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        self._bars: Dict[int, QFrame] = {}
        self._labels: Dict[int, QLabel] = {}

        for gpu in self._gpus:
            # GPUラベル
            label = QLabel(f"GPU{gpu.index}: 0/{gpu.total_vram_gb:.0f}GB")
            label.setStyleSheet(f"color: {gpu.color}; font-size: 10px;")
            self._labels[gpu.index] = label
            layout.addWidget(label)

            # ミニバー
            bar = QFrame()
            bar.setFixedSize(100, 12)
            bar.setStyleSheet(f"""
                QFrame {{
                    background-color: #2d2d2d;
                    border: 1px solid {gpu.color};
                    border-radius: 3px;
                }}
            """)
            self._bars[gpu.index] = bar
            layout.addWidget(bar)

        layout.addStretch()

    def set_usage(self, gpu_index: int, used_gb: float):
        """使用量を設定"""
        if gpu_index not in self._usage:
            return

        self._usage[gpu_index] = used_gb

        gpu = next((g for g in self._gpus if g.index == gpu_index), None)
        if gpu:
            self._labels[gpu_index].setText(
                f"GPU{gpu_index}: {used_gb:.0f}/{gpu.total_vram_gb:.0f}GB"
            )
