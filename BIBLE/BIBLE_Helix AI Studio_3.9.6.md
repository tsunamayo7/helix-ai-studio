# Helix AI Studio - Project Bible (包括的マスター設計書)

**バージョン**: 3.9.6
**アプリケーションバージョン**: 3.9.6 "Helix AI Studio - PyInstaller終了時エラー修正, API接続エラーハンドリング改善"
**作成日**: 2026-02-03
**最終更新**: 2026-02-03
**目的**: プロジェクトの全容・経緯・設計思想を1ファイルで完全に把握するための聖典

---

## v3.9.6 更新履歴 (2026-02-03)

### 主な変更点

**概要**:
v3.9.6 は以下の改善を実装:
1. PyInstaller終了時の「Failed to remove temporary directory」エラーを修正
2. mixAIタブのAPI接続エラーハンドリングを改善
3. アプリケーション終了時のクリーンアップ処理を強化

**修正・追加内容**:

| # | 問題/要望 | 対策 |
|---|----------|------|
| A | PyInstaller終了時エラー | `disable_windowed_traceback=True`を.specに追加、closeEventでワーカー終了処理を実装 |
| B | API Connection error | エラーの原因と解決方法を詳細に表示するよう改善 |
| C | アプリ終了時の残留スレッド | `atexit`と`aboutToQuit`シグナルでクリーンアップ処理を追加 |

---

## PyInstaller終了時エラー修正 (v3.9.6)

### 問題

アプリケーション終了時に以下の警告ダイアログが表示される:
```
Failed to remove temporary directory:
C:\Users\tomot\AppData\Local\Temp\_MEI229322
```

### 原因

- PyInstallerでビルドされたexeが終了時に一時ディレクトリを削除できない
- ワーカースレッドやサブプロセスがまだ実行中の可能性

### 解決策

**1. HelixAIStudio.spec の変更**

```python
exe = EXE(
    ...
    disable_windowed_traceback=True,  # v3.9.6: 警告ダイアログを非表示
    ...
)
```

**2. main_window.py の closeEvent 改善**

```python
def closeEvent(self, event):
    """ウィンドウクローズイベント (v3.9.6: 適切なクリーンアップ処理追加)"""
    # ワーカースレッドを停止
    self._cleanup_workers()

    # セッション状態を保存
    self.session_manager.save_workflow_state()

    event.accept()

def _cleanup_workers(self):
    """v3.9.6: ワーカースレッドをクリーンアップ"""
    # mixAI (LLMmix) タブのワーカーを停止
    if hasattr(self, 'llmmix_tab') and hasattr(self.llmmix_tab, 'worker'):
        worker = self.llmmix_tab.worker
        if worker and worker.isRunning():
            worker.cancel()
            worker.wait(3000)
```

**3. HelixAIStudio.py に atexit ハンドラ追加**

```python
import atexit
import gc

def cleanup_on_exit():
    """v3.9.6: アプリケーション終了時のクリーンアップ処理"""
    gc.collect()
    # 残っているスレッドを確認・終了

atexit.register(cleanup_on_exit)
app.aboutToQuit.connect(cleanup_on_exit)
```

### 参考

