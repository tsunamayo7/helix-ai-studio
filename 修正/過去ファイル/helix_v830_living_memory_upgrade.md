# Helix AI Studio v8.3.0 "Living Memory" — Claude Code CLI 実装指示書

**対象バージョン**: v8.2.0 → v8.3.0
**コードネーム**: "Living Memory"（生きた記憶）
**作成日**: 2026-02-10
**作成者**: Claude Opus 4.6

---

## 0. 本指示書の目的

v8.2.0で完成した「RAG外殻」（Phase 1/2/3全てに記憶注入）の上に、
**記憶の自律的な成長・老化・集約**メカニズムを実装する。

具体的には:
1. **RAPTOR要約トリガー** — セッション終了・週次・バージョン更新の3段階で記憶を自動集約
2. **Temporal KG実動化** — valid_from/valid_toの実動作検証+GraphRAGコミュニティ要約
3. **DEPRECATEDモジュール完全削除** — helix_core5モジュール除去 + PyInstaller specクリーンアップ + exe安定ビルド

---

## 1. 作業前の必須手順（読み飛ばし禁止）

以下のファイルを**全文**読んでから実装に着手すること。

```
必読ファイル（この順番で）:
1. BIBLE/BIBLE_Helix AI Studio_8.2.0.md          — 全体アーキテクチャ把握（特にセクション3.7, 3.8, 3.9）
2. src/memory/memory_manager.py                   — HelixMemoryManager全メソッド把握（RAPTOR追加先）
3. src/helix_core/graph_rag.py                    — GraphRAG実装状態（Temporal KG拡張先、唯一の非DEPRECATED helix_coreモジュール）
4. src/backends/mix_orchestrator.py               — Phase完了時のフック（RAPTOR要約トリガー挿入先）
5. src/tabs/claude_tab.py                         — soloAIセッション終了のフック（RAPTOR要約トリガー挿入先）
6. src/helix_core/memory_store.py                 — DEPRECATED確認（削除対象）
7. src/helix_core/vector_store.py                 — DEPRECATED確認（削除対象）
8. src/helix_core/light_rag.py                    — DEPRECATED確認（削除対象）
9. src/helix_core/rag_pipeline.py                 — DEPRECATED確認（削除対象）
10. src/helix_core/hybrid_search_engine.py         — DEPRECATED確認（削除対象）
11. HelixAIStudio.spec                             — hiddenimportsクリーンアップ対象
```

**読了確認**: 各ファイルの行数・クラス名・メソッド一覧をログ出力してから次に進むこと。

---

## 2. Phase A: RAPTOR要約トリガーの実装

### 2.1 現状の問題

BIBLE v8.2.0 セクション3.7では「RAPTOR風多段要約: session→weekly→version」と記載があり、
`episode_summaries` テーブル（summary_type: session/weekly/version）も定義済み。
しかし、以下が**未実装**:

- セッション終了時に要約を生成するトリガーが存在しない
- 週次要約のスケジューラーが存在しない
- バージョン更新時の要約生成ロジックが存在しない

### 2.2 RAPTOR 3段階要約アーキテクチャ

```
セッション終了（mixAI Phase 3完了 / soloAI新規セッション押下）
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Level 1: Session Summary                        │
│  ・当該セッションの全episodesを取得                 │
│  ・ministral-3:8b で 200文字以内に要約              │
│  ・episode_summaries に summary_type='session' で保存│
│  ・非同期実行（UIブロックなし）                      │
└──────────────────────┬──────────────────────────┘
                       │
        蓄積（10セッション以上 or 月曜起動時）
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Level 2: Weekly Summary                         │
│  ・直近7日間の session_summary を取得               │
│  ・ministral-3:8b で 300文字以内に集約              │
│  ・episode_summaries に summary_type='weekly' で保存│
│  ・起動時バックグラウンドチェック                     │
└──────────────────────┬──────────────────────────┘
                       │
         バージョン更新時（APP_VERSION変更検出）
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Level 3: Version Summary                        │
│  ・該当バージョン期間の weekly_summaries を取得      │
│  ・ministral-3:8b で 500文字以内に統括要約           │
│  ・episode_summaries に summary_type='version' で保存│
│  ・バージョン変更時1回のみ実行                       │
└─────────────────────────────────────────────────┘
```

### 2.3 memory_manager.py への追加メソッド

`HelixMemoryManager` クラスに以下の3メソッドを追加:

