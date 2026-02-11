v7.1.0 "Adaptive Models" アップグレードを実施してください。

## 目的
Claude Opus 4.6に対応し、モデル選択を動的化する。

## 作業前の必須手順
以下のファイルを全文読んでから修正を開始すること:
- src/utils/constants.py
- src/tabs/helix_orchestrator_tab.py
- src/backends/mix_orchestrator.py
- src/backends/claude_cli_backend.py
- src/tabs/claude_tab.py

## 修正内容

### 1. constants.py
APP_VERSION = "7.1.0", APP_CODENAME = "Adaptive Models" に更新。
以下の定数を追加:

```python
CLAUDE_MODELS = [
    {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6 (最高知能)", "description": "最も高度で知的なモデル。複雑な推論・計画立案に最適", "tier": "opus", "is_default": True},
    {"id": "claude-opus-4-5-20250929", "display_name": "Claude Opus 4.5 (高品質)", "description": "高品質でバランスの取れた応答。安定性重視", "tier": "opus", "is_default": False},
    {"id": "claude-sonnet-4-5-20250929", "display_name": "Claude Sonnet 4.5 (高速)", "description": "高速応答とコスト効率。日常タスク向き", "tier": "sonnet", "is_default": False},
]
DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"
```

### 2. helix_orchestrator_tab.py（mixAI設定タブ）
「Claude設定」セクションのモデルドロップダウンを CLAUDE_MODELS から動的生成に変更。
- QComboBox の addItem(display_name, userData=model_id) パターンで構築
- 設定保存: config["claude_model_id"] = combo.currentData()
- 設定復元: 保存済みmodel_idからインデックスを復元
- ツールチップにmodel descriptionを表示

### 3. mix_orchestrator.py（3Phase実行エンジン）
_run_claude_cli() メソッドに model_id パラメータを追加。
Claude CLIコマンド構築時に --model {model_id} を挿入:
```python
if model_id:
    cmd.extend(["--model", model_id])
```
Phase 1 (_execute_phase1) と Phase 3 (_execute_phase3) の呼び出しで、
config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID) を渡す。

### 4. claude_cli_backend.py / claude_tab.py（soloAIタブ）
soloAIタブにモデル選択UIがあれば同じCLAUDE_MODELS定数で動的化。
Claude CLI呼び出しに --model オプションを追加。

### 5. ハードコード文字列の除去
ソースコード全体から "Opus 4.5" や "Claude Opus 4.5" のハードコードを検索し、
CLAUDE_MODELS からの動的参照に置き換える:
```bash
grep -rn "Opus 4.5" src/ --include="*.py"
```

### 6. ツール実行ログ・ステータスバー
Phase実行時のログ表示で、固定文字列「Claude CLI (MCP)」等を
選択モデルの display_name に動的変更。

### 7. ビルド＆BIBLE
- pyinstaller HelixAIStudio.spec --noconfirm でビルド確認
- BIBLE/BIBLE_Helix AI Studio_7.1.0.md を新規作成

## 受入条件
- モデルドロップダウンに3モデルが表示される（デフォルト: Opus 4.6）
- Phase 1/3のClaude CLI呼び出しに --model が含まれる
- 設定変更がアプリ再起動後も保持される
- grep -rn "Opus 4.5" src/ --include="*.py" が0件
- PyInstallerビルドが成功する
