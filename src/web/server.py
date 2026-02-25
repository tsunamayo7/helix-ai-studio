"""
Helix AI Studio - Web UIサーバー (v9.3.0)

FastAPI + Uvicornサーバー。
PyQt6アプリケーションとは別プロセスで起動し、
共有バックエンド（Claude CLI, RAGBuildLock等）にアクセスする。

起動方法:
  1. スタンドアロン: python -m src.web.server
  2. PyQt6統合: HelixAIStudio.py の設定画面からトグルで起動

技術的な注意:
  - FastAPI (asyncio) と PyQt6 (QEventLoop) は別プロセスで実行
  - プロセス間通信は現時点では不要（Claude CLIは都度subprocess実行のため）
  - RAGBuildLockの共有はPhase 2以降で対応
"""

import asyncio
import json
import logging
import os
import secrets
import subprocess
import time as _time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import WebAuthManager
from .api_routes import router as api_router
from .rag_bridge import WebRAGBridge
from .chat_store import ChatStore
from .ws_manager import WebSocketManager

# v11.5.3: Discord通知
try:
    from ..utils.discord_notifier import notify_discord as _notify_discord
except ImportError:
    def _notify_discord(*args, **kwargs): return False

logger = logging.getLogger(__name__)

# =============================================================================
# グローバル状態
# =============================================================================

rag_bridge = WebRAGBridge()
chat_store = ChatStore()

ws_manager = WebSocketManager(max_connections=3)
auth_manager = WebAuthManager()

_app_state = {
    "pyqt_running": False,
    "active_websockets": 0,
    "rag_locked": False,
}


def get_app_state() -> dict:
    """API routesからアクセスするための状態取得"""
    _app_state["active_websockets"] = ws_manager.active_count
    return _app_state


# =============================================================================
# v9.5.0: Web実行ロック
# =============================================================================

LOCK_FILE = Path("data/web_execution_lock.json")


def _set_execution_lock(tab: str, client_info: str, prompt: str):
    """Web実行ロックを設定"""
    lock_data = {
        "locked": True,
        "tab": tab,
        "client_info": client_info,
        "started_at": datetime.now().isoformat(),
        "prompt_preview": prompt[:50],
    }
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding='utf-8')


def _release_execution_lock():
    """Web実行ロックを解除"""
    try:
        LOCK_FILE.write_text('{"locked": false}', encoding='utf-8')
    except Exception as e:
        logger.warning(f"[server] Failed to release execution lock: {e}")


