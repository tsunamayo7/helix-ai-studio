"""CLI AIクライアント — Claude Code CLI / Codex CLI / Gemini CLI"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# Known CLI model definitions
CLAUDE_CODE_MODELS = [
    {"id": "opus", "name": "Claude Opus 4.6 (1M)", "description": "Most capable model"},
    {"id": "sonnet", "name": "Claude Sonnet 4.6", "description": "Fast & powerful balance"},
    {"id": "haiku", "name": "Claude Haiku 4.5", "description": "Fastest & lowest cost"},
]

CODEX_MODELS = [
    {"id": "gpt-5.4", "name": "GPT-5.4", "description": "Latest frontier model"},
    {"id": "gpt-5.4-mini", "name": "GPT-5.4 Mini", "description": "Compact frontier model"},
    {"id": "gpt-5.3-codex", "name": "GPT-5.3 Codex", "description": "Codex optimized"},
    {"id": "gpt-5.3-codex-spark", "name": "GPT-5.3 Codex Spark", "description": "Ultra-fast coding"},
    {"id": "gpt-5.2-codex", "name": "GPT-5.2 Codex", "description": "Stable Codex model"},
    {"id": "gpt-5.2", "name": "GPT-5.2", "description": "Long-running agent model"},
]

GEMINI_CLI_MODELS = [
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Most capable"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Fast inference"},
]


def detect_installed_clis() -> dict[str, bool]:
    """インストール済みCLIを自動検出。"""
    return {
        "claude_code": shutil.which("claude") is not None,
        "codex": shutil.which("codex") is not None,
        "gemini_cli": shutil.which("gemini") is not None,
    }


def list_cli_models() -> dict[str, list[dict]]:
    """インストール済みCLIのモデル一覧を返す。"""
    installed = detect_installed_clis()
    result = {}

    if installed["claude_code"]:
        result["claude_code"] = CLAUDE_CODE_MODELS
    if installed["codex"]:
        result["codex"] = CODEX_MODELS
    if installed["gemini_cli"]:
        result["gemini_cli"] = GEMINI_CLI_MODELS

    return result


def _resolve_command(cmd_name: str) -> str:
    """コマンド名をフルパスに解決する（Windows .cmd/.exe対応）。"""
    resolved = shutil.which(cmd_name)
    if resolved:
        return resolved
    return cmd_name


def _run_subprocess(cmd: list[str], timeout: int = 300, stdin_text: str | None = None) -> subprocess.CompletedProcess:
    """サブプロセスを同期的に実行する（asyncio.to_thread用）。"""
    resolved_cmd = [_resolve_command(cmd[0])] + cmd[1:]
    return subprocess.run(
        resolved_cmd,
        capture_output=True,
        timeout=timeout,
        shell=True,
        input=stdin_text.encode("utf-8") if stdin_text else None,
    )


async def stream_chat_claude_code(
    model: str,
    message: str,
    system: str = "",
) -> AsyncIterator[str]:
    """Claude Code CLI で非対話チャット（ストリーミング風）。"""
    # 長文プロンプトはstdin経由で渡す（コマンドライン引数長制限回避）
    if len(message) > 500:
        cmd = ["claude", "-p", "-", "--model", model, "--output-format", "json"]
        stdin_text = message
    else:
        cmd = ["claude", "-p", message, "--model", model, "--output-format", "json"]
        stdin_text = None

    try:
        result = await asyncio.to_thread(_run_subprocess, cmd, 300, stdin_text)

        if result.returncode != 0:
            error_text = result.stderr.decode("utf-8", errors="replace").strip()
            yield f"[Claude Code エラー] {error_text}"
            return

        output = result.stdout.decode("utf-8", errors="replace").strip()
        try:
            data = json.loads(output)
            result_text = data.get("result", output)
        except json.JSONDecodeError:
            result_text = output

        # チャンク分割してストリーミング風に返す
        chunk_size = 50
        for i in range(0, len(result_text), chunk_size):
            yield result_text[i:i + chunk_size]
            await asyncio.sleep(0.02)

    except subprocess.TimeoutExpired:
        yield "[Claude Code タイムアウト] 300秒以内に応答がありませんでした"
    except FileNotFoundError:
        yield "[エラー] claude コマンドが見つかりません。Claude Code CLIをインストールしてください。"
    except Exception as e:
        logger.exception("Claude Code CLI実行エラー: %s (type=%s)", e, type(e).__name__)
        yield f"[エラー] {type(e).__name__}: {e}"


async def stream_chat_codex(
    model: str,
    message: str,
) -> AsyncIterator[str]:
    """Codex CLI で非対話チャット（ストリーミング風）。"""
    cmd = ["codex", "exec", "-m", model, "--", message]

    try:
        result = await asyncio.to_thread(_run_subprocess, cmd, 300)

        if result.returncode != 0:
            error_text = result.stderr.decode("utf-8", errors="replace").strip()
            yield f"[Codex エラー] {error_text}"
            return

        output = result.stdout.decode("utf-8", errors="replace").strip()

        # チャンク分割
        chunk_size = 50
        for i in range(0, len(output), chunk_size):
            yield output[i:i + chunk_size]
            await asyncio.sleep(0.02)

    except subprocess.TimeoutExpired:
        yield "[Codex タイムアウト] 300秒以内に応答がありませんでした"
    except FileNotFoundError:
        yield "[エラー] codex コマンドが見つかりません。Codex CLIをインストールしてください。"
    except Exception as e:
        logger.exception("Codex CLI実行エラー: %s (type=%s)", e, type(e).__name__)
        yield f"[エラー] {type(e).__name__}: {e}"


async def stream_chat_gemini_cli(
    model: str,
    message: str,
) -> AsyncIterator[str]:
    """Gemini CLI で非対話チャット（ストリーミング風）。"""
    cmd = ["gemini", "-p", message, "-m", model]

    try:
        result = await asyncio.to_thread(_run_subprocess, cmd, 300)

        if result.returncode != 0:
            error_text = result.stderr.decode("utf-8", errors="replace").strip()
            yield f"[Gemini CLI エラー] {error_text}"
            return

        output = result.stdout.decode("utf-8", errors="replace").strip()

        chunk_size = 50
        for i in range(0, len(output), chunk_size):
            yield output[i:i + chunk_size]
            await asyncio.sleep(0.02)

    except subprocess.TimeoutExpired:
        yield "[Gemini CLI タイムアウト] 300秒以内に応答がありませんでした"
    except FileNotFoundError:
        yield "[エラー] gemini コマンドが見つかりません。Gemini CLIをインストールしてください。"
    except Exception as e:
        logger.exception("Gemini CLI実行エラー: %s (type=%s)", e, type(e).__name__)
        yield f"[エラー] {type(e).__name__}: {e}"


async def stream_chat_cli(
    provider: str,
    model: str,
    message: str,
    system: str = "",
) -> AsyncIterator[str]:
    """CLI統合インターフェース。"""
    if provider == "claude_code":
        async for chunk in stream_chat_claude_code(model, message, system):
            yield chunk
    elif provider == "codex":
        async for chunk in stream_chat_codex(model, message):
            yield chunk
    elif provider == "gemini_cli":
        async for chunk in stream_chat_gemini_cli(model, message):
            yield chunk
    else:
        yield f"[エラー] 未対応のCLIプロバイダ: {provider}"
