"""
Helix AI Studio - Constants
アプリケーション全体で使用される定数を定義
"""

# =============================================================================
# アプリケーション情報
# =============================================================================
APP_NAME = "Helix AI Studio"
APP_VERSION = "11.0.0"
APP_CODENAME = "Smart History"
APP_DESCRIPTION = (
    "Helix AI Studio v11.0.0 'Smart History' - "
    "UI簡素化, cloudAI継続送信(--resume), Historyタブ新設, "
    "BIBLEクロスタブ統合, MCP分散配置, RAGタブチャットUI化"
)

# v8.5.0: 情報収集フォルダ
INFORMATION_FOLDER = "data/information"
SUPPORTED_DOC_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.csv', '.json'}

# v8.5.0: チャンキングデフォルト
DEFAULT_CHUNK_SIZE = 512          # トークン
DEFAULT_CHUNK_OVERLAP = 64        # トークン
MAX_FILE_SIZE_MB = 50             # 1ファイルの最大サイズ

# v8.5.0 Patch 1: RAG設定デフォルト値
RAG_DEFAULT_TIME_LIMIT = 90       # 分
RAG_MIN_TIME_LIMIT = 10           # 分
RAG_MAX_TIME_LIMIT = 1440         # 分（24時間）
RAG_TIME_STEP = 10                # 分刻み
RAG_CHUNK_STEP = 64               # チャンクサイズ刻み
RAG_OVERLAP_STEP = 8              # オーバーラップ刻み

# v8.5.0: RAG構築（後方互換エイリアス）
RAG_MIN_TIME_MINUTES = RAG_MIN_TIME_LIMIT
RAG_MAX_TIME_MINUTES = RAG_MAX_TIME_LIMIT
RAG_VERIFICATION_SAMPLE_SIZE = 10 # 検証時のサンプリング数

# v8.5.0: ロック
RAG_LOCK_POLL_INTERVAL_MS = 1000  # ロック状態確認間隔

# v8.4.0: Mid-Session Summary設定
MID_SESSION_TRIGGER_COUNT = 5    # 中間要約トリガーのメッセージ間隔
MID_SESSION_CONTEXT_CHARS = 600  # 中間要約コンテキストの最大文字数

# =============================================================================
# Adaptive Thinking - Effort Level (v9.8.0: replaces ThinkingMode)
# =============================================================================
class EffortLevel:
    """
    Claude Code CLI の effort 設定（Opus 4.6 専用）
    環境変数 CLAUDE_CODE_EFFORT_LEVEL で反映する。
    """
    DEFAULT = "default"   # 未使用（env設定なし = CLI既定動作）
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def all_levels(cls) -> list:
        """全てのeffortレベルをリストで返す"""
        return [cls.DEFAULT, cls.LOW, cls.MEDIUM, cls.HIGH]

    @classmethod
    def is_opus_46(cls, model_id: str) -> bool:
        """Opus 4.6系モデルかどうか判定（effortが有効なモデル）"""
        if not model_id:
            return False
        return model_id.startswith("claude-opus-4-6")

