"""
mixAI 3Phase統合オーケストレーター v7.1.0

新3Phase実行パイプライン:
  Phase 1: Claude CLI計画立案（--cwdオプション付き、ツール使用指示を明記）
  Phase 2: ローカルLLM順次実行（Ollama APIで1モデルずつロード→実行→アンロード）
  Phase 3: Claude CLI比較統合（2回目呼び出し、Phase 1+Phase 2全結果を渡す）

v7.0.0: 旧5Phase→新3Phaseへの全面書き換え
  - --cwdオプション追加でClaudeが自発的にツール使用
  - ファイル埋め込み方式を廃止（Claudeが自分でReadツールを使用）
  - Phase 2は順次実行（RTX PRO 6000で1モデルずつ）
  - 品質不足時の再実行ループ（最大2回、Phase 2を再実行）
"""

import subprocess
import json
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from .sequential_executor import (
    SequentialExecutor,
    SequentialTask,
    SequentialResult,
    filter_chain_of_thought,
)
from ..utils.constants import DEFAULT_CLAUDE_MODEL_ID

logger = logging.getLogger(__name__)

# Phase 1出力から抽出するJSONのキー
PHASE1_JSON_KEYS = ("claude_answer", "local_llm_instructions", "complexity")

# Phase 3に渡す結果の最大文字数（コンテキストウィンドウ圧迫防止）
MAX_PHASE1_ANSWER_CHARS = 8000
MAX_PHASE2_RESULT_CHARS_PER_ITEM = 5000


