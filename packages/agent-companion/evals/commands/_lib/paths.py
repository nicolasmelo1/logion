"""Path resolution helpers."""

from __future__ import annotations

from pathlib import Path


def resolve_path(value: str | Path, root: Path) -> Path:
    """Resolve ``value`` relative to ``root`` when it is not absolute.

    Expanduser, then anchor to ``root`` if relative, then ``.resolve()``.
    """
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


PACKAGE_ROOT: Path = Path(__file__).resolve().parents[3]
"""``packages/agent-companion/`` — the repo-relative anchor."""
