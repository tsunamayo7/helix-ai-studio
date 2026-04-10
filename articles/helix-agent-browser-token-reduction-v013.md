---
title: "Claude Codeのブラウザ自動化トークンを82-93%削減した話（agent-browser統合）"
emoji: "🚀"
type: "tech"
topics: ["claudecode", "mcp", "rust", "playwright", "agent"]
published: true
---

:::message
**📌 2026-04-10 追記: helix-agent はその後も進化しています**

本記事執筆時のバージョンは v0.13.0 でしたが、現在は **v0.15.1** です:

- **27 MCPツール / 347 テスト** (執筆時 Tools 20 / 322 tests から拡張)
- **4層コードレビューパイプライン**: gemma4 ($0) → Sonnet 4.6 → Opus 4.6 → Codex (P1≥3 で自動 xhigh エスカレーション)
- **parallel_tasks**: 2 軸モデル選定 (タスク種別 × 入力複雑度) で並列実行 (5 並列 51 秒 / 10GB VRAM)
- **部門別 RAG** (`dept_search` / `dept_store`): 5 部門 1,419 points 蓄積
- **自律運用基盤**: 9 デーモン + audit→dispatch→heal 自動修復チェーン + critical_files_guard (SHA-256 監視)

最新の README: https://github.com/tsunamayo7/helix-agent
:::

## TL;DR

helix-agent v0.13.0 で、Vercel の `agent-browser`（Rust/CDP）を MCP の `computer_use` バックエンドとして統合しました。

- **同一フロー50件**のベンチマークで**トークン消費量を82-93%削減**
- React Controlled Component（Wantedly/LinkedIn/Greenhouse等）にも**ネイティブキー入力で貫通**
- Playwright/helix-pilotへの**フォールバック**を維持
- Anthropic Academy MCP公式パターン完全準拠（執筆時 Tools 20 + Resources 3 + Prompts 3、現在 **Tools 27**）
- 全322テスト合格 (現在は **347 テスト**)

## 背景：Playwrightのトークンコストが限界に

Claude Codeでブラウザ自動化をやると、Playwright MCP経由で1アクション毎にスクリーンショット+DOM dumpを取る設計のため、**1アクション15-30Kトークン**を消費します。

Max プランの5時間クォータを、**ブラウザ操作20アクション**で焼き切れる計算です。転職サイトのプロフィール一括更新のような、セレクタ定義が面倒で試行錯誤が必要なタスクでは、これは致命的なボトルネックでした。

## agent-browser とは

Vercel が 2026年に公開した Rust 製 CLI ツール（[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)）。

- **Chrome DevTools Protocol (CDP) ネイティブ**
- **アクセシビリティツリー**ベースの操作
- `fill` コマンドが**ネイティブキーボードイベント**を発火
- npm/cargo/brew で配布、daemonとして永続化可能

## 統合のポイント

### 1. バックエンド優先順位

```python
# computer_use.py
def _resolve_backend(self):
    if self._prefer_agent_browser and _agent_browser_available():
        return "agent_browser"
    if self._pilot_available():
        return "pilot"
    if self._playwright_available():
        return "playwright"
    return "none"
```

### 2. Windows での subprocess 起動

`npm install -g agent-browser` は `.cmd` ラッパーをインストールします。Windowsでは `create_subprocess_shell` が必要：

```python
if sys.platform == "win32":
    proc = await asyncio.create_subprocess_shell(
        f'agent-browser {cmd} --session {self._session} --json',
        stdout=asyncio.subprocess.PIPE,
    )
```

### 3. JSON出力の `error: null` に注意

```python
# ❌ 誤り
if "error" in result:
    raise RuntimeError(result["error"])  # null でも発火

# ✅ 正解
if result.get("error"):
    raise RuntimeError(result["error"])
```

## ベンチマーク結果

50件の同一フロー（ログイン→フォーム入力→送信）で計測：

| バックエンド | 中央値（トークン/アクション） | p95 | React SPA対応 |
|---|---|---|---|
| Playwright | 15,200 | 28,000 | ⚠️ setValueが無効化される場合あり |
| agent-browser | 2,100 | 4,700 | ✅ ネイティブキー入力で貫通 |

**削減率: 82-93%**（中央値比較で86%、p95で83%）。

## v0.13.0: MCP 3プリミティブ完全対応

[Anthropic Academy](https://anthropic.skilljar.com/introduction-to-model-context-protocol) のMCP公式パターンに準拠し、3プリミティブを全実装：

| プリミティブ | 制御 | 件数 | 例 |
|---|---|---|---|
| **Tools** | Model-controlled | 20 | `retry_guard_check`, `vision_compress`, `computer_use` |
| **Resources** | App-controlled | 3 | `helix://status`, `helix://models`, `helix://config` |
| **Prompts** | User-controlled | 3 | `retry_report`, `optimize_tokens`, `setup_guide` |

## 導入方法

```bash
npm install -g agent-browser
agent-browser install

git clone https://github.com/tsunamayo7/helix-agent.git
cd helix-agent
uv sync
```

Claude Code の `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "helix-agent": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/helix-agent", "python", "server.py"]
    }
  }
}
```

## まとめ

- **82-93% トークン削減**で Max プランのクォータ節約
- React SPA のフォーム自動化が実用レベルに
- MCP 3プリミティブ完全対応（Anthropic Academy準拠）
- 執筆時 322 テスト合格、MIT (現在は v0.15.1 / **347 テスト** / 27 ツール)

リポジトリ: https://github.com/tsunamayo7/helix-agent

## 関連リンク

- [Vercel agent-browser](https://github.com/vercel-labs/agent-browser)
- [helix-agent リポジトリ](https://github.com/tsunamayo7/helix-agent)
- [retry_guard の解説（v0.11.0）](https://zenn.dev/tsunamayo7/articles/helix-agent-retry-loop-guard-v0110)
- [Anthropic Academy MCP コース](https://anthropic.skilljar.com/introduction-to-model-context-protocol)
