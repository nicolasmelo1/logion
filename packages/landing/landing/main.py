# SPDX-License-Identifier: MIT
"""Logion landing FastAPI app.

Templates, static assets, and copy live under ``landing/``.
The page content is loaded from ``landing/content/site.yaml`` so it
can be edited without touching Python.
"""

from __future__ import annotations

import os
import re
from html import escape
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
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
PUBLIC_PATHS = (
    "/",
    "/pricing",
    "/terms",
    "/privacy",
    "/credits-terms",
    "/referrals-terms",
    "/llms.txt",
)
AI_CRAWLERS = (
    "GPTBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-User",
    "PerplexityBot",
    "Google-Extended",
    "CCBot",
)
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REFERRAL_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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


def canonical_url(path: str) -> str:
    base = str(content.get("seo", {}).get("canonical_base", "")).rstrip("/")
    normalized_path = "/" if path == "/" else f"/{path.strip('/')}"
    return f"{base}{normalized_path}"


def robots_txt() -> str:
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
    ]
    for crawler in AI_CRAWLERS:
        lines.extend([
            f"User-agent: {crawler}",
            "Allow: /",
            "",
        ])
    lines.append(f"Sitemap: {canonical_url('/sitemap.xml')}")
    return "\n".join(lines) + "\n"


def sitemap_xml() -> str:
    urls = "\n".join(
        "  <url>\n"
        f"    <loc>{escape(canonical_url(path), quote=True)}</loc>\n"
        "  </url>"
        for path in PUBLIC_PATHS
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def _format_llms_link(entry: dict[str, Any]) -> str:
    title = str(entry.get("title", "Untitled"))
    href = str(entry.get("href", "/"))
    description = str(entry.get("description", "")).strip()
    url = href if href.startswith("https://") else canonical_url(href)
    suffix = f" - {description}" if description else ""
    return f"- [{title}]({url}){suffix}"


def llms_txt() -> str:
    ai = content.get("ai", {})
    site = content.get("site", {})
    pages = ai.get("llms_txt_pages", []) or []
    sections = ai.get("llms_txt_sections", []) or []
    lines = [
        f"# {site.get('name', 'Logion')}",
        "",
        str(ai.get("llms_txt_summary", site.get("description", ""))),
        "",
        "## Pages",
        "",
    ]
    for page in pages:
        if isinstance(page, dict):
            lines.append(_format_llms_link(page))
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading", "")).strip()
        if not heading:
            continue
        lines.extend(["", f"## {heading}", ""])
        for link in section.get("links", []) or []:
            if isinstance(link, dict):
                lines.append(_format_llms_link(link))
    return "\n".join(lines).rstrip() + "\n"


def legal_page(slug: str) -> dict[str, str]:
    page = content.get("legal", {}).get(slug, {})
    markdown_name = page.get("markdown")
    if not isinstance(markdown_name, str):
        raise TypeError(f"legal page {slug!r} must define a markdown file")
    resolved = (CONTENT_DIR / markdown_name).resolve()
    if not resolved.is_relative_to(CONTENT_DIR.resolve()):
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


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pricing.html", _ctx())


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


@app.get("/credits-terms", response_class=HTMLResponse)
def credits_terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(page=legal_page("credits")),
    )


@app.get("/referrals-terms", response_class=HTMLResponse)
def referrals_terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(page=legal_page("referrals")),
    )


@app.get("/c/{course_slug}", response_class=HTMLResponse)
def referral_landing(
    request: Request,
    course_slug: str,
    ref: str | None = None,
) -> HTMLResponse:
    if not SLUG_PATTERN.match(course_slug):
        raise HTTPException(status_code=404, detail="course not found")
    referral_code: str | None = None
    if ref is not None:
        if not REFERRAL_CODE_PATTERN.match(ref):
            raise HTTPException(
                status_code=400,
                detail="invalid referral code",
            )
        referral_code = ref
    referral_cfg = content.get("referral", {})
    template = str(
        referral_cfg.get(
            "command_template",
            "lgn courses acquire {slug} --referral-code {code}",
        )
    )
    if referral_code:
        command = template.format(slug=course_slug, code=referral_code)
    else:
        command = f"lgn courses acquire {course_slug}"
    # MVP: no cookies, no third-party tracking on this route.
    return templates.TemplateResponse(
        request,
        "referral.html",
        _ctx(
            course_slug=course_slug,
            referral_code=referral_code,
            command=command,
        ),
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> PlainTextResponse:
    return PlainTextResponse(
        robots_txt(),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/sitemap.xml")
def sitemap() -> Response:
    return Response(
        sitemap_xml(),
        media_type="application/xml; charset=utf-8",
    )


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms() -> PlainTextResponse:
    return PlainTextResponse(
        llms_txt(),
        media_type="text/plain; charset=utf-8",
    )


def main() -> None:
    import uvicorn

    host = os.getenv("LOGION_LANDING_HOST", "127.0.0.1")
    port = int(os.getenv("LOGION_LANDING_PORT", "8001"))
    uvicorn.run("landing.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
