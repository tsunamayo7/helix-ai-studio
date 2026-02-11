# Helix AI Studio v6.0.0 アップグレード指示書（決定版）

**対象**: Claude Code CLI による自動実行
**基準バージョン**: HelixAIStudio v5.2.0
**目標バージョン**: HelixAIStudio v6.0.0
**作成日**: 2026-02-05

---

## ⚠️ 実行前の必須手順

この指示書を実行する前に、以下の手順を必ず行ってください。

1. プロジェクトルートで `find . -name "*.py" -not -path "./.venv/*" | head -100` を実行し、全Pythonファイル一覧を確認すること
2. `src/main_window.py` を読み、現在のタブ追加順序（addTab呼び出し箇所）と各タブの変数名を正確に把握すること
3. `src/tabs/` ディレクトリ内の全ファイルを確認し、「チャット作成」タブに該当するファイル名を特定すること
4. `src/backends/claude_executor.py` を読み、現在のAPI/CLI分岐ロジックを把握すること
5. `src/utils/constants.py` を読み、現在のバージョン文字列を確認すること
6. `config/` ディレクトリ内の設定ファイルを確認し、api_key関連の項目を把握すること
7. `requirements.txt` または `pyproject.toml` を確認し、`anthropic` パッケージの有無を確認すること

不明な箇所は推測せず、必ずファイルを読んで確認してから作業を進めてください。

---

## 1. 設計思想

### 1.1 コンセプトの根本転換

v6.0.0は設計思想を根本から転換するメジャーアップグレードです。

旧コンセプト（v5.2.0以前）では「Claude APIの使用コスト削減のためにローカルLLMで一部処理を代替する」という方針でした。新コンセプト（v6.0.0）では「Claude Codeの出力精度を最大化するために、ローカルLLMを並行ワーカーチームとして活用する」という方針に転換します。

Claude Codeの使用量削減はもはや目的ではありません。Claude Max（$150/月）の無制限CLI利用を前提に、Claude Codeが十全に力を発揮できるようローカルLLMチームが多角的な検証結果を提供し、Claude Codeがそれらを評価・統合して最高品質のアウトプットを生み出す環境を構築します。

### 1.2 Claude呼び出し最小化の原則

Claude Codeの呼び出し回数は1ユーザーリクエストあたり最大2回に制限します。この設計原則の根拠は以下の通りです。

Claude Code（Opus 4.5）は1回の呼び出しが高コスト（レート制限を消費）だが高品質な判断ができます。ローカルLLMは何度呼んでも追加コストゼロだが個々の品質はClaude以下です。この非対称性を最大限に活かすため、「高コストなClaudeは最小回数で最大価値を出す」「ゼロコストなローカルは品質が出るまで何度でも反復する」という原則を採用します。

### 1.3 Claude生成指示文によるローカルLLM精度底上げ

v6.0.0の最大のイノベーションは、Phase 1でClaude Opus 4.5が各ローカルLLM向けの最適な指示文を生成する点にあります。

従来の設計では、ローカルLLMへの指示はアプリのPythonコードに埋め込まれた固定テンプレートから生成されていました。これではテンプレート作成者（開発者）の指示設計能力が品質の天井を決めてしまいます。v6.0.0では、Claude Opus 4.5がユーザーの質問を深く理解したうえで「この質問に対して検索担当LLMにはこう聞くべき」「コーディング担当LLMにはこの仕様で実装させるべき」というタスク固有の最適な指示文を動的に生成します。これにより、ローカルLLMの実効的な出力精度がClaude品質の指示文によって底上げされ、Phase 3の品質検証ループでの再実行回数も減少します。

---

## 2. 変更の全体像

本アップグレードは4つの変更カテゴリで構成されます。

**変更A** — 5Phase実行アーキテクチャの新規実装（mixAIタブの中核機能）
**変更B** — Claude API認証の完全廃止（CLI専用化）
**変更C** — タブ構成の変更（チャット作成タブ完全削除、mixAIタブ先頭配置）
**変更D** — mixAI設定画面の刷新（並行ワーカー設定、品質検証設定の新設）

実装は段階的に行い、各段階で動作確認を挟んでください。推奨順序はセクション9に記載しています。

---

## 3. 変更A: 5Phase実行アーキテクチャ

### 3.1 フロー全体図

mixAIタブで送信ボタンが押された際の実行フローを以下に定義します。Claude Code CLIの呼び出しはPhase 1とPhase 4の最大2回のみです。

```
ユーザーがmixAIチャットで送信ボタンを押す
    │
    ▼
╔══════════════════════════════════════════════════════════╗
║ Phase 1: Claude初回実行（Claude CLI呼び出し 1回目）      ║
║                                                          ║
║ Claude Code CLIを --append-system-prompt 付きで起動。    ║
║ Claudeは2つのタスクを同時に実行する:                     ║
║                                                          ║
║ タスクA: ユーザー指示に対する自身の回答を生成             ║
║   （コード生成・分析・設計・検索など）                    ║
║   → result_claude として保存                             ║
║                                                          ║
║ タスクB: 各ローカルLLM向けの最適な指示文をJSON生成       ║
║   → instructions.json として保存                         ║
║   ★ Claudeの知性で指示文品質を担保する核心機能          ║
║   ★ 不要カテゴリは skip_categories で除外               ║
║                                                          ║
║ → Claude CLIプロセス終了                                 ║
╚══════════════════════════════════════════════════════════╝
    │
    ▼
╔══════════════════════════════════════════════════════════╗
║ Phase 2: ローカルLLMチーム並行実行（Claude呼出なし）     ║
║                                                          ║
║ アプリが instructions.json をパースし各LLMに並行指示:    ║
║ ├── 検索担当LLM   ← Claudeが書いた検索用指示文で実行   ║
║ ├── レポート担当LLM ← Claudeが書いたレポート用指示文   ║
║ ├── アーキテクト担当LLM ← Claudeが書いた設計用指示文   ║
║ └── コーディング担当LLM ← Claudeが書いたコード用指示文 ║
║                                                          ║
║ ThreadPoolExecutor(max_workers=3) で並行実行             ║
║ → 各LLMの結果を local_results[] に収集                  ║
╚══════════════════════════════════════════════════════════╝
    │
    ▼
╔══════════════════════════════════════════════════════════╗
║ Phase 3: 品質検証ループ（Claude呼出なし）                ║
║                                                          ║
║ 品質検証担当LLM（nemotron-3-nano:30b）が各結果を評価:   ║
║ ├── 品質OK → Phase 4へ                                  ║
║ └── 品質NG → Claudeの元指示文をベースにプロンプト改善   ║
║     → 該当LLMに再実行指示                                ║
║     → 再評価（最大N回、設定で変更可能）                  ║
║                                                          ║
║ ★ 再実行時もClaude品質の指示文がベースなので            ║
║   プロンプト品質の土台が維持される                       ║
║ ★ このループは何回回してもClaude呼出コストゼロ          ║
╚══════════════════════════════════════════════════════════╝
    │
    ▼
╔══════════════════════════════════════════════════════════╗
║ Phase 4: Claude比較検証＋最終統合（Claude CLI 2回目）    ║
║                                                          ║
║ Claude Code CLI再起動:                                   ║
║ --append-system-prompt に以下を注入:                     ║
║   ・Phase 1での自身の成果物 (result_claude)              ║
║   ・Phase 2-3完了後の全ローカルLLM結果                   ║
║                                                          ║
║ Claudeは自身の成果物とローカルLLM結果を比較検証し、     ║
║ 最善の最終回答を生成。必要ならファイル操作も実行。       ║
║ → ユーザーへのチャット回答を表示                         ║
╚══════════════════════════════════════════════════════════╝
    │
    ▼
╔══════════════════════════════════════════════════════════╗
║ Phase 5: ナレッジ管理（Claude呼出なし・バックグラウンド）║
║                                                          ║
║ 常駐LLMがバックグラウンドで自律実行:                     ║
║ ├── nemotron-3-nano:30b → 会話全文+並行結果を要約       ║
║ ├── qwen3-embedding:4b → ベクトル化                     ║
║ └── SQLite + FAISS に保存                                ║
╚══════════════════════════════════════════════════════════╝
```

