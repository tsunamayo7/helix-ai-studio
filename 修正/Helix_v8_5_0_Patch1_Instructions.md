# Helix AI Studio v8.5.0 Patch 1 アップグレード指示書

**対象**: Claude Code CLI による一括実装
**バージョン**: v8.5.0 → v8.5.0 Patch 1
**コードネーム**: "Autonomous Knowledge Factory" (継続)
**推定作業時間**: 3-4時間
**前提条件**: v8.5.0 の情報収集タブ・RAGパイプライン基盤が実装済み

> この指示書に記載された全修正を順番に実施してください。
> 各セクション完了後、該当ファイルの変更箇所を報告してください。
> BIBLEの更新、不要コード削除、ビルドまで含めた一括作業です。

---

## 修正一覧（全8項目）

| # | カテゴリ | 内容 | 優先度 | 対象ファイル |
|---|---------|------|--------|-------------|
| 1 | バグ修正 | PLAN_SYSTEM_PROMPT未接続の修正確認 | P0 | rag_planner.py |
| 2 | UI改善 | RAG構築設定のUI調整（時間刻み・最大値・保存ボタン） | P1 | information_collection_tab.py, constants.py |
| 3 | 機能追加 | プラン概要の自然言語表示（コピー可能） | P1 | rag_planner.py, information_collection_tab.py |
| 4 | 機能追加 | 選択的更新（カテゴリ/ファイル単位で更新対象を絞る） | P1 | information_collection_tab.py, rag_executor.py, diff_detector.py |
| 5 | 機能追加 | Document Cleanupシステム（孤児検出・安全削除） | P1 | 新規: document_cleanup.py, information_collection_tab.py |
| 6 | エラー処理 | RAGパイプライン全体のエラーハンドリング強化 | P1 | rag_builder.py, rag_executor.py, rag_planner.py, rag_verifier.py |
| 7 | BIBLE更新 | BIBLE v8.5.0 作成 | P2 | BIBLE/ |
| 8 | リリース | 不要ファイル/コード削除、ビルド | P2 | 各所 |

---

## 修正1: PLAN_SYSTEM_PROMPT未接続の修正確認（P0）

### 背景
前回の修正で `_call_claude_cli()` にて `PLAN_SYSTEM_PROMPT` をプロンプト本文に結合する方式で修正済み。
フォールバック発動時のログ追加・UIへの `⚠️ デフォルトプラン（Claude接続失敗）` 表示も修正済み。

### 確認事項
以下が正しく実装されていることを確認してください:

1. `src/rag/rag_planner.py` 152-161行目付近:
   - `full_prompt = PLAN_SYSTEM_PROMPT + "\n\n" + prompt` が存在すること
   - `cmd` に `full_prompt` が渡されていること

2. `src/rag/rag_planner.py` 105-107行目付近:
   - `logger.warning("Using fallback default plan due to Claude CLI failure")` が存在すること

3. `src/tabs/information_collection_tab.py`:
   - `plan.get("fallback")` によるステータス分岐が存在すること
   - フォールバック時に `"⚠️ デフォルトプラン（Claude接続失敗）"` と表示されること

4. `src/rag/rag_planner.py` `_create_default_plan()`:
   - 返却dictに `"fallback": True` が含まれていること

**確認のみ。問題がなければ次へ進んでください。問題があれば修正してください。**

---

## 修正2: RAG構築設定のUI調整（P1）

### 2-1. 時間設定の刻みと最大値の変更

**ファイル**: `src/tabs/information_collection_tab.py`

情報収集タブ内の「想定実行時間」SpinBoxの設定を以下に変更:

```python
# 変更前（推定）:
self.time_spinbox.setRange(5, 120)
self.time_spinbox.setSingleStep(1)  # または5

# 変更後:
self.time_spinbox.setRange(10, 1440)  # 最小10分、最大1440分（24時間）
self.time_spinbox.setSingleStep(10)   # 10分刻み
self.time_spinbox.setValue(90)        # デフォルト90分
self.time_spinbox.setSuffix(" 分")    # サフィックス確認
```

