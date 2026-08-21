# SPDX-License-Identifier: MIT
"""Logion landing FastAPI app.

Templates, static assets, and copy live under ``landing/``.
The page content is loaded from ``landing/content/site.yaml`` so it
can be edited without touching Python.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC
from html import escape
from pathlib import Path
from typing import TypedDict

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup
from markupsafe import escape as markup_escape
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from landing._json import JsonObject, child, children, strings

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CONTENT_DIR = PACKAGE_DIR / "content"
CONTENT_PATH = CONTENT_DIR / "site.yaml"
MARKDOWN_PATH = CONTENT_DIR / "landing.md"
FAVICON_PATH = STATIC_DIR / "favicon.svg"
GITHUB_REPO = "nicolasmelo1/logion"
# The product API. Its own OpenAPI contract is the one agents should read, so
# /openapi.json and /docs on the landing host point here instead of describing
# these marketing routes.
API_BASE = os.environ.get(
    "LOGION_API_BASE_URL", "https://api.logion.sh"
).rstrip("/")
_MANIFEST_CHANNELS = ("stable", "latest")
# Channel whose published version drives the hero readout. Sourced from the
# release manifest on main so the page reflects actual GitHub Releases.
_READOUT_CHANNEL = "stable"
RELEASE_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/"
    f"releases/manifest-{_READOUT_CHANNEL}.json"
)
# In-process cache so render does not fetch GitHub on every request. One fetch
# per cold start and at most one per TTL window on a warm instance.
_READOUT_TTL_SECONDS = 3600.0


class _ReadoutCache(TypedDict):
    """The memoised release readout and when it was fetched."""

    value: str | None
    at: float


_readout_cache: _ReadoutCache = {"value": None, "at": 0.0}

PUBLIC_PATHS = (
    "/",
    "/aktp",
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
# Every page that content-negotiates markdown also answers at a stable ``.md``
# URL, mapped here as route path -> slug. The rel="alternate" markdown hint in
# the page head points at the ``.md`` URL: advertising the HTML URL made the
# hint a dead end for any client that cannot set an Accept header, which is
# most crawlers.
MARKDOWN_PAGES = {
    "/": "index",
    "/aktp": "aktp",
    "/pricing": "pricing",
    "/terms": "terms",
    "/privacy": "privacy",
    "/credits-terms": "credits-terms",
    "/referrals-terms": "referrals-terms",
}
#: ``.md`` slug -> legal page key, for the four routes backed by a legal doc.
MARKDOWN_SLUGS = {
    path.lstrip("/"): slug for path, slug in LEGAL_ROUTES.items()
}
#: Schema URI declared by the Agent Skills discovery index (Cloudflare RFC).
AGENT_SKILLS_SCHEMA = (
    "https://schemas.agentskills.io/discovery/0.2.0/schema.json"
)
#: Media type registered by the AI Catalog spec for an ai-catalog document.
AI_CATALOG_MEDIA_TYPE = "application/ai-catalog+json"
AI_CRAWLERS = (
    "GPTBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-User",
    "PerplexityBot",
    "Google-Extended",
    "CCBot",
)
# Cloudflare's Content Signals policy, declared per user-agent group so a
# parser reading only one crawler's block still sees it. Everything is open:
# the public copy exists to be indexed, grounded on, and trained on — an agent
# that can quote Logion correctly is the whole point of the landing page.
CONTENT_SIGNAL = "search=yes,ai-input=yes,ai-train=yes"
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REFERRAL_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def load_content(path: Path = CONTENT_PATH) -> JsonObject:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"site content at {path} must be a mapping")
    return data


def load_markdown(path: Path = MARKDOWN_PATH) -> str:
    return path.read_text(encoding="utf-8")


_TRANSCRIPT_STRING_RE = re.compile(r"&#34;.*?&#34;")


def transcript_html(text: str) -> Markup:
    """Colorize a terminal transcript: prompt, command, comment, output.

    Comment lines (leading ``#``) carry no prompt; command continuations
    (previous line ending in ``\\``) stay command-colored.
    """
    out: list[str] = []
    in_continuation = False
    for raw in text.rstrip("\n").split("\n"):
        line = str(markup_escape(raw))
        stripped = raw.strip()
        if stripped.startswith("#"):
            out.append(f'<span class="tl-c">{line}</span>')
            in_continuation = False
            continue
        if raw.startswith("$"):
            body = _TRANSCRIPT_STRING_RE.sub(
                lambda m: f'<span class="tl-s">{m.group(0)}</span>',
                str(markup_escape(raw[1:])),
            )
            out.append(f'<span class="tl-p">$</span>{body}')
            in_continuation = stripped.endswith("\\")
            continue
        if in_continuation:
            out.append(line)
            in_continuation = stripped.endswith("\\")
            continue
        out.append(f'<span class="tl-o">{line}</span>')
    # Safe: every line is passed through markup_escape before span-wrapping;
    # the only unescaped content is the literal span markup above.
    return Markup("\n".join(out))  # nosec B704


_md_renderer = MarkdownIt("commonmark", {"html": False})


def render_markdown(markdown: str) -> str:
    return _md_renderer.render(markdown)


def canonical_url(path: str) -> str:
    base = str(child(content, "seo").get("canonical_base", "")).rstrip("/")
    normalized_path = "/" if path == "/" else f"/{path.strip('/')}"
    return f"{base}{normalized_path}"


def markdown_alternate(path: str) -> str | None:
    """The ``.md`` URL advertised as *path*'s markdown alternate."""
    slug = MARKDOWN_PAGES.get(path)
    return canonical_url(f"/{slug}.md") if slug else None


def robots_txt() -> str:
    lines = [
        "User-agent: *",
        f"Content-Signal: {CONTENT_SIGNAL}",
        "Allow: /",
        "Disallow: /setup/",
        "",
    ]
    for crawler in AI_CRAWLERS:
        lines.extend([
            f"User-agent: {crawler}",
            f"Content-Signal: {CONTENT_SIGNAL}",
            "Allow: /",
            "Disallow: /setup/",
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


def _format_llms_link(entry: JsonObject) -> str:
    title = str(entry.get("title", "Untitled"))
    href = str(entry.get("href", "/"))
    description = str(entry.get("description", "")).strip()
    url = href if href.startswith("https://") else canonical_url(href)
    suffix = f" - {description}" if description else ""
    return f"- [{title}]({url}){suffix}"


def when_to_use_lines() -> list[str]:
    """Routing guidance for an agent choosing whether to reach for Logion.

    Rendered high in llms.txt, above the link index: an agent deciding
    *whether* to use Logion needs this before it needs a list of URLs.
    """
    block = child(child(content, "ai"), "when_to_use")
    if not block:
        return []
    lines = ["", f"## {block.get('heading', 'When to use Logion')}", ""]
    use_when = strings(block, "use_when")
    if use_when:
        lines.append("Use Logion when:")
        lines.append("")
        lines.extend(f"- {item.strip()}" for item in use_when)
    not_for = strings(block, "not_for")
    if not_for:
        lines += ["", "Do not reach for Logion for:", ""]
        lines.extend(f"- {item.strip()}" for item in not_for)
    how = str(block.get("how_to_call", "")).strip()
    if how:
        lines += ["", "How to call it:", "", how]
    return lines


def llms_txt() -> str:
    ai = child(content, "ai")
    site = child(content, "site")
    pages = children(ai, "llms_txt_pages")
    sections = children(ai, "llms_txt_sections")
    lines = [
        f"# {site.get('name', 'Logion')}",
        "",
        str(ai.get("llms_txt_summary", site.get("description", ""))),
    ]
    lines.extend(when_to_use_lines())
    lines += [
        "",
        "## Pages",
        "",
    ]
    for page in pages:
        lines.append(_format_llms_link(page))
    for section in sections:
        heading = str(section.get("heading", "")).strip()
        if not heading:
            continue
        lines.extend(["", f"## {heading}", ""])
        for link in children(section, "links"):
            if isinstance(link, dict):
                lines.append(_format_llms_link(link))
    return "\n".join(lines).rstrip() + "\n"


def legal_page(slug: str) -> dict[str, str]:
    page = child(child(content, "legal"), slug)
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


def _static_fingerprint() -> str:
    """Short content hash over every served static asset.

    Templates append it to /static URLs as ?v=<hash>, so browsers fetch a
    fresh copy exactly when a deploy changes any asset. Without it, the
    long-lived edge/browser cache on /static (hours) keeps serving stale
    CSS/JS against freshly deployed HTML.
    """
    digest = hashlib.sha256()
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(STATIC_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


ASSET_VERSION = _static_fingerprint()


class HeadRequestMiddleware:
    """Answer HEAD the way GET is answered, with the body suppressed.

    FastAPI's ``APIRoute`` — unlike Starlette's ``Route`` — does not add HEAD
    alongside GET, so every URL on this app answered 405 to the HEAD probe
    crawlers and link checkers send before committing to a GET. Rewriting the
    method for routing and dropping the body keeps the status and headers
    (Content-Length included) identical to the GET, as RFC 9110 requires.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self.app(scope, receive, send)
            return
        body_sent = False

        async def send_headers_only(message: Message) -> None:
            nonlocal body_sent
            if message["type"] == "http.response.body":
                # One empty terminal body message; further chunks the GET
                # handler streams are dropped rather than re-sent.
                if body_sent:
                    return
                body_sent = True
                message = {"type": "http.response.body", "body": b""}
            await send(message)

        await self.app({**scope, "method": "GET"}, receive, send_headers_only)


def _merge_vary(existing: str | None) -> str:
    """Add Accept and Accept-Encoding to a Vary header without duplicating."""
    tokens: list[str] = []
    seen: set[str] = set()
    for token in [*(existing or "").split(","), "Accept", "Accept-Encoding"]:
        name = token.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            tokens.append(name)
    return ", ".join(tokens)


class VaryOnAcceptMiddleware:
    """Tell shared caches that these responses depend on the Accept header.

    The negotiating routes return HTML or markdown from the same URL depending
    on Accept, and the 404 handler picks between HTML, JSON and markdown the
    same way. Without ``Vary: Accept`` a shared cache — and there are two in
    front of this app, Vercel's and Cloudflare's — may store one
    representation and serve it to every later caller: an agent asking for
    markdown gets the cached HTML, or a browser gets raw markdown, depending
    only on who arrived first.

    Scoped to the routes that actually negotiate. Stamping every response
    would split the cache key for assets whose body never varies by Accept.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        negotiating_path = scope.get("path", "") in MARKDOWN_PAGES

        async def send_with_vary(message: Message) -> None:
            # 404 is negotiated on every path, not just the known ones.
            if message["type"] == "http.response.start" and (
                negotiating_path or message["status"] == 404
            ):
                headers = MutableHeaders(scope=message)
                headers["vary"] = _merge_vary(headers.get("vary"))
            await send(message)

        await self.app(scope, receive, send_with_vary)


app = FastAPI(
    title="Logion",
    # The landing app is not the product API. FastAPI's generated schema for
    # these marketing routes was being discovered as "the Logion API" by agent
    # crawlers, which read 15 HTML routes as the whole contract. The
    # /openapi.json and /docs routes below point at the real one instead.
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(HeadRequestMiddleware)
app.add_middleware(VaryOnAcceptMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["transcript_html"] = transcript_html
templates.env.globals["markdown_alternate"] = markdown_alternate
templates.env.globals["github_repo"] = GITHUB_REPO
content = load_content()
markdown_content = load_markdown()
aktp_markdown_content = load_markdown(CONTENT_DIR / "aktp.md")
FAVICON_BYTES = FAVICON_PATH.read_bytes()


def _installer_redirect(asset: str) -> RedirectResponse:
    if not re.fullmatch(r"install(_lib)?\.(sh|ps1)", asset):
        raise HTTPException(status_code=500, detail="Invalid installer asset")
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/scripts/{asset}"
    )
    return RedirectResponse(url, status_code=302)


@app.get("/install.sh", include_in_schema=False)
def install_sh() -> RedirectResponse:
    return _installer_redirect("install.sh")


@app.get("/install_lib.sh", include_in_schema=False)
def install_lib_sh() -> RedirectResponse:
    return _installer_redirect("install_lib.sh")


@app.get("/install.ps1", include_in_schema=False)
def install_ps1() -> RedirectResponse:
    return _installer_redirect("install.ps1")


@app.get("/install_lib.ps1", include_in_schema=False)
def install_lib_ps1() -> RedirectResponse:
    return _installer_redirect("install_lib.ps1")


@app.get("/releases/manifest-{channel}.json", include_in_schema=False)
def release_manifest(channel: str) -> RedirectResponse:
    if channel not in _MANIFEST_CHANNELS:
        raise HTTPException(status_code=404)
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/"
        f"releases/manifest-{channel}.json"
    )
    return RedirectResponse(url, status_code=302)


def _fallback_readout() -> str:
    """Static hero readout from site.yaml, used when GitHub is unreachable."""
    readouts = child(child(content, "hero"), "readouts")
    return str(readouts.get("bottom", ""))


def _fetch_release_readout() -> str | None:
    """Fetch the published version from the release manifest on GitHub.

    Returns ``v<version> · <channel>`` for the CLI package, or None on any
    network/parse failure so the caller can fall back to the static value.
    """
    request = urllib.request.Request(
        RELEASE_MANIFEST_URL,
        headers={"Accept": "application/json", "User-Agent": "logion-landing"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            data = json.loads(response.read())
    except (OSError, urllib.error.URLError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    packages = data.get("packages")
    cli = packages.get("logion-cli") if isinstance(packages, dict) else None
    version = cli.get("version") if isinstance(cli, dict) else None
    if not isinstance(version, str) or not version:
        return None
    channel = data.get("channel", _READOUT_CHANNEL)
    return f"v{version} · {channel}"


def release_readout(*, now: float | None = None) -> str:
    """Hero readout derived from GitHub Releases, cached with a TTL.

    On a cache miss this performs one synchronous fetch (bounded by the
    2.5s timeout); it never *fails* rendering on a network error — a failed
    fetch falls back to the static site.yaml readout. Within the TTL the
    cached value is returned with no network call.
    """
    current = time.monotonic() if now is None else now
    cached = _readout_cache["value"]
    if cached is not None and current - _readout_cache["at"] < (
        _READOUT_TTL_SECONDS
    ):
        return cached
    value = _fetch_release_readout() or _fallback_readout()
    _readout_cache["value"] = value
    _readout_cache["at"] = current
    return value


def _ctx(**extra: object) -> dict[str, object]:
    # A Jinja render context, not a JSON payload: values are
    # arbitrary Python objects the templates consume directly.
    ctx: dict[str, object] = dict(content)
    ctx.setdefault("breadcrumbs", child(content, "breadcrumbs"))
    ctx.setdefault("page_date_modified", None)
    ctx.setdefault("release_readout", _fallback_readout())
    ctx.setdefault("setup_mode", False)
    ctx.setdefault(
        "api_base",
        os.environ.get("LOGION_API_BASE_URL", "https://api.logion.sh"),
    )
    ctx.setdefault("asset_v", ASSET_VERSION)
    ctx.update(extra)
    return ctx


def _legal_date_modified(slug: str) -> str | None:
    page = child(child(content, "legal"), slug)
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
    site = child(content, "site")
    sections: list[str] = [f"# {site.get('name', 'Logion')} — full content\n"]
    summary = site.get("one_liner") or child(content, "ai").get(
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
    faq_items = children(child(content, "faq"), "items")
    if faq_items:
        sections.append("## FAQ\n")
        for item in faq_items:
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
    design = child(content, "design")
    site = child(content, "site")
    palette = child(design, "palette")
    type_cfg = child(design, "type")
    logos = child(design, "logos")
    links = child(design, "links")
    base = str(child(content, "seo").get("canonical_base", "")).rstrip("/")

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
        block = child(palette, theme)
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
    for item in children(design, "motif"):
        lines.append(f"- {item}")
    lines += ["", "## links"]
    for key, href in links.items():
        lines.append(f"- {key}: {_abs(str(href))}")
    return "\n".join(lines).rstrip() + "\n"


def ai_catalog() -> JsonObject:
    """The Agentic Resource Discovery catalog for /.well-known/ai-catalog.json.

    A Level 2 (Discoverable) catalog: ``specVersion`` and ``entries`` plus a
    ``host`` block identifying the operator. Entries are read from site.yaml
    rather than assembled here, so the catalog can only ever advertise an
    artifact the content file actually declares — a catalog entry pointing at
    nothing is worse for an agent than no catalog at all.
    """
    catalog = child(child(content, "ai"), "catalog")
    organization = child(child(content, "seo"), "organization")
    entries: list[JsonObject] = []
    for raw in children(catalog, "entries"):
        url = str(raw.get("url", ""))
        entry: JsonObject = {
            "identifier": str(raw.get("identifier", "")),
            "type": str(raw.get("type", "")),
            "url": url if url.startswith("https://") else canonical_url(url),
        }
        for source_key, field in (
            ("display_name", "displayName"),
            ("description", "description"),
        ):
            value = str(raw.get(source_key, "")).strip()
            if value:
                entry[field] = value
        tags = strings(raw, "tags")
        if tags:
            entry["tags"] = tags
        entries.append(entry)
    host: JsonObject = {
        "displayName": str(organization.get("name", "Logion")),
        "identifier": str(catalog.get("host_identifier", "")),
        "logoUrl": canonical_url("/static/favicon.svg"),
    }
    documentation_url = str(catalog.get("documentation_url", "")).strip()
    if documentation_url:
        host["documentationUrl"] = documentation_url
    return {
        "specVersion": str(catalog.get("spec_version", "1.0")),
        "host": host,
        "entries": entries,
    }


def _skill_artifact_path(entry: JsonObject) -> Path:
    """Resolve a declared skill artifact to a path inside ``content/``."""
    artifact = entry.get("artifact")
    if not isinstance(artifact, str):
        raise TypeError("agent skill entry must define an artifact path")
    resolved = (CONTENT_DIR / artifact).resolve()
    if not resolved.is_relative_to(CONTENT_DIR.resolve()):
        raise ValueError(f"skill artifact {artifact!r} escapes content dir")
    return resolved


def agent_skills_index() -> JsonObject:
    """The Agent Skills discovery index for /.well-known/agent-skills.

    Each digest is a SHA-256 over the bytes this app actually serves, read at
    request time rather than written into site.yaml: a hand-maintained digest
    is a digest that silently stops matching the artifact.
    """
    skills: list[JsonObject] = []
    for entry in children(child(content, "ai"), "agent_skills"):
        name = str(entry.get("name", ""))
        digest = hashlib.sha256(
            _skill_artifact_path(entry).read_bytes()
        ).hexdigest()
        skills.append({
            "name": name,
            "type": str(entry.get("type", "skill-md")),
            "description": str(entry.get("description", "")).strip(),
            "url": canonical_url(f"/.well-known/agent-skills/{name}/SKILL.md"),
            "digest": f"sha256:{digest}",
        })
    return {
        "$schema": AGENT_SKILLS_SCHEMA,
        "skills": skills,
    }


def pricing_markdown() -> str:
    """The pricing table as markdown, for both /pricing and /pricing.md."""
    pricing_cfg = child(content, "pricing")
    lines = [
        f"# {pricing_cfg.get('heading', 'Pricing')}",
        "",
        str(pricing_cfg.get("intro", "")),
    ]
    for row in children(pricing_cfg, "rows"):
        lines.append(f"- **{row.get('label')}**: {row.get('value')}")
    return "\n".join(lines).rstrip() + "\n"


def markdown_for_slug(slug: str) -> str | None:
    """Markdown for a ``.md`` slug, or None when the slug is not a page."""
    if slug == "index":
        return markdown_content
    if slug == "aktp":
        return aktp_markdown_content
    if slug == "pricing":
        return pricing_markdown()
    legal_slug = MARKDOWN_SLUGS.get(slug)
    if legal_slug is not None:
        return legal_page(legal_slug)["markdown"]
    return None


def not_found_markdown() -> str:
    """A recovery note for an agent that landed on a path we do not serve.

    A bare 404 leaves a crawler with nowhere to go. Naming the machine-readable
    entrypoints costs one small body and turns a dead end into a redirect the
    agent performs itself.
    """
    site = child(content, "site")
    lines = [
        "# 404 — not found",
        "",
        f"{site.get('name', 'Logion')} does not serve this path. "
        "Start from one of these:",
        "",
    ]
    for path in ("/", "/pricing", "/llms.txt", "/llms-full.txt"):
        lines.append(f"- {canonical_url(path)}")
    lines += [
        "",
        "## Machine-readable entrypoints",
        "",
        f"- {canonical_url('/.well-known/ai-catalog.json')}"
        " — every Logion artifact an agent can use",
        f"- {canonical_url('/.well-known/agent-skills/index.json')}"
        " — installable skills",
        f"- {canonical_url('/sitemap.xml')} — every public page",
        f"- {API_BASE}/openapi.json — the marketplace API contract",
    ]
    return "\n".join(lines).rstrip() + "\n"


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if "text/markdown" in request.headers.get("accept", ""):
        return PlainTextResponse(
            markdown_content,
            media_type="text/markdown; charset=utf-8",
        )
    return templates.TemplateResponse(
        request, "index.html", _ctx(release_readout=release_readout())
    )


@app.get("/setup/complete", response_class=HTMLResponse)
def setup_complete(request: Request) -> Response:
    """Render the hero page in setup mode after GitHub OAuth.

    The raw setup token is never in the URL; a single-use handoff id is
    carried in the fragment (#hid=...) and claimed by browser JS directly
    against the API. This route only serves the shell; personalization is
    injected client-side.
    """
    response = templates.TemplateResponse(
        request,
        "index.html",
        _ctx(
            release_readout=release_readout(),
            setup_mode=True,
        ),
    )
    # Transitional OAuth-flow page: never cache, never index.
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@app.get("/aktp", response_class=HTMLResponse)
def aktp(request: Request) -> Response:
    if _wants_markdown(request):
        return PlainTextResponse(
            aktp_markdown_content,
            media_type="text/markdown; charset=utf-8",
        )
    return templates.TemplateResponse(request, "aktp.html", _ctx())


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request) -> Response:
    if _wants_markdown(request):
        return PlainTextResponse(
            pricing_markdown(),
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
    referral_cfg = child(content, "referral")
    template = str(
        referral_cfg.get(
            "command_template",
            "logion courses acquire {slug} --referral-code {code}",
        )
    )
    if referral_code:
        command = template.format(slug=course_slug, code=referral_code)
    else:
        command = f"logion courses acquire {course_slug}"
    # Keep referral landing attribution-free at the browser layer.
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


@app.get("/.well-known/ai-catalog.json")
def well_known_ai_catalog() -> Response:
    """Serve the Agentic Resource Discovery catalog."""
    return Response(
        json.dumps(ai_catalog(), indent=2) + "\n",
        media_type=AI_CATALOG_MEDIA_TYPE,
    )


@app.get("/.well-known/agent-skills/index.json")
def well_known_agent_skills() -> Response:
    """Serve the Agent Skills discovery index."""
    return Response(
        json.dumps(agent_skills_index(), indent=2) + "\n",
        media_type="application/json",
    )


@app.get("/.well-known/agent-skills/{name}/SKILL.md")
def well_known_skill(name: str) -> PlainTextResponse:
    """Serve a declared skill artifact as markdown.

    Only names declared in site.yaml resolve, so the path parameter cannot
    be used to read an arbitrary file out of ``content/``.
    """
    for entry in children(child(content, "ai"), "agent_skills"):
        if entry.get("name") == name:
            return PlainTextResponse(
                _skill_artifact_path(entry).read_text(encoding="utf-8"),
                media_type="text/markdown; charset=utf-8",
            )
    raise HTTPException(status_code=404, detail="skill not found")


@app.get("/{slug}.md", response_class=PlainTextResponse)
def page_markdown(slug: str) -> PlainTextResponse:
    """Serve a page's markdown at a stable URL, without content negotiation."""
    markdown = markdown_for_slug(slug)
    if markdown is None:
        raise HTTPException(status_code=404, detail="page not found")
    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
    )


@app.get("/openapi.json", include_in_schema=False)
def openapi_contract() -> RedirectResponse:
    """Point agents at the marketplace contract, not at this app's routes."""
    return RedirectResponse(f"{API_BASE}/openapi.json", status_code=302)


@app.get("/docs", include_in_schema=False)
def api_docs() -> RedirectResponse:
    """Point /docs at the API reference rather than this app's Swagger UI."""
    return RedirectResponse(f"{API_BASE}/docs", status_code=302)


@app.exception_handler(404)
async def not_found_handler(request: Request, _exc: Exception) -> Response:
    """Answer a 404 with a body the caller can actually act on.

    Content-negotiated three ways because the three kinds of caller want
    different things from a miss: a browser wants the page, an API client
    wants the JSON error shape it already parses, and a crawler sending
    ``*/*`` wants somewhere to go next — so markdown is the default.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(
            request, "not_found.html", _ctx(), status_code=404
        )
    if "application/json" in accept:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return PlainTextResponse(
        not_found_markdown(),
        status_code=404,
        media_type="text/markdown; charset=utf-8",
    )


def main() -> None:
    import uvicorn

    host = os.getenv("LOGION_LANDING_HOST", "127.0.0.1")
    port = int(os.getenv("LOGION_LANDING_PORT", "8001"))
    uvicorn.run("landing.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