# =============================================================================
# FastAPIアプリケーション
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動/終了フック"""
    logger.info("Helix AI Studio Web Server starting...")
    logger.info(f"Port: {os.environ.get('HELIX_WEB_PORT', 8500)}")
    yield
    logger.info("Helix AI Studio Web Server shutting down...")


app = FastAPI(
    title="Helix AI Studio Web API",
    version="10.0.0",
    lifespan=lifespan,
)

# CORS設定
# v9.9.2: allow_credentials=True と allow_origins=["*"] の組み合わせは
# ブラウザが拒否するため、明示的なオリジンリストに変更。
# Tailscale VPN経由のローカル/モバイルアクセスを想定。
_CORS_ORIGINS = [
    "http://localhost:8500",
    "http://127.0.0.1:8500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    # v10.0.0: Tailscale IP + マシン名ベースアクセスの両方を許可
    allow_origin_regex=r"http://(100\.\d+\.\d+\.\d+|[a-zA-Z0-9\-]+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST APIルーター
app.include_router(api_router)

# フロントエンド静的ファイル配信（StaticFilesのルートマウントを避ける）
# ルートマウント("/")はWebSocketリクエストを横取りしてAssertionErrorを起こすため、
# /assets のみStaticFilesでマウントし、それ以外はcatch-all GETルートでSPA対応する
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


# =============================================================================
# WebSocket エンドポイント (cloudAI / 旧soloAI)
# =============================================================================

async def _websocket_cloud_handler(websocket: WebSocket, token: str):
    """
    cloudAI WebSocketエンドポイント (v10.1.0: 旧soloAI)。
    接続時にJWT認証を行い、認証成功後にメッセージを受信する。

    クライアント → サーバー メッセージ:
      {"action": "execute", "prompt": "...", "model_id": "...", ...}
      {"action": "cancel"}
      {"action": "ping"}

    サーバー → クライアント メッセージ:
      {"type": "streaming", "chunk": "...", "done": false}
      {"type": "streaming", "chunk": "...", "done": true}
      {"type": "status", "status": "...", "detail": "..."}
      {"type": "error", "error": "..."}
      {"type": "pong"}
    """
    # JWT認証
    client_ip = websocket.client.host
    if not auth_manager.check_ip(client_ip):
        await websocket.close(code=4003, reason="IP not allowed")
        return

    payload = auth_manager.verify_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # 接続受け入れ
    client_id = str(uuid.uuid4())
    connected = await ws_manager.connect(websocket, client_id)
    if not connected:
        await websocket.close(code=4029, reason="Too many connections")
        return

    try:
        await ws_manager.send_status(client_id, "connected", "cloudAI WebSocket ready")

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                await ws_manager.send_to(client_id, {"type": "pong"})

            elif action == "execute":
                await _handle_solo_execute(client_id, data)

            elif action == "cancel":
                # Phase 1では未実装（Claude CLIはsubprocessなのでkillが必要）
                await ws_manager.send_status(client_id, "cancelled", "キャンセルは現在未対応です")

            else:
                await ws_manager.send_error(client_id, f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(client_id)


@app.websocket("/ws/cloud")
async def websocket_cloud(websocket: WebSocket, token: str = Query(...)):
    await _websocket_cloud_handler(websocket, token)


@app.websocket("/ws/solo")
async def websocket_solo_compat(websocket: WebSocket, token: str = Query(...)):
    """v10.1.0: 後方互換エイリアス（/ws/solo → /ws/cloud と同じハンドラ）"""
    await _websocket_cloud_handler(websocket, token)


# =============================================================================
# WebSocket エンドポイント (mixAI)
# =============================================================================

@app.websocket("/ws/mix")
async def websocket_mix(websocket: WebSocket, token: str = Query(...)):
    """
    mixAI WebSocketエンドポイント。
    3Phase実行の進捗をリアルタイム配信。

    クライアント → サーバー:
      {"action": "execute", "prompt": "...", "model_id": "...",
       "model_assignments": {...}, "project_dir": "...", "attached_files": [...]}
      {"action": "cancel"}

    サーバー → クライアント:
      {"type": "phase_changed", "phase": 1, "description": "..."}
      {"type": "streaming", "chunk": "...", "done": false}
      {"type": "llm_started", "category": "coding", "model": "devstral-2:123b"}
      {"type": "llm_finished", "category": "coding", "success": true, "elapsed": 12.5}
      {"type": "phase2_progress", "completed": 2, "total": 5}
      {"type": "streaming", "chunk": "...", "done": true}
      {"type": "error", "error": "..."}
    """
    # JWT認証（cloudAIと同じ）
    client_ip = websocket.client.host
    if not auth_manager.check_ip(client_ip):
        await websocket.close(code=4003, reason="IP not allowed")
        return

    payload = auth_manager.verify_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    client_id = str(uuid.uuid4())
    connected = await ws_manager.connect(websocket, client_id)
    if not connected:
        await websocket.close(code=4029, reason="Too many connections")
        return

    try:
        await ws_manager.send_status(client_id, "connected", "mixAI WebSocket ready")

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                await ws_manager.send_to(client_id, {"type": "pong"})
            elif action == "execute":
                await _handle_mix_execute(client_id, data)
            elif action == "cancel":
                await ws_manager.send_status(client_id, "cancelled", "キャンセルは現在未対応です")
            else:
                await ws_manager.send_error(client_id, f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"mixAI WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"mixAI WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(client_id)


# =============================================================================
# WebSocket エンドポイント (localAI)  v11.5.3
# =============================================================================

@app.websocket("/ws/local")
async def websocket_local(websocket: WebSocket, token: str = Query(...)):
    """
    localAI WebSocketエンドポイント。
    Ollama API を直接呼び出してストリーミング応答を返す。

    クライアント → サーバー:
      {"action": "execute", "prompt": "...", "model": "gemma3:27b",
       "chat_id": "...", "attached_files": [...]}
      {"action": "cancel"}

    サーバー → クライアント:
      {"type": "streaming", "chunk": "...", "done": false}
      {"type": "streaming", "chunk": "...", "done": true}
      {"type": "status", "status": "...", "detail": "..."}
      {"type": "error", "error": "..."}
    """
    # JWT認証
    client_ip = websocket.client.host
    if not auth_manager.check_ip(client_ip):
        await websocket.close(code=4003, reason="IP not allowed")
        return

    payload = auth_manager.verify_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    client_id = str(uuid.uuid4())
    connected = await ws_manager.connect(websocket, client_id)
    if not connected:
        await websocket.close(code=4029, reason="Too many connections")
        return

    try:
        await ws_manager.send_status(client_id, "connected", "localAI WebSocket ready")

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                await ws_manager.send_to(client_id, {"type": "pong"})

            elif action == "execute":
                await _handle_local_execute(client_id, data)

            elif action == "cancel":
                await ws_manager.send_status(client_id, "cancelled", "キャンセルは現在未対応です")

            else:
                await ws_manager.send_error(client_id, f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"localAI WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"localAI WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(client_id)


async def _handle_local_execute(client_id: str, data: dict):
    """
    localAI実行ハンドラ (v11.5.3)
    Ollama API を使ってローカルLLMチャットを実行する。
    """
    prompt = data.get("prompt", "")
    chat_id = data.get("chat_id")
    model = data.get("model", "")
    attached_files = data.get("attached_files", [])
    client_info = data.get("client_info", "Web Client")

    if not prompt:
        await ws_manager.send_error(client_id, "Prompt is empty")
        return

    # 設定読み込み（ollama_host等に必要）
    settings = _load_merged_settings()

    # モデル未指定なら設定から取得
    if not model:
        try:
            assignments = settings.get("model_assignments", {})
            model = assignments.get("coding") or ""
        except Exception:
            pass
    if not model:
        await ws_manager.send_error(client_id, "No model specified. Please select a model.")
        return

    ollama_host = settings.get("ollama_host", "http://localhost:11434")

    # 実行ロック
    _set_execution_lock("localAI", client_info, prompt)

    # チャットID管理
    if not chat_id:
        chat = chat_store.create_chat(tab="localAI")
        chat_id = chat["id"]
        await ws_manager.send_to(client_id, {
            "type": "chat_created",
            "chat_id": chat_id,
        })

    chat_store.add_message(chat_id, "user", prompt)

    # タイトル自動生成
    chat = chat_store.get_chat(chat_id)
    if chat and chat["message_count"] == 1:
        title = chat_store.auto_generate_title(chat_id)
        await ws_manager.send_to(client_id, {
            "type": "chat_title_updated",
            "chat_id": chat_id,
            "title": title,
        })

    # 添付ファイル情報をプロンプトに追加
    full_prompt = prompt
    if attached_files:
        full_prompt += "\n\n[添付ファイル]\n" + "\n".join(f"- {f}" for f in attached_files)

    ws_manager.set_active_task(client_id, "localAI")
    await ws_manager.send_status(client_id, "executing", f"{model} 実行中...")

    # Discord: チャット開始通知
    _notify_discord("localAI", "started", f"モデル: {model}\n{prompt[:200]}")

    start_time = _time.time()

    try:
        response = await _run_ollama_async(
            model=model,
            prompt=full_prompt,
            timeout=_get_claude_timeout_sec(),
            host=ollama_host,
        )

        elapsed = _time.time() - start_time

        # モデルサマリーを末尾に付記
        model_summary = f"\n\n---\n🤖 **使用モデル (Ollama)**: `{model}`"
        response_with_summary = response + model_summary

        # 応答保存（サマリー込み）
        chat_store.add_message(chat_id, "assistant", response_with_summary,
                               metadata={"model": model, "elapsed": round(elapsed, 1)})

        await ws_manager.send_streaming(client_id, response_with_summary, done=True)
        await ws_manager.send_status(client_id, "completed", f"実行完了 ({elapsed:.1f}s)")

        # Discord: 完了通知
        _notify_discord("localAI", "completed", response[:500], elapsed=elapsed)

        # 会話をRAGに保存
        asyncio.ensure_future(_save_web_conversation(
            [{"role": "user", "content": prompt},
             {"role": "assistant", "content": response}],
            tab="localAI",
        ))

    except Exception as e:
        elapsed = _time.time() - start_time
        error_msg = str(e)

        # Ollama接続エラーの場合、わかりやすいメッセージに変換
        if "ConnectError" in error_msg or "Connection refused" in error_msg:
            error_msg = f"Ollama に接続できません ({ollama_host})。Ollama が起動しているか確認してください。"
        elif "404" in error_msg:
            error_msg = f"モデル '{model}' が見つかりません。Ollama でモデルをプルしてください。"

        await ws_manager.send_error(client_id, error_msg)

        # Discord: エラー通知
        _notify_discord("localAI", "error", prompt[:200], error=error_msg)

    finally:
        _release_execution_lock()
        ws_manager.set_active_task(client_id, None)


# =============================================================================
# SPA catch-all ルート（WebSocketルートより後に定義）
# =============================================================================

if frontend_dist.exists():
    # SPA対応: 404エラー時にindex.htmlを返す（catch-allルートの代わり）
    # これによりAPIルートとの競合を完全に回避できる
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.requests import Request as StarletteRequest

    _original_index = frontend_dist / "index.html"

    @app.exception_handler(404)
    async def spa_not_found_handler(request: StarletteRequest, exc: StarletteHTTPException):
        """404時にSPAのindex.htmlを返す（APIリクエストは除外）"""
        path = request.url.path
        # APIやdocsパスは通常の404を返す
        if path.startswith(("/api/", "/ws/", "/docs", "/openapi.json", "/redoc")):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail or "Not found"},
            )
        # 静的ファイルが存在すればそれを返す
        file_path = frontend_dist / path.lstrip("/")
        if file_path.is_file() and ".." not in path:
            return FileResponse(file_path)
        # それ以外はSPAのindex.htmlを返す
        return FileResponse(_original_index)


async def _handle_solo_execute(client_id: str, data: dict):
    """
    cloudAI実行ハンドラ (v10.1.0: 旧soloAI, v9.2.0: ChatStore統合)。
    Claude CLIをsubprocessで実行し、結果をWebSocketで送信。
    """
    from ..utils.subprocess_utils import run_hidden

    prompt = data.get("prompt", "")
    chat_id = data.get("chat_id")  # v9.2.0
    model_id = data.get("model_id", "") or _get_default_model()
    project_dir = data.get("project_dir", "")
    timeout = data.get("timeout") or 0
    timeout = timeout if timeout > 0 else _get_claude_timeout_sec()
    use_mcp = data.get("use_mcp", True)
    auto_approve = data.get("auto_approve", True)
    enable_rag = data.get("enable_rag", True)
    attached_files = data.get("attached_files", [])
    client_info = data.get("client_info", "Web Client")  # v9.5.0

    if not prompt:
        await ws_manager.send_error(client_id, "Prompt is empty")
        return

    # v9.5.0: Web実行ロック設定
    _set_execution_lock("cloudAI", client_info, prompt)

    # v9.2.0: チャットIDがない場合は新規作成
    if not chat_id:
        chat = chat_store.create_chat(tab="cloudAI")
        chat_id = chat["id"]
        await ws_manager.send_to(client_id, {
            "type": "chat_created",
            "chat_id": chat_id,
        })

    # ユーザーメッセージ保存
    chat_store.add_message(chat_id, "user", prompt)

    # タイトル自動生成（最初のメッセージ時）
    chat = chat_store.get_chat(chat_id)
    if chat and chat["message_count"] == 1:
        title = chat_store.auto_generate_title(chat_id)
        await ws_manager.send_to(client_id, {
            "type": "chat_title_updated",
            "chat_id": chat_id,
            "title": title,
        })

    # v9.2.0: コンテキストモードに応じたプロンプト構築
    context_result = chat_store.build_context_for_prompt(chat_id, prompt)
    full_prompt = context_result["prompt"]

    # トークン警告
    if context_result.get("warning"):
        await ws_manager.send_to(client_id, {
            "type": "token_warning",
            "message": context_result["warning"],
            "token_estimate": context_result["token_estimate"],
        })

    # RAGコンテキスト注入（フルモード以外）
    if enable_rag and context_result["mode"] != "full":
        try:
            rag_context = await rag_bridge.build_context(prompt, tab="cloudAI")
            if rag_context:
                full_prompt = f"{rag_context}\n\n{full_prompt}"
                await ws_manager.send_to(client_id, {
                    "type": "status",
                    "status": "rag_injected",
                    "message": f"RAGコンテキスト注入: {len(rag_context)}文字",
                })
        except Exception as e:
            logger.warning(f"RAG context build failed: {e}")

    # ファイル添付情報をプロンプトに追加
    if attached_files:
        file_lines = [f"- {f}" for f in attached_files]
        full_prompt += f"\n\n[添付ファイル]\n" + "\n".join(file_lines)

    # ステータス: 実行中
    ws_manager.set_active_task(client_id, "cloudAI")
    await ws_manager.send_status(client_id, "executing", f"Claude ({model_id}) 実行中...")

    # v11.5.3: Discord開始通知
    _notify_discord("cloudAI", "started", f"モデル: {model_id}\n{prompt[:200]}")

    # Claude CLI構築
    cmd = [
        "claude",
        "-p",
        "--output-format", "json",
        "--model", model_id,
    ]
    if auto_approve:
        cmd.append("--dangerously-skip-permissions")

    run_cwd = project_dir if project_dir and os.path.isdir(project_dir) else None

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_hidden(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
                env={**os.environ, "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"},
                cwd=run_cwd,
            )
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode == 0:
            try:
                output_data = json.loads(stdout)
                response_text = output_data.get("result", stdout)
            except json.JSONDecodeError:
                response_text = stdout.strip()

            # モデルサマリーを末尾に付記
            model_summary = f"\n\n---\n🤖 **使用モデル**: `{model_id}`"
            response_with_summary = response_text + model_summary

            # アシスタント応答保存（サマリー込み）
            chat_store.add_message(chat_id, "assistant", response_with_summary,
                                   metadata={"model": model_id, "mode": context_result["mode"],
                                             "tokens_estimated": context_result["token_estimate"]})

            # 完了送信（サマリー込み）
            await ws_manager.send_streaming(client_id, response_with_summary, done=True)
            await ws_manager.send_status(client_id, "completed", "実行完了")

            # v11.5.3: Discord完了通知
            _notify_discord("cloudAI", "completed", response_text[:500])

            # 会話をRAGに保存
            asyncio.ensure_future(_save_web_conversation(
                [{"role": "user", "content": prompt},
                 {"role": "assistant", "content": response_text}],
                tab="cloudAI",
            ))
        else:
            error_msg = f"Claude CLI error (code {result.returncode}): {stderr[:500]}"
            chat_store.add_message(chat_id, "error", error_msg)
            await ws_manager.send_error(client_id, error_msg)

    except subprocess.TimeoutExpired:
        await ws_manager.send_error(client_id, f"Claude CLI timed out ({timeout}s)")
        _notify_discord("cloudAI", "timeout", prompt[:200], error=f"Timeout {timeout}s")
    except FileNotFoundError:
        await ws_manager.send_error(client_id, "Claude CLI not found")
        _notify_discord("cloudAI", "error", prompt[:200], error="Claude CLI not found")
    except Exception as e:
        await ws_manager.send_error(client_id, f"Execution error: {str(e)}")
        _notify_discord("cloudAI", "error", prompt[:200], error=str(e))
    finally:
        _release_execution_lock()  # v9.5.0
        ws_manager.set_active_task(client_id, None)


# =============================================================================
# mixAI 3Phase実行ハンドラ
# =============================================================================

async def _handle_mix_execute(client_id: str, data: dict):
    """
    mixAI 3Phase実行ハンドラ。

    MixAIOrchestratorはQThread(PyQt6)前提のため、Web版では
    直接Claude CLIとOllama APIを呼び出す軽量版を実装する。

    Phase 1: Claude CLI → 計画JSON + claude_answer
    Phase 2: Ollama API → ローカルLLM順次実行
    Phase 3: Claude CLI → 比較統合 → 最終回答
    """
    prompt = data.get("prompt", "")
    chat_id = data.get("chat_id")  # v9.2.0
    model_id = data.get("model_id", "") or _get_default_model()
    # v9.3.0: orchestrator_engine（config.jsonから読み取り）
    engine_id = _load_orchestrator_engine()
    model_assignments = data.get("model_assignments", {})
    project_dir = data.get("project_dir", "")
    attached_files = data.get("attached_files", [])
    timeout = data.get("timeout") or 0
    timeout = timeout if timeout > 0 else _get_claude_timeout_sec()
    enable_rag = data.get("enable_rag", True)
    client_info = data.get("client_info", "Web Client")  # v9.5.0

    if not prompt:
        await ws_manager.send_error(client_id, "Prompt is empty")
        return

    # v9.5.0: Web実行ロック設定
    _set_execution_lock("mixAI", client_info, prompt)

    # v9.2.0: チャットIDがない場合は新規作成
    if not chat_id:
        chat = chat_store.create_chat(tab="mixAI")
        chat_id = chat["id"]
        await ws_manager.send_to(client_id, {
            "type": "chat_created",
            "chat_id": chat_id,
        })

    # ユーザーメッセージ保存
    chat_store.add_message(chat_id, "user", prompt)

    # タイトル自動生成
    chat = chat_store.get_chat(chat_id)
    if chat and chat["message_count"] == 1:
        title = chat_store.auto_generate_title(chat_id)
        await ws_manager.send_to(client_id, {
            "type": "chat_title_updated",
            "chat_id": chat_id,
            "title": title,
        })

    # v9.2.0: コンテキストモードに応じたプロンプト構築
    context_result = chat_store.build_context_for_prompt(chat_id, prompt)
    rag_prompt = context_result["prompt"]

    ws_manager.set_active_task(client_id, "mixAI")

    # v11.5.3: Discord開始通知
    _notify_discord("mixAI", "started", f"エンジン: {engine_id}\n{prompt[:200]}")

    # RAGコンテキスト注入（フルモード以外）
    if enable_rag and context_result["mode"] != "full":
        try:
            rag_context = await rag_bridge.build_context(prompt, tab="mixAI")
            if rag_context:
                rag_prompt = f"{rag_context}\n\n{rag_prompt}"
                await ws_manager.send_to(client_id, {
                    "type": "status",
                    "status": "rag_injected",
                    "message": f"RAGコンテキスト注入: {len(rag_context)}文字",
                })
        except Exception as e:
            logger.warning(f"RAG context build failed (mixAI): {e}")

    try:
        # ═══ Phase 1: 計画立案（v9.3.0: エンジン分岐） ═══
        engine_label = "ローカルLLM" if not _is_claude_engine(engine_id) else "Claude"
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 1,
            "description": f"Phase 1: {engine_label}計画立案中...",
        })

        if _is_claude_engine(engine_id):
            phase1_result = await _run_claude_cli_async(
                prompt=_build_phase1_prompt(rag_prompt),
                model_id=engine_id,
                project_dir=project_dir,
                timeout=timeout,
            )
        else:
            phase1_result = await _run_local_agent(
                prompt=_build_phase1_prompt(rag_prompt),
                model_name=engine_id,
                project_dir=project_dir,
                phase="p1",
            )

        # Phase 1結果パース
        claude_answer = phase1_result.get("claude_answer", "")
        llm_instructions = phase1_result.get("local_llm_instructions", {})
        complexity = phase1_result.get("complexity", "low")
        skip_phase2 = phase1_result.get("skip_phase2", False)

        # Phase 1のClaude回答をストリーミング送信
        if claude_answer:
            await ws_manager.send_to(client_id, {
                "type": "streaming",
                "chunk": f"**[Phase 1 Claude回答]**\n{claude_answer[:500]}...\n\n",
                "done": False,
            })

        # complexityがlowまたはskip_phase2の場合、Phase 2-3スキップ
        if skip_phase2 or complexity == "low":
            await ws_manager.send_streaming(client_id, claude_answer, done=True)
            await ws_manager.send_status(client_id, "completed", "Phase 2-3スキップ（低複雑度）")
            return

        # ═══ Phase 2: ローカルLLM順次実行 ═══
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 2,
            "description": "Phase 2: ローカルLLM順次実行中...",
        })

        tasks = _build_phase2_tasks(llm_instructions, model_assignments)
        phase2_results = []
        total_tasks = len(tasks)

        for i, task in enumerate(tasks):
            # LLM開始通知
            await ws_manager.send_to(client_id, {
                "type": "llm_started",
                "category": task["category"],
                "model": task["model"],
            })

            # Ollama API呼び出し
            start = _time.time()
            try:
                result = await _run_ollama_async(
                    model=task["model"],
                    prompt=task["prompt"],
                    timeout=task.get("timeout", 300),
                )
                elapsed = _time.time() - start
                phase2_results.append({
                    "category": task["category"],
                    "model": task["model"],
                    "response": result,
                    "success": True,
                    "elapsed": elapsed,
                })

                await ws_manager.send_to(client_id, {
                    "type": "llm_finished",
                    "category": task["category"],
                    "success": True,
                    "elapsed": round(elapsed, 1),
                })
            except Exception as e:
                elapsed = _time.time() - start
                phase2_results.append({
                    "category": task["category"],
                    "model": task["model"],
                    "response": str(e),
                    "success": False,
                    "elapsed": elapsed,
                })
                await ws_manager.send_to(client_id, {
                    "type": "llm_finished",
                    "category": task["category"],
                    "success": False,
                    "elapsed": round(elapsed, 1),
                })

            # 進捗通知
            await ws_manager.send_to(client_id, {
                "type": "phase2_progress",
                "completed": i + 1,
                "total": total_tasks,
            })

        # ═══ Phase 3: 比較統合（v9.3.0: エンジン分岐） ═══
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 3,
            "description": f"Phase 3: {engine_label}比較統合中...",
        })

        phase3_prompt = _build_phase3_prompt(prompt, claude_answer, phase2_results)
        if _is_claude_engine(engine_id):
            phase3_result = await _run_claude_cli_async(
                prompt=phase3_prompt,
                model_id=engine_id,
                project_dir=project_dir,
                timeout=timeout,
            )
        else:
            phase3_result = await _run_local_agent(
                prompt=phase3_prompt,
                model_name=engine_id,
                project_dir=project_dir,
                phase="p3",
            )

        # 最終回答抽出
        if isinstance(phase3_result, dict):
            final_answer = phase3_result.get("final_answer", str(phase3_result))
        else:
            final_answer = str(phase3_result)

        # モデルサマリーを生成（Phase2 カテゴリ別）
        p2_lines = []
        for r in phase2_results:
            status_icon = "✅" if r["success"] else "❌"
            p2_lines.append(f"  {status_icon} {r['category']}: `{r['model']}`")

        if p2_lines:
            p2_block = "\n- Phase 2 (ローカルLLM):\n" + "\n".join(p2_lines)
        else:
            p2_block = "\n- Phase 2: スキップ（低複雑度）"

        model_summary = (
            f"\n\n---\n🤖 **使用モデル**\n"
            f"- Phase 1/3 (オーケストレーター): `{engine_id}`"
            f"{p2_block}"
        )
        final_answer_with_summary = final_answer + model_summary

        # アシスタント応答保存（サマリー込み）
        chat_store.add_message(chat_id, "assistant", final_answer_with_summary,
                               metadata={"model": model_id, "mode": context_result["mode"]})

        await ws_manager.send_streaming(client_id, final_answer_with_summary, done=True)
        await ws_manager.send_status(client_id, "completed", "3Phase実行完了")

        # v11.5.3: Discord完了通知
        _notify_discord("mixAI", "completed", final_answer[:500])

        # 会話をRAGに保存
        asyncio.ensure_future(_save_web_conversation(
            [{"role": "user", "content": prompt},
             {"role": "assistant", "content": final_answer}],
            tab="mixAI",
        ))

    except Exception as e:
        await ws_manager.send_error(client_id, f"mixAI execution error: {str(e)}")
        _notify_discord("mixAI", "error", prompt[:200], error=str(e))
    finally:
        _release_execution_lock()  # v9.5.0
        ws_manager.set_active_task(client_id, None)


# =============================================================================
# mixAI ヘルパー関数
# =============================================================================

async def _run_claude_cli_async(prompt: str, model_id: str,
                                project_dir: str = "", timeout: int = 0) -> dict:
    """Claude CLIを非同期で実行"""
    if timeout <= 0:
        timeout = _get_claude_timeout_sec()
    from ..utils.subprocess_utils import run_hidden

    cmd = ["claude", "-p", "--output-format", "json", "--model", model_id,
           "--dangerously-skip-permissions"]

    run_cwd = project_dir if project_dir and os.path.isdir(project_dir) else None

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: run_hidden(
            cmd, input=prompt, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=timeout,
            env={**os.environ, "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"},
            cwd=run_cwd,
        )
    )

    stdout = result.stdout or ""
    if result.returncode == 0:
        try:
            data = json.loads(stdout)
            text = data.get("result", stdout)
        except json.JSONDecodeError:
            text = stdout.strip()

        # JSON構造の抽出を試行
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"claude_answer": text, "complexity": "low", "skip_phase2": True}
    else:
        raise RuntimeError(f"Claude CLI error (code {result.returncode})")


async def _run_ollama_async(model: str, prompt: str,
                            timeout: int = 300, host: str = "http://localhost:11434") -> str:
    """Ollama APIを非同期で呼び出し"""
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


# =============================================================================
# v9.3.0: ローカルLLMエージェント実行
# =============================================================================

def _get_default_model() -> str:
    """v11.5.0: cloud_models.json からデフォルトモデルIDを取得"""
    try:
        from ..utils.constants import get_default_claude_model
        return get_default_claude_model()
    except Exception:
        return ""


def _get_claude_timeout_sec() -> int:
    """
    設定ファイルからClaudeタイムアウト（秒）を読み取る。

    優先順位:
      1. general_settings.json → timeout_minutes（デスクトップ設定画面の値）
      2. config.json → timeout（秒単位）
      3. app_settings.json → claude.timeout_minutes
      4. デフォルト: 5400秒（90分）
    """
    timeout_sec = 5400  # デフォルト 90分

    # app_settings.json（最低優先度）
    try:
        p = Path("config/app_settings.json")
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            v = d.get("claude", {}).get("timeout_minutes")
            if v and isinstance(v, (int, float)) and v > 0:
                timeout_sec = int(v) * 60
    except Exception:
        pass

    # config.json（秒単位）
    try:
        p = Path("config/config.json")
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            v = d.get("timeout")
            if v and isinstance(v, (int, float)) and v > 0:
                timeout_sec = int(v)
    except Exception:
        pass

    # general_settings.json（最高優先度）
    try:
        p = Path("config/general_settings.json")
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            v = d.get("timeout_minutes")
            if v and isinstance(v, (int, float)) and v > 0:
                timeout_sec = int(v) * 60
    except Exception:
        pass

    return timeout_sec


def _is_claude_engine(engine_id: str) -> bool:
    """Claude CLIで実行すべきエンジンかどうか"""
    return engine_id.startswith("claude-")


def _load_orchestrator_engine() -> str:
    """config.jsonからorchestrator_engineを読み取り"""
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("orchestrator_engine") or ""
    except Exception as e:
        logger.warning(f"[server] Failed to load orchestrator engine: {e}")
    return ""


async def _run_local_agent(prompt: str, model_name: str,
                            project_dir: str, phase: str = "p1") -> dict:
    """ローカルLLMエージェントを非同期で実行"""
    # local_agent.py 自体はPyQt6に依存しないが、
    # from ..backends.local_agent だと backends/__init__.py が実行され
    # mix_orchestrator → PyQt6 の連鎖importが発生する。
    # importlib.util で .py ファイルを直接ロードして __init__.py をバイパスする。
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "src.backends.local_agent",
        str(Path(__file__).parent.parent / "backends" / "local_agent.py"),
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LocalAgentRunner = _mod.LocalAgentRunner

    config_path = Path("config/config.json")
    tools_config = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        tools_config = config.get("local_agent_tools", {})

    agent = LocalAgentRunner(
        model_name=model_name,
        project_dir=project_dir,
        tools_config=tools_config,
    )

    # Web版では書き込み自動承認
    agent.on_write_confirm = lambda tool, path, preview: True

    system_prompt = _build_local_system_prompt(phase)
    result = await asyncio.to_thread(agent.run, system_prompt, prompt)

    # JSON構造の抽出を試行
    try:
        start = result.find('{')
        end = result.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    if phase == "p1":
        return {"claude_answer": result, "complexity": "low", "skip_phase2": True}
    else:
        return {"status": "complete", "final_answer": result}


def _build_local_system_prompt(phase: str) -> str:
    """ローカルLLM用システムプロンプト"""
    if phase == "p1":
        return """あなたはソフトウェアエンジニアリングの計画立案を行うAIです。
