# SPDX-License-Identifier: MIT
"""Logion landing FastAPI app.

Templates, static assets, and copy live under ``landing/``.
The page content is loaded from ``landing/content/site.yaml`` so it
can be edited without touching Python.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CONTENT_DIR = PACKAGE_DIR / "content"
CONTENT_PATH = CONTENT_DIR / "site.yaml"
MARKDOWN_PATH = CONTENT_DIR / "landing.md"
ASCII_HERO_PATH = STATIC_DIR / "ascii" / "zeus.txt"


def load_content(path: Path = CONTENT_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"site content at {path} must be a mapping")
    return data


def load_markdown(path: Path = MARKDOWN_PATH) -> str:
    return path.read_text(encoding="utf-8")


_md_renderer = MarkdownIt("commonmark", {"html": False})


def render_markdown(markdown: str) -> str:
    return _md_renderer.render(markdown)


def legal_page(slug: str) -> dict[str, str]:
    page = content.get("legal", {}).get(slug, {})
    markdown_name = page.get("markdown")
    if not isinstance(markdown_name, str):
        raise TypeError(f"legal page {slug!r} must define a markdown file")
    resolved = (CONTENT_DIR / markdown_name).resolve()
    if not str(resolved).startswith(str(CONTENT_DIR.resolve())):
        raise ValueError(f"legal page {slug!r} path escapes content directory")
    markdown = resolved.read_text(encoding="utf-8")
    return {
        "heading": str(page.get("heading", slug.title())),
        "markdown": markdown,
        "html": render_markdown(markdown),
    }


app = FastAPI(title="Logion")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
content = load_content()
markdown_content = load_markdown()
ascii_hero = ASCII_HERO_PATH.read_text(encoding="utf-8")


def _ctx(**extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = dict(content)
    ctx["ascii_hero"] = ascii_hero
    ctx.update(extra)
    return ctx


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if "text/markdown" in request.headers.get("accept", ""):
        return PlainTextResponse(
            markdown_content,
            media_type="text/markdown; charset=utf-8",
        )
    return templates.TemplateResponse(request, "index.html", _ctx())


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(page=legal_page("terms")),
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(page=legal_page("privacy")),
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


def main() -> None:
    legacy_host = os.getenv("CLAWSERA_LANDING_HOST")
    legacy_port = os.getenv("CLAWSERA_LANDING_PORT")
    host = os.getenv("LOGION_LANDING_HOST", legacy_host or "127.0.0.1")
    port = int(os.getenv("LOGION_LANDING_PORT", legacy_port or "8001"))
    uvicorn.run("landing.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
