# Claude Codeへの依頼文 — Helix AI Studio v8.0.0 "Living Bible"
# ※ BIBLE Manager + UI改善 + チャット改行修正 統合版

## 添付ファイル
   - `helix_v8_bible_manager_design.md`（BIBLE Manager設計書 — 1166行）"C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio\修正\helix_v8_bible_manager_design.md"
   - `helix_v8_bible_manager_prompt.md`（BIBLE Manager実装仕様 — コンパクト版）"C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio\修正\helix_v8_bible_manager_prompt.md"

---

## 依頼文（ここから貼り付け）

```
添付の2ファイルを最初から最後まで熟読してから作業を開始してください。

- helix_v8_bible_manager_design.md: BIBLE Manager機能の完全設計書（1166行）
- helix_v8_bible_manager_prompt.md: BIBLE Manager実装仕様のコンパクト版

## あなたへの依頼

Helix AI Studio を v7.2.0 "Polish" → v8.0.0 "Living Bible" にアップグレードしてください。
本アップグレードは以下の3本柱で構成されます:

1. **BIBLE Manager** — BIBLEファイルをアプリの第一級オブジェクトとして扱う新機能（添付設計書の通り）
2. **チャット表示の改行・Markdown対応** — Claude応答の改行が潰れる致命的バグの修正
3. **UI品質向上** — Cyberpunk Minimalテーマの洗練化、視覚的階層の強化

### 作業の進め方（厳守）

以下のフェーズ順で段階的に実装し、各フェーズ完了時に動作確認を行うこと。

---

#### フェーズ0: 現状把握（省略不可）

```bash
# バージョン確認（v7.2.0であること）
grep -n "APP_VERSION\|APP_CODENAME" src/utils/constants.py

# チャット表示関連のコードを把握（改行問題の原因特定）
grep -rn "setText\|setHtml\|setMarkdown\|setPlainText\|toHtml\|toPlainText\|QTextEdit\|QTextBrowser\|QLabel.*wrap\|insertHtml\|append\|setDocument" src/tabs/ src/widgets/ --include="*.py" | head -40

# チャット出力エリアの実装を特定
grep -rn "chat\|result\|output\|response.*area\|display.*area\|message.*area" src/tabs/helix_orchestrator_tab.py src/tabs/claude_tab.py --include="*.py" | head -30

# Markdown変換の有無
grep -rn "markdown\|QTextDocument\|html\|rich.*text" src/ --include="*.py" | head -20

# ファイル添付の現在の実装を把握
grep -rn "attach\|ファイルを添付\|file.*drop\|dropEvent\|_on_file" src/tabs/ --include="*.py"

# mixAIオーケストレータの構造を把握
cat src/backends/mix_orchestrator.py

# Phase 1プロンプト構築の現在の実装
grep -rn "def.*prompt\|def.*build.*prompt\|phase1\|phase_1" src/backends/ --include="*.py"

# 設定タブのUI構造を把握
grep -rn "class.*Tab\|addWidget\|addLayout\|QGroupBox\|setLayout" src/tabs/helix_orchestrator_tab.py | head -30

# 現在のBIBLEファイル配置
find . -name "BIBLE*.md" -maxdepth 3 2>/dev/null

# 現在のwidgets構成
ls -la src/widgets/

# スタイルシート関連
grep -rn "setStyleSheet\|stylesheet\|\.qss\|QSS\|palette" src/ --include="*.py" | head -30

# ボタンスタイルの現状
grep -rn "QPushButton\|btn.*style\|button.*style" src/tabs/ src/widgets/ --include="*.py" | head -20

# 添付ファイルの管理変数とクリア処理
grep -rn "_attached\|attached_files\|_attachments\|file_list" src/ --include="*.py"
grep -rn "def.*send\|def.*submit\|\.clear()" src/tabs/ --include="*.py" | head -20
grep -rn "attach.*widget\|file.*label\|file.*chip" src/ --include="*.py"

# soloAIのステージUI関連
grep -rn "S0\|S1\|S2\|S3\|S4\|S5\|Intake\|stage\|ステージ\|依頼受領\|工程" src/tabs/claude_tab.py
grep -rn "Prev\|Next\|工程リセット" src/tabs/claude_tab.py

