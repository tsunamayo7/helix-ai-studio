# Helix AI Studio v9.0.0 Phase 1: Web UI基盤構築
## 実装指示書（Claude Code CLI用）

**作成日**: 2026-02-15
**対象**: Phase 1 — FastAPI + WebSocket + 認証 + soloAI Web対応 + React基盤
**想定期間**: 3-4日
**原則**: 既存コードの変更ゼロ。全て新規ファイル追加のみ。

---

## 1. Phase 1 の目標

Phase 1完了時に達成されるべき状態:

1. FastAPIサーバーがポート8500で起動し、Tailscale VPN経由でiPhone/iPadからアクセス可能
2. PIN + JWT認証でセキュアなアクセス制御
3. soloAI（Claude CLI単体）がWebブラウザから実行可能（WebSocketストリーミング対応）
4. React基盤UIがモバイルレスポンシブで動作
5. 既存PyQt6アプリケーションに一切の変更なし

---

## 2. ディレクトリ構造（新規追加のみ）

```
helix-ai-studio/
├── src/
│   ├── backends/          ← 変更なし
│   ├── rag/               ← 変更なし
│   ├── tabs/              ← 変更なし
│   ├── web/               ← ★ 新規ディレクトリ
│   │   ├── __init__.py
│   │   ├── server.py          # FastAPI + Uvicornサーバー起動
│   │   ├── auth.py            # PIN + JWT認証
│   │   ├── api_routes.py      # REST APIエンドポイント
│   │   ├── ws_manager.py      # WebSocket接続管理
│   │   └── signal_bridge.py   # pyqtSignal → WebSocket ブリッジ
│   └── utils/             ← 変更なし
├── frontend/              ← ★ 新規ディレクトリ
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   │   ├── manifest.json      # PWA用
│   │   └── icon-192.png       # PWAアイコン
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   ├── client.js      # REST APIクライアント
│       │   └── websocket.js   # WebSocket管理
│       ├── components/
│       │   ├── LoginScreen.jsx     # PIN入力画面
│       │   ├── ChatView.jsx        # チャットメッセージ表示
│       │   ├── InputBar.jsx        # メッセージ入力バー
│       │   ├── StatusIndicator.jsx # 接続状態表示
│       │   └── MarkdownRenderer.jsx # Markdown表示
│       ├── hooks/
│       │   ├── useAuth.js      # 認証フック
│       │   └── useWebSocket.js # WebSocket接続フック
│       └── styles/
│           └── globals.css     # Tailwind CSS
└── config/
    └── web_config.json    ← ★ 新規（Web UI設定）
```

---

## 3. バックエンド実装

### 3.1 `config/web_config.json` — Web UI設定

```json
{
  "web_server": {
    "enabled": false,
    "host": "0.0.0.0",
    "port": 8500,
    "pin": "000000",
    "jwt_secret": "",
    "jwt_expiry_hours": 168,
    "allowed_tailscale_subnet": "100.64.0.0/10",
    "cors_origins": ["*"],
    "max_concurrent_sessions": 3
  }
}
```

**実装ノート**:
- `jwt_secret` が空の場合、初回起動時に `secrets.token_hex(32)` で自動生成して保存
- `pin` はデフォルト "000000"。ユーザーがPyQt6設定画面またはこのJSONで変更
- `allowed_tailscale_subnet` で Tailscale IP範囲外のアクセスを拒否

---

### 3.2 `src/web/__init__.py`

```python
"""Helix AI Studio - Web UI Server (v9.0.0)"""
```

---

### 3.3 `src/web/auth.py` — 認証モジュール

