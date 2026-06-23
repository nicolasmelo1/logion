# SPDX-License-Identifier: MIT
"""Logion landing FastAPI app.

Templates, static assets, and copy live under ``landing/``.
The page content is loaded from ``landing/content/site.yaml`` so it
can be edited without touching Python.
"""

from __future__ import annotations

import os
import re
from datetime import UTC
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
FAVICON_PATH = STATIC_DIR / "favicon.svg"
PUBLIC_PATHS = (
    "/",
    "/pricing",
    "/terms",
    "/privacy",
    "/credits-terms",
    "/referrals-terms",
    "/llms.txt",
    "/llms-full.txt",
    "/design.txt",
)
LEGAL_ROUTES = {
    "/terms": "terms",
    "/privacy": "privacy",
    "/credits-terms": "credits",
    "/referrals-terms": "referrals",
}
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
FAVICON_BYTES = FAVICON_PATH.read_bytes()


def _ctx(**extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = dict(content)
    ctx["ascii_hero"] = ascii_hero
    ctx.setdefault("breadcrumbs", content.get("breadcrumbs", {}))
    ctx.setdefault("page_date_modified", None)
    ctx.update(extra)
    return ctx


def _legal_date_modified(slug: str) -> str | None:
    page = content.get("legal", {}).get(slug, {})
    markdown_name = page.get("markdown")
    if not isinstance(markdown_name, str):
        return None
    resolved = (CONTENT_DIR / markdown_name).resolve()
    if not resolved.is_relative_to(CONTENT_DIR.resolve()):
        return None
    try:
        ts = resolved.stat().st_mtime
    except OSError:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()


def _wants_markdown(request: Request) -> bool:
    return "text/markdown" in request.headers.get("accept", "")


def _legal_markdown_response(slug: str) -> PlainTextResponse:
    page = legal_page(slug)
    return PlainTextResponse(
        page["markdown"],
        media_type="text/markdown; charset=utf-8",
    )


def llms_full_txt() -> str:
    """Concatenated full-site content for AI ingestion (one fetch)."""
    site = content.get("site", {})
    sections: list[str] = [f"# {site.get('name', 'Logion')} — full content\n"]
    summary = site.get("one_liner") or content.get("ai", {}).get(
        "llms_txt_summary", ""
    )
    if summary:
        sections.append(str(summary).strip() + "\n")
    sections.append("## /\n")
    sections.append(markdown_content.strip() + "\n")
    for path, slug in LEGAL_ROUTES.items():
        try:
            page = legal_page(slug)
        except (OSError, TypeError, ValueError) as exc:
            sections.append(f"## {path}\n\n_unavailable: {exc}_\n")
            continue
        sections.append(f"## {path}\n")
        sections.append(page["markdown"].strip() + "\n")
    faq_block = content.get("faq", {})
    if faq_block.get("items"):
        sections.append("## FAQ\n")
        for item in faq_block["items"]:
            q = str(item.get("q", "")).strip()
            a = str(item.get("a", "")).strip()
            if q and a:
                sections.append(f"### {q}\n\n{a}\n")
    if content.get("design"):
        # Drop design.txt's own "# ... — design.txt" title line so the brand
        # manifest nests cleanly under the llms-full "## /design.txt" heading.
        design_body = design_txt().split("\n", 2)[-1]
        sections.append("## /design.txt\n")
        sections.append(design_body.strip() + "\n")
    return "\n".join(sections).rstrip() + "\n"


def design_txt() -> str:
    """Plain-text brand manifest for agents and humans (logion.sh/design.txt).

    Generated from the ``design:`` block in site.yaml so it cannot drift from
    the page. Mirrors docs/branding-guide.md in a compact, parseable form
    (one ``key: value`` or ``key:`` + indented list per stanza).
    """
    design = content.get("design", {})
    site = content.get("site", {})
    palette = design.get("palette", {})
    type_cfg = design.get("type", {})
    logos = design.get("logos", {})
    links = design.get("links", {})
    base = str(content.get("seo", {}).get("canonical_base", "")).rstrip("/")

    def _abs(href: str) -> str:
        return href if href.startswith("https://") else f"{base}{href}"

    lines: list[str] = [
        f"# {site.get('name', 'Logion')} — design.txt",
        "",
        f"motto: {design.get('motto', '')}",
        f"voice: {str(design.get('voice', '')).strip()}",
        "",
        "## logos",
    ]
    for key in ("mark", "wordmark", "wordmark_light", "favicon"):
        if key in logos:
            lines.append(f"- {key}: {_abs(str(logos[key]))}")
    lines += ["", "## palette"]
    for theme in ("dark", "light"):
        block = palette.get(theme, {})
        if block:
            tokens = "  ".join(f"{k}={v}" for k, v in block.items())
            lines.append(f"- {theme}: {tokens}")
    if palette.get("logo_seal"):
        lines.append(f"- logo_seal: {palette['logo_seal']}")
    lines += [
        "",
        "## type",
        f"- mono: {type_cfg.get('mono', '')}",
        f"- serif: {type_cfg.get('serif', '')}",
        f"- ornament: {type_cfg.get('ornament', '')}",
        "",
        "## motif",
    ]
    for item in design.get("motif", []) or []:
        lines.append(f"- {item}")
    lines += ["", "## links"]
    for key, href in links.items():
        lines.append(f"- {key}: {_abs(str(href))}")
    return "\n".join(lines).rstrip() + "\n"


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if "text/markdown" in request.headers.get("accept", ""):
        return PlainTextResponse(
            markdown_content,
            media_type="text/markdown; charset=utf-8",
        )
    return templates.TemplateResponse(request, "index.html", _ctx())


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request) -> Response:
    if _wants_markdown(request):
        pricing_cfg = content.get("pricing", {})
        lines = [
            f"# {pricing_cfg.get('heading', 'Pricing')}",
            "",
            str(pricing_cfg.get("intro", "")),
        ]
        for row in pricing_cfg.get("rows", []):
            lines.append(f"- **{row.get('label')}**: {row.get('value')}")
        return PlainTextResponse(
            "\n".join(lines).rstrip() + "\n",
            media_type="text/markdown; charset=utf-8",
        )
    return templates.TemplateResponse(request, "pricing.html", _ctx())


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request) -> Response:
    if _wants_markdown(request):
        return _legal_markdown_response("terms")
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(
            page=legal_page("terms"),
            page_date_modified=_legal_date_modified("terms"),
        ),
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> Response:
    if _wants_markdown(request):
        return _legal_markdown_response("privacy")
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(
            page=legal_page("privacy"),
            page_date_modified=_legal_date_modified("privacy"),
        ),
    )


