"""
post_to_note.py - note.com投稿用の記事テンプレートを生成

Playwright MCPが実際のnote.com投稿操作を行う。
このスクリプトは記事本文（Markdown）の生成を担当。

Usage:
    python scripts/post_to_note.py --title "タイトル" --version "11.9.1" --changes "変更内容"
    python scripts/post_to_note.py --title "タイトル" --version "11.9.1" --output article.md
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_changelog_entry(version: str) -> str:
    """CHANGELOG.md から指定バージョンのエントリを抽出"""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        return ""

    text = changelog_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_section = False
    entry_lines = []

    for line in lines:
        if line.startswith(f"## [{version}]"):
            in_section = True
            continue
        elif line.startswith("## [") and in_section:
            break
        elif in_section:
            entry_lines.append(line)

    return "\n".join(entry_lines).strip()


def load_app_info() -> dict:
    """constants.py からアプリ情報を取得"""
    try:
        constants_path = Path("src/utils/constants.py")
        text = constants_path.read_text(encoding="utf-8")
        info = {}
        for line in text.splitlines():
            if line.startswith("APP_VERSION"):
                info["version"] = line.split('"')[1]
            elif line.startswith("APP_CODENAME"):
                info["codename"] = line.split('"')[1]
        return info
    except Exception:
        return {}


def generate_article(title: str, version: str, changes: str,
                     github_url: str, screenshots_dir: str) -> str:
    """note.com投稿用の記事テンプレートを生成"""

    app_info = load_app_info()
    codename = app_info.get("codename", "")
    changelog = load_changelog_entry(version)

    # スクリーンショットの一覧
    ss_dir = Path(screenshots_dir)
    screenshots = sorted(ss_dir.glob("*.png")) if ss_dir.exists() else []

    today = datetime.now().strftime("%Y/%m/%d")

    article = f"""# {title}

> Helix AI Studio v{version} "{codename}" をリリースしました。

## 概要

Helix AI Studio は、複数のAI（Claude, GPT, Gemini, ローカルLLM）を統合操作できるデスクトップアプリケーションです。PyQt6製のネイティブGUIとFastAPI製のWeb UIを搭載しています。

## v{version} の変更内容

{changes if changes else changelog if changelog else "(変更内容をここに記述)"}

## スクリーンショット

"""

    if screenshots:
        for ss in screenshots:
            article += f"![{ss.stem}]({ss.name})\n\n"
        article += "> スクリーンショットはnote投稿時にPlaywright MCPが添付します。\n\n"
    else:
        article += "> (スクリーンショットはnote投稿時に添付)\n\n"

    article += f"""## リンク

- GitHub: {github_url}
- 更新日: {today}

## ハッシュタグ

#HelixAIStudio #AI #Claude #PyQt6 #デスクトップアプリ #個人開発
"""

    return article


def main():
    parser = argparse.ArgumentParser(description="note.com article generator")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--version", default=None, help="App version (auto-detect if omitted)")
    parser.add_argument("--changes", default="", help="Change description text")
    parser.add_argument(
        "--github-url",
        default="https://github.com/tsunamayo7/helix-ai-studio",
        help="GitHub repository URL"
    )
    parser.add_argument("--screenshots-dir", default="screenshots", help="Screenshots directory")
    parser.add_argument("--output", default=None, help="Output file (default: stdout)")
    args = parser.parse_args()

    version = args.version
    if not version:
        info = load_app_info()
        version = info.get("version", "0.0.0")

    article = generate_article(
        title=args.title,
        version=version,
        changes=args.changes,
        github_url=args.github_url,
        screenshots_dir=args.screenshots_dir,
    )

    if args.output:
        Path(args.output).write_text(article, encoding="utf-8")
        print(f"Saved: {args.output}")
    else:
        print(article)


if __name__ == "__main__":
    main()