**補足**: 最大1440分（24時間）にする理由は、将来的にBIBLE全バージョン + 大量技術ドキュメントの一括投入に対応するため。

### 2-2. チャンクサイズ・オーバーラップの刻み

```python
# チャンクサイズ: 64刻み
self.chunk_spinbox.setRange(128, 2048)
self.chunk_spinbox.setSingleStep(64)
self.chunk_spinbox.setValue(512)

# オーバーラップ: 8刻み
self.overlap_spinbox.setRange(0, 256)
self.overlap_spinbox.setSingleStep(8)
self.overlap_spinbox.setValue(64)
```

### 2-3. 設定を保存するボタンの追加

**ファイル**: `src/tabs/information_collection_tab.py`

RAG構築設定セクション内に「設定を保存」ボタンを追加する。

```python
# 「設定を保存」ボタン（SECONDARY_BTN スタイル）
self.save_settings_btn = QPushButton("設定を保存")
self.save_settings_btn.setStyleSheet(SECONDARY_BTN)
self.save_settings_btn.setToolTip("RAG構築設定をconfig/app_settings.jsonに保存します")
self.save_settings_btn.clicked.connect(self._save_rag_settings)
```

配置場所: チャンクサイズ・オーバーラップの行の右側、または下の行に配置。

保存先: `config/app_settings.json` に以下のキーで保存:

```json
{
  "rag": {
    "time_limit_minutes": 90,
    "chunk_size": 512,
    "overlap": 64
  }
}
```

アプリ起動時にこの設定を読み込んでSpinBoxに反映する `_load_rag_settings()` も実装すること。

### 2-4. constants.py の更新

**ファイル**: `src/utils/constants.py`

RAG関連の定数を追加（既存定数がある場合は更新）:

```python
# RAG設定デフォルト値
RAG_DEFAULT_TIME_LIMIT = 90       # 分
RAG_MIN_TIME_LIMIT = 10           # 分
RAG_MAX_TIME_LIMIT = 1440         # 分（24時間）
RAG_DEFAULT_CHUNK_SIZE = 512      # トークン
RAG_DEFAULT_OVERLAP = 64          # トークン
RAG_TIME_STEP = 10                # 分刻み
RAG_CHUNK_STEP = 64               # チャンクサイズ刻み
RAG_OVERLAP_STEP = 8              # オーバーラップ刻み
```

---

## 修正3: プラン概要の自然言語表示（P1）

### 3-1. PLAN_SYSTEM_PROMPTにsummaryフィールドを追加

**ファイル**: `src/rag/rag_planner.py`

`PLAN_SYSTEM_PROMPT`（18-66行目付近）のJSON出力仕様に `"summary"` フィールドを追加:

```
出力JSON仕様に以下を追加:
  "summary": "プラン全体の概要を日本語2-3文で記述。
    どのようなファイル群を処理し、各ファイルの特性（技術仕様/履歴/設計書等）に応じて
    どのような処理戦略を採用するかを簡潔に説明すること。"
```

### 3-2. フォールバックプランにもsummary追加

**ファイル**: `src/rag/rag_planner.py` `_create_default_plan()`

```python
return {
    ...,
    "summary": "デフォルトプランです。Claude接続に失敗したため、全ファイルを標準設定（reference/medium）で処理します。",
    "fallback": True
}
```

### 3-3. UI側のプラン表示を改善

**ファイル**: `src/tabs/information_collection_tab.py` `_display_plan()`

現在のプラン表示エリアを以下の構造に変更:

```
┌────────────────────────────────────────────────────────┐
│ 現在のプラン                                            │
│                                                        │
│ ステータス: プラン作成済み                                │
│                                                        │
│ 📋 プラン概要:                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │ 6つの技術ドキュメント（アーキテクチャ設計書、         │   │
│ │ メモリ仕様書、GPU構成表、バージョン履歴、            │   │
│ │ DBスキーマ定義、トラブルシューティングガイド）を       │   │
│ │ 分析しました。SQLiteスキーマ定義は構造化データ        │   │
│ │ としてエンティティ抽出を重点的に行い、...             │   │
│ │                                    [📋 コピー]     │   │
│ └──────────────────────────────────────────────────┘   │
│                                                        │
│ ファイル数: 6 | ステップ数: 5 | 推定時間: 95.6分        │
│ 01_Architecture... : technical / high / 13チャンク      │
│ 02_Memory...       : technical / high / 23チャンク      │
│ ...                                                    │
│                                                        │
│         [Claudeにプラン作成を依頼]                       │
└────────────────────────────────────────────────────────┘
```