@app.get("/credits-terms", response_class=HTMLResponse)
def credits_terms(request: Request) -> Response:
    if _wants_markdown(request):
        return _legal_markdown_response("credits")
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(
            page=legal_page("credits"),
            page_date_modified=_legal_date_modified("credits"),
        ),
    )


@app.get("/referrals-terms", response_class=HTMLResponse)
def referrals_terms(request: Request) -> Response:
    if _wants_markdown(request):
        return _legal_markdown_response("referrals")
    return templates.TemplateResponse(
        request,
        "legal.html",
        _ctx(
            page=legal_page("referrals"),
            page_date_modified=_legal_date_modified("referrals"),
        ),
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


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico() -> Response:
    """Serve the SVG favicon at /favicon.ico for browsers that auto-request it.

    Without this route Safari (and some Chrome configurations) treat the
    missing /favicon.ico as a hard miss and show no tab icon even when
    <link rel="icon" href="/static/favicon.svg"> is declared.
    """
    return Response(
        FAVICON_BYTES,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


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


@app.get("/llms-full.txt", response_class=PlainTextResponse)
def llms_full() -> PlainTextResponse:
    return PlainTextResponse(
        llms_full_txt(),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/design.txt", response_class=PlainTextResponse)
def design() -> PlainTextResponse:
    return PlainTextResponse(
        design_txt(),
        media_type="text/plain; charset=utf-8",
    )


def main() -> None:
    import uvicorn

    host = os.getenv("LOGION_LANDING_HOST", "127.0.0.1")
    port = int(os.getenv("LOGION_LANDING_PORT", "8001"))
    uvicorn.run("landing.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
