# SPDX-License-Identifier: MIT
"""Copy installed skills into a coding agent's skill directory.

Logion's canonical install location is
``$LOGION_HOME/installed/<course-id>/<version-id>/``.  That keeps
Logion's lifecycle separate from the user's agent harness.  But agents
(Claude Code, Codex, OpenCode, Hermes, ...) load skills from their own
fixed directories, so without a synced copy the user has to wire the
two together manually after every install.

This module reads the skill name from the bundle's SKILL.md frontmatter
and offers to copy the installed skill.  The target directory is whatever the
user types — no auto-detection, no harness inference.  The known
conventions are listed in the prompt as examples only.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Shown only as examples in the prompt.  We do not infer or filter.
# Codex user scope moved to the cross-harness ~/.agents/skills;
# ~/.codex/skills is legacy and detected separately by the adapter.
EXAMPLE_AGENT_DIRS: tuple[tuple[str, str], ...] = (
    ("Claude Code", "~/.claude/skills"),
    ("Codex", "~/.agents/skills"),
    ("OpenCode", "~/.config/opencode/skills"),
    ("Hermes", "~/.hermes/skills"),
)


def read_skill_name(source_dir: Path) -> str | None:
    """Read ``name:`` from the bundle's SKILL.md frontmatter."""
    skill_md = source_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    block = text[3:end]
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            value = stripped[len("name:") :].strip().strip('"').strip("'")
            return value or None
    return None


def prompt_symlink_dir(
    skill_name: str,
    *,
    explicit_dir: str | None,
    no_symlink: bool,
) -> Path | None:
    """Decide where to copy the installed skill.

    Returns the resolved parent directory (which the copy will be
    placed inside) or ``None`` to skip.

    Resolution order:
      1. ``--no-symlink`` → None.
      2. ``--symlink-dir PATH`` → PATH (no prompt).
      3. Non-interactive (stdin not a TTY) → None.
      4. Otherwise prompt: y/n, then a free-form path.
    """
    if no_symlink:
        return None
    if explicit_dir:
        return Path(explicit_dir).expanduser()
    if not sys.stdin.isatty():
        return None

    sys.stdout.write(
        f"\nCopy skill '{skill_name}' into a coding-agent skill dir? [y/N]: "
    )
    sys.stdout.flush()
    try:
        raw = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\n")
        return None
    if raw not in ("y", "yes"):
        return None

    sys.stdout.write("Target directory for the skill copy. Examples:\n")
    for label, path in EXAMPLE_AGENT_DIRS:
        sys.stdout.write(f"  {label:14}  {path}\n")
    sys.stdout.write("Path: ")
    sys.stdout.flush()
    try:
        raw_path = input().strip()
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\n")
        return None
    if not raw_path:
        return None
    return Path(raw_path).expanduser()


def create_symlink(
    parent_dir: Path, skill_name: str, install_dest: Path
) -> Path:
    """Copy ``install_dest`` into ``parent_dir / skill_name``.

    Replaces any prior symlink, file, or directory at the target.
    Creates ``parent_dir`` if missing.  Returns the resulting copy path.

    The function name is kept for compatibility with older internal
    callers; the behavior is intentionally a real copy because some
    harnesses do not load skills through symlinks reliably.
    """
    parent_dir.mkdir(parents=True, exist_ok=True)
    target = parent_dir / skill_name
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    shutil.copytree(install_dest, target, symlinks=False)
    return target


def resolve_symlink_intent(
    source_dir: Path, args
) -> tuple[str | None, Path | None]:
    """Read the skill name and prompt for skill-copy target up-front.

    Returns ``(skill_name, symlink_parent)``.  Either or both may be None
    if the bundle has no readable name or the user declined.
    """
    skill_name = read_skill_name(source_dir)
    if not skill_name:
        return None, None
    symlink_parent = prompt_symlink_dir(
        skill_name,
        explicit_dir=getattr(args, "symlink_dir", None),
        no_symlink=getattr(args, "dry_run", False)
        or getattr(args, "no_symlink", True),
    )
    return skill_name, symlink_parent


def apply_post_install_symlink(
    symlink_parent: Path, skill_name: str, dest: Path
) -> Path | None:
    """Sync the skill copy and surface errors as warnings (non-fatal).

    Returns the copy path on success, or None if the copy failed, so
    callers can record only copies that actually exist on disk.
    """
    try:
        target = create_symlink(symlink_parent, skill_name, dest)
    except OSError as exc:
        sys.stderr.write(
            f"WARN: skill copy failed ({exc}); canonical install is fine\n"
        )
        return None
    sys.stdout.write(f"Copied: {dest} -> {target}\n")
    return target
