"""
src/utils/style_helpers.py
v11.9.0: セマンティックスタイルヘルパー

使い方:
    from ..utils.style_helpers import SS

    widget.setStyleSheet(SS.ok())        # 成功 (緑)
    widget.setStyleSheet(SS.err())       # エラー (赤)
    widget.setStyleSheet(SS.warn())      # 警告 (黄)
    widget.setStyleSheet(SS.muted())     # 補助テキスト (グレー)
    widget.setStyleSheet(SS.accent())    # アクセント (スカイブルー)
    widget.setStyleSheet(SS.primary())   # プライマリテキスト

    # フォントサイズ上書き
    widget.setStyleSheet(SS.muted("10px"))
    widget.setStyleSheet(SS.ok("9pt"))
    widget.setStyleSheet(SS.accent("12px", bold=True))
"""

from .styles import COLORS, FONT_SCALE


class _SS:
    """セマンティックスタイルシートヘルパー"""

    _D = f"{FONT_SCALE['body']}px"  # デフォルトフォントサイズ

    # ─── ステータスカラー ─────────────────────────────────────────

    def ok(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['success']}; font-size: {size}; font-weight: {w};"

    def err(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['error']}; font-size: {size}; font-weight: {w};"

    def warn(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['warning']}; font-size: {size}; font-weight: {w};"

    def info(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['info']}; font-size: {size}; font-weight: {w};"

    # ─── テキストカラー ───────────────────────────────────────────

    def muted(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['text_secondary']}; font-size: {size}; font-weight: {w};"

    def accent(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['accent']}; font-size: {size}; font-weight: {w};"

    def primary(self, size: str = _D, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"color: {COLORS['text_primary']}; font-size: {size}; font-weight: {w};"

    def dim(self, size: str = _D) -> str:
        return f"color: {COLORS['text_muted']}; font-size: {size};"

    # ─── 特殊用途 ─────────────────────────────────────────────────

    def code(self) -> str:
        """インラインコード・モノスペース表示"""
        from .styles import FONT_FAMILY_MONO, FONT_SCALE
        return (
            f"font-family: {FONT_FAMILY_MONO}; "
            f"color: {COLORS['success']}; "
            f"background-color: {COLORS['bg_elevated']}; "
            f"font-size: {FONT_SCALE['small']}px; "
            f"padding: 1px 4px; border-radius: 3px;"
        )

    def input_area(self) -> str:
        """チャット入力エリア"""
        return (
            f"background-color: {COLORS['bg_elevated']}; "
            f"color: {COLORS['text_primary']}; "
            f"border: none;"
        )

    def input_frame(self, border_top: bool = True) -> str:
        """入力エリアのフレーム"""
        border = f"border-top: 1px solid {COLORS['border']};" if border_top else ""
        return f"background-color: {COLORS['bg_surface']}; {border}"

    def card_frame(self) -> str:
        """カード背景"""
        return (
            f"background-color: {COLORS['bg_card']}; "
            f"border: 1px solid {COLORS['border']}; "
            f"border-radius: 6px;"
        )

    def section_title(self) -> str:
        """セクション見出し"""
        return (
            f"color: {COLORS['accent']}; "
            f"font-size: {FONT_SCALE['small']}px; "
            f"font-weight: bold; letter-spacing: 0.3px;"
        )

    def json_editor(self) -> str:
        """JSONエディタ"""
        from .styles import FONT_FAMILY_MONO, FONT_SCALE
        return (
            f"QTextEdit {{ "
            f"background: {COLORS['bg_base']}; "
            f"color: {COLORS['text_primary']}; "
            f"font-family: {FONT_FAMILY_MONO}; "
            f"font-size: {FONT_SCALE['small']}px; }}"
        )

    # ─── 用途別エイリアス (よく使うパターンの短縮形) ───────────────

    def cli_ok(self)      -> str: return self.ok("9pt")
    def cli_err(self)     -> str: return self.err("9pt")
    def cli_warn(self)    -> str: return self.warn("9pt")
    def api_ok(self)      -> str: return self.ok("12px")
    def api_pending(self) -> str: return self.warn("11px")
    def ollama_ok(self)   -> str: return self.ok("11px")
    def ollama_err(self)  -> str: return self.err("11px")
    def discord_ok(self)  -> str: return self.ok("10px")
    def discord_err(self) -> str: return self.err("10px")
    def discord_pend(self)-> str: return self.warn("10px")


# シングルトン
SS = _SS()
