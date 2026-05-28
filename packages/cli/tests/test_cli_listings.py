"""Tests for listings commands."""

from __future__ import annotations

import argparse

from cli.commands.listings.parser import register


def test_listings_search_default_limit_is_twenty() -> None:
    """listings search --limit defaults to 20."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)
    args = parser.parse_args(["listings", "search"])
    assert args.limit == 20
