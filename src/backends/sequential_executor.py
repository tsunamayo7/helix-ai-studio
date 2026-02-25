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


# v11.6.0: cloud_models.json から model_name → (provider, model_id) を動的解決
def _get_cloud_provider_for_model(model_name: str) -> str | None:
    """
    Phase 2 コンボに表示されているモデル名 (display name) から
    cloud_models.json の provider を返す。
    ローカルモデル（Ollama）の場合は None を返す。
    """
    try:
        import json
        from pathlib import Path
        path = Path("config/cloud_models.json")
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        for m in data.get("models", []):
            if m.get("name") == model_name or m.get("model_id") == model_name:
                return m.get("provider")
    except Exception:
        pass
    return None


def _resolve_cloud_model_id(model_name: str) -> str:
    """v11.6.0: display name から model_id を解決。見つからなければ model_name をそのまま返す。"""
    try:
        import json
        from pathlib import Path
        data = json.loads(Path("config/cloud_models.json").read_text(encoding="utf-8"))
        for m in data.get("models", []):
            if m.get("name") == model_name:
                return m.get("model_id", model_name)
    except Exception:
        pass
    return model_name

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

    # v10.0.0: Cloud AI モデル識別パターン
    CLOUD_AI_MODELS = {
        "GPT-5.3-Codex (CLI)": "codex",
        "Claude Sonnet 4.6 (CLI)": "claude-sonnet-4-6",
        "Claude Opus 4.6 (CLI)": "claude-opus-4-6",
    }

    def _is_cloud_model(self, model: str) -> bool:
        """v11.6.0: cloud_models.json の provider フィールドで動的判定"""
        # 後方互換: 旧ハードコードリスト（CLIモデル名形式）
        if model in self.CLOUD_AI_MODELS:
            return True
        # 動的判定: cloud_models.json に登録されていればクラウドモデル
        return _get_cloud_provider_for_model(model) is not None

    def _execute_cloud_task(self, task: SequentialTask) -> SequentialResult:
        """v11.6.0: 全クラウドプロバイダー対応 (anthropic_api/openai_api/google_api/*_cli)"""
        start = time.time()

        # 旧ハードコードリストで試みる（後方互換）
        model_key = self.CLOUD_AI_MODELS.get(task.model, "")

        # 旧リストにない場合は cloud_models.json から provider/model_id を取得
        provider = None
        model_id = task.model
        if not model_key:
            provider = _get_cloud_provider_for_model(task.model)
            model_id = _resolve_cloud_model_id(task.model)

        try:
            raw = ""

            # --- 旧ハードコード互換パス ---
            if model_key == "codex":
                from .codex_cli_backend import run_codex_cli
                raw = run_codex_cli(task.prompt, timeout=task.timeout)

            elif model_key.startswith("claude-"):
                from .claude_cli_backend import ClaudeCLIBackend
                from .base import BackendRequest
                cli = ClaudeCLIBackend(model=model_key, skip_permissions=True)
                req = BackendRequest(prompt=task.prompt, session_id=f"phase2_{task.category}")
                resp = cli.send(req)
                if not resp.success:
                    raise RuntimeError(resp.response_text)
                raw = resp.response_text

            # --- v11.6.0: 動的プロバイダーパス ---
            elif provider == "anthropic_api":
                from .claude_backend import ClaudeBackend
                from .base import BackendRequest
                backend = ClaudeBackend(model=model_id)
                req = BackendRequest(prompt=task.prompt, session_id=f"phase2_{task.category}")
                resp = backend.send(req)
                if not resp.success:
                    raise RuntimeError(resp.response_text)
                raw = resp.response_text

            elif provider == "anthropic_cli":
                from .claude_cli_backend import ClaudeCLIBackend
                from .base import BackendRequest
                cli = ClaudeCLIBackend(model=model_id, skip_permissions=True)
                req = BackendRequest(prompt=task.prompt, session_id=f"phase2_{task.category}")
                resp = cli.send(req)
                if not resp.success:
                    raise RuntimeError(resp.response_text)
                raw = resp.response_text

            elif provider == "openai_api":
                from .openai_api_backend import call_openai_api
                raw = call_openai_api(prompt=task.prompt, model_id=model_id)

            elif provider == "openai_cli":
                from .codex_cli_backend import run_codex_cli
                raw = run_codex_cli(task.prompt, timeout=task.timeout)

            elif provider == "google_api":
                from .google_api_backend import call_google_api
                raw = call_google_api(prompt=task.prompt, model_id=model_id)

            elif provider == "google_cli":
                import subprocess
                env = os.environ.copy()
                result = subprocess.run(
                    ["gemini", "-p", task.prompt, "--model", model_id, "--yolo"],
                    capture_output=True, text=True, timeout=task.timeout, env=env,
                )
                raw = result.stdout.strip()
                if result.returncode != 0 and not raw:
                    raise RuntimeError(result.stderr or f"Gemini CLI error code {result.returncode}")

            else:
                raise RuntimeError(f"Unknown cloud model or provider: {task.model} / {provider}")

            elapsed = time.time() - start
            filtered = filter_chain_of_thought(raw)
            logger.info(f"Phase 2 Cloud AI完了: {task.category} ({task.model}) "
                       f"{elapsed:.1f}秒, {len(filtered)}文字")
            return SequentialResult(
                category=task.category, model=task.model, success=True,
                response=filtered, elapsed=elapsed, order=task.order,
                original_prompt=task.prompt, expected_output=task.expected_output,
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"Phase 2 Cloud AI失敗: {task.category} ({task.model}): {e}")
            return SequentialResult(
                category=task.category, model=task.model, success=False,
                response=f"エラー: {str(e)}", elapsed=elapsed, order=task.order,
                original_prompt=task.prompt, expected_output=task.expected_output,
            )

    def execute_task(self, task: SequentialTask) -> SequentialResult:
        """
        単一タスクを実行。

        v10.0.0: Cloud AI (CLI) モデルの場合はCLIバックエンド経由で実行。
        それ以外はOllama APIで実行。

        1. モデルのロード状態を確認（必要なら待機）
        2. Ollama /api/generate で実行
        3. chain-of-thoughtフィルタリング適用
        4. 結果を返す

        Args:
            task: 実行するタスク

        Returns:
            実行結果
        """
        # v11.7.0: 全体 try/except で UI 状態整合性を保証
        try:
            return self._execute_task_inner(task)
        except Exception as e:
            logger.error(
                f"[SequentialExecutor] execute_task raised unexpectedly: "
                f"category={task.category}, model={task.model}, error={e}",
                exc_info=True,
            )
            return SequentialResult(
                category=task.category, model=task.model, success=False,
                response=f"予期しないエラー: {type(e).__name__}: {str(e)}",
                elapsed=0.0, order=task.order,
                original_prompt=task.prompt, expected_output=task.expected_output,
            )

    def _execute_task_inner(self, task: SequentialTask) -> SequentialResult:
        """v11.7.0: execute_task の内部実装（例外が素通りしても安全なように分離）"""
        # v10.0.0: Cloud AI モデルの場合はCLI経由
        if self._is_cloud_model(task.model):
            return self._execute_cloud_task(task)

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
