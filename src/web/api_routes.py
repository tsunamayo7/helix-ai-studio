"""
Helix AI Studio - REST API Routes (v9.3.0)

エンドポイント:
  POST /api/auth/login           - PIN認証 → JWT取得
  GET  /api/auth/verify          - JWT検証
  GET  /api/status               - サーバーステータス
  POST /api/solo/execute         - soloAI実行（非ストリーミング）
  GET  /api/config/models        - 利用可能モデル一覧
  GET  /api/config/ollama-models - Ollamaモデル一覧
  GET  /api/settings             - 設定取得
  PUT  /api/settings             - 設定更新
  GET  /api/monitor/gpu          - GPUモニター
  GET  /api/files/browse         - ファイルブラウザ
  GET  /api/health               - ヘルスチェック（認証不要）
  GET  /api/chats                - チャット一覧
  POST /api/chats                - 新規チャット作成
  GET  /api/chats/{chat_id}      - チャット詳細+メッセージ
  PUT  /api/chats/{chat_id}/title - タイトル更新
  PUT  /api/chats/{chat_id}/mode  - コンテキストモード変更
  DELETE /api/chats/{chat_id}    - チャット削除
  GET  /api/chats/storage/stats  - ストレージ統計
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .auth import WebAuthManager
from .file_transfer import UPLOAD_MAX_SIZE_BYTES, UPLOAD_MAX_SIZE_MB, UPLOAD_ALLOWED_EXTENSIONS, validate_upload

logger = logging.getLogger(__name__)

# =============================================================================
# リクエスト/レスポンスモデル
# =============================================================================

class LoginRequest(BaseModel):
    pin: str

class LoginResponse(BaseModel):
    token: str
    expires_in_hours: int

class SoloExecuteRequest(BaseModel):
    prompt: str
    model_id: str = ""
    attached_files: list[str] = []
    project_dir: str = ""
    timeout: int = 0  # 0 = 設定ファイルから読み込み
    use_mcp: bool = True
    auto_approve: bool = True

class StatusResponse(BaseModel):
    status: str
    version: str
    pyqt_running: bool
    active_websockets: int
    rag_locked: bool

class ModelInfo(BaseModel):
    id: str
    display_name: str
    description: str
    tier: str
    is_default: bool

# =============================================================================
# 依存性注入: 認証チェック
# =============================================================================

security = HTTPBearer()
auth_manager = WebAuthManager()

# v11.2.1: ブルートフォース対策
_login_attempts: dict = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
LOGIN_LOCKOUT_SECONDS = 900


async def verify_jwt(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """JWT認証の依存性注入"""
    # IP チェック
    client_ip = request.client.host
    if not auth_manager.check_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not in allowed range")

    # JWT検証
    payload = auth_manager.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload

# =============================================================================
# ルーター定義
# =============================================================================

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """ヘルスチェック（認証不要）"""
    return {"status": "ok", "service": "helix-ai-studio", "version": "9.6.0"}


# =============================================================================
# v9.5.0: Web実行ロック
# =============================================================================

@router.get("/api/execution/lock")
async def get_execution_lock(payload: dict = Depends(verify_jwt)):
    """現在のロック状態取得"""
    lock_file = Path("data/web_execution_lock.json")
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding='utf-8'))
            return data
        except Exception:
            pass
    return {"locked": False}


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    """PIN認証 → JWT発行"""
    client_ip = request.client.host

    # IPチェック
    if not auth_manager.check_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not in allowed range")

    # v11.2.1: レート制限チェック
    now = time.time()
    attempts = _login_attempts[client_ip]
    # 古いタイムスタンプを除去
    _login_attempts[client_ip] = [t for t in attempts if now - t < LOGIN_WINDOW_SECONDS]
    attempts = _login_attempts[client_ip]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        oldest = min(attempts)
        retry_after = int(LOGIN_LOCKOUT_SECONDS - (now - oldest))
        logger.warning(f"Login rate limit exceeded from {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    # PIN検証
    if not auth_manager.verify_pin(body.pin):
        _login_attempts[client_ip].append(now)
        logger.warning(f"Failed login attempt from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid PIN")

    # 認証成功: 試行履歴をクリア
    _login_attempts[client_ip] = []

    # JWT発行
    token = auth_manager.create_token(client_ip)
    logger.info(f"Login successful from {client_ip}")

    return LoginResponse(
        token=token,
        expires_in_hours=auth_manager.jwt_expiry_hours,
    )


@router.get("/api/auth/verify")
async def verify_auth(payload: dict = Depends(verify_jwt)):
    """JWTトークン検証"""
    return {"valid": True, "sub": payload.get("sub")}


@router.get("/api/status", response_model=StatusResponse)
async def get_status(payload: dict = Depends(verify_jwt)):
    """サーバーステータス取得"""
    # WebSocketマネージャーはserver.pyから注入される（後述）
    from .server import get_app_state
    state = get_app_state()

    return StatusResponse(
        status="running",
        version="9.6.0",
        pyqt_running=state.get("pyqt_running", False),
        active_websockets=state.get("active_websockets", 0),
        rag_locked=state.get("rag_locked", False),
    )


@router.get("/api/config/models", response_model=list[ModelInfo])
async def get_models(payload: dict = Depends(verify_jwt)):
    """v11.5.0: cloud_models.json からモデル一覧を動的取得"""
    models = []
    try:
        config_path = Path("config/cloud_models.json")
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            model_list = data.get("models", []) if isinstance(data, dict) else data
            for i, m in enumerate(model_list):
                models.append(ModelInfo(
                    id=m.get("model_id", ""),
                    display_name=m.get("name", m.get("display_name", m.get("model_id", ""))),
                    description=m.get("provider", ""),
                    tier=m.get("provider", "unknown"),
                    is_default=(i == 0),
                ))
    except Exception as e:
        logger.warning(f"Failed to load cloud_models.json: {e}")
    return models


@router.post("/api/solo/execute")
async def solo_execute(body: SoloExecuteRequest, payload: dict = Depends(verify_jwt)):
    """
    soloAI実行（非ストリーミング / REST版）。
    ストリーミング版はWebSocketで別途提供。
    軽量なリクエスト向け。
    """
    from ..utils.subprocess_utils import run_hidden

    cmd = [
        "claude",
        "-p",
        "--output-format", "json",
        "--model", body.model_id,
    ]

    if body.auto_approve:
        cmd.append("--dangerously-skip-permissions")

    run_cwd = body.project_dir if body.project_dir and os.path.isdir(body.project_dir) else None

    # timeout=0 の場合は設定ファイルから読み込み
    effective_timeout = body.timeout
    if effective_timeout <= 0:
        from .server import _get_claude_timeout_sec
        effective_timeout = _get_claude_timeout_sec()

    try:
        result = run_hidden(
            cmd,
            input=body.prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=effective_timeout,
            env={**os.environ, "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"},
            cwd=run_cwd,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode == 0:
            try:
                output_data = json.loads(stdout)
                response_text = output_data.get("result", stdout)
            except json.JSONDecodeError:
                response_text = stdout.strip()

            return {
                "status": "success",
                "response": response_text,
                "model": body.model_id,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Claude CLI error (code {result.returncode}): {stderr[:500]}",
            )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail=f"Claude CLI timed out ({effective_timeout}s)",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Claude CLI not found. Is 'claude' command installed?",
        )


# =============================================================================
# ファイルブラウザAPI
# =============================================================================

ALLOWED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.md', '.txt',
                      '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini',
                      '.html', '.css', '.sql', '.sh', '.bat', '.ps1',
                      '.csv', '.xml', '.env', '.gitignore', '.dockerfile'}
MAX_BROWSE_DEPTH = 3
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                 '.mypy_cache', '.pytest_cache', 'dist', 'build', '.egg-info'}


class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    extension: str = ""


@router.get("/api/files/browse", response_model=list[FileItem])
async def browse_files(
    dir_path: str = "",
    payload: dict = Depends(verify_jwt),
):
    """
    ディレクトリ内のファイル一覧を取得。
    セキュリティ: パストラバーサル防止 + ホワイトリスト拡張子のみ。
    """
    # config/config.jsonからproject_dirを取得
    project_dir = _get_project_dir()
    if not project_dir:
        raise HTTPException(status_code=400, detail="Project directory not configured")

    # パストラバーサル防止
    if dir_path:
        target = Path(project_dir) / dir_path
        try:
            target.resolve().relative_to(Path(project_dir).resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal detected")
    else:
        target = Path(project_dir)

    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith('.') and entry.name not in ('.env', '.gitignore'):
                continue
            if entry.is_dir() and entry.name in EXCLUDED_DIRS:
                continue

            item = FileItem(
                name=entry.name,
                path=str(entry.relative_to(Path(project_dir))),
                is_dir=entry.is_dir(),
                size=entry.stat().st_size if entry.is_file() else 0,
                extension=entry.suffix.lower() if entry.is_file() else "",
            )
            items.append(item)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return items


def _get_project_dir() -> str | None:
    """config/config.jsonからproject_dirを取得"""
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("project_dir", "")
    except Exception as e:
        logger.warning(f"[api_routes] Failed to load project_dir: {e}")
    return None


# =============================================================================
# 設定 API (GET/PUT)
# =============================================================================

class SettingsResponse(BaseModel):
    claude_model_id: str = ""
    claude_timeout_minutes: int = 90
    model_assignments: dict = {}
    orchestrator_engine: str = ""
    local_agent_tools: dict = {}
    project_dir: str = ""
    ollama_host: str = "http://localhost:11434"
    pin: str = ""
    jwt_expiry_hours: int = 168
    max_connections: int = 3


@router.get("/api/settings", response_model=SettingsResponse)
async def get_settings(payload: dict = Depends(verify_jwt)):
    """設定取得（デスクトップ設定ファイル読み取り専用 + web_config.json統合）"""
    settings = _load_merged_settings()
    settings["pin"] = ""  # PINは表示しない
    return settings


class SettingsUpdate(BaseModel):
    pin: str | None = None
    jwt_expiry_hours: int | None = None
    claude_timeout_minutes: int | None = None
    language: str | None = None


@router.put("/api/settings")
async def update_settings(update: SettingsUpdate, payload: dict = Depends(verify_jwt)):
    """Web UI設定を更新（PIN, JWT有効期限, Claudeタイムアウト）"""
    web_config_path = Path("config/web_config.json")

    if web_config_path.exists():
        with open(web_config_path, 'r', encoding='utf-8') as f:
            full_web_config = json.load(f)
    else:
        full_web_config = {}

    web_server = full_web_config.get("web_server", {})

    if update.pin and len(update.pin) >= 4:
        web_server["pin"] = update.pin
    if update.jwt_expiry_hours:
        web_server["jwt_expiry_hours"] = update.jwt_expiry_hours

    full_web_config["web_server"] = web_server
    with open(web_config_path, 'w', encoding='utf-8') as f:
        json.dump(full_web_config, f, ensure_ascii=False, indent=2)

    # general_settings.json に保存（デスクトップ/Web共通）
    gs_updated = False
    try:
        gs_path = Path("config/general_settings.json")
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
        else:
            gs = {}

        if update.claude_timeout_minutes and update.claude_timeout_minutes > 0:
            gs["timeout_minutes"] = update.claude_timeout_minutes
            gs_updated = True
            logger.info(f"Claude timeout updated to {update.claude_timeout_minutes} minutes")

        if update.language and update.language in ('ja', 'en'):
            gs["language"] = update.language
            gs_updated = True
            logger.info(f"Language updated to {update.language}")

        if gs_updated:
            with open(gs_path, 'w', encoding='utf-8') as f:
                json.dump(gs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save general_settings: {e}")

    return {"status": "ok", "message": "設定を保存しました"}


def _load_merged_settings() -> dict:
    """general_settings.json + app_settings.json + config.json + web_config.json を統合読み込み"""
    from ..utils.constants import get_default_claude_model
    _default_model = get_default_claude_model()
    result = {
        "claude_model_id": _default_model,
        "claude_timeout_minutes": 90,
        "model_assignments": {},
        "orchestrator_engine": _default_model,
        "local_agent_tools": {},
        "project_dir": "",
        "ollama_host": "http://localhost:11434",
        "pin": "",
        "jwt_expiry_hours": 168,
        "max_connections": 3,
    }

    # app_settings.json（デスクトップアプリ設定 - 読み取り専用）
    try:
        app_settings_path = Path("config/app_settings.json")
        if app_settings_path.exists():
            with open(app_settings_path, 'r', encoding='utf-8') as f:
                app_settings = json.load(f)
            claude = app_settings.get("claude", {})
            if claude.get("default_model"):
                result["claude_model_id"] = claude["default_model"]
            if claude.get("timeout_minutes"):
                result["claude_timeout_minutes"] = claude["timeout_minutes"]
            app_mgr = app_settings.get("app_manager", {})
            if app_mgr.get("base_directory"):
                result["project_dir"] = app_mgr["base_directory"]
    except Exception:
        pass

    # config.json（デスクトップアプリ設定 - 読み取り専用）
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if config.get("claude_model_id"):
                result["claude_model_id"] = config["claude_model_id"]
            if config.get("timeout"):
                result["claude_timeout_minutes"] = config["timeout"] // 60
            if config.get("model_assignments"):
                result["model_assignments"] = config["model_assignments"]
            if config.get("project_dir"):
                result["project_dir"] = config["project_dir"]
            if config.get("ollama_host"):
                result["ollama_host"] = config["ollama_host"]
            # v9.3.0
            if config.get("orchestrator_engine"):
                result["orchestrator_engine"] = config["orchestrator_engine"]
            if config.get("local_agent_tools"):
                result["local_agent_tools"] = config["local_agent_tools"]
    except Exception:
        pass

    # general_settings.json（デスクトップ設定画面の値 - タイムアウト最高優先度）
    try:
        gs_path = Path("config/general_settings.json")
        if gs_path.exists():
            with open(gs_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)
            if gs.get("timeout_minutes"):
                result["claude_timeout_minutes"] = gs["timeout_minutes"]
    except Exception:
        pass

    # web_config.json（Web UI固有設定 - 編集可能）
    try:
        web_config_path = Path("config/web_config.json")
        if web_config_path.exists():
            with open(web_config_path, 'r', encoding='utf-8') as f:
                full_web = json.load(f)
            web_server = full_web.get("web_server", {})
            result["jwt_expiry_hours"] = web_server.get("jwt_expiry_hours", result["jwt_expiry_hours"])
            result["max_connections"] = web_server.get("max_concurrent_sessions", result["max_connections"])
    except Exception:
        pass

    return result


# =============================================================================
# Ollamaモデル一覧
# =============================================================================

@router.get("/api/config/ollama-models")
async def get_ollama_models(payload: dict = Depends(verify_jwt)):
    """Ollama APIから利用可能なモデル一覧を取得"""
    import httpx
    settings = _load_merged_settings()
    ollama_host = settings.get("ollama_host", "http://localhost:11434")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            resp.raise_for_status()
            models_data = resp.json().get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size": _format_size(m.get("size", 0)),
                    "modified": m.get("modified_at", ""),
                }
                for m in models_data
            ]
    except Exception:
        return []


def _format_size(size_bytes: int) -> str:
    """バイト数を人間可読形式に変換"""
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.0f}KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f}MB"
    else:
        return f"{size_bytes / (1024 ** 3):.1f}GB"


# =============================================================================
# GPUモニター
# =============================================================================

@router.get("/api/monitor/gpu")
async def get_gpu_info(payload: dict = Depends(verify_jwt)):
    """nvidia-smi経由でGPU情報を取得"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )

        if result.returncode != 0:
            return {"gpus": [], "error": "nvidia-smi failed"}

        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append({
                    "name": parts[0],
                    "memory_used": int(float(parts[1])),
                    "memory_total": int(float(parts[2])),
                    "utilization": int(float(parts[3])),
                    "temperature": int(float(parts[4])),
                    "power_draw": round(float(parts[5]), 1),
                })

        return {"gpus": gpus}

    except FileNotFoundError:
        return {"gpus": [], "error": "nvidia-smi not found"}
    except Exception as e:
        return {"gpus": [], "error": str(e)}


