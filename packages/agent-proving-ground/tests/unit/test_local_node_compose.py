"""Compose contract tests for the phase 15.14.1 local node.

The plan's required test: non-root users, read-only base filesystems,
dropped capabilities, no privileged mode/socket/host-home mounts,
separate volumes, separate secrets, and declared limits. These read
the compose file the operator actually runs, so a service that loses
one of those guarantees fails here before it fails a real run.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_PATH = (
    Path(__file__).resolve().parents[4]
    / "deploy"
    / "local-node"
    / "compose.yaml"
)


def _load() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _role_services(compose: dict) -> dict:
    return {
        name: service
        for name, service in compose["services"].items()
        if name in {"consumer", "auditor"}
    }


def test_both_roles_are_declared() -> None:
    compose = _load()
    assert {"consumer", "auditor"} <= set(compose["services"])


def test_roles_run_non_root_with_distinct_uids() -> None:
    compose = _load()
    uids = {
        name: str(service["user"])
        for name, service in _role_services(compose).items()
    }
    assert set(uids.values()) == {"10001:10001", "10002:10002"}
    assert all(uid.split(":")[0] != "0" for uid in uids.values())


def test_roles_have_read_only_filesystem_and_dropped_capabilities() -> None:
    compose = _load()
    for name, service in _role_services(compose).items():
        assert service.get("read_only") is True, name
        assert "ALL" in (service.get("cap_drop") or []), name
        assert "no-new-privileges:true" in (
            service.get("security_opt") or []
        ), name


def test_no_privileged_mode_socket_or_host_home_mounts() -> None:
    compose = _load()
    for name, service in _role_services(compose).items():
        assert service.get("privileged") is not True, name
        for mount in service.get("volumes") or []:
            source = mount.split(":")[0]
            assert not source.startswith("/"), (
                f"{name}: host bind mount forbidden: {mount}"
            )
            assert "docker.sock" not in mount, name
            assert not mount.startswith("/Users/"), name
            assert not mount.startswith("/home/"), name


def test_roles_use_separate_named_volumes() -> None:
    compose = _load()
    role_mounts: dict[str, set[str]] = {}
    for name, service in _role_services(compose).items():
        role_mounts[name] = {
            mount.split(":")[0] for mount in service.get("volumes") or []
        }
    assert role_mounts["consumer"].isdisjoint(role_mounts["auditor"])


def test_roles_use_separate_secrets() -> None:
    compose = _load()
    secrets = {
        name: set(service.get("secrets") or [])
        for name, service in _role_services(compose).items()
    }
    assert secrets["consumer"] == {
        "consumer_api_key",
        "consumer_codex_auth",
    }
    assert secrets["auditor"] == {
        "auditor_api_key",
        "auditor_codex_auth",
    }
    for secret_name, entry in compose["secrets"].items():
        # Secrets come from files outside the image, never baked in.
        assert "file" in entry, secret_name


def test_roles_declare_resource_limits() -> None:
    compose = _load()
    for name, service in _role_services(compose).items():
        limits = (
            service.get("deploy", {}).get("resources", {}).get("limits", {})
        )
        assert limits.get("cpus") is not None, name
        assert limits.get("memory") is not None, name
        assert limits.get("pids") is not None, name
        environment = service.get("environment", {})
        assert environment.get("ROLE_WALL_TIME_SECONDS") is not None, name
        command = service.get("command") or []
        assert "timeout --signal=TERM" in " ".join(command), name
        assert "ROLE_WALL_TIME_SECONDS" in " ".join(command), name


def test_roles_have_separate_codex_auth_secrets() -> None:
    compose = _load()
    for name, service in _role_services(compose).items():
        secrets = set(service.get("secrets") or [])
        assert f"{name}_codex_auth" in secrets
        assert f"{name}_api_key" in secrets
        assert f"{name}_codex_auth" in compose["secrets"]


def test_role_image_installs_pinned_codex_harness() -> None:
    dockerfile = COMPOSE_PATH.with_name("Dockerfile.role").read_text(
        encoding="utf-8"
    )
    assert "ARG CODEX_VERSION=" in dockerfile
    assert "@openai/codex@${CODEX_VERSION}" in dockerfile
    assert "codex-role" in dockerfile
    assert "mkdir -p /home/agent/.logion/spool /workspace/task" in dockerfile
    assert "/home/agent/.logion/spool" in dockerfile


def test_role_docs_exist() -> None:
    docs = COMPOSE_PATH.parents[2] / "docs" / "node" / "local-macos.md"
    assert docs.is_file()


def test_operator_surface_validates_and_provisions_prerequisites() -> None:
    script = COMPOSE_PATH.with_name("node.sh").read_text(encoding="utf-8")
    for required in (
        "validate_disk",
        "ensure_devrig",
        "validate_provider_auth",
        "provision_role_identity",
        'make -C "${WORKSPACE_ROOT}" dev-up',
        'make -C "${WORKSPACE_ROOT}" dev-api',
    ):
        assert required in script


def test_operator_reset_rotates_server_side() -> None:
    script = COMPOSE_PATH.with_name("node.sh").read_text(encoding="utf-8")
    assert "rotate_role_key" in script
    assert "/api-keys" in script
    reset_body = script.split("node_reset()", 1)[1]
    assert "node_compose down" not in reset_body
    assert 'node_compose stop "${role}"' in reset_body


def test_operator_supports_docker_and_podman() -> None:
    script = COMPOSE_PATH.with_name("node.sh").read_text(encoding="utf-8")
    docs = (
        COMPOSE_PATH.parents[2] / "docs" / "node" / "local-macos.md"
    ).read_text(encoding="utf-8")
    assert "CONTAINER_RUNTIME" in script
    assert "host.containers.internal" in script
    assert "Docker" in docs
    assert "Podman" in docs
