"""
Helix AI Studio v11.8.0 "Refined Obsidian" — UI Style System
全UIスタイルの中央集権的な定義。各タブ/ウィジェットからimportして使用する。
"""
import os as _os

# アイコンパス（SpinBox矢印用）
_ICONS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'icons')
_ARROW_UP = _os.path.normpath(_os.path.join(_ICONS_DIR, 'arrow_up.png')).replace('\\', '/')
_ARROW_DOWN = _os.path.normpath(_os.path.join(_ICONS_DIR, 'arrow_down.png')).replace('\\', '/')

# =============================================================================
# v11.8.0: "Refined Obsidian" カラーシステム
#
# 設計原則:
#   - 4層の深度 (base → surface → card → elevated)
#   - アクセントは sky-500 (#38bdf8) — 蛍光シアンから脱却
#   - WCAG AA 対応コントラスト比
# =============================================================================

COLORS = {
    # ─── 背景レイヤー（深度順）───────────────────────────────────────
    "bg_base":       "#080c14",   # 最深部 (ウィンドウ背景)
    "bg_surface":    "#0d1117",   # 第2層 (メインコンテンツエリア)
    "bg_card":       "#131921",   # 第3層 (カード・グループボックス)
    "bg_elevated":   "#1a2233",   # 第4層 (ドロップダウン・ポップアップ)

    # ─── ボーダー ─────────────────────────────────────────────────────
    "border":        "#1e2d42",   # 標準ボーダー (bg_cardと差別化)
    "border_strong": "#2a3f5a",   # 強調ボーダー (フォーカス時等)
    "border_subtle": "#141c2a",   # 薄いボーダー (セパレーター)

    # ─── アクセント（Sky Blue ベース）─────────────────────────────────
    "accent":        "#38bdf8",   # プライマリアクセント (sky-400)
    "accent_bright": "#7dd3fc",   # ライト (hover)
    "accent_dim":    "#0ea5e9",   # ダーク (active/pressed)
    "accent_muted":  "#0c4a6e",   # 極薄 (選択背景・ハイライト背景)

    # ─── セマンティックカラー ─────────────────────────────────────────
    "success":       "#34d399",   # 成功 (emerald-400)
    "success_bg":    "#064e3b",   # 成功背景
    "warning":       "#fbbf24",   # 警告 (amber-400)
    "warning_bg":    "#451a03",   # 警告背景
    "error":         "#f87171",   # エラー (red-400)
    "error_bg":      "#450a0a",   # エラー背景
    "info":          "#818cf8",   # 情報 (indigo-400)
    "info_bg":       "#1e1b4b",   # 情報背景

    # ─── テキスト ──────────────────────────────────────────────────────
    "text_primary":    "#e2e8f0",  # メインテキスト (slate-200)
    "text_secondary":  "#94a3b8",  # サブテキスト (slate-400)
    "text_muted":      "#475569",  # 補助テキスト (slate-600)
    "text_disabled":   "#334155",  # 無効テキスト (slate-700)
    "text_on_accent":  "#000d1a",  # アクセント上のテキスト (暗め)

    # ─── 後方互換エイリアス（既存コードが参照するキー名）─────────────
    "bg_dark":       "#080c14",   # → bg_base
    "bg_darker":     "#0d1117",   # → bg_surface
    "bg_medium":     "#0d1117",   # → bg_surface
    "accent_cyan":   "#38bdf8",   # → accent (蛍光→スレート)
    "accent_green":  "#34d399",   # → success
    "accent_orange": "#fbbf24",   # → warning
    "accent_red":    "#f87171",   # → error
    "text_dim":      "#94a3b8",   # → text_secondary
    "panel_bg":      "#131921",   # → bg_card
    "border_light":  "#2a3f5a",   # → border_strong
}

# =============================================================================
# v11.8.0: タイポグラフィシステム
#
# 日本語環境では Noto Sans JP / Yu Gothic UI が適切。
# Windows/macOS/Linux 対応のフォールバックスタックを使用。
# =============================================================================

FONT_FAMILY_UI = (
    '"Noto Sans JP", "Yu Gothic UI", "Meiryo UI", "Hiragino Sans", '
    '"Inter", "Segoe UI Variable", "Segoe UI", "SF Pro Display", '
    '"Helvetica Neue", sans-serif'
)