# =============================================================================
# ファイル内容読み書きAPI (v9.1.0)
# =============================================================================

VIEWABLE_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.jsx', '.ts', '.tsx',
                       '.json', '.yaml', '.yml', '.toml', '.html', '.css',
                       '.sql', '.sh', '.bat', '.csv', '.xml', '.env',
                       '.gitignore', '.cfg', '.ini', '.log'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
MAX_FILE_READ_SIZE = 1024 * 1024  # 1MB


@router.get("/api/files/content")
async def read_file_content(
    file_path: str,
    payload: dict = Depends(verify_jwt),
):
    """ファイル内容を取得。テキストは文字列、画像はbase64。"""
    project_dir = _get_project_dir()
    if not project_dir:
        raise HTTPException(status_code=400, detail="Project directory not configured")

    target = Path(project_dir) / file_path
    try:
        target.resolve().relative_to(Path(project_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = target.suffix.lower()
    file_size = target.stat().st_size

    if file_size > MAX_FILE_READ_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 1MB)")

    if ext in VIEWABLE_EXTENSIONS:
        try:
            content = target.read_text(encoding='utf-8', errors='replace')
            return {"type": "text", "content": content, "extension": ext,
                    "size": file_size, "path": file_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif ext in IMAGE_EXTENSIONS:
        import base64
        content_bytes = target.read_bytes()
        b64 = base64.b64encode(content_bytes).decode('ascii')
        mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
                '.svg': 'image/svg+xml'}.get(ext, 'application/octet-stream')
        return {"type": "image", "content": b64, "mime": mime,
                "extension": ext, "size": file_size, "path": file_path}

    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")


class FileWriteRequest(BaseModel):
    content: str


@router.put("/api/files/content")
async def write_file_content(
    file_path: str,
    request: FileWriteRequest,
    payload: dict = Depends(verify_jwt),
):
    """テキストファイルの内容を上書き保存。"""
    project_dir = _get_project_dir()
    if not project_dir:
        raise HTTPException(status_code=400, detail="Project directory not configured")

    target = Path(project_dir) / file_path
    try:
        target.resolve().relative_to(Path(project_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal detected")

    ext = target.suffix.lower()
    if ext not in VIEWABLE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only text files can be edited")

    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        target.write_text(request.content, encoding='utf-8')
        return {"status": "ok", "size": len(request.content.encode('utf-8')), "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RAGステータスAPI (v9.1.0)
# =============================================================================

@router.get("/api/rag/status")
async def rag_status(payload: dict = Depends(verify_jwt)):
    """RAG状態（ロック状態 + 統計）"""
    from .rag_bridge import WebRAGBridge
    bridge = WebRAGBridge()
    lock = bridge.is_rag_locked()

    stats = {}
    try:
        from ..rag.rag_builder import RAGBuilder
        builder = RAGBuilder(folder_path="data/information")
        stats = builder.get_rag_stats()
    except Exception:
        pass

    return {"lock": lock, "stats": stats}


class RAGSearchRequest(BaseModel):
    query: str


@router.post("/api/rag/search")
async def rag_search(request: RAGSearchRequest, payload: dict = Depends(verify_jwt)):
    """RAG検索（デバッグ用）"""
    from .rag_bridge import WebRAGBridge
    bridge = WebRAGBridge()
    context = await bridge.build_context(request.query)
    return {"context": context, "length": len(context)}


# =============================================================================
# チャット履歴 API (v9.2.0)
# =============================================================================

from .chat_store import ChatStore

chat_store = ChatStore()


@router.get("/api/chats/storage/stats")
async def storage_stats(payload: dict = Depends(verify_jwt)):
    """ストレージ統計"""
    return chat_store.get_storage_stats()


@router.get("/api/chats")
async def list_chats(tab: str = None, payload: dict = Depends(verify_jwt)):
    """チャット一覧取得"""
    chats = chat_store.list_chats(tab=tab)
    return {"chats": chats}


@router.post("/api/chats")
async def create_chat(tab: str = "cloudAI", context_mode: str = "session",
                      payload: dict = Depends(verify_jwt)):
    """新規チャット作成"""
    chat = chat_store.create_chat(tab=tab, context_mode=context_mode)
    return chat


@router.get("/api/chats/{chat_id}")
async def get_chat_detail(chat_id: str, payload: dict = Depends(verify_jwt)):
    """チャット詳細 + メッセージ取得"""
    chat = chat_store.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = chat_store.get_messages(chat_id)
    return {"chat": chat, "messages": messages}


class TitleUpdate(BaseModel):
    title: str


@router.put("/api/chats/{chat_id}/title")
async def update_title(chat_id: str, body: TitleUpdate, payload: dict = Depends(verify_jwt)):
    """タイトル更新"""
    chat_store.update_chat_title(chat_id, body.title)
    return {"status": "ok"}


class ModeUpdate(BaseModel):
    mode: str


@router.put("/api/chats/{chat_id}/mode")
async def update_mode(chat_id: str, body: ModeUpdate, payload: dict = Depends(verify_jwt)):
    """コンテキストモード変更"""
    chat_store.update_context_mode(chat_id, body.mode)
    return {"status": "ok", "mode": body.mode}


@router.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str, payload: dict = Depends(verify_jwt)):
    """チャット削除"""
    chat_store.delete_chat(chat_id)
    return {"status": "ok"}


# =============================================================================
# v9.5.0: ファイルアップロード / 転送 API
# =============================================================================

UPLOAD_DIR = Path("data/web_uploads")


@router.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...),
                      payload: dict = Depends(verify_jwt)):
    """モバイルからファイルをアップロード"""
    filename = file.filename or "unnamed_file"
    logger.info(f"Upload request: filename={filename}, size={file.size}, content_type={file.content_type}")

    error = validate_upload(filename, file.size)
    if error:
        raise HTTPException(status_code=400, detail=error)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # v11.2.1: パストラバーサル防止 — ベース名のみ取得し特殊文字をアンダースコアに置換
    base_name = Path(filename).name
    safe_base = re.sub(r'[^\w\-.]', '_', base_name)
    safe_name = f"{timestamp}_{safe_base}"
    save_path = UPLOAD_DIR / safe_name
    if not save_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # ストリーミング書き込み（メモリ効率）
    total_size = 0
    with open(save_path, 'wb') as f:
        while chunk := await file.read(1024 * 64):  # 64KB chunks
            total_size += len(chunk)
            if total_size > UPLOAD_MAX_SIZE_BYTES:
                save_path.unlink(exist_ok=True)
                raise HTTPException(status_code=413,
                    detail=f"ファイルサイズ上限 ({UPLOAD_MAX_SIZE_MB}MB) 超過")
            f.write(chunk)

    return {
        "status": "ok",
        "filename": safe_name,
        "original_name": filename,
        "size": total_size,
        "path": str(save_path),
    }


@router.get("/api/files/uploads")
async def list_uploads(payload: dict = Depends(verify_jwt)):
    """アップロード済みファイル一覧"""
    if not UPLOAD_DIR.exists():
        return {"files": []}
    files = []
    for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files}


