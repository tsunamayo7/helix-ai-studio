# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.9.2
**アプリケーションバージョン**: 3.9.2 "Helix AI Studio - soloAI/mixAI、Ollamaストリクトモード、フォールバック"
**作成日**: 2026-02-02
**最終更新**: 2026-02-02
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.9.2 更新履歴 (2026-02-02)

### 主な変更点

**概要**:
v3.9.2 はUIの改善（タブ名変更、モデル一覧表示拡大）、Ollamaモードの厳密化、
CLI認証でのHaiku 4.5フォールバック、思考モードの事前判定を実装。

**修正・追加内容**:

| カテゴリ | 問題/要望 | 対策 |
|----------|----------|------|
| A. UI改善 | mixAI(設定)のモデル一覧が1行しか見えない | `setMaximumHeight(150)` を `setMinimumHeight(280)` + `Expanding` に変更 |
| B. 接続テスト | soloAI(設定)にテスト機能がない | API/CLI/Ollama各認証の接続テスト、統合モデルテスト、最終テスト成功表示を追加 |
| C-1. Ollama厳密化 | 認証=Ollamaでも他バックエンドに送信されることがある | Ollamaモード時は `_send_via_ollama()` で直接送信、設定タブのモデルを強制使用 |
| C-2. タブ名変更 | 「Claude」「LLMmix」が分かりにくい | 「soloAI」「mixAI」に改名（内部識別子は維持） |
| D. UI無効化 | Ollamaモードで使用モデル/思考が選択可能 | Ollamaモード時は `model_combo` と `thinking_combo` を無効化 |
| E. Haiku フォールバック | CLI×Haiku 4.5がモデル不正エラー | エラー検出時に自動でSonnetにフォールバック、通知表示 |
| F. 思考モード判定 | thinkingパラメータ非対応エラー | 事前判定（Haiku×thinking→警告）、実行時フォールバック（エラー検出→OFF再送信） |

---

## タブ構成 (v3.9.2)

### タブ構成 (4タブ)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | 🤖 soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | 🔀 mixAI | チャット / 設定 | マルチLLMオーケストレーション |
| 3 | 📝 チャット作成 | - | チャット原稿の作成・編集 |
| 4 | ⚙️ 一般設定 | - | アプリ全体の設定 |

---

## soloAI タブ詳細 (v3.9.2 更新)

### 認証モードと送信先の対応

| 認証モード | 送信先 | 使用モデル | 思考モード |
|------------|--------|------------|------------|
| CLI (Max/Proプラン) | Claude CLI | UI選択 | UI選択（Haiku時は警告） |
| API (従量課金) | RoutingExecutor | UI選択 | UI選択 |
| Ollama (ローカル) | Ollama API直接 | 設定タブ固定 | 常にOFF（無効化） |

### 接続テスト機能 (v3.9.2 新規)

**soloAI(設定)タブに追加された機能**:

1. **API接続テスト**: `anthropic` ライブラリで最小リクエスト送信、レイテンシ表示
2. **CLI確認**: `claude --version` 実行
3. **統合モデルテスト**: 現在の認証方式でテスト実行（ワンボタン）
4. **最終テスト成功表示**: `config/claude_settings.json` に保存、「✅ 最終テスト成功: CLI (2026-02-02 18:30, 0.50秒)」形式で表示

### Ollamaモード時のUI状態

| UI要素 | 状態 | 理由 |
|--------|------|------|
| 使用モデル (`model_combo`) | 無効化 (disabled) | 設定タブのモデルを強制使用 |
| 思考モード (`thinking_combo`) | 無効化 + OFF固定 | ローカルLLMはthinkingパラメータ非対応 |
| 認証状態インジケータ | 🖥️ + 実効モデル表示 | 「Ollamaモード: 有効, モデル: qwen3-coder」 |

### Ollama直接送信フロー (v3.9.2)

```
認証モード = Ollama (ローカル)
    ↓
_send_message() で auth_mode == 2 を検出
    ↓
_send_via_ollama(prompt, ollama_url, ollama_model) 呼び出し
    ↓
OllamaWorkerThread でスレッド実行
    ↓
ollama.Client.generate() で直接送信
    ↓
_on_ollama_response() で表示・履歴保存
```

---

## mixAI タブ詳細 (v3.9.2 更新)

### モデル一覧テーブルの改善

**変更前** (v3.9.1):
```python
self.ollama_models_table.setMaximumHeight(150)  # 1行しか見えない
```

**変更後** (v3.9.2):
```python
self.ollama_models_table.setMinimumHeight(280)
self.ollama_models_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
self.ollama_models_table.verticalHeader().setDefaultSectionSize(32)  # 行高さ固定
```

**効果**: 複数行（8行程度）が常時表示可能

---

## CLI × Haiku 4.5 フォールバック (v3.9.2)

### 事前判定 (F)

**_send_via_cli() 内で実行**:

1. モデル選択が「Haiku」の場合、思考モードを確認
2. thinking != OFF の場合、警告表示してOFFに変更
3. 選択モデルとプロンプトをインスタンス変数に保存（フォールバック用）

