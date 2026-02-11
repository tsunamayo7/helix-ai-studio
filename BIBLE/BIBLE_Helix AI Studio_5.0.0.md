# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 5.0.0
**アプリケーションバージョン**: 5.0.0 "Helix AI Studio - Claude中心型オーケストレーション・オンデマンドモデル統合・UI強化・自動ナレッジ管理"
**作成日**: 2026-02-04
**最終更新**: 2026-02-04
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v5.0.0 更新履歴 (2026-02-04)

### 主な変更点

**概要**:
v5.0.0 はメジャーアップグレード。Claudeを完全な中心に据え、ローカルLLMは特化領域の補助ツールとして活用する新アーキテクチャ:

1. **Claude完全中心型アーキテクチャ**: Claude CLIがフルオーケストレーター、ローカルLLMは補助ツール
2. **ファイル操作自動許可**: `--dangerously-skip-permissions`による完全自動実行
3. **チャットUI強化**: カーソル移動（↑開始位置/↓終了位置）、ファイル添付ドロップ対応
4. **オンデマンドモデル統合**: RTX PRO 6000の空きVRAM (~72GB) を活用した4カテゴリモデル
5. **自動ナレッジ管理**: 会話完了後の自動要約・キーワード抽出・SQLite保存
6. **ウィンドウサイズ永続化**: QSettingsによる位置・サイズ・状態の記憶

---

## 修正・追加内容詳細

| # | 要件 | 対策 | 受入条件 |
|---|------|------|---------|
| 1 | Claude中心型への完全移行 | Claude CLIをフルオーケストレーターとし、ローカルLLMはツールとして提供 | Claudeが主導してタスク実行 |
| 2 | ファイル操作の自動許可 | `--dangerously-skip-permissions`フラグを全CLI呼び出しに適用 | 許可ダイアログなしで自動実行 |
| 3 | チャットUI強化 | EnhancedChatInput実装（カーソル移動、添付ファイル対応） | ↑↓キーでカーソル移動、D&Dでファイル添付 |
| 4 | オンデマンドモデル統合 | 4カテゴリ（code/reasoning/precision_cd/general）のVRAMティア管理 | タスク難度に応じて自動選択・ロード |
| 5 | 自動ナレッジ管理 | 会話完了後に自動でトピック・キーワード・決定事項を抽出・保存 | バックグラウンドで自動処理 |
| 6 | ウィンドウサイズ永続化 | QSettingsでgeometry/windowStateを保存・復元 | 次回起動時に前回の位置・サイズを復元 |

---

## ファイル変更一覧 (v5.0.0)

| ファイル | 変更内容 |
|----------|----------|
| `src/utils/constants.py` | バージョン 4.6.0 → 5.0.0、APP_DESCRIPTION更新 |
| `src/backends/claude_executor.py` | **新規**: Claude CLI実行エンジン（ストリーミング対応） |
| `src/backends/ondemand_manager.py` | **新規**: オンデマンドモデルマネージャー（VRAMティア管理） |
| `src/widgets/__init__.py` | **新規**: UIウィジェットパッケージ |
| `src/widgets/chat_input.py` | **新規**: 強化チャット入力（カーソル移動・添付対応） |
| `src/widgets/ondemand_settings.py` | **新規**: オンデマンドモデル設定ウィジェット |
| `src/knowledge/__init__.py` | **新規**: ナレッジ管理パッケージ |
| `src/knowledge/knowledge_manager.py` | **新規**: 会話ナレッジ抽出・保存マネージャー |
| `src/knowledge/knowledge_worker.py` | **新規**: バックグラウンドナレッジ処理ワーカー |
| `src/main_window.py` | QSettings追加、ウィンドウサイズ永続化実装 |
| `src/tabs/helix_orchestrator_tab.py` | Claude中心型アーキテクチャに刷新、ナレッジ管理統合 |
| `config/ondemand_models.json` | **新規**: オンデマンドモデル設定ファイル |
| `HelixAIStudio.spec` | v5.0.0モジュールをhiddenimportsに追加 |
| `BIBLE/BIBLE_Helix AI Studio_5.0.0.md` | 本ファイル追加 |

---

## Claude中心型アーキテクチャ (v5.0.0)

### 設計思想

v5.0.0では、Claudeを完全な中心に据えた新アーキテクチャを採用:

**新アーキテクチャ (v5.0)**:
```
ユーザー入力
    ↓
Claude CLI (--dangerously-skip-permissions -p)
    ├── MCP経由でWeb検索・ファイル操作を実行
    ├── タスク難度に応じてローカルLLMをツール呼び出し
    │   ├── code: qwen3-coder:30b (コード特化)
    │   ├── reasoning: gpt-oss:120b (大規模推論)
    │   ├── precision_cd: devstral-2:123b (超高精度CD)
    │   └── general: qwen3-next:80b (次世代汎用)
    └── 結果を統合して出力
    ↓
会話完了後: 自動ナレッジ処理
    ├── nemotron-3-nano:30bで要約・キーワード抽出
    └── SQLite + ベクトルストアに保存
```

