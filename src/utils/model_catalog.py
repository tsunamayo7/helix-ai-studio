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


def normalize_model_id(raw_model_id: str) -> str:
    """model_id からCLIコマンド部分を除去し、純粋なモデルIDを返す。

    cloud_models.json で CLI コマンドが model_id に埋め込まれている場合に対応:
      "codex -m gpt-5.3-codex"           → "gpt-5.3-codex"
      "claude --model claude-sonnet-4-6"  → "claude-sonnet-4-6"
      "gemini-3-flash-preview"            → "gemini-3-flash-preview"（変更なし）
    """
    if not raw_model_id:
        return raw_model_id
    parts = raw_model_id.split()
    if len(parts) == 1:
        return raw_model_id
    # "-m" or "--model" フラグの後の値を抽出
    for i, p in enumerate(parts):
        if p in ("-m", "--model") and i + 1 < len(parts):
            return parts[i + 1]
    # CLIコマンド名が先頭にある場合（"codex ..." / "claude ..."）
    cli_prefixes = ("codex", "claude", "gemini")
    if parts[0] in cli_prefixes:
        return parts[-1]
    return raw_model_id


def _infer_family(provider: str) -> str:
    """provider 文字列から family を推定"""
    if "anthropic" in provider:
        return "claude"
    elif "openai" in provider:
        return "gpt"
    elif "google" in provider:
        return "gemini"
    return "unknown"


def get_cloud_models() -> list[dict]:
    """cloud_models.json からクラウドモデル一覧を取得（v2.0スキーマ補完付き）"""
    try:
        if CLOUD_MODELS_PATH.exists():
            with open(CLOUD_MODELS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            models = data.get("models", [])
            for m in models:
                m.setdefault("display_name", m.get("name", ""))
                m.setdefault("family", _infer_family(m.get("provider", "")))
                m.setdefault("transport", "api" if "_api" in m.get("provider", "") else "cli")
                m.setdefault("capabilities", {})
                m.setdefault("deprecated", False)
            return models
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


def get_phase2_role_candidates(
    role: str,
    ollama_url: str = None,
    skip_label: str = "(未選択 - スキップ)"
) -> list[str]:
    """v12.7.2: Phase 2 role-based 候補取得。

    各モデルを supports_role() で判定し、推奨/参考に分類する。
    vision ロールは非対応モデルを一切表示しない（厳格フィルタ）。
    Cloud AI も Ollama も同一の supports_role() で判定する。
    """
    from src.utils.model_capabilities import supports_role as _supports_role

    url = ollama_url or OLLAMA_DEFAULT_URL
    items = [skip_label]

    # --- Ollama モデル ---
    local_recommended = []
    local_reference = []

    try:
        import httpx
        resp = httpx.get(f"{url}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
        else:
            models = []
    except Exception:
        models = []

    if role == "vision":
        # vision: Ollama /api/show で capabilities を確認（既存互換）
        for name in models:
            try:
                import httpx as _httpx
                show_resp = _httpx.post(f"{url}/api/show", json={"name": name}, timeout=2)
                if show_resp.status_code == 200:
                    caps = show_resp.json().get("capabilities", [])
                    if "vision" in caps:
                        local_recommended.append(name)
                    # vision 非対応は表示しない（厳格）
            except Exception:
                pass
    else:
        # vision 以外: model_capabilities で判定
        for name in models:
            # Ollama /api/show で vision capability を取得して上書き
            ollama_vision = False
            if role == "vision":  # ここには到達しないが安全のため
                try:
                    import httpx as _httpx
                    show_resp = _httpx.post(f"{url}/api/show", json={"name": name}, timeout=2)
                    if show_resp.status_code == 200:
                        ollama_vision = "vision" in show_resp.json().get("capabilities", [])
                except Exception:
                    pass

            if _supports_role(name, role):
                local_recommended.append(name)
            else:
                local_reference.append(name)

    # --- Cloud モデル（同一の supports_role で判定）---
    cloud_recommended = []
    cloud_reference = []

    for m in get_cloud_models():
        model_id = normalize_model_id(m.get("model_id", ""))
        display = m.get("name", model_id)
        if not model_id:
            continue
        if _supports_role(model_id, role):
            cloud_recommended.append(display)
        elif role != "vision":
            # vision 非対応 Cloud モデルは表示しない（厳格）
            cloud_reference.append(display)

    # --- リスト構築 ---
    if role == "vision":
        if local_recommended:
            items.append("── 対応モデル（ローカル）──")
            items.extend(local_recommended)
        if cloud_recommended:
            items.append("── 対応モデル（Cloud AI・コスト発生）──")
            items.extend(cloud_recommended)
    else:
        if local_recommended:
            items.append("── 推奨（ローカル）──")
            items.extend(local_recommended)
        if local_reference:
            items.append("── 参考（ローカル）──")
            items.extend(local_reference)
        if cloud_recommended:
            items.append("── 推奨（Cloud AI・コスト発生）──")
            items.extend(cloud_recommended)
        if cloud_reference:
            items.append("── 参考（Cloud AI）──")
            items.extend(cloud_reference)

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
