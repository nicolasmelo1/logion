#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the Logion Marketplace Companion skill package.

Runs structural, manifest, and secret checks and prints a report.
Exits 0 on success, 1 on failure.

Usage:
    python scripts/package_skill.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "course",
    "references",
    "scripts",
    "tests",
]

REQUIRED_FILES = [
    "SKILL.md",
    "course/capabilities.yaml",
    "references/creator-course-management.md",
    "references/account-and-identity.md",
    "references/notifications-and-reports.md",
    "references/payments-and-checkout.md",
    "references/bounties.md",
    "references/course-review-queue.md",
    "references/admin-operations.md",
    "references/troubleshooting.md",
]

# High-confidence secret patterns: always FAIL the check.
SECRET_PATTERNS_CRITICAL = [
    "-----BEGIN",
    "ghp_",
    "gho_",
    "sk-",
    "AKIA",
    "private_key",
    "api_key",
    "apikey",
    "auth_token",
    "bearer ",
]

# Low-confidence patterns: WARN in source/asset files,
# FAIL only inside SKILL.md body.
SECRET_PATTERNS_LOW = [
    "secret",
    "token",
    "password",
    "credential",
]

MAX_SKILL_SIZE_KB = 16


def _check_structure(report: list[str]) -> bool:
    """Verify all required directories and files exist."""
    ok = True
    for d in REQUIRED_DIRS:
        if not (ROOT / d).is_dir():
            report.append(f"MISSING directory: {d}/")
            ok = False
        else:
            report.append(f"OK directory: {d}/")

    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            report.append(f"MISSING file: {f}")
            ok = False
        else:
            report.append(f"OK file: {f}")
    return ok


def _check_skill_md(report: list[str]) -> bool:
    """Verify SKILL.md has frontmatter and is within size budget."""
    ok = True
    skill_path = ROOT / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        report.append("FAIL SKILL.md missing frontmatter")
        ok = False
    else:
        report.append("OK SKILL.md has frontmatter")

    lines = content.splitlines()
    frontmatter_end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_end = i
            break

    if frontmatter_end is None:
        report.append("FAIL SKILL.md frontmatter not closed")
        return False

    body = "\n".join(lines[frontmatter_end + 1 :])

    size_kb = len(content.encode("utf-8")) / 1024
    if size_kb > MAX_SKILL_SIZE_KB:
        report.append(
            f"FAIL SKILL.md size {size_kb:.1f}KB exceeds "
            f"budget {MAX_SKILL_SIZE_KB}KB"
        )
        ok = False
    else:
        report.append(f"OK SKILL.md size {size_kb:.1f}KB within budget")

    for pattern in SECRET_PATTERNS_CRITICAL:
        if pattern.lower() in body.lower():
            report.append(
                f"FAIL SKILL.md body contains "
                f"critical secret pattern: {pattern}"
            )
            ok = False

    for pattern in SECRET_PATTERNS_LOW:
        if pattern.lower() in body.lower():
            report.append(
                f"WARN SKILL.md body contains "
                f"low-confidence pattern: {pattern}"
            )

    return ok


def _check_capabilities(report: list[str]) -> bool:
    """Verify the canonical capability manifest parses and is valid.

    The detailed schema validation (tools enum, domain rules, env regex,
    filesystem path rules) lives in
    ``packages/cli/cli/_course_capabilities.py`` and is exercised by
    ``tests/test_capability_manifest.py``.  Here we only confirm the
    file parses as a mapping with ``version: 1`` so this lint passes
    even when the cli package isn't on the path.
    """
    import yaml

    cap_path = ROOT / "course" / "capabilities.yaml"
    try:
        data = yaml.safe_load(cap_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.append("FAIL course/capabilities.yaml not found")
        return False
    except (OSError, yaml.YAMLError) as exc:
        report.append(f"FAIL course/capabilities.yaml read/parse error: {exc}")
        return False

    if not isinstance(data, dict):
        report.append("FAIL course/capabilities.yaml is not a mapping")
        return False

    if data.get("version") != 1:
        report.append(
            "FAIL course/capabilities.yaml: version must be exactly 1"
        )
        return False

    report.append("OK course/capabilities.yaml parses as version 1 manifest")
    if "summary" in data:
        report.append("OK capabilities.yaml has key: summary")
    return True


# Files where low-confidence patterns are acceptable.
_LOW_PATTERN_ALLOWLIST = {
    "capabilities.yaml",
    "account-and-identity.md",
    "troubleshooting.md",
}

# Files that reference secret pattern names for documentation
# or test assertions — not actual secrets.  ``capabilities.yaml``
# declares env var NAMES the course reads (e.g. ``DSPY_API_KEY``),
# never their values, so the critical scan must not flag it.
_SECRET_NAME_SKIP_FILES = {
    "package_skill.py",
    "test_package_skill.py",
    "test_skill_structure.py",
    "test_capability_manifest.py",
    "capabilities.yaml",
}


def _should_skip_path(
    path: Path, skip_dirs: set[str], skip_exts: set[str]
) -> bool:
    """Return True if this path should be skipped during checks."""
    if path.is_dir():
        return True
    if path.suffix in skip_exts:
        return True
    if any(part in skip_dirs for part in path.parts):
        return True
    if path.name in _SECRET_NAME_SKIP_FILES:
        return True
    rel = path.relative_to(ROOT)
    return rel.parts[0] == "tests" and path.suffix == ".py"


def _check_no_secrets(report: list[str]) -> bool:
    """Verify no runtime files contain critical secrets.

    Critical patterns (e.g. ghp_, AKIA, PEM headers) always FAIL
    outside of test/checker files.
    Low-confidence patterns (secret, token, password) only WARN
    outside of allowlisted documentation files.
    """
    ok = True
    skip_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "evals",
    }
    skip_exts = {".pyc", ".pyo", ".gguf", ".bin"}

    for path in ROOT.rglob("*"):
        if _should_skip_path(path, skip_dirs, skip_exts):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # nosec B110,B112
            continue

        text_lower = text.lower()
        rel = path.relative_to(ROOT)

        for pattern in SECRET_PATTERNS_CRITICAL:
            if pattern.lower() in text_lower:
                report.append(
                    f"FAIL {rel} contains critical secret pattern: {pattern}"
                )
                ok = False

        if path.name in _LOW_PATTERN_ALLOWLIST:
            continue

        for pattern in SECRET_PATTERNS_LOW:
            if pattern.lower() in text_lower:
                report.append(
                    f"WARN {rel} contains low-confidence pattern: {pattern}"
                )

    return ok


def main() -> int:
    report: list[str] = []
    ok = True

    ok &= _check_structure(report)
    ok &= _check_skill_md(report)
    ok &= _check_capabilities(report)
    ok &= _check_no_secrets(report)

    for line in report:
        print(line)

    if not ok:
        print("\nFAILED: Package validation failed.")
        return 1

    print("\nPASSED: Package validation succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
