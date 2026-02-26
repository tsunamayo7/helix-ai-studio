"""v11.0.0: モデル候補の動的取得を一元管理するModelCatalog

全タブのComboBoxに候補を供給する。固定配列(addItems)を禁止し、
必ずこのモジュール経由でモデル一覧を取得する。

cloud_models.json → cloudAI登録済みモデル
Ollama /api/tags  → localAIインストール済みモデル
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CLOUD_MODELS_PATH = Path("config/cloud_models.json")
OLLAMA_DEFAULT_URL = "http://localhost:11434"


def get_cloud_models() -> list[dict]:
    """cloud_models.json からクラウドモデル一覧を取得"""
    try:
        if CLOUD_MODELS_PATH.exists():
            with open(CLOUD_MODELS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("models", [])
    except Exception as e:
        logger.warning(f"Failed to load cloud models: {e}")
    return []


def get_cloud_model_names() -> list[str]:
    """cloudAI登録済みモデルの表示名リスト"""
    return [m.get("name", "") for m in get_cloud_models() if m.get("name")]


def get_provider_for_engine(engine_id: str) -> str | None:
    """v11.9.3: engine_id (model_id or display name) から provider を返す"""
    for m in get_cloud_models():
        if m.get("model_id") == engine_id or m.get("name") == engine_id:
            return m.get("provider")
    return None

def is_cloud_engine(engine_id: str) -> bool:
    """v11.9.3: engine_idがクラウドモデルかどうか判定"""
    return get_provider_for_engine(engine_id) is not None


def get_ollama_installed_models(ollama_url: str = None) -> list[str]:
    """Ollamaインストール済みモデル名を取得 (/api/tags)"""
    url = ollama_url or OLLAMA_DEFAULT_URL
    try:
        import httpx
        resp = httpx.get(f"{url}/api/tags", timeout=3)
        if resp.status_code == 200:
            return [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def get_phase13_candidates(ollama_url: str = None, skip_label: str = "") -> list[str]:
    """Phase 1/3: cloudAI登録済みモデル + localAIインストール済みモデル"""
    items = []
    if skip_label:
        items.append(skip_label)
    items.extend(get_cloud_model_names())
    local = get_ollama_installed_models(ollama_url)
    if local:
        items.append("--- Local LLM ---")
        items.extend(local)
    return items


def get_phase2_candidates(ollama_url: str = None,
                          skip_label: str = "(未選択 - スキップ)") -> list[str]:
    """v11.6.0: Phase 2: [スキップ] + localAIモデル + [クラウドAI（コスト注意）]"""
    items = [skip_label]
    local = get_ollama_installed_models(ollama_url)
    if local:
        items.extend(local)
    cloud = get_cloud_model_names()
    if cloud:
        items.append("── Cloud AI（コスト発生・要注意）──")
        items.extend(cloud)
    return items


def get_phase2_vision_candidates(ollama_url: str = None,
                                  skip_label: str = "(未選択 - スキップ)") -> list[str]:
    """v11.6.0: Phase 2 vision カテゴリ専用 — vision capability を持つモデルを優先表示。"""
    url = ollama_url or OLLAMA_DEFAULT_URL
    items = [skip_label]

    try:
        import httpx
        resp = httpx.get(f"{url}/api/tags", timeout=3)
        if resp.status_code != 200:
            return items
        models = [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
    except Exception:
        return items

    vision_models = []
    other_models = []

    for name in models:
        try:
            import httpx as _httpx
            show_resp = _httpx.post(f"{url}/api/show", json={"name": name}, timeout=2)
            if show_resp.status_code == 200:
                caps = show_resp.json().get("capabilities", [])
                if "vision" in caps:
                    vision_models.append(name)
                else:
                    other_models.append(name)
            else:
                other_models.append(name)
        except Exception:
            other_models.append(name)

    if vision_models:
        items.append("── Vision 対応 ──")
        items.extend(vision_models)
    if other_models:
        items.append("── Vision 非対応（参考）──")
        items.extend(other_models)

    # クラウドモデルも追加
    cloud = get_cloud_model_names()
    if cloud:
        items.append("── Cloud AI（コスト発生・要注意）──")
        items.extend(cloud)

    return items


def get_phase35_candidates(skip_label: str = "（未選択 - スキップ）") -> list[str]:
    """Phase 3.5: [スキップ] + cloudAI登録済みモデル全て"""
    items = [skip_label]
    items.extend(get_cloud_model_names())
    return items


def get_phase4_candidates(skip_label: str = "（未選択 - スキップ）") -> list[str]:
    """Phase 4: [無効] + cloudAI登録済みモデル全て"""
    items = [skip_label]
    items.extend(get_cloud_model_names())
    return items


def get_rag_cloud_candidates() -> list[str]:
    """RAG CloudモデルCombo: cloudAI登録済みモデル全て"""
    return get_cloud_model_names()


def get_rag_local_candidates(ollama_url: str = None) -> list[str]:
    """RAG ローカルモデルCombo: localAIインストール済みモデル全て"""
    return get_ollama_installed_models(ollama_url)


def populate_combo(combo, items: list[str], current_value: str = None):
    """v11.6.0: コンボボックスに候補をセットし、セパレーター（"──"始まり）を選択不可にする"""
    combo.blockSignals(True)
    combo.clear()
    for item in items:
        combo.addItem(item)
        if item.startswith("──") or item.startswith("---"):
            model = combo.model()
            idx = combo.count() - 1
            entry = model.item(idx)
            if entry:
                from PyQt6.QtCore import Qt
                entry.setFlags(entry.flags() & ~Qt.ItemFlag.ItemIsEnabled)
    if current_value:
        idx = combo.findText(current_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.addItem(current_value)
            combo.setCurrentIndex(combo.count() - 1)
    combo.blockSignals(False)
