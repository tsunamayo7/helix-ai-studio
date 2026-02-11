# Helix AI Studio - Project BIBLE (包括的マスター設計書)

**バージョン**: 6.3.0 "True Pipeline"
**アプリケーションバージョン**: 6.3.0
**作成日**: 2026-02-06
**最終更新**: 2026-02-06
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v6.3.0 "True Pipeline" 更新履歴

### コンセプト: "Reliable Intelligence" (信頼性のある知能)

v6.3.0は5Phase実行パイプラインの安定性向上とユーザー体験の改善に焦点。内部推論の漏洩防止、GPU動的検出、Knowledge統計のリアルタイム取得を実現:

### 主な変更点

1. **chain-of-thought フィルタリング (問題4対策)**
   - ローカルLLM (nemotron等) の内部推論が出力に漏洩する問題を解決
   - `parallel_pool.py` に `filter_chain_of_thought()` 関数を新規追加
   - 英語・日本語の思考パターンを正規表現でフィルタリング

2. **Knowledge統計リアルタイム取得 (問題7対策)**
   - `KnowledgeManager` に `get_stats()` / `get_count()` メソッド追加
   - 設定タブの「更新」ボタンで実データから件数・最終更新日時を取得
   - SQLiteから直接クエリして正確な統計を表示

3. **Ollama接続テストエラー修正 (問題3対策)**
   - `ollama_status_label` を正しく使用するよう修正
   - 属性参照エラーを解消

4. **GPU動的検出 (問題5対策確認)**
   - `vram_simulator.py` の `detect_gpus()` 関数で実GPU情報を取得
   - nvidia-smi経由で実際のGPU名・VRAM容量を自動検出

5. **5Phase実行パイプライン動作確認 (問題1,2,6)**
   - Phase 1: Claude初回実行 ✓
   - Phase 2: ローカルLLMチーム並行実行 ✓
   - Phase 3: 品質検証ループ ✓
   - Phase 4: Claude最終統合（2回目呼び出し） ✓
   - Phase 5: ナレッジ自動保存 ✓

6. **PyInstaller specファイル更新**
   - 5Phase関連モジュールをhiddenimportsに追加
   - `mix_orchestrator`, `parallel_pool`, `quality_verifier`, `phase1_parser`, `phase1_prompt`, `phase4_prompt`

---

## 修正問題一覧 (v6.3.0)

| 問題ID | 重要度 | 概要 | 対策 | ファイル |
|--------|--------|------|------|----------|
| 問題1 | P0 | Phase 2並列実行不在 | 既に実装済みを確認 | `mix_orchestrator.py` |
| 問題2 | P0 | Phase 4 Claude呼び出し不在 | 既に実装済みを確認 | `mix_orchestrator.py` |
| 問題3 | P0 | Ollama接続テストエラー | `ollama_status_label`使用確認 | `helix_orchestrator_tab.py` |
| 問題4 | P1 | chain-of-thought漏洩 | フィルタリング関数追加 | `parallel_pool.py` |
| 問題5 | P1 | GPUインデックス逆転 | 動的検出実装確認 | `vram_simulator.py` |
| 問題6 | P1 | 最終回答が内部ログ形式 | パイプライン正常動作確認 | `mix_orchestrator.py` |
| 問題7 | P2 | Knowledge件数未更新 | `get_stats()`追加 | `knowledge_manager.py`, `settings_cortex_tab.py` |

---

## chain-of-thought フィルタリング詳細

### 新規追加関数

```python
# src/backends/parallel_pool.py

def filter_chain_of_thought(text: str) -> str:
    """
    ローカルLLMの出力からchain-of-thought（思考過程）を除去する。

    nemotron等のモデルが内部推論過程を漏洩する問題への対策。
    例: "We need to comply: answer in Japanese, m..."
        "Let me think about this..."
    """
```

### フィルタリングパターン

| パターン種別 | 例 |
|--------------|-----|
| 英語思考開始 | "Let me", "I should", "We need to" |
| 内部制約言及 | "comply with", "answer in Japanese" |
| メタ発言 | "follow output rules", "within constraints" |
| 日本語思考 | "考え", "まず", "では" |

