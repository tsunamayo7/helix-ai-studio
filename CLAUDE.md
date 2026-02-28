# CLAUDE.md — Helix AI Studio

> Claude Code がこのプロジェクトで作業する際に必ず読むファイルです。
> 詳細な仕様は `BIBLE_Helix_AI_Studio_11_5_3.md` を参照してください。

---

## プロジェクト概要

**Helix AI Studio v11.5.3 "Web LocalAI + Discord"**

PyQt6製のAIオーケストレーションデスクトップアプリ + FastAPI製Web UI。
Claude CLI / Anthropic API / OpenAI API / Google Gemini API / Ollama（ローカルLLM）を
5Phaseパイプラインで統合する。

- **オーナー**: tsunamayo7
- **LICENSE著作者名**: tsunamayo7
- **言語**: 日本語/英語（i18n対応）
- **実行環境**: Windows 11（デスクトップ）+ モバイルブラウザ（Web UI）

---

## ディレクトリ構造（重要ファイルのみ）

```
HelixAIStudio.py          # エントリポイント
src/
  tabs/
    claude_tab.py         # cloudAI タブ（Claude CLI/API チャット）
    local_ai_tab.py       # localAI タブ（Ollama チャット）
    helix_orchestrator_tab.py  # mixAI タブ（5Phase パイプライン）
    settings_cortex_tab.py     # 一般設定タブ
  web/
    server.py             # FastAPI + WebSocket（/ws/cloud /ws/mix /ws/local）
    api_routes.py         # REST API エンドポイント
  backends/
    anthropic_api_backend.py
    openai_api_backend.py
    google_api_backend.py
    api_priority_resolver.py
  utils/
    constants.py          # APP_VERSION, APP_CODENAME
    discord_notifier.py   # notify_discord() — 全ハンドラから呼ぶ
    i18n.py               # t('key') 関数
frontend/src/
  App.jsx                 # メインアプリ（4タブ: mixAI/cloudAI/localAI/files）
  components/
    LocalAIView.jsx       # localAI チャット（ModelSelector付き）
    MixAIView.jsx         # mixAI チャット（フェーズ表示付き）
    TabBar.jsx            # タブバー
  hooks/
    useWebSocket.js       # WS接続（sendMessage/sendMixMessage/sendLocalMessage）
i18n/
  ja.json                 # 日本語（正）
  en.json                 # 英語（ja.jsonと常に同期）
config/
  config.json             # 機密設定（.gitignore済み）
  *.example.json          # テンプレート（git管理対象）
```

---

## 技術スタック

| 層 | 技術 |
|---|---|
| デスクトップ GUI | PyQt6 |
| Web バックエンド | FastAPI + Uvicorn + WebSocket |
| Web フロントエンド | React + Tailwind CSS |
| ローカルLLM | Ollama (`_run_ollama_async` / `httpx`) |
| Claude 実行 | Claude CLI subprocess + Anthropic SDK |
| DB | SQLite（ChatStore） |
| 通知 | Discord Webhook（`notify_discord()`） |
| 多言語 | 共通 i18n/ja.json, i18n/en.json |

---

## 作業ルール（必ず守ること）

### コミット・ブランチ

- **mainブランチへの直接コミットは禁止**（オーナーが確認してからmerge）
- 作業ブランチ命名: `feature/xxx`, `fix/xxx`, `debug/xxx`
- コミットメッセージ: `v11.5.x 内容: 変更の要約` 形式

### バージョン管理

- バージョン変更時は必ず2箇所を同時に更新する:
  1. `src/utils/constants.py` — `APP_VERSION`, `APP_CODENAME`
  2. `BIBLE_Helix_AI_Studio_11_5_3.md` — Changelogセクション

### i18n ルール

- **ja.json が正（マスター）**、en.json は ja.json と常に同じキー構造を持つ
- コードで `t('key')` を使う際は **ja.json と en.json の両方に必ず追加する**
- キーの命名規則: `スコープ.タブ名.要素名`（例: `desktop.cloudAI.sendBtnMain`）
- デスクトップ: `desktop.*` / Web: `web.*` / 共通: `common.*` / タブ: `tabs.*`

### スタイル・UI ルール（デスクトップ PyQt6）

- 全タブの送信ボタンは `PRIMARY_BTN` スタイル + `setFixedHeight(32)`
- 入力フィールド: `background: #252526`, `border: none`, `font: Yu Gothic UI 11`
- 会話継続パネル: `background: #1a1a2e`, `border: 1px solid #2a2a3e`
- 新しいタブを追加する場合は cloudAI/localAI のパターンに揃える