具体的な実装:

```python
# サマリー表示エリア（QTextEdit、読み取り専用、コピー可能）
self.plan_summary_text = QTextEdit()
self.plan_summary_text.setReadOnly(True)
self.plan_summary_text.setMaximumHeight(120)
self.plan_summary_text.setStyleSheet(OUTPUT_AREA_STYLE)
self.plan_summary_text.setPlaceholderText("プランを作成すると、ここに概要が表示されます")

# コピーボタン
self.copy_plan_btn = QPushButton("📋 コピー")
self.copy_plan_btn.setStyleSheet(SECONDARY_BTN)
self.copy_plan_btn.setToolTip("プラン概要をクリップボードにコピー")
self.copy_plan_btn.setFixedWidth(100)
self.copy_plan_btn.clicked.connect(self._copy_plan_summary)
```

`_copy_plan_summary()` の実装:

```python
def _copy_plan_summary(self):
    """プラン概要をクリップボードにコピー（自然言語テキスト全体）"""
    from PyQt6.QtWidgets import QApplication
    clipboard = QApplication.clipboard()
    # サマリー + ファイル詳細を結合した全文をコピー
    full_text = self._build_full_plan_text()
    clipboard.setText(full_text)
    self.statusChanged.emit("プラン概要をコピーしました")
```

`_build_full_plan_text()` は以下のような自然言語テキストを生成:

```
【RAG構築プラン概要】
プラン作成日時: 2026-02-13 15:30
推定処理時間: 95.6分
対象ファイル: 6件

概要:
6つの技術ドキュメント（アーキテクチャ設計書、メモリ仕様書...）を分析しました。...

ファイル別計画:
  1. 01_Architecture_3Phase_Pipeline.txt
     分類: technical / 優先度: high / 推定チャンク: 13
  2. 02_Memory_Architecture_4Layer.txt
     分類: technical / 優先度: high / 推定チャンク: 23
  ...
```

---

## 修正4: 選択的更新（カテゴリ/ファイル単位で更新対象を絞る）（P1）

### 目的
データ量が増えた場合に、全ファイルを再処理せず、ユーザーが更新対象を選択できるようにする。

### 4-1. ファイル一覧にチェックボックスを追加

**ファイル**: `src/tabs/information_collection_tab.py`

ファイル一覧テーブル（QTableWidget等）の先頭カラムにチェックボックスを追加:

```
☑ | ファイル名                              | サイズ   | 更新日      | RAG状態
☑ | 01_Architecture_3Phase_Pipeline.txt     | 6.8 KB   | 2026-02-13 | 構築済み
☑ | 02_Memory_Architecture_4Layer.txt       | 11.8 KB  | 2026-02-13 | 構築済み
☐ | 03_Hardware_GPU_ModelMapping.txt         | 7.0 KB   | 2026-02-13 | 構築済み（変更なし）
☑ | 07_new_document.txt                     | 3.2 KB   | 2026-02-14 | ★新規
```

「RAG状態」カラムを追加し、以下のステータスを表示:
- `★新規` — data/information/ に存在するがdocumentsテーブルに未登録
- `変更あり` — ファイルのSHA256がdocumentsテーブルと不一致
- `構築済み` — 変更なし
- `削除済み` — documentsテーブルに存在するがファイルが削除されている

### 4-2. 全選択/全解除 + 差分のみ選択ボタン

