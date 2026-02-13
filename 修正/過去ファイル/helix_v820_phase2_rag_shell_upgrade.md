# Helix AI Studio v8.2.0 "RAG Shell" — Claude Code CLI 実装指示書

**対象バージョン**: v8.1.0 → v8.2.0
**コードネーム**: "RAG Shell"（RAG外殻）
**作成日**: 2026-02-10
**作成者**: Claude Opus 4.6

---

## 0. 本指示書の目的

v8.1.0で実装した4層メモリ（Thread/Episodic/Semantic/Procedural）を、
**Phase 2のローカルLLM群にも注入**する。これにより、RAG/メモリが
ローカルLLMの「外殻（shell）」として機能し、ローカルLLM単独では
知り得ない文脈情報を付与してPhase 2出力品質を大幅に向上させる。

加えて、**exe実行不能の問題を診断・修正**し、
`python HelixAIStudio.py` による直接実行の安定性も担保する。

---

## 1. 作業前の必須手順（読み飛ばし禁止）

以下のファイルを**全文**読んでから実装に着手すること。
「既に知っている」と思っても必ず再読すること。

```
必読ファイル（この順番で）:
1. src/memory/memory_manager.py        — 4層メモリ統合マネージャー全体像
2. src/backends/mix_orchestrator.py     — 3Phase実行フロー、Phase 1/3の記憶注入箇所
3. src/backends/sequential_executor.py  — Phase 2順次実行エンジン、Ollama API呼び出し
4. src/tabs/helix_orchestrator_tab.py   — mixAI設定タブ（RAG設定の現在地を確認）
5. src/tabs/settings_cortex_tab.py      — 一般設定タブ（記憶・知識管理セクション）
6. src/helix_core/rag_pipeline.py       — 旧RAGパイプライン（現在の検索実装確認）
7. src/helix_core/hybrid_search_engine.py — ハイブリッド検索（BM25+ベクトル+グラフ）
8. src/utils/constants.py               — バージョン定数、モデル定義
9. BIBLE/BIBLE_Helix AI Studio_8.1.0.md — 現行BIBLE（特にセクション3.4, 3.7, 3.8）
10. HelixAIStudio.py                     — エントリポイント（起動時エラー確認用）
```

**読了確認**: 各ファイルの行数とクラス名をログに出力してから次に進むこと。

---

## 2. Phase A: exe実行不能の診断と修正

### 2.1 診断手順

**最優先で以下を実行し、エラーを特定する。**

```bash
# Step 1: Python直接実行でエラー確認
cd "C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio"
python HelixAIStudio.py 2>&1 | tee logs/startup_debug.log

# Step 2: エラーが出た場合、import順序を確認
python -c "
import sys
sys.path.insert(0, '.')
try:
    from src.memory.memory_manager import HelixMemoryManager, MemoryRiskGate
    print('OK: memory_manager import')
except Exception as e:
    print(f'FAIL: memory_manager - {e}')

try:
    from src.backends.mix_orchestrator import MixAIOrchestrator
    print('OK: mix_orchestrator import')
except Exception as e:
    print(f'FAIL: mix_orchestrator - {e}')

try:
    from src.tabs.settings_cortex_tab import SettingsCortexTab
    print('OK: settings_cortex_tab import')
except Exception as e:
    print(f'FAIL: settings_cortex_tab - {e}')
"

# Step 3: 依存パッケージ確認
pip list | findstr -i "networkx numpy pyqt6 aiohttp"
```

### 2.2 よくある原因と修正パターン

**パターン1: networkx未インストール**
```bash
pip install networkx --break-system-packages
```

**パターン2: memory_manager.pyの循環import**
```python
# memory_manager.py内でhelix_coreモジュールをトップレベルimportしている場合
# → 遅延importに変更
# 修正前:
from src.helix_core.graph_rag import GraphRAG
# 修正後:
def _get_graph_rag(self):
    from src.helix_core.graph_rag import GraphRAG
    return GraphRAG()
```