FONT_FAMILY_MONO = (
    '"JetBrains Mono", "Fira Code", "Cascadia Code", '
    '"Consolas", "Courier New", monospace'
)

# タイポスケール（px）
FONT_SCALE = {
    "display":  16,   # タイトル・ヘッダー
    "body":     13,   # 本文・ラベル（基準）
    "small":    11,   # 補助情報・バッジ
    "xs":       10,   # タイムスタンプ・極小
}

# フォントウェイト
FONT_WEIGHT = {
    "bold":    "bold",    # 700
    "medium":  "600",     # 600
    "normal":  "normal",  # 400
}

# =============================================================================
# v11.8.0: グローバルアプリケーションスタイルシート
# main_window.py の create_application() で
# app.setStyleSheet(GLOBAL_APP_STYLESHEET) として適用する。
# =============================================================================

GLOBAL_APP_STYLESHEET = f"""
/* ═══════════════════════════════════════════════════════════════════
   Helix AI Studio v11.8.0 "Refined Obsidian" — Global Stylesheet
   ═══════════════════════════════════════════════════════════════════ */

/* ─── ベースリセット ─────────────────────────────────────────────── */
* {{
    font-family: {FONT_FAMILY_UI};
    font-size: {FONT_SCALE['body']}px;
    color: {COLORS['text_primary']};
    outline: none;
}}

QApplication, QMainWindow, QWidget {{
    background-color: {COLORS['bg_base']};
    color: {COLORS['text_primary']};
}}

/* ─── メインウィンドウ・中央ウィジェット ─────────────────────────── */
QMainWindow::centralWidget,
QStackedWidget,
QSplitter {{
    background-color: {COLORS['bg_surface']};
}}

QSplitter::handle {{
    background-color: {COLORS['border_subtle']};
    width: 1px;
    height: 1px;
}}

/* ─── タブバー ───────────────────────────────────────────────────── */
QTabWidget::pane {{
    background-color: {COLORS['bg_surface']};
    border: 1px solid {COLORS['border']};
    border-top: none;
    border-radius: 0 0 6px 6px;
}}

QTabBar {{
    background-color: {COLORS['bg_base']};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLORS['text_muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    font-size: {FONT_SCALE['body']}px;
    font-weight: {FONT_WEIGHT['normal']};
    min-width: 60px;
}}

QTabBar::tab:selected {{
    color: {COLORS['accent']};
    border-bottom: 2px solid {COLORS['accent']};
    font-weight: {FONT_WEIGHT['medium']};
    background-color: transparent;
}}

QTabBar::tab:hover:!selected {{
    color: {COLORS['text_secondary']};
    background-color: rgba(56, 189, 248, 0.04);
}}

/* ─── QGroupBox (セクションカード) ──────────────────────────────── */
QGroupBox {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 20px;
    padding: 16px 14px 14px 14px;
    font-size: {FONT_SCALE['body']}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    padding: 2px 8px;
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_secondary']};
    font-weight: {FONT_WEIGHT['medium']};
    font-size: {FONT_SCALE['small']}px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border-radius: 4px;
}}

/* ─── 入力フィールド ─────────────────────────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 7px 10px;
    font-size: {FONT_SCALE['body']}px;
    selection-background-color: {COLORS['accent_muted']};
    selection-color: {COLORS['text_primary']};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {COLORS['accent_dim']};
    background-color: {COLORS['bg_elevated']};
}}

QLineEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_disabled']};
    border-color: {COLORS['border_subtle']};
}}

QLineEdit::placeholder {{
    color: {COLORS['text_muted']};
}}

/* ─── コンボボックス ──────────────────────────────────────────────── */
QComboBox {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_SCALE['body']}px;
    min-width: 80px;
}}

QComboBox:hover {{
    border-color: {COLORS['border_strong']};
}}

QComboBox:focus {{
    border-color: {COLORS['accent_dim']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
    padding-right: 4px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_muted']};
    width: 0;
    height: 0;
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {COLORS['accent_muted']};
    selection-color: {COLORS['accent_bright']};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}}

QComboBox QAbstractItemView::item:disabled {{
    color: {COLORS['text_muted']};
    font-style: italic;
    font-size: {FONT_SCALE['small']}px;
}}

/* ─── スクロールバー ─────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_strong']};
    border-radius: 4px;
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_muted']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_strong']};
    border-radius: 4px;
    min-width: 32px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['text_muted']};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ─── チェックボックス ───────────────────────────────────────────── */
QCheckBox {{
    color: {COLORS['text_secondary']};
    font-size: {FONT_SCALE['body']}px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS['border_strong']};
    border-radius: 4px;
    background-color: {COLORS['bg_elevated']};
}}

QCheckBox::indicator:hover {{
    border-color: {COLORS['accent_dim']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent_dim']};
    border-color: {COLORS['accent_dim']};
    image: none;
}}

QCheckBox:disabled {{
    color: {COLORS['text_disabled']};
}}

/* ─── ラベル ─────────────────────────────────────────────────────── */
QLabel {{
    color: {COLORS['text_secondary']};
    font-size: {FONT_SCALE['body']}px;
    background-color: transparent;
}}

/* ─── テーブル・ツリー ───────────────────────────────────────────── */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {COLORS['bg_card']};
    alternate-background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    gridline-color: {COLORS['border_subtle']};
    font-size: {FONT_SCALE['body']}px;
    outline: none;
}}

QTableWidget::item, QTreeWidget::item, QListWidget::item {{
    padding: 5px 8px;
    border: none;
}}

QTableWidget::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: {COLORS['accent_muted']};
    color: {COLORS['accent_bright']};
}}

QTableWidget::item:hover,
QTreeWidget::item:hover,
QListWidget::item:hover {{
    background-color: rgba(56, 189, 248, 0.06);
}}

QHeaderView::section {{
    background-color: {COLORS['bg_base']};
    color: {COLORS['text_muted']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 6px 10px;
    font-size: {FONT_SCALE['xs']}px;
    font-weight: {FONT_WEIGHT['medium']};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ─── ツールチップ ───────────────────────────────────────────────── */
QToolTip {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_SCALE['small']}px;
}}

/* ─── プログレスバー ─────────────────────────────────────────────── */
QProgressBar {{
    background-color: {COLORS['bg_elevated']};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    font-size: {FONT_SCALE['xs']}px;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

/* ─── セパレーター ───────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {COLORS['border']};
    background-color: {COLORS['border']};
    border: none;
    max-height: 1px;
    max-width: 1px;
}}

/* ─── ステータスバー ─────────────────────────────────────────────── */
QStatusBar {{
    background-color: {COLORS['bg_base']};
    color: {COLORS['text_muted']};
    border-top: 1px solid {COLORS['border_subtle']};
    font-size: {FONT_SCALE['small']}px;
}}

/* ─── Slider ─────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background-color: {COLORS['bg_elevated']};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLORS['accent_bright']};
}}

QSlider::sub-page:horizontal {{
    background-color: {COLORS['accent_dim']};
    border-radius: 2px;
}}

/* ─── Menu ───────────────────────────────────────────────────── */
QMenu {{
    background-color: {COLORS['bg_elevated']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 8px 20px;
    border-radius: 4px;
    color: {COLORS['text_primary']};
}}

QMenu::item:selected {{
    background-color: {COLORS['accent_muted']};
    color: {COLORS['accent_bright']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLORS['border']};
    margin: 4px 8px;
}}

/* ─── ToolBar ─────────────────────────────────────────────────── */
QToolBar {{
    background-color: {COLORS['bg_base']};
    border: none;
    padding: 4px;
    spacing: 6px;
}}

/* ─── 言語切り替えボタン (TopBar) ──────────────────────────────── */
QPushButton#langBtn {{
    background-color: transparent;
    color: {COLORS['text_muted']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: {FONT_SCALE['small']}px;
    min-width: 0;
}}

QPushButton#langBtn:checked,
QPushButton#langBtn[active="true"] {{
    background-color: {COLORS['accent_dim']};
    color: {COLORS['text_on_accent']};
    border-color: {COLORS['accent_dim']};
}}
"""