```python
"""
Helix AI Studio - Web認証 (v9.0.0)
Tailscale IP制限 + PIN + JWT認証

セキュリティレイヤー:
  Layer 1: Tailscale VPN（ネットワークレベル）
  Layer 2: IP範囲チェック（100.64.0.0/10 = Tailscaleサブネット）
  Layer 3: PIN認証 → JWTトークン発行
  Layer 4: JWT Bearer認証（APIリクエスト毎）
"""

import ipaddress
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt  # PyJWT

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/web_config.json")
DEFAULT_JWT_EXPIRY_HOURS = 168  # 7日間


class WebAuthManager:
    """Web UI認証マネージャー"""

    def __init__(self):
        self._config = self._load_config()
        self._ensure_jwt_secret()

    def _load_config(self) -> dict:
        """設定読み込み"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f).get("web_server", {})
        return {}

    def _save_config(self, config: dict):
        """設定保存"""
        full_config = {"web_server": config}
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)

    def _ensure_jwt_secret(self):
        """JWTシークレットが未設定なら自動生成"""
        if not self._config.get("jwt_secret"):
            self._config["jwt_secret"] = secrets.token_hex(32)
            self._save_config(self._config)
            logger.info("JWT secret auto-generated and saved")

    @property
    def pin(self) -> str:
        return self._config.get("pin", "000000")

    @property
    def jwt_secret(self) -> str:
        return self._config["jwt_secret"]

    @property
    def jwt_expiry_hours(self) -> int:
        return self._config.get("jwt_expiry_hours", DEFAULT_JWT_EXPIRY_HOURS)

    @property
    def allowed_subnet(self) -> str:
        return self._config.get("allowed_tailscale_subnet", "100.64.0.0/10")

    def check_ip(self, client_ip: str) -> bool:
        """
        Tailscale IPサブネットチェック。
        ローカルホスト（127.0.0.1, ::1）は常に許可。
        """
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return True
        try:
            addr = ipaddress.ip_address(client_ip)
            network = ipaddress.ip_network(self.allowed_subnet, strict=False)
            return addr in network
        except ValueError:
            logger.warning(f"Invalid IP address: {client_ip}")
            return False

    def verify_pin(self, pin_input: str) -> bool:
        """PIN照合"""
        return secrets.compare_digest(pin_input, self.pin)

    def create_token(self, client_ip: str) -> str:
        """JWT発行"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "helix_web_user",
            "iat": now,
            "exp": now + timedelta(hours=self.jwt_expiry_hours),
            "ip": client_ip,
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_token(self, token: str) -> dict | None:
        """JWT検証。成功時にペイロードを返す。失敗時にNone。"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.info("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
```

**依存パッケージ**: `pip install PyJWT`

---

### 3.4 `src/web/ws_manager.py` — WebSocket接続マネージャー

```python
"""
Helix AI Studio - WebSocket接続管理 (v9.0.0)

WebSocket接続のライフサイクル管理:
  - 接続プール管理
  - 認証済み接続のみ保持
  - ブロードキャスト / ユニキャスト送信
  - 自動切断 (ping/pong)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """WebSocket接続クライアント"""
    websocket: WebSocket
    client_id: str
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    active_task: Optional[str] = None  # "soloAI" / "mixAI" / None


class WebSocketManager:
    """WebSocket接続プールマネージャー"""

    def __init__(self, max_connections: int = 3):
        self._clients: dict[str, WebSocketClient] = {}
        self._max_connections = max_connections
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """
        WebSocket接続を受け入れ。
        最大接続数を超える場合はFalseを返す。
        """
        async with self._lock:
            if len(self._clients) >= self._max_connections:
                logger.warning(f"Max WebSocket connections reached ({self._max_connections})")
                return False

            await websocket.accept()
            self._clients[client_id] = WebSocketClient(
                websocket=websocket,
                client_id=client_id,
            )
            logger.info(f"WebSocket connected: {client_id} (total: {len(self._clients)})")
            return True

    async def disconnect(self, client_id: str):
        """WebSocket切断"""
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"WebSocket disconnected: {client_id} (total: {len(self._clients)})")

    async def send_to(self, client_id: str, message: dict):
        """特定クライアントにJSON送信"""
        client = self._clients.get(client_id)
        if client:
            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket send error to {client_id}: {e}")
                await self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: str = None):
        """全クライアントにブロードキャスト"""
        disconnected = []
        for cid, client in self._clients.items():
            if cid == exclude:
                continue
            try:
                await client.websocket.send_json(message)
            except Exception:
                disconnected.append(cid)

        for cid in disconnected:
            await self.disconnect(cid)

    async def send_streaming(self, client_id: str, chunk: str, done: bool = False):
        """ストリーミングチャンク送信"""
        await self.send_to(client_id, {
            "type": "streaming",
            "chunk": chunk,
            "done": done,
        })

    async def send_status(self, client_id: str, status: str, detail: str = ""):
        """ステータス更新送信"""
        await self.send_to(client_id, {
            "type": "status",
            "status": status,
            "detail": detail,
        })

    async def send_error(self, client_id: str, error: str):
        """エラー送信"""
        await self.send_to(client_id, {
            "type": "error",
            "error": error,
        })

    def set_active_task(self, client_id: str, task: str | None):
        """クライアントのアクティブタスクを設定"""
        if client_id in self._clients:
            self._clients[client_id].active_task = task

    def get_client(self, client_id: str) -> WebSocketClient | None:
        """クライアント情報取得"""
        return self._clients.get(client_id)
```