ユーザーの質問に対して、まずプロジェクトの構造やファイルを確認し、
適切な計画を立案してください。

利用可能なツール:
- read_file: ファイルを読む
- list_dir: ディレクトリ一覧
- search_files: ファイル検索

まずプロジェクト構造を確認し、関連ファイルを読んでから回答してください。

出力は以下のJSON形式で ```json ``` で囲んでください:
{
  "claude_answer": "ユーザーへの回答（日本語）",
  "local_llm_instructions": { ... },
  "complexity": "simple|moderate|complex",
  "skip_phase2": false
}"""
    else:  # p3
        return """あなたはソフトウェアエンジニアリングの統合・レビューを行うAIです。
Phase 1の計画とPhase 2のローカルLLM実行結果を比較・統合し、
最終的な回答を生成してください。

出力は以下のJSON形式で ```json ``` で囲んでください:
{
  "status": "complete",
  "final_answer": "統合された最終回答（日本語）"
}"""


def _build_phase1_prompt(user_prompt: str) -> str:
    """Phase 1用プロンプト構築（MixAIOrchestratorの_execute_phase1相当）"""
    from src.utils.i18n import get_language
    _lang = get_language()
    _lang_line = "Respond in English." if _lang == "en" else "日本語で回答してください。"
    _answer_example = "Your direct answer" if _lang == "en" else "あなたの直接回答"
    return f"""{_lang_line}
