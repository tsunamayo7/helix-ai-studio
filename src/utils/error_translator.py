"""
Helix AI Studio — Error Translator

外部API/CLIからのエラーメッセージをi18nキーにマッピングし、
アプリの表示言語に応じた翻訳を返す。

対応バックエンド:
  - Claude CLI (Anthropic)
  - Ollama (ローカルLLM)
  - Google Gemini API / CLI
  - OpenAI API (GPT)

Usage:
    from src.utils.error_translator import translate_error
    user_msg = translate_error(str(e), source="ollama")
"""

import re
import logging
from typing import Optional

from .i18n import t, get_language

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# パターン定義: (regex, i18n_key, extra_kwargs_extractor)
#   - regex: エラーメッセージにマッチする正規表現
#   - i18n_key: 翻訳キー
#   - extra_kwargs_extractor: マッチオブジェクトからパラメータを抽出する関数 (optional)
# ---------------------------------------------------------------------------

_COMMON_PATTERNS = [
    # --- 接続エラー ---
    (re.compile(r"Connect(?:ion)?(?:Error|Refused|Reset)|ECONNREFUSED|Connection refused",
                re.IGNORECASE),
     "common.errors.connectionRefused", None),

    # --- タイムアウト ---
    (re.compile(r"(?:Timeout|timed?\s*out)(?:Error|Expired)?", re.IGNORECASE),
     "common.errors.timeout", None),

    # --- DNS / ネットワーク ---
    (re.compile(r"Name(?:Resolution|Lookup)Error|getaddrinfo failed|DNS",
                re.IGNORECASE),
     "common.errors.dnsError", None),

    # --- SSL/TLS ---
    (re.compile(r"SSL(?:Error|CertVerificationError)|certificate verify failed",
                re.IGNORECASE),
     "common.errors.sslError", None),

    # --- レート制限 ---
    (re.compile(r"(?:429|rate.?limit|too.?many.?requests|overloaded)",
                re.IGNORECASE),
     "common.errors.rateLimited", None),

    # --- 認証エラー ---
    (re.compile(r"\b401\b|Unauthorized|authentication.?failed|invalid.?(?:api.?)?key",
                re.IGNORECASE),
     "common.errors.unauthorized", None),

    # --- 権限不足 ---
    (re.compile(r"\b403\b|Forbidden|permission.?denied|Access.?Denied",
                re.IGNORECASE),
     "common.errors.forbidden", None),

    # --- リソース未検出 ---
    (re.compile(r"\b404\b|Not\s*Found", re.IGNORECASE),
     "common.errors.notFound", None),

    # --- サーバーエラー ---
    (re.compile(r"\b50[0-3]\b|Internal\s*Server\s*Error|Bad\s*Gateway|Service\s*Unavailable",
                re.IGNORECASE),
     "common.errors.serverError", None),

    # --- JSON パースエラー ---
    (re.compile(r"JSON(?:Decode)?Error|Expecting\s+value|Invalid\s+JSON",
                re.IGNORECASE),
     "common.errors.invalidJson", None),

    # --- メモリ / リソース不足 ---
    (re.compile(r"out\s*of\s*memory|OOM|CUDA.*?error|GPU.*?memory",
                re.IGNORECASE),
     "common.errors.outOfMemory", None),
]

# ---------------------------------------------------------------------------
# Claude CLI 固有パターン
# ---------------------------------------------------------------------------
_CLAUDE_PATTERNS = [
    (re.compile(r"\[ACTION\s+REQUIRED\]", re.IGNORECASE),
     "common.errors.claude.actionRequired", None),

    (re.compile(r"Claude\s+CLI\s+(?:not\s+found|見つかりません)", re.IGNORECASE),
     "common.errors.claude.notFound", None),

    (re.compile(r"Claude\s+CLI\s+(?:timed?\s*out|タイムアウト)", re.IGNORECASE),
     "common.errors.claude.timeout", None),

    (re.compile(r"Claude\s+CLI\s+error\s*\(code\s+(\d+)\)", re.IGNORECASE),
     "common.errors.claude.exitCode",
     lambda m: {"code": m.group(1)}),

    # v12.7.1: 日本語エラーメッセージパターン (mix_orchestrator が生成する形式)
    (re.compile(r"Claude\s+CLI\s+の実行に失敗しました\s*\(code\s+(\d+)\)", re.IGNORECASE),
     "common.errors.claude.exitCode",
     lambda m: {"code": m.group(1)}),

    (re.compile(r"Claude\s+CLI\s*(?:終了コード|exit\s*code)\s*(\d+)", re.IGNORECASE),
     "common.errors.claude.exitCode",
     lambda m: {"code": m.group(1)}),

    (re.compile(r"Claude\s+CLI\s+API\s+エラー", re.IGNORECASE),
     "common.errors.claude.apiError", None),

    (re.compile(r"(?:credit|billing|usage).?(?:limit|exceeded|quota)",
                re.IGNORECASE),
     "common.errors.claude.quotaExceeded", None),
]

