# Helix AI Studio v9.6.0 "Global Ready"
## Web UI + デスクトップUI 英語切替 + README.md
## 実装設計書（Claude Code CLI用 — 5分割実行）

**作成日**: 2026-02-17
**前提**: v9.5.0 "Cross-Device Sync" 完了済み
**方針**: 共通i18n基盤を作成し、Web UI→デスクトップUIの順で段階的に翻訳適用

---

## 1. v9.6.0 の全体像

| # | 機能 | 対象 | CLI Run |
|---|------|------|---------|
| A | 共通i18n基盤（Python + React） | 両方 | Run 1 |
| B | Web UI全コンポーネント翻訳 | Web | Run 1 |
| C | README.md作成 | - | Run 1 |
| D | デスクトップ: 一般設定タブ + メインウィンドウ | Desktop | Run 2 |
| E | デスクトップ: mixAIタブ（helix_orchestrator_tab.py） | Desktop | Run 3 |
| F | デスクトップ: soloAIタブ + 情報収集タブ | Desktop | Run 4 |
| G | デスクトップ: ウィジェット + バックエンド + BIBLE更新 | Desktop | Run 5 |

### ファイル規模と分割根拠

| ファイル | 行数 | CLI Run |
|---------|------|---------|
| **Web UI（全コンポーネント）** | ~1,400行 | Run 1 |
| README.md + i18n基盤 | 新規 | Run 1 |
| settings_cortex_tab.py | ~743行 | Run 2 |
| main_window.py | ~760行 | Run 2 |
| helix_orchestrator_tab.py | ~3,277行 | Run 3 |
| claude_tab.py / claude_chat_tab.py | ~推定800行 | Run 4 |
| information_collection_tab.py | ~1,212行 | Run 4 |
| widgets/ + backends UIメッセージ | ~500行 | Run 5 |
| BIBLE更新 | - | Run 5 |

---

## 2. 共通i18n基盤設計

### 2.1 Python側: `src/utils/i18n.py` (新規)

デスクトップとWebバックエンドで共有するPython i18nモジュール。

```python
"""
Helix AI Studio — 多言語サポート (i18n)
デスクトップ（PyQt6）とWebバックエンドで共有。

使い方:
    from src.utils.i18n import t, set_language, get_language

    label.setText(t('settings.save'))
    set_language('en')
"""

import json
from pathlib import Path
from typing import Optional

_translations = {}
_current_lang = 'ja'
_i18n_dir = Path(__file__).parent.parent.parent / 'i18n'

def _load_translations():
    """翻訳ファイルを読み込み"""
    global _translations
    for lang_file in _i18n_dir.glob('*.json'):
        lang_code = lang_file.stem  # 'ja', 'en'
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                _translations[lang_code] = json.load(f)
        except Exception as e:
            print(f"[i18n] Failed to load {lang_file}: {e}")

def _resolve(obj: dict, path: str):
    """ネストされたキーを解決: 'settings.save' → 値"""
    keys = path.split('.')
    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current if isinstance(current, str) else None

def t(key: str, **params) -> str:
    """翻訳キーを解決。欠落時は日本語→キー名にフォールバック。

    Args:
        key: ドット区切りの翻訳キー (例: 'settings.claudeModel.title')
        **params: プレースホルダー置換 (例: count=3)

    Returns:
        翻訳されたテキスト
    """
    if not _translations:
        _load_translations()

    # 現在の言語 → 日本語フォールバック → キー名
    text = _resolve(_translations.get(_current_lang, {}), key)
    if text is None:
        text = _resolve(_translations.get('ja', {}), key)
    if text is None:
        return key

    # {count}, {name} 等のプレースホルダー置換
    for k, v in params.items():
        text = text.replace(f'{{{k}}}', str(v))
    return text

def set_language(lang: str):
    """言語を切り替え"""
    global _current_lang
    if lang in ('ja', 'en'):
        _current_lang = lang
        # general_settings.json に保存
        _save_language_preference(lang)

def get_language() -> str:
    """現在の言語を取得"""
    return _current_lang

def init_language():
    """起動時に言語設定を読み込み"""
    global _current_lang
    _load_translations()
    try:
        gs_path = Path('config/general_settings.json')
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
            _current_lang = gs.get('language', 'ja')
    except Exception:
        pass

def _save_language_preference(lang: str):
    """general_settings.json に言語設定を保存"""
    try:
        gs_path = Path('config/general_settings.json')
        gs = {}
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
        gs['language'] = lang
        with open(gs_path, 'w', encoding='utf-8') as f:
            json.dump(gs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[i18n] Failed to save language: {e}")
```

