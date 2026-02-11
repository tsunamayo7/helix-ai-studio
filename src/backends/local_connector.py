"""
Local Connector - Phase 3.5 (v2.4.0 Enhanced)

ローカルLLM (Ollama, LM Studio など) への接続インターフェース

v2.4.0 機能追加:
- モデル一覧取得 (list_models)
- ストリーミングレスポンス対応 (generate_stream)
- 構造化出力対応 (generate_structured)
- 推奨モデルプリセット
- 詳細な生成オプション (temperature, top_p, context_length)
- Ollama API完全対応

参照:
- https://github.com/ollama/ollama/blob/main/docs/api.md
- https://docs.ollama.com/api/openai-compatibility
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Generator, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# エンドポイントプリセット (v2.5.0)
# ============================================
ENDPOINT_PRESETS = {
    "ollama": {
        "name": "Ollama (ローカル)",
        "endpoint": "http://localhost:11434",
        "description": "ローカルでOllamaを実行している場合の標準エンドポイント",
        "models": ["llama3.2:8b", "qwen2.5:14b", "deepseek-coder:6.7b"],
    },
    "lm_studio": {
        "name": "LM Studio",
        "endpoint": "http://localhost:1234",
        "description": "LM Studioのデフォルトエンドポイント (OpenAI互換)",
        "models": [],
    },
    "trinity": {
        "name": "Trinity Exoskeleton",
        "endpoint": "http://localhost:8000",
        "description": "Trinity Exoskeletonのハイブリッドオーケストレーター (OpenAI互換)",
        "models": ["trinity-auto", "trinity-pm", "trinity-engineer", "trinity-advisor"],
        "api_key": "trinity-local-key",
    },
    "ollama_cloud": {
        "name": "Ollama Cloud",
        "endpoint": "https://api.ollama.com",
        "description": "Ollama CloudサービスのエンドポイントClaude Code連携可能）",
        "models": ["glm-4.7:cloud", "minimax-m2.1:cloud"],
    },
}

# ============================================
# 推奨モデルプリセット (2025-2026)
# ============================================
RECOMMENDED_MODELS = {
    "general": [
        {"name": "llama3.2:8b", "description": "Meta Llama 3.2 8B - バランス良好、汎用向け", "vram": "8GB"},
        {"name": "qwen2.5:14b", "description": "Qwen 2.5 14B - 高性能、多言語対応", "vram": "12GB"},
        {"name": "deepseek-r1:14b", "description": "DeepSeek R1 14B - 高度な推論能力", "vram": "12GB"},
        {"name": "mistral:7b", "description": "Mistral 7B - 軽量で高速", "vram": "6GB"},
    ],
    "coding": [
        {"name": "deepseek-coder:6.7b", "description": "DeepSeek Coder - 87言語対応、コード特化", "vram": "6GB"},
        {"name": "qwen2.5-coder:7b", "description": "Qwen 2.5 Coder - GPT-4o相当のコード修復", "vram": "6GB"},
        {"name": "codellama:13b", "description": "Code Llama 13B - コード生成・補完特化", "vram": "10GB"},
        {"name": "starcoder2:7b", "description": "StarCoder2 7B - 多言語コード生成", "vram": "6GB"},
    ],
    "fast": [
        {"name": "llama3.2:1b", "description": "Llama 3.2 1B - 超軽量、即時応答", "vram": "2GB"},
        {"name": "qwen2.5:0.5b", "description": "Qwen 2.5 0.5B - 最小モデル", "vram": "1GB"},
        {"name": "phi3:mini", "description": "Phi-3 Mini - Microsoft軽量モデル", "vram": "3GB"},
        {"name": "gemma2:2b", "description": "Gemma 2 2B - Google軽量モデル", "vram": "2GB"},
    ],
    "japanese": [
        {"name": "elyza:jp-7b", "description": "ELYZA Japanese 7B - 日本語特化", "vram": "6GB"},
        {"name": "llm-jp:13b", "description": "LLM-JP 13B - 日本語LLM研究成果", "vram": "10GB"},
    ],
}


class ConnectionStatus(Enum):
    """接続ステータス"""
    NOT_CONFIGURED = "not_configured"
    NOT_CONNECTED = "not_connected"
    HEALTHCHECK_FAILED = "healthcheck_failed"
    CONNECTED = "connected"


@dataclass
class LocalConnectorConfig:
    """ローカルコネクタ設定"""
    endpoint: str = ""
    model_name: str = ""
    timeout_seconds: int = 60  # v2.4.0: デフォルト60秒に延長
    max_tokens: int = 4096
    # v2.4.0: 追加オプション
    temperature: float = 0.7
    top_p: float = 0.9
    context_length: int = 4096
    streaming_enabled: bool = True  # ストリーミングデフォルトON

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocalConnectorConfig':
        return cls(
            endpoint=data.get("endpoint", ""),
            model_name=data.get("model_name", ""),
            timeout_seconds=data.get("timeout_seconds", 60),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            top_p=data.get("top_p", 0.9),
            context_length=data.get("context_length", 4096),
            streaming_enabled=data.get("streaming_enabled", True),
        )


@dataclass
class OllamaModel:
    """Ollamaモデル情報"""
    name: str
    size: int = 0  # bytes
    modified_at: str = ""
    digest: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def size_gb(self) -> float:
        """サイズをGBで返す"""
        return self.size / (1024 ** 3) if self.size else 0.0

    @property
    def parameter_size(self) -> str:
        """パラメータサイズを返す (例: 7B, 13B)"""
        return self.details.get("parameter_size", "不明")


class LocalConnector:
    """
    ローカルLLMコネクタ (v2.4.0 Enhanced)

    Features:
    - healthcheck() - 接続確認
    - generate(prompt, options) - テキスト生成
    - generate_stream(prompt, options, callback) - ストリーミング生成
    - generate_structured(prompt, schema) - 構造化出力
    - list_models() - モデル一覧取得
    - pull_model(model_name) - モデルダウンロード
    - get_recommended_models(category) - 推奨モデル取得
    """

    def __init__(self, config: Optional[LocalConnectorConfig] = None, data_dir: Optional[str] = None):
        """
        Args:
            config: 接続設定
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.config_file = self.data_dir / "local_connector_config.json"
        self.config = config or LocalConnectorConfig()

        self._status = ConnectionStatus.NOT_CONFIGURED
        self._last_error: Optional[str] = None
        self._cached_models: List[OllamaModel] = []  # v2.4.0: モデルキャッシュ
        self._api_type: Optional[str] = None  # "ollama" or "openai_compatible"

        # 設定を読み込み
        self._load_config()

    def _load_config(self):
        """設定を読み込み"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = LocalConnectorConfig.from_dict(data)

                if self.config.endpoint:
                    self._status = ConnectionStatus.NOT_CONNECTED
                else:
                    self._status = ConnectionStatus.NOT_CONFIGURED

                logger.info(f"[LocalConnector] Loaded config: {self.config.endpoint}")

            except Exception as e:
                logger.error(f"[LocalConnector] Failed to load config: {e}")

    def save_config(self):
        """設定を保存"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"[LocalConnector] Saved config")
        except Exception as e:
            logger.error(f"[LocalConnector] Failed to save config: {e}")

    def set_endpoint(self, endpoint: str, model_name: str = ""):
        """エンドポイントを設定"""
        self.config.endpoint = endpoint.rstrip("/")
        if model_name:
            self.config.model_name = model_name

        if endpoint:
            self._status = ConnectionStatus.NOT_CONNECTED
        else:
            self._status = ConnectionStatus.NOT_CONFIGURED

        self.save_config()
        logger.info(f"[LocalConnector] Endpoint set: {endpoint}")

    def healthcheck(self) -> tuple[bool, str]:
        """
        ヘルスチェック

        Returns:
            (success, message): 成功/失敗とメッセージ
        """
        if not self.config.endpoint:
            self._status = ConnectionStatus.NOT_CONFIGURED
            self._last_error = "エンドポイントが設定されていません"
            return False, self._last_error

        # 複数のヘルスチェックエンドポイントを試す
        health_paths = [
            "/health",
            "/api/health",
            "/v1/models",
            "/api/tags",  # Ollama
            "",  # ルート
        ]

        for path in health_paths:
            url = f"{self.config.endpoint}{path}"
            try:
                req = urllib.request.Request(url, method='GET')
                req.add_header('Accept', 'application/json')
                req.add_header('User-Agent', 'HelixAIStudio/1.0')

                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        self._status = ConnectionStatus.CONNECTED
                        self._last_error = None
                        logger.info(f"[LocalConnector] Healthcheck OK: {url}")
                        return True, f"接続成功: {self.config.endpoint}"

            except urllib.error.URLError as e:
                continue
            except Exception as e:
                continue

        # すべて失敗
        self._status = ConnectionStatus.HEALTHCHECK_FAILED
        self._last_error = f"エンドポイント {self.config.endpoint} に接続できません"
        logger.warning(f"[LocalConnector] Healthcheck failed: {self._last_error}")
        return False, self._last_error

    def generate(
        self,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str, Dict[str, Any]]:
        """
        テキスト生成

        Args:
            prompt: 入力プロンプト
            options: 生成オプション

        Returns:
            (success, response_text, metadata)
        """
        if not self.config.endpoint:
            return False, "エンドポイントが設定されていません", {"error_type": "NotConnectedError"}

        if self._status == ConnectionStatus.NOT_CONNECTED:
            # まずヘルスチェック
            ok, msg = self.healthcheck()
            if not ok:
                return False, msg, {"error_type": "HealthcheckFailed"}

        # リクエストを構築
        options = options or {}
        max_tokens = options.get("max_tokens", self.config.max_tokens)
        model = options.get("model", self.config.model_name)

        # OpenAI互換APIを想定
        request_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": options.get("temperature", 0.7),
        }

        # 複数のAPIエンドポイントを試す
        api_paths = [
            "/v1/chat/completions",  # OpenAI互換
            "/api/chat",              # Ollama
            "/api/generate",          # Ollama (legacy)
        ]

        for path in api_paths:
            url = f"{self.config.endpoint}{path}"
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(request_body).encode('utf-8'),
                    method='POST'
                )
                req.add_header('Content-Type', 'application/json')
                req.add_header('Accept', 'application/json')

                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                    if response.status == 200:
                        response_data = json.loads(response.read().decode('utf-8'))

                        # OpenAI形式
                        if "choices" in response_data:
                            text = response_data["choices"][0].get("message", {}).get("content", "")
                            return True, text, {"api": path, "model": model}

                        # Ollama形式
                        if "response" in response_data:
                            return True, response_data["response"], {"api": path, "model": model}

                        # 不明な形式
                        return True, str(response_data), {"api": path, "model": model}

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # このパスは存在しない
                self._last_error = f"HTTP {e.code}: {e.reason}"
                logger.error(f"[LocalConnector] HTTP error: {self._last_error}")
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"[LocalConnector] Generate error: {e}")

        return False, f"生成に失敗しました: {self._last_error}", {"error_type": "GenerationFailed"}

    # ========================================
    # v2.4.0: 新機能
    # ========================================

    def list_models(self) -> tuple[bool, List[OllamaModel], str]:
        """
        利用可能なモデル一覧を取得

        Returns:
            (success, models, message)
        """
        if not self.config.endpoint:
            return False, [], "エンドポイントが設定されていません"

        # Ollama API: GET /api/tags
        api_paths = [
            "/api/tags",      # Ollama
            "/v1/models",     # OpenAI互換
        ]

        for path in api_paths:
            url = f"{self.config.endpoint}{path}"
            try:
                req = urllib.request.Request(url, method='GET')
                req.add_header('Accept', 'application/json')
                req.add_header('User-Agent', 'HelixAIStudio/2.4.0')

                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))

                        models = []
                        # Ollama形式
                        if "models" in data:
                            self._api_type = "ollama"
                            for m in data["models"]:
                                models.append(OllamaModel(
                                    name=m.get("name", ""),
                                    size=m.get("size", 0),
                                    modified_at=m.get("modified_at", ""),
                                    digest=m.get("digest", ""),
                                    details=m.get("details", {}),
                                ))

                        # OpenAI互換形式
                        elif "data" in data:
                            self._api_type = "openai_compatible"
                            for m in data["data"]:
                                models.append(OllamaModel(
                                    name=m.get("id", ""),
                                    details={"owned_by": m.get("owned_by", "")},
                                ))

                        self._cached_models = models
                        logger.info(f"[LocalConnector] Found {len(models)} models")
                        return True, models, f"{len(models)}個のモデルが見つかりました"

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                self._last_error = f"HTTP {e.code}: {e.reason}"
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"[LocalConnector] list_models error: {e}")

        return False, [], f"モデル一覧の取得に失敗: {self._last_error}"

    def get_cached_models(self) -> List[OllamaModel]:
        """キャッシュされたモデル一覧を返す"""
        return self._cached_models

    def generate_stream(
        self,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str, Dict[str, Any]]:
        """
        ストリーミングテキスト生成

        Args:
            prompt: 入力プロンプト
            options: 生成オプション
            on_token: トークン受信時のコールバック

        Returns:
            (success, full_response, metadata)
        """
        if not self.config.endpoint:
            return False, "エンドポイントが設定されていません", {"error_type": "NotConnectedError"}

        options = options or {}
        model = options.get("model", self.config.model_name)

        # Ollama /api/chat (streaming)
        request_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": options.get("temperature", self.config.temperature),
                "top_p": options.get("top_p", self.config.top_p),
                "num_ctx": options.get("context_length", self.config.context_length),
            }
        }

        url = f"{self.config.endpoint}/api/chat"
        full_response = ""

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_body).encode('utf-8'),
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                for line in response:
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            if "message" in chunk:
                                content = chunk["message"].get("content", "")
                                full_response += content
                                if on_token:
                                    on_token(content)

                            # 完了チェック
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

            return True, full_response, {"api": "/api/chat", "model": model, "streaming": True}

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[LocalConnector] Stream error: {e}")
            return False, f"ストリーミング生成に失敗: {e}", {"error_type": "StreamingFailed"}

    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Dict[str, Any], str]:
        """
        構造化出力（JSON Schema制約付き生成）

        Args:
            prompt: 入力プロンプト
            schema: JSON Schema
            options: 生成オプション

        Returns:
            (success, parsed_data, raw_response)
        """
        if not self.config.endpoint:
            return False, {}, "エンドポイントが設定されていません"

        options = options or {}
        model = options.get("model", self.config.model_name)

        # Ollama format parameter
        request_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": schema,  # JSON Schema
            "stream": False,
            "options": {
                "temperature": 0,  # 構造化出力は低温推奨
            }
        }

        url = f"{self.config.endpoint}/api/chat"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_body).encode('utf-8'),
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode('utf-8'))
                content = data.get("message", {}).get("content", "")

                try:
                    parsed = json.loads(content)
                    return True, parsed, content
                except json.JSONDecodeError:
                    return False, {}, f"JSONパースエラー: {content[:100]}"

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[LocalConnector] Structured output error: {e}")
            return False, {}, f"構造化出力に失敗: {e}"

    def pull_model(
        self,
        model_name: str,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> tuple[bool, str]:
        """
        モデルをダウンロード (Ollama pull相当)

        Args:
            model_name: モデル名
            on_progress: 進捗コールバック (status, percent)

        Returns:
            (success, message)
        """
        if not self.config.endpoint:
            return False, "エンドポイントが設定されていません"

        url = f"{self.config.endpoint}/api/pull"
        request_body = {"name": model_name, "stream": True}

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_body).encode('utf-8'),
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=600) as response:  # 10分タイムアウト
                for line in response:
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            status = chunk.get("status", "")
                            total = chunk.get("total", 0)
                            completed = chunk.get("completed", 0)

                            if on_progress and total > 0:
                                percent = (completed / total) * 100
                                on_progress(status, percent)
                            elif on_progress:
                                on_progress(status, 0)

                        except json.JSONDecodeError:
                            continue

            logger.info(f"[LocalConnector] Model pulled: {model_name}")
            return True, f"モデル '{model_name}' のダウンロードが完了しました"

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[LocalConnector] Pull error: {e}")
            return False, f"モデルダウンロードに失敗: {e}"

    def delete_model(self, model_name: str) -> tuple[bool, str]:
        """
        モデルを削除

        Args:
            model_name: モデル名

        Returns:
            (success, message)
        """
        if not self.config.endpoint:
            return False, "エンドポイントが設定されていません"

        url = f"{self.config.endpoint}/api/delete"
        request_body = {"name": model_name}

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_body).encode('utf-8'),
                method='DELETE'
            )
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    logger.info(f"[LocalConnector] Model deleted: {model_name}")
                    return True, f"モデル '{model_name}' を削除しました"

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[LocalConnector] Delete error: {e}")
            return False, f"モデル削除に失敗: {e}"

        return False, "削除に失敗しました"

    @staticmethod
    def get_recommended_models(category: str = "general") -> List[Dict[str, str]]:
        """
        推奨モデル一覧を取得

        Args:
            category: カテゴリ ("general", "coding", "fast", "japanese")

        Returns:
            推奨モデルのリスト
        """
        return RECOMMENDED_MODELS.get(category, RECOMMENDED_MODELS["general"])

    @staticmethod
    def get_all_recommended_categories() -> List[str]:
        """推奨モデルのカテゴリ一覧を取得"""
        return list(RECOMMENDED_MODELS.keys())

    def get_status(self) -> ConnectionStatus:
        """現在の接続ステータスを取得"""
        return self._status

    def get_status_message(self) -> str:
        """ステータスメッセージを取得"""
        messages = {
            ConnectionStatus.NOT_CONFIGURED: "エンドポイント未設定",
            ConnectionStatus.NOT_CONNECTED: "未接続 (疎通確認が必要)",
            ConnectionStatus.HEALTHCHECK_FAILED: f"接続失敗: {self._last_error or '不明'}",
            ConnectionStatus.CONNECTED: f"接続済み: {self.config.endpoint}",
        }
        return messages.get(self._status, "不明")

    def is_available(self) -> bool:
        """利用可能かどうか"""
        return self._status == ConnectionStatus.CONNECTED

    def update_config(self, config: LocalConnectorConfig):
        """設定を更新（CP3: UIから呼び出し）"""
        self.config = config
        if config.endpoint:
            self._status = ConnectionStatus.NOT_CONNECTED
        else:
            self._status = ConnectionStatus.NOT_CONFIGURED
        logger.info(f"[LocalConnector] Config updated: {config.endpoint}")


# グローバルインスタンス（スレッドセーフ）
import threading

_local_connector: Optional[LocalConnector] = None
_local_connector_lock = threading.Lock()


def get_local_connector() -> LocalConnector:
    """
    LocalConnectorのグローバルインスタンスを取得（スレッドセーフ）

    ダブルチェックロッキングパターンを使用
    """
    global _local_connector
    if _local_connector is None:
        with _local_connector_lock:
            if _local_connector is None:
                _local_connector = LocalConnector()
    return _local_connector
