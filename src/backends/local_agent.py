"""
Helix AI Studio - ローカルLLMエージェントランナー (v9.3.0)

Ollama APIのツール呼び出し機能を使い、ファイル操作を含む
エージェントループを実行する。Claude CLIの代替として機能。

対応ツール:
  - read_file: ファイル読み取り
  - list_dir: ディレクトリ一覧
  - search_files: ファイル名/内容検索
  - write_file: ファイル書き込み（確認付き）
  - create_file: ファイル新規作成（確認付き）
"""

import json
import os
import logging
from pathlib import Path
from typing import Callable, Optional

import httpx

from ..utils.i18n import t

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"
MAX_AGENT_LOOPS = 15          # 最大ツール呼び出し回数
MAX_FILE_READ_SIZE = 512_000  # 500KB
MAX_SEARCH_RESULTS = 20


# ═══════════════════════════════════════════════════════════════
# ツール定義（Ollama API tools パラメータ形式）
# ═══════════════════════════════════════════════════════════════

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "ファイルの内容を読み取る。テキストファイルのみ対応。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "読み取るファイルのパス（プロジェクトルートからの相対パス）"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "ディレクトリの内容一覧を取得する。ファイル名、サイズ、種別を返す。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "一覧取得するディレクトリのパス（プロジェクトルートからの相対パス、空文字でルート）"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "ファイル名またはファイル内容をキーワード検索する。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード"
                    },
                    "search_content": {
                        "type": "boolean",
                        "description": "trueでファイル内容も検索、falseでファイル名のみ"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "既存ファイルの内容を上書き保存する。テキストファイルのみ。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "書き込むファイルのパス"
                    },
                    "content": {
                        "type": "string",
                        "description": "書き込む内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "新規ファイルを作成する。親ディレクトリが存在しない場合は自動作成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "作成するファイルのパス"
                    },
                    "content": {
                        "type": "string",
                        "description": "ファイルの内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
]

# 読み取り専用ツール（write確認不要）
READ_ONLY_TOOLS = {"read_file", "list_dir", "search_files"}
WRITE_TOOLS = {"write_file", "create_file"}

# 除外ディレクトリ
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'dist',
                 'build', '.next', '.cache', 'data'}


