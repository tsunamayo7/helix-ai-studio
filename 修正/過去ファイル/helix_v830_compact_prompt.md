# v8.3.0 "Living Memory" — Claude Code CLI 実行プロンプト

以下の作業を段階的に実施してください。各段階で完了確認をしてから次に進んでください。

## 前提

このプロジェクトは Helix AI Studio v8.2.0 "RAG Shell" です。
BIBLE: BIBLE/BIBLE_Helix AI Studio_8.2.0.md を最初に全文読んでください。
詳細版は"C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio\修正\helix_v830_living_memory_upgrade.md"を読んでください。

## 段階1: RAPTOR要約トリガー実装

**最初に以下を全文読むこと（読み飛ばし禁止）**:
- src/memory/memory_manager.py（全メソッド構造を把握）
- src/backends/mix_orchestrator.py（Phase 3完了後の後処理フローを把握）
- src/tabs/claude_tab.py（新規セッションハンドラを把握）
- src/main_window.py または HelixAIStudio.py（起動時フックの挿入先を把握）

### 1-A: memory_manager.pyに3メソッド追加

HelixMemoryManagerクラスに以下を追加:

**generate_session_summary(session_id)**（async）:
- episodesテーブルから当該session_idの全レコード取得
- 2往復未満ならスキップ
- 既にsession要約が存在するならスキップ
- 会話テキストを構築（最大2000文字）
- ministral-3:8bで200文字以内に要約
- episode_summariesに summary_type='session' で保存
- 例外時はwarningログのみ（メイン処理に影響しない）

**generate_weekly_summary()**（async）:
- 直近7日間のsession summaryを取得
- 条件: 10件以上蓄積 or 前回weeklyから7日以上経過
- 3件未満ならスキップ
- ministral-3:8bで300文字以内に集約
- episode_summariesに summary_type='weekly' で保存

**generate_version_summary(version)**（async）:
- 既にversion要約が存在するならスキップ
- weekly summariesを取得（なければsession summariesから代替）
- ministral-3:8bで500文字以内に統括
- episode_summariesに summary_type='version', session_id=f'version_{version}' で保存

**_call_resident_llm(prompt, max_tokens)の確認**:
- Memory Risk Gateが既にOllama呼び出しメソッドを持っているならそれを共用
- なければ新規追加: ministral-3:8bへのaiohttp POSTで `http://localhost:11434/api/generate`

### 1-B: トリガー挿入（3箇所）

**mixAI Phase 3完了後**:
- mix_orchestrator.pyのPhase 3完了+Memory Risk Gate後処理の後に追加
- `asyncio.ensure_future(self.memory_manager.generate_session_summary(session_id))`

**soloAI 新規セッション押下時**:
- claude_tab.pyの「新規セッション」ボタンハンドラ内、セッションIDリセット前に追加
- `asyncio.ensure_future(self.memory_manager.generate_session_summary(self.current_session_id))`

**起動時（main_window.pyまたはHelixAIStudio.py）**:
- QTimer.singleShot(30000) で weekly summary チェック
- QTimer.singleShot(45000) で version summary チェック（data/.last_version と APP_VERSION比較）
- version check は旧バージョンの統括要約を生成し、data/.last_version を更新

## 段階2: Temporal KG実動化 + GraphRAGコミュニティ要約

**最初にこれを読むこと**: src/helix_core/graph_rag.py

### 2-A: Temporal KG検証

以下をgrepで確認し、結果を報告:
```bash
grep -n "valid_from" src/memory/memory_manager.py
grep -n "valid_to" src/memory/memory_manager.py
grep -n "DEPRECATE" src/memory/memory_manager.py
grep -n "valid_to IS NULL" src/memory/memory_manager.py
```

**修正が必要な場合**:
- semantic_nodes INSERT時にvalid_from=datetime('now')を設定
- UPDATE/DEPRECATE時にvalid_to=datetime('now')を設定
- search_semantic_by_text()にvalid_toフィルタ追加
- get_semantic_history(subject)メソッド追加（期限切れ含む時系列表示）

### 2-B: GraphRAGコミュニティ要約

graph_rag.pyに以下を追加:
- `detect_communities()`: networkx Louvainアルゴリズムで知識グラフのクラスタ検出
- `get_community_nodes(community)`: クラスタのノード詳細取得
- `generate_community_summaries(memory_manager)`: 各クラスタをministral-3:8bで100文字以内に要約

memory_manager.pyに以下を追加:
- `rebuild_knowledge_graph()`: SQLiteからグラフ再構築→コミュニティ検出→要約生成
- コミュニティ要約はepisode_summariesにsummary_type='community'で保存
- ノードが10個以上ある場合のみ実行

