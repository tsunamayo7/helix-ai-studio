# Helix AI Studio v7.0.0 → v7.1.0 修正指示書
# Claude Opus 4.6 対応 & モデル選択機能の拡充

## コードネーム: v7.1.0 "Adaptive Models"

---

## ■ 概要

現在のHelix AI Studio v7.0.0は、Claude設定のモデルドロップダウンが「Claude Opus 4.5 (最高品質)」にハードコードされており、最新のClaude Opus 4.6に対応していない。
本修正では以下を実施する:

1. Claudeモデル選択の動的化（Opus 4.6対応 + 将来のモデル追加を容易にする設計）
2. Claude Code CLIの`--model`オプション対応
3. 3Phase実行パイプラインの各Phase呼び出しでモデル指定を反映
4. 設定の永続化（選択したモデルをconfig.jsonに保存・復元）
5. UI上のモデル表示名・説明の更新

---

## ■ 作業前の必須手順

以下のファイルを**全文読み込んでから**作業を開始すること。推測での修正は禁止。

```bash
# 1. 定数定義（モデル名がハードコードされている可能性）
cat src/utils/constants.py

# 2. mixAIタブUI（モデルドロップダウンの実装箇所）
cat src/tabs/helix_orchestrator_tab.py

# 3. 3Phase実行エンジン（Claude CLI呼び出し箇所）
cat src/backends/mix_orchestrator.py

# 4. Claude CLIバックエンド（CLIコマンド構築箇所）
cat src/backends/claude_cli_backend.py

# 5. soloAIタブ（Claude単独チャットのモデル選択）
cat src/tabs/claude_tab.py

# 6. 設定保存・読込のロジック
cat src/tabs/settings_cortex_tab.py

# 7. 現在のconfigファイル
cat config/settings.json 2>/dev/null || echo "settings.json not found"
cat config/config.json 2>/dev/null || echo "config.json not found"
```

---

## ■ 修正1: constants.py — Claudeモデル定義の追加

### 目的
モデル一覧を1箇所で管理し、UI・バックエンド両方から参照できるようにする。

### 実装内容

`src/utils/constants.py` に以下の定数を追加:

```python
# ============================================================
# Claude Models Definition (v7.1.0)
# ============================================================
# Claude Code CLIで使用可能なモデル一覧
# --model オプションに渡す値をkeyとする
CLAUDE_MODELS = [
    {
        "id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6 (最高知能)",
        "description": "最も高度で知的なモデル。複雑な推論・計画立案に最適",
        "tier": "opus",
        "is_default": True,
    },
    {
        "id": "claude-opus-4-5-20250929",
        "display_name": "Claude Opus 4.5 (高品質・バランス)",
        "description": "高品質でバランスの取れた応答。安定性重視の場合に推奨",
        "tier": "opus",
        "is_default": False,
    },
    {
        "id": "claude-sonnet-4-5-20250929",
        "display_name": "Claude Sonnet 4.5 (高速・コスト効率)",
        "description": "高速応答とコスト効率のバランス。日常的なタスクに最適",
        "tier": "sonnet",
        "is_default": False,
    },
]

# デフォルトモデルID
DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"

# 思考モード定義
CLAUDE_THINKING_MODES = [
    {"id": "none", "display_name": "なし", "description": "思考なし（最速）"},
    {"id": "Deep", "display_name": "Deep", "description": "深い推論（推奨）"},
]
DEFAULT_THINKING_MODE = "Deep"
```

### 注意事項
- `APP_VERSION` を `"7.1.0"` に更新
- `APP_CODENAME` を `"Adaptive Models"` に更新
- 既存の定数（APP_NAME等）は変更しない

---

## ■ 修正2: helix_orchestrator_tab.py — 設定タブUI更新

### 目的
「Claude設定」セクションのモデルドロップダウンをCLAUDE_MODELSから動的生成する。

### 修正箇所の特定方法
ファイル内で以下を検索:
- `"Claude Opus 4.5"` または `"Opus"` の文字列 → ハードコードされたモデル名
- `QComboBox` でモデル選択を構築している箇所
- `claude_model` や `model_combo` 等の変数名

### 実装内容

