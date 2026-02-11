# Helix AI Studio v7.0.0 Claude Code実装指示書

**重要**: この指示書は3回に分けてClaude Codeに投入してください。
各回の完了後、動作確認を行ってから次に進んでください。

---

## 投入前の準備

### プランファイルの配置

`HelixAIStudio_v7_UpdatePlan.md` を以下に配置:
```
C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio\修正\HelixAIStudio_v7_UpdatePlan.md
```

### 各回の投入方法

Claude Codeのターミナルで以下のように投入:
```bash
cd "C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio"
claude
```
対話モードで指示テキストを貼り付けてください。

---

## 第1回: バックエンド（3Phase実行エンジン）

### 指示テキスト（以下をそのままコピーして貼り付け）

```
Helix AI Studio v7.0.0 のバックエンド実装を行います。

## 必読ファイル
以下のファイルを先に全文読んでから作業してください:
1. 修正/HelixAIStudio_v7_UpdatePlan.md の「第3部: 新3Phase実行パイプライン設計」（セクション3.1～3.4）
2. 修正/HelixAIStudio_v7_UpdatePlan.md の「第3.5部: Claude MCPツール戦略」（セクション3.5.0～3.5.5）
3. src/backends/mix_orchestrator.py（現在の実装を理解するため）
4. src/backends/parallel_pool.py
5. src/backends/phase1_parser.py
6. src/backends/phase1_prompt.py
7. src/backends/phase4_prompt.py

## 作業内容

### 1. 旧5Phase→新3Phaseへの書き換え
src/backends/mix_orchestrator.py を全面的に書き換えてください。

旧実装の実態（動作していない5Phase）:
  Stage 1: タスク分析（nemotron） → Stage 2: Claude CLI（1回） → Stage 3: 画像解析 → Stage 4: RAG → Stage 5: バリデーション

新3Phase:
  Phase 1: Claude CLI計画立案（--cwdオプション追加、システムプロンプトにツール使用指示を明記）
  Phase 2: ローカルLLM順次実行（Ollama APIで1モデルずつロード→実行→アンロード）
  Phase 3: Claude CLI比較統合（2回目呼び出し、Phase 1+Phase 2全結果を渡す）

### 2. Phase 1 システムプロンプトの実装
プランのセクション3.5.5に記載の _build_phase1_system_prompt() を実装してください。
重要ポイント:
- 「利用可能なツール」セクションでRead, Bash, Glob, Grep, WebSearch, WebFetchを明示的に列挙
- 出力形式としてJSON（claude_answer + local_llm_instructions）を指定
- complexityに基づくPhase 2スキップ判定を含める

### 3. Phase 2 順次実行エンジン
parallel_pool.py を書き換えて sequential_executor.py を作成:
- Ollama API /api/generate を使用
- モデルのロード待機（/api/tags でロード状態確認）
- 1モデルずつ順次実行（並列ではない）
- 各タスクの結果を data/phase2/task_{order}_{model}.txt に保存
- chain-of-thoughtフィルタリングを維持（v6.3.0のfilter_chain_of_thought()を継承）

### 4. Phase 3 統合プロンプトの実装
プランのセクション3.5.5に記載の _build_phase3_system_prompt() を実装:
- Phase 1の自身の回答を含める
- Phase 2の全ローカルLLM結果を含める
- ツール使用指示（Read/Write/Edit, Bash, WebSearch）を含める
- 品質不足時の再実行指示JSON出力形式を定義

### 5. Claude CLI呼び出し方法の変更
現在:
  cmd = ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json", "--model", "opus"]
  stdin: ファイル内容埋め込み済みプロンプト

変更後:
  cmd = ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json", "--model", "opus", "--cwd", project_dir]
  stdin: システムプロンプト（ツール使用指示付き）+ ユーザー入力
  ※ファイルの埋め込みは削除。Claudeが自分でReadツールを使って読む設計に変更

### 6. 不要ファイルの削除
以下のファイルが不要になる場合は削除:
- src/backends/parallel_pool.py → sequential_executor.py に置き換え
- src/backends/phase4_prompt.py → phase3_prompt.py にリネーム（Phase 4→Phase 3に変更のため）
- その他、旧5Phaseで使用されていたが新3Phaseでは不要なファイル

### 7. constants.py の更新
APP_VERSION = "7.0.0"
APP_CODENAME = "Orchestrated Intelligence"

## 禁止事項
- 「既に実装されています」「確認しました」だけで済ませないこと。必ず実際のコードを変更すること
- 表面的な名前変更（Phase→Stageの置換等）だけで済ませないこと
- 旧Stage方式のコードを残さないこと
- _build_full_prompt()のファイル埋め込み方式を残さないこと

## 検証方法（作業完了後に必ず実施）
以下のコマンドで動作確認してください:

1. grep -r "Stage" src/backends/ で旧Stage参照が残っていないことを確認
2. grep -r "_build_full_prompt" src/ でファイル埋め込み方式が残っていないことを確認
3. grep -n "phase1\|phase2\|phase3\|Phase 1\|Phase 2\|Phase 3" src/backends/mix_orchestrator.py で3Phase構造が実装されていることを確認
4. grep -n "--cwd" src/backends/ で--cwdオプションが追加されていることを確認
5. grep -n "WebSearch\|Read\|Bash" src/backends/ でシステムプロンプトにツール使用指示が含まれていることを確認
```

