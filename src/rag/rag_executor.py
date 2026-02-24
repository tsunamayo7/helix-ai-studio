"""
Helix AI Studio - RAG Executor (v8.5.0 Patch 1)
Step 2: ローカルLLMによる自律的RAG構築実行

v8.5.0 Patch 1 修正:
- P0-3: KG生成の無言失敗修正（モデル事前チェック、詳細エラーハンドリング）
- P1-2: document_semantic_links テーブルへの書き込み追加
- P0-1: Sub-step E-H の新メソッド追加
  - execute_raptor_summaries: RAPTOR階層要約生成
  - execute_graphrag_communities: GraphRAGコミュニティ検出・要約
  - execute_summary_embeddings: 要約Embedding生成・永続化
  - execute_verification_queries: 検証クエリ品質チェック
"""

import json
import hashlib
import logging
import struct
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from .document_chunker import DocumentChunker, Chunk
from ..utils.constants import (
    INFORMATION_FOLDER, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP,
)

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
EMBEDDING_MODEL = ""   # v11.5.0: 動的取得（_get_ctrl/emb_model()）
CONTROL_MODEL = ""     # v11.5.0: 動的取得
KG_MODEL = ""          # v11.5.0: 動的取得

_FALLBACK_EMBEDDING = "nomic-embed-text:latest"
_FALLBACK_CONTROL = "mistral:latest"
_FALLBACK_KG = "mistral:latest"


def _get_rag_ctrl_model() -> str:
    """v11.5.0: RAG用制御モデルを動的取得"""
    try:
        from ..memory.model_config import get_quality_llm
        m = get_quality_llm()
        if m:
            return m
    except Exception:
        pass
    return CONTROL_MODEL or _FALLBACK_CONTROL


def _get_rag_emb_model() -> str:
    """v11.5.0: RAG用Embeddingモデルを動的取得"""
    try:
        from ..memory.model_config import get_embedding_model
        m = get_embedding_model()
        if m:
            return m
    except Exception:
        pass
    return EMBEDDING_MODEL or _FALLBACK_EMBEDDING


def _get_rag_kg_model() -> str:
    """v11.5.0: RAG用KGモデルを動的取得"""
    try:
        from ..memory.model_config import get_quality_llm
        m = get_quality_llm()
        if m:
            return m
    except Exception:
        pass
    return KG_MODEL or _FALLBACK_KG


def _embedding_to_blob(embedding: List[float]) -> bytes:
    return struct.pack(f'{len(embedding)}f', *embedding)