重要な分岐: ユーザーの質問が単純（挨拶、簡単な質問等）な場合、Phase 1でClaudeが全カテゴリをskip_categoriesに含めるため、Phase 2-3はスキップされPhase 1の回答がそのままユーザーに返されます。この場合のClaude呼び出しは1回のみです。

### 3.2 新規ファイル一覧

以下のファイルをすべて新規作成してください。

```
src/backends/phase1_prompt.py       ← Phase 1のシステムプロンプト定義
src/backends/phase1_parser.py       ← Phase 1出力のパーサー
src/backends/parallel_pool.py       ← Phase 2の並行実行プール
src/backends/quality_verifier.py    ← Phase 3の品質検証ループ
src/backends/phase4_prompt.py       ← Phase 4の統合プロンプト生成
src/backends/mix_orchestrator.py    ← 全Phaseを統合制御するオーケストレーター
src/knowledge/knowledge_manager.py  ← Phase 5のナレッジ管理
src/knowledge/knowledge_worker.py   ← Phase 5のバックグラウンドワーカー
```

`src/knowledge/` ディレクトリが存在しない場合は作成し、`__init__.py` も配置してください。

### 3.3 Phase 1: システムプロンプト定義

`src/backends/phase1_prompt.py` を以下の内容で作成してください。

```python
"""
Phase 1: Claude Code初回実行用システムプロンプト

Claudeに2つのタスクを同時実行させる:
  タスクA: ユーザー指示に対する自身の回答生成
  タスクB: 各ローカルLLM向けの最適な指示文をJSON形式で生成

タスクBの指示文品質がPhase 2-3の全体精度を決定するため、
このプロンプトの設計は極めて重要。
"""

PHASE1_SYSTEM_PROMPT = """
あなたはHelix AI Studioの司令官です。ユーザーの指示に対して以下の2つのタスクを実行してください。

■ タスク1: 自身による実行
ユーザーの指示に対して、あなた自身で検索・分析・設計・コーディングなど必要な作業を実行し、最善の回答を生成してください。これが「あなたの成果物」です。通常通りの品質で回答してください。

■ タスク2: ローカルLLMチームへの指示文生成
以下の4カテゴリのローカルLLMに対する最適な指示文を生成してください。各指示文はそのLLMが「単独で」実行できるよう、必要な文脈・制約・期待する出力形式をすべて含めてください。ローカルLLMはユーザーとの会話履歴を持たないため、指示文の中に必要な文脈をすべて含めることが極めて重要です。

あなたの回答の末尾に、必ず以下のJSON形式で出力してください。
JSONブロックは必ず ```json と ``` で囲んでください。

```json
{
  "local_llm_instructions": {
    "search": {
      "prompt": "検索担当への具体的な指示文。検索キーワード候補、どの観点で情報を集めるかを明記。",
      "expected_output": "期待する出力の形式や内容の説明"
    },
    "report": {
      "prompt": "レポート担当への具体的な指示文。比較・分析の観点、構成を明記。",
      "expected_output": "期待する出力の形式や内容の説明"
    },
    "architect": {
      "prompt": "アーキテクト担当への具体的な指示文。要件・制約・ディレクトリ構成・設計パターンを明記。",
      "expected_output": "期待する出力の形式や内容の説明"
    },
    "coding": {
      "prompt": "コーディング担当への具体的な指示文。使用言語・フレームワーク・命名規則・エラーハンドリング方針・ファイル構成を明記。",
      "expected_output": "期待する出力の形式や内容の説明"
    }
  },
  "skip_categories": []
}
```

■ 指示文生成ルール:
1. ユーザーの質問が単純な場合（挨拶、簡単な質問、雑談、一般的な知識の問い合わせ等）は、全4カテゴリを skip_categories に含めてください。例: "skip_categories": ["search", "report", "architect", "coding"]
2. 一部のカテゴリだけ不要な場合（例: コードを書く必要がない質問）も、そのカテゴリ名を skip_categories に含めてください。
3. 各指示文にはユーザーの質問の文脈を十分に含めてください。ローカルLLMは会話履歴を一切持ちません。
4. コーディング担当への指示には、使用言語・フレームワーク・命名規則・エラーハンドリング方針・具体的なファイル名を必ず明記してください。
5. 検索担当への指示には、検索キーワード候補と、どの観点で情報を集めるかを明記してください。
6. アーキテクト担当への指示には、ディレクトリ構成図の出力を要求してください。
7. skip_categories に含まれたカテゴリは後続のPhaseで実行されません。

■ 重要: JSONブロックは回答の末尾に1つだけ配置してください。回答本文の途中にJSONを含めないでください。
"""
```

### 3.4 Phase 1: 出力パーサー

`src/backends/phase1_parser.py` を以下の内容で作成してください。

