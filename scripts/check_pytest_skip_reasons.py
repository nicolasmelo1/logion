#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Require an explanation on every pytest skip / xfail.

Forbidden forms (any of these fail the check):

  - ``pytest.skip()``                  — no reason given
  - ``@pytest.mark.skip``              — bare marker, no reason
  - ``@pytest.mark.skip()``            — empty call, no reason
  - ``@pytest.mark.skipif(cond)``      — no reason kwarg
  - ``@pytest.mark.xfail``             — bare marker, no reason
  - ``@pytest.mark.xfail()``           — empty call, no reason

Allowed:

  - ``pytest.skip("explanation")`` / ``pytest.skip(reason="...")``
  - ``pytest.importorskip("module")`` (different API, by design)
  - ``@pytest.mark.skip("explanation")`` /
    ``@pytest.mark.skip(reason="...")``

Disabling a test without saying why is the single highest-velocity
way for AI contributors to silently shed coverage. The rule is
small and the cost of writing one sentence is trivial.
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SCAN_DIRS = ("packages", "tests")
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

SKIP_FUNCS = {"skip"}
MARK_NAMES_REQUIRING_REASON = {"skip", "skipif", "xfail"}


def _has_reason(call: ast.Call) -> bool:
    """A call has a 'reason' if it carries a non-empty positional string
    OR a ``reason=...`` keyword argument."""
    for kw in call.keywords:
        if kw.arg == "reason":
            return True
    # Positional string reason — pytest accepts this form.
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return True
    return False


def _is_pytest_attr(node: ast.AST, name: str) -> bool:
    """True if `node` is `pytest.<name>` (attribute access)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == "pytest"
    )


def _is_pytest_mark(node: ast.AST) -> str | None:
    """If `node` is `pytest.mark.<X>`, return X; else None."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    ):
        return node.attr
    return None


def scan(path: str) -> list[tuple[int, str]]:
    """Return [(lineno, message), ...] for each offending node."""
    with open(path) as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []
    hits: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        # 1. Direct calls: pytest.skip(...)
        if (
            isinstance(node, ast.Call)
            and _is_pytest_attr(node.func, "skip")
            and not _has_reason(node)
        ):
            hits.append((
                node.lineno,
                "pytest.skip() without a reason",
            ))

        # 2. Decorators that need a reason: skip / skipif / xfail
        decorator_lists = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            decorator_lists.append(node.decorator_list)
        if isinstance(node, ast.ClassDef):
            decorator_lists.append(node.decorator_list)

        for decorators in decorator_lists:
            for dec in decorators:
                # Bare attribute, no call: @pytest.mark.skip
                mark = _is_pytest_mark(dec)
                if mark in MARK_NAMES_REQUIRING_REASON:
                    hits.append((
                        dec.lineno,
                        f"@pytest.mark.{mark} without a reason",
                    ))
                    continue
                # Call form: @pytest.mark.skip(...) etc.
                if isinstance(dec, ast.Call):
                    inner_mark = _is_pytest_mark(dec.func)
                    if (
                        inner_mark in MARK_NAMES_REQUIRING_REASON
                        and not _has_reason(dec)
                    ):
                        hits.append((
                            dec.lineno,
                            f"@pytest.mark.{inner_mark}() without a reason",
                        ))
    return hits


def iter_python_files() -> list[str]:
    files: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(ROOT, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                if fname.endswith(".py"):
                    files.append(os.path.join(dirpath, fname))
    return sorted(files)


def main() -> None:
    failures: list[tuple[str, int, str]] = []
    for path in iter_python_files():
        rel = os.path.relpath(path, ROOT)
        for lineno, msg in scan(path):
            failures.append((rel, lineno, msg))

    if not failures:
        print("check_pytest_skip_reasons: ok.")
        return

    print("check_pytest_skip_reasons: missing-reason hits:")
    for rel, lineno, msg in failures:
        print(f"  {rel}:{lineno}  {msg}")
    print(
        "\nAdd a one-sentence explanation: "
        '`pytest.skip("why")` or `@pytest.mark.skip(reason="why")`.'
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
