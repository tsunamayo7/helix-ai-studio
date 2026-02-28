---
title: "【Helix AI Studio】環境構築からアプリ起動まで完全ガイド（Windows）"
emoji: "🛠️"
type: "tech"
topics: ["python", "ai", "ollama", "windows", "環境構築"]
published: true
---

# 【Helix AI Studio】環境構築からアプリ起動まで完全ガイド（Windows）

この記事では、**Helix AI Studio** を Windows 上でゼロから環境構築し、起動するまでの全手順を解説します。Python や AI ツールに初めて触れる方でも迷わないよう、すべてのステップを画面操作レベルで説明していきます。

> Helix AI Studio は、Claude / ChatGPT / Gemini / ローカルLLM を 1 つのデスクトップアプリから統合操作できるオープンソースの AI オーケストレーターです。
> GitHub: https://github.com/tsunamayo7/helix-ai-studio

---

## 0. 始める前に確認すること

以下の条件を満たしているか確認してください。

| 項目 | 必須要件 | 推奨要件 |
|------|---------|---------|
| OS | Windows 10（64bit） | Windows 11 |
| メモリ (RAM) | 8GB 以上 | 16GB〜32GB |
| GPU | なしでも可 | NVIDIA GPU（ローカルLLM使用時） |
| ストレージ空き容量 | 5GB 以上 | 10GB 以上 |
| インターネット接続 | 必須 | -- |

### ローカルLLM を使う場合の推奨 GPU

Ollama でローカル AI モデルを動かす場合、以下の NVIDIA GPU を推奨します。

| GPU | VRAM | 対応モデル目安 |
|-----|------|--------------|
| GeForce RTX 3060 | 12GB | 4B〜8B パラメータモデル |
| GeForce RTX 3080 / 3090 | 10〜24GB | 8B〜14B パラメータモデル |
| GeForce RTX 4070 Ti | 12GB | 4B〜8B パラメータモデル |
| GeForce RTX 4080 / 4090 | 16〜24GB | 14B〜32B パラメータモデル |

> GPU がなくても cloudAI タブ（Claude / ChatGPT / Gemini の API 経由）は問題なく使えます。ローカルLLM だけ GPU が必要です。

---

## 1. Python のインストール

Helix AI Studio は Python 3.10 以上で動作します。**Python 3.11 または 3.12** を推奨します。

### 1-1. ダウンロード

1. ブラウザで https://www.python.org/downloads/ を開きます
2. 「**Download Python 3.12.x**」（黄色い大きなボタン）をクリックします
3. インストーラー（`python-3.12.x-amd64.exe`）がダウンロードされます

### 1-2. インストール

1. ダウンロードしたインストーラーをダブルクリックして実行します
2. **最初の画面で「Add python.exe to PATH」にチェックを入れてください（最重要）**
3. 「Install Now」をクリックします
4. インストールが完了したら「Close」をクリックします

> **PATH に追加し忘れた場合**: インストーラーを再実行 →「Modify」→「Next」→「Add Python to environment variables」にチェック →「Install」で修正できます。

### 1-3. 動作確認

コマンドプロンプトを開いて（`Win + R` → `cmd` → Enter）、以下を入力します。

```cmd
python --version
```

`Python 3.12.x` のようにバージョンが表示されれば成功です。

**エラーが出る場合**:
- 「`'python' は、内部コマンドまたは外部コマンド...として認識されていません`」→ PATH が通っていません。上記の手順で PATH を追加してください
- コマンドプロンプトを**一度閉じて再度開く**ことで解決する場合もあります

---

## 2. Git のインストール（任意）

Git はバージョン管理ツールです。GitHub からソースコードを取得するのに使います。

### 方法 A: Git をインストールする（推奨）

1. https://git-scm.com/download/win からインストーラーをダウンロードします
2. ダウンロードした `.exe` を実行し、すべてデフォルト設定のまま「Next」→「Install」で完了します

### 方法 B: Git を使わない場合

Git をインストールしなくても、GitHub から ZIP ファイルとしてダウンロードできます（手順は次のステップで説明します）。

---

## 3. Helix AI Studio の取得

### 方法 A: git clone（Git インストール済みの場合）

コマンドプロンプトを開き、任意の作業フォルダに移動してから以下を実行します。

```cmd
cd C:\Users\%USERNAME%\Desktop
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
```

### 方法 B: ZIP ダウンロード（Git なしの場合）