# 実行中表示
grep -rn "生成中\|実行中\|running\|processing\|progress" src/tabs/ --include="*.py" | head -20

# 会話継続パネル
grep -rn "会話継続\|continue\|resume\|中断\|interrupt" src/ --include="*.py"

# ステータスバー
grep -rn "statusBar\|status_bar\|setStatusTip\|showMessage" src/ --include="*.py"
```

上記の結果を全て確認し、以下を報告してから実装を開始すること:
- チャット出力がどのウィジェット（QTextEdit? QLabel? QTextBrowser?）で表示されているか
- 改行が潰れる原因（setText vs setHtml、\n vs <br>の問題等）
- ファイル添付処理がどの関数で行われているか
- mix_orchestrator.pyのPhase 1プロンプト構築箇所
- 現在のスタイルシート適用方法

---

#### フェーズ1: チャット表示の改行・Markdown対応（最優先バグ修正）

現在、Claude CLIの応答がチャットエリアに表示される際、改行が全て潰れて
一塊のテキストになっている。これはユーザー体験を著しく損なう致命的な問題。

**修正方針:**

A) 応答テキストの表示にMarkdown→HTMLレンダリングを導入:
   ```python
   import re

   def markdown_to_html(text: str) -> str:
       """簡易Markdown→HTML変換（外部ライブラリ不要版）"""
       lines = text.split('\n')
       html_parts = []
       in_code_block = False
       code_lang = ""

       for line in lines:
           # コードブロック
           if line.startswith('```'):
               if in_code_block:
                   html_parts.append('</code></pre>')
                   in_code_block = False
               else:
                   code_lang = line[3:].strip()
                   html_parts.append(
                       f'<pre style="background:#1a1a2e;border:1px solid #333;'
                       f'border-radius:6px;padding:12px;margin:8px 0;'
                       f'font-family:Consolas,monospace;font-size:13px;'
                       f'color:#e0e0e0;overflow-x:auto;"><code>'
                   )
                   in_code_block = True
               continue

           if in_code_block:
               # コードブロック内はHTMLエスケープのみ
               escaped = line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
               html_parts.append(escaped + '\n')
               continue

           # 見出し
           if line.startswith('### '):
               html_parts.append(
                   f'<h3 style="color:#00d4ff;margin:16px 0 8px;'
                   f'font-size:15px;border-bottom:1px solid #333;'
                   f'padding-bottom:4px;">{line[4:]}</h3>'
               )
           elif line.startswith('## '):
               html_parts.append(
                   f'<h2 style="color:#00d4ff;margin:20px 0 10px;'
                   f'font-size:17px;border-bottom:1px solid #444;'
                   f'padding-bottom:6px;">{line[3:]}</h2>'
               )
           elif line.startswith('# '):
               html_parts.append(
                   f'<h1 style="color:#00ffcc;margin:24px 0 12px;'
                   f'font-size:20px;">{line[2:]}</h1>'
               )
           # リスト
           elif line.strip().startswith('- ') or line.strip().startswith('* '):
               content = line.strip()[2:]
               indent = len(line) - len(line.lstrip())
               margin = 8 + indent * 4
               html_parts.append(
                   f'<div style="margin-left:{margin}px;padding:2px 0;">'
                   f'<span style="color:#00d4ff;">●</span> {apply_inline(content)}</div>'
               )
           elif re.match(r'^\d+\.\s', line.strip()):
               content = re.sub(r'^\d+\.\s', '', line.strip())
               html_parts.append(
                   f'<div style="margin-left:12px;padding:2px 0;">{apply_inline(content)}</div>'
               )
           # 空行
           elif line.strip() == '':
               html_parts.append('<div style="height:8px;"></div>')
           # 通常テキスト
           else:
               html_parts.append(f'<p style="margin:4px 0;line-height:1.6;">{apply_inline(line)}</p>')

       return '\n'.join(html_parts)

   def apply_inline(text: str) -> str:
       """インラインMarkdown変換"""
       # Bold
       text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#ffffff;">\1</strong>', text)
       # Italic
       text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
       # Inline code
       text = re.sub(
           r'`([^`]+)`',
           r'<code style="background:#1a1a2e;padding:2px 6px;border-radius:3px;'
           r'font-family:Consolas,monospace;font-size:12px;color:#ff9800;">\1</code>',
           text
       )
       return text
   ```

B) 応答をチャットエリアに表示する箇所を修正:
   - `setText(response)` → `setHtml(markdown_to_html(response))`
   - または `QTextBrowser` を使用し `.setHtml()` で表示
   - `QTextEdit` を使用している場合は `setReadOnly(True)` + `setHtml()`

C) soloAIタブの応答表示も同様に修正

D) ユーザー入力は改行をそのまま保持（Ctrl+Enterで送信、Enterで改行）

**重要**: markdown_to_html()は `src/utils/markdown_renderer.py` として独立ファイルにし、
mixAI・soloAI両方から呼び出せるようにすること。

**フェーズ1完了確認:**
```bash
# markdown_renderer.pyが作成されたこと
test -f src/utils/markdown_renderer.py && echo "OK" || echo "MISSING"

