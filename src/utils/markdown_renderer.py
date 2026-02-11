"""
Helix AI Studio - Markdown Renderer (v8.0.0)
純Python簡易Markdown→HTML変換（外部ライブラリ不要）

Claudeの応答テキストをリッチHTMLに変換し、
QTextEdit/QTextBrowserで美しく表示する。
"""

import re
from typing import List


def markdown_to_html(text: str) -> str:
    """
    Markdown テキストを HTML に変換する。

    対応構文:
    - 見出し (# ## ###)
    - コードブロック (```)
    - リスト (- * 1.)
    - 太字 (**bold**)
    - 斜体 (*italic*)
    - インラインコード (`code`)
    - 水平線 (---)
    - 空行
    """
    if not text:
        return ""

    lines = text.split('\n')
    html_parts: List[str] = []
    in_code_block = False
    code_lang = ""

    for line in lines:
        # コードブロック開始/終了
        if line.strip().startswith('```'):
            if in_code_block:
                html_parts.append('</code></pre>')
                in_code_block = False
            else:
                code_lang = line.strip()[3:].strip()
                lang_label = (
                    f'<div style="color:#888;font-size:11px;'
                    f'margin-bottom:4px;">{code_lang}</div>'
                    if code_lang else ''
                )
                html_parts.append(
                    f'{lang_label}'
                    f'<pre style="background:#1a1a2e;border:1px solid #333;'
                    f'border-radius:6px;padding:12px;margin:8px 0;'
                    f'font-family:Consolas,\'Courier New\',monospace;font-size:13px;'
                    f'color:#e0e0e0;overflow-x:auto;white-space:pre-wrap;'
                    f'word-wrap:break-word;"><code>'
                )
                in_code_block = True
            continue

        if in_code_block:
            # コードブロック内はHTMLエスケープのみ
            escaped = _html_escape(line)
            html_parts.append(escaped + '\n')
            continue

        # 水平線
        if re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', line.strip()):
            html_parts.append(
                '<hr style="border:none;border-top:1px solid #333;margin:16px 0;">'
            )
            continue

        # 見出し
        if line.startswith('### '):
            content = _apply_inline(line[4:])
            html_parts.append(
                f'<h3 style="color:#00d4ff;margin:16px 0 8px;'
                f'font-size:15px;border-bottom:1px solid #333;'
                f'padding-bottom:4px;">{content}</h3>'
            )
        elif line.startswith('## '):
            content = _apply_inline(line[3:])
            html_parts.append(
                f'<h2 style="color:#00d4ff;margin:20px 0 10px;'
                f'font-size:17px;border-bottom:1px solid #444;'
                f'padding-bottom:6px;">{content}</h2>'
            )
        elif line.startswith('# '):
            content = _apply_inline(line[2:])
            html_parts.append(
                f'<h1 style="color:#00ffcc;margin:24px 0 12px;'
                f'font-size:20px;">{content}</h1>'
            )
        # 箇条書きリスト
        elif re.match(r'^(\s*)([-*])\s+', line):
            m = re.match(r'^(\s*)([-*])\s+(.*)', line)
            if m:
                indent = len(m.group(1))
                content = _apply_inline(m.group(3))
                margin = 8 + indent * 4
                html_parts.append(
                    f'<div style="margin-left:{margin}px;padding:2px 0;">'
                    f'<span style="color:#00d4ff;font-size:10px;">&#9679;</span> '
                    f'{content}</div>'
                )
        # 番号付きリスト
        elif re.match(r'^(\s*)\d+\.\s+', line):
            m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
            if m:
                indent = len(m.group(1))
                content = _apply_inline(m.group(2))
                margin = 8 + indent * 4
                html_parts.append(
                    f'<div style="margin-left:{margin}px;padding:2px 0;">'
                    f'{content}</div>'
                )
        # 空行
        elif line.strip() == '':
            html_parts.append('<div style="height:8px;"></div>')
        # テーブル行（|で始まる）
        elif line.strip().startswith('|'):
            # セパレータ行をスキップ
            if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            cells_html = ''.join(
                f'<td style="padding:4px 8px;border:1px solid #333;">'
                f'{_apply_inline(c)}</td>'
                for c in cells
            )
            html_parts.append(
                f'<tr style="background:#1a1a2e;">{cells_html}</tr>'
            )
        # 通常テキスト
        else:
            content = _apply_inline(line)
            html_parts.append(
                f'<p style="margin:4px 0;line-height:1.6;">{content}</p>'
            )

    # 未閉じのコードブロック
    if in_code_block:
        html_parts.append('</code></pre>')

    # テーブル行の連続を<table>タグで囲む
    result = '\n'.join(html_parts)
    result = _wrap_table_rows(result)

    return result


def _html_escape(text: str) -> str:
    """HTMLエスケープ"""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _apply_inline(text: str) -> str:
    """インラインMarkdown変換"""
    # HTMLエスケープ（コード以外のタグ注入防止）
    # ただし、既にHTMLが含まれていないテキスト向け
    text = _html_escape(text)

    # Bold: **text**
    text = re.sub(
        r'\*\*(.+?)\*\*',
        r'<strong style="color:#ffffff;">\1</strong>',
        text
    )
    # Italic: *text* (Boldと重複しないよう、**を除外)
    text = re.sub(
        r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
        r'<em>\1</em>',
        text
    )
    # Inline code: `code`
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#1a1a2e;padding:2px 6px;border-radius:3px;'
        r'font-family:Consolas,monospace;font-size:12px;color:#ff9800;">\1</code>',
        text
    )
    return text


def _wrap_table_rows(html: str) -> str:
    """連続する<tr>行を<table>で囲む"""
    lines = html.split('\n')
    result = []
    in_table = False

    for line in lines:
        if '<tr ' in line or line.strip().startswith('<tr>'):
            if not in_table:
                result.append(
                    '<table style="border-collapse:collapse;margin:8px 0;'
                    'width:100%;font-size:12px;">'
                )
                in_table = True
            result.append(line)
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            result.append(line)

    if in_table:
        result.append('</table>')

    return '\n'.join(result)
