# Helix AI Studio v9.3.0 "Switchable Engine"
## P1/P3エンジン切替 + ローカルLLMエージェントツール + サーバー自動起動
## 実装設計書（Claude Code CLI用）

**作成日**: 2026-02-16
**前提**: v9.2.0 "Persistent Sessions" 完了済み
**想定期間**: 5-7日
**原則**: PyQt6側の変更は最小限（プルダウン追加 + 起動ボタン設置のみ）

---

## 1. v9.3.0 の全体像

```
┌─────────────────────────────────────────────────────────────┐
│                   mixAIタブ (Web / Windows)                  │
│                                                             │
│  P1/P3 エンジン: [Claude Opus 4.6        ▼]                │
│                   ├ Claude Opus 4.6  (最高性能・API)        │
│                   ├ Claude Sonnet 4.5 (高速・API)           │
│                   ├ devstral-2:123b   (ローカル・ツール対応)│
│                   └ gpt-oss:120b      (ローカル・ツール対応)│
│                                                             │
│  P2 カテゴリ別: [coding: devstral-2 ▼] [research: ...  ▼]  │
│                 (従来通り独立設定)                           │
│                                                             │
│  ┌────────────────────────────────────────┐                 │
│  │ ローカルLLMエンジン選択時:              │                 │
│  │  ✅ read_file    - ファイル読み取り     │                 │
│  │  ✅ list_dir     - ディレクトリ一覧     │                 │
│  │  ✅ search_files - ファイル検索         │                 │
│  │  ⚠️ write_file   - ファイル書き込み     │  ← 確認付き    │
│  │  ⚠️ create_file  - ファイル新規作成     │  ← 確認付き    │
│  └────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### v9.3.0 で実装する3機能:

| # | 機能 | 概要 |
|---|------|------|
| A | エンジン切替 | P1/P3をClaude CLI / ローカルLLMにプルダウンで切替（Web+Win両対応） |
| B | ローカルLLMエージェントツール | ファイル読み書き、検索をOllamaツール呼び出しで実行 |
| C | サーバー自動起動 | PyQt6アプリ内にWebサーバー起動ボタン + Windows起動時自動実行オプション |

---

## 2. 設定構造

### 2.1 config.json に追加

```json
{
  "claude_model_id": "claude-opus-4-6",
  "timeout": 1800,
  "project_dir": "C:\\Users\\tomot\\Desktop\\開発環境\\生成AIアプリ\\Helix AI Studio",
  "orchestrator_engine": "claude-opus-4-6",
  "model_assignments": {
    "coding": "devstral-2:123b",
    "research": "command-a:latest",
    "reasoning": "gpt-oss:120b",
    "vision": "gemma3:27b",
    "translation": "translategemma:27b"
  },
  "local_agent_tools": {
    "read_file": true,
    "list_dir": true,
    "search_files": true,
    "write_file": true,
    "create_file": true,
    "require_write_confirmation": true
  },
  "web_server": {
    "auto_start": false,
    "port": 8500
  }
}
```

### 2.2 orchestrator_engine の有効値

| 値 | エンジン種別 | P1/P3の実行方法 |
|----|-------------|-----------------|
| `claude-opus-4-6` | Claude CLI | `claude -p --model claude-opus-4-6` |
| `claude-opus-4-5-20250929` | Claude CLI | `claude -p --model claude-opus-4-5-20250929` |
| `claude-sonnet-4-5-20250929` | Claude CLI | `claude -p --model claude-sonnet-4-5-20250929` |
| `devstral-2:123b` | Ollama + Agent | エージェントループ + ツール呼び出し |
| `gpt-oss:120b` | Ollama + Agent | エージェントループ + ツール呼び出し |

判定ロジック: `orchestrator_engine` が `claude-` で始まる → Claude CLI、それ以外 → Ollama Agent

---

## 3. 機能A: エンジン切替

### 3.1 バックエンド: エンジン判定 (`src/web/server.py` 修正)

```python
def _is_claude_engine(engine_id: str) -> bool:
    """Claude CLIで実行すべきエンジンかどうか"""
    return engine_id.startswith("claude-")


