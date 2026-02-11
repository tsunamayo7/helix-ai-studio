# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.9.5
**アプリケーションバージョン**: 3.9.5 "Helix AI Studio - チャット作成タブ改善, 設定保存機能修正, thinking警告改善"
**作成日**: 2026-02-03
**最終更新**: 2026-02-03
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.9.5 更新履歴 (2026-02-03)

### 主な変更点

**概要**:
v3.9.5 は修正依頼に基づき、以下の改善を実装:
1. チャット作成タブの送信ボタンを「soloAI」「mixAI」に変更
2. 一般設定タブの設定保存ボタンに実際の保存処理を実装
3. soloAI thinkingモード警告の改善（エラー検出パターン拡張）
4. mixAI Claudeモデル設定エラーメッセージの改善

**修正・追加内容**:

| # | 問題/要望 | 対策 |
|---|----------|------|
| A | チャット作成タブのボタンが旧名称 | 「→ soloAI」「→ mixAI」に変更、タブインデックス修正 |
| B | 一般設定の設定保存が機能しない | `_on_save_settings`に実際のJSON保存処理を実装 |
| C | thinkingモードエラー検出が不十分 | エラーパターンを拡張（--think, unknown option等追加） |
| D | mixAI Claudeエラーメッセージが不親切 | 解決方法を含む詳細なエラーメッセージに変更 |
| E | Haiku 4.5のthinking事前警告が不正確 | Haiku/Sonnet共にextended thinking対応のため警告削除 |

---

## チャット作成タブ改善 (v3.9.5)

### 送信ボタンの変更

**変更前**:
- → Claude Code
- → Helix Orchestrator
- → Gemini Designer

**変更後**:
- → soloAI (タブインデックス0へ送信)
- → mixAI (タブインデックス1へ送信)

```python
# chat_creation_tab.py
send_solo_btn = QPushButton("→ soloAI")
send_solo_btn.setToolTip("soloAIタブのチャット入力欄にコンテンツを送信します")
send_solo_btn.clicked.connect(lambda: self._on_send_to("solo"))

send_mix_btn = QPushButton("→ mixAI")
send_mix_btn.setToolTip("mixAIタブのタスク入力欄にコンテンツを送信します")
send_mix_btn.clicked.connect(lambda: self._on_send_to("mix"))
```

### 後方互換性

旧ターゲット名（"claude", "helix"）も引き続きサポート。

---

## 設定保存機能修正 (v3.9.5)

### settings_cortex_tab.py の変更

**新規実装**: `_on_save_settings` に実際の保存処理を追加

```python
def _on_save_settings(self):
    """設定保存 (v3.9.5: 実際の保存処理を実装)"""
    # 設定ファイルパス: config/general_settings.json
    config_path = config_dir / "general_settings.json"

    # APIキーを環境変数に設定
    if api_key and not api_key.endswith("..."):
        os.environ["ANTHROPIC_API_KEY"] = api_key

    # 設定データを収集・保存
    settings_data = {
        "dark_mode": ...,
        "font_size": ...,
        "auto_save": ...,
        "auto_context": ...,
        "cli_enabled": ...,
        "knowledge_enabled": ...,
        "knowledge_path": ...,
        "encyclopedia_enabled": ...,
    }
```

---

## thinkingモード警告改善 (v3.9.5)

### 変更点

1. **Haiku 4.5事前警告の削除**
   - Web検索結果により、Haiku 4.5もextended thinkingをサポート確認
   - 事前にOFFに強制する処理を削除
   - エラー発生時の自動フォールバックに依存

2. **エラー検出パターンの拡張**

```python
# 旧パターン
thinking_errors = ["thinking", "extended thinking", "not supported", "invalid parameter"]

# 新パターン (v3.9.5)
thinking_errors = [
    "thinking", "extended thinking", "not supported", "invalid parameter",
    "--think", "think hard", "ultrathink", "unsupported flag",
    "unknown option", "unrecognized option", "invalid option"
]
```

