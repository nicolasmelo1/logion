"""Architecture tests: enforce domain design rules.

These tests assert that the social-management package follows the
domain-based structure (core, discord, x, cost, content) with
constants.py and models.py per domain, and that no constants are
loose in non-constants modules.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent / "social_management"

DOMAINS = ["core", "discord", "x", "cost", "content"]

REQUIRED_FILES = {
    "core": [
        "__init__.py",
        "constants.py",
        "config.py",
        "errors.py",
        "models.py",
    ],
    "discord": ["__init__.py", "constants.py", "models.py", "client.py"],
    "x": ["__init__.py", "constants.py", "models.py", "client.py"],
    "cost": ["__init__.py", "constants.py", "estimator.py", "ledger.py"],
    "content": ["__init__.py", "constants.py", "queue.py"],
}


def _module_names(node: ast.Module) -> set[str]:
    """Return top-level names assigned at module level."""
    names: set[str] = set()
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(item, ast.AnnAssign) and isinstance(
            item.target, ast.Name
        ):
            names.add(item.target.id)
    return names


class TestDomainStructure:
    """Verify the domain package structure exists and is complete."""

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_dir_exists(self, domain: str) -> None:
        assert (PKG_ROOT / domain).is_dir(), f"missing domain dir: {domain}"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_has_required_files(self, domain: str) -> None:
        for fname in REQUIRED_FILES[domain]:
            assert (PKG_ROOT / domain / fname).exists(), (
                f"missing {fname} in domain {domain}"
            )

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_has_constants_py(self, domain: str) -> None:
        assert (PKG_ROOT / domain / "constants.py").exists(), (
            f"domain {domain} must have constants.py"
        )

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_has_init_py(self, domain: str) -> None:
        assert (PKG_ROOT / domain / "__init__.py").exists(), (
            f"domain {domain} must have __init__.py"
        )


class TestNoConstantsOutsideConstantsPy:
    """Ensure module-level ALL_CAPS constants live in constants.py only."""

    # Modules that are allowed to have uppercase names (not constants).
    ALLOWED_MODULES: ClassVar[set[str]] = {
        "constants.py",
        "__init__.py",
        "config.py",  # SocialConfig, XBackend type alias
        "models.py",  # Pydantic models
        "errors.py",  # Exception classes
        "cli.py",  # argparse
        "__main__.py",
    }

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_no_loose_constants_in_domain_modules(self, domain: str) -> None:
        domain_dir = PKG_ROOT / domain
        for py_file in domain_dir.glob("*.py"):
            if py_file.name in self.ALLOWED_MODULES:
                continue
            source = py_file.read_text()
            tree = ast.parse(source)
            names = _module_names(tree)
            upper_names = {n for n in names if n.isupper() and len(n) > 1}
            assert not upper_names, (
                f"{py_file.name} in domain {domain} has loose "
                f"constants: {upper_names}. Move them to constants.py."
            )

    def test_no_loose_constants_in_top_level_modules(self) -> None:
        for py_file in PKG_ROOT.glob("*.py"):
            if py_file.name in self.ALLOWED_MODULES:
                continue
            source = py_file.read_text()
            tree = ast.parse(source)
            names = _module_names(tree)
            upper_names = {n for n in names if n.isupper() and len(n) > 1}
            assert not upper_names, (
                f"{py_file.name} has loose constants: "
                f"{upper_names}. Move them to a domain constants.py."
            )


class TestDomainImportability:
    """Verify each domain is importable and exports its key symbols."""

    def test_core_exports_config_and_errors(self) -> None:
        from social_management.core.config import SocialConfig
        from social_management.core.errors import SocialError

        assert SocialConfig is not None
        assert SocialError is not None

    def test_discord_exports_client(self) -> None:
        from social_management.discord.client import DiscordClient

        assert DiscordClient is not None

    def test_x_exports_client(self) -> None:
        from social_management.x.client import XClient

        assert XClient is not None

    def test_cost_exports_estimator_and_ledger(self) -> None:
        from social_management.cost.estimator import CostEstimator
        from social_management.cost.ledger import SpendLedger

        assert CostEstimator is not None
        assert SpendLedger is not None

    def test_content_exports_queue(self) -> None:
        from social_management.content.queue import add, list_drafts

        assert add is not None
        assert list_drafts is not None

    def test_discord_constants_importable(self) -> None:
        from social_management.discord.constants import (
            DISCORD_API,
            KNOWN_FORUM_CHANNELS,
        )

        assert DISCORD_API
        assert KNOWN_FORUM_CHANNELS

    def test_x_constants_importable(self) -> None:
        from social_management.x.constants import X_API

        assert X_API

    def test_cost_constants_importable(self) -> None:
        from social_management.cost.constants import (
            POST_COST_CENTS,
            POST_WITH_LINK_COST_CENTS,
        )

        assert POST_COST_CENTS > 0
        assert POST_WITH_LINK_COST_CENTS > 0

    def test_content_constants_importable(self) -> None:
        from social_management.content.constants import CONTENT_DIR

        assert CONTENT_DIR

    def test_core_constants_importable(self) -> None:
        from social_management.core.constants import (
            WEBHOOK_ENV_BY_CHANNEL,
        )

        assert WEBHOOK_ENV_BY_CHANNEL


class TestNoOldStyleImports:
    """Ensure old flat-module imports are gone."""

    def test_no_top_level_models_module(self) -> None:
        assert not (PKG_ROOT / "models.py").exists(), (
            "models.py should be split into domain models.py files"
        )

    def test_no_top_level_errors_module(self) -> None:
        assert not (PKG_ROOT / "errors.py").exists(), (
            "errors.py should be in core/"
        )

    def test_no_top_level_config_module(self) -> None:
        assert not (PKG_ROOT / "config.py").exists(), (
            "config.py should be in core/"
        )

    def test_no_top_level_cost_module(self) -> None:
        assert not (PKG_ROOT / "cost.py").exists(), (
            "cost.py should be split into cost/ domain"
        )

    def test_no_top_level_discord_module(self) -> None:
        assert not (PKG_ROOT / "discord.py").exists(), (
            "discord.py should be in discord/ domain"
        )

    def test_no_top_level_x_client_module(self) -> None:
        assert not (PKG_ROOT / "x_client.py").exists(), (
            "x_client.py should be in x/ domain"
        )

    def test_no_top_level_content_module(self) -> None:
        assert not (PKG_ROOT / "content.py").exists(), (
            "content.py should be in content/ domain"
        )