async def _execute_p1(prompt: str, engine_id: str, project_dir: str) -> dict:
    """Phase 1を適切なエンジンで実行"""
    if _is_claude_engine(engine_id):
        return await _run_claude_cli_async(prompt, model_id=engine_id,
                                            project_dir=project_dir)
    else:
        return await _run_local_agent(prompt, model_name=engine_id,
                                       project_dir=project_dir, phase="p1")


async def _execute_p3(prompt: str, engine_id: str, project_dir: str) -> dict:
    """Phase 3を適切なエンジンで実行"""
    if _is_claude_engine(engine_id):
        return await _run_claude_cli_async(prompt, model_id=engine_id,
                                            project_dir=project_dir)
    else:
        return await _run_local_agent(prompt, model_name=engine_id,
                                       project_dir=project_dir, phase="p3")
```

### 3.2 PyQt6側: mixAIタブにエンジンプルダウン追加

**対象ファイル**: `src/tabs/llmmix_tab.py`

```python
# 既存のモデル割当セクションの上に追加

def _create_engine_selector(self) -> QWidget:
    """P1/P3エンジン選択UI"""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel("P1/P3 エンジン:")
    label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 12px; font-weight: bold;")
    layout.addWidget(label)

    self.engine_combo = QComboBox()
    self.engine_combo.setStyleSheet(COMBO_BOX_STYLE)

    # エンジン選択肢を構築
    self._engine_options = [
        ("claude-opus-4-6", "Claude Opus 4.6 (最高性能)"),
        ("claude-opus-4-5-20250929", "Claude Opus 4.5 (高品質)"),
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5 (高速)"),
    ]
    # Ollamaモデルを動的追加
    self._add_ollama_engines()

    for engine_id, display_name in self._engine_options:
        self.engine_combo.addItem(display_name, engine_id)

    # config.jsonから現在の設定を復元
    current_engine = self._load_engine_setting()
    idx = self.engine_combo.findData(current_engine)
    if idx >= 0:
        self.engine_combo.setCurrentIndex(idx)

    self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
    layout.addWidget(self.engine_combo, 1)

    # エンジン種別インジケーター
    self.engine_type_label = QLabel()
    self._update_engine_indicator(current_engine)
    layout.addWidget(self.engine_type_label)

    return container

def _add_ollama_engines(self):
    """Ollamaから大型モデル（P1/P3候補）を追加"""
    # エージェント対応モデルのリスト（関数呼び出し対応）
    agent_capable = [
        "devstral-2:123b",
        "gpt-oss:120b",
        "command-a:latest",
    ]
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            installed = {m["name"] for m in models}
            for model_name in agent_capable:
                if model_name in installed:
                    size = next((m.get("size", 0) for m in models
                                 if m["name"] == model_name), 0)
                    size_str = f"{size / (1024**3):.0f}GB" if size else ""
                    self._engine_options.append(
                        (model_name, f"{model_name} (ローカル {size_str})")
                    )
    except Exception:
        pass  # Ollama未起動時はClaude選択肢のみ

def _on_engine_changed(self, index):
    """エンジン変更時の処理"""
    engine_id = self.engine_combo.currentData()
    self._save_engine_setting(engine_id)
    self._update_engine_indicator(engine_id)

def _update_engine_indicator(self, engine_id: str):
    """エンジン種別ラベルを更新"""
    if engine_id.startswith("claude-"):
        self.engine_type_label.setText("☁️ API")
        self.engine_type_label.setStyleSheet(
            f"color: {COLORS['accent_cyan']}; font-size: 11px; padding: 2px 6px; "
            f"background-color: rgba(6, 182, 212, 0.15); border-radius: 4px;")
    else:
        self.engine_type_label.setText("🖥️ ローカル")
        self.engine_type_label.setStyleSheet(
            f"color: #10b981; font-size: 11px; padding: 2px 6px; "
            f"background-color: rgba(16, 185, 129, 0.15); border-radius: 4px;")

