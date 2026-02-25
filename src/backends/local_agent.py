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
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "ウェブを検索して最新情報を取得する。GitHub releases、公式ドキュメント、ニュース等に有効。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索クエリ（英語推奨、例: 'qwen3 coder latest release github'）"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "取得する結果の最大件数（デフォルト5、最大10）",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "指定URLのページ内容を取得する。GitHub releases page、ドキュメントページ等の詳細内容確認に使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "取得するURL（https://で始まること）"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "取得する最大文字数（デフォルト3000）",
                        "default": 3000
                    }
                },
                "required": ["url"]
            }
        }
    },
]

# v11.1.0: Browser Use ツール定義（browser_useパッケージが必要）
BROWSER_USE_TOOL = {
    "type": "function",
    "function": {
        "name": "browser_use",
        "description": "Browser Useでウェブページを自動操作してコンテンツを取得する。fetch_urlより高精度だが重い。JavaScriptレンダリングが必要なページに使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "取得するURL（https://で始まること）"
                },
                "task": {
                    "type": "string",
                    "description": "ページから取得したい情報の説明（省略可）",
                    "default": ""
                }
            },
            "required": ["url"]
        }
    }
}

# v11.3.1: localAI / mixAI search 担当 LLM 向け Web ツール使い分けガイド
LOCALAI_WEB_TOOL_GUIDE = """## Web情報取得ツールの優先順位

1. web_search(query) — URLを探す（まずここから）
2. fetch_url(url) — 静的HTMLページ取得（軽量・高速）
3. browser_use(url) — JSレンダリングページ取得（重い）

ルール:
- fetch_url で内容が取れた場合は browser_use を使わない
- browser_use は fetch_url が空や不完全だった場合のみ使う
- max_chars は 4000〜6000 を目安にトークン節約を意識する
"""