### Claude CLI実行機能

```python
def execute_claude_cli(
    prompt: str,
    model: str = "opus",
    timeout_seconds: int = 600,
    attached_files: List[str] = None,
    working_directory: str = None,
    mcp_config: str = None,
    append_system_prompt: str = None,
    enable_auto_permission: bool = True,  # ★v5.0: デフォルトTrue
) -> Dict[str, Any]:
    """
    Claude CLIを呼び出してMCPツールを実行

    - --dangerously-skip-permissions: ファイル操作自動許可
    - -p (--print): 非対話モード
    - --model: opus/sonnet/haiku選択
    - 添付ファイル対応
    """
```

### オンデマンドシステムプロンプト

Claude CLIには以下のシステムプロンプトが自動付与される:

```
あなたは複数のローカルLLMをツールとして利用できます。
タスクの難度・性質に応じて適切なモデルを選択してください:

【オンデマンドモデル】
- code (qwen3-coder:30b): コード生成・分析・リファクタリング
- reasoning (gpt-oss:120b): 複雑な推論・多段階分析
- precision_cd (devstral-2:123b): CI/CD・超高精度コード生成
- general (qwen3-next:80b): マルチモーダル・汎用タスク

【使用指針】
- 簡単なタスク: あなた自身で処理
- コード特化タスク: code モデルを呼び出し
- 複雑な推論: reasoning または precision_cd を活用
- 特殊なマルチモーダル: general を検討
```

---

## オンデマンドモデル管理 (v5.0.0)

### VRAMティア分類

| ティア | VRAM範囲 | 戦略 | 例 |
|--------|----------|------|-----|
| A | < 30GB | 常駐と共存可能 | qwen3-coder:30b (19GB) |
| B | 30-60GB | 常駐と共存可能 | qwen3-next:80b (50GB) |
| C | 60-72GB | 常駐アンロード必要 | gpt-oss:120b (65GB) |
| D | > 72GB | 常駐アンロード必須・単独実行 | devstral-2:123b (75GB) |

### OnDemandModelManager

```python
class OnDemandModelManager:
    """RTX PRO 6000のオンデマンドVRAMスロット管理"""

    async def load_and_execute(
        self,
        category: str,      # "code", "reasoning", "precision_cd", "general"
        prompt: str,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        1. VRAMティアを判定
        2. 必要に応じて常駐モデルをアンロード
        3. オンデマンドモデルをロード
        4. 推論実行
        5. 常駐モデルを再ロード
        """
```

### 設定ファイル (config/ondemand_models.json)

```json
{
    "version": "5.0.0",
    "gpu_config": {
        "gpu_name": "RTX PRO 6000",
        "total_vram_gb": 96,
        "resident_vram_gb": 24,
        "available_for_ondemand_gb": 72
    },
    "resident_model": {
        "model": "nemotron-3-nano:30b",
        "vram_gb": 24
    },
    "ondemand_models": {
        "code": {"model": "qwen3-coder:30b", "vram_gb": 19, "tier": "A"},
        "reasoning": {"model": "gpt-oss:120b", "vram_gb": 65, "tier": "C"},
        "precision_cd": {"model": "devstral-2:123b", "vram_gb": 75, "tier": "D"},
        "general": {"model": "qwen3-next:80b", "vram_gb": 50, "tier": "B"}
    }
}
```

---

## チャットUI強化 (v5.0.0)

### EnhancedChatInput

```python
class EnhancedChatInput(QTextEdit):
    """強化チャット入力ウィジェット"""

    # シグナル
    message_submitted = pyqtSignal(str)      # メッセージ送信
    files_dropped = pyqtSignal(list)          # ファイルドロップ

    # キーバインディング
    # ↑: カーソル先頭に移動 (1行目のみ)
    # ↓: カーソル末尾に移動 (最終行のみ)
    # Enter: 送信
    # Shift+Enter: 改行
```

### AttachmentBar

```python
class AttachmentBar(QWidget):
    """水平スクロール可能な添付ファイル表示バー"""

    # ファイルドロップ対応
    # 各ファイルに削除ボタン付き
    # スタイリッシュなダークテーマ
```

### ChatInputArea

```python
class ChatInputArea(QWidget):
    """チャット入力エリア（添付バー + 入力欄 + 送信ボタン）"""

    # レイアウト:
    # ┌─────────────────────────────────────┐
    # │ [添付ファイル1] [添付ファイル2] ... │
    # ├─────────────────────────────────────┤
    # │ テキスト入力エリア          [送信] │
    # └─────────────────────────────────────┘
```