def _load_engine_setting(self) -> str:
    """config.jsonからエンジン設定を読み込み"""
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("orchestrator_engine", "claude-opus-4-6")
    except Exception:
        pass
    return "claude-opus-4-6"

def _save_engine_setting(self, engine_id: str):
    """config.jsonにエンジン設定を保存"""
    try:
        config_path = Path("config/config.json")
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        config["orchestrator_engine"] = engine_id
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Engine setting save failed: {e}")
```

### 3.3 Web UI: 設定画面で読み取り専用表示

v9.1.0の方針通り、Web UIでは `orchestrator_engine` を読み取り専用InfoRowで表示:

```jsx
// SettingsView.jsx に追加
<InfoRow label="P1/P3エンジン" value={settings.orchestrator_engine || 'claude-opus-4-6'} />
```

### 3.4 MixAIOrchestrator の修正 (`src/backends/mix_orchestrator.py`)

```python
def _execute_phase1(self) -> dict:
    """Phase 1: エンジンに応じた計画立案"""
    engine = self.config.get("orchestrator_engine", "claude-opus-4-6")

    if engine.startswith("claude-"):
        # 従来通りClaude CLI実行
        return self._execute_phase1_claude(engine)
    else:
        # ローカルLLMエージェント実行
        return self._execute_phase1_local(engine)

def _execute_phase1_claude(self, model_id: str) -> dict:
    """Phase 1: Claude CLI版（従来の実装）"""
    # 既存の _execute_phase1() のロジックをここに移動
    system_prompt = self._build_phase1_system_prompt()
    # ... 既存コード
    raw = self._run_claude_cli(full_prompt, model_id=model_id)
    return self._parse_phase1_output(raw)

def _execute_phase1_local(self, model_name: str) -> dict:
    """Phase 1: ローカルLLMエージェント版"""
    from .local_agent import LocalAgentRunner

    agent = LocalAgentRunner(
        model_name=model_name,
        project_dir=self.config.get("project_dir", ""),
        tools_config=self.config.get("local_agent_tools", {}),
        timeout=self.config.get("timeout", 1800),
    )

    system_prompt = self._build_phase1_system_prompt()
    user_prompt = self._build_user_prompt()

    # ローカルLLMのストリーミング出力をUIに転送
    agent.on_streaming = lambda text: self.streaming_output.emit(text)
    agent.on_tool_call = lambda tool, args: self.streaming_output.emit(
        f"\n🔧 ツール実行: {tool}({json.dumps(args, ensure_ascii=False)[:100]})\n"
    )

    result = agent.run(system_prompt, user_prompt)
    return self._parse_phase1_output(result)

# Phase 3も同様に分岐
def _execute_phase3(self, claude_answer: str, phase2_results: list) -> dict:
    engine = self.config.get("orchestrator_engine", "claude-opus-4-6")
    if engine.startswith("claude-"):
        return self._execute_phase3_claude(claude_answer, phase2_results, engine)
    else:
        return self._execute_phase3_local(claude_answer, phase2_results, engine)
```

---

## 4. 機能B: ローカルLLMエージェントツール

### 4.1 新規ファイル: `src/backends/local_agent.py`

```python
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
import glob
import logging
from pathlib import Path
from typing import Callable, Optional

import httpx

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
                return "エラー: Ollama APIからの応答がありません"

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
                func_args = tool_call["function"]["arguments"]

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

        return "警告: エージェントループが上限に達しました（最大15回のツール呼び出し）"

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
```

### 4.2 Web版のエージェント: `src/web/server.py` に追加

```python
from ..backends.local_agent import LocalAgentRunner