**パターン3: SQLiteデータベース初期化エラー**
```python
# data/helix_memory.db が存在しない場合にCREATE TABLEが失敗
# → __init__内でos.makedirs('data', exist_ok=True)を追加
```

**パターン4: PyInstallerバイナリが古いだけ**
```bash
# v8.1.0のコード変更後にexeを再ビルドしていない場合
# → 当面はpython直接実行で運用し、Phase C完了後にexeビルド
python HelixAIStudio.py
```

### 2.3 python直接実行の安定化

exeビルドは最後に行う。まずpython直接実行を安定させる:

```python
# HelixAIStudio.py 冒頭に以下を追加（なければ）
import sys
import os

# パス解決
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# data/ディレクトリ確保
os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('config', exist_ok=True)
```

### 2.4 受入条件（Phase A）

- [ ] `python HelixAIStudio.py` で正常に起動する
- [ ] mixAIタブ/soloAIタブ/一般設定タブが表示される
- [ ] Ollama接続テストが成功する
- [ ] 一般設定タブの「記憶・知識管理」セクションが表示される
- [ ] エラーが出た場合はログに記録し、修正を実施

---

## 3. Phase B: Phase 2 RAGコンテキスト注入の実装

### 3.1 アーキテクチャ概要

```
ユーザー入力
    │
    ▼
Phase 1: Claude CLI（既存・記憶注入済み v8.1.0）
    │
    │ → Phase 1結果 + 各カテゴリへの指示JSON
    │
    ▼
★ Phase 2 前処理（v8.2.0 新規）
    │
    ├─→ カテゴリ別RAGコンテキスト構築
    │     ├── coding    → Procedural Memory（手順記憶）+ コード関連Semantic
    │     ├── research  → Episodic Memory（過去調査）+ Semantic KG（事実）
    │     ├── reasoning → Semantic Memory（事実・関係）+ Episodic（議論履歴）
    │     ├── translation → Episodic Memory（過去翻訳例）
    │     └── vision    → Semantic Memory（画像関連事実）
    │
    ▼
Phase 2: SequentialExecutor（各モデルにRAGコンテキスト付きプロンプト送信）
    │
    ▼
Phase 3: Claude CLI 比較統合（既存・記憶注入済み v8.1.0）
```

### 3.2 memory_manager.py への追加メソッド

`src/memory/memory_manager.py` の `HelixMemoryManager` クラスに以下を追加:

```python
def build_context_for_phase2(self, user_message: str, category: str) -> str:
    """
    Phase 2ローカルLLM向けの記憶コンテキストを構築する。
    カテゴリに応じて検索する記憶層を選択し、コンパクトなコンテキストを返す。

    Args:
        user_message: ユーザーの元の質問
        category: "coding" | "research" | "reasoning" | "translation" | "vision"

    Returns:
        <memory_context>...</memory_context> 形式の文字列。空の場合は空文字列。
    """
    context_parts = []

    try:
        # カテゴリ別の検索戦略
        if category == "coding":
            # コーディング: 手順記憶を最優先、次に関連事実
            procedures = self.search_procedural(user_message, top_k=3)
            if procedures:
                context_parts.append("## 関連する過去の手順・パターン")
                for proc in procedures:
                    context_parts.append(f"- {proc['title']}: {proc.get('steps', '')[:200]}")

            facts = self.search_semantic(user_message, top_k=3)
            if facts:
                context_parts.append("## 関連する技術的事実")
                for fact in facts:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                    )

        elif category == "research":
            # リサーチ: エピソード記憶（過去の調査）+ 事実
            episodes = self.search_episodic(user_message, top_k=3)
            if episodes:
                context_parts.append("## 過去の関連調査・議論")
                for ep in episodes:
                    summary = ep.get('summary', ep.get('content', ''))[:200]
                    context_parts.append(f"- {summary}")

            facts = self.search_semantic(user_message, top_k=5)
            if facts:
                context_parts.append("## 既知の事実")
                for fact in facts:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                    )

        elif category == "reasoning":
            # 推論: 事実記憶を最優先（論理的根拠として）
            facts = self.search_semantic(user_message, top_k=7)
            if facts:
                context_parts.append("## 推論の根拠となる既知の事実")
                for fact in facts:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                        f" (確信度: {fact.get('confidence', 'N/A')})"
                    )

            episodes = self.search_episodic(user_message, top_k=2)
            if episodes:
                context_parts.append("## 過去の関連議論")
                for ep in episodes:
                    summary = ep.get('summary', ep.get('content', ''))[:150]
                    context_parts.append(f"- {summary}")

        elif category == "translation":
            # 翻訳: 過去の翻訳例（エピソード記憶）
            episodes = self.search_episodic(user_message, top_k=3)
            if episodes:
                context_parts.append("## 過去の関連翻訳・表現例")
                for ep in episodes:
                    summary = ep.get('summary', ep.get('content', ''))[:200]
                    context_parts.append(f"- {summary}")

        elif category == "vision":
            # ビジョン: 関連する画像分析の事実
            facts = self.search_semantic(user_message, top_k=3)
            if facts:
                context_parts.append("## 関連する視覚分析の事実")
                for fact in facts:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                    )

        # コンテキストが空なら空文字列を返す
        if not context_parts:
            return ""

        # トークン制限: ローカルLLM向けなのでコンパクトに（最大800文字）
        context_text = "\n".join(context_parts)
        if len(context_text) > 800:
            context_text = context_text[:800] + "\n... (truncated)"

        return f"\n<memory_context>\n{context_text}\n</memory_context>\n"

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Phase 2 memory context build failed for {category}: {e}"
        )
        return ""
```