```python
"""
Phase 1出力パーサー

Claude Code Phase 1の出力テキストから以下の2つを分離する:
  1. result_claude: Claudeの回答テキスト（タスクAの成果物）
  2. instructions: ローカルLLM向け指示文JSON（タスクBの成果物）

JSON解析に失敗した場合やskip_categoriesで全カテゴリがスキップされた場合、
instructionsはNoneを返す。この場合Phase 2-3はスキップされ、
result_claudeがそのままユーザーへの回答となる。
"""

import json
import re
from typing import Optional


def parse_phase1_output(claude_output: str) -> tuple[str, Optional[dict]]:
    """
    Claude Code Phase 1の出力を解析し、
    Claudeの回答テキストとローカルLLM指示文JSONを分離する。

    Args:
        claude_output: Claude Code CLIの全出力テキスト

    Returns:
        (result_claude, instructions) のタプル。
        instructionsはJSON解析成功時はdict、失敗時またはスキップ時はNone。
    """
    # 末尾の ```json ... ``` ブロックを探す（最後のマッチを使用）
    pattern = r'```json\s*(\{.*?\})\s*```'
    matches = list(re.finditer(pattern, claude_output, re.DOTALL))

    if not matches:
        # JSON指示文なし → Phase 2-3スキップ
        return claude_output.strip(), None

    # 最後のJSONブロックを指示文として扱う
    last_match = matches[-1]
    json_str = last_match.group(1)

    # Claudeの回答テキスト = JSONブロック前の部分
    result_claude = claude_output[:last_match.start()].strip()

    try:
        instructions = json.loads(json_str)

        # バリデーション: 必須キーの存在確認
        if "local_llm_instructions" not in instructions:
            return claude_output.strip(), None

        # skip_categoriesで全カテゴリがスキップされている場合
        skip = set(instructions.get("skip_categories", []))
        all_categories = {"search", "report", "architect", "coding"}
        active_categories = all_categories - skip

        if not active_categories:
            # 全スキップ → Phase 2-3不要
            return result_claude, None

        # アクティブなカテゴリのうち、実際に指示文が存在するものを確認
        llm_inst = instructions.get("local_llm_instructions", {})
        has_valid_instruction = any(
            cat in llm_inst and llm_inst[cat].get("prompt")
            for cat in active_categories
        )

        if not has_valid_instruction:
            return result_claude, None

        return result_claude, instructions

    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        # JSON解析失敗 → Phase 2-3スキップ（Claudeの回答のみ返す）
        return claude_output.strip(), None
```

### 3.5 Phase 2: 並行実行プール

`src/backends/parallel_pool.py` を以下の内容で作成してください。

```python
"""
Phase 2: ローカルLLMチーム並行実行プール

Claudeが生成した指示文（instructions.json）に基づき、
各担当ローカルLLMをThreadPoolExecutorで並行実行する。

GPU2枚（RTX PRO 6000 + RTX 5070 Ti）の物理的並列処理上限を考慮し、
max_workers=3をデフォルトとする。
"""

import concurrent.futures
import requests
import time
from dataclasses import dataclass, field
from typing import Optional

OLLAMA_API_BASE = "http://localhost:11434/api"


@dataclass
class ParallelTask:
    """並行実行タスク定義"""
    category: str          # "search" | "report" | "architect" | "coding"
    model: str             # Ollamaモデル名（例: "nemotron-3-nano:30b"）
    prompt: str            # Claudeが生成した指示文
    expected_output: str   # 期待する出力形式の説明（品質検証で使用）
    timeout: int = 300     # タイムアウト秒数


@dataclass
class ParallelResult:
    """並行実行結果"""
    category: str          # タスクカテゴリ
    model: str             # 使用したモデル名
    success: bool          # 実行成功/失敗
    response: str          # LLMの応答テキスト（失敗時はエラーメッセージ）
    elapsed: float         # 処理時間（秒）
    iteration: int = 1     # 何回目の実行か（Phase 3の再実行追跡用）
    original_prompt: str = ""  # 元のClaude生成指示文（Phase 3で再利用）
    expected_output: str = ""  # 期待する出力（Phase 3で再利用）


class ParallelWorkerPool:
    """
    ローカルLLMへの並行タスク実行プール。

    アプリ側（Python）で制御し、Claude Codeは一切関与しない。
    """

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers

    def execute_parallel(self, tasks: list[ParallelTask]) -> list[ParallelResult]:
        """複数タスクをThreadPoolExecutorで並行実行し、全結果を返す"""
        if not tasks:
            return []

        results: list[ParallelResult] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_map = {
                executor.submit(self._run_single_task, task): task
                for task in tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                task = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(ParallelResult(
                        category=task.category,
                        model=task.model,
                        success=False,
                        response=f"ThreadPool Error: {str(e)}",
                        elapsed=0.0,
                        original_prompt=task.prompt,
                        expected_output=task.expected_output,
                    ))
        return results

    def execute_single(self, task: ParallelTask) -> ParallelResult:
        """単一タスクを実行（Phase 3の再実行用）"""
        return self._run_single_task(task)

    def _run_single_task(self, task: ParallelTask) -> ParallelResult:
        """OllamaのGenerate APIで単一タスクを実行"""
        start = time.time()
        try:
            response = requests.post(
                f"{OLLAMA_API_BASE}/generate",
                json={
                    "model": task.model,
                    "prompt": task.prompt,
                    "stream": False,
                    "keep_alive": "5m",  # 反復ループ用に5分間VRAMに保持
                },
                timeout=task.timeout,
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                return ParallelResult(
                    category=task.category,
                    model=task.model,
                    success=True,
                    response=data.get("response", ""),
                    elapsed=elapsed,
                    original_prompt=task.prompt,
                    expected_output=task.expected_output,
                )
            else:
                return ParallelResult(
                    category=task.category,
                    model=task.model,
                    success=False,
                    response=f"HTTP {response.status_code}: {response.text[:200]}",
                    elapsed=elapsed,
                    original_prompt=task.prompt,
                    expected_output=task.expected_output,
                )

        except requests.exceptions.Timeout:
            return ParallelResult(
                category=task.category,
                model=task.model,
                success=False,
                response=f"Timeout after {task.timeout}s",
                elapsed=time.time() - start,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )
        except requests.exceptions.ConnectionError:
            return ParallelResult(
                category=task.category,
                model=task.model,
                success=False,
                response="Ollama接続失敗。Ollamaが起動しているか確認してください。",
                elapsed=time.time() - start,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )
        except Exception as e:
            return ParallelResult(
                category=task.category,
                model=task.model,
                success=False,
                response=f"Error: {str(e)}",
                elapsed=time.time() - start,
                original_prompt=task.prompt,
                expected_output=task.expected_output,
            )

    def build_tasks_from_instructions(
        self,
        instructions: dict,
        model_assignments: dict[str, str],
    ) -> list[ParallelTask]:
        """
        Phase 1でClaude が生成したinstructions JSONから
        並行実行タスクリストを構築する。

        Args:
            instructions: phase1_parser が返した dict
            model_assignments: 設定画面で選択されたカテゴリ→モデル名マッピング
                例: {
                    "search": "nemotron-3-nano:30b",
                    "report": "qwen3-next:80b",
                    "architect": "nemotron-3-nano:30b",
                    "coding": "qwen3-coder:30b",
                }
        """
        tasks = []
        skip = set(instructions.get("skip_categories", []))
        llm_inst = instructions.get("local_llm_instructions", {})

        for category, spec in llm_inst.items():
            # スキップ対象は除外
            if category in skip:
                continue
            # モデルが割り当てられていないカテゴリは除外
            model = model_assignments.get(category)
            if not model:
                continue
            # 指示文が空のカテゴリは除外
            prompt = spec.get("prompt", "").strip()
            if not prompt:
                continue

            tasks.append(ParallelTask(
                category=category,
                model=model,
                prompt=prompt,
                expected_output=spec.get("expected_output", ""),
            ))

        return tasks
```

### 3.6 Phase 3: 品質検証ループ

`src/backends/quality_verifier.py` を以下の内容で作成してください。

