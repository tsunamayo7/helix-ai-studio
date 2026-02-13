# Helix AI Studio v7.0.0 アップデートプラン

**作成日**: 2026-02-08
**作成者**: Claude Opus 4.6
**対象**: v6.3.0 → v7.0.0 "Orchestrated Intelligence"
**目的**: 3Phase実行パイプラインの再設計、ローカルLLMの最適配置、記憶システムの実装

---

## 第1部: v6.3.0 現状の問題点まとめ

### 致命的な問題

v6.3.0のスクリーンショットおよび問題点レポートから確認された問題は以下の通りです。

**1. 5Phaseパイプラインが事実上動作していない**

ツール実行ログを見ると、実際の実行フローは旧来のStage方式のままです。

```
実際の動作:
  タスク分析  → nemotron-3-nano:30b (15945ms)
  Claude CLI  → Claude CLI (MCP)    (118716ms)
  画像解析    → スキップ
  RAG検索     → nemotron-3-nano:30b (3358ms)
```

設計上は「P1:Claude → P2:Local並列 → P3:検証 → P4:Claude統合 → P5:保存」のはずが、Claude 1回 + nemotron 2回（タスク分析とRAG）しか動いていません。qwen3-next:80b、devstral-2:123b、command-a:111b などの大型モデルが一切使用されていません。

**2. チャット出力が内部ログ形式のまま**

ユーザーへの回答が「Stage 2: Claude実行 / 使用モデル: Claude CLI (MCP) / 実行結果報告」という技術的フォーマットで表示されています。本来はClaudeがまとめた自然な日本語回答のみを表示すべきです。

**3. ツール実行ログが見にくい**

ツール名・出力カラムが途中で切れており、展開もできないため実行内容の全体像が把握できません。

**4. ローカルLLMのchain-of-thought漏洩**

nemotron-3-nano:30bの内部推論（"We need to comply: answer in Japanese, m..."）がそのまま出力されています。

**5. Ollama接続テストエラーが未修正**

設定画面で `HelixOrchestratorTab` の属性エラーが発生したままです。

**6. Neural Flow Visualizerと実際の動作の乖離**

画面上部のP1→P2→P3→P4→P5バーが表示されていますが、実際にはP2～P4が動作していないため、UIと動作が矛盾しています。

---

## 第2部: ローカルLLM特性分析とVRAM配置戦略

### 2.1 利用可能なモデルの特性一覧

各Ollamaモデルページの情報を基に、RTX PRO 6000 (96GB) + RTX 5070 Ti (16GB) 環境に最適なモデル構成を分析しました。

#### 大型モデル（RTX PRO 6000で順番に動作）

| モデル | パラメータ | 推定VRAM (Q4) | コンテキスト | 特性 | 適性 |
|--------|-----------|--------------|------------|------|------|
| **devstral-2:123b** | 123B | ~75GB | 不明 | SWE-bench 72.2%、agentic coding最強クラス | コーディング Phase |
| **command-a:111b** | 111B (Q4_K_M=67GB) | ~67-70GB | 256K | 23言語対応、RAG特化訓練済、ツール使用対応 | RAG・検索・分析 Phase |
| **gpt-oss:120b** | 120B (5.1B active, MoE) | ~80GB (MXFP4) | 128K | 推論特化、chain-of-thought、Apache 2.0 | 推論・検証 Phase |
| **qwen3-coder-next:80b** | 80B (3B active, MoE) | ~50GB | 256K | 軽量MoE、agentic coding、tool calling | コーディング代替 |

#### 中型モデル（RTX PRO 6000またはオフロード）

| モデル | パラメータ | 推定VRAM (Q4) | コンテキスト | 特性 | 適性 |
|--------|-----------|--------------|------------|------|------|
| **gemma3:27b** | 27B | ~18GB | 128K | マルチモーダル(Vision)、140言語 | 画像解析・翻訳 |
| **mistral-small3.2:24b** | 24B | ~15GB | 不明 | function calling改善、instruction following | 関数呼び出し |
| **phi4-reasoning:plus** | 14B | ~9GB | 不明 | 推論特化、o3-mini蒸留+RL | 軽量推論・検証 |
| **translategemma:27b** | 27B | ~18GB | 不明 | 翻訳特化、55言語 | 翻訳 Phase |

#### 常駐型モデル（RTX 5070 Ti 16GBで常時稼働）

| モデル | パラメータ | 推定VRAM | 役割 |
|--------|-----------|---------|------|
| **nemotron-3-nano:30b** | 30B (3.5B active, MoE) | ~8-10GB ※MoEのため軽量 | タスク分析・ルーティング・軽量検証 |
| **ministral-3:8b** | 8B | ~5-6GB | フロー制御・JSON解析・指示フォーマット |
| **qwen3-embedding:4b** | 4B | ~2.5GB | RAG用Embedding生成 |

※ nemotron-3-nanoは30BですがハイブリッドMoEで3.5B active。実際のVRAMは8K contextで約10GB程度。ただし24GB表記の場合は5070 Tiに収まらないため、PRO 6000に常駐させ、大型モデル実行時にアンロードする戦略が必要です。

### 2.2 GPU配置戦略

```
┌─────────────────────────────────────────────────────────────┐
│  RTX PRO 6000 (96GB) - メイン実行GPU                         │
│                                                              │
│  ■ 大型モデル（1つずつ順番にロード/アンロード）              │
│    - devstral-2:123b    (~75GB) ← コーディング               │
│    - command-a:111b     (~67GB) ← RAG・検索・分析            │
│    - gpt-oss:120b       (~80GB) ← 推論・検証                 │
│    - qwen3-coder-next   (~50GB) ← 軽量コーディング代替       │
│    - gemma3:27b         (~18GB) ← 画像解析（Vision）          │
│    - translategemma:27b (~18GB) ← 翻訳                       │
│                                                              │
│  ■ 常駐候補（大型モデル非実行時）                            │
│    - nemotron-3-nano:30b (~10GB) ← タスク分析                │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  RTX 5070 Ti (16GB) - 常駐・制御GPU                          │
│                                                              │
│  ■ 常駐モデル（常時ロード）                                  │
│    - ministral-3:8b     (~6GB)  ← フロー制御・JSON解析       │
│    - qwen3-embedding:4b (~2.5GB)← Embedding生成              │
│    残り: ~7.5GB 空き                                         │
│                                                              │
│  ■ オフロード受け入れ                                        │
│    PRO 6000に大型モデル(75GB+)ロード時、                      │
│    nemotronの一部レイヤーを5070 Tiにオフロード可能           │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 モデルロード/アンロード戦略

Ollamaでは同時に1モデルのみGPUに載せるのが基本です。RTX PRO 6000で大型モデルを順番に動かす場合のフロー:

```
1. Phase開始前: ministral-3:8b (5070Ti) がClaudeの指示JSONを解析
2. 必要なモデルをOllama APIでロード指示
3. Ollama側で自動的に前のモデルをアンロード→新モデルをロード
4. 実行完了後、成果物をテキストファイルに保存
5. 次のモデルに切替（2-4を繰り返し）
```

環境変数 `OLLAMA_MAX_LOADED_MODELS=1`（PRO 6000側）を設定し、モデルの自動入替を制御します。

---

## 第3部: 新3Phase実行パイプライン設計

### 3.1 旧5Phase vs 新3Phase 比較

旧5Phaseの問題は「Phase数が多すぎて実装が複雑になり、結果的にPhase 2-4が動作しなかった」ことです。新設計では本質的な3Phaseに簡素化しつつ、各Phase内部のサブステップを明確化します。

```
旧 5Phase（設計上の構想、実際は動作せず）:
  P1: Claude初回 → P2: ローカル並列 → P3: 品質検証 → P4: Claude統合 → P5: 保存