**重要**: `search_procedural()`, `search_semantic()`, `search_episodic()` が
既に `HelixMemoryManager` に存在するか確認すること。
存在しない場合は、各層のSQLite検索メソッドを追加する必要がある。

```python
# 以下のメソッドが未実装なら追加（memory_manager.py内）

def search_procedural(self, query: str, top_k: int = 3) -> list:
    """Procedural Memory（手順記憶）をベクトル検索"""
    try:
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []
        # SQLiteからproceduresテーブルを検索
        cursor = self.db.execute(
            "SELECT id, title, steps, tags, embedding FROM procedures"
        )
        results = []
        for row in cursor:
            if row[4]:  # embedding exists
                stored_emb = self._deserialize_embedding(row[4])
                similarity = self._cosine_similarity(query_embedding, stored_emb)
                if similarity > 0.3:  # 閾値
                    results.append({
                        'id': row[0], 'title': row[1],
                        'steps': row[2], 'tags': row[3],
                        'similarity': similarity
                    })
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Procedural search error: {e}")
        return []

def search_semantic(self, query: str, top_k: int = 5) -> list:
    """Semantic Memory（知識グラフ）をキーワード+ベクトル検索"""
    try:
        # まずキーワード検索
        cursor = self.db.execute(
            """SELECT id, subject, predicate, object, confidence, valid_from, valid_to
               FROM semantic_nodes
               WHERE (valid_to IS NULL OR valid_to > datetime('now'))
               AND (subject LIKE ? OR object LIKE ?)""",
            (f"%{query[:50]}%", f"%{query[:50]}%")
        )
        results = []
        for row in cursor:
            results.append({
                'id': row[0], 'subject': row[1],
                'predicate': row[2], 'object': row[3],
                'confidence': row[4]
            })
        return results[:top_k]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Semantic search error: {e}")
        return []

def search_episodic(self, query: str, top_k: int = 3) -> list:
    """Episodic Memory（エピソード記憶）をベクトル検索"""
    try:
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []
        cursor = self.db.execute(
            "SELECT id, session_id, content, summary, embedding, timestamp FROM episodes ORDER BY timestamp DESC LIMIT 100"
        )
        results = []
        for row in cursor:
            if row[4]:  # embedding exists
                stored_emb = self._deserialize_embedding(row[4])
                similarity = self._cosine_similarity(query_embedding, stored_emb)
                if similarity > 0.3:
                    results.append({
                        'id': row[0], 'session_id': row[1],
                        'content': row[2], 'summary': row[3],
                        'timestamp': row[5], 'similarity': similarity
                    })
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Episodic search error: {e}")
        return []
```

