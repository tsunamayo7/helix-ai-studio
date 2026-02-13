"""
Helix AI Studio - Cyberpunk Minimal Theme Styles (v8.0.0)
全UIスタイルの中央集権的な定義。各タブ/ウィジェットからimportして使用する。
"""

# =============================================================================
# カラーパレット
# =============================================================================
COLORS = {
    "bg_dark": "#0a0a1a",
    "bg_medium": "#1a1a2e",
    "bg_card": "#1f2937",
    "border": "#2a2a3e",
    "border_light": "#374151",
    "accent_cyan": "#00d4ff",
    "accent_green": "#00ff88",
    "accent_orange": "#ff9800",
    "accent_red": "#ff6666",
    "text_primary": "#e0e0e0",
    "text_secondary": "#888",
    "text_muted": "#555",
}

# =============================================================================
# セクションカードデザイン（QGroupBox）
# =============================================================================
SECTION_CARD_STYLE = """
    QGroupBox {
        background-color: #1a1a2e;
        border: 1px solid #2a2a3e;
        border-radius: 8px;
        margin-top: 16px;
        padding: 16px 12px 12px 12px;
        font-size: 13px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background-color: #0a0a1a;
        border: 1px solid #2a2a3e;
        border-radius: 4px;
        color: #00d4ff;
        font-weight: bold;
        font-size: 13px;
    }
"""

# =============================================================================
# ボタンスタイル（3段階）
# =============================================================================

# プライマリ（実行、送信、保存）
PRIMARY_BTN = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #00d4ff, stop:1 #0099cc);
        color: #0a0a0a;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #33ddff, stop:1 #00bbee);
    }
    QPushButton:pressed {
        background: #0088aa;
    }
    QPushButton:disabled {
        background: #333;
        color: #666;
    }
"""

# セカンダリ（ファイル添付、履歴、スニペット）
SECONDARY_BTN = """
    QPushButton {
        background: transparent;
        color: #00d4ff;
        border: 1px solid #00d4ff;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 12px;
    }
    QPushButton:hover {
        background: rgba(0, 212, 255, 0.1);
        border-color: #33ddff;
    }
    QPushButton:pressed {
        background: rgba(0, 212, 255, 0.2);
    }
    QPushButton:disabled {
        color: #555;
        border-color: #333;
    }
"""

# デンジャー（クリア、リセット）
DANGER_BTN = """
    QPushButton {
        background: transparent;
        color: #ff6666;
        border: 1px solid #ff6666;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 12px;
    }
    QPushButton:hover {
        background: rgba(255, 102, 102, 0.1);
        border-color: #ff8888;
    }
    QPushButton:pressed {
        background: rgba(255, 102, 102, 0.2);
    }
"""

# =============================================================================
# チャットメッセージスタイル
# =============================================================================

USER_MESSAGE_STYLE = """
    background: #1a2a3e;
    border-left: 3px solid #00d4ff;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 8px 60px 8px 8px;
    color: #e0e0e0;
"""

AI_MESSAGE_STYLE = """
    background: #1a1a2e;
    border-left: 3px solid #00ff88;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 8px 8px 8px 60px;
    color: #e0e0e0;
"""

# =============================================================================
# 入力エリアスタイル
# =============================================================================

INPUT_AREA_STYLE = """
    QTextEdit, QPlainTextEdit {
        background: #0a0a1a;
        border: 1px solid #2a2a3e;
        border-radius: 8px;
        padding: 12px;
        color: #e0e0e0;
        font-size: 13px;
        selection-background-color: rgba(0, 212, 255, 0.26);
    }
    QTextEdit:focus, QPlainTextEdit:focus {
        border: 1px solid #00d4ff;
    }
"""

# =============================================================================
# 出力テキストエリアスタイル
# =============================================================================

OUTPUT_AREA_STYLE = """
    QTextEdit {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 10px;
        font-family: 'Consolas', 'Courier New', monospace;
        line-height: 1.5;
        color: #e0e0e0;
    }
"""

# =============================================================================
# タブバースタイル
# =============================================================================

TAB_BAR_STYLE = """
    QTabBar::tab {
        background: transparent;
        color: #888;
        padding: 10px 24px;
        border-bottom: 2px solid transparent;
        font-size: 13px;
    }
    QTabBar::tab:selected {
        color: #00d4ff;
        border-bottom: 2px solid #00d4ff;
        font-weight: bold;
    }
    QTabBar::tab:hover:!selected {
        color: #aaa;
        border-bottom: 2px solid #444;
    }
    QTabWidget::pane {
        border: none;
    }
"""

# =============================================================================
# スクロールバースタイル
# =============================================================================

SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background: #0a0a1a;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #333;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #00d4ff;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
    QScrollBar:horizontal {
        background: #0a0a1a;
        height: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal {
        background: #333;
        border-radius: 4px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #00d4ff;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }
"""

# =============================================================================
# プログレスバースタイル
# =============================================================================

PROGRESS_BAR_STYLE = """
    QProgressBar {
        background-color: #1a1a2e;
        border: 1px solid #2a2a3e;
        border-radius: 4px;
        text-align: center;
        color: #e0e0e0;
        font-size: 11px;
        height: 20px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #00d4ff, stop:1 #00ff88);
        border-radius: 3px;
    }
"""

