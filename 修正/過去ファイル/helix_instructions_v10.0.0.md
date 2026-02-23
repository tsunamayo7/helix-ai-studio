# Helix AI Studio — v9.9.2 → v10.0.0 更新依頼

**作業対象:** `C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio`

**提出物（全バッチ共通）:**
- 変更ファイル一覧と差分サマリー（変更前後の該当行番号を含むこと）
- 更新後BIBLE（`BIBLE/BIBLE_Helix AI Studio_10.0.0.md`）
- 動作確認ログ（テスト項目・設定・結果を明記）
- `helix_source_bundle.txt` 再生成（`scripts/build_bundle.py` 実行）
- `GitHub/` 内の README.md / README_ja.md / CHANGELOG.md 更新

---

## 【前提・作業ルール】

1. **i18n連動ルール（全バッチ共通）:**
   新規追加・変更するすべてのUI文字列は `i18n/ja.json` と `i18n/en.json` へ**同時登録**し、
   `retranslateUi()` または React の `t()` で参照すること。ハードコードは一切禁止。

2. **後方互換ルール:**
   既存の日本語UIは変更しない。英語は切替時のみ適用。

3. **確認→報告→修正→検証のサイクル:**
   "設計はあるはず" という推定で実装完了とせず、**実ファイルの行番号を示して**存在を確認した上で修正すること。

4. **バッチ独立性:**
   各バッチは独立して実行できること。前バッチの成果物（修正済みファイル）を引き継いで次バッチを実行すること。

---

# ═══════════════════════════════════════════
# バッチA — Opus 4.6 担当（アーキテクチャ整合・品質強化）
# ═══════════════════════════════════════════

**推奨モデル:** Claude Opus 4.6
**理由:** 複数ファイルにまたがる設計整合の確認・記憶4層の仕様精査・残存コード排除など、
深い文脈保持と網羅的な論理検証が必要なタスク群。

---

## A-1. 未導入ツール選択時のエラー表示強化

**対象:** Anthropic CLI（Claude CLI）/ OpenAI CLI（Codex CLI）/ Ollama

**確認手順（実施してから修正）:**
`src/backends/` および `src/tabs/` の各ファイルを開き、以下を行番号付きで列挙すること。
- 各CLIの未インストール検出箇所
- 未インストールモデル選択時の処理箇所
- エラーメッセージのハードコードがあれば i18n化

**実装要件:**
- CLI未インストール時 → ステータスバーにアイコン付きエラー表示（i18n対応）
- Ollama未起動時 → 既存の接続テストボタンに加え、モデル選択ドロップダウンを無効化してツールチップ表示
- 未インストールモデル選択時 → 実行ボタン押下時にダイアログ（i18n対応）
- エラー発生時にDiscord Webhook通知を送信（A-5の実装後に連動すること）

---

## A-2. Claude-Mem流儀の記憶4層整合確認・修正

**確認手順:**
`src/memory/memory_manager.py` を全文精査し、以下を報告すること。

- Layer 1（Thread）→ Layer 2（Episodic）→ Layer 3（Semantic）→ Layer 4（Procedural）→ Layer 5（Document）の各遷移ロジックが実装されているか
- Memory Risk Gate（`ministral-3:8b` による保存/破棄判定）の実行フロー：
  「どのファイルの何行目で、どのモデルを呼び出し、どの条件で保存/破棄するか」を明記
- `evaluate_and_store()` の呼び出し元がmixAI/soloAI両方に存在するか
- `build_context_phase1_short()` が実際にPhase 1注入に使われているか、詳細注入との切替が機能しているか

**修正要件（確認後に必要な箇所のみ修正）:**
- 上記確認で欠落・不整合が発覚した箇所を修正
- memory_scope キーを `{app, project, chat}` の3値に統一（mixAI/soloAI共通）
- ローカルLLM（Memory Risk Gate）が失敗した場合のフォールバック：
  「保存判定をスキップして保存」または「破棄」のどちらかをconfigで選択可能にする（クラウドAIへの丸投げは禁止）

---

## A-3. 記憶・RAGの「混線防止」仕様の明文化と実装

