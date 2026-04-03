"""Tests for helix_studio.models (Pydantic schemas)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from helix_studio.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationSummary,
    ConversationDetail,
    MCPExecuteRequest,
    MemoryAddRequest,
    MemorySearchRequest,
    MemoryStatusResponse,
    ModelInfo,
    ModelTestRequest,
    PipelineRequest,
    PipelineStatus,
    SettingResponse,
    SettingUpdate,
)


class TestChatMessage:
    def test_valid(self):
        m = ChatMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"

    def test_role_required(self):
        with pytest.raises(ValidationError):
            ChatMessage(content="hello")


class TestChatRequest:
    def test_defaults(self):
        r = ChatRequest()
        assert r.provider == "ollama"
        assert r.model == ""
        assert r.messages == []

    def test_with_messages(self):
        r = ChatRequest(
            provider="claude",
            model="claude-sonnet-4-20250514",
            messages=[ChatMessage(role="user", content="hi")],
        )
        assert len(r.messages) == 1


class TestChatResponse:
    def test_minimal(self):
        r = ChatResponse(
            conversation_id="conv-1",
            message_id="msg-1",
            content="response",
            provider="ollama",
            model="gemma3:27b",
        )
        assert r.tokens_in is None
        assert r.duration_ms is None


class TestConversationCreate:
    def test_defaults(self):
        c = ConversationCreate()
        assert c.title == "New Chat"
        assert c.provider == "ollama"


class TestConversationSummary:
    def test_all_fields(self):
        s = ConversationSummary(
            id="1", title="Test", provider="ollama",
            model="gemma3:27b", created_at="2026-01-01", updated_at="2026-01-01",
        )
        assert s.id == "1"


class TestConversationDetail:
    def test_inherits_summary(self):
        d = ConversationDetail(
            id="1", title="T", provider="p", model="m",
            created_at="c", updated_at="u",
            system_prompt="sp", messages=[],
        )
        assert d.system_prompt == "sp"


class TestSettingUpdate:
    def test_accepts_various_types(self):
        s = SettingUpdate(settings={"k1": "v1", "k2": True, "k3": 42})
        assert s.settings["k2"] is True


class TestPipelineRequest:
    def test_required_input(self):
        r = PipelineRequest(input_text="do something")
        assert r.title == "New Pipeline"

    def test_missing_input(self):
        with pytest.raises(ValidationError):
            PipelineRequest()


class TestMemorySearchRequest:
    def test_defaults(self):
        r = MemorySearchRequest(query="test")
        assert r.limit == 10
        assert r.user_id == ""


class TestMemoryAddRequest:
    def test_required_text(self):
        with pytest.raises(ValidationError):
            MemoryAddRequest()


class TestMCPExecuteRequest:
    def test_required_fields(self):
        r = MCPExecuteRequest(server="helix_pilot", tool_name="click")
        assert r.arguments == {}


class TestModelInfo:
    def test_optional_fields(self):
        m = ModelInfo(provider="ollama", name="gemma4:31b")
        assert m.size is None


class TestModelTestRequest:
    def test_defaults(self):
        r = ModelTestRequest(provider="ollama")
        assert r.model == ""
