---
title: "【Helix AI Studio】完全操作マニュアル — 全タブ・全機能の使い方"
emoji: "📖"
type: "tech"
topics: ["ai", "python", "pyqt6", "claude", "ollama"]
published: true
---

## はじめに

本記事は **Helix AI Studio** の全タブ・全機能を画面ごとに解説する操作マニュアルです。初めてアプリを起動した方でも、画面を見ながら一つずつ操作できるよう、各UI要素の場所と役割をていねいに説明します。

> Helix AI Studio は、Claude / ChatGPT / Gemini / ローカルLLM を1つのデスクトップアプリで統合し、複数AIの協調実行（3Phaseパイプライン）まで行えるオープンソースのAIオーケストレーションツールです。

https://github.com/tsunamayo7/helix-ai-studio

---

## 1. メインウィンドウの全体構成

アプリを起動すると、ダークテーマのメインウィンドウが表示されます。

![Helix AI Studio メインウィンドウ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/desktop_mixai.png)

### タブバー（画面上部）

ウィンドウ上部に **4つのメインタブ** が並んでいます。クリックして切り替えます。

| タブ名 | 役割 |
|--------|------|
| **mixAI** | 複数AIによる協調パイプライン実行 |
| **cloudAI** | Claude / GPT / Gemini とのクラウドAIチャット |
| **localAI** | Ollama（ローカルLLM）とのプライベートチャット |
| **Settings** | APIキー・言語・Web UI・Discord通知などの一般設定 |

タブバーの右端には **言語切替ボタン** があり、日本語と英語をワンクリックで切り替えられます。

---

## 2. mixAI タブ（マルチAI協調パイプライン）

mixAI は Helix AI Studio の中核機能です。1つのプロンプトを投げると、複数のAIが段階的に処理し、最終的に統合された高品質な回答を返します。

### 2-1. チャット サブタブ

mixAI タブを開くと、まず「チャット」サブタブが表示されます。

![mixAI パイプライン実行中](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/mixai_monitor.png)

#### プロンプト入力エリア

画面下部にテキスト入力欄があります。ここにAIへの指示（プロンプト）を入力します。複数行の入力にも対応しています。

#### 「実行」ボタン

入力欄の右側にある **「実行」ボタン** をクリックすると、3Phaseパイプラインが開始されます。実行中はボタンが無効化され、進捗が画面に表示されます。

#### フェーズ進捗表示

パイプラインは以下の3フェーズで順に実行されます。画面上部のプログレスバーとステータスラベルで現在のフェーズを確認できます。

1. **Phase 1（Claude 計画立案）**: タスクを分析し、受入基準・出力フォーマット・各モデルへの指示を自動生成します
2. **Phase 2（ローカルLLM 順次実行）**: コーディング・リサーチ・推論・翻訳・ビジョンの各カテゴリでローカルLLMが順に回答します
3. **Phase 3（Claude 比較統合）**: Phase 2の全回答を比較・評価し、1つの統合回答にまとめます。品質が基準を満たさない場合はリトライが行われます

#### 出力エリア

統合された最終回答が画面中央の出力エリアに表示されます。Markdown形式でレンダリングされるため、コードブロックやリストも見やすく表示されます。

#### PASS/FAIL 検証表示

Phase 3 の品質評価結果が **PASS**（合格）または **FAIL**（不合格）として表示されます。FAIL の場合は自動でリトライが実行されます。

![mixAI 実行完了](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/mixai_complete.png)

### 2-2. 設定 サブタブ

チャットサブタブの隣にある「設定」サブタブをクリックすると、パイプラインの構成をカスタマイズできます。

#### Phase 2 モデル選択

Phase 2 で使用するローカルLLMモデルを、以下の5カテゴリごとに選択できます。