```python
from src.utils.constants import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL_ID

# モデルドロップダウン構築（既存のQComboBoxを置き換え）
self.claude_model_combo = QComboBox()
for model in CLAUDE_MODELS:
    self.claude_model_combo.addItem(
        model["display_name"],  # 表示テキスト
        userData=model["id"]    # 内部値（CLIに渡す値）
    )
# デフォルト選択
default_idx = next(
    (i for i, m in enumerate(CLAUDE_MODELS) if m["id"] == DEFAULT_CLAUDE_MODEL_ID),
    0
)
self.claude_model_combo.setCurrentIndex(default_idx)

# ツールチップにモデル説明を表示
self.claude_model_combo.currentIndexChanged.connect(self._on_model_changed)

def _on_model_changed(self, index):
    model_id = self.claude_model_combo.currentData()
    model_info = next((m for m in CLAUDE_MODELS if m["id"] == model_id), None)
    if model_info:
        self.claude_model_combo.setToolTip(model_info["description"])
```

### 設定の永続化
- `_save_settings()` で `config["claude_model_id"] = self.claude_model_combo.currentData()` を保存
- `_load_settings()` で保存済みモデルIDからドロップダウンのインデックスを復元:

```python
saved_model_id = config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
for i in range(self.claude_model_combo.count()):
    if self.claude_model_combo.itemData(i) == saved_model_id:
        self.claude_model_combo.setCurrentIndex(i)
        break
```

---

## ■ 修正3: mix_orchestrator.py — 3Phase実行でのモデル指定

### 目的
Phase 1とPhase 3のClaude CLI呼び出しで、ユーザーが選択したモデルを`--model`オプションで指定する。

### 修正箇所の特定方法
ファイル内で以下を検索:
- `claude` コマンドを構築している箇所（`subprocess.run` や `cmd = [...]`）
- `_run_claude_cli` メソッド
- `--output-format json` を含むコマンド構築

### 実装内容

#### 3-a: モデルID取得の追加

`_run_claude_cli()` メソッド（またはPhase実行メソッド）に `model_id` パラメータを追加:

```python
def _run_claude_cli(self, prompt: str, system_prompt: str = "",
                     cwd: str = None, model_id: str = None) -> dict:
    """Claude Code CLIを実行"""
    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    # v7.1.0: モデル指定
    if model_id:
        cmd.extend(["--model", model_id])

    if system_prompt:
        cmd.extend(["--system", system_prompt])

    if cwd:
        # subprocess.run の cwd パラメータで指定（v7.0.0で修正済み）
        pass

    cmd.append("--dangerously-skip-permissions")
    # ... 既存の実行ロジック
```

#### 3-b: Phase 1/Phase 3 呼び出しでのモデル指定

```python
def _execute_phase1(self, user_message, ...):
    # 設定からモデルIDを取得
    model_id = self.config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
    result = self._run_claude_cli(
        prompt=phase1_prompt,
        system_prompt=self._build_phase1_system_prompt(),
        cwd=project_dir,
        model_id=model_id  # v7.1.0追加
    )
    # ...

def _execute_phase3(self, phase1_result, phase2_results, ...):
    model_id = self.config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
    result = self._run_claude_cli(
        prompt=phase3_prompt,
        system_prompt=self._build_phase3_system_prompt(),
        model_id=model_id  # v7.1.0追加
    )
    # ...
```

#### 3-c: configからの設定読み取り

MixAIOrchestratorの初期化時またはexecute時にconfigを受け取る仕組みを確認し、
`claude_model_id` がconfigから取得できるようにする。
既にconfigをコンストラクタまたはメソッド引数で受け取っている場合はそれを利用する。

---

## ■ 修正4: claude_cli_backend.py — soloAIタブ用のモデル対応

### 目的
soloAIタブ（Claude単独チャット）でも選択されたモデルを使用できるようにする。

### 修正箇所の特定方法
- `claude` コマンド構築箇所
- soloAIタブからバックエンドを呼び出す経路

### 実装内容
`_run_claude_cli` や `generate` メソッドに同様の `--model` オプション追加。
soloAIタブのUIにもモデル選択ドロップダウンがある場合は、同じ `CLAUDE_MODELS` 定数を使って動的生成する。

