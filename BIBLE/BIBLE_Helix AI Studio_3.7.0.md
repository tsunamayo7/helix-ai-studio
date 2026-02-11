# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.7.0
**アプリケーションバージョン**: 3.7.0 "Helix AI Studio - Enhanced Snippet Manager with Unipet Support"
**作成日**: 2026-01-20
**最終更新**: 2026-01-31
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.7.0 更新履歴 (2026-01-31)

### ユニペット機能強化 (Enhanced Snippet Manager)

**概要**:
v3.7.0 はスニペット機能を大幅に強化。App Manager Studioのユニペット機能を移植・改善。

**新機能**:

#### 1. スニペットプルダウンメニュー
- 「📋 スニペット ▼」ボタンクリックでプルダウンメニュー表示
- カテゴリ別にグループ化されたスニペット一覧
- ワンクリックでテキストを入力欄に挿入

#### 2. スニペット追加ボタン
- 「➕ 追加」ボタンで新規スニペット作成ダイアログ
- 名前・カテゴリ・内容を入力してカスタムスニペット登録
- data/snippets.json に保存

#### 3. 右クリックメニュー（編集・削除）
- スニペットボタン右クリックで編集・削除メニュー表示
- ユニペットファイルの編集サポート
- JSONスニペットの完全CRUD操作

#### 4. ユニペットフォルダ対応
- 「ユニペット」フォルダから.txtファイルを自動読み込み
- 「📂 ユニペットフォルダを開く」でエクスプローラー起動
- App Manager Studio互換のユニペット形式

**主要な変更**:

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/claude_tab.py` | スニペットUI強化、メニュー・ダイアログ追加 |
| `src/claude/snippet_manager.py` | 依存関係修正、自己完結型に変更 |
| `src/utils/constants.py` | バージョン 3.5.0 → 3.7.0 |

**UI変更**:
- 「📋 スニペット」→「📋 スニペット ▼」（プルダウン形式）
- 「➕ 追加」ボタン新設（履歴から引用ボタンの右隣）

---

## v3.6.0 更新履歴 (2026-01-31)

### App Manager タブ削除
- App Manager機能はApp Manager Studio（旧Claude Code GUI）へ移管
- 4タブ構成に変更: Claude Code, Gemini Designer, Cortex, Trinity AI

---

## v3.5.0 更新履歴 (2026-01-25)

### 権限確認自動スキップ機能

**概要**:
v3.5.0 は Claude CLI の権限確認ダイアログを自動的にスキップする機能を追加。
v3.4.0の「会話継続」機能では、Claude CLI が「Allow」「許可」ボタンを求めた際に GUI から応答できなかった問題を解決。

**問題の背景**:
v3.4.0で実装した会話継続機能（`--continue`フラグ）では、Claude CLIがファイル書き込み許可を求めた場合、
ユーザーは「はい」「続行」などのテキスト応答を送信しても、実際のCLI許可ダイアログには応答できなかった。

**解決策**:
`--dangerously-skip-permissions` フラグをデフォルトで有効化。

**主要な変更**:

#### 1. Claude CLI Backend 更新 (`src/backends/claude_cli_backend.py`)

**新機能**:
- `skip_permissions` プロパティ追加（デフォルト: `True`）
- `_build_command()` に `--dangerously-skip-permissions` フラグ対応追加
- コマンドライン構築時に権限スキップフラグを自動付与

**コード変更箇所**:
```python
# v3.5.0: __init__ にskip_permissions引数追加
def __init__(self, working_dir: str = None, thinking_level: str = "none", skip_permissions: bool = True):
    ...
    self._skip_permissions = skip_permissions

# v3.5.0: _build_command に権限スキップフラグ追加
def _build_command(self, prompt: str, use_continue: bool = False) -> List[str]:
    cmd = [self._claude_cmd, '-p', prompt]
    if self._skip_permissions:
        cmd.append('--dangerously-skip-permissions')
    ...
```

#### 2. Claude Code タブ UI更新 (`src/tabs/claude_tab.py`)

**新規UI要素**:
- 「🔓 許可」チェックボックスをツールバーに追加（デフォルト: ON）

**チェックボックスの動作**:
| 状態 | 動作 |
|------|------|
| ✅ ON（デフォルト） | ファイル書き込み・編集・削除を自動許可 |
| ⬜ OFF | 毎回Claude CLIが確認を求める（ターミナル操作必要） |

**追加コード箇所**:
- `_create_toolbar()` に `self._skip_permissions_checkbox` 追加
- `_send_message()` で Backend 初期化時に設定を渡す

#### 3. バージョン更新 (`src/utils/constants.py`)

```python
APP_VERSION = "3.5.0"
APP_DESCRIPTION = "Standalone Hybrid AI Development Platform - Claude Max/Pro Plan CLI Backend with Auto Permission Skip, Conversation Continue Support, Trinity AI, Ollama Integration, Chat History Citation & Enhanced App Manager"
```

**技術的変更（v3.4.0 → v3.5.0）**:

| 項目 | v3.4.0 | v3.5.0 |
|------|--------|--------|
| CLIコマンド | `claude -p "..."` | `claude -p "..." --dangerously-skip-permissions` |
| ファイル書き込み | 手動許可必要 | 自動許可 |
| UIコントロール | なし | 「🔓 許可」チェックボックス |

**ファイル変更一覧**:

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/claude_cli_backend.py` | `--dangerously-skip-permissions` フラグ対応、`skip_permissions` プロパティ追加 |
| `src/tabs/claude_tab.py` | 「🔓 許可」チェックボックス追加、CLI呼び出し時に設定を渡す |
| `src/utils/constants.py` | バージョン 3.4.0 → 3.5.0 |
| `PROJECT_BIBLE_HelixAIStudio.md` | v3.5.0 更新履歴追加 |
| `HelixAIStudio.exe` | 再ビルド完了（約84MB） |

