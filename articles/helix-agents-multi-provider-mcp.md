---
title: "helix-agents: Ollama / Codex / OpenAI を 1 つの MCP で扱う"
emoji: "🛠️"
type: "tech"
topics: ["mcp", "claudecode", "ollama", "codex", "python"]
published: true
---

:::message
**📌 2026-04-10 追記: helix-agent はその後も進化しています**

本記事は v0.9.0 時点 (11 ツール / 280 テスト) のマルチプロバイダ統合の解説ですが、現在は **v0.15.1 / 27 MCPツール / 347 テスト** まで拡張されています:

- **4 層コードレビューパイプライン** (gemma4 → Sonnet → Opus → Codex、`code_review` MCPツール)
- **codex_effort 制御** (none/minimal/low/medium/high/xhigh、P1≥3 で自動 xhigh)
- **parallel_tasks** (2 軸モデル選定で並列実行)
- **部門別 RAG** (`dept_search` / `dept_store`)
- **retry_guard** (リトライループ検知、`retry_guard_check`)
- **自律運用基盤** (9 デーモン + audit→dispatch→heal)

最新版: https://github.com/tsunamayo7/helix-agent
:::

`helix-agent` はもともと、Claude Code からローカル Ollama モデルへタスクを委譲するための MCP サーバーでした。

そこから発展させて、今は **helix-agents** として次の provider を 1 つの MCP で扱えるようにしています。

- `ollama`
- `codex`
- `openai-compatible`

## 何を変えたのか

単に provider を増やしただけではありません。

Claude Code で自然に使えるように、background agent の lifecycle も追加しました。

- `spawn_agent`
- `send_agent_input`
- `wait_agent`
- `list_agents`
- `close_agent`

これで、単発のツール呼び出しだけでなく、調査や実装を継続しながら進めやすくなりました。

内部の委譲方式も分けています。

- `ollama` と `openai-compatible` は内蔵 ReAct ループ
- `codex` は repo 作業向けの自律エージェント経路

## 使い分け

### Ollama

- ローカル要約
- 低コストな下書き生成
- Vision / OCR

### Codex

- repo をまたぐ実装作業
- コードレビュー
- 修正タスクの委譲

### OpenAI-compatible

- API 経由の chat model
- 標準的な chat completions 系 endpoint の利用

## 使い方の例

### Codex でレビュー

```text
think(
  task="この差分の回帰リスクを見て",
  provider="codex",
  cwd="/repo"
)
```

### Ollama でローカル要約

```text
think(
  task="このビルドログを要約して",
  provider="ollama"
)
```

### 調査用 background agent

```text
spawn_agent(
  description="flaky test 調査",
  provider="codex",
  agent_type="explorer"
)
```

続けて:

```text
send_agent_input(...)
wait_agent(...)
close_agent(...)
```

## セットアップ

```bash
git clone https://github.com/tsunamayo7/helix-agent.git
cd helix-agent
uv sync
uv run python server.py
```

Claude Code には次のように追加します。

```json
{
  "mcpServers": {
    "helix-agents": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/helix-agent", "python", "server.py"]
    }
  }
}
```

## 補足

- Codex は `codex` CLI が `PATH` に必要です
- OpenAI-compatible は API キーが必要です
- generic な OpenAI-compatible 経路は現状 text-first です
- Vision は現状 Ollama 経路が中心です

GitHub:
https://github.com/tsunamayo7/helix-agent