---

### 3.5 `src/web/signal_bridge.py` — pyqtSignal → WebSocket ブリッジ

**最重要コンポーネント**: 既存のpyqtSignalを一切変更せず、WebSocketクライアントに中継する。

```python
"""
Helix AI Studio - Signal Bridge (v9.0.0)

既存のpyqtSignal → WebSocket中継ブリッジ。
既存コードの変更ゼロで、PyQt6シグナルをWebクライアントに転送する。

動作原理:
  1. MixAIOrchestrator / ClaudeCLIBackend のインスタンスが生成されたら
     このブリッジにシグナルを接続する
  2. pyqtSignalが発火するたびにコールバックが呼ばれる
  3. コールバック内でasyncioイベントループにWebSocket送信をスケジュール
  4. WebSocketManagerが該当クライアントにJSON送信

重要な技術的考慮:
  - pyqtSignalはQtメインスレッド（またはQThread）で発火する
  - WebSocket送信はasyncioイベントループで実行する
  - スレッド間通信には asyncio.run_coroutine_threadsafe() を使用
"""

import asyncio
import json
import logging
from typing import Optional

from .ws_manager import WebSocketManager

logger = logging.getLogger(__name__)


class SignalBridge:
    """pyqtSignal → WebSocket ブリッジ"""

    def __init__(self, ws_manager: WebSocketManager, loop: asyncio.AbstractEventLoop):
        self._ws_manager = ws_manager
        self._loop = loop
        self._connections: list = []  # シグナル接続を追跡（切断用）

    def bridge_solo_ai(self, backend, client_id: str):
        """
        soloAI (Claude CLI) バックエンドのシグナルをWebSocketにブリッジ。

        接続するシグナル:
          - streaming_output(str)  → {"type": "streaming", "chunk": ..., "done": false}
          - all_finished(str)      → {"type": "streaming", "chunk": ..., "done": true}
          - error_occurred(str)    → {"type": "error", "error": ...}

        注: soloAIバックエンドの実装によってシグナル名が異なる場合があるので、
            claude_tab.pyのコード(_on_cli_response等)から実際のシグナル接続を確認する。
            Phase 1ではClaude CLIの非対話モード(`claude -p`)を直接呼び出し、
            結果をWebSocket経由で返す簡易実装とする。
        """

        def on_streaming(chunk: str):
            self._schedule_send(client_id, {
                "type": "streaming",
                "chunk": chunk,
                "done": False,
            })

        def on_finished(result: str):
            self._schedule_send(client_id, {
                "type": "streaming",
                "chunk": result,
                "done": True,
            })

        def on_error(error: str):
            self._schedule_send(client_id, {
                "type": "error",
                "error": error,
            })

        # シグナル接続（存在する場合のみ）
        if hasattr(backend, 'streaming_output'):
            backend.streaming_output.connect(on_streaming)
        if hasattr(backend, 'all_finished'):
            backend.all_finished.connect(on_finished)
        if hasattr(backend, 'error_occurred'):
            backend.error_occurred.connect(on_error)

        logger.info(f"Signal bridge connected for soloAI → client {client_id}")

    def bridge_mix_ai(self, orchestrator, client_id: str):
        """
        mixAIオーケストレーターのシグナルをWebSocketにブリッジ。
        （Phase 2で実装）

        接続するシグナル:
          - phase_changed(int, str)
          - streaming_output(str)
          - local_llm_started(str, str)
          - local_llm_finished(str, bool, float)
          - phase2_progress(int, int)
          - all_finished(str)
          - error_occurred(str)
        """
        # Phase 2 で実装
        pass

    def _schedule_send(self, client_id: str, message: dict):
        """
        asyncioイベントループにWebSocket送信をスケジュール。
        pyqtSignalのコールバック（Qtスレッド）からasyncio（別スレッド）へ安全に送信。
        """
        try:
            asyncio.run_coroutine_threadsafe(
                self._ws_manager.send_to(client_id, message),
                self._loop,
            )
        except Exception as e:
            logger.error(f"Signal bridge send error: {e}")
```

