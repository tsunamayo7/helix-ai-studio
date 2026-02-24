"""v11.0.0: ローカルLLMモデル設定の一元管理

全モジュール（memory_manager.py, rag_executor.py, rag_planner.py 等）は
このモジュールからモデル名を取得する。ハードコードを廃止。

各モデル参照箇所は **関数呼び出し時** に解決する（モジュールロード時ではない）。
これにより設定変更が即時反映される。
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# v11.5.0: デフォルトを空文字に変更。ユーザーが app_settings.json で設定する。
_DEFAULT_EXEC_LLM = ""
_DEFAULT_QUALITY_LLM = ""
_DEFAULT_EMBEDDING = ""


def _load_rag_settings() -> dict:
    """app_settings.json の rag セクションを読み込む"""
    try:
        p = Path("config/app_settings.json")
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f).get("rag", {})
    except Exception as e:
        logger.debug(f"Failed to load RAG settings: {e}")
    return {}


def get_exec_llm() -> str:
    """実行LLM（TKG構築、RAPTOR要約等）

    推奨: 32B以上、長コンテキスト対応モデル
    デフォルト: command-a:latest
    """
    return _load_rag_settings().get("exec_llm", _DEFAULT_EXEC_LLM)


def get_quality_llm() -> str:
    """品質チェックLLM（Memory Risk Gate、検証等）

    推奨: 8B程度の軽量高速モデル
    デフォルト: ministral-3:8b
    """
    return _load_rag_settings().get("quality_llm", _DEFAULT_QUALITY_LLM)


def get_embedding_model() -> str:
    """Embeddingモデル

    推奨: embedding専用モデル
    デフォルト: qwen3-embedding:0.6b
    """
    return _load_rag_settings().get("embedding_model", _DEFAULT_EMBEDDING)


def get_all_model_config() -> dict:
    """全モデル設定を辞書で取得"""
    return {
        "exec_llm": get_exec_llm(),
        "quality_llm": get_quality_llm(),
        "embedding_model": get_embedding_model(),
    }