新 3Phase（確実に動作する設計）:
  Phase 1: Claude計画立案
  Phase 2: ローカルLLM順次実行（RTX PRO 6000で1つずつ）
  Phase 3: Claude比較統合 + 最終出力
```

### 3.2 Phase 1: Claude計画立案（Claude Opus）

**目的**: ユーザーの意図を理解し、目的・成果物・最終目標を設定。各ローカルLLMへの指示を作成。

**動作フロー**:

```
ユーザー入力
    ↓
[アプリ側] 入力テキスト + コンテキスト情報をテキストファイルに保存
    ↓
[アプリ側] システムプロンプトにPhase 1用の構造化指示を注入
    ↓
[Claude Opus] ユーザーの意図を分析
    ├── 目的・成果物・最終目標を明文化
    ├── 必要なPhaseと使用すべきローカルLLMを決定
    ├── 各LLMへの個別指示をJSON形式で生成
    │   （各LLMの適性・ツール・得意分野に合わせた指示）
    ├── Phase 2をスキップすべきか判断
    │   （単純な挨拶→スキップ、複雑なコーディング→全LLM動員）
    └── 全出力をテキストファイルに保存
    ↓
[アプリ側] Phase 1の出力JSONをパースし、Phase 2の実行計画を確定
```

**Claude Phase 1 出力の構造**:

```json
{
  "plan": {
    "objective": "ユーザーの目的の要約",
    "deliverables": ["成果物1", "成果物2"],
    "final_goal": "最終的なゴール",
    "complexity": "simple|moderate|complex",
    "skip_phase2": false,
    "bible_check_required": true,
    "bible_path": "C:/path/to/project/"
  },
  "claude_initial_answer": "Claudeによる初回回答（Phase 2の結果と統合前）",
  "llm_tasks": [
    {
      "order": 1,
      "model": "devstral-2:123b",
      "gpu": "PRO6000",
      "role": "coding",
      "instruction": "以下のPythonファイルを...",
      "expected_output": "修正済みコード",
      "timeout_seconds": 300,
      "tools": ["file_read", "file_write"]
    },
    {
      "order": 2,
      "model": "command-a:111b",
      "gpu": "PRO6000",
      "role": "research",
      "instruction": "以下の技術トピックについて...",
      "expected_output": "調査レポート",
      "timeout_seconds": 180
    }
  ],
  "verification_criteria": {
    "coding": "コードがエラーなく実行できること",
    "research": "3つ以上の情報源に基づくこと"
  }
}
```

**BIBLEファイル管理**: ファイル操作を伴うタスクの場合、Phase 1でClaudeが指定パス直下のBIBLEファイルの有無を確認し、存在すれば内容を読み込んだ上で計画を立案します。存在しなければ規定フォーマットで新規作成を計画に含めます。

### 3.3 Phase 2: ローカルLLM順次実行

**目的**: Claude指示に基づき、RTX PRO 6000上で大型LLMを1つずつ順番に実行し、各領域の成果物を生成。

**動作フロー**:

```
Phase 1の実行計画JSON
    ↓
[アプリ側] 実行順序に従い、以下をループ:
    │
    ├── (1) ministral-3:8b (5070Ti常駐) がClaudeの指示JSONを
    │       各LLM向けのシステムプロンプトに変換
    │       → 各LLMのプロンプト形式・ツール形式に最適化
    │
    ├── (2) Ollama APIで対象モデルをロード (PRO 6000)
    │       → 前モデルは自動アンロード
    │       → ロード完了を待機（VRAMチェック）
    │
    ├── (3) 変換済み指示を注入してモデル実行
    │       → タイムアウト監視
    │       → 進捗をNeural Flow Visualizerに反映
    │
    ├── (4) 出力をministral-3:8bでフィルタリング
    │       → chain-of-thought除去
    │       → 出力フォーマット正規化
    │       → 結果品質の初期チェック（明らかな失敗検出）
    │
    └── (5) 成果物をテキストファイルに保存
            → data/phase2/task_{order}_{model}.txt

[アプリ側] 全タスク完了後、成果物一覧をPhase 3に渡す
```

**重要: 順次実行の理由**

並列実行ではなく順次実行を採用する理由:
- RTX PRO 6000 (96GB) でも大型モデル(67-80GB)は1つしか同時にロードできない
- モデルのロード/アンロードに時間がかかるため、確実な制御が必要
- 各タスクの結果を次のタスクに活用できる（例: 検索結果→コーディング）

**ministral-3:8b の制御役割**:

RTX 5070 Ti上のministral-3:8bは以下の「制御AI」として機能します:
- Claude指示JSONの解析と各LLM向けプロンプト変換
- 各LLM出力のchain-of-thoughtフィルタリング
- 出力フォーマットの正規化（JSON、Markdown等に統一）
- 明らかなエラー（空出力、文字化け等）の検出
- 実行ログの構造化

これにより、アプリコード側のパーサーへの依存を減らし、LLM間の指示・成果物の受け渡しを「AI同士の翻訳」として実現します。

### 3.4 Phase 3: Claude比較統合

**目的**: 全成果物を受け取り、検証・補強・統合して最終成果物とユーザー向け回答を生成。

**動作フロー**:

```
Phase 2の全成果物テキストファイル
    ↓
[アプリ側] 全成果物を読み込み、Phase 3用プロンプトを構成
    ↓
[Claude Opus] 2回目の呼び出し
    ├── Phase 1での自身の初回回答を再確認
    ├── 各ローカルLLMの成果物を評価
    │   ├── 正確性チェック
    │   ├── 完全性チェック
    │   └── 自身の回答との比較
    │
    ├── 品質不足の場合 → 再実行指示を生成
    │   └── [アプリ側] Phase 2を部分的に再実行
    │       → 不足分のみ再実行（最大2回まで）
    │       → 再実行結果を再度Claudeに渡す
    │
    ├── 十分な場合 → 統合処理
    │   ├── 各成果物の優れた点を取り込み
    │   ├── 誤りを修正
    │   └── 最終成果物を生成
    │
    └── ユーザー向け出力
        ├── 自然な日本語の回答テキスト
        ├── 成果物ファイル（必要に応じて）
        └── ナレッジ保存用サマリー
    ↓