---

### 3.6 `src/web/api_routes.py` — REST APIエンドポイント

```python
"""
Helix AI Studio - REST API Routes (v9.0.0 Phase 1)

Phase 1 エンドポイント:
  POST /api/auth/login       - PIN認証 → JWT取得
  GET  /api/auth/verify      - JWT検証
  GET  /api/status            - サーバーステータス
  POST /api/solo/execute      - soloAI実行（非ストリーミング）
  GET  /api/config/models     - 利用可能モデル一覧
  GET  /api/health            - ヘルスチェック（認証不要）
"""

import json
import logging
import os
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .auth import WebAuthManager

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
    model_id: str = "claude-opus-4-6"
    attached_files: list[str] = []
    project_dir: str = ""
    timeout: int = 600
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
    return {"status": "ok", "service": "helix-ai-studio", "version": "9.0.0"}


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    """PIN認証 → JWT発行"""
    client_ip = request.client.host

    # IPチェック
    if not auth_manager.check_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not in allowed range")

    # PIN検証
    if not auth_manager.verify_pin(body.pin):
        logger.warning(f"Failed login attempt from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid PIN")

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
        version="9.0.0",
        pyqt_running=state.get("pyqt_running", False),
        active_websockets=state.get("active_websockets", 0),
        rag_locked=state.get("rag_locked", False),
    )


@router.get("/api/config/models", response_model=list[ModelInfo])
async def get_models(payload: dict = Depends(verify_jwt)):
    """利用可能なClaudeモデル一覧"""
    # 既存のconstants.pyからインポート（読み取りのみ）
    try:
        from ..utils.constants import CLAUDE_MODELS
        return [ModelInfo(**m) for m in CLAUDE_MODELS]
    except ImportError:
        # フォールバック
        return [
            ModelInfo(
                id="claude-opus-4-6",
                display_name="Claude Opus 4.6 (最高知能)",
                description="最も高度で知的なモデル",
                tier="opus",
                is_default=True,
            )
        ]


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

    try:
        result = run_hidden(
            cmd,
            input=body.prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=body.timeout,
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
            detail=f"Claude CLI timed out ({body.timeout}s)",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Claude CLI not found. Is 'claude' command installed?",
        )
```

---

### 3.7 `src/web/server.py` — FastAPIサーバー本体