```python
# ファイル一覧の上にボタン行を追加
self.select_all_btn = QPushButton("全選択")
self.select_all_btn.setStyleSheet(SECONDARY_BTN)
self.select_all_btn.clicked.connect(self._select_all_files)

self.select_none_btn = QPushButton("全解除")
self.select_none_btn.setStyleSheet(SECONDARY_BTN)
self.select_none_btn.clicked.connect(self._deselect_all_files)

self.select_changed_btn = QPushButton("差分のみ選択")
self.select_changed_btn.setStyleSheet(SECONDARY_BTN)
self.select_changed_btn.setToolTip("新規・変更ありのファイルのみ選択します")
self.select_changed_btn.clicked.connect(self._select_changed_only)
```

### 4-3. プラン作成・RAG構築を選択ファイルのみに限定

`_do_create_plan()` で、チェックされたファイルのみを `rag_planner.create_plan()` に渡す:

```python
def _do_create_plan(self):
    selected_files = self._get_selected_files()  # チェック済みファイルのパスリスト
    if not selected_files:
        self.statusChanged.emit("⚠️ ファイルが選択されていません")
        return
    plan = self.rag_planner.create_plan(
        files=selected_files,
        time_limit_minutes=self.time_spinbox.value()
    )
    ...
```

### 4-4. diff_detector.py の活用

**ファイル**: `src/rag/diff_detector.py`

`_refresh_file_list()` 実行時（「更新」ボタン押下時）に diff_detector を使ってRAG状態を判定し、テーブルの「RAG状態」カラムに反映する。

```python
def _refresh_file_list(self):
    """ファイル一覧を更新し、RAG状態を表示"""
    files = self._scan_information_folder()
    diff_result = self.diff_detector.detect_changes(files)
    
    for file_info in diff_result:
        # file_info = {"path": ..., "status": "new"|"modified"|"unchanged"|"deleted", ...}
        row = self._add_file_row(file_info)
        
        # 新規・変更ありのファイルはデフォルトでチェックON
        if file_info["status"] in ("new", "modified"):
            row.setCheckState(Qt.CheckState.Checked)
        else:
            row.setCheckState(Qt.CheckState.Unchecked)
```

---

## 修正5: Document Cleanupシステム（P1）

### 目的
ソースファイルが削除された孤児データや、ユーザーが不要と判断したデータを安全に削除する。

### 5-1. document_cleanup.py の新規作成

**ファイル**: `src/rag/document_cleanup.py`（新規）

```python
"""
Document Cleanup Manager
孤児検出・安全削除・ユーザー承認ベースのデータクリーンアップ

削除安全レベル:
  Level 1（完全孤児）: ソースファイルなし + semantic紐付けなし → 安全に削除可能
  Level 2（依存あり孤児）: ソースファイルなし + semantic紐付けあり → 要確認
  Level 3（ユーザー選択削除）: ユーザーが明示的に不要と判断 → 確認ダイアログ後削除

削除フロー:
  1. ローカルLLM（ministral-3:8b）が最新ファイル一覧との突合を実行
  2. 孤児候補リストを生成（safety_level付き）
  3. UIに孤児リストを表示、ユーザーが選択
  4. 選択されたデータを削除（documents + document_summaries + document_semantic_links）
"""
```

クラス設計:

```python
class DocumentCleanupManager:
    def __init__(self, memory_manager, information_folder: str):
        self.memory_manager = memory_manager
        self.information_folder = information_folder
        self.logger = logging.getLogger("DocumentCleanup")
    
    def scan_orphans(self) -> list[dict]:
        """
        孤児データを検出する。
        
        Returns:
            list of {
                "source_file": str,        # 元ファイル名
                "chunk_count": int,         # チャンク数
                "semantic_links": int,      # semantic_nodesとの紐付け数
                "safety_level": 1|2,        # 1=完全孤児, 2=依存あり
                "safety_label": str,        # "安全に削除可能" | "要確認（semantic紐付けあり）"
                "last_built": str,          # 最終RAG構築日時
                "total_size_kb": float      # 推定データサイズ
            }
        """
        # 1. documentsテーブルからユニークなsource_fileを取得
        # 2. data/information/ フォルダの実ファイルと突合
        # 3. ファイルが存在しないものを孤児候補としてマーク
        # 4. document_semantic_linksテーブルで紐付き確認
        # 5. safety_levelを判定
        pass
    
    def delete_orphans(self, source_files: list[str], delete_semantic_links: bool = False) -> dict:
        """
        指定された孤児データを削除する。
        
        Args:
            source_files: 削除対象のsource_file名リスト
            delete_semantic_links: Trueの場合、document_semantic_linksも削除
        
        Returns:
            {
                "deleted_chunks": int,
                "deleted_summaries": int,
                "deleted_links": int,
                "errors": list[str]
            }
        """
        pass
    
    def delete_selected_documents(self, source_files: list[str]) -> dict:
        """
        ユーザーが選択したドキュメント（ソースファイルが存在するものも含む）を削除する。
        ファイル自体は削除せず、documentsテーブルのデータのみ削除。
        
        Args:
            source_files: 削除対象のsource_file名リスト
        
        Returns:
            同上
        """
        pass
    
    def get_document_stats(self) -> dict:
        """
        Document Memory全体の統計情報を返す。
        
        Returns:
            {
                "total_documents": int,      # ユニークsource_file数
                "total_chunks": int,         # チャンク総数
                "total_summaries": int,      # 要約数
                "total_semantic_links": int, # semantic紐付け数
                "orphan_count": int,         # 孤児ドキュメント数
                "last_build_date": str,      # 最終RAG構築日時
                "db_size_mb": float          # helix_memory.dbのサイズ
            }
        """
        pass
```

### 5-2. 情報収集タブにデータ管理セクションを追加

**ファイル**: `src/tabs/information_collection_tab.py`

RAG構築設定セクションの下、または実行制御セクションの下に「データ管理」セクションを追加:

```
┌────────────────────────────────────────────────────────┐
│ データ管理                                              │
│                                                        │
│ 📊 RAG統計:                                            │
│   登録ドキュメント: 6件 | チャンク: 107個                │
│   Semantic紐付け: 23件 | 最終構築: 2026-02-13 15:30    │
│                                                        │
│ ⚠️ 孤児データ: 2件検出                                  │
│ ┌──────────────────────────────────────────────────┐   │
│ │ ☑ old_spec_v1.txt (12チャンク)                   │   │
│ │   → 完全孤児・安全に削除可能                      │   │
│ │ ☐ api_design.txt (8チャンク)                     │   │
│ │   → semantic_nodes 5件と紐付き・要確認            │   │
│ └──────────────────────────────────────────────────┘   │
│                                                        │
│ [孤児スキャン]  [選択したデータを削除]                    │
│                                                        │
│ ── 手動削除 ──                                          │
│ 構築済みドキュメントから不要なものを選択して削除:         │
│ ┌──────────────────────────────────────────────────┐   │
│ │ ☐ 01_Architecture_3Phase_Pipeline.txt (13チャンク)│   │
│ │ ☐ 02_Memory_Architecture_4Layer.txt (23チャンク) │   │
│ │ ☐ 03_Hardware_GPU_ModelMapping.txt (13チャンク)   │   │
│ │ ...                                              │   │
│ └──────────────────────────────────────────────────┘   │
│                                                        │
│ [選択したドキュメントを削除]                              │
└────────────────────────────────────────────────────────┘
```

### 5-3. 削除確認ダイアログ

削除ボタン押下時に必ず確認ダイアログを表示:

```python
from PyQt6.QtWidgets import QMessageBox

def _confirm_and_delete(self, source_files: list[str], is_orphan: bool = False):
    """削除前の確認ダイアログ"""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setWindowTitle("データ削除の確認")
    
    count = len(source_files)
    if is_orphan:
        msg.setText(f"孤児データ {count}件 を削除します。この操作は元に戻せません。")
    else:
        msg.setText(f"選択された {count}件 のドキュメントデータを削除します。\n"
                    f"ファイル自体は削除されません（data/information/ 内に残ります）。\n"
                    f"この操作は元に戻せません。")
    
    msg.setDetailedText("\n".join(source_files))
    msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
    
    if msg.exec() == QMessageBox.StandardButton.Ok:
        result = self.cleanup_manager.delete_orphans(source_files) if is_orphan \
                 else self.cleanup_manager.delete_selected_documents(source_files)
        self.statusChanged.emit(
            f"削除完了: {result['deleted_chunks']}チャンク, "
            f"{result['deleted_summaries']}要約, "
            f"{result['deleted_links']}リンク"
        )
        self._refresh_data_management_section()
```

