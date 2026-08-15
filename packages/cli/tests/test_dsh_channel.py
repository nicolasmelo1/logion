# SPDX-License-Identifier: MIT
"""dsh harness adapter, native-state reader, and acquisition channel.

The fixtures reproduce the layout dsh actually writes at the pinned
release: profiles live at ``$DSH_HOME/profiles/<name>``, a profile
declares its bundles in its own ``package.json`` under ``dsh.profile``,
and `dsh plugin` (which forwards to pnpm) installs them under the
profile's ``node_modules``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._harness.dsh import (
    SUPPORTED_DSH_VERSION,
    DshAdapter,
    UnsupportedDshVersionError,
    dsh_home_for,
    require_supported_dsh,
)
from cli.commands.resources._channels.dsh import DshChannelAdapter
from cli.commands.resources._dsh_reconciliation import discover_dsh_state
from cli.commands.resources._dsh_state import (
    UnsupportedDshStateError,
    read_profile,
)

REVISION = "a" * 40
OTHER_REVISION = "b" * 40


def _write_profile(
    dsh_home: Path,
    profile: str = "default",
    *,
    bundles: list[str] | None = None,
    dependencies: dict | None = None,
    profile_manifest: dict | None = None,
) -> Path:
    directory = dsh_home / "profiles" / profile
    directory.mkdir(parents=True, exist_ok=True)
    manifest = (
        profile_manifest
        if profile_manifest is not None
        else {
            "name": f"dsh-profile-{profile}",
            "dependencies": dependencies or {},
            "dsh": {"profile": {"bundles": bundles or []}},
        }
    )
    (directory / "package.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return directory


def _install_bundle(
    directory: Path,
    name: str,
    *,
    revision: str | None = REVISION,
    repository: str = "https://github.com/owner/plugin",
    dependencies: dict | None = None,
) -> Path:
    installed = directory / "node_modules" / Path(name)
    installed.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "name": name,
        "version": "1.0.0",
        "repository": repository,
        "dependencies": dependencies or {"@deepseek-ai/dsh-tools": "^0.1.0"},
        "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
    }
    if revision is not None:
        manifest["gitHead"] = revision
    (installed / "package.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return installed


def _plan(**native) -> dict:
    base = {
        "argv": [
            "dsh",
            "plugin",
            "--profile",
            "default",
            "add",
            f"github:owner/plugin#{REVISION}",
        ],
        "revision": REVISION,
        "tested_version": SUPPORTED_DSH_VERSION,
        "upstream_locator": "gh:owner/plugin",
        "content_digest": "c" * 64,
    }
    base.update(native)
    return {"native": base}


# ── native state reader ─────────────────────────────────────────────


def test_reads_bundles_declared_in_the_profile_package_json(
    tmp_path: Path,
) -> None:
    home = dsh_home_for(tmp_path)
    directory = _write_profile(home, bundles=["@owner/plugin"])
    _install_bundle(directory, "@owner/plugin")

    bundles = read_profile(home, "default")
    assert [bundle.name for bundle in bundles] == ["@owner/plugin"]
    assert bundles[0].revision == REVISION
    assert bundles[0].repository == "https://github.com/owner/plugin"
    assert bundles[0].declared["dependencies"] == ["@deepseek-ai/dsh-tools"]


@pytest.mark.parametrize(
    "manifest",
    [
        # A manifest that never declares dsh.profile is a different
        # format, not an empty profile.
        {"name": "p", "dependencies": {}},
        {"name": "p", "dsh": {}},
        {"name": "p", "dsh": {"profile": {"bundles": "not-a-list"}}},
    ],
)
def test_unknown_profile_format_fails_closed(
    tmp_path: Path, manifest: dict
) -> None:
    home = dsh_home_for(tmp_path)
    _write_profile(home, profile_manifest=manifest)
    with pytest.raises(UnsupportedDshStateError):
        read_profile(home, "default")


def test_missing_bundle_manifest_is_quarantined_not_guessed(
    tmp_path: Path,
) -> None:
    home = dsh_home_for(tmp_path)
    _write_profile(home, bundles=["@owner/absent"])
    bundles = read_profile(home, "default")
    assert bundles[0].unsupported
    assert bundles[0].revision == ""


@pytest.mark.parametrize("profile", ["..", "a/b", "", "."])
def test_traversal_profile_names_are_rejected(
    tmp_path: Path, profile: str
) -> None:
    with pytest.raises(UnsupportedDshStateError):
        read_profile(dsh_home_for(tmp_path), profile)


# ── reconciliation ──────────────────────────────────────────────────


def test_reconcile_reads_state_without_mutating_it(tmp_path: Path) -> None:
    home = dsh_home_for(tmp_path)
    directory = _write_profile(home, bundles=["@owner/plugin"])
    installed = _install_bundle(directory, "@owner/plugin")
    before = {
        path: path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }

    entries = discover_dsh_state(tmp_path)
    assert len(entries) == 1
    assert entries[0]["manager"] == "dsh"
    assert entries[0]["revision"] == REVISION
    assert entries[0]["source"] == "https://github.com/owner/plugin"
    assert entries[0]["path"] == str(installed)
    # Attribution is the server's job; the reader never invents a link.
    assert entries[0]["resource_version_id"] is None

    after = {
        path: path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert before == after


def test_reconcile_is_empty_without_a_harness_home(tmp_path: Path) -> None:
    assert discover_dsh_state(tmp_path) == []


def test_reconcile_reports_unknown_profile_state(tmp_path: Path) -> None:
    home = dsh_home_for(tmp_path)
    _write_profile(home, profile_manifest={"name": "p"})
    entries = discover_dsh_state(tmp_path)
    assert entries[0]["unsupported"]


# ── argv validation ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["dsh", "plugin", "add", "github:owner/plugin"],
        # A flag in the package position changes what pnpm does with it.
        ["dsh", "plugin", "--profile", "default", "add", "--force"],
        # Anything but `add` is a different, unvalidated operation.
        ["dsh", "plugin", "--profile", "default", "remove", "x"],
        # A traversal profile name would escape the scope's harness home.
        ["dsh", "plugin", "--profile", "..", "add", "github:owner/plugin"],
        # Extra arguments are not part of the tested invocation.
        ["dsh", "plugin", "--profile", "d", "add", "x", "--global"],
    ],
)
def test_rejects_argv_that_is_not_the_tested_invocation(
    argv: list[str],
) -> None:
    with pytest.raises(RuntimeError):
        DshChannelAdapter._validate_argv(argv, {"revision": REVISION})


def test_rejects_a_package_spec_not_pinned_to_the_planned_revision() -> None:
    argv = [
        "dsh",
        "plugin",
        "--profile",
        "default",
        "add",
        f"github:owner/plugin#{OTHER_REVISION}",
    ]
    with pytest.raises(RuntimeError, match="not pinned"):
        DshChannelAdapter._validate_argv(argv, {"revision": REVISION})


@pytest.mark.parametrize("revision", ["", "abc", "z" * 40])
def test_rejects_a_plan_without_an_immutable_revision(revision: str) -> None:
    argv = [
        "dsh",
        "plugin",
        "--profile",
        "default",
        "add",
        "github:owner/plugin",
    ]
    with pytest.raises(RuntimeError, match="exact commit or version"):
        DshChannelAdapter._validate_argv(argv, {"revision": revision})


# ── version pinning ─────────────────────────────────────────────────


def test_absent_manager_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr("cli._harness.dsh.detect_dsh_version", lambda *_: None)
    with pytest.raises(
        UnsupportedDshVersionError, match="resource_native_tool_unsupported"
    ):
        require_supported_dsh()


def test_untested_manager_version_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "cli._harness.dsh.detect_dsh_version", lambda *_: "9.9.9"
    )
    with pytest.raises(
        UnsupportedDshVersionError,
        match="resource_native_tool_version_unsupported",
    ):
        require_supported_dsh()


def test_acquire_refuses_an_untested_manager(
    tmp_path: Path, monkeypatch
) -> None:
    """An untested dsh must fail before anything is executed."""
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.require_supported_dsh",
        _raise_unsupported,
    )
    executed: list = []
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.run_argv",
        lambda *args, **_kwargs: executed.append(args),
    )
    with pytest.raises(RuntimeError):
        DshChannelAdapter().acquire(
            plan=_plan(), destination=tmp_path, scope_root=tmp_path
        )
    assert executed == []


def _raise_unsupported(*_args, **_kwargs):
    raise UnsupportedDshVersionError("resource_native_tool_unsupported: x")


# ── acquisition ─────────────────────────────────────────────────────


class _Completed:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = b""
        self.stderr = b""


def test_acquire_pins_dsh_home_to_the_scope_and_records_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    """The install must land in the scope's harness home, not the user's."""
    home = dsh_home_for(tmp_path)
    calls: list[dict] = []

    def fake_run(argv, *, cwd, env_overrides=None, **_kwargs):
        calls.append({
            "argv": argv,
            "cwd": cwd,
            "env": env_overrides,
        })
        directory = _write_profile(home, bundles=["@owner/plugin"])
        _install_bundle(directory, "@owner/plugin")
        return _Completed()

    monkeypatch.setattr(
        "cli._harness.dsh.detect_dsh_version",
        lambda *_: SUPPORTED_DSH_VERSION,
    )
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.run_argv", fake_run
    )

    outcome = DshChannelAdapter().acquire(
        plan=_plan(), destination=tmp_path, scope_root=tmp_path
    )

    assert calls[0]["env"] == {"DSH_HOME": str(home)}
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["argv"][0] == "dsh"
    evidence = outcome.native_evidence
    assert evidence["manager_name"] == "dsh"
    assert evidence["manager_version"] == SUPPORTED_DSH_VERSION
    assert evidence["immutable_revision"] == REVISION
    assert evidence["canonical_source"] == "https://github.com/owner/plugin"
    assert evidence["declared_capabilities"]["dependencies"] == [
        "@deepseek-ai/dsh-tools"
    ]
    assert outcome.verification == "source_revision"
    assert outcome.installed_paths == [
        str(home / "profiles/default/node_modules/@owner/plugin")[
            len(str(tmp_path)) + 1 :
        ]
    ]


def test_acquire_rejects_an_install_without_the_planned_revision(
    tmp_path: Path, monkeypatch
) -> None:
    """A bundle with no gitHead cannot prove what revision it is."""
    home = dsh_home_for(tmp_path)

    def fake_run(*_args, **_kwargs):
        directory = _write_profile(home, bundles=["@owner/plugin"])
        _install_bundle(directory, "@owner/plugin", revision=None)
        return _Completed()

    monkeypatch.setattr(
        "cli._harness.dsh.detect_dsh_version",
        lambda *_: SUPPORTED_DSH_VERSION,
    )
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.run_argv", fake_run
    )
    with pytest.raises(RuntimeError, match="no unique bundle"):
        DshChannelAdapter().acquire(
            plan=_plan(), destination=tmp_path, scope_root=tmp_path
        )


def test_acquire_rejects_a_revision_that_does_not_match_the_plan(
    tmp_path: Path, monkeypatch
) -> None:
    home = dsh_home_for(tmp_path)

    def fake_run(*_args, **_kwargs):
        directory = _write_profile(home, bundles=["@owner/plugin"])
        _install_bundle(directory, "@owner/plugin", revision=OTHER_REVISION)
        return _Completed()

    monkeypatch.setattr(
        "cli._harness.dsh.detect_dsh_version",
        lambda *_: SUPPORTED_DSH_VERSION,
    )
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.run_argv", fake_run
    )
    with pytest.raises(RuntimeError, match="no unique bundle"):
        DshChannelAdapter().acquire(
            plan=_plan(), destination=tmp_path, scope_root=tmp_path
        )


# ── scope isolation ─────────────────────────────────────────────────


def test_repo_scope_targets_the_repository_harness_home(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "xpto"
    (repo / ".git").mkdir(parents=True)
    adapter = DshAdapter(home_dir=tmp_path / "home", cwd=repo, repo_root=repo)
    targets = adapter.scope_targets("repo-root")
    assert targets[0].target_path == repo / ".dsh"


def test_user_scope_never_points_into_a_repository(tmp_path: Path) -> None:
    repo = tmp_path / "xpto"
    (repo / ".git").mkdir(parents=True)
    user_home = tmp_path / "home"
    adapter = DshAdapter(home_dir=user_home, cwd=repo, repo_root=repo)
    targets = adapter.scope_targets("user")
    assert targets[0].target_path == user_home / ".dsh"


def test_two_repositories_get_separate_harness_homes(
    tmp_path: Path,
) -> None:
    homes = []
    for name in ("xpto", "acme"):
        repo = tmp_path / name
        (repo / ".git").mkdir(parents=True)
        adapter = DshAdapter(
            home_dir=tmp_path / "home", cwd=repo, repo_root=repo
        )
        homes.append(adapter.scope_targets("repo-root")[0].target_path)
    assert homes[0] != homes[1]


def test_repo_scope_without_a_git_worktree_yields_nothing(
    tmp_path: Path,
) -> None:
    """No silent fallback to user scope outside a worktree."""
    adapter = DshAdapter(home_dir=tmp_path / "home", cwd=tmp_path)
    assert adapter.scope_targets("repo-root") == []


def test_adapter_declares_no_observation_capability() -> None:
    assert DshAdapter.observation == "unsupported"


# ── revision evidence ───────────────────────────────────────────────


def test_revision_comes_from_the_profile_spec_when_githead_is_absent(
    tmp_path: Path,
) -> None:
    """pnpm does not write gitHead, so the pinned spec is the evidence.

    Matching only on gitHead would fail closed on every real install.
    """
    home = dsh_home_for(tmp_path)
    directory = _write_profile(
        home,
        bundles=["@owner/plugin"],
        dependencies={
            "@owner/plugin": f"git+https://example.test/p.git#{REVISION}"
        },
    )
    _install_bundle(directory, "@owner/plugin", revision=None)

    bundle = read_profile(home, "default")[0]
    assert bundle.revision == REVISION
    assert bundle.spec.endswith(REVISION)


def test_a_movable_spec_fragment_is_not_a_revision(tmp_path: Path) -> None:
    """A branch or tag names something that can change under the pin."""
    home = dsh_home_for(tmp_path)
    directory = _write_profile(
        home,
        bundles=["@owner/plugin"],
        dependencies={"@owner/plugin": "git+https://example.test/p.git#main"},
    )
    _install_bundle(directory, "@owner/plugin", revision=None)
    assert read_profile(home, "default")[0].revision == ""


def test_githead_wins_over_the_spec_when_both_are_present(
    tmp_path: Path,
) -> None:
    home = dsh_home_for(tmp_path)
    directory = _write_profile(
        home,
        bundles=["@owner/plugin"],
        dependencies={
            "@owner/plugin": f"git+https://example.test/p.git#{OTHER_REVISION}"
        },
    )
    _install_bundle(directory, "@owner/plugin", revision=REVISION)
    assert read_profile(home, "default")[0].revision == REVISION


# ── npm-hosted bundles ──────────────────────────────────────────────

NPM_VERSION = "0.1.0"


def test_accepts_an_exact_npm_version_as_the_pin() -> None:
    """dsh's own base bundle ships from npm, so both pins are valid."""
    argv = [
        "dsh",
        "plugin",
        "--profile",
        "default",
        "add",
        f"@logionsh/dsh-plugin@{NPM_VERSION}",
    ]
    DshChannelAdapter._validate_argv(argv, {"revision": NPM_VERSION})