```python
# ==========================================
# RAPTOR Multi-Level Summarization (v8.3.0)
# ==========================================

async def generate_session_summary(self, session_id: str) -> Optional[str]:
    """
    Level 1: セッション終了時にセッション全体の要約を生成する。
    
    - episodesテーブルから当該session_idの全レコードを取得
    - ministral-3:8b で200文字以内に要約
    - episode_summariesテーブルに保存（summary_type='session'）
    - 既に同一session_idのsession要約が存在する場合はスキップ
    
    Returns:
        生成された要約テキスト。スキップ・失敗時はNone。
    """
    try:
        # 既存チェック
        existing = self.db.execute(
            "SELECT id FROM episode_summaries WHERE session_id = ? AND summary_type = 'session'",
            (session_id,)
        ).fetchone()
        if existing:
            logger.debug(f"Session summary already exists for {session_id}")
            return None

        # セッションのエピソードを取得
        episodes = self.db.execute(
            "SELECT role, content FROM episodes WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        ).fetchall()
        
        if len(episodes) < 2:  # 最低でも1往復ないと要約不要
            return None

        # 会話テキスト構築（最大2000文字に切り詰め）
        conversation = "\n".join(
            f"{'User' if row[0] == 'user' else 'AI'}: {row[1][:300]}"
            for row in episodes
        )
        if len(conversation) > 2000:
            conversation = conversation[:2000] + "\n... (truncated)"

        # ministral-3:8b で要約生成
        prompt = (
            "以下の会話セッションを200文字以内で要約してください。"
            "主要な質問・結論・決定事項を含めてください。日本語で回答。\n\n"
            f"{conversation}\n\n要約:"
        )
        summary = await self._call_resident_llm(prompt, max_tokens=300)
        
        if not summary:
            return None

        # 保存
        self.db.execute(
            "INSERT INTO episode_summaries (session_id, summary_type, content, timestamp) "
            "VALUES (?, 'session', ?, datetime('now'))",
            (session_id, summary)
        )
        self.db.commit()
        logger.info(f"RAPTOR session summary generated for {session_id}: {len(summary)} chars")
        return summary

    except Exception as e:
        logger.warning(f"Session summary generation failed: {e}")
        return None


async def generate_weekly_summary(self) -> Optional[str]:
    """
    Level 2: 直近7日間のセッション要約を集約する。
    
    トリガー条件（いずれか）:
    - 未要約のセッション要約が10件以上蓄積
    - 月曜日の初回起動
    
    Returns:
        生成された週次要約テキスト。条件未達・失敗時はNone。
    """
    try:
        # 直近7日間の session_summary で、まだ weekly に集約されていないものを取得
        recent_sessions = self.db.execute(
            """SELECT id, session_id, content, timestamp 
               FROM episode_summaries 
               WHERE summary_type = 'session' 
               AND timestamp > datetime('now', '-7 days')
               ORDER BY timestamp ASC"""
        ).fetchall()

        if len(recent_sessions) < 3:  # 最低3セッションないと集約不要
            return None

        # 最新の weekly summary のタイムスタンプを確認
        last_weekly = self.db.execute(
            "SELECT timestamp FROM episode_summaries WHERE summary_type = 'weekly' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

        # 条件チェック: 10件以上 or 前回weeklから7日以上経過
        needs_weekly = False
        if len(recent_sessions) >= 10:
            needs_weekly = True
        elif last_weekly is None:
            needs_weekly = True  # 初回
        else:
            from datetime import datetime, timedelta
            last_time = datetime.fromisoformat(last_weekly[0])
            if datetime.now() - last_time > timedelta(days=7):
                needs_weekly = True

        if not needs_weekly:
            return None

        # セッション要約を結合
        summaries_text = "\n".join(
            f"[{row[3][:10]}] {row[2]}" for row in recent_sessions
        )
        if len(summaries_text) > 3000:
            summaries_text = summaries_text[:3000] + "\n... (truncated)"

        prompt = (
            "以下は直近1週間の複数セッション要約です。"
            "これらを300文字以内の週次レポートとして集約してください。"
            "主要な活動テーマ・成果・未解決事項を含めてください。日本語で回答。\n\n"
            f"{summaries_text}\n\n週次要約:"
        )
        summary = await self._call_resident_llm(prompt, max_tokens=500)

        if not summary:
            return None

        self.db.execute(
            "INSERT INTO episode_summaries (session_id, summary_type, content, timestamp) "
            "VALUES ('weekly_aggregate', 'weekly', ?, datetime('now'))",
            (summary,)
        )
        self.db.commit()
        logger.info(f"RAPTOR weekly summary generated: {len(summary)} chars from {len(recent_sessions)} sessions")
        return summary

    except Exception as e:
        logger.warning(f"Weekly summary generation failed: {e}")
        return None


async def generate_version_summary(self, version: str) -> Optional[str]:
    """
    Level 3: バージョン期間全体の活動をまとめる統括要約。
    
    トリガー: APP_VERSIONが前回記録と異なる場合に1回だけ実行。
    
    Returns:
        生成された統括要約テキスト。既存・失敗時はNone。
    """
    try:
        # 既存チェック
        existing = self.db.execute(
            "SELECT id FROM episode_summaries WHERE summary_type = 'version' AND session_id = ?",
            (f"version_{version}",)
        ).fetchone()
        if existing:
            return None

        # 直近の weekly summaries を全取得
        weeklies = self.db.execute(
            "SELECT content, timestamp FROM episode_summaries WHERE summary_type = 'weekly' ORDER BY timestamp ASC"
        ).fetchall()

        if not weeklies:
            # weeklySummaryがなければsession summaryから直接生成
            sessions = self.db.execute(
                "SELECT content, timestamp FROM episode_summaries WHERE summary_type = 'session' ORDER BY timestamp DESC LIMIT 20"
            ).fetchall()
            if not sessions:
                return None
            source_text = "\n".join(f"[{row[1][:10]}] {row[0]}" for row in sessions)
            source_label = f"{len(sessions)} sessions"
        else:
            source_text = "\n".join(f"[{row[1][:10]}] {row[0]}" for row in weeklies)
            source_label = f"{len(weeklies)} weekly summaries"

        if len(source_text) > 4000:
            source_text = source_text[:4000] + "\n... (truncated)"

        prompt = (
            f"以下はHelix AI Studio v{version}期間中の活動記録です（{source_label}）。"
            "500文字以内でバージョン統括要約を作成してください。"
            "期間中の主要な開発活動・技術的決定・学びを含めてください。日本語で回答。\n\n"
            f"{source_text}\n\nバージョン統括要約:"
        )
        summary = await self._call_resident_llm(prompt, max_tokens=800)

        if not summary:
            return None

        self.db.execute(
            "INSERT INTO episode_summaries (session_id, summary_type, content, timestamp) "
            "VALUES (?, 'version', ?, datetime('now'))",
            (f"version_{version}", summary)
        )
        self.db.commit()
        logger.info(f"RAPTOR version summary generated for v{version}: {len(summary)} chars")
        return summary

    except Exception as e:
        logger.warning(f"Version summary generation failed: {e}")
        return None
```

