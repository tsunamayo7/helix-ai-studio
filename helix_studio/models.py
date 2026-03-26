"""Pydantic スキーマ定義"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── チャット ──────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str = Field(..., description="user / assistant / system")
    content: str


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    provider: str = Field("ollama", description="ollama / claude / openai / openai_compat")
    model: str = ""
    messages: list[ChatMessage] = []
    system_prompt: str = ""


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    role: str = "assistant"
    content: str
    provider: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    duration_ms: int | None = None


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    provider: str = "ollama"
    model: str = ""
    system_prompt: str = ""


class ConversationSummary(BaseModel):
    id: str
    title: str
    provider: str
    model: str
    created_at: str
    updated_at: str


class ConversationDetail(ConversationSummary):
    system_prompt: str
    messages: list[dict]


# ── 設定 ──────────────────────────────────────────────
class SettingUpdate(BaseModel):
    settings: dict[str, str | bool | int | float]


class SettingResponse(BaseModel):
    settings: dict[str, str | bool | int | float]


# ── パイプライン ──────────────────────────────────────
class PipelineRequest(BaseModel):
    title: str = "New Pipeline"
    input_text: str
    step1_model: str = ""
    step2_model: str = ""
    step3_model: str = ""


class PipelineStatus(BaseModel):
    id: str
    title: str
    status: str
    current_step: int
    step1_result: str | None = None
    step2_result: str | None = None
    step3_result: str | None = None
    step4_result: str | None = None
    error_msg: str | None = None
    created_at: str
    completed_at: str | None = None


# ── Mem0 ─────────────────────────────────────────────
class MemorySearchRequest(BaseModel):
    query: str
    user_id: str = ""
    limit: int = 10


class MemoryAddRequest(BaseModel):
    text: str
    user_id: str = ""


class MemoryStatusResponse(BaseModel):
    available: bool
    memory_count: int = 0
    error: str | None = None


# ── MCP ──────────────────────────────────────────────
class MCPExecuteRequest(BaseModel):
    server: str = Field(..., description="helix_pilot / helix_sandbox")
    tool_name: str
    arguments: dict = {}


# ── モデル一覧 ────────────────────────────────────────
class ModelInfo(BaseModel):
    provider: str
    name: str
    size: str | None = None
    modified_at: str | None = None


class ModelTestRequest(BaseModel):
    provider: str
    model: str = ""
    url: str = ""
    api_key: str = ""