### 2.2 共有翻訳ファイル: `i18n/ja.json`, `i18n/en.json`

プロジェクトルートの `i18n/` ディレクトリに配置。Python（デスクトップ）とReact（Web）の両方から参照。

```
Helix AI Studio/
├── i18n/                  # ★ 共有翻訳ファイル
│   ├── ja.json            # 日本語（デフォルト）
│   └── en.json            # 英語
├── frontend/
│   └── src/
│       └── i18n/
│           └── index.js   # React用フック（i18n/*.json をimport）
```

### 2.3 翻訳ファイルのキー構造

デスクトップとWebで共通のネームスペースを使用:

```
common.*          — 共通テキスト（保存、エラー、ログイン等）
tabs.*            — タブ名
desktop.*         — デスクトップ専用テキスト
  desktop.mixAI.*           — mixAIタブ
  desktop.soloAI.*          — soloAIタブ
  desktop.settings.*        — 一般設定タブ
  desktop.information.*     — 情報収集タブ
  desktop.mainWindow.*      — メインウィンドウ
  desktop.widgets.*         — ウィジェット
web.*             — Web UI専用テキスト
  web.preLogin.*            — ログアウト後閲覧
  web.login.*               — ログイン画面
  web.chat.*                — チャット画面
  web.inputBar.*            — 入力バー
  web.fileManager.*         — ファイルマネージャー
  web.settings.*            — Web設定画面
```

### 2.4 React側: `frontend/src/i18n/index.js`

```jsx
import React, { createContext, useContext, useState, useCallback } from 'react';
// ★ プロジェクトルートの共有i18nファイルを参照
// vite.config.jsでaliasを設定するか、ビルド時にコピー
import ja from '../../../i18n/ja.json';
import en from '../../../i18n/en.json';

const translations = { ja, en };
const LanguageContext = createContext();

function resolve(obj, path) {
  return path.split('.').reduce((acc, key) => acc?.[key], obj);
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('helix_lang') || 'ja'; }
    catch { return 'ja'; }
  });

  const changeLang = useCallback((newLang) => {
    setLang(newLang);
    try { localStorage.setItem('helix_lang', newLang); } catch {}
    // サーバーにも保存（デスクトップと同期）
    fetch('/api/settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('helix_token')}`,
      },
      body: JSON.stringify({ language: newLang }),
    }).catch(() => {});
  }, []);

  const t = useCallback((key, params = {}) => {
    let text = resolve(translations[lang], key);
    if (text === undefined || typeof text !== 'string') {
      text = resolve(translations['ja'], key);
    }
    if (text === undefined || typeof text !== 'string') return key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    });
    return text;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang: changeLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useI18n must be used within LanguageProvider');
  return ctx;
}
```

### 2.5 言語設定の同期

```
Web UI で English 選択
    ↓ localStorage + PUT /api/settings { language: 'en' }
    ↓
FastAPI → general_settings.json に保存
    ↓
Desktop PyQt6 は general_settings.json を参照
    → 次回起動時に英語で表示
    → または設定タブの言語切替で即時反映（QSignal）
```

API拡張 (`src/web/api_routes.py`): `SettingsUpdate` に `language: str | None = None` を追加。
PUT /api/settings で `general_settings.json` の `language` キーを更新。

---

## 3. CLI Run 1: Web UI i18n + README

### 対象ファイル
- **新規**: `i18n/ja.json`, `i18n/en.json`, `frontend/src/i18n/index.js`, `README.md`, `src/utils/i18n.py`
- **修正**: `frontend/src/main.jsx`, 全10フロントエンドコンポーネント, `src/web/api_routes.py`

### ja.json / en.json の作成手順

1. 全フロントエンドコンポーネント（App.jsx, LoginScreen.jsx, TabBar.jsx, ChatView.jsx, InputBar.jsx, MixAIView.jsx, ChatListPanel.jsx, FileManagerView.jsx, SettingsView.jsx, StatusIndicator.jsx）を読み込む
2. 全てのハードコード日本語文字列を抽出
3. `web.*` ネームスペースでja.jsonに格納
4. 対応する英語翻訳をen.jsonに格納
5. デスクトップ用の `desktop.*`, `common.*` キーはRun 2以降で段階的に追加

### コンポーネント翻訳ルール

- 各コンポーネント冒頭に `import { useI18n } from '../i18n';` を追加
- 関数内で `const { t, lang } = useI18n();`
- 全ハードコード日本語を `t('web.xxx.yyy')` に置換（alert/confirm含む）
- soloAI / mixAI / Claude / Ollama / RAG / Phase は翻訳しない
- 日付フォーマット: `lang === 'en' ? 'en-US' : 'ja-JP'`

### README.md

英語で記述。以下のセクション構成:
1. タイトル + 概要（Multi-model AI orchestration）
2. Key Features（3Phase, Dual Interface, Memory, RAG, Cross-Device Sync）
3. Architecture（ASCII図）
4. Hardware Requirements
5. Tech Stack
6. Quick Start（Prerequisites, Installation, Running）
7. Project Structure（ディレクトリツリー）
8. Design Philosophy
9. Version History
10. License: MIT / Author: tomlo (@tsunamayo7)

### CLI Run 1 コマンド

```powershell
claude -p "v9_6_0_Global_Ready.md のCLI Run 1を実行してください。

