# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.1.0
**アプリケーションバージョン**: 4.1.0 "Helix AI Studio - GPUモニター改善, オンデマンド4枠化, Ollama詳細ステータス"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.1.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.1.0 は Helix_v4.0.0_Evaluation.md の評価レポートに基づく改善を実装:

1. **GPUモニター nvidia-smi 修正** - PyInstaller環境対応
2. **Ollama接続テストにモデル別ステータス追加** - ロード中/待機中/未DL表示
3. **オンデマンドモデル4枠化** - v2提案書準拠の柔軟な構成
4. **ToolType拡張** - LARGE_INFERENCE, HIGH_PRECISION_CODE, NEXT_GEN_UNIVERSAL 追加
5. **GPU割り当てインジケータ追加** - 各モデルのVRAM/GPU情報表示

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | GPUモニターnvidia-smiエラー | `shutil.which()`でパス探索、Windowsデフォルトパスフォールバック、`CREATE_NO_WINDOW`フラグ、タイムアウト設定 | ✅ |
| 2 | Ollama接続テスト拡充 | `/api/ps`でロード中モデル取得、設定モデル全ての状態を個別表示（🟢ロード中/🟡待機中/🔴未DL） | ✅ |
| 3 | オンデマンドモデル4枠化 | code_specialist, large_inference, high_precision_code, next_gen_universal の4枠構成 | ✅ |
| 4 | オンデマンド有効/無効トグル | 各オンデマンドモデルにチェックボックス追加、OrchestratorConfigに_enabled フラグ追加 | ✅ |
| 5 | ToolType拡張 | LARGE_INFERENCE, HIGH_PRECISION_CODE, NEXT_GEN_UNIVERSAL を Enum に追加 | ✅ |
| 6 | GPU割り当てインジケータ | 常時ロードモデルに「→ PRO 6000 (24GB)」等のGPU割り当て表示追加 | ✅ |

---

## ファイル変更一覧 (v4.1.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/tool_orchestrator.py` | ToolType拡張（3種追加）、OrchestratorConfig拡張（4枠+有効/無効フラグ+GPU管理設定） |
| `src/tabs/helix_orchestrator_tab.py` | GPUモニター修正、Ollama詳細ステータス、オンデマンド4枠UI、GPU割り当てインジケータ |
| `src/utils/constants.py` | バージョン 4.0.0 → 4.1.0 |
| `BIBLE/BIBLE_Helix AI Studio_4.1.0.md` | 本ファイル追加 |

---

## ToolType (v4.1.0 拡張版)

| タイプ | 説明 | 推奨モデル | 状態 |
|--------|------|-----------|------|
| UNIVERSAL_AGENT | 万能エージェント | Nemotron-3-Nano 30B | v4.0継承 |
| CODE_SPECIALIST | コード特化 | Qwen3-Coder 30B | v4.0継承 |
| IMAGE_ANALYZER | 画像解析 | Gemma3 12B/27B | v4.0継承 |
| RAG_MANAGER | RAG管理 | Nemotron-3-Nano 30B | v4.0継承 |
| WEB_SEARCH | Web検索 | Qwen3-Coder 30B + Ollama web_search | v4.0継承 |
| LIGHT_TOOL | 軽量ツール | Gemma3 4B/12B | v4.0継承 |
| **LARGE_INFERENCE** | 大規模推論 | GPT-OSS 120B | **v4.1新規** |
| **HIGH_PRECISION_CODE** | 超高精度コード | Devstral 2 123B | **v4.1新規** |
| **NEXT_GEN_UNIVERSAL** | 次世代汎用 | Qwen3-Next 80B | **v4.1新規** |

---

## OrchestratorConfig (v4.1.0 拡張版)

```python
@dataclass
class OrchestratorConfig:
    # Ollama接続
    ollama_url: str = "http://localhost:11434"

    # 常時ロードモデル
    universal_agent_model: str = "nemotron-3-nano:30b"
    image_analyzer_model: str = "gemma3:12b"
    embedding_model: str = "bge-m3:latest"

    # オンデマンドモデル（4枠: v2提案書準拠）
    code_specialist_model: str = "qwen3-coder:30b"
    large_inference_model: str = "gpt-oss:120b"
    high_precision_code_model: str = "devstral-2:123b"    # v4.1追加
    next_gen_universal_model: str = "qwen3-next:80b"      # v4.1追加

    # オンデマンドモデル有効/無効
    code_specialist_enabled: bool = True
    large_inference_enabled: bool = True
    high_precision_code_enabled: bool = False   # デフォルト無効（75GB重い）
    next_gen_universal_enabled: bool = False    # デフォルト無効

    # Claude設定
    claude_model: str = "claude-opus-4-5"
    claude_auth_mode: str = "cli"
    thinking_mode: str = "Standard"

    # RAG設定
    rag_enabled: bool = True
    rag_auto_save: bool = True
    rag_save_threshold: str = "medium"

    # GPU管理（v4.1追加）
    gpu_monitor_interval: int = 5  # 秒
    keep_alive_resident: str = "-1"   # 常時ロード: 永続
    keep_alive_ondemand: str = "5m"   # オンデマンド: 5分
```