### 3.3 sequential_executor.py の修正

`src/backends/sequential_executor.py` で、各モデル実行前にRAGコンテキストを
プロンプトに注入するように修正。

**修正箇所を特定するための読み方**:
- Ollama API `/api/generate` を呼び出している箇所を探す
- その直前でプロンプト文字列を構築しているロジックを特定
- そこにRAGコンテキストを挿入する

```python
# sequential_executor.py 内の修正イメージ

# 既存のメソッド（例: execute_category() や _run_model()）内で、
# Ollama APIに送るpromptを構築している箇所を見つけて、以下を追加:

async def execute_category(self, category: str, instruction: str,
                           user_message: str, memory_manager=None):
    """
    カテゴリ別のローカルLLMを実行する。
    v8.2.0: memory_manager引数を追加し、RAGコンテキストを注入。
    """
    model = self._get_model_for_category(category)

    # ★ v8.2.0: Phase 2 RAGコンテキスト注入
    memory_context = ""
    if memory_manager:
        try:
            memory_context = memory_manager.build_context_for_phase2(
                user_message, category
            )
            if memory_context:
                logger.info(
                    f"Phase 2 RAG context injected for {category}: "
                    f"{len(memory_context)} chars"
                )
        except Exception as e:
            logger.warning(f"Phase 2 RAG context failed for {category}: {e}")

    # プロンプト構築（memory_contextを指示の前に挿入）
    full_prompt = f"{memory_context}\n{instruction}" if memory_context else instruction

    # 既存のOllama API呼び出しに full_prompt を渡す
    result = await self._call_ollama(model, full_prompt)
    # ...
```

### 3.4 mix_orchestrator.py の修正

`src/backends/mix_orchestrator.py` で、Phase 2実行時に `memory_manager` を
`SequentialExecutor` に渡すように修正。

```python
# mix_orchestrator.py 内の Phase 2 呼び出し箇所を修正

# 既存コード（Phase 2呼び出し）を探し、memory_managerを引数追加:

# 修正前（v8.1.0）:
# result = await self.sequential_executor.execute_category(
#     category, instruction, user_message
# )

# 修正後（v8.2.0）:
# result = await self.sequential_executor.execute_category(
#     category, instruction, user_message,
#     memory_manager=self.memory_manager  # ★ v8.2.0追加
# )
```

**重要**: `mix_orchestrator.py` が `self.memory_manager` を保持しているか確認。
v8.1.0でPhase 1/3への記憶注入のために既にインスタンス化されているはず。
されていない場合は、`__init__` で初期化を追加:

```python
# mix_orchestrator.py の __init__ 内
from src.memory.memory_manager import HelixMemoryManager

class MixAIOrchestrator:
    def __init__(self, ...):
        # ... 既存の初期化 ...
        # ★ v8.2.0: Phase 2用にもmemory_managerを保持
        try:
            self.memory_manager = HelixMemoryManager()
        except Exception as e:
            logger.warning(f"Memory manager init failed: {e}")
            self.memory_manager = None
```

### 3.5 helix_core モジュール群との関係整理

以下のファイルを確認し、`memory_manager.py` との関係を明確化:

```
確認対象:
- src/helix_core/memory_store.py    → memory_manager.pyが置き換え？並存？
- src/helix_core/vector_store.py    → qwen3-embedding:4bとの関係
- src/helix_core/light_rag.py       → 記憶・知識管理の「RAG有効化」はこれ？
- src/helix_core/rag_pipeline.py    → Phase 2前のRAG検索パイプライン
- src/helix_core/hybrid_search_engine.py → RRF統合の実装状態
```

**判断基準**:
- `memory_manager.py` が内部で `rag_pipeline.py` を呼び出している → そのまま
- `memory_manager.py` が独自にSQLite検索している → `rag_pipeline.py` は旧コード
- どちらも使われていない → デッドコード。コメントアウトまたは削除

**作業**:
1. 各ファイルを読んで、実際にimportされている箇所を `grep -rn` で検索
2. デッドコードは `# DEPRECATED: v8.2.0 - replaced by memory_manager.py` コメントを追加
3. 生きているコードは memory_manager.py からの呼び出し経路を確認

