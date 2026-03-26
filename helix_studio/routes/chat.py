"""チャット WebSocket + REST API ルーター"""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from helix_studio.config import get_setting
from helix_studio.db import get_connection
from helix_studio.models import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)
from helix_studio.services import cloud_ai, local_ai, cli_ai, mem0, rag, tools

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


# ── WebSocket チャット ────────────────────────────────


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """WebSocketでストリーミングチャット。"""
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            provider = data.get("provider", "ollama")
            model = data.get("model", "")
            content = data.get("content", "")
            system_prompt = data.get("system_prompt", "")
            conversation_id = data.get("conversation_id", "")

            if not content:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "content": "メッセージが空です",
                }))
                continue

            # 会話IDがなければ新規作成
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                await _create_conversation(conversation_id, provider, model, system_prompt)

            # ユーザーメッセージをDB保存
            user_msg_id = str(uuid.uuid4())
            await _save_message(
                user_msg_id, conversation_id, "user", content,
                provider, model,
            )

            # ツールコマンド処理（@search, @file）
            tool_context = await _process_tool_commands(content)

            # 過去のメッセージを取得して会話履歴を構築
            messages = await _load_conversation_messages(conversation_id)

            # ツール結果をコンテキストに注入
            if tool_context:
                messages.insert(0, {"role": "system", "content": tool_context})

            # Mem0自動注入
            mem0_inject = await get_setting("mem0_auto_inject")
            if mem0_inject == "true" and content:
                await _inject_mem0_context(messages, content)

            # RAG自動注入
            rag_enabled = data.get("rag_enabled", True)
            if rag_enabled and content:
                await _inject_rag_context(messages, content)

            # LLM自律Web検索（tool use対応モデルのみ）
            if not tool_context:  # 手動@searchがなければ自動検索を試みる
                auto_search = await _auto_web_search(provider, model, content, messages)
                if auto_search:
                    messages.insert(0, {"role": "system", "content": auto_search})

            # ストリーミング応答
            start_ms = time.monotonic_ns() // 1_000_000
            full_response = ""
            try:
                async for chunk in _route_stream(provider, model, messages, system_prompt):
                    full_response += chunk
                    await ws.send_text(json.dumps({
                        "type": "chunk",
                        "content": chunk,
                        "conversation_id": conversation_id,
                    }))
            except Exception as e:
                logger.exception("ストリーミングエラー")
                await ws.send_text(json.dumps({
                    "type": "error",
                    "content": f"エラーが発生しました: {e}",
                    "conversation_id": conversation_id,
                }))
                continue

            duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms

            # アシスタントメッセージをDB保存
            asst_msg_id = str(uuid.uuid4())
            await _save_message(
                asst_msg_id, conversation_id, "assistant", full_response,
                provider, model, duration_ms=duration_ms,
            )

            # プロバイダ表示名の生成
            provider_labels = {
                "ollama": "ローカル / Ollama",
                "openai_compat": "ローカル / OpenAI互換",
                "claude": "Cloud / Claude API",
                "openai": "Cloud / OpenAI API",
                "claude_code": "CLI / Claude Code",
                "codex": "CLI / Codex",
                "gemini_cli": "CLI / Gemini",
            }
            provider_label = provider_labels.get(provider, provider)

            # 完了通知（モデル情報付き）
            await ws.send_text(json.dumps({
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": asst_msg_id,
                "duration_ms": duration_ms,
                "provider": provider,
                "provider_label": provider_label,
                "model": model,
            }))

    except WebSocketDisconnect:
        logger.info("WebSocket切断")
    except Exception as e:
        logger.exception("WebSocketエラー: %s", e)


# ── REST API ──────────────────────────────────────────


@router.post("/api/chat")
async def post_chat(req: ChatRequest) -> ChatResponse:
    """非ストリーミング版チャット（フォールバック）。"""
    conversation_id = req.conversation_id or str(uuid.uuid4())

    if not req.conversation_id:
        await _create_conversation(conversation_id, req.provider, req.model, req.system_prompt)

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    start_ms = time.monotonic_ns() // 1_000_000
    chunks: list[str] = []
    async for chunk in _route_stream(req.provider, req.model, messages, req.system_prompt):
        chunks.append(chunk)
    content = "".join(chunks)
    duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms

    msg_id = str(uuid.uuid4())
    await _save_message(msg_id, conversation_id, "assistant", content, req.provider, req.model, duration_ms=duration_ms)

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=msg_id,
        content=content,
        provider=req.provider,
        model=req.model,
        duration_ms=duration_ms,
    )