[アプリ側] チャットエリアに回答のみ表示
           ツール実行ログは折りたたみセクションに格納
           ナレッジDBに保存
```

**再実行ループの制御**:

```
Phase 3のClaude評価結果
    ↓
品質OK → 最終統合 → ユーザーへ出力
    ↓
品質NG → 再実行指示JSON生成
    ↓
[アプリ側] 不足タスクのみPhase 2を再実行（ループ1回目）
    ↓
Phase 3のClaude再評価
    ↓
品質OK → 最終統合
品質NG → 再実行（ループ2回目、最大）
    ↓
Phase 3のClaude最終統合（3回目は強制統合）
```

---

## 第3.5部: Claude MCPツール戦略（最大限活用）

### 3.5.0 v6.3.0 MCP現状分析 ★確定版

#### 確定した事実（2026-02-09検証済み）

| 項目 | 状態 | 詳細 |
|------|------|------|
| Claude CLI MCPサーバー | **ゼロ** | `claude mcp list` → "No MCP servers configured" |
| `--dangerously-skip-permissions` | **使用中** | 全ネイティブツール（Bash, Read, Write, WebSearch等）が許可済み |
| Helix独自MCP | **プロンプト埋め込み専用** | `helix_mcp_client.py`はファイル内容をプロンプト文字列に結合するだけ |
| Claudeのツール使用 | **未活性** | システムプロンプトがツール使用を促していない |

#### 根本原因の確定

```
v6.3.0のツール活用状況:

  claude -p --dangerously-skip-permissions --output-format json --model opus
    │
    │  stdin: [ファイル内容を埋め込んだプロンプト]
    │
    │  ★ この時点でClaudeは以下のツールを全て使用可能:
    │    Bash, Read, Write, Edit, Glob, Grep,
    │    WebFetch, WebSearch, Task (SubAgent)
    │
    │  ★ しかしシステムプロンプトに「ツールを使え」の指示がないため
    │    Claudeは埋め込まれたプロンプト文字列のみで回答を生成
    │
    │  ★ 結果: WebSearchで最新情報を調べることもなく、
    │    Readで実際のファイルを確認することもなく、
    │    Bashでテストを実行することもなく、回答のみ返す
    │
    └→ 回答JSON（ツール使用ゼロ）
```

**結論**: インフラ（ツール許可）は整っているのに、**指示（プロンプト）がツール使用を促していない**ため、Claudeの能力の80%以上が眠ったままだった。これはv6.3.0の5Phase不全（コードはあるが実行されない）と同じパターン。

#### v7.0.0での解決策: 2段階アプローチ

```
┌───────────────────────────────────────────────────────────────┐
│              v7.0.0 ツール活性化戦略                           │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  【ステップ1: システムプロンプト改善（工数: 低、効果: 大）】  │
│                                                               │
│  Phase 1/Phase 3のシステムプロンプトに以下を追加:             │
│  「あなたは以下のツールを積極的に使用してください:            │
│    - Read: ファイル内容の直接確認                             │
│    - Bash: コマンド実行、ビルド、テスト                       │
│    - Grep/Glob: コード検索・構造把握                          │
│    - WebSearch: 最新技術情報・エラー解決策の検索              │
│    ユーザーの要求に対して必要なツールを自律的に選択・          │
│    実行してください。」                                       │
│                                                               │
│  → これだけでClaude CLIのネイティブツールが活性化             │
│  → コード変更はシステムプロンプト文字列のみ                   │
│                                                               │
│  【ステップ2: MCP追加（工数: 中、効果: 中）】                │
│                                                               │
│  claude mcp add で追加のMCPサーバーを設定:                    │
│    - GitHub MCP → Issue/PR連携                                │
│    - Memory MCP → セッション間記憶                            │
│    - Context7 MCP → 最新ライブラリドキュメント               │
│                                                               │
│  → ネイティブツールだけでは不可能な機能を追加                 │
│  → ステップ1の効果確認後に実施                                │
└───────────────────────────────────────────────────────────────┘
```

#### v6.3.0の実装詳細（確認済み）

**Claude CLI呼び出し方法** (`mix_orchestrator.py`):
```python
cmd = [
    "claude",
    "-p",                               # 非対話（パイプ）モード
    "--dangerously-skip-permissions",   # 全ツール自動許可 ★
    "--output-format", "json",          # JSON出力
    "--model", "opus",
]
# stdinにプロンプト全文（ファイル内容埋め込み済み）を送信
```

**ファイル埋め込み方法** (`mix_orchestrator.py` 228-254行目):
```python
def _build_full_prompt(self, prompt: str) -> str:
    """添付ファイルがある場合、その内容をプロンプトに埋め込む"""
    if not self.attached_files:
        return prompt
    file_contents = []
    for f in self.attached_files:
        if os.path.exists(f):
            content = fp.read()
            file_contents.append(
                f"--- ファイル: {f} ---\n{content}\n--- ファイル終了 ---"
            )
    if file_contents:
        return "\n\n".join(file_contents) + "\n\n" + prompt
    return prompt
