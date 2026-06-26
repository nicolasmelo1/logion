# SPDX-License-Identifier: MIT
"""Tests for bundled documentation articles."""

from __future__ import annotations

from importlib.resources import files


def test_docs_marketplace_loop_article_exists() -> None:
    """The marketplace-loop article must be bundled and loadable."""
    article_path = files("cli.docs") / "marketplace-loop.md"
    assert article_path.is_file(), (
        "marketplace-loop.md is missing from cli.docs"
    )
    text = article_path.read_text(encoding="utf-8")
    # Frontmatter with summary is required by the docs loader.
    assert text.startswith("---"), (
        "marketplace-loop.md must start with frontmatter"
    )
    assert "summary:" in text[:200], (
        "marketplace-loop.md must have a summary field"
    )
    assert "# " in text, "marketplace-loop.md must have a heading"
    # Core sections from the plan.
    assert "Search by category" in text
    assert "Inspect" in text
    assert "Free acquisition" in text
    assert "Paid acquisition" in text
    assert "Install" in text
    assert "review" in text.lower()
    assert "Bounty" in text or "bounty" in text
    assert "publication" in text.lower()


def test_docs_search_finds_bounty_almost_fits() -> None:
    """``logion docs search`` must find the marketplace-loop article
    when searching for 'almost fits'."""
    from cli.commands.docs.handlers import _load_articles

    articles = _load_articles()
    slugs = [a.slug for a in articles]
    assert "marketplace-loop" in slugs, "marketplace-loop article not loaded"

    # Simulate the search: check that 'almost fits' appears in the
    # marketplace-loop article content.
    article = next(a for a in articles if a.slug == "marketplace-loop")
    haystack = " ".join((
        article.slug,
        article.title,
        article.summary,
        article.content,
    )).casefold()
    assert "almost fits" in haystack or "almost-good" in haystack, (
        "marketplace-loop article must contain 'almost fits' or "
        "'almost-good' so docs search can discover it"
    )