async def _run_local_agent(prompt: str, model_name: str,
                            project_dir: str, phase: str = "p1") -> str:
    """ローカルLLMエージェントを非同期で実行"""
    import asyncio

    config_path = Path("config/config.json")
    tools_config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        tools_config = config.get("local_agent_tools", {})

    agent = LocalAgentRunner(
        model_name=model_name,
        project_dir=project_dir,
        tools_config=tools_config,
    )

    # 書き込み確認（Web版では自動承認。将来WebSocket経由で確認UIを追加可能）
    agent.on_write_confirm = lambda tool, path, preview: True

    # ブロッキング呼び出しを別スレッドで実行
    system_prompt = _build_local_system_prompt(phase)
    result = await asyncio.to_thread(agent.run, system_prompt, prompt)
    return result


def _build_local_system_prompt(phase: str) -> str:
    """ローカルLLM用システムプロンプト"""
    if phase == "p1":
        return """あなたはソフトウェアエンジニアリングの計画立案を行うAIです。
ユーザーの質問に対して、まずプロジェクトの構造やファイルを確認し、
適切な計画を立案してください。

利用可能なツール:
- read_file: ファイルを読む
- list_dir: ディレクトリ一覧
- search_files: ファイル検索

まずプロジェクト構造を確認し、関連ファイルを読んでから回答してください。

出力は以下のJSON形式で ```json ``` で囲んでください:
{
  "claude_answer": "ユーザーへの回答（日本語）",
  "local_llm_instructions": { ... },
  "complexity": "simple|moderate|complex",
  "skip_phase2": false
}"""
    else:  # p3
        return """あなたはソフトウェアエンジニアリングの統合・レビューを行うAIです。
Phase 1の計画とPhase 2のローカルLLM実行結果を比較・統合し、
最終的な回答を生成してください。

出力は以下のJSON形式で ```json ``` で囲んでください:
{
  "status": "complete",
  "final_answer": "統合された最終回答（日本語）"
}"""
```

---

## 5. 機能C: サーバー自動起動

### 5.1 PyQt6: 設定タブのWeb UIセクション修正

**対象**: `src/tabs/settings_cortex_tab.py`

```python
def _create_web_ui_section(self) -> QGroupBox:
    """Web UIサーバー設定セクション（v9.3.0拡張）"""
    group = QGroupBox("Web UI サーバー")
    group.setStyleSheet(SECTION_CARD_STYLE)
    layout = QVBoxLayout(group)

    # 起動/停止トグルボタン
    toggle_row = QHBoxLayout()
    self.web_ui_toggle = QPushButton("▶ サーバー起動")
    self.web_ui_toggle.setCheckable(True)
    self.web_ui_toggle.setStyleSheet("""
        QPushButton {
            background-color: #059669; color: white;
            padding: 10px 20px; border-radius: 8px;
            font-size: 13px; font-weight: bold;
        }
        QPushButton:checked {
            background-color: #dc2626;
        }
    """)
    self.web_ui_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    self.web_ui_toggle.clicked.connect(self._toggle_web_server)
    toggle_row.addWidget(self.web_ui_toggle)

    self.web_ui_status_label = QLabel("停止中")
    self.web_ui_status_label.setStyleSheet(
        f"color: {COLORS['text_secondary']}; font-size: 12px;")
    toggle_row.addWidget(self.web_ui_status_label)
    toggle_row.addStretch()
    layout.addLayout(toggle_row)

    # アクセスURL表示
    self.web_ui_url_label = QLabel("")
    self.web_ui_url_label.setStyleSheet(
        f"color: {COLORS['accent_cyan']}; font-size: 12px;")
    self.web_ui_url_label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(self.web_ui_url_label)

    # 自動起動チェックボックス
    auto_row = QHBoxLayout()
    self.web_auto_start_cb = QCheckBox("アプリ起動時にサーバーを自動開始")
    self.web_auto_start_cb.setStyleSheet(
        f"color: {COLORS['text_primary']}; font-size: 12px;")
    self.web_auto_start_cb.setChecked(self._load_auto_start_setting())
    self.web_auto_start_cb.stateChanged.connect(self._save_auto_start_setting)
    auto_row.addWidget(self.web_auto_start_cb)
    auto_row.addStretch()
    layout.addLayout(auto_row)

    # ポート番号
    port_row = QHBoxLayout()
    port_label = QLabel("ポート:")
    port_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
    port_row.addWidget(port_label)
    self.web_port_spin = QSpinBox()
    self.web_port_spin.setRange(1024, 65535)
    self.web_port_spin.setValue(self._load_port_setting())
    self.web_port_spin.setStyleSheet(SPINBOX_STYLE)
    self.web_port_spin.setFixedWidth(80)
    port_row.addWidget(self.web_port_spin)
    port_row.addStretch()
    layout.addLayout(port_row)

    return group

