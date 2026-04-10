---
title: "Claude Code のリトライループで Max quota が19分で消えた話と MCP で止める方法"
emoji: "🛡️"
type: "tech"
topics: ["claudecode", "mcp", "python", "ollama", "個人開発"]
published: true
---

:::message
**📌 2026-04-10 追記: helix-agent はその後も進化しています**

本記事執筆時のバージョンは v0.11.0 / 308 テストでしたが、現在は **v0.15.1 / 347 テスト / 27 MCPツール** です。`retry_guard_check` / `retry_guard_status` / `retry_guard_reset` は標準搭載のまま、以下が追加されています:

- **4 層コードレビューパイプライン** (gemma4 → Sonnet → Opus → Codex)
- **parallel_tasks** (並列タスク実行)
- **部門別 RAG** (`dept_search` / `dept_store`)
- **自律運用基盤** (9 デーモン + audit→dispatch→heal)

最新版: https://github.com/tsunamayo7/helix-agent
:::

## はじめに

Claude Code の Opus を使っていて、**Max plan の5時間分クォータが19分で消える**という現象を体験した方はいないでしょうか。原因の大半は、Claude が同じツールを同じ引数で延々と呼び続けるリトライループです。

この記事では、その現象への対策として作った MCP サーバー **[helix-agent](https://github.com/tsunamayo7/helix-agent)** の `retry_guard` について紹介します。

## 課題: Claude Code の隠れたトークン喰い

### 実際に報告されている現象

Anthropic は2026年3月末、[公式に「ユーザーが想定より早くクォータを消費している」と認めました](https://www.theregister.com/2026/03/31/anthropic_claude_code_limits/)。MacRumors の記事では、Max プラン加入者が[5時間のクォータを19分で使い切った事例](https://www.macrumors.com/2026/03/26/claude-code-users-rapid-rate-limit-drain-bug/)が紹介されています。

### 原因の一つは「リトライループ」

GitHub issue [anthropics/claude-code#41659](https://github.com/anthropics/claude-code/issues/41659) に記録されている通り、Opus は**エラーを誤読すると同じツール呼び出しを同じ引数で延々と繰り返す**ことがあります。ユーザーが「違う方法を試して」と割り込んでも無視されるケースすら報告されています。

1回のツール呼び出しで数千〜数万トークン消費するため、ループが30-50回続くと、5時間のクォータが数十分で溶けます。

### 公式の対応

現時点で Claude Code にはビルトインのループ検知機能がありません。コミュニティの best practice は「自分で PreToolUse hook を書く」です。しかしそれでは個人開発者ごとに車輪の再発明が発生します。

## 既存ツールとの差別化

MCP 関連のトークン削減ツールは既にいくつか存在します:

| ツール | アプローチ | カバー範囲 |
|---|---|---|
| Claude Code Tool Search（公式） | MCPスキーマをオンデマンド読み込み | セッション起動時の66Kトークン削減 |
| token-optimizer-mcp (ooples) | Brotli圧縮+SQLiteキャッシュ | メッセージ履歴の再圧縮 |
| OmniParser系 MCP | ローカル vision で画面解析 | スクリーンショット15Kトークン削減 |
| **helix-agent (本記事)** | **リトライループ検知** | **エージェントランタイムのループ防止** |

既存ツールは「情報を圧縮する」方向の最適化で、helix-agent の `retry_guard` は「無駄な呼び出しを起こさせない」方向で、レイヤーが異なります。

## retry_guard の仕組み

### シンプルな設計

```python
retry_guard_check(tool_name="navigate", args={"url": "..."})
# → {
#   "loop_detected": true,
#   "repeat_count": 3,
#   "recommendation": "Tool 'navigate' called 3 times with identical args.
#                      Likely stuck in retry loop. Vary args or escalate to Opus."
# }
```

内部処理:
1. `(tool_name, sorted_args)` を JSON 化して SHA1 でハッシュ化
2. セッション毎の履歴に `(hash, timestamp)` を追加
3. 時間窓（デフォルト300秒）で古い記録をプルーニング
4. 同一ハッシュが閾値（デフォルト3回）以上なら警告

**LLM 不要・純ロジックで sub-millisecond** で動きます。

### 3つのツール

| ツール | 役割 |
|---|---|
| `retry_guard_check` | ツール呼び出し前にループ検知 |
| `retry_guard_status` | セッション統計（呼び出し総数・ユニーク数・最大反復数） |
| `retry_guard_reset` | ループ解消後の履歴クリア |

### 実装（抜粋）

```python
class RetryGuard:
    def __init__(self, threshold: int = 3, window_seconds: int = 300):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._history: dict[str, list[tuple[str, float]]] = defaultdict(list)

    @staticmethod
    def _hash_call(tool_name: str, args: Any) -> str:
        payload = json.dumps({"t": tool_name, "a": args}, sort_keys=True, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    def check(self, tool_name, args, session_id="default"):
        now = time.time()
        self._prune(session_id, now)
        h = self._hash_call(tool_name, args)
        self._history[session_id].append((h, now))
        count = sum(1 for (x, _) in self._history[session_id] if x == h)
        return {
            "loop_detected": count >= self.threshold,
            "repeat_count": count,
            "recommendation": self._build_recommendation(tool_name, count),
        }
```

全体で約100行、テストは28件書いています。

## おまけ機能: 日本語ユーザー向け拡張

v0.11.0 では日本語ユーザー向けに2つの機能を追加しました。

### vision_compress / dom_compress

ローカルの gemma4:31b を使って、スクリーンショットや HTML を Claude に渡す前に圧縮します:

- **vision_compress**: 15,000 トークンのスクリーンショット → 400 トークンの JSON 要約
- **dom_compress**: 114,000 トークンの HTML → 500 トークンの構造化抽出

### helix-agent-ja-input

Claude Code のターミナルは React Ink で作られており、IME との相性が悪く、Windows で日本語を打つと**文字重複・カーソルずれ・変換中 Enter で暴発**等の問題が発生します（[Zenn の詳細解説記事](https://zenn.dev/atu4403/articles/claudecode-japanese-input-solution)）。

macOS には [Prompt Line](https://qiita.com/nkmr_jp/items/c0dd480d320fc333e60a) という対策アプリがありますが、Windows には対応していません。そこで tkinter（標準ライブラリ）だけで Windows 向けフローティング入力ウィンドウを書きました:

```bash
uv run helix-agent-ja-input
```

起動すると小さな常に最前面のウィンドウが開き、OS ネイティブ IME で日本語を普通に入力できます。`Ctrl+Enter` でクリップボードにコピーされ、Claude Code ターミナルで `Ctrl+V` すれば完了です。

依存パッケージゼロ・Python 標準ライブラリのみで動きます。

## セットアップ

```bash
git clone https://github.com/tsunamayo7/helix-agent.git
cd helix-agent
uv sync
```

`~/.claude/settings.json` に追加:

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

Claude Code を再起動すれば `retry_guard_check` が使えるようになります。

日本語入力ヘルパー単独で使う場合:

```bash
uv run helix-agent-ja-input
```

## まとめ

helix-agent v0.11.0 は Claude Code のリトライループ問題を直接解決する MCP サーバーです。

- **retry_guard** — ループ検知、純ロジック、LLM不要
- **vision_compress / dom_compress** — ローカル gemma4 でトークン圧縮
- **helix-agent-ja-input** — Windows 日本語入力問題を解決

MIT ライセンス・執筆時 308 テスト通過 (現在は v0.15.1 / **347 テスト**)。

フィードバック（特に retry_guard が見逃したループ事例）歓迎します。

GitHub: https://github.com/tsunamayo7/helix-agent

---

:::message
本記事の retry_guard は、Claude Code 内蔵の loop detection ではなく外付け MCP サーバーとしての実装です。Anthropic の将来の公式実装と重複・統合される可能性がある点にご留意ください。
:::