# 両タブから呼び出されていること
grep -rn "markdown_to_html\|markdown_renderer" src/tabs/ --include="*.py"

# setTextがチャット応答表示に使われていないこと（setHtmlに置換済み）
grep -rn "setText.*response\|setText.*result\|setText.*output" src/tabs/helix_orchestrator_tab.py src/tabs/claude_tab.py

# テスト
python -c "
from src.utils.markdown_renderer import markdown_to_html
test = '# Title\n\nHello **bold** world\n\n\`\`\`python\nprint(42)\n\`\`\`\n\n- item1\n- item2'
html = markdown_to_html(test)
print('Contains <h1>:', '<h1' in html)
print('Contains <strong>:', '<strong' in html)
print('Contains <pre>:', '<pre' in html)
print('Contains bullet:', '●' in html)
print('Length:', len(html))
"
```

---

#### フェーズ2: UI品質向上

v7.2.0のUIは機能的だが「フラット」で視覚的な階層感が弱い。
以下の改善を実施して、プロフェッショナルなCyberpunk aesthetic を実現する。

**改善A: セクションカードデザイン**

設定タブの各セクション（Claude設定、Ollama接続、3Phase実行設定等）を
カード風のコンテナで囲み、視覚的なグルーピングを明確にする:

```python
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
```

**改善B: ボタンの統一スタイル**

現在のボタンはフラットで機能ごとの区別がしにくい。
プライマリ/セカンダリ/デンジャーの3段階に分けてスタイリング:

```python
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
    }
"""
```

**改善C: Phaseインジケーターの洗練化**

現在の `● P1:Claude計画 → P2:ローカルLLM → P3:Claude統合` はプレーンテキスト。
これをプログレスバー風のビジュアルインジケーターに改善:

```python
class PhaseIndicator(QWidget):
    """3Phase実行状態の視覚的インジケーター"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phases = [
            ("P1", "Claude計画", "#00d4ff"),
            ("P2", "ローカルLLM", "#00ff88"),
            ("P3", "Claude統合", "#ff9800"),
        ]
        self.current_phase = -1  # -1=未実行
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        for i, (label, desc, color) in enumerate(self.phases):
            # Phase ノード
            node = QFrame()
            node.setFixedSize(180, 36)
            node.setStyleSheet(f"""
                QFrame {{
                    background: #1a1a2e;
                    border: 2px solid #333;
                    border-radius: 18px;
                }}
            """)
            node_layout = QHBoxLayout(node)
            node_layout.setContentsMargins(8, 0, 8, 0)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: #555; font-size: 10px;")
            dot.setFixedWidth(16)

            text = QLabel(f"{label}: {desc}")
            text.setStyleSheet("color: #888; font-size: 11px;")

            node_layout.addWidget(dot)
            node_layout.addWidget(text)

            layout.addWidget(node)

            # コネクタ矢印（最後以外）
            if i < len(self.phases) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #444; font-size: 14px;")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setFixedWidth(30)
                layout.addWidget(arrow)

        setattr(self, '_nodes', layout)

    def set_active_phase(self, phase_index: int):
        """アクティブフェーズを設定（0=P1, 1=P2, 2=P3）"""
        self.current_phase = phase_index
        # 実装: ノードのボーダー色とドット色をアクティブカラーに変更
        # 完了フェーズは ✓ アイコンに変更
