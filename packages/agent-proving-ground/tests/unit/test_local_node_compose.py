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
    assert secrets["consumer"] == {"consumer_api_key"}
    assert secrets["auditor"] == {"auditor_api_key"}
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


def test_role_docs_exist() -> None:
    docs = COMPOSE_PATH.parents[2] / "docs" / "node" / "local-macos.md"
    assert docs.is_file()
