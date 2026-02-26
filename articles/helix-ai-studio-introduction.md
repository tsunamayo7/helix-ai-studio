---
title: "【無料・OSS】複数AIを同時に使えるデスクトップアプリ「Helix AI Studio」を作った話"
emoji: "🧬"
type: "tech"
topics: ["ai", "python", "pyqt6", "claude", "ollama"]
published: true
---

## Claude、ChatGPT、Gemini、ローカルLLM……どれが一番いい？

答えは **「全部使う」** です。

各AIには得意分野があります。Claudeは設計と日本語、GPTはコード生成、Geminiは検索統合、ローカルLLMはプライバシー。**Helix AI Studio** はこれらを1つのアプリで統合し、5Phaseパイプラインで協調動作させます。

https://github.com/tsunamayo7/helix-ai-studio

![Helix AI Studio Demo](/images/demo_helix.gif)

## 他ツールとの比較

| 特徴 | Helix AI Studio | CLI単体ツール | ローカルLLM UI | エージェントFW |
|------|:-:|:-:|:-:|:-:|
| マルチAI協調 (5Phase) | ✅ | ❌ | ❌ | △ |
| デスクトップGUI | ✅ | ❌ | ✅ | ❌ |
| モバイルWeb UI | ✅ | ❌ | △ | ❌ |
| ローカルLLM統合 | ✅ | ❌ | ✅ | △ |
| RAG (文書検索) | ✅ | ❌ | △ | △ |
| 無料・OSS | ✅ | ✅ | ✅ | ✅ |

## 5つの主要機能

### 1. mixAI — マルチAI協調

複数AIが役割分担して1つのタスクを処理します。

1. **Phase 1** (Claude): タスク分析 → 受入基準・出力フォーマット・モデル別指示を生成
2. **Phase 2** (ローカルLLM群): コーディング・リサーチ・推論・翻訳・ビジョンの5カテゴリで並列実行
3. **Phase 3** (Claude): 統合・品質評価・リトライループ
4. **Phase 4** (オプション): ファイル変更の自動適用

### 2. cloudAI — クラウドAIチャット

Claude / ChatGPT / Gemini / Codex を統一UIで利用。APIキーを設定するだけで切替可能です。

### 3. localAI — ローカルLLMチャット

Ollama経由でローカルLLMと会話。データが外部に出ないのでプライバシー重視の用途に。

### 4. Web UI — モバイルからも操作

FastAPI + React製のWebインターフェースが内蔵。同一ネットワーク内のスマホやタブレットからもアクセスできます。

### 5. RAG — ドキュメント検索

PDFやテキストファイルをベクトル化し、会話に関連文書を自動注入します。

## データの安全性

| 接続方式 | 学習リスク | 最適な用途 |
|---------|----------|-----------|
| Anthropic API | 学習に使われない (規約明記) | 業務・機密データ |
| Claude Code CLI | 同上 (Max/Pro契約) | 開発・コーディング |
| OpenAI API | オプトアウト可 | 汎用 |
| Ollama (ローカル) | リスクゼロ (完全ローカル) | 極秘データ |
| Gemini API | Google規約に準拠 | 検索統合 |

## セットアップ (Windows)

### 前提条件

- Windows 10/11
- Python 3.12+
- NVIDIA GPU推奨 (ローカルLLM使用時)

### インストール手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# 2. 依存関係インストール
pip install -r requirements.txt

# 3. 設定ファイルを作成
copy config\config.example.json config\config.json
# config.json にAPIキーを記入

# 4. 起動
python HelixAIStudio.py
```

Web UIを使う場合:
```bash
cd frontend && npm install && npm run build && cd ..
# アプリ起動後、Settings タブで Web UI を有効化
```

## なぜ作ったか

AI時代において「どのAIを使うか」ではなく「AIをどう組み合わせるか」が重要だと考えました。各AIの強みを活かしながら弱点を補完し合う仕組みを、個人開発者でも使えるデスクトップアプリとして実現したかった。それがHelix AI Studioの出発点です。

## リンク

- **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
- **note.com記事 (詳細版)**: https://note.com/ai_tsunamayo_7/n/n410331c01ab0