### Discord通知ルール

```python
# 全 WebSocket ハンドラ（cloudAI/mixAI/localAI）に以下3点を必ず実装する
_notify_discord(tab, "started",   prompt[:200])          # 実行開始時
_notify_discord(tab, "completed", response[:500], elapsed=elapsed)  # 完了時
_notify_discord(tab, "error",     prompt[:200], error=str(e))       # エラー時
```

### 機密ファイルを絶対に編集・コミットしない

```
config/config.json
config/web_config.json
config/general_settings.json
config/app_settings.json
config/helix_pilot.json
logs/
data/rag_db/
data/memory/
data/helix_pilot_screenshots/
```

---

## Helix Pilot v2.0 — GUI 自動操作ツール

Claude Code がデスクトップ GUI をユーザー目線で操作するための外部ツール。
ローカル Vision LLM (Ollama) がスクリーンショットを解釈し、
Claude Code はテキスト (JSON) のみで画面状態を把握できる。

- **ファイル**: `scripts/helix_pilot.py`
- **設定**: `config/helix_pilot.json`
- **Vision モデル**: `mistral-small3.2:latest` (画面解析)
- **Reasoning モデル**: `gemma3:27b` (auto/browse のプラン生成)
- **出力**: 全コマンドが JSON を stdout に出力（`--compact` で簡潔化）

### v2.0 新機能: 自律実行コマンド（コンテキスト削減の主役）

**重要**: 複数ステップのGUI操作は、個別コマンドを連続実行する代わりに
`auto` / `browse` コマンドを使うこと。コンテキスト消費を 90% 以上削減できる。

```bash
# ★ 推奨: 自律実行（ローカルLLMがプランニング＋実行を一括処理）
# デスクトップアプリ操作
python scripts/helix_pilot.py auto "cloudAIタブをクリックしてhelloと入力し送信" --window "Helix AI Studio" --compact

# ブラウザ操作
python scripts/helix_pilot.py browse "note.comで新規記事を作成しタイトルを入力" --window "Google Chrome" --compact

# --dry-run: プランのみ表示（実行しない）。安全確認に使用
python scripts/helix_pilot.py auto "設定タブを開いてモデルを変更" --window "Helix AI Studio" --dry-run --compact
```

### 出力モード（`--compact` / `--output-mode`）

```bash
# compact: 不要フィールド除去+説明文500文字制限（推奨）
python scripts/helix_pilot.py describe --window "Helix AI Studio" --compact

# minimal: ok/errorのみ（最小コンテキスト消費）
python scripts/helix_pilot.py click 100 50 --window "Helix AI Studio" --output-mode minimal

# normal: v1.0互換の詳細出力（デフォルト、configで変更可能）
python scripts/helix_pilot.py find "送信ボタン" --window "Helix AI Studio" --output-mode normal
```

### 基本コマンド一覧（v1.0互換）

```bash
# 状態確認
python scripts/helix_pilot.py status

# スクリーンショット撮影
python scripts/helix_pilot.py screenshot --window "Helix AI Studio" --name shot1

# Vision LLM で画面を説明（キャッシュ機能付き: 画面未変更時はLLM呼び出し省略）
python scripts/helix_pilot.py describe --window "Helix AI Studio"

# UI要素の座標を特定
python scripts/helix_pilot.py find "送信ボタン" --window "Helix AI Studio"

# 操作結果の検証
python scripts/helix_pilot.py verify "メッセージが送信された" --window "Helix AI Studio"

# クリック / テキスト入力 / ホットキー / スクロール
python scripts/helix_pilot.py click 100 50 --window "Helix AI Studio"
python scripts/helix_pilot.py type "テストメッセージ" --window "Helix AI Studio"
python scripts/helix_pilot.py hotkey ctrl+c --window "Helix AI Studio"
python scripts/helix_pilot.py scroll -3 --window "Helix AI Studio"

# クリック＋スクリーンショット（ポップアップ保持）
python scripts/helix_pilot.py click-screenshot 100 50 --window "Helix AI Studio" --delay 0.3

# 画面安定待ち / GIF録画 / シナリオ
python scripts/helix_pilot.py wait-stable --timeout 60 --window "Helix AI Studio"
python scripts/helix_pilot.py record --window "Helix AI Studio" --name demo --duration 10 --fps 5
python scripts/helix_pilot.py run-scenario demo_captures/scenarios/test.json
```

