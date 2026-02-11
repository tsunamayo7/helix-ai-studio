# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.9.3
**アプリケーションバージョン**: 3.9.3 "Helix AI Studio - mixAI本実装, Ollama MCPツール統合"
**作成日**: 2026-02-02
**最終更新**: 2026-02-02
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.9.3 更新履歴 (2026-02-02)

### 主な変更点

**概要**:
v3.9.3 は修正依頼に基づき、以下の3つの重要な改善を実装:
1. mixAI オーケストレーションのシミュレーション→本実装移行
2. soloAI Ollamaモード時のMCPツール統合（ファイル操作・Web検索）
3. Claude CLI 接続問題の調査と改善

**修正・追加内容**:

| カテゴリ | 問題/要望 | 対策 |
|----------|----------|------|
| A. mixAI本実装 | オーケストレーションがシミュレーションのまま | `OrchestratorWorker._call_llm()` を実際のLLM呼び出し（Ollama/Claude API）に置き換え |
| B. MCPツール統合 | Ollamaモードでファイル操作・Web検索ができない | `OllamaToolExecutor` クラス新規作成、プロンプトベースのツール呼び出し実装 |
| C. UI更新 | シミュレーションモード表示が残っている | 「⚠️ シミュレーションモード」→「✅ 本実装モード」に変更 |
| D. ツール実行通知 | ツール実行状況が分からない | `toolExecuted` シグナル追加、ステータスバーに実行結果表示 |

---

## mixAI 本実装 (v3.9.3)

### OrchestratorWorker._call_llm() の変更

**変更前** (v3.9.2):
```python
def _call_llm(self, role, provider, prompt, context):
    time.sleep(0.3)  # シミュレーション用遅延
    role_prompts = {...}
    return role_prompts.get(role, f"[{role.value}] 処理完了")
```

**変更後** (v3.9.3):
```python
def _call_llm(self, role, provider, prompt, context):
    # プロバイダーに応じた実際のLLM呼び出し
    if provider.value.startswith("ollama:"):
        return self._call_ollama(model, system_prompt, full_prompt)
    elif provider.value in ["claude-opus-4-5", ...]:
        return self._call_claude_api(provider.value, system_prompt, full_prompt)
    else:
        # フォールバック
        return self._call_ollama(ollama_light_model, ...)
```

### 役割別システムプロンプト

| 役割 | システムプロンプト概要 |
|------|------------------------|
| SUPERVISOR | タスク分析、目的整理 |
| ROUTER | 意図分類（コーディング/リサーチ/ドキュメント/バグ修正） |
| PLANNER | 具体的手順策定（5ステップ以内） |
| RESEARCHER | 必要情報の整理（前提条件、考慮事項） |
| EXECUTOR | タスク核心部分の実行 |
| REVIEWER | 結果検証、改善提案 |
| SUMMARIZER | 全処理結果の統合、最終回答 |

### 新規追加メソッド (helix_orchestrator_tab.py)

| メソッド | 説明 |
|----------|------|
| `_call_ollama()` | Ollama経由でLLM呼び出し |
| `_call_claude_api()` | Claude API経由でLLM呼び出し |

---

## Ollama MCPツール統合 (v3.9.3)

### OllamaToolExecutor クラス

**ファイル**: `src/mcp/ollama_tools.py`

OllamaはネイティブでMCPをサポートしていないため、プロンプトベースでツール呼び出しをシミュレート。

### サポートツール

| ツール名 | 説明 | 呼び出し形式 |
|----------|------|-------------|
| `read_file` | ファイル読み取り | `<<TOOL:read_file:path=/path/to/file>>` |
| `list_files` | ディレクトリ一覧 | `<<TOOL:list_files:path=/path/to/dir>>` |
| `web_search` | Web検索（Brave API） | `<<TOOL:web_search:query=検索クエリ>>` |

### ツール呼び出しフロー

```
1. OllamaWorkerThread起動
   ↓
2. MCP有効の場合、get_tools_system_prompt()でツール説明を取得
   ↓
3. プロンプトにツール説明を追加
   ↓
4. Ollama API呼び出し
   ↓
5. 応答から <<TOOL:...>> パターンを検出
   ↓
6. execute_tool()でツール実行
   ↓
7. 結果をツール呼び出し部分に挿入
   ↓
8. toolExecuted シグナルで通知
```

### セキュリティ制限

| 制限 | 理由 |
|------|------|
| ファイル書き込み無効 | セキュリティ保護 |
| ファイルサイズ制限 (100KB) | メモリ保護 |
| ディレクトリ一覧最大50件 | 出力サイズ制限 |
| Web検索結果最大5件 | コンテキスト節約 |