| カテゴリ | 用途 | 推奨モデル例 |
|---------|------|-------------|
| **Coding** | コード生成・レビュー | qwen2.5-coder, codellama |
| **Research** | 調査・情報整理 | llama3, mistral |
| **Reasoning** | 論理的推論・分析 | deepseek-r1, phi4 |
| **Translation** | 翻訳タスク | aya, gemma2 |
| **Vision** | 画像理解（マルチモーダル） | llava, llama3.2-vision |

各カテゴリの横にある **チェックボックス** で有効/無効を切り替えます。使わないカテゴリのチェックを外すと、そのカテゴリはスキップされます。

モデルのドロップダウンリストには、Ollamaにインストール済みのモデルが自動で表示されます。「モデル管理」ボタンをクリックすると、表示するモデルの追加・非表示を管理できます。

#### クラウドモデル選択

Phase 1 / Phase 3 で使用するクラウドモデル（Claude等）を選択するドロップダウンがあります。`config/cloud_models.json` に登録したモデルが一覧表示されます。

![mixAI パイプライン動作](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/mixai_pipeline.gif)

---

## 3. cloudAI タブ（クラウドAIチャット）

cloudAI タブでは、Claude / ChatGPT / Gemini などのクラウドAIと直接チャットできます。

![cloudAI チャット画面](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/cloudai_chat.png)

### モデルセレクタ（画面上部）

タブ上部のドロップダウンリストから使用するモデルを選択します。`config/cloud_models.json` に登録したすべてのモデルが表示されます。プロバイダー（Anthropic / OpenAI / Google / Claude CLI）は自動的に判定されます。

例:
- `claude-sonnet-4-20250514` → Anthropic API で実行
- `gpt-4o` → OpenAI API で実行
- `gemini-2.0-flash` → Google Gemini API で実行

### 入力エリアと送信ボタン

画面下部にプロンプト入力欄と **送信ボタン** があります。テキストを入力し、送信ボタンをクリックするとAIに送信されます。

### ストリーミング応答表示

AIの回答はストリーミング形式で、生成されるたびにリアルタイムで画面に表示されます。Markdown記法でレンダリングされるため、コードや表も整形されて表示されます。

### 会話継続パネル

チャットエリアの上部に **会話継続パネル** が表示される場合があります。前回の会話を引き継ぐかどうかを選択できます。「継続する」をクリックすると、前回の文脈を保持したまま対話を続けられます。

### プロバイダーの切替

モデルを切り替えるだけで、使用するAPIプロバイダーが自動的に切り替わります。特別な操作は不要です。

- **Anthropic API**: Claude系モデル（claude-sonnet, claude-opus 等）
- **OpenAI API**: GPT系モデル（gpt-4o, o3 等）
- **Google API**: Gemini系モデル（gemini-2.0-flash 等）
- **Claude CLI**: Claude Code CLIを直接呼び出し（Max/Proプラン向け）

![Gemini チャット画面](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/gemini_chat.png)

---

## 4. localAI タブ（ローカルLLMチャット）

localAI タブでは、Ollama経由でローカルにインストールしたLLMとチャットします。データは一切外部に送信されないため、機密情報を扱う場面に最適です。

![localAI チャット画面](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/desktop_localai_chat.png)

### モデルセレクタ

タブ上部のドロップダウンリストに、Ollamaにインストール済みのモデルが自動的に一覧表示されます。使用したいモデルを選択してください。

### マルチモデル会話

localAI の大きな特徴として、**会話の途中でモデルを切り替えて対話を継続** できます。例えば、最初に `llama3` で質問し、次に `codellama` でコードレビューを依頼する、といった使い方が可能です。チャット画面には、どのモデルが回答したかが明示されます。

![マルチモデル会話](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/localai_multimodel.png)

### 入力エリアと送信ボタン

画面下部の入力欄にプロンプトを入力し、**送信ボタン** をクリックします。応答はリアルタイムで表示されます。

### ツール使用（ファイルシステムアクセス）

