# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.6.0
**アプリケーションバージョン**: 4.6.0 "Helix AI Studio - Claude主導型アーキテクチャ・GPUモニター強化"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.6.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.6.0 はClaude主導型アーキテクチャへの刷新とGPUモニターの大幅強化:

1. **Claude主導型アーキテクチャ**: Claude CLIを経由してMCPツール（Web検索、ファイル操作等）を実際に実行
2. **ローカルLLMの役割明確化**: 計画立案・検証の補助ツールとして位置づけ、実際のアクションはClaude主導
3. **GPUモニター時間軸選択**: 60秒/5分/15分/30分/1時間から選択可能
4. **GPUモニターシークバー**: スライダーで過去のデータを参照可能

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | mixAIがローカルLLMで「計画」だけ出力する問題 | Stage 2をClaude CLI経由で実際にMCPツールを実行するアーキテクチャに刷新 | Claude CLIで実際のWeb検索・ファイル操作を実行 |
| 2 | GPUモニター時間軸が細かすぎる | 時間範囲選択コンボボックス追加（60秒/5分/15分/30分/1時間） | ユーザーが任意の時間範囲を選択可能 |
| 3 | 過去のGPU変化が確認できない | シークバー（スライダー）追加で過去のデータを参照可能 | スライダーで過去の任意時点のグラフ表示 |

---

## ファイル変更一覧 (v4.6.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/helix_orchestrator_tab.py` | Claude CLI実行機能追加、GPUUsageGraph時間軸選択・シークバー対応、Stage 2をClaude実行に変更 |
| `src/backends/tool_orchestrator.py` | ドキュメントヘッダー更新（v4.6アーキテクチャ説明） |
| `src/utils/constants.py` | バージョン 4.5.0 → 4.6.0、APP_DESCRIPTION更新 |
| `BIBLE/BIBLE_Helix AI Studio_4.6.0.md` | 本ファイル追加 |

---

## Claude主導型アーキテクチャ (v4.6.0)

### 設計思想

v4.6では、mixAIのアーキテクチャを根本から刷新しました：

**従来 (v4.5以前)**:
```
ユーザー入力
    ↓
ローカルLLM (Stage 1-5) → 各ステージでローカルLLMが処理
    ↓
出力（計画のみ、実際のアクションは実行されない）
```

**新アーキテクチャ (v4.6)**:
```
ユーザー入力
    ↓
Stage 1: タスク分析（ローカルLLM）→ 計画立案
    ↓
Stage 2: Claude CLI実行 → MCPツールで実際にWeb検索・ファイル操作を実行
    ↓
Stage 3-5: 画像解析・RAG・バリデーション
    ↓
出力（実際のアクション結果を含む）
```

### Claude CLI実行機能

```python
def _execute_claude_cli(self, prompt: str, timeout_seconds: int = 300) -> Dict[str, Any]:
    """
    Claude CLIを呼び出してMCPツールを実行

    - Claude CLIの存在を自動検出
    - --print オプションで非対話モード実行
    - タイムアウト対応（デフォルト5分）
    - エラー時はローカルLLMにフォールバック
    """
```

### Stage 2の処理フロー

```python
def _execute_stage_2_claude_execution(self):
    """
    1. Stage 1の分析結果をコンテキストとして利用
    2. Claude CLIにMCPツール実行を指示
    3. 成功時: Claude CLIの出力を使用
    4. 失敗時: ローカルLLM（qwen3-coder）にフォールバック
    """
```

---

## GPUモニター強化 (v4.6.0)

### 時間範囲選択

```python
TIME_RANGES = {
    "60秒": 60,
    "5分": 300,
    "15分": 900,
    "30分": 1800,
    "1時間": 3600,
}
```

### シークバー機能

```python
def set_view_offset(self, offset_seconds: int):
    """表示オフセットを設定（過去のデータを参照）"""
    self.view_offset = max(0, offset_seconds)
    self.update()

def get_data_duration(self) -> float:
    """記録データの全期間（秒）を取得"""
```

### UI構成 (v4.6)

```
📊 GPUモニター (v4.6: 時間軸選択・シークバー対応)
├── [GPUUsageGraph] - リアルタイムグラフ（最大1時間分保存）
│   ├── GPU 0: 緑
│   ├── GPU 1: 青
│   └── イベントマーカー: オレンジ縦線
├── [時間軸コントロール行]
│   ├── 時間範囲: [60秒 | 5分 | 15分 | 30分 | 1時間]
│   └── 過去を表示: [━━━━━━━●━━] -30秒
├── [GPU情報テキスト] - 現在のVRAM使用量
├── [ボタン行]
│   ├── 🔄 GPU情報更新
│   ├── ▶ 記録開始 / ⏹ 記録停止
│   ├── 🗑️ クリア
│   └── ⏩ 現在（シークバーをリセット）
└── 💡 説明: "スライダーで過去のデータを参照できます"
```

---

## 5ステージパイプライン (v4.6更新)

### パイプライン構成

```
Stage 1: タスク分析
    ↓ (nemotron-3-nano:30b) - ローカルLLM
Stage 2: Claude実行 ★v4.6新規
    ↓ (Claude CLI + MCP) - 実際のアクション実行
Stage 3: 画像解析
    ↓ (ministral-3:8b, 画像パス指定時のみ)
Stage 4: RAG検索
    ↓ (qwen3-embedding:4b, RAG有効時のみ)
Stage 5: バリデーションレポート
    ↓ (nemotron-3-nano:30b)
最終出力
```

---

## 常駐モデル構成 (継続: v4.2より)

### RTX PRO 6000 (96GB) — 推論メイン

| モデル | VRAM | 役割 |
|--------|------|------|
| Nemotron-3-Nano:30B | ~24GB | テキスト推論（常駐） |
| **空き** | **~72GB** | オンデマンドスロット |

### RTX 5070 Ti (16GB) — Embedding + Image常駐

| モデル | VRAM | 役割 |
|--------|------|------|
| qwen3-embedding:4b | 2.5GB | RAG埋め込み（常駐） |
| ministral-3:8b | 6.0GB | 画像理解（常駐） |
| OS/ドライバ/Ollama | ~1.0GB | システム |
| KVキャッシュ余裕 | ~6.5GB | 推論時動的確保 |

---

## タブ構成 (v4.6.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.6** | チャット / 設定 | **Claude主導型・GPUモニター強化** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## v4.5.0からの継承課題

- [x] ローカルLLMが計画のみ出力する問題 → **v4.6でClaude主導型に刷新**
- [x] GPUモニター時間軸が細かすぎる → **v4.6で時間軸選択追加**
- [x] 過去のGPU変化が確認できない → **v4.6でシークバー追加**
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI
- [ ] FAISS全インデックス再構築スクリプト

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | ~80.4 MB |
| exe (root) | `HelixAIStudio.exe` | ~80.4 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.6.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude CLI / Claude API / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.7以降)

1. **ストリーミング応答**: Ollamaからのリアルタイム応答表示
2. **チャット履歴エクスポート**: JSON/Markdown形式での会話保存
3. **RAG本格統合**: FAISS + SQLiteによるベクトルストア強化
4. **複数GPU負荷分散**: GPU割り当ての動的最適化
5. **パイプラインカスタマイズ**: ユーザー定義ステージの追加
6. **Claude CLI設定UI**: Claude CLIパスの手動設定オプション

---

## 参考文献

- BIBLE_Helix AI Studio_4.5.0.md (前バージョン)
- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Anthropic Claude Documentation
- Ollama API Documentation