# =============================================================================
# v11.8.0: セクションカードデザイン（QGroupBox 個別上書き用）
# =============================================================================
SECTION_CARD_STYLE = f"""
    QGroupBox {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 20px;
        padding: 16px 14px 14px 14px;
        font-size: {FONT_SCALE['body']}px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        top: -1px;
        padding: 2px 8px;
        background-color: {COLORS['bg_card']};
        color: {COLORS['text_muted']};
        font-weight: {FONT_WEIGHT['medium']};
        font-size: {FONT_SCALE['xs']}px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        border-radius: 4px;
    }}
"""

# =============================================================================
# v11.8.0: ボタンスタイル（3段階）
# =============================================================================

PRIMARY_BTN = f"""
    QPushButton {{
        background-color: {COLORS['accent_dim']};
        color: {COLORS['text_on_accent']};
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: {FONT_WEIGHT['medium']};
        font-size: {FONT_SCALE['body']}px;
        letter-spacing: 0.2px;
    }}
    QPushButton:hover {{
        background-color: {COLORS['accent']};
    }}
    QPushButton:pressed {{
        background-color: {COLORS['accent_dim']};
        padding: 9px 19px 7px 21px;
    }}
    QPushButton:disabled {{
        background-color: {COLORS['bg_elevated']};
        color: {COLORS['text_disabled']};
    }}
"""

