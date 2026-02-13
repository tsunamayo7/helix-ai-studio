"""
Helix AI Studio - RAG Planner (v8.5.0)
Step 1: Claude Opus 4.6 にRAG構築プランを策定させる
"""

import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from .document_chunker import DocumentChunker
from ..utils.constants import SUPPORTED_DOC_EXTENSIONS

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """あなたはHelix AI StudioのRAG構築プランナーです。
ユーザーが提供した情報収集フォルダ内のファイルを分析し、
最適なRAG構築プランをJSON形式で出力してください。

## 入力情報
- ファイル一覧（ファイル名、サイズ、拡張子、先頭プレビュー）
- 既存RAGの統計（チャンク数、Semantic Node数、最終構築日時）
- ユーザー指定の実行時間上限

## 出力JSON仕様
厳密に以下のJSON形式のみ出力してください（説明文不要）:
{
  "plan_id": "UUID文字列",
  "analysis": {
    "total_files": 整数,
    "total_size_kb": 小数,
    "file_classifications": [
      {
        "file": "ファイル名",
        "category": "research|technical|reference|meeting|other",
        "priority": "high|medium|low",
        "estimated_chunks": 整数,
        "chunk_strategy": "fixed|semantic|sentence",
        "summary_depth": "detailed|standard|brief",
        "key_entities_hint": ["キーワード1", "キーワード2"]
      }
    ]
  },
  "execution_plan": {
    "steps": [
      {
        "step_id": 整数,
        "name": "ステップ名",
        "target_files": ["all"] または ["ファイル名"],
        "model": "direct|qwen3-embedding:4b|ministral-3:8b|command-a:111b",
        "estimated_minutes": 小数,
        "gpu": 0または1
      }
    ],
    "total_estimated_minutes": 小数,
    "parallel_safe": false
  },
  "verification_criteria": {
    "min_chunk_coverage": 0.95,
    "min_embedding_count": 整数,
    "expected_entity_count_range": [最小, 最大],
    "sample_query_tests": ["テストクエリ1", "テストクエリ2"]
  },
  "summary": "プラン全体の概要を日本語2-3文で記述。どのようなファイル群を処理し、各ファイルの特性（技術仕様/履歴/設計書等）に応じてどのような処理戦略を採用するかを簡潔に説明すること。"
}"""


