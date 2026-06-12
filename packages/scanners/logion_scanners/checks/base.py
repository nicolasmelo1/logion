"""Base class for agent scanner checks."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from logion_scanners.models import ScannerFinding

# Binary/executable extensions to skip during text-based scanning.
SKIP_EXTENSIONS: frozenset[str] = frozenset({
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    # Documents/archives
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    # Blocked executables/binaries
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".msi",
    ".com",
    ".scr",
    ".app",
    ".deb",
    ".rpm",
    ".iso",
    ".dmg",
})


@dataclass(frozen=True)
class Pattern:
    """A scanner pattern definition."""

    regex: str
    rule_id: str
    description: str


# Pre-enumerated file content shared across checks.
FileContent = tuple[Path, str, str]  # (abs_path, relative_path, content)


class BaseCheck(ABC):
    """Abstract base class for agent scanner checks."""

    name: str = "unnamed-check"

    @abstractmethod
    def run(
        self,
        bundle_path: Path,
        files: list[FileContent] | None = None,
    ) -> list[ScannerFinding]:
        """Scan a course bundle directory and return findings."""
        ...


def iter_text_files(
    bundle_path: Path,
    *,
    extra_skip: frozenset[str] | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> Iterator[FileContent]:
    """Walk a bundle and yield (abs_path, relative_path, content)
    tuples."""
    skip = SKIP_EXTENSIONS | (extra_skip or frozenset())
    for p in bundle_path.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in skip:
            continue
        if allowed_extensions and ext and ext not in allowed_extensions:
            continue
        try:
            content = p.read_text(errors="replace", encoding="utf-8")
        except OSError:
            continue
        rel = str(p.relative_to(bundle_path))
        yield (p, rel, content)


MARKDOWN_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown"})

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def iter_command_lines(
    content: str,
    suffix: str,
) -> Iterator[tuple[int, str]]:
    """Yield ``(line_no, line)`` pairs eligible for command-pattern checks.

    Markdown prose routinely *talks about* commands ("there is no
    ``pip install`` step") without executing anything; only fenced code
    blocks carry executable intent. For markdown files, yield only the
    lines inside ``\\`\\`\\```/``~~~`` fences (line numbers preserved);
    for every other file type, yield all lines.
    """
    if suffix.lower() not in MARKDOWN_EXTENSIONS:
        yield from enumerate(content.splitlines(), start=1)
        return
    in_fence = False
    for line_no, line in enumerate(content.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            yield (line_no, line)


def collect_text_files(
    bundle_path: Path,
    *,
    extra_skip: frozenset[str] | None = None,
    allowed_extensions: frozenset[str] | None = None,
) -> list[FileContent]:
    """Materialize iter_text_files() into a list."""
    return list(
        iter_text_files(
            bundle_path,
            extra_skip=extra_skip,
            allowed_extensions=allowed_extensions,
        )
    )
