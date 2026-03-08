# Helix AI Studio v12.0.0 デモ撮影レポート（再録画版）
**撮影日**: 2026-03-05
**完了日時**: 2026-03-05 02:13
**前回との差異**: BIBLEダイアログ自動実行修正後の完全クリーン版

---

## 修正内容（前回録画からの改善点）

### BIBLEダイアログ自動実行化
**ファイル**: `src/tabs/helix_orchestrator_tab.py`

mixAI Phase3完了後に表示される「BIBLEを更新しますか？」確認ダイアログを廃止し、
自動実行に変更。ユーザー介入なしで完走するよう修正済み。

- **修正前**: `QMessageBox.question()` によるモーダルダイアログでブロック
- **修正後**: `logger.info()` のみでダイアログなし自動実行

---

## 撮影タスク一覧

| # | タスク | モデル | 動画ファイル | サイズ | 時間 | 結果 |
|---|--------|--------|------------|--------|------|------|
| ① | mixAI CrewAI P1+P2+P3全動作 | CrewAI (ministral-3:8b + gemma3:4b) | task1_mixai_crewai.mp4 | 29 MB | 645.2s (10.8分) | ✅ PASS |
| ② | cloudAI Claude → tkinter UIアプリ作成 | Claude Opus 4.6 [CLI] | task2_cloud_claude.mp4 | 8.2 MB | 198.2s (3.3分) | ✅ PASS |
| ③ | localAI qwen3.5 → コード生成確認 | qwen3.5:122b (Ollama) | task3_local_qwen.mp4 | 56 MB | 854.8s (14.2分) | ✅ PASS |
| ④ | cloudAI GPT チャット返答確認 | GPT-5.3-codex [Codex] | task4_cloud_gpt.mp4 | 11 MB | 241.5s (4.0分) | ✅ PASS |

**全タスク完了: 4/4**

---

## タスク詳細

### ① mixAI CrewAI P1+P2+P3全動作確認

**目的**: CrewAI Phase1（タスク分解）→ Phase2（並列エージェント実行）→ Phase3（統合評価）のフルパイプライン完走確認

**プロンプト**: PythonのFlaskを使ったシンプルなREST APIの設計・実装（routing, CRUD, エラーハンドリング含む）

**確認内容**:
- Phase1 JSON出力（タスク分解）正常動作
- Phase2 CrewAIエンジン起動・並列実行（ministral-3:8b + gemma3:4b）
- Phase3 統合評価: coding 7/7 PASS、reasoning 3/3 PASS、research 3/4 PASS
- BIBLEダイアログ出ずに完走（修正効果確認）

**動画**: `task1_mixai_crewai.mp4` (29 MB, 645.2秒)

---

### ② cloudAI Claude → tkinter UIアプリ作成確認

**目的**: Claude CLI経由でtkinker GUIアプリ作成コードを生成できることを確認

**モデル**: Claude Opus 4.6 [CLI]

**プロンプト**: Python tkinterを使ったシンプルなUIアプリ作成（ウィンドウ、ラベル、ボタン、メッセージボックス）

**確認内容**:
- cloudAIタブでClaudeモデル選択
- プロンプト送信→応答受信
- hello_gui.py コード生成レスポンス確認（CLI完了ステータス表示）

**技術メモ**:
- cloudAI送信: `buttons[7].click_input()` (L=2412, T=1990, R=2542, B=2038)
- 入力: クリップボード経由貼り付け（CP932エンコード問題回避）

**動画**: `task2_cloud_claude.mp4` (8.2 MB, 198.2秒)

---

### ③ localAI qwen3.5 → コード生成確認

**目的**: ローカルLLM（qwen3.5:122b）がコード生成タスクに応答できることを確認

**モデル**: qwen3.5:122b (Ollama ローカル実行)

**プロンプト**: Pythonで数値のリストを処理する関数を作成（合計、平均、最大値、最小値、ソートしたリストを返す）

**確認内容**:
- localAIタブでqwen3.5:122b選択
- プロンプト送信（`buttons[6].click_input()` で送信ボタン直接クリック）
- 応答受信（Python関数コード生成 + 実行例出力）
- **応答時間**: 約14.2分（122B大規模モデル、ローカル実行）