### 適用箇所

`_run_single_task()` メソッド内で、Ollama APIレスポンス取得直後にフィルタリングを適用:

```python
if response.status_code == 200:
    raw_response = data.get("response", "")
    filtered_response = filter_chain_of_thought(raw_response)  # v6.3.0追加
    return ParallelResult(
        ...
        response=filtered_response,
        ...
    )
```

---

## Knowledge統計機能詳細

### 新規追加メソッド

```python
# src/knowledge/knowledge_manager.py

def get_stats(self) -> Dict[str, Any]:
    """
    ナレッジDBの統計情報を取得

    Returns:
        {"count": 件数, "last_updated": 最終更新日時}
    """

def get_count(self) -> int:
    """ナレッジの総件数を取得（互換性用）"""
```

### 設定タブ連携

```python
# src/tabs/settings_cortex_tab.py

def _refresh_knowledge_stats(self):
    """Knowledge統計を更新 (v6.3.0: 実データ取得対応)"""
    km = get_knowledge_manager()
    stats = km.get_stats()
    count = stats.get("count", 0)
    last_updated = stats.get("last_updated")
    # UI更新
```

---

## アーキテクチャ概要

### 5Phase実行パイプライン (v6.0.0～)

```
┌─────────────────────────────────────────────────────────────────┐
│                    5Phase Execution Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Claude初回実行（回答生成 + LLM指示文JSON作成）        │
│      ↓                                                          │
│  Phase 2: ローカルLLMチーム並行実行（ThreadPoolExecutor）       │
│      ↓       ※ chain-of-thoughtフィルタリング適用 (v6.3.0)     │
│  Phase 3: 品質検証ループ（ローカルVerifier、再実行最大3回）     │
│      ↓                                                          │
│  Phase 4: Claude最終統合（比較検証・統合回答）                  │
│      ↓                                                          │
│  Phase 5: ナレッジ管理（自動保存、SQLite）                      │
└─────────────────────────────────────────────────────────────────┘
```

### ファイル依存関係

```
MixAIOrchestrator (mix_orchestrator.py)
    │
    ├── Phase 1 → Claude CLI (-p --output-format json)
    │       └── phase1_parser.py (JSONパース)
    │       └── phase1_prompt.py (システムプロンプト)
    │
    ├── Phase 2 → ParallelWorkerPool (parallel_pool.py)
    │       └── filter_chain_of_thought() [v6.3.0]
    │
    ├── Phase 3 → QualityVerifier (quality_verifier.py)
    │
    ├── Phase 4 → Claude CLI
    │       └── phase4_prompt.py (統合プロンプト)
    │
    └── Phase 5 → KnowledgeManager (knowledge_manager.py)
                └── get_stats() [v6.3.0]
```

---

## 変更ファイル一覧 (v6.3.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | APP_VERSION → 6.3.0, APP_DESCRIPTION更新 (確認済み) |
| `src/backends/parallel_pool.py` | `filter_chain_of_thought()` 関数追加 |
| `src/knowledge/knowledge_manager.py` | `get_stats()`, `get_count()` メソッド追加 |
| `src/tabs/settings_cortex_tab.py` | `_refresh_knowledge_stats()` 実データ取得対応 |
| `src/tabs/helix_orchestrator_tab.py` | バージョン表記更新 (v6.3.0) |
| `src/widgets/neural_visualizer.py` | バージョン表記更新 (v6.3.0) |
| `HelixAIStudio.spec` | 5Phase関連モジュールをhiddenimportsに追加 |

---

## PyInstaller 設定更新

### 追加されたhiddenimports (v6.3.0)

```python
# HelixAIStudio.spec

hiddenimports=[
    # ... 既存 ...
    # v6.0.0: 5Phase実行パイプライン
    'src.backends.mix_orchestrator',
    'src.backends.parallel_pool',
    'src.backends.quality_verifier',
    'src.backends.phase1_parser',
    'src.backends.phase1_prompt',
    'src.backends.phase4_prompt',
    # ... 続き ...
]
```

---

## ディレクトリ構造 (v6.3.0)