**参照ドキュメント**:
- [Claude Code CLI Permissions](https://docs.anthropic.com/claude-code)

---

## v3.4.0 更新履歴 (2026-01-25)

### 会話継続サポート (Conversation Continue)

**概要**:
v3.4.0 は Claude CLI の会話継続機能（`--continue` フラグ）をサポート。
Claude が質問や確認を求めた場合に、同じ会話コンテキストで応答を送信できる。

**背景**:
Claude Code CLI を使用した場合、AIがファイル書き込み許可を求めたり、
追加情報を要求するケースがある。これまでは新規会話として送信されていたが、
`--continue` フラグを使用することで会話の文脈を維持したまま応答可能に。

**主要な変更**:

#### 1. Claude CLI Backend 更新 (`src/backends/claude_cli_backend.py`)

**新機能**:
- `_build_command(use_continue: bool)` に `--continue` フラグ対応追加
- `send_continue(message: str)` メソッド追加（会話継続専用）

**コード変更箇所**:
```python
def _build_command(self, prompt: str, use_continue: bool = False) -> List[str]:
    cmd = [self._claude_cmd, '-p', prompt]
    if use_continue:
        cmd.append('--continue')
    ...

def send_continue(self, message: str, ...) -> BackendResponse:
    """会話継続専用メソッド"""
    return self.send(request, use_continue=True)
```

#### 2. Claude Code タブ UI更新 (`src/tabs/claude_tab.py`)

**新しいUI構成**:
| 領域 | 幅 | 内容 |
|------|-----|------|
| 左側 | 2/3 | 通常の入力エリア（元のUI） |
| 右側 | 1/3 | 会話継続エリア（新規追加） |

**会話継続エリアの機能**:
- 「💬 会話継続」ヘッダー
- 継続入力フィールド（自由入力）
- クイックボタン:
  - **はい** (緑): "はい"を送信
  - **続行** (青): "続行してください"を送信
  - **実行** (紫): "実行してください"を送信
- **📤 送信**ボタン: 入力欄の内容を`--continue`フラグ付きで送信

**新規追加メソッド**:
- `_create_input_area()`: 横分割レイアウトに変更
- `_send_continue_message(text: str)`: 継続メッセージ送信
- `_send_continue_from_input()`: 入力欄からの送信
- `_on_continue_response(response)`: 継続応答の処理

**新規クラス**:
- `ContinueWorkerThread`: 継続専用ワーカースレッド

#### 3. バージョン更新 (`src/utils/constants.py`)

```python
APP_VERSION = "3.4.0"
APP_DESCRIPTION = "Standalone Hybrid AI Development Platform - Claude Max/Pro Plan Native Support with Conversation Continue, Trinity AI, Ollama Integration & Chat History Citation"
```

**使用方法**:

Claudeが確認質問をした場合（例: ファイル書き込み許可）:

1. **クイックボタン使用**:
   - 「はい」「続行」「実行」のいずれかをクリック

2. **カスタム応答**:
   - 継続入力欄にテキストを入力
   - 「📤 送信」をクリック

これにより、`--continue`フラグ付きでClaudeに送信され、会話の文脈が維持される。

**ファイル変更一覧**:

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/claude_cli_backend.py` | `--continue` フラグ対応、`send_continue()` メソッド追加 |
| `src/tabs/claude_tab.py` | 横分割レイアウト、会話継続エリア追加 |
| `src/utils/constants.py` | バージョン 3.3.0 → 3.4.0 |
| `PROJECT_BIBLE_HelixAIStudio.md` | v3.4.0 更新履歴追加 |
| `HelixAIStudio.exe` | 再ビルド完了（約80MB） |

---

## v3.3.0 更新履歴 (2026-01-25)

### App Manager機能強化 - アイコン変更・名前変更のEXE対応

**概要**:
v3.3.0は、App ManagerタブのUI操作で選択したアイコンがEXEファイルに反映されるよう改善し、
名前変更機能も他ファイルとの整合性を保ちながら一括変更できるよう強化したアップデート。

**機能強化内容**:

#### 1. アイコン変更機能 (`_on_change_icon`)
選択したアイコンがEXEのアイコン（およびタスクバー表示）に設定されるよう改善。

- **ico変換機能**: png/jpg/jpeg画像を自動的に.icoファイルに変換（Pillow使用）
- **specファイル更新**: `.spec`ファイルの`icon=`パラメータを自動更新
- **マルチサイズアイコン**: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 の6サイズを生成
- **再ビルド案内**: アイコンをEXEに反映するには再ビルドが必要な旨を表示

#### 2. 名前変更機能 (`_on_rename_app`)
アプリの名前を変更する際、関連ファイルの整合性を保ちながら一括変更。

**変更対象**:
- フォルダ名
- PROJECT_BIBLE.md（ファイル名と内容）
- EXEファイル名
- .specファイル（ファイル名とname=パラメータ）
- メインPythonファイル名（例: OldApp.py → NewApp.py）
- constants.py内のAPP_NAME
- build.bat内のファイル参照
- distフォルダ内のEXE

**新規追加メソッド**:
- `_create_ico_file()`: 画像からマルチサイズ.icoを生成
- `_update_spec_icon()`: specファイルのicon=を更新
- `_update_bible_content()`: PROJECT_BIBLE内のアプリ名を置換
- `_update_constants_app_name()`: constants.pyのAPP_NAMEを更新
- `_update_spec_name()`: specファイルのname=とAnalysis引数を更新
- `_update_build_bat()`: build.bat内のファイル参照を更新

#### 3. ウィンドウアイコン設定
- **_set_window_icon()** メソッドを`main_window.py`に追加
- アプリケーション起動時にicon.ico/icon.pngを検索してウィンドウアイコンに設定
- `QApplication.setWindowIcon()`でタスクバーアイコンも統一

#### 4. specファイル更新
- `HelixAIStudio.spec`に`icon='icon.ico'`パラメータを追加
- ビルド時にアイコンがEXEに埋め込まれるよう設定

**修正ファイル**:
- `src/tabs/app_manager_tab.py` - アイコン変更・名前変更機能強化
- `src/main_window.py` - ウィンドウアイコン設定メソッド追加
- `src/utils/constants.py` - バージョン 3.3.0
- `HelixAIStudio.spec` - icon=パラメータ追加
- `icon.ico` - icon.pngから生成（マルチサイズ）

**技術的変更点**:

| 項目 | v3.2.0 | v3.3.0 |
|------|--------|--------|
| アイコン変更 | ファイルコピーのみ | ico変換 + spec更新 + 再ビルド案内 |
| 名前変更 | フォルダ・EXE・BIBLE名のみ | spec・constants・build.bat含む一括変更 |
| ウィンドウアイコン | 未設定 | 起動時に自動設定 |
| タスクバーアイコン | 未設定 | QApplication経由で設定 |
| EXEアイコン | specに未設定 | icon='icon.ico'で埋め込み |

**依存関係**:
- Pillow (PIL): アイコン変換に使用（オプション - なくてもicoファイルを直接指定可能）

---

## v3.2.0 更新履歴 (2026-01-25)

### Claude Max/Proプラン CLI Backend 完全対応

**問題**:
認証モード「CLI (Max/Proプラン)」を選択し、インジケータが✅でも実際にはAPIキーエラーが発生する。
Backend表示が `local` になり、APIキーを要求される。

**根本原因**:
`claude_tab.py` の `_send_message()` が認証モードに関係なく `RoutingExecutor` を経由しており、
CLIバックエンドが直接使用されていなかった。

**修正内容**:

1. **CLIWorkerThread クラスを追加** (`claude_tab.py`):
   - CLI経由でAI応答を取得するワーカースレッド
   - ストリーミング対応（`chunkReceived`, `completed`, `errorOccurred` シグナル）
   - BackendRequest/BackendResponse形式で統一

2. **_send_message() のCLIモード分岐** (`claude_tab.py`):
   - 認証モードが CLI (index=0) かつ `_use_cli_mode=True` の場合
   - `RoutingExecutor` を経由せず、直接 `CLIWorkerThread` を使用
   - APIモード/Ollamaモードは従来通り `RoutingExecutor` を使用

3. **_send_via_cli() メソッドを追加** (`claude_tab.py`):
   - CLI経由での送信処理を専用メソッドに分離
   - 思考モード（none/light/deep）の設定対応
   - 作業ディレクトリの設定対応
   - 認証状態の表示

4. **_on_cli_response() ハンドラを追加** (`claude_tab.py`):
   - CLI応答の処理と表示
   - チャット履歴への保存（ai_source: "Claude-CLI"）
   - エラー時の詳細表示

5. **_init_backend() の修正**:
   - `_cli_backend` の明示的な初期化
   - CLI利用可能時は `_cli_backend` と `backend` 両方に設定

**修正ファイル**:
- `src/tabs/claude_tab.py` - CLIバックエンド切り替えロジック
- `src/utils/constants.py` - バージョン 3.2.0

**技術的変更点**:

| 項目 | v3.1.0 | v3.2.0 |
|------|--------|--------|
| CLIモード送信 | RoutingExecutor経由 | 直接CLIBackend使用 |
| CLI応答ハンドラ | なし | `_on_cli_response()` |
| CLI専用スレッド | なし | `CLIWorkerThread` |
| バックエンド参照 | `self.backend` のみ | `self._cli_backend` + `self.backend` |

**Claude CLI コマンドリファレンス**:
```bash
# 基本実行
claude -p "Your prompt here"

# 思考モード
claude -p "prompt" --think         # Standard (light)
claude -p "prompt" --think hard    # Deep (medium)
claude -p "prompt" --think ultrathink  # Maximum (deep/medium_opus)
```

**参考リンク**:
- Claude Code CLI: https://docs.anthropic.com/claude-code
- Extra Usage: https://support.claude.com/en/articles/12429409
- Max Plan: https://support.claude.com/ja/articles/11145838

---

## v3.1.0-bugfix 更新履歴 (2026-01-25)

### バグ修正 - Claudeチャット履歴保存機能の修正

**問題**:
「チャット履歴から引用」ダイアログでGeminiの履歴のみが表示され、Claudeの履歴が見えない。

**原因**:
ClaudeTabの`_on_executor_response`メソッドで履歴保存のログが不十分だったため、保存処理の追跡が困難だった。

**修正内容**:
1. **ai_sourceの動的決定** (`claude_tab.py`):
   - バックエンド名に基づいてai_sourceを自動判定（claude/gemini/ollama/trinity）
   - デフォルトは"Claude"を維持

2. **履歴保存ログの強化** (`claude_tab.py`):
   - 保存前に`pending_msg`の有無と`ai_source`をINFOレベルでログ出力
   - 保存成功時にentry_idとai_sourceをログ出力
   - 保存失敗時にexc_info=Trueでスタックトレースを記録
   - pending_messageが無い場合にWARNINGログを出力

3. **metadataの拡張**:
   - `source_tab: "ClaudeTab"`を追加（履歴の発生源を追跡可能に）

**修正ファイル**:
- `src/tabs/claude_tab.py` - 履歴保存ロジック強化

---

## v3.1.0 更新履歴 (2026-01-25)

### チャット履歴管理 & 引用機能追加

**概要**:
v3.1.0 は統合チャット履歴管理システムと履歴引用機能を追加。
ClaudeCodeアプリからの履歴インポート機能も実装し、過去の会話を
Helix AI Studioでも活用可能に。

**主要な変更**:

#### 1. チャット履歴管理システム新規作成 (`src/data/chat_history_manager.py`)

**新規追加クラス**:
| クラス | 説明 |
|--------|------|
| `ChatHistoryManager` | 統合履歴管理（セッション・エントリ両対応） |
| `ChatSession` | 完全なチャットセッション（複数メッセージ） |
| `ChatMessage` | 個別のチャットメッセージ |
| `ChatEntry` | 単一の入出力ペア（v5.8.0互換） |
| `SessionSummary` | セッション要約（インデックス用） |

**主要機能**:
- セッションベースの履歴管理
- エントリベースの履歴管理（ClaudeCode互換）
- AIソース別フィルタリング（Claude/Gemini/Trinity/Ollama）
- 期間フィルタリング（今日/週/月）
- キーワード検索
- 引用テキスト生成

**データ保存先**:
```
data/chat_history/
├── sessions/           # 個別セッションファイル
├── index.json          # セッションインデックス
└── entries.json        # エントリ形式履歴
```

#### 2. 履歴引用ウィジェット新規作成 (`src/ui/components/history_citation_widget.py`)

**新規追加クラス**:
| クラス | 説明 |
|--------|------|
| `HistoryCitationWidget` | 履歴検索・プレビュー・引用挿入ウィジェット |
| `HistoryCitationDialog` | モーダル引用ダイアログ |

**UI構成**:
- フィルターバー（AIソース、期間、キーワード検索）
- 検索結果リスト
- プレビューパネル
- 引用挿入ボタン

#### 3. Claude Code タブ更新 (`src/tabs/claude_tab.py`)

**新機能**:
- `📜 履歴から引用` ボタン追加
- 応答受信時にチャット履歴を自動保存
- 引用ダイアログから選択した履歴を入力欄に挿入

**追加コード箇所**:
- インポート: `from ..data.chat_history_manager import get_chat_history_manager`
- 初期化: `self.chat_history_manager = get_chat_history_manager()`
- 履歴保存: `_on_executor_response()` 内で `add_entry()` 呼び出し
- 引用機能: `_on_citation()` メソッド追加

#### 4. Gemini Designer タブ更新 (`src/tabs/gemini_designer_tab.py`)

**新機能**:
- 応答受信時にチャット履歴を自動保存

**追加コード箇所**:
- インポート: `from ..data.chat_history_manager import get_chat_history_manager`
- 初期化: `self.chat_history_manager = get_chat_history_manager()`
- 履歴保存: `_on_send_chat()` 内で `add_entry()` 呼び出し

#### 5. ClaudeCodeからの履歴インポート

**インポート機能**:
- `import_from_claudecode()` メソッドで一括インポート
- セッションファイル（`data/logs/sessions/*.json`）を変換
- エントリファイル（`data/history.json`）を変換

**インポート結果**:
- 105セッションをインポート
- 26エントリをインポート
- `imported_from: "ClaudeCode"` メタデータ付与

#### 6. バージョン更新 (`src/utils/constants.py`)

```python
APP_VERSION = "3.1.0"
APP_DESCRIPTION = "Standalone Hybrid AI Development Platform - Claude Max/Pro Plan Native Support with Trinity AI, Ollama Integration & Chat History Citation"
```

#### 7. データモジュール更新 (`src/data/__init__.py`)

**エクスポート追加**:
```python
from .chat_history_manager import (
    ChatHistoryManager,
    ChatSession,
    ChatMessage,
    ChatEntry,
    SessionSummary,
    get_chat_history_manager
)
```

**ファイル変更一覧**:

| ファイル | 変更内容 |
|----------|----------|
| `src/data/chat_history_manager.py` | 新規作成 - 統合チャット履歴管理 |
| `src/data/__init__.py` | チャット履歴エクスポート追加 |
| `src/ui/components/history_citation_widget.py` | 新規作成 - 履歴引用ウィジェット |
| `src/tabs/claude_tab.py` | 履歴保存・引用ボタン追加 |
| `src/tabs/gemini_designer_tab.py` | 履歴保存機能追加 |
| `src/utils/constants.py` | バージョン3.1.0に更新 |

---

## v3.0.0 更新履歴 (2026-01-25)

### Trinity AI タブ追加 & Ollama連携強化

**概要**:
v3.0.0 は TrinityExoskeleton の3段階リレー処理（Drafter → Critic → Refiner）を
GUI上で直接操作できる「Trinity AI」タブを追加。また、各タブの機能拡充を実施。

**主要な変更**:

#### 1. Trinity AI タブ新規作成 (`src/tabs/trinity_ai_tab.py`)

**新規追加**:
- `TrinityAITab` クラス: TrinityExoskeleton連携タブ
- `TrinityRelayThread` クラス: リレー処理をバックグラウンドで実行

**3段階リレー処理**:
| ステップ | 役割 | 説明 |
|----------|------|------|
| Drafter | 起案者 | 初期実装案を生成 |
| Critic | 批評者 | 批評・検証を実行 |
| Refiner | 洗練者 | 最終成果物を生成 |

**UI構成**:
- 左パネル: 入力エリア、最終出力表示
- 右パネル: 3段階（Drafter/Critic/Refiner）の各出力表示
- ツールバー: モデル選択、Ollamaエンドポイント設定、履歴保存オプション

**履歴保存機能**:
- LightRAGベースでJSONL形式で保存
- `data/trinity_history/trinity_history.jsonl`

#### 2. Claude Code タブ更新 (`src/tabs/claude_tab.py`)

**新機能**:
- Ollama連携モード追加（環境変数ベース設定）
- CLI認証とAPI認証の切り替え機能強化

#### 3. Gemini Designer タブ更新 (`src/tabs/gemini_designer_tab.py`)

**新機能**:
- API接続テスト用チャット送信機能追加
- UIデザイン提案機能の強化

#### 4. App Manager タブ更新 (`src/tabs/app_manager_tab.py`)

**新機能**:
- アイコン変更ボタン追加
- 名前変更ボタン追加
- 複製ボタン追加

#### 5. Cortex タブ更新 (`src/tabs/settings_cortex_tab.py`)

**新機能**:
- SpinBox幅拡大（操作性向上）
- APIキー設定UI改善
- MCP設定保存機能強化
- GitHub/Slack認証連携オプション

#### 6. メインウィンドウ更新 (`src/main_window.py`)

**変更内容**:
- Trinity AIタブを5番目のタブとして追加
- タブツールチップの詳細化
- 5タブ構成に更新（Claude Code, Gemini Designer, App Manager, Cortex, Trinity AI）

#### 7. バージョン更新 (`src/utils/constants.py`)

```python
APP_VERSION = "3.0.0"
APP_DESCRIPTION = "Standalone Hybrid AI Development Platform - Claude Max/Pro Plan Native Support with Trinity AI & Ollama Integration"
```

#### 8. ビルド設定更新 (`HelixAIStudio.spec`)

**hiddenimports追加**:
- `src.tabs.trinity_ai_tab`

**ファイル変更一覧**:

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/trinity_ai_tab.py` | 新規作成 - Trinity AI タブ |
| `src/tabs/claude_tab.py` | Ollama連携モード追加 |
| `src/tabs/gemini_designer_tab.py` | API接続テスト機能追加 |
| `src/tabs/app_manager_tab.py` | アイコン/名前変更/複製ボタン追加 |
| `src/tabs/settings_cortex_tab.py` | UI改善、認証連携オプション |
| `src/main_window.py` | Trinity AIタブ統合 |
| `src/utils/constants.py` | バージョン3.0.0に更新 |
| `HelixAIStudio.spec` | hiddenimports追加 |

**ビルド成果物**:
- `dist/HelixAIStudio.exe` - ビルド出力（約80MB）
- `HelixAIStudio.exe` - プロジェクトルートにコピー済み

---

## v2.5.0 更新履歴 (2026-01-24)

### Claude Max/Pro プラン ネイティブサポート & UI簡素化

**概要**:
v2.5.0 は Claude Max/Pro プランの認証をネイティブサポートし、
ClaudeCodeアプリと同様のCLI経由認証を実現。また、UIを大幅に簡素化し、
ユーザー体験を向上。

**主要な変更**:

#### 1. Claude CLI Backend 実装 (`src/backends/claude_cli_backend.py`)

**新規追加**:
- `ClaudeCLIBackend` クラス: Claude CLI (`claude -p`) 経由でMax/Proプラン認証を使用
- `find_claude_command()`: Claude CLIのパスを自動検出
- `check_claude_cli_available()`: CLI利用可能性チェック
- `get_claude_cli_backend()`: シングルトンインスタンス取得

**特徴**:
- Claude Max/Proプランのサブスクリプションを直接使用
- Extra Usage（追加使用量）機能に対応
- 使用制限に達しても従量課金で継続可能
- 参考: https://support.claude.com/en/articles/12429409

**認証フロー**:
1. ターミナルで `claude login` を実行
2. ブラウザでClaude.comにログイン
3. Helix AI StudioでCLI認証モードを選択

#### 2. Claude タブ UI 更新 (`src/tabs/claude_tab.py`)

**新規UI要素**:
- **認証モード選択**: CLI (Max/Proプラン) / API (従量課金) の切り替え
- **認証状態インジケータ**: 認証状態をリアルタイム表示 (✅/⚠️/❌)

**認証モード**:
| モード | 説明 | 認証方法 |
|--------|------|----------|
| CLI (Max/Proプラン) | Claude CLIを使用 | `claude login` でログイン |
| API (従量課金) | Anthropic API直接使用 | ANTHROPIC_API_KEY環境変数 |

#### 3. Ollama + Trinity 連携強化 (`src/backends/local_connector.py`)

**新規追加**:
- `ENDPOINT_PRESETS` 定数: 主要なローカルAIサービスのプリセット設定

**プリセット**:
| プリセット | エンドポイント | 説明 |
|------------|----------------|------|
| Ollama | http://localhost:11434 | 標準Ollamaエンドポイント |
| LM Studio | http://localhost:1234 | LM Studio (OpenAI互換) |
| Trinity Exoskeleton | http://localhost:8000 | Trinity API (OpenAI互換) |
| Ollama Cloud | https://api.ollama.com | クラウドOllama |

**Cortex タブ UI更新**:
- クイック接続ボタン追加: ワンクリックでプリセット適用
- Trinity Exoskeletonとの連携が容易に

#### 4. Cortex タブ 簡素化 (`src/tabs/settings_cortex_tab.py`)

**変更**: 13サブタブ → 8サブタブに削減

**残存タブ (8)**:
1. ⚙️ 一般設定
2. 🤖 AIモデル設定
3. 🛠️ MCPサーバー管理
4. 🧠 ローカル記憶 (Cortex)
5. 💰 予算管理
6. 🖥️ Local接続
7. 📚 Knowledge
8. 📖 Encyclopedia

**削除/コメントアウト (5)**:
- 🔒 MCPポリシー (MCPサーバー管理に統合検討)
- 🔀 ルーティングログ (開発者向け)
- 📋 監査ビュー (開発者向け)
- 🌡️ Thermal管理 (上級者向け)
- 🔺 Trinity Dashboard (Local接続で代替)

#### 5. UI/UX 改善

**ツールチップ強化**:
- メインタブのツールチップを詳細化
- 認証方法、キーボードショートカット、機能概要を追加

**操作性向上**:
- 認証状態の視覚的フィードバック
- プリセットボタンによるワンクリック設定

#### 6. バージョン更新 (`src/utils/constants.py`)

```python
APP_VERSION = "2.5.0"
APP_DESCRIPTION = "Standalone Hybrid AI Development Platform - Claude Max/Pro Plan Native Support"
```

**ファイル変更一覧**:

| ファイル | 変更内容 |
|----------|----------|
| `src/backends/claude_cli_backend.py` | 新規作成 - CLI Backend |
| `src/backends/__init__.py` | エクスポート追加 |
| `src/backends/local_connector.py` | ENDPOINT_PRESETS追加 |
| `src/tabs/claude_tab.py` | 認証モード選択UI追加 |
| `src/tabs/settings_cortex_tab.py` | タブ簡素化、プリセットボタン追加 |
| `src/main_window.py` | ツールチップ詳細化 |
| `src/utils/constants.py` | バージョン更新 |

**参照ドキュメント**:
- [Claude Code CLI](https://docs.anthropic.com/claude-code)
- [Extra Usage for Paid Plans](https://support.claude.com/en/articles/12429409)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Claude Code + Ollama Integration](https://docs.ollama.com/integrations/claude-code)

---

## v2.4.1 更新履歴 (2026-01-24)

### Mock機能撤廃と本実装 - Production Ready化

**概要**:
v2.4.1 はMock調査報告書に基づき、すべてのダミー/モック実装を本実装に置き換えた
「本番運用対応」アップデート。セキュリティ脆弱性の修正も含む。

**背景**:
- Mock調査報告書で多数のダミー実装・セキュリティ問題が指摘された
- google-generativeai ライブラリが2025年11月30日でEOLとなり移行が必要
- パストラバーサル脆弱性、スレッドセーフでないシングルトン等の問題

**主要な変更**:

#### 1. Gemini Backend 本実装 (`src/backends/gemini_backend.py`)

**修正内容**:
- `google-generativeai` (EOL) から `google-genai` ライブラリに移行
- `_generate_dummy_response()` を廃止
- 実際のGemini API呼び出しを実装
- ストリーミング応答対応 (`generate_content_stream`)
- モデル名マッピング追加 (gemini-3-pro → gemini-2.5-pro)

**新規メソッド**:
- `set_streaming_callback()`: ストリーミングコールバック設定
- `generate_stream()`: ストリーミング生成（ジェネレータ版）
- `is_available()`: API利用可能チェック
- `get_model_info()`: モデル情報取得

**環境変数**:
- `GEMINI_API_KEY` または `GOOGLE_API_KEY` を設定

**参照**:
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/libraries

#### 2. MCPクライアント 本実装 (`src/mcp_client/helix_mcp_client.py`)

**セキュリティ修正（緊急）**:
- **パストラバーサル脆弱性の修正**
  - `_validate_path()` 関数追加
  - プロジェクトルート外へのアクセスを禁止
  - すべてのファイル操作で検証を実施
- 非同期subprocess対応 (`asyncio.create_subprocess_exec`)
- タイムスタンプを `datetime.now().isoformat()` に修正

**新規関数**:
- `_validate_path(path, allowed_roots)`: パス検証（セキュリティ）
- `set_allowed_paths(paths)`: 許可パスリスト設定

**新規メソッド**:
- `get_tool_descriptions()`: ツール説明取得
- `clear_audit_log()`: 監査ログクリア

#### 3. Server Manager セキュリティ強化 (`src/mcp_client/server_manager.py`)

**修正内容**:
- `install_cmd.split()` を `shlex.split(install_cmd)` に変更
- コマンドインジェクション対策
- `shell=False` を明示

#### 4. LightRAG 本実装 (`src/helix_core/light_rag.py`)

**修正内容**:
- `MockLightRAG` 相当のダミー実装を廃止
- SQLite永続化実装
- TF-IDFベースのキーワード検索
- FTS5全文検索対応
- ハイブリッド検索（TF-IDF + FTS）

**新規メソッド**:
- `remove_document()`: ドキュメント削除
- `get_stats()`: 統計情報取得
- `_search_keyword()`: TF-IDF検索
- `_search_fts()`: FTS5検索
- `_search_hybrid()`: ハイブリッド検索

**データベーススキーマ**:
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    metadata TEXT,
    tokens TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE VIRTUAL TABLE documents_fts USING fts5(id, content, source);
```

#### 5. GraphRAG 本実装 (`src/helix_core/graph_rag.py`)

**修正内容**:
- ダミー実装を廃止
- SQLite永続化実装
- キーワード検索（Jaccard係数）
- FTS5全文検索対応
- pyvis可視化対応

**新規メソッド**:
- `remove_node()`: ノード削除（関連エッジも削除）
- `query_fts()`: FTS5検索
- `get_connected_nodes()`: 接続ノード取得
- `get_edges_for_node()`: ノード関連エッジ取得
- `get_stats()`: 統計情報取得
- `export_to_json()`: JSONエクスポート
- `clear_graph()`: グラフクリア

**データベーススキーマ**:
```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    episode_id TEXT,
    metadata TEXT
);
CREATE TABLE edges (
    source_id TEXT,
    target_id TEXT,
    relation TEXT,
    weight REAL,
    timestamp TEXT
);
CREATE VIRTUAL TABLE nodes_fts USING fts5(id, label, content);
```

#### 6. Gemini Designer Tab 本実装 (`src/tabs/gemini_designer_tab.py`)

**修正内容**:
- `DummyAnalysisThread` を `GeminiAnalysisThread` に置換
- `DummyProposalThread` を `GeminiProposalThread` に置換
- 実際のGemini API呼び出しによるUI分析
- API未設定時のフォールバック対応

**新規クラス**:
- `GeminiAnalysisThread`: Gemini APIを使用したUI分析
- `GeminiProposalThread`: Gemini APIを使用した改善案生成

#### 7. スレッドセーフなシングルトン

**修正ファイル**:
- `src/backends/local_llm_manager.py`
- `src/backends/local_connector.py`

**修正内容**:
```python
# ダブルチェックロッキングパターン
_instance = None
_lock = threading.Lock()

def get_instance():
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = Instance()
    return _instance
```

**セキュリティ修正サマリー**:

| 問題 | 重大度 | 修正内容 |
|------|--------|----------|
| パストラバーサル脆弱性 | 緊急 | `_validate_path()` による検証 |
| コマンドインジェクション | 高 | `shlex.split()` 使用 |
| スレッド非安全シングルトン | 中 | ダブルチェックロッキング |
| ダミー応答 | 中 | 実API呼び出し |

**ビルド情報**:
- EXEサイズ: 約77MB
- ビルドツール: PyInstaller 6.17.0
- Python: 3.12.7
- ビルド日時: 2026-01-24

**参照ドキュメント**:
- [google-genai PyPI](https://pypi.org/project/google-genai/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)

---

## v2.4.0 更新履歴 (2026-01-24)

### Ollama統合強化 - ローカルAI接続の大幅改善

**概要**:
v2.4.0 はOllama/LM Studio等のローカルLLM接続機能を大幅に拡張したアップデート。
最新のOllama API機能に対応し、モデル管理・詳細設定・推奨モデルプリセット機能を追加。

**背景**:
- Ollama 2025-2026で多くの新機能が追加された（構造化出力、ツール呼び出し、ストリーミング改善等）
- ローカルAIの利用が増加、設定UIの充実が必要
- DeepSeek、Qwen、Llamaなど高性能オープンソースモデルの台頭

**主要な変更**:

#### 1. LocalConnector 機能拡張 (`src/backends/local_connector.py`)

**新規追加機能**:
- `list_models()`: Ollamaにインストール済みのモデル一覧を取得
- `generate_stream()`: ストリーミングテキスト生成（トークン逐次表示）
- `generate_structured()`: JSON Schema制約付き構造化出力
- `pull_model()`: モデルダウンロード（ollama pull相当）
- `delete_model()`: モデル削除
- `get_recommended_models()`: カテゴリ別推奨モデル取得

**新規データクラス**:
- `OllamaModel`: モデル情報（名前、サイズ、詳細）

**設定拡張** (`LocalConnectorConfig`):
- `temperature`: 0.0-2.0（デフォルト: 0.7）
- `top_p`: 0.0-1.0（デフォルト: 0.9）
- `context_length`: コンテキスト長（デフォルト: 4096）
- `streaming_enabled`: ストリーミングON/OFF

**推奨モデルプリセット** (`RECOMMENDED_MODELS`):
```python
RECOMMENDED_MODELS = {
    "general": [
        {"name": "llama3.2:8b", "description": "Meta Llama 3.2 8B", "vram": "8GB"},
        {"name": "qwen2.5:14b", "description": "Qwen 2.5 14B", "vram": "12GB"},
        {"name": "deepseek-r1:14b", "description": "DeepSeek R1 14B", "vram": "12GB"},
    ],
    "coding": [
        {"name": "deepseek-coder:6.7b", "description": "DeepSeek Coder", "vram": "6GB"},
        {"name": "qwen2.5-coder:7b", "description": "Qwen 2.5 Coder", "vram": "6GB"},
    ],
    "fast": [
        {"name": "llama3.2:1b", "description": "Llama 3.2 1B", "vram": "2GB"},
        {"name": "phi3:mini", "description": "Phi-3 Mini", "vram": "3GB"},
    ],
    "japanese": [
        {"name": "elyza:jp-7b", "description": "ELYZA Japanese 7B", "vram": "6GB"},
    ],
}
```

#### 2. Local接続タブUI大幅改善 (`src/tabs/settings_cortex_tab.py`)

**新規UI要素**:
- **モデル選択コンボボックス**: インストール済みモデルをドロップダウンで選択
- **モデル一覧取得ボタン**: 接続後にワンクリックで取得
- **推奨モデルパネル**: カテゴリ別（general/coding/fast/japanese）で推奨モデル表示
- **詳細設定パネル**:
  - Temperature スピンボックス (0.0-2.0)
  - Top-P スピンボックス (0.0-1.0)
  - Max Tokens スピンボックス (256-32768)
  - Context Length スピンボックス (512-131072)
  - ストリーミング有効/無効チェックボックス
- **テスト生成ボタン**: 簡単なテストメッセージで動作確認

**改善点**:
- UIレイアウトの最適化
- ツールチップの充実
- エラーメッセージの詳細化

#### 3. backends/__init__.py 更新

- `OllamaModel`、`RECOMMENDED_MODELS` をエクスポート追加

#### 4. APP_VERSION 更新

- `src/utils/constants.py`: "2.4.0" に更新

**技術参照**:
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Best Ollama Models 2025](https://collabnix.com/best-ollama-models-in-2025-complete-performance-comparison/)

**ビルド情報**:
- EXEサイズ: 約77MB
- ビルドツール: PyInstaller 6.17.0
- Python: 3.12.7

---

## v2.3.0 更新履歴 (2026-01-24)

### Inspector依存の完全削除 - スタンドアロン化

（※v2.3.0の内容は前回のユーザー指示で提供されたPROJECT_BIBLEに含まれています）

---

## v2.2.5 更新履歴 (2026-01-23)

### Trinity UI Inspector: Semantic Event Log 検証装置への移行

**概要**:
v2.2.5 は Trinity UI Inspector の設計思想を根本から刷新したアップデート。
UI操作を制限・誘導するアプローチを廃止し、**Semantic Event Log のみを検証根拠とする「意味的検証装置」**として完成させた。

**設計変更の背景**:
- 従来の「マウス・キーボード操作禁止」アプローチは UX を著しく損なう
- 視覚的なスクリーンショット検証は不安定で環境依存性が高い
- Inspector の責務を「意味的なイベント検証」に限定することで、シンプルで堅牢な設計を実現

**新しい設計思想**:
1. **ユーザー操作は常に許可** - Inspector は操作を止めない
2. **Semantic Event Log が唯一の検証根拠** - UI操作ではなくイベントを検証
3. **操作結果がイベントとして来なければ NG** - 暗黙の成功判定を排除
4. **PROJECT_BIBLE への反映確認** - 検証結果を記録

**変更内容**:
- `src/tabs/trinity_inspector_tab.py`: **完全リファクタリング**
  - **削除した要素**:
    - カウントダウン表示/操作禁止UI（元々存在しなかった）
    - AI評価の視覚検証前提プロンプト
    - 修正フェーズの複雑なFSM
    - `FixProposalDialog` クラス
    - `EvaluationResult` Enum
    - デモモードの評価結果生成
  - **新規追加**:
    - `VerificationResult` Enum: OK / NG / NEXT / PENDING
    - `ExpectedEvent` / `ReceivedEvent` dataclass: イベントの期待値と受信値
    - `_poll_state_file()`: Inspector Hook 状態ファイルのポーリング
    - `_start_monitoring()` / `_stop_monitoring()`: イベント監視制御
    - `_update_events_table()`: 受信イベントの時系列表示
    - `_run_manual_verification()`: イベントベースの手動検証
  - **UI変更**:
    - 「監視状態」パネル: 現在待機中のイベント名を表示
    - 「受信済みイベント一覧」テーブル: 時刻/イベント/データ/検証状態
    - 「最終検証結果」パネル: OK/NG/NEXT + 検証理由
    - 「PROJECT_BIBLE 反映確認」パネル: プレビュー + 適用
    - ステータスバー: 「ユーザー操作は常に許可されています」

- `src/utils/constants.py`: APP_VERSION を 2.2.5 に更新

**Inspector の責務（v2.2.5以降）**:
1. 対象アプリの起動確認（プロセス存在）
2. Semantic Event Log の受信待機
3. Event の順序・内容・整合性の検証
4. 検証結果（OK / NG / NEXT）の生成
5. PROJECT_BIBLE への反映確認

**FSM 状態（簡素化）**:
| 状態 | 説明 |
|------|------|
| `IDLE` | 初期状態 |
| `APP_SELECTED` | アプリ選択済み |
| `MONITORING` | イベント監視中 |
| `VERIFYING` | 検証中 |
| `RESULT_OK` | 検証完了: OK |
| `RESULT_NG` | 検証完了: NG |
| `RESULT_NEXT` | 検証完了: NEXT（次のステップへ） |

**イベント監視の仕組み**:
```python
# Inspector Hook 状態ファイルをポーリング（500ms間隔）
_state_file_path = Path(tempfile.gettempdir()) / "trinity_hook_state" / "HelixAIStudio_state.json"

def _poll_state_file(self):
    """状態ファイルをポーリング"""
    if not self._state_file_path.exists():
        return
    with open(self._state_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    event_history = data.get("event_history", [])
    # 新しいイベントを受信イベントリストに追加
```

**検証ロジック**:
```python
def _run_manual_verification(self):
    """手動検証を実行"""
    if len(self._received_events) > 0:
        app_ready_found = any(e.event_type == "app_ready" for e in self._received_events)
        if app_ready_found:
            self._set_verification_result(VerificationResult.OK, "...")
        else:
            self._set_verification_result(VerificationResult.NEXT, "...")
    else:
        self._set_verification_result(VerificationResult.NG, "...")
```

**補足**:
この修正は安全性を下げるものではなく、Inspector を「意味的検証装置」として完成させるためのもの。
ユーザーは自由に操作でき、その結果は Semantic Event Log として記録・検証される。

---

## v2.2.4 更新履歴 (2026-01-23)

### PyInstaller EXEスタックオーバーフロー修正

**概要**:
v2.2.4 はPyInstallerでビルドしたEXEが起動時にスタックオーバーフロー（exit code: -1073741571 / 0xC00000FD）で
クラッシュする問題を修正したアップデート。

**問題の原因**:
1. `InspectorHook`クラスが`QObject`を継承していた
2. `QObject`のインスタンス化には`QApplication`が必要
3. モジュールインポート時（`QApplication`初期化前）にシングルトンが作成されていた
4. PyInstaller EXE環境で特にこの問題が顕在化（Python実行時は偶然動作していた）

**変更内容**:
- `src/utils/inspector_hook.py`:
  - **`InspectorHook`クラスの`QObject`継承を廃止**
  - 純粋なPythonクラス（`object`継承）に変更
  - `pyqtSignal`を廃止し、コールバックベースの通知システムに変更
    - `connect_state_changed(callback)`: 状態変更コールバック登録
    - `connect_event_occurred(callback)`: イベント発生コールバック登録
  - `QTimer`の遅延初期化を実装（`on_app_ready()`で初期化）
  - PyQt6のインポートを関数内に移動（遅延インポート）
- `HelixAIStudio.spec`:
  - `PyQt6.sip`を`hiddenimports`に追加（推奨ベストプラクティス）
  - 欠落していたモジュールを追加:
    - `src.backends.registry`
    - `src.helix_core.hybrid_search_engine`
    - `src.helix_core.web_search_engine`
    - `src.helix_core.auto_collector`
    - `src.mcp_client.helix_mcp_client`
    - `src.mcp_client.server_manager`
    - `src.tabs.encyclopedia_tab`
    - `src.tabs.trinity_dashboard_tab`
    - `src.tabs.trinity_inspector_tab`
    - `src.tabs.screenshot_capturer`
    - `src.ui.components.workflow_bar`
    - `src.ui_designer.ui_refiner`
    - `src.ui_designer.qss_generator`
    - `src.ui_designer.layout_analyzer`
- `src/utils/constants.py`: APP_VERSION を 2.2.4 に更新

**技術的詳細**:
```python
# v2.2.4: QObject継承を廃止し、純粋なPythonクラスに変更
class InspectorHook:  # QObject継承なし
    """
    PyInstaller EXE対応: QApplicationが存在しない状態で
    インスタンス化されてもスタックオーバーフローが発生しない
    """

    def _ensure_timer_initialized(self):
        """QTimerを遅延初期化（QApplication初期化後に呼び出し）"""
        if self._timer_initialized:
            return
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            if QApplication.instance() is not None:
                self._file_update_timer = QTimer()
                self._file_update_timer.timeout.connect(self._write_state_to_file)
                self._file_update_timer.start(500)
                self._timer_initialized = True
        except Exception as e:
            logger.warning(f"Failed to initialize QTimer: {e}")
```

**参考資料**:
- [PyQt6 App crashes on windows due to stack buffer overrun](https://forum.qt.io/topic/157345/pyqt6-app-crashes-on-windows-due-to-stack-buffer-overrun)
- [PyInstaller PyQt6 hiddenimports](https://github.com/pyinstaller/pyinstaller/issues/7122)
- [Packaging PyQt6 applications for Windows](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/)

---

## v2.2.3 更新履歴 (2026-01-23)

### PyInstaller EXE起動問題の修正

**概要**:
v2.2.3 はPyInstallerでビルドしたEXEが起動しない問題を修正したアップデート。
パス処理とhiddenimportsの設定を修正し、EXEが正常に起動するようになった。

**問題の原因**:
1. `HelixAIStudio.spec`のhiddenimportsに誤ったモジュールパスが指定されていた
   - `src.helix_core.local_llm_manager` → 正しくは `src.backends.local_llm_manager`
   - `src.helix_core.thermal_controller` → 存在しないモジュール（削除）
2. `HelixAIStudio.py`で`Path(__file__).parent`を使用していたが、
   PyInstaller EXE実行時には一時フォルダ(`sys._MEIPASS`)を指すため動作しなかった

**変更内容**:
- `HelixAIStudio.py`:
  - `get_application_path()` 関数を追加（PyInstaller対応）
  - EXE実行時: `sys.executable`のディレクトリを使用
  - Python実行時: `__file__`のディレクトリを使用
  - `APP_PATH`グローバル変数でアプリケーションパスを一元管理
  - srcパスの追加ロジックを`sys._MEIPASS`対応に修正
- `HelixAIStudio.spec`:
  - `src.helix_core.local_llm_manager` → `src.backends.local_llm_manager` に修正
  - `src.helix_core.thermal_controller` → 削除し、以下を追加:
    - `src.backends.thermal_monitor`
    - `src.backends.thermal_policy`
    - `src.backends.cloud_adapter`
- `src/utils/constants.py`: APP_VERSION を 2.2.3 に更新

**技術的詳細**:
```python
# PyInstaller対応のパス取得
def get_application_path() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller EXE実行時
        return Path(sys.executable).parent
    else:
        # Python実行時
        return Path(__file__).parent
```

**参考資料**:
- [PyInstaller Run-time Information](https://pyinstaller.org/en/stable/runtime-information.html)

---

## v2.2.2 更新履歴 (2026-01-23)

### Phase G+: Inspector Hook エラー通知強化

**概要**:
v2.2.2 は Inspector Hook のエラー状態通知を強化したアップデート。
Claude Codeタブの例外ハンドラでon_error()を呼び出すことで、
Trinity UI Inspectorがエラー発生を即座に検知できるようになった。

**変更内容**:
- `src/tabs/claude_tab.py`:
  - `_on_send()` 例外ハンドラで `on_error()` 呼び出し追加
  - `_send_message()` state_guard 例外ハンドラで `on_error()` 呼び出し追加
  - `_send_message()` send 例外ハンドラで `on_error()` 呼び出し追加
- `src/utils/constants.py`: APP_VERSION を 2.2.2 に更新

**設計思想**:
> エラーが発生したら即座にHook経由で通知
> Trinity側でerror_stateをチェックしてNG判定可能に

---

## v2.2.1 更新履歴 (2026-01-23)

### Phase G: Inspector Friendly Hook (Trinity連携)

**概要**:
v2.2.1 は Phase G を実装したアップデート。
Trinity が推測ではなく事実に基づいて Helix AI Studio の状態を確認できるようにする
「Inspector Friendly Hook」システムを実装。

---

### Phase G 主要機能

- **InspectorHook** (`src/utils/inspector_hook.py`)
  - シングルトンパターンによる状態一元管理
  - PyQt6シグナル/スロット機構を活用した Observer パターン
  - 読み取り専用の状態公開（外部からは get_state() のみ）
  - タイムスタンプ付きで状態変更履歴を記録（直近20件）
  - 8種類のイベントタイプをサポート

---

### Inspector State (監視対象状態)

| 状態 | 説明 | 更新タイミング |
|------|------|---------------|
| `app_ready` | アプリ起動完了状態 | MainWindow 初期化完了時 |
| `current_tab` | 現在のアクティブタブ | タブ切替時 |
| `last_user_action` | 最後のユーザー操作 | 各種UI操作時 |
| `chat_sent` | チャット送信中フラグ | 送信時 true、応答受信時 false |
| `last_response_received` | 応答受信フラグ | 応答受信時 |
| `active_model` | 現在選択中のモデル | モデル変更時 |
| `routing_decision` | ルーティング決定情報 | RoutingExecutor 実行時 |
| `error_state` | エラー状態 | エラー発生時 |
| `current_workflow_phase` | ワークフロー工程 | 工程遷移時 |
| `workflow_progress` | ワークフロー進捗(%) | 工程遷移時 |
| `approval_state` | 承認状態マップ | 承認変更時 |
| `risk_approved` | リスク承認フラグ | 承認変更時 |

---

### Inspector Event Types

| イベント | 説明 |
|---------|------|
| `app_ready` | アプリ起動完了 |
| `tab_changed` | タブ切替 |
| `chat_sent` | チャット送信 |
| `response_received` | 応答受信 |
| `model_changed` | モデル変更 |
| `routing_decision` | ルーティング決定 |
| `error_occurred` | エラー発生 |
| `workflow_changed` | ワークフロー変更 |
| `approval_changed` | 承認状態変更 |

---

### 新規ファイル

**Phase G:**
- `src/utils/inspector_hook.py`: InspectorHook, InspectorState, InspectorEvent, InspectorEventType, get_inspector_hook

---

### 修正ファイル

- `src/utils/__init__.py`: InspectorHook 関連をエクスポート追加
- `src/main_window.py`: InspectorHook 初期化、app_ready 通知、タブ切替フック追加
- `src/tabs/claude_tab.py`: チャット送信/応答受信/ルーティング決定/ワークフロー変更/承認変更/モデル変更フック追加
- `src/utils/constants.py`: APP_VERSION を 2.2.1 に更新
- `HelixAIStudio.spec`: inspector_hook を hiddenimports に追加

---

### 技術選定理由

| 技術 | 選定理由 |
|------|---------|
| シングルトンパターン | 状態の一元管理、グローバルアクセス |
| PyQt6 シグナル/スロット | Qt標準のObserverパターン実装 |
| dataclass | 状態データの型安全な管理 |
| タイムスタンプ履歴 | 状態変更の追跡・デバッグ支援 |

---

### 使用例

```python
from src.utils.inspector_hook import get_inspector_hook

# シングルトン取得
hook = get_inspector_hook()

# 状態取得
state = hook.get_state()
print(state["app_ready"])  # True/False
print(state["current_tab"])  # "Claude Code", etc.
print(state["chat_sent"])  # True/False

# イベント履歴取得
history = hook.get_event_history()

# シグナル接続
hook.stateChanged.connect(lambda state: print(f"State: {state}"))
hook.eventOccurred.connect(lambda event, data: print(f"Event: {event}"))
```

---

### 受け入れ条件達成 (Phase G)

- ✅ INSPECTOR_STATE 辞書でアプリ状態を一元管理
- ✅ アプリ起動完了 → app_ready=True
- ✅ タブ切替 → current_tab 更新
- ✅ チャット送信 → chat_sent=True
- ✅ 応答受信 → last_response_received=True
- ✅ Trinity が推測ではなく事実を確認できる状態

---

## v2.2.0 更新履歴 (2026-01-22)

### Phase F: ハイブリッド情報収集モデル (Encyclopedia)

**概要**:
v2.2.0 は Phase F を実装したアップデート。
静的データベース（RAG）と動的Web検索を組み合わせた高精度・高信頼・最新性を両立する
ハイブリッド情報収集システム「Encyclopedia」を実装。

---

### Phase F 主要機能

- **HybridSearchEngine** (`src/helix_core/hybrid_search_engine.py`)
  - 静的DB（VectorStore）+ 動的Web検索の統合検索
  - Reciprocal Rank Fusion (RRF) による結果統合
  - 閾値ベースのWeb検索自動補完
  - キャッシュ機能（TTL設定可能）
  - 検索履歴記録
  - LLM回答生成連携

- **WebSearchEngine** (`src/helix_core/web_search_engine.py`)
  - DuckDuckGo検索（無料・プライバシー重視）
  - Brave Search API対応（オプション）
  - ドメイン信頼度スコアリング
  - ブロックドメインフィルタ
  - レート制限対応
  - コンテンツ取得機能

- **AutoCollector** (`src/helix_core/auto_collector.py`)
  - トピックベースの自動収集
  - スケジュール実行（バックグラウンドスレッド）
  - VectorStoreへの自動登録
  - 重複検出・除去
  - 収集履歴管理
  - デフォルトトピック（Python, AI/ML, Claude, Gemini）

- **EncyclopediaTab** (`src/tabs/encyclopedia_tab.py`)
  - ハイブリッド検索UI
  - 静的/動的結果の可視化（色分け表示）
  - LLM回答生成機能
  - 自動収集管理UI
  - 信頼度バー表示
  - ソースリンク表示
  - 設定パネル（閾値、プロバイダー、収集設定）

---

### 技術選定理由

| 技術 | 選定理由 |
|------|---------|
| DuckDuckGo Search | 無料、プライバシー重視、Python SDK充実 |
| Brave Search API | AI向け最適化、高品質、フォールバック用 |
| Reciprocal Rank Fusion | 複数検索結果の統合に最適、実装シンプル |
| 既存VectorStore活用 | 新規DB不要、Phase C資産活用 |

---

### 新規ファイル

**Phase F:**
- `src/helix_core/hybrid_search_engine.py`: HybridSearchEngine, HybridSearchResult, SearchResultItem, SearchSource
- `src/helix_core/web_search_engine.py`: WebSearchEngine, WebSearchResult
- `src/helix_core/auto_collector.py`: AutoCollector, CollectionTopic, CollectionRecord, CollectionStats, CollectionStatus
- `src/tabs/encyclopedia_tab.py`: EncyclopediaTab, SearchWorker, CollectionWorker

---

### 修正ファイル

- `src/helix_core/__init__.py`: Phase F モジュールをエクスポート追加
- `src/tabs/settings_cortex_tab.py`: 「📖 Encyclopedia」タブを追加（13番目のサブタブ）
- `src/tabs/screenshot_capturer.py`: Encyclopedia Panel タブ対応追加（計13サブタブ）
- `src/utils/constants.py`: APP_VERSION を 2.2.0 に更新

---

### Cortexタブ拡張

- **サブタブ構成** (計13タブ)
  1. 一般設定
  2. AIモデル設定
  3. MCPサーバー管理
  4. MCPポリシー
  5. ローカル記憶
  6. ルーティングログ
  7. 監査ビュー
  8. 予算管理
  9. Local接続
  10. Thermal管理
  11. Knowledge Dashboard
  12. Trinity Dashboard
  13. **Encyclopedia Panel** (NEW)

---

### データファイル追加

- `data/hybrid_search/search_cache.json`: 検索キャッシュ
- `data/hybrid_search/search_history.jsonl`: 検索履歴
- `data/hybrid_search/config.json`: ハイブリッド検索設定
- `data/web_search/config.json`: Web検索設定
- `data/web_search/cache.json`: Web検索キャッシュ
- `data/auto_collector/topics.json`: 収集トピック
- `data/auto_collector/history.jsonl`: 収集履歴
- `data/auto_collector/config.json`: 収集設定
- `data/auto_collector/seen_hashes.json`: 重複検出用ハッシュ

---

### ログファイル追加

- `logs/hybrid_search.log`: ハイブリッド検索ログ
- `logs/web_search.log`: Web検索ログ
- `logs/auto_collector.log`: 自動収集ログ

---

### スクリーンキャプチャ対応

- メインタブ: 3タブ（Claude Code, Gemini Designer, App Manager）
- Cortexサブタブ: 13タブ
- **合計: 16画面**

---

### 受け入れ条件達成 (Phase F)

- ✅ Static検索の高精度retrieval
- ✅ 低信頼static → dynamic補完
- ✅ LLMへの統合promptテンプレート
- ✅ Helix UIで統合表示（Encyclopediaタブ）
- ✅ 自動収集機能（AutoCollector）
- ✅ TrinityExoskeleton連携準備完了

---

## v2.1.0 更新履歴 (2026-01-22)

### Phase E: TrinityExoskeleton連携強化 + UI総合化

**概要**:
v2.1.0 は Phase E を実装したアップデート。
Trinity Dashboard による ModelRepository / LocalLLMManager / HybridRouter の統合可視化、
Designer連携（UI図からSuggestionへ）、Workflow自動設定機能を実装。

---

### Phase E 主要機能

- **TrinityDashboardTab** (`src/tabs/trinity_dashboard_tab.py`)
  - ModelRepository 統計表示（登録モデル数、Cloud/Local比率、デフォルトモデル）
  - LocalLLMManager 状態監視（State、VRAM使用量、ロード済みモデル）
  - HybridRouter ルーティング統計（戦略、Local/Cloud選択率、総ルーティング数）
  - ルーティング戦略のリアルタイム切り替え（5種類）
  - 最近のルーティング決定履歴表示（色分け表示）
  - 登録モデル一覧表示
  - Designer連携: スクリーンショットからUI改善Suggestion生成
  - Workflow自動設定: Mother AI連携によるワークフロー自動構築

---

### Designer連携機能

- **UI図→Suggestion生成**
  - スクリーンショット選択からUI分析を実行
  - レイアウト、スタイル、アクセシビリティの改善提案を自動生成
  - 生成されたSuggestionをGemini Designerに送信可能
  - QSS変更の具体的な提案を含む

---

### Workflow自動設定機能

- **タスク/Workflow自動設定**
  - タスク受信時にMother AIが最適なWorkflowを自動設定
  - Reviewer AI によるレビューを含むか選択可能
  - Designer AI による UI チェックを含むか選択可能
  - 現在のWorkflow状態をリアルタイム表示
  - 手動でのWorkflow設定も可能

---

### 新規ファイル

**Phase E:**
- `src/tabs/trinity_dashboard_tab.py`: TrinityDashboardTab

---

### 修正ファイル

- `src/tabs/settings_cortex_tab.py`: 「🔺 Trinity Dashboard」タブを追加（12番目のサブタブ）
- `src/tabs/screenshot_capturer.py`: Trinity Dashboard タブ対応追加（計12サブタブ）
- `src/utils/constants.py`: APP_VERSION を 2.1.0 に更新

---

### Cortexタブ拡張

- **サブタブ構成** (計12タブ)
  1. 一般設定
  2. AIモデル設定
  3. MCPサーバー管理
  4. MCPポリシー
  5. ローカル記憶
  6. ルーティングログ
  7. 監査ビュー
  8. 予算管理
  9. Local接続
  10. Thermal管理
  11. Knowledge Dashboard
  12. **Trinity Dashboard** (NEW)

---

### スクリーンキャプチャ対応

- メインタブ: 3タブ（Claude Code, Gemini Designer, App Manager）
- Cortexサブタブ: 12タブ
- **合計: 15画面**

---

### 受け入れ条件達成 (Phase E)

- ✅ Trinity側にModelRepository/LocalLLMManager Routerを差分表示
- ✅ スクリーンショット機能を全タブ対象に確定（15画面対応）
- ✅ Designer連携（UI図からSuggestionへ）
- ✅ タスク/Workflow自動設定

---

## v2.0.0 更新履歴 (2026-01-22)

### Phase 4.0: Intelligent AI Orchestration & RAG-Based Knowledge Pipeline

**概要**:
v2.0.0 は Phase B〜D を統合した大型アップデート。
Local/Cloud ハイブリッドルーティング、RAG ベースの知識パイプライン、
3分割 AI オーケストレーション（Mother AI）を実装し、
AI 協調による高度な開発支援を実現。

---

### Phase B: Domain Models + Hybrid Routing

- **ModelRepository** (`src/backends/model_repository.py`)
  - ドメイン別 Local モデルのリスト管理
  - バージョン/メタデータ保存（model_repository.json）
  - モデルの検索・フィルタリング機能
  - デフォルトモデル登録（Claude Sonnet/Opus/Haiku 4.5, Gemini 3 Pro/Flash, Local）
  - コスト情報（USD/1K tokens）、コンテキスト長管理

- **HybridRouter** (`src/routing/hybrid_router.py`)
  - task_type + budget + resource + policy から backend を選択
  - 5種類のルーティング戦略
    - LOCAL_FIRST: ローカル優先
    - CLOUD_FIRST: クラウド優先
    - COST_OPTIMIZED: コスト最適化
    - QUALITY_FIRST: 品質優先
    - BALANCED: バランス（デフォルト）
  - ModelRepository/CloudAdapter/ThermalPolicy/BudgetBreaker との連携
  - フォールバックチェーン構築
  - RoutingDecision JSON への記録

---

### Phase C: RAG-Based Knowledge Pipeline

- **FeedbackCollector** (`src/helix_core/feedback_collector.py`)
  - ユーザー評価（good/bad/neutral/corrected）の記録
  - Q/A ペアの構造化保存（qa_entries.jsonl）
  - 失敗QAの追跡と修正
  - 統計情報（成功率、エントリ数）の提供

- **VectorStore** (`src/helix_core/vector_store.py`)
  - 軽量ベクトルストア（FAISS不要、純Python実装）
  - sentence-transformers による埋め込み生成（オプション）
  - フォールバック: ハッシュベースの疑似埋め込み
  - コサイン類似度による検索
  - インデックスの永続化（pickle + JSONL）

- **RAGPipeline** (`src/helix_core/rag_pipeline.py`)
  - プロンプトへの関連コンテキスト自動注入
  - FeedbackCollector + VectorStore 統合
  - Q/A 履歴からの定期インデクシング
  - Knowledge Dashboard 連携

---

### Phase D: Mother AI Controller (3分割AI協調)

- **MotherAIController** (`src/helix_core/mother_ai.py`)
  - Executor AI (Claude/Local): タスク実行管理
  - Designer AI (Gemini): UI/UX デザイン連携
  - Reviewer AI (Claude Opus/Local): コードレビュー統括
  - 3 AI 間のフロー制御とオーケストレーション
  - ワークフロー管理（create_workflow, execute_workflow）
  - システム最適化提案生成（analyze_and_recommend）
  - パフォーマンス/コスト/品質分析

---

### 統合UI: Knowledge Dashboard

- **KnowledgeDashboardTab** (`src/tabs/knowledge_dashboard_tab.py`)
  - RAG パイプライン統計表示
  - ベクトルストア統計表示
  - フィードバック統計表示
  - Mother AI 推奨事項表示
  - 手動インデクシング操作（Q/A インデクス、全再インデクス）
  - RAG 設定（Top K、最小スコア）
  - テスト検索機能

- **Cortexタブ拡張**
  - 「📚 Knowledge」タブを追加（11番目のサブタブ）
  - スクリーンキャプチャ対応更新（計13画面）

---

### 新規ファイル

**Phase B:**
- `src/backends/model_repository.py`: ModelRepository, ModelMetadata, ModelDomain, ModelSource

**Phase C:**
- `src/helix_core/feedback_collector.py`: FeedbackCollector, FeedbackRating, QAEntry, FeedbackStats
- `src/helix_core/vector_store.py`: SimpleVectorStore, VectorDocument, SearchResult
- `src/helix_core/rag_pipeline.py`: RAGPipeline, RAGContext, IndexingStats

**Phase D:**
- `src/helix_core/mother_ai.py`: MotherAIController, AIRole, TaskStatus, AITask, WorkflowStep, SystemRecommendation

**UI:**
- `src/tabs/knowledge_dashboard_tab.py`: KnowledgeDashboardTab, IndexingWorker

**Routing:**
- `src/routing/hybrid_router.py`: HybridRouter, RoutingStrategy, RoutingContext, RoutingDecision

---

### 修正ファイル

- `src/helix_core/__init__.py`: Phase C/D モジュールをエクスポート追加
- `src/backends/__init__.py`: ModelRepository をエクスポート追加
- `src/routing/__init__.py`: HybridRouter をエクスポート追加
- `src/tabs/settings_cortex_tab.py`: 「📚 Knowledge」タブを追加
- `src/tabs/screenshot_capturer.py`: Thermal/Knowledge タブ対応追加（計11サブタブ）
- `src/utils/constants.py`: APP_VERSION を 2.0.0 に更新

---

### ログファイル追加

- `logs/model_repository.log`: ModelRepository 操作ログ
- `logs/hybrid_router.log`: HybridRouter 決定ログ
- `logs/feedback_collector.log`: FeedbackCollector 操作ログ
- `logs/vector_store.log`: VectorStore 操作ログ
- `logs/rag_pipeline.log`: RAGPipeline 操作ログ
- `logs/mother_ai.log`: MotherAI 操作ログ

---

### データファイル追加

- `data/model_repository.json`: モデルリポジトリ
- `data/feedback/qa_entries.jsonl`: Q/A エントリ
- `data/feedback/feedback_stats.json`: フィードバック統計
- `data/vector_store/index.pkl`: ベクトルインデックス
- `data/vector_store/documents.jsonl`: ドキュメント
- `data/rag/indexing_stats.json`: インデクシング統計
- `data/mother_ai/tasks.jsonl`: Mother AI タスク履歴
- `data/mother_ai/recommendations.json`: システム最適化提案
- `data/mother_ai/current_workflow.json`: 現在のワークフロー

---

### 受け入れ条件達成

- ✅ ModelRepository: ドメイン別モデル管理、バージョン/メタデータ保存
- ✅ HybridRouter: task_type + budget + resource + policy から backend 選択
- ✅ FeedbackCollector: Q/A ペアの構造化保存、評価記録
- ✅ VectorStore: 埋め込み生成、類似検索
- ✅ RAGPipeline: コンテキスト自動注入、定期インデクシング
- ✅ MotherAI: 3分割AI協調、ワークフロー管理、最適化提案
- ✅ Knowledge Dashboard: 統合UI、インデクシング操作、統計表示
- ✅ スクリーンキャプチャ: Thermal/Knowledge タブ対応（計13画面）

---

## v1.9.0 更新履歴 (2026-01-22)

### Phase 3.5: Local LLM 最適制御 & Thermal Policy 実装

- **CP1: LocalLLM Manager（VRAM非常駐構造）** (`src/backends/local_llm_manager.py`)
  - UML状態遷移図に基づく状態管理（Idle/Loading/Active/Throttled/Unloading/Error）
  - Idle時はVRAMにモデルロードなし
  - Request時にLoading→Activeへ移行
  - idle_timeout後にUnloading→Idleへ移行
  - 状態遷移ログ記録（`logs/llm_state_transitions.jsonl`）

- **CP2: Thermal Monitor（GPU/CPU温度監視）** (`src/backends/thermal_monitor.py`)
  - nvidia-smi (Windows) を使用したGPU温度・VRAM監視
  - psutil を使用したCPU温度・使用率監視
  - 定期的なサンプリングと状態通知
  - 閾値超過時のコールバック発行
  - ログ記録（`logs/thermal_monitor.log`, `logs/thermal_readings.jsonl`）

- **CP3: Thermal Policy Control（温度制御ポリシー）** (`src/backends/thermal_policy.py`)
  - 状態機械に基づく温度制御（Normal/WarningTemp/StopTemp/Throttle/CoolingWait）
  - GPU/CPU温度閾値設定（Warning/Stop）
  - 高温時の自動スロットル/アンロード
  - LocalLLM Managerとの連携
  - ログ記録（`logs/thermal_policy.log`, `logs/thermal_policy_events.jsonl`）

- **CP4: Fan Control推奨表示**
  - 温度レベルに応じたファン制御推奨コマンド生成
  - Windows (nvidia-smi) / Linux対応
  - UIからコピー可能

- **CP5: CloudAI Adapter（フェールオーバー）** (`src/backends/cloud_adapter.py`)
  - バックエンド選択（local/cloud）の自動化
  - コスト見積もり機能
  - 予算チェック機能
  - フォールバック連鎖（Local→Sonnet→Opus）
  - 選択理由のログ記録（`logs/routing_decisions.jsonl`）

- **CP6: Logging & Diagnostics拡充** (`src/utils/diagnostics.py`)
  - Phase 3.5関連の全ログファイルを診断ZIPに追加
  - 設定ファイル（llm_manager_config.json, thermal_config.json等）も同梱

### Cortexタブ拡張

- **🌡️ Thermal管理タブ** (`src/tabs/settings_cortex_tab.py`)
  - Local LLM Mode設定（常駐/オンデマンド/手動）
  - Idle Timeout設定
  - GPU/CPU温度閾値設定（Warning/Stop）
  - リアルタイム温度表示（プログレスバー付き）
  - ファン制御推奨表示とコピー機能
  - 監視開始/停止ボタン

### 新規ファイル

- `src/backends/local_llm_manager.py`: LocalLLMManager, LLMManagerConfig, LLMState, get_llm_manager
- `src/backends/thermal_monitor.py`: ThermalMonitor, ThermalReading, ThermalThresholds, ThermalStatus, get_thermal_monitor
- `src/backends/thermal_policy.py`: ThermalPolicyController, ThermalPolicyConfig, ThermalPolicyState, get_thermal_policy
- `src/backends/cloud_adapter.py`: CloudAdapter, BackendType, SelectionReason, CostEstimate, BackendSelection, get_cloud_adapter

### 技術詳細

- **状態遷移図（LocalLLMManager）**:
  ```
  [*] --> Idle
  Idle --> Loading : request_received
  Loading --> Active : load_success
  Loading --> Error : load_failure
  Active --> Throttled : temp_exceeds_warn
  Active --> Unloading : idle_timeout
  Active --> Error : exec_failure
  Throttled --> Active : temp_normalized
  Throttled --> Unloading : idle_timeout
  Error --> Unloading : reset
  Unloading --> Idle : unload_complete
  ```

- **Thermal Policy State Machine**:
  ```
  [*] --> Normal
  Normal --> WarningTemp : gpu_temp > gpu_warn_threshold
  WarningTemp --> Normal : gpu_temp <= gpu_warn_threshold
  WarningTemp --> StopTemp : gpu_temp > gpu_stop_threshold
  StopTemp --> CoolingWait : throttle_applied
  Throttle --> Normal : gpu_temp <= gpu_warn_threshold
  CoolingWait --> Normal : temp_normalized
  ```

- **デフォルト閾値**:
  - gpu_warn_threshold = 70℃
  - gpu_stop_threshold = 85℃
  - cpu_warn_threshold = 70℃
  - cpu_stop_threshold = 90℃

---

## v1.8.2 更新履歴 (2026-01-22)

### Cortex内全サブタブスクリーンキャプチャ対応

- **スクリーンキャプチャ機能拡張**
  - v1.8.1の機能を拡張し、Cortex内の全9サブタブを個別キャプチャ
  - メインタブ3つ + Cortexサブタブ9つ = 計12画面をキャプチャ
  - フォルダ階層を維持したZIP生成

- **ScreenshotCaptureThread 機能強化** (`src/tabs/screenshot_capturer.py`)
  - `cortex_subtab_mapping`: 9サブタブのマッピング定義
  - `_capture_cortex_subtabs()`: Cortex内サブタブ個別キャプチャ
  - `_find_child_tab_widget()`: ネストされたQTabWidget探索
  - サブタブ情報も `routing_decisions.jsonl` に記録

### 技術詳細

- PyQt6 `QTabWidget.widget(index)` でサブタブウィジェットを取得
- 再帰的なQTabWidget探索でネスト対応
- サブタブ切り替え後150msの待機時間で描画安定化
- フォールバック機能（サブタブ未検出時はCortex全体キャプチャ）

---

## v1.8.0 更新履歴 (2026-01-22)

### 新機能 (CP1〜CP9実装)

- **CP1: Routing Decision Log**: ルーティング決定をJSONLに記録、Cortex UIで閲覧可能
- **CP2: 予算サーキットブレーカー**: セッション/日次予算のリアルタイム監視、警告/停止機能
- **CP3: Local接続UI完成**: ローカルLLM(Trinity/Ollama)のエンドポイント設定、疎通確認
- **CP4: Workflow Engine安定化**: 工程履歴の追跡、UI表示、成果リンク機能
- **CP5: スクリーンショット取得UI**: App Managerから画面キャプチャ、プロジェクトフォルダに保存
- **CP6: Gemini Designer改善**: スクリーンショット分析機能、UI要素抽出レポート生成
- **CP7: MCP Policy細粒度設定**: プロジェクト単位のポリシー設定UI、スコープ管理
- **CP8: 監査ビュー強化**: フィルタ/検索/CSV・JSONエクスポート対応
- **CP9: Local LLM実装受け口**: tools call対応準備、fallback連動

### Settings/Cortexタブ拡張

- **MCPポリシータブ**: ツール単位の承認スコープと制約を設定
- **監査ビュータブ**: ルーティングログのフィルタ・エクスポート

---

## v1.2.0 主要機能

- **AIモデルを最新バージョンに更新**:
  - Claude: Sonnet 4.5 / Opus 4.5 / Haiku 4.5 対応
  - Gemini: Gemini 3 Pro / Gemini 3 Flash 対応
- **MCP Tool Search機能**: 多数のMCPツール使用時にコンテキストを95%削減する動的ツール読み込み
- **詳細な日本語ツールチップ**: 全UIコンポーネントに詳細で分かりやすい日本語ツールチップを実装
- **MCPサーバー拡充**: Slack, Google Drive連携サーバーを追加
- **プロジェクト名**: Helix AI Studio (論理と視覚の螺旋構造を象徴)
- **ベースバージョン**: Claude Code GUI v7.6.2 + Trinity Exoskeleton v2.2.5
- **4タブ構成**: Claude Code / Gemini Designer / App Manager / Settings(Cortex)
- **MCP統合**: Model Context Protocolネイティブサポート
- **Knowledge Graph**: GraphRAG/LightRAG ベースの知識管理
- **UI Refiner**: Gemini専用UI調整パイプライン

---

## 目次

1. [原初の意図 (Original Intent)](#1-原初の意図-original-intent)
2. [プロジェクト概要](#2-プロジェクト概要)
3. [アーキテクチャ全体像](#3-アーキテクチャ全体像)
4. [タブ構成と機能要件](#4-タブ構成と機能要件)
5. [技術的要件と外部ツール](#5-技術的要件と外部ツール)
6. [ディレクトリ構造](#6-ディレクトリ構造)
7. [セキュリティ設計](#7-セキュリティ設計)
8. [ビルド・デプロイ](#8-ビルドデプロイ)
9. [今後のロードマップ](#9-今後のロードマップ)
10. [AI向けコンテキスト要約](#10-ai向けコンテキスト要約)
11. [参考リソース](#11-参考リソース)

---

## 1. 原初の意図 (Original Intent)

### 1.1 なぜ作るのか

**背景**
Claude Code GUIは強力な開発支援ツールとして進化してきたが、以下の発展可能性があった：

1. **MCP未対応**: Model Context Protocolによる自律的なツール連携が未実装
2. **UI調整の手動性**: 生成されたアプリのUI調整が手作業中心
3. **知識グラフの欠如**: プロジェクト構造の可視化・理解が困難
4. **ローカルAI統合の余地**: Trinity Exoskeletonの機能をより深く統合可能

**解決策としてHelix AI Studioを新規開発**

| 課題 | Helix AI Studioでの解決 |
|------|------------------------|
| MCP未対応 | ネイティブMCPクライアント統合 |
| UI調整の手動性 | Gemini Designer（UI Refiner Pipeline） |
| 知識グラフの欠如 | Knowledge Graph Visualization |
| ローカルAI統合 | Settings/Cortex（LightRAG、記憶システム） |

### 1.2 核心的な価値

1. **論理と視覚の螺旋構造**: Claude（論理）とGemini（視覚）の協調
2. **自律型開発環境**: MCPによる安全な外部リソースアクセス
3. **使うほど賢くなる**: GraphRAGによる開発履歴の蓄積と活用
4. **シームレスなワークフロー**: 設計→実装→UI調整→検証の一貫性

### 1.3 名前の由来

**Helix** (螺旋)
- Claude（論理構築）とGemini（UIデザイン）の二重螺旋
- Trinity（ローカルAI）による進化的な発展
- DNAのように自己複製・進化するAI開発環境

---

## 2. プロジェクト概要

### 2.1 基本情報

| 項目 | 値 |
|------|-----|
| プロジェクト名 | Helix AI Studio |
| 現在のバージョン | 1.8.0 |
| 開発開始日 | 2026-01-20 |
| プラットフォーム | Windows 11 / Python 3.12+ |
| GUIフレームワーク | PyQt6 6.10.0+ |
| ベースプロジェクト | Claude Code GUI v7.6.2 |
| Claude AIモデル | Claude Sonnet 4.5 / Opus 4.5 / Haiku 4.5 |
| Gemini AIモデル | Gemini 3 Pro / Gemini 3 Flash |

### 2.2 技術スタック

```
┌─────────────────────────────────────────────────────────────┐
│  Helix AI Studio v1.8.0                                     │
├─────────────────────────────────────────────────────────────┤
│  UI Layer        │ PyQt6, QSS (Qt Style Sheets)            │
│                  │ 4 tabs: Claude Code, Gemini Designer,   │
│                  │         App Manager, Settings(Cortex)   │
├─────────────────────────────────────────────────────────────┤
│  MCP Layer       │ mcp (Python SDK)                        │
│                  │ HelixMCPClient - ツール呼び出しルーター │
│                  │ MCP Tool Search - 動的ツール読み込み    │
│                  │ filesystem, git, brave-search,          │
│                  │ github, slack, google-drive サポート    │
├─────────────────────────────────────────────────────────────┤
│  Claude Layer    │ Claude Sonnet/Opus/Haiku 4.5            │
│                  │ Claude CLI + Native MCP Client          │
│                  │ Aider-style Diff View                   │
│                  │ Autonomous Context Loading              │
├─────────────────────────────────────────────────────────────┤
│  Gemini Layer    │ Gemini 3 Pro / Gemini 3 Flash           │
│                  │ Gemini CLI Agent Mode + Extensions      │
│                  │ UI Refiner Pipeline                     │
│                  │ QSS/レイアウト自動生成                  │
├─────────────────────────────────────────────────────────────┤
│  Knowledge Layer │ GraphRAG (Temporal Knowledge Graph)     │
│                  │ LightRAG (Fast Retrieval)               │
│                  │ networkx + pyvis (可視化)               │
├─────────────────────────────────────────────────────────────┤
│  Helix Core      │ Trinity Exoskeleton v2.2.5 ベース       │
│                  │ ローカルLLM連携（接続I/F設計済・        │
│                  │ 実接続はPhase 3.x予定）                 │
│                  │ 時系列記憶管理                          │
├─────────────────────────────────────────────────────────────┤
│  Browser Layer   │ Playwright, browser-use                 │
│                  │ Auto-Debug（自動検索解決）              │
├─────────────────────────────────────────────────────────────┤
│  Data Layer      │ JSON, SQLite, File System               │
│                  │ Knowledge Graph Storage                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. アーキテクチャ全体像

### 3.1 システム構成図

```
┌────────────────────────────────────────────────────────────────┐
│                    Helix AI Studio                              │
├────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Claude Code  │  │   Gemini     │  │     App      │          │
│  │    Tab       │  │  Designer    │  │   Manager    │          │
│  │              │  │    Tab       │  │    Tab       │          │
│  │ - Logic      │  │ - UI Polish  │  │ - Graph View │          │
│  │ - MCP Tools  │  │ - QSS Gen    │  │ - File Deps  │          │
│  │ - Diff View  │  │ - Layout Fix │  │ - Launch App │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│  ┌──────┴─────────────────┴─────────────────┴───────┐          │
│  │              Helix MCP Client                     │          │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐           │          │
│  │  │filesys  │  │  git    │  │ brave   │  ...      │          │
│  │  │ server  │  │ server  │  │ search  │           │          │
│  │  └─────────┘  └─────────┘  └─────────┘           │          │
│  └──────────────────────────────────────────────────┘          │
│                           │                                     │
│  ┌────────────────────────┴─────────────────────────┐          │
│  │              Helix Core (Trinity Base)            │          │
│  │  ┌─────────────┐  ┌─────────────┐                │          │
│  │  │  GraphRAG   │  │  LightRAG   │                │          │
│  │  │  (時系列)   │  │ (高速検索)  │                │          │
│  │  └─────────────┘  └─────────────┘                │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐          │
│  │          Settings / Cortex Tab                    │          │
│  │  - MCP Server Manager                             │          │
│  │  - Local Memory (LightRAG)                        │          │
│  │  - Model Configuration                            │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 データフロー

```
User Request
     │
     ▼
┌─────────────────┐
│  Claude Code    │ ─── Logic & Architecture ───┐
│  Tab            │                              │
└────────┬────────┘                              │
         │                                       │
         ▼                                       │
┌─────────────────┐                              │
│  MCP Client     │ ─── Tool Execution ─────────┤
│  (filesys/git)  │                              │
└────────┬────────┘                              │
         │                                       │
         ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│  App Manager    │ ◄── Graph View ─── │  Generated App  │
│  Tab            │                    └─────────────────┘
└────────┬────────┘                              │
         │                                       │
         ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│  Gemini         │ ─── UI Polish ──── │  Polished UI    │
│  Designer Tab   │                    └─────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Helix Core     │ ─── Knowledge Storage
│  (GraphRAG)     │
└─────────────────┘
```

---

## 4. タブ構成と機能要件

### Tab 1: Claude Code (Logic & Architecture)

**役割**: アプリの論理設計、バックエンド構築、TDDパイプラインの実行
**ベース**: Claude Code GUI v7.6.2 の「AppBuilder」機能

**【新規・改良機能】**

1. **Native MCP Client統合 [Ref: Cline, awesome-mcp-servers]**
   - アプリがMCPホストとして機能
   - `filesystem`, `git`, `brave-search` などのMCPサーバーと直接通信
   - サンドボックス外のファイルシステムや外部APIへ安全にアクセス

2. **Aider-style Diff View [Ref: Aider]**
   - コード生成時、全ファイル書き換えではなく差分（Diff）のみを生成
   - ユーザーが「適用/却下」を選択できるUIをチャット内に追加

3. **Autonomous Context Loading [Ref: OpenCode]**
   - 関連ファイルをプロジェクト内から自律的に探索
   - TrinityのPerception機能を統合してコンテキストに追加

### Tab 2: Gemini Designer (UI/UX Refinement)

**役割**: 作成されたアプリのUI調整、QSS生成、レイアウト修正
**ベース**: Claude Code GUIのGeminiタブ + Gemini CLI Agent Mode

**【新規実装: UI Refiner Pipeline】**

- **入力**: 対象アプリのフォルダパス（App Managerと連動）
- **モード**: `UI Polish Mode`
- **プロセス**:
  1. **Analysis**: `main_window.py`, `styles.qss` などGUI関連ファイルを読み込み
  2. **Visualization**: スクリーンショット認識でレイアウトの崩れを特定
  3. **Proposal**: QSS修正案やレイアウト変更を提案
  4. **Application**: ユーザー承認後、スタイルファイルのみを書き換え

### Tab 3: App Manager (Project Hub)

**役割**: アプリの起動、管理、可視化
**ベース**: Claude Code GUI v7.4.0

**【新規・改良機能】**

1. **Knowledge Graph Visualization [Ref: Graphiti, LightRAG]**
   - `networkx` + `pyvis` (またはWebEngine) でファイル構造を可視化
   - プロジェクト内の「機能」と「ファイル」の関係を図示
   - TrinityのGraphRAG技術を応用

### Tab 4: Settings / Cortex (Knowledge & Local AI)

**役割**: 設定管理およびローカルAI/記憶の管理
**ベース**: Trinity Exoskeleton v2.2.5 の設定 + Cortex

**【新規・改良機能】**

1. **Local Memory (LightRAG Implementation) [Ref: HKUDS/LightRAG]**
   - Graphベースの検索（LightRAG簡易版）を導入
   - 開発履歴を時系列で保持
   - 「前回のあのエラーはどう解決した？」に即答

2. **MCP Server Manager**
   - 使用するMCPサーバー（Filesystem, Github, Postgres等）の有効/無効を切り替えるGUI

---

## 5. 技術的要件と外部ツール

### 5.1 MCP (Model Context Protocol)
**参考**: Anthropic, Cline
- ライブラリ: `mcp` (Python SDK)
- 実装: `HelixMCPClient` クラスでClaude/Geminiからのツール呼び出しをルーティング

### 5.2 Temporal Knowledge Graph
**参考**: getzep/graphiti
- TrinityのGraphRAGを拡張
- ノードに「タイムスタンプ」と「エピソードID」を付与
- アプリのバージョンごとの変更履歴をグラフとして保持

### 5.3 Browser Automation
**参考**: browser-use, punkpeye/awesome-mcp-servers
- Trinity v2.2.5の`browser-use` (Playwrightベース)
- Claudeタブから「調査ツール」として明示的に呼び出し可能
- **Auto-Debug機能**: エラー発生時、自動的にStackOverflowや公式ドキュメントを検索

### 5.4 LightRAG
**参考**: HKUDS/LightRAG
- 軽量RAGフレームワーク
- ドキュメントインデックス、知識グラフ探索
- マルチモーダル（PDF/画像）対応

---

## 6. ディレクトリ構造

```
Helix AI Studio/
├── HelixAIStudio.py          # エントリーポイント
├── PROJECT_BIBLE_Helix.md    # ← 本ドキュメント
├── CHANGELOG.md              # 変更履歴
├── requirements.txt          # 依存パッケージ
│
├── src/                      # ソースコード
│   ├── __init__.py
│   ├── main_window.py        # メインウィンドウ
│   ├── app_config.py         # 設定管理
│   │
│   ├── helix_core/           # ローカル脳 (Trinity Base)
│   │   ├── __init__.py
│   │   ├── graph_rag.py      # GraphRAG実装
│   │   ├── light_rag.py      # LightRAG実装
│   │   ├── memory_store.py   # 時系列記憶管理
│   │   └── perception.py     # Perception Engine
│   │
│   ├── mcp_client/           # MCPクライアント
│   │   ├── __init__.py
│   │   ├── helix_mcp_client.py  # メインクライアント
│   │   ├── filesystem_server.py # ファイルシステムサーバー
│   │   ├── git_server.py     # Gitサーバー
│   │   └── server_manager.py # サーバー管理
│   │
│   ├── ui_designer/          # Gemini UI調整エンジン
│   │   ├── __init__.py
│   │   ├── ui_refiner.py     # UI Refiner Pipeline
│   │   ├── qss_generator.py  # QSSジェネレーター
│   │   └── layout_analyzer.py # レイアウト分析
│   │
│   ├── tabs/                 # 4つのメインタブ
│   │   ├── __init__.py
│   │   ├── claude_tab.py     # Claude Code タブ
│   │   ├── gemini_designer_tab.py  # Gemini Designer タブ
│   │   ├── app_manager_tab.py      # App Manager タブ
│   │   └── settings_cortex_tab.py  # Settings/Cortex タブ
│   │
│   ├── claude/               # Claude CLI統合
│   │   ├── __init__.py
│   │   ├── process_controller.py
│   │   ├── diff_viewer.py    # Aider-style Diff View
│   │   ├── context_loader.py # Autonomous Context Loading
│   │   └── terminal_widget.py
│   │
│   ├── gemini/               # Gemini統合
│   │   ├── __init__.py
│   │   ├── gemini_cli_controller.py
│   │   └── gemini_config.py
│   │
│   ├── ui/                   # UIコンポーネント
│   │   ├── __init__.py
│   │   ├── styles.py
│   │   ├── widgets.py
│   │   └── graph_viewer.py   # Knowledge Graph表示
│   │
│   ├── utils/                # ユーティリティ
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   └── helpers.py
│   │
│   └── data/                 # データ管理
│       ├── __init__.py
│       ├── session_manager.py
│       └── history_manager.py
│
├── config/                   # 設定ファイル
│   ├── mcp_servers.json      # MCPサーバー設定
│   └── app_settings.json     # アプリ設定
│
├── data/                     # 実行時データ
│   └── knowledge_graph/      # Knowledge Graphデータ
│
└── logs/                     # ログファイル
```

---

## 7. セキュリティ設計

### 7.1 MCPセキュリティ

- **サンドボックス制御**: MCPサーバーごとにアクセス権限を設定
- **承認フロー**: 危険な操作は明示的なユーザー承認が必要
- **監査ログ**: 全MCPツール呼び出しを記録

### 7.2 認証情報管理

- **Fernetによる暗号化**: APIキーなどの機密情報を暗号化保存
- **環境変数優先**: 可能な限り環境変数から認証情報を取得

---

## 8. ビルド・デプロイ

### 8.1 開発環境セットアップ

```bash
# 仮想環境作成
python -m venv venv
venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# MCPサーバーインストール（必要に応じて）
npm install -g @anthropic/mcp-server-filesystem
npm install -g @anthropic/mcp-server-git
```

### 8.2 実行

```bash
python HelixAIStudio.py
```

### 8.3 ビルド (PyInstaller)

```bash
pyinstaller --onefile --windowed --name HelixAIStudio HelixAIStudio.py
```

---

## 9. 今後のロードマップ

> **フェーズ番号の区別について**
>
> 本ロードマップには2種類のPhase番号が存在します：
> - **概念フェーズ（Phase 1〜6）**: 機能カテゴリ別のマイルストーン（MCP統合、UI Designer等）
> - **実装フェーズ（Phase 1.x〜3.x）**: 実際の開発進捗（安定性、抽象化、Local統合）
>
> | 実装フェーズ | 内容 | 該当バージョン |
> |-------------|------|----------------|
> | Phase 1.x | 安定性・安全性・監査（Risk Gate、MCP Policy、承認システム） | v1.3.0〜v1.6.1 |
> | Phase 2.x | 抽象化・ルーティング・コスト制御（BackendRouter、Budget） | v1.7.0〜v1.9.0 |
> | Phase 3.x | Local/Trinity完全統合（healthcheck、fallback、Thermal） | v1.9.0 |
> | Phase 4.0 | AI協調・RAG・MotherAI（HybridRouter、RAGPipeline、MotherAI） | v2.0.0 |

### Phase 1: 基盤構築 (v1.1.0) - 完了
- [x] 4タブ構成のメインウィンドウ
- [x] Claude Code タブ（UI骨格とダミー応答実装）
- [x] UIの全面的な日本語化、ツールチップ実装

### Phase 2: 最新AIモデル対応 (v1.2.0) - 完了
- [x] Claude 4.5系列モデル対応 (Sonnet 4.5 / Opus 4.5 / Haiku 4.5)
- [x] Gemini 3系列モデル対応 (Gemini 3 Pro / Gemini 3 Flash)
- [x] MCP Tool Search機能の説明追加（動的ツール読み込み）
- [x] MCPサーバー拡充 (Slack, Google Drive追加)
- [x] 詳細な日本語ツールチップの実装

### Phase 3: MCP統合 (v1.3.0)
- [ ] HelixMCPClient完全実装
- [ ] filesystem/git MCPサーバー統合
- [ ] MCP Server Manager GUI

### Phase 4: UI Designer (v1.4.0)
- [ ] Gemini UI Refiner Pipeline
- [ ] QSS自動生成
- [ ] スクリーンショット認識

### Phase 5: Knowledge Graph (v1.5.0)
- [ ] GraphRAG実装
- [ ] LightRAG統合
- [ ] 可視化UI（pyvis/WebEngine）

### Phase 6: Advanced Features (v2.0.0)
- [ ] Aider-style Diff View
- [ ] Autonomous Context Loading
- [ ] Auto-Debug機能

---

### 【実装フェーズ】Phase 2.x: 抽象化・ルーティング・コスト制御 (v1.7.x〜)

> **目的**: 複数バックエンド（Claude/Gemini/Local）を統一的に扱い、コスト効率と可用性を向上させる

#### 2.1 BackendRouter（決定理由の可視化）
- [ ] 統一ルーティングインターフェース実装
- [ ] タスク種別に基づく自動バックエンド選択
- [ ] 決定理由のログ出力（DecisionLogger）
- [ ] UI上でのルーティング結果表示

#### 2.2 Project別ModelPreset
- [ ] プロジェクトごとのモデル設定保存
- [ ] タスク種別×モデルのマッピング定義
- [ ] 設定UIの実装

#### 2.3 Cost/Budget Circuit Breaker
- [ ] UsageMetrics: 使用量トラッキング
- [ ] BudgetBreaker: 予算上限での自動停止
- [ ] アラート通知機能

#### 2.4 Fallback戦略（安全優先）
- [ ] バックエンド障害時の自動切り替え
- [ ] 優先度チェーン設定
- [ ] ヘルスチェック機構

**既存の基盤ファイル**（Phase 2.x向けに設計済み）:
- `src/routing/router.py` - BackendRouter基盤
- `src/routing/classifier.py` - タスク分類器
- `src/routing/fallback.py` - フォールバック戦略
- `src/routing/decision_logger.py` - 決定ログ
- `src/routing/model_presets.py` - モデルプリセット
- `src/metrics/usage_metrics.py` - 使用量メトリクス
- `src/metrics/budget_breaker.py` - 予算ブレーカー
- `src/backends/base.py` - バックエンド抽象基底クラス

---

### 【実装フェーズ】Phase 3.x: Local/Trinity完全統合 (v2.0.x〜)

> **目的**: ローカルLLM（Ollama/LM Studio等）との完全統合によりオフライン動作・コスト削減を実現

#### 3.1 Local Backend接続
- [ ] Ollama APIクライアント実装
- [ ] LM Studio互換接続
- [ ] モデル一覧取得・選択UI

#### 3.2 Healthcheck機構
- [ ] 定期的なバックエンド状態確認
- [ ] 接続断検出と通知
- [ ] 自動再接続

#### 3.3 Trinity Exoskeleton統合
- [ ] GraphRAG/LightRAGとの連携
- [ ] 開発履歴からの学習
- [ ] コンテキスト自動補完

#### 3.4 Hybrid推論
- [ ] ローカル/クラウド自動選択
- [ ] コスト最適化ルーティング
- [ ] 品質フォールバック

**既存の基盤ファイル**（Phase 3.x向けに設計済み）:
- `src/backends/local_connector.py` - ローカル接続I/F
- `src/backends/local_backend.py` - ローカルバックエンド
- `src/helix_core/` - Trinity統合コンポーネント

---

## 10. AI向けコンテキスト要約

```
【プロジェクト】Helix AI Studio v1.6.2
【目的】Claude + Gemini + ローカルAI(Trinity)を統合した次世代開発環境
【構成】4タブ: Claude Code / Gemini Designer / App Manager / Settings
【AIモデル】
- Claude: Sonnet 4.5 (推奨) / Opus 4.5 / Haiku 4.5
- Gemini: Gemini 3 Pro (推奨) / Gemini 3 Flash
【特徴】
- MCPネイティブサポート（外部ツール連携）
- MCP Tool Search（動的ツール読み込み、コンテキスト95%削減）
- Aider-style Diff View（差分適用UI）
- GraphRAG/LightRAG（知識グラフ・記憶）
- UI Refiner（Geminiによる自動UI調整）
【ベース】Claude Code GUI v7.6.2 + Trinity Exoskeleton v2.2.5
【技術スタック】Python 3.12+ / PyQt6 / mcp SDK / networkx / pyvis
【実装フェーズ】
- Phase 1.x（v1.3〜1.6）: 安定性・安全性・監査 ← 完了
- Phase 2.x（v1.7〜）: 抽象化・ルーティング・コスト制御 ← 次
- Phase 3.x（v2.0〜）: Local/Trinity完全統合 ← 計画中
【注意】Local LLM連携は接続I/F設計済み、実接続はPhase 3.x
```

---

## 11. 参考リソース

### 外部プロジェクト

| プロジェクト | 概要 | 適用箇所 |
|-------------|------|----------|
| [OpenCode](https://github.com/OpenCodeAI/opencode) | オープンソースAI coding agent | Autonomous Context Loading |
| [Cline](https://github.com/clinebot/cline) | 自律型コーディングエージェント | MCPクライアント設計 |
| [Aider](https://github.com/paul-gauthier/aider) | Terminal-based AI pair programmer | Diff View UI |
| [getzep/graphiti](https://github.com/getzep/graphiti) | 時系列対応知識グラフ | GraphRAG実装 |
| [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | 軽量RAGフレームワーク | LightRAG実装 |
| [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | MCPサーバーカタログ | MCPサーバー選定 |

### 公式ドキュメント

- [Claude Code CLI](https://code.claude.com/docs/ja/overview)
- [Gemini CLI](https://codelabs.developers.google.com/getting-started-gemini-cli-extensions?hl=ja)
- [MCP Protocol](https://modelcontextprotocol.io/)

---

---

## 12. 修正履歴

### v3.5.0 (2026-01-25) - 権限確認自動スキップ機能 (Auto Permission Skip)

**概要**:
Claude CLIの `--dangerously-skip-permissions` フラグを使用した権限確認自動スキップ機能を追加。

**主要変更**:
- `src/backends/claude_cli_backend.py` - `--dangerously-skip-permissions` フラグ対応
- `src/tabs/claude_tab.py` - 「🔓 許可」チェックボックス追加
- `src/utils/constants.py` - バージョン 3.5.0

---

### v3.4.0 (2026-01-25) - 会話継続機能 (Conversation Continue)

**概要**:
Claude CLIの `--continue` フラグを使用した会話継続機能を追加。

**主要変更**:
- `src/backends/claude_cli_backend.py` - `--continue` フラグ対応
- `src/tabs/claude_tab.py` - 横分割レイアウト、会話継続エリア追加
- `ContinueWorkerThread` クラス追加

---

### v3.3.0 (2026-01-25) - App Manager機能強化 (アイコン変更・名前変更のEXE対応)

**概要**:
App ManagerタブのUI操作で選択したアイコンがEXEファイルに反映されるよう改善。

**主要変更**:
- `src/tabs/app_manager_tab.py` - アイコン変更・名前変更機能強化
- `src/main_window.py` - ウィンドウアイコン設定メソッド追加
- `HelixAIStudio.spec` - icon=パラメータ追加

---

### v3.2.0 (2026-01-25) - Claude Max/Proプラン CLI Backend 完全対応

**概要**:
認証モードCLI (Max/Proプラン)選択時に直接CLIBackendを使用するよう修正。

**主要変更**:
- `src/tabs/claude_tab.py` - CLIWorkerThread追加、CLIモード分岐実装
- `src/utils/constants.py` - バージョン 3.2.0

---

### v3.1.0 (2026-01-25) - チャット履歴管理 & 引用機能追加 + バグ修正

**概要**:
統合チャット履歴管理システムと履歴引用機能を追加。履歴保存ロジックも強化。

**主要変更**:
- `src/data/chat_history_manager.py` - 新規作成
- `src/ui/components/history_citation_widget.py` - 新規作成
- `src/tabs/claude_tab.py` - 履歴保存・引用ボタン追加、ai_source動的判定

---

### v3.0.0 (2026-01-25) - Trinity AI タブ追加 & Ollama連携強化

**概要**:
TrinityExoskeletonの3段階リレー処理をGUI上で直接操作できる「Trinity AI」タブを追加。

**主要変更**:
- `src/tabs/trinity_ai_tab.py` - 新規作成
- 5タブ構成に更新（Claude Code, Gemini Designer, App Manager, Cortex, Trinity AI）

---

### v2.1.0 (2026-01-22) - Phase E: TrinityExoskeleton連携強化 + UI総合化

**概要**:
Trinity Dashboard による ModelRepository / LocalLLMManager / HybridRouter の統合可視化、
Designer連携（UI図からSuggestionへ）、Workflow自動設定機能を実装。

**新規ファイル**:
- `src/tabs/trinity_dashboard_tab.py`: TrinityDashboardTab

**修正ファイル**:
- `src/tabs/settings_cortex_tab.py`: 「🔺 Trinity Dashboard」タブを追加
- `src/tabs/screenshot_capturer.py`: Trinity Dashboard タブ対応追加（計12サブタブ）
- `src/utils/constants.py`: APP_VERSION を 2.1.0 に更新

**機能詳細**:
- ModelRepository 統計表示（登録モデル数、Cloud/Local比率）
- LocalLLMManager 状態監視（State、VRAM使用量）
- HybridRouter ルーティング統計（戦略、選択率）
- ルーティング戦略のリアルタイム切り替え（5種類）
- 最近のルーティング決定履歴表示（色分け）
- Designer連携: スクリーンショット→UI改善Suggestion生成
- Workflow自動設定: Mother AI連携

**受け入れ条件達成**:
- ✅ Trinity側にModelRepository/LocalLLMManager Routerを差分表示
- ✅ スクリーンショット機能を全タブ対象に確定（15画面対応）
- ✅ Designer連携（UI図からSuggestionへ）
- ✅ タスク/Workflow自動設定

---

### v2.0.0 (2026-01-22) - Phase 4.0: Intelligent AI Orchestration & RAG-Based Knowledge Pipeline

**概要**:
Local/Cloud ハイブリッドルーティング、RAG ベースの知識パイプライン、
3分割 AI オーケストレーション（Mother AI）を実装した大型アップデート。

**新規ファイル**:
- `src/backends/model_repository.py`: ModelRepository, ModelMetadata, ModelDomain, ModelSource
- `src/routing/hybrid_router.py`: HybridRouter, RoutingStrategy, RoutingContext, RoutingDecision
- `src/helix_core/feedback_collector.py`: FeedbackCollector, FeedbackRating, QAEntry, FeedbackStats
- `src/helix_core/vector_store.py`: SimpleVectorStore, VectorDocument, SearchResult
- `src/helix_core/rag_pipeline.py`: RAGPipeline, RAGContext, IndexingStats
- `src/helix_core/mother_ai.py`: MotherAIController, AIRole, TaskStatus, AITask, WorkflowStep, SystemRecommendation
- `src/tabs/knowledge_dashboard_tab.py`: KnowledgeDashboardTab, IndexingWorker

**修正ファイル**:
- `src/helix_core/__init__.py`: Phase C/D モジュールをエクスポート追加
- `src/backends/__init__.py`: ModelRepository をエクスポート追加
- `src/routing/__init__.py`: HybridRouter をエクスポート追加
- `src/tabs/settings_cortex_tab.py`: 「📚 Knowledge」タブを追加
- `src/tabs/screenshot_capturer.py`: Thermal/Knowledge タブ対応追加（計11サブタブ）
- `src/utils/constants.py`: APP_VERSION を 2.0.0 に更新

**受け入れ条件達成**:
- ✅ ModelRepository: ドメイン別モデル管理、バージョン/メタデータ保存
- ✅ HybridRouter: 5種類のルーティング戦略、フォールバックチェーン
- ✅ FeedbackCollector: Q/A ペアの構造化保存、評価記録
- ✅ VectorStore: 埋め込み生成、類似検索
- ✅ RAGPipeline: コンテキスト自動注入、定期インデクシング
- ✅ MotherAI: 3分割AI協調、ワークフロー管理、最適化提案
- ✅ Knowledge Dashboard: 統合UI、インデクシング操作、統計表示
- ✅ スクリーンキャプチャ: Thermal/Knowledge タブ対応（計13画面）

---

### v1.9.0 (2026-01-22) - Phase 3.5: Local LLM 最適制御 & Thermal Policy

**概要**:
Local LLM の VRAM 非常駐構造と Thermal Policy による温度制御を実装。
高温時の自動スロットル/アンロードでハードウェアを保護。

**新規ファイル**:
- `src/backends/local_llm_manager.py`:
  - LocalLLMManager: VRAM非常駐のLLM管理
  - LLMState: Idle/Loading/Active/Throttled/Unloading/Error
  - LLMManagerConfig: idle_timeout, auto_unload設定
  - get_llm_manager(): グローバルインスタンス取得
- `src/backends/thermal_monitor.py`:
  - ThermalMonitor: GPU/CPU温度監視
  - nvidia-smi/psutil による温度取得
  - ThermalReading, ThermalThresholds, ThermalStatus
  - get_thermal_monitor(): グローバルインスタンス取得
- `src/backends/thermal_policy.py`:
  - ThermalPolicyController: 温度ベースの状態機械
  - ThermalPolicyState: Normal/WarningTemp/StopTemp/Throttle/CoolingWait
  - ThermalPolicyConfig: 閾値設定
  - get_thermal_policy(): グローバルインスタンス取得
- `src/backends/cloud_adapter.py`:
  - CloudAdapter: Local/Cloud切り替え
  - BackendType, SelectionReason, CostEstimate, BackendSelection
  - フォールバック連鎖、コスト見積もり、予算チェック
  - get_cloud_adapter(): グローバルインスタンス取得

**修正ファイル**:
- `src/backends/__init__.py`: Phase 3.5 モジュールをエクスポート追加
- `src/tabs/settings_cortex_tab.py`:
  - 「🌡️ Thermal管理」タブを追加
  - Local LLM Mode設定（常駐/オンデマンド/手動）
  - 温度閾値設定UI（GPU/CPU Warning/Stop）
  - リアルタイム温度表示（プログレスバー）
  - ファン制御推奨表示とコピー機能
  - 監視開始/停止ボタン
- `src/utils/diagnostics.py`:
  - Phase 3.5関連ログファイルを診断ZIPに追加
  - 設定ファイル（llm_manager_config.json等）も同梱
- `src/utils/constants.py`: APP_VERSION を 1.9.0 に更新

**ログファイル追加**:
- `logs/local_llm_manager.log`: LLMManager操作ログ
- `logs/llm_state_transitions.jsonl`: 状態遷移記録
- `logs/thermal_monitor.log`: 温度監視ログ
- `logs/thermal_readings.jsonl`: 温度読み取り記録
- `logs/thermal_policy.log`: ポリシー操作ログ
- `logs/thermal_policy_events.jsonl`: ポリシー状態遷移記録
- `logs/cloud_adapter.log`: CloudAdapter操作ログ

**設定ファイル追加**:
- `data/llm_manager_config.json`: LLMManager設定
- `data/thermal_config.json`: ThermalMonitor設定
- `data/thermal_policy_config.json`: ThermalPolicy設定

**受け入れ条件達成**:
- ✅ LocalLLMManager: Idle時はVRAMロードなし、Request時にActive移行
- ✅ ThermalMonitor: GPU/CPU温度をUIで表示、logに残る
- ✅ ThermalPolicy: 閾値超過時にスロットル/アンロード
- ✅ CloudAdapter: routing_decisions.jsonlに選択理由記録
- ✅ Fan推奨: UIから提案内容がコピー可能
- ✅ Cortex Thermal管理タブ: 全設定がUIから反映される

---

### v1.8.2 (2026-01-22) - Cortex内全サブタブスクリーンキャプチャ対応

**概要**:
v1.8.1のスクリーンキャプチャ機能を拡張し、Cortexタブ内の全9サブタブを
個別にキャプチャできるよう改良。より詳細なUI記録が可能に。

**修正ファイル**:
- `src/tabs/screenshot_capturer.py`:
  - `cortex_subtab_mapping` 追加（9サブタブのマッピング定義）
  - `_capture_cortex_subtabs()` メソッド追加（Cortex内サブタブ個別キャプチャ）
  - `_find_child_tab_widget()` メソッド追加（ネストされたQTabWidget探索）
  - `capture_all_tabs()` を修正（Cortexはサブタブ個別でキャプチャ）
  - `_log_to_routing_decisions()` 更新（サブタブ情報も記録）
- `src/tabs/settings_cortex_tab.py`:
  - スクリーンキャプチャセクションの説明文を更新（サブタブ対応を明記）
  - ツールチップを詳細化
- `src/utils/constants.py`: APP_VERSION を 1.8.2 に更新

**機能詳細**:
- **キャプチャ対象**:
  - メインタブ（3タブ）: Claude Code, Gemini Designer, App Manager
  - Cortexサブタブ（9タブ）: 一般設定, AIモデル設定, MCPサーバー管理,
    MCPポリシー, ローカル記憶, ルーティングログ, 監査ビュー, 予算管理, Local接続
- **保存先**: `data/Screenshots/{プロジェクト名}/`
  - メインタブ: 各タブフォルダ直下
  - Cortexサブタブ: `Cortex/Cortex_{サブタブ名}_{タイムスタンプ}.png`
- **ファイル名**: `Cortex_{General|AIModels|MCPServer|...}_{YYYYMMDD_HHMMSS}.png`
- **ZIP構造**: フォルダ階層を維持したZIPファイル

**技術詳細**:
- PyQt6 `QTabWidget.widget(index)` でサブタブウィジェットを取得
- `_find_child_tab_widget()` で再帰的にネストされたQTabWidgetを探索
- サブタブ切り替え後に150msの待機時間で描画安定化
- フォールバック: サブタブが見つからない場合はCortex全体をキャプチャ

**受け入れ条件達成**:
- ✅ Cortex内全9サブタブを個別にキャプチャ
- ✅ メインタブ3つ + Cortexサブタブ9つ = 計12画面をキャプチャ
- ✅ ZIPにフォルダ構造を維持して格納
- ✅ routing_decisions.jsonl にサブタブ情報も記録
- ✅ 既存UIレイアウトに影響なし

**動作確認済み**:
- ビルド成功: `HelixAIStudio.exe` (37.44MB)
- 構文チェック: 全修正ファイルでエラーなし

---

### v1.8.1 (2026-01-22) - 全UI画面スクリーンキャプチャ機能

**概要**:
Cortex設定画面の一般設定タブに、全主要タブを一括キャプチャする機能を追加。
スクリーンショットはプロジェクト単位でフォルダ分けされ、ZIP化される。

**新規ファイル**:
- `src/tabs/screenshot_capturer.py`: ScreenshotCaptureThreadクラス

**修正ファイル**:
- `src/tabs/settings_cortex_tab.py`:
  - 「スクリーンキャプチャ」セクション追加
  - `_on_capture_all_tabs()`, `_on_capture_progress()`, `_on_capture_completed()` メソッド追加
- `src/utils/constants.py`: APP_VERSION を 1.8.1 に更新

**機能詳細**:
- **保存先**: `data/Screenshots/{プロジェクト名}/{タブ名}/`
- **サブフォルダ**: ClaudeCode/, GeminiDesigner/, AppManager/, Cortex/
- **ファイル名**: `{タブ名}_{YYYYMMDD_HHMMSS}.png`
- **ZIP**: `AllTabs_{YYYYMMDD_HHMMSS}.zip`
- **ログ**: `logs/screenshot_app.log` (INFO), `logs/routing_decisions.jsonl` (reason_code="all_ui_screenshot")

**UI仕様**:
- ボタン: "📸 全 UI 画面をキャプチャして保存"
- 処理中は無効化、進捗表示
- 完了時にダイアログ通知

**受け入れ条件達成**:
- ✅ 各主要タブを1回ずつ確実に取得しPNGで保存
- ✅ ZIPが正常生成される
- ✅ data/Screenshots/ からアクセス可能
- ✅ routing_decisions.jsonl にイベントが残る
- ✅ 既存UIレイアウトを壊さない
- ✅ エラー時はUIにメッセージ表示、ログに記録

---

### v1.7.0 (2026-01-22) - Phase 2.x 統合完了: RoutingExecutor & CP1-CP10

**概要**:
Phase 2.xの中核機能（CP1〜CP10）を統合した送信実行レイヤーを完成。
全ての送信がRoutingExecutorを経由するようになり、タスク分類→バックエンド選択→予算チェック→ポリシー確認→フォールバック→メトリクス記録が自動化された。

**新規ファイル**:
- `src/backends/registry.py`: BackendRegistry（全バックエンドインスタンスの管理）
- `src/routing/routing_executor.py`: RoutingExecutor（CP1-CP10統合送信エントリーポイント）

**修正ファイル**:
- `src/backends/__init__.py`: BackendRegistry, get_backend_registryをエクスポート追加
- `src/routing/__init__.py`: RoutingExecutor, get_routing_executor, ModelPreset関連をエクスポート追加
- `src/routing/router.py`: TaskType参照の修正（.value → .name）
- `src/tabs/claude_tab.py`:
  - RoutingExecutorThreadクラス追加（CP1-CP10統合スレッド）
  - `_send_message`をRoutingExecutor使用に変更
  - `_on_executor_response`ハンドラ追加（予算超過、ポリシーブロック対応）
- `src/tabs/settings_cortex_tab.py`:
  - LocalConnectorのインスタンス取得と初期化
  - `_load_local_connector_settings`メソッド追加
  - `_save_local_settings`をLocalConnector.save_config使用に変更
  - `_check_local_health`をLocalConnector.healthcheck使用に変更

**統合機能（CP1-CP10）**:
| CP | 機能 | 状態 |
|------|------|------|
| CP1 | Backend抽象化 | ✅ BackendRegistry作成 |
| CP2 | Task分類器 | ✅ RoutingExecutor統合 |
| CP3 | Router（自動ルーティング） | ✅ 承認スナップショット参照 |
| CP4 | Cost & Time メトリクス | ✅ usage_metrics.jsonl出力 |
| CP5 | Fallback制御 | ✅ Local→Sonnet→Opus連鎖 |
| CP6 | Routing Decision Log | ✅ 決定ログ自動記録 |
| CP7 | Project別ModelPreset | ✅ economy/quality/balanced |
| CP8 | 予算サーキットブレーカー | ✅ session/daily予算 |
| CP9 | Prompt Pack | ✅ Backend別自動注入 |
| CP10 | Local接続受け口 | ✅ healthcheck/設定保存 |

**アーキテクチャ改善**:
```
User Input → ClaudeTab
             ↓
         RoutingExecutor
             ├─ CP8: 予算チェック
             ├─ CP2: タスク分類
             ├─ CP3/CP7: バックエンド選択（Preset適用）
             ├─ CP6: 決定ログ作成
             ├─ CP3: ポリシーチェック
             ├─ CP9: Prompt Pack注入
             └─ CP5: フォールバック付き実行
                  ├─ CP4: メトリクス記録
                  └─ CP8: コスト記録
             ↓
         Response to UI
```

**動作確認済み**:
- ビルド成功: `HelixAIStudio.exe` (39.2MB)
- 構文チェック: 全新規ファイルでエラーなし

---

### v1.6.2 (2026-01-21) - PROJECT_BIBLE整合性修正（ロードマップPhase番号明確化）

**背景**:
- ロードマップのPhase番号が「概念フェーズ」と「実装フェーズ」で二重化しており、AIが誤認するリスクがあった
- Trinity/Local LLMの実装状態が曖昧で「フル稼働中」と誤解される可能性があった
- Phase 2.x（抽象化・ルーティング）の入口が明文化されておらず、設計が散らばるリスクがあった

**修正内容**:
1. **ロードマップ冒頭にフェーズ番号の区別を追記**:
   - 概念フェーズ（Phase 1〜6）: 機能カテゴリ別マイルストーン
   - 実装フェーズ（Phase 1.x〜3.x）: 実際の開発進捗
   - 対応表を追加してバージョンとの紐付けを明確化

2. **Trinity/Local LLMの実装状態を明記**:
   - 技術スタック表に「接続I/F設計済・実接続はPhase 3.x予定」を追記
   - AIが「Local LLMがフル稼働中」と誤解することを防止

3. **実装フェーズ Phase 2.x / 3.x セクションを新設**:
   - Phase 2.x: 抽象化・ルーティング・コスト制御（v1.7.x〜）
     - BackendRouter、Project別ModelPreset、Budget Circuit Breaker、Fallback戦略
   - Phase 3.x: Local/Trinity完全統合（v2.0.x〜）
     - Local Backend接続、Healthcheck、Trinity統合、Hybrid推論
   - 既存の基盤ファイル一覧を記載し、次フェーズの開始点を明確化

**効果**:
- AIがPhase番号を正しく解釈し、「実装済みの機能を再設計」するリスクを排除
- 次フェーズの指示時に設計が散らばることを防止
- 新規AIがプロジェクトに参加した際の理解速度が向上

---

### v1.6.1 (2026-01-21) - SessionManager API欠落による送信準備エラー修正

**現象**:
- Claudeタブでメッセージ送信時に「送信準備エラー」が発生
- エラー内容: `AttributeError: 'SessionManager' object has no attribute 'get_current_session_id'`
- 送信前の状態確認処理で呼び出されるAPIが未実装だったことが原因

**修正内容**:
- **`src/data/session_manager.py` 修正**:
  - `get_current_session_id()` メソッドを追加（外部API）
    - 常に有効なセッションIDを返すことを保証
    - メソッド呼び出しで自動的にセッションIDを生成または復元
  - `ensure_current_session()` メソッドを実装（内部処理）
    - メモリ上のセッションIDを優先的に使用
    - session_state.jsonからの復元機能
    - 存在しない場合はuuid4で新規生成
  - `_load_session_id_from_file()` プライベートメソッド追加
    - session_state.jsonからcurrent_session_idを読み込み
  - `_save_session_id_to_file()` プライベートメソッド追加
    - session_state.jsonにcurrent_session_idを保存
  - インスタンス変数 `current_session_id` を追加
    - セッションIDをメモリ上に保持
  - import文に `uuid` を追加

**session_state.json構造拡張**:
```json
{
  "current_session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "active_project_id": "project_name",
  "active_profile_id": "normal-dev"
}
```

**動作フロー**:
1. Claudeタブで送信ボタン押下
2. 送信前処理で `session_manager.get_current_session_id()` を呼び出し
3. `ensure_current_session()` が実行される:
   - メモリにセッションIDがあればそれを返す
   - なければsession_state.jsonから復元
   - それもなければuuid4で新規生成してファイル保存
4. 有効なセッションIDが返され、送信処理が続行

**受け入れ条件達成**:
- ✅ SessionManagerに `get_current_session_id()` メソッドが存在
- ✅ Claudeタブ送信時に「送信準備エラー」が発生しない
- ✅ セッションIDがsession_state.jsonに永続化される
- ✅ 既存のsession保存/履歴機能に影響なし（互換性担保）

**テスト手順**:
1. アプリ起動→Claudeタブでメッセージ送信
2. エラーダイアログが表示されないことを確認
3. logs/session_manager.log に「Session ID generated」または「Session ID loaded」が記録されることを確認
4. data/session_state.json に `current_session_id` が保存されることを確認

---

### v1.6.0 (2026-01-21) - Phase 1.3: MCPツール単位ポリシー + 監査ビュー + プロジェクト別承認
- **MCPツール単位ポリシー（MCPToolPolicy）**:
  - `src/security/mcp_policy.py` 新規作成: 各MCPツールにrequired_scopesと制約を定義
    - 初期ポリシー15種類実装（filesystem系5, git系6, network系4）
    - allowed_paths, max_files_touched, allow_outside_projectなどの制約
  - `src/mcp/mcp_executor.py` 新規作成: MCP実行直前ガード
    - check_execution_permission(): 統一チェック入口
    - ポリシー遵守チェック + 承認スコープチェック
    - 監査ログ記録（executed/blocked）
    - MCPAuditLogger: logs/mcp_audit.logにJSONL形式で記録

- **プロジェクト別デフォルト承認（ApprovalProfile）**:
  - `src/security/project_approval_profiles.py` 新規作成: プロジェクト単位の承認セット管理
    - デフォルト4プロファイル実装:
      - read-only: 読み取り専用（安全）
      - normal-dev: 通常開発（標準）
      - risky: 全権限許可（危険）
      - custom: カスタマイズ可能
    - プロジェクトごとに専用プロファイル作成可能
    - data/project_profiles.jsonに保存
  - `src/data/project_manager.py` 新規作成: プロジェクトID管理
    - 現在のプロジェクト情報を保持
    - data/current_project.jsonに保存
  - session_manager.py拡張:
    - save_project_session(), load_project_session()追加
    - active_project_id, active_profile_idをsession_state.jsonに保存

- **監査ビューUI**:
  - `src/tabs/cortex_audit_tab.py` 新規作成: MCP監査ログ閲覧UI
    - 表示項目: timestamp, tool_name, action, project_id, reason/files
    - フィルタ機能: action（executed/blocked）, tool名, project ID
    - 詳細表示: ダブルクリックで全情報表示
    - 直近100件表示（閲覧専用）
    - アクションに応じた色分け（executed=緑、blocked=赤）

- **診断連動拡張**:
  - diagnostics.py修正: 診断ZIPに追加
    - data/project_profiles.json
    - data/mcp_policies.json
    - data/current_project.json
    - logs/mcp_audit.log（既存）

- **MCP実行ガード入口関数**:
  - MCPExecutor.check_execution_permission(): 統一チェック入口（最重要）
  - MCPExecutor.execute_filesystem_read()
  - MCPExecutor.execute_filesystem_write()
  - MCPExecutor.execute_filesystem_delete()
  - MCPExecutor.execute_git_command()
  - MCPExecutor.execute_network_request()

- **定義済みMCPToolPolicy一覧（15種類）**:
  - filesystem.read: [FS_READ]
  - filesystem.write: [FS_WRITE], max_files=5
  - filesystem.delete: [FS_DELETE, FS_WRITE], max_files=3
  - filesystem.list: [FS_READ]
  - filesystem.move: [FS_WRITE], max_files=5
  - git.read_status: [GIT_READ]
  - git.diff: [GIT_READ]
  - git.log: [GIT_READ]
  - git.commit: [GIT_WRITE]
  - git.push: [GIT_WRITE]
  - git.checkout: [GIT_WRITE]
  - browser.search: [NETWORK], allow_outside_project=True
  - brave.search: [NETWORK], allow_outside_project=True
  - fetch.url: [NETWORK], allow_outside_project=True
  - slack.post: [NETWORK], allow_outside_project=True

- **受け入れ条件達成**:
  - ✅ MCPツールごとにrequired_scopesが設定されている
  - ✅ 承認されていないscopeのツール実行は必ず拒否される
  - ✅ プロジェクト選択でDefault Profileが自動適用可能
  - ✅ MCP実行履歴/拒否履歴がCortexの監査ビューで確認できる
  - ✅ 診断ZIPにプロジェクト/プロファイル/監査ログが含まれる

### v1.5.0 (2026-01-21) - Phase 1.2: Risk Gate強化 + Diff危険度算出 + 診断連動
- **Risk Gate強化（チェックリスト式承認）**:
  - `src/security/risk_gate.py` 新規作成: ApprovalScope定義（8項目）
    - FS_READ（ファイル読み取り）
    - FS_WRITE（ファイル書き込み）
    - FS_DELETE（ファイル削除）
    - GIT_READ（Gitread操作）
    - GIT_WRITE（Git書き込み操作）
    - NETWORK（外部ネットワークアクセス）
    - BULK_EDIT（大量編集）
    - OUTSIDE_PROJECT（プロジェクト外パスアクセス）
  - `src/security/approvals_store.py` 新規作成: 承認永続化と監査ログ
    - session_state.jsonにapprovalsセクション保存
    - logs/risk_audit.logにJSONL形式で監査ログ記録
  - S3承認UIを強化（claude_tab.py）:
    - チェックボックス形式で各スコープを個別に承認可能
    - 「全て承認」「全て取消」一括操作ボタン
    - 承認状態の可視化（承認済み数表示）
  - 内部二重ガード: UI + 関数レベルで承認チェック

- **Diff危険度の自動算出**:
  - `src/utils/diff_risk.py` 新規作成: DiffRiskAnalyzer実装
    - files_changed, lines_added/deleted, risk_score (0-100), risk_level (LOW/MEDIUM/HIGH)
    - センシティブファイル検出（.env, config, auth, keys, credentials等）
    - 大量編集判定（5ファイル以上 or 300行以上）
    - ファイル削除検出
    - プロジェクト外パス検出
  - `src/claude/diff_viewer.py` 新規作成: Diffプレビューダイアログ
    - 危険度サマリ表示（risk_level, risk_score, 要因リスト）
    - シンタックスハイライト（追加行=緑、削除行=赤）
    - HIGH判定時は承認必須ガード
    - 適用前にRisk Gateチェック実行

- **診断連動（Diagnostics ZIP拡張）**:
  - `src/utils/diagnostics.py` 新規作成: DiagnosticsExporter実装
    - 同梱物追加:
      - data/session_state.json（workflow + approvals + flags）
      - data/workflow_state.json
      - data/diff_risk_report.json（直近のDiffRiskReport）
      - logs/risk_audit.log（Risk Gate監査ログ）
      - logs/workflow.log, logs/app.log等の各種ログ
    - 機密情報マスク処理:
      - APIキー、トークン、パスワード、Cookie、メールアドレス等
      - 正規表現による自動検出とマスク
    - README.txtを自動生成（診断パッケージの説明）
  - session_manager.py拡張:
    - save_diff_risk_report(), load_diff_risk_report()追加
    - get_session_state_path()追加

- **受け入れ条件達成**:
  - ✅ S3にチェックリスト表示、session_state.jsonに承認内容保存
  - ✅ 承認がないscopeの操作はUI + 内部で二重ガード
  - ✅ Diffプレビューに危険度サマリ表示、HIGHなら承認必須
  - ✅ S6 ReviewテンプレにDiffRiskReport反映可能な構造
  - ✅ 診断ZIPにworkflow_state, approvals, diff_risk_report, risk_audit.log含む
  - ✅ 機密情報マスク処理実装

- **ガード入口関数**:
  - RiskGate.check_operation(): 全操作の承認チェック入口
  - RiskGate.check_file_write(): ファイル書き込みチェック
  - RiskGate.check_file_delete(): ファイル削除チェック
  - RiskGate.check_bulk_edit(): 大量編集チェック
  - RiskGate.check_git_write(): Git書き込みチェック
  - RiskGate.check_network_access(): ネットワークアクセスチェック
  - RiskGate.check_outside_project(): プロジェクト外アクセスチェック

- **Diff危険度閾値**:
  - BULK_EDIT_FILE_THRESHOLD = 5 （5ファイル以上で大量編集）
  - BULK_EDIT_LINES_THRESHOLD = 300 （300行以上で大量編集）

### v1.4.0 (2026-01-21) - Phase 1.1: 工程バー全タブ展開 + 工程テンプレ + 二重ガード
- **全タブ共通の工程バー**:
  - `src/ui/components/workflow_bar.py` を新規作成
  - 4タブすべてに工程バー（WorkflowBar）を表示
  - Claude Codeタブ: Prev/Next/Resetボタンあり（操作可能）
  - 他タブ（Gemini, App Manager, Settings）: 参照専用（ボタンなし）
  - 成果物フラグのミニ表示（Context✅, Plan❌, Approval❌, Tests❌）
- **工程テンプレ管理**:
  - `src/data/workflow_templates.py` を新規作成
  - 固定フォーマット: S1 (Context Load), S2 (Plan), S3 (Risk Gate), S6 (Review), S7 (Release)
  - S2 Plan テンプレ: [GOAL], [NON-GOALS], [TASKS], [FILES TO TOUCH], [RISKS], [DONE CRITERIA]
  - S6 Review テンプレ: [DIFF SUMMARY], [RISK CHECK], [ROLLBACK PLAN], [NEXT ACTION]
- **送信時の自動テンプレ付与**:
  - `src/claude/prompt_preprocessor.py` を新規作成
  - 工程に応じてテンプレートを自動で先頭に付与（デフォルトON）
  - テンプレ付与時はチャット画面に通知を表示
- **二重ガード（UI + 内部ロジック）**:
  - `workflow_state.py` に `can_send()` および `can_write()` メソッドを追加
  - UIガードに加え、内部ロジックでも工程違反をブロック
  - S3承認なしでの書き込み操作を内部レベルで拒否
- **履歴管理（History Manager）**:
  - `src/data/history_manager.py` を新規作成
  - 工程イベント（phase_entered, phase_blocked, approval_granted, tests_result）を記録
  - `data/workflow_history.json` に履歴を保存
- **Session/History連動**:
  - 成果物フラグ（has_context, has_plan, risk_approved等）を session_state.json に保存
  - 工程遷移、承認、ブロックイベントをHistoryManagerとWorkflowLoggerの両方に記録
- **WorkflowState全タブ配布**:
  - `main_window.py` にワークフロー状態更新シグナル（workflowStateChanged）を追加
  - 各タブにworkflow_stateとmain_windowへの参照を渡す
  - 工程変更時に全タブの工程バーが同期更新される

### v1.3.0 (2026-01-20)
- **工程状態機械（Workflow State Machine）導入**:
  - 固定8段階の工程管理システムを実装（S0〜S7）
  - S0: 依頼受領 (Intake)
  - S1: コンテキスト読込 (Context Load)
  - S2: 計画 (Plan)
  - S3: 危険判定・承認 (Risk Gate)
  - S4: 実装 (Implement)
  - S5: テスト/検証 (Verify)
  - S6: 差分レビュー (Review)
  - S7: 確定・記録 (Release)
- **工程状態の永続化**:
  - `data/workflow_state.json` に工程状態を保存
  - アプリ再起動時に前回の工程状態を復元
- **Claude Code タブに工程バーUI追加**:
  - 現在工程の表示、進捗バー、工程説明
  - Prev/Nextボタンで工程を1段階ずつ遷移（飛ばせない）
  - S3 Risk Gateで承認チェックボックスを表示
  - 工程リセットボタンで強制的にS0に戻す機能
- **送信ガード機能**:
  - S4実装工程での書き込み操作にはS3承認が必須
  - 工程に応じて送信をブロックし、適切な工程への誘導メッセージを表示
- **監査ログ機能**:
  - `logs/workflow.log` に工程遷移、承認、ブロックイベントを記録
  - 全ての状態変更を追跡可能に
- **新規ファイル**:
  - `src/data/workflow_state.py`: 工程状態機械のコア実装
  - `src/data/session_manager.py`: セッション管理とworkflow_state永続化
  - `src/data/workflow_logger.py`: 工程専用ロガー
- **定数管理**:
  - `src/utils/constants.py` にWorkflowPhase、Pathsクラスを追加

### v1.2.1 (2026-01-20)
- **Claudeタブ機能追加**:
  - 思考モード選択（Thinking Mode）を実装
  - OFF / Standard / Deep の3モードを選択可能
  - Deepモードではタイムアウト延長対応
- **設定タブ改善**:
  - AIモデル設定のラベルを「起動時のデフォルトモデル」に変更
  - 「※各タブで変更した場合はそちらが優先されます」注記を追加
  - Geminiタイムアウト設定（QSpinBox）を新規追加（デフォルト5分、最大60分）
- **MCPサーバー管理タブ改善**:
  - QSplitterを導入し、サーバーリストと詳細エリアを分割
  - 詳細エリアを拡大（比率 2:3）し、スペースをフル活用
- **定数管理の追加**:
  - `src/utils/constants.py` を新規作成
  - APP_VERSION, ThinkingMode, ClaudeModels, GeminiModels, DefaultSettings を定義
- **内部改善**:
  - main_window.pyをconstantsから定数を読み込むように修正
  - gemini_designer_tabにset_timeout/get_timeoutメソッドを追加

### v1.2.0 (2026-01-20)
- **AIモデル更新**:
  - Claude: Claude 3.5 Sonnet → Claude Sonnet 4.5 / Opus 4.5 / Haiku 4.5
  - Gemini: Gemini 2.5 Pro → Gemini 3 Pro / Gemini 3 Flash
- **MCP機能強化**:
  - MCP Tool Search機能の説明を追加（動的ツール読み込み、コンテキスト95%削減）
  - MCPサーバー追加: Slack連携、Google Drive連携
- **UI改善**:
  - 全UIコンポーネントに詳細な日本語ツールチップを実装
  - 各機能の説明を充実させ、ユーザビリティを向上
- **バグ修正**:
  - app_manager_tab.py の import os 不足を修正

### v1.1.0 (2026-01-20)
- UIの全面的な日本語化
- 4タブ構成の実装
- 基本的なツールチップの実装

---

*Last updated: 2026-01-25*
*Generated for: Helix AI Studio v3.5.0*