```python
"""
Phase 3: 品質検証ループ（Claude呼び出し一切なし）

常駐LLM（nemotron-3-nano:30b）が各ローカルLLMの出力品質を評価する。
品質NGの場合、Claudeが生成した元の指示文をベースにプロンプトを改善し、
該当LLMに再実行を指示する。

★ 核心: 再実行時もClaude品質の指示文がベースとして維持されるため、
  プロンプト品質の土台が崩れない。
★ このループは何回回してもClaude Code呼び出しコストゼロ。
"""

import requests
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .parallel_pool import ParallelResult, ParallelWorkerPool, ParallelTask

OLLAMA_API_BASE = "http://localhost:11434/api"


class QualityVerifier:
    """品質検証＋再実行ループの管理者"""

    def __init__(
        self,
        verifier_model: str = "nemotron-3-nano:30b",
        max_retries: int = 3,
    ):
        self.verifier_model = verifier_model
        self.max_retries = max_retries

    def verify_and_refine(
        self,
        result: 'ParallelResult',
        pool: 'ParallelWorkerPool',
    ) -> 'ParallelResult':
        """
        1つの並行実行結果を検証し、品質NGなら再実行する。

        再実行時はresult.original_prompt（Claude生成の指示文）を
        ベースとして使用するため、プロンプト品質の土台が維持される。

        Args:
            result: Phase 2の実行結果（original_prompt, expected_outputを含む）
            pool: 再実行用のParallelWorkerPool

        Returns:
            最終的なParallelResult（品質OKまたは最大再試行回数到達）
        """
        current_result = result

        for retry in range(self.max_retries):
            # 品質評価を常駐LLMで実行
            evaluation = self._evaluate_quality(
                response=current_result.response,
                original_prompt=current_result.original_prompt,
                expected_output=current_result.expected_output,
            )

            if evaluation["pass"]:
                return current_result

            # 品質NG → Claude生成の元指示文をベースにプロンプト改善して再実行
            improved_prompt = self._build_improved_prompt(
                original_prompt=current_result.original_prompt,
                previous_response=current_result.response,
                feedback=evaluation["feedback"],
                expected_output=current_result.expected_output,
            )

            from .parallel_pool import ParallelTask
            retry_task = ParallelTask(
                category=current_result.category,
                model=current_result.model,
                prompt=improved_prompt,
                expected_output=current_result.expected_output,
            )

            new_result = pool.execute_single(retry_task)
            new_result.iteration = retry + 2  # 2回目, 3回目, ...
            new_result.original_prompt = current_result.original_prompt  # 元指示文は維持
            current_result = new_result

        # 最大再試行回数に達した場合、最後の結果を返す
        return current_result

    def _evaluate_quality(
        self, response: str, original_prompt: str, expected_output: str
    ) -> dict:
        """
        常駐LLM（nemotron-3-nano:30b等）で品質評価を実行。

        Returns:
            {"pass": True/False, "feedback": "改善点の説明"}
        """
        eval_prompt = f"""あなたは品質検証AIです。以下の「元の指示」に対する「実行結果」の品質を評価してください。

【元の指示】
{original_prompt[:2000]}

【期待する出力】
{expected_output[:500]}

【実行結果】
{response[:3000]}

以下のJSON形式のみで回答してください。他のテキストは出力しないでください。
{{"pass": true, "feedback": ""}} または {{"pass": false, "feedback": "具体的な改善点"}}

評価基準:
- 指示に対して適切な内容が含まれているか
- 期待する出力形式に合っているか
- 明らかなエラーや矛盾がないか
- 実用的な情報が含まれているか

JSON:"""

        try:
            r = requests.post(
                f"{OLLAMA_API_BASE}/generate",
                json={
                    "model": self.verifier_model,
                    "prompt": eval_prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=120,
            )
            if r.status_code == 200:
                raw = r.json().get("response", "{}")
                data = json.loads(raw)
                return {
                    "pass": bool(data.get("pass", True)),
                    "feedback": str(data.get("feedback", "")),
                }
        except Exception:
            pass

        # 評価自体が失敗した場合はパスとみなす（安全側に倒す）
        return {"pass": True, "feedback": ""}

    def _build_improved_prompt(
        self,
        original_prompt: str,
        previous_response: str,
        feedback: str,
        expected_output: str,
    ) -> str:
        """
        Claude生成の元指示文をベースに、フィードバックを追記した改善プロンプトを構築。

        ★ ベースがClaude品質の指示文なので、改善を重ねても品質の土台が維持される。
        """
        return f"""{original_prompt}

--- 以下は前回実行に対するフィードバックです。これを踏まえて改善してください ---

【前回の出力に対する問題点】
{feedback}

【期待する出力形式】
{expected_output}

上記の問題点を修正し、より高品質な結果を生成してください。"""
```

### 3.7 Phase 4: 統合プロンプト生成

`src/backends/phase4_prompt.py` を以下の内容で作成してください。

```python
"""
Phase 4: Claude比較検証＋最終統合用プロンプト生成

Phase 1でのClaudeの成果物とPhase 2-3完了後のローカルLLM結果を
--append-system-prompt 用の文字列に整形する。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .parallel_pool import ParallelResult


# 注入する結果の最大文字数（コンテキストウィンドウ圧迫防止）
MAX_CLAUDE_RESULT_CHARS = 8000
MAX_LOCAL_RESULT_CHARS_PER_ITEM = 5000


def build_phase4_system_prompt(
    result_claude: str,
    local_results: list,  # list[ParallelResult]
) -> str:
    """
    Phase 4のClaude Code CLI呼び出し用 --append-system-prompt を構築。

    Args:
        result_claude: Phase 1でのClaudeの成果物テキスト
        local_results: Phase 2-3完了後の全ローカルLLM結果
    """
    # ローカルLLM結果のフォーマット
    local_sections = []
    for r in local_results:
        if not r.success:
            local_sections.append(
                f"【{r.category}担当】モデル: {r.model} / 状態: 失敗 / "
                f"理由: {r.response[:200]}"
            )
            continue

        iteration_note = f"（再実行{r.iteration}回目で品質OK）" if r.iteration > 1 else ""
        truncated = r.response[:MAX_LOCAL_RESULT_CHARS_PER_ITEM]
        local_sections.append(
            f"【{r.category}担当】モデル: {r.model} / "
            f"処理時間: {r.elapsed:.1f}秒{iteration_note}\n"
            f"{truncated}"
        )

    local_summary = "\n\n" + ("=" * 40) + "\n\n".join(local_sections)

    return f"""あなたはHelix AI Studioの司令官です。これは最終統合フェーズ（Phase 4）です。

■ あなたの役割
先ほど（Phase 1で）あなた自身が生成した成果物と、ローカルLLMチームが並行実行した成果物の両方が以下に示されています。これらを比較検証し、最善の最終回答を生成してください。

■ 比較検証のルール
- ローカルLLMが優れた指摘・提案をしている場合、あなたの回答に統合してください
- ローカルLLMの結果があなたの判断と矛盾する場合、あなた自身の判断を優先してください
- 最終判断は常にあなたが行います
- 必要な場合はファイル操作（コード書き込み・ファイル生成等）を実行してください
- ユーザーへの回答は自然な文章で提示してください。ローカルLLMの存在に言及する必要はありません

■ あなた自身のPhase 1成果物
{result_claude[:MAX_CLAUDE_RESULT_CHARS]}

■ ローカルLLMチームの成果物
{local_summary}

上記を踏まえて、ユーザーへの最終回答を生成してください。"""
```

