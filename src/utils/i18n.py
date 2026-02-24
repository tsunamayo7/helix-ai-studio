"""
Helix AI Studio -- i18n (Internationalization)
Desktop (PyQt6) and Web backend share this module.

Usage:
    from src.utils.i18n import t, set_language, get_language, init_language

    label.setText(t('settings.save'))
    set_language('en')
"""

import json
from pathlib import Path
from typing import Optional

_translations = {}
_current_lang = 'ja'
_app_root = Path(__file__).parent.parent.parent
_i18n_dir = _app_root / 'i18n'


def _load_translations():
    """Load translation files from i18n/ directory."""
    global _translations
    for lang_file in _i18n_dir.glob('*.json'):
        lang_code = lang_file.stem  # 'ja', 'en'
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                _translations[lang_code] = json.load(f)
        except Exception as e:
            print(f"[i18n] Failed to load {lang_file}: {e}")


def _resolve(obj: dict, path: str):
    """Resolve nested key: 'settings.save' -> value"""
    keys = path.split('.')
    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current if isinstance(current, (str, list, dict)) else None


def t(key: str, **params) -> str:
    """Resolve translation key. Falls back to Japanese, then key name.

    Args:
        key: Dot-separated translation key (e.g. 'settings.claudeModel.title')
        **params: Placeholder substitutions (e.g. count=3)

    Returns:
        Translated text
    """
    if not _translations:
        _load_translations()

    # Current language -> Japanese fallback -> key name
    text = _resolve(_translations.get(_current_lang, {}), key)
    if text is None:
        text = _resolve(_translations.get('ja', {}), key)
    if text is None:
        return key

    # Lists (e.g. header arrays) and dicts (e.g. gpuTimeRanges) are returned as-is
    if isinstance(text, (list, dict)):
        return text

    # {count}, {name} placeholder substitution
    for k, v in params.items():
        text = text.replace(f'{{{k}}}', str(v))
    return text


def set_language(lang: str):
    """Switch language."""
    global _current_lang
    if lang in ('ja', 'en'):
        _current_lang = lang
        _save_language_preference(lang)


def get_language() -> str:
    """Get current language."""
    return _current_lang


def init_language():
    """Load language preference at startup."""
    global _current_lang
    _load_translations()
    try:
        gs_path = _app_root / 'config' / 'general_settings.json'
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
            _current_lang = gs.get('language', 'ja')
    except Exception:
        pass


def _save_language_preference(lang: str):
    """Save language preference to general_settings.json."""
    try:
        gs_path = _app_root / 'config' / 'general_settings.json'
        gs = {}
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
        gs['language'] = lang
        gs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gs_path, 'w', encoding='utf-8') as f:
            json.dump(gs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[i18n] Failed to save language: {e}")
