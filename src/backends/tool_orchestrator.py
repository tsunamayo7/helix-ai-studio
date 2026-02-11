"""
Helix AI Studio - Tool Orchestrator
Claude主導型ツールオーケストレーター

設計思想:
- Claudeが主導し、MCPツール（Web検索、ファイル操作等）を実際に実行
- ローカルLLMは「計画立案・検証」の補助ツールとして機能
- 実際のアクションはClaude CLI経由で実行
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """ツールタイプ定義"""
    UNIVERSAL_AGENT = "universal_agent"      # 万能エージェント (Nemotron-3-Nano)
    CODE_SPECIALIST = "code_specialist"       # コード特化 (Qwen3-Coder)
    IMAGE_ANALYZER = "image_analyzer"         # 画像解析 (Gemma3)
    RAG_MANAGER = "rag_manager"              # RAG管理 (Nemotron-3-Nano)
    WEB_SEARCH = "web_search"                # Web検索 (Qwen3-Coder + Ollama web_search)
    LIGHT_TOOL = "light_tool"                # 軽量ツール (Gemma3 4B/12B)
    LARGE_INFERENCE = "large_inference"      # 大規模推論 (GPT-OSS 120B)
    HIGH_PRECISION_CODE = "high_precision_code"  # 超高精度コード (Devstral 2 123B)
    NEXT_GEN_UNIVERSAL = "next_gen_universal"    # 次世代汎用 (Qwen3-Next 80B)


@dataclass
class ToolConfig:
    """ツール設定"""
    name: str
    tool_type: ToolType
    ollama_model: str
    description: str
    vram_gb: float = 0.0
    context_length: int = 128000
    supports_thinking: bool = False
    supports_vision: bool = False
    is_always_loaded: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tool_type": self.tool_type.value,
            "ollama_model": self.ollama_model,
            "description": self.description,
            "vram_gb": self.vram_gb,
            "context_length": self.context_length,
            "supports_thinking": self.supports_thinking,
            "supports_vision": self.supports_vision,
            "is_always_loaded": self.is_always_loaded,
        }


@dataclass
class ToolResult:
    """ツール実行結果"""
    success: bool
    tool_name: str
    output: str
    execution_time_ms: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class OrchestratorConfig:
    """オーケストレーター設定"""
    ollama_url: str = "http://localhost:11434"

    # 常時ロードモデル
    universal_agent_model: str = "nemotron-3-nano:30b"
    image_analyzer_model: str = "ministral-3:8b"  # v4.2: gemma3:12b → ministral-3:8b (Vision性能向上)
    embedding_model: str = "qwen3-embedding:4b"   # v4.2: bge-m3 → qwen3-embedding:4b (精度向上)

    # Embedding詳細設定 (v4.2追加)
    embedding_dimension: int = 2560               # MRL対応、最大2560次元
    embedding_context_length: int = 32768         # 32Kコンテキスト
    embedding_instruction: str = "Instruct: 与えられたテキストから意味的に類似するコンテンツを検索する"

    # オンデマンドモデル（4枠: v2提案書準拠）
    code_specialist_model: str = "qwen3-coder:30b"
    large_inference_model: str = "gpt-oss:120b"
    high_precision_code_model: str = "devstral-2:123b"
    next_gen_universal_model: str = "qwen3-next:80b"

    # オンデマンドモデル有効/無効
    code_specialist_enabled: bool = True
    large_inference_enabled: bool = True
    high_precision_code_enabled: bool = False   # デフォルト無効（75GB重い）
    next_gen_universal_enabled: bool = False    # デフォルト無効

    # Claude設定
    claude_model: str = "claude-opus-4-5"
    claude_auth_mode: str = "cli"  # "cli" or "api"
    thinking_mode: str = "Standard"  # "OFF", "Standard", "Deep"

    # RAG設定
    rag_enabled: bool = True
    rag_auto_save: bool = True
    rag_save_threshold: str = "medium"  # "low", "medium", "high"

    # GPU管理
    gpu_monitor_interval: int = 5  # 秒
    keep_alive_resident: str = "-1"   # 常時ロード: 永続
    keep_alive_ondemand: str = "5m"   # オンデマンド: 5分

    # v8.0.0: BIBLE Manager
    bible_auto_discover: bool = True     # ファイル添付時にBIBLE自動検出
    bible_auto_manage: bool = True       # Phase完了後にBIBLE自律管理
    bible_project_root: str = ""         # プロジェクトルート（空=自動検出）

    # v8.4.2: 品質検証設定
    max_phase2_retries: int = 2          # Phase 2再実行の最大回数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ollama_url": self.ollama_url,
            "universal_agent_model": self.universal_agent_model,
            "image_analyzer_model": self.image_analyzer_model,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "embedding_context_length": self.embedding_context_length,
            "embedding_instruction": self.embedding_instruction,
            "code_specialist_model": self.code_specialist_model,
            "large_inference_model": self.large_inference_model,
            "high_precision_code_model": self.high_precision_code_model,
            "next_gen_universal_model": self.next_gen_universal_model,
            "code_specialist_enabled": self.code_specialist_enabled,
            "large_inference_enabled": self.large_inference_enabled,
            "high_precision_code_enabled": self.high_precision_code_enabled,
            "next_gen_universal_enabled": self.next_gen_universal_enabled,
            "claude_model": self.claude_model,
            "claude_auth_mode": self.claude_auth_mode,
            "thinking_mode": self.thinking_mode,
            "rag_enabled": self.rag_enabled,
            "rag_auto_save": self.rag_auto_save,
            "rag_save_threshold": self.rag_save_threshold,
            "gpu_monitor_interval": self.gpu_monitor_interval,
            "keep_alive_resident": self.keep_alive_resident,
            "keep_alive_ondemand": self.keep_alive_ondemand,
            "bible_auto_discover": self.bible_auto_discover,
            "bible_auto_manage": self.bible_auto_manage,
            "bible_project_root": self.bible_project_root,
            "max_phase2_retries": self.max_phase2_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrchestratorConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ToolOrchestrator:
    """
    Claude中心型ツールオーケストレーター

    Claudeが全体を統括し、必要に応じてローカルLLM（Ollama）をツールとして呼び出す
    """

    # 推奨モデル構成（mixAI_Redesign_Proposal_v2に基づく）
    RECOMMENDED_MODELS = {
        ToolType.UNIVERSAL_AGENT: {
            "primary": "nemotron-3-nano:30b",
            "fallback": ["qwen3:30b", "llama3.1:8b"],
            "description": "万能エージェント - ツール実行、RAG管理、1Mコンテキスト",
        },
        ToolType.CODE_SPECIALIST: {
            "primary": "qwen3-coder:30b",
            "fallback": ["devstral2:123b", "codellama:34b"],
            "description": "コード検証・生成・修正、Web検索エージェント兼用",
        },
        ToolType.IMAGE_ANALYZER: {
            "primary": "ministral-3:8b",  # v4.2: gemma3:12b → ministral-3:8b
            "fallback": ["ministral-3:14b", "gemma3:12b", "llava:13b"],
            "description": "画像解析、サムネイル分析、スクリーンショットOCR (MM MTBench 80.80, 256K ctx)",
        },
        ToolType.LIGHT_TOOL: {
            "primary": "ministral-3:8b",  # v4.2: gemma3:4b → ministral-3:8b
            "fallback": ["gemma3:12b", "gemma3:4b", "phi3:mini"],
            "description": "軽量汎用ツール（翻訳、要約、分類）、ネイティブFunction Calling対応",
        },
    }

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._ollama_client = None
        self._tool_execution_log: List[ToolResult] = []
        self._loaded_models: Dict[str, bool] = {}

    def initialize(self) -> bool:
        """オーケストレーターを初期化"""
        try:
            import ollama
            self._ollama_client = ollama.Client(host=self.config.ollama_url)

            # 接続テスト
            self._ollama_client.list()
            logger.info(f"[ToolOrchestrator] Ollama接続成功: {self.config.ollama_url}")
            return True

        except ImportError:
            logger.error("[ToolOrchestrator] ollamaライブラリがインストールされていません")
            return False
        except Exception as e:
            logger.error(f"[ToolOrchestrator] Ollama接続失敗: {e}")
            return False

    def get_available_models(self) -> List[Dict[str, Any]]:
        """利用可能なOllamaモデル一覧を取得"""
        if not self._ollama_client:
            return []

        try:
            response = self._ollama_client.list()
            models = []

            if hasattr(response, 'models'):
                raw_models = response.models
            elif isinstance(response, dict) and 'models' in response:
                raw_models = response['models']
            else:
                return []

            for model in raw_models:
                if isinstance(model, dict):
                    name = model.get('model') or model.get('name', '')
                    size = model.get('size', 0)
                else:
                    name = getattr(model, 'model', None) or getattr(model, 'name', '')
                    size = getattr(model, 'size', 0)

                if name:
                    models.append({
                        "name": name,
                        "size_gb": size / 1e9 if isinstance(size, int) else 0,
                        "loaded": self._loaded_models.get(name, False),
                    })

            return models

        except Exception as e:
            logger.error(f"[ToolOrchestrator] モデル一覧取得失敗: {e}")
            return []

    def execute_tool(
        self,
        tool_type: ToolType,
        prompt: str,
        context: Optional[str] = None,
        image_path: Optional[str] = None,
        thinking_enabled: bool = False,
    ) -> ToolResult:
        """
        ツールを実行

        Args:
            tool_type: 実行するツールタイプ
            prompt: ユーザープロンプト
            context: 追加コンテキスト
            image_path: 画像パス（画像解析時）
            thinking_enabled: 思考モード有効化（対応モデルのみ）

        Returns:
            ToolResult: 実行結果
        """
        if not self._ollama_client:
            return ToolResult(
                success=False,
                tool_name=tool_type.value,
                output="",
                error_message="Ollamaクライアントが初期化されていません",
            )

        # モデルを選択
        model = self._select_model_for_tool(tool_type)
        if not model:
            return ToolResult(
                success=False,
                tool_name=tool_type.value,
                output="",
                error_message=f"ツール {tool_type.value} に対応するモデルが見つかりません",
            )

        # システムプロンプトを構築
        system_prompt = self._build_system_prompt(tool_type)

        # フルプロンプトを構築
        full_prompt = prompt
        if context:
            full_prompt = f"【コンテキスト】\n{context}\n\n【タスク】\n{prompt}"

        start_time = time.time()

        try:
            # 画像解析の場合
            if tool_type == ToolType.IMAGE_ANALYZER and image_path:
                result = self._execute_vision_tool(model, system_prompt, full_prompt, image_path)
            else:
                result = self._execute_text_tool(model, system_prompt, full_prompt, thinking_enabled)

            execution_time = (time.time() - start_time) * 1000

            tool_result = ToolResult(
                success=True,
                tool_name=tool_type.value,
                output=result,
                execution_time_ms=execution_time,
                metadata={"model": model, "thinking_enabled": thinking_enabled},
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            tool_result = ToolResult(
                success=False,
                tool_name=tool_type.value,
                output="",
                execution_time_ms=execution_time,
                error_message=str(e),
            )

        # ログに記録
        self._tool_execution_log.append(tool_result)

        return tool_result

    def _select_model_for_tool(self, tool_type: ToolType) -> Optional[str]:
        """ツールタイプに応じたモデルを選択"""
        model_mapping = {
            ToolType.UNIVERSAL_AGENT: self.config.universal_agent_model,
            ToolType.CODE_SPECIALIST: self.config.code_specialist_model,
            ToolType.IMAGE_ANALYZER: self.config.image_analyzer_model,
            ToolType.RAG_MANAGER: self.config.universal_agent_model,
            ToolType.WEB_SEARCH: self.config.code_specialist_model,
            ToolType.LIGHT_TOOL: self.config.image_analyzer_model,  # Gemma3 12Bを軽量ツールとして使用
            ToolType.LARGE_INFERENCE: self.config.large_inference_model,
            ToolType.HIGH_PRECISION_CODE: self.config.high_precision_code_model,
            ToolType.NEXT_GEN_UNIVERSAL: self.config.next_gen_universal_model,
        }
        return model_mapping.get(tool_type)

    def _build_system_prompt(self, tool_type: ToolType) -> str:
        """ツールタイプに応じたシステムプロンプトを構築"""
        # v4.5: すべてのプロンプトに日本語回答の強制指示を追加
        japanese_instruction = "【最重要】必ず日本語で回答してください。英語での回答は禁止です。\n\n"

        prompts = {
            ToolType.UNIVERSAL_AGENT: (
                "あなたは万能AIツールです。与えられたタスクを正確に実行し、"
                "結果を簡潔かつ正確に日本語で報告してください。"
                "複雑なタスクは手順に分解して処理してください。"
            ),
            ToolType.CODE_SPECIALIST: (
                "あなたはコード専門AIツールです。"
                "コードの検証、生成、修正、リファクタリングを行います。"
                "常にベストプラクティスに従い、エラーハンドリングを考慮してください。"
                "出力はコードブロックで囲み、説明は日本語で記述してください。"
            ),
            ToolType.IMAGE_ANALYZER: (
                "あなたは画像解析AIツールです。"
                "画像の内容を詳細に分析し、テキスト抽出、オブジェクト検出、"
                "レイアウト理解を行います。分析結果を日本語で構造化して報告してください。"
            ),
            ToolType.RAG_MANAGER: (
                "あなたはRAG（検索拡張生成）管理AIです。"
                "過去の会話や保存されたドキュメントから関連情報を検索し、"
                "適切なコンテキストを日本語で提供してください。\n\n"
                "【出力ルール】\n"
                "- 最終的な検索結果のみを出力してください\n"
                "- 思考過程、推論、内部メモは一切出力しないでください\n"
                "- 「Let me think...」「We should...」などの英語の思考は禁止です\n"
                "- 関連情報が見つからない場合は「関連する情報は見つかりませんでした。」とのみ回答\n"
                "- 結果は箇条書きで簡潔に日本語で出力してください"
            ),
            ToolType.WEB_SEARCH: (
                "あなたはWeb検索AIツールです。"
                "インターネットから最新の情報を検索し、"
                "信頼性の高いソースを優先して結果を日本語で要約してください。"
            ),
            ToolType.LIGHT_TOOL: (
                "あなたは軽量AIツールです。"
                "翻訳、要約、分類などの軽量タスクを高速に処理します。"
                "出力は日本語で簡潔にまとめてください。"
            ),
            ToolType.LARGE_INFERENCE: (
                "あなたは大規模推論AIツールです。"
                "複雑な論理的推論、数学的問題解決、戦略的分析を行います。"
                "思考過程を日本語で段階的に示し、結論を明確に述べてください。"
            ),
            ToolType.HIGH_PRECISION_CODE: (
                "あなたは超高精度コードAIツールです。"
                "SWE-Benchレベルの高度なバグ修正、複雑なリファクタリング、"
                "アーキテクチャ設計を行います。最高品質のコードを出力し、説明は日本語で行ってください。"
            ),
            ToolType.NEXT_GEN_UNIVERSAL: (
                "あなたは次世代汎用AIツールです。"
                "235Bクラスの推論能力で、あらゆるタスクに高精度で対応します。"
                "創造性と正確性を両立した出力を日本語で生成してください。"
            ),
        }
        base_prompt = prompts.get(tool_type, "あなたは有能なAIアシスタントです。すべて日本語で回答してください。")
        return japanese_instruction + base_prompt

    def _execute_text_tool(
        self,
        model: str,
        system_prompt: str,
        prompt: str,
        thinking_enabled: bool = False,
    ) -> str:
        """テキストベースのツールを実行"""
        options = {"num_predict": 2048}

        # Thinking対応モデルの場合
        if thinking_enabled and "nemotron" in model.lower():
            # Nemotron-3-NanoのThinkingモード
            options["thinking"] = True

        response = self._ollama_client.generate(
            model=model,
            prompt=f"{system_prompt}\n\n{prompt}",
            options=options,
        )

        if isinstance(response, dict):
            return response.get('response', '')
        return getattr(response, 'response', str(response))

    def _execute_vision_tool(
        self,
        model: str,
        system_prompt: str,
        prompt: str,
        image_path: str,
    ) -> str:
        """画像解析ツールを実行"""
        import base64
        from pathlib import Path

        # 画像をBase64エンコード
        image_file = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

        with open(image_file, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        response = self._ollama_client.generate(
            model=model,
            prompt=f"{system_prompt}\n\n{prompt}",
            images=[image_data],
            options={"num_predict": 2048},
        )

        if isinstance(response, dict):
            return response.get('response', '')
        return getattr(response, 'response', str(response))

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """実行ログを取得"""
        return [r.to_dict() for r in self._tool_execution_log]

    def clear_execution_log(self):
        """実行ログをクリア"""
        self._tool_execution_log.clear()

    def save_config(self, path: Optional[Path] = None):
        """設定を保存"""
        if path is None:
            path = Path(__file__).parent.parent.parent / "config" / "tool_orchestrator.json"

        path.parent.mkdir(exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"[ToolOrchestrator] 設定を保存: {path}")

    def load_config(self, path: Optional[Path] = None):
        """設定を読み込み"""
        if path is None:
            path = Path(__file__).parent.parent.parent / "config" / "tool_orchestrator.json"

        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.config = OrchestratorConfig.from_dict(data)
            logger.info(f"[ToolOrchestrator] 設定を読み込み: {path}")


# シングルトンインスタンス
_orchestrator_instance: Optional[ToolOrchestrator] = None


def get_tool_orchestrator() -> ToolOrchestrator:
    """ToolOrchestratorのシングルトンインスタンスを取得"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = ToolOrchestrator()
        _orchestrator_instance.load_config()
    return _orchestrator_instance