### 5-4. 孤児スキャンの自動実行

アプリ起動時、および「更新」ボタン押下時に `scan_orphans()` を自動実行し、
孤児が検出された場合のみ「⚠️ 孤児データ: N件検出」を表示する。
孤児がない場合は「✅ データ健全」と表示。

---

## 修正6: エラーハンドリング強化（P1）

### 6-1. rag_planner.py

```python
# _call_claude_cli() のエラーハンドリング強化
def _call_claude_cli(self, prompt: str) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, 
            timeout=300, encoding='utf-8'
        )
        if result.returncode != 0:
            logger.error(f"Claude CLI returned non-zero exit code: {result.returncode}")
            logger.error(f"stderr: {result.stderr[:500]}")
            raise RuntimeError(f"Claude CLI error (code {result.returncode}): {result.stderr[:200]}")
        
        if not result.stdout.strip():
            logger.error("Claude CLI returned empty response")
            raise RuntimeError("Claude CLI returned empty response")
        
        return result.stdout.strip()
    
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out after 300 seconds")
        raise RuntimeError("Claude CLI timed out (5分超過)")
    except FileNotFoundError:
        logger.error("Claude CLI not found. Is 'claude' command installed and in PATH?")
        raise RuntimeError("Claude CLIが見つかりません。claude コマンドがPATHに設定されているか確認してください")
    except UnicodeDecodeError as e:
        logger.error(f"Claude CLI response encoding error: {e}")
        raise RuntimeError(f"Claude CLI応答のエンコーディングエラー: {e}")
```

### 6-2. rag_executor.py

各ステップ（chunking, embedding, summarization, KG生成）でtry-exceptを配置し、
個別ステップの失敗が全体を停止させないようにする:

```python
# 各ステップの構造
def _execute_step(self, step_name: str, func, *args):
    """個別ステップの実行とエラーハンドリング"""
    try:
        self.progress_callback(f"実行中: {step_name}")
        result = func(*args)
        logger.info(f"Step '{step_name}' completed successfully")
        return result
    except Exception as e:
        logger.error(f"Step '{step_name}' failed: {e}", exc_info=True)
        self._log_step_error(step_name, str(e))
        # チャンキングの失敗は致命的→全体停止
        if step_name == "chunking":
            raise
        # その他のステップは警告してスキップ
        self.progress_callback(f"⚠️ {step_name} でエラー発生、スキップします")
        return None
```

### 6-3. rag_builder.py（パイプライン全体）

```python
def build(self, plan: dict) -> dict:
    """RAG構築パイプラインの実行"""
    build_log = {
        "build_id": str(uuid.uuid4()),
        "start_time": datetime.now().isoformat(),
        "plan_id": plan.get("plan_id"),
        "steps_completed": [],
        "steps_failed": [],
        "status": "running"
    }
    
    try:
        # Step 1: Chunking
        # Step 2: Embedding
        # Step 3: Summarization
        # Step 4: KG Generation
        # Step 5: Verification
        ...
        build_log["status"] = "completed"
    except KeyboardInterrupt:
        build_log["status"] = "cancelled"
        logger.warning("RAG build cancelled by user")
    except Exception as e:
        build_log["status"] = "failed"
        build_log["error"] = str(e)
        logger.error(f"RAG build failed: {e}", exc_info=True)
    finally:
        build_log["end_time"] = datetime.now().isoformat()
        self._save_build_log(build_log)
    
    return build_log
```

### 6-4. UI側のエラー表示

**ファイル**: `src/tabs/information_collection_tab.py`

RAG構築失敗時に、進捗バーを赤色に変更し、エラーメッセージをステータスバーに表示:

```python
def _on_build_error(self, error_msg: str):
    """RAG構築エラー時のUI更新"""
    self.progress_bar.setStyleSheet("""
        QProgressBar::chunk { background-color: #ff6666; }
    """)
    self.statusChanged.emit(f"❌ RAG構築失敗: {error_msg}")
    self.build_start_btn.setEnabled(True)
    self.cancel_btn.setEnabled(False)
    self.retry_btn.setEnabled(True)  # 再実行ボタンを有効化
```

### 6-5. rag_verifier.py

品質検証失敗時の処理:

```python
def verify(self, build_result: dict) -> dict:
    """Claude Opus 4.6による品質検証"""
    try:
        verification = self._call_claude_for_verification(build_result)
        return verification
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        # 検証失敗は致命的ではない→警告付きで通過
        return {
            "status": "SKIP",
            "reason": f"品質検証をスキップしました（理由: {e}）",
            "checks": {}
        }
```

---

## 修正7: BIBLE更新（P2）

### BIBLE v8.5.0 の作成

**ファイル**: `BIBLE/BIBLE_Helix AI Studio_8.5.0.md`

BIBLE v8.4.2をベースに以下を更新:

1. **ヘッダー更新**:
   - バージョン: 8.5.0
   - コードネーム: "Autonomous Knowledge Factory"
   - 最終更新: 2026-02-13

2. **バージョン変遷サマリーテーブルに追加**:
   ```
   | v8.5.0 | Autonomous Knowledge Factory | Document Memory (Layer 5)・情報収集タブ・自律RAG構築パイプライン・Document Cleanup |
   ```

3. **設計哲学に追加**（12番目）:
   ```
   12. **自律知識構築** — ユーザー提供ドキュメントからAIが自律的にRAGを設計・構築・検証する。
       Claudeがプラン策定と品質検証を担い、ローカルLLMが大量の反復処理を実行する
       「知性のコスト最適化」を長時間自律タスクに拡張（v8.5.0新設）
   ```

4. **新規セクション追加**:
   - `### 4.6 Document Memory（Layer 5）` — documentsテーブル・document_summariesテーブル・document_semantic_linksテーブル・rag_build_logsテーブルの定義
   - `### 6.3.5 情報収集タブ` — UI要素一覧・操作フロー
   - `### 5.X RAG構築パイプライン` — 3ステップ（プラン策定→自律実行→品質検証）のフロー
   - `### 5.X Document Cleanup` — 孤児検出・安全削除フロー

5. **ディレクトリ構造の更新**:
   ```
   ├── data/
   │   ├── information/           # ★ v8.5.0: 情報収集フォルダ
   │   └── helix_memory.db        # ★ v8.5.0: Layer 5 Document Memory追加
   ├── src/
   │   ├── rag/                   # ★ v8.5.0: RAGパイプラインモジュール群
   │   │   ├── __init__.py
   │   │   ├── rag_builder.py
   │   │   ├── rag_planner.py
   │   │   ├── rag_executor.py
   │   │   ├── rag_verifier.py
   │   │   ├── document_chunker.py
   │   │   ├── document_cleanup.py  # ★ v8.5.0 Patch 1
   │   │   ├── diff_detector.py
   │   │   └── time_estimator.py
   │   ├── tabs/
   │   │   ├── information_collection_tab.py  # ★ v8.5.0: 情報収集タブ
   │   ├── widgets/
   │   │   ├── rag_progress_widget.py   # ★ v8.5.0
   │   │   └── rag_lock_overlay.py      # ★ v8.5.0
   ```

6. **config/app_settings.json の更新記述**:
   ```json
   {
     "version": "8.5.0",
     "rag": {
       "time_limit_minutes": 90,
       "chunk_size": 512,
       "overlap": 64
     }
   }
   ```

7. **ローカルLLM一覧の更新**:
   情報収集パイプラインでの各モデルの役割を追記:
   - ministral-3:8b: 制御AI + ★RAG品質判定 + ★ドキュメント要約・キーワード抽出
   - qwen3-embedding:4b: Embedding生成 + ★ドキュメントチャンクEmbedding生成
   - command-a:111b: research + ★Semantic Node/Edge生成