### 2.4 _call_resident_llm ヘルパーの確認

上記3メソッドは全て `_call_resident_llm()` を使用する。
このメソッドが `memory_manager.py` に存在するか確認すること。

```python
# もし未実装なら追加（既存のOllama API呼び出しパターンを流用）:
async def _call_resident_llm(self, prompt: str, max_tokens: int = 300) -> Optional[str]:
    """
    常駐LLM（ministral-3:8b）を呼び出して結果テキストを返す。
    Memory Risk Gate と同じ呼び出し経路を使用。
    """
    import aiohttp
    try:
        payload = {
            "model": "ministral-3:8b",
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens}
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "").strip()
                else:
                    logger.warning(f"Resident LLM returned status {resp.status}")
                    return None
    except Exception as e:
        logger.warning(f"Resident LLM call failed: {e}")
        return None
```

**重要**: Memory Risk Gate（MemoryRiskGate）が既に同様のOllama呼び出しをしている場合、
その内部メソッドを共用すること。コードの重複を避ける。

### 2.5 トリガー挿入箇所

#### A. セッション要約トリガー（Level 1）

**mixAI — Phase 3完了後**:
```python
# src/backends/mix_orchestrator.py
# Phase 3完了＋後処理（Memory Risk Gate）の後に追加:

# ★ v8.3.0: RAPTOR Session Summary
if self.memory_manager:
    import asyncio
    asyncio.ensure_future(
        self.memory_manager.generate_session_summary(self.current_session_id)
    )
    logger.info("RAPTOR session summary triggered")
```