### 3.8 5Phase統合オーケストレーター

`src/backends/mix_orchestrator.py` を以下の内容で作成してください。これがmixAIタブの中核エンジンです。

```python
"""
mixAI 5Phase統合オーケストレーター

全5Phaseを順次実行し、PyQt6シグナルでUIに状態を通知する。
Claude Code CLIの呼び出しは最大2回（Phase 1とPhase 4）。
Phase 2, 3, 5はローカルLLMのみで動作し、Claude呼び出しコストゼロ。
"""

import subprocess
import json
import os
from PyQt6.QtCore import QThread, pyqtSignal

from .phase1_prompt import PHASE1_SYSTEM_PROMPT
from .phase1_parser import parse_phase1_output
from .parallel_pool import ParallelWorkerPool
from .quality_verifier import QualityVerifier
from .phase4_prompt import build_phase4_system_prompt


class MixAIOrchestrator(QThread):
    """mixAIタブの5Phase実行エンジン"""

    # ═══ UI通知用シグナル ═══
    phase_changed = pyqtSignal(int, str)       # (phase番号, 説明テキスト)
    streaming_output = pyqtSignal(str)         # Phase 1/4のClaude出力（逐次表示用）
    local_llm_started = pyqtSignal(str, str)   # (category, model名)
    local_llm_finished = pyqtSignal(str, bool, float)  # (category, success, elapsed)
    quality_retry = pyqtSignal(str, int)       # (category, retry回数)
    all_finished = pyqtSignal(str)             # 最終回答テキスト
    error_occurred = pyqtSignal(str)           # エラーメッセージ

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
            attached_files: 添付ファイルパスのリスト
            model_assignments: カテゴリ→Ollamaモデル名マッピング
                例: {"search": "nemotron-3-nano:30b",
                     "report": "qwen3-next:80b",
                     "architect": "nemotron-3-nano:30b",
                     "coding": "qwen3-coder:30b"}
            config: アプリ設定dict。以下のキーを参照:
                - claude_model: str (デフォルト "opus")
                - max_workers: int (デフォルト 3)
                - max_retries: int (デフォルト 3)
                - verifier_model: str (デフォルト "nemotron-3-nano:30b")
                - timeout: int (デフォルト 600)
                - auto_knowledge: bool (デフォルト True)
        """
        super().__init__()
        self.user_prompt = user_prompt
        self.attached_files = attached_files
        self.model_assignments = model_assignments
        self.config = config
        self._cancelled = False

    def cancel(self):
        """実行キャンセル"""
        self._cancelled = True

    def run(self):
        try:
            self._execute_pipeline()
        except Exception as e:
            self.error_occurred.emit(f"オーケストレーターエラー: {str(e)}")

    def _execute_pipeline(self):
        """5Phase パイプラインの実行"""

        # ══════════════════════════════════════
        # Phase 1: Claude初回実行（CLI呼び出し 1/2）
        # ══════════════════════════════════════
        self.phase_changed.emit(1, "🧠 Claude Code 実行中（回答生成 + LLM指示文作成）...")
        phase1_output = self._run_claude_cli(
            prompt=self.user_prompt,
            system_prompt=PHASE1_SYSTEM_PROMPT,
        )
        if self._cancelled:
            return

        # Phase 1出力のパース: Claudeの回答 と LLM指示文 を分離
        result_claude, instructions = parse_phase1_output(phase1_output)

        # instructions が None → 単純な質問。Phase 2-3スキップ、Claudeの回答をそのまま返す
        if instructions is None:
            self.all_finished.emit(result_claude)
            # Phase 5: ナレッジ管理（自動保存ONの場合）
            if self.config.get("auto_knowledge", True):
                self.phase_changed.emit(5, "📚 ナレッジ管理中...")
                # KnowledgeWorkerの起動はmixAIタブ側で行う
            return

        # ══════════════════════════════════════
        # Phase 2: ローカルLLMチーム並行実行（Claude呼出なし）
        # ══════════════════════════════════════
        self.phase_changed.emit(2, "🤖 ローカルLLMチーム 並行実行中...")
        pool = ParallelWorkerPool(
            max_workers=self.config.get("max_workers", 3)
        )
        tasks = pool.build_tasks_from_instructions(
            instructions, self.model_assignments
        )

        # 開始シグナル発行
        for task in tasks:
            self.local_llm_started.emit(task.category, task.model)

        # 並行実行
        local_results = pool.execute_parallel(tasks)

        # 完了シグナル発行
        for r in local_results:
            self.local_llm_finished.emit(r.category, r.success, r.elapsed)

        if self._cancelled:
            return

        # ══════════════════════════════════════
        # Phase 3: 品質検証ループ（Claude呼出なし）
        # ══════════════════════════════════════
        self.phase_changed.emit(3, "🔍 品質検証中...")
        verifier = QualityVerifier(
            verifier_model=self.config.get("verifier_model", "nemotron-3-nano:30b"),
            max_retries=self.config.get("max_retries", 3),
        )

        refined_results = []
        for result in local_results:
            if not result.success:
                # 実行失敗した結果はそのまま通す
                refined_results.append(result)
                continue

            refined = verifier.verify_and_refine(result=result, pool=pool)
            if refined.iteration > 1:
                self.quality_retry.emit(result.category, refined.iteration)
            refined_results.append(refined)

        if self._cancelled:
            return

        # ══════════════════════════════════════
        # Phase 4: Claude比較検証＋最終統合（CLI呼び出し 2/2）
        # ══════════════════════════════════════
        self.phase_changed.emit(4, "🧠 Claude Code 最終統合中...")
        phase4_system = build_phase4_system_prompt(result_claude, refined_results)

        final_output = self._run_claude_cli(
            prompt=self.user_prompt,
            system_prompt=phase4_system,
        )

        self.all_finished.emit(final_output)

        # ══════════════════════════════════════
        # Phase 5: ナレッジ管理（バックグラウンド開始通知）
        # ══════════════════════════════════════
        if self.config.get("auto_knowledge", True):
            self.phase_changed.emit(5, "📚 ナレッジ管理中...")
            # 実際のKnowledgeWorker起動はmixAIタブ側でall_finishedシグナル後に行う

    def _run_claude_cli(self, prompt: str, system_prompt: str = None) -> str:
        """
        Claude Code CLIを非対話モードで実行。

        常に --dangerously-skip-permissions を付与し、ファイル操作を自動許可する。
        """
        cmd = [
            "claude",
            "-p",                              # 非対話（パイプ）モード
            "--dangerously-skip-permissions",   # ファイル操作の自動許可
            "--output-format", "json",          # JSON出力
            "--model", self.config.get("claude_model", "opus"),
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # 添付ファイルの内容をプロンプトに埋め込む（v5.2.0の既存ロジック踏襲）
        full_prompt = self._build_full_prompt(prompt)
        cmd.append(full_prompt)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.get("timeout", 600),
                env={**os.environ, "FORCE_COLOR": "0"},
            )

            if result.returncode == 0:
                try:
                    output_data = json.loads(result.stdout)
                    return output_data.get("result", result.stdout)
                except json.JSONDecodeError:
                    return result.stdout.strip()
            else:
                raise RuntimeError(
                    f"Claude CLI終了コード {result.returncode}: "
                    f"{result.stderr[:500] if result.stderr else 'エラー詳細なし'}"
                )

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Claude CLIがタイムアウト({self.config.get('timeout', 600)}秒)しました"
            )

    def _build_full_prompt(self, prompt: str) -> str:
        """添付ファイルがある場合、その内容をプロンプトに埋め込む"""
        if not self.attached_files:
            return prompt

        file_contents = []
        for f in self.attached_files:
            if not os.path.exists(f):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']:
                file_contents.append(f"[画像ファイル: {f}]")
            else:
                try:
                    with open(f, 'r', encoding='utf-8', errors='replace') as fp:
                        content = fp.read()
                    if len(content) > 50000:
                        content = content[:50000] + "\n\n... (ファイルが大きいため省略)"
                    file_contents.append(
                        f"--- ファイル: {f} ---\n{content}\n--- ファイル終了 ---"
                    )
                except Exception:
                    file_contents.append(f"[ファイル読み込み失敗: {f}]")

        if file_contents:
            return "\n\n".join(file_contents) + "\n\n" + prompt
        return prompt
```