**実装要件:**
- `chat_id` / `project_id` / `app_id` の3スコープをメモリDBの全テーブルに付与（未付与テーブルがあれば追加）
- チャット削除時のクリーンアップ定義：
  `DELETE FROM episodic_memory WHERE chat_id = ?` 相当の処理を `chat_store.py` の削除APIに追加
- RAG検索時に他チャットの記憶がヒットしないよう `WHERE chat_id = ?` フィルタを確認・追加
- 翻訳キー・UI部品だけが残存する「幽霊データ」の定義と定期整理処理（`_cleanup_orphaned_memories()` として `memory_manager.py` に追加）

---

## A-4. Web セッション永続性の確認・修正

**確認手順:**
`src/web/auth.py` を全文精査し、以下を報告すること（推測不可、実コードで確認）。
- JWT秘密鍵の生成箇所と保存先（ファイル/メモリ/config）
- アプリ再起動後も同じ鍵が使われるか
- JWT有効期限とリフレッシュ処理の有無

**修正要件（確認後に必要な箇所のみ）:**
- 秘密鍵がメモリ生成の場合 → `config/web_config.json` への永続化に変更（初回生成時のみ書き込み、以降は読み込み）
- 有効期限が短すぎる場合（1時間未満）→ デフォルト24時間に変更し、configで設定可能にする

---

## A-5. Discordを「通知専用」として活用（強化版）

**現状:** Discord Webhook URL設定とDiscord送信ボタンは実装済み（一般設定タブ）

**追加実装要件:**
- 通知トリガー（すべてi18n対応メッセージ）:
  - mixAI / soloAI 実行開始時
  - 正常完了時（実行時間・使用Phaseを含む）
  - エラー発生時（エラー内容を含む）
  - Web UI接続時（接続URLとQRコードを送信 ← 後述のA-6名前URLを使用）
- 通知のON/OFFは一般設定タブのトグルで制御（i18n対応）
- QRコードはPythonの `qrcode` ライブラリで生成してDiscordに添付
  （`pip install qrcode[pil]` を `requirements.txt` に追加）

---

## A-6. スマホ接続URLの名前ベース化

**問題:** 現在のWeb UI接続URLがTailscale IPアドレス直書き（`100.x.x.x:8500`）

**実装要件:**
- `general_settings.json` に `web_host_name` フィールドを追加（例: `"helix-studio"`, デフォルト空文字）
- `web_host_name` が設定されていれば `http://<web_host_name>:8500` をプライマリURLとして使用
- 未設定の場合はTailscale IP → localhost の順でフォールバック
- 一般設定タブに「ホスト名（任意）」入力欄を追加（i18n対応）
- 一般設定タブの「URLをコピー」「QRを表示」ボタンはプライマリURLで動作
- IPアドレスは「詳細を表示」折り畳みセクションに格納（デフォルト非表示）
- Web接続時のDiscord通知（A-5）もプライマリURLを使用

---

## A-7. 残存コードの完全排除

**確認・修正手順:**
以下を `grep -rn` 等で全ファイル検索し、残存があれば削除すること。
- `settings_diff` への参照（import / 関数呼び出し）→ v9.9.2で削除済みのはずだが念のため確認
- `preset_opus_codex` への参照
- `presetLabel` / `presetOpusCodexTip` / `presetApplied` のi18nキー使用箇所
- `show_settings_diff_dialog` / `load_settings_snapshot` への参照

検索結果（ゼロ件であることの確認ログ）を提出物に含めること。

---

## A-8. プロンプトキャッシュ最適化

**背景・要件:**
Claudeのprompt caching機能（beta）を活用してトークン消費・遅延・コストを削減する。

**実装方針（以下の優先順で検討・実装）:**

1. **システムプロンプトのキャッシュ化:**
   `src/backends/mix_orchestrator.py` のPhase 1/3において、BIBLEコンテンツ・メモリコンテキストを含む
   システムプロンプト部分を `cache_control: {"type": "ephemeral"}` 付きで送信するよう変更。
   対象: Claude CLI経由の場合は `--system` パラメータにキャッシュ対象を集約する設計を検討。

2. **会話履歴の先頭キャッシュ:**
   長いチャット履歴がある場合、先頭のN件（configで設定可能、デフォルト10件）を
   キャッシュ対象として扱い、都度送信しない設計を検討。