---

## 修正8: 不要ファイル/コード削除、ビルド（P2）

### 8-1. 不要ファイル・コードの確認と削除

以下を確認し、不要なものがあれば削除:

1. **未使用のimport文**: 各 `src/rag/*.py` ファイルで未使用のimportがないか確認
2. **デバッグ用print文**: `print()` が残っていないか確認（`logger` に置き換え）
3. **TODO/FIXMEコメント**: 対応済みのものは削除
4. **空の `__init__.py`**: 必要なexportが記述されているか確認
5. **旧バージョンの設定値**: `constants.py` に古いRAG関連定数が残っていないか

### 8-2. constants.py のバージョン更新

```python
APP_VERSION = "8.5.0"
```

### 8-3. app_settings.json の更新

```json
{
  "version": "8.5.0",
  ...
}
```

### 8-4. HelixAIStudio.spec の確認

PyInstallerビルド定義に以下が含まれていることを確認:
- `src/rag/` ディレクトリの全 `.py` ファイル
- `src/widgets/rag_progress_widget.py`
- `src/widgets/rag_lock_overlay.py`
- `src/tabs/information_collection_tab.py`
- `data/information/` フォルダ（空フォルダとして含める）

### 8-5. requirements.txt の確認

v8.5.0で追加された依存パッケージがあれば追記。

### 8-6. ビルド実行

全修正完了後:

```bash
# 1. 構文チェック
python -m py_compile src/rag/rag_planner.py
python -m py_compile src/rag/rag_executor.py
python -m py_compile src/rag/rag_builder.py
python -m py_compile src/rag/rag_verifier.py
python -m py_compile src/rag/document_cleanup.py
python -m py_compile src/tabs/information_collection_tab.py

# 2. アプリ起動テスト
python HelixAIStudio.py

# 3. PyInstallerビルド（起動テスト成功後）
pyinstaller HelixAIStudio.spec
```

---

## 実施順序

```
Phase 1: 確認・修正（30分）
  └─ 修正1: PLAN_SYSTEM_PROMPT確認
  └─ 修正2: UI調整（時間刻み・保存ボタン）

Phase 2: 機能追加（2時間）
  └─ 修正3: プラン概要表示
  └─ 修正4: 選択的更新
  └─ 修正5: Document Cleanup

Phase 3: 品質・リリース（1時間）
  └─ 修正6: エラーハンドリング
  └─ 修正7: BIBLE更新
  └─ 修正8: クリーンアップ・ビルド
```

---

## 完了条件

- [ ] プラン作成で `⚠️ デフォルトプラン` にならず、ファイル別にcategory/priorityが異なること
- [ ] 想定実行時間が10分刻みで10〜1440分の範囲で設定可能なこと
- [ ] 「設定を保存」ボタンで設定がapp_settings.jsonに永続化されること
- [ ] プラン概要が自然言語で表示され、コピーボタンでクリップボードにコピーできること
- [ ] ファイル一覧にチェックボックスとRAG状態カラムが表示されること
- [ ] 「差分のみ選択」ボタンで新規/変更ファイルのみが選択されること
- [ ] データ管理セクションで孤児スキャン・削除が動作すること
- [ ] 手動削除で選択したドキュメントのRAGデータが削除できること
- [ ] 削除前に確認ダイアログが表示されること
- [ ] RAG構築失敗時にエラーメッセージがUIに表示されること
- [ ] BIBLE v8.5.0が作成されていること
- [ ] `python HelixAIStudio.py` で起動できること
- [ ] PyInstallerビルドが成功すること

---

## 注意事項

- 既存のmixAI/soloAIタブの動作に影響を与えないこと
- Cyberpunk Minimalテーマ（styles.pyのスタイル定数）を使用すること
- 新規UIにはsetToolTipを付与すること（設計哲学7: UIの自己文書化）
- ログはloggerを使用し、print文は使わないこと
- 全ての新規ファイルに適切なdocstringを記述すること
