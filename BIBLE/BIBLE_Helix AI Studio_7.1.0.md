# Helix AI Studio - Project BIBLE (包括的マスター設計書)

**バージョン**: 7.1.0 "Adaptive Models"
**アプリケーションバージョン**: 7.1.0
**作成日**: 2026-02-09
**最終更新**: 2026-02-09
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v7.1.0 "Adaptive Models" 更新履歴

### コンセプト: "Adaptive Models" (適応型モデル選択)

v7.1.0はClaude Opus 4.6への対応と、Claudeモデル選択の動的化を実施。ハードコードされたモデル名を`CLAUDE_MODELS`定数に統合し、新モデル追加時にconstants.pyの1箇所変更で全UIに反映される設計に刷新:

### 主な変更点

1. **Claude Opus 4.6対応**
   - Claude Opus 4.6を新デフォルトモデルとして追加
   - `DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"`
   - 最も高度で知的なモデル。複雑な推論・計画立案に最適

2. **CLAUDE_MODELS定数による動的モデル選択**
   - `src/utils/constants.py`に`CLAUDE_MODELS`リストを新設
   - 各モデル定義: `id`, `display_name`, `description`, `tier`, `is_default`
   - ヘルパー関数: `get_claude_model_by_id()`, `get_default_claude_model()`
   - 全UIのドロップダウンが`CLAUDE_MODELS`から自動生成
   - `QComboBox.addItem(display_name, userData=model_id)`パターンで実装

3. **mixAIタブ(helix_orchestrator_tab.py)の動的化**
   - Claude設定セクションのモデルドロップダウンをCLAUDE_MODELSから動的生成
   - 設定保存: `config.claude_model_id = combo.currentData()`
   - 設定復元: 保存済みmodel_idからインデックスを自動復元
   - ステータスバーに選択モデル名を動的表示

4. **soloAIタブ(claude_tab.py)の動的化**
   - ツールバーのmodel_comboをCLAUDE_MODELSから動的生成
   - 設定タブのデフォルトモデル選択も動的化
   - ツールチップもCLAUDE_MODELSのdescriptionから自動生成

5. **Claude CLI呼び出しのmodel_id対応**
   - `_run_claude_cli(prompt, model_id=None)`にmodel_idパラメータ追加
   - Phase 1/Phase 3のClaude CLI呼び出しに`--model {model_id}`を直接渡す
   - `ClaudeCLIBackend.MODEL_MAP`にOpus 4.6エントリ追加
   - `_get_model_id()`で`claude-`で始まるIDはそのまま返す対応

6. **ハードコード文字列の除去**
   - "Opus 4.5"、"Sonnet 4.5 (推奨)"等のハードコードUI文字列を全除去
   - 各所のツールチップ・エラーメッセージをCLAUDE_MODELSからの動的参照に置換

---

## 変更ファイル一覧 (v7.1.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | APP_VERSION=7.1.0, CLAUDE_MODELS定数, ヘルパー関数, ClaudeModelsクラス更新 |
| `src/tabs/helix_orchestrator_tab.py` | Claude設定ドロップダウン動的化, config保存/復元, ステータス表示 |
| `src/tabs/claude_tab.py` | toolbar/settings model_combo動的化, CLI呼び出しmodel_id対応 |
| `src/backends/mix_orchestrator.py` | _run_claude_cli()にmodel_idパラメータ追加, Phase 1/3でmodel_id渡し |
| `src/backends/claude_cli_backend.py` | MODEL_MAPにOpus 4.6追加, _get_model_id()の4.6対応 |
| `src/backends/claude_backend.py` | コメント・エラーメッセージのハードコード除去 |
| `src/backends/cloud_adapter.py` | バックエンドタイプ名のバージョン番号除去 |
| `src/backends/model_repository.py` | モデルメタデータ名のバージョン番号除去 |

---

## CLAUDE_MODELS定数 (v7.1.0)

```python
CLAUDE_MODELS = [
    {"id": "claude-opus-4-6",
     "display_name": "Claude Opus 4.6 (最高知能)",
     "description": "最も高度で知的なモデル。複雑な推論・計画立案に最適",
     "tier": "opus", "is_default": True},
    {"id": "claude-opus-4-5-20250929",
     "display_name": "Claude Opus 4.5 (高品質)",
     "description": "高品質でバランスの取れた応答。安定性重視",
     "tier": "opus", "is_default": False},
    {"id": "claude-sonnet-4-5-20250929",
     "display_name": "Claude Sonnet 4.5 (高速)",
     "description": "高速応答とコスト効率。日常タスク向き",
     "tier": "sonnet", "is_default": False},
]
DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"
```

### モデル追加手順

新モデルを追加する場合、`src/utils/constants.py`の`CLAUDE_MODELS`リストに辞書を追加するだけで全UIに自動反映:

```python
# 例: Claude Sonnet 5.0を追加
CLAUDE_MODELS.append({
    "id": "claude-sonnet-5-0-20260301",
    "display_name": "Claude Sonnet 5.0 (次世代)",
    "description": "次世代のバランスモデル",
    "tier": "sonnet",
    "is_default": False,
})
```

---

## アーキテクチャ概要 (v7.0.0からの継承)

### 3Phase実行パイプライン

```
┌─────────────────────────────────────────────────────────────────┐
│                    3Phase Execution Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Claude CLI計画立案                                     │
│      - --model {CLAUDE_MODEL_ID} で選択モデルを指定              │
│      - --cwdオプション付き、ツール使用指示を明記                   │
│      ↓                                                          │
│  Phase 2: ローカルLLM順次実行                                    │
│      - SequentialExecutor: 1モデルずつロード→実行→アンロード     │
│      ↓                                                          │
│  Phase 3: Claude CLI比較統合                                     │
│      - --model {CLAUDE_MODEL_ID} で選択モデルを指定              │
│      - Phase 1回答 + Phase 2全結果を渡す                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## v7.0.0 → v7.1.0 移行ガイド

### 破壊的変更

なし。v7.0.0からの完全な後方互換性を維持。

### 互換性

- v7.0.0の設定ファイル: `claude_model`キーで保存された値は`claude_model_id`にフォールバック
- `ClaudeModels`クラス: 後方互換性のため維持（`all_models()`がCLAUDE_MODELSのdisplay_nameを返す）
- `ClaudeCLIBackend.MODEL_MAP`: 旧表示名("Claude Opus 4.5 (最高性能)"等)もマッピング済み

### 設定の自動マイグレーション

```python
# helix_orchestrator_tab.py での復元ロジック
saved_model_id = config.claude_model_id or config.claude_model
# → CLAUDE_MODELSのidとマッチすればそのインデックスに復元
# → マッチしなければデフォルト(Opus 4.6)にフォールバック
```

---

*このBIBLEは Claude Opus 4.6 により生成されました*
