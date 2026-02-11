# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.3.0
**アプリケーションバージョン**: 4.3.0 "Helix AI Studio - ツール実行ログ強化 (モデル名表示対応)"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.3.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.3.0 はmixAIタブのツール実行ログにモデル名表示機能を追加:

1. **ツール実行ログに「モデル」列を追加**: 各ツール実行時に使用されたLLMモデル名を表示
2. **モデル識別機能**: nemotron-3-nano:30b, ministral-3:8b等のモデル名をログで確認可能
3. **UI改善**: 列幅調整、色分け表示でモデル識別を容易に

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | ツール実行ログにモデル名を表示 | QTreeWidgetに「モデル」列を追加 | ✅ |
| 2 | モデル情報の伝達 | `_emit_tool_result()`で`ToolResult.metadata`からモデル名を取得・送信 | ✅ |
| 3 | UIでのモデル名表示 | `_on_tool_executed()`でモデル名を表示（青色で強調） | ✅ |
| 4 | バージョン更新 | 4.2.0 → 4.3.0 | ✅ |

---

## ファイル変更一覧 (v4.3.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/helix_orchestrator_tab.py` | ツール実行ログに「モデル」列追加、`_emit_tool_result()`でmodel情報送信、`_on_tool_executed()`でモデル名表示、バージョン表記更新 |
| `src/backends/tool_orchestrator.py` | ドキュメントヘッダーにv4.3更新内容を追加 |
| `src/utils/constants.py` | バージョン 4.2.0 → 4.3.0、APP_DESCRIPTION更新 |
| `BIBLE/BIBLE_Helix AI Studio_4.3.0.md` | 本ファイル追加 |

---

## ツール実行ログUI (v4.3.0)

### 新しい列構成

```
| ツール      | モデル                    | ステータス | 実行時間 | 出力              |
|------------|--------------------------|-----------|---------|------------------|
| タスク分析  | nemotron-3-nano:30b      | ✅        | 37084ms | We need to...    |
| コード処理  | qwen3-coder:30b          | ✅        | 3983ms  | powershell...    |
| 画像解析   | ministral-3:8b           | ✅        | 5200ms  | Image shows...   |
```

### 表示仕様

- **モデル列**: 青色(#60a5fa)で表示、25文字を超える場合は省略表示
- **ステータス列**: 成功=緑色(#22c55e)、失敗=赤色(#ef4444)
- **出力列**: 40文字を超える場合は省略表示（"..."で終端）

---

## 技術詳細

### モデル情報の流れ

1. `ToolOrchestrator.execute_tool()`: `ToolResult.metadata={"model": model_name}`を設定
2. `MixAIWorker._emit_tool_result()`: `result.metadata.get("model")`でモデル名取得
3. `tool_executed`シグナル: `{"model": model_name, ...}`を含むdictを送信
4. `HelixOrchestratorTab._on_tool_executed()`: QTreeWidgetItemにモデル名を追加

### コード変更詳細

#### helix_orchestrator_tab.py

```python
# ヘッダーラベル更新
self.tool_log_tree.setHeaderLabels(["ツール", "モデル", "ステータス", "実行時間", "出力"])

# _emit_tool_result()
model_name = result.metadata.get("model", "") if result.metadata else ""
self.tool_executed.emit({
    "model": model_name,  # 追加
    ...
})

# _on_tool_executed()
model_name = result.get("model", "")
item = QTreeWidgetItem([
    result.get("stage", ""),
    model_name,  # 新規列
    "✅" if result.get("success") else "❌",
    f"{result.get('execution_time_ms', 0):.0f}ms",
    output_display,
])
item.setForeground(1, QColor("#60a5fa"))  # モデル名を青色で表示
```

---

## 継承内容 (v4.2.0より)

### 常駐モデル構成

#### RTX PRO 6000 (96GB) — 推論メイン

| モデル | VRAM | 役割 |
|--------|------|------|
| Nemotron-3-Nano:30B | ~24GB | テキスト推論（常駐） |
| **空き** | **~72GB** | オンデマンドスロット |

#### RTX 5070 Ti (16GB) — Embedding + Image常駐

| モデル | VRAM | 役割 |
|--------|------|------|
| qwen3-embedding:4b | 2.5GB | RAG埋め込み（常駐） |
| ministral-3:8b | 6.0GB | 画像理解（常駐） |
| OS/ドライバ/Ollama | ~1.0GB | システム |
| KVキャッシュ余裕 | ~6.5GB | 推論時動的確保 |

---

## タブ構成 (v4.3.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.3** | チャット / 設定 | **Claude中心型マルチLLMオーケストレーション（ツール実行ログ強化）** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## v4.2.0からの継承課題

- [x] ツール実行ログでモデル名表示 → **v4.3で解決**
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
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.3.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.4以降)

1. **ストリーミング応答**: Ollamaからのリアルタイム応答表示
2. **チャット履歴エクスポート**: JSON/Markdown形式での会話保存
3. **RAG本格統合**: FAISS + SQLiteによるベクトルストア強化
4. **複数GPU負荷分散**: GPU割り当ての動的最適化

---

## 参考文献

- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Helix_v4.0.0_Evaluation.md (評価レポート)
- Anthropic Claude Documentation
- Ollama API Documentation
