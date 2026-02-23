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


def get_phase13_candidates(skip_label: str = "") -> list[str]:
    """Phase 1/3: cloudAI登録済みモデル全て"""
    items = []
    if skip_label:
        items.append(skip_label)
    items.extend(get_cloud_model_names())
    return items


def get_phase2_candidates(ollama_url: str = None,
                          skip_label: str = "(未選択 - スキップ)") -> list[str]:
    """Phase 2: [スキップ] + localAIモデル + cloudAIモデル"""
    items = [skip_label]
    local = get_ollama_installed_models(ollama_url)
    if local:
        items.extend(local)
    cloud = get_cloud_model_names()
    if cloud:
        items.append("--- Cloud AI ---")
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
    """コンボボックスに候補をセットし、現在値を復元する汎用関数"""
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(items)
    if current_value:
        idx = combo.findText(current_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # 現在値が候補にない場合は追加して選択
            combo.addItem(current_value)
            combo.setCurrentIndex(combo.count() - 1)
    combo.blockSignals(False)
