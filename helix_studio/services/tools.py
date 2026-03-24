"""ツールサービス — Web検索 + ファイル操作（無料・軽量）"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Web検索（DuckDuckGo — 無料・APIキー不要）──


async def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """DuckDuckGo Instant Answer API + HTML検索で結果を取得（無料）"""
    results = []

    # DuckDuckGo Instant Answer API（公式、無料）
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
            )
            data = resp.json()

            # Abstract（概要）
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": data["AbstractText"][:300],
                    "url": data.get("AbstractURL", ""),
                    "source": "DuckDuckGo",
                })

            # RelatedTopics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", "")[:300],
                        "url": topic.get("FirstURL", ""),
                        "source": "DuckDuckGo",
                    })
    except Exception as e:
        logger.debug("DuckDuckGo API検索失敗: %s", e)

    # DuckDuckGo HTML検索（フォールバック）
    if len(results) < max_results:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                text = resp.text
                # シンプルなHTMLパース（BeautifulSoup不要）
                import re
                links = re.findall(
                    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'class="result__snippet"[^>]*>(.*?)</span>',
                    text, re.DOTALL,
                )
                for url, title, snippet in links[:max_results - len(results)]:
                    clean_title = re.sub(r'<[^>]+>', '', title).strip()
                    clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    if clean_title:
                        results.append({
                            "title": clean_title,
                            "snippet": clean_snippet[:300],
                            "url": url,
                            "source": "DuckDuckGo",
                        })
        except Exception as e:
            logger.debug("DuckDuckGo HTML検索失敗: %s", e)

    return results[:max_results]


def format_search_results(results: list[dict]) -> str:
    """検索結果をLLMに渡すテキスト形式に整形"""
    if not results:
        return "検索結果が見つかりませんでした。"
    lines = ["## Web検索結果\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}. {r['title']}**")
        lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   URL: {r['url']}")
        lines.append("")
    return "\n".join(lines)


# ── ファイル操作（ローカルファイルシステム）──

# セキュリティ: アクセス可能なベースディレクトリ
ALLOWED_BASE_DIRS = [
    "C:/Development",
    "C:/Users",
]


def _is_safe_path(path: str) -> bool:
    """パストラバーサル防止。許可されたディレクトリ内のみアクセス可能。"""
    try:
        resolved = str(Path(path).resolve())
        return any(resolved.startswith(str(Path(d).resolve())) for d in ALLOWED_BASE_DIRS)
    except Exception:
        return False


async def list_files(path: str) -> dict[str, Any]:
    """ディレクトリの内容を一覧表示"""
    if not _is_safe_path(path):
        return {"error": f"アクセス不可: {path}（許可されたディレクトリ外）"}

    p = Path(path)
    if not p.exists():
        return {"error": f"パスが存在しません: {path}"}
    if not p.is_dir():
        return {"error": f"ディレクトリではありません: {path}"}

    entries = []
    try:
        for item in sorted(p.iterdir()):
            if item.name.startswith("."):
                continue  # 隠しファイルスキップ
            entry = {
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
            }
            if item.is_file():
                entry["size"] = item.stat().st_size
                entry["size_display"] = _format_size(item.stat().st_size)
            entries.append(entry)
    except PermissionError:
        return {"error": f"権限エラー: {path}"}

    return {"path": str(p), "entries": entries, "count": len(entries)}


async def read_file(path: str, max_size: int = 1_000_000) -> dict[str, Any]:
    """ファイルを読み取り（最大1MB）"""
    if not _is_safe_path(path):
        return {"error": f"アクセス不可: {path}（許可されたディレクトリ外）"}

    p = Path(path)
    if not p.exists():
        return {"error": f"ファイルが存在しません: {path}"}
    if not p.is_file():
        return {"error": f"ファイルではありません: {path}"}
    if p.stat().st_size > max_size:
        return {"error": f"ファイルが大きすぎます: {_format_size(p.stat().st_size)}（上限: {_format_size(max_size)}）"}

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(p),
            "content": content,
            "size": p.stat().st_size,
            "lines": content.count("\n") + 1,
        }
    except Exception as e:
        return {"error": f"読み取りエラー: {e}"}


async def write_file(path: str, content: str) -> dict[str, Any]:
    """ファイルに書き込み"""
    if not _is_safe_path(path):
        return {"error": f"アクセス不可: {path}（許可されたディレクトリ外）"}

    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": str(p), "size": p.stat().st_size, "ok": True}
    except Exception as e:
        return {"error": f"書き込みエラー: {e}"}


def format_file_listing(result: dict) -> str:
    """ファイル一覧をLLMに渡すテキスト形式に整形"""
    if result.get("error"):
        return f"エラー: {result['error']}"
    lines = [f"## ファイル一覧: {result['path']}\n"]
    for e in result.get("entries", []):
        if e["type"] == "dir":
            lines.append(f"  📁 {e['name']}/")
        else:
            lines.append(f"  📄 {e['name']} ({e.get('size_display', '')})")
    lines.append(f"\n合計: {result.get('count', 0)} 項目")
    return "\n".join(lines)


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