---

## 自動ナレッジ管理 (v5.0.0)

### KnowledgeManager

```python
class KnowledgeManager:
    """会話ナレッジの自動抽出・保存・検索"""

    def process_conversation(self, conversation: List[Dict]) -> Dict:
        """
        1. nemotron-3-nano:30bで会話を分析
        2. JSON形式で抽出:
           - topic: 主題
           - keywords: キーワードリスト
           - decisions: 決定事項
           - code_snippets: コードスニペット
           - action_items: アクションアイテム
           - summary: 要約
        3. SQLiteに保存
        4. qwen3-embedding:4bで埋め込み生成
        """
```

### KnowledgeWorker

```python
class KnowledgeWorker(QThread):
    """会話完了後の自動ナレッジ処理ワーカー"""

    # シグナル
    progress = pyqtSignal(str)     # 進捗メッセージ
    completed = pyqtSignal(dict)   # 処理結果
    error = pyqtSignal(str)        # エラー

    # バックグラウンドで非同期実行
    # キャンセル対応
```

### データストア

```sql
-- knowledge.db
CREATE TABLE knowledge (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    topic TEXT,
    keywords TEXT,      -- JSON array
    decisions TEXT,     -- JSON array
    code_snippets TEXT, -- JSON array
    action_items TEXT,  -- JSON array
    summary TEXT,
    raw_conversation TEXT,
    embedding BLOB
);
```

---

## ウィンドウサイズ永続化 (v5.0.0)

### QSettings実装

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("HelixAIStudio", "MainWindow")
        self._restore_window_geometry()

    def _restore_window_geometry(self):
        """前回のウィンドウ状態を復元"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self._center_on_screen()

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        """終了時にウィンドウ状態を保存"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        event.accept()
```

---

## 常駐モデル構成 (v5.0.0)

### RTX PRO 6000 (96GB) — 推論メイン

| モデル | VRAM | 役割 |
|--------|------|------|
| Nemotron-3-Nano:30B | ~24GB | テキスト推論・ナレッジ抽出（常駐） |
| **空き** | **~72GB** | オンデマンドスロット（4カテゴリ） |

### RTX 5070 Ti (16GB) — Embedding + Image常駐

| モデル | VRAM | 役割 |
|--------|------|------|
| qwen3-embedding:4b | 2.5GB | RAG埋め込み・ナレッジ埋め込み（常駐） |
| ministral-3:8b | 6.0GB | 画像理解（常駐） |
| OS/ドライバ/Ollama | ~1.0GB | システム |
| KVキャッシュ余裕 | ~6.5GB | 推論時動的確保 |

---

## タブ構成 (v5.0.0)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット（自動許可デフォルトON） |
| 2 | **mixAI v5.0** | チャット / 設定 | **Claude中心型・オンデマンド統合・ナレッジ自動保存** |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## v4.6.0からの改善

- [x] ローカルLLMからClaude中心へ完全移行
- [x] ファイル操作自動許可
- [x] チャットUI強化（カーソル移動・ファイル添付）
- [x] オンデマンドモデル4カテゴリ統合
- [x] 自動ナレッジ管理
- [x] ウィンドウサイズ永続化
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] ナレッジ検索UI
- [ ] FAISS全インデックス再構築スクリプト

---

## ビルド成果物

| ファイル | パス | 説明 |
|----------|------|------|
| exe | `dist/HelixAIStudio.exe` | PyInstallerビルド出力 |
| exe (root) | `HelixAIStudio.exe` | ルートコピー |
| config | `config/ondemand_models.json` | オンデマンドモデル設定 |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_5.0.0.md` | 本ファイル |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude CLI / Claude API / Ollama
- **Database**: SQLite (ナレッジストア)
- **Embedding**: qwen3-embedding:4b
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)

---

## 今後の展望 (v5.1以降)

1. **ナレッジ検索UI**: 蓄積されたナレッジの検索・閲覧インターフェース
2. **ストリーミング応答**: Ollamaからのリアルタイム応答表示
3. **チャット履歴エクスポート**: JSON/Markdown形式での会話保存
4. **RAG本格統合**: FAISS + SQLiteによるベクトルストア強化
5. **オンデマンドモデルUI**: モデル選択・VRAM監視の詳細UI
6. **複数GPU負荷分散**: GPU割り当ての動的最適化
7. **Claude API直接統合**: Claude CLIなしでのAPI呼び出しオプション

---

## 参考文献

- BIBLE_Helix AI Studio_4.6.0.md (前バージョン)
- RTX5070Ti_Resident_Model_Verification.md (常駐モデル検証レポート)
- mixAI_Redesign_Proposal_v2.md (設計提案書)
- Anthropic Claude Documentation
- Ollama API Documentation
