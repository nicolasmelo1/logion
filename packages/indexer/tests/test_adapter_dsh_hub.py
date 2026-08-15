"""Tests for the dsh hub adapter: bundle detection and revision pinning."""

from __future__ import annotations

import json

import pytest

from logion_indexer.adapters.dsh_hub import DshHubAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

OWNER = "dsh-external"
REPO = "hub"
REVISION = "a" * 40
OTHER_REVISION = "b" * 40

_HEAD_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/commits/HEAD"


def _tree_url(revision: str) -> str:
    return (
        f"https://api.github.com/repos/{OWNER}/{REPO}"
        f"/git/trees/{revision}?recursive=1"
    )


def _raw_url(revision: str, path: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{revision}/{path}"
    )


def _json(payload: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode("utf-8"))


def _bundle_manifest(**overrides) -> dict:
    manifest = {
        "name": "dsh-hello-plugin",
        "description": "A hello plugin",
        "license": "MIT",
        "dependencies": {"@deepseek-ai/dsh-tools": "^0.1.0"},
        "peerDependencies": {"cordis": "^3"},
        "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
    }
    manifest.update(overrides)
    return manifest


def _transport(
    *,
    revision: str = REVISION,
    paths: list[str] | None = None,
    manifests: dict[str, object] | None = None,
) -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(_HEAD_URL, _json({"sha": revision}))
    tree_paths = (
        paths if paths is not None else ["packages/hello/package.json"]
    )
    transport.set_response(
        _tree_url(revision),
        _json({"tree": [{"path": path} for path in tree_paths]}),
    )
    for path, manifest in (manifests or {}).items():
        transport.set_response(_raw_url(revision, path), _json(manifest))
    return transport


def test_discovers_a_bundle_pinned_to_the_resolved_revision() -> None:
    path = "packages/hello/package.json"
    adapter = DshHubAdapter(_transport(manifests={path: _bundle_manifest()}))
    results = list(adapter.discover(f"{OWNER}/{REPO}"))

    assert len(results) == 1
    resource = results[0]
    assert resource.resource_type == "plugin"
    assert resource.canonical_uri == f"gh:{OWNER}/{REPO}#packages/hello"
    assert resource.source_commit == REVISION
    assert resource.license_spdx == "MIT"
    assert resource.title == "dsh-hello-plugin"


def test_manifests_are_read_at_the_pinned_revision_not_head() -> None:
    """Reading at a mutable ref could describe a different tree."""
    path = "packages/hello/package.json"
    transport = _transport(manifests={path: _bundle_manifest()})
    # A manifest only reachable through the mutable ref must not be used.
    transport.set_response(
        _raw_url("HEAD", path), _json(_bundle_manifest(name="wrong"))
    )
    results = list(DshHubAdapter(transport).discover(f"{OWNER}/{REPO}"))
    assert results[0].title == "dsh-hello-plugin"


def test_records_publisher_declared_dependencies_as_claims() -> None:
    path = "packages/hello/package.json"
    adapter = DshHubAdapter(_transport(manifests={path: _bundle_manifest()}))
    declared = next(iter(adapter.discover(f"{OWNER}/{REPO}")))
    assert declared.declared_capabilities == {
        "tools": ["@deepseek-ai/dsh-tools", "cordis"],
        "patch": "./cordis.patch.yml",
    }
    # Declared capabilities never enter the validated package map.
    assert declared.inferred_map is None


@pytest.mark.parametrize(
    "manifest",
    [
        {"name": "not-a-bundle"},
        {"name": "x", "dsh": {}},
        {"name": "x", "dsh": {"bundle": {}}},
        {"name": "x", "dsh": {"bundle": {"patch": 1}}},
    ],
)
def test_a_package_without_dsh_bundle_is_not_a_plugin(manifest: dict) -> None:
    path = "packages/hello/package.json"
    adapter = DshHubAdapter(_transport(manifests={path: manifest}))
    assert list(adapter.discover(f"{OWNER}/{REPO}")) == []


def test_unreadable_manifest_is_skipped_not_guessed() -> None:
    transport = _transport()
    transport.set_response(
        _raw_url(REVISION, "packages/hello/package.json"),
        HttpResponse(200, b"{not json"),
    )
    assert list(DshHubAdapter(transport).discover(f"{OWNER}/{REPO}")) == []


def test_a_repository_without_an_immutable_revision_fails_closed() -> None:
    transport = FakeTransport()
    transport.set_response(_HEAD_URL, _json({"sha": "short"}))
    with pytest.raises(TypeError):
        list(DshHubAdapter(transport).discover(f"{OWNER}/{REPO}"))


def test_a_failed_revision_lookup_fails_closed() -> None:
    transport = FakeTransport()
    transport.set_response(_HEAD_URL, HttpResponse(404, b"{}"))
    with pytest.raises(RuntimeError, match="revision lookup"):
        list(DshHubAdapter(transport).discover(f"{OWNER}/{REPO}"))


def test_limit_caps_the_number_of_bundles() -> None:
    paths = [f"packages/p{i}/package.json" for i in range(3)]
    adapter = DshHubAdapter(
        _transport(
            paths=paths,
            manifests={path: _bundle_manifest() for path in paths},
        )
    )
    assert len(list(adapter.discover(f"{OWNER}/{REPO}", limit=2))) == 2


@pytest.mark.parametrize("target", ["no-slash", ""])
def test_requires_an_owner_repository_target(target: str) -> None:
    with pytest.raises(ValueError, match="owner/repository"):
        list(DshHubAdapter(FakeTransport()).discover(target))


def test_only_repo_mode_is_supported() -> None:
    with pytest.raises(ValueError, match="owner/repository"):
        list(
            DshHubAdapter(FakeTransport()).discover(
                f"{OWNER}/{REPO}", mode="topic"
            )
        )


def test_a_root_manifest_has_no_subpath_fragment() -> None:
    adapter = DshHubAdapter(
        _transport(
            paths=["package.json"],
            manifests={"package.json": _bundle_manifest()},
        )
    )
    resource = next(iter(adapter.discover(f"{OWNER}/{REPO}")))
    assert resource.canonical_uri == f"gh:{OWNER}/{REPO}"


def test_a_path_merely_ending_in_package_json_is_not_a_manifest() -> None:
    """`my-package.json` is a different file, not a manifest."""
    adapter = DshHubAdapter(
        _transport(
            paths=["docs/my-package.json"],
            manifests={"docs/my-package.json": _bundle_manifest()},
        )
    )
    assert list(adapter.discover(f"{OWNER}/{REPO}")) == []