### 第1回の動作確認チェックリスト

Claude Codeの作業完了後、つなまよさんが確認する項目:

- [ ] `src/backends/mix_orchestrator.py` が書き換わっている（diffで差分確認）
- [ ] `src/backends/sequential_executor.py` が新規作成されている
- [ ] Phase 1のシステムプロンプトに「Read」「Bash」「WebSearch」等のツール名が含まれている
- [ ] `--cwd` が Claude CLI コマンドに追加されている
- [ ] `_build_full_prompt()` のファイル埋め込みが削除されている
- [ ] `constants.py` が v7.0.0 になっている
- [ ] `grep -r "Stage" src/backends/` で旧Stage参照が出ない

---

## 第2回: UI改善 + 設定タブ

### 指示テキスト（以下をそのままコピーして貼り付け）

```
Helix AI Studio v7.0.0 のUI実装を行います。第1回でバックエンドの3Phase化は完了済みです。

## 必読ファイル
以下のファイルを先に全文読んでから作業してください:
1. 修正/HelixAIStudio_v7_UpdatePlan.md の「第6部: UI改善設計」
2. 修正/HelixAIStudio_v7_UpdatePlan.md の「第4部: 各Phase最適LLMの再設計」のセクション4.2
3. 修正/HelixAIStudio_v7_UpdatePlan.md の「第3.5部」のセクション3.5.7（MCP設定UI）
4. src/tabs/helix_orchestrator_tab.py（現在の実装）
5. src/widgets/neural_visualizer.py
6. src/main_window.py

## 作業内容

### 1. チャット出力エリアの改善
現状: 「Stage 2: Claude実行 / 使用モデル: Claude CLI (MCP)」という内部ログ形式で表示
改善: Phase 3のClaude統合回答（自然な日本語）のみをチャットエリアに表示

具体的には:
- mix_orchestrator.py の最終出力から claude_answer 部分のみを抽出してチャットに表示
- 内部ログ（各Phaseの実行結果、モデル名、実行時間等）は別セクションに格納

### 2. ツール実行ログのアコーディオン化
現状: 固定テーブルで出力が途中で切れている
改善: 各Phase行が展開可能なアコーディオン形式

プランの第6部セクション6.2のUI設計に従い:
- 各Phase行をクリックで展開/折りたたみ
- 展開時に出力全文を表示
- Phase 2はサブステップ（各モデルの実行）も展開可能

### 3. Neural Flow Visualizerの3Phase化
現状: P1:Claude → P2:Local → P3:検証 → P4:統合 → P5:保存 の5ノード
改善: Phase 1:Claude計画 → Phase 2:ローカルLLM → Phase 3:Claude統合 の3ノード

Phase 2ノードの中にサブステップ表示:
- 各モデルの実行状態（待機/実行中/完了/エラー）

### 4. 設定タブのカテゴリ変更
現状の4カテゴリ: 検索/レポート/アーキテクト/コーディング
新5カテゴリ: coding/research/reasoning/translation/vision

プランの第4部セクション4.2に記載の新カテゴリに合わせて設定UIを変更:
- coding: 第1選択 devstral-2:123b / 代替 qwen3-coder-next:80b
- research: 第1選択 command-a:111b / 代替 nemotron-3-nano:30b
- reasoning: 第1選択 gpt-oss:120b / 代替 phi4-reasoning:14b
- translation: translategemma:27b（専用）
- vision: gemma3:27b / mistral-small3.2:24b

### 5. 常駐モデル設定の変更
現状の常駐: nemotron-3-nano:30b(PRO 6000), ministral-3:8b(5070Ti), qwen3-embedding:4b(5070Ti)
新常駐: ministral-3:8b(5070Ti), qwen3-embedding:4b(5070Ti)
※ nemotron-3-nano:30bは常駐から外し、Phase 2の順次実行で使用

### 6. MCP設定セクションの追加
プランのセクション3.5.7に従い、設定タブにMCP設定セクションを追加:
- Claude Code CLIネイティブツール一覧（表示のみ）
- Claude Code CLI MCPサーバー状態（claude mcp listの結果表示）
- [Claude CLI設定を確認]ボタン

### 7. 不要UIの削除
旧5Phase関連の以下のUI要素を削除:
- Phase 4「統合」とPhase 5「保存」のNeural Flowノード
- 旧Stage表示（Stage 1, 2, 3...）
- 旧カテゴリ設定（検索/レポート/アーキテクト/コーディング）

## 禁止事項
- v6.3.0のUI要素を残したまま新UIを追加しないこと（混在させない）
- 旧5PhaseのNeural Flowノードを残さないこと
- 旧カテゴリ名（検索/レポート/アーキテクト/コーディング）を残さないこと

## 検証方法（作業完了後に必ず実施）
1. python HelixAIStudio.py を実行し、アプリが起動することを確認
2. mixAIタブのNeural Flow Visualizerが3ノード（P1, P2, P3）であることを目視確認
3. 設定タブで5カテゴリ（coding, research, reasoning, translation, vision）が表示されることを確認
4. grep -r "Stage\|P4:統合\|P5:保存\|レポート担当\|アーキテクト担当" src/tabs/ src/widgets/ で旧表示が残っていないことを確認
```