```python
"""
Helix AI Studio - Web UIサーバー (v9.0.0 Phase 1)

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
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import WebAuthManager
from .api_routes import router as api_router
from .ws_manager import WebSocketManager

logger = logging.getLogger(__name__)

# =============================================================================
# グローバル状態
# =============================================================================

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
    version="9.0.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tailscale VPN内なので全許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST APIルーター
app.include_router(api_router)

# フロントエンド静的ファイル配信
# ビルド済みフロントエンドが frontend/dist/ に存在する場合のみ
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


# =============================================================================
# WebSocket エンドポイント (soloAI)
# =============================================================================

@app.websocket("/ws/solo")
async def websocket_solo(websocket: WebSocket, token: str = Query(...)):
    """
    soloAI WebSocketエンドポイント。
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
        await ws_manager.send_status(client_id, "connected", "soloAI WebSocket ready")

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


async def _handle_solo_execute(client_id: str, data: dict):
    """
    soloAI実行ハンドラ。
    Claude CLIをsubprocessで実行し、結果をWebSocketで送信。

    Phase 1の制約:
      - ストリーミングは非対応（Claude CLI -p は一括出力のため）
      - 結果は一括でdone=trueとして送信
      - 実行中はstatus更新を送信

    将来の改善:
      - claude --streamオプション対応時にリアルタイムストリーミング
      - または Anthropic API SDK直接使用でストリーミング
    """
    from ..utils.subprocess_utils import run_hidden

    prompt = data.get("prompt", "")
    model_id = data.get("model_id", "claude-opus-4-6")
    project_dir = data.get("project_dir", "")
    timeout = data.get("timeout", 600)
    use_mcp = data.get("use_mcp", True)
    auto_approve = data.get("auto_approve", True)

    if not prompt:
        await ws_manager.send_error(client_id, "Prompt is empty")
        return

    # ステータス: 実行中
    ws_manager.set_active_task(client_id, "soloAI")
    await ws_manager.send_status(client_id, "executing", f"Claude ({model_id}) 実行中...")

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
        # subprocessを非同期で実行（イベントループをブロックしない）
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_hidden(
                cmd,
                input=prompt,
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

            # 完了送信
            await ws_manager.send_streaming(client_id, response_text, done=True)
            await ws_manager.send_status(client_id, "completed", "実行完了")
        else:
            error_msg = f"Claude CLI error (code {result.returncode}): {stderr[:500]}"
            await ws_manager.send_error(client_id, error_msg)

    except subprocess.TimeoutExpired:
        await ws_manager.send_error(client_id, f"Claude CLI timed out ({timeout}s)")
    except FileNotFoundError:
        await ws_manager.send_error(client_id, "Claude CLI not found")
    except Exception as e:
        await ws_manager.send_error(client_id, f"Execution error: {str(e)}")
    finally:
        ws_manager.set_active_task(client_id, None)


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


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8500
    start_server(port=port)
```

**依存パッケージ**: `pip install fastapi uvicorn[standard] python-multipart`

---

## 4. フロントエンド実装

### 4.1 `frontend/package.json`

```json
{
  "name": "helix-ai-studio-web",
  "version": "9.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-markdown": "^9.0.1",
    "react-syntax-highlighter": "^15.6.1",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "vite": "^6.0.7"
  }
}
```

