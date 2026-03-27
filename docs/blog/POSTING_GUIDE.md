# 記事投稿ガイド

> Chromeのセキュリティ制限（Cookie暗号化のDPAPIバインド）により、プロファイルコピーでの自動投稿ができませんでした。
> 以下の手順で各プラットフォームに手動投稿してください。

---

## 投稿記事一覧

| ファイル | プラットフォーム | 言語 | 操作 |
|----------|-----------------|------|------|
| `devto_v2.md` | [Dev.to](https://dev.to/new) | EN | 新規記事 or 既存更新 |
| `note_v2.md` | [note.com](https://note.com/notes/new) | JA | 新規記事 |
| `zenn_v2.md` | [Zenn](https://zenn.dev/dashboard) | JA | 新規記事 |
| `qiita_v2.md` | [Qiita](https://qiita.com/drafts/new) | JA | 新規記事 |
| `social_posts.md` | 複数 | EN/JA | 各セクションをコピペ |

---

## 各プラットフォームの投稿手順

### 1. Dev.to（既存記事の更新）
1. https://dev.to/tsunamayo7/i-built-a-self-hosted-ai-chat-app-that-connects-7-providers-in-one-ui-12ok にアクセス
2. 「Edit」ボタンをクリック
3. `devto_v2.md` の内容で記事全体を差し替え
4. front matterの `published: false` を `published: true` に変更して保存

### 2. note.com
1. https://note.com/notes/new にアクセス
2. タイトル: `個人開発で「全部入りAIチャット」を作った話 ― Helix AI Studio v2.0`
3. `note_v2.md` の本文をエディタに貼り付け
4. GIF画像はURLをそのまま貼り付け（note.comはmarkdownの画像URL対応）
5. 公開

### 3. Zenn
1. https://zenn.dev/dashboard にアクセス
2. 「記事を作成」→「テキストエディタ」
3. `zenn_v2.md` の全内容をペースト（front matter含む）
4. `published: false` を `published: true` に変更
5. 公開

### 4. Qiita
1. https://qiita.com/drafts/new にアクセス
2. タイトル: `7つのAIプロバイダーを1画面で切り替え — Helix AI Studio v2.0を作った`
3. タグ: `Python`, `AI`, `FastAPI`, `Ollama`, `個人開発`
4. `qiita_v2.md` の本文をペースト
5. 公開

### 5. X (Twitter)
1. https://x.com/compose/tweet にアクセス
2. `social_posts.md` の「X (Twitter) — Japanese」セクションをコピペ
3. 英語版も投稿したい場合は「X (Twitter) — English」も

### 6. Hashnode
1. https://hashnode.com/draft にアクセス
2. `social_posts.md` の「Hashnode」セクションをコピペ

### 7. Hacker News
1. https://news.ycombinator.com/submit にアクセス
2. タイトル: `Show HN: Helix AI Studio – 7 AI providers in one self-hosted web UI`
3. URL: `https://github.com/tsunamayo7/helix-ai-studio`
4. コメントは `social_posts.md` の「Hacker News」セクションから

### 8. Reddit
1. r/selfhosted: https://www.reddit.com/r/selfhosted/submit
2. r/LocalLLaMA: https://www.reddit.com/r/LocalLLaMA/submit
3. `social_posts.md` の「Reddit」セクションから各subreddit向けをコピペ

### 9. Product Hunt
1. https://www.producthunt.com/posts/new にアクセス
2. `social_posts.md` の「Product Hunt」セクションからタグラインと説明をコピペ

---

## GIF画像URL

記事中で使用するGIF画像のURL:

| 画像 | EN | JA |
|------|----|----|
| Streaming | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_streaming_demo.gif` | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_streaming_demo.gif` |
| Pipeline | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_pipeline_demo.gif` | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_pipeline_demo.gif` |
| Provider Switch | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_provider_switch.gif` | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_provider_switch.gif` |
| Search | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_search_demo.gif` | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_search_demo.gif` |
| Navigation | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/en/gh_navigation_demo.gif` | `https://raw.githubusercontent.com/tsunamayo7/helix-ai-studio/master/docs/images/ja/gh_navigation_demo.gif` |
