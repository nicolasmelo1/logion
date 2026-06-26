# SPDX-License-Identifier: MIT
"""Tests for bounty-first companion guidance and reference routing.

Verifies that SKILL.md teaches category/tag search, routes to
bounties when a course almost fits, and that bounties.md is in the
reference routing inventory.
"""

from __future__ import annotations

from pathlib import Path

from evals.optimizers.dspy.reference_routing_inventory import REFERENCE_NAMES

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = PACKAGE_ROOT / "SKILL.md"
BOUNTIES_REF = PACKAGE_ROOT / "references" / "bounties.md"


def test_skill_mentions_category_tag_search() -> None:
    """SKILL.md must mention --category and --tag for structured search."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "--category" in text, "SKILL.md must mention --category"
    assert "--tag" in text, "SKILL.md must mention --tag"


def test_skill_mentions_bounty_routing_when_almost_fits() -> None:
    """SKILL.md must route to bounties when a course almost fits."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "almost" in text.lower(), (
        "SKILL.md must mention the 'almost fits' bounty routing rule"
    )
    assert "bounties.md" in text, (
        "SKILL.md must reference references/bounties.md for bounty routing"
    )


def test_bounties_reference_in_routing_inventory() -> None:
    """bounties must be in the canonical reference routing inventory."""
    assert "bounties" in REFERENCE_NAMES, (
        "'bounties' must be in REFERENCE_NAMES for reference routing"
    )
    assert BOUNTIES_REF.is_file(), "references/bounties.md must exist"


def test_bounties_reference_has_when_to_create_section() -> None:
    """bounties.md must have a 'When to create a bounty' section."""
    text = BOUNTIES_REF.read_text(encoding="utf-8")
    assert "When to create a bounty" in text


def test_bounties_reference_has_do_not_create_section() -> None:
    """bounties.md must have a 'Do not create a bounty when' section."""
    text = BOUNTIES_REF.read_text(encoding="utf-8")
    assert "Do not create a bounty when" in text


def test_bounties_reference_has_creator_funded_flow() -> None:
    """bounties.md must have a minimal creator-funded flow example."""
    text = BOUNTIES_REF.read_text(encoding="utf-8")
    assert "Minimal creator-funded flow" in text
    assert "logion bounties create" in text
    assert "logion bounties fund" in text
    assert "logion bounties open" in text


def test_bounties_reference_examples_no_yes_in_agent_facing_flow() -> None:
    """Creator-funded flow must not use --yes (agents must ask)."""
    text = BOUNTIES_REF.read_text(encoding="utf-8")
    # Find the "Minimal creator-funded flow" section.
    section_start = text.find("## Minimal creator-funded flow")
    assert section_start >= 0
    # Get the section up to the next ## heading or end of file.
    next_heading = text.find("\n## ", section_start + 1)
    if next_heading < 0:
        next_heading = len(text)
    section = text[section_start:next_heading]
    # Check only bash code blocks (between ```bash and ```), not the
    # surrounding prose which may mention --yes in instruction text.
    import re

    bash_blocks = re.findall(r"```bash\n(.*?)```", section, re.DOTALL)
    for block in bash_blocks:
        assert "--yes" not in block, (
            "Creator-funded flow bash example must not include --yes"
        )
