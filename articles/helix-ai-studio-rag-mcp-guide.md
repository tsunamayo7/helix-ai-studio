---
title: "RAGとMCPで広がるAIチャットの可能性──Helix AI Studioの実装ガイド"
emoji: "🔧"
type: "tech"
topics: ["python", "rag", "mcp", "fastapi", "ai"]
published: true
---

## はじめに

AIチャットアプリを作るとき、単純にAPIを叩くだけでは物足りなくなる瞬間がある。「自分のドキュメントを読ませたい」「外部ツールを使わせたい」──そういった要望に応えるのがRAG（Retrieval-Augmented Generation）とMCP（Model Context Protocol）だ。

この記事では、筆者が開発しているオープンソースのAIチャットアプリ「Helix AI Studio」でのRAGとMCPの実装について、設計思想と具体的な実装方法を解説する。

**リポジトリ**: https://github.com/tsunamayo7/helix-ai-studio
**ライブデモ**: https://helix-ai-studio.onrender.com

## Helix AI Studioの概要

Helix AI Studioは、7つのAIプロバイダー（OpenAI・Claude・Gemini・Cohere・Groq・Perplexity・OpenRouter）に対応したセルフホスト型のチャットアプリケーションだ。

主な技術スタック:

- **バックエンド**: Python / FastAPI
- **フロントエンド**: HTML / CSS / JavaScript
- **データベース**: SQLite（チャット履歴） + ChromaDB（ベクトル検索）
- **デプロイ**: Docker / Render

## RAGの実装

### アーキテクチャ

RAGの処理フローは以下の通りだ。

1. ドキュメントのアップロード（PDF・テキスト対応）
2. テキストの抽出とチャンク分割
3. 埋め込みベクトルの生成
4. ChromaDBへのインデックス保存
5. ユーザークエリに対するベクトル類似検索
6. 関連チャンクをコンテキストとしてプロンプトに注入
7. AIモデルによる回答生成

### チャンク分割の設計

ドキュメントを適切なサイズに分割することは、RAGの精度に直結する。Helix AI Studioでは以下のアプローチを採用している。

- チャンクサイズ: 段落単位を基本に、長すぎる場合は文単位で分割
- オーバーラップ: 前後のチャンクと一部重複させて文脈の断絶を防止
- メタデータ: ファイル名・ページ番号などを各チャンクに付与

### ChromaDBの活用

ベクトルデータベースとしてChromaDBを採用した理由は、軽量でセットアップが簡単なこと、そしてPythonとの親和性が高いことだ。SQLiteベースなので、追加のインフラが不要という点も個人開発には嬉しい。

## MCPの実装

### Model Context Protocolとは

MCPはAnthropicが提唱するプロトコルで、AIモデルが外部ツールと対話するための標準的な仕組みだ。これにより、AIが単なるテキスト生成を超えて実際のアクションを実行できるようになる。

### Helix AI StudioでのMCP統合

対応しているツール操作の例:

- **ファイルシステム**: ファイルの読み書き・一覧取得
- **Web検索**: インターネット上の情報をリアルタイムに取得
- **データベース**: PostgreSQLなどへのクエリ実行
- **Git操作**: リポジトリの状態確認やコミット

### MCPサーバーの設定

MCPツールの追加は設定画面から行える。サーバーのURL（またはローカルパス）を指定するだけで、利用可能なツールが自動的に検出される。

## Mem0によるメモリ機能

RAGやMCPと並んで重要なのが、会話をまたいだ記憶機能だ。Mem0ライブラリを統合することで、ユーザーの好みやコンテキストをセッション間で保持できる。

これにより「前回の会話で言ったこと」をAIが覚えていてくれるため、毎回コンテキストを説明し直す必要がなくなる。

## セットアップ方法

### Dockerの場合

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
docker compose up -d
```

### ローカル環境の場合

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
pip install -r requirements.txt
python main.py
```

### Renderへのデプロイ

READMEの「Deploy to Render」ボタンからワンクリックでデプロイ可能だ。

## まとめ

RAGとMCPを組み合わせることで、AIチャットアプリは「質問に答えるだけ」の存在から「知識を持ち、行動できる」存在へと進化する。Helix AI Studioはこれらの機能をオープンソースで提供しているので、ぜひ試してみてほしい。

フィードバックやコントリビューションは、GitHubのIssueやDiscussionで受け付けている。