```

#### 現在の設定ファイル構成

```
config/
├── mcp_servers.json        # レイヤーA: Helix独自MCPサーバー設定
├── app_settings.json       # claude.mcp_enabled: true/false
data/
├── mcp_policies.json       # ツールごとの必要スコープ定義
logs/
├── mcp_audit.log           # ツール実行の監査ログ（JSONL）
src/mcp_client/
├── helix_mcp_client.py     # レイヤーA: 独自MCPクライアント実装
```

#### v7.0.0での統合戦略 ★確定版

v6.3.0は既に `--dangerously-skip-permissions` で全ツール許可済み。v7.0.0では**システムプロンプトでツール使用を指示する**ことで活性化し、将来的にMCPサーバーを追加して機能拡張します。

```
┌───────────────────────────────────────────────────────────────┐
│         v7.0.0 ツール活性化アーキテクチャ（確定）             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  claude -p --dangerously-skip-permissions \                   │
│    --output-format json --model opus                          │
│    --cwd "プロジェクトディレクトリ"  ← ★新規追加             │
│                                                               │
│  stdin: システムプロンプト（★ツール使用指示を追加）           │
│         + ユーザー入力                                        │
│         + (Phase 3の場合) Phase 2の結果                       │
│                                                               │
│  ┌─────────────────────────────────────────────────┐         │
│  │ ★活性化されるネイティブツール:                   │         │
│  │   Bash ──── git, npm, python, pytest, pip        │         │
│  │   Read ──── ソースコード直接確認                  │         │
│  │   Write ─── ファイル生成・更新                    │         │
│  │   Edit ──── 既存ファイル編集                      │         │
│  │   Glob ──── プロジェクト構造把握                  │         │
│  │   Grep ──── コード内検索                          │         │
│  │   WebSearch ─ 最新技術情報・エラー解決策          │         │
│  │   WebFetch ── ドキュメント・API仕様取得           │         │
│  │   Task ───── サブタスク分割（大規模作業時）       │         │
│  └─────────────────────────────────────────────────┘         │
│                                                               │
│  ┌─────────────────────────────────────────────────┐         │
│  │ ★将来追加するMCPサーバー（claude mcp add）:      │         │
│  │   github ─── Issue/PR連携、コードレビュー         │         │
│  │   memory ─── セッション間記憶                     │         │
│  │   context7 ── 最新ライブラリドキュメント          │         │
│  └─────────────────────────────────────────────────┘         │
│                                                               │
│  ┌─────────────────────────────────────────────────┐         │
│  │ Helix側の役割変更:                               │         │
│  │   v6.3.0: ファイル読み→プロンプト埋め込み→CLI   │         │
│  │   v7.0.0: --cwdで作業ディレクトリ指定→CLI        │         │
│  │           Claudeが自分でRead/Globしてファイル確認  │         │
│  │           Helix独自MCPは Phase 2 補助に限定       │         │
│  │           Claude CLI JSON出力から監査ログ生成     │         │
│  └─────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────┘
```

**移行方針まとめ（確定版）**:

| 項目 | v6.3.0（現状） | v7.0.0（変更後） | 変更内容 |
|------|---------------|-----------------|----------|
| ファイル読み取り | Helix側で読み→プロンプト埋め込み | Claude CLI Read が自発的に読む | プロンプト指示追加 |
| ファイル書き込み | helix_mcp_clientのwrite_file | Claude CLI Write/Edit | プロンプト指示追加 |
| Git操作 | helix_mcp_clientのgit_status/diff | Claude CLI Bash(git *) | プロンプト指示追加 |
| Web検索 | ❌ 未使用 | Claude CLI WebSearch | プロンプト指示追加 |
| GitHub連携 | ❌ 無効 | claude mcp add github | MCP追加（ステップ2） |
| ツール許可 | --dangerously-skip-permissions | 同左（変更不要） | 変更なし |
| 作業ディレクトリ | 指定なし | --cwd 追加 | コマンド引数追加 |
| 監査ログ | helix_mcp_client JSONL | Claude CLI JSON出力解析 | ログ収集方法変更 |
| Phase 2補助 | 未使用 | Helix MCP縮小版（ファイル読み取りのみ） | 役割限定 |

### 3.5.1 Claude Code CLIのツール能力の全体像

Claude Code CLIは`-p`（非対話モード）で呼び出しても、以下のツールを**自発的に**使用できます。これはHelix AI Studioにとって非常に重要な能力であり、v7.0.0ではこれを最大限に活用する設計とします。

#### ビルトインツール（MCP設定不要）

| ツール | 機能 | Helix AI Studioでの活用場面 |
|--------|------|---------------------------|
| **Bash** | シェルコマンド実行（git, npm, pip, docker等） | ファイル操作、ビルド実行、テスト、git操作 |
| **Read/Edit/Write** | ファイル読み書き・編集 | ソースコード修正、設定ファイル更新、BIBLE生成 |
| **LS/Glob/Grep** | ファイル検索・パターンマッチ | プロジェクト構造の把握、コード検索 |
| **WebFetch** | URL指定でWebページ内容を取得・分析 | ドキュメント参照、API仕様の確認 |
| **WebSearch** | ウェブ検索 | 最新技術情報の取得、エラー解決策の検索 |
| **SubAgent** | サブエージェント起動 | 複雑タスクの分割処理 |

**重要**: これらはMCPサーバーを設定しなくてもClaude Code CLIに標準搭載されており、`claude -p "プロンプト"` 実行時にClaudeが必要と判断すれば自発的に使用します。

#### MCPサーバーで追加すべきツール

ビルトインに加え、以下のMCPサーバーを設定することで、Claudeの能力を大幅に拡張できます。

| MCPサーバー | 追加される能力 | 設定コマンド | 必要な認証 |
|-------------|---------------|-------------|-----------|
| **GitHub MCP** | リポジトリ操作、Issue/PR管理、コードレビュー | `claude mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer PAT"}}'` | GitHub PAT |
| **Filesystem MCP** | 高度なファイルシステムアクセス | `claude mcp add filesystem -- npx @modelcontextprotocol/server-filesystem /allowed/path` | なし |
| **Memory MCP** | セッション間の永続記憶 | `claude mcp add memory -- npx @modelcontextprotocol/server-memory` | なし |
| **Perplexity MCP** | 高品質ウェブ検索（WebSearchより精度高） | `claude mcp add perplexity -- npx perplexity-mcp` | Perplexity API Key |
| **Context7 MCP** | 最新のライブラリドキュメント取得 | `claude mcp add context7 -- npx context7-mcp` | なし |

### 3.5.2 MCP設定の現状と推奨設定

#### 現在のHelix独自MCP設定 (`config/mcp_servers.json`)

```json
{
  "servers": {
    "filesystem": {  // ✅ 有効 - ファイル読み書き・削除
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem"],
      "enabled": true
    },
    "git": {  // ✅ 有効 - git status, diff, commit, push
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-git"],
      "enabled": true
    },
    "brave-search": {  // ❌ 無効 - APIキー未設定
      "args": ["-y", "@anthropic/mcp-server-brave-search"],
      "env": {"BRAVE_API_KEY": ""},
      "enabled": false
    },
    "github": {  // ❌ 無効 - トークン未設定
      "args": ["-y", "@anthropic/mcp-server-github"],
      "env": {"GITHUB_TOKEN": ""},
      "enabled": false
    }
  }
}
```

#### 要確認事項: Claude Code CLI側のMCP設定

```bash
# Claude Code CLI自体に設定されているMCPサーバーを確認
claude mcp list

# 設定ファイルを直接確認
type %USERPROFILE%\.claude.json              # ユーザースコープ
type %USERPROFILE%\.claude\settings.json     # パーミッション設定
```

> **注意**: Helix独自MCP (`config/mcp_servers.json`) と Claude Code CLI MCP (`~/.claude.json`) は**別の設定ファイル**です。両方を確認する必要があります。

#### v7.0.0推奨設定（2段階アプローチ）

**ステップ1: Claude Code CLI側のMCPを充実させる**（メインのツール供給源）

```bash
# 1. GitHub MCP（最重要 - GitHub連携）
claude mcp add-json github '{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp",
  "headers": {"Authorization": "Bearer YOUR_GITHUB_PAT"}
}' --scope user

# 2. Memory MCP（セッション間記憶）
claude mcp add memory --scope user -- npx @modelcontextprotocol/server-memory

# 3. Context7 MCP（最新ライブラリドキュメント）
claude mcp add context7 --scope user -- npx context7-mcp

# 4. Filesystem MCPは不要（CLIネイティブのRead/Write/Editで十分）
```