SECONDARY_BTN = f"""
    QPushButton {{
        background-color: transparent;
        color: {COLORS['accent']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: {FONT_SCALE['body']}px;
        font-weight: {FONT_WEIGHT['normal']};
    }}
    QPushButton:hover {{
        background-color: rgba(56, 189, 248, 0.08);
        border-color: {COLORS['accent']};
        color: {COLORS['accent_bright']};
    }}
    QPushButton:pressed {{
        background-color: rgba(56, 189, 248, 0.15);
    }}
    QPushButton:disabled {{
        color: {COLORS['text_disabled']};
        border-color: {COLORS['border_subtle']};
    }}
"""

DANGER_BTN = f"""
    QPushButton {{
        background-color: transparent;
        color: {COLORS['error']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: {FONT_SCALE['body']}px;
    }}
    QPushButton:hover {{
        background-color: rgba(248, 113, 113, 0.08);
        border-color: {COLORS['error']};
    }}
    QPushButton:pressed {{
        background-color: rgba(248, 113, 113, 0.15);
    }}
"""

# =============================================================================
# v11.8.0: チャットメッセージスタイル
# =============================================================================

USER_MESSAGE_STYLE = f"""
    background: {COLORS['bg_elevated']};
    border-left: 3px solid {COLORS['accent_dim']};
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    margin: 4px 0;
    color: {COLORS['text_primary']};
    font-size: {FONT_SCALE['body']}px;
"""

AI_MESSAGE_STYLE = f"""
    background: {COLORS['bg_card']};
    border-left: 3px solid {COLORS['border_strong']};
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    margin: 4px 0;
    color: {COLORS['text_primary']};
    font-size: {FONT_SCALE['body']}px;
"""

# =============================================================================
# v11.8.0: 入力エリアスタイル
# =============================================================================

INPUT_AREA_STYLE = f"""
    QTextEdit, QPlainTextEdit {{
        background: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 12px;
        color: {COLORS['text_primary']};
        font-size: {FONT_SCALE['body']}px;
        selection-background-color: {COLORS['accent_muted']};
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {COLORS['accent_dim']};
    }}
"""

# =============================================================================
# 出力テキストエリアスタイル
# =============================================================================

OUTPUT_AREA_STYLE = f"""
    QTextEdit {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 10px;
        font-family: {FONT_FAMILY_MONO};
        line-height: 1.5;
        color: {COLORS['text_primary']};
    }}
"""

# =============================================================================
# v11.8.0: タブバースタイル（個別適用用）
# =============================================================================

TAB_BAR_STYLE = f"""
    QTabBar::tab {{
        background: transparent;
        color: {COLORS['text_muted']};
        padding: 10px 24px;
        border-bottom: 2px solid transparent;
        font-size: {FONT_SCALE['body']}px;
    }}
    QTabBar::tab:selected {{
        color: {COLORS['accent']};
        border-bottom: 2px solid {COLORS['accent']};
        font-weight: {FONT_WEIGHT['medium']};
    }}
    QTabBar::tab:hover:!selected {{
        color: {COLORS['text_secondary']};
        border-bottom: 2px solid {COLORS['border_strong']};
    }}
    QTabWidget::pane {{
        border: none;
    }}
"""