@pytest.mark.parametrize("pin", ["^0.1.0", "~0.1.0", "latest", "0.1"])
def test_rejects_a_resolvable_range_as_a_pin(pin: str) -> None:
    """A range lets the manager resolve to something uncatalogued."""
    argv = [
        "dsh",
        "plugin",
        "--profile",
        "default",
        "add",
        f"@logionsh/dsh-plugin@{pin}",
    ]
    with pytest.raises(RuntimeError, match="exact commit or version"):
        DshChannelAdapter._validate_argv(argv, {"revision": pin})


def test_an_npm_install_is_identified_by_its_resolved_version(
    tmp_path: Path, monkeypatch
) -> None:
    home = dsh_home_for(tmp_path)

    def fake_run(*_args, **_kwargs):
        directory = _write_profile(
            home,
            bundles=["@logionsh/dsh-plugin"],
            dependencies={"@logionsh/dsh-plugin": NPM_VERSION},
        )
        installed = _install_bundle(
            directory, "@logionsh/dsh-plugin", revision=None
        )
        manifest = json.loads(
            (installed / "package.json").read_text(encoding="utf-8")
        )
        manifest["version"] = NPM_VERSION
        (installed / "package.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return _Completed()

    monkeypatch.setattr(
        "cli._harness.dsh.detect_dsh_version",
        lambda *_: SUPPORTED_DSH_VERSION,
    )
    monkeypatch.setattr(
        "cli.commands.resources._channels.dsh.run_argv", fake_run
    )
    outcome = DshChannelAdapter().acquire(
        plan=_plan(
            argv=[
                "dsh",
                "plugin",
                "--profile",
                "default",
                "add",
                f"@logionsh/dsh-plugin@{NPM_VERSION}",
            ],
            revision=NPM_VERSION,
        ),
        destination=tmp_path,
        scope_root=tmp_path,
    )
    assert outcome.native_evidence["immutable_revision"] == ""
    assert outcome.installed_paths == [
        ".dsh/profiles/default/node_modules/@logionsh/dsh-plugin"
    ]
