# Helix AI Studio v11.0.0 "Smart History" 実装指示書（完全版 v3）

**作成日**: 2026-02-22
**改訂日**: 2026-02-22（Phase 6 大幅拡張 + NoScroll統一 + 領域別保存 + 日英i18n）
**対象**: Claude Code CLI による実装作業
**前提**: v10.1.0 "Unified Studio" → v11.0.0 "Smart History"
**ソース**: `helix_source_bundle.txt` (42ファイル, 30,569行)
**UI規則**: `HelixAIStudio_v11_UI_Design_Rules.md`（別紙）を必ず併読

> この文書はClaude Codeが実装作業を行う際の完全な設計仕様です。
> 各セクションにはファイル名・行番号・具体的な変更内容を記載しています。

---

## ⚠️ 全Phase共通の実装規則（v3追加）

以下の規則は全Phaseのコードに適用する。詳細は別紙 `HelixAIStudio_v11_UI_Design_Rules.md` を参照。

### R1. NoScrollウィジェット必須

```python
# ❌ 禁止
from PyQt6.QtWidgets import QComboBox, QSpinBox
combo = QComboBox()

# ✅ 必須
from src.widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
combo = NoScrollComboBox()
```

**新規ファイル**: `src/widgets/no_scroll_widgets.py`（マウスホイール無効化済みのQComboBox/QSpinBox/QDoubleSpinBox）

### R2. 領域別保存ボタン

各設定QGroupBoxの末尾に保存ボタンを配置。画面最下部の単一保存ボタンは廃止。

```python
from src.widgets.section_save_button import create_section_save_button
# QGroupBoxの末尾に追加
group_layout.addWidget(create_section_save_button(self._save_this_section))
```

**新規ファイル**: `src/widgets/section_save_button.py`

### R3. 日英i18n完全対応

全テキスト（ラベル、ボタン、ツールチップ、QMessageBox タイトル/本文）を`t()`経由で取得。ja.json / en.json 両方にキーを定義。

```python
# ❌ 禁止
QMessageBox.warning(self, "エラー", f"保存失敗: {e}")

# ✅ 必須
QMessageBox.warning(self, t('common.error'), t('desktop.ragTab.saveFailed', error=str(e)))
```

---

## 実装フェーズ概要

| Phase | 内容 | リスク | 推定変更量 |
|-------|------|--------|-----------|
| **Phase 1** | ②③⑦ UI削除・簡素化 | 低 | -400行 |
| **Phase 2** | ④ cloudAIタブ刷新 + 継続送信ボタン | 中 | +250行 |
| **Phase 3** | ① Historyタブ新設 + JSONL記録 | 中 | +500行 |
| **Phase 4** | ③' BIBLE クロスタブ統合 | 高 | +300行 |
| **Phase 5** | ⑤ localAI MCP (Python MCP SDK) | 高 | +600行 |
| **Phase 6** | ⑥ RAGタブ（旧:情報収集）全面刷新 | 高 | +1200行 (リライト) |

### Phase 6 v2 変更サマリ

| 変更項目 | 旧 (v1 spec) | 新 (v2 spec) |
|----------|-------------|-------------|
| タブ名 | 📚 情報収集 | 🧠 RAG |
| サブタブ名 | 実行 / 設定 | チャット / 設定 |
| チャットAIモデル | 固定表示 | cloudAI の `cloud_models.json` から選択可能 |
| 常駐LLMモデル | ministral-3:8b / qwen3-embedding:4b 固定 | ユーザー設定可能（3ロール選択） |
| RAG強化 | なし | LightRAG式インクリメンタルKG + HyPE + Reranker（自動動作） |
| 推定変更量 | +800行 | +1200行 |

---

# Phase 1: UI削除・簡素化 (②③⑦)

## 1-A. mixAI 3Phase表示クリーンアップ (②)

### 削除対象

**ファイル**: `src/tabs/helix_orchestrator_tab.py`

#### PhaseIndicator（P1→P2→P3→P4ボタン）
- **場所**: `_create_chat_layout()` 内、行11461-11463付近
- **操作**: PhaseIndicator ウィジェットの生成・addWidget をコメントアウトまたは削除
- **注意**: PhaseIndicator クラス定義自体（`src/widgets/` 内）は残してもよいが、import文も不要なら削除

#### NeuralFlowCompactWidget（"P1:計画立案 -- P2:役割実行..." テキスト）
- **場所**: `_create_chat_layout()` 内、行11470-11480付近
- **操作**: NeuralFlowCompactWidget の生成・addWidget を削除
- **注意**: `src/widgets/neural_flow_widget.py` の import 文も削除

#### 3Phase pipeline プレースホルダーテキスト
- **操作**: チャット画面の初期プレースホルダーから3Phase関連の説明文を削除

### 保持対象（削除しないこと）
- **ExecutionMonitorWidget**: LLM実行モニター（ストール検出機能あり）→ 維持
- **ツール実行ログエキスパンダー**: → 維持

---

## 1-B. mixAI設定削減 (③)

### 削除対象

**ファイル**: `src/tabs/helix_orchestrator_tab.py`

#### BIBLE Manager セクション
- **場所**: 行12050-12090付近
- **操作**: BibleStatusPanel 関連UI（グループボックス全体）を削除
- **注意**: ③'で新方式に置き換えるため、BibleInjector のバックエンドコードは残す

#### VRAM Budget Simulator
- **場所**: 行12093-12115付近
- **操作**: VRAMCompactWidget, open_simulator_btn を削除
- **関連ファイル**: `src/widgets/vram_simulator.py` → import 文を削除（行9547付近）
- **ファイル削除**: `src/widgets/vram_simulator.py` 自体を削除

#### GPU Monitor
- **場所**: 行12115-12210付近
- **操作**: gpu_group（QGroupBox）全体を削除

#### Phase 1/3 Search/Browse Mode コンボ
- **場所**: 行11750-11763付近
- **操作**: `mixai_search_mode_combo` を削除
- **バックエンド**: `mix_orchestrator.py` 行2764-2771 の search_mode ロジックを削除

#### Phase 1/3 Ollama モデル選択肢
- **操作**: Phase 1/3 のモデル選択をクラウドモデルのみに制限
- **注意**: Phase 2 のローカルモデル選択はそのまま維持

#### [☁API] ラベル
- **場所**: 行11709付近
- **操作**: ラベル削除

#### Adaptive thinking (effort_combo) - mixAI側
- **場所**: 行11724付近
- **操作**: `effort_combo` UI要素を削除
- **バックエンド**: `_build_cli_env()` の effort 処理は残す（config.json 隠し設定として）
- **関連**: `EffortLevel` クラス（constants.py 行54-74）は削除

---

## 1-C. 一般設定タブ整理 (⑦)

### 削除対象

**ファイル**: `src/tabs/general_settings_tab.py`（該当部分がmain_window.pyの場合あり）

#### MCPサーバー管理セクション
- **場所**: 行19528-19569付近
- **操作**: MCP管理UIを削除（各タブに分散するため）
- **注意**: バックエンド（`ClaudeCLIBackend` の `--mcp-server` 処理）は残す

#### Web UI カスタムサーバー設定
- **場所**: 行19876-19938付近
- **操作**: custom_server_label, URL/APIキー入力, テストボタン, ステータスラベルを削除
- **メソッド削除**: `_test_custom_server()`, `_load_custom_server_setting()`
- **保持**: Web UI start/stop, ポート設定, auto-start, Discord webhook

#### Memory & Knowledge Management
- **操作**: 以下の変更を実施
  - 全チェックボックスのデフォルトを ON に変更
  - Memory Risk Gate はUIから削除（常時ON、安全機能）
  - RAG enable は情報収集タブとの重複を解消（一般設定側を削除）
  - 残りの設定は折りたたみ可能な「Advanced Settings」グループに移動

### ファイル削除

| ファイル | 理由 |
|---------|------|
| `src/widgets/vram_simulator.py` | ③で不要 |
| `src/backends/openai_compat_backend.py` | ⑤⑦で不要（使用箇所がないこと要確認） |
| `config/custom_server.json` | ⑤⑦で不要 |

---

# Phase 2: cloudAIタブ刷新 + 継続送信ボタン (④ + A8)

## 2-A. Adaptive thinking UI削除

**ファイル**: `src/tabs/claude_tab.py`

### 削除対象
- **場所**: 行14850-14858付近
- **操作**: `effort_label` + `effort_combo` を削除
- **参照箇所**: `_send_via_cli()` 行16816-16824 の effort 取得ロジックを変更

### バックエンド維持（隠し設定化）
```python
# _send_via_cli() 内の effort 取得を config.json から読む形に変更
def _get_effort_from_config(self) -> str:
    """config.json から effort_level を読み取る（UI削除後の隠し設定）"""
    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("effort_level", "high")
    except Exception:
        pass
    return "high"  # デフォルトは high
```

---

## 2-B. モデルセレクタをチャット画面に移動

### 現状
- チャット画面: "New Session" + "History" ボタン + バージョンバッジ
- 設定タブ: モデル選択コンボ

### 変更
- **チャット画面上部バー**: `[Model: ▼ Claude Opus 4.6] [⚙ 詳細設定] [🔄 New]`
- **モデル選択**: `NoScrollComboBox` を使用（R1ルール）
- **"New Session" ボタン**: 「🔄 New」に変更、セッション管理と連動
- **"History" ボタン**: 削除（Phase 3で別タブに移行）

```python
from src.widgets.no_scroll_widgets import NoScrollComboBox

self.cloud_model_combo = NoScrollComboBox()
self._load_cloud_models_to_combo(self.cloud_model_combo)
```

### モデル管理用 JSON

**新規ファイル**: `config/cloud_models.json`

```json
{
  "models": [
    {
      "name": "Claude Opus 4.6",
      "model_id": "claude-opus-4-6",
      "command": "claude --model claude-opus-4-6",
      "builtin": true
    },
    {
      "name": "Claude Sonnet 4.6",
      "model_id": "claude-sonnet-4-6",
      "command": "claude --model claude-sonnet-4-6",
      "builtin": true
    },
    {
      "name": "Claude Opus 4.5",
      "model_id": "claude-opus-4-5-20250929",
      "command": "claude --model claude-opus-4-5-20250929",
      "builtin": true
    },
    {
      "name": "Claude Sonnet 4.5",
      "model_id": "claude-sonnet-4-5-20250929",
      "command": "claude --model claude-sonnet-4-5-20250929",
      "builtin": true
    },
    {
      "name": "GPT-5.3 Codex",
      "model_id": "gpt-5.3-codex",
      "command": "codex --model gpt-5.3-codex",
      "builtin": true
    }
  ]
}
```

### モデル管理ボタン

チャット画面のモデルセレクタ横に「管理」ボタンを配置。押下でダイアログを表示:
- **追加**: モデル名 + コマンド文字列を入力 → JSON追記
- **削除**: 選択モデルを削除（`builtin: true` は保護）
- **並び替え**: ↑↓ボタン or ドラッグ&ドロップ
- **更新**: JSON保存 → 全ドロップダウン（mixAI Phase 1/3/3.5/4 含む）を一括リフレッシュ

---

## 2-C. 「⚙ 詳細設定」ボタン

**動作**: OS デフォルトエディタで `~/.claude/settings.json` を開く