3. **トークン節約ログ:**
   キャッシュヒット時に節約されたトークン数をステータスバーに表示（i18n対応）

**注意:** Claude CLI（`claude -p`）経由では直接APIのキャッシュ制御が困難な場合、
`--system` フラグへのBIBLE/メモリ集約（現在の `build_context_phase1_short()` 活用）を
最優先として実施し、直接API呼び出しへの移行は将来課題として記録すること。

---

# ═══════════════════════════════════════════
# バッチB — Sonnet 4.6 担当（UI・機能拡張）
# ═══════════════════════════════════════════

**推奨モデル:** Claude Sonnet 4.6
**理由:** UIコンポーネント追加・Phase構成変更・モデル選択肢追加など、
パターンが明確で定型的な実装タスク群。

**前提:** バッチAの成果物（修正済みファイル）を取り込んだ状態で実行すること。

---

## B-1. 言語設定 English の完全適用

**確認手順（実施してから修正）:**
以下のコマンドで未キー化文字列を全列挙し、報告すること。
```bash
# PyQt6: setText/setTitle/setPlaceholderText/setToolTipでt()を使っていない行
grep -rn 'setText\|setTitle\|setPlaceholder\|setToolTip' src/tabs/ src/widgets/ | grep -v "t('"

# React: t()を使わず日本語・英語文字列をハードコードしている行
grep -rn '"[ぁ-んァ-ヶ一-龠]' frontend/src/
grep -rn "'[ぁ-んァ-ヶ一-龠]" frontend/src/
```

**修正要件:**
- 発見したすべての未キー化文字列を `i18n/ja.json` / `i18n/en.json` へ追加
- `retranslateUi()` に未登録のウィジェットがあれば追加
- バッチBで新規追加するすべてのUI要素も同時にキー化すること

---

## B-2. mixAIタブのタイトル整合とPhase順整列

**参照:** `2_mixAI設定1.png` および `2_mixAI設定1en.png`

**変更要件:**
- グループボックスの名称変更:
  - 「モデル設定」→「Phase 1 / 3」（i18n key: `desktop.mixAI.phase13GroupLabel`）
  - 「Phase2ローカルLLM設定」→「Phase 2」（i18n key: `desktop.mixAI.phase2GroupLabel`）
- 設定UIのレイアウト順をPhase番号順に整列:
  Phase 1/3 → Phase 2 → Phase 3.5（B-4で追加）→ Phase 4
- 既存の英語訳も同様に更新

---

## B-3. Phase 2のクラウドAI選択肢追加とJSON出力統一

**変更要件（`src/backends/mix_orchestrator.py` / `src/tabs/helix_orchestrator_tab.py`）:**

- Phase 2のcoding カテゴリの選択肢に以下を追加:
  - `GPT-5.3-Codex (CLI)` （key: `gpt-5.3-codex-cli`）
  - `Claude Sonnet 4.6 (CLI)` （key: `claude-sonnet-4.6-cli`）
  - `Claude Opus 4.6 (CLI)` （key: `claude-opus-4.6-cli`）

- **出力形式の統一（全Phase 2カテゴリ共通）:**
  Phase 2の出力は必ず以下のJSONスキーマに準拠させる。
  実行後にパース失敗した場合は最大2回リトライ、それでも失敗した場合はプレーンテキストとして
  Phase 3に渡す（フォールバック）。
  ```json
  {
    "category": "coding",
    "model_used": "...",
    "output": "...",
    "confidence": 0.0-1.0,
    "notes": "..."
  }
  ```

- **フォールバック設計:**
  1. 指定モデルが利用不可 → 同カテゴリの次の選択肢（軽量候補）へ自動フォールバック
  2. 全選択肢不可 → Phase 2スキップしてPhase 3へ（既存スキップ機能を流用）
  3. フォールバック発生時はステータスバーとDiscord通知（A-5連動）

---

## B-4. Phase 3.5の導入（5Phase体制）

**変更要件:**

