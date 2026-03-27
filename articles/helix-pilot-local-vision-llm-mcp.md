---
title: "ローカル Vision LLM でデスクトップを AI に操作させる MCP サーバーを作った"
emoji: "🖥️"
type: "tech"
topics: ["mcp", "claudecode", "ollama", "python", "windows"]
published: true
---

Claude Code でブラウザ操作はできる。でも **Premiere Pro** や **Excel**、**メモ帳** は？

既存の GUI 自動化ツールを調べると、こんな状況でした:

- **Peekaboo**: MCP + Ollama 対応だが **macOS 専用**
- **Cua**: クロスプラットフォームだが **VM 内操作**（ホスト OS を直接触れない）
- **UI-TARS Desktop**: ByteDance 製、MCP 対応だが **CLI ネイティブではない**
- **Computer Use 系**: **クラウド API 必須**（GPT-4V: $0.01/画像、1 日 100 回で月 $30）

**「Windows + ローカル完結 + MCP ネイティブ」の組み合わせが空白地帯だった。** だから作りました。

## helix-pilot とは

**ローカルの Ollama Vision LLM を使って、Windows デスクトップを AI エージェントが直接操作する MCP サーバー**です。

![Architecture](https://raw.githubusercontent.com/tsunamayo7/helix-pilot/main/docs/demo/architecture.png)

**主な特徴:**

| 特徴 | 詳細 |
|------|------|
| 100% ローカル | Ollama で完結、API 費用ゼロ、データ外部送信なし |
| Windows ネイティブ | Win32 API で直接操作（VM でもコンテナでもない） |
| MCP ネイティブ | Claude Code / Codex CLI / Cursor からすぐ使える |
| 15 個のツール | screenshot, click, type, find, auto, browse 等 |
| 安全設計 | 緊急停止、シークレット検出、ウィンドウ拒否リスト |

## デモ: MCP ツール呼び出しの流れ

![MCP Demo](https://raw.githubusercontent.com/tsunamayo7/helix-pilot/main/docs/demo/mcp_tools_demo.gif)

`status()` でシステム確認 → `screenshot()` で画面キャプチャ → `describe()` で Vision LLM 解析 → `auto()` で自律実行。全てローカルの Ollama で処理されます。

## なぜローカル Vision LLM なのか

**コスト**: クラウド Vision API は 1 リクエストごとに課金。helix-pilot は Ollama で **完全無料**。

**プライバシー**: 画面のスクリーンショットには機密情報が含まれる可能性がある。ローカルなら **データが PC の外に出ない**。

**レイテンシ**: ローカル推論は 1-3 秒。クラウドは 5-10 秒 + ネットワーク遅延。

**対応モデル:**

| モデル | サイズ | 特徴 |
|--------|--------|------|
| `mistral-small3.2` | 24B | バランス型、座標推定精度が高い |
| `gemma3:27b` | 27B | Google 製、日本語にも強い |
| `llava` | 7B-34B | 軽量で高速、VRAM 4GB から動作 |
| `moondream` | 1.8B | 超軽量、CPU でも動作可能 |

## クイックスタート（3 ステップ）

### 1. Vision モデルをインストール

```bash
ollama pull mistral-small3.2
```

### 2. helix-pilot をクローン

```bash
git clone https://github.com/tsunamayo7/helix-pilot.git
cd helix-pilot
uv sync
```

### 3. Claude Code に接続

`.claude.json` に追加:

```json
{
  "mcpServers": {
    "helix-pilot": {
      "command": "uv",
      "args": ["--directory", "/path/to/helix-pilot", "run", "server.py"]
    }
  }
}
```

これだけで Claude Code から `screenshot()`, `click()`, `auto()` 等の 15 個のツールが使えるようになります。

## 安全設計 — GUI 自動化に必須

AI にデスクトップ操作させるなら安全機構は必須です。helix-pilot は 6 層の安全機構を実装:

1. **緊急停止**: マウスを画面隅に移動するだけで即座に停止
2. **シークレット検出**: `sk-...`, `ghp_...` 等の API キーの入力を自動ブロック
3. **ウィンドウ拒否リスト**: Task Manager、Windows Security 等への操作を禁止
4. **アクション検証**: LLM が生成した操作計画を実行前に安全チェック
5. **ポリシー制御**: `observe_only` → `draft_only` → `apply_with_approval` の段階実行
6. **ユーザー操作検知**: ユーザーが PC を使用中は自動的に一時停止

## 競合との比較

| 機能 | helix-pilot | terminator | UI-TARS | Peekaboo | Cua |
|------|:-----------:|:----------:|:-------:|:--------:|:---:|
| MCP サーバー | **Yes** | No | Partial | Yes | No |
| Windows ホスト直接操作 | **Yes** | Yes | Yes | No (macOS) | No (VM) |
| ローカル Vision LLM | **Yes** | No | No | Yes | No |
| クラウド API 不要 | **Yes** | No | No | **Yes** | No |
| 安全機構 | **Yes** | Partial | No | No | Partial |
| OSS (MIT) | **Yes** | Yes | Yes | Yes | Yes |

## まとめ

helix-pilot は「**ローカルで、安全に、MCP 経由で Windows デスクトップを AI に操作させる**」ための MCP サーバーです。

- クラウド API 不要 — Ollama でローカル完結
- Claude Code / Codex CLI / Cursor から即座に利用可能
- 安全設計 — 緊急停止、シークレット検出、段階的実行モード

GitHub で MIT ライセンスで公開しています。試してフィードバックいただけると嬉しいです。

https://github.com/tsunamayo7/helix-pilot

---

*この記事は [helix-pilot v1.0.0](https://github.com/tsunamayo7/helix-pilot/releases/tag/v1.0.0) に基づいています。*
