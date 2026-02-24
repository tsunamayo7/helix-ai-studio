"""
Helix AI Studio - API Priority Resolver (v11.4.0)

「APIキーがあれば API 優先 → なければ CLI フォールバック」の
判定ロジックを一元管理するモジュール。
"""
import logging
from enum import Enum
from typing import Tuple

logger = logging.getLogger(__name__)


class ConnectionMode(Enum):
    """接続モード"""
    AUTO = "auto"           # API優先 → CLI フォールバック
    API_ONLY = "api_only"   # API のみ（CLI フォールバックなし）
    CLI_ONLY = "cli_only"   # CLI のみ（API Key があっても無視）


class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


def resolve_anthropic_connection(
    mode: ConnectionMode = ConnectionMode.AUTO,
) -> Tuple[str, dict]:
    """
    Anthropic の接続方式を解決する。

    Returns:
        (method, kwargs) のタプル
        method: "anthropic_api" | "claude_cli" | "unavailable"
        kwargs: 接続に必要な情報
    """
    from .anthropic_api_backend import get_anthropic_api_key
    from . import check_claude_cli_available

    if mode == ConnectionMode.CLI_ONLY:
        cli_ok, msg = check_claude_cli_available()
        if cli_ok:
            return "claude_cli", {}
        return "unavailable", {"reason": f"Claude CLI が利用できません: {msg}"}

    if mode in (ConnectionMode.AUTO, ConnectionMode.API_ONLY):
        api_key = get_anthropic_api_key()
        if api_key:
            return "anthropic_api", {"api_key": api_key}

    if mode == ConnectionMode.API_ONLY:
        return "unavailable", {
            "reason": (
                "Anthropic API キーが設定されていません。\n"
                "一般設定 → API Keys → Anthropic API Key に設定してください。"
            )
        }

    # AUTO: API Key なし → CLI フォールバック
    cli_ok, msg = check_claude_cli_available()
    if cli_ok:
        logger.info("[APIPriorityResolver] Anthropic API key not set, falling back to Claude CLI")
        return "claude_cli", {}

    return "unavailable", {
        "reason": (
            "Claude に接続できません。\n"
            "以下のいずれかを設定してください:\n"
            "  1. Anthropic API Key: 一般設定 → API Keys → Anthropic API Key\n"
            "  2. Claude Code CLI: claude login でログイン"
        )
    }


def resolve_openai_connection(
    mode: ConnectionMode = ConnectionMode.AUTO,
) -> Tuple[str, dict]:
    """
    OpenAI の接続方式を解決する。

    Returns:
        (method, kwargs) のタプル
        method: "openai_api" | "codex_cli" | "unavailable"
        kwargs: 接続に必要な情報
    """
    from .openai_api_backend import get_openai_api_key
    from .codex_cli_backend import _resolve_codex_path

    if mode == ConnectionMode.CLI_ONLY:
        codex_path = _resolve_codex_path()
        if codex_path:
            return "codex_cli", {}
        return "unavailable", {"reason": "Codex CLI が見つかりません"}

    if mode in (ConnectionMode.AUTO, ConnectionMode.API_ONLY):
        api_key = get_openai_api_key()
        if api_key:
            return "openai_api", {"api_key": api_key}

    if mode == ConnectionMode.API_ONLY:
        return "unavailable", {
            "reason": (
                "OpenAI API キーが設定されていません。\n"
                "一般設定 → API Keys → OpenAI API Key に設定してください。"
            )
        }

    # AUTO: API Key なし → Codex CLI フォールバック
    codex_path = _resolve_codex_path()
    if codex_path:
        logger.info("[APIPriorityResolver] OpenAI API key not set, falling back to Codex CLI")
        return "codex_cli", {}

    return "unavailable", {
        "reason": (
            "OpenAI に接続できません。\n"
            "以下のいずれかを設定してください:\n"
            "  1. OpenAI API Key: 一般設定 → API Keys → OpenAI API Key\n"
            "  2. Codex CLI: codex login でログイン"
        )
    }


def resolve_google_connection(
    mode: ConnectionMode = ConnectionMode.API_ONLY,
) -> Tuple[str, dict]:
    """
    v11.5.0 L-G: Google Gemini API 接続方式を解決する。

    Returns:
        (method, kwargs) のタプル
        method: "google_api" | "unavailable"
        kwargs: 接続に必要な情報
    """
    from .google_api_backend import get_google_api_key, is_google_genai_sdk_available

    # SDK チェック
    if not is_google_genai_sdk_available():
        return "unavailable", {
            "reason": (
                "google-genai SDK が未インストールです。\n"
                "pip install google-genai\n"
                "注意: google-generativeai は EOL（2025/11/30）です"
            )
        }

    # API Key チェック
    key = get_google_api_key()
    if not key:
        return "unavailable", {
            "reason": (
                "Google API Key が未設定です。\n"
                "取得先: https://aistudio.google.com/app/apikey\n"
                "設定場所: 一般設定 → API Keys → Google API Key"
            )
        }

    return "google_api", {"api_key": key}
