"""Unit tests for the phase 15.14.1 sandbox assertions and queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.files import (
    InstallScopedToRepositoryAssertion,
    RoleCleanupCompleteAssertion,
    SandboxCrossVolumeCanaryUnreadableAssertion,
    SandboxRealHarnessUsesLogionAssertion,
    SandboxRoleResourceLimitsEnforcedAssertion,
    SandboxRolesRunNonRootAssertion,
)
from agent_proving_ground.scenarios.loader import load_scenario


def _identity_manifest() -> dict:
    return {
        "roles": {
            "consumer": {
                "uid": 10001,
                "expected_uid": 10001,
                "home_writable": True,
                "user": "agent",
                "limits": {
                    "cpus": 1.0,
                    "memory_bytes": 1610612736,
                    "pids": 256,
                    "wall_time_seconds": 3600,
                    "wall_time_enforced": True,
                },
            },
            "auditor": {
                "uid": 10002,
                "expected_uid": 10002,
                "home_writable": True,
                "user": "agent",
                "limits": {
                    "cpus": 1.0,
                    "memory_bytes": 1610612736,
                    "pids": 256,
                    "wall_time_seconds": 3600,
                    "wall_time_enforced": True,
                },
            },
        }
    }


def _make_ctx(tmp_path: Path) -> AssertionContext:
    class _FakeApi:
        name = "fake"

    class _FakeWorld:
        data: ClassVar[dict] = {}

    return AssertionContext(
        scenario_name="phase_15_14_1_local_multi_agent_node",
        phase_id="test",
        world=_FakeWorld(),
        api=_FakeApi(),
        artifacts_dir=tmp_path,
        timeline=None,
    )


def _write_manifest(tmp_path: Path, relative: str, payload: dict) -> str:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload))
    return relative


async def _evaluate(assertion, tmp_path: Path, payload: dict, params=None):
    relative = _write_manifest(tmp_path, "evidence/manifest.json", payload)
    ctx = _make_ctx(tmp_path)
    return await assertion.evaluate(
        ctx, {"manifest": relative, **(params or {})}
    )


class TestRolesRunNonRoot:
    async def test_passes_on_distinct_non_root_uids(self, tmp_path):
        outcome = await _evaluate(
            SandboxRolesRunNonRootAssertion(),
            tmp_path,
            _identity_manifest(),
        )
        assert outcome.status == "passed"

    async def test_fails_when_a_role_is_root(self, tmp_path):
        payload = _identity_manifest()
        payload["roles"]["auditor"]["uid"] = 0
        outcome = await _evaluate(
            SandboxRolesRunNonRootAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        assert "uid=0" in outcome.message

    async def test_fails_when_uid_drifts_from_declaration(self, tmp_path):
        payload = _identity_manifest()
        payload["roles"]["consumer"]["uid"] = 10002
        outcome = await _evaluate(
            SandboxRolesRunNonRootAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"

    async def test_fails_when_role_home_is_not_writable(self, tmp_path):
        payload = _identity_manifest()
        payload["roles"]["auditor"]["home_writable"] = False
        outcome = await _evaluate(
            SandboxRolesRunNonRootAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        assert "home-not-writable" in outcome.message


class TestResourceLimits:
    async def test_passes_when_limits_declared(self, tmp_path):
        outcome = await _evaluate(
            SandboxRoleResourceLimitsEnforcedAssertion(),
            tmp_path,
            _identity_manifest(),
        )
        assert outcome.status == "passed"

    async def test_fails_when_a_limit_is_missing(self, tmp_path):
        payload = _identity_manifest()
        payload["roles"]["consumer"]["limits"]["wall_time_enforced"] = False
        outcome = await _evaluate(
            SandboxRoleResourceLimitsEnforcedAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        assert "wall_time_enforced" in outcome.message


class TestCrossVolumeCanaries:
    async def test_passes_when_every_canary_unreadable(self, tmp_path):
        payload = {
            "canaries": {
                f"{role}_sees_{probe}": {
                    "readable": False,
                    "role": role,
                }
                for role in ("consumer", "auditor")
                for probe in (
                    "host_home",
                    "host_keychain",
                    "docker_socket",
                    "peer_home",
                    "peer_credential",
                    "peer_spool",
                    "peer_workspace",
                )
            }
        }
        outcome = await _evaluate(
            SandboxCrossVolumeCanaryUnreadableAssertion(), tmp_path, payload
        )
        assert outcome.status == "passed"

    async def test_fails_when_a_canary_is_readable(self, tmp_path):
        payload = {
            "canaries": {
                "consumer_sees_host_home": {
                    "readable": True,
                    "role": "consumer",
                },
            }
        }
        outcome = await _evaluate(
            SandboxCrossVolumeCanaryUnreadableAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"

    async def test_fails_when_required_canaries_are_missing(self, tmp_path):
        payload = {
            "canaries": {
                "consumer_sees_docker_socket": {
                    "readable": False,
                    "role": "consumer",
                }
            }
        }
        outcome = await _evaluate(
            SandboxCrossVolumeCanaryUnreadableAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        assert "missing required canaries" in outcome.message


class TestRealHarnessUsesLogion:
    async def test_passes_for_two_in_container_codex_runs(self, tmp_path):
        payload = {
            "harness_runs": {
                role: {
                    "process_exit_code": 0,
                    "proof_read_exit_code": 0,
                    "proof": f"logion 0.2.0\nLOGION_HARNESS_OK {role}",
                    "prompt": "run logion --version",
                    "codex_version": "codex-cli 0.150.1",
                }
                for role in ("consumer", "auditor")
            }
        }
        outcome = await _evaluate(
            SandboxRealHarnessUsesLogionAssertion(), tmp_path, payload
        )
        assert outcome.status == "passed"
        # The auditor recomputes this verdict from facts, so the outcome
        # carries every observed field at the evidence root in the
        # {"ok": ..., "value": ...} envelope, role-keyed.
        evidence = outcome.evidence
        assert set(evidence) == {
            "harness_runs",
            "process_exit_code",
            "proof_read_exit_code",
            "proof",
            "prompt",
            "codex_version",
        }
        assert evidence["process_exit_code"] == {
            "ok": True,
            "value": {"auditor": 0, "consumer": 0},
        }
        assert evidence["proof"]["value"]["consumer"].endswith(
            "LOGION_HARNESS_OK consumer"
        )

    async def test_failed_runs_still_retain_their_facts(self, tmp_path):
        """A failed capture is evidence too: facts go out either way."""
        payload = {
            "harness_runs": {
                "consumer": {
                    "process_exit_code": 1,
                    "proof_read_exit_code": 1,
                    "proof": "",
                    "prompt": "run logion --version",
                    "codex_version": None,
                },
                "auditor": {
                    "process_exit_code": 0,
                    "proof_read_exit_code": 0,
                    "proof": "logion 0.2.0\nLOGION_HARNESS_OK auditor",
                    "prompt": "run logion --version",
                    "codex_version": "codex-cli 0.150.1",
                },
            }
        }
        outcome = await _evaluate(
            SandboxRealHarnessUsesLogionAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        evidence = outcome.evidence
        # A non-zero exit was still observed: ok means "seen", and the
        # contract's expected_values are what reject the value.
        assert evidence["process_exit_code"] == {
            "ok": True,
            "value": {"auditor": 0, "consumer": 1},
        }
        # A field nothing observed is still retained — typed as a missing
        # failure, never a fabricated placeholder. A report that dropped the
        # fact entirely would read as "not retained" and hide the gap.
        assert evidence["codex_version"] == {
            "ok": False,
            "failure": "missing",
            "value": {"auditor": "codex-cli 0.150.1", "consumer": None},
        }


class TestInstallScopedToRepository:
    def _payload(self) -> dict:
        return {
            "repository_scope": {
                "visible_in_xpto": True,
                "absent_from_abc": True,
                "absent_from_user_scope": True,
                "absent_from_auditor": True,
            }
        }

    async def test_passes_when_scoped(self, tmp_path):
        outcome = await _evaluate(
            InstallScopedToRepositoryAssertion(), tmp_path, self._payload()
        )
        assert outcome.status == "passed"

    async def test_fails_when_fixture_leaks_to_abc(self, tmp_path):
        payload = self._payload()
        payload["repository_scope"]["absent_from_abc"] = False
        outcome = await _evaluate(
            InstallScopedToRepositoryAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"
        assert "absent_from_abc" in outcome.message


class TestRoleCleanupComplete:
    def _payload(self) -> dict:
        return {
            "selective_reset": {
                "consumer_state_removed": True,
                "consumer_key_rejected": True,
                "consumer_new_key_accepted": True,
                "auditor_state_preserved": True,
                "auditor_key_accepted": True,
                "reset_exit_code": 0,
                "up_exit_code": 0,
            }
        }

    async def test_passes_on_clean_selective_reset(self, tmp_path):
        outcome = await _evaluate(
            RoleCleanupCompleteAssertion(), tmp_path, self._payload()
        )
        assert outcome.status == "passed"

    async def test_fails_when_auditor_state_was_removed(self, tmp_path):
        payload = self._payload()
        payload["selective_reset"]["auditor_state_preserved"] = False
        outcome = await _evaluate(
            RoleCleanupCompleteAssertion(), tmp_path, payload
        )
        assert outcome.status == "failed"

    async def test_fails_on_missing_manifest(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        outcome = await RoleCleanupCompleteAssertion().evaluate(
            ctx, {"manifest": "evidence/absent.json"}
        )
        assert outcome.status == "failed"


class TestScenarioShape:
    def test_scenario_loads_and_carries_every_gate_assertion(self):
        spec = load_scenario("builtin:phase_15_14_1_local_multi_agent_node")
        assert spec.api_adapter == "local-devrig"
        assert {agent.id for agent in spec.agents} == {
            "consumer",
            "auditor",
        }
        declared = {
            item.type for phase in spec.phases for item in phase.assertions
        } | {item.type for item in spec.final_assertions}
        required = {
            "sandbox.roles_run_non_root",
            "sandbox.role_resource_limits_enforced",
            "sandbox.real_harness_uses_logion",
            "files.install_scoped_to_repository",
            "sandbox.cross_volume_canary_unreadable",
            "api.role_credentials_isolated",
            "api.state_survives_restart",
            "files.role_cleanup_complete",
            "logs.no_500s",
        }
        assert required <= declared

    def test_no_development_only_drivers(self):
        spec = load_scenario("builtin:phase_15_14_1_local_multi_agent_node")
        assert all(
            agent.driver not in {"scripted", "local-process", "mock"}
            for agent in spec.agents
        )

    def test_local_hooks_reference_existing_scripts(self):
        spec = load_scenario("builtin:phase_15_14_1_local_multi_agent_node")
        # tests/ lives at <pkg-root>/tests/unit/, so the repo root is
        # three levels up from this file's directory.
        repo_root = Path(__file__).resolve().parents[4]
        for phase in spec.phases:
            if phase.local_hook:
                assert (repo_root / phase.local_hook).is_file(), (
                    f"missing local hook: {phase.local_hook}"
                )
