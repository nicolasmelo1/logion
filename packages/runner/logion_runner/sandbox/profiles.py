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
#:
#: There is deliberately no module-level default digest. A build that
#: nothing produces is not a pin, and a constant here would let a job run
#: against whatever the runner happened to have. The coordinator names the
#: exact digest per job; ``make runner-image`` prints the one it built.
PROFILE_V0_NAME = "logion-runner-job"

#: Length of the hex body of a ``sha256:`` digest.
_DIGEST_HEX_LEN = 64

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
    digest = image.split("@", 1)[1]
    hex_body = digest.removeprefix("sha256:")
    if len(hex_body) != _DIGEST_HEX_LEN or not all(
        char in "0123456789abcdef" for char in hex_body
    ):
        raise ValueError(
            f"sandbox image digest is not a sha256 hex digest: {digest!r}"
        )
    if hex_body == "0" * _DIGEST_HEX_LEN:
        raise ValueError("sandbox image digest cannot be the zero placeholder")
    return image


def runnable_reference(image: str) -> str:
    """Return the reference the container runtime can actually resolve.

    ``name@sha256:<hex>`` is the contract the coordinator speaks, but that
    form only resolves for images carrying a *repository* digest, i.e. ones
    pulled from or pushed to a registry. A locally built image has none, so
    the runnable form is the bare content digest, which is the image's own
    config digest and identifies exactly the same bytes.
    """
    return image.split("@", 1)[1]