ユーザーの質問に対して、以下の2つを提供してください:

1. あなた自身の回答 (claude_answer)
2. ローカルLLMへの指示 (local_llm_instructions)

JSON形式で出力してください:
{{
  "claude_answer": "{_answer_example}",
  "complexity": "low|medium|high",
  "skip_phase2": false,
  "local_llm_instructions": {{
    "coding": {{"skip": false, "prompt": "コーディング観点での分析指示", "expected_output": "コード例", "timeout_seconds": 300}},
    "research": {{"skip": false, "prompt": "調査観点での分析指示", "expected_output": "調査結果", "timeout_seconds": 300}},
    "reasoning": {{"skip": false, "prompt": "推論観点での分析指示", "expected_output": "推論結果", "timeout_seconds": 300}}
  }}
}}

complexity=lowの場合はskip_phase2=trueとしてください。

ユーザーの質問:
{user_prompt}"""


def _build_phase2_tasks(llm_instructions: dict, model_assignments: dict) -> list:
    """Phase 2タスクリスト構築"""
    tasks = []
    for category, spec in llm_instructions.items():
        if isinstance(spec, dict) and not spec.get("skip", True):
            model = model_assignments.get(category)
            if not model:
                continue
            prompt = spec.get("prompt", "").strip()
            if not prompt:
                continue
            tasks.append({
                "category": category,
                "model": model,
                "prompt": prompt,
                "timeout": spec.get("timeout_seconds", 300),
            })
    return tasks


def _build_phase3_prompt(user_prompt: str, claude_answer: str,
                         phase2_results: list) -> str:
    """Phase 3用プロンプト構築"""
    from src.utils.i18n import get_language
    _lang = get_language()
    _lang_line = "Respond in English." if _lang == "en" else "日本語で回答してください。"
    _answer_example = "Integrated final answer" if _lang == "en" else "統合された最終回答"
    results_text = ""
    for r in phase2_results:
        if r["success"]:
            results_text += f"\n### {r['category']} ({r['model']})\n{r['response'][:5000]}\n"

    return f"""{_lang_line}