**soloAI — 新規セッション押下時 / ウィンドウクローズ時**:
```python
# src/tabs/claude_tab.py
# 「新規セッション」ボタンのハンドラ内、セッションIDリセット前に追加:

# ★ v8.3.0: RAPTOR Session Summary
if self.memory_manager and self.current_session_id:
    import asyncio
    asyncio.ensure_future(
        self.memory_manager.generate_session_summary(self.current_session_id)
    )
```

#### B. 週次要約トリガー（Level 2）

**起動時バックグラウンドチェック**:
```python
# HelixAIStudio.py または src/main_window.py
# アプリ起動後、UIが表示された後にバックグラウンド実行:

# ★ v8.3.0: RAPTOR Weekly Summary check on startup
def _check_weekly_summary(self):
    """起動時に週次要約の必要性をチェック"""
    if self.memory_manager:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(self.memory_manager.generate_weekly_summary())
        else:
            loop.run_until_complete(self.memory_manager.generate_weekly_summary())

# QTimerで起動30秒後に1回だけ実行（起動直後のUI負荷を避ける）
from PyQt6.QtCore import QTimer
QTimer.singleShot(30000, self._check_weekly_summary)
```

#### C. バージョン要約トリガー（Level 3）

**起動時バージョン変更検出**:
```python
# HelixAIStudio.py または src/main_window.py

# ★ v8.3.0: RAPTOR Version Summary on version change
def _check_version_summary(self):
    """バージョン変更時に統括要約を生成"""
    if not self.memory_manager:
        return
    
    from src.utils.constants import APP_VERSION
    
    # 前回起動時のバージョンを記録ファイルから取得
    version_file = os.path.join('data', '.last_version')
    last_version = ""
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            last_version = f.read().strip()
    
    if last_version and last_version != APP_VERSION:
        # バージョンが変わった → 旧バージョンの統括要約を生成
        import asyncio
        asyncio.ensure_future(
            self.memory_manager.generate_version_summary(last_version)
        )
        logger.info(f"RAPTOR version summary triggered for v{last_version}")
    
    # 現在バージョンを記録
    with open(version_file, 'w') as f:
        f.write(APP_VERSION)

# QTimerで起動45秒後に実行（weekly checkの後）
QTimer.singleShot(45000, self._check_version_summary)
```

### 2.6 受入条件（Phase A）

- [ ] `generate_session_summary()` が memory_manager.py に実装されている
- [ ] `generate_weekly_summary()` が memory_manager.py に実装されている
- [ ] `generate_version_summary()` が memory_manager.py に実装されている
- [ ] `_call_resident_llm()` が実装されている（既存メソッドの流用可）
- [ ] mixAI Phase 3完了後に session summary トリガーが発火する
- [ ] soloAI 新規セッション押下時に session summary トリガーが発火する
- [ ] 起動30秒後に weekly summary チェックが実行される
- [ ] 起動45秒後に version summary チェックが実行される
- [ ] episode_summaries テーブルに session/weekly/version の3種が保存される
- [ ] 全トリガーが非同期実行でUIをブロックしない
- [ ] 全トリガーが例外時にwarningログのみでメイン処理に影響しない

---

## 3. Phase B: Temporal KG実動化 + GraphRAGコミュニティ要約

### 3.1 現状の問題

- `semantic_nodes` テーブルに `valid_from`/`valid_to` カラムは定義済み
- `graph_rag.py` に Temporal KG 拡張メソッドがあるが、**実動作が未検証**
- GraphRAG の「コミュニティ要約」（ノード群の自動クラスタリング+要約生成）が未実装

### 3.2 Temporal KG 検証手順

```python
# 以下のコードパスを実際に追跡し、動作を検証すること:

# 1. semantic_nodesへのINSERT時にvalid_fromが設定されるか
grep -n "valid_from" src/memory/memory_manager.py
grep -n "valid_from" src/helix_core/graph_rag.py

# 2. UPDATE時に旧ノードのvalid_toが設定されるか（DEPRECATE操作）
grep -n "valid_to" src/memory/memory_manager.py
grep -n "DEPRECATE" src/memory/memory_manager.py

# 3. 検索時にvalid_toフィルタが適用されるか
grep -n "valid_to IS NULL" src/memory/memory_manager.py
```

### 3.3 Temporal KG 修正が必要な場合

