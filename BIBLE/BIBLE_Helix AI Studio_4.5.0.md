# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 4.5.0
**アプリケーションバージョン**: 4.5.0 "Helix AI Studio - 日本語回答徹底・GPU動的記録グラフ表示"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v4.5.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v4.5.0 は日本語回答の徹底とGPU動的記録・グラフ表示機能を追加:

1. **日本語回答の徹底**: すべてのLLMプロンプトに「必ず日本語で回答」の強制指示を追加
2. **GPU動的記録機能**: LLM実行時にGPU使用量を自動記録
3. **GPUグラフ表示**: 時系列でGPU使用量をリアルタイムグラフ表示
4. **LLMイベントマーカー**: 各ステージ実行後5秒でGPU使用量を記録し、グラフに表示

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | 日本語回答徹底 | helix_orchestrator_tab.pyの全ステージプロンプトに「必ず日本語で回答」を追加 | ✅ |
| 2 | システムプロンプト強化 | tool_orchestrator.pyの_build_system_prompt()に日本語強制指示を追加 | ✅ |
| 3 | GPU動的記録機能 | GPUUsageGraphウィジェットを新規実装、add_data_point()で時系列記録 | ✅ |
| 4 | GPUグラフ表示 | PyQt6 QPainterでリアルタイムグラフ描画（最大60秒分表示） | ✅ |
| 5 | LLMイベントマーカー | _schedule_gpu_record_after_llm()で各ステージ実行後5秒に自動記録 | ✅ |
| 6 | GPU記録自動開始 | _on_execute()でLLM実行時にGPU記録を自動開始 | ✅ |

---

## ファイル変更一覧 (v4.5.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/helix_orchestrator_tab.py` | GPUUsageGraphクラス追加、全ステージプロンプトに日本語指示追加、GPU記録メソッド追加 |
| `src/backends/tool_orchestrator.py` | _build_system_prompt()に日本語強制指示を追加、ドキュメントヘッダー更新 |
| `src/utils/constants.py` | バージョン 4.4.0 → 4.5.0、APP_DESCRIPTION更新 |
| `src/main_window.py` | mixAIタブのツールチップをv4.5仕様に更新 |
| `BIBLE/BIBLE_Helix AI Studio_4.5.0.md` | 本ファイル追加 |

---

## 日本語回答徹底機能 (v4.5.0)

### 実装箇所

#### 1. helix_orchestrator_tab.py - 各ステージプロンプト

```python
# Stage 1: タスク分析
analysis_prompt = f"""【重要】必ず日本語で回答してください。英語での回答は禁止です。

以下のタスクを分析し、実行計画を最大6行で簡潔にまとめてください。
...
"""

# Stage 2-5も同様に日本語指示を追加
```

#### 2. tool_orchestrator.py - システムプロンプト

```python
def _build_system_prompt(self, tool_type: ToolType) -> str:
    # v4.5: すべてのプロンプトに日本語回答の強制指示を追加
    japanese_instruction = "【最重要】必ず日本語で回答してください。英語での回答は禁止です。\n\n"

    base_prompt = prompts.get(tool_type, "...")
    return japanese_instruction + base_prompt
```

---

## GPU動的記録・グラフ表示機能 (v4.5.0)

### GPUUsageGraphクラス

```python
class GPUUsageGraph(QWidget):
    """v4.5: GPU使用量の動的グラフ表示ウィジェット"""

    def __init__(self, parent=None):
        # データ保存用（最大60サンプル = 60秒分）
        self.max_samples = 60
        self.gpu_data: Dict[int, List[Dict[str, Any]]] = {}
        self.events: List[Dict[str, Any]] = []  # LLM起動イベント

    def add_data_point(self, gpu_index: int, vram_used_mb: int, vram_total_mb: int, event: str = ""):
        """データポイントを追加"""
        ...

    def add_event(self, event_name: str):
        """LLM起動イベントを記録"""
        ...

    def paintEvent(self, event):
        """グラフを描画（PyQt6 QPainter使用）"""
        ...
```

### GPU記録メソッド

```python
def _toggle_gpu_recording(self):
    """GPU記録の開始/停止"""

def _start_gpu_recording(self):
    """GPU記録を開始（1秒間隔）"""

def _stop_gpu_recording(self):
    """GPU記録を停止"""

def _record_gpu_usage(self):
    """GPU使用量を記録（nvidia-smi使用）"""

def _record_gpu_with_event(self, event_name: str):
    """イベント付きでGPU使用量を記録"""

def _schedule_gpu_record_after_llm(self, stage_name: str):
    """LLM起動後5秒後にGPU使用量を記録するスケジュール"""
```

### 自動記録フロー

```
1. ユーザーが「実行」ボタンをクリック
   ↓
2. _on_execute()でGPU記録を自動開始
   ↓
3. 各ステージ実行時に_on_tool_executed()が呼ばれる
   ↓
4. _schedule_gpu_record_after_llm()で即座にイベント記録
   ↓
5. 5秒後にQTimer.singleShot()で再度記録
   ↓
6. グラフにイベントマーカー（縦線）として表示
```

---

## 5ステージパイプライン詳細 (継続: v4.4.0より)

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

## タブ構成 (v4.5.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | **mixAI v4.5** | チャット / 設定 | **日本語回答徹底・GPU動的グラフ表示** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## GPUモニターUI (v4.5.0)

### 設定タブ内構成

```
📊 GPUモニター (v4.5: 動的記録・グラフ表示)
├── [GPUUsageGraph] - リアルタイムグラフ（60秒分、GPU別色分け）
│   ├── GPU 0: 緑
│   ├── GPU 1: 青
│   └── イベントマーカー: オレンジ縦線
├── [GPU情報テキスト] - 現在のVRAM使用量
├── [ボタン行]
│   ├── 🔄 GPU情報更新
│   ├── ▶ 記録開始 / ⏹ 記録停止
│   └── 🗑️ クリア
└── 💡 説明: "LLM実行時に自動で5秒後にGPU使用量を記録します"
```

---

## v4.4.0からの継承課題

- [x] 日本語回答徹底 → **v4.5で解決**
- [x] GPU動的記録・グラフ表示 → **v4.5で解決**
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
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_4.5.0.md` | - |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v4.6以降)

1. **ストリーミング応答**: Ollamaからのリアルタイム応答表示
2. **チャット履歴エクスポート**: JSON/Markdown形式での会話保存
3. **RAG本格統合**: FAISS + SQLiteによるベクトルストア強化
4. **複数GPU負荷分散**: GPU割り当ての動的最適化
5. **パイプラインカスタマイズ**: ユーザー定義ステージの追加

---

## 参考文献

- BIBLE_Helix AI Studio_4.4.0.md (前バージョン)
- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Anthropic Claude Documentation
- Ollama API Documentation
