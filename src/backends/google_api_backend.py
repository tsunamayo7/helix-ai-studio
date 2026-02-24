"""
Google Gemini API Backend（v11.5.0 L-G）

SDK要件:
    pip install google-genai          # ← 必ずこちら（統合SDK GA版）
    # ❌ pip install google-generativeai  # EOL（2025/11/30）使用禁止

認証:
    環境変数 GEMINI_API_KEY または GOOGLE_API_KEY を設定
    取得先: https://aistudio.google.com/app/apikey
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


def is_google_genai_sdk_available() -> bool:
    """google-genai（統合SDK）がインストール済みかどうか確認"""
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def get_google_api_key() -> Optional[str]:
    """API キーを環境変数 → general_settings.json の順で取得"""
    # 環境変数を優先（GOOGLE_API_KEY が GEMINI_API_KEY より優先される仕様）
    key = (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if key:
        return key
    # general_settings.json から読み込み
    try:
        import json
        settings_path = Path("config/general_settings.json")
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return data.get("google_api_key") or None
    except Exception:
        pass
    return None


def call_google_api_stream(
    prompt: str,
    model_id: str = "gemini-2.5-flash",
    system_prompt: str = "",
    api_key: Optional[str] = None,
    max_output_tokens: int = 8192,
    temperature: float = 0.7,
) -> Iterator[str]:
    """
    Gemini API をストリーミングで呼び出すジェネレーター。

    Args:
        prompt: ユーザープロンプト
        model_id: Gemini モデル ID（例: "gemini-2.5-flash"）
        system_prompt: システムプロンプト（空の場合は省略）
        api_key: API Key（省略時は get_google_api_key() から取得）
        max_output_tokens: 最大出力トークン数
        temperature: 生成温度（0.0〜1.0）

    Yields:
        str: 応答テキストのチャンク

    Raises:
        ImportError: google-genai が未インストールの場合
        ValueError: API Key が未設定の場合
    """
    if not is_google_genai_sdk_available():
        raise ImportError(
            "google-genai がインストールされていません。\n"
            "pip install google-genai を実行してください。\n"
            "注意: 旧ライブラリ google-generativeai は EOL です。"
        )

    key = api_key or get_google_api_key()
    if not key:
        raise ValueError(
            "Google API Key が未設定です。\n"
            "取得先: https://aistudio.google.com/app/apikey\n"
            "設定方法: 一般設定 > API Keys > Google API Key に入力して保存"
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    config_kwargs = {
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt

    config = types.GenerateContentConfig(**config_kwargs)

    try:
        for chunk in client.models.generate_content_stream(
            model=model_id,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as e:
        error_msg = str(e)
        if "APIError" in type(e).__name__:
            raise RuntimeError(f"Gemini API エラー: {error_msg}") from e
        raise RuntimeError(f"Gemini API 通信エラー: {error_msg}") from e


def call_google_api(
    prompt: str,
    model_id: str = "gemini-2.5-flash",
    system_prompt: str = "",
    api_key: Optional[str] = None,
    max_output_tokens: int = 8192,
    temperature: float = 0.7,
) -> str:
    """非ストリーミング版。RAG Planner等の同期バッチ処理向け。"""
    chunks = []
    for chunk in call_google_api_stream(
        prompt=prompt,
        model_id=model_id,
        system_prompt=system_prompt,
        api_key=api_key,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    ):
        chunks.append(chunk)
    return "".join(chunks)