1. プロジェクトルートに i18n/ ディレクトリを作成
2. src/utils/i18n.py を作成（Python i18nモジュール）
3. frontend/src/i18n/index.js を作成（React LanguageProvider + useI18nフック）
4. 全フロントエンドコンポーネントを読み込み、全ハードコード日本語文字列を抽出して i18n/ja.json の web.* ネームスペースに格納。en.jsonに英語翻訳を格納。common.* は共通テキスト。
5. frontend/src/main.jsx にLanguageProviderを追加
6. 全10フロントエンドコンポーネントのハードコード日本語を t() に置換
7. SettingsViewに言語切替セクション追加、App.jsxヘッダーにEN/JPトグル追加
8. api_routes.py の SettingsUpdate に language フィールド追加
9. README.md をプロジェクトルートに作成（英語、MIT License、著者: tomlo @tsunamayo7）
10. cd frontend && npm run build

注意:
- ja.jsonに既存UIの全日本語テキストを漏れなく含めること
- 日本語モードが現在と完全同一であること
- フォールバック: en.jsonにキー欠落→ja.jsonの値を表示
- vite.config.js で i18n/ へのパスエイリアスが必要な場合は追加すること" --dangerously-skip-permissions
```

---

## 4. CLI Run 2: デスクトップ — 一般設定タブ + メインウィンドウ

### 対象ファイル（~1,500行）
- `src/tabs/settings_cortex_tab.py` (~743行) — 一般設定タブ全体
- `src/main_window.py` (~760行) — メインウィンドウ、タブ名、ステータスバー

### 翻訳方法

```python
from ..utils.i18n import t

# Before
self.save_button.setText("設定を保存")
self.statusBar().showMessage("Ready")
label = QLabel("デフォルトモデル:")

# After
self.save_button.setText(t('common.save'))
self.statusBar().showMessage(t('common.ready'))
label = QLabel(t('desktop.settings.defaultModel'))
```

### デスクトップ言語切替UI

settings_cortex_tab.py に言語切替セクションを追加:

```python
# 言語設定セクション
lang_group = QGroupBox(t('desktop.settings.language.title'))
lang_layout = QHBoxLayout()
self.lang_ja_btn = QPushButton("日本語")
self.lang_en_btn = QPushButton("English")
# ボタンクリック → set_language() → 全UIテキスト更新
```

### init_language() 呼び出し

`HelixAIStudio.py` の起動時に `init_language()` を呼び出し、general_settings.json から言語設定を読み込む。

### CLI Run 2 コマンド

```powershell
claude -p "v9_6_0_Global_Ready.md のCLI Run 2を実行してください。

対象: src/tabs/settings_cortex_tab.py と src/main_window.py

1. 両ファイルの全ハードコード日本語文字列を抽出し、i18n/ja.json の desktop.settings.* と desktop.mainWindow.* に追加。en.jsonにも英語翻訳を追加。
2. 両ファイルの日本語文字列を from src.utils.i18n import t を使って t() に置換
3. settings_cortex_tab.py に言語切替セクションを追加（日本語/English ボタン）。言語変更時は set_language() を呼び、全ラベルを retranslate するメソッドを実装。
4. HelixAIStudio.py の起動処理に init_language() 呼び出しを追加
5. main_window.py のタブ名、ステータスバーメッセージ、ウィンドウタイトルを t() に置換
6. setToolTip のテキストも翻訳対象とすること

