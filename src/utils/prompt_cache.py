"""
Helix AI Studio - Prompt Cache Optimizer (v10.0.0)

Claude CLI の Prompt Caching を最適化するユーティリティ。

Claude API は 1024+ トークンの共通プレフィックスを自動キャッシュする。
このモジュールは:
  1. システムプロンプト（固定部分）を先頭に配置
  2. BIBLEコンテキスト（変更頻度低）を次に配置
  3. メモリコンテキスト（変更頻度中）をその次に配置
  4. ユーザープロンプト（毎回変化）を最後に配置

これにより、自動キャッシュのヒット率を最大化する。
"""

import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# プロンプトキャッシュ（system prompt + BIBLE の結合テキストを保持）
_cache: dict = {}
_CACHE_TTL = 300  # 5分


def build_optimized_prompt(
    system_prompt: str,
    bible_context: str = "",
    memory_context: str = "",
    user_prompt: str = "",
) -> str:
    """キャッシュ最適化されたプロンプトを構築する

    Claude APIの自動Prompt Cachingは、リクエスト間で共通するプレフィックスを
    自動的にキャッシュする。変化しない部分をプレフィックスとして固定配置することで
    キャッシュヒット率を向上させる。

    プロンプト構造:
      [System Prompt (固定)] → [BIBLE (低頻度変更)] → [Memory (中頻度変更)] → [User (毎回変化)]

    Args:
        system_prompt: Phase 1/Phase 3のシステムプロンプト
        bible_context: BIBLEから生成されたコンテキスト
        memory_context: メモリマネージャーから生成されたコンテキスト
        user_prompt: ユーザーの質問

    Returns:
        最適化されたフルプロンプト
    """
    parts = []

    # 1. System Prompt (固定部分 - キャッシュ最有力候補)
    if system_prompt:
        parts.append(system_prompt)

    # 2. BIBLE Context (低頻度変更 - キャッシュ準有力候補)
    if bible_context:
        parts.append(bible_context)

    # 3. Memory Context (中頻度変更)
    if memory_context:
        parts.append(memory_context)

    # 4. User Prompt (毎回変化 - キャッシュ対象外)
    if user_prompt:
        parts.append(f"## ユーザーの要求:\n{user_prompt}")

    return "\n\n".join(parts)


def get_cached_prefix(system_prompt: str, bible_context: str = "") -> Optional[str]:
    """キャッシュ済みプレフィックスを取得（TTL内ならキャッシュヒット）

    Args:
        system_prompt: システムプロンプト
        bible_context: BIBLEコンテキスト

    Returns:
        キャッシュ済みプレフィックス（存在する場合）、なければNone
    """
    key = hashlib.md5(f"{system_prompt}{bible_context}".encode()).hexdigest()
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        logger.debug(f"[PromptCache] Cache hit: {key[:8]}")
        return entry["prefix"]
    return None


def set_cached_prefix(system_prompt: str, bible_context: str = "", prefix: str = ""):
    """プレフィックスをキャッシュに保存"""
    key = hashlib.md5(f"{system_prompt}{bible_context}".encode()).hexdigest()
    _cache[key] = {"prefix": prefix, "ts": time.time()}
    logger.debug(f"[PromptCache] Cache set: {key[:8]}, len={len(prefix)}")


def estimate_cache_savings(prefix_len: int, calls_per_session: int = 5) -> dict:
    """キャッシュによるトークン節約量を推定

    Claude API の prompt caching は、キャッシュヒット時に
    入力トークン数の 90% を削減する（課金ベース）。

    Args:
        prefix_len: 共通プレフィックスの文字数
        calls_per_session: セッション内の予想呼び出し回数

    Returns:
        推定節約情報
    """
    tokens_est = prefix_len // 3
    saved_per_call = int(tokens_est * 0.9)
    total_saved = saved_per_call * (calls_per_session - 1)  # 初回はキャッシュなし
    return {
        "prefix_tokens": tokens_est,
        "saved_per_call": saved_per_call,
        "total_saved_tokens": total_saved,
        "calls": calls_per_session,
    }
