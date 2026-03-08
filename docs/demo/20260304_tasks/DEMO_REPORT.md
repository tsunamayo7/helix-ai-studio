# Helix AI Studio v12.0.0 デモ撮影レポート
**撮影日**: 2026-03-04
**完了日時**: 2026-03-04 22:26:22

---

## 撮影タスク一覧

| # | タスク | モデル | 動画ファイル | サイズ | 時間 | 結果 |
|---|--------|--------|------------|--------|------|------|
| ① | mixAI CrewAI P2エンジン全動作 | CrewAI (Phase1+2) | task1_crewai_fixed.mp4 + task1_crewai_p2.mp4 | 47.3 + 99.6 MB | - | ✅ PASS |
| ② | cloudAI Claude → VirtualDesktop UIアプリ作成 | Claude Sonnet 4.6 [CLI] | task2_claude_result.mp4 | 1.6 MB | ~40s | ✅ PASS |
| ③ | localAI qwen3.5 → コード生成確認 | qwen3.5:122b (Ollama) | task3_qwen_local.mp4 | 127.3 MB | 2810s (46.8分) | ✅ PASS |
| ④ | cloudAI GPT チャット返答確認 | GPT-5.3-codex [Codex] | task4_gpt_chat.mp4 | 21.4 MB | 511.5s (8.5分) | ✅ PASS |

**全タスク完了: 4/4**

---

## タスク詳細

### ① mixAI CrewAI P2エンジン全動作確認

**目的**: CrewAI Phase1（タスク分解）→ Phase2（並列エージェント実行）のフルパイプライン動作確認

**プロンプト**: Flask REST API コード生成 + レビュー（coding/reasoning カテゴリ）

**確認内容**:
- Phase1 JSON出力（タスク分解）正常動作
- Phase2 CrewAIエンジン起動・並列実行
- 評価結果: coding 4/7 FAIL（datetime.timezone.utc バグ、201ステータス欠落、400エラーハンドラ未定義）+ retry_needed 出力
- reasoning 3/3 PASS（REST設計・セキュリティ・拡張性・エラーハンドリング全観点網羅）

**修正内容（セッション中）**:
- `mix_orchestrator.py`: `run_cwd=None` 修正（CrewAI subprocess 実行パス）
- `crewai_engine.py`: stdout/stderr パッチ適用（Phase2ハング修正）
- `_parse_phase1_output`: JSON失敗時のPhase2スキップバグ修正

**動画**: `task1_crewai_fixed.mp4` (47.3 MB) + `task1_crewai_p2.mp4` (99.6 MB)

---

### ② cloudAI Claude → VirtualDesktop UIアプリ作成確認

**目的**: Claude CLI経由でVirtual Desktop UIアプリ作成コードを生成できることを確認

**モデル**: Claude Sonnet 4.6 [CLI]

**プロンプト**: Python Tkinterを使ったシンプルなUIアプリ作成

**確認内容**:
- cloudAIタブでClaudeモデル選択
- プロンプト送信→応答受信
- コード生成レスポンス確認（CLI完了ステータス表示）

**動画**: `task2_claude_result.mp4` (1.6 MB, ~40秒)

---

### ③ localAI qwen3.5 → コード生成確認

**目的**: ローカルLLM（qwen3.5:122b）がコード生成タスクに応答できることを確認

**モデル**: qwen3.5:122b (Ollama ローカル実行)

**プロンプト**: Pythonでリストを処理する関数の実装

**確認内容**:
- localAIタブでqwen3.5:122b選択
- プロンプト送信（pywinauto `buttons[6].click_input()` で送信ボタン直接クリック）
- 応答受信（Python関数コード生成）
- **応答時間**: 約46.8分（122B大規模モデル、ローカル実行）

**技術メモ**:
- localAI の `input_field` は純粋な `QTextEdit`（キーショートカット送信不可）
- 送信ボタン `▶ 送信` は `\u25b6` 絵文字を含むため cp932 エンコード不可
- 解決: `buttons = main_win.descendants(control_type='Button')` でインデックス指定
- `buttons[6].click_input()` で正確にクリック成功

**動画**: `task3_qwen_local.mp4` (127.3 MB, 2810秒)

---

### ④ cloudAI GPT チャット返答確認

**目的**: OpenAI GPT（Codex）モデルでチャット応答できることを確認

**モデル**: GPT-5.3-codex [Codex]

**プロンプト**: 「GPTモデルとして、日本語で自己紹介をお願いします。あなたの得意なことを教えてください。」

**確認内容**:
- cloudAIタブでGPT-5.3-codex [Codex]モデル選択（ComboBox `items[1]`）
- プロンプト入力・送信（`buttons[7].click_input()` で送信ボタン直接クリック）
- GPT応答受信（Responses API ストリーミング形式）
- `llm.completed` イベント確認、ステータスバー「Codex CLI完了」表示

**技術メモ**:
- cloudAI の送信ボタン `▶ 返信` も `\u25b6` 絵文字を含む → `buttons[7].click_input()`
- pywinauto Button[7]: L=2412, T=1990, R=2542, B=2038
- GPT Responses API のストリーミングJSON形式で応答表示

**動画**: `task4_gpt_chat.mp4` (21.4 MB, 511.5秒)

---

## 技術的知見まとめ

### pywinauto ボタン操作（Helix AI Studio v12.0.0）

| ボタン | Index | Rect (L, T, R, B) | 絵文字 |
|--------|-------|---------------------|--------|
| localAI ▶ 送信 | buttons[6] | 2412, 2038, 2542, 2086 | `\u25b6` |
| cloudAI ▶ 返信 | buttons[7] | 2412, 1990, 2542, 2038 | `\u25b6` |
| cloudAI Tab | tabs[3] | 138, 34, 288, 89 | - |
| Model ComboBox | - | 306, 145, 618, 184 | - |

### 座標系の注意
- pywinauto 座標 ≠ helix_pilot スクリーンショット座標
- helix_pilot: window region (0, 34, 3837, 2125) → 1920px にリサイズ (scale=2.0099)
- click: `abs_x = win.left + x`, `abs_y = win.top + y`

### 入力フィールド送信方式
| タブ | Widget | 送信方法 |
|------|--------|----------|
| cloudAI | `ChatInputTextEdit` | Shift+Enter（enter_to_send=null時）/ ▶返信ボタン |
| localAI | 純粋な `QTextEdit` | ▶送信ボタンのみ（キーショートカット不可） |

---

## 動画ファイル一覧

```
docs/demo/20260304_tasks/
├── task1_crewai_fixed.mp4    (47.3 MB)  - mixAI CrewAI Phase1完了まで
├── task1_crewai_p2.mp4       (99.6 MB)  - mixAI CrewAI Phase2・評価結果
├── task2_claude_result.mp4    (1.6 MB)  - cloudAI Claude コード生成
├── task3_qwen_local.mp4     (127.3 MB)  - localAI qwen3.5:122b コード生成（46.8分）
├── task4_gpt_chat.mp4        (21.4 MB)  - cloudAI GPT-5.3-codex チャット
└── DEMO_REPORT.md                       - 本レポート
```

**合計**: 約 297.2 MB

---

*生成: Claude Code (claude-sonnet-4-6) — 2026-03-04*