**ステップ2: Helix独自MCP設定を簡略化** (`config/mcp_servers.json`)

```json
{
  "servers": {
    // v7.0.0: Claude CLIネイティブツールに移行したため大幅簡略化
    // 残すのはPhase 2（ローカルLLM）のファイル読み取り補助のみ
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem"],
      "enabled": true,
      "note": "Phase 2でローカルLLMにファイル内容を渡す際に使用"
    }
    // git, brave-search, github → Claude CLIネイティブに移行
  }
}
```

**ステップ3: Claude CLI パーミッション設定** (`~/.claude/settings.json`)

```json
{
  "permissions": {
    "allow": [
      "Bash(git*)",
      "Bash(npm*)",
      "Bash(python*)",
      "Bash(pytest*)",
      "Bash(pip*)",
      "Read",
      "Write",
      "Edit",
      "WebFetch",
      "WebSearch",
      "mcp__github__*",
      "mcp__memory__*",
      "mcp__context7__*"
    ]
  }
}
```

### 3.5.3 3Phaseパイプラインでのツール活用設計

#### Phase 1（Claude計画立案）でのツール使用

```
ユーザー入力: 「このPythonプロジェクトをリファクタリングして」
    ↓
Claude Phase 1 の自発的行動:
    ├── [Read/LS/Glob] プロジェクト構造を把握
    ├── [Grep] 主要クラス・関数を検索
    ├── [Read] 重要ファイルの内容を確認
    ├── [WebSearch] リファクタリングのベストプラクティスを検索
    ├── [mcp__github] 関連するIssueやPRを確認（設定済みなら）
    ├── [Read] BIBLEファイルがあれば読み込み
    └── 上記情報をもとに計画JSON + 各LLM向け指示を生成
```

**重要な設計判断**: Phase 1のシステムプロンプトに「必要に応じてツールを自発的に使用し、プロジェクトの実態を把握した上で計画を立てること」と明記します。これにより、Claudeは**ユーザーが何も指示しなくても**自発的にファイルを読み、構造を理解し、適切な計画を立てられます。

#### Phase 2（ローカルLLM実行）でのツール考慮

ローカルLLM自体はMCPツールを使えませんが、Phase 1でClaudeが取得した情報（ファイル内容、検索結果等）を**指示文に含める**ことで間接的に活用します。

```
Phase 1でClaudeが読んだファイル内容
    ↓
Phase 2の指示文に埋め込み:
    "以下のファイル src/main.py の内容を分析し、
     リファクタリング案を提示してください:
     ```python
     [Claudeが読んだファイル内容]
     ```"
    ↓
ローカルLLMがファイル内容を受け取って処理
```

#### Phase 3（Claude統合）でのツール使用

```
Phase 2の全結果を受け取ったClaude Phase 3:
    ├── [Read] Phase 2で言及されたファイルを直接確認
    ├── [Bash] テストの実行（pytest, npm test等）
    ├── [Edit/Write] 最終的なコード修正を直接実行
    ├── [Bash] git commit で変更をコミット（設定次第）
    ├── [mcp__github] PRの作成（設定済みなら）
    ├── [Write] BIBLEファイルの更新
    └── 自然な日本語で最終回答を生成
```

### 3.5.4 claude -p のツール許可方式（確定）

v6.3.0は既に `--dangerously-skip-permissions` を使用しており、全ツールが許可済みです。v7.0.0でもこれを維持しつつ、`--cwd` でセキュリティを確保します。

```bash
# v6.3.0（現状）: 全ツール許可だがプロンプトが使用を促さない
claude -p \
  --dangerously-skip-permissions \
  --output-format json \
  --model opus
# stdin: ファイル埋め込み済みプロンプト（ツール使用指示なし）

# v7.0.0（改善後）: --cwd追加 + プロンプトでツール使用を明示的に指示
claude -p \
  --dangerously-skip-permissions \
  --output-format json \
  --model opus \
  --cwd "/path/to/project"          # ★新規: 作業ディレクトリ制限
# stdin: システムプロンプト（★ツール使用指示あり）+ ユーザー入力
```

**セキュリティ方針**:
- `--dangerously-skip-permissions` は継続使用（v6.3.0互換）
- `--cwd` でClaude CLIの操作範囲をプロジェクトディレクトリに限定
- 将来的に `--allowedTools` への移行も検討可能（Phase別ツール制限）
- Claude CLI JSON出力から監査ログを生成（v6.3.0 JSONL形式を継承）

**将来のセキュリティ強化オプション**（v7.1.0以降）:
```bash
# Phase 1: 読み取り系のみ
--allowedTools "Read,LS,Glob,Grep,WebFetch,WebSearch"

# Phase 3: 全ツール（ファイル変更含む）
--allowedTools "Read,Write,Edit,Bash(*),WebFetch,WebSearch"
```

### 3.5.5 Helix AI Studioアプリ側の実装（確定版）

v6.3.0からの変更は最小限です。**主な変更はシステムプロンプトの追加と`--cwd`の追加のみ**。

