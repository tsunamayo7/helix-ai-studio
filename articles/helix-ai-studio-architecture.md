---
title: "【技術解説】マルチAIオーケストレーション「Helix AI Studio」のアーキテクチャ設計"
emoji: "🏗"
type: "tech"
topics: ["ai", "architecture", "fastapi", "pyqt6", "llm"]
published: true
---

## なぜマルチAIオーケストレーションなのか

単一エージェントの限界は学術的にも示されています。arXiv:2511.15755 によると、マルチエージェント構成は単一エージェントの80-140倍の品質向上が確認されています。

Helix AI Studio は **5Phaseパイプライン** でクラウドAI (Claude/GPT/Gemini) とローカルLLM (Ollama) を協調動作させるデスクトップアプリです。

https://github.com/tsunamayo7/helix-ai-studio

## コア: 3+1 Phase パイプライン

```
Phase 1 (Claude)     → タスク分析・受入基準・モデル別指示の生成
    ↓
Phase 2 (Local LLMs) → 5カテゴリ (coding/research/reasoning/translation/vision) で並列実行
    ↓
Phase 3 (Claude)     → 統合・品質評価・リトライループ
    ↓
Phase 4 (Sonnet)     → [Optional] ファイル変更の自動適用
```

### Phase 1: 設計フェーズ

Claudeがタスクを分析し、以下を生成します:
- `acceptance_criteria`: 品質判定基準
- `expected_output_format`: 出力フォーマット
- `per_model_instructions`: モデル別の最適化された指示

### Phase 2: 実行フェーズ

ローカルLLMが5つの専門カテゴリに分かれて実行:
```python
CATEGORIES = ["coding", "research", "reasoning", "translation", "vision"]
```
各カテゴリに最適なモデルを割り当て (例: CodeLlama → coding, Llama3 → reasoning)。

### Phase 3: 統合・評価フェーズ

Claudeが全Phase 2の出力を統合し、Phase 1で定義した `acceptance_criteria` に基づいて品質評価。基準未達なら自動リトライ。

### Phase 4: 適用フェーズ (オプション)

Claude Sonnetがファイル変更を解析し、差分を自動適用。

## デュアルインターフェース設計

```
┌─────────────────────────────────────────────┐
│  Desktop (PyQt6)     │  Web UI (React+FastAPI)│
│  - ネイティブGUI      │  - SPA + WebSocket    │
│  - GPU モニター       │  - モバイル対応        │
│  - VRAM シミュレータ   │  - JWT認証            │
│  - チャット履歴パネル  │  - Tailwind CSS       │
├─────────────────┴────────────────────────────┤
│              共有レイヤー                      │
│  SQLite DB │ config/ │ i18n/ (ja.json/en.json)│
└──────────────────────────────────────────────┘
```

### 技術スタック

| 層 | 技術 |
|---|---|
| デスクトップ GUI | PyQt6 |
| Web フロントエンド | React + Vite + Tailwind CSS |
| Web バックエンド | FastAPI + Uvicorn + WebSocket |
| クラウドAI | Anthropic / OpenAI / Gemini API |
| CLI | Claude Code CLI / Codex CLI |
| ローカルLLM | Ollama API (httpx) |
| メモリ/知識 | SQLite + ベクトル検索 |
| 多言語 | 共通 JSON (ja/en) |

## 4層メモリシステム

```
┌──────────────────────────┐
│  Thread Memory           │ ← 現在の会話コンテキスト
├──────────────────────────┤
│  Episodic Memory         │ ← 過去のインタラクション記録
├──────────────────────────┤
│  Semantic Memory         │ ← 抽象的知識
├──────────────────────────┤
│  Procedural Memory       │ ← パターン・ワークフロー
└──────────────────────────┘
        ↑
  Memory Risk Gate (常駐LLMによる品質チェック)
```

会話履歴は SQLite で永続化。RAGはドキュメントをベクトル化し、関連情報を自動注入します。

## BIBLE駆動ドキュメントファースト設計

プロジェクト仕様書 (`BIBLE_Helix_AI_Studio_*.md`) をPhase 1に自動注入し、設計意図の一貫性を保証します。完全性スコアリングにより仕様カバレッジを可視化。

## セキュリティ設計

### データ保護
- Phase 2はローカル実行 — 機密データが外部に出ない
- APIキーは `config/config.json` で管理 (.gitignore済み)

### Web UIセキュリティ
- JWT認証 (有効期限付きトークン)
- ブルートフォース防止 (レート制限)
- パストラバーサル防止

### MCP安全設計
- 許可リストによるツール制限
- 最小権限の原則
- 人間承認ゲート

## 統一UIテーマ: Obsidianパレット

v11.9.0で導入された一元化カラーシステム:

```python
COLORS = {
    "bg_base":     "#080c14",  # 最深部
    "bg_surface":  "#0d1117",  # 第2層
    "bg_card":     "#131921",  # 第3層
    "accent":      "#38bdf8",  # sky-400
    "success":     "#34d399",  # emerald-400
    "warning":     "#fbbf24",  # amber-400
    "error":       "#f87171",  # red-400
    ...
}
```

全UIコンポーネントがこの辞書を参照し、テーマの一貫性を保証。v11.9.1で240箇所以上のハードコードリテラルを排除完了。

## 開発プロセス

個人開発。v8.4 → v11.9 まで30+バージョンを重ねてきました。最近はClaude Code自体を使った自動化も推進:

- **Playwright MCP**: ブラウザ自動テスト
- **gh CLI**: ブランチ・コミット・PR管理
- **ffmpeg**: デモGIF自動生成
- **note.com自動投稿**: Playwright経由

## リンク

- **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
- **初心者ガイド**: https://note.com/ai_tsunamayo_7/n/n410331c01ab0
- **note.com記事 (詳細版)**: https://note.com/ai_tsunamayo_7/n/n5a97fbf68798