```python
def _open_claude_code_settings(self):
    """Claude Code settings.json をOSデフォルトエディタで開く"""
    import platform
    settings_path = Path.home() / ".claude" / "settings.json"

    # ファイルが存在しない場合はデフォルト値で作成
    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        default = {"effortLevel": "high", "permissions": {}, "env": {}}
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2, ensure_ascii=False)

    try:
        if platform.system() == "Windows":
            os.startfile(str(settings_path))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(settings_path)])
        else:
            subprocess.run(["xdg-open", str(settings_path)])
    except Exception as e:
        logger.error(f"Failed to open settings: {e}")
        QMessageBox.warning(self, "Error", f"Cannot open settings file:\n{e}")
```

---

## 2-D. 「継続送信」ボタン (A8: アプローチA セッション管理強化)

### UI変更

**ファイル**: `src/tabs/claude_tab.py` → `_create_input_area()` 行15570付近

送信ボタン行（btn_layout）に「継続送信」ボタンを追加:

```python
# 既存: 送信ボタン（新規セッション）
self.send_btn = QPushButton(t('common.send') + " ▶")
self.send_btn.setDefault(True)
self.send_btn.setToolTip(t('desktop.cloudAI.sendTooltip'))
btn_layout.addWidget(self.send_btn)

# 【v11.0.0 新規】継続送信ボタン（セッション維持）
self.continue_send_btn_main = QPushButton("📌 " + t('desktop.cloudAI.continueSendMain'))
self.continue_send_btn_main.setToolTip(t('desktop.cloudAI.continueSendMainTooltip'))
self.continue_send_btn_main.setEnabled(False)  # 初回は無効
self.continue_send_btn_main.setStyleSheet("""
    QPushButton {
        background: #1a3a2a; color: #00ff88;
        border: 1px solid #00ff88; border-radius: 4px;
        padding: 6px 16px; font-weight: bold;
    }
    QPushButton:hover { background: #2a4a3a; }
    QPushButton:disabled {
        background: #1a1a2e; color: #555; border-color: #333;
    }
""")
btn_layout.addWidget(self.continue_send_btn_main)
```

### 新規プロパティ・メソッド

**ファイル**: `src/tabs/claude_tab.py`

```python
class ClaudeTab:
    def __init__(self, ...):
        ...
        self._claude_session_id: Optional[str] = None  # CLIセッションID

    def _on_continue_send_main(self):
        """継続送信ボタン押下時（セッション維持モード）"""
        message = self.input_field.toPlainText().strip()
        if not message:
            return

        can_send, guard_message = self._check_send_guard()
        if not can_send:
            QMessageBox.warning(self, t('desktop.cloudAI.sendBlockTitle'),
                f"{guard_message}\n\n{t('desktop.cloudAI.proceedWorkflowRetry')}")
            return

        self._send_message_with_session(message)
        self.input_field.clear()

    def _send_message_with_session(self, message: str):
        """セッション継続モードでCLI送信"""
        # _send_message() と同じ前処理を共有
        # ...（RAGロック判定、session_id確保、プロンプト前処理、メモリ注入等）

        # CLIバックエンド取得（既存ロジック流用）
        self._cli_backend = get_claude_cli_backend(
            working_dir, skip_permissions=skip_permissions, model=selected_model)

        # CLIWorkerThread を resume_session_id 付きで起動
        self._cli_worker = CLIWorkerThread(
            backend=self._cli_backend,
            prompt=processed_message,
            model=selected_model,
            working_dir=working_dir,
            effort_level=effort_level,
            resume_session_id=self._claude_session_id  # ← セッション継続の核心
        )
        self._cli_worker.sessionCaptured.connect(self._on_session_captured)
        self._cli_worker.chunkReceived.connect(self._on_cli_chunk)
        self._cli_worker.completed.connect(self._on_cli_response)
        self._cli_worker.errorOccurred.connect(self._on_cli_error)
        self._cli_worker.start()

    def _on_session_captured(self, session_id: str):
        """CLIからsession_idを受信"""
        self._claude_session_id = session_id
        self.continue_send_btn_main.setEnabled(True)
        short_id = session_id[:8]
        self.continue_send_btn_main.setText(f"📌 {t('desktop.cloudAI.continueSendMain')} ({short_id}...)")
        self.continue_send_btn_main.setToolTip(f"Session ID: {session_id}")
        logger.info(f"[ClaudeTab] Session captured: {session_id}")

    def _on_new_session(self):
        """新規セッション開始（既存メソッド拡張）"""
        self._claude_session_id = None
        self.continue_send_btn_main.setEnabled(False)
        self.continue_send_btn_main.setText("📌 " + t('desktop.cloudAI.continueSendMain'))
        # ... 既存のクリア処理 ...
```

### シグナル接続

```python
# _create_input_area() の末尾、行15748付近
self.send_btn.clicked.connect(self._on_send)
self.continue_send_btn_main.clicked.connect(self._on_continue_send_main)  # 新規
```

### バックエンド変更

**ファイル**: `src/backends/claude_cli_backend.py`

#### ClaudeCLIBackend._build_command() 拡張

```python
def _build_command(self, extra_options=None, use_continue=False,
                   resume_session_id=None) -> List[str]:
    claude_cmd = find_claude_command()
    cmd = [claude_cmd, "-p"]

    model_id = self._get_model_id()
    if model_id:
        cmd.extend(["--model", model_id])

    # v11.0.0: セッション復元（--resume）
    if resume_session_id:
        cmd.extend(["--resume", resume_session_id])
    elif use_continue:
        cmd.append("--continue")

    # v11.0.0: JSON出力でsession_id取得
    cmd.extend(["--output-format", "json"])

    if self._skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    if extra_options:
        cmd.extend(extra_options)

    return cmd
```

#### レスポンスパース（session_id 抽出）

`send()` メソッド内で stdout を JSON パースし、`session_id` を `metadata` に格納:

```python
# send() メソッド内、stdout 収集後（行1830付近以降）
try:
    import json as _json
    response_json = _json.loads("".join(stdout_data))
    captured_session_id = response_json.get("session_id")
    if captured_session_id:
        metadata["session_id"] = captured_session_id
except (json.JSONDecodeError, ValueError):
    # JSON出力でない場合はテキストとして処理（既存動作を維持）
    pass
```

#### CLIWorkerThread 拡張

```python
class CLIWorkerThread(QThread):
    chunkReceived = pyqtSignal(str)
    completed = pyqtSignal(BackendResponse)
    sessionCaptured = pyqtSignal(str)   # v11.0.0: session_id通知
    errorOccurred = pyqtSignal(str)

    def __init__(self, backend, prompt, model=None, working_dir=None,
                 effort_level="default", resume_session_id=None, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._prompt = prompt
        self._model = model
        self._working_dir = working_dir
        self._effort_level = effort_level
        self._resume_session_id = resume_session_id  # v11.0.0
        self._full_response = ""
        self._start_time = None

    def run(self):
        ...
        request = BackendRequest(
            session_id="cli_session",
            phase="S4",
            user_text=self._prompt,
            toggles={},
            context={
                "resume_session_id": self._resume_session_id  # v11.0.0
            }
        )
        response = self._backend.send(request)

        # v11.0.0: session_id 抽出・通知
        if response.metadata and "session_id" in response.metadata:
            self.sessionCaptured.emit(response.metadata["session_id"])

        self.completed.emit(response)
```

### 通常の「送信 ▶」ボタンとの連動

通常の「送信 ▶」（`_on_send` → `_send_via_cli`）もJSON出力に変更し、session_id を取得:
- `_send_via_cli()` も `CLIWorkerThread` の `sessionCaptured` シグナルを接続
- 初回送信で session_id を取得 → 「継続送信」ボタンが自動的に有効化

### MCP設定の分散配置 (⑦ cloudAI側)

cloudAI 設定サブタブに MCP チェックボックスを追加:

```python
# cloudAI 設定サブタブ内
mcp_group = QGroupBox(t('desktop.cloudAI.mcpSettings'))
mcp_layout = QVBoxLayout()

self.cloudai_mcp_filesystem = QCheckBox(t('desktop.settings.mcpFilesystem'))
self.cloudai_mcp_git = QCheckBox(t('desktop.settings.mcpGit'))
self.cloudai_mcp_brave = QCheckBox(t('desktop.settings.mcpBrave'))

mcp_layout.addWidget(self.cloudai_mcp_filesystem)
mcp_layout.addWidget(self.cloudai_mcp_git)
mcp_layout.addWidget(self.cloudai_mcp_brave)

# v11.0.0 R2: 領域別保存ボタン
from src.widgets.section_save_button import create_section_save_button
mcp_layout.addWidget(create_section_save_button(self._save_cloudai_mcp_settings))

mcp_group.setLayout(mcp_layout)
```

保存先: `config/config.json` → `mcp_settings.cloudAI` セクション

### 「mixAI Phase Registration」削除

- **場所**: cloudAI設定サブタブ内、行14998-15010付近
- **操作**: `mixai_phase_group` セクション全体を削除
- **理由**: モデル管理機能（2-B）に統合

---

# Phase 3: Historyタブ新設 + JSONL記録 (①)

## 3-A. JSONL ログ記録

### 新規ファイル: `data/chat_history_log.jsonl`

追記専用（append-only）のログファイル。各行が1つのメッセージ:

```jsonl
{"timestamp":"2026-02-22T19:30:00","tab":"cloudAI","model":"claude-opus-4-6","role":"user","content":"プロジェクト構造を教えて","session_id":"abc123"}
{"timestamp":"2026-02-22T19:30:15","tab":"cloudAI","model":"claude-opus-4-6","role":"assistant","content":"このプロジェクトは...","session_id":"abc123","duration_ms":3200}
{"timestamp":"2026-02-22T19:45:00","tab":"mixAI","model":"phase2-qwen3","role":"user","content":"コードレビューして","session_id":"mix_001"}
```

### メタデータ生成: Pythonコードで直接記録（LLM不使用）

```python
# src/utils/chat_logger.py（新規）
import json
import time
from pathlib import Path
from datetime import datetime

class ChatLogger:
    """全タブ共通のJSONLチャットログ記録"""

    def __init__(self, log_path: str = None):
        self._log_path = Path(log_path or "data/chat_history_log.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_message(self, tab: str, model: str, role: str, content: str,
                    session_id: str = None, duration_ms: float = None,
                    extra: dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tab": tab,
            "model": model,
            "role": role,
            "content": content,
        }
        if session_id:
            entry["session_id"] = session_id
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 2)
        if extra:
            entry.update(extra)

        with open(self._log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def search(self, query: str = None, tab: str = None,
               limit: int = 50, offset: int = 0) -> list:
        """ログ検索（キーワード・タブフィルタ対応）"""
        results = []
        if not self._log_path.exists():
            return results

        with open(self._log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if tab and entry.get("tab") != tab:
                        continue
                    if query and query.lower() not in entry.get("content", "").lower():
                        continue
                    results.append(entry)
                except json.JSONDecodeError:
                    continue

        # 新しい順にソート
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results[offset:offset + limit]
```

### 各タブへのフック追加

#### cloudAI (`claude_tab.py`)
- `_send_message()` 内: ユーザーメッセージ送信時に `chat_logger.log_message()`
- `_on_cli_response()` 内: AI応答受信時に `chat_logger.log_message()`

#### mixAI (`helix_orchestrator_tab.py`)
- Phase 1/3 開始時: ユーザー入力をログ
- 各Phase完了時: 結果をログ

#### localAI (`local_ai_tab.py`)
- `_send_message()` 内: 送受信をログ

### 既存 ChatStore SQLite との関係

- **ChatStore は維持**: Web UI 連携用として引き続き使用
- **JSONL は追加記録**: ChatStore への書き込みと並行して JSONL にも記録
- **History タブは JSONL を参照**: ChatStore ではなく JSONL を読む