以下のパターンで修正:

```python
# memory_manager.py 内のSemantic Memory操作メソッド

# A. ノード追加時 — valid_from を必ず設定
def add_semantic_node(self, subject, predicate, obj, confidence=0.8, source="ai"):
    self.db.execute(
        """INSERT INTO semantic_nodes 
           (subject, predicate, object, confidence, valid_from, source) 
           VALUES (?, ?, ?, ?, datetime('now'), ?)""",
        (subject, predicate, obj, confidence, source)
    )
    self.db.commit()

# B. ノード更新時 — 旧ノードを期限切れにし、新ノードを追加
def update_semantic_node(self, node_id, new_object, new_confidence=None):
    # 旧ノードの valid_to を設定（論理削除）
    self.db.execute(
        "UPDATE semantic_nodes SET valid_to = datetime('now') WHERE id = ?",
        (node_id,)
    )
    # 旧ノード情報を取得して新ノード追加
    old = self.db.execute(
        "SELECT subject, predicate, confidence, source FROM semantic_nodes WHERE id = ?",
        (node_id,)
    ).fetchone()
    if old:
        self.add_semantic_node(
            old[0], old[1], new_object,
            new_confidence or old[2], old[3]
        )

# C. 検索時 — 有効期間内のノードのみ返す
def search_semantic_current(self, query, top_k=5):
    """有効なセマンティックノードのみを検索"""
    cursor = self.db.execute(
        """SELECT id, subject, predicate, object, confidence 
           FROM semantic_nodes 
           WHERE (valid_to IS NULL OR valid_to > datetime('now'))
           AND (subject LIKE ? OR object LIKE ?)""",
        (f"%{query[:50]}%", f"%{query[:50]}%")
    )
    return [dict(zip(['id','subject','predicate','object','confidence'], row)) 
            for row in cursor.fetchall()[:top_k]]

# D. 履歴検索 — 期限切れノードも含めて時系列表示
def get_semantic_history(self, subject, top_k=10):
    """特定主語の変遷履歴を取得"""
    cursor = self.db.execute(
        """SELECT id, subject, predicate, object, confidence, valid_from, valid_to
           FROM semantic_nodes 
           WHERE subject LIKE ?
           ORDER BY valid_from DESC""",
        (f"%{subject}%",)
    )
    return [dict(zip(
        ['id','subject','predicate','object','confidence','valid_from','valid_to'], row
    )) for row in cursor.fetchall()[:top_k]]
```

### 3.4 GraphRAGコミュニティ要約

networkxベースの知識グラフに対して、Louvainコミュニティ検出+要約を実装:

```python
# src/helix_core/graph_rag.py に追加

import networkx as nx
try:
    from networkx.algorithms.community import louvain_communities
except ImportError:
    louvain_communities = None


class GraphRAG:
    # ... 既存メソッド ...

    # ★ v8.3.0: コミュニティ検出・要約
    def detect_communities(self) -> list:
        """
        Louvainアルゴリズムで知識グラフのコミュニティ（トピッククラスタ）を検出する。
        
        Returns:
            list of sets: 各コミュニティに属するノードIDのセット
        """
        if louvain_communities is None:
            logger.warning("Louvain community detection not available")
            return []
        
        if self.graph.number_of_nodes() < 3:
            return []

        try:
            communities = louvain_communities(self.graph, seed=42)
            # 小さすぎるコミュニティ（2ノード未満）を除外
            return [c for c in communities if len(c) >= 2]
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            return []

    def get_community_nodes(self, community: set) -> list:
        """コミュニティのノード詳細情報を取得"""
        nodes = []
        for node_id in community:
            data = self.graph.nodes.get(node_id, {})
            nodes.append({
                'id': node_id,
                'label': data.get('label', str(node_id)),
                'subject': data.get('subject', ''),
                'predicate': data.get('predicate', ''),
                'object': data.get('object', '')
            })
        return nodes

    async def generate_community_summaries(self, memory_manager) -> list:
        """
        各コミュニティの要約を生成する。
        
        GraphRAG論文の「コミュニティ要約」アプローチ:
        - 各クラスタのノード群を取得
        - 事実（トリプル）を列挙
        - ministral-3:8bで要約
        
        Returns:
            list of dict: [{community_id, nodes_count, summary}]
        """
        communities = self.detect_communities()
        if not communities:
            return []

        results = []
        for i, community in enumerate(communities):
            nodes = self.get_community_nodes(community)
            
            # トリプルを列挙
            triples_text = "\n".join(
                f"- {n['subject']} {n['predicate']} {n['object']}"
                for n in nodes if n['subject']
            )
            
            if not triples_text:
                continue

            if len(triples_text) > 1500:
                triples_text = triples_text[:1500] + "\n..."

            prompt = (
                f"以下は関連する{len(nodes)}個の事実のグループです。"
                "このグループのトピックを100文字以内で要約してください。日本語で回答。\n\n"
                f"{triples_text}\n\nトピック要約:"
            )

            try:
                summary = await memory_manager._call_resident_llm(prompt, max_tokens=200)
                if summary:
                    results.append({
                        'community_id': i,
                        'nodes_count': len(nodes),
                        'summary': summary
                    })
            except Exception as e:
                logger.warning(f"Community {i} summary failed: {e}")

        logger.info(f"GraphRAG community summaries generated: {len(results)}/{len(communities)}")
        return results
```