```
Helix AI Studio/
├── HelixAIStudio.py          # エントリーポイント
├── HelixAIStudio.exe         # ビルド済み実行ファイル
├── HelixAIStudio.spec        # PyInstaller設定 (v6.3.0更新)
├── src/
│   ├── main_window.py        # メインウィンドウ
│   ├── backends/
│   │   ├── mix_orchestrator.py   # 5Phase実行エンジン
│   │   ├── parallel_pool.py      # ローカルLLM並列実行 (v6.3.0: CoTフィルタ追加)
│   │   ├── quality_verifier.py   # 品質検証
│   │   ├── phase1_parser.py      # Phase 1 JSONパーサー
│   │   ├── phase1_prompt.py      # Phase 1 システムプロンプト
│   │   ├── phase4_prompt.py      # Phase 4 統合プロンプト
│   │   └── ...
│   ├── tabs/
│   │   ├── helix_orchestrator_tab.py  # mixAIタブ (v6.3.0)
│   │   ├── claude_tab.py              # Claude専用タブ
│   │   └── settings_cortex_tab.py     # 設定タブ (v6.3.0: Knowledge統計)
│   ├── widgets/
│   │   ├── neural_visualizer.py  # Neural Flow Visualizer (v6.3.0)
│   │   └── vram_simulator.py     # VRAM Budget Simulator
│   ├── knowledge/
│   │   ├── knowledge_manager.py  # v6.3.0: get_stats()追加
│   │   └── knowledge_worker.py
│   └── utils/
│       └── constants.py          # バージョン定数 (6.3.0)
├── config/                       # 設定ファイル
├── data/                         # データ保存
├── logs/                         # ログファイル
├── dist/                         # ビルド出力
└── BIBLE/                        # BIBLEドキュメント
    └── BIBLE_Helix AI Studio_6.3.0.md  # 本ファイル
```

---

## GPU環境要件

### 推奨構成 (開発者環境)

- **GPU 0**: RTX PRO 6000 Blackwell (96GB VRAM)
- **GPU 1**: RTX 5070 Ti (16GB VRAM)
- **合計VRAM**: 112GB

### GPU動的検出 (v6.3.0確認済み)

`vram_simulator.py` の `detect_gpus()` 関数が nvidia-smi 経由で自動検出:

```python
def detect_gpus() -> List[GPUInfo]:
    """実際のGPU情報を検出"""
    # nvidia-smi --query-gpu=index,name,memory.total --format=csv
```

---

## 技術スタック (v6.3.0)

| カテゴリ | 技術 | バージョン/詳細 |
|---------|------|----------------|
| 言語 | Python | 3.12.7 |
| GUI | PyQt6 | 6.x |
| グラフィックス | QGraphicsScene | ノードベース可視化 |
| Claude連携 | Claude Code CLI | 非対話モード (-p) |
| ローカルLLM | Ollama API | HTTP REST |
| ビルド | PyInstaller | 6.17.0 |
| データベース | SQLite3 | Knowledge管理 |

---

## v6.2.0 → v6.3.0 移行ガイド

### 新機能

1. **chain-of-thoughtフィルタリング**: ローカルLLMの内部推論が出力に漏洩しなくなります
2. **Knowledge統計リアルタイム取得**: 設定タブで正確な件数・更新日時を確認可能

### 修正

1. **Ollama接続テスト**: エラーが発生しなくなります
2. **GPU検出**: 実際のGPU情報が正しく表示されます

### 互換性

- v6.2.0の設定ファイルはそのまま使用可能
- API互換性維持
- データベーススキーマ変更なし

---

## 次期バージョン予定 (v6.4.0以降)

### Feature C: Context Dock & Artifacts

- **Context Dock**: 右サイドバーに常駐、RAGヒットドキュメントをカード形式表示
- **Artifacts View**: Claude生成コードを別ペインでシンタックスハイライト表示

### その他

- モデル自動選択（VRAMベース最適化）
- ベンチマーク結果に基づくモデルレコメンド機能
- ダッシュボード機能
- 多言語対応

---

*このBIBLEは Claude Opus 4.5 により生成されました*