### 4.2 `frontend/vite.config.js`

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8500',
      '/ws': {
        target: 'ws://localhost:8500',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
```

### 4.3 `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
  <link rel="manifest" href="/manifest.json" />
  <title>Helix AI Studio</title>
</head>
<body class="bg-gray-950 text-gray-100">
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

### 4.4 `frontend/public/manifest.json` — PWA設定

```json
{
  "name": "Helix AI Studio",
  "short_name": "Helix AI",
  "description": "AI Orchestration Studio - Mobile Interface",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#030712",
  "theme_color": "#10b981",
  "orientation": "any",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    }
  ]
}
```

### 4.5 フロントエンドのソースコード

以下、主要コンポーネントの設計概要。実装時は Tailwind CSS + React 18 + React Markdown を使用。

#### `frontend/src/main.jsx`
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

#### `frontend/src/App.jsx` — メインアプリ

```jsx
import React, { useState, useEffect } from 'react';
import LoginScreen from './components/LoginScreen';
import ChatView from './components/ChatView';
import InputBar from './components/InputBar';
import StatusIndicator from './components/StatusIndicator';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';

export default function App() {
  const { token, isAuthenticated, login, logout } = useAuth();
  const { status, messages, sendMessage, isExecuting } = useWebSocket(token);

  if (!isAuthenticated) {
    return <LoginScreen onLogin={login} />;
  }

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      {/* ヘッダー */}
      <header className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold text-sm">
            H
          </div>
          <span className="text-lg font-semibold text-gray-100">Helix AI Studio</span>
        </div>
        <StatusIndicator status={status} />
      </header>

      {/* チャットエリア */}
      <ChatView messages={messages} isExecuting={isExecuting} />

      {/* 入力バー */}
      <InputBar onSend={sendMessage} disabled={isExecuting} />
    </div>
  );
}
```

#### `frontend/src/hooks/useAuth.js` — 認証フック

```javascript
import { useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'helix_jwt_token';
const API_BASE = '';  // 同一オリジン (vite proxy or production)

export function useAuth() {
  const [token, setToken] = useState(() => {
    // メモリ内で保持（localStorage不使用、sessionStorageも不使用）
    return null;
  });

  // ページリロード時のトークン復元用（一時的にwindowオブジェクトに保存）
  useEffect(() => {
    if (window.__helix_token) {
      setToken(window.__helix_token);
    }
  }, []);

  const login = useCallback(async (pin) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    setToken(data.token);
    window.__helix_token = data.token;  // リロード時の一時保存
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    window.__helix_token = null;
  }, []);

  return {
    token,
    isAuthenticated: !!token,
    login,
    logout,
  };
}
```

#### `frontend/src/hooks/useWebSocket.js` — WebSocket接続フック

```javascript
import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket(token) {
  const [status, setStatus] = useState('disconnected');
  const [messages, setMessages] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // WebSocket接続
  useEffect(() => {
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/solo?token=${token}`;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
      };

      ws.onclose = (event) => {
        setStatus('disconnected');
        wsRef.current = null;
        // 自動再接続（5秒後）
        if (event.code !== 4001 && event.code !== 4003) {
          reconnectRef.current = setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        setStatus('error');
      };
    }

    connect();

    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [token]);

  // メッセージハンドラ
  function handleMessage(data) {
    switch (data.type) {
      case 'streaming':
        if (data.done) {
          // 完了: 最後のassistantメッセージを確定
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant' && updated[lastIdx].streaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: data.chunk || updated[lastIdx].content,
                streaming: false,
              };
            } else {
              updated.push({ role: 'assistant', content: data.chunk, streaming: false });
            }
            return updated;
          });
          setIsExecuting(false);
        } else {
          // ストリーミングチャンク追記
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant' && updated[lastIdx].streaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + data.chunk,
              };
            } else {
              updated.push({ role: 'assistant', content: data.chunk, streaming: true });
            }
            return updated;
          });
        }
        break;

      case 'status':
        setStatus(data.status);
        if (data.status === 'executing') setIsExecuting(true);
        if (data.status === 'completed' || data.status === 'cancelled') setIsExecuting(false);
        break;

      case 'error':
        setMessages(prev => [
          ...prev,
          { role: 'system', content: `エラー: ${data.error}`, isError: true },
        ]);
        setIsExecuting(false);
        break;

      case 'pong':
        break;

      default:
        console.warn('Unknown WebSocket message type:', data.type);
    }
  }

  // メッセージ送信
  const sendMessage = useCallback((prompt, options = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    // ユーザーメッセージ追加
    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setIsExecuting(true);

    wsRef.current.send(JSON.stringify({
      action: 'execute',
      prompt,
      model_id: options.modelId || 'claude-opus-4-6',
      project_dir: options.projectDir || '',
      timeout: options.timeout || 600,
      use_mcp: options.useMcp !== false,
      auto_approve: options.autoApprove !== false,
    }));
  }, []);

  return {
    status,
    messages,
    sendMessage,
    isExecuting,
  };
}
```

#### `frontend/src/components/LoginScreen.jsx`

```jsx
import React, { useState } from 'react';

