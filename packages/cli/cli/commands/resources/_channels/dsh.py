# SPDX-License-Identifier: MIT
"""Delegated DeepSeek Harness plugin acquisition channel."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cli._harness.dsh import (
    DSH_HOME_ENV,
    UnsupportedDshVersionError,
    dsh_home_for,
    require_supported_dsh,
)

from .._dsh_state import (
    DshBundle,
    UnsupportedDshStateError,
    read_profile,
    valid_profile_name,
)
from .base import AcquisitionOutcome, ChannelAdapter, run_argv

#: The two immutable pins a dsh distribution can carry: an exact Git
#: commit for a repository-hosted bundle, or an exact npm version for a
#: registry-hosted one (dsh's own base bundle ships that way).
_GIT_REVISION = re.compile(r"[0-9a-f]{40}")
_NPM_VERSION = re.compile(
    r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)


def _is_immutable_pin(value: str) -> bool:
    return bool(
        _GIT_REVISION.fullmatch(value) or _NPM_VERSION.fullmatch(value)
    )


#: `dsh plugin --profile NAME add SPEC` — the only form this channel runs.
_ARGV_PREFIX = ("dsh", "plugin", "--profile")
_ARGV_LENGTH = 6


class DshChannelAdapter(ChannelAdapter):
    """Use dsh's profile plugin manager and read its native state."""

    channel = "dsh"

    def acquire(
        self, *, plan: dict[str, Any], destination: Path, scope_root: Path
    ) -> AcquisitionOutcome:
        del destination
        native = plan.get("native") or {}
        argv = [str(value) for value in native.get("argv") or []]
        self._validate_argv(argv, native)
        try:
            manager_version = require_supported_dsh()
        except UnsupportedDshVersionError as exc:
            raise RuntimeError(str(exc)) from exc

        profile = argv[3]
        dsh_home = dsh_home_for(scope_root)
        # dsh resolves profiles from $DSH_HOME. Without this override the
        # install lands in the operator's own harness home, which is a
        # different scope than the one Logion planned and recorded.
        result = run_argv(
            argv,
            cwd=scope_root,
            env_overrides={DSH_HOME_ENV: str(dsh_home)},
            timeout_seconds=900,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout)[:500].decode(
                errors="replace"
            )
            raise RuntimeError(f"dsh plugin acquisition failed: {detail}")

        bundle = self._installed_bundle(dsh_home, profile, native)
        return AcquisitionOutcome(
            installed_paths=[str(bundle.path.relative_to(scope_root))],
            native_evidence={
                "schema_version": 1,
                "manager_name": "dsh",
                "manager_version": manager_version,
                "receipt_id": bundle.name,
                "canonical_source": bundle.repository
                or str(native.get("upstream_locator") or ""),
                "immutable_revision": bundle.revision,
                "content_digest": str(native.get("content_digest") or ""),
                "declared_capabilities": bundle.declared,
            },
            verification="source_revision",
            notes=["declared capabilities are publisher claims, not verified"],
        )

    @staticmethod
    def _validate_argv(argv: list[str], native: dict[str, Any]) -> None:
        if (
            len(argv) != _ARGV_LENGTH
            or tuple(argv[:3]) != _ARGV_PREFIX
            or argv[4] != "add"
        ):
            raise RuntimeError(
                "resource_native_tool_unsupported: dsh acquisition requires "
                "`plugin --profile NAME add PACKAGE`"
            )
        if not valid_profile_name(argv[3]):
            raise RuntimeError(
                "resource_native_tool_unsupported: invalid dsh profile name"
            )
        # A flag in the package position would change what pnpm does with
        # everything after it, so only a plain spec is accepted.
        if not argv[5] or argv[5].startswith("-"):
            raise RuntimeError(
                "resource_native_tool_unsupported: invalid dsh package spec"
            )
        revision = str(native.get("revision") or "")
        if not _is_immutable_pin(revision):
            raise RuntimeError(
                "dsh distribution requires an exact commit or version pin"
            )
        if revision not in argv[5]:
            raise RuntimeError(
                "dsh package spec is not pinned to the planned revision"
            )

    @staticmethod
    def _installed_bundle(
        dsh_home: Path, profile: str, native: dict[str, Any]
    ) -> DshBundle:
        """Find the one installed bundle at the planned revision."""
        try:
            bundles = read_profile(dsh_home, profile)
        except UnsupportedDshStateError as exc:
            raise RuntimeError(
                f"unsupported dsh profile state: {exc}"
            ) from exc

        expected = str(native.get("revision") or "").lower()
        # Identity is the immutable pin, never the package name: two
        # bundles can share a name and a name is not evidence of what was
        # installed. A Git bundle proves it with its revision, an npm one
        # with the exact version the manager resolved.
        matches = [
            bundle
            for bundle in bundles
            if expected in {bundle.revision, bundle.version.lower()}
            and (bundle.revision or bundle.version)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "dsh profile state has no unique bundle at the planned "
                f"pin (found {len(matches)})"
            )
        return matches[0]