3. **エラーメッセージの改善**
   - 「Note: Claude CLIのバージョンによっては--thinkオプションが利用できない場合があります」を追加

---

## mixAI エラーメッセージ改善 (v3.9.5)

### _call_claude_cli のエラーメッセージ

**変更前**:
```
ANTHROPIC_API_KEY が設定されておらず、Claude CLI も利用できません。
```

**変更後**:
```
Claude APIキー未設定かつCLI利用不可

【解決方法】
1. 一般設定タブでANTHROPIC_API_KEYを設定する
2. または、Claude CLIをインストールしてログインする
   npm install -g @anthropic-ai/claude-code
   claude login

詳細: {CLIチェックメッセージ}
```

---

## ファイル変更一覧 (v3.9.5)

| ファイル | 変更内容 |
|----------|----------|
| `src/tabs/chat_creation_tab.py` | 送信ボタンをsoloAI/mixAIに変更、タブインデックス修正 |
| `src/tabs/settings_cortex_tab.py` | `_on_save_settings`に実際の保存処理を実装 |
| `src/tabs/claude_tab.py` | thinking事前警告削除、エラー検出パターン拡張 |
| `src/tabs/helix_orchestrator_tab.py` | Claudeエラーメッセージ改善 |
| `src/utils/constants.py` | バージョン 3.9.4 → 3.9.5 |
| `BIBLE/BIBLE_Helix AI Studio_3.9.5.md` | 本ファイル追加 |

---

## 認証方式×モデル×機能の対応マトリクス (v3.9.5 更新)

| 認証方式 | モデル | 思考モード | MCPツール | mixAI対応 | 備考 |
|----------|--------|------------|-----------|-----------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ | ✅ | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ | ✅ | **v3.9.5: 思考モード利用可能** |
| CLI | Haiku 4.5 | OFF/Standard/Deep | ✅ | ✅ | **v3.9.5: 思考モード利用可能** |
| API | Opus 4.5 | OFF/Standard/Deep | ❌ | ✅ | API経由は独自MCP未実装 |
| API | Sonnet 4.5 | OFF/Standard/Deep | ❌ | ✅ | 同上 |
| API | Haiku 4.5 | OFF/Standard/Deep | ❌ | ✅ | 同上 |
| Ollama | (設定タブ) | OFF固定 | ✅ | ✅ | プロンプトベースツール |

**Note**: Sonnet 4.5とHaiku 4.5の両方でextended thinkingがサポートされています（Anthropic公式ドキュメント確認済み）。
CLI経由でエラーが発生した場合は自動的にOFFにフォールバックします。

---

## タブ構成 (v3.9.5)

### タブ構成 (4タブ)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | mixAI | チャット / 設定 | マルチLLMオーケストレーション |
| 3 | チャット作成 | - | チャット原稿の作成・編集 (**v3.9.5でボタン改善**) |
| 4 | 一般設定 | - | アプリ全体の設定 (**v3.9.5で保存機能修正**) |

---

## ビルド成果物

| ファイル | パス |
|----------|------|
| exe | `dist/HelixAIStudio.exe` |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_3.9.5.md` |

---

## v3.9.4からの継承課題

- [x] チャット作成タブのボタン名称修正 → **v3.9.5で解決**
- [x] 設定保存ボタン機能修正 → **v3.9.5で解決**
- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI

---

## 参考: Extended Thinking サポートモデル (2026年1月時点)

| モデル | Extended Thinking | 備考 |
|--------|------------------|------|
| Claude Opus 4.5 | ✅ | 全機能対応 |
| Claude Sonnet 4.5 | ✅ | 全機能対応 |
| Claude Haiku 4.5 | ✅ | 初のHaikuでextended thinking対応 |
| Claude Opus 4/4.1 | ✅ | 対応 |
| Claude Sonnet 4 | ✅ | 対応 |

参照: [What's new in Claude 4.5 - Claude API Docs](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-5)
