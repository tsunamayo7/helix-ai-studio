# Helix AI Studio - インストールガイド

## 必要環境

- Python 3.10 以上
- Windows 10/11
- (推奨) NVIDIA GPU + CUDA (ローカルLLM使用時)

## クイックインストール

```bash
# リポジトリをクローン
git clone https://github.com/your-repo/helix-ai-studio.git
cd helix-ai-studio

# install.bat を実行（対話的インストール）
install.bat
```

または手動で:

```bash
pip install -r requirements.txt
python HelixAIStudio.py
```

## 必須依存パッケージ

`requirements.txt` に記載されたパッケージが自動インストールされます。

## オプション設定

### Claude CLI（cloudAI / mixAI 機能に必要）

Claude Code CLI をインストール・認証してください:
https://docs.anthropic.com/en/docs/claude-code

### Ollama（localAI 機能に必要）

Ollama をインストールしてモデルをダウンロード:
https://ollama.ai

```bash
ollama pull qwen3:32b
```

### Browser Use（JS レンダリング対応 URL 取得）

localAI で JavaScript が必要な Web ページのコンテンツを取得できるようになります。
未インストール時は静的ページのみ取得可能（httpx ベース、追加インストール不要）。

**方法 1: アプリ内からインストール（推奨）**

アプリ起動後、「一般設定」→「オプションツール状態」→ `Browser Use` の `[pip install browser-use]` ボタンをクリック。
Chromium も自動でインストールされます。

**方法 2: 手動インストール**

```bash
pip install browser-use
python -m playwright install chromium
```

インストール後、アプリを再起動して localAI 設定の「JS対応URL取得を有効化」チェックを確認してください。
チェックボックスにカーソルを合わせると現在の動作モード（JS対応 or 静的ページのみ）が表示されます。

### sentence-transformers（ローカル Embedding）

RAG の Embedding を Ollama に依存せずローカルで生成できます。
未インストール時は Ollama の Embedding 機能で動作します。

```bash
pip install sentence-transformers
```

## 起動

```bash
python HelixAIStudio.py
```