class RAGExecutor:
    """ローカルLLMによるRAG構築実行エンジン"""

    def __init__(self, db_path: str = "data/helix_memory.db",
                 ollama_host: str = DEFAULT_OLLAMA_HOST):
        self.db_path = db_path
        self.ollama_host = ollama_host
        self.chunker = DocumentChunker()
        self._cancelled = False

    def cancel(self):
        """実行をキャンセル"""
        self._cancelled = True

    def reset(self):
        """キャンセル状態をリセット"""
        self._cancelled = False

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # モデル事前チェック (P0-3)
    # =========================================================================

    def _check_model_available(self, model_name: str) -> bool:
        """Ollamaモデルの利用可能性チェック"""
        import requests
        try:
            resp = requests.get(
                f"{self.ollama_host}/api/tags",
                timeout=10
            )
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                available = model_name in models or any(model_name in m for m in models)
                if not available:
                    logger.error(
                        f"Model '{model_name}' not found in Ollama. "
                        f"Available: {models[:10]}"
                    )
                else:
                    logger.info(f"Model '{model_name}' confirmed available in Ollama")
                return available
            else:
                logger.error(f"Ollama /api/tags returned status {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False

    # =========================================================================
    # Step 2a (Sub-step A): チャンキング
    # =========================================================================

    def execute_step(self, step_name: str, func, *args):
        """個別ステップの実行とエラーハンドリング"""
        try:
            logger.info(f"Step '{step_name}' started")
            result = func(*args)
            logger.info(f"Step '{step_name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"Step '{step_name}' failed: {e}", exc_info=True)
            # チャンキングの失敗は致命的→全体停止
            if step_name == "chunking":
                raise
            # その他のステップは警告してNone返却（スキップ）
            logger.warning(f"Step '{step_name}' skipped due to error")
            return None

    def execute_chunking(self, plan: dict, folder_path: str,
                         progress_callback: Optional[Callable] = None) -> List[Chunk]:
        """プランに基づいてファイルをチャンキング"""
        all_chunks = []
        classifications = plan.get("analysis", {}).get("file_classifications", [])

        # ファイル分類マップ
        file_map = {c["file"]: c for c in classifications}

        folder = Path(folder_path)
        files = sorted(f for f in folder.rglob('*')
                       if f.is_file() and f.suffix.lower()
                       in {'.txt', '.md', '.pdf', '.docx', '.csv', '.json'})

        for i, file_path in enumerate(files):
            if self._cancelled:
                break

            file_name = file_path.name
            classification = file_map.get(file_name, {})
            strategy = classification.get("chunk_strategy", "semantic")

            # プランのチャンクサイズ設定
            params = {}
            for step in plan.get("execution_plan", {}).get("steps", []):
                if step.get("name") == "チャンキング" and "params" in step:
                    params = step["params"]
                    break

            chunk_size = params.get("chunk_size", DEFAULT_CHUNK_SIZE)
            overlap = params.get("overlap", DEFAULT_CHUNK_OVERLAP)

            chunks = self.chunker.chunk_file(
                str(file_path), strategy=strategy,
                chunk_size=chunk_size, overlap=overlap
            )

            # ソースハッシュを計算
            source_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            for chunk in chunks:
                chunk.metadata["source_hash"] = source_hash
                chunk.metadata["category"] = classification.get("category", "reference")

            all_chunks.extend(chunks)

            if progress_callback:
                progress_callback("チャンキング", i + 1, len(files), file_name)

        logger.info(f"Chunking complete: {len(all_chunks)} chunks from {len(files)} files")
        return all_chunks

    # =========================================================================
    # Step 2b (Sub-step B): Embedding生成
    # =========================================================================

    def execute_embeddings(self, chunks: List[Chunk],
                           progress_callback: Optional[Callable] = None) -> List[Chunk]:
        """qwen3-embedding:4bでEmbedding生成（同期実行）"""
        import requests
        try:
            from ..memory.model_config import get_embedding_model
            embedding_model = get_embedding_model()
        except Exception:
            embedding_model = EMBEDDING_MODEL  # フォールバック

        for i, chunk in enumerate(chunks):
            if self._cancelled:
                break

            try:
                url = f"{self.ollama_host}/api/embed"
                payload = {"model": embedding_model, "input": chunk.content}
                resp = requests.post(url, json=payload, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings and len(embeddings) > 0:
                        chunk.embedding = _embedding_to_blob(embeddings[0])
                else:
                    logger.warning(f"Embedding failed for chunk {i}: status={resp.status_code}")
            except Exception as e:
                logger.warning(f"Embedding error for chunk {i}: {e}")

            if progress_callback:
                progress_callback("Embedding生成", i + 1, len(chunks),
                                  chunk.source_file)

        embedded_count = sum(1 for c in chunks if c.embedding)
        logger.info(f"Embedding complete: {embedded_count}/{len(chunks)} chunks")
        return chunks

    # =========================================================================
    # Step 2c (Sub-step C): チャンク要約・キーワード抽出
    # =========================================================================

    def execute_summarization(self, chunks: List[Chunk],
                               progress_callback: Optional[Callable] = None) -> List[Chunk]:
        """ministral-3:8bで要約/キーワード抽出"""
        import requests
        try:
            from ..memory.model_config import get_quality_llm
            quality_llm = get_quality_llm()
        except Exception:
            quality_llm = CONTROL_MODEL  # フォールバック

        EXTRACT_PROMPT = """以下のテキストチャンクについて、JSON形式のみ出力してください。
説明文やマークダウンは不要です。

出力形式:
{{"summary": "1-2文の要約", "keywords": ["キーワード1", "キーワード2", "キーワード3"], "entities": ["エンティティ1", "エンティティ2"]}}

テキスト:
{chunk_text}

JSON:"""

        parse_fail_count = 0

        for i, chunk in enumerate(chunks):
            if self._cancelled:
                break

            try:
                prompt = EXTRACT_PROMPT.format(chunk_text=chunk.content[:1000])
                url = f"{self.ollama_host}/api/generate"
                payload = {
                    "model": quality_llm,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                }
                resp = requests.post(url, json=payload, timeout=120)

                if resp.status_code == 200:
                    raw = resp.json().get("response", "")
                    parsed = self._parse_extraction(raw)
                    chunk.summary = parsed.get("summary", "")
                    chunk.keywords = parsed.get("keywords", [])
                    chunk.entities = parsed.get("entities", [])
                    if not chunk.summary:
                        parse_fail_count += 1
                        logger.debug(
                            f"Summarization chunk {i}: empty summary, "
                            f"raw response (先頭200字): {raw[:200]}"
                        )
                else:
                    logger.warning(
                        f"Summarization HTTP error chunk {i}: status={resp.status_code}"
                    )
            except Exception as e:
                logger.warning(f"Summarization error for chunk {i}: {e}")

            if progress_callback:
                progress_callback("要約/キーワード抽出", i + 1, len(chunks),
                                  chunk.source_file)

        summarized_count = sum(1 for c in chunks if c.summary)
        logger.info(
            f"Summarization complete: {summarized_count}/{len(chunks)} chunks "
            f"(parse_failures={parse_fail_count})"
        )
        return chunks

    # =========================================================================
    # Step 2d (Sub-step D): エンティティ抽出・TKGエッジ構築
    # =========================================================================

    def execute_kg_generation(self, chunks: List[Chunk], model: str = KG_MODEL,
                               progress_callback: Optional[Callable] = None) -> dict:
        """Semantic Node/Edge生成 (P0-3: 詳細エラーハンドリング付き)"""
        import requests

        KG_PROMPT = """以下のテキストチャンクから知識グラフのノードとエッジを抽出してください。

形式（JSONのみ出力）:
{{"nodes": [{{"entity": "...", "attribute": "...", "value": "..."}}],
 "edges": [{{"source": "...", "target": "...", "relation": "..."}}]}}

テキスト:
{chunk_text}

エンティティヒント: {entity_hints}"""

        # P0-3: モデル事前チェック
        if not self._check_model_available(model):
            logger.error(f"KG generation aborted: model '{model}' not available")
            return {"nodes_added": 0, "edges_added": 0,
                    "error": f"Model '{model}' not available in Ollama"}

        total_nodes = 0
        total_edges = 0
        success_count = 0
        failed_count = 0
        consecutive_failures = 0

        logger.info(f"KG生成開始: {len(chunks)}チャンク対象, モデル: {model}")

        for i, chunk in enumerate(chunks):
            if self._cancelled:
                break

            entity_hints = json.dumps(chunk.entities or [], ensure_ascii=False)
            try:
                prompt = KG_PROMPT.format(
                    chunk_text=chunk.content[:1500],
                    entity_hints=entity_hints,
                )
                url = f"{self.ollama_host}/api/generate"
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                }
                resp = requests.post(url, json=payload, timeout=120)

                if resp.status_code == 200:
                    raw = resp.json().get("response", "")
                    kg_data = self._parse_kg(raw)

                    if not kg_data.get("nodes") and not kg_data.get("edges"):
                        logger.debug(f"KG generation for chunk {i}: no nodes/edges parsed "
                                     f"from response (len={len(raw)})")

                    nodes_added, edges_added = self._store_kg_data(kg_data, chunk)
                    total_nodes += nodes_added
                    total_edges += edges_added
                    success_count += 1
                    consecutive_failures = 0
                    logger.debug(
                        f"KG chunk {i}/{len(chunks)}: "
                        f"nodes={nodes_added}, edges={edges_added}"
                    )
                else:
                    logger.warning(
                        f"KG generation HTTP error for chunk {i}: "
                        f"status={resp.status_code}, body={resp.text[:200]}"
                    )
                    failed_count += 1
                    consecutive_failures += 1

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ollama接続エラー (chunk {i}): {model} に接続できません: {e}")
                failed_count += 1
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    logger.error("3回連続接続エラー: KG生成を中止します")
                    break

            except json.JSONDecodeError as e:
                raw_text = resp.text[:200] if 'resp' in dir() else "(response unavailable)"
                logger.warning(
                    f"KG生成のJSON解析エラー (chunk {i}): {e}\n"
                    f"  raw response (先頭200字): {raw_text}"
                )
                failed_count += 1
                consecutive_failures = 0

            except Exception as e:
                logger.error(
                    f"KG生成の予期しないエラー (chunk {i}): {e}",
                    exc_info=True
                )
                failed_count += 1
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    logger.error("3回連続エラー: KG生成を中止します")
                    break

            if progress_callback:
                progress_callback("エンティティ抽出・TKGエッジ構築", i + 1, len(chunks),
                                  chunk.source_file)

        logger.info(
            f"KG生成完了: {success_count}/{len(chunks)}チャンク成功, "
            f"{total_nodes}ノード, {total_edges}エッジ生成, "
            f"{failed_count}件失敗"
        )
        return {
            "nodes_added": total_nodes,
            "edges_added": total_edges,
            "success_count": success_count,
            "failed_count": failed_count,
        }

    # =========================================================================
    # Step 2e (Sub-step E): RAPTOR階層要約生成
    # =========================================================================

    def execute_raptor_summaries(self, chunks: List[Chunk],
                                  model: str = KG_MODEL,
                                  progress_callback: Optional[Callable] = None) -> int:
        """RAPTOR階層要約: ファイル群をクラスタリングし、階層的な要約を生成"""
        import requests

        # ファイルごとにグループ化
        file_groups = {}
        for chunk in chunks:
            file_groups.setdefault(chunk.source_file, []).append(chunk)

        conn = self._get_conn()
        raptor_count = 0

        try:
            file_count = len(file_groups)
            for idx, (source_file, file_chunks) in enumerate(file_groups.items()):
                if self._cancelled:
                    break

                # ドキュメントレベル要約
                chunk_summaries = [c.summary for c in file_chunks if c.summary]
                if chunk_summaries:
                    combined = "\n".join(f"- {s}" for s in chunk_summaries[:20])
                    prompt = (
                        f"以下は「{source_file}」の各チャンク要約です。\n"
                        "ドキュメント全体を3-5文で要約してください。\n\n"
                        f"{combined}\n\n出力（日本語、3-5文のみ）:"
                    )
                    try:
                        url = f"{self.ollama_host}/api/generate"
                        payload = {
                            "model": _get_rag_ctrl_model(),
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.1, "num_predict": 512},
                        }
                        resp = requests.post(url, json=payload, timeout=60)
                        if resp.status_code == 200:
                            doc_summary = resp.json().get("response", "").strip()
                            if doc_summary:
                                # Embedding生成
                                emb_blob = self._get_embedding_sync(doc_summary)
                                conn.execute(
                                    "INSERT INTO document_summaries "
                                    "(source_file, level, summary, summary_embedding, entity_count) "
                                    "VALUES (?, 'document', ?, ?, ?)",
                                    (source_file, doc_summary, emb_blob,
                                     sum(len(c.entities or []) for c in file_chunks))
                                )
                                raptor_count += 1
                    except Exception as e:
                        logger.warning(f"RAPTOR document summary error for {source_file}: {e}")

                if progress_callback:
                    progress_callback("RAPTOR階層要約生成", idx + 1, file_count, source_file)

            # コレクション全体要約
            if not self._cancelled:
                doc_summaries = conn.execute(
                    "SELECT source_file, summary FROM document_summaries "
                    "WHERE level = 'document' ORDER BY created_at DESC LIMIT 20"
                ).fetchall()

                if doc_summaries:
                    combined = "\n".join(
                        f"- [{r['source_file']}] {r['summary']}" for r in doc_summaries
                    )
                    prompt = (
                        "以下はドキュメントコレクションの各文書要約です。\n"
                        "コレクション全体を5-8文で要約してください。\n\n"
                        f"{combined}\n\n出力（日本語、5-8文のみ）:"
                    )
                    try:
                        url = f"{self.ollama_host}/api/generate"
                        payload = {
                            "model": _get_rag_ctrl_model(),
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.1, "num_predict": 800},
                        }
                        resp = requests.post(url, json=payload, timeout=60)
                        if resp.status_code == 200:
                            collection_summary = resp.json().get("response", "").strip()
                            if collection_summary:
                                emb_blob = self._get_embedding_sync(collection_summary)
                                conn.execute(
                                    "INSERT INTO document_summaries "
                                    "(source_file, level, summary, summary_embedding) "
                                    "VALUES ('_collection', 'collection', ?, ?)",
                                    (collection_summary, emb_blob)
                                )
                                raptor_count += 1
                    except Exception as e:
                        logger.warning(f"RAPTOR collection summary error: {e}")

            conn.commit()
            logger.info(f"RAPTOR summaries complete: {raptor_count} summaries generated")
        finally:
            conn.close()

        return raptor_count

    # =========================================================================
    # Step 2f (Sub-step F): GraphRAGコミュニティ検出・要約
    # =========================================================================

    def execute_graphrag_communities(self, model: str = KG_MODEL,
                                      progress_callback: Optional[Callable] = None) -> int:
        """GraphRAGコミュニティ検出: semantic_nodesからコミュニティを検出し要約"""
        import requests

        conn = self._get_conn()
        community_count = 0

        try:
            # 有効なノードを取得
            nodes = conn.execute(
                "SELECT id, entity, attribute, value FROM semantic_nodes "
                "WHERE valid_to IS NULL"
            ).fetchall()

            if not nodes:
                logger.info("GraphRAG: No semantic nodes found, skipping community detection")
                if progress_callback:
                    progress_callback("GraphRAGコミュニティ", 1, 1, "ノードなし")
                return 0

            # エッジを取得
            edges = conn.execute(
                "SELECT se.source_node_id, se.target_node_id, se.relation, "
                "sn1.entity as source_entity, sn2.entity as target_entity "
                "FROM semantic_edges se "
                "JOIN semantic_nodes sn1 ON se.source_node_id = sn1.id "
                "JOIN semantic_nodes sn2 ON se.target_node_id = sn2.id "
                "WHERE se.valid_to IS NULL"
            ).fetchall()

            # エンティティの隣接リストを構築
            adjacency = {}
            for edge in edges:
                src = edge["source_entity"]
                tgt = edge["target_entity"]
                adjacency.setdefault(src, set()).add(tgt)
                adjacency.setdefault(tgt, set()).add(src)

            # 連結成分ベースのコミュニティ検出
            visited = set()
            communities = []

            for node in nodes:
                entity = node["entity"]
                if entity in visited:
                    continue

                # BFS で連結成分を探索
                community = []
                queue = [entity]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    community.append(current)
                    for neighbor in adjacency.get(current, []):
                        if neighbor not in visited:
                            queue.append(neighbor)

                if len(community) >= 2:  # 2ノード以上のコミュニティのみ
                    communities.append(community)

            logger.info(f"GraphRAG: Found {len(communities)} communities from {len(nodes)} nodes")

            # 各コミュニティの要約を生成
            for idx, community in enumerate(communities):
                if self._cancelled:
                    break

                # コミュニティのノード情報を収集
                entity_details = []
                for entity_name in community[:20]:  # 最大20エンティティ
                    row = conn.execute(
                        "SELECT entity, attribute, value FROM semantic_nodes "
                        "WHERE entity = ? AND valid_to IS NULL LIMIT 3",
                        (entity_name,)
                    ).fetchall()
                    for r in row:
                        entity_details.append(
                            f"- {r['entity']}: {r['attribute']} = {r['value']}"
                        )

                if entity_details:
                    prompt = (
                        "以下の知識グラフコミュニティの要約を3文で生成してください。\n\n"
                        f"エンティティ数: {len(community)}\n"
                        f"詳細:\n" + "\n".join(entity_details[:30]) + "\n\n"
                        "出力（日本語、3文のみ）:"
                    )
                    try:
                        url = f"{self.ollama_host}/api/generate"
                        payload = {
                            "model": _get_rag_ctrl_model(),
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.1, "num_predict": 256},
                        }
                        resp = requests.post(url, json=payload, timeout=60)
                        if resp.status_code == 200:
                            summary = resp.json().get("response", "").strip()
                            if summary:
                                emb_blob = self._get_embedding_sync(summary)
                                conn.execute(
                                    "INSERT INTO document_summaries "
                                    "(source_file, level, summary, summary_embedding, entity_count) "
                                    "VALUES (?, 'collection', ?, ?, ?)",
                                    (f"_community_{idx}", summary, emb_blob,
                                     len(community))
                                )
                                community_count += 1
                    except Exception as e:
                        logger.warning(f"GraphRAG community {idx} summary error: {e}")

                if progress_callback:
                    progress_callback("GraphRAGコミュニティ", idx + 1, len(communities),
                                      f"コミュニティ{idx}")

            conn.commit()
            logger.info(f"GraphRAG communities complete: {community_count} summaries generated")
        finally:
            conn.close()

        return community_count

    # =========================================================================
    # Step 2g (Sub-step G): 要約Embedding生成・永続化
    # =========================================================================

    def execute_summary_embeddings(self,
                                     progress_callback: Optional[Callable] = None) -> int:
        """要約のうちEmbedding未生成のものにqwen3-embedding:4bでEmbeddingを付与"""
        conn = self._get_conn()
        updated_count = 0

        try:
            # Embedding未生成の要約を取得
            rows = conn.execute(
                "SELECT id, summary FROM document_summaries "
                "WHERE summary_embedding IS NULL"
            ).fetchall()

            if not rows:
                logger.info("Summary embeddings: all summaries already have embeddings")
                if progress_callback:
                    progress_callback("要約Embedding", 1, 1, "完了済み")
                return 0

            for i, row in enumerate(rows):
                if self._cancelled:
                    break

                emb_blob = self._get_embedding_sync(row["summary"])
                if emb_blob:
                    conn.execute(
                        "UPDATE document_summaries SET summary_embedding = ? WHERE id = ?",
                        (emb_blob, row["id"])
                    )
                    updated_count += 1

                if progress_callback:
                    progress_callback("要約Embedding生成", i + 1, len(rows),
                                      f"要約#{row['id']}")

            conn.commit()
            logger.info(f"Summary embeddings complete: {updated_count}/{len(rows)} updated")
        finally:
            conn.close()

        return updated_count

    # =========================================================================
    # Step 2h (Sub-step H): 検証クエリ品質チェック
    # =========================================================================

    def execute_verification_queries(self, chunks: List[Chunk],
                                       progress_callback: Optional[Callable] = None) -> dict:
        """ministral-3:8bで検証クエリを生成し、RAG検索品質をセルフチェック"""
        import requests
        import random
        try:
            from ..memory.model_config import get_quality_llm
            quality_llm = get_quality_llm()
        except Exception:
            quality_llm = CONTROL_MODEL  # フォールバック

        QUERY_GEN_PROMPT = """以下のテキストの内容について、検索テストに使える質問を1つ生成してください。
質問のみ出力してください（日本語）。

テキスト:
{chunk_text}"""

        # サンプルチャンクを選択（最大10件）
        sample_size = min(10, len(chunks))
        sample_chunks = random.sample(chunks, sample_size) if len(chunks) > sample_size else chunks

        scores = []
        for i, chunk in enumerate(sample_chunks):
            if self._cancelled:
                break

            try:
                # 1. 検証クエリ生成
                prompt = QUERY_GEN_PROMPT.format(chunk_text=chunk.content[:500])
                url = f"{self.ollama_host}/api/generate"
                payload = {
                    "model": quality_llm,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 128},
                }
                resp = requests.post(url, json=payload, timeout=30)

                if resp.status_code != 200:
                    continue

                query = resp.json().get("response", "").strip()
                if not query:
                    continue

                # 2. クエリのEmbeddingを生成
                query_emb = self._get_embedding_sync(query)
                if not query_emb:
                    continue

                # 3. DB内のチャンクEmbeddingとコサイン類似度で検索
                conn = self._get_conn()
                try:
                    db_chunks = conn.execute(
                        "SELECT source_file, chunk_index, chunk_embedding "
                        "FROM documents WHERE chunk_embedding IS NOT NULL"
                    ).fetchall()

                    if not db_chunks:
                        continue

                    # 最も類似度の高いチャンクを見つける
                    best_score = 0.0
                    best_file = ""
                    query_vec = struct.unpack(f'{len(query_emb)//4}f', query_emb)

                    for db_chunk in db_chunks:
                        if db_chunk["chunk_embedding"]:
                            try:
                                db_vec = struct.unpack(
                                    f'{len(db_chunk["chunk_embedding"])//4}f',
                                    db_chunk["chunk_embedding"]
                                )
                                # コサイン類似度
                                dot = sum(a * b for a, b in zip(query_vec, db_vec))
                                norm_q = sum(a * a for a in query_vec) ** 0.5
                                norm_d = sum(a * a for a in db_vec) ** 0.5
                                if norm_q > 0 and norm_d > 0:
                                    sim = dot / (norm_q * norm_d)
                                    if sim > best_score:
                                        best_score = sim
                                        best_file = db_chunk["source_file"]
                            except Exception:
                                pass

                    # 元チャンクのファイルが最上位に来たら高スコア
                    hit = 1 if best_file == chunk.source_file else 0
                    score = int(best_score * 100)
                    scores.append({"query": query[:100], "score": score,
                                   "hit": hit, "best_file": best_file})

                finally:
                    conn.close()

            except Exception as e:
                logger.warning(f"Verification query error for chunk {i}: {e}")

            if progress_callback:
                progress_callback("検証クエリ品質チェック", i + 1, len(sample_chunks),
                                  chunk.source_file)

        avg_score = sum(s["score"] for s in scores) // max(len(scores), 1) if scores else 0
        hit_rate = sum(s["hit"] for s in scores) / max(len(scores), 1) if scores else 0

        logger.info(
            f"Verification queries complete: {len(scores)} queries, "
            f"avg_score={avg_score}, hit_rate={hit_rate:.2f}"
        )

        return {
            "avg_score": avg_score,
            "hit_rate": round(hit_rate, 2),
            "query_count": len(scores),
            "details": scores,
        }

    # =========================================================================
    # 旧互換: execute_multi_level_summary (RAPTOR統合前の互換メソッド)
    # =========================================================================

    def execute_multi_level_summary(self, chunks: List[Chunk],
                                      progress_callback: Optional[Callable] = None):
        """旧互換: execute_raptor_summaries へ委譲"""
        return self.execute_raptor_summaries(chunks, progress_callback=progress_callback)

    # =========================================================================
    # DB保存
    # =========================================================================

    def save_chunks_to_db(self, chunks: List[Chunk]):
        """チャンクをDBに保存"""
        conn = self._get_conn()
        try:
            for chunk in chunks:
                tags_json = json.dumps(chunk.keywords or [], ensure_ascii=False)
                metadata_json = json.dumps(chunk.metadata, ensure_ascii=False)
                conn.execute("""
                    INSERT INTO documents
                    (source_file, source_hash, title, chunk_index, content,
                     chunk_embedding, metadata, category, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk.source_file,
                    chunk.metadata.get("source_hash", ""),
                    chunk.source_file,  # titleはファイル名
                    chunk.chunk_index,
                    chunk.content,
                    chunk.embedding,
                    metadata_json,
                    chunk.metadata.get("category", "reference"),
                    tags_json,
                ))
            conn.commit()
            logger.info(f"Saved {len(chunks)} chunks to database")
        finally:
            conn.close()

    def clear_file_chunks(self, source_file: str):
        """特定ファイルのチャンクをクリア（再構築用）"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM documents WHERE source_file = ?", (source_file,))
            conn.execute("DELETE FROM document_summaries WHERE source_file = ?", (source_file,))
            conn.commit()
        finally:
            conn.close()

    def clear_all_chunks(self):
        """全チャンクをクリア"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM documents")
            conn.execute("DELETE FROM document_summaries")
            conn.execute("DELETE FROM document_semantic_links")
            conn.commit()
            logger.info("All document chunks cleared")
        finally:
            conn.close()

    # =========================================================================
    # ヘルパー
    # =========================================================================

    def _parse_extraction(self, raw: str) -> dict:
        """要約抽出結果をパース"""
        try:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return {"summary": "", "keywords": [], "entities": []}

    def _parse_kg(self, raw: str) -> dict:
        """KG抽出結果をパース"""
        try:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            logger.debug(f"KG JSON parse failed, raw response: {raw[:300]}")
        return {"nodes": [], "edges": []}

    def _store_kg_data(self, kg_data: dict, chunk: Chunk) -> tuple:
        """KGデータをsemantic_nodesに保存 (P1-2: document_semantic_links連携付き)

        Returns:
            tuple: (nodes_added, edges_added)
        """
        conn = self._get_conn()
        nodes_added = 0
        edges_added = 0
        now = datetime.now().isoformat()

        # P1-2: ドキュメントIDを取得
        doc_row = conn.execute(
            "SELECT id FROM documents WHERE source_file = ? AND chunk_index = ? LIMIT 1",
            (chunk.source_file, chunk.chunk_index)
        ).fetchone()
        doc_id = doc_row["id"] if doc_row else None

        try:
            for node in kg_data.get("nodes", []):
                entity = node.get("entity", "")
                attribute = node.get("attribute", "")
                value = node.get("value", "")
                if not entity or not value:
                    continue

                # Embeddingを生成
                emb_blob = self._get_embedding_sync(f"{entity} {attribute} {value}")

                try:
                    # 既存ノードを期間終了
                    conn.execute(
                        "UPDATE semantic_nodes SET valid_to = ? "
                        "WHERE entity = ? AND attribute = ? AND valid_to IS NULL",
                        (now, entity, attribute)
                    )
                    # 新規追加
                    cursor = conn.execute(
                        "INSERT INTO semantic_nodes "
                        "(entity, attribute, value, value_embedding, confidence, "
                        "source_session, valid_from) "
                        "VALUES (?, ?, ?, ?, 0.8, ?, ?)",
                        (entity, attribute, value, emb_blob,
                         f"rag_{chunk.source_file}", now)
                    )
                    node_id = cursor.lastrowid
                    nodes_added += 1

                    # P1-2: document_semantic_links に紐付けを保存
                    if doc_id and node_id:
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO document_semantic_links "
                                "(document_id, semantic_node_id, link_type, confidence) "
                                "VALUES (?, ?, 'extracted', 1.0)",
                                (doc_id, node_id)
                            )
                        except Exception as e:
                            logger.debug(f"document_semantic_links insert error: {e}")

                except Exception as e:
                    logger.debug(f"KG node insert error: {e}")

            # エッジ
            for edge in kg_data.get("edges", []):
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                rel = edge.get("relation", "related_to")
                if not src or not tgt:
                    continue

                try:
                    src_row = conn.execute(
                        "SELECT id FROM semantic_nodes WHERE entity = ? AND valid_to IS NULL LIMIT 1",
                        (src,)
                    ).fetchone()
                    tgt_row = conn.execute(
                        "SELECT id FROM semantic_nodes WHERE entity = ? AND valid_to IS NULL LIMIT 1",
                        (tgt,)
                    ).fetchone()
                    if src_row and tgt_row:
                        conn.execute(
                            "INSERT OR IGNORE INTO semantic_edges "
                            "(source_node_id, target_node_id, relation, weight, valid_from) "
                            "VALUES (?, ?, ?, 1.0, ?)",
                            (src_row["id"], tgt_row["id"], rel, now)
                        )
                        edges_added += 1
                except Exception:
                    pass

            conn.commit()
        finally:
            conn.close()

        return (nodes_added, edges_added)

    def _get_embedding_sync(self, text: str) -> Optional[bytes]:
        """同期Embedding取得"""
        import requests
        try:
            from ..memory.model_config import get_embedding_model
            _embedding_model = get_embedding_model()
        except Exception:
            _embedding_model = EMBEDDING_MODEL  # フォールバック
        try:
            url = f"{self.ollama_host}/api/embed"
            payload = {"model": _embedding_model, "input": text}
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if embeddings and len(embeddings) > 0:
                    return _embedding_to_blob(embeddings[0])
        except Exception:
            pass
        return None
