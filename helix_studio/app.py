"""FastAPI アプリケーション本体"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from helix_studio.db import init_db
from helix_studio.routes import (
    chat,
    crew_api,
    memory,
    models_api,
    pages,
    pipeline_api,
    settings_api,
    tools_api,
)

logger = logging.getLogger(__name__)

# パス設定
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリ起動時にDBを初期化。"""
    logger.info("Helix AI Studio を起動中...")
    await init_db()
    logger.info("データベース初期化完了")
    yield
    logger.info("Helix AI Studio をシャットダウン")


def create_app() -> FastAPI:
    """FastAPIアプリを作成して返す。"""
    app = FastAPI(
        title="Helix AI Studio",
        description="ローカルLLM + クラウドAI統合チャットスタジオ",
        version="0.1.0",
        lifespan=lifespan,
    )

    # テンプレート設定
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    pages.setup_templates(templates)

    # 静的ファイル
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ルーター登録
    app.include_router(pages.router)
    app.include_router(chat.router)
    app.include_router(models_api.router)
    app.include_router(memory.router)
    app.include_router(settings_api.router)
    app.include_router(pipeline_api.router)
    app.include_router(crew_api.router)
    app.include_router(tools_api.router)

    return app


app = create_app()