@router.post("/api/conversations")
async def create_conversation(req: ConversationCreate) -> dict:
    """新規会話を作成。"""
    conv_id = str(uuid.uuid4())
    await _create_conversation(conv_id, req.provider, req.model, req.system_prompt, req.title)
    return {"id": conv_id, "title": req.title}


@router.get("/api/conversations")
async def list_conversations() -> list[dict]:
    """会話一覧を取得。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, title, provider, model, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


@router.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str) -> dict:
    """会話詳細（メッセージ含む）を取得。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        )
        conv = await cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="会話が見つかりません")

        cursor = await db.execute(
            "SELECT id, role, content, provider, model, tokens_in, tokens_out, "
            "duration_ms, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at",
            (conv_id,),
        )
        messages = await cursor.fetchall()
        return {
            **dict(conv),
            "messages": [dict(m) for m in messages],
        }
    finally:
        await db.close()


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str) -> dict:
    """会話を削除。"""
    db = await get_connection()
    try:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()
        return {"deleted": conv_id}
    finally:
        await db.close()


# ── ヘルパー ──────────────────────────────────────────


async def _route_stream(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    system_prompt: str = "",
):
    """プロバイダに応じたストリーミングを返す。"""
    if provider in ("claude", "openai"):
        api_key_map = {"claude": "claude_api_key", "openai": "openai_api_key"}
        api_key = await get_setting(api_key_map[provider]) or ""
        if not api_key:
            raise ValueError(f"{provider}のAPIキーが設定されていません。設定画面から入力してください。")
        async for chunk in cloud_ai.stream_chat(provider, api_key, model, messages, system_prompt):
            yield chunk
    elif provider == "openai_compat":
        url = await get_setting("openai_compat_url") or ""
        api_key = await get_setting("openai_compat_api_key") or ""
        if not url:
            raise ValueError("OpenAI互換APIのURLが設定されていません。")
        async for chunk in local_ai.stream_chat("openai_compat", url, model, messages, api_key):
            yield chunk
    elif provider in ("claude_code", "codex", "gemini_cli"):
        # CLI経由
        user_content = messages[-1]["content"] if messages else ""
        async for chunk in cli_ai.stream_chat_cli(provider, model, user_content, system_prompt):
            yield chunk
    else:
        # デフォルト: Ollama
        url = await get_setting("ollama_url") or "http://localhost:11434"
        async for chunk in local_ai.stream_chat("ollama", url, model, messages):
            yield chunk


async def _process_tool_commands(content: str) -> str:
    """メッセージ中の @search/@file コマンドを処理し、結果テキストを返す。

    使い方:
      @search キーワード   → Web検索してLLMにコンテキスト注入
      @file パス           → ファイル読み取りしてLLMにコンテキスト注入
      @ls パス             → ディレクトリ一覧を取得
    """
    import re
    parts = []

    # @search コマンド
    search_matches = re.findall(r'@search\s+(.+?)(?=@\w|$)', content, re.DOTALL)
    for query in search_matches:
        query = query.strip()
        if query:
            try:
                results = await tools.web_search(query, max_results=5)
                parts.append(tools.format_search_results(results))
            except Exception as e:
                parts.append(f"[Web検索エラー] {e}")

    # @file コマンド
    file_matches = re.findall(r'@file\s+([\S]+)', content)
    for path in file_matches:
        try:
            result = await tools.read_file(path.strip())
            if result.get("error"):
                parts.append(f"[ファイルエラー] {result['error']}")
            else:
                file_content = result.get("content", "")
                if len(file_content) > 5000:
                    file_content = file_content[:5000] + "\n...(truncated)"
                parts.append(f"## ファイル: {path}\n```\n{file_content}\n```")
        except Exception as e:
            parts.append(f"[ファイル読み取りエラー] {e}")

    # @ls コマンド
    ls_matches = re.findall(r'@ls\s+([\S]+)', content)
    for path in ls_matches:
        try:
            result = await tools.list_files(path.strip())
            parts.append(tools.format_file_listing(result))
        except Exception as e:
            parts.append(f"[ディレクトリ一覧エラー] {e}")

    return "\n\n".join(parts) if parts else ""