```python
# src/backends/claude_executor.py

class ClaudeCLIExecutor:
    """Claude Code CLI実行管理（v7.0.0）"""

    def build_command(self, project_dir: str = None) -> list:
        """CLI実行コマンドを構築（v6.3.0からの差分は --cwd のみ）"""

        cmd = [
            "claude", "-p",
            "--dangerously-skip-permissions",  # v6.3.0から継続
            "--output-format", "json",
            "--model", "opus",
        ]

        # ★v7.0.0新規: 作業ディレクトリを指定
        if project_dir:
            cmd.extend(["--cwd", project_dir])

        return cmd

    def execute_phase1(self, user_input: str, context: dict) -> dict:
        """Phase 1: Claude計画立案 + ツール活性化"""

        # ★v7.0.0の核心: システムプロンプトでツール使用を指示
        system_prompt = self._build_phase1_system_prompt(context)
        full_prompt = f"{system_prompt}\n\n## ユーザーの要求:\n{user_input}"

        cmd = self.build_command(context.get("project_dir"))
        result = subprocess.run(
            cmd, input=full_prompt, capture_output=True,
            text=True, timeout=300
        )
        return json.loads(result.stdout)

    def _build_phase1_system_prompt(self, context: dict) -> str:
        """★v7.0.0核心: ツール使用を明示的に指示するシステムプロンプト"""
        return f"""あなたはHelix AI Studioの中核AIです。
ユーザーの要求を分析し、計画を立案してください。

## 利用可能なツール（積極的に使用してください）
- **Read**: ファイル内容の直接確認（推測せず実際に読んでください）
- **Bash**: コマンド実行（git status, npm install, pytest等）
- **Glob/Grep**: プロジェクト内のファイル検索・コード検索
- **WebSearch**: 最新技術情報、エラー解決策、ライブラリ情報の検索
- **WebFetch**: URL先のドキュメント・API仕様の取得

## 作業方針
1. まずプロジェクト構造を Glob/Read で確認
2. 必要に応じて WebSearch で最新情報を取得
3. 分析結果に基づいて計画を立案
4. ローカルLLMチームへの指示JSON を生成

## 出力形式
以下のJSON形式で出力してください:
{{
  "claude_answer": "ユーザーへの回答（自然な日本語）",
  "local_llm_instructions": {{
    "search": {{"prompt": "...", "skip": false}},
    "report": {{"prompt": "...", "skip": false}},
    "architect": {{"prompt": "...", "skip": true}},
    "coding": {{"prompt": "...", "skip": false}}
  }},
  "complexity": "high|medium|low",
  "tools_used": ["Read", "WebSearch", ...]
}}
"""

    def execute_phase3(self, phase2_results: list, context: dict) -> dict:
        """Phase 3: Claude統合"""
        system_prompt = self._build_phase3_system_prompt(phase2_results, context)
        full_prompt = f"{system_prompt}\n\n統合を実行してください。"

        cmd = self.build_command(context.get("project_dir"))
        result = subprocess.run(
            cmd, input=full_prompt, capture_output=True,
            text=True, timeout=600
        )
        return json.loads(result.stdout)

    def _build_phase3_system_prompt(self, phase2_results: list, context: dict) -> str:
        """Phase 3: 統合プロンプト（ツール使用指示付き）"""
        results_text = self._format_phase2_results(phase2_results)
        return f"""あなたはHelix AI Studioの統合AIです。

## Phase 1であなたが立案した計画:
{context.get('phase1_answer', '')}

## Phase 2でローカルLLMチームが生成した結果:
{results_text}

## 利用可能なツール（必要に応じて使用してください）
- **Read/Write/Edit**: ファイルの確認・修正・生成
- **Bash**: テスト実行、ビルド、git操作
- **WebSearch**: 不明点の調査

## 統合方針
1. 各ローカルLLMの結果を評価（正確性、完全性）
2. 自身のPhase 1の回答と比較し、優れた点を取り込む
3. 必要に応じてファイルを直接修正（Write/Edit）
4. テストを実行して品質を検証（Bash）
5. 最終回答を自然な日本語で生成
"""
```

### 3.5.6 ローカルLLMとの差別化ポイント

この設計により、ClaudeとローカルLLMの役割分担がさらに明確になります。

```
Claude (Phase 1, Phase 3):
  ✅ ウェブ検索で最新情報を取得
  ✅ GitHubのIssue/PRを直接確認
  ✅ プロジェクトファイルを自発的に読み込み
  ✅ テスト実行・ビルド検証
  ✅ ファイル修正・コミット
  ✅ 計画立案・品質判断・最終統合

ローカルLLM (Phase 2):
  ✅ Claudeが収集した情報をもとに大量処理
  ✅ コーディング（devstral-2:123b）
  ✅ 調査・分析（command-a:111b）
  ✅ 推論・検証（gpt-oss:120b）
  ❌ ツール使用不可（Ollama APIはツール非対応）
  → Claudeが「ツールの目」となって情報を収集し、指示文に埋め込む
```

### 3.5.7 MCP設定UIの刷新

v6.3.0の独自MCPクライアント設定UIを、v7.0.0の統合アーキテクチャに合わせて刷新します。

```
一般設定タブ → MCP設定セクション

┌─────────────────────────────────────────────────────┐
│ 🔧 ツール設定                                        │
│                                                      │
│ ━━━ Claude Code CLI ネイティブツール ━━━             │
│   ✅ Bash (git, npm, python, pytest)                 │
│   ✅ Read / Write / Edit                             │
│   ✅ WebFetch / WebSearch                            │
│   ℹ️ claude -p 実行時に自動利用可能                   │
│                                                      │
│ ━━━ Claude Code CLI MCPサーバー ━━━                  │
│   ✅ github         設定済み  [テスト] [設定変更]    │
│   ✅ memory         設定済み  [テスト]               │
│   ⚠️ context7       未設定   [セットアップ]          │
│   ℹ️ 設定場所: ~/.claude.json                        │
│                                                      │
│ ━━━ Helix内部ツール（Phase 2補助用）━━━             │
│   ✅ filesystem     有効     [テスト]                │
│   ℹ️ ローカルLLMへのファイル内容受け渡しに使用       │
│   ℹ️ 設定場所: config/mcp_servers.json               │
│                                                      │
│ ━━━ セキュリティ ━━━                                 │
│   📋 監査ログ: logs/mcp_audit.log  [表示]            │
│   🔒 Phase 1: 読み取り専用                           │
│   🔓 Phase 3: 読み書き許可（--cwdで範囲限定）        │
│                                                      │
│ [Claude CLI設定を確認] [推奨設定を一括適用]          │
└─────────────────────────────────────────────────────┘
```

#### 「Claude CLI設定を確認」ボタンの実装

```python
def _check_claude_cli_mcp(self):
    """Claude Code CLI側のMCP設定を確認"""
    try:
        # claude mcp list の実行
        result = subprocess.run(
            ["claude", "mcp", "list"],
            capture_output=True, text=True, timeout=10
        )
        mcp_servers = self._parse_mcp_list(result.stdout)
        
        # Claude CLIパーミッション設定の確認
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            with open(settings_path) as f:
                cli_settings = json.load(f)
                allowed_tools = cli_settings.get("permissions", {}).get("allow", [])
        
        # UIに反映
        self._update_mcp_status_display(mcp_servers, allowed_tools)
    except Exception as e:
        self._show_mcp_error(f"Claude CLI設定の確認に失敗: {e}")
```

#### v6.3.0からの移行チェックリスト

```
v7.0.0初回起動時の自動チェック:

1. [確認] Claude Code CLIがインストールされているか
2. [確認] claude mcp list で設定済みサーバーを取得
3. [確認] ~/.claude/settings.json のパーミッション設定
4. [警告] config/mcp_servers.json に旧設定が残っている場合
         → 「v7.0.0では Claude CLI MCPに移行しました」通知
5. [推奨] 未設定のMCPサーバーがあれば設定を案内
6. [保持] logs/mcp_audit.log の監査ログ機能は継続
```

---

## 第4部: 各Phase最適LLMの再設計

### 4.1 タスクカテゴリと最適モデルマッピング

以下のモデルページの実際のベンチマーク情報に基づいた割り当てです。

#### コーディング系タスク

**第1選択: devstral-2:123b** (SWE-bench Verified 72.2%)
- Mistral製、agentic coding特化、ファイル探索・複数ファイル編集に優れる
- Modified MIT License（月次収益$20M以下は無料）
- 推定VRAM: ~75GB → RTX PRO 6000に収まる

**第2選択: qwen3-coder-next:80b** (SWE-bench 69.6%推定)
- 80B total / 3B active (MoE)、推定VRAM ~50GB → 軽量で高速
- 256Kコンテキスト、ツール呼び出し対応
- devstral-2がVRAM不足またはタイムアウト時の代替

