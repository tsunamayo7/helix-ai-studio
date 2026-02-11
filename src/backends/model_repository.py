"""
Model Repository - Phase B

ドメイン別 Local モデルのリスト管理、バージョン/メタデータ保存

Features:
- 分野別 Local モデルのリスト管理
- バージョン/メタデータ保存
- モデルの検索・フィルタリング
"""

import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ModelDomain(Enum):
    """モデルのドメイン（分野）"""
    GENERAL = "general"           # 汎用
    CODING = "coding"             # コーディング特化
    CREATIVE = "creative"         # 創作・文章生成
    ANALYSIS = "analysis"         # 分析・推論
    MULTILINGUAL = "multilingual" # 多言語対応
    VISION = "vision"             # 画像認識
    EMBEDDING = "embedding"       # 埋め込み生成


class ModelSource(Enum):
    """モデルのソース"""
    LOCAL = "local"               # ローカル（Ollama, LM Studio等）
    CLOUD_CLAUDE = "cloud_claude" # Claude API
    CLOUD_GEMINI = "cloud_gemini" # Gemini API
    CLOUD_OPENAI = "cloud_openai" # OpenAI API


@dataclass
class ModelMetadata:
    """モデルのメタデータ"""
    model_id: str                 # 一意の識別子
    name: str                     # 表示名
    source: str                   # ModelSource値
    domain: str                   # ModelDomain値
    version: str = "1.0.0"        # バージョン
    description: str = ""         # 説明
    parameters: str = ""          # パラメータ数（例: "7B", "70B"）
    context_length: int = 4096    # コンテキスト長
    quantization: str = ""        # 量子化形式（例: "Q4_K_M"）
    endpoint: str = ""            # エンドポイントURL（ローカル用）
    api_model_id: str = ""        # API用モデルID
    cost_per_1k_input: float = 0.0   # 入力1Kトークンあたりコスト（USD）
    cost_per_1k_output: float = 0.0  # 出力1Kトークンあたりコスト（USD）
    tags: List[str] = field(default_factory=list)  # タグ
    created_at: str = ""          # 作成日時
    updated_at: str = ""          # 更新日時
    is_active: bool = True        # 有効フラグ
    priority: int = 0             # 優先度（高いほど優先）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        return cls(
            model_id=data.get("model_id", ""),
            name=data.get("name", ""),
            source=data.get("source", ModelSource.LOCAL.value),
            domain=data.get("domain", ModelDomain.GENERAL.value),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            parameters=data.get("parameters", ""),
            context_length=data.get("context_length", 4096),
            quantization=data.get("quantization", ""),
            endpoint=data.get("endpoint", ""),
            api_model_id=data.get("api_model_id", ""),
            cost_per_1k_input=data.get("cost_per_1k_input", 0.0),
            cost_per_1k_output=data.get("cost_per_1k_output", 0.0),
            tags=data.get("tags", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            is_active=data.get("is_active", True),
            priority=data.get("priority", 0),
        )


