# SPDX-License-Identifier: MIT
"""Handlers for bundled Logion documentation."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from importlib.resources import files

from cli._output import emit_json

_ARTICLES_PACKAGE = "cli.docs"
_HEADING = re.compile(r"^# (.+)$", re.MULTILINE)
_SUMMARY = re.compile(r"^summary:\s*(.+)$", re.MULTILINE)
_META = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    summary: str
    content: str


def _load_articles() -> list[Article]:
    articles: list[Article] = []
    for resource in files(_ARTICLES_PACKAGE).iterdir():
        if not resource.name.endswith(".md") or resource.name == "README.md":
            continue
        raw = resource.read_text(encoding="utf-8")
        title_match = _HEADING.search(raw)
        summary_match = _SUMMARY.search(raw)
        articles.append(
            Article(
                slug=resource.name.removesuffix(".md"),
                title=title_match.group(1) if title_match else resource.name,
                summary=summary_match.group(1) if summary_match else "",
                content=_META.sub("", raw, count=1).rstrip() + "\n",
            )
        )
    return sorted(articles, key=lambda article: article.slug)


def _article_payload(article: Article) -> dict[str, str]:
    return {
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
    }


def handle_docs(args: argparse.Namespace) -> int:
    """List articles or print one complete article."""
    if args.article == "search":
        return handle_docs_search(args)
    articles = _load_articles()
    if not args.article:
        data = [
            {
                "slug": article.slug,
                "title": article.title,
                "summary": article.summary,
            }
            for article in articles
        ]
        if args.json_output:
            emit_json("logion.docs.index", {"articles": data})
            return 0
        print("Logion documentation (bundled with this CLI):")
        for entry in data:
            print(f"  {entry['slug']:<22} {entry['summary']}")
        print("\nRead:   logion docs ARTICLE")
        print('Search: logion docs search "QUERY"')
        return 0

    by_slug = {article.slug: article for article in articles}
    article = by_slug.get(args.article)
    if article is None:
        suggestions = difflib.get_close_matches(args.article, by_slug, n=3)
        message = f"Unknown documentation article: {args.article}"
        if suggestions:
            message += f". Did you mean: {', '.join(suggestions)}?"
        print(message, file=sys.stderr)
        return 2
    if args.json_output:
        emit_json("logion.docs.article", _article_payload(article))
    else:
        print(article.content, end="")
    return 0


def handle_docs_search(args: argparse.Namespace) -> int:
    """Search titles, summaries, and article bodies."""
    query = " ".join(args.query).strip()
    if not query:
        print("A documentation search query is required.", file=sys.stderr)
        return 2
    terms = query.casefold().split()
    matches = []
    for article in _load_articles():
        haystack = " ".join((
            article.slug,
            article.title,
            article.summary,
            article.content,
        )).casefold()
        matched_terms = sum(term in haystack for term in terms)
        if matched_terms:
            score = matched_terms * 100 + sum(
                haystack.count(term) for term in terms
            )
            matches.append((score, article))
    matches.sort(key=lambda item: (-item[0], item[1].slug))
    results = [
        {
            "slug": article.slug,
            "title": article.title,
            "summary": article.summary,
        }
        for _, article in matches[: max(args.limit, 0)]
    ]
    payload = {"query": query, "matches": results, "total": len(matches)}
    if args.json_output:
        emit_json("logion.docs.search", payload)
        return 0
    if not results:
        print(f"No documentation matches for {query!r}.")
        return 0
    print(f"Documentation matches for {query!r}:")
    for result in results:
        print(f"  {result['slug']:<22} {result['summary']}")
    return 0