def _toggle_web_server(self):
    """サーバー起動/停止"""
    if self.web_ui_toggle.isChecked():
        try:
            from ..web.server import start_server_background
            port = self.web_port_spin.value()
            self._web_server_thread = start_server_background(port=port)
            self.web_ui_toggle.setText("■ サーバー停止")
            self.web_ui_status_label.setText(f"稼働中 (ポート {port})")

            # Tailscale IP取得
            import subprocess
            result = subprocess.run(["tailscale", "ip", "-4"],
                                     capture_output=True, text=True, timeout=5)
            ip = result.stdout.strip() if result.returncode == 0 else "localhost"
            self.web_ui_url_label.setText(f"📱 http://{ip}:{port}")
        except Exception as e:
            self.web_ui_toggle.setChecked(False)
            self.web_ui_toggle.setText("▶ サーバー起動")
            self.web_ui_status_label.setText(f"起動失敗: {e}")
    else:
        if hasattr(self, '_web_server_thread') and self._web_server_thread:
            self._web_server_thread.stop()
            self._web_server_thread = None
        self.web_ui_toggle.setText("▶ サーバー起動")
        self.web_ui_status_label.setText("停止中")
        self.web_ui_url_label.setText("")

def _load_auto_start_setting(self) -> bool:
    """自動起動設定を読み込み"""
    try:
        with open("config/config.json", 'r') as f:
            config = json.load(f)
        return config.get("web_server", {}).get("auto_start", False)
    except Exception:
        return False