## 段階3: DEPRECATEDモジュール完全削除 + exe安定ビルド

### 3-A: 削除前最終確認
```bash
grep -rn "from src.helix_core.memory_store" src/ --include="*.py"
grep -rn "from src.helix_core.vector_store" src/ --include="*.py"
grep -rn "from src.helix_core.light_rag" src/ --include="*.py"
grep -rn "from src.helix_core.rag_pipeline" src/ --include="*.py"
grep -rn "from src.helix_core.hybrid_search_engine" src/ --include="*.py"
grep -rn "import memory_store" src/ --include="*.py"
grep -rn "import vector_store" src/ --include="*.py"
grep -rn "import light_rag" src/ --include="*.py"
grep -rn "import rag_pipeline" src/ --include="*.py"
grep -rn "import hybrid_search" src/ --include="*.py"
```

**全て0件であることを確認後に削除**:
- src/helix_core/memory_store.py
- src/helix_core/vector_store.py
- src/helix_core/light_rag.py
- src/helix_core/rag_pipeline.py
- src/helix_core/hybrid_search_engine.py

**graph_rag.pyは絶対に削除しない**（コミュニティ検出で使用中）

### 3-B: HelixAIStudio.spec修正

hiddenimportsから削除:
- `'src.helix_core.light_rag'`
- `'src.helix_core.rag_pipeline'`

残す:
- `'src.helix_core.graph_rag'`

### 3-C: helix_core/__init__.py修正

削除モジュールのimport/exportがあれば除去

### 3-D: exe ビルド
```bash
pyinstaller HelixAIStudio.spec --noconfirm
dist\HelixAIStudio\HelixAIStudio.exe
```
失敗時は start_helix.bat を作成:
```batch
@echo off
cd /d "%~dp0"
python HelixAIStudio.py
if errorlevel 1 pause
```

## 段階4: 定数更新・BIBLE生成

### 4-A: constants.py更新
```python
APP_VERSION = "8.3.0"
APP_CODENAME = "Living Memory"
```

### 4-B: BIBLE v8.3.0生成

BIBLE v8.2.0をベースに更新:
- バージョン: 8.3.0 "Living Memory"
- 設計哲学第9項追加: 記憶の自律成長
- v8.3.0三本柱:
  1. RAPTOR要約トリガー（session/weekly/version + communityの4種要約）
  2. Temporal KG実動化 + GraphRAGコミュニティ要約
  3. DEPRECATEDモジュール完全削除 + exe安定化
- セクション3.7にRAPTORトリガーの具体的発火条件を追記
- セクション3.9を「モジュール削除完了」に更新
- 新セクション: GraphRAGコミュニティ要約
- セクション12: hiddenimportsを更新
- 付録C: v8.3.0変更履歴
- 500行以上必須

### 4-C: 起動テスト
- `python HelixAIStudio.py` で正常起動確認
- ImportErrorなし
- 全タブ表示

## 完了報告

以下の形式で結果を報告してください:

```
=== v8.3.0 "Living Memory" 実装完了報告 ===

■ Phase A (RAPTOR要約):
  - generate_session_summary(): 行数
  - generate_weekly_summary(): 行数
  - generate_version_summary(): 行数
  - _call_resident_llm(): 新規/既存共用
  - トリガー挿入: mixAI(行番号) / soloAI(行番号) / 起動時(行番号)

■ Phase B (Temporal KG + GraphRAG):
  - valid_from設定: 確認済み行番号 / 修正
  - valid_to設定: 確認済み行番号 / 修正
  - valid_toフィルタ: 確認済み行番号 / 修正
  - detect_communities(): 行数
  - generate_community_summaries(): 行数
  - rebuild_knowledge_graph(): 行数

■ Phase C (モジュール削除 + exe):
  - 削除ファイル: 5件
  - grep残存参照: 0件確認
  - spec修正: 2行削除
  - exe/bat: 方式

■ Phase D (BIBLE):
  - BIBLE v8.3.0: 行数
  - constants.py: 8.3.0 / Living Memory

■ テスト結果:
  - python起動: OK/NG
  - graph_rag.py import: OK/NG
  - 全タブ表示: OK/NG
```

## 禁止事項

- 「既に実装済み」と言わず、grepで行番号を確認して報告する
- graph_rag.pyを削除しない（DEPRECATEDではない、コミュニティ検出で使用中）
- RAPTOR要約でUIをブロックしない（全てasyncio.ensure_future）
- ministral-3:8b呼び出しを同期にしない（async/await使用）
- 削除対象5ファイル以外のhelix_coreファイルを削除しない
- BIBLEに設計案を書かない（実装済みのみ記載）
- テストを省略しない