```

**改善D: チャットエリアのメッセージバブル**

mixAIの結果表示エリアとsoloAIのチャットエリアで、
ユーザーメッセージとAI応答を視覚的に区別する:

```python
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
```

**改善E: 入力エリアの改善**

mixAIの入力エリアにプレースホルダー例文が表示されるのは良いが、
soloAIの入力エリアが地味すぎる。入力フォーカス時のハイライトを追加:

```python
INPUT_AREA_STYLE = """
    QTextEdit {
        background: #0a0a1a;
        border: 1px solid #2a2a3e;
        border-radius: 8px;
        padding: 12px;
        color: #e0e0e0;
        font-size: 13px;
        selection-background-color: #00d4ff44;
    }
    QTextEdit:focus {
        border: 1px solid #00d4ff;
        box-shadow: 0 0 8px rgba(0, 212, 255, 0.3);
    }
"""
```

**改善F: タブバーの洗練化**

現在のタブバー（mixAI / soloAI / 一般設定）の下線が細い。
アクティブタブをより目立たせる:

```python
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
"""
```

**改善G: スクロールバーのカスタマイズ**

デフォルトのスクロールバーがテーマに合っていない。細いカスタムスクロールバーに:

```python
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
    QScrollBar::add-line, QScrollBar::sub-line {
        height: 0;
    }
"""
```
**改善H: 添付ファイルの送信後クリア**

現在、チャット送信時にテキスト入力欄はクリアされるが、添付ファイル表示が
残ったまま。次回送信時に意図せず同じファイルが再送される可能性がある。

修正内容:
- 送信ボタン押下時、テキストのクリアと同時に添付ファイルリストもクリアする
- 添付ファイルの内部リスト(self._attached_files等)もリセットする
- soloAI/mixAI両方で同じ修正を適用

```python
def _on_send(self):
    """送信ボタンのハンドラ"""
    # ... 既存の送信処理 ...

    # テキストクリア（既存）
    self.input_area.clear()

    # 添付ファイルクリア（追加）
    self._attached_files.clear()          # 内部リスト
    self._update_attachment_display()     # UIの添付ファイル表示を更新
    # または直接:
    # for widget in self._attachment_widgets:
    #     widget.deleteLater()
    # self._attachment_widgets.clear()
```

**改善I: 送信済みメッセージに添付ファイル名を明示**

チャット履歴上の「ユーザー」メッセージにテキストのみ表示され、
どのファイルを添付したか分からない。添付ファイルがある場合は
メッセージの先頭にファイル名を表示する。

```python
def _format_user_message(self, text: str, attachments: list) -> str:
    """ユーザーメッセージのフォーマット（添付ファイル名付き）"""
    if not attachments:
        return text

    # 添付ファイル表示を先頭に追加
    file_names = [os.path.basename(f) for f in attachments]
    attachment_html = ''.join(
        f'<span style="background:#1a2a3e;border:1px solid #00d4ff;'
        f'border-radius:4px;padding:2px 8px;margin:2px 4px 2px 0;'
        f'font-size:11px;color:#00d4ff;display:inline-block;">'
        f'📎 {name}</span>'
        for name in file_names
    )
    return f'<div style="margin-bottom:8px;">{attachment_html}</div>{text}'
```

表示イメージ:
```
┌─────────────────────────────────────────────┐
│ 📎 helix_v8_bible_manager_design.md         │
│ 📎 helix_v8_bible_manager_prompt.md         │
│                                             │
│ 添付の2ファイルを熟読してから作業を...       │
└─────────────────────────────────────────────┘
```

**重要**: 改善Hと改善Iは、フェーズ0の現状把握で添付ファイル関連の
コードを特定した後に実装すること。具体的には以下を調査:

```bash
# 添付ファイルの管理変数を特定
grep -rn "_attached\|attached_files\|file_list\|_attachments" src/ --include="*.py"

# 送信ハンドラでのクリア処理を確認
grep -rn "def.*send\|def.*submit\|clear()\|\.clear()" src/tabs/ --include="*.py"

