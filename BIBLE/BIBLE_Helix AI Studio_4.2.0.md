# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.2.0
**アプリケーションバージョン**: 4.2.0 "Helix AI Studio - 常駐モデル最適化 (qwen3-embedding + ministral-3)"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.2.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.2.0 は RTX5070Ti_Resident_Model_Verification.md に基づく常駐モデルの最適化を実装:

1. **Embeddingモデル変更**: bge-m3 → qwen3-embedding:4b
2. **Imageモデル変更**: gemma3:12b → ministral-3:8b
3. **VRAM効率改善**: 9.3GB → 8.5GB (RTX 5070 Ti)
4. **性能向上**: 全指標で現行を上回る

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | Embeddingモデル更新 | bge-m3 → qwen3-embedding:4b (2.5GB, 32K ctx, 2560dim) | ✅ |
| 2 | Imageモデル更新 | gemma3:12b → ministral-3:8b (6.0GB, 256K ctx, MM MTBench +20.6%) | ✅ |
| 3 | Embedding詳細設定追加 | OrchestratorConfigに embedding_dimension, embedding_context_length, embedding_instruction 追加 | ✅ |
| 4 | UI更新 | 常時ロードモデルのコンボボックス・VRAM表示を新モデルに対応 | ✅ |
| 5 | バージョン更新 | 4.1.0 → 4.2.0 | ✅ |

---

## ファイル変更一覧 (v4.2.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/tool_orchestrator.py` | Embeddingモデル変更、Imageモデル変更、embedding詳細設定追加、RECOMMENDED_MODELS更新 |
| `src/tabs/helix_orchestrator_tab.py` | モデルコンボボックス更新、VRAM表示更新、バージョン表記更新 |
| `src/utils/constants.py` | バージョン 4.1.0 → 4.2.0 |
| `BIBLE/BIBLE_Helix AI Studio_4.2.0.md` | 本ファイル追加 |

---

## 常駐モデル構成 (v4.2.0)

### RTX PRO 6000 (96GB) — 推論メイン

| モデル | VRAM | 役割 |
|--------|------|------|
| Nemotron-3-Nano:30B | ~24GB | テキスト推論（常駐） |
| **空き** | **~72GB** | オンデマンドスロット |

### RTX 5070 Ti (16GB) — Embedding + Image常駐

| モデル | VRAM | 役割 | 変更 |
|--------|------|------|------|
| **qwen3-embedding:4b** | 2.5GB | RAG埋め込み（常駐） | **NEW** (bge-m3から変更) |
| **ministral-3:8b** | 6.0GB | 画像理解（常駐） | **NEW** (gemma3:12bから変更) |
| OS/ドライバ/Ollama | ~1.0GB | システム | |
| **KVキャッシュ余裕** | **~6.5GB** | 推論時動的確保 | **+0.8GB改善** |

### VRAM配分比較

```
RTX 5070 Ti 16GB VRAM配分
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v4.1.0 (bge-m3 + gemma3:12b)
[##EMB 1.2##][########IMAGE 8.1########][OS1.0][===余裕 5.7===]

v4.2.0 (qwen3-emb:4b + ministral-3:8b)  ★推奨
[##EMB 2.5###][######IMAGE 6.0######][OS1.0][====余裕 6.5====]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0GB        4GB        8GB       12GB       16GB
```

---

## Embeddingモデル比較 (v4.2.0)

| 項目 | bge-m3 (v4.1.0) | qwen3-embedding:4b (v4.2.0) | 改善 |
|------|----------------|----------------------------|------|
| パラメータ | 567M | 4B | 7倍 |
| Ollamaサイズ | 1.2GB | 2.5GB | +1.3GB |
| コンテキスト | 8K | **32K** | **4倍** |
| 最大次元 | 1024 | **2560** | **MRL対応** |
| Instruction対応 | ❌ | **✅** | **1-5%精度向上** |
| MTEB multilingual | ~63.0 | **大幅に上位** | |
| 日本語品質 | 良好 | **優秀 (Qwen3基盤)** | |

### OrchestratorConfig Embedding設定

```python
embedding_model: str = "qwen3-embedding:4b"
embedding_dimension: int = 2560          # MRL対応、最大2560次元
embedding_context_length: int = 32768    # 32Kコンテキスト
embedding_instruction: str = "Instruct: 与えられたテキストから意味的に類似するコンテンツを検索する"
```

**移行時の注意点**:
- FAISS次元が1024 → 2560に変更されるため、**全インデックスの再構築が必須**
- 既存のベクトルとの互換性はなし（ベクトル空間が完全に異なる）

---

## Imageモデル比較 (v4.2.0)

| 項目 | gemma3:12b (v4.1.0) | ministral-3:8b (v4.2.0) | 改善 |
|------|---------------------|-------------------------|------|
| パラメータ | 12B | 8B | -4B (効率化) |
| Ollamaサイズ | 8.1GB | **6.0GB** | **-2.1GB** |
| MM MTBench | 67.00 | **80.80** | **+20.6%** |
| Arena Hard | 43.6 | **50.9** | **+16.7%** |
| コンテキスト | 128K | **256K** | **2倍** |
| Function Calling | ❌ | **✅ ネイティブ** | |
| JSON出力 | 手動プロンプト | **ネイティブ対応** | |
| Vision Encoder | SigLIP | ViT 410M (Pixtral) | |