class MixAIOrchestrator(QThread):
    """mixAIタブの3Phase実行エンジン v8.0.0 (BIBLE Manager統合)"""

    # ═══ UI通知用シグナル ═══
    phase_changed = pyqtSignal(int, str)       # (phase番号, 説明テキスト)
    streaming_output = pyqtSignal(str)         # Phase 1/3のClaude出力（逐次表示用）
    local_llm_started = pyqtSignal(str, str)   # (category, model名)
    local_llm_finished = pyqtSignal(str, bool, float)  # (category, success, elapsed)
    phase2_progress = pyqtSignal(int, int)     # (完了数, 総数)
    all_finished = pyqtSignal(str)             # 最終回答テキスト
    error_occurred = pyqtSignal(str)           # エラーメッセージ
    bible_action_proposed = pyqtSignal(object, str)  # v8.0.0: (BibleAction, reason)

    def __init__(
        self,
        user_prompt: str,
        attached_files: list[str],
        model_assignments: dict[str, str],
        config: dict,
    ):
        """
        Args:
            user_prompt: ユーザーの入力テキスト
            attached_files: 添付ファイルパスのリスト（--cwdと組み合わせて使用）
            model_assignments: カテゴリ→Ollamaモデル名マッピング
                例: {"coding": "devstral-2:123b",
                     "research": "command-a:111b",
                     "reasoning": "gpt-oss:120b",
                     "vision": "gemma3:27b",
                     "translation": "translategemma:27b"}
            config: アプリ設定dict。以下のキーを参照:
                - claude_model: str (デフォルト "opus")
                - timeout: int (デフォルト 600)
                - auto_knowledge: bool (デフォルト True)
                - project_dir: str (Claude CLIの--cwdに渡すディレクトリ)
                - max_phase2_retries: int (デフォルト 2)
        """
        super().__init__()
        self.user_prompt = user_prompt
        self.attached_files = attached_files
        self.model_assignments = model_assignments
        self.config = config
        self._cancelled = False
        self._phase2_results: list[SequentialResult] = []
        self._phase_times: dict[str, float] = {}
        self._bible_context = None  # v8.0.0: BibleInfo or None
        self._memory_manager = None  # v8.1.0: HelixMemoryManager or None

    def set_bible_context(self, bible):
        """v8.0.0: BIBLEコンテキストを設定"""
        self._bible_context = bible

    def set_memory_manager(self, memory_manager):
        """v8.1.0: メモリマネージャーを設定"""
        self._memory_manager = memory_manager

    def cancel(self):
        """実行キャンセル"""
        self._cancelled = True

    def get_phase2_results(self) -> list[SequentialResult]:
        """Phase 2の結果を取得"""
        return self._phase2_results

    def get_phase_times(self) -> dict[str, float]:
        """各Phaseの実行時間を取得"""
        return self._phase_times

    def run(self):
        try:
            self._execute_pipeline()
        except Exception as e:
            logger.exception("オーケストレーターエラー")
            self.error_occurred.emit(f"オーケストレーターエラー: {str(e)}")

    def _execute_pipeline(self):
        """3Phase パイプラインの実行"""

        # セッションディレクトリの作成（短期記憶）
        self._session_dir = self._create_session_dir()

        # ══════════════════════════════════════
        # Phase 1: Claude計画立案（CLI呼び出し 1/2）
        # ══════════════════════════════════════
        self.phase_changed.emit(1, "Phase 1: Claude計画立案中...")
        phase1_start = time.time()

        phase1_result = self._execute_phase1()
        self._phase_times["phase1"] = time.time() - phase1_start

        if self._cancelled:
            return

        # Phase 1結果のパース
        claude_answer = phase1_result.get("claude_answer", "")
        llm_instructions = phase1_result.get("local_llm_instructions", {})
        complexity = phase1_result.get("complexity", "low")
        skip_phase2 = phase1_result.get("skip_phase2", False)

        # v8.4.0: acceptance_criteriaを抽出（Phase 3で使用）
        self._acceptance_criteria = self._extract_acceptance_criteria(llm_instructions)

        # Phase 1の結果を短期記憶に保存
        self._save_session_phase1(phase1_result, claude_answer)

        # complexityがlowまたはskip_phase2=trueの場合、Phase 2-3をスキップ
        if skip_phase2 or complexity == "low":
            logger.info(f"Phase 2-3スキップ: complexity={complexity}, skip_phase2={skip_phase2}")
            self._save_session_metadata(claude_answer, skipped=True)
            self.all_finished.emit(claude_answer)
            return

        # ══════════════════════════════════════
        # Phase 2: ローカルLLM順次実行（Claude呼出なし）
        # ══════════════════════════════════════
        self.phase_changed.emit(2, "Phase 2: ローカルLLM順次実行中...")
        phase2_start = time.time()

        tasks = self._build_phase2_tasks(llm_instructions)

        if not tasks:
            # タスクがない場合はPhase 1の回答をそのまま返す
            logger.info("Phase 2タスクなし → Phase 1回答を返却")
            self.all_finished.emit(claude_answer)
            return

        executor = SequentialExecutor()
        self._phase2_results = []
        total_tasks = len(tasks)

        for i, task in enumerate(tasks):
            if self._cancelled:
                return

            # v8.2.0: Phase 2 RAGコンテキスト注入
            if self._memory_manager:
                try:
                    rag_ctx = self._memory_manager.build_context_for_phase2(
                        self.user_prompt, task.category
                    )
                    if rag_ctx:
                        task.prompt = f"{rag_ctx}\n{task.prompt}"
                        logger.info(
                            f"Phase 2 RAG context injected for {task.category}: "
                            f"{len(rag_ctx)} chars"
                        )
                except Exception as e:
                    logger.warning(f"Phase 2 RAG context failed for {task.category}: {e}")

            self.local_llm_started.emit(task.category, task.model)
            result = executor.execute_task(task)
            self._phase2_results.append(result)
            self.local_llm_finished.emit(result.category, result.success, result.elapsed)
            self.phase2_progress.emit(i + 1, total_tasks)

        self._phase_times["phase2"] = time.time() - phase2_start

        # Phase 2の結果を短期記憶に保存
        self.save_phase2_results(os.path.join(self._session_dir, "phase2"))

        if self._cancelled:
            return

        # ══════════════════════════════════════
        # Phase 3: Claude比較統合（CLI呼び出し 2/2）
        # ══════════════════════════════════════
        self.phase_changed.emit(3, "Phase 3: Claude比較統合中...")
        phase3_start = time.time()

        final_output = self._execute_phase3(claude_answer, self._phase2_results)
        self._phase_times["phase3"] = time.time() - phase3_start

        if self._cancelled:
            return

        # 統合結果を解析（品質不足による再実行指示があるかチェック）
        retry_result = self._check_phase3_retry(final_output)

        if retry_result is not None:
            # 再実行ループ（最大2回）
            max_retries = self.config.get("max_phase2_retries", 2)
            for retry_count in range(max_retries):
                if self._cancelled:
                    return

                retry_tasks = retry_result.get("retry_tasks", [])
                if not retry_tasks:
                    break

                self.phase_changed.emit(2, f"Phase 2: 再実行中 ({retry_count + 1}/{max_retries})...")

                for task_spec in retry_tasks:
                    if self._cancelled:
                        return
                    retry_prompt = task_spec.get("instruction", "")
                    # v8.2.0: 再実行時もRAGコンテキスト注入
                    if self._memory_manager:
                        try:
                            rag_ctx = self._memory_manager.build_context_for_phase2(
                                self.user_prompt, task_spec.get("category", "unknown")
                            )
                            if rag_ctx:
                                retry_prompt = f"{rag_ctx}\n{retry_prompt}"
                                logger.info(
                                    f"Phase 2 RAG context injected for retry "
                                    f"{task_spec.get('category', '?')}: {len(rag_ctx)} chars"
                                )
                        except Exception as e:
                            logger.warning(f"Phase 2 RAG retry context failed: {e}")

                    retry_task = SequentialTask(
                        category=task_spec.get("category", "unknown"),
                        model=task_spec.get("model", ""),
                        prompt=retry_prompt,
                        expected_output=task_spec.get("expected_output", ""),
                        timeout=task_spec.get("timeout_seconds", 300),
                        order=task_spec.get("order", 99),
                    )
                    self.local_llm_started.emit(retry_task.category, retry_task.model)
                    result = executor.execute_task(retry_task)
                    # 該当カテゴリの結果を更新
                    self._phase2_results = [
                        result if r.category == result.category else r
                        for r in self._phase2_results
                    ]
                    self.local_llm_finished.emit(result.category, result.success, result.elapsed)

                # 再度Phase 3を実行
                self.phase_changed.emit(3, f"Phase 3: 再統合中 ({retry_count + 1}/{max_retries})...")
                final_output = self._execute_phase3(claude_answer, self._phase2_results)

                retry_result = self._check_phase3_retry(final_output)
                if retry_result is None:
                    break

        # 最終回答を抽出
        if isinstance(final_output, dict):
            answer = final_output.get("final_answer", final_output.get("claude_answer", str(final_output)))
        else:
            answer = str(final_output)

        # Phase 3の結果と最終回答を短期記憶に保存
        self._save_session_phase3(answer)
        self._save_session_metadata(answer, skipped=False)

        self.all_finished.emit(answer)

        # v8.1.0: Post-Phase Memory Risk Gate
        if self._memory_manager:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self._memory_manager.evaluate_and_store(
                        f"mixai_{int(time.time())}", answer, self.user_prompt
                    )
                )
                loop.close()
                logger.info("Memory Risk Gate completed (mixAI)")
                # v8.3.1: RAPTOR非同期トリガー (別スレッド)
                import threading
                _session_id = f"mixai_{int(time.time())}"
                _mm = self._memory_manager
                _msgs = [{"role": "user", "content": self.user_prompt},
                         {"role": "assistant", "content": answer}]
                def _raptor_bg():
                    try:
                        _mm.raptor_summarize_session(_session_id, _msgs)
                        _mm.raptor_try_weekly()
                    except Exception as _e:
                        logger.warning(f"RAPTOR background: {_e}")
                threading.Thread(target=_raptor_bg, daemon=True).start()
            except Exception as e:
                logger.warning(f"Memory Risk Gate failed: {e}")

        # v8.0.0: Post-Phase BIBLE自律管理
        if self._bible_context and self.config.get("bible_auto_manage", True):
            try:
                from ..bible.bible_lifecycle import BibleLifecycleManager, BibleAction
                execution_result = {
                    "changed_files": [],
                    "app_version": self.config.get("app_version", ""),
                }
                action, reason = BibleLifecycleManager.determine_action(
                    self._bible_context, execution_result, self.config
                )
                if action != BibleAction.NONE:
                    self.bible_action_proposed.emit(action, reason)
            except Exception as e:
                logger.warning(f"BIBLE lifecycle check failed: {e}")

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: Claude計画立案
    # ═══════════════════════════════════════════════════════════════

    def _execute_phase1(self) -> dict:
        """Phase 1: Claude CLI計画立案を実行"""
        system_prompt = self._build_phase1_system_prompt()

        # v8.0.0: BIBLEコンテキスト注入
        bible_block = ""
        if self._bible_context:
            try:
                from ..bible.bible_injector import BibleInjector
                bible_ctx = BibleInjector.build_context(self._bible_context, mode="phase1")
                bible_block = f"<project_context>\n{bible_ctx}\n</project_context>\n\n"
            except Exception as e:
                logger.warning(f"BIBLE context injection failed: {e}")

        # v8.1.0: 記憶コンテキスト注入
        memory_block = ""
        if self._memory_manager:
            try:
                mem_ctx = self._memory_manager.build_context_for_phase1(self.user_prompt)
                if mem_ctx:
                    memory_block = f"<memory_context>\n{mem_ctx}\n</memory_context>\n\n"
            except Exception as e:
                logger.warning(f"Memory context injection failed: {e}")

        full_prompt = f"{system_prompt}\n\n{bible_block}{memory_block}## ユーザーの要求:\n{self.user_prompt}"

        # 添付ファイルがある場合はパス情報のみ伝える（内容の埋め込みはしない）
        if self.attached_files:
            files_info = "\n".join(f"- {f}" for f in self.attached_files)
            full_prompt += f"\n\n## 添付ファイル（Readツールで内容を確認してください）:\n{files_info}"

        model_id = self.config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
        raw_output = self._run_claude_cli(full_prompt, model_id=model_id)
        return self._parse_phase1_output(raw_output)

    def _build_phase1_system_prompt(self) -> str:
        """v8.4.0: Phase 1用システムプロンプト — 2段階構造化（設計分析→指示書生成）"""
        return """あなたはHelix AI Studioの計画立案AIです。
以下のユーザーの要求に対して、**2段階**で応答してください。

## Step 1: 設計分析 (Design Analysis)
まず以下を分析してください:
- 問題の分解と要件整理
- 必要な技術要素と依存関係
- リスク・制約の洗い出し
- 各カテゴリ（coding/research/reasoning/translation/vision）へのタスク分配方針

## Step 2: 指示書生成 (Instruction Generation)
Step 1の分析を踏まえ、以下を生成してください:
- 各カテゴリ別の詳細な指示書（JSON形式）
- 各指示書に **acceptance_criteria** を必ず含める
- ユーザーへの中間報告（初回回答）

## 利用可能なツール（積極的に使用してください）
- **Read**: ファイル内容の直接確認（推測せず実際に読んでください）
- **Bash**: コマンド実行（git status, npm install, pytest等）
- **Glob/Grep**: プロジェクト内のファイル検索・コード検索
- **WebSearch**: 最新技術情報、エラー解決策、ライブラリ情報の検索
- **WebFetch**: URL先のドキュメント・API仕様の取得

## 作業方針
1. まずプロジェクト構造を Glob/Read で確認
2. 必要に応じて WebSearch で最新情報を取得
3. **Step 1: 設計分析** — 問題分解・技術要素・リスク・タスク分配を整理
4. **Step 2: 指示書生成** — 設計分析結果に基づいて精密な指示書を生成

codingカテゴリの指示書を生成する際は、使用するライブラリ・
フレームワークの最新APIを考慮してください。Context7 MCPが
利用可能な場合、最新ドキュメントを参照して指示書に反映して
ください。

## 出力形式
以下のJSON形式で出力してください（```json で囲んでください）:

```json
{
  "claude_answer": "ユーザーへの回答（自然な日本語）",
  "design_analysis": {
    "requirements": ["要件1", "要件2"],
    "tech_elements": ["技術要素1", "技術要素2"],
    "risks": ["リスク1"],
    "task_distribution": "タスク分配の方針説明"
  },
  "local_llm_instructions": {
    "coding": {
      "prompt": "具体的なコーディング指示",
      "expected_output": "期待する出力形式",
      "context": "関連ファイルパス・API仕様等",
      "acceptance_criteria": [
        "基準1: 具体的な完了条件",
        "基準2: 検証可能な品質基準"
      ],
      "expected_output_format": "出力形式の指定",
      "skip": false
    },
    "research": {
      "prompt": "具体的な調査指示",
      "expected_output": "期待する出力形式",
      "context": "",
      "acceptance_criteria": ["基準1"],
      "expected_output_format": "",
      "skip": false
    },
    "reasoning": {
      "prompt": "具体的な推論・検証指示",
      "expected_output": "期待する出力形式",
      "context": "",
      "acceptance_criteria": ["基準1"],
      "expected_output_format": "",
      "skip": false
    },
    "vision": {
      "prompt": "具体的な画像解析指示",
      "expected_output": "期待する出力形式",
      "context": "",
      "acceptance_criteria": [],
      "expected_output_format": "",
      "skip": true
    },
    "translation": {
      "prompt": "具体的な翻訳指示",
      "expected_output": "期待する出力形式",
      "context": "",
      "acceptance_criteria": [],
      "expected_output_format": "",
      "skip": true
    }
  },
  "complexity": "simple|moderate|complex",
  "skip_phase2": false,
  "tools_used": ["Read", "WebSearch"]
}
```

## complexity判定基準
- **simple**: 挨拶、雑談、簡単なQ&A → skip_phase2: true
- **moderate**: 1カテゴリのみで対応可能な技術的質問
- **complex**: 複数カテゴリの協調が必要な高度なタスク

## skip_phase2の判定
- 挨拶・雑談・一般知識の問い合わせ → true
- 技術的な実装・設計・分析が必要 → false

## 各カテゴリの指示文作成ルール
- 各promptにはユーザーの質問の全文脈を含める（LLMは会話履歴を持たない）
- **acceptance_criteria**: 各カテゴリに検証可能な完了条件を最低1つ含める（Phase 3評価で使用）
- **context**: 関連ファイルパスやAPI仕様を含める（ローカルLLMの精度向上に直結）
- coding: 使用言語、フレームワーク、命名規則、エラーハンドリングを明記
- research: 検索キーワード候補、収集すべき情報の種類を明記
- reasoning: 検証すべき論理的観点、品質チェック基準を明記
- vision: 画像分析の観点を明記（画像タスクがある場合のみskip: false）
- translation: 原文の言語、翻訳先言語、専門用語の取扱いを明記
- 不要なカテゴリはskip: trueに設定"""

    def _parse_phase1_output(self, raw_output: str) -> dict:
        """Phase 1のClaude出力をパースしてJSONを抽出"""
        if not raw_output or not raw_output.strip():
            logger.warning("Phase 1: 空の出力を受信")
            return {"claude_answer": "", "local_llm_instructions": {}, "complexity": "low", "skip_phase2": True}

        # JSONブロックを抽出（```json ... ``` 形式）
        import re
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', raw_output)

        for json_str in reversed(json_blocks):
            try:
                parsed = json.loads(json_str.strip())
                if isinstance(parsed, dict) and "claude_answer" in parsed:
                    logger.info("Phase 1: 有効なJSONブロックを検出")
                    return parsed
            except json.JSONDecodeError:
                continue

        # ```json形式が見つからない場合、生のJSON検索
        json_pattern = r'\{\s*"claude_answer"\s*:[\s\S]*?\n\}'
        match = re.search(json_pattern, raw_output)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    logger.info("Phase 1: 生JSONブロックを検出")
                    return parsed
            except json.JSONDecodeError:
                pass

        # JSON解析失敗 → Claude回答全体をclaude_answerとして返す（Phase 2スキップ）
        logger.warning("Phase 1: JSON解析失敗 → Phase 2スキップ")
        return {
            "claude_answer": raw_output.strip(),
            "local_llm_instructions": {},
            "complexity": "low",
            "skip_phase2": True,
        }

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: タスク構築
    # ═══════════════════════════════════════════════════════════════

    def _build_phase2_tasks(self, llm_instructions: dict) -> list[SequentialTask]:
        """Phase 1のlocal_llm_instructionsからPhase 2タスクリストを構築"""
        tasks = []
        order = 1

        for category, spec in llm_instructions.items():
            if not isinstance(spec, dict):
                continue
            # skip: trueのカテゴリは除外
            if spec.get("skip", False):
                continue
            # モデルが割り当てられていないカテゴリは除外
            model = self.model_assignments.get(category)
            if not model:
                logger.debug(f"Phase 2: カテゴリ '{category}' にモデル未割当 → スキップ")
                continue
            # 指示文が空のカテゴリは除外
            prompt = spec.get("prompt", "").strip()
            if not prompt:
                continue

            tasks.append(SequentialTask(
                category=category,
                model=model,
                prompt=prompt,
                expected_output=spec.get("expected_output", ""),
                timeout=spec.get("timeout_seconds", 300),
                order=order,
            ))
            order += 1

        # order順にソート
        tasks.sort(key=lambda t: t.order)
        return tasks

    # ═══════════════════════════════════════════════════════════════
    # Phase 3: Claude比較統合
    # ═══════════════════════════════════════════════════════════════

    def _extract_acceptance_criteria(self, llm_instructions: dict) -> dict:
        """v8.4.0: Phase 1指示書からacceptance_criteriaを抽出"""
        criteria = {}
        for category, spec in llm_instructions.items():
            if isinstance(spec, dict) and not spec.get("skip", True):
                ac = spec.get("acceptance_criteria", [])
                if ac:
                    criteria[category] = ac
        return criteria

    def _execute_phase3(self, phase1_answer: str, phase2_results: list[SequentialResult]) -> dict:
        """Phase 3: Claude CLI比較統合を実行"""
        system_prompt = self._build_phase3_system_prompt(phase1_answer, phase2_results)

        # v8.0.0: BIBLEコンテキスト注入（Phase 3用）
        bible_block = ""
        if self._bible_context:
            try:
                from ..bible.bible_injector import BibleInjector
                bible_ctx = BibleInjector.build_context(self._bible_context, mode="phase3")
                bible_block = f"\n\n<project_context>\n{bible_ctx}\n</project_context>"
            except Exception as e:
                logger.warning(f"BIBLE Phase 3 context injection failed: {e}")

        # v8.1.0: 記憶コンテキスト注入（Phase 3用）
        memory_block = ""
        if self._memory_manager:
            try:
                mem_ctx = self._memory_manager.build_context_for_phase3(
                    self.user_prompt, phase1_answer)
                if mem_ctx:
                    memory_block = f"\n\n<memory_context>\n{mem_ctx}\n</memory_context>"
            except Exception as e:
                logger.warning(f"Memory Phase 3 context injection failed: {e}")

        full_prompt = f"{system_prompt}{bible_block}{memory_block}\n\n統合を実行してください。"

        model_id = self.config.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)
        raw_output = self._run_claude_cli(full_prompt, model_id=model_id)
        return self._parse_phase3_output(raw_output)

    def _build_phase3_system_prompt(self, phase1_answer: str, phase2_results: list[SequentialResult]) -> str:
        """v8.4.0: Phase 3用システムプロンプト — Acceptance Criteria評価 + 統合"""
        results_text = self._format_phase2_results(phase2_results)

        # v8.4.0: Acceptance Criteriaセクション構築
        criteria_section = ""
        criteria = getattr(self, '_acceptance_criteria', {})
        if criteria:
            criteria_lines = []
            for cat, items in criteria.items():
                criteria_lines.append(f"### {cat}カテゴリ")
                for i, c in enumerate(items, 1):
                    criteria_lines.append(f"  {i}. {c}")
            criteria_json = "\n".join(criteria_lines)
            criteria_section = f"""

## 品質評価チェックリスト (Acceptance Criteria)
以下のAcceptance Criteriaに対して、各Phase 2出力を評価してください。

{criteria_json}

各基準に対して以下の形式で判定:
- **PASS**: 基準を満たしている（根拠を1文で）
- **FAIL**: 基準を満たしていない（不足点と再実行指示）

全基準PASSの場合のみ最終統合回答を生成。
1つでもFAILがあれば再実行カテゴリと具体的指示を返却。
"""

        return f"""あなたはHelix AI Studioの統合AIです。

## Phase 1であなたが立案した計画と初回回答:
{phase1_answer[:MAX_PHASE1_ANSWER_CHARS]}

## Phase 2でローカルLLMチームが生成した結果:
{results_text}
{criteria_section}
## 利用可能なツール（必要に応じて使用してください）
- **Read/Write/Edit**: ファイルの確認・修正・生成
- **Bash**: テスト実行、ビルド、git操作
- **WebSearch**: 不明点の調査

## 統合方針
1. Acceptance Criteriaに基づいて各ローカルLLMの結果をPASS/FAIL判定
2. 自身のPhase 1の回答と比較し、優れた点を取り込む
3. 必要に応じてファイルを直接修正（Write/Edit）
4. テストを実行して品質を検証（Bash）
5. 最終回答を自然な日本語で生成

## 出力形式
以下のJSON形式で出力してください（```json で囲んでください）:

品質が十分な場合（全基準PASS）:
```json
{{
  "status": "complete",
  "final_answer": "ユーザーへの最終回答（自然な日本語）",
  "criteria_evaluation": {{
    "coding": [{{"criterion": "基準1", "result": "PASS", "reason": "根拠"}}],
    "research": [{{"criterion": "基準1", "result": "PASS", "reason": "根拠"}}]
  }},
  "integration_notes": "統合時の判断メモ"
}}
```

品質不足で再実行が必要な場合（1つ以上FAIL）:
```json
{{
  "status": "retry_needed",
  "final_answer": "現時点での暫定回答",
  "criteria_evaluation": {{
    "coding": [{{"criterion": "基準1", "result": "FAIL", "reason": "不足点"}}]
  }},
  "retry_tasks": [
    {{
      "category": "coding",
      "model": "devstral-2:123b",
      "instruction": "改善された指示文（FAIL基準を満たすための具体的指示）",
      "expected_output": "期待する出力",
      "order": 1,
      "timeout_seconds": 300
    }}
  ],
  "retry_reason": "再実行が必要な理由"
}}
```

## 重要なルール
- Acceptance Criteriaが存在する場合、各基準を必ずPASS/FAIL判定してください
- ローカルLLMが優れた指摘・提案をしている場合、あなたの回答に統合してください
- ローカルLLMの結果があなたの判断と矛盾する場合、あなた自身の判断を優先してください
- 最終判断は常にあなたが行います
- ユーザーへの回答は自然な文章で提示してください。ローカルLLMの存在に言及する必要はありません"""

    def _format_phase2_results(self, results: list[SequentialResult]) -> str:
        """Phase 2の全結果をテキストにフォーマット"""
        if not results:
            return "(Phase 2の結果はありません)"

        sections = []
        for r in results:
            if not r.success:
                sections.append(
                    f"### {r.category}担当（{r.model}）: 失敗\n"
                    f"理由: {r.response[:200]}"
                )
                continue

            truncated = r.response[:MAX_PHASE2_RESULT_CHARS_PER_ITEM]
            sections.append(
                f"### {r.category}担当（{r.model}）: 成功 ({r.elapsed:.1f}秒)\n"
                f"{truncated}"
            )

        return "\n\n".join(sections)

    def _parse_phase3_output(self, raw_output: str) -> dict:
        """Phase 3のClaude出力をパース"""
        if not raw_output or not raw_output.strip():
            return {"status": "complete", "final_answer": ""}

        import re
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', raw_output)

        for json_str in reversed(json_blocks):
            try:
                parsed = json.loads(json_str.strip())
                if isinstance(parsed, dict) and "final_answer" in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue

        # JSON解析失敗 → 出力全体を最終回答として返す
        return {"status": "complete", "final_answer": raw_output.strip()}

    def _check_phase3_retry(self, phase3_output: dict) -> dict | None:
        """統合フェーズの出力から品質再実行指示があるかチェック"""
        if isinstance(phase3_output, dict) and phase3_output.get("status") == "retry_needed":
            retry_tasks = phase3_output.get("retry_tasks", [])
            if retry_tasks:
                return phase3_output
        return None

    # ═══════════════════════════════════════════════════════════════
    # Claude CLI実行
    # ═══════════════════════════════════════════════════════════════

    def _run_claude_cli(self, prompt: str, model_id: str = None) -> str:
        """
        Claude Code CLIを非対話モードで実行。

        v7.0.0変更:
        - --cwdオプション追加でプロジェクトディレクトリを指定
        - ファイル埋め込み方式を廃止（Claudeが自分でReadツールを使用）
        - stdinでプロンプトを送信
        v7.1.0変更:
        - model_idパラメータ追加（CLAUDE_MODELSのidを直接渡す）
        """
        # v7.1.0: model_id → --model に直接渡す
        effective_model = model_id or self.config.get("claude_model_id") or self.config.get("claude_model", DEFAULT_CLAUDE_MODEL_ID)

        cmd = [
            "claude",
            "-p",                              # 非対話（パイプ）モード
            "--dangerously-skip-permissions",   # 全ツール自動許可
            "--output-format", "json",          # JSON出力
            "--model", effective_model,
        ]

        # v7.0.0: 作業ディレクトリ（subprocess.runのcwdパラメータで指定）
        project_dir = self.config.get("project_dir")
        run_cwd = project_dir if project_dir and os.path.isdir(project_dir) else None

        try:
            # Windows用の処理
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.config.get("timeout", 600),
                env={**os.environ, "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"},
                creationflags=creationflags,
                cwd=run_cwd,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if result.returncode == 0:
                try:
                    output_data = json.loads(stdout)
                    return output_data.get("result", stdout)
                except json.JSONDecodeError:
                    return stdout.strip()
            else:
                raise RuntimeError(
                    f"Claude CLI終了コード {result.returncode}: "
                    f"{stderr[:500] if stderr else 'エラー詳細なし'}"
                )

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Claude CLIがタイムアウト({self.config.get('timeout', 600)}秒)しました"
            )

    # ═══════════════════════════════════════════════════════════════
    # Phase 2結果のファイル保存
    # ═══════════════════════════════════════════════════════════════

    def save_phase2_results(self, session_dir: str = None):
        """Phase 2の結果をテキストファイルに保存"""
        if not self._phase2_results:
            return

        save_dir = session_dir or os.path.join("data", "phase2")
        os.makedirs(save_dir, exist_ok=True)

        for result in self._phase2_results:
            filename = f"task_{result.order}_{result.model.replace(':', '_').replace('/', '_')}.txt"
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Category: {result.category}\n")
                    f.write(f"Model: {result.model}\n")
                    f.write(f"Success: {result.success}\n")
                    f.write(f"Elapsed: {result.elapsed:.1f}s\n")
                    f.write(f"Order: {result.order}\n")
                    f.write("=" * 60 + "\n")
                    f.write(result.response)
                logger.info(f"Phase 2結果保存: {filepath}")
            except Exception as e:
                logger.error(f"Phase 2結果の保存失敗: {filepath}: {e}")

    # ═══════════════════════════════════════════════════════════════
    # v7.0.0: 短期記憶（Session Memory）
    # ═══════════════════════════════════════════════════════════════

    def _create_session_dir(self) -> str:
        """セッション用ディレクトリを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join("data", "sessions", timestamp)
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "phase2"), exist_ok=True)
        logger.info(f"セッションディレクトリ作成: {session_dir}")
        return session_dir

    def _save_session_phase1(self, phase1_result: dict, claude_answer: str):
        """Phase 1の計画JSONとClaude回答を短期記憶に保存"""
        try:
            # Phase 1計画JSON
            plan_path = os.path.join(self._session_dir, "phase1_plan.json")
            with open(plan_path, 'w', encoding='utf-8') as f:
                json.dump(phase1_result, f, ensure_ascii=False, indent=2)

            # Phase 1 Claude回答
            answer_path = os.path.join(self._session_dir, "phase1_claude_answer.txt")
            with open(answer_path, 'w', encoding='utf-8') as f:
                f.write(claude_answer)

            logger.info(f"Phase 1結果を短期記憶に保存: {self._session_dir}")
        except Exception as e:
            logger.error(f"Phase 1短期記憶の保存失敗: {e}")

    def _save_session_phase3(self, final_answer: str):
        """Phase 3の統合結果を短期記憶に保存"""
        try:
            path = os.path.join(self._session_dir, "phase3_integration.txt")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(final_answer)
            logger.info(f"Phase 3結果を短期記憶に保存: {path}")
        except Exception as e:
            logger.error(f"Phase 3短期記憶の保存失敗: {e}")

    def _save_session_metadata(self, final_answer: str, skipped: bool = False):
        """セッションメタデータを短期記憶に保存"""
        try:
            metadata = {
                "session_start": getattr(self, '_session_dir', '').split(os.sep)[-1],
                "user_prompt": self.user_prompt[:500],
                "project_dir": self.config.get("project_dir", ""),
                "phase_times": self._phase_times,
                "phase2_skipped": skipped,
                "phase2_results_count": len(self._phase2_results),
                "final_answer_length": len(final_answer),
                "timestamp": datetime.now().isoformat(),
                # v8.4.0: Acceptance Criteria追跡
                "acceptance_criteria": getattr(self, '_acceptance_criteria', {}),
            }
            path = os.path.join(self._session_dir, "metadata.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"セッションメタデータ保存: {path}")
        except Exception as e:
            logger.error(f"セッションメタデータの保存失敗: {e}")
