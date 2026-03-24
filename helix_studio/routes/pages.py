"""HTMLページ配信ルーター"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from helix_studio.config import get_all_settings

router = APIRouter(tags=["pages"])

# テンプレートはapp.pyで設定されたパスを使用
templates: Jinja2Templates | None = None


def setup_templates(t: Jinja2Templates) -> None:
    """app.py から呼ばれ、Jinja2Templates インスタンスを設定する。"""
    global templates
    templates = t


def _get_templates() -> Jinja2Templates:
    if templates is None:
        raise RuntimeError("テンプレートが初期化されていません")
    return templates


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """チャット画面"""
    settings = await get_all_settings()
    return _get_templates().TemplateResponse(
        request=request, name="chat.html",
        context={"page": "chat", "settings": settings},
    )


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request):
    """パイプライン画面"""
    settings = await get_all_settings()
    return _get_templates().TemplateResponse(
        request=request, name="pipeline.html",
        context={"page": "pipeline", "settings": settings},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """設定画面"""
    settings = await get_all_settings()
    return _get_templates().TemplateResponse(
        request=request, name="settings.html",
        context={"page": "settings", "settings": settings},
    )


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """履歴画面"""
    settings = await get_all_settings()
    return _get_templates().TemplateResponse(
        request=request, name="history.html",
        context={"page": "history", "settings": settings},
    )
