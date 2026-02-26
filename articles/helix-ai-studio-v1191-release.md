---
title: "Helix AI Studio v11.9.2 リリース — カラー排除240箇所 + ターミナル表示 + Enter送信切替"
emoji: "🎨"
type: "tech"
topics: ["ai", "python", "release", "pyqt6", "cicd"]
published: true
---

## 概要

**Helix AI Studio** は、Claude / ChatGPT / Gemini / ローカルLLM を5Phaseパイプラインで統合するPyQt6デスクトップアプリです。v11.9.2 をリリースしました。

https://github.com/tsunamayo7/helix-ai-studio

## v11.9.2 変更点

### 新機能: ターミナル表示トグル

設定タブから、コンソールウィンドウの表示/非表示をリアルタイムで切り替えられるようになりました。デバッグ時にログ確認が容易になります。

- Windows API (`GetConsoleWindow` + `ShowWindow`) を使用
- `general_settings.json` に `terminal_visible` として保存

### 新機能: Enter/Shift+Enter 送信切替

チャット送信のキーバインドを選択できるようになりました:

- **ON** (デフォルト): `Enter` で送信、`Shift+Enter` で改行
- **OFF**: `Shift+Enter` で送信、`Enter` で改行

全5つの入力ウィジェット (cloudAI / localAI / mixAI / 会話継続パネル) で統一動作します。

### Color Purge: インラインカラー完全排除

17個のPythonファイルから **240箇所以上** のハードコードされた16進カラーリテラル (`#rrggbb`) を排除し、一元管理の `COLORS` 辞書参照に置換しました。

**Before:**
```python
self.chat_display.append(
    f"<div style='color: #ef4444; margin-top: 10px;'>"
    f"<b>Error:</b> {error_msg}</div>"
)
```

**After:**
```python
self.chat_display.append(
    f"<div style='color: {COLORS['error']}; margin-top: 10px;'>"
    f"<b>Error:</b> {error_msg}</div>"
)
```

**修正対象ファイル (17件):**

| ファイル | 変更箇所数 |
|---------|-----------|
| claude_tab.py | ~72 |
| neural_visualizer.py | ~15 |
| chat_history_panel.py | ~10 |
| markdown_renderer.py | ~13 |
| helix_orchestrator_tab.py | 11 |
| chat_widgets.py | 8 |
| local_ai_tab.py | 10 |
| 他10ファイル | ~40 |

**効果:**
- テーマカラー変更が `styles.py` の1箇所で完結
- Obsidianパレットの一貫性を保証
- 将来のテーマ切替 (ライトモード等) の基盤

### パイプライン自動化

Claude Codeを活用した開発→デプロイの自動化パイプラインを構築:

```
コード修正 (Edit)
  ↓
py_compile + i18n チェック (Bash)
  ↓
スクリーンショット撮影 (Python)
  ↓
デモGIF生成 (ffmpeg)
  ↓
git commit + push (gh CLI)
  ↓
PR作成 (gh pr create)
  ↓
記事投稿 (Playwright MCP → note.com)
```

### v11.9.0 からの主な修正

- **SplashScreen修正**: `showMessage` の `color=None` TypeError を修正
- **EXEアイコン**: `sys._MEIPASS` フォールバック + `AppUserModelID` 対応
- **QSSグローバル統一**: 全タブで Obsidian テーマを適用

## 今後の予定

- スクリーンショット + PC操作委任機能 (Computer Use)
- テーマ切替機能 (COLORS辞書の差し替えで実現可能に)
- Phase 2 並列実行の最適化
- Qiita クロスポスト対応

## リンク

- **GitHub**: https://github.com/tsunamayo7/helix-ai-studio
- **初心者ガイド (note)**: https://note.com/ai_tsunamayo_7/n/n410331c01ab0
- **アーキテクチャ解説 (note)**: https://note.com/ai_tsunamayo_7/n/n5a97fbf68798
- **v11.9.1リリースノート (note)**: https://note.com/ai_tsunamayo_7/n/n410888aabe47