---

## 3-B. History タブ新設

### 新規ファイル: `src/tabs/history_tab.py`

### タブ構成変更

```
v10.1.0:
[mixAI] [cloudAI] [localAI] [情報収集] [一般設定]

v11.0.0:
[mixAI] [cloudAI] [localAI] [📜 History] [🧠 RAG] [一般設定]
```

### UI設計

```
┌─ 📜 History タブ ──────────────────────────────────────┐
│ ┌─ フィルタバー ─────────────────────────────────────┐ │
│ │ [🔍 検索: ____________] [Tab: ▼ All] [📅 日付]    │ │
│ │ [Sort: ▼ 新しい順]     [🔄 更新]                   │ │
│ └───────────────────────────────────────────────────┘ │
```

**フィルタバーのコンボは全て NoScrollComboBox を使用（R1ルール）**:

```python
from src.widgets.no_scroll_widgets import NoScrollComboBox

# タブフィルタ
self.tab_filter = NoScrollComboBox()
self.tab_filter.addItem(t('desktop.history.filterAll'), "all")
self.tab_filter.addItem("mixAI", "mixAI")
self.tab_filter.addItem("cloudAI", "cloudAI")
self.tab_filter.addItem("localAI", "localAI")
self.tab_filter.addItem(t('desktop.tabs.rag'), "rag")

# ソート順
self.sort_combo = NoScrollComboBox()
self.sort_combo.addItem(t('desktop.history.sortNewest'), "desc")
self.sort_combo.addItem(t('desktop.history.sortOldest'), "asc")
```
│                                                        │
│ ┌─ チャット一覧 ─────────────────────────────────────┐ │
│ │ 📅 2026-02-22                                      │ │
│ │ ┌──────────────────────────────────────────────┐   │ │
│ │ │ ☁ cloudAI | Opus 4.6 | 19:30                │   │ │
│ │ │ 👤 プロジェクト構造を教えて                    │   │ │
│ │ │ 🤖 このプロジェクトは...（展開→全文）          │   │ │
│ │ └──────────────────────────────────────────────┘   │ │
│ │ ┌──────────────────────────────────────────────┐   │ │
│ │ │ 🔀 mixAI | Phase2-qwen3 | 19:45             │   │ │
│ │ │ 👤 コードレビューして                          │   │ │
│ │ │ 🤖 レビュー結果...                            │   │ │
│ │ └──────────────────────────────────────────────┘   │ │
│ └───────────────────────────────────────────────────┘ │
│                                                        │
│ ┌─ 選択メッセージ詳細 ──────────────────────────────┐  │
│ │ （クリックで展開: 全文表示 + メタデータ）           │  │
│ │ [📋 コピー] [📎 他タブに引用]                      │  │
│ └───────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 各タブからの「New Session」「History」ボタン削除

#### cloudAI (`claude_tab.py`)
- **削除**: "New Session" ボタン → 「🔄 New」に変更（2-B に統合）
- **削除**: "History" ボタン → History タブに移行

#### mixAI (`helix_orchestrator_tab.py`)
- **削除**: "New Session" ボタン
- **削除**: "History" ボタン

#### localAI (`local_ai_tab.py`)
- **削除**: "History" ボタン（存在する場合）

### AI による過去チャット参照

History タブのデータを AI が参照できるようにする:
- ユーザーが「前回の会話を参照して」等と言った場合
- `ChatLogger.search()` でJSONLを検索し、関連する過去メッセージをコンテキストに注入

```python
def build_history_context(self, query: str, max_entries: int = 5) -> str:
    """過去チャットから関連コンテキストを構築"""
    results = self._chat_logger.search(query=query, limit=max_entries)
    if not results:
        return ""

    context_parts = ["<past_chat_history>"]
    for entry in results:
        context_parts.append(
            f"[{entry['timestamp']}] [{entry['tab']}] [{entry['model']}]\n"
            f"{entry['role']}: {entry['content'][:500]}"
        )
    context_parts.append("</past_chat_history>")
    return "\n".join(context_parts)
```

---

# Phase 4: BIBLE クロスタブ統合 (③')

## 設計方針

BIBLEボタンの目的:
1. **AIにBIBLEの記載規則を把握させる**（全文注入ではない）
2. **AIが自律的にBIBLEを新規作成・更新する**（条件: 既存BIBLE有り or UI表示物の新規作成時）

## 4-A. BibleContextMixin（共有ロジック）

### 新規ファイル: `src/mixins/bible_context_mixin.py`

```python
class BibleContextMixin:
    """全タブ共通のBIBLE連携ミックスイン"""

    BIBLE_RULES_PROMPT = """
あなたはBIBLE（Build Information Base for Lifecycle Engineering）の管理を担当します。

## BIBLEの記載規則
- ファイル名: BIBLE_<プロジェクト名>_<バージョン>.md
- 構成: プロジェクト概要、タブ構成図、Phase一覧、新規ファイル一覧、Changelog、設定ファイル構成、技術スタック
- バージョニング: セマンティックバージョニング準拠
- 更新タイミング: 機能追加・変更・削除のたびに更新

## 自律的な判断基準
以下の場合、BIBLEの新規作成または更新を実行してください:
1. 既存のBIBLEファイルが存在する場合 → 変更内容を反映して更新
2. UI表示物（アプリ等）を新規作成する場合 → 新しいBIBLEを作成
3. 上記以外 → BIBLEの作成・更新は不要
"""

    def _get_bible_path(self) -> Optional[Path]:
        """BIBLEフォルダ内の最新BIBLEファイルを取得"""
        bible_dir = Path("BIBLE")
        if not bible_dir.exists():
            return None
        bible_files = sorted(bible_dir.glob("BIBLE_*.md"), reverse=True)
        return bible_files[0] if bible_files else None

    def _build_bible_rules_context(self) -> str:
        """BIBLEの記載規則コンテキストを構築（全文ではなく規則のみ）"""
        context = self.BIBLE_RULES_PROMPT

        bible_path = self._get_bible_path()
        if bible_path:
            try:
                with open(bible_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                headings = [l.strip() for l in lines if l.startswith('#')]
                context += f"\n\n## 既存BIBLE構造 ({bible_path.name})\n"
                context += "\n".join(headings)
            except Exception:
                pass

        return context

    def _inject_bible_to_prompt(self, prompt: str) -> str:
        """プロンプトにBIBLE規則コンテキストを注入"""
        bible_context = self._build_bible_rules_context()
        return f"<bible_context>\n{bible_context}\n</bible_context>\n\n{prompt}"
```

## 4-B. 各タブへの「📖 BIBLE」ボタン追加

### 共通UI

各タブのボタン行（📎添付, ✂スニペット等の並び）に追加:

```python
self.bible_btn = QPushButton("📖 BIBLE")
self.bible_btn.setCheckable(True)  # トグルボタン
self.bible_btn.setChecked(False)
self.bible_btn.setToolTip(t('desktop.common.bibleToggleTooltip'))
self.bible_btn.setStyleSheet("""
    QPushButton { background: transparent; color: #ffa500;
        border: 1px solid #ffa500; border-radius: 4px;
        padding: 4px 12px; font-size: 11px; }
    QPushButton:checked { background: rgba(255, 165, 0, 0.2);
        border: 2px solid #ffa500; font-weight: bold; }
    QPushButton:hover { background: rgba(255, 165, 0, 0.1); }
""")
btn_layout.addWidget(self.bible_btn)
```

### 各タブの送信処理への統合

```python
# _send_message() 内で BIBLE ボタン状態を確認
if hasattr(self, 'bible_btn') and self.bible_btn.isChecked():
    processed_message = self._inject_bible_to_prompt(processed_message)
```

### 対象タブ
- **cloudAI**: `_send_via_cli()` のプロンプトに注入
- **mixAI**: Phase 1/3 のシステムプロンプトに注入（既存の `BibleInjector` を規則注入方式に変更）
- **localAI**: Ollama API の system message に注入

---

# Phase 5: localAI MCP (Python MCP SDK) (⑤)

## 5-A. モジュール構成

### 新規ディレクトリ: `src/mcp/`

```
src/mcp/
├── __init__.py
├── server_manager.py      # McpServerManager: stdio接続管理
├── catalog.py             # McpCatalog: tools/resources レジストリ
├── tool_adapter.py        # ToolAdapterOllama: MCP schema → Ollama tools変換
├── dispatcher.py          # ToolCallDispatcher: tool_calls → MCP実行
└── policy.py              # PolicyEngine: allowlist/パス制限/確認
```

### 依存パッケージ

```bash
pip install mcp --break-system-packages
```

## 5-B. McpServerManager

```python
# src/mcp/server_manager.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class McpServerManager:
    """MCPサーバ接続管理（stdio方式）"""

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}
        self._configs: dict = {}

    async def connect(self, server_id: str, command: str, args: list = None):
        """MCPサーバに接続"""
        params = StdioServerParameters(command=command, args=args or [])
        read, write = await stdio_client(params).__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        self._sessions[server_id] = session

    async def list_tools(self, server_id: str) -> list:
        """接続済みサーバのツール一覧を取得"""
        session = self._sessions.get(server_id)
        if not session:
            return []
        result = await session.list_tools()
        return result.tools

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict):
        """ツールを実行"""
        session = self._sessions.get(server_id)
        if not session:
            raise RuntimeError(f"Server {server_id} not connected")
        return await session.call_tool(tool_name, arguments)

    async def disconnect_all(self):
        """全サーバから切断"""
        for session in self._sessions.values():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        self._sessions.clear()
```

## 5-C. ToolAdapterOllama

```python
# src/mcp/tool_adapter.py

class ToolAdapterOllama:
    """MCP tool schema → Ollama tools 形式に変換"""

    @staticmethod
    def convert(mcp_tools: list) -> list:
        """MCPツール定義をOllama tools形式に変換"""
        ollama_tools = []
        for tool in mcp_tools:
            ollama_tool = {
                "type": "function",
                "function": {
                    "name": f"mcp_{tool.name}",
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {
                        "type": "object", "properties": {}, "required": []
                    }
                }
            }
            ollama_tools.append(ollama_tool)
        return ollama_tools

    @staticmethod
    def merge_with_builtin(mcp_tools: list, builtin_tools: list) -> list:
        """MCPツールを既存のAGENT_TOOLSとマージ"""
        merged = list(builtin_tools)  # 既存ツールを先に
        merged.extend(mcp_tools)      # MCPツールを追加
        return merged
```

## 5-D. 既存ツール実行ループとの統合

**ファイル**: `src/backends/local_agent.py` + `src/tabs/local_ai_tab.py`

既存の `OllamaWorkerThread` の `_execute_tool()` を拡張:

```python
def _execute_tool(self, tool_name: str, arguments: dict) -> str:
    """ツールを実行（MCP対応拡張）"""

    # MCP ツールの場合（"mcp_" プレフィックス）
    if tool_name.startswith("mcp_"):
        actual_name = tool_name[4:]  # "mcp_" を除去
        server_id = self._find_server_for_tool(actual_name)
        if server_id:
            result = asyncio.run(
                self._mcp_manager.call_tool(server_id, actual_name, arguments)
            )
            return str(result)

    # 既存の組み込みツール
    if tool_name == "read_file":
        return self._tool_read_file(arguments)
    elif tool_name == "write_file":
        return self._tool_write_file(arguments)
    # ... 既存ツール処理 ...
```

## 5-E. localAI設定タブにMCPチェックボックス追加