# 読み取り専用ツール（write確認不要）
READ_ONLY_TOOLS = {"read_file", "list_dir", "search_files", "web_search", "fetch_url", "browser_use"}
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

        # v10.1.0: モニターコールバック
        self.on_monitor_start: Optional[Callable[[str], None]] = None
        self.on_monitor_finish: Optional[Callable[[str, bool], None]] = None

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
        # v11.1.0: Browser Use ツールを条件付きで追加
        if self._is_browser_use_enabled():
            active.append(BROWSER_USE_TOOL)
        return active

    def _is_browser_use_enabled(self) -> bool:
        """v11.1.0: config.jsonのlocalai_browser_use_enabledとbrowser_useパッケージを確認"""
        try:
            import json as _json
            from pathlib import Path as _Path
            config_path = _Path("config/config.json")
            if not config_path.exists():
                return False
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = _json.load(f)
            if not cfg.get("localai_browser_use_enabled", False):
                return False
            import browser_use  # noqa: F401
            return True
        except Exception:
            return False

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
        # v10.1.0: モニター開始通知
        if self.on_monitor_start:
            try:
                self.on_monitor_start(self.model_name)
            except Exception as _cb_err:
                logger.debug(f"[LocalAgent] monitor_start callback error (non-fatal): {_cb_err}")

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
                result = resp.json()

                # v10.1.0: モニター完了通知
                if self.on_monitor_finish:
                    try:
                        self.on_monitor_finish(self.model_name, True)
                    except Exception as _cb_err:
                        logger.debug(f"[LocalAgent] monitor_finish callback error (non-fatal): {_cb_err}")

                return result
        except httpx.TimeoutException:
            logger.error(f"Ollama timeout ({self.timeout}s)")
            # v10.1.0: モニターエラー通知
            if self.on_monitor_finish:
                try:
                    self.on_monitor_finish(self.model_name, False)
                except Exception as _cb_err:
                    logger.debug(f"[LocalAgent] monitor_finish callback error (non-fatal): {_cb_err}")
            return None
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            # v10.1.0: モニターエラー通知
            if self.on_monitor_finish:
                try:
                    self.on_monitor_finish(self.model_name, False)
                except Exception as _cb_err:
                    logger.debug(f"[LocalAgent] monitor_finish callback error (non-fatal): {_cb_err}")
            return None

    # ═══ ツール実行 ═══

    def _execute_tool(self, name: str, args: dict) -> dict:
        """ツールを実行して結果を返す"""
        # パストラバーサル防止（path キーがある場合）
        if "path" in args:
            if not self._validate_path(args["path"]):
                return {"error": f"パスが不正です: {args['path']}"}

        # v11.2.1: list_dir の path は省略可能（空/None = project_dir）
        # "path" キーなしで呼ばれた場合にも明示的にバリデーション
        if name == "list_dir":
            list_dir_path = args.get("path") or ""
            if list_dir_path and "path" not in args:
                if not self._validate_path(list_dir_path):
                    return {"error": f"パスが不正です: {list_dir_path}"}

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
            elif name == "web_search":
                return self._tool_web_search(args["query"], args.get("max_results", 5))
            elif name == "fetch_url":
                return self._tool_fetch_url(args["url"], args.get("max_chars", 3000))
            elif name == "browser_use":
                return self._tool_browser_use(args.get("url", ""), args.get("task", ""))
            else:
                return {"error": f"未知のツール: {name}"}
        except Exception as e:
            logger.debug(f"[LocalAgent] Tool execution silent error in {name}: {e}")
            return {"error": str(e)}

    def _validate_path(self, rel_path: str) -> bool:
        """パストラバーサル防止（v11.2.1: is_relative_to 使用で str.startswith の弱点を解消）"""
        try:
            resolved = (self.project_dir / rel_path).resolve()
            base = self.project_dir.resolve()
            return resolved.is_relative_to(base)
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
                    except Exception as _read_err:
                        logger.debug(f"[LocalAgent] search: skip unreadable file {fp}: {_read_err}")

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

    def _tool_web_search(self, query: str, max_results: int = 5) -> dict:
        """v10.1.0: Brave Search API または DuckDuckGo でウェブ検索を実行"""
        import json as _json
        from pathlib import Path as _Path

        # Brave Search API キーの確認
        brave_api_key = None
        try:
            settings_path = _Path("config/general_settings.json")
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    settings = _json.load(f)
                brave_api_key = settings.get("brave_search_api_key", "")
        except Exception as _cfg_err:
            logger.debug(f"[LocalAgent] web_search: config load failed (non-fatal): {_cfg_err}")

        try:
            if brave_api_key:
                import httpx
                resp = httpx.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"Accept": "application/json", "X-Subscription-Token": brave_api_key},
                    params={"q": query, "count": min(max_results, 10)},
                    timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
                results = [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
                    for r in data.get("web", {}).get("results", [])[:max_results]
                ]
                return {"results": results, "source": "brave"}
            else:
                import httpx
                resp = httpx.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
                    timeout=15,
                    follow_redirects=True
                )
                resp.raise_for_status()
                data = resp.json()
                results = []
                for r in data.get("Results", [])[:max_results]:
                    results.append({"title": r.get("Text", ""), "url": r.get("FirstURL", ""), "snippet": ""})
                if not results and data.get("AbstractURL"):
                    results.append({"title": data.get("Heading", ""), "url": data.get("AbstractURL", ""), "snippet": data.get("Abstract", "")})
                return {"results": results, "source": "duckduckgo"}
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}"}

    def _tool_fetch_url(self, url: str, max_chars: int = 3000) -> dict:
        """v10.1.0: 指定 URL のページ内容をテキストで取得（HTML タグ除去）"""
        if not url.startswith("https://"):
            return {"error": "https:// で始まる URL のみ許可されています"}
        try:
            import httpx
            import re
            headers = {"User-Agent": "Mozilla/5.0 (compatible; HelixAI/1.0)"}
            # GitHub API の場合は PAT を自動付与
            if "api.github.com" in url:
                try:
                    from pathlib import Path as _GP
                    gs_path = _GP("config/general_settings.json")
                    if gs_path.exists():
                        import json as _gj
                        with open(gs_path, 'r') as _gf:
                            pat = _gj.load(_gf).get("github_pat", "")
                        if pat:
                            headers["Authorization"] = f"Bearer {pat}"
                except Exception as _pat_err:
                    logger.debug(f"[LocalAgent] fetch_url: PAT load failed (non-fatal): {_pat_err}")
            resp = httpx.get(url, timeout=15, follow_redirects=True, headers=headers)
            resp.raise_for_status()
            text = resp.text
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return {"content": text[:max_chars], "url": url, "truncated": len(text) > max_chars}
        except Exception as e:
            return {"error": f"URL fetch failed: {str(e)}"}

    def _tool_browser_use(self, url: str, task: str = "", max_chars: int = 6000) -> dict:
        """v11.3.1: JS レンダリング対応 URL 取得（browser-use ヘッドレスブラウザ使用）。

        LLM・API キー不要。browser-use を純粋な JS レンダリングエンジンとして使用する。
        browser-use 未インストール時は httpx にフォールバック（静的ページのみ対応）。
        失敗時は {"error": ...} を返す（例外を上位に投げない）。

        戻り値フォーマット (v11.3.1):
            method: "browser_use" | "httpx_fallback"
            url: 元リクエスト URL
            final_url: リダイレクト後 URL
            title: ページタイトル
            content: 本文テキスト（最大 max_chars 文字）
            content_truncated: bool
            fetched_at: ISO8601 UTC タイムスタンプ
            notes: "js-rendered" | "static-httpx"
        """
        if not url.startswith("https://"):
            return {"error": "https:// で始まる URL のみ許可されています"}

        import datetime
        fetched_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        max_chars = min(max_chars, 8000)  # 暴走防止

        # browser-use による JS レンダリング取得を試みる
        try:
            import asyncio
            import re
            from browser_use import Browser

            async def _async_fetch(target_url: str) -> tuple:
                """(text, final_url, title) を返す"""
                browser = Browser()
                await browser.start()
                try:
                    page = await browser.new_page(target_url)
                    await asyncio.sleep(2)  # JS レンダリング待機
                    text = await page.evaluate('() => document.body.innerText') or ""
                    title = ""
                    try:
                        title = await page.evaluate('() => document.title') or ""
                    except Exception:
                        pass
                    final_url = target_url
                    try:
                        final_url = await page.get_url() or target_url
                    except Exception:
                        pass
                    return text, final_url, title
                finally:
                    await browser.stop()

            # QThread 内でも安全な新規イベントループで実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                raw_text, final_url, title = loop.run_until_complete(_async_fetch(url))
            finally:
                loop.close()

            text = re.sub(r'\s+', ' ', raw_text).strip()
            truncated = len(text) > max_chars
            return {
                "method": "browser_use",
                "url": url,
                "final_url": final_url,
                "title": title,
                "content": text[:max_chars],
                "content_truncated": truncated,
                "fetched_at": fetched_at,
                "notes": "js-rendered",
            }

        except ImportError:
            logger.debug("browser_use not installed, falling back to httpx for URL fetch")
        except Exception as e:
            logger.warning(f"browser_use fetch failed for {url}: {e}, falling back to httpx")

        # httpx フォールバック（静的ページ用）
        try:
            import httpx
            import re
            headers = {"User-Agent": "Mozilla/5.0 (compatible; HelixAI/1.0)"}
            resp = httpx.get(url, timeout=20, follow_redirects=True, headers=headers)
            resp.raise_for_status()
            final_url = str(resp.url)
            text = resp.text
            # title 抽出
            title = ""
            title_match = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            # HTML 除去
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            truncated = len(text) > max_chars
            return {
                "method": "httpx_fallback",
                "url": url,
                "final_url": final_url,
                "title": title,
                "content": text[:max_chars],
                "content_truncated": truncated,
                "fetched_at": fetched_at,
                "notes": "static-httpx",
            }
        except Exception as e:
            return {"error": f"URL fetch failed (browser_use + httpx): {str(e)}"}