@router.delete("/api/files/uploads/{filename}")
async def delete_upload(filename: str, payload: dict = Depends(verify_jwt)):
    """アップロードファイル削除"""
    target = UPLOAD_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        target.resolve().relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    target.unlink()
    return {"status": "ok"}


@router.get("/api/files/download")
async def download_file(path: str, payload: dict = Depends(verify_jwt)):
    """サーバー上のファイルをモバイル端末にダウンロード"""
    project_dir = _get_project_dir()
    if not project_dir:
        raise HTTPException(status_code=400, detail="Project directory not configured")

    target = Path(project_dir) / path

    # パストラバーサル防止
    try:
        target.resolve().relative_to(Path(project_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # サイズ制限
    if target.stat().st_size > UPLOAD_MAX_SIZE_BYTES:
        raise HTTPException(status_code=413,
            detail=f"ファイルサイズが上限 ({UPLOAD_MAX_SIZE_MB}MB) を超えています")

    # 拡張子チェック
    if target.suffix.lower() not in UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"非対応の拡張子: {target.suffix}")

    return FileResponse(path=str(target), filename=target.name,
                        media_type="application/octet-stream")


@router.post("/api/files/copy-to-project")
async def copy_upload_to_project(filename: str, dest_dir: str = "",
                                  payload: dict = Depends(verify_jwt)):
    """アップロードファイルをプロジェクトディレクトリにコピー（モバイル→Windows）"""
    source = UPLOAD_DIR / filename
    if not source.exists():
        raise HTTPException(status_code=404, detail="Upload not found")

    project_dir = Path(_get_project_dir())
    # タイムスタンププレフィックス除去（YYYYMMDD_HHMMSS_originalname）
    original_name = "_".join(filename.split("_")[2:]) if filename.count("_") >= 2 else filename
    dest = project_dir / dest_dir / original_name

    # パストラバーサル防止
    try:
        dest.resolve().relative_to(project_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)

    return {"status": "ok", "path": str(dest.relative_to(project_dir))}


# =============================================================================
# v9.5.0: ログアウト後チャット閲覧（認証不要）
# =============================================================================

@router.get("/api/chats/public-list")
async def public_chat_list(limit: int = 10):
    """認証不要: 直近チャットのタイトル+プレビューを返す

    注意: JWT認証なし。Tailscale VPN内アクセス前提。
    チャット本文は含まない。タイトルとプレビュー（50文字）のみ。
    """
    try:
        from .chat_store import ChatStore
        store = ChatStore()
        chats = store.list_chats(limit=limit)

        public_chats = []
        for chat in chats:
            # 最初のユーザーメッセージからプレビューを抽出
            preview = ""
            first_assistant = ""
            messages = store.get_messages(chat["id"], limit=2)
            for msg in messages:
                if msg["role"] == "user" and not preview:
                    preview = msg["content"][:50]
                if msg["role"] == "assistant" and not first_assistant:
                    first_assistant = msg["content"][:50]

            public_chats.append({
                "id": chat["id"],
                "title": chat.get("title", "無題"),
                "tab": chat.get("tab", "cloudAI"),
                "created_at": chat.get("created_at", ""),
                "updated_at": chat.get("updated_at", ""),
                "message_count": chat.get("message_count", 0),
                "user_preview": preview,
                "assistant_preview": first_assistant,
            })

        return {"chats": public_chats, "total": len(public_chats)}
    except Exception as e:
        return {"chats": [], "total": 0, "error": str(e)}
