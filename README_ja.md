<!-- SPDX-FileCopyrightText: 2026 Helix AI Studio Contributors -->
<!-- SPDX-License-Identifier: MIT -->

# Helix AI Studio

**Claude中心のマルチモデルAIオーケストレーション デュアルインターフェースアプリ (Desktop + Web)**
Claude Code CLIを「頭脳」、ローカルLLM（Ollama）を「専門チーム」として配置 — Cyberpunk Minimal GUIとクロスデバイスWeb UIで統合。

![Version](https://img.shields.io/badge/version-11.9.1-00d4ff)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![i18n](https://img.shields.io/badge/i18n-ja%20%7C%20en-emerald)

> English README: [README.md](README.md)

> 🧩 **目的**: クラウドAI（Claude）の強みを活かしながら、ローカルLLMの得意分野（軽量推論、常駐・監視機能）を分離・併用して、回答品質と再現性を底上げする。

---

## 動作概要

Helix AI Studioは **3+1Phaseパイプライン** で動作します：

1. **Phase 1 (Claude Code CLI)** — 設計分析 → 各ローカルモデルへの構造化指示書を生成
2. **Phase 2 (ローカルLLMチーム / Ollama, 順次実行)** — 専門カテゴリ別に実行 (coding / research / reasoning / translation / vision)
3. **Phase 3 (Claude Code CLI)** — 統合、Acceptance Criteria (PASS/FAIL) で検証・最終回答を生成
4. **Phase 4（オプション）** — Sonnet 4.6/4.5がPhase 3の構造化出力からファイル変更を適用

このアプローチは、複数の視点を統合することで回答品質を向上させつつ、**VRAM負荷の高い120Bクラスモデル**（順次実行）にも対応します。

---

## なぜ Helix なのか？

| | Helix AI Studio | CLIコーディングエージェント¹ | ローカルLLM UI² | エージェントFW³ |
|---|---|---|---|---|
| **Claudeがオーケストレーター** | ✅ 計画立案＋品質検証 | ✅ コーディング特化 | ❌ | 構成次第 |
| **ローカルLLMがワーカー** | ✅ 多角的検証 | ❌ | ✅ 推論のみ | 構成次第 |
| **デスクトップ＋Web デュアルUI** | ✅ DB/設定共有 | ❌ | 一部 | ❌ |
| **BIBLEファースト** | ✅ 自動注入 | ❌ | ❌ | ❌ |
| **すぐ使える（コード不要）** | ✅ アプリとして完結 | ❌ | ✅ | ❌ コード必要 |

¹ OpenCode, Aider, Cline — コーディングタスクに特化、単一モデル中心
² OpenWebUI, AnythingLLM, LM Studio — ローカル推論UIとして優秀、オーケストレーション機能なし
³ CrewAI, LangGraph, AutoGen — 強力なフレームワーク、ただしエージェントロジックを自分で書く必要あり

**Helix はこれらの上位レイヤー**に位置します。Claudeが計画立案と品質検証を担い、ローカルLLM（Ollama）が多角的な検証を行う。その全パイプラインが、コードを書かずに使えるデスクトップ＋Webアプリとして動作します。

> 研究メモ: マルチエージェントオーケストレーションは単一エージェントと比較して[80〜140倍の品質向上](https://arxiv.org/abs/2511.15755)を達成した事例があります。

---

## 主な機能 (v11.9.1 "Color Purge")

### オーケストレーション (mixAI)
- **3+1Phaseパイプライン**: Claude計画 → ローカルチーム実行 → Claude統合・検証 → (任意) Sonnetが変更適用
- **Phase 4（オプション）**: Sonnet 4.6/4.5がPhase 3の構造化出力からファイル変更を適用
- **構造化Phase 1**: design_analysis + acceptance_criteria + expected_output_format
- **Phase 3でのAcceptance Criteria評価** (PASS/FAILチェックリスト)
- **品質ループ**: 設定可能なPhase 2リトライ上限 (`max_phase2_retries`)
- **Phase 2スキップ**: 各ローカルLLMカテゴリを「未選択」にしてスキップ可能
- **Neural Flow / Phase進捗可視化** (パイプラインの透明性)
- **P1/P3エンジン切替**: Claude API、ローカルLLM、GPT-5.3-Codexに対応
- **プリセット**: 「P1=Opus4.6 / P3=GPT-5.3-Codex」ワンクリックプリセット

### Claude直接チャット (soloAI)
- **Claude Code CLI** 直接対話モード
- **GPT-5.3-Codex (CLI)** — Codex CLIバックエンド経由の実行オプション
- **Opus 4.6専用Adaptive thinking (effort)** — 推論強度を調整可能 (low/medium/high)
- **検索/ブラウズ方式**: なし / Claude WebSearch / Browser Use 選択式
- WebSocketによるストリーミング応答
- ファイル添付とコンテキスト注入

### ローカルLLMチーム (Ollama)
- **5つの専門カテゴリ**: coding / research / reasoning / translation / vision（各カテゴリのスキップ可能）
- **SequentialExecutor**: 大型モデル用 (ロード → 実行 → アンロード)
- **常駐モデル**: 制御AI + Embeddingモデルを一般設定で管理（任意、GPU検出対応）

### デュアルインターフェース (Desktop + Web)
- **デスクトップ**: PyQt6ネイティブアプリ（全設定フルコントロール）
- **Web UI**: React SPA（スマートフォン・タブレット・リモートPCからアクセス可能）
- **クロスデバイス同期**: Tailscale VPN経由のセキュアアクセス、実行ロック、ファイル転送
- **チャット履歴永続化**: コンテキストモード（single/session/full）付きセッション管理
- **デスクトップチャット履歴** (v9.7.0): QDockWidgetサイドパネル。検索/タブフィルタ/日付グループ化。Web UIと同じSQLite DBを共有

### メモリ・ナレッジ (Adaptive / Living Memory)
- **4層メモリ**: Thread / Episodic / Semantic / Procedural
- **Memory Risk Gate**: 常駐LLMが記憶候補を品質判定 (ADD/UPDATE/DEPRECATE/SKIP)
- **RAPTOR多段要約** (session → weekly) でスケーラブルな長期コンテキスト
- **Temporal KGエッジ** + **GraphRAGコミュニティ要約**
- **防御的メモリ注入** (保存済み記憶からのプロンプトインジェクションを防止するガードテキスト)

### "BIBLE-first" ドキュメントシステム
- **BIBLE Manager**: 自動検出 → パース → Phase 1/3注入 → ライフサイクル管理
- 現在のBIBLEの完全性スコア・セクション数を表示

### UX / デスクトップアプリ
- Cyberpunk Minimalなデザイン、一貫したスタイルとツールチップ（セルフドキュメンティングUI）
- ファイル添付 / クリップボードインポート / スポットアクション / ツール実行ログ
- **VRAM Budget Simulator**
- **GPUモニター** (タイムライン + 記録機能)

### MCP (Model Context Protocol) サポート
- MCPサーバー管理 (filesystem / git / web search コネクタ等)
- MCPの使用には注意が必要です。サードパーティMCPサーバーはプロンプトインジェクションのリスクがあります。
  詳細は公式MCPドキュメントを参照してください。

---

## デモ

### mixAI — 3+1Phaseパイプライン (Claude → ローカルLLM → Claude → Sonnet)
![mixAI デモ](docs/screenshots/mixai_demo.gif)

### cloudAI — Claudeチャット
![cloudAI Chat](docs/screenshots/HelixAIStudio_20260225_073406.png)

---

## スクリーンショット

| mixAI Chat | mixAI Settings | cloudAI Chat | cloudAI Settings | localAI Chat |
|---|---|---|---|---|
| ![mixAI Chat](docs/screenshots/HelixAIStudio_20260225_073402.png) | ![mixAI Settings](docs/screenshots/HelixAIStudio_20260225_073404.png) | ![cloudAI Chat](docs/screenshots/HelixAIStudio_20260225_073406.png) | ![cloudAI Settings](docs/screenshots/HelixAIStudio_20260225_073407.png) | ![localAI Chat](docs/screenshots/HelixAIStudio_20260225_073408.png) |

| localAI Settings | History | RAG Chat | RAG Build | RAG Settings |
|---|---|---|---|---|
| ![localAI Settings](docs/screenshots/HelixAIStudio_20260225_073410.png) | ![History](docs/screenshots/HelixAIStudio_20260225_073411.png) | ![RAG Chat](docs/screenshots/HelixAIStudio_20260225_073412.png) | ![RAG Build](docs/screenshots/HelixAIStudio_20260225_074153.png) | ![RAG Settings](docs/screenshots/HelixAIStudio_20260225_074155.png) |

---

## クイックスタート

### 前提条件
- Windows 10/11
- Python 3.12+
- NVIDIA GPU (CUDA) 推奨
- **Ollama** がローカルで動作していること (デフォルトAPI: `http://localhost:11434/api`)
- **Claude Code CLI** (Node.js 18+)

公式ドキュメント:
- Claude Code CLI 概要: https://docs.claude.com/en/docs/claude-code/overview
- Ollama API 入門: https://docs.ollama.com/api/introduction
- MCP ドキュメント: https://docs.anthropic.com/en/docs/mcp

### インストール

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# インタラクティブインストーラー（推奨）
install.bat

# または手動インストール:
pip install -r requirements.txt

# Claude Code CLI のインストール (Node.js 18+)
npm install -g @anthropic-ai/claude-code

# (任意) Phase 2用のローカルモデルをOllamaでプル
ollama pull devstral-2:123b
ollama pull command-a:latest
ollama pull gpt-oss:120b
ollama pull translategemma:27b
ollama pull gemma3:27b

# 常駐モデル (任意)
ollama pull ministral-3:8b
ollama pull qwen3-embedding:4b

# アプリ起動
python HelixAIStudio.py
````

> **初めての方**: [SETUP_GUIDE.md](SETUP_GUIDE.md) に Python / Node.js / Ollama / APIキー取得の詳細手順とトラブルシューティングがあります。

### スタンドアロン実行ファイルのビルド (Windows)

```bash
pip install pyinstaller
pyinstaller HelixAIStudio.spec --noconfirm
# dist/HelixAIStudio/HelixAIStudio.exe
```

---

## アーキテクチャ

```mermaid
graph LR
  User["User"] --> P1a["Phase 1a: Design analysis (Claude Code CLI)"]
  P1a --> P1b["Phase 1b: Instructions + Acceptance Criteria (Claude Code CLI)"]
  P1b --> P2["Phase 2: Local LLM Team (Ollama, Sequential)"]
  P2 --> P3["Phase 3: Integrate + Criteria Evaluation (Claude Code CLI)"]
  P3 --> P4["Phase 4 (Optional): Apply file changes (Sonnet 4.6/4.5)"]
  P4 --> User

  P2 --> coding["coding: devstral-2:123b"]
  P2 --> research["research: command-a:latest"]
  P2 --> reasoning["reasoning: gpt-oss:120b"]
  P2 --> translation["translation: translategemma:27b"]
  P2 --> vision["vision: gemma3:27b"]
```

---

## セキュリティ・プライバシーについて

### 設計原則

* **機密データはローカル優先** — Phase 2 はすべてローカルLLM (Ollama) で実行されます。検証段階で機密コードやドキュメントがマシン外に送信されることはありません。
* **APIキーはローカル保存** — キーは `config/general_settings.json` (git-ignored) または環境変数に保存されます。Helix が第三者にクレデンシャルを送信することはありません。
* **Web UIは非公開設計** — 内蔵Webサーバーは [Tailscale VPN](https://tailscale.com) 経由のアクセスを想定しています。ポート 8500 を公共インターネットに公開しないでください。
* **メモリ注入ガード** — 保存済みメモリには、蓄積コンテキストからのプロンプトインジェクション攻撃を防止するセーフティゲートプロンプトが含まれます。

### MCP (Model Context Protocol)

MCPサーバーはHelixの機能を拡張しますが、サードパーティサーバーは**デフォルトで信頼されません**。

* 2025年に[AnthropicのGit MCPサーバーにセキュリティ脆弱性](https://www.techradar.com/pro/security/anthropics-official-git-mcp-servers-had-worrying-security-flaws)が発見・修正されました。リスクカテゴリとして実在します。
* ファイル、git、ネットワークに触れるMCPサーバーには、許可リスト・最小権限・人間承認ゲートを使用してください。
* コミュニティ製より[公式リファレンスサーバー](https://github.com/modelcontextprotocol/servers)を優先してください。

### Phase 4 (ファイル変更)

Phase 4 は Sonnet 経由でファイル変更を自動適用します。本番ワークフローでは Phase 4 を有効にする前に **Phase 3 の出力を必ずレビュー** してください。

---

### i18n (国際化)
- **日本語 (デフォルト) + 英語** UI切替
- 共有翻訳ファイル (`i18n/ja.json`, `i18n/en.json`) をDesktopとWebの両方で使用

## 技術スタック

| コンポーネント | 技術 |
| -------------- | ---- |
| デスクトップGUI | PyQt6 |
| Web UI | React + Vite + Tailwind CSS |
| Webサーバー | FastAPI + Uvicorn (WebSocket) |
| Claude | Claude Code CLI (`claude`) |
| ローカルLLM | Ollama API (`http://localhost:11434/api`) |
| メモリ・ナレッジ | SQLite + ベクトル埋め込み + グラフユーティリティ |
| i18n | 共有JSON (ja/en) Desktop + Web両対応 |
| ビルド | PyInstaller (Desktop) / Vite (Web) |
| デザイン | Cyberpunk Minimal |

---

## プロジェクト構成 (概要)

```
Helix AI Studio/
├── frontend/              # Web UI (React + Vite)
│   └── src/
│       ├── components/    # Reactコンポーネント
│       ├── i18n/          # React i18nフック
│       └── main.jsx
├── i18n/                  # 共有翻訳ファイル
│   ├── ja.json            # 日本語 (デフォルト)
│   └── en.json            # 英語
├── src/
│   ├── backends/          # Claude/Ollama オーケストレーション
│   ├── tabs/              # mixAI / soloAI / settings (PyQt6)
│   ├── widgets/           # Neural Flow, VRAM simulator, チャット履歴パネル
│   ├── web/               # FastAPIサーバー, WebSocket, 認証, ChatStore
│   ├── bible/             # BIBLE discovery/parser/panel
│   ├── memory/            # 4層メモリ, risk gate, RAPTOR/GraphRAG
│   ├── rag/               # RAGビルダー, ベクトル検索
│   ├── mcp/               # MCP統合 / サーバー管理
│   ├── security/          # approvals / safety gates
│   └── utils/             # constants, diagnostics, i18n
├── config/                # 設定ファイル
├── BIBLE/                 # プロジェクトドキュメント
├── HelixAIStudio.py       # デスクトップアプリ エントリポイント
└── requirements.txt
```

---

### Web UI セットアップ (任意)

```bash
# Web UIフロントエンドのビルド
cd frontend
npm install
npm run build
cd ..

# デスクトップアプリ起動時にWeb UIが自動提供されます
# Tailscale VPN経由で任意のデバイスからアクセス可能
```

---

## バージョン履歴

| バージョン | コードネーム | 主な変更 |
|-----------|------------|---------|
| v11.9.1 | Color Purge | 残存インラインカラーリテラル完全排除（9ファイル・約100箇所）、COLORS/SS統一 |
| v11.9.0 | Unified Obsidian | per-tab stylesheet撤廃、SSセマンティックヘルパー、SplashScreen、EXEアイコン修正 |
| v11.8.0 | Polished Dark | Refined Obsidian 4層カラー、GLOBAL_APP_STYLESHEET、薄EXEランチャー |
| v11.7.0 | Resilient Core | 12ファイルエラーハンドリング強化、CLI→APIフォールバックチェーン |
| v11.6.0 | Provider Aware | Phase 2動的クラウドモデル検出、Visionコンボフィルタリング |
| v11.5.4 | Model Summary + Language Fix | 返答末尾にモデル名表示、mixAI英語応答修正 |
| v11.5.3 | Web LocalAI + Discord | Web LocalAI (Ollama WebSocket)、Discord通知、cloudAI/localAI表示統一 |
| v11.5.2 | Visual Parity | ログローテーション、パストラバーサル修正、ブルートフォース対策、自動クリーンアップ、RAG2ステップ |
| v11.5.1 | Provider Pure | プロバイダールーティング整理、APIキーセキュリティUI |
| v11.5.0 | Model Agnostic | マルチプロバイダーAPI (Anthropic/OpenAI/Google)、APIファースト |
| v9.9.1 | Memory & Codex | HelixMemoryManager強化(private除外/段階注入/ビューアAPI)、Codex CLI soloAI対応、mixAI Opus4.6/Codexプリセット、検索選択式、設定保存修正、差分ダイアログ修正、スクロール誤操作防止、保存UIボタン統一 |
| v9.8.0 | GitHub Ready | Sonnet 4.6追加、Adaptive thinking (effort)、Phase 4実装適用、常駐モデル一般設定移設、Phase 2スキップ、コンテキストバー修正 |
| v9.7.1 | Desktop Chat History | SpinBox UX修正、mixAI/soloAIヘッダー整理、モデルセレクタ重複排除、タイムアウトi18n修正、RAG設定NoScrollSpinBox、Ollama設定並び順変更 |
| v9.7.0 | Desktop Chat History | デスクトップチャット履歴サイドパネル、設定UI簡素化、Ollama設定一元化 |
| v9.6.0 | Global Ready | Web UI + デスクトップUI 英語切替（共有i18n基盤）/ README.md |
| v9.5.0 | Cross-Device Sync | Web実行ロック、モバイルファイル添付、デバイス間転送 |
| v9.3.0 | Switchable Engine | P1/P3エンジン切替（Claude API / ローカルLLM） |
| v9.2.0 | Persistent Sessions | チャット永続化、コンテキストモード |
| v9.0.0 | Web UI | React Web UI、FastAPI、WebSocketストリーミング |
| v8.5.0 | Autonomous RAG | RAGビルダー、情報収集タブ |
| v8.4.0 | Contextual Intelligence | 4層メモリ、RAPTOR要約 |

詳細は [CHANGELOG.md](CHANGELOG.md) を参照してください。

---

## Discord通知の設定

1. [Discord Webhook URL](https://support.discord.com/hc/ja/articles/228383668) を取得
2. Helix AI Studio → 一般設定タブ → Web UI Server セクション
3. Discord Webhook URL 欄に貼り付けて保存
4. 通知イベント（チャット開始/完了/エラー）を各チェックボックスで選択

## Web UIのビルド（開発者向け）

`frontend/dist/` はgit管理外です。クローン後または変更後に以下を実行してください：

```bash
cd frontend
npm install
npm run build
cd ..
```

デスクトップアプリ起動時に `dist/` が自動的に配信されます。

---

## コンプライアンス・データ取り扱い

### Anthropic（Claude）

Helixは**公式のClaude Code CLI**（`claude`バイナリ）または**Anthropic APIを直接**呼び出します。コンシューマーサブスクリプションのOAuthトークンを第三者ツールとして流用する設計ではありません。

> 2026年1月以降、Anthropicは[Claude Codeハーネスのなりすましを技術的にブロック](https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/)しています。Helixは公式ドキュメント通りのCLI呼び出しまたはAPIキー接続を使用するため**影響なし**です。

重要ポイント:
* **自動化・大量処理には** → [Anthropic APIキー](https://console.anthropic.com/settings/keys)を使用（Commercial Terms適用、学習データ対象外）
* **個人利用・対話用途には** → Claude Code CLI でのアカウントログインで問題なし
* **コンシューマーアカウント（Free/Pro/Max）** → 2025年9月以降、デフォルトで会話が[モデル学習に使用される可能性](https://www.anthropic.com/news/usage-policy-update)あり。プライバシー設定でオプトアウト、またはAPIキーへの切り替えを推奨
* すべての利用は [Anthropic利用規約](https://www.anthropic.com/legal/usage-policy) に準拠してください

### OpenAI（Codex CLI）

* Codex CLI はアカウントログインとAPIキー認証の両方をサポート — [認証ドキュメント](https://developers.openai.com/codex/auth/)
* 自動化ワークフローには [APIキーのベストプラクティス](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) を適用。キーを共有しないでください
* 利用は [OpenAI利用規約](https://openai.com/policies/row-terms-of-use/) に準拠

### Ollama・ローカルモデル

* Ollama本体は [MITライセンス](https://github.com/ollama/ollama/blob/main/LICENSE)
* **モデルのライセンスは個別に異なります** — 商用利用前に [Ollamaライブラリ](https://ollama.com/library) で各モデルのライセンスを確認してください（Llama系はMetaのCommunity License等）

### まとめ

| アクセス方法 | 学習リスク | 推奨用途 |
|---|---|---|
| Anthropic APIキー (Commercial) | なし | 自動化、機密データ |
| Claude Code CLI (Pro/Maxログイン) | オプトアウト推奨 | 対話型の個人利用 |
| Ollama (ローカル) | なし | プライバシー重視のPhase 2 |

---

## ライセンス

MIT (詳細は LICENSE を参照)

## 変更履歴

[CHANGELOG.md](CHANGELOG.md) に詳細なバージョン履歴を記載しています。

---

## コントリビュート

コントリビュートを歓迎します！ PRを提出する前に [CONTRIBUTING.md](CONTRIBUTING.md) をお読みください。

## セキュリティ

セキュリティ脆弱性については [SECURITY.md](SECURITY.md) を参照してください。

---

> 🤖 **AI支援について**: このプロジェクトの開発・ドキュメント作成にはAIツール（Claude）を活用しています。最終的な設計判断・検証・品質管理は開発者が責任を持って行っています。