```bash
# デッドコード検出
grep -rn "from src.helix_core.memory_store" src/
grep -rn "from src.helix_core.vector_store" src/
grep -rn "from src.helix_core.light_rag" src/
grep -rn "from src.helix_core.rag_pipeline" src/
grep -rn "from src.helix_core.hybrid_search" src/
```

### 3.6 受入条件（Phase B）

- [ ] `memory_manager.py` に `build_context_for_phase2()` メソッドが追加されている
- [ ] `search_procedural()`, `search_semantic()`, `search_episodic()` が実装されている
- [ ] `sequential_executor.py` がPhase 2実行前にRAGコンテキストを注入している
- [ ] `mix_orchestrator.py` がPhase 2実行時に `memory_manager` を渡している
- [ ] RAGコンテキスト注入時にログに `Phase 2 RAG context injected for {category}` が出力される
- [ ] RAGコンテキスト取得失敗時もPhase 2は正常に実行される（フォールバック動作）
- [ ] helix_coreモジュール群とmemory_manager.pyの関係がコメントで明記されている
- [ ] coding/research/reasoning/translation/vision 各カテゴリで異なる検索戦略が適用される

---

## 4. Phase C: 定数更新・BIBLE生成・exeビルド

### 4.1 constants.py 更新

```python
# src/utils/constants.py
APP_VERSION = "8.2.0"
APP_CODENAME = "RAG Shell"
APP_DESCRIPTION = "Phase 2 RAGコンテキスト注入・記憶の外殻化"
```

### 4.2 BIBLE v8.2.0 生成

BIBLE v8.1.0（`BIBLE/BIBLE_Helix AI Studio_8.1.0.md`）をベースに、
以下のセクションを更新・追加してv8.2.0を生成:

**更新するセクション**:
1. ヘッダー: バージョン → 8.2.0 "RAG Shell"
2. バージョン変遷サマリー: v8.2.0行を追加
3. v8.2.0四本柱（新規セクション）:
   - Phase 2 RAGコンテキスト注入
   - カテゴリ別検索戦略
   - helix_coreモジュール整理
   - exe実行安定化
4. セクション3.1: 3Phase実行パイプライン図にPhase 2のRAG注入を追記
5. セクション3.4: SequentialExecutor説明にRAGコンテキスト注入の記載追加
6. セクション3.7: 記憶コンテキスト注入フローにPhase 2を追記:
   ```
   ├─→ [mixAI Phase 2] build_context_for_phase2(category) → 各ローカルLLMに注入
   ```
7. 付録A: v8.2.0 変更履歴を新規追加

**BIBLE生成ルール**:
- 500行以上であること
- v8.1.0の全セクションを維持（削除禁止）
- 実装済みの内容のみ記載（設計案は書かない）
- ファイルパスとクラス名は実際のコードと一致させる

### 4.3 exeビルド（最後に実行）

```bash
# Step 1: specファイル確認
# HelixAIStudio.spec の hiddenimports に以下があることを確認:
#   'src.memory',
#   'src.memory.memory_manager',

# Step 2: ビルド
pyinstaller HelixAIStudio.spec --noconfirm

# Step 3: 起動テスト
dist\HelixAIStudio\HelixAIStudio.exe

# Step 4: エラーが出たらログを確認
# dist\HelixAIStudio\logs\ 内のログを確認
```

**exeビルドが失敗する場合の代替策**:
```bash
# batファイルで直接起動（暫定措置）
# start_helix.bat を作成:
@echo off
cd /d "%~dp0"
python HelixAIStudio.py
pause
```

### 4.4 受入条件（Phase C）

- [ ] `constants.py` の `APP_VERSION` が "8.2.0" である
- [ ] BIBLE v8.2.0 が生成され、500行以上である
- [ ] BIBLE v8.2.0 のPhase 2記述にRAGコンテキスト注入が記載されている
- [ ] `python HelixAIStudio.py` で正常起動する
- [ ] （可能であれば）exeビルドが成功し、起動する