```python
# localAI 設定サブタブ
mcp_group = QGroupBox(t('desktop.localAI.mcpSettings'))
mcp_layout = QVBoxLayout()

self.localai_mcp_filesystem = QCheckBox(t('desktop.settings.mcpFilesystem'))
self.localai_mcp_git = QCheckBox(t('desktop.settings.mcpGit'))
self.localai_mcp_brave = QCheckBox(t('desktop.settings.mcpBrave'))

mcp_layout.addWidget(self.localai_mcp_filesystem)
mcp_layout.addWidget(self.localai_mcp_git)
mcp_layout.addWidget(self.localai_mcp_brave)

# v11.0.0 R2: 領域別保存ボタン
from src.widgets.section_save_button import create_section_save_button
mcp_layout.addWidget(create_section_save_button(self._save_localai_mcp_settings))

mcp_group.setLayout(mcp_layout)
```

保存先: `config/config.json` → `mcp_settings.localAI` セクション

## 5-F. モデル能力表示の拡張

localAI設定タブのモデルテーブル列を拡張:

```
現在: [Name] [Size] [Modified]
変更: [Name] [Size] [Tools] [Vision] [Thinking] [Context]
```

データソース: Ollama `/api/show` エンドポイント:
- **Tools**: capabilities に "tools" があるか
- **Vision**: model_info に "projector" があるか
- **Thinking**: モデル名パターンマッチ（qwen3, devstral等）
- **Context**: `num_ctx` 値

## 5-G. モデル管理改善

### モデル追加
- 現在: テキスト入力 → `ollama pull`
- 変更: ポップアップ（モデル名 + サイズ指定） → `ollama pull model:size` → プログレス表示 → 完了後自動リスト更新

### モデル削除
- 現在: テーブル行選択 → 削除ボタン
- 変更: テーブルにチェックボックス列追加 → 複数選択 → 「Delete Selected」 → 確認ダイアログ

## 5-H. カスタムサーバー（OpenAI互換）削除

- **場所**: localAI設定サブタブ 行18526付近
- **操作**: カスタムサーバー管理セクション全体を削除
- **ファイル削除**: `src/backends/openai_compat_backend.py`, `config/custom_server.json`

---

# Phase 6: RAGタブ全面刷新 (⑥) — v2 大幅拡張

## 6-0. 変更概要

### 旧Phase 6（v1 spec）からの主な変更点

| 項目 | v1 | v2（本版） |
|------|-----|-----------|
| タブ表示名 | 📚 情報収集 | **🧠 RAG** |
| サブタブ「実行」 | 存続（名称そのまま） | **→「チャット」に改名、cloudAI風チャットUIに全面刷新** |
| チャットAIモデル | 固定1モデル | **`cloud_models.json` から選択可能（設定画面）** |
| 常駐LLM（3ロール） | `ministral-3:8b` / `qwen3-embedding:4b` ハードコード | **ユーザー選択可能（localAI Ollamaモデル一覧から3ロール指定）** |
| RAG強化 | なし | **LightRAG式KGマージ + HyPE + Reranker 自動適用** |
| 推定変更量 | +800行 | **+1200行** |

---

## 6-A. タブ名変更: 情報収集 → RAG

### 変更箇所

**ファイル**: `src/main_window.py`（タブ追加部分）

```python
# 旧
self.tab_widget.addTab(self.info_collection_tab, t('desktop.tabs.infoCollection'))

# 新
self.tab_widget.addTab(self.rag_tab, t('desktop.tabs.rag'))
```

**i18n**: `locales/ja.json` / `locales/en.json`

```json
// ja.json
"desktop.tabs.rag": "🧠 RAG"

// en.json
"desktop.tabs.rag": "🧠 RAG"
```

**クラス名変更**: `InformationCollectionTab` → `RagTab`

```python
# src/tabs/rag_tab.py（旧 information_collection_tab.py をリネーム）
class RagTab(QWidget):
    ...
```

### サブタブ名変更

```python
# 旧
self.sub_tab_widget.setTabText(0, t('desktop.infoTab.execSubTab'))     # "実行"
self.sub_tab_widget.setTabText(1, t('desktop.infoTab.settingsSubTab')) # "設定"

# 新
self.sub_tab_widget.setTabText(0, t('desktop.ragTab.chatSubTab'))      # "チャット"
self.sub_tab_widget.setTabText(1, t('desktop.ragTab.settingsSubTab'))  # "設定"
```

---

## 6-B. 「チャット」サブタブ — cloudAI風チャットUI

### リライト対象

**旧ファイル**: `src/tabs/information_collection_tab.py`（約1500行）の「実行」サブタブ部分
**新ファイル**: `src/tabs/rag_tab.py` → `_create_chat_subtab()` メソッド

### UI設計

```
┌─ 🧠 RAG ──────────────────────────────────────────────┐
│ [チャット] [設定]                                       │
├─ チャット サブタブ ────────────────────────────────────┤
│                                                        │
│ ┌─ ステータスバー ─────────────────────────────────┐  │
│ │ 📁 7 files (65.9KB) │ ✅ RAG 7/7 │ 🧠 842 nodes │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ 🤖 AI: 現在の状態です:                                  │
│     📁 7 ファイル (65.9KB)                              │
│     ✅ RAG: 7/7 構築済み                                │
│     🧠 Knowledge Graph: 842 nodes, 475 edges           │
│     💡 質問があればお聞きください。                       │
│        RAG構築・再構築もチャットで指示できます。          │
│                                                        │
│ 👤 User: このプロジェクトの主要な技術スタックは？         │
│                                                        │
│ 🤖 AI: RAGコンテキストを検索中...                       │
│     [検索結果: 3件のチャンクが関連]                       │
│     PyQt6をデスクトップUI、ReactをWeb UIに使用し...       │
│                                                        │
│ 👤 User: RAGを再構築して                                 │
│                                                        │
│ 🤖 AI: RAG構築を開始します...                           │
│     📋 プラン: 7ファイル → 推定12分                       │
│     [████████████░░░░] Step 4/8: TKGエッジ構築 (5:34)   │
│     ✅ 完了！842 nodes, 475 edges, 28 communities       │
│                                                        │
├────────────────────────────────────────────────────────┤
│ [入力フィールド                                    ]   │
│ [📁追加] [📊統計] [🔄再構築] [📋プラン]      [送信 ▶]  │
└────────────────────────────────────────────────────────┘
```

### 実装コード

```python
def _create_chat_subtab(self) -> QWidget:
    """チャットサブタブ（cloudAI風UI）"""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)

    # --- ステータスバー ---
    self.rag_status_bar = QLabel()
    self.rag_status_bar.setStyleSheet("""
        QLabel {
            background: #1a1a2e; color: #00d4ff;
            border: 1px solid #333; border-radius: 4px;
            padding: 6px 12px; font-size: 11px;
        }
    """)
    layout.addWidget(self.rag_status_bar)
    self._refresh_status_bar()

    # --- チャット表示エリア（QTextBrowser） ---
    self.chat_display = QTextBrowser()
    self.chat_display.setOpenExternalLinks(True)
    self.chat_display.setStyleSheet("""
        QTextBrowser {
            background: #0d1117; color: #e6edf3;
            border: 1px solid #333; border-radius: 4px;
            padding: 12px; font-size: 13px;
        }
    """)
    layout.addWidget(self.chat_display, stretch=1)

    # --- 入力エリア ---
    input_layout = QVBoxLayout()

    self.rag_input = QPlainTextEdit()
    self.rag_input.setMaximumHeight(80)
    self.rag_input.setPlaceholderText(
        t('desktop.ragTab.inputPlaceholder'))
    input_layout.addWidget(self.rag_input)

    # --- ボタン行 ---
    btn_layout = QHBoxLayout()

    # クイックアクションボタン群
    self.add_files_btn = QPushButton("📁 " + t('desktop.ragTab.addFiles'))
    self.add_files_btn.clicked.connect(self._add_files)
    btn_layout.addWidget(self.add_files_btn)

    self.stats_btn = QPushButton("📊 " + t('desktop.ragTab.stats'))
    self.stats_btn.clicked.connect(lambda: self._quick_action("stats"))
    btn_layout.addWidget(self.stats_btn)

    self.rebuild_btn = QPushButton("🔄 " + t('desktop.ragTab.rebuild'))
    self.rebuild_btn.clicked.connect(lambda: self._quick_action("rebuild"))
    btn_layout.addWidget(self.rebuild_btn)

    self.plan_btn = QPushButton("📋 " + t('desktop.ragTab.plan'))
    self.plan_btn.clicked.connect(lambda: self._quick_action("plan"))
    btn_layout.addWidget(self.plan_btn)

    btn_layout.addStretch()

    # 送信ボタン
    self.rag_send_btn = QPushButton(t('common.send') + " ▶")
    self.rag_send_btn.setDefault(True)
    self.rag_send_btn.clicked.connect(self._on_send)
    btn_layout.addWidget(self.rag_send_btn)

    input_layout.addLayout(btn_layout)
    layout.addLayout(input_layout)

    return widget
```

### チャットバックエンド: Claude CLI + RAGコンテキスト自動注入

```python
def _on_send(self):
    """チャット送信処理"""
    message = self.rag_input.toPlainText().strip()
    if not message:
        return
    self.rag_input.clear()

    # チャットにユーザーメッセージ表示
    self._append_chat("user", message)

    # コマンド判定（クイックアクションまたはAI問い合わせ）
    cmd = self._detect_command(message)
    if cmd:
        self._execute_command(cmd, message)
        return

    # RAGコンテキスト検索 → Claude CLIに送信
    self._send_to_claude_with_rag(message)

def _send_to_claude_with_rag(self, message: str):
    """RAGコンテキストを付与してClaude CLIに送信"""
    # 1. RAGコンテキスト検索（HelixMemoryManager経由）
    rag_context = ""
    if self._memory_manager:
        try:
            rag_context = self._memory_manager.build_context_for_solo(message)
        except Exception as e:
            logger.warning(f"RAG context build failed: {e}")

    # 2. プロンプト構築
    system_context = f"""あなたはRAG（Retrieval-Augmented Generation）アシスタントです。
以下のナレッジベースコンテキストを参照して質問に回答してください。
また、ユーザーがRAG構築や再構築を指示した場合は、適切なコマンドを提案してください。

{rag_context}"""

    full_prompt = f"{system_context}\n\nユーザーの質問: {message}"

    # 3. Claude CLI送信（cloudAIと同じCLIWorkerThread使用）
    selected_model = self._get_selected_cloud_model()
    self._cli_backend = get_claude_cli_backend(
        working_dir=str(Path(self._folder_path).parent),
        model=selected_model)

    self._cli_worker = CLIWorkerThread(
        backend=self._cli_backend,
        prompt=full_prompt,
        model=selected_model)
    self._cli_worker.completed.connect(self._on_claude_response)
    self._cli_worker.errorOccurred.connect(self._on_claude_error)
    self._cli_worker.start()

    self._append_chat("system", t('desktop.ragTab.searching'))

def _get_selected_cloud_model(self) -> str:
    """設定画面で選択されたCloudモデルIDを取得"""
    try:
        return self.rag_cloud_model_combo.currentData() or "claude-sonnet-4-5-20250929"
    except Exception:
        return "claude-sonnet-4-5-20250929"
```

### コマンド検出と実行

