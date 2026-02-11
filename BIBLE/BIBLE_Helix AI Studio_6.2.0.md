# Helix AI Studio - Project BIBLE (包括的マスター設計書)

**バージョン**: 6.2.0 "Crystal Cognition"
**アプリケーションバージョン**: 6.2.0
**作成日**: 2026-02-05
**最終更新**: 2026-02-05
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v6.2.0 "Crystal Cognition" 更新履歴

### コンセプト: "Transparent Intelligence" (透明な知能)

v6.2.0はUI/UXの大幅刷新を実施。AIが「今何を考え、どのモデルが動き、どのVRAMを消費しているか」を完全に可視化:

### 主な変更点

1. **Neural Flow Visualizer (Feature A)**
   - 5Phaseパイプラインのノードベース動的フローチャート
   - `QGraphicsScene`ベースの可視化
   - 実行中のノードが「脈打つ（Pulsing）」アニメーション
   - 各ノードクリックで中間生成テキスト・推論ログをポップアップ表示

2. **VRAM Budget Simulator (Feature B)**
   - インタラクティブなGPUリソース管理盤
   - RTX PRO 6000 (96GB) + RTX 5070 Ti (16GB) のデュアルGPU可視化
   - モデル選択でVRAMブロックがスタック表示
   - オーバーフロー警告をリアルタイム表示
   - ドラッグ&ドロップでGPU間モデル移動