1. ブラウザで https://github.com/tsunamayo7/helix-ai-studio を開きます
2. 緑色の「**Code**」ボタンをクリックします
3. 「**Download ZIP**」をクリックします
4. ダウンロードした ZIP を展開します（右クリック →「すべて展開」）
5. 展開先のフォルダ名を `helix-ai-studio` に変更しておくと分かりやすいです

> **注意**: 展開先のパスに日本語（全角文字）が含まれるとエラーの原因になることがあります。`C:\helix-ai-studio` や `C:\Users\ユーザー名\Desktop\helix-ai-studio` など、できるだけシンプルなパスを使ってください。

---

## 4. 依存パッケージのインストール

### 4-1. ワンクリック インストール（推奨）

Helix AI Studio にはインストーラーが同梱されています。

1. エクスプローラーで `helix-ai-studio` フォルダを開きます
2. **`install.bat`** をダブルクリックします
3. 画面の指示に従い、オプション機能のインストール可否を選択します（Y/N）
4. すべて完了するまで待ちます

これだけで、Python パッケージのインストール、設定ファイルのテンプレート配置、データフォルダの作成が自動的に行われます。

### 4-2. 手動インストール

コマンドプロンプトで `helix-ai-studio` フォルダに移動し、以下を実行します。

```cmd
cd C:\Users\%USERNAME%\Desktop\helix-ai-studio

pip install -r requirements.txt
```

#### よくあるエラーと対処法

| エラーメッセージ | 原因と対処法 |
|---------------|------------|
| `'pip' は認識されていません` | Python の PATH が通っていません。ステップ 1 に戻って確認してください |
| `Permission denied` / アクセス拒否 | コマンドプロンプトを「管理者として実行」してください |
| `ERROR: Could not build wheels` | Visual C++ Build Tools が必要な場合があります。`pip install --upgrade pip setuptools wheel` を先に実行してください |

---

## 5. Ollama のインストール（ローカルLLM を使う場合）

Ollama は、ローカルでLLMを動かすためのツールです。localAI タブで利用します。クラウド AI（cloudAI タブ）のみ使う場合はスキップ可能です。

### 5-1. ダウンロードとインストール

1. https://ollama.com/download にアクセスします
2. 「**Download for Windows**」をクリックしてインストーラーをダウンロードします
3. ダウンロードした `.exe` を実行し、「Next」→「Install」→「Finish」で完了です

### 5-2. AI モデルのダウンロード

インストール後、コマンドプロンプトを開いて以下を実行します。

**まずは軽量モデル（4B パラメータ）を試す場合:**

```cmd
ollama pull gemma3:4b
```

**より高品質な応答が欲しい場合（16GB以上の VRAM が必要）:**

```cmd
ollama pull gemma3:27b
```

**コーディング特化モデル:**

```cmd
ollama pull devstral:24b
```

**汎用で高性能（推奨）:**

```cmd
ollama pull qwen3:32b
```

### 5-3. 動作確認

```cmd
ollama list
```

ダウンロードしたモデル名が表示されれば成功です。

> Ollama はバックグラウンドでサーバーとして動作します。タスクトレイに Ollama のアイコンが表示されていれば起動中です。表示されていない場合は、スタートメニューから「Ollama」を起動してください。

---

## 6. API キーの設定（クラウド AI を使う場合）

クラウド上の AI（Claude、Gemini、ChatGPT）を使うには API キーが必要です。ローカルLLM のみ使う場合はスキップできます。

### 6-1. 設定ファイルの準備

`install.bat` を使った場合は自動的に作成されていますが、手動の場合は以下を実行します。

```cmd
cd C:\Users\%USERNAME%\Desktop\helix-ai-studio
copy config\general_settings.example.json config\general_settings.json
copy config\cloud_models.example.json config\cloud_models.json
```

> 設定ファイルは**アプリの GUI からも編集できます**（起動後「一般設定」タブ → API Keys セクション）。

### 6-2. 各 API キーの取得先

| プロバイダ | 取得先 URL | 備考 |
|-----------|-----------|------|
| **Anthropic**（Claude） | https://console.anthropic.com/settings/keys | 有料。$5〜のクレジット購入が必要 |
| **Google**（Gemini） | https://aistudio.google.com/apikey | **無料枠あり！** まず試すならこちらがおすすめ |
| **OpenAI**（ChatGPT） | https://platform.openai.com/api-keys | 有料。$5〜のクレジット購入が必要 |

> **初めての方へ**: Google Gemini API は無料枠があるので、まず Gemini から試すのがおすすめです。API キーを取得したら、アプリ起動後に「一般設定」タブで入力できます。

---

## 7. アプリの起動

いよいよ起動です。

