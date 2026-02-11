"""
Model Presets - Phase 2.7

Project別のモデル設定プリセット管理
"""

import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# 組み込みプリセット定義
BUILTIN_PRESETS = {
    "economy": {
        "name": "economy",
        "display_name": "エコノミー (コスト重視)",
        "description": "コストを抑えた設定。Sonnetを中心に、検証はLocalへ",
        "mapping": {
            "PLAN": "claude-sonnet-4-5",
            "IMPLEMENT": "claude-sonnet-4-5",
            "RESEARCH": "gemini-3-flash",
            "REVIEW": "claude-sonnet-4-5",
            "VERIFY": "local",
            "CHAT": "claude-haiku-4-5",
        }
    },
    "quality": {
        "name": "quality",
        "display_name": "クオリティ (品質重視)",
        "description": "品質を最優先。重要なフェーズはOpusを使用",
        "mapping": {
            "PLAN": "claude-opus-4-5",
            "IMPLEMENT": "claude-sonnet-4-5",
            "RESEARCH": "gemini-3-pro",
            "REVIEW": "claude-opus-4-5",
            "VERIFY": "claude-sonnet-4-5",
            "CHAT": "claude-sonnet-4-5",
        }
    },
    "balanced": {
        "name": "balanced",
        "display_name": "バランス (推奨)",
        "description": "コストと品質のバランス。デフォルト設定",
        "mapping": {
            "PLAN": "claude-opus-4-5",
            "IMPLEMENT": "claude-sonnet-4-5",
            "RESEARCH": "gemini-3-pro",
            "REVIEW": "claude-sonnet-4-5",
            "VERIFY": "local",
            "CHAT": "claude-sonnet-4-5",
        }
    },
    "local_first": {
        "name": "local_first",
        "display_name": "ローカル優先",
        "description": "可能な限りローカルAIを使用。オフライン向け",
        "mapping": {
            "PLAN": "local",
            "IMPLEMENT": "local",
            "RESEARCH": "local",
            "REVIEW": "local",
            "VERIFY": "local",
            "CHAT": "local",
        }
    },
}


@dataclass
class ModelPreset:
    """モデルプリセット"""
    name: str
    display_name: str
    description: str
    mapping: Dict[str, str] = field(default_factory=dict)
    is_builtin: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelPreset':
        return cls(
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            mapping=data.get("mapping", {}),
            is_builtin=data.get("is_builtin", False),
        )


