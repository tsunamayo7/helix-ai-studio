# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 6.1.0
**アプリケーションバージョン**: 6.1.0 "Helix AI Studio - 5Phase最適化・オンデマンドモデル廃止・ベンチマーク最適モデル設定"
**作成日**: 2026-02-05
**最終更新**: 2026-02-05
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v6.1.0 更新履歴 (2026-02-05)

### 主な変更点

**概要**:
v6.1.0はv6.0.0の5Phase統合アーキテクチャを踏まえた不要コードの削除とローカルLLMモデル設定の最適化を実施:

1. **オンデマンドモデルシステム完全削除**: v6.0.0の5Phase統合で不要となったオンデマンドモデル関連のUI・コード・ファイルを削除
2. **カテゴリ別ローカルLLMモデル最適化**: ベンチマークPDF資料に基づき、RTX 5070 Ti(16GB) + RTX PRO 6000(96GB)環境に最適なモデルを選定・設定
3. **不要ファイル削除**: claude_executor.py、ondemand_manager.py、ondemand_settings.py を削除
4. **PyInstaller設定更新**: specファイルから削除されたモジュール参照を除去

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

### カテゴリ別ローカルLLMモデル (v6.1.0 最適化)

| カテゴリ | 推奨モデル | VRAM | ベンチマーク | GPU配置 |
|---------|------------|------|--------------|---------|
| 検索担当 | nemotron-3-nano:30b | 24GB | IFBench 71.5%, 1M ctx | RTX 5070 Ti + PRO 6000分散 |
| レポート担当 | qwen3-next:80b | 50GB | 高効率MoE, 分析向き | PRO 6000 |
| アーキテクト担当 | qwen3-next:80b | 50GB | 設計・推論力 | PRO 6000 |
| コーディング担当 | devstral-2:123b | 75GB | SWE-bench 72.2% 最高 | PRO 6000 |

**軽量代替オプション**:
- コーディング軽量版: qwen3-coder:30b (19GB, SWE-bench 69.6%)

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | オンデマンドモデルUI削除 | helix_orchestrator_tab.pyから関連UIセクション削除 | 設定画面にオンデマンドモデル設定が表示されない |
| 2 | オンデマンドモデルファイル削除 | ondemand_manager.py, ondemand_settings.py, claude_executor.py削除 | 該当ファイルが存在しない |
| 3 | カテゴリ別モデル最適化 | ベンチマークPDFに基づきモデル選定・VRAM表示追加 | 各カテゴリに最適モデルが設定可能 |
| 4 | PyInstaller設定更新 | specファイルからhiddenimports削除 | ビルドが警告なく成功 |
| 5 | バージョン更新 | constants.py APP_VERSION → 6.1.0 | アプリタイトルに6.1.0表示 |

---

## 削除されたファイル一覧 (v6.1.0)

| ファイル | 理由 |
|----------|------|
| `src/backends/claude_executor.py` | 未使用（ClaudeCLIBackendに統合済み） |
| `src/backends/ondemand_manager.py` | 5Phase統合で不要（カテゴリ別モデル方式に移行） |
| `src/widgets/ondemand_settings.py` | オンデマンドUI削除に伴い不要 |

---

## ファイル変更一覧 (v6.1.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | バージョン 6.0.0 → 6.1.0 |
| `src/widgets/__init__.py` | OnDemandModelSettingsのimport削除、バージョンコメント更新 |
| `src/tabs/helix_orchestrator_tab.py` | オンデマンドモデルUI削除、カテゴリ別モデル選択を最適化 |
| `HelixAIStudio.spec` | 削除モジュールのhiddenimports除去 |
| `BIBLE/BIBLE_Helix AI Studio_6.1.0.md` | 本ファイル追加 |

---

## コード変更詳細 (v6.1.0)

### 1. カテゴリ別モデル選択の最適化

**helix_orchestrator_tab.py** (抜粋):
```python
# 検索担当 (IFBench 71.5%, ツール使用に強い)
self.search_model_combo.addItems([
    "nemotron-3-nano:30b",  # 24GB, IFBench 71.5%, 1Mコンテキスト (推奨)
    "qwen3-next:80b",       # 50GB, 高効率MoE
    "qwen3:30b",            # 汎用
])

# レポート担当 (分析・レポート生成向き)
self.report_model_combo.addItems([
    "qwen3-next:80b",       # 50GB, 高効率MoE, 分析向き (推奨)
    "nemotron-3-nano:30b",  # 24GB, 汎用性高い
    "qwen3:30b",
])

# アーキテクト担当 (設計・推論向き)
self.architect_model_combo.addItems([
    "qwen3-next:80b",       # 50GB, 設計力 (推奨)
    "nemotron-3-nano:30b",  # 24GB, 汎用
    "qwen3:30b",
])

# コーディング担当 (SWE-bench最高スコア)
self.coding_model_combo.addItems([
    "devstral-2:123b",      # 75GB, SWE-bench 72.2% 最高 (推奨, PRO 6000向け)
    "qwen3-coder:30b",      # 19GB, SWE-bench 69.6%, 軽量代替
    "codellama:34b",
])
```

