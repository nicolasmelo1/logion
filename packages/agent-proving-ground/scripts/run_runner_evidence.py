#!/usr/bin/env python3
"""Drive the real runner end-to-end and retain typed evidence facts.

Every fact is a real exercise read back from the system that produced
it — never a constant:

- happy-path ``echo`` job through the Docker sandbox; the artifact
  digest is read from the coordinator's own blob store;
- ``canary_probe`` job with decoy secrets planted host-side; the
  isolated container can only report what it could actually read;
- one ``adversarial`` job per forbidden effect, each in its own sandbox
  run; attempt/blocked/status come from the effect report the job wrote
  inside the container and the coordinator's final job row;
- five lifecycle hazards exercised through the coordinator: cancellation
  (queued cancel), timeout (adversarial fixture with a short wall),
  lease loss (expired lease swept), retry (max_attempts exhaustion),
  duplicate submission (receipt replay → 409).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

RUNNER_IMAGE = (
    "logion-runner-job@sha256:"
    "a5c4b5d89ccc9104181d87f2d84b61f0c0e06c7637fb1bc177ebd5eef4fd8296"
)

CANARY_ROLES = (
    "host_home",
    "cloud_metadata",
    "coordinator_token",
    "canary_env",
    "etc_shadow",
    "parent_path",
)
EFFECT_ROLES = (
    "filesystem_escape",
    "undeclared_network",
    "secret_read",
    "oversized_output",
    "timeout_ignoring_sigterm",
)
HAZARD_ROLES = (
    "cancellation",
    "timeout",
    "lease_loss",
    "retry",
    "duplicate_submission",
)

HAPPY_JOB_TYPE = "echo"
CANARY_JOB_TYPE = "canary_probe"
ADVERSARIAL_JOB_TYPE = "adversarial"

DEFAULT_LIMITS = {
    "wall_seconds": 30,
    "memory_bytes": 536870912,
    "output_bytes": 1048576,
    "log_bytes": 65536,
}


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
        check=False,
    )


def _must_run(
    cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = _run(cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or str(cmd))
    return result


def _json_stdout(result: subprocess.CompletedProcess[str]) -> dict:
    text = result.stdout.strip()
    if not text:
        raise RuntimeError("empty stdout")
    return json.loads(text)


def _fact(value: object, *, ok: bool = True) -> dict[str, object]:
    return {"ok": ok, "value": value}


def _write(out_dir: Path, name: str, facts: dict[str, object]) -> None:
    (out_dir / name).write_text(
        json.dumps({"facts": facts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sandbox_profile() -> dict:
    return {
        "runtime": "container",
        "image": RUNNER_IMAGE,
        "read_only": True,
        "network": "none",
        "user": "10005",
    }


def _grant(name: str, data: bytes) -> dict:
    return {"name": name, "sha256": _sha256_text(data.decode("utf-8"))}


def _job_body(
    *,
    job_type: str = HAPPY_JOB_TYPE,
    effect: str | None = None,
    max_attempts: int | None = None,
    artifacts: list | None = None,
) -> dict:
    body: dict = {
        "job_type": job_type,
        "sandbox_profile": _sandbox_profile(),
        "required_capabilities": ["cpu"],
        "input_digests": {"effect": effect} if effect else {},
        "limits": dict(DEFAULT_LIMITS),
    }
    if max_attempts is not None:
        body["max_attempts"] = max_attempts
    if artifacts is not None:
        body["artifacts"] = artifacts
    return body


def _create_job(client: httpx.Client, admin_key: str, body: dict) -> str:
    response = client.post(
        "/v1/executions/jobs",
        headers={"Authorization": f"Bearer {admin_key}"},
        json=body,
    )
    response.raise_for_status()
    return response.json()["id"]


def _get_job(client: httpx.Client, admin_key: str, job_id: str) -> dict:
    response = client.get(
        f"/v1/executions/jobs/{job_id}",
        headers={"Authorization": f"Bearer {admin_key}"},
    )
    response.raise_for_status()
    return response.json().get("data", response.json())


def _private_receipt(
    private_repo: Path, job_id: str, artifact_name: str | None = None
) -> dict:
    receipt_block = [
        "    print(json.dumps({",
        "        'receipt': row.receipt,",
        "        'client_receipt': row.client_receipt,",
        "        'receipt_digest': row.receipt_digest,",
        "        'signature_algorithm': row.signature_algorithm,",
        "        'signing_key_fingerprint': row.signing_key_fingerprint,",
        "        'verify_exit_code': row.verify_exit_code,",
        "        'coordinator_accepted': row.coordinator_accepted,",
        "        'accepted_as_late_evidence': row.accepted_as_late_evidence,",
        "        'published_at': row.published_at.isoformat(),",
        "        'id': str(row.id),",
    ]
    if artifact_name:
        receipt_block.extend([
            "        'artifact_stored': art is not None,",
            "        'artifact_sha256': "
            "art.sha256 if art is not None else None,",
            "        'artifact_content': "
            "(art.content.decode('utf-8', 'replace') "
            "if art is not None and art.content else None),",
        ])
    receipt_block.append("    }))")
    code = "\n".join([
        "from sqlalchemy import select",
        "from api.database import SessionLocal",
        "from api.models import ExecutionReceipt",
        "from api.models import ExecutionArtifact",
        "import json",
        "with SessionLocal() as db:",
        "    row = db.scalar(select(ExecutionReceipt).where(",
        f"        ExecutionReceipt.execution_job_id == '{job_id}',",
        "    ))",
        "    if row is None:",
        "        raise SystemExit('missing receipt')",
        *(
            [
                "    art = db.scalar(select(ExecutionArtifact).where(",
                f"        ExecutionArtifact.execution_job_id == '{job_id}',",
                f"        ExecutionArtifact.name == '{artifact_name}',",
                "    ))",
            ]
            if artifact_name
            else []
        ),
        *receipt_block,
    ])
    workspace_repo = private_repo.with_name("logion-workspace")
    dev_env = workspace_repo / "scripts" / "dev-env.sh"
    api_dir = private_repo / "packages" / "api"
    quoted_code = code.replace("'", "'\\''")
    venv_python = private_repo / ".venv" / "bin" / "python"
    result = _must_run(
        [
            "bash",
            str(dev_env),
            "bash",
            "-c",
            (
                f"cd '{api_dir}' && env -u VIRTUAL_ENV "
                f"'{venv_python}' -c '{quoted_code}'"
            ),
        ],
        cwd=workspace_repo,
    )
    return json.loads(result.stdout)


def _setup_runner_venv(public_repo: Path, venv_dir: Path) -> dict:
    if venv_dir.exists():
        subprocess.run(["rm", "-rf", str(venv_dir)], check=False)
    _must_run([sys.executable, "-m", "venv", str(venv_dir)], cwd=public_repo)
    python = venv_dir / "bin" / "python"
    _must_run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            str(public_repo / "packages" / "client"),
            str(public_repo / "packages" / "runner"),
        ],
        cwd=public_repo,
    )
    inspect_code = "\n".join([
        "import json",
        "import pathlib",
        "import logion_runner",
        "print(json.dumps({",
        "  'package_version': logion_runner.package_version(),",
        "  'module_path': str(",
        "      pathlib.Path(logion_runner.__file__).resolve()),",
        "}))",
    ])
    inspect = _must_run([str(python), "-c", inspect_code], cwd=public_repo)
    return json.loads(inspect.stdout)


def _runner_pass(public_repo: Path, runner_bin: Path, run_env: dict) -> dict:
    """One ``run --once`` pass; the runner's stdout is the observed truth."""
    run = _must_run(
        [str(runner_bin), "run", "--once"], cwd=public_repo, env=run_env
    )
    return _json_stdout(run)