```python
def _detect_command(self, message: str) -> Optional[str]:
    """メッセージからコマンドを検出"""
    lower = message.lower().strip()
    patterns = {
        "rebuild": ["再構築", "rebuild", "rag構築", "rag build", "構築して"],
        "plan": ["プラン", "plan", "計画"],
        "stats": ["統計", "stats", "ステータス", "status", "状態"],
        "list": ["一覧", "list", "ファイル", "files"],
    }
    for cmd, keywords in patterns.items():
        if any(kw in lower for kw in keywords):
            return cmd
    return None

def _execute_command(self, cmd: str, original_message: str):
    """検出されたコマンドを実行"""
    if cmd == "rebuild":
        self._cmd_rebuild_rag()
    elif cmd == "plan":
        self._cmd_create_plan()
    elif cmd == "stats":
        self._cmd_show_stats()
    elif cmd == "list":
        self._cmd_list_files()

def _cmd_rebuild_rag(self):
    """RAG再構築（既存RAGBuilder使用）"""
    self._append_chat("assistant", t('desktop.ragTab.rebuildStarting'))
    # 既存の RAGBuilder (QThread) を起動
    self._rag_builder = RAGBuilder(
        folder_path=self._folder_path,
        db_path=self._db_path,
        time_limit_minutes=self._time_limit)
    self._rag_builder.signals.step_completed.connect(self._on_rag_step)
    self._rag_builder.signals.build_completed.connect(self._on_rag_complete)
    self._rag_builder.signals.step_progress.connect(self._on_rag_progress)
    self._rag_builder.start()
```

### クイックアクションボタン

```python
def _quick_action(self, action: str):
    """クイックアクションボタン押下時（定型メッセージを送信）"""
    messages = {
        "stats": t('desktop.ragTab.quickStats'),    # "現在のRAG統計を表示して"
        "rebuild": t('desktop.ragTab.quickRebuild'), # "RAGを再構築して"
        "plan": t('desktop.ragTab.quickPlan'),       # "RAG構築プランを作成して"
    }
    if action in messages:
        self.rag_input.setPlainText(messages[action])
        self._on_send()
```

---

## 6-C. 設定サブタブ — Claudeモデル選択 + ローカルLLM 3ロール選択

### UI設計

```
┌─ 設定 サブタブ ────────────────────────────────────────┐
│                                                        │
│ ┌─ チャットAI設定 ──────────────────────────────────┐  │
│ │ Claude モデル: [▼ Claude Sonnet 4.5          ]     │  │
│ │ ℹ cloud_models.json から読み込み                    │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─ ローカルLLMロール設定 ───────────────────────────┐  │
│ │                                                    │  │
│ │ 🔧 実行LLM（要約・KG構築）:                         │  │
│ │    [▼ command-a:latest            ]                │  │
│ │    推奨: 32B以上、長コンテキスト対応モデル           │  │
│ │                                                    │  │
│ │ ✅ 品質チェックLLM（検証・分類）:                    │  │
│ │    [▼ ministral-3:8b              ]                │  │
│ │    推奨: 8B程度の軽量高速モデル                      │  │
│ │                                                    │  │
│ │ 📐 Embeddingモデル:                                 │  │
│ │    [▼ qwen3-embedding:4b          ]                │  │
│ │    推奨: embedding専用モデル                         │  │
│ │                                                    │  │
│ │ [🔄 Ollamaモデル再読込]                             │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─ RAG構築設定 ─────────────────────────────────────┐  │
│ │ 制限時間: [▼ 90分  ] │ チャンクサイズ: [▼ 512   ] │  │
│ │ オーバーラップ: [▼ 64 ]                             │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─ RAG自動強化 ──────── ─────────────────────────────┐ │
│ │ ☑ 応答後に自動KG更新（LightRAG式）                  │ │
│ │ ☑ 仮想質問事前生成（HyPE）                          │ │
│ │ ☑ 検索結果リランキング                              │ │
│ │ ℹ 全機能はバックグラウンドで自動実行されます          │ │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─ 対象フォルダ ────────────────────────────────────┐  │
│ │ data/information_collection                        │  │
│ │ [📂 変更] [📄 ファイル一覧]                         │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│                            [💾 保存]                   │
└────────────────────────────────────────────────────────┘
```

### Claudeモデル選択の実装

```python
def _create_settings_subtab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)

    from src.widgets.no_scroll_widgets import NoScrollComboBox, NoScrollSpinBox
    from src.widgets.section_save_button import create_section_save_button

    # --- チャットAI設定 ---
    chat_ai_group = QGroupBox(t('desktop.ragTab.chatAiSettings'))
    chat_ai_layout = QFormLayout()

    self.rag_cloud_model_combo = NoScrollComboBox()
    self._load_cloud_models_to_combo(self.rag_cloud_model_combo)
    chat_ai_layout.addRow(
        t('desktop.ragTab.claudeModel'), self.rag_cloud_model_combo)

    chat_ai_group.setLayout(chat_ai_layout)
    # R2: 領域別保存ボタン
    chat_ai_layout.addRow("", create_section_save_button(self._save_rag_chat_ai_settings))
    layout.addWidget(chat_ai_group)

    # --- ローカルLLMロール設定 ---
    llm_role_group = QGroupBox(t('desktop.ragTab.localLlmRoles'))
    llm_role_layout = QFormLayout()
    # ... 以下6-D参照 ...

def _load_cloud_models_to_combo(self, combo: NoScrollComboBox):
    """cloud_models.json からモデル一覧を読み込みコンボに設定"""
    combo.clear()
    try:
        config_path = Path("config/cloud_models.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for model in data.get("models", []):
                combo.addItem(model["name"], model["model_id"])
    except Exception as e:
        logger.warning(f"Failed to load cloud models: {e}")
        # フォールバック
        combo.addItem("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929")
```

---

## 6-D. ローカルLLM 3ロール選択可能化

### 設計方針

現在ハードコードされている2つの定数を**ユーザー選択可能**に変更:

```python
# 旧（src/memory/memory_manager.py 行3730-3731）
EMBEDDING_MODEL = "qwen3-embedding:4b"   # 固定
CONTROL_MODEL = "ministral-3:8b"          # 固定

# 旧（src/rag/rag_executor.py 行6423-6424）
EMBEDDING_MODEL = "qwen3-embedding:4b"   # 固定
CONTROL_MODEL = "ministral-3:8b"          # 固定
```

これを**3ロール**に分離し、設定画面から変更可能にする:

| ロール | 用途 | デフォルト | 推奨要件 |
|--------|------|-----------|---------|
| **実行LLM** | TKGエンティティ抽出、RAPTOR要約、GraphRAGコミュニティ要約 | `command-a:latest` | 32B+、長コンテキスト |
| **品質チェックLLM** | Memory Risk Gate（抽出・検証）、要約・キーワード、検証クエリ | `ministral-3:8b` | 8B程度、高速応答 |
| **Embeddingモデル** | チャンクembedding、fact embedding、検索用embedding | `qwen3-embedding:4b` | embedding専用 |

### 設定UI実装

```python
    # --- ローカルLLMロール設定 ---
    llm_role_group = QGroupBox(t('desktop.ragTab.localLlmRoles'))
    llm_role_layout = QFormLayout()

    # 実行LLM
    self.exec_llm_combo = NoScrollComboBox()
    exec_hint = QLabel(t('desktop.ragTab.execLlmHint'))
    exec_hint.setStyleSheet("color: #888; font-size: 10px;")
    exec_container = QVBoxLayout()
    exec_container.addWidget(self.exec_llm_combo)
    exec_container.addWidget(exec_hint)
    exec_wrapper = QWidget()
    exec_wrapper.setLayout(exec_container)
    llm_role_layout.addRow(
        "🔧 " + t('desktop.ragTab.execLlm'), exec_wrapper)

    # 品質チェックLLM
    self.quality_llm_combo = NoScrollComboBox()
    quality_hint = QLabel(t('desktop.ragTab.qualityLlmHint'))
    quality_hint.setStyleSheet("color: #888; font-size: 10px;")
    quality_container = QVBoxLayout()
    quality_container.addWidget(self.quality_llm_combo)
    quality_container.addWidget(quality_hint)
    quality_wrapper = QWidget()
    quality_wrapper.setLayout(quality_container)
    llm_role_layout.addRow(
        "✅ " + t('desktop.ragTab.qualityLlm'), quality_wrapper)

    # Embeddingモデル
    self.embedding_combo = NoScrollComboBox()
    emb_hint = QLabel(t('desktop.ragTab.embeddingHint'))
    emb_hint.setStyleSheet("color: #888; font-size: 10px;")
    emb_container = QVBoxLayout()
    emb_container.addWidget(self.embedding_combo)
    emb_container.addWidget(emb_hint)
    emb_wrapper = QWidget()
    emb_wrapper.setLayout(emb_container)
    llm_role_layout.addRow(
        "📐 " + t('desktop.ragTab.embeddingModel'), emb_wrapper)

    # Ollamaモデル再読込ボタン
    refresh_btn = QPushButton("🔄 " + t('desktop.ragTab.refreshModels'))
    refresh_btn.clicked.connect(self._refresh_ollama_models)
    llm_role_layout.addRow("", refresh_btn)

    # R2: 領域別保存ボタン
    llm_role_layout.addRow("", create_section_save_button(self._save_rag_llm_roles))

    llm_role_group.setLayout(llm_role_layout)
    layout.addWidget(llm_role_group)
```

### Ollamaモデル読み込み

```python
def _refresh_ollama_models(self):
    """Ollama /api/tags からモデル一覧を取得し3コンボに反映"""
    try:
        import requests
        ollama_url = self._get_ollama_url()
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = sorted([m["name"] for m in resp.json().get("models", [])])

            for combo, default in [
                (self.exec_llm_combo, "command-a:latest"),
                (self.quality_llm_combo, "ministral-3:8b"),
                (self.embedding_combo, "qwen3-embedding:4b"),
            ]:
                current = combo.currentText()
                combo.clear()
                combo.addItems(models)
                # 現在値 or デフォルト値をセット
                idx = combo.findText(current if current else default)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.addItem(default)
                    combo.setCurrentText(default)
    except Exception as e:
        logger.warning(f"Ollama model refresh failed: {e}")
```

### バックエンド反映（CONTROL_MODEL / EMBEDDING_MODEL の動的化）

**新規ファイル**: `src/memory/model_config.py`

```python
"""ローカルLLMモデル設定の一元管理（v11.0.0）

全モジュール（memory_manager.py, rag_executor.py, rag_planner.py 等）は
このモジュールからモデル名を取得する。ハードコードを廃止。
"""
import json
from pathlib import Path

_DEFAULT_EXEC_LLM = "command-a:latest"
_DEFAULT_QUALITY_LLM = "ministral-3:8b"
_DEFAULT_EMBEDDING = "qwen3-embedding:4b"

def _load_rag_settings() -> dict:
    try:
        p = Path("config/app_settings.json")
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f).get("rag", {})
    except Exception:
        pass
    return {}

def get_exec_llm() -> str:
    """実行LLM（TKG構築、RAPTOR要約等）"""
    return _load_rag_settings().get("exec_llm", _DEFAULT_EXEC_LLM)

def get_quality_llm() -> str:
    """品質チェックLLM（Memory Risk Gate、検証等）"""
    return _load_rag_settings().get("quality_llm", _DEFAULT_QUALITY_LLM)

def get_embedding_model() -> str:
    """Embeddingモデル"""
    return _load_rag_settings().get("embedding_model", _DEFAULT_EMBEDDING)
```

**変更対象ファイル**（全箇所でハードコードを置換）:

| ファイル | 旧 | 新 |
|---------|-----|-----|
| `src/memory/memory_manager.py` 行3730-3731 | `CONTROL_MODEL = "ministral-3:8b"` | `from .model_config import get_quality_llm; CONTROL_MODEL = get_quality_llm()` |
| `src/memory/memory_manager.py` 行3730 | `EMBEDDING_MODEL = "qwen3-embedding:4b"` | `from .model_config import get_embedding_model; EMBEDDING_MODEL = get_embedding_model()` |
| `src/rag/rag_executor.py` 行6423-6424 | 同上 | 同上 |
| `src/rag/rag_builder.py` 行6013 | `kg_model = "command-a:latest"` | `from ..memory.model_config import get_exec_llm; kg_model = get_exec_llm()` |
| `MemoryRiskGate.__init__` | `CONTROL_MODEL` 参照 | `get_quality_llm()` 呼び出し |

**重要**: 各モデル参照箇所は**関数呼び出し時**に解決する（モジュールロード時ではない）。これにより設定変更が即時反映される。

### 設定の保存

```python
def _save_settings(self):
    """RAG設定をapp_settings.jsonに保存"""
    settings_path = Path("config/app_settings.json")
    try:
        data = {}
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        data["rag"] = {
            "claude_model": self.rag_cloud_model_combo.currentData(),
            "exec_llm": self.exec_llm_combo.currentText(),
            "quality_llm": self.quality_llm_combo.currentText(),
            "embedding_model": self.embedding_combo.currentText(),
            "time_limit": self.time_limit_spin.value(),
            "chunk_size": self.chunk_size_spin.value(),
            "chunk_overlap": self.overlap_spin.value(),
            # RAG強化フラグ
            "auto_kg_update": self.auto_kg_check.isChecked(),
            "hype_enabled": self.hype_check.isChecked(),
            "reranker_enabled": self.reranker_check.isChecked(),
        }

        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("RAG settings saved")
    except Exception as e:
        logger.error(f"Failed to save RAG settings: {e}")
```

---

## 6-E. RAG自動強化ロジック（バックグラウンド自動動作）

### 設計思想

**ユーザー操作を最小限にする**: 全強化ロジックは `evaluate_and_store()` パイプライン内で自動実行。UIに追加するのはON/OFFチェックボックス3つのみ（設定サブタブ内、6-Cのデザインに含む）。

### 強化1: LightRAG式インクリメンタルKG更新

**発動条件**: 全タブの `evaluate_and_store()` 実行後に自動発動
**UI操作**: 不要（設定の `☑ 応答後に自動KG更新` で制御）

既存の `evaluate_and_store()` は fact の entity-attribute-value を保存し、同一session内の co_occurrence edge のみを張る。これを拡張して**エンティティ間の意味的関係**も抽出する。

**変更ファイル**: `src/memory/memory_manager.py` → `evaluate_and_store()` 拡張

```python
async def evaluate_and_store(self, session_id, ai_response, user_query,
                              memory_scope=MEMORY_SCOPE_APP):
    """応答後に記憶候補を抽出し、Risk Gateで判定して保存（v11.0.0 KG強化版）"""

    # --- 既存処理（v10.x と同一） ---
    # 1. extract_memories() → facts, procedures
    # 2. validate_memories() → ADD/UPDATE/DEPRECATE/SKIP
    # 3. add_fact() + save_procedure()
    # 4. _auto_link_session_facts() → co_occurrence edges
    # ... （既存コード維持） ...

    # --- v11.0.0 新規: LightRAG式 関係抽出 ---
    rag_settings = _load_rag_settings()
    if rag_settings.get("auto_kg_update", True) and len(facts) >= 2:
        try:
            await self._extract_and_merge_relations(
                session_id, facts, user_query, ai_response)
        except Exception as e:
            logger.warning(f"[v11.0.0] KG relation extraction failed: {e}")

    # --- v11.0.0 新規: HyPE 仮想質問生成 ---
    if rag_settings.get("hype_enabled", True) and facts:
        try:
            await self._generate_hypothetical_questions(session_id, facts)
        except Exception as e:
            logger.warning(f"[v11.0.0] HyPE generation failed: {e}")
```

**新規メソッド**: `_extract_and_merge_relations()`

```python
async def _extract_and_merge_relations(self, session_id: str,
                                        facts: list, user_query: str,
                                        ai_response: str):
    """LightRAG式: facts間の意味的関係を品質チェックLLMで抽出しKGにマージ"""
    from .model_config import get_quality_llm

    # 抽出対象をconfidence上位10件に絞る
    target_facts = sorted(facts, key=lambda f: f.get('confidence', 0),
                          reverse=True)[:10]

    entities_text = "\n".join(
        f"- {f.get('entity','')}.{f.get('attribute','')}: {f.get('value','')[:80]}"
        for f in target_facts
    )

    prompt = f"""以下のエンティティ間の関係を抽出してください。

[エンティティ一覧]
{entities_text}

[会話コンテキスト]
Q: {user_query[:500]}
A: {ai_response[:500]}

出力形式（JSONのみ）:
[
  {{"source": "entity1.attr1", "target": "entity2.attr2",
    "relation": "depends_on|causes|implements|uses|extends|part_of|related_to",
    "weight": 0.0-1.0}}
]

関係がない場合は空配列 [] を返してください。"""

    raw = await self.risk_gate._call_ollama(get_quality_llm(), prompt)

    try:
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start >= 0 and end > start:
            relations = json.loads(raw[start:end])
        else:
            return
    except json.JSONDecodeError:
        return

    # KGにマージ
    conn = self._get_conn()
    try:
        for rel in relations[:15]:  # 上限15関係
            source_entity = rel.get("source", "").split(".")[0]
            target_entity = rel.get("target", "").split(".")[0]
            relation = rel.get("relation", "related_to")
            weight = min(max(rel.get("weight", 0.5), 0.1), 1.0)

            # source/target ノードIDを検索
            src_row = conn.execute(
                "SELECT id FROM semantic_nodes WHERE entity = ? "
                "AND valid_to IS NULL ORDER BY valid_from DESC LIMIT 1",
                (source_entity,)).fetchone()
            tgt_row = conn.execute(
                "SELECT id FROM semantic_nodes WHERE entity = ? "
                "AND valid_to IS NULL ORDER BY valid_from DESC LIMIT 1",
                (target_entity,)).fetchone()

            if src_row and tgt_row:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_edges "
                    "(source_node_id, target_node_id, relation, weight, valid_from) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (src_row["id"], tgt_row["id"], relation, weight,
                     datetime.now().isoformat()))

        conn.commit()
        logger.info(f"[v11.0.0] KG relations merged: {len(relations)} extracted")
    finally:
        conn.close()
```

### 強化2: HyPE（Hypothetical Prompt Embeddings）

**発動条件**: fact保存時に自動発動
**UI操作**: 不要（設定の `☑ 仮想質問事前生成` で制御）

```python
async def _generate_hypothetical_questions(self, session_id: str, facts: list):
    """HyPE: 各factに対して仮想質問を生成し、embeddingと共に保存"""
    from .model_config import get_quality_llm, get_embedding_model

    for fact in facts[:5]:  # 上位5件に限定（処理負荷制御）
        fact_text = f"{fact.get('entity','')}.{fact.get('attribute','')}: {fact.get('value','')}"

        prompt = f"""以下の事実について、ユーザーが尋ねそうな質問を2つ生成してください。
事実: {fact_text}
出力（1行に1質問、質問のみ）:"""

        raw = await self.risk_gate._call_ollama(get_quality_llm(), prompt)
        questions = [q.strip() for q in raw.strip().split('\n') if q.strip()][:2]

        for q in questions:
            emb = await self.risk_gate._get_embedding(q)
            if emb:
                emb_blob = _embedding_to_blob(emb)
                conn = self._get_conn()
                try:
                    conn.execute("""
                        INSERT INTO hype_questions
                        (fact_entity, fact_attribute, question, question_embedding,
                         source_session, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (fact.get('entity',''), fact.get('attribute',''),
                          q, emb_blob, session_id,
                          datetime.now().isoformat()))
                    conn.commit()
                finally:
                    conn.close()
```

**DBスキーマ追加** (`_init_db()` に追加):

```python
# v11.0.0: HyPE（仮想質問事前生成）テーブル
c.execute("""
    CREATE TABLE IF NOT EXISTS hype_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_entity TEXT NOT NULL,
        fact_attribute TEXT NOT NULL,
        question TEXT NOT NULL,
        question_embedding BLOB,
        source_session TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_hype_entity "
          "ON hype_questions(fact_entity, fact_attribute)")
```

### 強化3: Reranker

**発動条件**: `build_context_for_*()` 系メソッド内で自動発動
**UI操作**: 不要（設定の `☑ 検索結果リランキング` で制御）

```python
def _rerank_results(self, query: str, candidates: list, top_k: int = 5) -> list:
    """品質チェックLLMによる検索結果リランキング（v11.0.0）"""
    from .model_config import get_quality_llm

    rag_settings = _load_rag_settings()
    if not rag_settings.get("reranker_enabled", True):
        return candidates[:top_k]

    if len(candidates) <= top_k:
        return candidates

    # 候補テキストを整形
    candidate_texts = []
    for i, c in enumerate(candidates[:20]):  # 上限20件
        summary = c.get("summary", c.get("value", ""))[:100]
        candidate_texts.append(f"{i}: {summary}")

    prompt = f"""質問に対して最も関連度の高い候補をランキングしてください。

質問: {query}

候補:
{chr(10).join(candidate_texts)}

最も関連度の高い順にインデックスをカンマ区切りで出力（数字のみ）:"""

    raw = self._call_resident_llm(prompt, max_tokens=64)

    try:
        indices = [int(x.strip()) for x in raw.split(',') if x.strip().isdigit()]
        reranked = []
        seen = set()
        for idx in indices:
            if 0 <= idx < len(candidates) and idx not in seen:
                reranked.append(candidates[idx])
                seen.add(idx)
        # ランキングされなかった候補を末尾に追加
        for i, c in enumerate(candidates):
            if i not in seen:
                reranked.append(c)
        return reranked[:top_k]
    except Exception:
        return candidates[:top_k]
```

**適用箇所**: 既存の `build_context_for_phase1()`, `build_context_for_phase2()`, `build_context_for_phase3()`, `build_context_for_solo()` の検索結果返却前に `_rerank_results()` を挿入。

### HyPE検索の統合

`search_episodes()` / `search_semantic()` に加えて、HyPE質問テーブルも検索対象に追加:

```python
def search_hype_by_text(self, query: str, top_k: int = 5) -> list:
    """v11.0.0: HyPE質問とのベクトルマッチング"""
    emb = self._get_embedding_sync(query)
    if emb is None:
        return []

    conn = self._get_conn()
    try:
        rows = conn.execute(
            "SELECT fact_entity, fact_attribute, question, question_embedding "
            "FROM hype_questions WHERE question_embedding IS NOT NULL"
        ).fetchall()
        scored = []
        for row in rows:
            sim = _cosine_similarity(emb, row["question_embedding"])
            scored.append({
                "entity": row["fact_entity"],
                "attribute": row["fact_attribute"],
                "question": row["question"],
                "similarity": sim,
            })
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]
    finally:
        conn.close()
```

### RAG自動強化UIチェックボックス（設定サブタブ内）