# =============================================================================
# AIモデル設定
# =============================================================================
# v7.1.0: Claudeモデル定義（動的選択対応）
CLAUDE_MODELS = [
    {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6 (最高知能)", "description": "最も高度で知的なモデル。複雑な推論・計画立案に最適", "tier": "opus", "is_default": True, "i18n_display": "desktop.mixAI.claudeModelOpus46", "i18n_desc": "desktop.mixAI.claudeModelOpus46Desc"},
    {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6 (高速・高性能)", "description": "高速かつ高性能。Opus 4.6に次ぐ推論力とコスト効率", "tier": "sonnet", "is_default": False, "i18n_display": "desktop.mixAI.claudeModelSonnet46", "i18n_desc": "desktop.mixAI.claudeModelSonnet46Desc"},
    {"id": "claude-opus-4-5-20250929", "display_name": "Claude Opus 4.5 (高品質)", "description": "高品質でバランスの取れた応答。安定性重視", "tier": "opus", "is_default": False, "i18n_display": "desktop.mixAI.claudeModelOpus45", "i18n_desc": "desktop.mixAI.claudeModelOpus45Desc"},
    {"id": "claude-sonnet-4-5-20250929", "display_name": "Claude Sonnet 4.5 (高速)", "description": "高速応答とコスト効率。日常タスク向き", "tier": "sonnet", "is_default": False, "i18n_display": "desktop.mixAI.claudeModelSonnet45", "i18n_desc": "desktop.mixAI.claudeModelSonnet45Desc"},
]
DEFAULT_CLAUDE_MODEL_ID = "claude-opus-4-6"


def get_claude_model_by_id(model_id: str) -> dict | None:
    """モデルIDからモデル定義を取得"""
    for m in CLAUDE_MODELS:
        if m["id"] == model_id:
            return m
    return None


def get_default_claude_model() -> dict:
    """デフォルトのClaudeモデル定義を取得"""
    for m in CLAUDE_MODELS:
        if m["is_default"]:
            return m
    return CLAUDE_MODELS[0]


class ClaudeModels:
    """Claudeモデル定数（後方互換性のため維持）"""
    SONNET_45 = "Claude Sonnet 4.5 (高速)"
    SONNET_46 = "Claude Sonnet 4.6 (高速・高性能)"
    OPUS_45 = "Claude Opus 4.5 (高品質)"
    OPUS_46 = "Claude Opus 4.6 (最高知能)"

    @classmethod
    def all_models(cls) -> list:
        """全てのClaudeモデル表示名をリストで返す"""
        return [m["display_name"] for m in CLAUDE_MODELS]

class GeminiModels:
    """Geminiモデル定数"""
    PRO_3 = "Gemini 3 Pro (推奨)"
    FLASH_3 = "Gemini 3 Flash (高速)"

    @classmethod
    def all_models(cls) -> list:
        """全てのGeminiモデルをリストで返す"""
        return [cls.PRO_3, cls.FLASH_3]

# =============================================================================
# デフォルト設定値
# =============================================================================
class DefaultSettings:
    """デフォルト設定値"""
    CLAUDE_TIMEOUT_MIN = 30     # Claudeタイムアウト (分)
    GEMINI_TIMEOUT_MIN = 5      # Geminiタイムアウト (分)
    FONT_SIZE = 10              # 基本フォントサイズ
    DARK_MODE = True            # ダークモードデフォルト
    AUTO_SAVE = True            # 自動保存デフォルト
    AUTO_CONTEXT = True         # 自動コンテキストデフォルト

# =============================================================================
# MCPサーバー
# =============================================================================
class MCPServers:
    """MCPサーバー識別子"""
    FILESYSTEM = "filesystem"
    GIT = "git"
    BRAVE_SEARCH = "brave-search"
    GITHUB = "github"
    SLACK = "slack"
    GOOGLE_DRIVE = "google-drive"

# =============================================================================
# Workflow State Machine (工程状態機械)
# =============================================================================
class WorkflowPhase:
    """工程（Phase）の定義"""
    S0_INTAKE = "S0_INTAKE"              # 依頼受領
    S1_CONTEXT = "S1_CONTEXT"            # BIBLE/現状読込
    S2_PLAN = "S2_PLAN"                  # 計画
    S3_RISK_GATE = "S3_RISK_GATE"        # 危険判定・承認
    S4_IMPLEMENT = "S4_IMPLEMENT"        # 実装
    S5_VERIFY = "S5_VERIFY"              # テスト/静的検証
    S6_REVIEW = "S6_REVIEW"              # 差分レビュー
    S7_RELEASE = "S7_RELEASE"            # 確定・記録

    @classmethod
    def all_phases(cls) -> list:
        """全ての工程をリストで返す"""
        return [
            cls.S0_INTAKE,
            cls.S1_CONTEXT,
            cls.S2_PLAN,
            cls.S3_RISK_GATE,
            cls.S4_IMPLEMENT,
            cls.S5_VERIFY,
            cls.S6_REVIEW,
            cls.S7_RELEASE,
        ]

    @classmethod
    def get_display_name(cls, phase: str) -> str:
        """工程の表示名を返す"""
        display_names = {
            cls.S0_INTAKE: "S0: 依頼受領 (Intake)",
            cls.S1_CONTEXT: "S1: コンテキスト読込 (Context Load)",
            cls.S2_PLAN: "S2: 計画 (Plan)",
            cls.S3_RISK_GATE: "S3: 危険判定・承認 (Risk Gate)",
            cls.S4_IMPLEMENT: "S4: 実装 (Implement)",
            cls.S5_VERIFY: "S5: テスト/検証 (Verify)",
            cls.S6_REVIEW: "S6: 差分レビュー (Review)",
            cls.S7_RELEASE: "S7: 確定・記録 (Release)",
        }
        return display_names.get(phase, phase)

    @classmethod
    def get_description(cls, phase: str) -> str:
        """工程の説明を返す"""
        descriptions = {
            cls.S0_INTAKE: "ユーザーからの依頼を受領し、要件を整理します。",
            cls.S1_CONTEXT: "PROJECT_BIBLEや現在のコードを読み込み、コンテキストを構築します。",
            cls.S2_PLAN: "実装計画を作成し、アプローチを決定します。",
            cls.S3_RISK_GATE: "危険な操作（書き込み・削除等）の実行可否を判定し、承認を取得します。",
            cls.S4_IMPLEMENT: "実際のコード実装を行います。",
            cls.S5_VERIFY: "テスト実行や静的解析により、実装を検証します。",
            cls.S6_REVIEW: "コードの差分をレビューし、変更内容を確認します。",
            cls.S7_RELEASE: "変更を確定し、記録として保存します。",
        }
        return descriptions.get(phase, "")

# =============================================================================
# パス設定
# =============================================================================
class Paths:
    """ファイルパス定数"""
    DATA_DIR = "data"
    CONFIG_DIR = "config"
    LOGS_DIR = "logs"

    # Workflow State
    WORKFLOW_STATE_FILE = "data/workflow_state.json"
    WORKFLOW_LOG_FILE = "logs/workflow.log"