### 第2回の動作確認チェックリスト

- [ ] アプリが `python HelixAIStudio.py` で起動する
- [ ] Neural Flowが3ノード（P1/P2/P3）になっている
- [ ] 設定タブに5カテゴリ（coding/research/reasoning/translation/vision）がある
- [ ] 旧4カテゴリ（検索/レポート/アーキテクト/コーディング）が消えている
- [ ] MCP設定セクションが設定タブに存在する
- [ ] ツール実行ログが展開可能になっている

---

## 第3回: ビルド + BIBLE + 統合テスト

### 指示テキスト（以下をそのままコピーして貼り付け）

```
Helix AI Studio v7.0.0 の最終仕上げを行います。第1回でバックエンド、第2回でUIの実装が完了しています。

## 必読ファイル
1. 修正/HelixAIStudio_v7_UpdatePlan.md の「第5部: 記憶システムの設計」
2. 修正/HelixAIStudio_v7_UpdatePlan.md の「第7部: BIBLEファイル管理機能」
3. BIBLE/BIBLE_Helix AI Studio_6.3.0.md（前バージョンの形式を参考に）
4. HelixAIStudio.spec（PyInstaller設定）

## 作業内容

### 1. 記憶システムの実装
プランの第5部に従い:
- 短期記憶: data/session/ にPhase間の中間結果をテキストファイルとして保存
- 長期記憶: 既存のKnowledge DB (SQLite) を継承、get_stats()はv6.3.0実装を維持

### 2. BIBLE v7.0.0の生成
BIBLE/BIBLE_Helix AI Studio_7.0.0.md を新規作成してください。
v6.3.0のBIBLEの形式を踏襲しつつ、以下を反映:
- バージョン: 7.0.0 "Orchestrated Intelligence"
- 変更履歴: 旧5Phase→新3Phase、MCP活性化、UI刷新
- ディレクトリ構造: 新規ファイル・削除ファイルを反映
- 技術スタック: 変更点を反映
- 3Phase実行パイプラインの正確な記述
- 変更ファイル一覧: 全変更ファイルをリスト

### 3. PyInstallerビルド
HelixAIStudio.spec を更新:
- 新規ファイル（sequential_executor.py等）をhiddenimportsに追加
- 削除ファイル（旧parallel_pool.py等）をhiddenimportsから除去
- ビルド実行: pyinstaller HelixAIStudio.spec
- ビルド成功を確認（dist/HelixAIStudio.exe が生成されること）

### 4. 不要ファイルの最終クリーンアップ
以下を確認・削除:
- src/backends/ 内の旧5Phase関連で使われなくなったファイル
- __pycache__ の古いキャッシュ
- 旧BIBLEは削除しない（履歴として保持）

### 5. 統合テスト
アプリを起動し、以下のテストを実行してClaude Codeのチャットに結果を報告:

テスト1（Phase 2スキップ確認）:
入力: 「こんにちは」
期待: Phase 1のみで回答が返り、Phase 2-3がスキップされること

テスト2（3Phase動作確認）:
入力: 「Pythonでフィボナッチ数列を計算する関数を書いてください。性能も考慮してください。」
期待: Phase 1→Phase 2（coding担当LLM実行）→Phase 3の順で実行されること
確認: ツール実行ログに各Phaseの実行時間が表示されること

テスト3（ツール使用確認）:
入力: 「このプロジェクトのsrc/backends/ディレクトリの構造を教えてください」
期待: Claude CLIがReadまたはGlobツールを使用してディレクトリを確認すること
確認: Claude CLI JSON出力内にtool_use（Read, LS, Glob等）が含まれること

## 禁止事項
- BIBLEに「既に実装済みを確認」という記述を書かないこと。実際のコードの状態を正確に記述すること
- ビルドエラーを無視しないこと。エラーがあれば修正してからビルドすること
- テスト結果を偽らないこと。実際にアプリを起動して確認すること

## 検証方法
1. dist/HelixAIStudio.exe が存在し、サイズが50MB以上であること
2. BIBLE/BIBLE_Helix AI Studio_7.0.0.md が存在すること
3. テスト1-3の結果をチャットに報告すること
4. constants.py の APP_VERSION が "7.0.0" であること
```

