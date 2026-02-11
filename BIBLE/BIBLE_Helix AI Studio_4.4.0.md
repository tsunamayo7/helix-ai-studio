# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.4.0
**アプリケーションバージョン**: 4.4.0 "Helix AI Studio - マルチステージパイプライン実行"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.4.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.4.0 はmixAIタブに5ステージマルチパイプライン実行機能を追加:

1. **5ステージパイプライン実行**: タスク分析→コード処理→画像解析→RAG検索→バリデーションレポート
2. **使用モデル自己申告機能**: 各ステージ終了時に「(自己申告) 使用モデル: xxx」を自動出力
3. **画像パス自動検出**: プロンプト内の画像パスを正規表現で検出し、Stage 3に自動渡し
4. **最終バリデーションレポート生成**: 全ステージの結果をPASS/FAIL判定付きでまとめ

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | マルチステージパイプライン実行 | MixAIWorker.run()を5ステージ順次実行に再構築 | ✅ |
| 2 | Stage 1: タスク分析 | 万能エージェント（nemotron-3-nano:30b）で実行計画生成 | ✅ |
| 3 | Stage 2: コード処理 | コード特化（qwen3-coder:30b）でスクリプト生成 | ✅ |
| 4 | Stage 3: 画像解析 | ministral-3:8bで画像からJSON抽出、画像なし時はスキップ | ✅ |
| 5 | Stage 4: RAG検索 | qwen3-embedding:4bでRAG検索、無効時はスキップ | ✅ |
| 6 | Stage 5: バリデーションレポート | 全ステージ結果をPASS/FAIL判定付きでレポート生成 | ✅ |
| 7 | 使用モデル自己申告 | 各ステージ出力末尾に「(自己申告) 使用モデル: xxx」自動追加 | ✅ |
| 8 | 画像パス自動検出 | _extract_image_path()でプロンプト内パスを正規表現抽出 | ✅ |

---

## ファイル変更一覧 (v4.4.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/helix_orchestrator_tab.py` | MixAIWorkerを5ステージパイプラインに再構築、_extract_image_path()追加、バージョン表記更新 |
| `src/backends/tool_orchestrator.py` | ドキュメントヘッダーにv4.4更新内容を追加 |
| `src/utils/constants.py` | バージョン 4.3.0 → 4.4.0、APP_DESCRIPTION更新 |
| `src/main_window.py` | mixAIタブのツールチップをv4.4仕様に更新 |
| `BIBLE/BIBLE_Helix AI Studio_4.4.0.md` | 本ファイル追加 |

---

## 5ステージパイプライン詳細 (v4.4.0)

### パイプライン構成

```
Stage 1: タスク分析
    ↓ (nemotron-3-nano:30b)
Stage 2: コード処理
    ↓ (qwen3-coder:30b)
Stage 3: 画像解析
    ↓ (ministral-3:8b, 画像パス指定時のみ)
Stage 4: RAG検索
    ↓ (qwen3-embedding:4b, RAG有効時のみ)
Stage 5: バリデーションレポート
    ↓ (nemotron-3-nano:30b)
最終出力
```

### 各ステージの詳細

#### Stage 1: タスク分析
- **モデル**: nemotron-3-nano:30b (万能エージェント)
- **目的**: タスクを分析し、最大6行の実行計画を生成
- **出力**: 設計・仮説・モデル割り当ての計画

#### Stage 2: コード処理
- **モデル**: qwen3-coder:30b (コード特化)
- **目的**: PowerShell/Pythonスクリプトの生成
- **入力**: Stage 1の分析結果をコンテキストとして使用

#### Stage 3: 画像解析
- **モデル**: ministral-3:8b (画像解析)
- **目的**: 画像からJSON形式で情報抽出
- **抽出項目**:
  - selected_claude_model: 選択Claudeモデル名
  - auth_method: 認証方式
  - thinking_setting: Thinking設定
  - ollama_host: OllamaホストURL
  - ollama_connection_status: 接続ステータス
  - resident_models: 常駐モデルとGPU割り当て
  - gpu_monitor: GPU名、VRAM使用量
