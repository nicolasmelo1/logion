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
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CONTENT_PATH = PACKAGE_DIR / "content" / "site.yaml"


def load_content(path: Path = CONTENT_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"site content at {path} must be a mapping")
    return data


app = FastAPI(title="Logion")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
content = load_content()


def _ctx(**extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = dict(content)
    ctx.update(extra)
    return ctx


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", _ctx())


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request) -> HTMLResponse:
    page = content.get("legal", {}).get("terms", {})
    return templates.TemplateResponse(request, "legal.html", _ctx(page=page))


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    page = content.get("legal", {}).get("privacy", {})
    return templates.TemplateResponse(request, "legal.html", _ctx(page=page))


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