### 第3回の動作確認チェックリスト

- [ ] `dist/HelixAIStudio.exe` が生成されている
- [ ] `BIBLE/BIBLE_Helix AI Studio_7.0.0.md` が新規作成されている
- [ ] テスト1: 「こんにちは」でPhase 2がスキップされる
- [ ] テスト2: 複雑な質問で3Phase全てが実行される
- [ ] テスト3: Claude CLIがツール（Read/Glob等）を実際に使用する
- [ ] ツール実行ログが各Phaseの実行時間を表示する
- [ ] アプリの exeファイル が正常に起動する

---

## 注意事項

### v6.3.0の失敗を繰り返さないために

1. **各回の作業後に必ず動作確認を行う**。動作確認せず次の回に進まない
2. **「既に実装済み」を信用しない**。Claude Codeがそう報告しても、grep等で実際にコードを確認する
3. **第1回が最重要**。バックエンドが正しく動作しないとUI実装もビルドも無意味
4. **第3回のテスト結果が全てを語る**。テスト1-3が全て通れば成功

### トラブル時の対処

- Claude Codeが途中で止まったら、作業途中のファイルをgit diffで確認し、続きから指示
- ビルドエラーが出たら、エラーメッセージをそのままClaude Codeに貼り付けて修正を依頼
- Phase 2でOllamaモデルが動かない場合、先に `ollama run devstral-2:123b` で手動テスト