class LocalAgentRunner:
    """ローカルLLMによるエージェントループ実行"""

    def __init__(self, model_name: str, project_dir: str,
                 tools_config: dict = None,
                 ollama_host: str = OLLAMA_HOST,
                 timeout: int = 1800):
        self.model_name = model_name
        self.project_dir = Path(project_dir) if project_dir else Path(".")
        self.tools_config = tools_config or {}
        self.ollama_host = ollama_host
        self.timeout = timeout

        # コールバック
        self.on_streaming: Optional[Callable[[str], None]] = None
        self.on_tool_call: Optional[Callable[[str, dict], None]] = None
        self.on_write_confirm: Optional[Callable[[str, str, str], bool]] = None

        # 書き込み確認が必要かどうか
        self.require_write_confirmation = self.tools_config.get(
            "require_write_confirmation", True)

        # 利用可能ツールをフィルタ
        self._active_tools = self._build_active_tools()

        # ツール実行ログ
        self.tool_log: list[dict] = []

    def _build_active_tools(self) -> list:
        """設定に基づいて有効なツールをフィルタ"""
        active = []
        for tool in AGENT_TOOLS:
            tool_name = tool["function"]["name"]
            if self.tools_config.get(tool_name, True):
                active.append(tool)
        return active

    # ═══ メインエージェントループ ═══

    def run(self, system_prompt: str, user_prompt: str) -> str:
        """
        エージェントループを実行。

        1. LLMにプロンプト + ツール定義を送信
        2. LLMがツール呼び出しを返した場合 → ツール実行 → 結果をLLMに返す
        3. LLMがテキスト応答を返した場合 → 完了

        Returns:
            最終的なテキスト応答
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for loop_count in range(MAX_AGENT_LOOPS):
            response = self._call_ollama_chat(messages)

            if not response:
                return t('desktop.backends.agentNoResponse')

            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])

            # テキスト応答がある場合はストリーミング出力
            if message.get("content"):
                if self.on_streaming:
                    self.on_streaming(message["content"])

            # ツール呼び出しがない場合 → 完了
            if not tool_calls:
                return message.get("content", "")

            # ツール呼び出しを処理
            messages.append(message)  # アシスタントメッセージを追加

            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                func_args = tool_call["function"].get("arguments", {})

                # コールバック通知
                if self.on_tool_call:
                    self.on_tool_call(func_name, func_args)

                # ツール実行
                result = self._execute_tool(func_name, func_args)

                # ログ記録
                self.tool_log.append({
                    "tool": func_name,
                    "args": func_args,
                    "result_length": len(str(result)),
                    "loop": loop_count,
                })

                # ツール結果をメッセージに追加
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return t('desktop.backends.agentLoopLimit')

    # ═══ Ollama API呼び出し ═══

    def _call_ollama_chat(self, messages: list) -> dict | None:
        """Ollama Chat API（ツール対応）を呼び出し"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.ollama_host}/api/chat",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "tools": self._active_tools,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "num_predict": 8192,
                        },
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.error(f"Ollama timeout ({self.timeout}s)")
            return None
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return None

    # ═══ ツール実行 ═══

    def _execute_tool(self, name: str, args: dict) -> dict:
        """ツールを実行して結果を返す"""
        # パストラバーサル防止
        if "path" in args:
            if not self._validate_path(args["path"]):
                return {"error": f"パスが不正です: {args['path']}"}

        try:
            if name == "read_file":
                return self._tool_read_file(args["path"])
            elif name == "list_dir":
                return self._tool_list_dir(args.get("path", ""))
            elif name == "search_files":
                return self._tool_search_files(
                    args["query"], args.get("search_content", False))
            elif name == "write_file":
                return self._tool_write_file(args["path"], args["content"])
            elif name == "create_file":
                return self._tool_create_file(args["path"], args["content"])
            else:
                return {"error": f"未知のツール: {name}"}
        except Exception as e:
            return {"error": str(e)}

    def _validate_path(self, rel_path: str) -> bool:
        """パストラバーサル防止"""
        try:
            target = (self.project_dir / rel_path).resolve()
            return str(target).startswith(str(self.project_dir.resolve()))
        except Exception:
            return False

    # ═══ 各ツール実装 ═══

    def _tool_read_file(self, rel_path: str) -> dict:
        """ファイル読み取り"""
        target = self.project_dir / rel_path
        if not target.is_file():
            return {"error": f"ファイルが見つかりません: {rel_path}"}
        if target.stat().st_size > MAX_FILE_READ_SIZE:
            return {"error": f"ファイルが大きすぎます: {target.stat().st_size} bytes (上限 500KB)"}
        try:
            content = target.read_text(encoding='utf-8', errors='replace')
            return {"content": content, "path": rel_path,
                    "size": len(content), "lines": content.count('\n') + 1}
        except Exception as e:
            return {"error": f"読み取りエラー: {e}"}

    def _tool_list_dir(self, rel_path: str) -> dict:
        """ディレクトリ一覧"""
        target = self.project_dir / rel_path if rel_path else self.project_dir
        if not target.is_dir():
            return {"error": f"ディレクトリが見つかりません: {rel_path}"}
        items = []
        try:
            for entry in sorted(target.iterdir()):
                if entry.name in EXCLUDED_DIRS or entry.name.startswith('.'):
                    continue
                items.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                    "extension": entry.suffix if entry.is_file() else None,
                })
            return {"path": rel_path or ".", "items": items, "count": len(items)}
        except Exception as e:
            return {"error": str(e)}

    def _tool_search_files(self, query: str, search_content: bool = False) -> dict:
        """ファイル検索"""
        results = []
        query_lower = query.lower()

        for root, dirs, files in os.walk(self.project_dir):
            # 除外ディレクトリをスキップ
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]

            for filename in files:
                if len(results) >= MAX_SEARCH_RESULTS:
                    break

                filepath = Path(root) / filename
                rel_path = str(filepath.relative_to(self.project_dir))

                # ファイル名検索
                if query_lower in filename.lower():
                    results.append({"path": rel_path, "match_type": "filename"})
                    continue

                # 内容検索
                if search_content and filepath.suffix in {'.py', '.js', '.jsx', '.ts',
                    '.tsx', '.json', '.md', '.txt', '.html', '.css', '.yaml', '.toml'}:
                    try:
                        if filepath.stat().st_size > MAX_FILE_READ_SIZE:
                            continue
                        content = filepath.read_text(encoding='utf-8', errors='ignore')
                        if query_lower in content.lower():
                            # マッチ行を抽出
                            for i, line in enumerate(content.split('\n'), 1):
                                if query_lower in line.lower():
                                    results.append({
                                        "path": rel_path,
                                        "match_type": "content",
                                        "line": i,
                                        "context": line.strip()[:200],
                                    })
                                    break
                    except Exception:
                        pass

        return {"query": query, "results": results, "count": len(results)}

    def _tool_write_file(self, rel_path: str, content: str) -> dict:
        """ファイル書き込み（確認付き）"""
        target = self.project_dir / rel_path
        if not target.is_file():
            return {"error": f"ファイルが存在しません: {rel_path}（新規作成はcreate_fileを使用）"}

        # 書き込み確認
        if self.require_write_confirmation and self.on_write_confirm:
            approved = self.on_write_confirm("write_file", rel_path, content[:500])
            if not approved:
                return {"status": "cancelled", "message": "ユーザーがキャンセルしました"}

        try:
            target.write_text(content, encoding='utf-8')
            return {"status": "ok", "path": rel_path, "size": len(content)}
        except Exception as e:
            return {"error": f"書き込みエラー: {e}"}

    def _tool_create_file(self, rel_path: str, content: str) -> dict:
        """ファイル新規作成（確認付き）"""
        target = self.project_dir / rel_path
        if target.exists():
            return {"error": f"ファイルが既に存在します: {rel_path}（上書きはwrite_fileを使用）"}

        # 書き込み確認
        if self.require_write_confirmation and self.on_write_confirm:
            approved = self.on_write_confirm("create_file", rel_path, content[:500])
            if not approved:
                return {"status": "cancelled", "message": "ユーザーがキャンセルしました"}

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
            return {"status": "ok", "path": rel_path, "size": len(content)}
        except Exception as e:
            return {"error": f"作成エラー: {e}"}
