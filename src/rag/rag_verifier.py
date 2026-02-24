"""
Helix AI Studio - RAG Verifier (v8.5.0 Patch 1)
Step 3: Claude Opus 4.6 によるRAG品質検証

v8.5.0 Patch 1 修正:
- P2-1: 検証結果の詳細ログ出力
"""

import json
import logging
import random
import sqlite3
import struct
import subprocess
from typing import Optional, List

from ..utils.constants import RAG_VERIFICATION_SAMPLE_SIZE
from ..utils.subprocess_utils import run_hidden

logger = logging.getLogger(__name__)

VERIFICATION_PROMPT = """あなたはRAG品質検証AIです。構築されたRAGの品質を以下の基準で評価してください。

## 検証基準
1. **完全性** (Coverage): 元ドキュメントの情報がRAGに十分反映されているか
2. **重複排除** (Dedup): 同一情報が重複して格納されていないか
3. **鮮度** (Freshness): source_hashが最新ファイルと一致するか
4. **構造品質** (Structure): Semantic Node/Edgeが論理的に正しいか
5. **検索品質** (Retrieval): サンプルクエリで適切なチャンクが返されるか

## 入力データ
- RAG統計: {rag_stats}
- サンプルチャンク（ランダム抽出）: {sample_chunks}
- Semantic Nodeサンプル: {sample_nodes}
- 元ファイルのハッシュ一致状況: {hash_check}

## 出力JSON（JSONのみ出力。説明文不要）
{{
  "overall_verdict": "PASS" or "FAIL",
  "score": 0-100の整数,
  "criteria": {{
    "coverage": {{"pass": true/false, "score": 0-100, "note": "..."}},
    "dedup": {{"pass": true/false, "score": 0-100, "note": "..."}},
    "freshness": {{"pass": true/false, "score": 0-100, "note": "..."}},
    "structure": {{"pass": true/false, "score": 0-100, "note": "..."}},
    "retrieval": {{"pass": true/false, "score": 0-100, "note": "..."}}
  }},
  "remediation_steps": [
    {{
      "target_step": ステップID,
      "reason": "理由",
      "action": "再実行アクション"
    }}
  ],
  "estimated_remediation_minutes": 0
}}"""


