# Helix v8.0.0 "Living Bible" — BIBLE Manager 実装プロンプト（CLI用）

## 概要
BIBLEファイルをアプリの第一級オブジェクトにする。
ファイル添付時の自動検索、書式検証、Phase注入、自律更新を実装。

## 事前調査（必須・省略不可）
```bash
find src/ -type f -name "*.py" | sort
grep -rn "attach\|ファイルを添付\|file.*drop\|dropEvent" src/ --include="*.py"
cat src/backends/mix_orchestrator.py
cat src/backends/phase1_prompt.py
grep -rn "def.*attach\|def.*file\|def.*drop" src/tabs/ --include="*.py"
ls -la BIBLE/ 2>/dev/null
```

## 新規ファイル（8個）

### 1. src/bible/__init__.py
公開API: BibleDiscovery, BibleParser, BibleInfo, BibleInjector, BibleLifecycleManager

### 2. src/bible/bible_schema.py
- BibleSectionType(Enum): HEADER, VERSION_HISTORY, ARCHITECTURE, CHANGELOG, FILE_LIST, DIRECTORY_STRUCTURE（必須6種）+ DESIGN_PHILOSOPHY, TECH_STACK, UI_ARCHITECTURE, MIGRATION_GUIDE, TROUBLESHOOTING, ROADMAP（推奨6種）+ GPU_REQUIREMENTS, MODEL_CONFIG, BUILD_CONFIG, CUSTOM（任意4種）
- BibleSection(dataclass): type, title, content, line_start, line_end, completeness(float)
- BibleInfo(dataclass): file_path, project_name, version, codename, created_date, updated_date, sections[], raw_content, line_count
  - property version_tuple → (int, int, int)
  - property missing_required_sections → List[BibleSectionType]
  - property completeness_score → float (0.0-1.0, 必須存在率60% + 内容充実度40%)
- BIBLE_TEMPLATE: 日本語Markdownテンプレート（必須6セクション + 技術スタック + ロードマップ）
- SECTION_HEADING_MAP: Dict[BibleSectionType, List[str]] 見出しパターン正規表現

### 3. src/bible/bible_parser.py
- BibleParser.parse_header(Path) → Optional[BibleInfo]: 先頭2000文字からメタ情報抽出
- BibleParser.parse_full(Path) → Optional[BibleInfo]: 全セクション分割、completeness算出
- _detect_section_type(line) → Optional[BibleSectionType]: SECTION_HEADING_MAPで判定
- _estimate_completeness(type, content) → float: 行数ベース + コードブロック/テーブル有無ボーナス

### 4. src/bible/bible_discovery.py
BIBLE_PATTERNS = ["BIBLE_*.md", "BIBLE.md", "PROJECT_BIBLE.md", "**/BIBLE/*.md", "docs/BIBLE*.md"]
- BibleDiscovery.discover(start_path) → List[BibleInfo]:
  ファイルなら親dir取得 → カレント+子(3階層)探索 → 見つからなければ親(5階層)遡上 → バージョン降順ソート
- BibleDiscovery.discover_from_prompt(text) → List[BibleInfo]:
  正規表現でWindows/Unixパス抽出 → 各パスでdiscover() → 重複除去

### 5. src/bible/bible_injector.py
- BibleInjector.build_context(bible, mode) → str:
  mode="phase1": HEADER+ARCHITECTURE+CHANGELOG+DIRECTORY+TECH_STACK
  mode="phase3": HEADER+FILE_LIST+ARCHITECTURE
  mode="update": 全文+不足セクション情報+更新指示

### 6. src/bible/bible_lifecycle.py
- BibleAction(Enum): NONE, UPDATE_CHANGELOG, ADD_SECTIONS, CREATE_NEW, VERSION_UP
- BibleLifecycleManager.determine_action(bible, result, config) → (BibleAction, str):
  BIBLEなし+変更5個以上→CREATE_NEW / 必須不足→ADD_SECTIONS / バージョン不一致→VERSION_UP / 変更あり→UPDATE_CHANGELOG
- BibleLifecycleManager.execute_action(): Claude CLI呼び出しでBIBLE生成/更新

### 7. src/widgets/bible_panel.py
BibleStatusPanel(QWidget): Cyberpunk Minimalスタイル
- 📖 BIBLE Manager ヘッダー(#00d4ff)
- ステータス(検出=#00ff88 / 未検出=#ff8800)
- プロジェクト名・バージョン・行数
- 完全性QProgressBar(≥80%緑/≥50%黄/<50%赤)
- 不足セクション一覧
- [📝新規作成] [🔄更新] [📋詳細] ボタン
- update_bible(Optional[BibleInfo])メソッド

### 8. src/widgets/bible_notification.py
BibleNotificationWidget(QFrame): チャットエリア上部に表示
- 「📖 BIBLE検出: {name} v{version} "{codename}"」
- [コンテキストに追加] [無視] ボタン
- add_clicked / dismiss_clicked シグナル

## 既存ファイル修正

### mix_orchestrator.py
- self._bible_context: Optional[BibleInfo] = None
- set_bible_context(bible) メソッド追加
- _build_phase1_prompt()で<project_context>タグ注入
- Phase 3プロンプトでmode="phase3"注入
- _execute_pipeline()末尾にPost-Phase: BibleLifecycleManager.determine_action()
- bible_action_proposed = pyqtSignal(object, str) シグナル追加

### helix_orchestrator_tab.py
- 設定タブにBibleStatusPanelを追加（ツール設定MCPの上）
- _on_file_attached()でBibleDiscovery.discover()呼び出し
- 実行ボタンでdiscover_from_prompt()も実行
- BibleNotificationWidgetをチャットエリアに表示
- bible_action_proposedシグナルで更新確認ダイアログ表示

### constants.py
- APP_VERSION = "8.0.0"
- APP_CODENAME = "Living Bible"

### config.json
追加キー: bible_auto_discover(true), bible_auto_manage(true), bible_project_root("")

### HelixAIStudio.spec
hiddenimports追加: src.bible, src.bible.bible_schema, src.bible.bible_parser,
src.bible.bible_discovery, src.bible.bible_injector, src.bible.bible_lifecycle,
src.widgets.bible_panel, src.widgets.bible_notification

## 受入条件
```bash
# BIBLE自動検出テスト
python -c "from src.bible import BibleDiscovery; print(BibleDiscovery.discover('.'))"
# モジュール存在確認
python -c "from src.bible import BibleParser, BibleInfo, BibleInjector, BibleLifecycleManager"
# 旧バージョン残留なし
grep -rn "v7\.1\.0" src/utils/constants.py  # → v8.0.0であること
# ビルド
pyinstaller HelixAIStudio.spec --noconfirm
```
□ ファイル添付 → BIBLE自動検出 → 通知表示
□ 「コンテキストに追加」→ Phase 1に<project_context>注入
□ 設定タブにBIBLE Managerパネル表示・完全性スコア表示
□ Phase 3後にBIBLE更新提案（変更ファイルあり時）
□ 「新規作成」でテンプレートBIBLE生成
□ config.jsonで機能ON/OFF可能
□ PyInstallerビルド成功
