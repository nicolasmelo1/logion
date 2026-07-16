"""Pin: the indexer must not re-implement SKILL.md scanning.

All tree-walking / SKILL.md parsing / skill-root discovery is delegated
to ``logion_skillmap``.  ``github_source.py`` is the single seam that
calls ``logion_skillmap.infer()``; no other module in the package may
import ``infer`` or parse SKILL.md frontmatter itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent / "logion_indexer"

# Substrings that betray a second scanner re-implementing skillmap logic.
# (``yaml.safe_load`` is intentionally excluded: config.py uses it to load
# the seed file, which is not skill scanning.)
_SCANNER_MARKERS = (
    "_parse_frontmatter",
    'split("---")',
    "_SKILL_MD",
)


def _sources() -> list[Path]:
    return [p for p in _PKG.rglob("*.py") if "__pycache__" not in p.parts]


class TestNoSecondScanner:
    def test_infer_imported_only_in_github_source(self) -> None:
        importers: set[str] = set()
        for path in _sources():
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "logion_skillmap"
                    and any(alias.name == "infer" for alias in node.names)
                ):
                    importers.add(path.name)
        assert importers <= {"github_source.py"}, (
            f"logion_skillmap.infer imported outside github_source.py: "
            f"{importers}"
        )

    def test_no_frontmatter_scanner_reimplemented(self) -> None:
        offenders: list[str] = []
        for path in _sources():
            text = path.read_text()
            for marker in _SCANNER_MARKERS:
                if marker in text:
                    offenders.append(f"{path.name}: {marker}")
        assert offenders == [], (
            f"second SKILL.md scanner detected: {offenders}"
        )