```python
    # --- RAG自動強化 ---
    enhance_group = QGroupBox(t('desktop.ragTab.autoEnhance'))
    enhance_layout = QVBoxLayout()

    self.auto_kg_check = QCheckBox(t('desktop.ragTab.autoKgUpdate'))
    self.auto_kg_check.setChecked(True)
    self.auto_kg_check.setToolTip(t('desktop.ragTab.autoKgUpdateTip'))
    enhance_layout.addWidget(self.auto_kg_check)

    self.hype_check = QCheckBox(t('desktop.ragTab.hypeEnabled'))
    self.hype_check.setChecked(True)
    self.hype_check.setToolTip(t('desktop.ragTab.hypeEnabledTip'))
    enhance_layout.addWidget(self.hype_check)

    self.reranker_check = QCheckBox(t('desktop.ragTab.rerankerEnabled'))
    self.reranker_check.setChecked(True)
    self.reranker_check.setToolTip(t('desktop.ragTab.rerankerEnabledTip'))
    enhance_layout.addWidget(self.reranker_check)

    info_label = QLabel(t('desktop.ragTab.autoEnhanceInfo'))
    info_label.setStyleSheet("color: #888; font-size: 10px;")
    enhance_layout.addWidget(info_label)

    # R2: 領域別保存ボタン
    enhance_layout.addWidget(create_section_save_button(self._save_rag_enhance_settings))

    enhance_group.setLayout(enhance_layout)
    layout.addWidget(enhance_group)
```

---

## 6-F. 全タブ横断: メモリモデル動的化の影響範囲

Phase 6-D のモデル動的化は、RAGタブだけでなく**全タブのメモリ処理**に影響する。以下は影響を受ける全ファイルの一覧:

| ファイル | 影響箇所 | 変更内容 |
|---------|---------|---------|
| `src/memory/memory_manager.py` | 行3730-3731 定数定義 | `model_config` から動的取得に変更 |
| `src/memory/memory_manager.py` | `MemoryRiskGate` 全メソッド | `CONTROL_MODEL` → `get_quality_llm()` |
| `src/memory/memory_manager.py` | `_get_embedding()` / `_get_embedding_sync()` | `EMBEDDING_MODEL` → `get_embedding_model()` |
| `src/memory/memory_manager.py` | `_call_resident_llm()` | `CONTROL_MODEL` → `get_quality_llm()` |
| `src/memory/memory_manager.py` | `graphrag_community_summary()` | `CONTROL_MODEL` → `get_quality_llm()` |
| `src/rag/rag_executor.py` | 行6423-6424 定数定義 | `model_config` から動的取得に変更 |
| `src/rag/rag_executor.py` | embedding生成全箇所 | `EMBEDDING_MODEL` → `get_embedding_model()` |
| `src/rag/rag_executor.py` | 要約・検証全箇所 | `CONTROL_MODEL` → `get_quality_llm()` |
| `src/rag/rag_builder.py` | 行6013 `kg_model` | `"command-a:latest"` → `get_exec_llm()` |
| `src/tabs/helix_orchestrator_tab.py` | `evaluate_and_store()` 呼び出し行2666 | 変更不要（MemoryManager内部で解決） |
| `src/tabs/claude_tab.py` | `evaluate_and_store()` 呼び出し行16929 | 変更不要（同上） |
| `src/tabs/local_ai_tab.py` | `evaluate_and_store()` 呼び出し行17430 | 変更不要（同上） |

---

# 共通: i18n キー追加（日英バイリンガル）

> 全キーの完全一覧は `HelixAIStudio_v11_UI_Design_Rules.md` セクション3.4を参照。
> 以下はJSON構造を示す。

## locales/ja.json 追加分

```json
{
  "common": {
    "saveSection": "保存",
    "saveSectionDone": "保存完了",
    "saveSectionFailed": "保存失敗"
  },
  "desktop": {
    "tabs": {
      "rag": "🧠 RAG",
      "history": "📜 History"
    },
    "cloudAI": {
      "continueSendMain": "継続送信",
      "continueSendMainTooltip": "同一セッション内で追加質問を送信（トークン節約）",
      "sessionCaptured": "セッション確立: {id}",
      "advancedSettings": "詳細設定",
      "advancedSettingsTooltip": "Claude Code settings.json を開く",
      "modelManage": "管理",
      "modelManageTooltip": "モデルの追加・削除・並び替え",
      "mcpSettings": "MCP サーバー設定",
      "sendBlockTitle": "送信ブロック",
      "modelManageTitle": "モデル管理",
      "modelManageAddName": "モデル名",
      "modelManageAddCmd": "コマンド",
      "modelManageAdd": "追加",
      "modelManageDelete": "削除",
      "modelManageBuiltinProtected": "ビルトインモデルは削除できません",
      "settingsSaved": "cloudAI設定を保存しました",
      "settingsSaveFailed": "保存失敗: {error}",
      "settingsOpenFailed": "設定ファイルを開けません: {error}"
    },
    "localAI": {
      "mcpSettings": "MCP サーバー設定",
      "modelCapTools": "Tools",
      "modelCapVision": "Vision",
      "modelCapThinking": "Thinking",
      "modelCapContext": "Context",
      "deleteSelected": "選択削除",
      "deleteConfirmTitle": "モデル削除確認",
      "deleteConfirmMsg": "{count}個のモデルを削除しますか？",
      "settingsSaved": "localAI設定を保存しました"
    },
    "common": {
      "bibleToggleTooltip": "BIBLE管理モードON: AIが自律的にBIBLEを作成・更新します"
    },
    "history": {
      "searchPlaceholder": "チャット履歴を検索...",
      "filterAll": "全タブ",
      "sortNewest": "新しい順",
      "sortOldest": "古い順",
      "copyMessage": "コピー",
      "quoteToTab": "他タブに引用",
      "noResults": "該当するチャットが見つかりません"
    },
    "ragTab": {
      "chatSubTab": "チャット",
      "settingsSubTab": "設定",
      "inputPlaceholder": "RAGに質問する / コマンドを入力...",
      "addFiles": "追加",
      "stats": "統計",
      "rebuild": "再構築",
      "plan": "プラン",
      "searching": "RAGコンテキストを検索中...",
      "rebuildStarting": "RAG構築を開始します...",
      "rebuildComplete": "RAG構築完了: {nodes}ノード, {edges}エッジ, {communities}コミュニティ",
      "rebuildFailed": "RAG構築失敗: {error}",
      "quickStats": "現在のRAG統計を表示して",
      "quickRebuild": "RAGを再構築して",
      "quickPlan": "RAG構築プランを作成して",
      "chatAiSettings": "チャットAI設定",
      "claudeModel": "Claude モデル",
      "localLlmRoles": "ローカルLLMロール設定",
      "execLlm": "実行LLM（要約・KG構築）",
      "execLlmHint": "推奨: 32B以上、長コンテキスト対応モデル",
      "qualityLlm": "品質チェックLLM（検証・分類）",
      "qualityLlmHint": "推奨: 8B程度の軽量高速モデル",
      "embeddingModel": "Embeddingモデル",
      "embeddingHint": "推奨: embedding専用モデル",
      "refreshModels": "Ollamaモデル再読込",
      "refreshSuccess": "{count}個のモデルを読み込みました",
      "refreshFailed": "Ollamaモデル読込失敗: {error}",
      "autoEnhance": "RAG自動強化",
      "autoKgUpdate": "応答後に自動KG更新（LightRAG式）",
      "autoKgUpdateTip": "各タブでのAI応答後にエンティティ間関係を自動抽出してKGに追加",
      "hypeEnabled": "仮想質問事前生成（HyPE）",
      "hypeEnabledTip": "保存されたfactに対して仮想質問を生成し検索精度を向上",
      "rerankerEnabled": "検索結果リランキング",
      "rerankerEnabledTip": "RAG検索結果をLLMで再ランキングして最も関連性の高い結果を返す",
      "autoEnhanceInfo": "全機能はバックグラウンドで自動実行されます",
      "buildParams": "RAG構築パラメータ",
      "timeLimit": "制限時間（分）",
      "chunkSize": "チャンクサイズ",
      "chunkOverlap": "オーバーラップ",
      "folderSettings": "対象フォルダ",
      "folderChange": "変更",
      "folderFileList": "ファイル一覧",
      "saveFailed": "RAG設定の保存に失敗: {error}",
      "statusBar": "📁 {files}ファイル ({size}) │ {ragStatus} │ 🧠 {nodes}ノード",
      "addFilesTitle": "ファイルを追加",
      "addFilesFilter": "サポートファイル ({ext})",
      "fileSizeOverTitle": "ファイルサイズ超過",
      "fileSizeExceeded": "{name}: {size}MB (最大{max}MB)",
      "filesAdded": "{count}ファイルを追加しました",
      "planCreated": "RAG構築プランを作成しました",
      "planFailed": "プラン作成に失敗: {error}"
    },
    "mixAI": {
      "phase13Saved": "Phase 1/3 設定を保存しました",
      "phase2Saved": "Phase 2 設定を保存しました",
      "phase35Saved": "Phase 3.5 設定を保存しました",
      "phase4Saved": "Phase 4 設定を保存しました",
      "ollamaSaved": "Ollama接続設定を保存しました",
      "residentSaved": "常駐モデル設定を保存しました",
      "bibleCreateFailed": "BIBLE作成失敗: {error}"
    },
    "settings": {
      "mcpFilesystem": "Filesystem (MCP)",
      "mcpGit": "Git (MCP)",
      "mcpBrave": "Brave Search (MCP)",
      "memorySaved": "メモリ設定を保存しました",
      "webuiSaved": "Web UI設定を保存しました"
    }
  }
}
```

## locales/en.json 追加分