### 3.5 graph_rag.py とmemory_manager.pyの統合

```python
# memory_manager.py に追加

async def rebuild_knowledge_graph(self):
    """
    SQLiteのsemantic_nodesからnetworkxグラフを再構築し、
    コミュニティ要約を生成する。
    起動時・記憶大量追加後に実行。
    """
    try:
        from src.helix_core.graph_rag import GraphRAG
        
        graph_rag = GraphRAG()
        
        # SQLiteからvalid（期限切れでない）ノードを取得してグラフ構築
        nodes = self.db.execute(
            """SELECT id, subject, predicate, object, confidence 
               FROM semantic_nodes 
               WHERE valid_to IS NULL OR valid_to > datetime('now')"""
        ).fetchall()
        
        for node in nodes:
            graph_rag.graph.add_node(
                node[0],
                label=f"{node[1]}-{node[2]}-{node[3]}",
                subject=node[1], predicate=node[2], object=node[3],
                confidence=node[4]
            )

        # エッジも追加
        edges = self.db.execute(
            "SELECT from_node, to_node, relation, weight FROM semantic_edges"
        ).fetchall()
        
        for edge in edges:
            if graph_rag.graph.has_node(edge[0]) and graph_rag.graph.has_node(edge[1]):
                graph_rag.graph.add_edge(edge[0], edge[1], relation=edge[2], weight=edge[3])

        logger.info(
            f"Knowledge graph rebuilt: {graph_rag.graph.number_of_nodes()} nodes, "
            f"{graph_rag.graph.number_of_edges()} edges"
        )

        # コミュニティ要約（ノードが10以上ある場合のみ）
        if graph_rag.graph.number_of_nodes() >= 10:
            summaries = await graph_rag.generate_community_summaries(self)
            if summaries:
                # コミュニティ要約をepisode_summariesに保存
                for s in summaries:
                    self.db.execute(
                        "INSERT INTO episode_summaries (session_id, summary_type, content, timestamp) "
                        "VALUES (?, 'community', ?, datetime('now'))",
                        (f"community_{s['community_id']}", s['summary'])
                    )
                self.db.commit()
                logger.info(f"Stored {len(summaries)} community summaries")

        return graph_rag

    except Exception as e:
        logger.warning(f"Knowledge graph rebuild failed: {e}")
        return None
```

### 3.6 受入条件（Phase B）

- [ ] `valid_from` が semantic_nodes INSERT 時に必ず設定されている（grepで確認）
- [ ] `valid_to` が DEPRECATE/UPDATE 操作時に設定されている（grepで確認）
- [ ] `search_semantic_by_text()` が `valid_to IS NULL OR valid_to > datetime('now')` フィルタを含む
- [ ] `get_semantic_history()` メソッドが実装されている
- [ ] `detect_communities()` が graph_rag.py に実装されている
- [ ] `generate_community_summaries()` が graph_rag.py に実装されている
- [ ] `rebuild_knowledge_graph()` が memory_manager.py に実装されている
- [ ] コミュニティ要約がepisode_summariesテーブルにsummary_type='community'で保存される
- [ ] networkx のLouvainコミュニティ検出が動作する（networkx >= 2.8 確認）

---

## 4. Phase C: DEPRECATEDモジュール完全削除 + exe安定ビルド

### 4.1 削除対象ファイル

v8.2.0でDEPRECATED指定された5ファイル:

