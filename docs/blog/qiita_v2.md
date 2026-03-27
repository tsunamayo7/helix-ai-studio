<!--
title: 7つのAIプロバイダーを1画面で切り替え — Helix AI Studio v2.0を作った
tags: Python, AI, FastAPI, Ollama, 個人開発
-->

# 7つのAIプロバイダーを1画面で切り替え — Helix AI Studio v2.0を作った

## この記事で分かること

- 7つのAIプロバイダー（Ollama / Claude / OpenAI / vLLM / Claude Code CLI / Codex CLI / Gemini CLI）を1つのUIで切り替える方法
- FastAPI + WebSocketでストリーミングチャットを実装する構成
- RAG・共有記憶・MCPを1アプリに統合するアーキテクチャ

**GitHub**: https://github.com/tsunamayo7/helix-ai-studio
**Live Demo**: https://helix-ai-studio.onrender.com

## 背景：AIツールが増えすぎた問題

ローカルLLMはOllama、高精度タスクはClaude API、コード生成はClaude Code CLI——AIプロバイダーごとにUIが違い、会話履歴も分散します。RAG用のベクトルDBやMCPサーバーも別管理。

この「ツール散在問題」を解決するために、**Helix AI Studio v2.0**を作りました。

![ストリーミングデモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_streaming_demo.gif)

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| Backend | FastAPI + Python 3.12 + WebSocket |
| Frontend | Jinja2 + Tailwind CSS + Alpine.js |
| DB | SQLite（会話履歴）+ Qdrant（ベクトル検索） |
| LLM | Ollama（ローカル）+ 各社API/CLI |

## 主要機能と実装のポイント

### 1. 7プロバイダー統一アクセス

![プロバイダ切替](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_provider_switch.gif)

各プロバイダーは共通インターフェースで抽象化しています。ユーザーがUIでプロバイダーを選択すると、対応するハンドラーが呼ばれ、WebSocket経由でストリーミングレスポンスを返します。

CLI系（Claude Code / Codex / Gemini）はサブプロセスとして起動し、stdoutを非同期で読み取って疑似ストリーミングに変換しています。CLIの存在はシステム起動時に自動検出され、未インストールならUIから非表示になります。

### 2. 3ステップパイプライン

![パイプラインデモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_pipeline_demo.gif)

```
Step 1: 計画 (Cloud/CLI) → タスク分析と計画生成
Step 2: 実行 (Local LLM)  → 計画に基づく実行
Step 3: 検証 (Cloud/CLI) → 品質評価とフィードバック
```

高精度なモデルで計画・検証し、ローカルLLMで実行するハイブリッド構成です。各ステップのプロバイダーとモデルは個別に設定できます。CrewAIマルチエージェントモードでは、dev_team / research_team / writing_teamの3プリセットから選択可能です。

### 3. RAGナレッジベース

- ドラッグ&ドロップでドキュメント登録（25+形式対応）
- **ハイブリッド検索**: denseベクトル + BM25スパース + RRF（Reciprocal Rank Fusion）
- **Docling連携**: PDF・Office（docx/pptx/xlsx）の構造化パース
- **TEI Reranker**: bge-reranker-v2-m3による再スコアリング
- Ollama embedding（qwen3-embedding:8b）でAPI費用ゼロ

### 4. Mem0共有記憶

Qdrantベースの共有記憶をビルトイン。Claude Code、Codex CLI、Open WebUIなど複数のAIツール間で記憶を共有できます。チャット時に関連記憶が自動で注入されます。

### 5. MCP連携

Model Context Protocolクライアントを内蔵。stdio transportで外部MCPサーバーと接続し、ツール検出・実行を行います。設定画面からサーバーの追加・起動・停止が可能です。

## セットアップ手順

```bash
# 1. クローン
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# 2. 依存インストール（uvを使用）
uv sync

# 3. 起動
python run.py
# → http://localhost:8504 でアクセス
```

Ollamaが動いていれば、すぐにローカルLLMとチャットできます。Cloud APIを使う場合は設定画面でキーを入力するだけです。

```bash
# Docker Composeでも起動可能
docker compose up -d
```

![全機能ツアー](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_navigation_demo.gif)

## 100%セルフホスト対応

クラウドAPIキーは**任意**です。Ollama + Qdrant の構成で全機能がローカルで動作します。会話データもナレッジベースも自分のマシンに保存され、外部にデータが出ません。

## まとめ

Helix AI Studioは「AIツールの散在」を1つのWebアプリで解決することを目指しています。個人プロジェクトとして開発中ですが、GitHubでスターやIssueをいただけると大変励みになります。

https://github.com/tsunamayo7/helix-ai-studio