以下の情報を統合して、最高品質の最終回答を作成してください。

## ユーザーの質問
{user_prompt}

## Phase 1 Claude回答
{claude_answer[:8000]}

## Phase 2 ローカルLLM結果
{results_text}

## 指示
全ての情報を統合し、最終回答をJSON形式で出力してください:
{{"final_answer": "{_answer_example}"}}"""


# =============================================================================
# 会話保存ヘルパー
# =============================================================================

async def _save_web_conversation(messages: list, tab: str):
    """Web会話をRAGに非同期保存（エラー無視）"""
    try:
        session_id = await rag_bridge.save_conversation(messages, tab)
        logger.info(f"Web conversation saved to RAG: {session_id}")
    except Exception as e:
        logger.warning(f"Conversation save failed: {e}")


# =============================================================================
# サーバー起動（スタンドアロン）
# =============================================================================

def start_server(host: str = "0.0.0.0", port: int = 8500):
    """Uvicornでサーバーを起動"""
    import uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


# =============================================================================
# PyQt6統合: バックグラウンドサーバー起動
# =============================================================================

import threading


class WebServerThread:
    """PyQt6から起動するWeb UIサーバースレッド"""

    def __init__(self, host="0.0.0.0", port=8500):
        self.host = host
        self.port = port
        self._thread = None
        self._server = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        import uvicorn
        config = uvicorn.Config(app, host=self.host, port=self.port,
                                log_level="info")
        self._server = uvicorn.Server(config)
        self._server.run()

    def stop(self):
        if self._server:
            self._server.should_exit = True

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()


def start_server_background(port=8500) -> WebServerThread:
    """PyQt6からバックグラウンドでサーバーを起動（同一プロセス版、直接使用非推奨）

    NOTE: PyQt6の設定画面からはlauncher.pyのstart_server_backgroundを使用すること。
    このモジュールをimportするとfastapiのトップレベルimportが走るため、
    fastapi未インストール環境ではImportErrorが発生する。
    """
    server = WebServerThread(port=port)
    server.start()
    return server


if __name__ == "__main__":
    import sys

    # HELIX_WEB_SERVER_ONLY=1 の場合はサーバーのみ起動（PyQt6ウィンドウを開かない）
    if os.environ.get("HELIX_WEB_SERVER_ONLY") != "1":
        print("Warning: HELIX_WEB_SERVER_ONLY is not set. "
              "If launched from PyQt6, set this env var to prevent GUI spawn.",
              file=sys.stderr)

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8500
    start_server(port=port)
