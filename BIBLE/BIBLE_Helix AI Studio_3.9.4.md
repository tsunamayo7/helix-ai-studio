# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.9.4
**アプリケーションバージョン**: 3.9.4 "Helix AI Studio - mixAI CLI認証対応, モデル選択問題修正, UIフィードバック改善"
**作成日**: 2026-02-02
**最終更新**: 2026-02-02
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.9.4 更新履歴 (2026-02-02)

### 主な変更点

**概要**:
v3.9.4 は修正依頼に基づき、以下の重要な改善を実装:
1. soloAI モデル選択問題の修正（Sonnet選択時にOpusが使用される問題）
2. mixAI でCLI認証を使用可能に（APIキーなしでも動作）
3. UI視覚的フィードバックの改善（Ollama選択時のグレーアウト）
4. API/CLI認証設定の一般設定タブへの移設（共通化）
5. モデル選択UIの改善（スクロール選択廃止、プルダウンのみ）

**修正・追加内容**:

| # | 問題/要望 | 対策 |
|---|----------|------|
| A | Sonnet4.5選択時にOpus4.5が使用される | `ClaudeCLIBackend`にモデル指定オプション追加、`--model`フラグ対応 |
| B | mixAIでCLI認証が使えない | `_call_claude_cli()`メソッド追加、APIキーなし時CLIにフォールバック |
| C | Ollama選択時にモデル・思考がグレーアウトしない | `_set_ollama_ui_disabled()`にstyleSheet追加、視覚的フィードバック改善 |
| D | 保存メッセージが「Claude設定」のまま | 「soloAI設定を保存しました」に変更 |
| E | Ollamaモデル設定が正しく適用されない | 初期状態空、「モデル一覧更新」ボタンに名称変更、スクロール無効化 |
| F | 7役割モデル割り当てでスクロール選択可能 | `NoScrollComboBox`クラス作成、wheelEvent無効化 |
| G | API/CLI認証設定がsoloAIにのみ存在 | 一般設定タブに移設、soloAI/mixAI共通化 |

---

## CLIモデル選択対応 (v3.9.4)

### ClaudeCLIBackend の変更

**新規追加**:

```python
# v3.9.4: モデルIDマッピング
MODEL_MAP = {
    "Claude Opus 4.5": "claude-opus-4-5-20251101",
    "Claude Sonnet 4.5 (推奨)": "claude-sonnet-4-5-20250929",
    "Claude Haiku 4.5 (高速)": "claude-haiku-4-5-20251001",
}

def __init__(self, working_dir=None, thinking_level="none", skip_permissions=True, model=None):
    # ...
    self._model = model  # v3.9.4: モデル選択対応

def _build_command(self, extra_options=None, use_continue=False):
    # v3.9.4: モデル選択
    model_id = self._get_model_id()
    if model_id:
        cmd.extend(["--model", model_id])
```

### _send_via_cli の変更

```python
# v3.9.4: モデル選択を取得（UIから）
selected_model = model_text

# CLIバックエンドへの参照を取得 (v3.9.4: モデル選択を渡す)
self._cli_backend = get_claude_cli_backend(working_dir, skip_permissions=skip_permissions, model=selected_model)
```

---

## mixAI CLI認証対応 (v3.9.4)

### _call_claude_api の変更

```python
def _call_claude_api(self, model: str, system_prompt: str, user_prompt: str) -> str:
    """Claude API/CLI経由でLLMを呼び出し (v3.9.4: CLI対応追加)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # v3.9.4: APIキーがない場合はCLIを試行
    if not api_key:
        return self._call_claude_cli(model, system_prompt, user_prompt)

    try:
        # API呼び出し...
    except Exception as e:
        # API呼び出し失敗時もCLIにフォールバック
        return self._call_claude_cli(model, system_prompt, user_prompt)
```

### 新規追加メソッド

| メソッド | 説明 |
|----------|------|
| `_call_claude_cli()` | CLI経由でClaude呼び出し（mixAI用） |

---

## UI改善 (v3.9.4)

### Ollama選択時のグレーアウト

```python
def _set_ollama_ui_disabled(self, disabled: bool):
    """v3.9.4: グレーアウト視覚フィードバック追加"""
    disabled_style = """
        QComboBox:disabled {
            background-color: #404040;
            color: #808080;
            border: 1px solid #505050;
        }
    """
    self.model_combo.setStyleSheet(disabled_style if disabled else "")
    self.thinking_combo.setStyleSheet(disabled_style if disabled else "")
```

### NoScrollComboBox クラス

```python
class NoScrollComboBox(QComboBox):
    """マウスホイールで値が変わらないQComboBox"""
    def wheelEvent(self, event):
        event.ignore()  # ホイールイベントを無視
```

### Ollamaモデル選択UI

