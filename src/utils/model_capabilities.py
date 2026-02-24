"""
Helix AI Studio — モデル能力レジストリ (v11.3.0)

config/model_capabilities.json から動的にモデル能力を取得する。
ハードコードによるモデル判定を廃止し、ファイル更新だけで新モデルに対応できる。
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CAPS_PATH = Path("config/model_capabilities.json")
_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        if _CAPS_PATH.exists():
            data = json.loads(_CAPS_PATH.read_text(encoding='utf-8'))
            _cache = data
            return data
    except Exception as e:
        logger.warning(f"model_capabilities.json load failed: {e}")
    return {}


def get_model_capability(model_id: str, key: str, default=None):
    """指定モデルの能力値を取得する。モデルが未登録の場合は default_capabilities を使用。"""
    data = _load()
    models = data.get("models", {})

    # 完全一致
    if model_id in models:
        return models[model_id].get(key, default)

    # プレフィックス一致（将来のマイナーバージョン追加に対応）
    for registered_id, caps in models.items():
        if model_id.startswith(registered_id) or registered_id.startswith(model_id.split("-20")[0]):
            return caps.get(key, default)

    # デフォルト能力値
    defaults = data.get("default_capabilities", {})
    return defaults.get(key, default)


def supports_adaptive_thinking(model_id: str) -> bool:
    """モデルが Adaptive Thinking (effort level) をサポートするか。"""
    return bool(get_model_capability(model_id, "supports_adaptive_thinking", False))


def get_adaptive_thinking_env_var(model_id: str) -> Optional[str]:
    """Adaptive Thinking の環境変数名を返す。未対応モデルは None。"""
    if not supports_adaptive_thinking(model_id):
        return None
    return get_model_capability(model_id, "adaptive_thinking_env_var", "CLAUDE_CODE_EFFORT_LEVEL")


def get_adaptive_thinking_levels(model_id: str) -> list:
    """Adaptive Thinking の有効レベル一覧を返す。"""
    return get_model_capability(model_id, "adaptive_thinking_levels", ["low", "medium", "high"])


def invalidate_cache():
    """キャッシュを破棄して次回読み込み時に再取得させる（設定変更後に呼ぶ）。"""
    global _cache
    _cache = None