### 3.9 Phase 5: ナレッジ管理

`src/knowledge/__init__.py` を空ファイルとして作成してください。

`src/knowledge/knowledge_manager.py` を以下の内容で作成してください。

```python
"""
Phase 5: ローカルLLMによる自動ナレッジ管理

会話完了後にバックグラウンドで動作し、会話内容と並行実行結果を
要約・ベクトル化してSQLite + FAISSに保存する。
Claude Codeは一切関与しない。
"""

import requests
import json
import sqlite3
from datetime import datetime
from pathlib import Path

OLLAMA_API_BASE = "http://localhost:11434/api"


class KnowledgeManager:
    """ローカルLLM専任のナレッジ管理者"""

    def __init__(
        self,
        db_path: str = "knowledge/knowledge.db",
        summary_model: str = "nemotron-3-nano:30b",
        embedding_model: str = "qwen3-embedding:4b",
    ):
        self.db_path = db_path
        self.summary_model = summary_model
        self.embedding_model = embedding_model
        self._ensure_db()

    def _ensure_db(self):
        """SQLiteデータベースとテーブルの初期化"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    topic TEXT,
                    summary TEXT,
                    keywords TEXT,
                    user_prompt TEXT,
                    has_code INTEGER DEFAULT 0,
                    has_file_ops INTEGER DEFAULT 0,
                    embedding BLOB
                )
            """)

    def process_conversation(
        self,
        user_prompt: str,
        final_response: str,
        local_results: list = None,
    ) -> dict:
        """会話と並行結果を統合してナレッジ化し保存する"""
        # 要約用テキストの構築
        conv_text = f"ユーザー: {user_prompt}\n\nClaude回答: {final_response[:2000]}"
        if local_results:
            conv_text += "\n\n--- ローカルLLM並行結果 ---\n"
            conv_text += "\n".join([
                f"[{r.category}/{r.model}]: {r.response[:300]}"
                for r in local_results if r.success
            ])

        # 常駐LLMで要約生成
        knowledge = self._generate_summary(conv_text)
        knowledge["user_prompt"] = user_prompt[:500]
        knowledge["timestamp"] = datetime.now().isoformat()

        # ベクトル化
        embedding = self._generate_embedding(
            f"{knowledge.get('topic', '')} {knowledge.get('summary', '')}"
        )

        # SQLiteに保存
        self._store(knowledge, embedding)

        return knowledge

    def _generate_summary(self, conv_text: str) -> dict:
        """常駐LLMで会話を要約"""
        prompt = f"""以下の会話を分析し、JSON形式で要約してください。

{conv_text[:3000]}

出力形式（JSONのみ出力してください）:
{{"topic":"主な話題","keywords":["キーワード1","キーワード2","キーワード3"],"summary":"50字以内の要約","has_code":false,"has_file_ops":false}}
JSON:"""
        try:
            r = requests.post(
                f"{OLLAMA_API_BASE}/generate",
                json={"model": self.summary_model, "prompt": prompt,
                      "stream": False, "format": "json"},
                timeout=120,
            )
            if r.status_code == 200:
                return json.loads(r.json().get("response", "{}"))
        except Exception:
            pass
        return {"topic": "不明", "summary": "要約生成失敗", "keywords": []}

    def _generate_embedding(self, text: str) -> list:
        """Embeddingモデルでベクトル化"""
        try:
            r = requests.post(
                f"{OLLAMA_API_BASE}/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json().get("embedding", [])
        except Exception:
            pass
        return []

    def _store(self, knowledge: dict, embedding: list):
        """SQLiteに保存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO knowledge
                       (timestamp, topic, summary, keywords, user_prompt,
                        has_code, has_file_ops, embedding)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        knowledge.get("timestamp", ""),
                        knowledge.get("topic", ""),
                        knowledge.get("summary", ""),
                        json.dumps(knowledge.get("keywords", []), ensure_ascii=False),
                        knowledge.get("user_prompt", ""),
                        int(knowledge.get("has_code", False)),
                        int(knowledge.get("has_file_ops", False)),
                        json.dumps(embedding) if embedding else None,
                    ),
                )
        except Exception:
            pass  # ナレッジ保存失敗はアプリ動作に影響させない
```

`src/knowledge/knowledge_worker.py` を以下の内容で作成してください。

```python
"""Phase 5: バックグラウンドナレッジワーカー（QThread）"""

from PyQt6.QtCore import QThread, pyqtSignal


class KnowledgeWorker(QThread):
    """会話完了後にバックグラウンドでナレッジ管理を実行するワーカー"""

    completed = pyqtSignal(dict)   # ナレッジ保存完了時
    error = pyqtSignal(str)        # エラー発生時

    def __init__(self, user_prompt: str, final_response: str,
                 local_results: list, knowledge_manager):
        super().__init__()
        self.user_prompt = user_prompt
        self.final_response = final_response
        self.local_results = local_results
        self.km = knowledge_manager

    def run(self):
        try:
            result = self.km.process_conversation(
                self.user_prompt, self.final_response, self.local_results
            )
            self.completed.emit(result)
        except Exception as e:
            self.error.emit(f"ナレッジ管理エラー: {str(e)}")
```

---

## 4. 変更B: Claude API認証の完全廃止

### 4.1 廃止の理由