# =============================================================================
# v11.8.0: スクロールバースタイル（個別適用用）
# =============================================================================

SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {COLORS['border_strong']};
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS['text_muted']};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        background: none;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {COLORS['border_strong']};
        border-radius: 4px;
        min-width: 32px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS['text_muted']};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
        background: none;
    }}
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
    }}
"""

# =============================================================================
# v11.8.0: プログレスバースタイル（個別適用用）
# =============================================================================

PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        text-align: center;
        color: {COLORS['text_primary']};
        font-size: {FONT_SCALE['small']}px;
        height: 20px;
    }}
    QProgressBar::chunk {{
        background: {COLORS['accent']};
        border-radius: 3px;
    }}
"""

# =============================================================================
# v11.8.0: コンボボックススタイル（個別適用用）
# =============================================================================

COMBO_BOX_STYLE = f"""
    QComboBox {{
        background-color: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 6px 10px;
        color: {COLORS['text_primary']};
        font-size: {FONT_SCALE['body']}px;
    }}
    QComboBox:hover {{
        border-color: {COLORS['border_strong']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['border_strong']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['accent_muted']};
        selection-color: {COLORS['accent_bright']};
    }}
"""

# =============================================================================
# BIBLE Manager パネルスタイル
# =============================================================================

BIBLE_PANEL_STYLE = f"""
    QFrame {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 12px;
    }}
"""

BIBLE_HEADER_STYLE = f"color: {COLORS['accent']}; font-size: 14px; font-weight: bold;"
BIBLE_STATUS_FOUND_STYLE = f"color: {COLORS['success']}; font-size: 12px;"
BIBLE_STATUS_NOT_FOUND_STYLE = f"color: {COLORS['warning']}; font-size: 12px;"

# =============================================================================
# BIBLE 通知ウィジェットスタイル
# =============================================================================

BIBLE_NOTIFICATION_STYLE = f"""
    QFrame {{
        background-color: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['accent']};
        border-radius: 6px;
        padding: 8px 12px;
    }}
"""

# =============================================================================
# Phaseインジケータースタイル
# =============================================================================

def phase_node_style(active: bool = False, completed: bool = False, color: str = "#333") -> str:
    """Phase ノードのスタイルを動的生成"""
    if completed:
        border_color = color
        bg = COLORS['success_bg']
    elif active:
        border_color = color
        bg = COLORS['bg_card']
    else:
        border_color = COLORS['text_disabled']
        bg = COLORS['bg_card']
    return f"""
        QFrame {{
            background: {bg};
            border: 2px solid {border_color};
            border-radius: 18px;
        }}
    """

PHASE_ARROW_STYLE = f"color: {COLORS['text_disabled']}; font-size: 14px;"
PHASE_DOT_INACTIVE = f"color: {COLORS['text_muted']}; font-size: 10px;"
PHASE_TEXT_INACTIVE = f"color: {COLORS['text_secondary']}; font-size: 11px;"


# =============================================================================
# ユーティリティ関数
# =============================================================================

def score_color(score: float) -> str:
    """完全性スコアに応じた色を返す"""
    if score >= 0.8:
        return COLORS['success']
    elif score >= 0.5:
        return COLORS['warning']
    else:
        return COLORS['error']


def score_bar_style(score: float) -> str:
    """完全性スコアに応じたプログレスバースタイル"""
    color = score_color(score)
    return f"""
        QProgressBar {{
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            text-align: center;
            color: {COLORS['text_primary']};
            font-size: {FONT_SCALE['small']}px;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 3px;
        }}
    """


# =============================================================================
# v8.5.0: 情報収集タブ用スタイル
# =============================================================================

RAG_STATUS_BADGE = f"""
    QLabel {{
        background-color: {COLORS['accent_muted']};
        border: 1px solid {COLORS['accent']};
        border-radius: 10px;
        padding: 4px 12px;
        color: {COLORS['accent']};
        font-size: {FONT_SCALE['small']}px;
        font-weight: bold;
    }}
"""