### 実行時フォールバック (E)

**_on_cli_response() 内で実行**:

1. エラーテキストに "model not found", "permission denied" 等を検出
2. 保存した選択モデルが「Haiku」の場合、Sonnetにフォールバック
3. UIのmodel_comboをSonnetに変更
4. 警告表示後、保存したプロンプトで再送信

### 思考モードフォールバック (F)

**_on_cli_response() 内で実行**:

1. エラーテキストに "thinking", "not supported" 等を検出
2. thinking_comboがOFF以外の場合、OFFに変更
3. 警告表示後、保存したプロンプトで再送信

---

## ファイル変更一覧 (v3.9.2)

| ファイル | 変更内容 |
|----------|----------|
| `src/main_window.py` | タブ名変更: Claude→soloAI, LLMmix→mixAI |
| `src/tabs/claude_tab.py` | 接続テスト機能追加、Ollama直接送信、UI無効化、フォールバック処理、OllamaWorkerThread追加 |
| `src/tabs/helix_orchestrator_tab.py` | モデル一覧テーブルの高さ拡大（setMinimumHeight(280)） |
| `src/utils/constants.py` | バージョン 3.9.1 → 3.9.2、APP_DESCRIPTION更新 |
| `BIBLE_Helix AI Studio_3.9.2.md` | 本ファイル追加 |

---

## 技術詳細 (v3.9.2)

### 新規追加クラス

| クラス | 説明 |
|--------|------|
| `OllamaWorkerThread` | Ollama API直接呼び出し用スレッド、completed(str, float)シグナル |

### 新規追加メソッド (claude_tab.py)

| メソッド | 説明 |
|----------|------|
| `_test_api_connection()` | API接続テスト（anthropicライブラリ使用） |
| `_run_unified_model_test()` | 統合モデルテスト（現在の認証方式でテスト） |
| `_load_last_test_success()` | 最終テスト成功情報を読み込み |
| `_save_last_test_success()` | 最終テスト成功情報を保存 |
| `_set_ollama_ui_disabled()` | Ollamaモード時のUI無効化制御 |
| `_send_via_ollama()` | Ollama経由で直接送信 |
| `_on_ollama_response()` | Ollama応答受信時の処理 |
| `_on_ollama_error()` | Ollamaエラー発生時の処理 |

### 変更されたメソッド

| メソッド | 変更内容 |
|----------|----------|
| `_on_auth_mode_changed()` | Ollamaモード時のUI無効化、ステータス表示に実効モデル追加 |
| `_configure_ollama_mode()` | 設定タブのOllama設定を正しく参照 |
| `_send_message()` | Ollamaモード分岐を追加（直接送信） |
| `_send_via_cli()` | E/Fフォールバック用の変数保存、Haiku×thinking警告 |
| `_on_cli_response()` | E/Fフォールバック処理（Haiku→Sonnet、thinking→OFF） |
| `_create_settings_tab()` | 接続テスト機能、最終テスト成功表示を追加 |

---

## 設定ファイル (v3.9.2 更新)

### config/claude_settings.json

```json
{
  "ollama_url": "http://localhost:11434",
  "ollama_model": "qwen3-coder",
  "default_model": "Claude Sonnet 4.5 (推奨)",
  "timeout_minutes": 30,
  "mcp_servers": {
    "filesystem": true,
    "git": true,
    "brave-search": false
  },
  "last_test_success": {
    "auth": "CLI",
    "timestamp": "2026-02-02 18:30",
    "latency": 0.50
  }
}
```

---

## 認証方式×モデル×思考モードの対応マトリクス

| 認証方式 | モデル | 思考モード | 可否 | 備考 |
|----------|--------|------------|------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ | 全対応 |
| CLI | Haiku 4.5 | OFF | ⚠️ | 思考は警告、モデル不正時はSonnetにフォールバック |
| API | Opus 4.5 | OFF/Standard/Deep | ✅ | 全対応 |
| API | Sonnet 4.5 | OFF/Standard/Deep | ✅ | 全対応 |
| API | Haiku 4.5 | OFF/Standard/Deep | ✅ | API経由は思考対応 |
| Ollama | (設定タブ) | OFF固定 | ✅ | ローカルLLMはthinking非対応 |

---

## エラー検出パターン (v3.9.2)

### Haikuフォールバック対象

```python
haiku_errors = ["model not found", "permission denied", "unauthorized", "not available", "unsupported model"]
```

### 思考モードフォールバック対象

```python
thinking_errors = ["thinking", "extended thinking", "not supported", "invalid parameter"]
```

---

## ビルド成果物

| ファイル | パス |
|----------|------|
| exe | `dist/HelixAIStudio.exe` |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_3.9.2.md` |

---

## 次期バージョンへの課題

- [ ] mixAI オーケストレーション実行の実装（現在シミュレーション）
- [ ] MCP Tool Search機能の実装
- [ ] チャット履歴のエクスポート機能
- [ ] Ollamaストリーミング応答対応