class ModelPresetManager:
    """
    モデルプリセット管理

    プロジェクトごとにプリセットを割り当て可能
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: データディレクトリパス
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.presets_file = self.data_dir / "model_presets.json"
        self.project_presets_file = self.data_dir / "project_model_presets.json"

        # プリセット: 組み込み + カスタム
        self.presets: Dict[str, ModelPreset] = {}
        self._load_builtin_presets()
        self._load_custom_presets()

        # プロジェクト→プリセットのマッピング
        self.project_preset_mapping: Dict[str, str] = {}
        self._load_project_presets()

    def _load_builtin_presets(self):
        """組み込みプリセットを読み込み"""
        for name, config in BUILTIN_PRESETS.items():
            self.presets[name] = ModelPreset(
                name=config["name"],
                display_name=config["display_name"],
                description=config["description"],
                mapping=config["mapping"],
                is_builtin=True,
            )

    def _load_custom_presets(self):
        """カスタムプリセットを読み込み"""
        if not self.presets_file.exists():
            return

        try:
            with open(self.presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for preset_data in data.get("custom_presets", []):
                preset = ModelPreset.from_dict(preset_data)
                preset.is_builtin = False
                self.presets[preset.name] = preset

            logger.info(f"[ModelPresetManager] Loaded custom presets from {self.presets_file}")

        except Exception as e:
            logger.error(f"[ModelPresetManager] Failed to load custom presets: {e}")

    def _load_project_presets(self):
        """プロジェクト→プリセットのマッピングを読み込み"""
        if not self.project_presets_file.exists():
            return

        try:
            with open(self.project_presets_file, "r", encoding="utf-8") as f:
                self.project_preset_mapping = json.load(f)

            logger.info(f"[ModelPresetManager] Loaded project presets: {len(self.project_preset_mapping)} projects")

        except Exception as e:
            logger.error(f"[ModelPresetManager] Failed to load project presets: {e}")

    def save_project_presets(self):
        """プロジェクト→プリセットのマッピングを保存"""
        try:
            with open(self.project_presets_file, "w", encoding="utf-8") as f:
                json.dump(self.project_preset_mapping, f, indent=2, ensure_ascii=False)

            logger.info(f"[ModelPresetManager] Saved project presets")

        except Exception as e:
            logger.error(f"[ModelPresetManager] Failed to save project presets: {e}")

    def save_custom_presets(self):
        """カスタムプリセットを保存"""
        try:
            custom_presets = [
                p.to_dict() for p in self.presets.values()
                if not p.is_builtin
            ]

            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump({"custom_presets": custom_presets}, f, indent=2, ensure_ascii=False)

            logger.info(f"[ModelPresetManager] Saved custom presets")

        except Exception as e:
            logger.error(f"[ModelPresetManager] Failed to save custom presets: {e}")

    def get_preset(self, preset_name: str) -> Optional[ModelPreset]:
        """プリセットを取得"""
        return self.presets.get(preset_name)

    def get_all_presets(self) -> List[ModelPreset]:
        """全プリセットを取得"""
        return list(self.presets.values())

    def add_custom_preset(self, preset: ModelPreset):
        """カスタムプリセットを追加"""
        preset.is_builtin = False
        self.presets[preset.name] = preset
        self.save_custom_presets()
        logger.info(f"[ModelPresetManager] Added custom preset: {preset.name}")

    def remove_custom_preset(self, preset_name: str) -> bool:
        """カスタムプリセットを削除"""
        if preset_name not in self.presets:
            return False

        preset = self.presets[preset_name]
        if preset.is_builtin:
            logger.warning(f"[ModelPresetManager] Cannot remove builtin preset: {preset_name}")
            return False

        del self.presets[preset_name]
        self.save_custom_presets()
        logger.info(f"[ModelPresetManager] Removed custom preset: {preset_name}")
        return True

    def set_project_preset(self, project_id: str, preset_name: str):
        """プロジェクトにプリセットを割り当て"""
        if preset_name not in self.presets:
            logger.warning(f"[ModelPresetManager] Unknown preset: {preset_name}")
            return

        self.project_preset_mapping[project_id] = preset_name
        self.save_project_presets()
        logger.info(f"[ModelPresetManager] Set project {project_id} -> preset {preset_name}")

    def get_project_preset(self, project_id: str) -> Optional[ModelPreset]:
        """プロジェクトのプリセットを取得"""
        preset_name = self.project_preset_mapping.get(project_id)
        if preset_name:
            return self.presets.get(preset_name)
        return None

    def get_project_preset_name(self, project_id: str) -> Optional[str]:
        """プロジェクトのプリセット名を取得"""
        return self.project_preset_mapping.get(project_id)

    def clear_project_preset(self, project_id: str):
        """プロジェクトのプリセット割り当てを解除"""
        if project_id in self.project_preset_mapping:
            del self.project_preset_mapping[project_id]
            self.save_project_presets()
            logger.info(f"[ModelPresetManager] Cleared preset for project {project_id}")

    def get_backend_for_task(
        self,
        project_id: str,
        task_type: str,
    ) -> Optional[str]:
        """
        プロジェクトとタスク種別からBackendを取得

        Args:
            project_id: プロジェクトID
            task_type: タスク種別

        Returns:
            Backend名 or None (プリセット未設定時)
        """
        preset = self.get_project_preset(project_id)
        if preset:
            return preset.mapping.get(task_type)
        return None


# グローバルインスタンス
_preset_manager: Optional[ModelPresetManager] = None


def get_preset_manager() -> ModelPresetManager:
    """ModelPresetManagerのグローバルインスタンスを取得"""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = ModelPresetManager()
    return _preset_manager