```json
{
  "common": {
    "saveSection": "Save",
    "saveSectionDone": "Saved",
    "saveSectionFailed": "Save Failed"
  },
  "desktop": {
    "tabs": {
      "rag": "🧠 RAG",
      "history": "📜 History"
    },
    "cloudAI": {
      "continueSendMain": "Continue",
      "continueSendMainTooltip": "Send follow-up in the same session (saves tokens)",
      "sessionCaptured": "Session captured: {id}",
      "advancedSettings": "Advanced",
      "advancedSettingsTooltip": "Open Claude Code settings.json",
      "modelManage": "Manage",
      "modelManageTooltip": "Add, remove, or reorder models",
      "mcpSettings": "MCP Server Settings",
      "sendBlockTitle": "Send Blocked",
      "modelManageTitle": "Manage Models",
      "modelManageAddName": "Model Name",
      "modelManageAddCmd": "Command",
      "modelManageAdd": "Add",
      "modelManageDelete": "Delete",
      "modelManageBuiltinProtected": "Built-in models cannot be deleted",
      "settingsSaved": "cloudAI settings saved",
      "settingsSaveFailed": "Save failed: {error}",
      "settingsOpenFailed": "Cannot open settings file: {error}"
    },
    "localAI": {
      "mcpSettings": "MCP Server Settings",
      "modelCapTools": "Tools",
      "modelCapVision": "Vision",
      "modelCapThinking": "Thinking",
      "modelCapContext": "Context",
      "deleteSelected": "Delete Selected",
      "deleteConfirmTitle": "Confirm Model Deletion",
      "deleteConfirmMsg": "Delete {count} model(s)?",
      "settingsSaved": "localAI settings saved"
    },
    "common": {
      "bibleToggleTooltip": "BIBLE mode ON: AI will autonomously create/update BIBLE"
    },
    "history": {
      "searchPlaceholder": "Search chat history...",
      "filterAll": "All Tabs",
      "sortNewest": "Newest First",
      "sortOldest": "Oldest First",
      "copyMessage": "Copy",
      "quoteToTab": "Quote to Tab",
      "noResults": "No matching chats found"
    },
    "ragTab": {
      "chatSubTab": "Chat",
      "settingsSubTab": "Settings",
      "inputPlaceholder": "Ask RAG a question / enter a command...",
      "addFiles": "Add",
      "stats": "Stats",
      "rebuild": "Rebuild",
      "plan": "Plan",
      "searching": "Searching RAG context...",
      "rebuildStarting": "Starting RAG build...",
      "rebuildComplete": "RAG build complete: {nodes} nodes, {edges} edges, {communities} communities",
      "rebuildFailed": "RAG build failed: {error}",
      "quickStats": "Show current RAG statistics",
      "quickRebuild": "Rebuild RAG",
      "quickPlan": "Create RAG build plan",
      "chatAiSettings": "Chat AI Settings",
      "claudeModel": "Claude Model",
      "localLlmRoles": "Local LLM Role Settings",
      "execLlm": "Execution LLM (Summary / KG Build)",
      "execLlmHint": "Recommended: 32B+, long context model",
      "qualityLlm": "Quality Check LLM (Validation / Classification)",
      "qualityLlmHint": "Recommended: ~8B lightweight fast model",
      "embeddingModel": "Embedding Model",
      "embeddingHint": "Recommended: embedding-dedicated model",
      "refreshModels": "Refresh Ollama Models",
      "refreshSuccess": "Loaded {count} model(s)",
      "refreshFailed": "Failed to load Ollama models: {error}",
      "autoEnhance": "RAG Auto-Enhancement",
      "autoKgUpdate": "Auto KG update after responses (LightRAG)",
      "autoKgUpdateTip": "Automatically extract entity relations after AI responses and add to KG",
      "hypeEnabled": "Hypothetical Prompt Embeddings (HyPE)",
      "hypeEnabledTip": "Generate hypothetical questions for saved facts to improve search accuracy",
      "rerankerEnabled": "Search Result Reranking",
      "rerankerEnabledTip": "Rerank RAG search results with LLM to return the most relevant results",
      "autoEnhanceInfo": "All features run automatically in the background",
      "buildParams": "RAG Build Parameters",
      "timeLimit": "Time Limit (min)",
      "chunkSize": "Chunk Size",
      "chunkOverlap": "Overlap",
      "folderSettings": "Target Folder",
      "folderChange": "Change",
      "folderFileList": "File List",
      "saveFailed": "Failed to save RAG settings: {error}",
      "statusBar": "📁 {files} file(s) ({size}) │ {ragStatus} │ 🧠 {nodes} node(s)",
      "addFilesTitle": "Add Files",
      "addFilesFilter": "Supported files ({ext})",
      "fileSizeOverTitle": "File Size Exceeded",
      "fileSizeExceeded": "{name}: {size}MB (max {max}MB)",
      "filesAdded": "{count} file(s) added",
      "planCreated": "RAG build plan created",
      "planFailed": "Failed to create plan: {error}"
    },
    "mixAI": {
      "phase13Saved": "Phase 1/3 settings saved",
      "phase2Saved": "Phase 2 settings saved",
      "phase35Saved": "Phase 3.5 settings saved",
      "phase4Saved": "Phase 4 settings saved",
      "ollamaSaved": "Ollama connection settings saved",
      "residentSaved": "Resident model settings saved",
      "bibleCreateFailed": "BIBLE creation failed: {error}"
    },
    "settings": {
      "mcpFilesystem": "Filesystem (MCP)",
      "mcpGit": "Git (MCP)",
      "mcpBrave": "Brave Search (MCP)",
      "memorySaved": "Memory settings saved",
      "webuiSaved": "Web UI settings saved"
    }
  }
}
```

---

# 設定ファイル構成変更

## config/config.json 追加セクション

```json
{
  "effort_level": "high",
  "mcp_settings": {
    "cloudAI": {
      "filesystem": true,
      "git": true,
      "brave": false
    },
    "localAI": {
      "filesystem": true,
      "git": false,
      "brave": true
    },
    "mixAI_phase1_3": "inherit_cloudAI",
    "mixAI_phase2": "inherit_localAI"
  }
}
```

## config/app_settings.json RAGセクション（v11.0.0 拡張）

```json
{
  "rag": {
    "claude_model": "claude-sonnet-4-5-20250929",
    "exec_llm": "command-a:latest",
    "quality_llm": "ministral-3:8b",
    "embedding_model": "qwen3-embedding:4b",
    "time_limit": 90,
    "chunk_size": 512,
    "chunk_overlap": 64,
    "auto_kg_update": true,
    "hype_enabled": true,
    "reranker_enabled": true
  }
}
```

## 新規ファイル

| ファイル | 用途 |
|---------|------|
| `config/cloud_models.json` | クラウドモデル管理 |
| `data/chat_history_log.jsonl` | 全文チャットログ |
| `src/memory/model_config.py` | ローカルLLMモデル設定一元管理 |
| `src/tabs/rag_tab.py` | RAGタブ（旧 information_collection_tab.py リネーム＋リライト） |
| `src/widgets/no_scroll_widgets.py` | NoScrollComboBox / NoScrollSpinBox 共通定義（R1ルール） |
| `src/widgets/section_save_button.py` | 領域別保存ボタンファクトリ（R2ルール） |

## 削除ファイル

| ファイル | 理由 |
|---------|------|
| `src/widgets/vram_simulator.py` | ③ VRAM Simulator 削除 |
| `src/backends/openai_compat_backend.py` | ⑤⑦ カスタムサーバー削除 |
| `config/custom_server.json` | ⑤⑦ カスタムサーバー削除 |

## リネームファイル

| 旧 | 新 | 理由 |
|----|-----|------|
| `src/tabs/information_collection_tab.py` | `src/tabs/rag_tab.py` | ⑥ タブ名変更 |

---

# タブ構成図 (v11.0.0)

```
HelixAIStudio.py
└─ MainWindow (QMainWindow)
   ├─ [Tab 0] 🔀 mixAI          -- 3Phase Orchestration
   │   ├─ 💬 Chat sub-tab       -- チャットUI (PhaseIndicator/NeuralFlow削除)
   │   │   └─ 📖 BIBLE toggle   -- BIBLE規則注入
   │   └─ ⚙️ Settings sub-tab   -- Phase設定 (BIBLE/VRAM/GPU削除、MCP分散配置)
   ├─ [Tab 1] ☁️ cloudAI         -- Cloud AI Chat
   │   ├─ 💬 Chat sub-tab
   │   │   ├─ [Model ▼] [⚙詳細] [🔄New]  -- モデル選択をチャット画面に移動
   │   │   ├─ 📖 BIBLE toggle
   │   │   ├─ [送信 ▶]                    -- 新規セッション送信
   │   │   └─ [📌 継続送信]                -- セッション維持送信 (v11.0.0)
   │   └─ ⚙️ Settings sub-tab   -- MCP設定(分散), モデル管理
   ├─ [Tab 2] 🖥️ localAI        -- Local LLM Chat
   │   ├─ 💬 Chat sub-tab
   │   │   └─ 📖 BIBLE toggle
   │   └─ ⚙️ Settings sub-tab   -- Ollama管理, MCP設定(分散), 能力表示強化
   ├─ [Tab 3] 📜 History         -- チャット履歴 (v11.0.0 新設)
   │   └─ 検索/フィルタ/ソート/詳細表示/引用
   ├─ [Tab 4] 🧠 RAG             -- RAGタブ (v11.0.0 全面刷新、旧:情報収集)
   │   ├─ 💬 チャット sub-tab    -- cloudAI風チャットUI + RAGコンテキスト自動注入
   │   │   ├─ ステータスバー (ファイル数/RAG状態/KGノード数)
   │   │   ├─ AI対話エリア (Claude CLI + RAG検索)
   │   │   ├─ [📁追加] [📊統計] [🔄再構築] [📋プラン]  -- クイックアクション
   │   │   └─ [送信 ▶]
   │   └─ ⚙️ 設定 sub-tab
   │       ├─ チャットAI設定 (Claudeモデル選択)       + 💾保存
   │       ├─ ローカルLLMロール設定 (3ロール)          + 💾保存
   │       ├─ RAG構築パラメータ                        + 💾保存
   │       ├─ RAG自動強化 (☑KG更新 ☑HyPE ☑Reranker)  + 💾保存
   │       └─ 対象フォルダ設定                         + 💾保存
   ├─ [Tab 5] ⚙️ Settings       -- 一般設定 (簡素化)
   │   ├─ AI状態確認
   │   ├─ Claude モデル設定              + 💾保存
   │   ├─ メモリ & ナレッジ (Advanced)   + 💾保存
   │   └─ Web UI サーバー               + 💾保存
   └─ [Corner] 🌐 言語切替
```

---

# 実装時の注意事項

## 後方互換性
- 既存の `config/config.json` に新しいキーが無い場合はデフォルト値を使用
- `cloud_models.json` が存在しない場合は `constants.py` の `CLAUDE_MODELS` リストから自動生成
- JSONL ログファイルが存在しない場合は初回書き込み時に自動作成
- `app_settings.json` に `exec_llm` / `quality_llm` / `embedding_model` が無い場合はデフォルト値（`command-a:latest` / `ministral-3:8b` / `qwen3-embedding:4b`）を使用
- `hype_questions` テーブルが存在しない場合は `_init_db()` で自動作成
- 旧 `information_collection_tab` の import を行っているファイルは `rag_tab` に更新

## Git コミット戦略
各Phase完了時にコミット:
1. `v11.0.0-phase1: UI cleanup (mixAI/settings simplification)`
2. `v11.0.0-phase2: cloudAI overhaul + session send`
3. `v11.0.0-phase3: History tab + JSONL logging`
4. `v11.0.0-phase4: BIBLE cross-tab integration`
5. `v11.0.0-phase5: localAI MCP (Python MCP SDK)`
6. `v11.0.0-phase6: RAG tab overhaul (chat UI + model selection + auto-enhance)`

## テスト確認ポイント
- Phase 1: 削除後にアプリが正常起動すること、mixAI 3Phase実行が動作すること
- Phase 2: 送信 ▶ で新規セッション、継続送信で --resume が動作すること
- Phase 3: 各タブでの送受信がJSONLに記録されること
- Phase 4: BIBLEボタンON時にコンテキストが注入されること
- Phase 5: localAIでMCPツール（filesystem等）が実行可能なこと
- Phase 6-A: タブ名が「🧠 RAG」、サブタブが「チャット/設定」と表示されること
- Phase 6-B: チャットサブタブでClaude CLIへの送信＋RAGコンテキスト注入が動作すること
- Phase 6-C: 設定画面でClaudeモデルが `cloud_models.json` から選択可能なこと
- Phase 6-D: 3ロールのLLM変更が `app_settings.json` に保存され、全タブのメモリ処理に反映されること
- Phase 6-E: `evaluate_and_store()` 後にKG関係抽出・HyPE生成が自動実行されること（ログ確認）
- Phase 6-E: 検索時にRerankerが動作し結果順序が変わること（ログ確認）

## v3ルール検証（全Phase横断）
- **R1**: `grep -r "QComboBox()\|QSpinBox()" src/` で標準クラス直接生成が0件であること
- **R2**: 各設定QGroupBox末尾に💾保存ボタンが存在すること、画面最下部の単一保存ボタンが無いこと
- **R3**: `grep -rn "QMessageBox" src/ | grep -v "t("` でハードコード文字列が0件であること
- **R3**: 言語切替（日→英）で全ラベル・ボタン・ツールチップ・ポップアップが英語に切り替わること