---

## ■ 修正5: claude_tab.py — soloAIタブのモデル選択UI

### 目的
soloAIタブにもモデル選択機能があるか確認し、あればCLAUDE_MODELSで動的化する。

### 確認・修正内容
- ファイルを読み、モデル選択UIの有無を確認
- 存在する場合: `CLAUDE_MODELS` からドロップダウンを生成（修正2と同じパターン）
- 存在しない場合: mixAIの設定を共有する形でOK（変更不要）

---

## ■ 修正6: VRAM Simulator のClaude表示更新（任意）

### 目的
VRAM Budget Simulatorの表示にClaudeモデル情報がハードコードされている場合、更新する。

### 確認箇所
```bash
grep -r "Opus 4.5" src/widgets/vram_simulator.py
grep -r "Opus 4.5" src/widgets/neural_visualizer.py
```

ハードコードが見つかった場合、動的にconfigの選択モデルを参照するか、
表示テキストを「Claude (選択モデル)」に変更する。

---

## ■ 修正7: ステータスバー / ツール実行ログの表示更新

### 目的
実行時のログやステータスバーに表示されるClaude情報を正確にする。

### 確認箇所
```bash
grep -rn "Opus" src/ --include="*.py"
grep -rn "claude_model\|Claude CLI (MCP)" src/ --include="*.py"
```

「Claude CLI (MCP)」などの表示が固定文字列の場合、選択モデル名を動的に表示するよう修正:
```python
# 例: ツール実行ログの表示
model_name = config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
display_name = next(
    (m["display_name"] for m in CLAUDE_MODELS if m["id"] == model_name),
    "Claude"
)
log_entry = f"Phase 1: {display_name}"
```

---

## ■ 修正8: PyInstallerビルド確認

### 実施内容
```bash
# ビルド
pyinstaller HelixAIStudio.spec --noconfirm

# ビルド成功確認
ls -la dist/HelixAIStudio.exe
```

---

## ■ 修正9: BIBLE v7.1.0 生成

### 実施内容
`BIBLE/BIBLE_Helix AI Studio_7.1.0.md` を新規作成。
以下を記載:
- v7.1.0 "Adaptive Models" の変更概要
- CLAUDE_MODELS定数の仕様
- `--model` オプションの導入
- 変更ファイル一覧
- v7.0.0→v7.1.0 移行ガイド

---

## ■ 受入条件チェックリスト

### モデル選択機能
- [ ] mixAI設定タブのモデルドロップダウンに3モデル（Opus 4.6, Opus 4.5, Sonnet 4.5）が表示される
- [ ] デフォルトが「Claude Opus 4.6 (最高知能)」になっている
- [ ] モデル選択を変更してアプリを再起動しても、選択が保持される
- [ ] モデルにカーソルを合わせると説明がツールチップ表示される

### 3Phase実行でのモデル反映
- [ ] Phase 1のClaude CLI呼び出しに `--model claude-opus-4-6` が含まれる
- [ ] Phase 3のClaude CLI呼び出しに `--model claude-opus-4-6` が含まれる
- [ ] 設定でOpus 4.5に変更した場合、Phase 1/3で `--model claude-opus-4-5-20250929` が使われる
- [ ] ツール実行ログに正しいモデル名が表示される

### soloAIタブ
- [ ] soloAIタブでもモデル選択が反映される（UIがある場合）

### 一般品質
- [ ] constants.py の APP_VERSION が "7.1.0" である
- [ ] PyInstallerビルドが成功する
- [ ] BIBLE v7.1.0 が生成される
- [ ] 「Claude Opus 4.5」のハードコード文字列がソースコード中に残っていない
  - 確認: `grep -rn "Opus 4.5" src/ --include="*.py"` → 0件

---

## ■ 将来の拡張性について

この設計により、新しいClaudeモデルが追加された場合:
1. `constants.py` の `CLAUDE_MODELS` リストに1エントリ追加するだけ
2. UI・バックエンド・設定保存はすべて自動対応
3. `is_default` フラグでデフォルトモデルを切り替え可能

---

*この修正指示書は Claude Opus 4.6 により作成されました*
*2026-02-09*
