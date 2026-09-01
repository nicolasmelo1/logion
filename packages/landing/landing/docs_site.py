# SPDX-License-Identifier: MIT
"""Render the generated documentation artifact.

The artifact is compiled by ``scripts/gen_docs.py`` from the OpenAPI contract,
the CLI's argparse tree and the hand-written guides. This module only reads it.
Nothing here may derive content, because the landing deploys with
``packages/landing/`` as its root and cannot see ``contracts/`` or import the
CLI — the split is a deployment constraint, not a preference.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from markdown_it import MarkdownIt

from landing._json import JsonObject, JsonValue, child, children

CONTENT_DIR = Path(__file__).resolve().parent / "content"
DOCS_PATH = CONTENT_DIR / "docs.json"

#: Artifact shape this renderer understands. A newer artifact is refused
#: outright rather than rendered with fields silently dropped.
SUPPORTED_ARTIFACT_VERSION = 1

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,127}$")
_HEADING_RE = re.compile(r"^(#{1,3}) (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class DocsPage:
    """One rendered documentation page."""

    slug: str
    title: str
    summary: str
    kind: str
    body: str

    @property
    def url(self) -> str:
        return "/docs" if self.slug == "index" else f"/docs/{self.slug}"

    @property
    def markdown_url(self) -> str:
        # The index lives at /docs, and /docs.md sits outside the /docs/ route
        # tree, so its markdown twin is addressed by slug like every other one.
        return f"/docs/{self.slug}.md"


class NavLink(TypedDict):
    """A sidebar entry, ready for the template."""

    title: str
    summary: str
    url: str
    active: bool


class NavSection(TypedDict):
    """A sidebar group, with the active page marked."""

    id: str
    title: str
    summary: str
    pages: list[NavLink]
    active: bool


class Heading(TypedDict):
    """One entry in the on-page outline."""

    text: str
    anchor: str


def _str(value: JsonValue | None, default: str = "") -> str:
    return value if isinstance(value, str) else default


class DocsSite:
    """The documentation artifact, loaded once per process."""

    def __init__(self, data: JsonObject) -> None:
        version = data.get("artifact_version")
        if version != SUPPORTED_ARTIFACT_VERSION:
            raise ValueError(
                f"docs artifact version {version!r} is not supported by this "
                f"renderer (expects {SUPPORTED_ARTIFACT_VERSION})"
            )
        self.source: JsonObject = child(data, "source")
        self.sections: list[JsonObject] = children(data, "sections")
        self._pages = {
            slug: DocsPage(
                slug=slug,
                title=_str(page.get("title"), slug),
                summary=_str(page.get("summary")),
                kind=_str(page.get("kind"), "page"),
                body=_str(page.get("body")),
            )
            for slug, page in _page_entries(data)
        }

    def __contains__(self, slug: str) -> bool:
        return slug in self._pages

    def get(self, slug: str) -> DocsPage | None:
        if not _SLUG_RE.match(slug):
            return None
        return self._pages.get(slug)

    @property
    def pages(self) -> list[DocsPage]:
        return list(self._pages.values())

    def index(self) -> DocsPage:
        page = self._pages.get("index")
        if page is None:  # pragma: no cover - the generator always writes it
            raise KeyError("docs artifact has no index page")
        return page

    def nav(self, current: str) -> list[NavSection]:
        """Sidebar sections with the active page marked."""
        sections: list[NavSection] = []
        for section in self.sections:
            entries = children(section, "pages")
            sections.append(
                {
                    "id": _str(section.get("id")),
                    "title": _str(section.get("title")),
                    "summary": _str(section.get("summary")),
                    "pages": [
                        {
                            "title": _str(entry.get("title")),
                            "summary": _str(entry.get("summary")),
                            "url": f"/docs/{_str(entry.get('slug'))}",
                            "active": _str(entry.get("slug")) == current,
                        }
                        for entry in entries
                    ],
                    "active": any(
                        _str(entry.get("slug")) == current
                        for entry in entries
                    ),
                }
            )
        return sections

    def outline(self, page: DocsPage) -> list[Heading]:
        """On-page heading outline, for the right-hand rail."""
        return [
            {"text": text.strip(), "anchor": anchor_for(text.strip())}
            for hashes, text in _HEADING_RE.findall(page.body)
            if len(hashes) == 2
        ]

    def llms_txt(self, base: str) -> str:
        """A complete, flat index of every page, for agents."""
        lines = [
            "# Logion documentation",
            "",
            "> Generated from the OpenAPI contract, the CLI argparse tree, "
            "and the hand-written guides. Every page also answers at its "
            "`.md` URL.",
            "",
            f"- API operations: {self.source.get('operations', '?')}",
            f"- CLI commands: {self.source.get('cli_commands', '?')}",
            f"- Contract digest: {self.source.get('contract_digest', '?')}",
            "",
        ]
        for section in self.sections:
            lines.append(f"## {_str(section.get('title'))}")
            lines.append("")
            for entry in children(section, "pages"):
                summary = _str(entry.get("summary"))
                suffix = f": {summary}" if summary else ""
                slug = _str(entry.get("slug"))
                lines.append(
                    f"- [{_str(entry.get('title'))}]({base}/docs/{slug}.md)"
                    f"{suffix}"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


#: Tables are the whole point of a reference page, and CommonMark has none, so
#: the table rule is enabled explicitly. HTML stays off: the artifact is
#: generated, but the guides inside it are hand-written and go through the same
#: renderer, so raw HTML must not be a path into the page.
_renderer = MarkdownIt("commonmark", {"html": False}).enable("table")


def render_html(markdown: str) -> str:
    """Render a page body, giving every h2/h3 the anchor its links expect."""
    tokens = _renderer.parse(markdown)
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag not in ("h2", "h3"):
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        if inline is not None and inline.type == "inline":
            token.attrSet("id", anchor_for(inline.content))
    return _renderer.renderer.render(tokens, _renderer.options, {})


def anchor_for(text: str) -> str:
    """Slugify a heading. Must match ``scripts/gen_docs.py``."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _page_entries(data: JsonObject) -> list[tuple[str, JsonObject]]:
    """The ``pages`` map as ``(slug, page)`` pairs, narrowed."""
    pages = data.get("pages")
    if not isinstance(pages, dict):
        return []
    return [
        (slug, page) for slug, page in pages.items() if isinstance(page, dict)
    ]


def load_docs(path: Path = DOCS_PATH) -> DocsSite:
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise TypeError("docs artifact is not a JSON object")
    return DocsSite(loaded)
