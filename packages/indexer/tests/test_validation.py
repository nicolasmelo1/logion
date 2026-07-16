"""Tests for inferred_map fragment validation via logion_skillmap."""

from __future__ import annotations

from logion_indexer.validation import (
    INFERRED_MAP_INVALID,
    fragment_errors,
    is_valid_fragment,
)

VALID = {
    "version": 1,
    "package": {"slug": "foo"},
    "components": {
        "capabilities": {"foo": {"entrypoint": "skills/foo/SKILL.md"}},
        "runtime": {
            "include": ["skills/foo/**"],
            "entrypoint": "skills/foo/SKILL.md",
        },
    },
}


class TestFragmentValidation:
    def test_valid_fragment(self) -> None:
        assert is_valid_fragment(VALID)
        assert fragment_errors(VALID) == []

    def test_null_fragment_invalid(self) -> None:
        assert not is_valid_fragment(None)
        assert fragment_errors(None) == [INFERRED_MAP_INVALID]

    def test_empty_capabilities_invalid(self) -> None:
        bad = {"version": 1, "package": {"slug": "x"}, "components": {}}
        assert not is_valid_fragment(bad)

    def test_unsupported_version_invalid(self) -> None:
        bad = dict(VALID)
        bad["version"] = 99
        assert not is_valid_fragment(bad)

    def test_traversal_entrypoint_invalid(self) -> None:
        bad = {
            "version": 1,
            "package": {"slug": "x"},
            "components": {
                "capabilities": {"x": {"entrypoint": "../escape/SKILL.md"}},
                "runtime": {"include": ["**"]},
            },
        }
        assert not is_valid_fragment(bad)
