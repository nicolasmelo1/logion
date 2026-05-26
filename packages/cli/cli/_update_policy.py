"""Update policy gates for ``logion skills update``.

Compares the locally installed manifest against a candidate remote
manifest and decides whether the upgrade can be applied silently or
must require explicit user approval.

The plan calls out a closed set of manifest fields that, if they
change between local and remote, require approval:

- ``required_tools`` — the skill claims a new tool capability
- ``permissions`` — declared OS / network / credential scopes
- ``env_vars`` — environment variables the skill reads
- ``execution_policy`` — auto-run vs. approval-required, danger flags

Pricing is *not* gated here: the entitlement model grants the buyer
ongoing access to the course (all versions) once purchased, so a
seller raising the list price does not re-bill an existing user.  We
surface a price change as an informational notice (``reasons``) but
do not force approval on its account.

``evaluate_update`` layers ``verify_installed_content`` on top of the
base policy: a locally modified install always blocks silent
overwrite, even when the manifest diff alone would have been safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cli._local_state import verify_installed_content

# Fields that force ``requires_approval`` when local ≠ remote.
GATED_FIELDS: tuple[str, ...] = (
    "required_tools",
    "permissions",
    "env_vars",
    "execution_policy",
)

# Fields surfaced as notices but that do NOT force approval.
NOTICE_FIELDS: tuple[str, ...] = (
    "price_cents_at_install",
    "currency",
)


@dataclass
class UpdatePolicyResult:
    """Outcome of comparing a local manifest to a remote manifest."""

    applicable: bool = False
    requires_approval: bool = False
    blocks_silent_overwrite: bool = False
    reasons: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applicable": self.applicable,
            "requires_approval": self.requires_approval,
            "blocks_silent_overwrite": self.blocks_silent_overwrite,
            "reasons": list(self.reasons),
            "notices": list(self.notices),
            "changed_fields": list(self.changed_fields),
        }


def _normalize(value: Any) -> Any:
    """Make values comparable: lists become sorted tuples; dicts sort keys."""
    if isinstance(value, list):
        return tuple(sorted((_normalize(v) for v in value), key=repr))
    if isinstance(value, dict):
        return tuple(sorted((k, _normalize(v)) for k, v in value.items()))
    return value


def check_update_policy(
    local_manifest: dict[str, Any],
    remote_manifest: dict[str, Any],
) -> UpdatePolicyResult:
    """Diff gated manifest fields and return an :class:`UpdatePolicyResult`.

    The result is *only* about the manifest diff; it does not look at
    on-disk content.  Use :func:`evaluate_update` to add the
    user-modification check.
    """
    result = UpdatePolicyResult()

    local_version = local_manifest.get("version_id")
    remote_version = remote_manifest.get("version_id")
    if remote_version and remote_version != local_version:
        result.applicable = True

    content_changed = local_manifest.get(
        "content_sha256"
    ) != remote_manifest.get("content_sha256")
    if content_changed:
        result.applicable = True

    for field_name in GATED_FIELDS:
        if _normalize(local_manifest.get(field_name)) != _normalize(
            remote_manifest.get(field_name)
        ):
            result.changed_fields.append(field_name)
            result.requires_approval = True
            result.reasons.append(
                f"{field_name} changed between installed and remote manifest"
            )

    for field_name in NOTICE_FIELDS:
        if _normalize(local_manifest.get(field_name)) != _normalize(
            remote_manifest.get(field_name)
        ):
            result.notices.append(
                f"{field_name} changed (informational; existing entitlement "
                "is not re-billed)"
            )

    return result


def evaluate_update(
    course_id: str,
    version_id: str,
    remote_manifest: dict[str, Any],
    local_manifest: dict[str, Any],
    home: Path | None = None,
) -> UpdatePolicyResult:
    """Combine :func:`check_update_policy` with content verification.

    If the installed files have been modified locally (i.e.
    ``verify_installed_content`` reports ``user_modified=True``), the
    update is forced to require approval *and*
    ``blocks_silent_overwrite`` is set, regardless of how clean the
    manifest diff was.
    """
    policy = check_update_policy(local_manifest, remote_manifest)

    verification = verify_installed_content(course_id, version_id, home)
    if verification["user_modified"]:
        policy.requires_approval = True
        policy.blocks_silent_overwrite = True
        policy.reasons.append(
            "installed content differs from manifest hash "
            "(user modification detected)"
        )

    return policy
