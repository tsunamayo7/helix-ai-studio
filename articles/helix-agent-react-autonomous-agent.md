---
title: "ローカル LLM を自律エージェントにした — Claude Code から呼べる ReAct MCP サーバー"
emoji: "🧠"
type: "tech"
topics: ["mcp", "claudecode", "ollama", "python", "agent"]
published: true
---

ローカルの Ollama モデルに「ファイルを読んで」「コマンドを実行して」と頼んだら、自分で考えて動いてくれる。そんな仕組みを作りました。

## 何ができるようになったか

[helix-agent](https://github.com/tsunamayo7/helix-agent) v0.4.0 で、ローカル LLM が **自律的にツールを使いながら推論する ReAct エージェント** になりました。

具体例を見てください。

```
タスク: 「pyproject.toml を読んで、プロジェクトの概要を教えて」

Step 1: 「ファイルを読む必要がある」 → read_file 実行
Step 2: ファイル内容を分析 → 「v0.4.0, 依存: fastmcp + httpx」と回答
✅ 2ステップで完了
```

LLM が自分で「何をすべきか」を考え、ツールを呼び出し、結果を見て次の行動を決める。これが ReAct（Reasoning + Acting）パターンです。

## 従来との違い

従来の helix-agent は「質問を送ったらテキストが返ってくる」だけでした。

```
従来: ユーザー → Claude Code → helix-agent → LLM「回答」→ 終わり
今回: ユーザー → Claude Code → helix-agent → LLM → ツール実行 → 観察 → 再推論 → ... → 回答
```

つまり、**考えて、動いて、結果を見て、また考える**。これがエージェントです。

## 使えるツール

エージェントが自律的に呼び出せるツールは 7 種類です。

| ツール | できること |
|--------|-----------|
| `read_file` | ファイルを読む |
| `write_file` | ファイルに書き込む |
| `list_files` | ディレクトリ内のファイル一覧 |
| `search_in_file` | ファイル内を正規表現で検索 |
| `run_command` | シェルコマンド実行（git, python, uv, ollama のみ） |
| `calculate` | 数式を計算 |
| `search_memory` | Qdrant で過去の知識を検索 |

## セキュリティ: PathGuard

エージェントにファイル操作を任せるのは怖い、と思うかもしれません。PathGuard がそこを守ります。

**やっていること:**

1. **ディレクトリ許可リスト** — 指定フォルダ以外にはアクセスできない
2. **機密ファイルブロック** — `.env`、`credentials`、SSH 鍵などは自動的にブロック
3. **パストラバーサル防止** — `../../` でシステムフォルダに到達しようとする攻撃を防ぐ
4. **コマンド制限** — `git`, `python`, `uv`, `ollama` 以外のコマンドは実行不可

```python
# これは通る
read_file("C:/Development/tools/helix-agent/README.md")

# これはブロックされる
read_file("C:/Users/tomot/.ssh/id_rsa")  # → PermissionError
read_file("C:/Windows/System32/config")   # → PermissionError
```

## セットアップ

2 分で完了します。

### 1. Ollama でモデルを用意

```bash
ollama pull gemma3
```

お好みで大型モデルも追加できます（`ollama pull nemotron-cascade-2` など）。helix-agent が自動で最適なモデルを選びます。

### 2. helix-agent をインストール

```bash
git clone https://github.com/tsunamayo7/helix-agent.git
cd helix-agent
uv sync
```

### 3. Claude Code に登録

`~/.claude/settings.json` に以下を追加してください。

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

`/path/to/helix-agent` はクローンしたディレクトリの絶対パスに置き換えてください。

これだけです。Claude Code を再起動すれば使えます。

## 実際に使ってみる

Claude Code で以下のように話しかけるだけです。

**単発の推論:**
```
「helix-agent で、この関数のバグを見つけて」
→ think ツールが自動選択される
```

**エージェントモード:**
```
「helix-agent の agent で、src ディレクトリの Python ファイルを調べて構成を教えて」
→ agent_task が list_files → read_file → 分析 → 回答
```

**ベンチマーク:**
```
「helix-agent で models benchmark を実行して」
→ 全モデルをテストし、スコアランキングを表示
```

## 技術的な仕組み

### なぜネイティブ Function Calling ではなく ReAct なのか

Ollama のネイティブ `tools` API は一部のモデル（Llama 3.1 など）しか対応していません。さらに Qwen3.5 では重大なバグが報告されています。

helix-agent は **プロンプトベースの ReAct** を採用しています。JSON 出力を強制することで、どのモデルでも同じように動きます。

```json
{"thought": "ファイルを読む必要がある", "action": "read_file", "action_input": "pyproject.toml"}
```

この方式のメリット:
- **全 Ollama モデルで動作**（モデル依存なし）
- **推論過程が可視化**される（thought フィールド）
- **デバッグが容易**

### 自動モデル選択 + ベンチマーク

v0.3.0 で追加したローカルベンチマーク機能は健在です。エージェントモードでも、タスクに最適なモデルが自動的に選ばれます。

## まとめ

| バージョン | できること |
|-----------|-----------|
| v0.1.0 | モデル自動選択で推論 |
| v0.2.0 | メタデータでルーティング精度向上 |
| v0.3.0 | ローカルベンチマーク + モデルオーバーライド |
| **v0.4.0** | **ReAct エージェント + ファイル操作 + PathGuard** |

ローカル LLM が「テキストを返すだけ」から「自分で考えて行動するエージェント」に進化しました。API 費用ゼロで。

GitHub: https://github.com/tsunamayo7/helix-agent

144 テスト通過、MIT ライセンスです。