async def _inject_mem0_context(
    messages: list[dict[str, str]],
    query: str,
) -> None:
    """Mem0から関連記憶を検索し、最後のユーザーメッセージに参考情報として注入。

    Ollamaの一部モデル（gemma3系など）はsystemロールのメッセージを無視する
    ことがあるため、systemではなくユーザーメッセージの先頭に埋め込む。
    """
    try:
        mem0_url = await get_setting("mem0_url") or "http://localhost:8080"
        user_id = await get_setting("mem0_user_id") or "tsunamayo7"
        memories = await mem0.search(mem0_url, user_id, query, limit=5)
        if memories:
            mem_texts = []
            for m in memories:
                text = m.get("memory", m.get("text", str(m)))
                mem_texts.append(f"- {text}")
            context = "【参考: 過去の記憶】\n" + "\n".join(mem_texts)
            # 最後のuserメッセージのcontentの前に参考情報として追加
            if messages:
                last_user = None
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]["role"] == "user":
                        last_user = i
                        break
                if last_user is not None:
                    messages[last_user]["content"] = (
                        context + "\n\n---\n\n" + messages[last_user]["content"]
                    )
    except Exception as e:
        logger.debug("Mem0注入をスキップ: %s", e)


async def _inject_rag_context(
    messages: list[dict[str, str]],
    query: str,
) -> None:
    """RAGナレッジベースから関連チャンクを検索し、ユーザーメッセージに注入。"""
    try:
        ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
        results = await rag.search(query, limit=3, ollama_url=ollama_url)
        if results:
            context = rag.format_rag_context(results)
            if context and messages:
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]["role"] == "user":
                        messages[i]["content"] = (
                            context + "\n\n---\n\n" + messages[i]["content"]
                        )
                        break
    except Exception as e:
        logger.debug("RAG注入をスキップ: %s", e)


async def _load_conversation_messages(conversation_id: str) -> list[dict[str, str]]:
    """会話の全メッセージをDBから取得してLLM用の形式で返す。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT role, content FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        await db.close()


async def _create_conversation(
    conv_id: str,
    provider: str,
    model: str,
    system_prompt: str = "",
    title: str = "新しい会話",
) -> None:
    """会話レコードをDBに作成。"""
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO conversations (id, title, provider, model, system_prompt) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, provider, model, system_prompt),
        )
        await db.commit()
    finally:
        await db.close()


async def _save_message(
    msg_id: str,
    conversation_id: str,
    role: str,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """メッセージをDBに保存し、会話のupdated_atを更新。"""
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, "
            "tokens_in, tokens_out, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, provider, model, tokens_in, tokens_out, duration_ms),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
    finally:
        await db.close()


# ── LLM自律Web検索（tool use） ──────────────────────────


# tool use 対応モデルのパターン（Ollama名）
_TOOL_USE_MODELS = {
    "qwen3", "qwen3.5", "llama4", "llama3.3", "llama3.1",
    "mistral", "mistral-small", "command-a", "command-r",
    "nemotron", "gpt-oss", "devstral", "gemma3",
}


def _supports_tool_use(provider: str, model: str) -> bool:
    """モデルがtool use（function calling）に対応しているか判定。"""
    # Cloud APIは全て対応
    if provider in ("claude", "openai"):
        return True
    # CLI経由は非対応（tool useの制御ができない）
    if provider in ("claude_code", "codex", "gemini_cli"):
        return False
    # Ollamaローカル: モデル名からファミリーを判定
    model_lower = model.lower().split(":")[0]  # "qwen3.5:122b" → "qwen3.5"
    return any(model_lower.startswith(family) for family in _TOOL_USE_MODELS)


_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information. Use this when the user asks about recent events, latest data, or topics that require up-to-date information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web",
                },
            },
            "required": ["query"],
        },
    },
}


async def _auto_web_search(
    provider: str, model: str, content: str, messages: list[dict]
) -> str:
    """tool use対応モデルにWeb検索ツールを提示し、LLMの判断で検索を実行する。"""
    if not _supports_tool_use(provider, model):
        return ""

    try:
        ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
        import httpx

        # tool use付きの非ストリーミング呼び出し
        if provider == "ollama" or provider not in ("claude", "openai"):
            payload = {
                "model": model,
                "messages": messages[-5:],  # 直近5件に制限（トークン節約）
                "tools": [_WEB_SEARCH_TOOL],
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as c:
                r = await c.post(f"{ollama_url}/api/chat", json=payload)
                if r.status_code != 200:
                    return ""
                data = r.json()

            # ツール呼び出しがあるか確認
            tool_calls = data.get("message", {}).get("tool_calls", [])
            if not tool_calls:
                return ""  # LLMが検索不要と判断

            # 検索実行
            search_results = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                if fn.get("name") == "web_search":
                    query = fn.get("arguments", {}).get("query", "")
                    if query:
                        logger.info("LLM auto web search: %s", query)
                        results = await tools.web_search(query, max_results=5)
                        search_results.append(tools.format_search_results(results))

            return "\n\n".join(search_results) if search_results else ""

        # Cloud API (Claude/OpenAI) は今後追加可能
        return ""

    except Exception as e:
        logger.debug("Auto web search failed: %s", e)
        return ""