**注意**: ministral-3は **Ollama 0.13.1以上が必要**（現在プレリリース）

---

## 性能向上サマリー (v4.1.0 → v4.2.0)

| 指標 | v4.1.0 | v4.2.0 | 改善 |
|------|--------|--------|------|
| Embedding精度 (MTEB) | ~63.0 | **大幅向上** | ✅✅✅ |
| Embeddingコンテキスト | 8K | **32K** | ✅✅✅ |
| Image理解 (MM MTBench) | 67.00 | **80.80** | ✅✅✅ (+20.6%) |
| Image推論 (Arena Hard) | 43.6 | **50.9** | ✅✅ (+16.7%) |
| Function Calling | ❌ | **✅ ネイティブ** | ✅✅✅✅ |
| コンテキスト (Image) | 128K | **256K** | ✅✅ |
| VRAM使用量 | 9.3GB | **8.5GB** | ✅ (-0.8GB) |
| KVキャッシュ余裕 | 5.7GB | **6.5GB** | ✅ (+0.8GB) |

**全項目で現行を上回りつつ、VRAM消費は減少**という理想的な移行。

---

## ToolType (v4.2.0)

| タイプ | 説明 | 推奨モデル | 状態 |
|--------|------|-----------|------|
| UNIVERSAL_AGENT | 万能エージェント | Nemotron-3-Nano 30B | 継承 |
| CODE_SPECIALIST | コード特化 | Qwen3-Coder 30B | 継承 |
| IMAGE_ANALYZER | 画像解析 | **Ministral-3 8B** | **v4.2変更** |
| RAG_MANAGER | RAG管理 | Nemotron-3-Nano 30B | 継承 |
| WEB_SEARCH | Web検索 | Qwen3-Coder 30B + Ollama web_search | 継承 |
| LIGHT_TOOL | 軽量ツール | **Ministral-3 8B** | **v4.2変更** |
| LARGE_INFERENCE | 大規模推論 | GPT-OSS 120B | 継承 |
| HIGH_PRECISION_CODE | 超高精度コード | Devstral 2 123B | 継承 |
| NEXT_GEN_UNIVERSAL | 次世代汎用 | Qwen3-Next 80B | 継承 |

---

## 設定パネルUI (v4.2.0)

### 常時ロードモデル

```
🔧 常時ロードモデル
 万能Agent:  [nemotron-3-nano:30b ▼]      → PRO 6000 (24GB)   🟢
 画像/軽量:  [ministral-3:8b ▼]            → 5070 Ti (6.0GB)   🟢  ★NEW
 Embedding:  [qwen3-embedding:4b ▼]        → 5070 Ti (2.5GB)   🟢  ★NEW
 合計: ~32.5GB (常時ロード) / PRO 6000: 24GB + 5070 Ti: 8.5GB
```

### オンデマンドモデル (4枠)

```
⚡ オンデマンドモデル
 ☑ コード特化:  [qwen3-coder:30b ▼]    (19GB)
 ☑ 大規模推論:  [gpt-oss:120b ▼]       (65GB)
 ☐ 超高精度CD:  [devstral-2:123b ▼]    (75GB)
 ☐ 次世代汎用:  [qwen3-next:80b ▼]     (50GB)
```

---

## タブ構成 (v4.2.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.2** | チャット / 設定 | **Claude中心型マルチLLMオーケストレーション（常駐モデル最適化）** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## 移行時の注意事項

### 1. Ollama 0.13.1要件（ministral-3）

ministral-3は **Ollama 0.13.1以上が必要** で、現在プレリリース段階。

**対策**:
- 安定版リリースを待ってから移行（推奨）
- またはプレリリース版を別環境でテスト後に本番適用
- フォールバック: gemma3:12bを選択可能

### 2. FAISS全インデックス再構築

Embedding次元変更（1024 → 2560）により、既存の全ベクトルインデックスが無効になる。

**対策**:
- 移行スクリプトの事前準備
- 一括再埋め込み処理の実行（全ドキュメント再処理）
- 移行期間中の旧インデックスバックアップ

---

## v4.1.0からの継承課題

- [x] 常駐モデル最適化 → **v4.2で解決**
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
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.2.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.3以降)

1. **RAG本格統合**: FAISS + SQLiteによるベクトルストア、qwen3-embedding:4b活用
2. **ministral-3 Function Calling活用**: mixAIオーケストレーションとの連携強化
3. **Web検索統合**: Ollama web_search/web_fetch機能の統合
4. **複数GPU負荷分散**: GPU割り当ての動的最適化

---

## 参考文献

- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Helix_v4.0.0_Evaluation.md (評価レポート)
- Anthropic Claude Documentation
- Ollama API Documentation
- Qwen3-Embedding Technical Report
- Mistral AI Ministral 3 Paper
