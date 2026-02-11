# Helix AI Studio v7.1.0 → v7.2.0 "Polish" 統合修正プロンプト

以下の全修正を実施せよ。各修正後にファイル保存し、最後にPyInstallerビルドを実行。

## 事前調査（必須）
```bash
grep -rn "v6\.2\.0\|v4\.6\|5Phase\|Phase 3.*再\|Opus 4.5\|最高品質\|最高性能" src/ --include="*.py"
```
上記の全結果を確認してから修正を開始すること。

## 修正A: constants.py
- APP_VERSION = "7.2.0", APP_CODENAME = "Polish"
- CLAUDE_MODELSリストが存在しなければ追加（Opus 4.6/4.5/Sonnet 4.5の3モデル、デフォルト=Opus 4.6）
- get_claude_model_by_id(), get_default_claude_model() ヘルパー追加

## 修正B: 旧バージョン番号除去
- "VRAM Budget Simulator (v6.2.0)" → "VRAM Budget Simulator"
- "GPUモニター (v4.6:" → "GPUモニター ("
- "5Phase" → "3Phase"（文脈に合わせて修正）
- grep結果の "Opus 4.5" ハードコード → CLAUDE_MODELSから動的取得

## 修正C: Phase 3再試行ラベル
"Phase 3 再実行設定" → "品質検証設定（ローカルLLM再実行）"
"Phase 3 再試行" → "品質再試行"

## 修正D: mix_orchestrator.py
_run_claude_cli()にmodel_idパラメータがなければ追加。
Phase 1/3でconfig.get("claude_model_id", DEFAULT_CLAUDE_MODEL_ID)を渡す。
CLIコマンドに --model {model_id} を挿入。

## 修正E: neural_visualizer.py
P4/P5ノード定義がコードに残っていれば削除（UIでは3ノードだがコード内残存の可能性）。

## 修正F: BIBLE生成
BIBLE/BIBLE_Helix AI Studio_7.2.0.md を生成。300行以上。
必須セクション: プロジェクト概要 / バージョン変遷(v1→v7.2) / 3Phaseアーキテクチャ /
CLAUDE_MODELS / UIアーキテクチャ(mixAI+soloAI+一般設定) / ローカルLLMモデル一覧 /
GPU環境要件 / デザインシステム / ディレクトリ構造 / 技術スタック / PyInstaller設定 / ロードマップ

## 修正G: GitHub公開準備
以下のファイルを生成:
- README.md（英語、バッジ付き、Features/Screenshots/Quick Start/Architecture）
- README_ja.md（日本語版）
- LICENSE（MIT）
- .gitignore（config/ dist/ *.exe __pycache__/ *.db logs/ .env node_modules/）
- requirements.txt（pip freeze相当）
- CHANGELOG.md（v6.0.0〜v7.2.0）

## 受入条件
```bash
# 全て0件であること
grep -rn "v6\.2\.0\|v4\.6" src/ --include="*.py"
grep -rn "Phase 3.*再実行\|Phase 3.*再試行" src/ --include="*.py"
# BIBLEが300行以上
wc -l "BIBLE/BIBLE_Helix AI Studio_7.2.0.md"
# README.mdが存在
test -f README.md && echo "OK"
# ビルド成功
pyinstaller HelixAIStudio.spec --noconfirm
```