Claude Maxプラン（$150/月）により、Claude Code CLIは無制限で利用可能です。API経由ではMCPツールや`--dangerously-skip-permissions`が使えないため、CLI専用化が最適です。`anthropic` Pythonパッケージは不要となります。

### 4.2 削除対象の特定方法

以下のコマンドを実行し、削除対象のコードを特定してください。

```bash
# API関連コードの検索
grep -rn "anthropic" src/ --include="*.py"
grep -rn "api_key" src/ --include="*.py"
grep -rn "API_KEY" src/ --include="*.py"
grep -rn "APIキー" src/ --include="*.py"
grep -rn "api key" src/ --include="*.py" -i
grep -rn "AuthenticationError" src/ --include="*.py"
grep -rn "APIConnectionError" src/ --include="*.py"

# 設定ファイル内のapi_key
grep -rn "api_key" config/ 2>/dev/null
```

### 4.3 削除対象一覧

上記検索結果に基づいて、以下をすべて削除してください。

一般設定タブ（ファイル名は検索で特定）から削除するもの: APIキー入力欄（QLineEdit）、APIキー保存・読み込みロジック、API接続テストボタンとそのハンドラ。

soloAI / mixAI 各タブの設定サブタブから削除するもの: API/CLI切替のQComboBoxまたはQRadioButton、API選択時の条件分岐コード。

バックエンドから削除するもの: `import anthropic` 文（すべての.pyファイル）、Claude API呼び出しモジュール（`claude_api.py`等のファイルが存在する場合はファイルごと削除）、`_call_claude_api` メソッドおよびAPI経由のモデル呼び出しコード。

設定ファイルから削除するもの: `config/app_settings.json`等の`api_key`フィールド。

依存関係から削除するもの: `requirements.txt`または`pyproject.toml`から`anthropic`パッケージ。

### 4.4 claude_executor.py のCLI専用化

`src/backends/claude_executor.py` 内にAPI/CLI分岐のif文がある場合、API分岐を完全に削除し、CLI実行パスのみを残してください。既存のCLI実行コード（subprocess呼び出し）はそのまま維持してください。soloAIタブからの利用はこの既存のclaude_executor.pyで行います。

---

## 5. 変更C: タブ構成の変更

### 5.1 チャット作成タブの完全削除

「チャット作成」タブに関連するすべてを削除します。

まず `src/tabs/` ディレクトリ内のファイルを確認し、チャット作成タブに該当するファイルを特定してください。ファイル名の候補は `chat_creator_tab.py`、`chat_create_tab.py`、`chat_draft_tab.py` 等です。特定したらファイルを削除してください。

次に `src/main_window.py` から以下を削除してください: チャット作成タブのimport文、チャット作成タブのインスタンス化コード（`self.xxx_tab = XxxTab(...)` のような行）、タブウィジェットへの追加行（`self.tab_widget.addTab(..., "チャット作成")` のような行）、チャット作成タブへの参照があるその他のコード（closeEventでのクリーンアップ等）。

チャット作成タブが独自のモデルやユーティリティファイルを持っている場合、それらも削除してください。

### 5.2 タブ順序の変更

`src/main_window.py` のaddTab呼び出し順序を変更し、mixAIタブを先頭に配置してください。

変更前（v5.2.0、4タブ）のタブ順序は soloAI(タブ0)、mixAI(タブ1)、チャット作成(タブ2)、一般設定(タブ3) です。

変更後（v6.0.0、3タブ）のタブ順序は mixAI(タブ0)、soloAI(タブ1)、一般設定(タブ2) です。

具体的なコード変更は以下の通りです（変数名はプロジェクトの実際の命名に合わせてください）。

```python
# v6.0.0: mixAIを先頭に配置、チャット作成タブ削除
self.tab_widget.addTab(self.mix_ai_tab, "mixAI")          # タブ0（先頭）
self.tab_widget.addTab(self.solo_ai_tab, "soloAI")        # タブ1
self.tab_widget.addTab(self.general_settings_tab, "一般設定")  # タブ2
```

重要: 変数名は既存コードに合わせてください。BIBLEの記録では mixAIタブは `helix_orchestrator_tab.py` / `llmmix_tab`、soloAIタブは `claude_tab.py` という名前です。実際のコードを確認してから変更してください。

---

## 6. 変更D: mixAI設定画面の刷新

### 6.1 設定画面の構成

mixAIタブの設定サブタブを以下の構成に刷新してください。既存のAPI関連設定（APIキー欄、API/CLI切替等）はすべて削除し、以下の新規設定で置き換えてください。

```
mixAI 設定サブタブ
│
├── セクション1: 📋 Claude Code設定
│   ├── モデル: [QComboBox] 選択肢: opus, sonnet, haiku
│   │   デフォルト: opus
│   ├── 思考モード: [QComboBox] 選択肢: OFF, Standard, Deep
│   │   デフォルト: OFF
│   └── タイムアウト(秒): [QSpinBox] 範囲: 60-1800
│       デフォルト: 600
│
├── セクション2: 🤖 ローカルLLMワーカー割り当て
│   ├── 検索担当: [QComboBox] Ollamaモデル一覧
│   │   デフォルト: nemotron-3-nano:30b
│   ├── レポート担当: [QComboBox] Ollamaモデル一覧
│   │   デフォルト: nemotron-3-nano:30b
│   ├── アーキテクト担当: [QComboBox] Ollamaモデル一覧
│   │   デフォルト: nemotron-3-nano:30b
│   └── コーディング担当: [QComboBox] Ollamaモデル一覧
│       デフォルト: qwen3-coder:30b
│   ※ [QPushButton: 🔄 モデル一覧更新] でOllama APIから再取得
│
├── セクション3: 🔄 品質検証設定
│   ├── 品質検証モデル: [QComboBox] Ollamaモデル一覧
│   │   デフォルト: nemotron-3-nano:30b
│   ├── 最大再試行回数: [QSpinBox] 範囲: 0-10
│   │   デフォルト: 3  ※0で品質検証ループ無効化
│   └── 並行ワーカー数: [QSpinBox] 範囲: 1-5
│       デフォルト: 3
│
├── セクション4: 📚 ナレッジ管理
│   ├── [QCheckBox] 会話完了後の自動ナレッジ保存
│   │   デフォルト: ON
│   └── DB場所: [QLabel] knowledge/knowledge.db （表示のみ）
│
└── [QPushButton: 💾 設定を保存]
    成功: ボタンテキスト → "✅ 保存しました"（緑色、2秒後リセット）
    失敗: ボタンテキスト → "❌ エラー: ..."（赤色、3秒後リセット）
```

### 6.2 Ollamaモデル一覧の動的取得

QComboBoxの選択肢をOllama APIから動的に取得するヘルパーを実装してください。

```python
def fetch_ollama_models() -> list[str]:
    """Ollama APIからインストール済みモデル名一覧を取得"""
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return sorted([m["name"] for m in models])
    except Exception:
        pass
    return []  # Ollama未起動時は空リスト
```