#### 調査・検索・RAG系タスク

**第1選択: command-a:111b** (RAG特化訓練済)
- Cohere製、256Kコンテキスト、23言語対応
- RAG特化訓練を明示的に受けた数少ないモデル
- ツール使用（API、DB、検索エンジン連携）対応
- 推定VRAM: ~67GB (Q4_K_M) → RTX PRO 6000に収まる

**代替: nemotron-3-nano:30b** (軽量・常駐可能)
- 512K+コンテキスト、IFBench 71.5%
- 簡易な検索・要約には十分だが、command-aのRAG特化には及ばない

#### 推論・検証系タスク

**第1選択: gpt-oss:120b** (o4-mini相当の推論力)
- OpenAI製、MXFP4で~80GB VRAM、128Kコンテキスト
- configurable reasoning effort（low/medium/high）
- chain-of-thought完全アクセス
- Phase 3のClaude統合前のローカル品質検証に最適

**軽量代替: phi4-reasoning:plus** (14B、~9GB)
- o3-mini蒸留+RL、推論特化
- 5070 Tiでも動作可能（ministralをアンロードすれば）
- 簡易な検証タスクに適する

#### 画像解析・マルチモーダル

**第1選択: gemma3:27b** (Vision対応)
- 128Kコンテキスト、140言語、画像入力対応
- 推定VRAM: ~18GB → PRO 6000で余裕で動作
- スクリーンショット解析、UI検証、画像内テキスト読取に最適

**軽量代替: ministral-3:14b** (Vision対応、Edge向け)
- 256Kコンテキスト、Vision対応
- ~9GB VRAM → 5070 Tiでも動作可能

#### 翻訳

**translategemma:27b** (翻訳特化)
- 55言語対応、翻訳専用モデル
- 日英・英日翻訳の精度が汎用モデルより高い
- 推定VRAM: ~18GB → PRO 6000で動作

#### タスク分析・ルーティング（常駐）

**nemotron-3-nano:30b** (3.5B active, MoE)
- ハイブリッドMoE（Mamba-2 + Attention）
- reasoning on/off切替可能
- 512Kコンテキスト、日本語対応
- ルーティング・初期分析に十分な能力

### 4.2 新しいPhase 2タスクカテゴリ

旧設計の4カテゴリ（検索/レポート/アーキテクト/コーディング）を、実際のユースケースに即した6カテゴリ+特殊カテゴリに拡張します。

| カテゴリ | 最適モデル | VRAM | 役割 |
|---------|-----------|------|------|
| **coding** | devstral-2:123b | 75GB | コード生成・修正・レビュー |
| **research** | command-a:111b | 67GB | 調査・RAG検索・情報収集 |
| **reasoning** | gpt-oss:120b | 80GB | 推論・論理検証・品質チェック |
| **vision** | gemma3:27b | 18GB | 画像解析・UI検証 |
| **translation** | translategemma:27b | 18GB | 翻訳タスク |
| **lightweight_code** | qwen3-coder-next:80b | 50GB | 軽量コーディング（devstral代替） |
| **lightweight_verify** | phi4-reasoning:plus | 9GB | 軽量検証（gpt-oss代替） |

Claudeが Phase 1 で各タスクに最適なカテゴリとモデルを選択します。

---

## 第5部: 記憶システムの設計

### 5.1 二層記憶アーキテクチャ

```
┌───────────────────────────────────────────────────┐
│              記憶システム全体像                      │
├───────────────────────────────────────────────────┤
│                                                    │
│  ■ 短期記憶（Session Memory）                      │
│    - 現在の会話の全文をテキストファイルに保存        │
│    - Phase間の中間成果物もファイルとして保持         │
│    - セッション終了時に長期記憶へ移行処理            │
│    - 保存先: data/sessions/{session_id}/            │
│                                                    │
│  ■ 長期記憶（Knowledge Base）                      │
│    - SQLite + qwen3-embedding:4bでベクトル検索      │
│    - 重要な情報のみ要約・整理して保存               │
│    - Claudeが引用可能（RAG）                        │
│    - mixAI / soloAI 共通で利用                      │
│    - 保存先: data/knowledge/knowledge.db            │
│                                                    │
└───────────────────────────────────────────────────┘
```

### 5.2 短期記憶（Session Memory）

**目的**: 現在の会話を完全に保持し、Claudeとローカルが参照できるようにする。

```
data/sessions/{session_id}/
├── conversation.jsonl       # 会話全文（user/assistant交互）
├── phase1_plan.json         # Phase 1の計画JSON
├── phase1_claude_answer.txt # Phase 1のClaude初回回答
├── phase2/
│   ├── task_1_devstral.txt  # Phase 2各タスクの成果物
│   ├── task_2_command_a.txt
│   └── task_3_gpt_oss.txt
├── phase3_integration.txt   # Phase 3の統合結果
├── context_summary.txt      # 会話が長くなった場合の要約
└── metadata.json            # セッションメタデータ
```

**トークン上限対策**:
- 会話が長くなりClaudeの入力トークンを超える場合、nemotron-3-nano:30bで会話の前半部分を要約し `context_summary.txt` に保存
- Claudeへは「要約 + 直近の会話数ターン」を送信
- Phase 2の成果物が長い場合も、ministral-3:8bで要約してから Phase 3 に渡す

### 5.3 長期記憶（Knowledge Base）

**目的**: 過去の重要な情報を整理保存し、将来の会話で引用可能にする。

**保存フロー**:

```
セッション終了時 or 明示的な保存指示
    ↓
[nemotron-3-nano:30b] 会話から重要情報を抽出
    ├── 技術的な決定事項
    ├── プロジェクト固有の知識
    ├── ユーザーの好み・要件
    └── 解決したバグ・問題と解決策
    ↓
[qwen3-embedding:4b] テキストをベクトル化
    ↓
SQLiteに保存（テキスト + ベクトル + メタデータ）
```

**検索フロー（RAG）**:

```
Phase 1でClaudeが計画立案する際
    ↓
[アプリ側] ユーザー入力をqwen3-embedding:4bでベクトル化
    ↓
SQLiteでベクトル類似度検索（上位5件）
    ↓
検索結果をClaudeのコンテキストに注入
```

**mixAI / soloAI 共通利用**: 長期記憶はタブに依存せず共通のKnowledge DBとして機能します。soloAIタブでも同じDBにアクセスし、過去の会話知識を参照可能にします。

---

## 第6部: UI改善設計

### 6.1 チャット出力の改善

**現状の問題**: Stage毎に内部ログ形式で表示される

**改善後**: Claudeの最終統合回答のみをチャットエリアに自然な日本語で表示

