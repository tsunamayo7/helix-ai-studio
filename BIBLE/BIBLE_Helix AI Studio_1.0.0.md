# PROJECT_BIBLE.md - 統合に関する注記

**日付**: 2026-01-25
**状態**: 統合完了

---

## 統合結果

このファイル（PROJECT_BIBLE.md）の内容は `PROJECT_BIBLE_HelixAIStudio.md` に統合されました。

**マスターファイル**: `PROJECT_BIBLE_HelixAIStudio.md`

---

## 統合時の確認事項・不明点

以下の点について、両ファイル間で記述の差異がありました。
今後問題が発生した場合は、以下を参照して確認してください。

### 1. v3.1.0 の記述の差異

| ファイル | 記述内容 |
|---------|---------|
| PROJECT_BIBLE_HelixAIStudio.md | 「チャット履歴管理 & 引用機能追加」- 新機能追加の詳細記述 |
| PROJECT_BIBLE.md (旧) | 「Claudeチャット履歴保存機能の修正」- バグ修正としての記述 |

**対応**: 両方の内容を統合。v3.1.0 として新機能追加の記述を採用し、バグ修正部分は `v3.1.0-bugfix` として別セクションを追加。

### 2. v3.2.0 と v3.3.0 の欠落

PROJECT_BIBLE_HelixAIStudio.md には v3.4.0 の後、直接 v3.1.0 に移行していましたが、
PROJECT_BIBLE.md には v3.3.0 と v3.2.0 の詳細が記載されていました。

**対応**: v3.3.0（App Manager機能強化）と v3.2.0（Claude Max/Pro CLI Backend完全対応）を
PROJECT_BIBLE_HelixAIStudio.md に追加しました。

### 3. 更新履歴テーブルの相違

PROJECT_BIBLE.md にはアプリケーション概要セクション内に簡易的な修正履歴テーブルがありましたが、
PROJECT_BIBLE_HelixAIStudio.md の「12. 修正履歴」セクションには古い v2.1.0 以前の情報のみでした。

**対応**: v3.0.0〜v3.5.0 のエントリを「12. 修正履歴」セクションに追加しました。

---

## このファイルの扱い

このファイルは統合の記録として保存されています。

- 通常の開発時は `PROJECT_BIBLE_HelixAIStudio.md` のみを参照・更新してください
- このファイルは不要になったら削除しても構いません
- 問題が発生した場合の参照資料としてのみ使用してください

---

*統合実施日: 2026-01-25*
*統合元: PROJECT_BIBLE.md (v3.5.0)*
*統合先: PROJECT_BIBLE_HelixAIStudio.md (v3.5.0)*
