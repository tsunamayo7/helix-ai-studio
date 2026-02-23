# Helix AI Studio v11.0.0 "Smart History" - Progress

## Phase 0: 共通モジュール作成
- [x] src/widgets/no_scroll_widgets.py 新規作成 (NoScrollComboBox/SpinBox/DoubleSpinBox)
- [x] src/widgets/section_save_button.py 新規作成 (領域別保存ボタンファクトリ)
- [x] config/cloud_models.json 新規作成 (5モデル: Opus4.6/Sonnet4.6/Opus4.5/Sonnet4.5/GPT-5.3)
- [x] src/utils/chat_logger.py 新規作成 (ChatLogger JSONL記録)
- [x] src/memory/model_config.py 新規作成 (ローカルLLMモデル動的設定)
- [x] src/mixins/__init__.py 新規作成
- [x] src/mixins/bible_context_mixin.py 新規作成 (BIBLEクロスタブMixin)

## Phase 1: UI削除・簡素化 (②③⑦)
- [x] 1-A: mixAI PhaseIndicator / NeuralFlowCompactWidget 削除
- [x] 1-A: GPUUsageGraph クラス全削除 (242行)
- [x] 1-A: GPU Monitor セクション全削除 (12メソッド+UI)
- [x] 1-B: mixAI設定 BIBLE Manager UI削除 (バックエンド_current_bibleに置換)
- [x] 1-B: mixAI設定 VRAM Simulator UI削除
- [x] 1-B: mixAI設定 Search/Browse Mode combo削除
- [x] 1-B: mixAI設定 effort_combo / gpt_effort_combo 削除 (config.json隠し設定化)
- [x] 1-B: mixAI設定 engine_type_label (☁API) 削除
- [x] 1-B: mixAI設定 Ollama P1/P3モデル選択肢を無効化 (クラウドのみ)
- [x] 1-C: 一般設定 MCPサーバー管理セクション削除
- [x] 1-C: 一般設定 カスタムサーバー設定削除
- [x] 1-C: 一般設定 Memory & Knowledge 簡略化 (RAG/RiskGate/Threshold削除)
- [x] ファイル削除: vram_simulator.py, openai_compat_backend.py, custom_server.json (次セッション)
- **削除量: helix_orchestrator_tab.py ~1000行, settings_cortex_tab.py ~224行**

## Phase 2: cloudAIタブ刷新 + 継続送信ボタン (④+A8)
- [x] 2-A: effort_combo UI削除 → _get_effort_from_config() (config.json読み込み)
- [x] 2-B: モデルセレクタをチャットヘッダーに移動 [Model ▼] [Advanced] [New]
- [x] 2-B: cloud_models.json からモデル動的読み込み (_load_cloud_models_to_combo)
- [x] 2-C: 「⚙ 詳細設定」ボタン追加 (_open_claude_code_settings → ~/.claude/settings.json)
- [x] 2-D: 「📌 継続送信」ボタン追加 (_on_continue_send_main)
- [x] 2-D: _claude_session_id セッション管理
- [x] 2-D: CLIWorkerThread resume_session_id パラメータ追加
- [x] 2-D: claude_cli_backend _build_command --resume 対応
- [x] 2-D: claude_cli_backend session_id 自動キャプチャ (stderr パース)
- [x] 2-D: _on_cli_response でのセッションID自動取得 → Continue Send 有効化
- [x] MCP設定をcloudAI設定タブに分散配置 (cloudai_mcp_filesystem/git/brave)
- [x] mixAI Phase Registration セクション削除 → MCP設定に置換
- [x] i18n 日英 8キー追加 (advancedSettings, continueSendMain, mcpSettings等)

## Phase 3: Historyタブ新設 + JSONL記録 (①)
- [x] 3-A: src/utils/chat_logger.py 新規作成 (Phase 0で完了)
- [x] 3-A: cloudAI JSONL フック追加 (user/assistant両方)
- [x] 3-B: src/tabs/history_tab.py 新規作成 (Phase 0で完了)
- [x] 3-B: main_window.py タブ追加（6タブ構成: Tab 3 = History）
- [x] 3-B: retranslateUi 更新（6タブインデックス対応）
- [x] i18n 日英キー追加 (historyTab, historyTip, history.searchPlaceholder等 7キー)

## Phase 4: BIBLEクロスタブ統合 (③')
- [x] 4-A: src/mixins/bible_context_mixin.py 新規作成 (Phase 0で完了)
- [x] 4-B: cloudAI に 📖 BIBLE トグルボタン追加
- [x] 4-B: mixAI に 📖 BIBLE トグルボタン追加
- [x] 4-B: localAI に 📖 BIBLE トグルボタン追加
- [x] 4-B: cloudAI _send_message に BIBLE コンテキスト注入統合
- [x] 4-B: mixAI _on_execute に BIBLE コンテキスト注入統合
- [x] 4-B: localAI _send_message に BIBLE コンテキスト注入統合
- [x] i18n 日英キー追加 (bibleToggleTooltip)

## Phase 5: localAI MCP (Python MCP SDK) (⑤)
- [x] 5-E: localAI設定タブに MCP チェックボックス追加 (filesystem/git/brave)
- [x] 5-E: _save_localai_mcp_settings / _load_localai_mcp_settings 実装
- [x] 5-E: retranslateUi 更新
- [ ] 5-A〜D: Python MCP SDK 完全統合 (次バージョンに延期)
- [ ] 5-F: モデル能力表示の拡張 (次バージョンに延期)
- [ ] 5-G: モデル管理改善 (次バージョンに延期)
- [x] i18n 日英キー追加 (localAI.mcpSettings)

## Phase 6: RAGタブ全面刷新 (⑥)
- [x] 6-A: タブ名変更 情報収集 → RAG (main_window.py + i18n)
- [x] 6-D: src/memory/model_config.py 新規作成 (Phase 0で完了)
- [x] 6-B: チャットサブタブ cloudAI風UI (RAGChatWorkerThread + 全アクションメソッド実装済み)
- [x] 6-C: 設定サブタブ cloud_models.json連携 (Claude→Cloud モデル名称変更・i18n 22キー追加済み)
- [ ] 6-E: RAG自動強化 (LightRAG/HyPE/Reranker) (次セッションで段階的実装)

## 完了後作業
- [x] constants.py APP_VERSION="11.0.0" APP_CODENAME="Smart History" 更新
- [x] helix_source_bundle.txt 再生成 (51ファイル, 1346.7 KB)
- [x] BIBLE v11.0.0 作成 + delta patches 更新 (2026-02-24)
- [ ] CHANGELOG 更新
