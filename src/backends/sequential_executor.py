"""
Phase 2: ローカルLLM順次実行エンジン v7.0.0

Ollama APIで1モデルずつロード→実行→アンロードの順次実行を行う。
RTX PRO 6000 (96GB) で大型モデル(67-80GB)を1つずつ動かすため、
並列ではなく順次実行が必須。

v7.0.0: parallel_pool.py を置き換え
  - 並列実行（ThreadPoolExecutor）→ 順次実行に変更
  - モデルのロード待機（/api/tags でロード状態確認）
  - 各タスクの結果を data/phase2/task_{order}_{model}.txt に保存
  - chain-of-thoughtフィルタリングを継承（v6.3.0のfilter_chain_of_thought()）
"""

import requests
import time
import re
import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_API_BASE = "http://localhost:11434/api"

# モデルロード待機の設定
MODEL_LOAD_TIMEOUT = 120  # モデルロードの最大待機秒数
MODEL_LOAD_CHECK_INTERVAL = 2  # ロード状態チェック間隔（秒）


def filter_chain_of_thought(text: str) -> str:
    """
    ローカルLLMの出力からchain-of-thought（思考過程）を除去する。

    nemotron等のモデルが内部推論過程を漏洩する問題への対策。
    例: "We need to comply: answer in Japanese, m..."
        "Let me think about this..."

    v6.3.0から継承、v7.0.0で維持。

    Args:
        text: LLMの生の出力テキスト

    Returns:
        思考過程を除去したテキスト
    """
    if not text:
        return ""

    lines = text.split("\n")
    filtered_lines = []

    # 思考過程を示すパターン（英語・日本語）
    skip_patterns = [
        # 英語の思考過程パターン
        r"^(Let me|I should|I need to|We should|We need to|Hmm|OK so|Alright)",
        r"^(Let's|I'll|I'm going to|First,? I)",
        r"^(Wait|Actually|Oh|Now)",
        r"^(Thinking|To answer|To respond)",
        # 内部制約への言及パターン
        r"must ans\.\.\.",
        r"follow output rules",
        r"respond in Japanese",
        r"Provide format\?",
        r"output nothing\?",
        r"within constraints",
        r"We need to comply",
        r"comply with",
        r"answer in Japanese",
        r"should respond",
        r"maybe stating",
        r"stating no results",
        # 日本語の思考過程パターン
        r"^(考え|思考|まず|では|えーと|うーん)",
        r"^(検討|分析|確認)",
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered_lines.append(line)
            continue

        is_cot = False
        for pattern in skip_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                is_cot = True
                logger.debug(f"[CoT Filter] Removed line: {stripped[:50]}...")
                break

        if not is_cot:
            filtered_lines.append(line)

    result = "\n".join(filtered_lines).strip()

    # 空のバレットポイントのみの場合は空文字にする
    if re.match(r'^[\s•\-\*\n]+$', result):
        logger.debug("[CoT Filter] Removed empty bullet points")
        return ""

    return result


@dataclass
class SequentialTask:
    """順次実行タスク定義 v7.0.0"""
    category: str          # "coding" | "research" | "reasoning" | "vision" | "translation"
    model: str             # Ollamaモデル名（例: "devstral-2:123b"）
    prompt: str            # Claudeが生成した指示文
    expected_output: str   # 期待する出力形式の説明
    timeout: int = 300     # タイムアウト秒数
    order: int = 1         # 実行順序


@dataclass
class SequentialResult:
    """順次実行結果 v7.0.0"""
    category: str          # タスクカテゴリ
    model: str             # 使用したモデル名
    success: bool          # 実行成功/失敗
    response: str          # LLMの応答テキスト（失敗時はエラーメッセージ）
    elapsed: float         # 処理時間（秒）
    order: int = 1         # 実行順序
    original_prompt: str = ""  # 元のClaude生成指示文（Phase 3再利用用）
    expected_output: str = ""  # 期待する出力（Phase 3再利用用）


class SequentialExecutor:
    """
    ローカルLLMへの順次タスク実行エンジン v7.0.0

    Ollama APIで1モデルずつロード→実行→アンロードを行う。
    RTX PRO 6000 (96GB) で大型モデルを1つずつ動かす設計。
    """

    def __init__(self, ollama_base: str = OLLAMA_API_BASE):
        self.ollama_base = ollama_base

    def execute_task(self, task: SequentialTask) -> SequentialResult:
        """
        単一タスクを実行。

        1. モデルのロード状態を確認（必要なら待機）
        2. Ollama /api/generate で実行
        3. chain-of-thoughtフィルタリング適用
        4. 結果を返す

        Args:
            task: 実行するタスク

        Returns:
            実行結果
        """
        start = time.time()

        try:
            # モデルのロード確認
            self._wait_for_model_ready(task.model)

            # Ollama /api/generate で実行
            response = requests.post(
                f"{self.ollama_base}/generate",
                json={
                    "model": task.model,
                    "prompt": task.prompt,
                    "stream": False,
                    "keep_alive": "1m",  # 次のモデルロードのためすぐにアンロード可能
                },
                timeout=task.timeout,
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                raw_response = data.get("response", "")

                # chain-of-thoughtフィルタリング適用
                filtered_response = filter_chain_of_thought(raw_response)

                logger.info(
                    f"Phase 2 完了: {task.category} ({task.model}) "
                    f"{elapsed:.1f}秒, {len(filtered_response)}文字"
                )

                return SequentialResult(
                    category=task.category,
                    model=task.model,
                    success=True,
                    response=filtered_response,
                    elapsed=elapsed,
                    order=task.order,
                    original_prompt=task.prompt,
                    expected_output=task.expected_output,
                )
            else:
                return SequentialResult(
                    category=task.category,
                    model=task.model,
                    success=False,
                    response=f"HTTP {response.status_code}: {response.text[:200]}",
                    elapsed=elapsed,
                    order=task.order,
                    original_prompt=task.prompt,
                    expected_output=task.expected_output,
                )

        except requests.exceptions.Timeout:
            return SequentialResult(
                category=task.category,
                model=task.model,
                success=False,
                response=f"タイムアウト ({task.timeout}秒)",
                elapsed=time.time() - start,
                order=task.order,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )
        except requests.exceptions.ConnectionError:
            return SequentialResult(
                category=task.category,
                model=task.model,
                success=False,
                response="Ollama接続失敗。Ollamaが起動しているか確認してください。",
                elapsed=time.time() - start,
                order=task.order,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )
        except Exception as e:
            return SequentialResult(
                category=task.category,
                model=task.model,
                success=False,
                response=f"エラー: {str(e)}",
                elapsed=time.time() - start,
                order=task.order,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )

    def _wait_for_model_ready(self, model_name: str):
        """
        モデルがOllamaにロードされるまで待機。

        /api/tags でモデルの存在を確認。
        Ollamaは /api/generate 呼び出し時に自動ロードするが、
        大型モデルのロードには時間がかかるため事前確認する。
        """
        try:
            response = requests.get(
                f"{self.ollama_base}/tags",
                timeout=10,
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if model_name in model_names:
                    logger.debug(f"モデル確認済み: {model_name}")
                    return
                # モデル名の部分一致もチェック（タグなしの場合）
                for name in model_names:
                    if name.startswith(model_name.split(":")[0]):
                        logger.debug(f"モデル確認済み（部分一致）: {model_name} → {name}")
                        return

                logger.warning(f"モデル未検出: {model_name} (Ollamaが自動ロードします)")
        except Exception as e:
            logger.warning(f"モデル確認失敗: {e} (実行を続行します)")

    def check_ollama_connection(self) -> bool:
        """Ollamaサーバーへの接続をテスト"""
        try:
            response = requests.get(
                f"{self.ollama_base}/tags",
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        """利用可能なOllamaモデル一覧を取得"""
        try:
            response = requests.get(
                f"{self.ollama_base}/tags",
                timeout=10,
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m.get("name", "") for m in models]
        except Exception:
            pass
        return []