export default function LoginScreen({ onLogin }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pin) return;
    setLoading(true);
    setError('');

    try {
      await onLogin(pin);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-950">
      <div className="w-full max-w-sm p-8 bg-gray-900 rounded-2xl border border-gray-800">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-emerald-600 flex items-center justify-center text-white font-bold text-2xl mb-4">
            H
          </div>
          <h1 className="text-xl font-semibold text-gray-100">Helix AI Studio</h1>
          <p className="text-sm text-gray-400 mt-1">Web Interface</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">PIN</label>
          <input
            type="password"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={10}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-center text-2xl tracking-widest text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder="••••••"
            autoFocus
          />
          {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          <button
            onClick={handleSubmit}
            disabled={loading || !pin}
            className="w-full mt-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-xl transition-colors"
          >
            {loading ? '認証中...' : 'ログイン'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

#### `frontend/src/components/ChatView.jsx`

```jsx
import React, { useRef, useEffect } from 'react';
import MarkdownRenderer from './MarkdownRenderer';

export default function ChatView({ messages, isExecuting }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isExecuting]);

  return (
    <main className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <div className="w-20 h-20 rounded-2xl bg-gray-900 flex items-center justify-center text-3xl mb-4">
            🧬
          </div>
          <p className="text-lg font-medium">Helix AI Studio</p>
          <p className="text-sm mt-1">soloAI — Claude直接対話</p>
        </div>
      )}

      {messages.map((msg, idx) => (
        <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div
            className={`max-w-[85%] rounded-2xl px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-emerald-700 text-white'
                : msg.isError
                ? 'bg-red-900/50 border border-red-800 text-red-200'
                : 'bg-gray-800 text-gray-100'
            }`}
          >
            {msg.role === 'assistant' ? (
              <MarkdownRenderer content={msg.content} />
            ) : (
              <p className="whitespace-pre-wrap">{msg.content}</p>
            )}
            {msg.streaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse" />
            )}
          </div>
        </div>
      ))}

      {isExecuting && messages[messages.length - 1]?.role !== 'assistant' && (
        <div className="flex justify-start">
          <div className="bg-gray-800 rounded-2xl px-4 py-3">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </main>
  );
}
```

#### `frontend/src/components/InputBar.jsx`

```jsx
import React, { useState, useRef } from 'react';

export default function InputBar({ onSend, disabled }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    // Ctrl+Enter or Cmd+Enter で送信
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e) => {
    setText(e.target.value);
    // 自動高さ調整
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  return (
    <div className="border-t border-gray-800 bg-gray-900 px-4 py-3 safe-area-inset-bottom">
      <div className="flex items-end gap-2 max-w-3xl mx-auto">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="メッセージを入力... (Ctrl+Enter で送信)"
          rows={1}
          className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 max-h-[200px]"
          disabled={disabled}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="shrink-0 w-12 h-12 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 flex items-center justify-center transition-colors"
        >
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
```

#### `frontend/src/components/StatusIndicator.jsx`

```jsx
import React from 'react';

const STATUS_STYLES = {
  connected: { dot: 'bg-emerald-400', text: '接続中', color: 'text-emerald-400' },
  executing: { dot: 'bg-amber-400 animate-pulse', text: '実行中', color: 'text-amber-400' },
  completed: { dot: 'bg-emerald-400', text: '完了', color: 'text-emerald-400' },
  disconnected: { dot: 'bg-gray-500', text: '未接続', color: 'text-gray-500' },
  error: { dot: 'bg-red-400', text: 'エラー', color: 'text-red-400' },
};

export default function StatusIndicator({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.disconnected;

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${style.dot}`} />
      <span className={`text-xs font-medium ${style.color}`}>{style.text}</span>
    </div>
  );
}
```

#### `frontend/src/components/MarkdownRenderer.jsx`

```jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

export default function MarkdownRenderer({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className="prose prose-invert prose-sm max-w-none"
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          return !inline && match ? (
            <SyntaxHighlighter
              style={oneDark}
              language={match[1]}
              PreTag="div"
              className="rounded-lg text-sm"
              {...props}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          ) : (
            <code className="bg-gray-700 px-1.5 py-0.5 rounded text-emerald-300 text-sm" {...props}>
              {children}
            </code>
          );
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {content || ''}
    </ReactMarkdown>
  );
}
```

#### `frontend/src/styles/globals.css` — Tailwind CSS

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* iOS Safari safe area対応 */
.safe-area-inset-bottom {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}

/* スクロールバースタイル */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

/* フォーカスアウトライン無効化（モバイル） */
@media (max-width: 768px) {
  textarea:focus, input:focus, button:focus {
    outline: none;
  }
}
```