**技術メモ**:
- localAI の入力フィールドは純粋な `QTextEdit`（キーショートカット送信不可）
- 送信ボタン `▶ 送信` は `\u25b6` 絵文字を含むため cp932 エンコード不可
- 解決: `buttons[6].click_input()` でクリック (L=2412, T=2038, R=2542, B=2086)

**動画**: `task3_local_qwen.mp4` (56 MB, 854.8秒)

---

### ④ cloudAI GPT チャット返答確認

**目的**: OpenAI GPT（Codex）モデルでチャット応答できることを確認

**モデル**: GPT-5.3-codex [Codex]

**プロンプト**: 「GPTモデルとして、日本語で自己紹介をお願いします。あなたの得意なことを教えてください。」

**確認内容**:
- cloudAIタブでGPT-5.3-codex [Codex]モデル選択
- プロンプト入力・送信（`buttons[7].click_input()` で送信ボタン直接クリック）
- GPT応答受信（Codex Responses API ストリーミング形式）
- `llm.sum.completed` イベント確認

**技術メモ**:
- cloudAI の送信ボタン `▶ 返信` も `\u25b6` 絵文字を含む → `buttons[7].click_input()`
- pywinauto Button[7]: L=2412, T=1990, R=2542, B=2038
- GPT Responses API のストリーミングJSON形式で応答表示

**動画**: `task4_cloud_gpt.mp4` (11 MB, 241.5秒)

---

## 技術的知見まとめ

### pywinauto ボタン操作（Helix AI Studio v12.0.0）

| ボタン | Index | Rect (L, T, R, B) | 絵文字 |
|--------|-------|---------------------|--------|
| localAI ▶ 送信 | buttons[6] | 2412, 2038, 2542, 2086 | `\u25b6` |
| cloudAI ▶ 返信 | buttons[7] | 2412, 1990, 2542, 2038 | `\u25b6` |
| mixAI ▶ 実行 | buttons[6] | 2401, 2010, 2531, 2058 | `\u25b6` |

### Tab インデックス

| タブ | Index | Rect (L, T, R, B) |
|------|-------|---------------------|
| mixAI | Tab[2] | 0, 34, 138, 89 |
| cloudAI | Tab[3] | 138, 34, 288, 89 |
| localAI | Tab[4] | 288, 34, 436, 89 |

### 座標系の注意
- pywinauto 座標 ≠ helix_pilot スクリーンショット座標
- helix_pilot: window region (0, 34, 3837, 2125) → 1920px にリサイズ (scale≈2.0099)
- pywinauto: 物理ピクセル座標（DPI 150%環境 = 3840×2160）

### 入力フィールド送信方式
| タブ | Widget | 送信方法 |
|------|--------|----------|
| cloudAI | `ChatInputTextEdit` | `buttons[7].click_input()` (▶ 返信) |
| localAI | 純粋な `QTextEdit` | `buttons[6].click_input()` (▶ 送信) |
| mixAI | `QTextEdit` | `buttons[6].click_input()` (▶ 実行) |

### 2ウィンドウ問題の解決
Helix AI Studio は起動時に2つのウィンドウを持つことがある。
`ElementAmbiguousError` 回避: `Desktop(backend='uia').windows(title='Helix AI Studio v12.0.0')[0]`

---

## 動画ファイル一覧

```
docs/demo/20260305_tasks/
├── task1_mixai_crewai.mp4    (29 MB)  - mixAI CrewAI Phase1→2→3全完走
├── task2_cloud_claude.mp4    (8.2 MB) - cloudAI Claude tkinter UIアプリ作成
├── task3_local_qwen.mp4      (56 MB)  - localAI qwen3.5:122b コード生成（14.2分）
├── task4_cloud_gpt.mp4       (11 MB)  - cloudAI GPT-5.3-codex チャット
└── DEMO_REPORT.md                     - 本レポート
```

**合計**: 約 104 MB

---

*生成: Claude Code (claude-sonnet-4-6) — 2026-03-05*
