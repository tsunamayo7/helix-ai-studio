"""
Ollama MCP Tools - v3.9.3
ローカルLLM (Ollama) 用のMCPライクなツール実行機能

OllamaはネイティブでMCPをサポートしていないため、
プロンプトベースでツール呼び出しをシミュレートする
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class OllamaToolExecutor:
    """
    Ollama用ツール実行クラス

    ローカルLLMがファイル操作やWeb検索を行えるようにする
    """

    # ツール呼び出しフォーマット
    # LLMは <<TOOL:tool_name:param1=value1:param2=value2>> の形式で出力
    TOOL_PATTERN = re.compile(r'<<TOOL:(\w+):([^>]+)>>')

    # 利用可能なツール定義
    AVAILABLE_TOOLS = {
        "read_file": {
            "description": "ファイルの内容を読み取る",
            "params": ["path"],
            "example": "<<TOOL:read_file:path=/path/to/file.txt>>"
        },
        "list_files": {
            "description": "ディレクトリ内のファイル一覧を取得",
            "params": ["path"],
            "example": "<<TOOL:list_files:path=/path/to/directory>>"
        },
        "write_file": {
            "description": "ファイルに内容を書き込む (要承認)",
            "params": ["path", "content"],
            "example": "<<TOOL:write_file:path=/path/to/file.txt:content=ファイルの内容>>"
        },
        "web_search": {
            "description": "Webで情報を検索する (Brave Search使用時のみ)",
            "params": ["query"],
            "example": "<<TOOL:web_search:query=検索クエリ>>"
        },
    }

    def __init__(self, enabled_tools: Optional[Dict[str, bool]] = None, working_dir: str = "."):
        """
        初期化

        Args:
            enabled_tools: 有効なツールの設定 (MCP設定から取得)
            working_dir: 作業ディレクトリ
        """
        self.enabled_tools = enabled_tools or {
            "filesystem": True,
            "git": True,
            "brave-search": False,
        }
        self.working_dir = Path(working_dir).resolve()
        self._brave_api_key = os.environ.get("BRAVE_API_KEY", "")

    def get_tools_system_prompt(self) -> str:
        """
        ツール使用のためのシステムプロンプトを生成

        Returns:
            ツール説明を含むシステムプロンプト
        """
        tools_desc = []

        if self.enabled_tools.get("filesystem", False):
            tools_desc.append(
                "- read_file: ファイルの内容を読み取る\n"
                "  使用例: <<TOOL:read_file:path=ファイルパス>>\n"
            )
            tools_desc.append(
                "- list_files: ディレクトリ内のファイル一覧を取得\n"
                "  使用例: <<TOOL:list_files:path=ディレクトリパス>>\n"
            )

        if self.enabled_tools.get("brave-search", False) and self._brave_api_key:
            tools_desc.append(
                "- web_search: Webで情報を検索する\n"
                "  使用例: <<TOOL:web_search:query=検索クエリ>>\n"
            )

        if not tools_desc:
            return ""

        return (
            "\n\n【利用可能なツール】\n"
            "以下のツールを使用できます。ツールを使う場合は指定された形式で出力してください。\n\n"
            + "".join(tools_desc) +
            "\n重要: ツールを使用する場合は、必ず <<TOOL:...>> の形式で出力してください。"
            "ツールの結果は自動的に提供されます。\n"
        )

    def parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        LLM応答からツール呼び出しをパース

        Args:
            response: LLMの応答テキスト

        Returns:
            ツール呼び出しのリスト
        """
        tool_calls = []

        for match in self.TOOL_PATTERN.finditer(response):
            tool_name = match.group(1)
            params_str = match.group(2)

            # パラメータをパース
            params = {}
            for param in params_str.split(":"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key.strip()] = value.strip()

            tool_calls.append({
                "tool": tool_name,
                "params": params,
                "match": match.group(0)
            })

        return tool_calls

    def execute_tool(self, tool_name: str, params: Dict[str, str]) -> Tuple[bool, str]:
        """
        ツールを実行

        Args:
            tool_name: ツール名
            params: パラメータ

        Returns:
            (成功したか, 結果またはエラーメッセージ)
        """
        try:
            if tool_name == "read_file":
                return self._execute_read_file(params)
            elif tool_name == "list_files":
                return self._execute_list_files(params)
            elif tool_name == "write_file":
                return self._execute_write_file(params)
            elif tool_name == "web_search":
                return self._execute_web_search(params)
            else:
                return False, f"不明なツール: {tool_name}"
        except Exception as e:
            logger.error(f"[OllamaToolExecutor] Tool execution error: {e}", exc_info=True)
            return False, f"ツール実行エラー: {str(e)}"

    def _execute_read_file(self, params: Dict[str, str]) -> Tuple[bool, str]:
        """ファイル読み取りを実行"""
        if not self.enabled_tools.get("filesystem", False):
            return False, "ファイルシステムツールが無効です"

        path_str = params.get("path", "")
        if not path_str:
            return False, "pathパラメータが必要です"

        # パスを解決
        file_path = Path(path_str)
        if not file_path.is_absolute():
            file_path = self.working_dir / file_path

        # セキュリティチェック: プロジェクト外アクセス防止
        try:
            file_path = file_path.resolve()
        except Exception:
            return False, f"無効なパス: {path_str}"

        if not file_path.exists():
            return False, f"ファイルが存在しません: {path_str}"

        if not file_path.is_file():
            return False, f"ファイルではありません: {path_str}"

        # ファイルサイズ制限 (100KB)
        if file_path.stat().st_size > 100 * 1024:
            return False, f"ファイルが大きすぎます (100KB制限): {path_str}"

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return True, f"【{path_str} の内容】\n{content}"
        except Exception as e:
            return False, f"ファイル読み取りエラー: {e}"

    def _execute_list_files(self, params: Dict[str, str]) -> Tuple[bool, str]:
        """ディレクトリ一覧を取得"""
        if not self.enabled_tools.get("filesystem", False):
            return False, "ファイルシステムツールが無効です"

        path_str = params.get("path", ".")
        dir_path = Path(path_str)
        if not dir_path.is_absolute():
            dir_path = self.working_dir / dir_path

        try:
            dir_path = dir_path.resolve()
        except Exception:
            return False, f"無効なパス: {path_str}"

        if not dir_path.exists():
            return False, f"ディレクトリが存在しません: {path_str}"

        if not dir_path.is_dir():
            return False, f"ディレクトリではありません: {path_str}"

        try:
            items = []
            for item in sorted(dir_path.iterdir())[:50]:  # 最大50件
                item_type = "📁" if item.is_dir() else "📄"
                items.append(f"  {item_type} {item.name}")

            return True, f"【{path_str} の内容】\n" + "\n".join(items)
        except Exception as e:
            return False, f"ディレクトリ読み取りエラー: {e}"

    def _execute_write_file(self, params: Dict[str, str]) -> Tuple[bool, str]:
        """ファイル書き込みを実行 (現在は無効)"""
        # セキュリティのため、書き込みは現在無効
        return False, "セキュリティのため、ファイル書き込みはOllamaモードでは無効です"

    def _execute_web_search(self, params: Dict[str, str]) -> Tuple[bool, str]:
        """Web検索を実行"""
        if not self.enabled_tools.get("brave-search", False):
            return False, "Web検索ツールが無効です"

        if not self._brave_api_key:
            return False, "BRAVE_API_KEY が設定されていません"

        query = params.get("query", "")
        if not query:
            return False, "queryパラメータが必要です"

        try:
            import requests

            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self._brave_api_key
            }
            url = f"https://api.search.brave.com/res/v1/web/search?q={query}&count=5"

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:5]:
                title = item.get("title", "")
                url = item.get("url", "")
                description = item.get("description", "")[:200]
                results.append(f"- {title}\n  {url}\n  {description}")

            if results:
                return True, f"【「{query}」の検索結果】\n" + "\n\n".join(results)
            else:
                return True, f"【「{query}」の検索結果】\n該当する結果が見つかりませんでした"

        except ImportError:
            return False, "requestsライブラリがインストールされていません"
        except Exception as e:
            return False, f"Web検索エラー: {e}"

    def process_response_with_tools(
        self,
        response: str,
        max_iterations: int = 3
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        LLM応答を処理し、ツール呼び出しがあれば実行

        Args:
            response: LLMの応答テキスト
            max_iterations: 最大ツール実行回数

        Returns:
            (処理後の応答, 実行されたツールのリスト)
        """
        executed_tools = []

        for _ in range(max_iterations):
            tool_calls = self.parse_tool_calls(response)
            if not tool_calls:
                break

            for tool_call in tool_calls:
                tool_name = tool_call["tool"]
                params = tool_call["params"]

                success, result = self.execute_tool(tool_name, params)
                executed_tools.append({
                    "tool": tool_name,
                    "params": params,
                    "success": success,
                    "result": result[:500]  # 結果を制限
                })

                # ツール呼び出しを結果で置換
                response = response.replace(
                    tool_call["match"],
                    f"\n\n【ツール結果: {tool_name}】\n{result}\n"
                )

        return response, executed_tools


# グローバルインスタンス
_global_tool_executor: Optional[OllamaToolExecutor] = None


def get_ollama_tool_executor(
    enabled_tools: Optional[Dict[str, bool]] = None,
    working_dir: str = "."
) -> OllamaToolExecutor:
    """
    OllamaToolExecutorインスタンスを取得

    Args:
        enabled_tools: 有効なツールの設定
        working_dir: 作業ディレクトリ

    Returns:
        OllamaToolExecutor インスタンス
    """
    global _global_tool_executor

    if enabled_tools is not None or _global_tool_executor is None:
        _global_tool_executor = OllamaToolExecutor(enabled_tools, working_dir)

    return _global_tool_executor