# =============================================================================
# コンボボックススタイル
# =============================================================================

COMBO_BOX_STYLE = """
    QComboBox {
        background-color: #1a1a2e;
        border: 1px solid #2a2a3e;
        border-radius: 4px;
        padding: 4px 8px;
        color: #e0e0e0;
        font-size: 12px;
    }
    QComboBox:hover {
        border-color: #00d4ff;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox QAbstractItemView {
        background-color: #1a1a2e;
        border: 1px solid #2a2a3e;
        color: #e0e0e0;
        selection-background-color: #00d4ff;
        selection-color: #0a0a0a;
    }
"""

# =============================================================================
# BIBLE Manager パネルスタイル
# =============================================================================

BIBLE_PANEL_STYLE = """
    QFrame {
        background-color: #1a1a2e;
        border: 1px solid #2a2a3e;
        border-radius: 8px;
        padding: 12px;
    }
"""

BIBLE_HEADER_STYLE = "color: #00d4ff; font-size: 14px; font-weight: bold;"
BIBLE_STATUS_FOUND_STYLE = "color: #00ff88; font-size: 12px;"
BIBLE_STATUS_NOT_FOUND_STYLE = "color: #ff8800; font-size: 12px;"

# =============================================================================
# BIBLE 通知ウィジェットスタイル
# =============================================================================

BIBLE_NOTIFICATION_STYLE = """
    QFrame {
        background-color: #1a2a3e;
        border: 1px solid #00d4ff;
        border-radius: 6px;
        padding: 8px 12px;
    }
"""

# =============================================================================
# Phaseインジケータースタイル
# =============================================================================

def phase_node_style(active: bool = False, completed: bool = False, color: str = "#333") -> str:
    """Phase ノードのスタイルを動的生成"""
    if completed:
        border_color = color
        bg = "#0a1a0a"
    elif active:
        border_color = color
        bg = "#1a1a2e"
    else:
        border_color = "#333"
        bg = "#1a1a2e"
    return f"""
        QFrame {{
            background: {bg};
            border: 2px solid {border_color};
            border-radius: 18px;
        }}
    """

PHASE_ARROW_STYLE = "color: #444; font-size: 14px;"
PHASE_DOT_INACTIVE = "color: #555; font-size: 10px;"
PHASE_TEXT_INACTIVE = "color: #888; font-size: 11px;"


# =============================================================================
# ユーティリティ関数
# =============================================================================

def score_color(score: float) -> str:
    """完全性スコアに応じた色を返す"""
    if score >= 0.8:
        return "#00ff88"
    elif score >= 0.5:
        return "#ffaa00"
    else:
        return "#ff4444"


def score_bar_style(score: float) -> str:
    """完全性スコアに応じたプログレスバースタイル"""
    color = score_color(score)
    return f"""
        QProgressBar {{
            background-color: #1a1a2e;
            border: 1px solid #2a2a3e;
            border-radius: 4px;
            text-align: center;
            color: #e0e0e0;
            font-size: 11px;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 3px;
        }}
    """


# =============================================================================
# v8.5.0: 情報収集タブ用スタイル
# =============================================================================

RAG_STATUS_BADGE = """
    QLabel {
        background-color: #1a2a3e;
        border: 1px solid #00d4ff;
        border-radius: 10px;
        padding: 4px 12px;
        color: #00d4ff;
        font-size: 11px;
        font-weight: bold;
    }
"""

RAG_STATUS_RUNNING = """
    QLabel {
        background-color: #1a3a1a;
        border: 1px solid #00ff88;
        border-radius: 10px;
        padding: 4px 12px;
        color: #00ff88;
        font-size: 11px;
        font-weight: bold;
    }
"""

RAG_STATUS_ERROR = """
    QLabel {
        background-color: #3a1a1a;
        border: 1px solid #ff6666;
        border-radius: 10px;
        padding: 4px 12px;
        color: #ff6666;
        font-size: 11px;
        font-weight: bold;
    }
"""

RAG_FILE_LIST_STYLE = """
    QTreeWidget {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 12px;
    }
    QTreeWidget::item {
        padding: 4px 8px;
    }
    QTreeWidget::item:selected {
        background-color: #00d4ff;
        color: #0a0a0a;
    }
    QHeaderView::section {
        background-color: #1f2937;
        color: #00d4ff;
        padding: 6px;
        border: 1px solid #374151;
        font-weight: bold;
    }
"""

# =============================================================================
# v8.1.0: SpinBox拡大スタイル
# =============================================================================
SPINBOX_STYLE = """
    QSpinBox {
        padding: 6px 12px; font-size: 14px;
        min-height: 32px; min-width: 100px;
        background: #1f2937; border: 1px solid #4b5563;
        border-radius: 6px; color: #e5e7eb;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        width: 28px; border: none; background: #2a2a3e;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background: #374151;
    }
    QSpinBox::up-arrow {
        image: none; border-left: 7px solid transparent;
        border-right: 7px solid transparent;
        border-bottom: 9px solid #00d4ff; width: 0; height: 0;
    }
    QSpinBox::down-arrow {
        image: none; border-left: 7px solid transparent;
        border-right: 7px solid transparent;
        border-top: 9px solid #00d4ff; width: 0; height: 0;
    }
"""