「🔄 モデル一覧更新」ボタン押下時にこの関数を呼び出し、全QComboBoxの選択肢を更新してください。

---

## 7. バージョン情報の更新

`src/utils/constants.py` のバージョン情報を以下に更新してください。

```python
APP_VERSION = "6.0.0"
APP_DESCRIPTION = (
    "Helix AI Studio - "
    "Claude Code常時駆動・並行ローカルLLM精度強化・自動ナレッジ管理"
)
```

---

## 8. 最終ファイル構成

変更完了後の目標ファイル構成です。★は新規作成、✗は削除、→は変更を示します。

```
HelixAIStudio/
├── HelixAIStudio.py                     （変更なし）
├── HelixAIStudio.spec                   （変更なし）
├── src/
│   ├── main_window.py                   → タブ順序変更、チャット作成削除
│   ├── tabs/
│   │   ├── helix_orchestrator_tab.py    → mixAI: 5Phase統合、設定画面刷新
│   │   ├── claude_tab.py               → soloAI: API分岐削除、CLI専用化
│   │   ├── ✗ (チャット作成タブ)         ✗ ファイル削除
│   │   └── (一般設定タブ)              → APIキー欄削除
│   ├── backends/
│   │   ├── claude_executor.py           → API分岐削除、CLI専用化
│   │   ├── ★ phase1_prompt.py          ★ 新規: Phase 1システムプロンプト
│   │   ├── ★ phase1_parser.py          ★ 新規: Phase 1出力パーサー
│   │   ├── ★ parallel_pool.py          ★ 新規: Phase 2並行実行プール
│   │   ├── ★ quality_verifier.py       ★ 新規: Phase 3品質検証ループ
│   │   ├── ★ phase4_prompt.py          ★ 新規: Phase 4統合プロンプト
│   │   ├── ★ mix_orchestrator.py       ★ 新規: 5Phase統合オーケストレーター
│   │   └── ✗ (claude_api.py等)         ✗ API呼び出しモジュール削除
│   ├── knowledge/
│   │   ├── ★ __init__.py               ★ 新規: パッケージ初期化
│   │   ├── ★ knowledge_manager.py      ★ 新規: Phase 5ナレッジ管理
│   │   └── ★ knowledge_worker.py       ★ 新規: Phase 5バックグラウンドワーカー
│   ├── claude/
│   │   └── snippet_manager.py           （変更なし）
│   ├── widgets/                          （変更なし）
│   └── utils/
│       ├── constants.py                 → バージョン 6.0.0 更新
│       └── config_manager.py            → api_key設定削除
├── config/
│   └── app_settings.json                → api_key項目削除
├── knowledge/
│   └── knowledge.db                     （自動生成）
└── BIBLE/
    └── BIBLE_Helix AI Studio_6.0.0.md   ★ 新規
```

---

## 9. 実装順序（必ずこの順序で段階的に実行）

各段階の完了後に動作確認を行い、問題がないことを確認してから次に進んでください。

### 段階1: 基盤整備（破壊的変更）

この段階ではアプリが正常に起動・動作する状態を維持しつつ、不要コードを除去します。

1. `constants.py` のバージョンを 6.0.0 に更新
2. チャット作成タブの特定と完全削除（ファイル削除 + main_window.pyからの参照除去）
3. `main_window.py` のタブ順序変更（mixAIを先頭に）
4. API関連コードの完全削除（全ファイルからanthropicパッケージ参照を除去）
5. `requirements.txt` から `anthropic` を削除
6. **動作確認**: アプリが起動し、mixAIタブが先頭に表示され、soloAIタブでCLI経由チャットが動作すること

### 段階2: 新規バックエンドモジュール作成

新しいファイルを作成します。この段階ではまだUI統合は行いません。

1. `src/backends/phase1_prompt.py` 作成
2. `src/backends/phase1_parser.py` 作成
3. `src/backends/parallel_pool.py` 作成
4. `src/backends/quality_verifier.py` 作成
5. `src/backends/phase4_prompt.py` 作成
6. `src/backends/mix_orchestrator.py` 作成
7. `src/knowledge/__init__.py` 作成
8. `src/knowledge/knowledge_manager.py` 作成
9. `src/knowledge/knowledge_worker.py` 作成

### 段階3: mixAIタブ統合

新規バックエンドをmixAIタブのUIに統合します。

1. mixAI設定サブタブの刷新（セクション6の構成に基づく）
2. mixAIチャット画面にMixAIOrchestrator統合（送信ボタン→オーケストレーター起動）
3. Phase進行状態のUI表示（ステータスバー、ラベル、またはチャットエリアへのシステムメッセージ挿入）
4. MixAIOrchestrator の各シグナル（phase_changed, local_llm_started等）をUIスロットに接続
5. all_finishedシグナル後にKnowledgeWorkerをバックグラウンド起動
6. **動作確認**: mixAIタブで送信時、Phase 1→2→3→4→5の順序で実行されること

### 段階4: ビルドと最終確認

1. PyInstallerビルド実行
2. チェックリスト（セクション10）の全項目確認
3. `BIBLE/BIBLE_Helix AI Studio_6.0.0.md` の生成

---

## 10. 受入条件チェックリスト

以下のすべてが満たされていることを確認してください。

タブ構成:
- [ ] アプリ起動時、mixAIタブが先頭（タブ0）に表示される
- [ ] soloAIタブがタブ1に表示される
- [ ] 一般設定タブがタブ2に表示される
- [ ] 「チャット作成」タブが存在しない
- [ ] チャット作成タブのPythonファイルがsrc/tabs/に存在しない

API廃止:
- [ ] 一般設定タブにAPIキー入力欄が存在しない
- [ ] soloAI/mixAIの設定にAPI/CLI切替UIが存在しない
- [ ] `grep -rn "anthropic" src/ --include="*.py"` の結果が0件
- [ ] `grep -rn "api_key" src/ --include="*.py"` の結果が0件（config読み込み除く）

soloAI動作:
- [ ] soloAIタブでClaude Code CLI経由のチャットが正常に動作する

mixAI 5Phase動作:
- [ ] 送信時、Phase進行状態がUIに表示される
- [ ] Phase 1でClaude Codeが回答＋ローカルLLM指示文JSONを出力する
- [ ] Phase 2でClaude生成の指示文に基づきローカルLLMが並行実行される
- [ ] Phase 3で品質NGの場合にプロンプト改善→再実行が行われる
- [ ] Phase 4でClaude Codeが最終統合した回答がユーザーに表示される
- [ ] 単純な質問（挨拶等）でPhase 2-3がスキップされ、Claude単独の回答が返る
- [ ] Phase 5でバックグラウンドナレッジ保存が実行される

mixAI設定:
- [ ] ローカルLLMワーカーのモデル割り当てが変更可能
- [ ] Ollamaモデル一覧が動的に取得される
- [ ] 品質検証の最大再試行回数が変更可能
- [ ] 設定保存ボタンが正常に動作する

バージョン:
- [ ] constants.pyのバージョンが6.0.0である
- [ ] PyInstallerビルドが成功する