class ModelRepository:
    """
    Model Repository

    分野別モデルのリスト管理とバージョン/メタデータ保存を提供

    機能:
    - モデルの登録・更新・削除
    - ドメイン別・ソース別検索
    - バージョン管理
    - 推奨モデルの取得
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.repo_file = self.data_dir / "model_repository.json"
        self._models: Dict[str, ModelMetadata] = {}

        # ログ設定
        self._setup_logging()

        # モデル読み込み
        self._load_repository()

        # デフォルトモデルを登録
        self._register_default_models()

        logger.info(f"[ModelRepository] Initialized with {len(self._models)} models")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "model_repository.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)

    def _load_repository(self):
        """リポジトリを読み込み"""
        if self.repo_file.exists():
            try:
                with open(self.repo_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for model_data in data.get("models", []):
                        model = ModelMetadata.from_dict(model_data)
                        self._models[model.model_id] = model
                logger.info(f"[ModelRepository] Loaded {len(self._models)} models from file")
            except Exception as e:
                logger.error(f"[ModelRepository] Failed to load repository: {e}")

    def _save_repository(self):
        """リポジトリを保存"""
        try:
            data = {
                "version": "1.0.0",
                "updated_at": datetime.now().isoformat(),
                "models": [m.to_dict() for m in self._models.values()],
            }
            with open(self.repo_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[ModelRepository] Saved {len(self._models)} models")
        except Exception as e:
            logger.error(f"[ModelRepository] Failed to save repository: {e}")

    def _register_default_models(self):
        """デフォルトモデルを登録"""
        default_models = [
            # Claude モデル
            ModelMetadata(
                model_id="claude-sonnet-4.5",
                name="Claude Sonnet 4.5",
                source=ModelSource.CLOUD_CLAUDE.value,
                domain=ModelDomain.CODING.value,
                version="4.5",
                description="コーディング・エージェント作業に最適。高いコード品質と推論能力",
                api_model_id="claude-sonnet-4-5-20250514",
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
                context_length=200000,
                tags=["coding", "recommended", "agent"],
                priority=90,
            ),
            ModelMetadata(
                model_id="claude-opus-4.5",
                name="Claude Opus",
                source=ModelSource.CLOUD_CLAUDE.value,
                domain=ModelDomain.ANALYSIS.value,
                version="4.5",
                description="最高性能。複雑な推論・高度なタスク向け",
                api_model_id="claude-opus-4-5-20250514",
                cost_per_1k_input=0.015,
                cost_per_1k_output=0.075,
                context_length=200000,
                tags=["analysis", "complex", "high-performance"],
                priority=100,
            ),
            ModelMetadata(
                model_id="claude-haiku-4.5",
                name="Claude Haiku 4.5",
                source=ModelSource.CLOUD_CLAUDE.value,
                domain=ModelDomain.GENERAL.value,
                version="4.5",
                description="高速・低コスト。Sonnet 4相当の性能",
                api_model_id="claude-haiku-4-5-20250514",
                cost_per_1k_input=0.00025,
                cost_per_1k_output=0.00125,
                context_length=200000,
                tags=["fast", "low-cost"],
                priority=70,
            ),
            # Gemini モデル
            ModelMetadata(
                model_id="gemini-3-pro",
                name="Gemini 3 Pro",
                source=ModelSource.CLOUD_GEMINI.value,
                domain=ModelDomain.VISION.value,
                version="3.0",
                description="最高性能の推論とマルチモーダル理解",
                api_model_id="gemini-3-pro",
                cost_per_1k_input=0.00125,
                cost_per_1k_output=0.005,
                context_length=1000000,
                tags=["multimodal", "vision", "recommended"],
                priority=85,
            ),
            ModelMetadata(
                model_id="gemini-3-flash",
                name="Gemini 3 Flash",
                source=ModelSource.CLOUD_GEMINI.value,
                domain=ModelDomain.GENERAL.value,
                version="3.0",
                description="Pro級の推論をFlash速度で実現",
                api_model_id="gemini-3-flash",
                cost_per_1k_input=0.000075,
                cost_per_1k_output=0.0003,
                context_length=1000000,
                tags=["fast", "low-cost", "multimodal"],
                priority=75,
            ),
            # Local モデルテンプレート
            ModelMetadata(
                model_id="local-default",
                name="Local LLM (Default)",
                source=ModelSource.LOCAL.value,
                domain=ModelDomain.GENERAL.value,
                version="1.0.0",
                description="ローカルで動作するLLM（Ollama/LM Studio等）",
                endpoint="http://127.0.0.1:8000",
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                tags=["local", "offline", "free"],
                priority=50,
            ),
        ]

        for model in default_models:
            if model.model_id not in self._models:
                model.created_at = datetime.now().isoformat()
                model.updated_at = datetime.now().isoformat()
                self._models[model.model_id] = model

        self._save_repository()

    # ========================================
    # CRUD操作
    # ========================================

    def register_model(self, model: ModelMetadata) -> bool:
        """
        モデルを登録

        Args:
            model: モデルメタデータ

        Returns:
            成功したかどうか
        """
        if not model.model_id:
            logger.error("[ModelRepository] Model ID is required")
            return False

        now = datetime.now().isoformat()
        model.created_at = now
        model.updated_at = now

        self._models[model.model_id] = model
        self._save_repository()

        logger.info(f"[ModelRepository] Registered model: {model.model_id}")
        return True

    def update_model(self, model_id: str, updates: Dict[str, Any]) -> bool:
        """
        モデルを更新

        Args:
            model_id: モデルID
            updates: 更新内容

        Returns:
            成功したかどうか
        """
        if model_id not in self._models:
            logger.error(f"[ModelRepository] Model not found: {model_id}")
            return False

        model = self._models[model_id]

        for key, value in updates.items():
            if hasattr(model, key):
                setattr(model, key, value)

        model.updated_at = datetime.now().isoformat()
        self._save_repository()

        logger.info(f"[ModelRepository] Updated model: {model_id}")
        return True

    def delete_model(self, model_id: str) -> bool:
        """
        モデルを削除

        Args:
            model_id: モデルID

        Returns:
            成功したかどうか
        """
        if model_id not in self._models:
            logger.error(f"[ModelRepository] Model not found: {model_id}")
            return False

        del self._models[model_id]
        self._save_repository()

        logger.info(f"[ModelRepository] Deleted model: {model_id}")
        return True

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """
        モデルを取得

        Args:
            model_id: モデルID

        Returns:
            モデルメタデータ（存在しない場合はNone）
        """
        return self._models.get(model_id)

    # ========================================
    # 検索・フィルタリング
    # ========================================

    def list_models(
        self,
        domain: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[ModelMetadata]:
        """
        モデル一覧を取得

        Args:
            domain: ドメインでフィルタ
            source: ソースでフィルタ
            tags: タグでフィルタ（いずれかを含む）
            active_only: アクティブなモデルのみ

        Returns:
            モデルのリスト（優先度順）
        """
        models = list(self._models.values())

        if active_only:
            models = [m for m in models if m.is_active]

        if domain:
            models = [m for m in models if m.domain == domain]

        if source:
            models = [m for m in models if m.source == source]

        if tags:
            models = [m for m in models if any(t in m.tags for t in tags)]

        # 優先度順にソート
        models.sort(key=lambda m: m.priority, reverse=True)

        return models

    def get_local_models(self) -> List[ModelMetadata]:
        """ローカルモデル一覧を取得"""
        return self.list_models(source=ModelSource.LOCAL.value)

    def get_cloud_models(self) -> List[ModelMetadata]:
        """クラウドモデル一覧を取得"""
        return [
            m for m in self._models.values()
            if m.source in [
                ModelSource.CLOUD_CLAUDE.value,
                ModelSource.CLOUD_GEMINI.value,
                ModelSource.CLOUD_OPENAI.value,
            ]
        ]

    def get_models_by_domain(self, domain: ModelDomain) -> List[ModelMetadata]:
        """ドメイン別モデル一覧を取得"""
        return self.list_models(domain=domain.value)

    def get_recommended_model(
        self,
        domain: Optional[str] = None,
        prefer_local: bool = False,
        max_cost: Optional[float] = None,
    ) -> Optional[ModelMetadata]:
        """
        推奨モデルを取得

        Args:
            domain: 対象ドメイン
            prefer_local: ローカルを優先
            max_cost: 最大コスト（USD/1K tokens）

        Returns:
            推奨モデル
        """
        models = self.list_models(domain=domain)

        if prefer_local:
            local_models = [m for m in models if m.source == ModelSource.LOCAL.value]
            if local_models:
                return local_models[0]

        if max_cost is not None:
            models = [m for m in models if m.cost_per_1k_input <= max_cost]

        return models[0] if models else None

    def search_models(self, query: str) -> List[ModelMetadata]:
        """
        モデルを検索

        Args:
            query: 検索クエリ

        Returns:
            マッチしたモデルのリスト
        """
        query_lower = query.lower()
        results = []

        for model in self._models.values():
            if (
                query_lower in model.name.lower() or
                query_lower in model.description.lower() or
                any(query_lower in tag.lower() for tag in model.tags)
            ):
                results.append(model)

        results.sort(key=lambda m: m.priority, reverse=True)
        return results


# ========================================
# グローバルインスタンス
# ========================================

_model_repository: Optional[ModelRepository] = None


def get_model_repository() -> ModelRepository:
    """ModelRepositoryのグローバルインスタンスを取得"""
    global _model_repository
    if _model_repository is None:
        _model_repository = ModelRepository()
    return _model_repository
