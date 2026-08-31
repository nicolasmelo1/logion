"""Sandbox profile v0: image pinning for the container backend.

The coordinator names a sandbox profile in every lease. Profile v0
(``isolated-runner-v0``) pins the exact container image by digest. The
runner refuses to execute when the profile or digest is missing or
unknown, so no job ever starts on an unpinned image.
"""

from __future__ import annotations

from logion_runner.job import SandboxProfile

#: Sandbox profile name the coordinator sends in ``sandbox_profile``.
PROFILE_V0 = "isolated-runner-v0"

#: Image pinned by digest. ``latest`` is forbidden by the profile; a
#: job's image reference is always ``name@sha256:<hex>``.
PROFILE_V0_NAME = "logion-runner-job"
# Digest of the reproducible Dockerfile.runner build published with this
# package. A zero digest is deliberately not a valid fallback.
PROFILE_V0_DIGEST = (
    "sha256:a5c4b5d89ccc9104181d87f2d84b61f0c0e06c7637fb1bc177ebd5eef4fd8296"
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


def profile_name(profile: SandboxProfile) -> str:
    """Return the canonical profile name for a coordinator profile object."""
    runtime = str(profile.get("runtime", ""))
    image = str(profile.get("image", ""))
    prefix = f"{PROFILE_V0_NAME}@sha256:"
    if runtime == "container" and image.startswith(prefix):
        return PROFILE_V0
    raise ValueError(f"unknown sandbox profile object: {profile!r}")


def image_for_profile(profile: SandboxProfile) -> str:
    """Return the pinned image reference declared by *profile*.

    The coordinator sends the full sandbox profile object. The runner executes
    only the exact digest-pinned image declared there and refuses unpinned or
    missing image fields.
    """
    runtime = str(profile.get("runtime", ""))
    image = str(profile.get("image", ""))
    if runtime != "container":
        raise ValueError(
            f"unknown sandbox runtime: {runtime!r} (expected 'container')"
        )
    if not image.startswith(f"{PROFILE_V0_NAME}@sha256:"):
        raise ValueError(
            "sandbox image must be pinned as "
            f"{PROFILE_V0_NAME}@sha256:..., got {image!r}"
        )
    if image.endswith("@sha256:" + "0" * 64):
        raise ValueError("sandbox image digest cannot be the zero placeholder")
    return image
