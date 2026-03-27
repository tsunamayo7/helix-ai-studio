---
title: "7つのAIを1つのUIに統合するOSSを作った — Helix AI Studio v2.0"
emoji: "🚀"
type: "tech"
topics: ["python", "ai", "fastapi", "ollama", "oss"]
published: false
---

## はじめに

AIツールが増えすぎて、タブが散らかっていませんか？

Ollama でローカル推論、Claude API で高精度な回答、Claude Code CLI でコード生成——プロバイダごとにUIが違い、会話履歴もバラバラ。RAG用のベクトルDBも別管理。この状況に疲れて、**1つのWebアプリに全部まとめるOSS**を作りました。

**Helix AI Studio v2.0** — FastAPI + WebSocket で動く軽量AIチャットスタジオです。

🔗 **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
🔗 **Live Demo**: https://helix-ai-studio.onrender.com

## 何ができるのか

![ストリーミングデモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_streaming_demo.gif)

### 7つのAIプロバイダをワンクリックで切替

Ollama / Claude API / OpenAI API / OpenAI互換(vLLM, llama.cpp) / Claude Code CLI / Codex CLI / Gemini CLI。すべて同じチャットUIから使えます。CLIツールは自動検出され、未インストールなら非表示になります。

![プロバイダ切替](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_provider_switch.gif)

### 3ステップパイプライン

```
Step 1: 計画 (Cloud/CLI) — タスク分析と計画生成
Step 2: 実行 (Local LLM)  — 計画に基づく実行
Step 3: 検証 (Cloud/CLI) — 結果の品質評価
```

CLIの高精度な推論で計画・検証し、ローカルLLMで実行する「いいとこ取り」パイプラインです。CrewAIマルチエージェントモードにも切替可能で、dev_team / research_team / writing_team の3プリセットを用意しています。

![パイプラインデモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_pipeline_demo.gif)

### RAG + Mem0 + MCP をビルトイン

- **RAGナレッジベース**: ドラッグ&ドロップでドキュメント登録。Qdrant + Ollama embeddingによるハイブリッド検索（dense + BM25 + RRF）。Docling連携でPDF/Office解析にも対応。
- **Mem0共有記憶**: 全AIツール（Claude Code, Codex, Open WebUI等）で記憶を共有。チャット時に関連記憶を自動注入。
- **MCP連携**: Model Context Protocolクライアント内蔵。stdio transportで任意のMCPサーバーと接続。

## 技術スタック

```
Backend:  FastAPI + Python 3.12 + WebSocket
Frontend: Jinja2 + Tailwind CSS + Alpine.js
DB:       SQLite (会話履歴) + Qdrant (ベクトル検索)
LLM:      Ollama (ローカル) + 各社API/CLI
```

フロントエンドにReact/Vueを使わず、**Jinja2テンプレート + Alpine.js**という軽量構成を選びました。理由はシンプルで、AIチャットアプリのUI要素はストリーミングテキスト表示が中心であり、仮想DOMの恩恵が薄いためです。Alpine.jsの`x-data`/`x-on`で十分な双方向バインディングが得られ、ビルドステップも不要になります。

WebSocket接続はFastAPIの`WebSocketEndpoint`で実装し、各プロバイダのストリーミングレスポンスを統一的にクライアントへ中継しています。CLI系プロバイダ（Claude Code等）はネイティブにストリーミング対応していないため、サブプロセスの標準出力を非同期で読み取り、疑似ストリーミングとして配信しています。

## セットアップ（3分）

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
uv sync          # 依存インストール
python run.py    # http://localhost:8504 で起動
```

Ollamaが動いていれば、この時点でローカルLLMとチャットできます。Cloud APIを使いたい場合は設定画面からAPIキーを入力するだけです。Docker Composeにも対応しています。

## 100%セルフホスト

クラウドAPIキーは**任意**です。Ollama + Qdrant だけで全機能が動作します。会話データ、ナレッジベース、記憶——すべて自分のマシンに保存されます。ベンダーロックインはありません。

![全機能ツアー](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_navigation_demo.gif)

## おわりに

Helix AI Studioは個人プロジェクトとして開発を続けています。「こういう機能がほしい」「このプロバイダに対応してほしい」といったフィードバックはGitHub Issuesで歓迎しています。

スターをいただけると開発の励みになります。

https://github.com/tsunamayo7/helix-ai-studio
