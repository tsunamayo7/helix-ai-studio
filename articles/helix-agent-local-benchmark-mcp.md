---
title: "Claude Code の API トークンを節約する MCP サーバーを作った — ローカル Ollama モデルに自動委譲"
emoji: "🤖"
type: "tech"
topics: ["mcp", "claudecode", "ollama", "python", "locallm"]
published: true
---

:::message
**📌 2026-04-10 追記: helix-agent はその後も大きく進化しています**

本記事は v0.3.0 / 82 テストの最古参の初出記事ですが、現在は **v0.15.1 / 347 テスト / 27 MCPツール / 7 本 OSS** に拡張されています:

- **4 層コードレビューパイプライン** (gemma4 → Sonnet → Opus → Codex)
- **parallel_tasks** (2 軸モデル選定で並列実行)
- **codex_effort 制御** + 自動 xhigh エスカレーション
- **部門別 RAG** (`dept_search` / `dept_store`)
- **自律運用基盤** (9 デーモン + audit→dispatch→heal)
- **retry_guard** (リトライループ検知)

最新版: https://github.com/tsunamayo7/helix-agent
:::

Claude Code を使っていると、API トークンの消費が気になりませんか？

ログ解析、コードレビュー、要約 — これらのタスクは毎回 Claude の API を叩いています。でも **ローカルの Ollama モデルで十分な作業**も多いはず。

そこで **helix-agent** を作りました。

## helix-agent とは

Claude Code のタスクを**ローカルの Ollama モデルに自動委譲**する MCP サーバーです。

```
ユーザー → Claude Code → helix-agent → ローカル LLM（ドラフト生成）
                                              ↓
                                        Claude が検証・強化
                                              ↓
                                        高品質な最終回答
```

**ポイント:**
- ローカル LLM が重い処理を担当（トークン消費ゼロ）
- Claude が最終検証（最小限のトークン）
- ユーザーは常に Claude 品質の回答を受け取る

## 他ツールとの違い

| 特徴 | helix-agent | PAL MCP | OllamaClaude |
|------|:-----------:|:-------:|:------------:|
| コンテキスト消費 | **<5%** | ~50% | ~2% |
| モデル自動選択 | **Yes** | Yes | フォールバックのみ |
| ローカルベンチマーク | **Yes** | No | No |
| Vision 対応 | **Yes** | モデル依存 | No |
| 設定ゼロ起動 | **Yes** | No | 一部 |

PAL MCP はコンテキストの約 50% を消費します。helix-agent は **5% 以下**。

## v0.3.0: ローカルベンチマーク

最新版の目玉機能は**ローカルベンチマーク**です。

ユーザーの実機で 8 種のテストを実行し、モデルの実力を数値化します:

| カテゴリ | テスト内容 |
|----------|-----------|
| コード生成 | FizzBuzz、文字列操作 |
| 推論 | 論理パズル、計算 |
| 指示追従 | JSON 出力、リスト形式 |
| 日本語 | 翻訳、要約 |
| 速度 | tokens/sec |

```python
# 未評価モデルを一括テスト
models(action="benchmark")

# ランキング確認
models(action="benchmark_status")
```

結果は `~/.helix-agent/benchmarks.json` にキャッシュされ、**ルーティングの優先度に自動反映**されます。

## 自動ルーティングの仕組み

```
タスク: 「この Python 関数のバグを探して」
  ↓
キーワード検出: "関数", "バグ" → CODE 能力
  ↓
モデル絞り込み: CODE 能力を持つモデルを抽出
  ↓
ベンチマークスコア + サイズ優先度でソート
  ↓
選択: qwen-coder:7b（スコア: 92/100）
```

ルーティングの判断基準:
1. **ローカルベンチマークスコア** — 実機での性能データ
2. **名前パターンマッチ** — モデル名から能力を推定
3. **サイズ優先** — quality モードでは大型モデルを優先
4. **既知モデルブースト** — 実績あるモデルに加点

## モデルオーバーライド

自動選択が合わない場合は、特定モデルに固定できます:

```python
# 全タスクを qwen3.5:122b に固定
models(action="use", model_name="qwen3.5:122b")

# 自動選択に戻す
models(action="use_auto")
```

## セットアップ（2 分）

```bash
# 1. Ollama でモデルを用意
ollama pull gemma3

# 2. クローンとインストール
git clone https://github.com/tsunamayo7/helix-agent.git
cd helix-agent && uv sync
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

これだけで、Claude Code がローカルモデルを使い始めます。

## 技術スタック

- **Python 3.12+** / uv
- **FastMCP** — MCP サーバー実装
- **httpx** — Ollama API 通信
- 依存は最小限（FastMCP + httpx のみ）
- 執筆時テスト 82 個パス (現在は v0.15.1 / **347 テスト** / 27 MCPツール)

## まとめ

helix-agent は「Claude Code のトークン節約」という実用的な問題を解決する MCP サーバーです。

- **設定ゼロ** — `uv run` で即起動
- **自動ルーティング** — タスクに最適なモデルを自動選択
- **ローカルベンチマーク** — 実機の性能データでルーティング最適化
- **品質優先** — ローカル LLM はドラフト、Claude が最終検証

GitHub: https://github.com/tsunamayo7/helix-agent

MIT ライセンス。Star をいただけると励みになります。

## 関連プロジェクト

- [helix-pilot](https://github.com/tsunamayo7/helix-pilot) — ローカル Vision LLM で Windows デスクトップを操作する MCP サーバー
- [Helix AI Studio](https://github.com/tsunamayo7/helix-ai-studio) — 7 プロバイダー統合のセルフホスト型 AI チャットアプリ