### 推奨ワークフロー（v2.0）

```bash
# ★ 複数ステップ操作 → auto コマンド1回で完了
python scripts/helix_pilot.py auto "cloudAIタブを開き、テスト入力して送信" --window "Helix AI Studio" --compact

# ★ ブラウザ操作 → browse コマンド1回で完了
python scripts/helix_pilot.py browse "Zennにログインして新規記事を作成" --window "Google Chrome" --compact

# 安全確認したい場合: --dry-run でプラン確認 → 問題なければ実行
python scripts/helix_pilot.py auto "設定を変更" --window "Helix AI Studio" --dry-run --compact
# プラン確認後:
python scripts/helix_pilot.py auto "設定を変更" --window "Helix AI Studio" --compact
```

### セキュリティ保護

**既存の保護（v1.0）:**
- **safe_mode**: `--window` 引数が必須（全画面操作禁止）
- **denied_windows**: Task Manager, Windows Security 等は操作不可
- **denied_input_patterns**: password, credential, token 等のテキスト入力を拒否
- **緊急停止**: マウスを画面左上隅に移動 → 即座に中止
- **ユーザー操作優先**: ユーザーのマウス/キーボード操作を検知すると自動一時停止

**v2.0 追加: ActionValidator（LLM生成アクションの安全検証）:**
- **アクションホワイトリスト**: 許可された種別のみ実行可能
- **禁止ホットキー**: Alt+F4, Ctrl+Alt+Del, Win+R, Win+L, Ctrl+W 等を拒否
- **禁止URLパターン**: file://, chrome://settings, localhost, LAN IP を拒否
- **禁止テキスト**: `<script`, `javascript:`, `rm -rf` 等の危険パターンを拒否
- **文字数制限**: 1ステップ5000文字まで
- **スクロール/待機制限**: 量・時間の上限あり
- **ドメイン制限**: `browse_config.denied_domains` で銀行サイト等をブロック
- **プラン全体検証**: 実行前に全ステップを一括検証、不正ステップは除外

---

## よく使うコマンド

```bash
# Python 構文チェック（変更後は必ず実行）
python -m py_compile src/web/server.py src/tabs/claude_tab.py

# i18n 構文チェック
python -c "import json; json.load(open('i18n/ja.json')); json.load(open('i18n/en.json')); print('OK')"

# ソースバンドル生成（Claudeへの共有用）
python scripts/build_bundle.py

# Web UI ビルド（フロントエンド変更後は必ず実行）
cd frontend && npm run build && cd ..

# BIBLE の存在確認
ls BIBLE_Helix_AI_Studio_*.md
```

---

## よくある作業パターン

### 新しい i18n キーを追加する場合

1. `i18n/ja.json` に日本語テキストを追加
2. `i18n/en.json` に同じキーで英語テキストを追加
3. コードで `t('新しいキー')` を使用

### 新しい WebSocket ハンドラを追加する場合

`src/web/server.py` の `_handle_solo_execute` を参考にし、以下を含める:
- JWT認証
- 実行ロック（`_set_execution_lock` / `_release_execution_lock`）
- ChatStore連携（`chat_store.create_chat`, `add_message`）
- Discord通知（started/completed/error の3点）
- RAG保存（`_save_web_conversation`）

### 新しいデスクトップタブを追加する場合

`src/tabs/local_ai_tab.py` をテンプレートとして:
- `_create_chat_tab()`: チャット表示 + 入力エリア
- `_create_continue_panel()`: 会話継続パネル
- `_create_settings_tab()`: 設定サブタブ
- `retranslateUi()`: i18n対応

---

## 詳細仕様の参照先

| 知りたいこと | 参照先 |
|---|---|
| 全体アーキテクチャ | `BIBLE_Helix_AI_Studio_11_5_3.md` §3 |
| バージョン変遷 | `BIBLE_Helix_AI_Studio_11_5_3.md` §2 |
| 実装済み機能一覧 | `BIBLE_Helix_AI_Studio_11_5_3.md` §設計哲学 |
| Changelog | `BIBLE_Helix_AI_Studio_11_5_3.md` §Changelog |
| Web APIエンドポイント | `src/web/api_routes.py` の docstring |
| モデル設定 | `config/cloud_models.example.json` |