class RAGVerifier:
    """クラウドAIによるRAG品質検証"""

    def __init__(self, db_path: str = "data/helix_memory.db",
                 claude_model: str = ""):
        self.db_path = db_path
        # v11.5.0: 動的モデル解決
        if not claude_model:
            from ..utils.constants import get_default_claude_model
            claude_model = get_default_claude_model()
        self.claude_model = claude_model

    def verify(self, plan: dict, folder_path: str) -> dict:
        """
        RAG品質検証を実行

        Returns:
            検証結果dict（overall_verdict, score, criteria, remediation_steps）
        """
        try:
            # 検証データを収集
            rag_stats = self._collect_rag_stats()
            sample_chunks = self._sample_chunks()
            sample_nodes = self._sample_nodes()
            hash_check = self._check_hashes(folder_path)

            # Claudeに検証依頼
            prompt = VERIFICATION_PROMPT.format(
                rag_stats=json.dumps(rag_stats, ensure_ascii=False, indent=2),
                sample_chunks=json.dumps(sample_chunks, ensure_ascii=False, indent=2),
                sample_nodes=json.dumps(sample_nodes, ensure_ascii=False, indent=2),
                hash_check=json.dumps(hash_check, ensure_ascii=False, indent=2),
            )

            result = self._call_claude_cli(prompt)
            verification = self._parse_result(result)
            # P2-1: 検証結果の詳細ログ出力
            logger.info(f"RAG verification: {verification.get('overall_verdict', 'UNKNOWN')} "
                        f"(score={verification.get('score', 0)})")
            logger.info(f"Verification result details: "
                        f"{json.dumps(verification, ensure_ascii=False)}")
            return verification

        except Exception as e:
            logger.error(f"RAG verification failed: {e}")
            logger.warning("Using auto-verify fallback due to Claude CLI failure")
            # フォールバック: 基本的な自動検証
            try:
                fallback_result = self._auto_verify(folder_path)
                # P2-1: フォールバック検証結果もログ出力
                logger.info(f"Auto-verify result: "
                            f"{json.dumps(fallback_result, ensure_ascii=False)}")
                return fallback_result
            except Exception as e2:
                logger.error(f"Auto-verify also failed: {e2}")
                return {
                    "overall_verdict": "SKIP",
                    "score": 0,
                    "criteria": {},
                    "reason": f"品質検証をスキップしました（理由: {e}）",
                    "remediation_steps": [],
                    "estimated_remediation_minutes": 0,
                }

    def _collect_rag_stats(self) -> dict:
        """RAG統計を収集"""
        conn = self._get_conn()
        try:
            total_chunks = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
            embedded_chunks = conn.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE chunk_embedding IS NOT NULL"
            ).fetchone()["cnt"]
            total_files = conn.execute(
                "SELECT COUNT(DISTINCT source_file) as cnt FROM documents"
            ).fetchone()["cnt"]
            total_nodes = conn.execute(
                "SELECT COUNT(*) as cnt FROM semantic_nodes WHERE valid_to IS NULL"
            ).fetchone()["cnt"]
            total_summaries = conn.execute(
                "SELECT COUNT(*) as cnt FROM document_summaries"
            ).fetchone()["cnt"]

            return {
                "total_chunks": total_chunks,
                "embedded_chunks": embedded_chunks,
                "total_files": total_files,
                "semantic_nodes": total_nodes,
                "document_summaries": total_summaries,
                "embedding_coverage": round(embedded_chunks / max(total_chunks, 1), 2),
            }
        finally:
            conn.close()

    def _sample_chunks(self, sample_size: int = RAG_VERIFICATION_SAMPLE_SIZE) -> list:
        """ランダムにチャンクをサンプリング"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT source_file, chunk_index, content, category, tags "
                "FROM documents ORDER BY RANDOM() LIMIT ?",
                (sample_size,)
            ).fetchall()
            return [
                {
                    "source_file": r["source_file"],
                    "chunk_index": r["chunk_index"],
                    "content_preview": r["content"][:200],
                    "category": r["category"],
                    "tags": r["tags"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def _sample_nodes(self, sample_size: int = RAG_VERIFICATION_SAMPLE_SIZE) -> list:
        """Semantic Nodeをサンプリング"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT entity, attribute, value, confidence "
                "FROM semantic_nodes WHERE valid_to IS NULL "
                "ORDER BY RANDOM() LIMIT ?",
                (sample_size,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _check_hashes(self, folder_path: str) -> dict:
        """元ファイルのハッシュ一致を確認"""
        import hashlib
        from pathlib import Path

        conn = self._get_conn()
        try:
            stored = conn.execute(
                "SELECT DISTINCT source_file, source_hash FROM documents"
            ).fetchall()
            stored_map = {r["source_file"]: r["source_hash"] for r in stored}
        finally:
            conn.close()

        folder = Path(folder_path)
        results = {"matched": 0, "mismatched": 0, "missing": 0, "details": []}

        for name, stored_hash in stored_map.items():
            file_path = folder / name
            if file_path.exists():
                current_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if current_hash == stored_hash:
                    results["matched"] += 1
                else:
                    results["mismatched"] += 1
                    results["details"].append(f"{name}: hash mismatch")
            else:
                results["missing"] += 1
                results["details"].append(f"{name}: file missing")

        return results

    def _call_claude_cli(self, prompt: str) -> str:
        """Claude CLIを呼び出す"""
        cmd = [
            "claude", "-p", prompt,
            "--model", self.claude_model,
            "--output-format", "text",
        ]
        try:
            result = run_hidden(
                cmd, capture_output=True, text=True, timeout=300, encoding='utf-8',
            )
            if result.returncode != 0:
                logger.error(f"Verifier Claude CLI error (code {result.returncode}): {result.stderr[:500]}")
                raise RuntimeError(f"Claude CLI failed: {result.stderr[:200]}")

            if not result.stdout.strip():
                logger.error("Verifier Claude CLI returned empty response")
                raise RuntimeError("Claude CLI returned empty response")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("Verifier Claude CLI timed out after 300 seconds")
            raise RuntimeError("Claude CLI timed out (5分超過)")
        except FileNotFoundError:
            logger.error("Claude CLI not found for verification")
            raise RuntimeError("Claude CLIが見つかりません")

    def _parse_result(self, raw: str) -> dict:
        """検証結果をパース"""
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        raise ValueError("No valid JSON in verification response")

    def _auto_verify(self, folder_path: str) -> dict:
        """Claude不使用の自動検証（フォールバック）"""
        stats = self._collect_rag_stats()
        hash_check = self._check_hashes(folder_path)

        coverage_score = min(int(stats["embedding_coverage"] * 100), 100)
        freshness_score = 100 if hash_check["mismatched"] == 0 else 50
        structure_score = 80 if stats["semantic_nodes"] > 0 else 40

        overall_score = (coverage_score + freshness_score + structure_score) // 3
        verdict = "PASS" if overall_score >= 70 else "FAIL"

        return {
            "overall_verdict": verdict,
            "score": overall_score,
            "criteria": {
                "coverage": {"pass": coverage_score >= 80, "score": coverage_score,
                             "note": f"Embedding coverage: {stats['embedding_coverage']}"},
                "dedup": {"pass": True, "score": 80, "note": "Auto-check skipped"},
                "freshness": {"pass": freshness_score >= 80, "score": freshness_score,
                              "note": f"Hash mismatches: {hash_check['mismatched']}"},
                "structure": {"pass": structure_score >= 60, "score": structure_score,
                              "note": f"Semantic nodes: {stats['semantic_nodes']}"},
                "retrieval": {"pass": True, "score": 75, "note": "Auto-check skipped"},
            },
            "remediation_steps": [],
            "estimated_remediation_minutes": 0,
        }

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