- **Phase体制変更:** 現在の「Phase 1→2→3→4」を「Phase 1→2→3→3.5→4」に変更
- **Phase 3.5の仕様:**
  - デフォルト: `None`（スキップ）
  - 目的: 大規模アプリ構築時の「最終レビュー」「最小修正指示」
  - 利用可能モデル:
    - `GPT-5.3-Codex (CLI)` 
    - `Claude Sonnet 4.6 (CLI)`
    - `Claude Opus 4.6 (CLI)`
  - 実行内容: Phase 3の出力を受け取り、大規模修正が必要かを判定。
    - 大規模修正が必要 → Phase 3に差し戻し指示を出力してPhase 3を再実行（最大1回）
    - 軽微な修正のみ → 修正指示をPhase 4に渡してPhase 4で適用
  - `mix_orchestrator.py` に `_execute_phase35()` を追加
  - mixAI設定タブに「Phase 3.5」設定グループを追加（B-2のPhase順整列に合わせる）
  - i18n対応: `desktop.mixAI.phase35GroupLabel` 等

---

## B-5. Web情報収集ロジックの確認・強化・ユーザー選択機能

**確認手順（実施してから修正）:**
`src/tabs/claude_tab.py`（soloAI）の `search_mode_combo` と、
`src/backends/mix_orchestrator.py`（mixAI Phase 1/3）の情報収集処理を精査し、
以下を報告すること。
- WebSearch / BrowserUse それぞれの実装状況（未実装 / 骨格のみ / 完全実装）
- 検索結果をプロンプトに挿入する際のトークン数見積もり（平均的なケース）
- 検索結果の重複・冗長部分の削減処理の有無

**実装要件（確認結果に基づいて修正）:**

1. **トークン削減ロジック（未実装の場合に追加）:**
   - 検索結果のHTML/Markdownをプレーンテキストに変換してから挿入
   - 挿入するトークン数の上限をconfigで設定可能（デフォルト: 2000トークン相当）
   - 上限超過時は先頭からトリムし、省略マーカーを付与

2. **ユーザーによる方式選択（soloAI・mixAI両対応）:**
   - 選択肢: `なし` / `WebSearch（Brave/DuckDuckGo）` / `BrowserUse（browser_use）`
   - WebSearch: `browser_use` 未インストール時でも動作するフォールバック実装
   - BrowserUse: `browser_use` 未インストール時は選択肢をグレーアウト＋ツールチップ表示
   - mixAIでの選択はPhase 1の情報収集ステップに適用
   - 選択状態は設定として永続化

3. **BrowserUse最適化:**
   `browser_use` 使用時は結果テキストを2000トークン上限でクリッピング後に挿入

---

## B-6. OpenAI互換サーバー対応とカスタムモデル管理

**背景:** OllamaにないモデルをOpenAI互換サーバー（llama.cpp, vLLM等）経由で使用可能にする。
また、ユーザーが各Phaseの選択肢に表示するモデルを自由に設定できるようにする。

**実装要件:**

### B-6-1. OpenAI互換サーバー接続設定
- 一般設定タブに「カスタムサーバー」セクションを追加:
  - サーバーURL（例: `http://localhost:8080/v1`）
  - APIキー（オプション、デフォルト空文字=`"none"`）
  - 接続テストボタン（`/v1/models` を叩いてモデル一覧を取得）
- `src/backends/` に `openai_compat_backend.py` を新規作成
  - `httpx` または `requests` でOpenAI互換APIを呼び出す
  - Ollama APIと同等のインターフェースでラップ

### B-6-2. カスタムモデル表示管理UI
- mixAI設定タブの各Phase（P1/3, P2各カテゴリ, P3.5, P4）に、
  「表示モデルを管理」ボタンを追加
- クリックするとダイアログが開き、以下が可能:
  - モデル一覧表示（Ollama検出済み / カスタムサーバー検出済み / 手動登録）
  - チェックボックスでPhaseの選択肢に表示/非表示を切替
  - 手動でモデル名を追加（フリーテキスト入力）
  - 設定は `config/custom_models.json` に保存
- すべてi18n対応（`desktop.mixAI.manageModels` 等のキーを追加）

### B-6-3. GPT-OSS Swallow 120B GGUF の導入設定テンプレート
- `config/custom_models.json` の初期テンプレートに以下を含める（コメント付き）:
  ```json
  {
    "_comment": "GPT-OSS Swallow 120B: llama.cpp server起動例",
    "_command": "llama-server -m GPT-OSS-Swallow-120B-RL-v0.1-Q4_K_M.gguf --port 8080 -ngl 99",
    "name": "GPT-OSS Swallow 120B (GGUF)",
    "server_url": "http://localhost:8080/v1",
    "api_key": "none",
    "enabled": false
  }
  ```