- [PyInstaller Issue #8866](https://github.com/pyinstaller/pyinstaller/issues/8866)
- [PyInstaller Issue #8701](https://github.com/pyinstaller/pyinstaller/issues/8701)

---

## API接続エラーハンドリング改善 (v3.9.6)

### 問題

mixAIタブでClaude APIに接続できない場合、エラーメッセージが不親切で原因が分かりにくい。

### 解決策

**helix_orchestrator_tab.py の _call_claude_api を改善**

エラータイプに応じた詳細なエラーメッセージを表示:

```python
except anthropic.APIConnectionError as e:
    raise ValueError(
        f"API Error: Connection error.\n\n"
        f"【原因】\n"
        f"・インターネット接続がオフライン\n"
        f"・Anthropic APIサーバーに到達できない\n"
        f"・プロキシ/ファイアウォール設定\n\n"
        f"【解決方法】\n"
        f"1. インターネット接続を確認する\n"
        f"2. Claude CLIモードに切り替える\n"
        f"3. Ollamaモデルを使用する"
    )

except anthropic.AuthenticationError as e:
    raise ValueError(
        f"API Error: Authentication failed.\n\n"
        f"【原因】\n"
        f"・APIキーが無効または期限切れ\n\n"
        f"【解決方法】\n"
        f"1. 一般設定タブでAPIキーを確認・更新する\n"
        f"2. https://console.anthropic.com でAPIキーを再生成"
    )
```

---

## ファイル変更一覧 (v3.9.6)

| ファイル | 変更内容 |
|----------|----------|
| `HelixAIStudio.spec` | `disable_windowed_traceback=True`に変更 |
| `HelixAIStudio.py` | `atexit`ハンドラと`cleanup_on_exit`関数を追加 |
| `src/main_window.py` | `closeEvent`と`_cleanup_workers`メソッドを追加 |
| `src/tabs/helix_orchestrator_tab.py` | API接続エラーハンドリングを改善 |
| `src/utils/constants.py` | バージョン 3.9.5 → 3.9.6 |
| `BIBLE/BIBLE_Helix AI Studio_3.9.6.md` | 本ファイル追加 |

---

## タブ構成 (v3.9.6)

### タブ構成 (4タブ)

| # | タブ名 | サブタブ | 説明 |
|---|--------|----------|------|
| 1 | soloAI | チャット / 設定 | 単一AIチャット＆設定統合 |
| 2 | mixAI | チャット / 設定 | マルチLLMオーケストレーション |
| 3 | チャット作成 | - | チャット原稿の作成・編集 |
| 4 | 一般設定 | - | アプリ全体の設定 |

---

## 認証方式×モデル×機能の対応マトリクス (v3.9.6)

| 認証方式 | モデル | 思考モード | MCPツール | mixAI対応 | 備考 |
|----------|--------|------------|-----------|-----------|------|
| CLI | Opus 4.5 | OFF/Standard/Deep | ✅ | ✅ | 全対応 |
| CLI | Sonnet 4.5 | OFF/Standard/Deep | ✅ | ✅ | 思考モード利用可能 |
| CLI | Haiku 4.5 | OFF/Standard/Deep | ✅ | ✅ | 思考モード利用可能 |
| API | Opus 4.5 | OFF/Standard/Deep | ❌ | ✅ | **v3.9.6: エラーハンドリング改善** |
| API | Sonnet 4.5 | OFF/Standard/Deep | ❌ | ✅ | **v3.9.6: エラーハンドリング改善** |
| API | Haiku 4.5 | OFF/Standard/Deep | ❌ | ✅ | **v3.9.6: エラーハンドリング改善** |
| Ollama | (設定タブ) | OFF固定 | ✅ | ✅ | プロンプトベースツール |

---

## ビルド成果物

| ファイル | パス | サイズ |
|----------|------|--------|
| exe | `dist/HelixAIStudio.exe` | 80.5 MB |
| BIBLE | `BIBLE/BIBLE_Helix AI Studio_3.9.6.md` | - |

---

## v3.9.5からの継承課題

- [x] PyInstaller終了時エラー → **v3.9.6で解決**
- [x] API接続エラーメッセージ改善 → **v3.9.6で解決**
- [ ] Claude API経由でのMCPツール統合
- [ ] Ollamaストリーミング応答対応
- [ ] チャット履歴のエクスポート機能
- [ ] Web検索ツールのAPIキー設定UI

---

## 既知の問題と回避策 (v3.9.6)

### 1. PyInstaller一時ディレクトリ警告

**状態**: 解決済み

`disable_windowed_traceback=True`により警告ダイアログは非表示になります。
一時ディレクトリの削除に失敗しても、Windowsのディスククリーンアップで自動的に削除されます。

### 2. API Connection Error

**状態**: 改善済み

エラー発生時に詳細な原因と解決方法が表示されます。
インターネット接続がない環境では、Ollamaモデルの使用を推奨します。

---

## 参考: Extended Thinking サポートモデル (2026年1月時点)

| モデル | Extended Thinking | 備考 |
|--------|------------------|------|
| Claude Opus 4.5 | ✅ | 全機能対応 |
| Claude Sonnet 4.5 | ✅ | 全機能対応 |
| Claude Haiku 4.5 | ✅ | 初のHaikuでextended thinking対応 |

---

## 技術スタック

- **Python**: 3.12+
- **GUI**: PyQt6
- **LLM**: Claude API / Claude CLI / Ollama
- **Build**: PyInstaller 6.17.0
- **Package**: Single-file EXE (onefile mode)