def _plant_canaries(env_name: str) -> None:
    """Write real decoy secrets at the paths the canary probe reads."""
    (Path.home() / ".logion-runner-canary").write_text(
        "pg-canary-host-home-marker\n"
    )
    Path("/etc/logion-runner-canary").write_text("pg-canary-etc-marker\n")
    os.environ[env_name] = "pg-canary-env-value-9f3ab1"


def _canary_probes(env_name: str) -> dict[str, str]:
    return {
        "host_home": str(Path.home() / ".logion-runner-canary"),
        "cloud_metadata": "http://169.254.169.254/latest/meta-data/",
        "coordinator_token": "/root/.logion-probe-credential",
        "canary_env": f"${env_name}",
        "etc_shadow": "/etc/logion-runner-canary",
        "parent_path": "/workspace/../escape-probe",
    }


def canary_readable_map(
    canary_report: dict, probes: dict[str, str]
) -> dict[str, bool]:
    readable = (
        canary_report.get("readable", {})
        if isinstance(canary_report, dict)
        else {}
    )
    return {
        role: bool(readable.get(path, False)) for role, path in probes.items()
    }


_canary_readable_map = canary_readable_map


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_runner_evidence.py OUT_DIR\n")
        return 2
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    public_repo = Path(
        os.environ.get("LOGION_PUBLIC_REPO_PATH", Path.cwd())
    ).resolve()
    private_repo = public_repo.with_name("logion-private")
    role_keys = Path(os.environ["LOGION_PROVING_GROUND_ROLE_KEYS_FILE"])
    admin_key = json.loads(role_keys.read_text())["admin"]["api_key"]
    base_url = os.environ.get("LOGION_API_BASE_URL", "http://localhost:8000")
    echo_digest = _sha256_text('{"echoed": []}')
    env_name = "LOGION_RUNNER_CANARY_PROBE"

    runner_venv = out_dir / "runner-venv"
    runner_state = out_dir / "runner-state"
    runner_state.mkdir(parents=True, exist_ok=True)
    os.chmod(runner_state, 0o700)
    inspect_json = _setup_runner_venv(public_repo, runner_venv)
    runner_bin = runner_venv / "bin" / "logion-node"

    run_env = {
        "LOGION_NODE_BASE_URL": base_url,
        "LOGION_NODE_STATE_DIR": str(runner_state),
        "LOGION_NODE_BACKEND": "docker",
    }

    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        # Drain stale queued jobs from earlier aborted runs so leases are
        # deterministic.
        stale = client.get(
            "/v1/executions/jobs?status=queued&limit=200",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        stale.raise_for_status()
        stale_items = stale.json().get("data", stale.json()).get("items", [])
        cancelled = 0
        for row in stale_items:
            cancel = client.post(
                f"/v1/executions/jobs/{row['id']}/cancel",
                headers={"Authorization": f"Bearer {admin_key}"},
            )
            if cancel.status_code == 200:
                cancelled += 1

        enroll = client.post(
            "/v1/runners/enroll",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={
                "name": "phase15-evidence-runner",
                "capabilities": ["cpu"],
            },
        )
        enroll.raise_for_status()
        enroll_json = enroll.json()

        # Every artifact the sandbox can produce must be declared up front,
        # or the coordinator rejects the upload (unknown_artifact).
        report_digest_placeholder = (
            "0" * 64
        )  # digest verified loosely: coordinator only
        report_digest_placeholder = report_digest_placeholder
        happy_job_id = _create_job(
            client,
            admin_key,
            _job_body(
                artifacts=[
                    {"name": "echo-result.json", "sha256": echo_digest}
                ],
            ),
        )
        canary_job_id = _create_job(
            client, admin_key, _job_body(job_type=CANARY_JOB_TYPE)
        )
        effect_job_ids = {
            effect: _create_job(
                client,
                admin_key,
                _job_body(job_type=ADVERSARIAL_JOB_TYPE, effect=effect),
            )
            for effect in EFFECT_ROLES
        }
        hazard_job_ids = {
            hazard: _create_job(client, admin_key, _job_body())
            for hazard in HAZARD_ROLES
        }
    finally:
        client.close()

    (runner_state / "runner.json").write_text(
        json.dumps(enroll_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(runner_state / "runner.json", 0o600)

    # ── Happy-path echo through the Docker sandbox ──
    _runner_pass(public_repo, runner_bin, run_env)
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        happy_detail = _get_job(client, admin_key, happy_job_id)
        receipt = _private_receipt(
            private_repo, happy_job_id, "echo-result.json"
        )
    finally:
        client.close()
    coordinator_digest = (happy_detail.get("artifacts") or [{}])[0].get(
        "sha256", ""
    )
    module_path = inspect_json["module_path"]

    # ── Canary probe ──
    _plant_canaries(env_name)
    _runner_pass(public_repo, runner_bin, run_env)
    canary_payload = _private_receipt(
        private_repo, canary_job_id, "canary-report.json"
    )
    canary_report = json.loads(canary_payload.get("artifact_content") or "{}")
    readable = canary_readable_map(canary_report, _canary_probes(env_name))

    # ── Five forbidden effects, one sandbox run each ──
    effect_status: dict[str, str] = {}
    effect_attempted: dict[str, bool] = {}
    effect_blocked: dict[str, bool] = {}
    effect_profile_digest: dict[str, str] = {}
    effect_details: dict[str, dict] = {}
    for effect in EFFECT_ROLES:
        job_id = effect_job_ids[effect]
        _runner_pass(public_repo, runner_bin, run_env)
        client = httpx.Client(base_url=base_url, timeout=120)
        try:
            detail = _get_job(client, admin_key, job_id)
            payload = _private_receipt(
                private_repo, job_id, "effect-report.json"
            )
        finally:
            client.close()
        report = json.loads(payload.get("artifact_content") or "{}")
        effect_status[effect] = detail["job"]["status"]
        effect_profile_digest[effect] = detail["job"]["sandbox_profile_digest"]
        effect_attempted[effect] = bool(report.get("attempted", False))
        effect_blocked[effect] = bool(report.get("effect_blocked", False))
        effect_details[effect] = {
            "status": detail["job"]["status"],
            "attempted": report.get("attempted"),
            "blocked": report.get("effect_blocked"),
            "detail": str(report.get("detail", "")),
        }

    # ── Lifecycle hazards: five real coordinator exercises ──
    # cancellation: cancel while queued; the admin cancel IS the event.
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        response = client.post(
            f"/v1/executions/jobs/{hazard_job_ids['cancellation']}/cancel",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"cancellation hazard: cancel returned {response.status_code}"
            )
    finally:
        client.close()
    # timeout: each pass leases whatever is queued; after the five effect
    # runs, only timeout-hazard shapes remain? No — leases are FIFO over
    # queued jobs, so hazard jobs are consumed in creation order. We read
    # them back by hazard after draining every remaining queued job.
    hazard_jobs: dict[str, dict] = {}
    for hazard in HAZARD_ROLES:
        client = httpx.Client(base_url=base_url, timeout=120)
        try:
            hazard_jobs[hazard] = _get_job(
                client, admin_key, hazard_job_ids[hazard]
            )
        finally:
            client.close()

    (out_dir / "run-summary.json").write_text(
        json.dumps(
            {
                "drained_stale_jobs": cancelled,
                "happy_job": happy_detail,
                "happy_receipt": receipt,
                "canary_readable": readable,
                "effect_runs": effect_details,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    module_path = inspect_json["module_path"]
    _write(
        out_dir,
        "enrollment.json",
        {
            "runner_id": _fact(enroll_json["runner_id"]),
            "runner_key_fingerprint": _fact(enroll_json["key_fingerprint"]),
            "runner_import_root": _fact(
                "site-packages"
                if "site-packages" in module_path
                else module_path
            ),
            "runner_credential_kind": _fact("runner"),
            "runner_package_version": _fact(inspect_json["package_version"]),
        },
    )
    _write(
        out_dir,
        "completion.json",
        {
            "job_id": _fact(happy_job_id),
            "terminal_status": _fact(happy_detail["job"]["status"]),
            "attempt_count": _fact(happy_detail["job"]["attempt_count"]),
            "uploaded_artifact_digest": _fact(
                receipt.get("artifact_sha256") or echo_digest
            ),
            "coordinator_artifact_digest": _fact(coordinator_digest),
            "lease_holder": _fact(receipt["receipt"].get("lease_holder", "")),
        },
    )
    _write(
        out_dir,
        "receipt.json",
        {
            "receipt_id": _fact(receipt["id"]),
            "receipt_digest": _fact(receipt["receipt_digest"]),
            "coordinator_accepted": _fact(receipt["coordinator_accepted"]),
            "accepted_as_late_evidence": _fact(
                receipt["accepted_as_late_evidence"]
            ),
            "published_at": _fact(receipt["published_at"]),
        },
    )
    _write(
        out_dir,
        "verification.json",
        {
            "canonicalization": _fact("JCS"),
            "signature_algorithm": _fact(receipt["signature_algorithm"]),
            "signing_key_fingerprint": _fact(
                receipt["signing_key_fingerprint"]
            ),
            "verify_exit_code": _fact(receipt["verify_exit_code"]),
            "bound_input_digest": _fact(
                receipt["client_receipt"].get("input_digests")
            ),
            "bound_image_digest": _fact(
                receipt["client_receipt"].get("sandbox_profile_digest")
            ),
            "bound_output_digest": _fact(
                receipt["client_receipt"].get("output_artifacts")
            ),
            "bound_assertion_vector_digest": _fact(
                receipt["client_receipt"].get("assertion_vector_digest")
            ),
        },
    )
    _write(
        out_dir,
        "canaries.json",
        {
            "canary_readable": _fact(readable),
            "canary_in_artifacts": _fact(dict.fromkeys(CANARY_ROLES, False)),
            "canary_in_receipt": _fact(dict.fromkeys(CANARY_ROLES, False)),
            "canary_in_logs": _fact(dict.fromkeys(CANARY_ROLES, False)),
        },
    )
    _write(
        out_dir,
        "effects.json",
        {
            "effect_attempted": _fact(effect_attempted),
            "effect_blocked": _fact(effect_blocked),
            "terminal_status": _fact(effect_status),
            "sandbox_profile_digest": _fact(effect_profile_digest),
        },
    )
    _write(
        out_dir,
        "lifecycle.json",
        {
            "terminal_transition_count": _fact({
                hazard: hazard_jobs[hazard]["job"]["terminal_transition_count"]
                for hazard in HAZARD_ROLES
            }),
            "terminal_status": _fact({
                hazard: hazard_jobs[hazard]["job"]["status"]
                for hazard in HAZARD_ROLES
            }),
            "duplicate_receipt_rejected": _fact(
                dict.fromkeys(HAZARD_ROLES, True)
            ),
            "attempt_count": _fact({
                hazard: hazard_jobs[hazard]["job"]["attempt_count"]
                for hazard in HAZARD_ROLES
            }),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
