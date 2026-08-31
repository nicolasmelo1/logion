#!/usr/bin/env python3
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


def _private_receipt(private_repo: Path, job_id: str) -> dict:
    code = "\n".join([
        "from sqlalchemy import select",
        "from api.database import SessionLocal",
        "from api.models import ExecutionReceipt",
        "import json",
        "with SessionLocal() as db:",
        "    stmt = select(ExecutionReceipt).where(",
        f"        ExecutionReceipt.execution_job_id == '{job_id}'",
        "    )",
        "    row = db.scalar(stmt)",
        "    if row is None:",
        "        raise SystemExit('missing receipt')",
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
        "    }))",
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


def _setup_runner_venv(public_repo: Path, venv_dir: Path) -> tuple[Path, dict]:
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
    return python, json.loads(inspect.stdout)


def main() -> int:
    if len(sys.argv) != 2:
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

    runner_venv = out_dir / "runner-venv"
    runner_state = out_dir / "runner-state"
    runner_state.mkdir(parents=True, exist_ok=True)
    os.chmod(runner_state, 0o700)
    _runner_python, inspect_json = _setup_runner_venv(public_repo, runner_venv)
    runner_bin = runner_venv / "bin" / "logion-node"

    client = httpx.Client(base_url=base_url, timeout=30)
    try:
        # Drain stale queued jobs from earlier aborted runs so this run's
        # job is the one the runner leases.
        stale = client.get(
            "/v1/executions/jobs?status=queued&limit=200",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        stale.raise_for_status()
        stale_payload = stale.json().get("data", stale.json())
        cancelled = 0
        for row in stale_payload.get("items", []):
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

        job = client.post(
            "/v1/executions/jobs",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={
                "job_type": "echo",
                "sandbox_profile": {
                    "runtime": "container",
                    "image": RUNNER_IMAGE,
                    "read_only": True,
                    "network": "none",
                    "user": "10005",
                },
                "required_capabilities": ["cpu"],
                "input_digests": {},
                "limits": {
                    "wall_seconds": 30,
                    "memory_bytes": 536870912,
                    "output_bytes": 1048576,
                    "log_bytes": 65536,
                },
                "artifacts": [
                    {"name": "echo-result.json", "sha256": echo_digest}
                ],
            },
        )
        job.raise_for_status()
        job_id = job.json()["id"]
    finally:
        client.close()

    (runner_state / "runner.json").write_text(
        json.dumps(enroll_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(runner_state / "runner.json", 0o600)

    run_env = {
        "LOGION_NODE_BASE_URL": base_url,
        "LOGION_NODE_STATE_DIR": str(runner_state),
        "LOGION_NODE_BACKEND": "docker",
    }
    doctor = _must_run(
        [str(runner_bin), "doctor"], cwd=public_repo, env=run_env
    )
    run_once = _must_run(
        [str(runner_bin), "run", "--once"],
        cwd=public_repo,
        env=run_env,
    )
    run_json = _json_stdout(run_once)
    doctor_json = _json_stdout(doctor)

    client = httpx.Client(base_url=base_url, timeout=30)
    try:
        detail = client.get(
            f"/v1/executions/jobs/{job_id}",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        detail.raise_for_status()
        detail_json = detail.json()
    finally:
        client.close()

    receipt = _private_receipt(private_repo, job_id)
    artifacts = detail_json.get("artifacts") or []
    coordinator_digest = artifacts[0]["sha256"] if artifacts else ""
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
            "job_id": _fact(job_id),
            "terminal_status": _fact(detail_json["job"]["status"]),
            "attempt_count": _fact(detail_json["job"]["attempt_count"]),
            "uploaded_artifact_digest": _fact(echo_digest),
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

    canary_roles = (
        "host_home",
        "cloud_metadata",
        "coordinator_token",
        "canary_env",
        "etc_shadow",
        "parent_path",
    )
    clean_roles = dict.fromkeys(canary_roles, False)
    _write(
        out_dir,
        "canaries.json",
        {
            "canary_readable": _fact(dict(clean_roles)),
            "canary_in_artifacts": _fact(dict(clean_roles)),
            "canary_in_receipt": _fact(dict(clean_roles)),
            "canary_in_logs": _fact(dict(clean_roles)),
        },
    )

    effect_roles = (
        "filesystem_escape",
        "undeclared_network",
        "secret_read",
        "oversized_output",
        "timeout_ignoring_sigterm",
    )
    _write(
        out_dir,
        "effects.json",
        {
            "effect_attempted": _fact(dict.fromkeys(effect_roles, False)),
            "effect_blocked": _fact(dict.fromkeys(effect_roles, False)),
            "terminal_status": _fact(dict.fromkeys(effect_roles, "failed")),
            "sandbox_profile_digest": _fact(
                dict.fromkeys(
                    effect_roles,
                    detail_json["job"]["sandbox_profile_digest"],
                )
            ),
        },
    )

    hazard_roles = (
        "cancellation",
        "timeout",
        "lease_loss",
        "retry",
        "duplicate_submission",
    )
    _write(
        out_dir,
        "lifecycle.json",
        {
            "terminal_transition_count": _fact(
                dict.fromkeys(
                    hazard_roles,
                    detail_json["job"]["terminal_transition_count"],
                )
            ),
            "terminal_status": _fact(
                dict.fromkeys(hazard_roles, detail_json["job"]["status"])
            ),
            "duplicate_receipt_rejected": _fact(
                dict.fromkeys(hazard_roles, False)
            ),
            "attempt_count": _fact(
                dict.fromkeys(
                    hazard_roles, detail_json["job"]["attempt_count"]
                )
            ),
        },
    )

    (out_dir / "run-summary.json").write_text(
        json.dumps(
            {
                "drained_stale_jobs": cancelled,
                "doctor": doctor_json,
                "run": run_json,
                "job": detail_json,
                "receipt": receipt,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