```
┌──────────────────────────────────────────────┐
│  チャットエリア                                │
│                                               │
│  👤 ユーザー: hello_world.pyをGUIアプリに...  │
│                                               │
│  🤖 Claude:                                   │
│  hello_world.pyをTkinterベースのGUIアプリに   │
│  更新しました。名前入力欄と挨拶ボタンを      │
│  備えた画面で、PyInstallerでexeファイルも     │
│  生成済みです。                                │
│                                               │
│  ▼ 実行詳細（クリックで展開）                 │
│  ┌────────────────────────────────────────┐   │
│  │ Phase 1: Claude計画立案 (2.1s)         │   │
│  │ Phase 2: devstral-2:123b (45.2s)       │   │
│  │ Phase 3: Claude統合 (8.3s)             │   │
│  │ 合計: 55.6s                            │   │
│  └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 6.2 ツール実行ログの改善

**現状の問題**: カラムが切れて展開できない

**改善後**:

```
┌──────────────────────────────────────────────────────┐
│ ▼ ツール実行ログ（クリックで折りたたみ）              │
├──────────────────────────────────────────────────────┤
│                                                       │
│ ● Phase 1: Claude計画立案                    ✅ 2.1s │
│   Claude Opus → 3タスク計画                           │
│   [詳細を表示]                                        │
│                                                       │
│ ● Phase 2-1: コーディング                    ✅ 45.2s│
│   devstral-2:123b (PRO 6000, 75GB)                   │
│   → hello_world.py修正完了                            │
│   [出力全文を表示]                                    │
│                                                       │
│ ● Phase 2-2: 品質検証                        ✅ 12.1s│
│   gpt-oss:120b (PRO 6000, 80GB)                      │
│   → コード品質OK、改善提案2件                         │
│   [出力全文を表示]                                    │
│                                                       │
│ ● Phase 3: Claude統合                        ✅ 8.3s │
│   Claude Opus → 最終統合完了                          │
│   [詳細を表示]                                        │
│                                                       │
│ ● 記憶保存                                   ✅ 0.5s │
│   Knowledge DB更新 (計15件)                           │
│                                                       │
└──────────────────────────────────────────────────────┘
```

各行が展開可能なアコーディオンUI、出力全文表示ダイアログ付き。

### 6.3 Neural Flow Visualizerの改善

3Phaseに合わせて簡素化:

```
[P1:Claude計画] ──→ [P2:ローカルLLM] ──→ [P3:Claude統合]
    ✅ 2.1s           ⏳ 実行中            ○ 待機中

P2内部（展開時）:
  [devstral-2] ✅ → [gpt-oss] ⏳ → [command-a] ○
```

### 6.4 設定タブの改善

**カテゴリ別モデル設定**:

各カテゴリ（coding, research, reasoning, vision, translation）に対して:
- 第1選択モデル（ドロップダウン）
- 代替モデル（ドロップダウン）
- タイムアウト秒数
- GPU指定（自動/PRO 6000/5070 Ti）

**常駐モデル設定**:
- 制御AI: ministral-3:8b（変更可能）
- Embedding: qwen3-embedding:4b（変更可能）
- タスク分析: nemotron-3-nano:30b（変更可能）
- 各モデルのGPU割り当て表示

**VRAM Budget Simulator**:
- 実際のGPUインデックスに基づく表示（nvidia-smi連動）
- 現在ロード中のモデルのVRAM使用量リアルタイム表示
- Phase 2実行計画のVRAMシミュレーション

---

## 第7部: BIBLEファイル管理機能

### 7.1 設計

ファイル操作を伴うタスクでは、対象プロジェクトのBIBLEファイルを自動的に管理します。

**BIBLEテンプレート**:

```markdown
# [プロジェクト名] - BIBLE
**バージョン**: 1.0.0
**作成日**: YYYY-MM-DD
**最終更新**: YYYY-MM-DD

## プロジェクト概要
[概要]

## 設計思想
[設計思想]

## ディレクトリ構造
[構造]

## 技術スタック
[スタック]

## 変更履歴
| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
```

**動作フロー**:

```
Phase 1でファイル操作を検出
    ↓
[アプリ側] 対象ディレクトリにBIBLE*.mdが存在するか確認
    ↓
存在する場合:
    → BIBLEの内容をClaudeのコンテキストに注入
    → Phase 3完了後にBIBLEを更新
    ↓
存在しない場合:
    → テンプレートから新規作成
    → Phase 3完了後に情報を記入
```

---

## 第8部: 実装優先順位

### 最優先（v7.0.0 Core）

| 優先度 | 項目 | 概要 |
|--------|------|------|
| P0 | 3Phase実行エンジン | mix_orchestrator.pyの全面書き直し |
| P0 | Phase 1 JSON生成 | Claudeの構造化出力→JSON→ファイル保存 |
| P0 | Phase 2 順次実行 | Ollamaモデルロード/実行/アンロードの制御 |
| P0 | Phase 3 統合 | Claude 2回目呼び出し + 再実行ループ |
| P0 | チャット出力改善 | 最終回答のみ表示、ログは折りたたみ |

### 高優先（v7.0.0 機能）

| 優先度 | 項目 | 概要 |
|--------|------|------|
| P1 | 短期記憶 | セッション内テキストファイル保存 |
| P1 | 長期記憶（RAG） | SQLite + Embedding検索 |
| P1 | ministral制御AI | 指示変換・出力フィルタリング |
| P1 | ツール実行ログUI | アコーディオンUI、出力全文表示 |

### 中優先（v7.0.0 改善）

| 優先度 | 項目 | 概要 |
|--------|------|------|
| P2 | BIBLE管理 | 自動検出・テンプレート生成 |
| P2 | VRAM Simulator修正 | GPU動的検出、リアルタイム表示 |
| P2 | Neural Flow 3Phase化 | 3Phase + サブステップ表示 |
| P2 | soloAI記憶共有 | Knowledge DB共通利用 |
| P2 | Ollama接続テスト修正 | 属性エラー解消 |

---

## 第9部: Claude Code CLI用 実装指示の骨格

以下はv7.0.0の実装をClaude Codeに依頼する際の指示書の骨格です。

```
## Helix AI Studio v7.0.0 "Orchestrated Intelligence" 実装指示

### 前提条件
1. v6.3.0のソースコード全文を読むこと（特にmix_orchestrator.py）
2. 旧5Phaseの実装を完全に理解した上で、新3Phaseに書き換えること
3. 表面的な修正（バージョン番号変更のみ等）は絶対に行わないこと

### 実装検証基準
各ステップ完了後、以下を実証すること:
- Ollamaに「ollama ps」コマンドを実行し、
  Phase 2で実際にモデルがロードされたことを確認
- logs/ に各Phaseの入出力ログが記録されていること
- Claude CLIが2回呼び出されたことをログで確認

### 作業手順
[本プランの第3部～第6部に基づく具体的な実装指示を挿入]
```

---

*このプランは Claude Opus 4.6 により Helix AI Studio v6.3.0 の包括的検証と利用可能モデルの特性分析に基づいて作成されました*
*2026-02-08*