```bash
# 削除前に最終確認（import参照がゼロであること）
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

# 参照ゼロを確認後に削除
del src\helix_core\memory_store.py
del src\helix_core\vector_store.py
del src\helix_core\light_rag.py
del src\helix_core\rag_pipeline.py
del src\helix_core\hybrid_search_engine.py
```

**注意**: `graph_rag.py` は削除しない。v8.3.0でコミュニティ検出に使用。

### 4.2 HelixAIStudio.spec クリーンアップ

```python
# HelixAIStudio.spec の hiddenimports から以下を削除:

# 削除する行:
'src.helix_core.light_rag',        # DELETED v8.3.0
'src.helix_core.rag_pipeline',     # DELETED v8.3.0

# 注意: 以下は残す
'src.helix_core.graph_rag',        # 残す（コミュニティ検出で使用）
```

### 4.3 helix_core/__init__.py クリーンアップ

```python
# src/helix_core/__init__.py がある場合、
# 削除したモジュールのimport/exportを除去

# 修正前（例）:
# from .memory_store import MemoryStore
# from .light_rag import LightRAG

# 修正後: 上記行を削除
```

### 4.4 exe安定ビルド手順

```bash
# Step 1: 依存関係確認
pip install pyinstaller networkx numpy aiohttp aiofiles PyQt6 PyQt6-WebEngine

# Step 2: specファイルのhiddenimportsが正しいことを確認
# （4.2のクリーンアップ済み）

# Step 3: ビルド
pyinstaller HelixAIStudio.spec --noconfirm

# Step 4: 起動テスト
dist\HelixAIStudio\HelixAIStudio.exe

# Step 5: エラー確認
# エラーが出る場合は以下をチェック:
# a) dist\HelixAIStudio\内にnetworkxパッケージが含まれているか
# b) data/ディレクトリが作成されるか
# c) 起動ログにimportエラーがないか
```

### 4.5 exe失敗時の代替手段

```batch
@echo off
REM start_helix.bat — exe不要のダイレクト起動
cd /d "%~dp0"
python HelixAIStudio.py
if errorlevel 1 (
    echo.
    echo [ERROR] 起動に失敗しました。ログを確認してください。
    echo   logs/ ディレクトリのログファイルを参照
    pause
)
```

### 4.6 受入条件（Phase C）

- [ ] 5つのDEPRECATEDファイルが削除されている
- [ ] grep で削除モジュールへの参照がゼロ
- [ ] graph_rag.py は残存しており、正常にimportできる
- [ ] HelixAIStudio.spec から light_rag, rag_pipeline が除去されている
- [ ] `python HelixAIStudio.py` で正常に起動する
- [ ] （可能であれば）`pyinstaller HelixAIStudio.spec --noconfirm` が成功する
- [ ] 起動テスト（exe or python直接）で全タブが表示される

---

## 5. Phase D: 定数更新・BIBLE生成

### 5.1 constants.py 更新

```python
APP_VERSION = "8.3.0"
APP_CODENAME = "Living Memory"
```

### 5.2 BIBLE v8.3.0 生成

BIBLE v8.2.0をベースに以下を更新・追加:

**更新するセクション**:
1. ヘッダー: 8.3.0 "Living Memory"
2. 設計哲学: 第9項追加「記憶の自律成長 — RAPTOR多段要約+GraphRAGコミュニティ要約で記憶が自動的に集約・階層化される」
3. バージョン変遷: v8.3.0行追加
4. v8.3.0三本柱（新規セクション）
5. セクション3.7: 4層メモリにRAPTOR要約トリガーの実装詳細を追記
6. セクション3.9: helix_coreモジュール → 削除完了（DEPRECATEDから完全削除に変更）
7. 新セクション: GraphRAGコミュニティ要約アーキテクチャ
8. セクション12: PyInstaller hiddenimports更新
9. セクション15: ロードマップ更新（v8.3.0完了を反映）
10. 付録C: v8.3.0 変更履歴を新規追加

**BIBLE生成ルール**:
- 500行以上であること
- v8.2.0の全セクションを維持（DEPRECATED記述は「v8.3.0で完全削除」に更新）
- 実装済みの内容のみ記載（設計案は書かない）
- episode_summariesテーブルのsummary_typeに `community` が追加されたことを記載

### 5.3 受入条件（Phase D）

