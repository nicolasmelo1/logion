from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from agent_proving_ground.api_adapters.base import ApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.runner import (
    CanaryNotExfiltratedAssertion,
    RunnerEnrolledAssertion,
    RunnerReceiptPublishedAssertion,
    RunnerReceiptValidAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _ctx(tmp_path: Path) -> AssertionContext:
    class Api:
        name = "test"

    return AssertionContext(
        "runner",
        "collect",
        cast(World, object()),
        cast(ApiAdapter, Api()),
        tmp_path,
        cast(Timeline, None),
    )


def test_runner_enrollment_requires_published_runner_and_credential(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "runner.json"
    manifest.write_text(
        json.dumps({
            "facts": {
                "runner_id": {"ok": True, "value": "r-1"},
                "runner_key_fingerprint": {"ok": True, "value": "abc"},
                "runner_import_root": {"ok": True, "value": "site-packages"},
                "runner_credential_kind": {"ok": True, "value": "runner"},
                "runner_package_version": {"ok": True, "value": "0.2.0"},
            }
        })
    )
    outcome = __import__("asyncio").run(
        RunnerEnrolledAssertion().evaluate(
            _ctx(tmp_path), {"manifest": "runner.json"}
        )
    )
    assert outcome.status == "passed"


def test_canary_assertion_rejects_missing_role(tmp_path: Path) -> None:
    manifest = tmp_path / "runner.json"
    roles = {
        name: {"host_home": False}
        for name in (
            "canary_readable",
            "canary_in_artifacts",
            "canary_in_receipt",
            "canary_in_logs",
        )
    }
    manifest.write_text(
        json.dumps({
            "facts": {
                name: {"ok": True, "value": value}
                for name, value in roles.items()
            }
        })
    )
    outcome = __import__("asyncio").run(
        CanaryNotExfiltratedAssertion().evaluate(
            _ctx(tmp_path), {"manifest": "runner.json"}
        )
    )
    assert outcome.status == "failed"


def _write_facts(tmp_path: Path, facts: dict) -> dict:
    manifest = tmp_path / "runner.json"
    manifest.write_text(json.dumps({"facts": facts}))
    return {"manifest": "runner.json"}


def test_bool_false_facts_are_not_rejected_as_forbidden(
    tmp_path: Path,
) -> None:
    """accepted_as_late_evidence=False is the honest honest-run value; ``0``
    must not collapse into the ``False`` sentinel (0 == False in Python)."""
    params = _write_facts(
        tmp_path,
        {
            "receipt_id": {"ok": True, "value": "rc-1"},
            "receipt_digest": {"ok": True, "value": "d" * 64},
            "coordinator_accepted": {"ok": True, "value": True},
            "accepted_as_late_evidence": {"ok": True, "value": False},
            "published_at": {"ok": True, "value": "2026-08-31T00:00:00Z"},
        },
    )
    outcome = __import__("asyncio").run(
        RunnerReceiptPublishedAssertion().evaluate(_ctx(tmp_path), params)
    )
    assert outcome.status == "passed"


def test_int_zero_facts_are_not_rejected_by_false_sentinel(
    tmp_path: Path,
) -> None:
    params = _write_facts(
        tmp_path,
        {
            "canonicalization": {"ok": True, "value": "JCS"},
            "signature_algorithm": {"ok": True, "value": "Ed25519"},
            "signing_key_fingerprint": {"ok": True, "value": "fp"},
            "verify_exit_code": {"ok": True, "value": 0},
            "bound_input_digest": {"ok": True, "value": "in"},
            "bound_image_digest": {"ok": True, "value": "img"},
            "bound_output_digest": {"ok": True, "value": "out"},
            "bound_assertion_vector_digest": {"ok": True, "value": "vec"},
        },
    )
    outcome = __import__("asyncio").run(
        RunnerReceiptValidAssertion().evaluate(_ctx(tmp_path), params)
    )
    assert outcome.status == "passed"


def test_canary_all_false_roles_pass(tmp_path: Path) -> None:
    """The all-False canary map is the honest no-exfiltration outcome."""
    clean = dict.fromkeys(
        (
            "host_home",
            "cloud_metadata",
            "coordinator_token",
            "canary_env",
            "etc_shadow",
            "parent_path",
        ),
        False,
    )
    params = _write_facts(
        tmp_path,
        {
            "canary_readable": {"ok": True, "value": dict(clean)},
            "canary_in_artifacts": {"ok": True, "value": dict(clean)},
            "canary_in_receipt": {"ok": True, "value": dict(clean)},
            "canary_in_logs": {"ok": True, "value": dict(clean)},
        },
    )
    outcome = __import__("asyncio").run(
        CanaryNotExfiltratedAssertion().evaluate(_ctx(tmp_path), params)
    )
    assert outcome.status == "passed"


def test_none_sentinel_still_fails(tmp_path: Path) -> None:
    params = _write_facts(
        tmp_path,
        {
            "runner_id": {"ok": True, "value": "r-1"},
            "runner_key_fingerprint": {"ok": True, "value": None},
            "runner_import_root": {"ok": True, "value": "site-packages"},
            "runner_credential_kind": {"ok": True, "value": "runner"},
            "runner_package_version": {"ok": True, "value": "0.2.0"},
        },
    )
    outcome = __import__("asyncio").run(
        RunnerEnrolledAssertion().evaluate(_ctx(tmp_path), params)
    )
    assert outcome.status == "failed"


def test_evidence_keyed_by_its_subject_survives_redaction() -> None:
    """Canary facts are keyed by what they are about, not what they hold."""
    from agent_proving_ground.redaction import redact_json

    assert redact_json({
        "coordinator_token": False,
        "secret_read": "failed",
        "canary_env": True,
    }) == {
        "coordinator_token": False,
        "secret_read": "failed",
        "canary_env": True,
    }


def test_a_real_credential_is_still_redacted_under_any_key() -> None:
    """Narrowing the key backstop must not let a credential through."""
    from agent_proving_ground.redaction import redact_json

    redacted = redact_json({
        "api_token": "logion_runner_" + "x" * 43,
        "secret_read": "Bearer sk_live_abcdefghijklmnopqrstuv",
        "harmless": "Bearer sk_live_abcdefghijklmnopqrstuv",
    })
    assert redacted["api_token"] == "<redacted>"
    assert "sk_live" not in str(redacted["secret_read"])
    assert "sk_live" not in str(redacted["harmless"])


def test_retained_evidence_does_not_carry_the_operator_home_path() -> None:
    """Public evidence must be portable and must not name a real host."""
    from pathlib import Path

    from agent_proving_ground.redaction import redact_json

    home = str(Path.home())
    redacted = redact_json({
        "artifact_root": f"{home}/workspaces/logion/.runs/p1515",
        "nested": [{"log_path": f"{home}/.devrig/api.log"}],
    })
    assert redacted == {
        "artifact_root": "~/workspaces/logion/.runs/p1515",
        "nested": [{"log_path": "~/.devrig/api.log"}],
    }
    assert home not in str(redacted)


def test_normalization_stays_out_of_the_secret_detector() -> None:
    """`redact_text` doubles as the detector; it must not rewrite paths.

    `timeline.no_unredacted_secret` fails a line whenever `redact_text`
    changes it, so a cosmetic rewrite in there reports every ordinary
    local path as a leak.
    """
    from pathlib import Path

    from agent_proving_ground.redaction import redact_json, redact_text

    line = f'{{"workspace": "{Path.home()}/logion/.runs/p1"}}'
    assert redact_text(line) == line
    assert redact_json({"workspace": f"{Path.home()}/logion/.runs/p1"}) == {
        "workspace": "~/logion/.runs/p1"
    }