- README_ja.md にGPT-OSS Swallow導入手順セクションを追加

---

## B-7. ①の英語適用（B-2〜B-6で追加した要素の漏れチェック）

B-2〜B-6で追加・変更したすべてのUI要素について、
`i18n/ja.json` と `i18n/en.json` への登録漏れがないことを最終確認し、
English切替での動作をテストして確認ログを提出すること。

---

# ═══════════════════════════════════════════
# バッチC — Opus 4.6 担当（統合・最終整合）
# ═══════════════════════════════════════════

**推奨モデル:** Claude Opus 4.6
**前提:** バッチA・Bの成果物を取り込んだ状態で実行すること。

---

## C-1. バージョン更新と最終整合

- `src/utils/constants.py`: `APP_VERSION = "10.0.0"`, `APP_CODENAME = "Enterprise Ready"`
- バッチA・Bで変更したすべてのファイルについて、BIBLEの記載と実コードの整合を最終確認
- `requirements.txt` の更新確認: `qrcode[pil]` 追加、`httpx` or `requests` 追加
- `helix_source_bundle.txt` 再生成

---

## C-2. BIBLE v10.0.0 作成

`BIBLE/BIBLE_Helix AI Studio_10.0.0.md` を新規作成。

**必須記載事項:**
- バッチA〜Cすべての変更を反映したアーキテクチャ図
- Phase体制の更新: 4Phase → 5Phase（Phase 3.5追加）
- 5Phase実行フロー詳細（各Phaseの入出力・フォールバック条件）
- OpenAI互換サーバー接続アーキテクチャ
- カスタムモデル管理フロー
- 記憶4層 + memory_scope統一の最終仕様
- Memory Risk Gateの実装確認結果（実ファイル・行番号付き）
- JWT永続化の実装確認結果（実ファイル・行番号付き）
- プロンプトキャッシュ対応状況
- Changelog（v9.9.2 → v10.0.0）
- テストチェックリスト（既存継承 + 新規追加分）
- 既知の制限事項（更新）

---

## C-3. 最終テストチェックリスト実行

以下をすべて実施し、結果を提出物に含めること。

| # | テスト項目 | 確認内容 |
|---|-----------|---------|
| C-1 | CLI未インストールエラー | Claude/Codex/Ollama各未導入状態でエラー表示確認 |
| C-2 | 5Phase実行 | Phase 3.5=Noneでスキップ / Phase 3.5指定で動作確認 |
| C-3 | Phase 2 JSON出力 | cloud AIモデル選択時の出力がJSONスキーマに準拠 |
| C-4 | フォールバック | Phase 2モデル不可時にスキップ動作確認 |
| C-5 | カスタムサーバー | 接続テストボタンでモデル一覧取得確認 |
| C-6 | カスタムモデル表示管理 | 追加/非表示/保存/読み込みサイクル確認 |
| C-7 | Web情報収集 | WebSearch/BrowserUseトークン上限クリッピング確認 |
| C-8 | Discord通知 | 開始/完了/エラー/Web接続時の通知確認 |
| C-9 | 名前URLコピー・QR | ホスト名設定時のURLが名前ベースになることを確認 |
| C-10 | JWT再起動永続 | サーバー再起動後もログイン状態が維持されることを確認 |
| C-11 | memory_scope混線防止 | 別チャットの記憶が検索結果に出ないことを確認 |
| C-12 | English完全適用 | i18n切替で全UI文字列が英語化されることを確認（B-7継承）|
| C-13 | Phase順表示 | mixAI設定タブがPhase 1/3→2→3.5→4の順で表示されることを確認 |
| C-14 | 回帰テスト | soloAI/mixAI正常動作・チャット履歴・BIBLE Manager・一般設定保存 |

---

*以上。バッチの境界は Claude Code のコンテキスト上限リスクを避けるための分割です。*
*各バッチの開始時に必ず `helix_source_bundle.txt` を最新状態で読み込んでから作業を開始してください。*