class RAGPlanner:
    """Claude Opus 4.6 によるRAG構築プラン策定"""

    def __init__(self, claude_model: str = "claude-opus-4-6"):
        self.claude_model = claude_model
        self.chunker = DocumentChunker()

    def create_plan(self, folder_path: str, time_limit_minutes: int,
                    existing_stats: Optional[dict] = None,
                    selected_files: Optional[list] = None) -> dict:
        """
        Claude Opus 4.6 にRAG構築プランを策定させる

        Args:
            folder_path: 情報収集フォルダパス
            time_limit_minutes: 実行時間上限（分）
            existing_stats: 既存RAG統計（任意）
            selected_files: 選択されたファイル名リスト（Noneの場合は全ファイル）

        Returns:
            プランJSON dict
        """
        # ファイル一覧と先頭プレビューを収集
        file_previews = self._collect_file_previews(folder_path)

        # 選択ファイルフィルタリング
        if selected_files:
            file_previews = [f for f in file_previews if f["file"] in selected_files]

        if not file_previews:
            logger.warning("No files found in information folder")
            return self._create_empty_plan()

        prompt = self._build_prompt(file_previews, existing_stats or {},
                                     time_limit_minutes)

        try:
            result = self._call_claude_cli(prompt)
            plan = self._parse_plan(result)
            logger.info(f"RAG plan created: {plan.get('plan_id', 'unknown')}")
            return plan
        except Exception as e:
            logger.error(f"RAG plan creation failed: {e}")
            logger.warning("Using fallback default plan due to Claude CLI failure")
            # フォールバック: デフォルトプランを生成
            return self._create_default_plan(file_previews, time_limit_minutes)

    def _collect_file_previews(self, folder_path: str, max_preview: int = 500) -> list:
        """ファイル一覧と先頭プレビューを収集"""
        previews = []
        folder = Path(folder_path)

        if not folder.exists():
            return previews

        for f in sorted(folder.rglob('*')):
            if f.is_file() and f.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
                try:
                    preview = DocumentChunker.get_file_preview(str(f), max_preview)
                    previews.append({
                        "file": f.name,
                        "size_kb": round(f.stat().st_size / 1024, 1),
                        "extension": f.suffix.lower(),
                        "preview": preview,
                    })
                except Exception as e:
                    logger.warning(f"Failed to preview {f.name}: {e}")

        return previews

    def _build_prompt(self, file_previews: list, existing_stats: dict,
                      time_limit_minutes: int) -> str:
        """Claude向けプロンプトを構築"""
        return f"""以下のファイルからRAG構築プランを作成してください。

## ファイル一覧
{json.dumps(file_previews, ensure_ascii=False, indent=2)}

## 既存RAG統計
{json.dumps(existing_stats, ensure_ascii=False, indent=2)}

## 制約条件
- 実行時間上限: {time_limit_minutes}分
- 利用可能モデル:
  - 常駐 GPU0: ministral-3:8b (6GB), qwen3-embedding:4b (2.5GB)
  - オンデマンド GPU1: command-a:111b (67GB)
- Embedding次元: 768 (qwen3-embedding:4b)

JSONのみ出力してください。"""

    def _call_claude_cli(self, prompt: str) -> str:
        """Claude CLIを呼び出す"""
        # PLAN_SYSTEM_PROMPTをプロンプト本文に結合
        # (Claude CLIに --system-prompt フラグが存在しないため)
        full_prompt = PLAN_SYSTEM_PROMPT + "\n\n" + prompt
        cmd = [
            "claude", "-p", full_prompt,
            "--model", self.claude_model,
            "--output-format", "text",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分タイムアウト
                encoding='utf-8',
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
            raise RuntimeError("Claude CLIが見つかりません。claudeコマンドがPATHに設定されているか確認してください")
        except UnicodeDecodeError as e:
            logger.error(f"Claude CLI response encoding error: {e}")
            raise RuntimeError(f"Claude CLI応答のエンコーディングエラー: {e}")

    def _parse_plan(self, raw: str) -> dict:
        """CLIの出力からJSONを抽出"""
        # JSON部分を抽出
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = raw[start:end]
            plan = json.loads(json_str)
            # plan_idが無ければ付与
            if "plan_id" not in plan:
                plan["plan_id"] = str(uuid.uuid4())
            return plan
        raise ValueError("No valid JSON found in Claude response")

    def _create_empty_plan(self) -> dict:
        """空のプラン"""
        return {
            "plan_id": str(uuid.uuid4()),
            "analysis": {"total_files": 0, "total_size_kb": 0, "file_classifications": []},
            "execution_plan": {"steps": [], "total_estimated_minutes": 0, "parallel_safe": False},
            "verification_criteria": {},
        }

    def _create_default_plan(self, file_previews: list,
                              time_limit_minutes: int) -> dict:
        """デフォルトプラン（Claude接続不可時のフォールバック）"""
        plan_id = str(uuid.uuid4())
        total_size_kb = sum(f.get("size_kb", 0) for f in file_previews)
        estimated_chunks = max(int(total_size_kb * 1024 / 512), 1)

        classifications = []
        for f in file_previews:
            est_chunks = max(int(f.get("size_kb", 1) * 1024 / 512), 1)
            classifications.append({
                "file": f["file"],
                "category": "reference",
                "priority": "medium",
                "estimated_chunks": est_chunks,
                "chunk_strategy": "semantic",
                "summary_depth": "standard",
                "key_entities_hint": [],
            })

        steps = [
            {"step_id": 1, "name": "チャンキング", "target_files": ["all"],
             "model": "direct", "estimated_minutes": max(total_size_kb * 0.01, 0.5), "gpu": -1},
            {"step_id": 2, "name": "Embedding生成", "target_files": ["all"],
             "model": "qwen3-embedding:4b", "estimated_minutes": estimated_chunks * 0.02, "gpu": 0},
            {"step_id": 3, "name": "チャンク要約・キーワード抽出", "target_files": ["all"],
             "model": "ministral-3:8b", "estimated_minutes": estimated_chunks * 0.15, "gpu": 0},
            {"step_id": 4, "name": "Semantic Node/Edge生成", "target_files": ["all"],
             "model": "command-a:111b", "estimated_minutes": estimated_chunks * 0.5 + 2.0, "gpu": 1},
            {"step_id": 5, "name": "多段要約生成", "target_files": ["all"],
             "model": "ministral-3:8b", "estimated_minutes": len(file_previews) * 0.5 + 1.0, "gpu": 0},
        ]

        total_est = sum(s["estimated_minutes"] for s in steps)

        return {
            "plan_id": plan_id,
            "fallback": True,
            "summary": "デフォルトプランです。Claude接続に失敗したため、全ファイルを標準設定（reference/medium）で処理します。",
            "analysis": {
                "total_files": len(file_previews),
                "total_size_kb": total_size_kb,
                "file_classifications": classifications,
            },
            "execution_plan": {
                "steps": steps,
                "total_estimated_minutes": total_est,
                "parallel_safe": False,
            },
            "verification_criteria": {
                "min_chunk_coverage": 0.95,
                "min_embedding_count": int(estimated_chunks * 0.9),
                "expected_entity_count_range": [max(estimated_chunks // 3, 5),
                                                 estimated_chunks * 2],
                "sample_query_tests": [],
            },
        }
