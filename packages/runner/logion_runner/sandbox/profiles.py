"""Sandbox profile v0: image pinning for the container backend.

The coordinator names a sandbox profile in every lease. Profile v0
(``isolated-runner-v0``) pins the exact container image by digest. The
runner refuses to execute when the profile or digest is missing or
unknown, so no job ever starts on an unpinned image.
"""

from __future__ import annotations

#: Sandbox profile name the coordinator sends in ``sandbox_profile``.
PROFILE_V0 = "isolated-runner-v0"

#: Image pinned by digest. ``latest`` is forbidden by the profile; a
#: job's image reference is always ``name@sha256:<hex>``.
PROFILE_V0_NAME = "logion-runner-job"
PROFILE_V0_DIGEST = (
    "sha256:0000000000000000000000000000000000000000000000000000000000000000"
)
PROFILE_V0_IMAGE = f"{PROFILE_V0_NAME}@{PROFILE_V0_DIGEST}"

#: Human-readable contract the profile enforces (mirrored by the
#: DockerBackend flag mapping and the Compose runner service).
PROFILE_V0_PROPERTIES: dict[str, object] = {
    "read_only_root": True,
    "tmpfs": ["/workspace", "/tmp"],  # nosec B108 - container tmpfs
    "cap_drop": ["ALL"],
    "no_new_privileges": True,
    "non_root_uid": 10005,
    "network": "none",
    "memory_limit_bytes": 536870912,
    "pids_limit": 128,
    "payload_via_tmpfs_file": True,
    "output_dir": "/workspace/out",
}


def image_for_profile(profile: str, digest: str) -> str:
    """Return the pinned image reference for *profile*.

    ``digest`` is the coordinator's ``sandbox_profile_digest``. When it
    carries an explicit ``sha256:...`` value it overrides the built-in
    pin; an empty digest is accepted only for the local test backend's
    deterministic fixtures, so the default resolves to the built-in pin.
    """
    if profile != PROFILE_V0:
        raise ValueError(
            f"unknown sandbox profile: {profile!r} (expected {PROFILE_V0!r})"
        )
    if digest.startswith("sha256:"):
        return f"{PROFILE_V0_NAME}@{digest}"
    return PROFILE_V0_IMAGE