# ファイル添付UIの構築
grep -rn "attach.*widget\|file.*label\|file.*display" src/ --include="*.py"


```
### 改善J: soloAIステージUIの整理

soloAIチャットタブ上部の以下のUI要素は、v6.x時代の「ステージベース」
ワークフロー（S0:依頼受領→S1:分析→...→S5:完了）の残骸であり、
v7.x以降のClaude CLI直接対話方式では実質的に機能していない。

**現状のUI要素（soloAIチャットタブ上部）:**
```
┌─────────────────────────────────────────────────────────┐
│ S0: 依頼受領 (Intake)                              0%   │
│ ユーザーからの依頼を受領し、要件を整理します。          │
│ ◀ Prev    Next ▶              🔄 工程リセット           │
└─────────────────────────────────────────────────────────┘
```

**修正方針: ステージUIをコンパクトなステータスバーに置換**

S0-S5のステージ遷移は削除し、代わりに以下のシンプルなステータス表示に置換:

```python
class SoloAIStatusBar(QWidget):
    """soloAI実行状態のシンプルな表示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # 実行状態インジケーター
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #888; font-size: 10px;")
        self.status_dot.setFixedWidth(16)
        layout.addWidget(self.status_dot)

        # ステータステキスト
        self.status_label = QLabel("待機中")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 新規セッションボタン（これは有用なので残す）
        self.btn_new_session = QPushButton("🔄 新規セッション")
        layout.addWidget(self.btn_new_session)

    def set_status(self, status: str, color: str = "#888"):
        """
        status: "waiting" / "running" / "completed" / "error" / "interrupted"
        """
        colors = {
            "waiting": ("#888", "待機中"),
            "running": ("#00d4ff", "Claude CLI 実行中..."),
            "completed": ("#00ff88", "完了"),
            "error": ("#ff4444", "エラー"),
            "interrupted": ("#ff8800", "中断 — 「続行」で再開可能"),
        }
        c, text = colors.get(status, ("#888", status))
        self.status_dot.setStyleSheet(f"color: {c}; font-size: 10px;")
        self.status_label.setStyleSheet(f"color: {c}; font-size: 12px;")
        self.status_label.setText(text)
```

**削除する要素:**
- S0-S5ステージ表示ラベル
- 「◀ Prev」「Next ▶」ボタン
- 0%プログレス表示
- 「🔄 工程リセット」ボタン
- ステージ説明テキスト（「ユーザーからの依頼を受領し...」）

**残す/改善する要素:**
- 「🔄 新規セッション」ボタン（新しいステータスバーに移動）
- 認証/モデル/思考/MCP等のオプションバー（現状維持、位置を調整）


### 改善K: 実行中タスクの視認性向上

**問題**: ステータスバーの「Claude CLI経由で応答を生成中...」が小さすぎて
実行中であることに気づきにくい。

**修正**: チャットエリア内に「実行中」のインライン表示を追加:

```python
class ExecutionIndicator(QFrame):
    """チャットエリア内の実行中インジケーター"""

    def __init__(self, task_description: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #1a1a2e;
                border: 1px solid #00d4ff;
                border-radius: 8px;
                padding: 12px;
                margin: 8px;
            }
        """)
        layout = QHBoxLayout(self)

        # アニメーションドット（●○○ → ○●○ → ○○● のようなパルス）
        self.dots = QLabel("● ○ ○")
        self.dots.setStyleSheet("color: #00d4ff; font-size: 14px;")
        layout.addWidget(self.dots)

        # タスク説明
        self.task_label = QLabel(task_description)
        self.task_label.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(self.task_label)

        # 経過時間
        self.time_label = QLabel("0:00")
        self.time_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.time_label)

        layout.addStretch()

        # タイマー
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._start_time = None
        self._dot_index = 0

    def start(self):
        self._start_time = time.time()
        self._timer.start(500)  # 0.5秒ごとに更新

    def stop(self):
        self._timer.stop()

    def _update(self):
        # 経過時間更新
        elapsed = int(time.time() - self._start_time)
        minutes, seconds = divmod(elapsed, 60)
        self.time_label.setText(f"{minutes}:{seconds:02d}")

        # ドットアニメーション
        dots = ["● ○ ○", "○ ● ○", "○ ○ ●"]
        self._dot_index = (self._dot_index + 1) % 3
        self.dots.setText(dots[self._dot_index])