# ---------------------------------------------------------------------------
# Ollama 固有パターン
# ---------------------------------------------------------------------------
_OLLAMA_PATTERNS = [
    (re.compile(r"model\s+['\"]?(\S+?)['\"]?\s+(?:not\s+found|が見つかりません)",
                re.IGNORECASE),
     "common.errors.ollama.modelNotFound",
     lambda m: {"model": m.group(1)}),

    (re.compile(r"Ollama\s+(?:に接続できません|接続失敗|Connect)", re.IGNORECASE),
     "common.errors.ollama.connectionFailed", None),

    (re.compile(r"Ollama\s+(?:タイムアウト|timeout)", re.IGNORECASE),
     "common.errors.ollama.timeout", None),

    (re.compile(r"pull(?:ing)?\s+(?:model\s+)?(?:failed|error)",
                re.IGNORECASE),
     "common.errors.ollama.pullFailed", None),
]

# ---------------------------------------------------------------------------
# Gemini 固有パターン
# ---------------------------------------------------------------------------
_GEMINI_PATTERNS = [
    (re.compile(r"Gemini\s+(?:CLI\s+)?(?:not\s+found|見つかりません)", re.IGNORECASE),
     "common.errors.gemini.notFound", None),

    (re.compile(r"SAFETY|safety.?block|block.*?(?:reason|filter)|HarmCategory",
                re.IGNORECASE),
     "common.errors.gemini.safetyBlock", None),

    (re.compile(r"(?:gemini|google).*?(?:quota|limit|exceeded)",
                re.IGNORECASE),
     "common.errors.gemini.quotaExceeded", None),

    (re.compile(r"GOOGLE_API_KEY|google.*?(?:api.?key|credentials)",
                re.IGNORECASE),
     "common.errors.gemini.apiKeyMissing", None),

    (re.compile(r"Gemini.*?(?:timed?\s*out|タイムアウト)", re.IGNORECASE),
     "common.errors.gemini.timeout", None),
]

# ---------------------------------------------------------------------------
# OpenAI / GPT 固有パターン
# ---------------------------------------------------------------------------
_OPENAI_PATTERNS = [
    (re.compile(r"OPENAI_API_KEY|openai.*?(?:api.?key|credentials)",
                re.IGNORECASE),
     "common.errors.openai.apiKeyMissing", None),

    (re.compile(r"(?:openai|gpt).*?(?:quota|limit|exceeded|billing)",
                re.IGNORECASE),
     "common.errors.openai.quotaExceeded", None),

    (re.compile(r"(?:openai|gpt).*?(?:context.?(?:length|window)|too.?long|max.?tokens)",
                re.IGNORECASE),
     "common.errors.openai.contextTooLong", None),

    (re.compile(r"(?:openai|gpt).*?(?:content.?filter|policy|moderation)",
                re.IGNORECASE),
     "common.errors.openai.contentFiltered", None),
]

# ---------------------------------------------------------------------------
# source -> パターンリスト マッピング
# ---------------------------------------------------------------------------
_SOURCE_PATTERNS = {
    "claude": _CLAUDE_PATTERNS,
    "ollama": _OLLAMA_PATTERNS,
    "gemini": _GEMINI_PATTERNS,
    "openai": _OPENAI_PATTERNS,
    "gpt":    _OPENAI_PATTERNS,
}


def translate_error(
    error_msg: str,
    source: Optional[str] = None,
    **extra_params,
) -> str:
    """
    外部エラーメッセージをアプリの表示言語に翻訳する。

    Args:
        error_msg:  例外メッセージ文字列
        source:     エラーのソース ("claude" / "ollama" / "gemini" / "openai" / "gpt")
                    None の場合は全パターンを試行
        **extra_params: 翻訳テンプレートに渡す追加パラメータ

    Returns:
        翻訳されたエラーメッセージ。マッチしない場合は元のメッセージを返す。
    """
    if not error_msg:
        return t("common.error")

    # 1) source 固有パターンを最初に試行
    if source:
        source_key = source.lower().replace(" ", "")
        patterns = _SOURCE_PATTERNS.get(source_key, [])
        result = _try_patterns(error_msg, patterns, extra_params)
        if result:
            return result

    # 2) 全 source 固有パターンを試行 (source=None の場合)
    if not source:
        for patterns in _SOURCE_PATTERNS.values():
            result = _try_patterns(error_msg, patterns, extra_params)
            if result:
                return result

    # 3) 共通パターンを試行
    result = _try_patterns(error_msg, _COMMON_PATTERNS, extra_params)
    if result:
        return result

    # 4) マッチなし — 元のメッセージを返す
    return error_msg


def translate_error_with_detail(
    error_msg: str,
    source: Optional[str] = None,
    **extra_params,
) -> str:
    """
    翻訳 + 元のエラーメッセージを詳細として付与する。

    Returns:
        "翻訳メッセージ\n詳細: 元のメッセージ" or 元のメッセージ（翻訳なしの場合）
    """
    translated = translate_error(error_msg, source, **extra_params)
    if translated != error_msg:
        # 翻訳が適用された場合、詳細を付与
        detail_label = t("common.errors.detail")
        return f"{translated}\n{detail_label}: {error_msg[:300]}"
    return error_msg


def _try_patterns(error_msg: str, patterns: list, extra_params: dict) -> Optional[str]:
    """パターンリストを順に試行し、最初にマッチした翻訳を返す。"""
    for regex, key, kwargs_fn in patterns:
        match = regex.search(error_msg)
        if match:
            params = dict(extra_params)
            if kwargs_fn:
                params.update(kwargs_fn(match))
            translated = t(key, **params)
            # t() がキー名をそのまま返した場合はマッチしたがi18nキーが未定義
            if translated != key:
                return translated
            else:
                logger.debug(f"[error_translator] i18n key not found: {key}")
    return None