対応モデルでは、**ツール使用機能** が有効になります。AIがファイルの読み書きやディレクトリ一覧の取得を行い、実際のファイル操作を含む回答を生成します。ツールが実行されるとチャット画面に実行状況が表示されます。ツールループの上限は15回に設定されています。

### 設定サブタブ

localAI タブの「設定」サブタブでは、以下を構成できます。

- **Ollama接続先**: デフォルトは `http://localhost:11434`
- **カスタムサーバー設定**: Ollama以外のAPIサーバーを追加
- **常駐モデル設定**: 起動時に自動ロードするモデルの指定

![localAI チャット動作](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/localai_chat.gif)

---

## 5. Settings タブ（一般設定）

Settings タブでは、アプリ全体の設定を管理します。スクロールして各セクションにアクセスしてください。

![設定画面](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/desktop_settings.png)

### AI状態確認セクション

画面上部に、接続中のAIバックエンドの状態が表示されます。

- **Claude CLI**: インストール・認証状態
- **Ollama**: 起動状態・接続確認
- **オプションツール**: Codex CLI やその他のツールの状態

「状態を更新」ボタンをクリックすると、最新の接続状態を再取得します。

### APIキー管理セクション

各プロバイダーのAPIキーをここで設定します。

1. **Anthropic API Key**: Anthropicの公式サイトで取得したキーを入力します
2. **OpenAI API Key**: OpenAIのAPIキーを入力します
3. **Google API Key**: Google AI StudioのAPIキーを入力します

入力後、**「保存」ボタン** をクリックすると設定が保存されます。キーは `config/config.json` に暗号化されずに保存されるため、取り扱いにご注意ください。

### 言語切替

アプリのUI言語を **日本語** と **English** で切り替えることができます。タブバー右端の言語ボタンからも切り替え可能です。切替後、すべてのラベルとメッセージが即座に翻訳されます。

### Web UIサーバー設定

Web UI（モバイルアクセス用）のサーバーを管理します。

- **有効/無効トグル**: Web UIサーバーの起動・停止を切り替えます
- **ポート番号**: デフォルトは `8000` です。変更する場合は任意のポート番号を入力します
- **PINコード**: Web UIへのアクセス時に必要なPINコードを設定できます。セキュリティのために必ず設定してください

### Discord通知設定

AIの実行開始・完了・エラーをDiscordに通知する機能です。

![Discord設定](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/discord_settings.png)

- **Webhook URL**: Discord側で作成したWebhook URLを入力します
- 設定すると、mixAI / cloudAI / localAI の全タブで実行状況がDiscordに自動送信されます

---

## 6. Web UI（モバイルアクセス）

Helix AI Studio には FastAPI + React 製の **Web UI** が内蔵されています。同一ネットワーク内のスマートフォンやタブレットからブラウザでアクセスできます。

### アクセス方法

1. Settings タブで Web UI を **有効** にします
2. 表示されるURL（例: `http://192.168.x.x:8000`）をスマートフォンのブラウザで開きます
3. PINコードを入力してログインします

![Web UI メイン画面](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/webui_main.png)

### Web UI のタブ構成

Web UIには以下の4つのタブがあります。

| タブ | 機能 |
|------|------|
| **mixAI** | 3Phaseパイプラインの実行（デスクトップ版と同等） |
| **cloudAI** | クラウドAIチャット |
| **localAI** | ローカルLLMチャット |
| **Files** | プロジェクトファイルの閲覧・管理 |

![Web UI チャット](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/webui_chat.png)

### ファイルブラウザ

「Files」タブでは、プロジェクト内のファイルをブラウザ上で閲覧できます。ディレクトリのナビゲーション、ファイル内容のプレビューが可能です。

![Web UI ファイルブラウザ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/webui_files.png)

### 多言語対応

Web UI も日本語・英語の切替に対応しています。

![Web UI 英語表示](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/webui_english.png)

---

## 7. RAG機能（ナレッジベース構築）

