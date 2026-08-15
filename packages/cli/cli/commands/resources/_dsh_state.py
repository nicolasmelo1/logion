# SPDX-License-Identifier: MIT
"""Read DeepSeek Harness profile state without invoking the manager.

dsh keeps profiles at ``$DSH_HOME/profiles/<name>``. A profile declares
itself in its own ``package.json`` under a ``dsh`` key: ``dsh.profile``
lists the bundles it stacks, and each installed bundle declares
``dsh.bundle`` in its own manifest. `dsh plugin` forwards to pnpm, so the
installed trees live under the profile's ``node_modules``.

Everything read here is untrusted input: an unknown shape is quarantined
with a reason rather than guessed at, because a guess would mint an
attribution Logion cannot stand behind.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The profile manifest shape this reader was recorded against. A profile
#: that declares a different one is quarantined, never interpreted.
SUPPORTED_PROFILE_KEYS = ("dsh", "profile", "bundles")

_REVISION_RE = re.compile(r"[0-9a-f]{40}")
_PROFILE_NAME_RE = re.compile(r"(?!\.+$)[a-zA-Z0-9._-]{1,64}")


class UnsupportedDshStateError(RuntimeError):
    """Raised when dsh state is absent or in an unrecognised format."""


@dataclass(frozen=True)
class DshBundle:
    """One bundle a dsh profile declares and pnpm installed."""

    name: str
    profile: str
    path: Path
    revision: str = ""
    repository: str = ""
    version: str = ""
    unsupported: str = ""
    declared: dict[str, Any] = field(default_factory=dict)


def profiles_root(dsh_home: Path) -> Path:
    """Return the directory holding every profile of a harness home."""
    return dsh_home / "profiles"


def valid_profile_name(name: str) -> bool:
    """Reject anything that is not a flat directory token."""
    return bool(_PROFILE_NAME_RE.fullmatch(name))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnsupportedDshStateError(
            f"unreadable dsh manifest at {path.name}"
        ) from exc


def _declared_bundles(manifest: dict[str, Any]) -> list[str]:
    """Return ``dsh.profile.bundles`` or fail closed on any other shape."""
    dsh = manifest.get("dsh")
    if not isinstance(dsh, dict):
        raise UnsupportedDshStateError("profile manifest has no dsh key")
    profile = dsh.get("profile")
    if not isinstance(profile, dict):
        raise UnsupportedDshStateError("profile manifest has no dsh.profile")
    bundles = profile.get("bundles")
    if not isinstance(bundles, list) or not all(
        isinstance(name, str) for name in bundles
    ):
        raise UnsupportedDshStateError("dsh.profile.bundles is not a list")
    return list(bundles)


def _declared_capabilities(manifest: dict[str, Any]) -> dict[str, Any]:
    """Collect what the publisher declares — never what Logion verified."""
    dependencies = manifest.get("dependencies")
    peer = manifest.get("peerDependencies")
    raw_dsh = manifest.get("dsh")
    dsh: dict[str, Any] = raw_dsh if isinstance(raw_dsh, dict) else {}
    raw_bundle = dsh.get("bundle")
    bundle: dict[str, Any] = raw_bundle if isinstance(raw_bundle, dict) else {}
    return {
        "dependencies": sorted(dependencies)
        if isinstance(dependencies, dict)
        else [],
        "peer_dependencies": sorted(peer) if isinstance(peer, dict) else [],
        "patch": str(bundle.get("patch") or ""),
    }


def read_profile(dsh_home: Path, profile: str) -> list[DshBundle]:
    """Read one profile's declared bundles and their installed manifests."""
    if not valid_profile_name(profile):
        raise UnsupportedDshStateError(f"invalid dsh profile name {profile!r}")
    directory = profiles_root(dsh_home) / profile
    manifest = _read_json(directory / "package.json")
    if not isinstance(manifest, dict):
        raise UnsupportedDshStateError("profile manifest is not an object")

    results: list[DshBundle] = []
    for name in _declared_bundles(manifest):
        installed_dir = directory / "node_modules" / Path(name)
        installed_manifest = installed_dir / "package.json"
        try:
            installed = _read_json(installed_manifest)
        except UnsupportedDshStateError as exc:
            results.append(
                DshBundle(
                    name=name,
                    profile=profile,
                    path=installed_dir,
                    unsupported=str(exc),
                )
            )
            continue
        if not isinstance(installed, dict):
            results.append(
                DshBundle(
                    name=name,
                    profile=profile,
                    path=installed_dir,
                    unsupported="bundle manifest is not an object",
                )
            )
            continue
        revision = str(installed.get("gitHead") or "").lower()
        results.append(
            DshBundle(
                name=name,
                profile=profile,
                path=installed_dir,
                revision=revision if _REVISION_RE.fullmatch(revision) else "",
                repository=_repository_uri(installed.get("repository")),
                version=str(installed.get("version") or ""),
                declared=_declared_capabilities(installed),
            )
        )
    return results


def read_all_profiles(dsh_home: Path) -> list[DshBundle]:
    """Read every profile of a harness home, quarantining bad ones."""
    root = profiles_root(dsh_home)
    if not root.is_dir():
        return []
    results: list[DshBundle] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        try:
            results.extend(read_profile(dsh_home, directory.name))
        except UnsupportedDshStateError as exc:
            results.append(
                DshBundle(
                    name=directory.name,
                    profile=directory.name,
                    path=directory,
                    unsupported=str(exc),
                )
            )
    return results


def _repository_uri(repository: Any) -> str:
    """Normalise npm's two `repository` shapes into one string."""
    if isinstance(repository, str):
        return repository
    if isinstance(repository, dict):
        return str(repository.get("url") or "")
    return ""