3. **Cyberpunk Minimal デザイン刷新**
   - ダークグレー背景 (#1a1a1a)
   - ネオンシアン (#00d4ff) / ネオングリーン (#00ff88) アクセント
   - グラデーション効果によるステータスバー
   - 半透明・グロー効果

---

## アーキテクチャ概要

### 5Phase実行パイプライン (v6.0.0～)

```
┌─────────────────────────────────────────────────────────────────┐
│                    5Phase Execution Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Claude初回実行（回答生成 + LLM指示文作成）             │
│      ↓                                                          │
│  Phase 2: ローカルLLMチーム並行実行（カテゴリ別モデル）         │
│      ↓                                                          │
│  Phase 3: 品質検証ループ（ローカルVerifier）                    │
│      ↓                                                          │
│  Phase 4: Claude最終統合（比較検証・統合回答）                  │
│      ↓                                                          │
│  Phase 5: ナレッジ管理（自動保存）                              │
└─────────────────────────────────────────────────────────────────┘
```

### v6.2.0 UI アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                         Main Window                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Tab Widget                             │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐              │    │
│  │  │ mixAI   │  │ soloAI  │  │  一般設定   │              │    │
│  │  └─────────┘  └─────────┘  └─────────────┘              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               mixAI Tab (v6.2.0)                         │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │        Neural Flow Compact Widget                │    │    │
│  │  │  [P1:Claude]→[P2:Local]→[P3:検証]→[P4:統合]→[P5:保存]│    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │              Chat Output Area                    │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Settings Tab (v6.2.0)                          │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │        VRAM Budget Simulator                     │    │    │
│  │  │  ┌────────────────┐  ┌────────────────┐         │    │    │
│  │  │  │ GPU 0: PRO 6000│  │ GPU 1: 5070 Ti │         │    │    │
│  │  │  │    96GB        │  │    16GB        │         │    │    │
│  │  │  └────────────────┘  └────────────────┘         │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 新規ファイル一覧 (v6.2.0)

| ファイル | 説明 |
|----------|------|
| `src/widgets/neural_visualizer.py` | Neural Flow Visualizer ウィジェット群 |
| `src/widgets/vram_simulator.py` | VRAM Budget Simulator ウィジェット群 |
| `BIBLE/BIBLE_Helix AI Studio_6.2.0.md` | 本ファイル |

---

## 変更ファイル一覧 (v6.2.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | APP_VERSION → 6.2.0, APP_DESCRIPTION更新 |
| `src/widgets/__init__.py` | Neural/VRAM ウィジェットのエクスポート追加 |
| `src/tabs/helix_orchestrator_tab.py` | Neural Flow / VRAM Simulator 統合 |
| `src/main_window.py` | Cyberpunk Minimalスタイルシート適用 |

---

## Neural Flow Visualizer 詳細

### クラス構成

```python
# src/widgets/neural_visualizer.py

class PhaseState(Enum):
    """Phase実行状態"""
    IDLE = "idle"           # 未実行（グレー）
    RUNNING = "running"     # 実行中（脈打つアニメーション）
    COMPLETED = "completed" # 完了（緑）
    FAILED = "failed"       # 失敗（赤）
    SKIPPED = "skipped"     # スキップ（黄色）

class PhaseNode(QGraphicsEllipseItem):
    """Phase表現ノード"""
    # 状態に応じた色変化
    # 実行中は脈打つアニメーション
    # クリックで詳細ポップアップ

class ConnectionLine(QGraphicsPathItem):
    """ノード間接続線（ベジェ曲線）"""

class PhaseDetailDialog(QDialog):
    """Phase詳細ポップアップダイアログ"""

class NeuralFlowVisualizer(QWidget):
    """メインビジュアライザーウィジェット"""

class NeuralFlowCompactWidget(QWidget):
    """コンパクト版（mixAIタブ用）"""
```

### 状態別カラー定義

| 状態 | カラー | Hex |
|------|--------|-----|
| IDLE | ダークグレー | #3d3d3d |
| RUNNING | ネオンシアン | #00d4ff |
| COMPLETED | ネオングリーン | #00ff88 |
| FAILED | ネオンレッド | #ff4757 |
| SKIPPED | ネオンオレンジ | #ffa502 |

---

## VRAM Budget Simulator 詳細

### クラス構成

```python
# src/widgets/vram_simulator.py

@dataclass
class ModelInfo:
    """モデル情報"""
    name: str
    vram_gb: float
    category: str  # search, report, architect, coding, verifier
    description: str
    color: str

@dataclass
class GPUInfo:
    """GPU情報"""
    index: int
    name: str
    total_vram_gb: float
    color: str

class VRAMBlock(QFrame):
    """VRAMブロック（ドラッグ可能）"""

class GPUBar(QFrame):
    """GPUバー（ドロップ受け入れ）"""

class ModelSelector(QFrame):
    """モデル選択パネル"""

class VRAMBudgetSimulator(QWidget):
    """メインシミュレーターウィジェット"""

class VRAMCompactWidget(QWidget):
    """コンパクト版（設定タブ用）"""
```

### 対応モデルカタログ

| モデル名 | VRAM | カテゴリ | 説明 |
|----------|------|----------|------|
| devstral-2:123b | 75GB | coding | SWE-bench 72.2% 最高 |
| qwen3-coder:30b | 19GB | coding | SWE-bench 69.6% 軽量 |
| qwen3-next:80b | 50GB | report | 高効率MoE 分析向き |
| nemotron-3-nano:30b | 24GB | search | IFBench 71.5% |
| nemotron-verifier:8b | 8GB | verifier | 品質検証用 |

---

## Cyberpunk Minimal テーマ

### カラーパレット

| 用途 | カラー | Hex |
|------|--------|-----|
| 背景（メイン） | ダークグレー | #1a1a1a |
| 背景（セカンダリ） | ダークグレー | #252525 |
| ボーダー | グレー | #2d2d2d |
| テキスト | ライトグレー | #e0e0e0 |
| アクセント1 | ネオンシアン | #00d4ff |
| アクセント2 | ネオングリーン | #00ff88 |
| エラー | ネオンレッド | #ff4757 |
| 警告 | ネオンオレンジ | #ffa502 |

### デザイン原則

1. **ダークモード優先**: 目に優しいダークグレー背景
2. **ネオンアクセント**: 重要な要素にはシアン/グリーンの輝き
3. **半透明効果**: グロー効果で奥行きを表現
4. **ミニマル**: 不要な装飾を排除、機能にフォーカス
5. **一貫性**: 全UIコンポーネントで統一されたスタイル

---

## ディレクトリ構造 (v6.2.0)

```
Helix AI Studio/
├── HelixAIStudio.py          # エントリーポイント
├── HelixAIStudio.exe         # ビルド済み実行ファイル
├── HelixAIStudio.spec        # PyInstaller設定
├── src/
│   ├── main_window.py        # メインウィンドウ (v6.2.0: Cyberpunk Minimal)
│   ├── backends/
│   │   ├── mix_orchestrator.py   # 5Phase実行エンジン
│   │   ├── parallel_pool.py      # ローカルLLM並列実行
│   │   ├── quality_verifier.py   # 品質検証
│   │   └── ...
│   ├── tabs/
│   │   ├── helix_orchestrator_tab.py  # mixAIタブ (v6.2.0: Neural Flow統合)
│   │   ├── claude_tab.py              # Claude専用タブ
│   │   └── settings_cortex_tab.py     # 設定タブ
│   ├── widgets/
│   │   ├── __init__.py           # v6.2.0: 新ウィジェットエクスポート
│   │   ├── chat_input.py         # 入力UI
│   │   ├── neural_visualizer.py  # v6.2.0: Neural Flow Visualizer
│   │   └── vram_simulator.py     # v6.2.0: VRAM Budget Simulator
│   └── utils/
│       └── constants.py          # バージョン定数 (6.2.0)
├── config/                       # 設定ファイル
├── data/                         # データ保存
├── logs/                         # ログファイル
├── dist/                         # ビルド出力
└── BIBLE/                        # BIBLEドキュメント
```

---

## GPU環境要件

### 推奨構成 (開発者環境)

- **GPU 0**: RTX PRO 6000 Blackwell (96GB VRAM)
- **GPU 1**: RTX 5070 Ti (16GB VRAM)
- **合計VRAM**: 112GB

### モデル配置戦略 (VRAM Simulator推奨)

```
RTX PRO 6000 (96GB):
  - devstral-2:123b (75GB, コーディング主力)
  - qwen3-next:80b (50GB, レポート/アーキテクト)
  ※ 同時に1つずつ実行

RTX 5070 Ti (16GB):
  - nemotron-3-nano:30b (24GB) ← オーバーフロー、PRO 6000に移動推奨
  - nemotron-verifier:8b (8GB, 検証)
  - qwen3-embedding:4b (2.5GB, Embedding)
```

---

## 技術スタック (v6.2.0)

| カテゴリ | 技術 | バージョン/詳細 |
|---------|------|----------------|
| 言語 | Python | 3.12+ |
| GUI | PyQt6 | 6.x |
| グラフィックス | QGraphicsScene | ノードベース可視化 |
| Claude連携 | Claude Code CLI | 非対話モード (-p) |
| ローカルLLM | Ollama API | HTTP REST |
| ビルド | PyInstaller | 6.17.0 |

---

## 次期バージョン予定 (v6.3.0以降)

### Feature C: Context Dock & Artifacts (次期実装)

- **Context Dock**: 右サイドバーに常駐、RAGヒットドキュメントをカード形式表示
- **Artifacts View**: Claude生成コードを別ペインでシンタックスハイライト表示

### その他

- モデル自動選択（VRAMベース最適化）
- ベンチマーク結果に基づくモデルレコメンド機能
- ダッシュボード機能

---

## v6.1.0 → v6.2.0 移行ガイド

### 新規機能

1. **Neural Flow Visualizer**: mixAIタブで5Phase実行状態を可視化
2. **VRAM Budget Simulator**: 設定タブでGPUリソースをシミュレーション
3. **Cyberpunk Minimalテーマ**: 全UIがダークグレー+ネオンアクセントに刷新

### 互換性

- v6.1.0の設定ファイルはそのまま使用可能
- API互換性維持

---

*このBIBLEは Claude Opus 4.5 により生成されました*
