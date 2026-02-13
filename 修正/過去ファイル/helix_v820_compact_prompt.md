# v8.2.0 "RAG Shell" — Claude Code CLI 実行プロンプト

以下の作業を段階的に実施してください。各段階で完了確認をしてから次に進んでください。

## 前提

このプロジェクトは Helix AI Studio v8.1.0 "Adaptive Memory" です。
BIBLE: BIBLE/BIBLE_Helix AI Studio_8.1.0.md を最初に全文読んでください。

## 段階1: 起動診断と修正

1. `python HelixAIStudio.py` を実行してエラーを確認
2. エラーがあれば修正:
   - import失敗 → 循環importを遅延importに変更
   - DB初期化失敗 → data/ディレクトリ作成の保証
   - パッケージ不足 → pip install
3. HelixAIStudio.py冒頭に以下が無ければ追加:
```python
import sys, os
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)
for d in ['data', 'logs', 'config']:
    os.makedirs(d, exist_ok=True)
```
4. 起動成功を確認してから次へ

## 段階2: Phase 2 RAGコンテキスト注入

**最初に以下を全文読むこと（読み飛ばし禁止）**:
- src/memory/memory_manager.py
- src/backends/sequential_executor.py
- src/backends/mix_orchestrator.py

### 2-A: memory_manager.pyに追加

HelixMemoryManagerクラスに`build_context_for_phase2(user_message, category)`を追加:
- category="coding" → search_procedural(top_k=3) + search_semantic(top_k=3)
- category="research" → search_episodic(top_k=3) + search_semantic(top_k=5)
- category="reasoning" → search_semantic(top_k=7) + search_episodic(top_k=2)
- category="translation" → search_episodic(top_k=3)
- category="vision" → search_semantic(top_k=3)
- 戻り値: `<memory_context>...</memory_context>`形式。コンテキスト空なら空文字列
- 最大800文字に切り詰め（ローカルLLM向けコンパクト化）
- 例外時は空文字列を返す（フォールバック）

search_procedural/search_semantic/search_episodicメソッドが未実装なら追加:
- search_procedural: proceduresテーブルからベクトル類似度検索
- search_semantic: semantic_nodesテーブルからキーワード+時間有効性検索
- search_episodic: episodesテーブルからベクトル類似度検索

### 2-B: sequential_executor.pyを修正

Ollama API呼び出し前にRAGコンテキストを注入:
- execute_category()またはモデル実行メソッドにmemory_manager引数を追加
- memory_managerがあれば build_context_for_phase2() を呼び出し
- 結果をpromptの先頭に付加
- ログ: `Phase 2 RAG context injected for {category}: {len} chars`

### 2-C: mix_orchestrator.pyを修正

Phase 2呼び出し時にself.memory_managerを渡す:
- self.memory_managerが未初期化なら__init__で初期化
- sequential_executor.execute_category()呼び出しにmemory_manager=self.memory_managerを追加

### 2-D: helix_coreモジュール整理

```bash
grep -rn "from src.helix_core.memory_store" src/
grep -rn "from src.helix_core.vector_store" src/
grep -rn "from src.helix_core.light_rag" src/
grep -rn "from src.helix_core.rag_pipeline" src/
```
- 実行フローで使われていないモジュールには `# DEPRECATED: v8.2.0` コメント追加
- memory_manager.pyとの関係をコメントで明記

## 段階3: 定数更新とBIBLE生成

### 3-A: constants.py更新
```python
APP_VERSION = "8.2.0"
APP_CODENAME = "RAG Shell"
```

### 3-B: BIBLE v8.2.0生成
BIBLE v8.1.0をベースに更新:
- バージョン: 8.2.0 "RAG Shell"
- v8.2.0四本柱を追加
- 3Phase図にPhase 2 RAG注入を追記
- セクション3.4 SequentialExecutorにRAG記述追加
- セクション3.7 記憶注入フローにPhase 2追加
- 付録A v8.2.0変更履歴追加
- 500行以上必須
- app_settings.jsonのモデルID不整合を修正

### 3-C: 起動テスト
`python HelixAIStudio.py` で起動確認

### 3-D: exe対応（可能であれば）
- HelixAIStudio.specのhiddenimportsに `src.memory.memory_manager` 追加
- `pyinstaller HelixAIStudio.spec --noconfirm`
- 起動テスト
- 失敗時は start_helix.bat を作成:
```batch
@echo off
cd /d "%~dp0"
python HelixAIStudio.py
pause
```

## 完了報告

以下の形式で結果を報告してください:

```
=== v8.2.0 "RAG Shell" 実装完了報告 ===

■ Phase A (起動修正):
  - 検出エラー: (具体的に)
  - 修正内容: (具体的に)
  - python起動: OK/NG

■ Phase B (Phase 2 RAG注入):
  - build_context_for_phase2(): 追加行数
  - 検索メソッド: 新規追加/既存利用
  - sequential_executor.py: 修正行数
  - mix_orchestrator.py: 修正行数
  - helix_core整理: DEPRECATED指定ファイル数

■ Phase C (BIBLE・exe):
  - BIBLE v8.2.0: 行数
  - exe/bat: 方式

■ テスト結果:
  - python起動: OK/NG
  - Phase 2 RAG注入ログ確認: OK/NG/記憶なしのためスキップ
  - soloAI記憶注入: OK/NG
```

## 禁止事項

- 「既に実装済み」と言わず、grepで行番号を確認して報告する
- ファイル存在だけでOKとしない（実行フローに組み込まれているか確認）
- テストを省略しない
- BIBLEに設計案を書かない（実装済みのみ記載）
- 旧モジュールを無断削除しない（DEPRECATEDコメントで対応）