RAG（Retrieval-Augmented Generation）機能により、手持ちのドキュメントをベクトル化してナレッジベースを構築し、AIの回答精度を向上させることができます。

### ドキュメントの追加

1. `data/information` フォルダにドキュメントファイルを配置します
2. 対応フォーマット: `.txt`, `.md`, `.pdf`, `.docx`, `.csv`, `.json`
3. 1ファイルの最大サイズは 50MB です

### ナレッジベースの構築

RAG設定画面で **「ビルド」ボタン** をクリックすると、配置したドキュメントのベクトル化が開始されます。

- **チャンクサイズ**: テキストを分割する単位（デフォルト: 512トークン）
- **オーバーラップ**: チャンク間の重複（デフォルト: 64トークン）
- **制限時間**: ビルドの最大実行時間（デフォルト: 90分、最大24時間）

ビルド中はプログレスバーが表示されます。完了すると、検証用のサンプリングテスト（10件）が自動で実行されます。

![RAGビルド](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/main/docs/demo/rag_build.png)

### 会話でのRAG利用

ナレッジベースが構築されると、cloudAI / localAI / mixAI の全タブで自動的にRAGが有効化されます。プロンプトの内容に関連するドキュメント断片が検索され、AIへの入力に自動注入されます。手動操作は不要です。

---

## 8. Tips & Tricks

### 用途別おすすめモデル組み合わせ

| 用途 | 推奨構成 |
|------|---------|
| コードレビュー | cloudAI で `claude-sonnet-4` を使用 |
| 長文の日本語文章作成 | cloudAI で `claude-sonnet-4` または mixAI パイプライン |
| 高速な質問応答 | localAI で `llama3` または `gemma2` |
| 機密データの分析 | localAI のみ使用（データ外部送信なし） |
| 複合タスク（調査+コード+文書化） | mixAI パイプライン（全カテゴリ有効） |
| 翻訳 | mixAI の Translation カテゴリ、または cloudAI |

### コスト最適化のコツ

- **ローカルLLMを積極活用**: Ollamaで動くモデルは完全無料です。簡単な質問はlocalAIで処理しましょう
- **mixAI の Phase 2 でローカルLLMを使う**: Phase 1/3 のみクラウドAPI呼び出しのため、APIコストを大幅に削減できます
- **不要なカテゴリはオフに**: mixAI設定で使わないカテゴリのチェックを外すと、処理時間とリソースを節約できます
- **軽量モデルから始める**: まず `gemini-2.0-flash` や小型のローカルモデルで試し、品質が不足する場合のみ大型モデルに切り替えましょう

### データの安全性

| 接続方式 | データ送信先 | 学習リスク |
|---------|------------|-----------|
| Anthropic API | Anthropicサーバー | 学習に使われない（規約明記） |
| OpenAI API | OpenAIサーバー | オプトアウト可能 |
| Google API | Googleサーバー | Google規約に準拠 |
| Ollama (ローカル) | どこにも送信しない | リスクゼロ |

---

## 9. トラブルシューティング

| 症状 | 対処法 |
|------|--------|
| cloudAI で応答がない | Settings タブでAPIキーが正しく設定されているか確認してください |
| localAI のモデル一覧が空 | Ollamaが起動しているか確認してください（`ollama serve`） |
| mixAI の Phase 2 がスキップされる | 設定サブタブでカテゴリが有効になっているか、モデルが選択されているか確認してください |
| Web UI にアクセスできない | Settings タブで Web UI が有効になっているか、ファイアウォール設定を確認してください |
| RAGビルドが進まない | ドキュメントが `data/information` に配置されているか、ファイル形式が対応しているか確認してください |

---

## GitHub リポジトリ

Helix AI Studio はオープンソースで公開されています。機能リクエストやバグ報告は Issue でお気軽にどうぞ。

https://github.com/tsunamayo7/helix-ai-studio

気に入っていただけたら、GitHubで Star をお願いします。開発の大きな励みになります。