RAG_STATUS_RUNNING = f"""
    QLabel {{
        background-color: {COLORS['success_bg']};
        border: 1px solid {COLORS['success']};
        border-radius: 10px;
        padding: 4px 12px;
        color: {COLORS['success']};
        font-size: {FONT_SCALE['small']}px;
        font-weight: bold;
    }}
"""

RAG_STATUS_ERROR = f"""
    QLabel {{
        background-color: {COLORS['error_bg']};
        border: 1px solid {COLORS['error']};
        border-radius: 10px;
        padding: 4px 12px;
        color: {COLORS['error']};
        font-size: {FONT_SCALE['small']}px;
        font-weight: bold;
    }}
"""

RAG_FILE_LIST_STYLE = f"""
    QTreeWidget {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        color: {COLORS['text_primary']};
        font-size: {FONT_SCALE['body']}px;
    }}
    QTreeWidget::item {{
        padding: 4px 8px;
    }}
    QTreeWidget::item:selected {{
        background-color: {COLORS['accent_muted']};
        color: {COLORS['accent_bright']};
    }}
    QHeaderView::section {{
        background-color: {COLORS['bg_base']};
        color: {COLORS['accent']};
        padding: 6px;
        border: 1px solid {COLORS['border']};
        font-weight: bold;
    }}
"""

# =============================================================================
# v8.1.0: SpinBox拡大スタイル
# =============================================================================
SPINBOX_STYLE = f"""
    QSpinBox {{
        padding: 4px 60px 4px 8px;
        font-size: {FONT_SCALE['body']}px;
        min-height: 32px;
        min-width: 80px;
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: 6px;
        color: {COLORS['text_primary']};
    }}
    QSpinBox::up-button {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        right: 2px;
        width: 26px;
        height: 26px;
        border: 1px solid {COLORS['border_strong']};
        border-radius: 4px;
        background: {COLORS['bg_elevated']};
    }}
    QSpinBox::down-button {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        right: 30px;
        width: 26px;
        height: 26px;
        border: 1px solid {COLORS['border_strong']};
        border-radius: 4px;
        background: {COLORS['bg_elevated']};
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {COLORS['border_strong']};
        border-color: {COLORS['accent']};
    }}
    QSpinBox::up-arrow {{
        image: url({_ARROW_UP});
        width: 10px;
        height: 10px;
    }}
    QSpinBox::down-arrow {{
        image: url({_ARROW_DOWN});
        width: 10px;
        height: 10px;
    }}
    QSpinBox:disabled {{
        background: {COLORS['bg_elevated']}; color: {COLORS['text_disabled']}; border: 1px solid {COLORS['border']};
    }}
"""

# =============================================================================
# v11.8.0: よく使うインラインスタイルショートカット
# =============================================================================

STYLE_ACCENT_TEXT    = f"color: {COLORS['accent']};"
STYLE_MUTED_TEXT     = f"color: {COLORS['text_muted']};"
STYLE_SECONDARY_TEXT = f"color: {COLORS['text_secondary']};"
STYLE_SUCCESS_TEXT   = f"color: {COLORS['success']};"
STYLE_WARNING_TEXT   = f"color: {COLORS['warning']};"
STYLE_ERROR_TEXT     = f"color: {COLORS['error']};"

STYLE_LABEL_HEADER = (
    f"color: {COLORS['text_secondary']}; "
    f"font-size: {FONT_SCALE['small']}px; "
    f"font-weight: {FONT_WEIGHT['medium']}; "
    f"letter-spacing: 0.3px; "
    f"text-transform: uppercase;"
)

STYLE_VALUE_DISPLAY = (
    f"color: {COLORS['accent']}; "
    f"font-size: {FONT_SCALE['display']}px; "
    f"font-weight: {FONT_WEIGHT['bold']};"
)

STYLE_CODE_INLINE = (
    f"font-family: {FONT_FAMILY_MONO}; "
    f"font-size: {FONT_SCALE['small']}px; "
    f"color: {COLORS['success']}; "
    f"background: {COLORS['bg_elevated']}; "
    f"padding: 1px 4px; "
    f"border-radius: 3px;"
)