注意:
- 既存のja.json/en.jsonを壊さないこと（desktop.* キーを追記）
- 日本語モードで既存と同一の表示であること
- retranslateUi パターン: 言語変更時に全setText/setToolTipを再適用" --dangerously-skip-permissions
```

---

## 5. CLI Run 3: デスクトップ — mixAIタブ

### 対象ファイル（~3,277行 — 最大ファイル）
- `src/tabs/helix_orchestrator_tab.py` — mixAIタブ全体

### 翻訳対象カテゴリ

| カテゴリ | 例 |
|---------|---|
| ボタンテキスト | ▶ 実行、■ キャンセル、🗑 クリア |
| ラベル | P1/P3:, メッセージを入力... |
| フェーズ名 | P1: Claude計画, P2: ローカルLLM, P3: Claude統合 |
| ツールチップ | 各ボタン・設定のsetToolTip |
| ステータス | 実行中..., 完了, エラー |
| 設定タブ | Claude設定, Ollama接続, 常駐モデル, カテゴリ別モデル, BIBLE Manager等 |

### CLI Run 3 コマンド

```powershell
claude -p "v9_6_0_Global_Ready.md のCLI Run 3を実行してください。

対象: src/tabs/helix_orchestrator_tab.py（約3,277行の大規模ファイル）

1. ファイル内の全ハードコード日本語文字列を抽出し、i18n/ja.json の desktop.mixAI.* に追加。en.jsonにも英語翻訳を追加。
2. 全日本語文字列を t() に置換
3. retranslateUi メソッドを実装（言語変更時の全テキスト再適用）
4. setToolTip テキストも翻訳対象
5. 設定サブタブ（Claude設定、Ollama接続、常駐モデル、3Phase実行設定、BIBLE Manager、VRAM Budget Simulator、GPUモニター）の全テキストを翻訳

注意:
- 既存のja.json/en.jsonのweb.*キーを壊さないこと
- フェーズ名（P1, P2, P3）やカテゴリ名（coding, research等）は技術用語として英語のまま
- QMessageBox、QInputDialog等のダイアログテキストも翻訳対象
- Neural Flow Visualizer内のテキストも翻訳対象" --dangerously-skip-permissions
```

---

## 6. CLI Run 4: デスクトップ — soloAIタブ + 情報収集タブ

### 対象ファイル（~2,000行）
- `src/tabs/claude_tab.py` — soloAIタブ
- `src/tabs/claude_chat_tab.py` — soloAIチャットサブタブ（存在する場合）
- `src/tabs/information_collection_tab.py` (~1,212行) — 情報収集タブ

### CLI Run 4 コマンド

```powershell
claude -p "v9_6_0_Global_Ready.md のCLI Run 4を実行してください。

対象:
- src/tabs/claude_tab.py（soloAIタブ）
- src/tabs/claude_chat_tab.py（存在する場合）
- src/tabs/information_collection_tab.py（情報収集タブ）

1. 各ファイルの全ハードコード日本語文字列を抽出し、i18n/ja.json の desktop.soloAI.* と desktop.information.* に追加。en.jsonにも英語翻訳を追加。
2. 全日本語文字列を t() に置換
3. retranslateUi メソッドを各クラスに実装
4. setToolTip テキストも翻訳対象
5. 情報収集タブ: RAG構築設定、実行制御、RAG統計、データ管理の全テキスト

注意:
- 既存のja.json/en.jsonを壊さないこと（desktop.*キーを追記）
- soloAIタブの認証設定、モデルテスト等のUI文字列も対象" --dangerously-skip-permissions
```

---

## 7. CLI Run 5: ウィジェット + バックエンド + BIBLE + 仕上げ

### 対象ファイル
- `src/widgets/web_lock_overlay.py` (~66行)
- `src/widgets/` 配下のその他ウィジェット
- `src/backends/mix_orchestrator.py` — UIに表示されるステータスメッセージ
- `src/backends/local_agent.py` — ツール実行ステータス
- `src/utils/constants.py` — APP_VERSION, APP_CODENAME, APP_DESCRIPTION
- `BIBLE/` — v9.6.0記載

### BIBLE更新内容

バージョン変遷サマリー:
```
| **v9.6.0** | **Global Ready** | **Web UI + デスクトップUI 英語切替（共有i18n基盤）/ README.md作成（GitHub公開用）** |
```

設計哲学追加:
```
16. **多言語UIの後方互換性** -- 共有i18nファイル（ja.json/en.json）を単一ソースとし、デスクトップ（PyQt6）とWeb（React）の両方が同一翻訳データを参照する。デフォルトは日本語、英語はオプトイン。翻訳キー欠落時は常に日本語にフォールバック（v9.6.0新設）
```

### CLI Run 5 コマンド

```powershell
claude -p "v9_6_0_Global_Ready.md のCLI Run 5を実行してください。