### 2. widgets/__init__.py の更新

```python
"""
Helix AI Studio - Widgets (v6.1.0)
UI強化ウィジェット群
"""

from .chat_input import (
    EnhancedChatInput,
    AttachmentWidget,
    AttachmentBar,
    ChatInputArea,
)

__all__ = [
    "EnhancedChatInput",
    "AttachmentWidget",
    "AttachmentBar",
    "ChatInputArea",
]
# v6.1.0: OnDemandModelSettings 削除（5Phase統合で不要）
```

---

## 技術スタック (v6.1.0)

| カテゴリ | 技術 | バージョン/詳細 |
|---------|------|----------------|
| 言語 | Python | 3.12+ |
| GUI | PyQt6 | 6.x |
| Claude連携 | Claude Code CLI | 非対話モード (-p) |
| ローカルLLM | Ollama API | HTTP REST |
| ビルド | PyInstaller | 6.17.0 |

---

## GPU環境要件

### 推奨構成 (開発者環境)
- **GPU 1**: RTX 5070 Ti (16GB VRAM)
- **GPU 2**: RTX PRO 6000 Blackwell (96GB VRAM)
- **合計VRAM**: 112GB

### モデル配置戦略
```
RTX 5070 Ti (16GB):
  - 軽量モデル (qwen3-coder:30b など)
  - 補助的な並列処理

RTX PRO 6000 (96GB):
  - devstral-2:123b (コーディング主力)
  - qwen3-next:80b (レポート/アーキテクト)
  - nemotron-3-nano:30b (検索)
```

---

## ディレクトリ構造 (v6.1.0)

```
Helix AI Studio/
├── HelixAIStudio.py          # エントリーポイント
├── HelixAIStudio.exe         # ビルド済み実行ファイル
├── HelixAIStudio.spec        # PyInstaller設定
├── build.bat                 # ビルドスクリプト
├── src/
│   ├── main_window.py        # メインウィンドウ
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── mix_orchestrator.py   # 5Phase実行エンジン
│   │   ├── parallel_pool.py      # ローカルLLM並列実行
│   │   ├── quality_verifier.py   # 品質検証
│   │   ├── phase1_prompt.py      # Phase 1システムプロンプト
│   │   ├── phase1_parser.py      # Phase 1出力パーサー
│   │   ├── phase4_prompt.py      # Phase 4システムプロンプト
│   │   ├── tool_orchestrator.py  # ツールオーケストレーター
│   │   ├── claude_cli_backend.py # Claude CLI連携
│   │   └── ... (その他バックエンド)
│   ├── tabs/
│   │   ├── helix_orchestrator_tab.py  # mixAIタブ（メイン）
│   │   ├── claude_tab.py              # Claude専用タブ
│   │   └── settings_cortex_tab.py     # 設定タブ
│   ├── widgets/
│   │   ├── __init__.py
│   │   └── chat_input.py         # 入力UI
│   ├── knowledge/
│   │   ├── knowledge_manager.py
│   │   └── knowledge_worker.py
│   └── utils/
│       └── constants.py          # バージョン定数
├── config/                       # 設定ファイル
├── data/                         # データ保存
├── logs/                         # ログファイル
├── dist/                         # ビルド出力
└── BIBLE/                        # BIBLEドキュメント
```

---

## v5.2.0 → v6.1.0 移行ガイド

### 削除された機能
1. **オンデマンドモデル設定**: mixAI設定タブから削除
2. **claude_executor.py**: ClaudeCLIBackendに統合済み

### 新しい設定方法
- **カテゴリ別モデル**: mixAI設定タブ内の「検索/レポート/アーキテクト/コーディング」ドロップダウンで選択

---

## 次期バージョン予定 (v6.2.0以降)

- Phase間の中間結果可視化UI
- モデル自動選択（VRAMベース）
- ベンチマーク結果に基づくモデルレコメンド機能

---

*このBIBLEは Claude Opus 4.5 により生成されました*
