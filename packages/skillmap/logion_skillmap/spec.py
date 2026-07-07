"""Agent Skills spec (agentskills.io) frontmatter validation."""

from __future__ import annotations

import re

from .models import ReviewFlag

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill_frontmatter(
    name: str,
    description: str | None,
    parent_dir: str,
    *,
    license_: str | None = None,
    compatibility: str | None = None,
    metadata: dict[str, str] | None = None,
    allowed_tools: str | None = None,
) -> list[ReviewFlag]:
    """Validate Agent Skills spec frontmatter fields.

    Returns one :class:`ReviewFlag` per violation with code
    ``spec_nonconformant:<rule>``.
    """
    flags: list[ReviewFlag] = []
    path = parent_dir

    # name: 1-64 chars, must match pattern and parent dir
    if len(name) < 1 or len(name) > 64:
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:name_length",
                path=path,
                message=f"name must be 1-64 chars, got {len(name)}",
            )
        )
    if not _NAME_RE.match(name):
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:name_format",
                path=path,
                message=f"name must match {_NAME_RE.pattern!r}, got {name!r}",
            )
        )
    dir_name = parent_dir.rstrip("/").rsplit("/", 1)[-1]
    if name != dir_name:
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:name_mismatch",
                path=path,
                message=f"name {name!r} must equal parent "
                f"directory name {dir_name!r}",
            )
        )

    # description: if present, 1-1024 chars non-empty
    if description is not None and (
        len(description) < 1 or len(description) > 1024
    ):
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:description_length",
                path=path,
                message=f"description must be 1-1024 chars, "
                f"got {len(description)}",
            )
        )

    # license: ≤500 chars if present
    if license_ is not None and len(license_) > 500:
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:license_length",
                path=path,
                message=f"license must be ≤500 chars, got {len(license_)}",
            )
        )

    # compatibility: ≤500 chars if present
    if compatibility is not None and len(compatibility) > 500:
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:compatibility_length",
                path=path,
                message=f"compatibility must be ≤500 chars, "
                f"got {len(compatibility)}",
            )
        )

    # metadata: str→str map if present
    if metadata is not None and not isinstance(metadata, dict):
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:metadata_type",
                path=path,
                message="metadata must be a string→string map",
            )
        )
    elif metadata is not None:
        for k, v in metadata.items():
            if not isinstance(k, str) or not isinstance(v, str):
                flags.append(
                    ReviewFlag(
                        code="spec_nonconformant:metadata_type",
                        path=path,
                        message=f"metadata key/value must be "
                        f"strings, got "
                        f"{type(k).__name__}"
                        f"→{type(v).__name__}",
                    )
                )
                break

    # allowed-tools: string if present
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        flags.append(
            ReviewFlag(
                code="spec_nonconformant:allowed_tools_type",
                path=path,
                message=f"allowed-tools must be a string, "
                f"got {type(allowed_tools).__name__}",
            )
        )

    return flags