- 初期状態は空（モデル一覧更新ボタンを押すまで）
- 「取得」→「モデル一覧更新」に名称変更
- プルダウンのみ（スクロール選択無効）
- setEditable(False)でプルダウン選択のみに

---

## API/CLI認証設定の一般設定タブ移設 (v3.9.4)

### 新規追加グループ (settings_cortex_tab.py)

```python
def _create_auth_group(self) -> QGroupBox:
    """v3.9.4: API/CLI認証設定グループを作成（soloAIから移設）"""
    group = QGroupBox("🔑 API / CLI 認証設定")
    # ANTHROPIC_API_KEY入力
    # API接続テストボタン
    # Claude CLI有効化チェックボックス
    # CLI状態確認ボタン
```

### 機能

| 機能 | 説明 |
|------|------|
| API接続テスト | APIキーで簡単なリクエストを送信して接続確認 |
| CLI確認 | `check_claude_cli_available()`で利用可否を確認 |
| 共通設定 | soloAI/mixAI両方で使用される |

---

## ファイル変更一覧 (v3.9.4)

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/claude_cli_backend.py` | MODEL_MAP追加、modelパラメータ追加、`--model`フラグ対応 |
| `src/tabs/claude_tab.py` | グレーアウトスタイル追加、eventFilter追加、保存メッセージ変更、Ollamaモデル選択UI改善 |
| `src/tabs/helix_orchestrator_tab.py` | NoScrollComboBox追加、_call_claude_cli追加、CLIフォールバック対応 |
| `src/tabs/settings_cortex_tab.py` | _create_auth_group追加、API/CLI認証設定UI追加 |
| `src/utils/constants.py` | バージョン 3.9.3 → 3.9.4 |
| `BIBLE/BIBLE_Helix AI Studio_3.9.4.md` | 本ファイル追加 |

---

## 新規追加クラス/メソッド (v3.9.4)

| 種類 | 名前 | ファイル | 説明 |
|------|------|----------|------|
| クラス | `NoScrollComboBox` | `helix_orchestrator_tab.py` | ホイール無効ComboBox |
| メソッド | `_call_claude_cli()` | `helix_orchestrator_tab.py` | mixAI用CLI呼び出し |
| メソッド | `_get_model_id()` | `claude_cli_backend.py` | モデルIDマッピング |
| メソッド | `_create_auth_group()` | `settings_cortex_tab.py` | 認証設定UI |
| メソッド | `_test_api_connection()` | `settings_cortex_tab.py` | API接続テスト |
| メソッド | `_test_cli_connection()` | `settings_cortex_tab.py` | CLI接続テスト |

---

## タブ構成 (v3.9.4)

### タブ構成 (4タブ) - v3.9.3から変更なし

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | 🤖 soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | 🔀 mixAI | チャット / 設定 | マルチLLMオーケストレーション（**v3.9.4でCLI対応**） |
| 3 | 📝 チャット作成 | - | チャット原稿の作成・編集 |
| 4 | ⚙️ 一般設定 | - | アプリ全体の設定（**v3.9.4で認証設定追加**） |

---

## 認証方式×モデル×機能の対応マトリクス (v3.9.4 更新)

| 認証方式 | モデル | 思考モード | MCPツール | mixAI対応 | 備考 |
|----------|--------|------------|-----------|-----------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ | ✅ (**v3.9.4**) | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ | ✅ (**v3.9.4**) | 全対応、**モデル選択修正** |
| CLI | Haiku 4.5 | OFF | ✅ | ✅ (**v3.9.4**) | 思考は警告 |
| API | Opus 4.5 | OFF/Standard/Deep | ❌ | ✅ | API経由は独自MCP未実装 |
| API | Sonnet 4.5 | OFF/Standard/Deep | ❌ | ✅ | 同上 |
| API | Haiku 4.5 | OFF/Standard/Deep | ❌ | ✅ | 同上 |
| Ollama | (設定タブ) | OFF固定 | ✅ | ✅ | プロンプトベースツール |

---

## ビルド成果物

| ファイル | パス |
|----------|------|
| exe | `dist/HelixAIStudio.exe` |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_3.9.4.md` |

---

## v3.9.3からの継承課題（一部解決）

- [x] mixAI でのCLI認証対応 → **v3.9.4で解決**
- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI

---

## 参考: Claude API モデルID (2026年1月時点)

| モデル名 | API ID | エイリアス |
|----------|--------|------------|
| Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | claude-sonnet-4-5 |
| Claude Opus 4.5 | claude-opus-4-5-20251101 | claude-opus-4-5 |
| Claude Haiku 4.5 | claude-haiku-4-5-20251001 | claude-haiku-4-5 |

参照: [Models overview - Claude API Docs](https://platform.claude.com/docs/en/about-claude/models/overview)
