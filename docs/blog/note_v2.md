# 個人開発で「全部入りAIチャット」を作った話 ― Helix AI Studio v2.0

*公開日: 2026-03-27*

---

## ChatGPTだけじゃ足りなくなった

AIチャットツールは世の中にたくさんあります。ChatGPT、Claude、Gemini……どれも素晴らしいサービスです。

でも、使い込んでいくうちにこんな不満が出てきました。

- **プロバイダーを切り替えるたびにタブを行き来するのが面倒**
- **ローカルLLM（Ollama）も同じUIで使いたい**
- **RAGやエージェント機能を自分好みにカスタマイズしたい**
- **データを全部自分のサーバーに置きたい**

「ないなら作ろう」。そう思って開発を始めたのが **Helix AI Studio** です。

---

## Helix AI Studio って何？

ひとことで言うと、**7つのAIプロバイダーを1つの画面で切り替えて使えるセルフホスト型AIチャット**です。

![ストリーミング応答デモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_streaming_demo.gif)

対応プロバイダーはこちら:

- **Ollama**（ローカルLLM）
- **Claude** / **OpenAI** / **Gemini**（クラウドAPI）
- **vLLM**（自前GPUサーバー）
- **Claude Code CLI** / **Codex CLI** / **Gemini CLI**（ターミナル統合）

プロバイダーの切り替えはワンクリック。会話の途中でも別のモデルに切り替えられます。

![プロバイダー切替デモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_provider_switch.gif)

---

## v2.0 で何が変わったか

今回のv2.0は、「賢さ」を大きくアップグレードしました。

### 3ステップパイプライン

普通のAIチャットは「質問→回答」の1往復ですが、Helix AI Studioでは**計画→実行→最終回答**の3ステップで処理します。

![パイプラインデモ](https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_pipeline_demo.gif)

複雑な質問でも、まずAIが「どう答えるか」を計画し、必要な情報を集めてから最終回答を生成します。体感として、一発回答よりも的確な答えが返ってくるようになりました。

### マルチエージェント（CrewAI統合）

複数のAIエージェントがチームを組んで作業する機能も追加しました。たとえば「リサーチ担当」と「まとめ担当」が分業して、1つのAIだけでは難しいタスクをこなせます。

### CLI統合

Claude Code CLI、Codex CLI、Gemini CLIをWebブラウザから呼び出せるようにしました。ターミナルを開かなくても、ブラウザ上でCLIツールの力を借りられます。

### その他の改善

- **UI言語切り替え**: 英語/日本語をボタン一つで切替
- **パイプライン結果表示の改善**: 各ステップの思考過程が見やすく

---

## もともと持っていた機能たち

v1.0から搭載している機能も紹介しておきます。

- **RAGナレッジベース**: ドキュメントをアップロードすると、Qdrantベクトル検索で関連情報を自動で引っ張ってきます
- **Mem0共有記憶**: セッションをまたいで「覚えていてくれる」記憶機能
- **MCPツール連携**: 外部ツールとの接続（Model Context Protocol）
- **Web検索**: リアルタイムの情報を取得して回答に反映

---

## 100%セルフホスト、データは自分のもの

Helix AI Studioの大きな特徴は、**完全にセルフホストできる**ことです。

クラウドAPIを使わずにOllama + vLLMだけで運用すれば、データが外部に出ることは一切ありません。企業の内部利用や、プライバシーを重視する方にも安心して使っていただけます。

もちろん、ClaudeやOpenAIのAPIを組み合わせるハイブリッド構成も可能です。

---

## 試してみたい方へ

**ライブデモ**を公開しています。インストール不要で、すぐに触れます:

https://helix-ai-studio.onrender.com

自分のサーバーに立てたい方は、GitHubからどうぞ:

https://github.com/tsunamayo7/helix-ai-studio

`docker compose up` 一発で起動できます。スターをいただけると開発の励みになります。

---

## さいごに

個人開発で「自分が本当に欲しいもの」を作るのは、やっぱり楽しいです。

AIツールは日進月歩で進化していますが、「全部入りで」「セルフホストできて」「自分好みにカスタマイズできる」ものは、まだあまりないと思っています。

同じような不満を感じている方の参考になれば嬉しいです。質問やフィードバックがあれば、GitHubのIssueやコメントでお気軽にどうぞ。

---

*前回の記事: [Helix AI Studio を公開しました](https://note.com/ai_tsunamayo_7/n/n574a800d6caf)*