1. src/widgets/ 配下の全ウィジェットファイルの日本語文字列を t() に置換。ja.json/en.json の desktop.widgets.* に追加。
2. src/backends/mix_orchestrator.py と src/backends/local_agent.py のUI表示用ステータスメッセージ（emit される文字列）を t() に置換。
3. constants.py を APP_VERSION='9.6.0', APP_CODENAME='Global Ready' に更新。APP_DESCRIPTION も英語ベースに。
4. BIBLE/ の最新BIBLEをベースにv9.6.0を追記（バージョン変遷、設計哲学#16、既知の制限事項更新）。
5. i18n/ja.json と i18n/en.json の全体を確認し、欠落キーがないか検証。
6. cd frontend && npm run build

注意:
- mix_orchestrator.py の emit シグナルで送出される日本語文字列はUI表示用なので翻訳対象
- バックエンドのログメッセージ（logger.info等）は翻訳不要（英語のまま）
- BIBLE更新時、既存セクションを壊さないこと" --dangerously-skip-permissions
```

---

## 8. テスト項目チェックリスト

### Run 1後: Web UI
| # | テスト | 期待結果 |
|---|-------|---------|
| 1 | デフォルト日本語 | 初回アクセス→日本語表示（既存と同一） |
| 2 | 英語切替 | 設定→English→全Web UIテキストが英語 |
| 3 | ブラウザリロード | 言語設定がlocalStorage永続化 |
| 4 | フォールバック | en.jsonにキー欠落→日本語表示 |
| 5 | README.md | プロジェクトルートに存在、Markdownレンダリング正常 |

### Run 2後: デスクトップ基盤
| # | テスト | 期待結果 |
|---|-------|---------|
| 6 | デスクトップ起動 | 日本語UIで正常起動（既存と同一） |
| 7 | 一般設定→言語→English | 一般設定タブが英語化 |
| 8 | メインウィンドウ | タブ名、ステータスバーが英語化 |
| 9 | Web UIで英語設定→デスクトップ再起動 | デスクトップも英語で起動 |

### Run 3後: mixAIタブ
| # | テスト | 期待結果 |
|---|-------|---------|
| 10 | mixAIチャットタブ | ボタン、ラベル、ステータスが英語 |
| 11 | mixAI設定タブ | Claude設定、モデル割当等が英語 |
| 12 | mixAI実行 | フェーズ進捗メッセージが英語 |

### Run 4後: soloAI + 情報収集
| # | テスト | 期待結果 |
|---|-------|---------|
| 13 | soloAIタブ | 全テキストが英語 |
| 14 | 情報収集タブ | RAG設定、実行制御が英語 |

### Run 5後: 仕上げ
| # | テスト | 期待結果 |
|---|-------|---------|
| 15 | WebLockOverlay | 「📱 Web UIから実行中」が英語 |
| 16 | BIBLE v9.6.0 | バージョン変遷、設計哲学が更新 |
| 17 | 全体回帰: 日本語モード | 全機能が日本語モードで変わらず動作 |
| 18 | 全体回帰: 英語モード | 全機能が英語モードで正常動作 |

---

## 9. 新規/変更ファイルサマリー（全Run合計）

| 種別 | ファイル | 内容 | Run |
|------|---------|------|-----|
| **新規** | `i18n/ja.json` | 日本語翻訳（共有） | 1-5 |
| **新規** | `i18n/en.json` | 英語翻訳（共有） | 1-5 |
| **新規** | `src/utils/i18n.py` | Python i18nモジュール | 1 |
| **新規** | `frontend/src/i18n/index.js` | React i18nフック | 1 |
| **新規** | `README.md` | GitHub公開用README | 1 |
| **修正** | `frontend/src/main.jsx` | LanguageProvider | 1 |
| **修正** | Web UI 全10コンポーネント | t()置換 | 1 |
| **修正** | `src/web/api_routes.py` | language設定対応 | 1 |
| **修正** | `HelixAIStudio.py` | init_language()呼出 | 2 |
| **修正** | `src/tabs/settings_cortex_tab.py` | t()置換+言語切替UI | 2 |
| **修正** | `src/main_window.py` | t()置換 | 2 |
| **修正** | `src/tabs/helix_orchestrator_tab.py` | t()置換 | 3 |
| **修正** | `src/tabs/claude_tab.py` | t()置換 | 4 |
| **修正** | `src/tabs/information_collection_tab.py` | t()置換 | 4 |
| **修正** | `src/widgets/*.py` | t()置換 | 5 |
| **修正** | `src/backends/mix_orchestrator.py` | UIメッセージt()置換 | 5 |
| **変更** | `src/utils/constants.py` | v9.6.0 / "Global Ready" | 5 |
| **変更** | `BIBLE/` | v9.6.0記載 | 5 |