```

**表示イメージ（チャットエリア内）:**
```
┌──────────────────────────────────────────────┐
│ 👤 ユーザー                                   │
│ 📎 helix_v8_bible_manager_design.md           │
│ 📎 helix_v8_bible_manager_prompt.md           │
│ 添付の2ファイルを熟読してから作業を...        │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ ● ○ ○  Claude CLI 実行中...          3:42    │
└──────────────────────────────────────────────┘
```

実行完了後は ExecutionIndicator を削除し、AI応答メッセージに置換。


### 改善L: 中断・エラー時の表示改善

**問題**: 中断時に「会話継続」パネルと「はい」「続行」「実行」ボタンが
表示されるが、何が中断されたか/どうすれば再開できるかが不明瞭。

**修正**: 中断時のUI表示を明確化:

```python
class InterruptionBanner(QFrame):
    """中断時にチャットエリアに表示するバナー"""

    def __init__(self, reason: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #2a1a0a;
                border: 1px solid #ff8800;
                border-radius: 8px;
                padding: 12px;
                margin: 8px;
            }
        """)
        layout = QVBoxLayout(self)

        # 中断理由
        header = QLabel(f"⚠️ 処理が中断されました")
        header.setStyleSheet("color: #ff8800; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        reason_label = QLabel(reason)
        reason_label.setStyleSheet("color: #ccc; font-size: 12px;")
        reason_label.setWordWrap(True)
        layout.addWidget(reason_label)

        # アクションボタン
        btn_layout = QHBoxLayout()

        btn_continue = QPushButton("▶ 続行")
        btn_continue.setStyleSheet(PRIMARY_BTN)  # styles.pyから
        btn_continue.setToolTip("中断箇所から処理を再開します")
        btn_layout.addWidget(btn_continue)

        btn_retry = QPushButton("🔄 再実行")
        btn_retry.setStyleSheet(SECONDARY_BTN)
        btn_retry.setToolTip("最初から処理をやり直します")
        btn_layout.addWidget(btn_retry)

        btn_cancel = QPushButton("✕ キャンセル")
        btn_cancel.setStyleSheet(DANGER_BTN)
        btn_cancel.setToolTip("処理を中止してチャットに戻ります")
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)
```

**表示イメージ:**
```
┌──────────────────────────────────────────────┐
│ ⚠️ 処理が中断されました                      │
│ Claude CLIの応答がタイムアウトしました。       │
│ 接続状態を確認してください。                   │
│                                              │
│ [▶ 続行]  [🔄 再実行]  [✕ キャンセル]       │
└──────────────────────────────────────────────┘
```

現在の「会話継続」パネル（右下に表示される小さなウィジェット）を
このバナーに置換する。


### 改善M: 認証/オプションバーのレイアウト調整

soloAIタブ上部の認証・オプションバーは有用だが、配置が詰まっている。

**現状:**
```
認証: CLI (Max/Proプラン) ☑ | 使用モデル: Claude Opus 4.6 | 思考: OFF | ■MCP ■差分表示 ■自動コンテキスト ■🐙許可 | 新規セッション
```

**改善**: 2行に分割して視認性を向上:
```
行1: 認証: CLI (Max/Proプラン) ☑ | 使用モデル: Claude Opus 4.6 (最高知能) | 思考: OFF
行2: ■MCP  ■差分表示 (Diff)  ■自動コンテキスト  ■🐙許可     [🔄 新規セッション]
```


**実装方法:**
- 上記スタイル定数を `src/utils/styles.py` にまとめて定義
- 各タブ/ウィジェットのコンストラクタで適用
- 既存の個別setStyleSheet()を可能な限りstyles.pyの定数に置換

**フェーズ2完了確認:**
```bash
# styles.pyが作成されたこと
test -f src/utils/styles.py && echo "OK" || echo "MISSING"

# 各タブでstyles.pyがimportされていること
grep -rn "from.*styles import\|import.*styles" src/tabs/ src/widgets/ --include="*.py"

# Phaseインジケーターが更新されていること
grep -rn "PhaseIndicator\|phase_indicator" src/ --include="*.py"

# 添付ファイルが送信後クリアされること（コードレベル確認）
grep -A5 "def.*send\|def.*submit" src/tabs/helix_orchestrator_tab.py src/tabs/claude_tab.py | grep -i "clear\|attach\|file"

# 送信済みメッセージに添付ファイル名が表示されること
grep -rn "attachment_html\|📎\|file_names\|_format_user_message" src/ --include="*.py"

# ステージUI関連が削除/置換されたこと
grep -c "S0\|Intake\|依頼受領\|工程リセット\|Prev.*Next" src/tabs/claude_tab.py
# → 大幅に減少していること（0が理想）

# 新UIウィジェットが存在すること
grep -rn "SoloAIStatusBar\|ExecutionIndicator\|InterruptionBanner" src/ --include="*.py"

# styles.pyにスタイルが集約されていること
grep -c "PRIMARY_BTN\|SECONDARY_BTN\|DANGER_BTN" src/utils/styles.py
```

---

#### フェーズ3: BIBLEコアモジュール（データ層）

※ 添付設計書の第2部 §2.1〜§2.2 に従い実装。

1. `src/bible/__init__.py` — 公開API
2. `src/bible/bible_schema.py` — スキーマ定義（16セクション型、テンプレート）
3. `src/bible/bible_parser.py` — パーサー（parse_header, parse_full）
4. `src/bible/bible_discovery.py` — 自動検索（discover, discover_from_prompt）

**フェーズ3完了確認:**
```bash
python -c "
from src.bible.bible_schema import BibleSectionType, BibleInfo, BIBLE_TEMPLATE
from src.bible.bible_parser import BibleParser
from src.bible.bible_discovery import BibleDiscovery
print('Schema types:', len(BibleSectionType))
print('Template length:', len(BIBLE_TEMPLATE))
"

python -c "
from src.bible.bible_parser import BibleParser
from pathlib import Path
for p in sorted(Path('.').glob('BIBLE/*.md')) + sorted(Path('.').glob('BIBLE_*.md')):
    info = BibleParser.parse_full(p)
    if info:
        print(f'{p.name}: v{info.version} - {info.line_count}行 - {len(info.sections)}セクション - 完全性{info.completeness_score:.0%}')
        missing = info.missing_required_sections
        if missing: print(f'  ⚠️ 不足: {[s.value for s in missing]}')
"
```

---

#### フェーズ4: Phase実行への統合（注入層）

5. `src/bible/bible_injector.py` — コンテキスト注入
6. `src/backends/mix_orchestrator.py` 修正 — set_bible_context, Phase 1/3注入

**フェーズ4完了確認:**
```bash
grep -n "bible_context\|set_bible_context\|BibleInjector\|project_context" src/backends/mix_orchestrator.py
```

---

#### フェーズ5: 自律管理 + UIパネル

7. `src/bible/bible_lifecycle.py` — 判定ロジック
8. `src/widgets/bible_panel.py` — 管理パネル（styles.pyのスタイル使用）
9. `src/widgets/bible_notification.py` — 検出通知
10. `src/tabs/helix_orchestrator_tab.py` 修正 — パネル配置、Discovery呼び出し

**BibleStatusPanelのスタイリング**: フェーズ2で作成したstyles.pyの
SECTION_CARD_STYLE, PRIMARY_BTN, SECONDARY_BTNを使用し、
他のセクションと統一感のあるデザインにすること。

**フェーズ5完了確認:**
```bash
python -c "
from src.widgets.bible_panel import BibleStatusPanel
from src.widgets.bible_notification import BibleNotificationWidget
print('UI widgets imported OK')
"
grep -n "BibleStatusPanel\|BibleDiscovery\|bible_notification" src/tabs/helix_orchestrator_tab.py
```

---

#### フェーズ6: 仕上げ

11. constants.py: APP_VERSION = "8.0.0", APP_CODENAME = "Living Bible"
12. config.jsonデフォルト値追加: bible_auto_discover, bible_auto_manage, bible_project_root
13. HelixAIStudio.spec hiddenimports追加（bible系8個 + markdown_renderer + styles）
14. BIBLE v8.0.0 更新

**最終受入条件:**
```bash
echo "=== バージョン ==="
grep "APP_VERSION\|APP_CODENAME" src/utils/constants.py

echo "=== 新規ファイル存在確認 ==="
for f in \
    src/utils/markdown_renderer.py \
    src/utils/styles.py \
    src/bible/__init__.py \
    src/bible/bible_schema.py \
    src/bible/bible_parser.py \
    src/bible/bible_discovery.py \
    src/bible/bible_injector.py \
    src/bible/bible_lifecycle.py \
    src/widgets/bible_panel.py \
    src/widgets/bible_notification.py; do
    test -f "$f" && echo "✓ $f" || echo "✗ $f MISSING"
done

echo "=== 全インポート ==="
python -c "
from src.utils.markdown_renderer import markdown_to_html
from src.utils.styles import PRIMARY_BTN, SECONDARY_BTN, SECTION_CARD_STYLE
from src.bible import BibleDiscovery, BibleParser, BibleInfo, BibleInjector
from src.bible.bible_lifecycle import BibleLifecycleManager, BibleAction
from src.widgets.bible_panel import BibleStatusPanel
from src.widgets.bible_notification import BibleNotificationWidget
print('All 10 new modules imported OK')
"

echo "=== Markdown変換テスト ==="
python -c "
from src.utils.markdown_renderer import markdown_to_html
test = '# Hello\n\nThis is **bold** and \`code\`.\n\n\`\`\`python\nprint(42)\n\`\`\`\n\n- item1\n- item2'
html = markdown_to_html(test)
assert '<h1' in html, 'Missing h1'
assert '<strong' in html, 'Missing strong'
assert '<pre' in html, 'Missing pre'
assert '●' in html, 'Missing bullet'
print('Markdown rendering OK')
"

echo "=== BIBLE検出テスト ==="
python -c "
from src.bible import BibleDiscovery
results = BibleDiscovery.discover('.')
for r in results: print(f'  Found: {r.file_path.name} v{r.version}')
"

echo "=== Orchestrator統合 ==="
grep -c "bible_context\|BibleInjector\|project_context\|bible_action\|markdown_to_html" src/backends/mix_orchestrator.py
# → 5行以上

echo "=== UIタブ統合 ==="
grep -c "BibleStatusPanel\|BibleDiscovery\|markdown_to_html\|styles\." src/tabs/helix_orchestrator_tab.py
# → 5行以上

echo "=== ビルド ==="
pyinstaller HelixAIStudio.spec --noconfirm
```

---

### 設計上の注意事項

1. **改行修正が最優先**: BIBLE ManagerよりもMarkdownレンダリング修正を先に実装すること。ユーザー体験に直結する。

2. **styles.pyは中央集権**: スタイル定数は全てstyles.pyに集約し、各ファイルでimportする。個別のsetStyleSheet()ハードコードを減らす。

3. **markdown_renderer.pyは軽量に**: 外部ライブラリ（markdown, mistune等）に依存しない純Pythonの簡易実装とする。PyInstallerビルドの依存関係を増やさない。

4. **BibleDiscoveryの探索順序**: カレント → 子(3階層) → 親(5階層遡上)。

5. **completeness_score**: 必須セクション存在率60% + 内容充実度平均40%。

6. **Phase 1注入**: `<project_context>`タグで囲む。Phase 2にはBIBLE不要。

7. **自律管理はユーザー承認必須**: BIBLEを勝手に書き換えない。必ず確認ダイアログ。

8. **エラーハンドリング**: BIBLE/Markdown機能が壊れてもアプリ全体に影響しないこと。

## 禁止事項

- フェーズ0の現状把握をスキップしないこと
- 改行問題を後回しにしないこと（フェーズ1で最初に修正）
- 外部Markdownライブラリを追加しないこと（純Python実装）
- 設計書のコード例をそのまま貼り付けず、既存コードの構造に適応させること
- スタイルをstyles.pyに集約せず個別ファイルにハードコードしないこと
- ビルド確認を省略しないこと
```

---