### 7-1. 起動コマンド

コマンドプロンプトで以下を実行します。

```cmd
cd C:\Users\%USERNAME%\Desktop\helix-ai-studio
python HelixAIStudio.py
```

### 7-2. 初回起動の流れ

1. スプラッシュスクリーンが表示されます
2. メインウィンドウが開きます
3. 以下の 3 つのタブが利用可能です:
   - **cloudAI**: Claude / ChatGPT / Gemini とのチャット（API キー設定済みの場合）
   - **localAI**: Ollama 経由のローカルLLM チャット（Ollama 起動中の場合）
   - **mixAI**: 複数 AI を 5Phase パイプラインで協調動作させるオーケストレーション機能
4. まずは「一般設定」タブを開いて、API キーの入力やモデル設定を確認してください

> 起動時に「Ollama に接続できません」と表示される場合は、Ollama がバックグラウンドで動作しているか確認してください（ステップ 5-3 参照）。

---

## 8. Web UI のセットアップ（任意）

Helix AI Studio には、スマートフォンやタブレットからアクセスできる Web UI が内蔵されています。

### 8-1. Node.js のインストール

1. https://nodejs.org/ にアクセスします
2. 「**LTS**」（推奨版）をダウンロードしてインストールします
3. コマンドプロンプトで確認します:

```cmd
node --version
npm --version
```

### 8-2. フロントエンドのビルド

```cmd
cd C:\Users\%USERNAME%\Desktop\helix-ai-studio\frontend
npm install
npm run build
```

`frontend\dist\index.html` が生成されれば成功です。

> `install.bat` を使った場合、Node.js が検出されればフロントエンドのビルドも自動で行われます。

### 8-3. Web UI の有効化

1. Helix AI Studio を起動します
2. 「**一般設定**」タブを開きます
3. 「**Web サーバー**」セクションで Web UI を有効化します
4. 同一ネットワーク内のデバイスから `http://<PCのIPアドレス>:8500` でアクセスできます

> PC の IP アドレスは、コマンドプロンプトで `ipconfig` を実行し、「IPv4 アドレス」の項目で確認できます（例: `192.168.1.10`）。

---

## 9. トラブルシューティング

### `ModuleNotFoundError: No module named 'xxx'`

依存パッケージが正しくインストールされていません。

```cmd
pip install -r requirements.txt
```

特定のモジュールのみ不足している場合:

```cmd
pip install <モジュール名>
```

### `CUDA is not available` / GPU が認識されない

NVIDIA GPU を使用しているのに認識されない場合:

1. 最新の NVIDIA ドライバーをインストールしてください: https://www.nvidia.com/Download/index.aspx
2. Ollama は自動的に GPU を検出しますが、ドライバーが古い場合は認識に失敗します

### Ollama に接続できない（`Connection refused`）

```cmd
ollama serve
```

上記を実行するか、スタートメニューから Ollama アプリを起動してください。Ollama はデフォルトで `http://localhost:11434` でリッスンします。

### ポート 8500 が使用中

Web UI のポートが他のアプリと競合している場合は、「一般設定」タブでポート番号を変更してください。

### アプリが起動しない / クラッシュする

```cmd
python -m py_compile HelixAIStudio.py
```

上記でエラーが出る場合は Python のバージョンが古い可能性があります。Python 3.11 以上に更新してください。

---

## 10. まとめ：起動までのチェックリスト

- [ ] Python 3.11+ をインストールし、PATH を通した
- [ ] `helix-ai-studio` フォルダを取得した（git clone または ZIP）
- [ ] `install.bat` を実行した（または `pip install -r requirements.txt`）
- [ ] （任意）Ollama をインストールし、モデルをダウンロードした
- [ ] （任意）API キーを設定した（Gemini 無料枠がおすすめ）
- [ ] `python HelixAIStudio.py` で起動を確認した

すべてにチェックが入れば、Helix AI Studio を使い始める準備は完了です。

---

## リンク集

- **GitHub リポジトリ**: https://github.com/tsunamayo7/helix-ai-studio
- **Ollama 公式**: https://ollama.com
- **Python 公式**: https://www.python.org
- **Node.js 公式**: https://nodejs.org
- **Anthropic Console**: https://console.anthropic.com
- **Google AI Studio**: https://aistudio.google.com
- **OpenAI Platform**: https://platform.openai.com

---

> この記事が役に立ったら、**GitHub で Star** をお願いします！
> https://github.com/tsunamayo7/helix-ai-studio
>
> 不明点やバグ報告は、GitHub の Issues からお気軽にどうぞ。