### MCP設定の取得

```python
def _get_mcp_settings(self) -> dict:
    settings = {
        "filesystem": False,
        "git": False,
        "brave-search": False,
    }
    # mcp_server_list から各サーバーの有効状態を取得
    for item in self.mcp_server_list:
        server_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        settings[server_id] = enabled
    return settings
```

---

## OllamaWorkerThread の更新 (v3.9.3)

### 新規パラメータ

| パラメータ | 型 | 説明 |
|------------|----|----|
| `mcp_enabled` | bool | MCPツール有効化 |
| `mcp_settings` | dict | MCPサーバー設定 |
| `working_dir` | str | 作業ディレクトリ |

### 新規シグナル

| シグナル | 引数 | 説明 |
|----------|------|------|
| `toolExecuted` | (str, bool) | ツール実行通知（ツール名, 成功フラグ） |

### 処理フロー

```python
# v3.9.3: MCPツール統合
if self._mcp_enabled:
    tool_executor = get_ollama_tool_executor(self._mcp_settings, self._working_dir)
    tool_prompt_addition = tool_executor.get_tools_system_prompt()

full_prompt = tool_prompt_addition + "\n\n" + self._prompt

# Ollama API呼び出し
response = client.generate(model=self._model, prompt=full_prompt)

# ツール呼び出し処理
if tool_executor:
    response_text, executed_tools = tool_executor.process_response_with_tools(response_text)
    for tool_info in executed_tools:
        self.toolExecuted.emit(tool_info["tool"], tool_info["success"])
```

---

## ファイル変更一覧 (v3.9.3)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/helix_orchestrator_tab.py` | OrchestratorWorker本実装（_call_llm, _call_ollama, _call_claude_api）、シミュレーションラベル→本実装ラベル |
| `src/tabs/claude_tab.py` | OllamaWorkerThread MCP対応、_send_via_ollama更新、_get_mcp_settings追加、_on_ollama_tool_executed追加 |
| `src/mcp/ollama_tools.py` | 新規作成: OllamaToolExecutor クラス |
| `src/utils/constants.py` | バージョン 3.9.2 → 3.9.3、APP_DESCRIPTION更新 |
| `BIBLE/BIBLE_Helix AI Studio_3.9.3.md` | 本ファイル追加 |

---

## 新規追加クラス (v3.9.3)

| クラス | ファイル | 説明 |
|--------|----------|------|
| `OllamaToolExecutor` | `src/mcp/ollama_tools.py` | Ollama用MCPツール実行 |

---

## タブ構成 (v3.9.3)

### タブ構成 (4タブ) - v3.9.2から変更なし

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | 🤖 soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | 🔀 mixAI | チャット / 設定 | マルチLLMオーケストレーション（**v3.9.3で本実装**） |
| 3 | 📝 チャット作成 | - | チャット原稿の作成・編集 |
| 4 | ⚙️ 一般設定 | - | アプリ全体の設定 |

---

## 認証方式×モデル×機能の対応マトリクス (v3.9.3 更新)

| 認証方式 | モデル | 思考モード | MCPツール | 備考 |
|----------|--------|------------|-----------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ (Claude Code) | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ (Claude Code) | 全対応 |
| CLI | Haiku 4.5 | OFF | ✅ (Claude Code) | 思考は警告 |
| API | Opus 4.5 | OFF/Standard/Deep | ❌ | API経由は独自MCP未実装 |
| API | Sonnet 4.5 | OFF/Standard/Deep | ❌ | 同上 |
| API | Haiku 4.5 | OFF/Standard/Deep | ❌ | 同上 |
| Ollama | (設定タブ) | OFF固定 | ✅ (**v3.9.3新規**) | プロンプトベースツール |

---

## ビルド成果物

| ファイル | パス |
|----------|------|
| exe | `dist/HelixAIStudio.exe` |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_3.9.3.md` |

---

## 次期バージョンへの課題

- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] mixAI でのMCPツール対応
- [ ] Web検索ツールのAPIキー設定UI

---

## 参考: Claude API モデルID (2026年1月時点)

| モデル名 | API ID | エイリアス |
|----------|--------|------------|
| Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | claude-sonnet-4-5 |
| Claude Opus 4.5 | claude-opus-4-5-20251101 | claude-opus-4-5 |
| Claude Haiku 4.5 | claude-haiku-4-5-20251001 | claude-haiku-4-5 |

参照: [Models overview - Claude API Docs](https://platform.claude.com/docs/en/about-claude/models/overview)