---

## GPU割り当てマップ (v4.1.0)

### 常時ロード構成

| モデル | VRAM | GPU割り当て | 役割 |
|--------|------|------------|------|
| Nemotron-3-Nano 30B | 24GB | PRO 6000 | 万能エージェント/RAG管理 |
| Gemma3 12B | 8.1GB | RTX 5070 Ti | 画像解析/軽量ツール |
| BGE-M3 Embedding | 2GB | PRO 6000 | RAGベクトル生成 |
| **合計** | **~34GB** | | |

### オンデマンド切替構成 (4枠)

| 枠 | モデル | VRAM | トリガー | デフォルト |
|----|--------|------|---------|-----------|
| 1 | Qwen3-Coder 30B | 19GB | コード検証・リファクタリング | 有効 |
| 2 | GPT-OSS 120B | 65GB | 複雑な推論タスク | 有効 |
| 3 | Devstral 2 123B | 75GB | SWE-Benchレベルのバグ修正 | 無効 |
| 4 | Qwen3-Next 80B | 50GB | 235Bクラス推論 | 無効 |

---

## GPUモニター改善 (v4.1.0)

### 修正内容

1. **パス探索の改善**: `shutil.which("nvidia-smi")` でPATH探索
2. **Windowsフォールバック**: デフォルトパス直接指定
   - `C:\Windows\System32\nvidia-smi.exe`
   - `C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe`
3. **コンソール非表示**: `subprocess.CREATE_NO_WINDOW` フラグ
4. **タイムアウト**: 10秒に設定（ハングアップ防止）
5. **プログレスバー表示**: VRAM使用率を視覚的に表示

### 表示例

```
GPU 0: NVIDIA RTX PRO 6000
  VRAM: [████████░░░░░░░░░░░░] 26,000/96,000 MB (27.1%)
  GPU使用率: 15%

合計VRAM: 26,000/96,000 MB
```

---

## Ollama接続テスト詳細ステータス (v4.1.0)

### 機能

- `/api/tags` でインストール済みモデル一覧取得
- `/api/ps` でロード中モデル一覧取得
- 設定モデルごとのステータス判定

### ステータス表示

| アイコン | ステータス | 説明 |
|---------|----------|------|
| 🟢 | ロード中 | VRAMにロードされて即時利用可能 |
| 🟡 | 待機中 | インストール済み、ロード待ち |
| 🔴 | 未DL | 未インストール、要ダウンロード |

### 表示例

```
✅ 接続成功 (0.12秒)

モデルステータス:
🟢 nemotron-3-nano:30b        ロード中  24,000MB   [常時]
🟢 gemma3:12b                 ロード中  8,100MB    [常時]
🟢 bge-m3:latest              ロード中  2,000MB    [常時]
🟡 qwen3-coder:30b            待機中    -          [OD]
🔴 gpt-oss:120b               未DL      -          [OD]
🔴 devstral-2:123b            未DL      -          [OD]
🔴 qwen3-next:80b             未DL      -          [OD]
```

---

## 設定パネルUI (v4.1.0)

### 常時ロードモデル

```
🔧 常時ロードモデル
 万能Agent:  [nemotron-3-nano:30b ▼]  → PRO 6000 (24GB)   🟢
 画像/軽量:  [gemma3:12b ▼]           → 5070 Ti (8.1GB)   🟢
 Embedding:  [bge-m3:latest ▼]        → PRO 6000 (2GB)    🟢
 合計: ~34GB (常時ロード)
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

## タブ構成 (v4.1.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.1** | チャット / 設定 | **Claude中心型マルチLLMオーケストレーション（4枠オンデマンド対応）** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## v4.0.0からの継承課題

- [x] GPUモニターnvidia-smiエラー → **v4.1で解決**
- [x] Ollama接続テスト拡充 → **v4.1で解決**
- [x] オンデマンドモデル4枠化 → **v4.1で解決**
- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | ~81 MB |
| exe (root) | `HelixAIStudio.exe` | ~81 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.1.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.2以降)

1. **RAG本格統合**: FAISS + SQLiteによるベクトルストア、自動会話保存
2. **オンデマンドモデル動的ロード/アンロード**: Ollama API経由の制御
3. **Web検索統合**: Ollama web_search/web_fetch機能の統合
4. **複数GPU負荷分散**: GPU割り当ての動的最適化

---

## 参考文献

- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Helix_v4.0.0_Evaluation.md (評価レポート)
- Anthropic Claude Documentation
- Ollama API Documentation
- NVIDIA Nemotron-3-Nano Model Card
- Google Gemma3 Technical Report
- Alibaba Qwen3-Coder Benchmark Results