- [ ] `APP_VERSION` が "8.3.0" である
- [ ] `APP_CODENAME` が "Living Memory" である
- [ ] BIBLE v8.3.0 が 500行以上である
- [ ] 付録Cにv8.3.0変更履歴が記載されている

---

## 6. 統合テスト手順

### 6.1 RAPTOR要約テスト

```
テスト1: Session Summary
  手順: soloAIタブで3回以上の質問をした後、「新規セッション」を押す
  期待: ログに "RAPTOR session summary generated" が出力
       → episode_summaries テーブルに summary_type='session' のレコードが存在

テスト2: Session Summary（mixAI）
  手順: mixAIタブで3Phase実行を完了する
  期待: Phase 3完了後のログに "RAPTOR session summary triggered" が出力

テスト3: Weekly Summary
  手順: 3つ以上のセッション要約が蓄積された状態でアプリを再起動
  期待: 起動30秒後にログで weekly summary チェックが実行
       → 条件達成時は "RAPTOR weekly summary generated" が出力

テスト4: Version Summary
  手順: data/.last_version を "8.2.0" に書き換えてから起動
  期待: 起動45秒後にログに "RAPTOR version summary triggered for v8.2.0" が出力
```

### 6.2 Temporal KG テスト

```
テスト5: valid_from設定
  手順: SQLiteブラウザで helix_memory.db の semantic_nodes を確認
  期待: valid_from カラムに日時が設定されている（NULLでない）

テスト6: valid_toフィルタ
  手順: 手動でsemantic_nodesの1レコードに valid_to=過去日時 を設定
  期待: search_semantic_by_text() の結果にそのレコードが含まれない
```

### 6.3 モジュール削除テスト

```
テスト7: 起動テスト
  手順: python HelixAIStudio.py を実行
  期待: ImportErrorなし、全タブ表示

テスト8: graph_rag.py健全性
  手順: python -c "from src.helix_core.graph_rag import GraphRAG; print('OK')"
  期待: "OK" が出力される
```

---

## 7. 実装順序まとめ

| 段階 | 内容 | 所要時間(推定) |
|------|------|---------------|
| **Phase A-1** | memory_manager.py全文読み | 10分 |
| **Phase A-2** | generate_session_summary() 実装 | 15分 |
| **Phase A-3** | generate_weekly_summary() 実装 | 15分 |
| **Phase A-4** | generate_version_summary() 実装 | 15分 |
| **Phase A-5** | _call_resident_llm() 実装/確認 | 10分 |
| **Phase A-6** | 3箇所のトリガー挿入 | 20分 |
| **Phase B-1** | Temporal KG valid_from/valid_to 検証 | 15分 |
| **Phase B-2** | 不足している temporal 操作メソッド追加 | 15分 |
| **Phase B-3** | graph_rag.py にコミュニティ検出追加 | 20分 |
| **Phase B-4** | rebuild_knowledge_graph() 実装 | 15分 |
| **Phase C-1** | grep最終確認 + 5ファイル削除 | 10分 |
| **Phase C-2** | spec + __init__.py クリーンアップ | 10分 |
| **Phase C-3** | exe ビルド or bat 作成 | 15分 |
| **Phase D-1** | constants.py更新 | 5分 |
| **Phase D-2** | BIBLE v8.3.0 生成 | 20分 |
| **Phase D-3** | 統合テスト | 15分 |

**合計**: 約3.5時間

---

## 8. 禁止事項

1. **「既に実装済み」と報告してはならない** — 必ずgrepで該当コードを確認し、行番号を提示すること
2. **graph_rag.pyを削除しない** — DEPRECATEDではない。コミュニティ検出で使用する
3. **テストを省略しない** — 各Phase完了後にテストを実行すること
4. **BIBLEに設計案を書かない** — 実装済みの内容のみ記載すること
5. **RAPTOR要約でUIをブロックしない** — 全て非同期実行（asyncio.ensure_future）とすること
6. **ministral-3:8bへの呼び出しを同期にしない** — async/awaitを使用すること
7. **削除対象5ファイル以外のhelix_coreファイルを削除しない** — graph_rag.py, auto_collector.py, feedback_collector.py, mother_ai.py, perception.py, web_search_engine.py は残す

---

*この指示書は Claude Opus 4.6 により、BIBLE v8.2.0精読および v8.1.0→v8.2.0 の実装履歴に基づいて作成されました。*
*2026-02-10*