---

## 5. 統合テスト手順

### 5.1 Phase 2 RAG注入の動作確認

```
テスト1: 記憶が空の状態
  入力: 「Pythonのリスト内包表記について教えてください」
  期待: Phase 2の各カテゴリでRAGコンテキストは空（ログに注入なし）
       → Phase 2は通常通り実行される

テスト2: 記憶がある状態
  準備: soloAIタブで何度か技術的な質問をして記憶を蓄積させる
  入力: mixAIタブで関連する技術質問を実行
  期待: Phase 2のログに "Phase 2 RAG context injected for coding: XXX chars" が出力
       → Phase 2のローカルLLM出力に記憶コンテキストの影響が見える

テスト3: フォールバック動作
  準備: data/helix_memory.db を一時的にリネーム（記憶DBなし状態を模擬）
  入力: mixAIタブで質問を実行
  期待: Phase 2がエラーなく実行される（warningログのみ）
       → 記憶DBを元に戻す
```

### 5.2 全体動作確認チェックリスト

- [ ] python直接実行で起動する
- [ ] mixAIタブでPhase 1→2→3が正常に実行される
- [ ] Phase 2実行ログにRAGコンテキスト注入の記録がある（記憶がある場合）
- [ ] soloAIタブで記憶注入が動作する（v8.1.0から継続）
- [ ] 一般設定タブの記憶統計が表示される
- [ ] Memory Risk Gateが後処理で実行される
- [ ] ツールチップが全タブで表示される（v8.1.0から継続）

---

## 6. 実装順序まとめ

| 段階 | 内容 | 所要時間(推定) |
|------|------|---------------|
| **Phase A-1** | python直接実行のエラー診断 | 10分 |
| **Phase A-2** | 起動エラー修正（import/DB初期化等） | 20分 |
| **Phase B-1** | memory_manager.pyファイル全文読み | 10分 |
| **Phase B-2** | sequential_executor.pyファイル全文読み | 10分 |
| **Phase B-3** | mix_orchestrator.pyファイル全文読み | 10分 |
| **Phase B-4** | build_context_for_phase2() + 検索メソッド実装 | 30分 |
| **Phase B-5** | sequential_executor.py修正（RAG注入ポイント追加） | 20分 |
| **Phase B-6** | mix_orchestrator.py修正（memory_manager受け渡し） | 10分 |
| **Phase B-7** | helix_coreモジュール整理・コメント追加 | 15分 |
| **Phase C-1** | constants.py更新 | 5分 |
| **Phase C-2** | BIBLE v8.2.0生成 | 20分 |
| **Phase C-3** | 統合テスト | 15分 |
| **Phase C-4** | exeビルド（またはbatファイル作成） | 10分 |

**合計**: 約3時間

---

## 7. 禁止事項

1. **「既に実装済み」と報告してはならない** — 必ずgrepで該当コードを確認し、行番号を提示すること
2. **ファイル存在確認だけで「OK」としない** — import文が実行フローに組み込まれているか確認すること
3. **テストを省略しない** — Phase A完了後にpython起動確認、Phase B完了後にPhase 2動作確認を必ず行うこと
4. **BIBLEに設計案を書かない** — 実装済みの内容のみ記載すること
5. **旧モジュールを無断削除しない** — DEPRECATEDコメントを追加し、次バージョンで削除計画を立てること

---

## 8. app_settings.json 不整合の修正

BIBLE v8.1.0セクション11.2で `claude.default_model` の値が
`"claude-opus-4-5-20251101"` と記載されているが、
`constants.py` の `CLAUDE_MODELS` では `"claude-opus-4-5-20250929"` がID。

```python
# config/app_settings.json の claude.default_model を確認し、
# constants.py の CLAUDE_MODELS[1]["id"] と一致させること。
# 正しい値: "claude-opus-4-5-20250929"
```

---

*この指示書は Claude Opus 4.6 により、BIBLE v8.1.0精読・v8.1.0検証レポート・
プロジェクト全履歴の分析に基づいて作成されました。*
*2026-02-10*