- **スキップ条件**: 画像パスが指定されていない場合

#### Stage 4: RAG検索
- **モデル**: qwen3-embedding:4b (Embedding)
- **目的**: コンテキストに関連する情報をRAG検索
- **スキップ条件**: config.rag_enabled = False の場合

#### Stage 5: バリデーションレポート
- **モデル**: nemotron-3-nano:30b (万能エージェント)
- **目的**: 全ステージ結果をPASS/FAIL判定付きでまとめ
- **出力フォーマット**:
```markdown
## 最終バリデーションレポート

### 判定結果: **PASS/FAIL**

### ステージ実行ログ

| Stage | 名前 | モデル | 結果 |
|-------|------|--------|------|
| 1 | タスク分析 | nemotron-3-nano:30b | ✅ |
| 2 | コード処理 | qwen3-coder:30b | ✅ |
| ...

(自己申告) 使用モデル: xxx
```

---

## 使用モデル自己申告機能

### 仕様
- 各ステージの出力末尾に自動的に追加
- フォーマット: `(自己申告) 使用モデル: {model_name}`
- ToolResult.metadataから取得、フォールバックはconfig値

### 実装例
```python
model_name = result.metadata.get("model", self.config.universal_agent_model)
output_with_model = f"{result.output}\n\n(自己申告) 使用モデル: {model_name}"
result.output = output_with_model
```

---

## 画像パス自動検出機能

### 検出パターン
1. 引用符で囲まれたパス: `"C:\path\to\image.png"`
2. Windows絶対パス: `C:\Users\...\image.jpg`
3. Unix絶対パス: `/home/.../image.png`

### 対応拡張子
- png, jpg, jpeg, gif, bmp, webp (大文字小文字両対応)

### 実装
```python
def _extract_image_path(self, prompt: str) -> Optional[str]:
    # 正規表現でパスを検出
    # os.path.exists()で実在確認
    # 最初にマッチした有効なパスを返す
```

---

## ツール実行ログUI (継続: v4.3.0より)

### 列構成
```
| ツール      | モデル                    | ステータス | 実行時間 | 出力              |
|------------|--------------------------|-----------|---------|------------------|
| タスク分析  | nemotron-3-nano:30b      | ✅        | 22035ms | We need to...    |
| コード処理  | qwen3-coder:30b          | ✅        | 15817ms | powershell...    |
| 画像解析   | ministral-3:8b           | ✅        | 5200ms  | {"claude_...     |
| RAG検索    | qwen3-embedding:4b       | ✅        | 3100ms  | 関連度の高い...    |
| バリデーション| nemotron-3-nano:30b     | ✅        | 8500ms  | ## 最終バリ...    |
```

---

## 常駐モデル構成 (継続: v4.2.0より)

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

## タブ構成 (v4.4.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.4** | チャット / 設定 | **5ステージマルチパイプライン実行** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## v4.3.0からの継承課題

- [x] マルチステージパイプライン実行 → **v4.4で解決**
- [x] 使用モデル自己申告 → **v4.4で解決**
- [ ] Claude API経由でのMCPツール統合
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
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.4.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.5以降)

1. **ストリーミング応答**: Ollamaからのリアルタイム応答表示
2. **チャット履歴エクスポート**: JSON/Markdown形式での会話保存
3. **RAG本格統合**: FAISS + SQLiteによるベクトルストア強化
4. **複数GPU負荷分散**: GPU割り当ての動的最適化
5. **パイプラインカスタマイズ**: ユーザー定義ステージの追加

---

## 参考文献

- BIBLE_Helix AI Studio_4.3.0.md (前バージョン)
- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Anthropic Claude Documentation
- Ollama API Documentation