#### Tailwind設定 `frontend/tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

#### PostCSS設定 `frontend/postcss.config.js`

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

---

## 5. 依存パッケージのインストール

### Python (バックエンド)
```bash
pip install fastapi uvicorn[standard] PyJWT python-multipart --break-system-packages
```

### Node.js (フロントエンド)
```bash
cd frontend
npm install
```

### ビルド手順
```bash
cd frontend
npm run build
# → frontend/dist/ に静的ファイルが生成される
# → FastAPIのStaticFilesマウントで自動配信
```

---

## 6. 起動・テスト手順

### 6.1 スタンドアロン起動（開発時）

ターミナル1: バックエンド
```bash
cd helix-ai-studio
python -m src.web.server
# → http://0.0.0.0:8500 で起動
```

ターミナル2: フロントエンド（開発モード / HMR）
```bash
cd frontend
npm run dev
# → http://localhost:5173 で起動（vite proxy経由でAPIに接続）
```

### 6.2 本番起動

```bash
cd frontend && npm run build && cd ..
python -m src.web.server
# → http://0.0.0.0:8500 で起動（フロントエンド同梱）
```

### 6.3 テスト項目チェックリスト

| # | テスト項目 | 方法 | 期待結果 |
|---|----------|------|---------|
| 1 | ヘルスチェック | `curl http://localhost:8500/api/health` | `{"status":"ok"}` |
| 2 | PIN認証 | `curl -X POST http://localhost:8500/api/auth/login -d '{"pin":"000000"}'` | JWT取得 |
| 3 | JWT検証 | `curl -H "Authorization: Bearer <token>" http://localhost:8500/api/auth/verify` | `{"valid":true}` |
| 4 | モデル一覧 | `curl -H "Authorization: Bearer <token>" http://localhost:8500/api/config/models` | CLAUDEモデル一覧 |
| 5 | soloAI REST | POST `/api/solo/execute` with prompt | Claude応答 |
| 6 | WebSocket接続 | ブラウザからWebSocket接続 | `connected`ステータス |
| 7 | soloAI WS実行 | WebSocket経由でexecuteアクション | ストリーミング応答 |
| 8 | Tailscale経由 | iPhoneからTailscale IP:8500にアクセス | ログイン画面表示 |
| 9 | PWAインストール | Safariで「ホーム画面に追加」 | アプリアイコン |
| 10 | 非Tailscale IP拒否 | 外部IPからアクセス | 403 Forbidden |

---

## 7. 既存コードへの影響分析

| 対象ファイル | 変更 | 理由 |
|------------|------|------|
| `src/backends/mix_orchestrator.py` | ❌ 変更なし | Phase 1はsoloAIのみ。WebSocket実行はClaude CLIを直接subprocess実行 |
| `src/tabs/claude_tab.py` | ❌ 変更なし | PyQt6 UI層は無関係 |
| `src/rag/rag_builder.py` | ❌ 変更なし | RAGBuildLockの参照はPhase 2以降 |
| `src/utils/constants.py` | ❌ 変更なし | 読み取りインポートのみ（CLAUDE_MODELS） |
| `src/utils/subprocess_utils.py` | ❌ 変更なし | run_hiddenを既存インポートで使用 |
| `config/config.json` | ❌ 変更なし | web_config.jsonは別ファイル |

**結論**: 既存ファイルへの変更は完全にゼロ。

---

## 8. Phase 2 への橋渡し

Phase 1完了後、Phase 2 で追加する機能:

1. **mixAI WebSocket対応** — signal_bridge.pyの `bridge_mix_ai()` を実装。3Phase進捗のリアルタイム表示
2. **mixAIタブUI** — React側にmixAIタブを追加。Phase進捗バー、ローカルLLMステータス表示
3. **ファイルブラウザ** — API + UIでプロジェクトディレクトリのファイル一覧/選択
4. **レスポンシブ改善** — タブ切替、設定画面のモバイル対応

Phase 1の `ws_manager.py` と `signal_bridge.py` は Phase 2 の拡張を見越した設計になっているため、追加実装のみで対応可能。