def _save_auto_start_setting(self, state):
    """自動起動設定を保存"""
    try:
        config_path = Path("config/config.json")
        config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        if "web_server" not in config:
            config["web_server"] = {}
        config["web_server"]["auto_start"] = bool(state)
        with open(config_path, 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Auto-start setting save failed: {e}")

def _load_port_setting(self) -> int:
    try:
        with open("config/config.json", 'r') as f:
            config = json.load(f)
        return config.get("web_server", {}).get("port", 8500)
    except Exception:
        return 8500
```

### 5.2 メインウィンドウ: アプリ起動時の自動サーバー開始

**対象**: `src/main_window.py` (初期化処理内に追加)

```python
def _auto_start_web_server(self):
    """config.jsonのweb_server.auto_start=trueならサーバーを自動起動"""
    try:
        with open("config/config.json", 'r') as f:
            config = json.load(f)
        if config.get("web_server", {}).get("auto_start", False):
            from .web.server import start_server_background
            port = config.get("web_server", {}).get("port", 8500)
            self._web_server_thread = start_server_background(port=port)
            logger.info(f"Web UI server auto-started on port {port}")

            # settings_cortex_tabのUIを更新
            if hasattr(self, 'settings_cortex_tab'):
                tab = self.settings_cortex_tab
                if hasattr(tab, 'web_ui_toggle'):
                    tab.web_ui_toggle.setChecked(True)
                    tab.web_ui_toggle.setText("■ サーバー停止")
                    tab.web_ui_status_label.setText(f"稼働中 (ポート {port})")
    except Exception as e:
        logger.warning(f"Web server auto-start failed: {e}")
```

---

## 6. テスト項目チェックリスト

### 機能A: エンジン切替
| # | テスト | 期待結果 |
|---|-------|---------|
| 1 | PyQt6 mixAIタブでプルダウン表示 | Claude 3種 + Ollamaモデル一覧 |
| 2 | Claude Opus 4.6選択→mixAI実行 | 従来通りClaude CLI実行 |
| 3 | Claude Sonnet 4.5選択→mixAI実行 | Sonnetモデルで実行、高速応答 |
| 4 | devstral-2:123b選択→mixAI実行 | Ollamaエージェントループで実行 |
| 5 | エンジン変更→config.json保存 | orchestrator_engineが更新 |
| 6 | Web UI設定画面 | 選択中エンジンが読み取り専用で表示 |

### 機能B: ローカルLLMエージェントツール
| # | テスト | 期待結果 |
|---|-------|---------|
| 7 | devstralでread_file実行 | 🔧 ツール実行ログがストリーミング表示 |
| 8 | devstralでlist_dir実行 | ディレクトリ一覧取得 |
| 9 | devstralでsearch_files実行 | ファイル検索結果表示 |
| 10 | devstralでwrite_file実行 | 確認ダイアログ→承認後に書き込み |
| 11 | パストラバーサル試行 | エラー「パスが不正です」 |
| 12 | 15回ツール呼び出し上限 | 「上限に達しました」メッセージ |

### 機能C: サーバー自動起動
| # | テスト | 期待結果 |
|---|-------|---------|
| 13 | 「▶ サーバー起動」ボタン | サーバー起動、Tailscale URL表示 |
| 14 | 「■ サーバー停止」ボタン | サーバー停止 |
| 15 | 「自動起動」チェック→アプリ再起動 | アプリ起動時にサーバー自動開始 |
| 16 | iPhoneから自動起動サーバーにアクセス | 正常に接続・操作可能 |

---

## 7. 新規/変更ファイルサマリー

| 種別 | ファイル | 内容 |
|------|---------|------|
| **新規** | `src/backends/local_agent.py` | ローカルLLMエージェント（ツール定義+ループ+5ツール実装） |
| **修正** | `src/backends/mix_orchestrator.py` | エンジン分岐（Claude/ローカル切替） |
| **修正** | `src/tabs/llmmix_tab.py` | エンジンプルダウン追加 |
| **修正** | `src/tabs/settings_cortex_tab.py` | サーバー起動ボタン強化 + 自動起動CB |
| **修正** | `src/main_window.py` | 自動サーバー起動処理追加 |
| **修正** | `src/web/server.py` | ローカルエージェント統合 + エンジン分岐 |
| **修正** | `src/web/api_routes.py` | orchestrator_engine読み取り対応 |
| **修正** | `frontend/src/components/SettingsView.jsx` | エンジン表示追加 |
| **変更** | `src/utils/constants.py` | v9.3.0 / "Switchable Engine" |
| **変更** | `config/config.json` | orchestrator_engine, local_agent_tools, web_server追加 |

### PyQt6への変更箇所:
- `llmmix_tab.py`: エンジンプルダウン追加
- `settings_cortex_tab.py`: サーバー起動ボタン改善 + 自動起動
- `main_window.py`: 自動起動処理（数行追加）
- `mix_orchestrator.py`: エンジン分岐ロジック
- `constants.py`: バージョン更新

---

## 8. トークン消費比較（Claude vs ローカル）

```
               P1/P3のAPIコスト    P2コスト    合計
Claude Opus:   高（~$0.05/回）     ¥0         ~$0.05/回
Claude Sonnet: 中（~$0.01/回）     ¥0         ~$0.01/回
ローカルLLM:   ¥0（電気代のみ）    ¥0         ¥0/回

月100回mixAI実行の場合:
  Opus:   ~$5.00/月
  Sonnet: ~$1.00/月
  ローカル: ¥0/月（電気代除く）
```

※ Maxプラン($150/月)はトークン課金ではなくレート制限制のため、
  実際のコスト差はレート制限回避の価値として表れる。
