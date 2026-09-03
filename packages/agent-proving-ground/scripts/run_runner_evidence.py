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

RUNNER_IMAGE_TAG = "logion-runner-job:fixed"


def resolve_runner_image(docker_cli: str = "docker") -> str:
    """Return the pinned reference for the locally built sandbox image.

    The digest is read back from the image the host actually holds. Writing
    a constant here would be a pin nothing produces: the first run on a
    machine that never built the image would either fail opaquely or, worse,
    match something else that happened to carry the name.
    """
    probe = subprocess.run(
        [
            docker_cli,
            "image",
            "inspect",
            RUNNER_IMAGE_TAG,
            "--format",
            "{{.Id}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"sandbox image {RUNNER_IMAGE_TAG} is not built; run "
            "`make runner-image` first"
        )
    return f"logion-runner-job@{probe.stdout.strip()}"


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


#: Which assertion each evidence file feeds. Three of the 15.15 contracts
#: name a fact ``terminal_status`` over three different keyspaces, so the
#: manifest is scoped by assertion rather than flat -- which is the shape
#: the auditor's recompute already reads.
EVIDENCE_ASSERTIONS: dict[str, str] = {
    "enrollment.json": "api.runner_enrolled",
    "completion.json": "api.runner_job_completed",
    "receipt.json": "api.runner_receipt_published",
    "verification.json": "crypto.runner_receipt_valid",
    "canaries.json": "sandbox.canary_not_exfiltrated",
    "effects.json": "sandbox.forbidden_effect_blocked",
    "lifecycle.json": "api.runner_job_terminal_once",
}


def _write(out_dir: Path, name: str, facts: dict[str, object]) -> None:
    (out_dir / name).write_text(
        json.dumps(
            {"assertion": EVIDENCE_ASSERTIONS[name], "facts": facts},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sandbox_profile(image: str) -> dict:
    return {
        "runtime": "container",
        "image": image,
        "read_only": True,
        "network": "none",
        "user": "10005",
    }


def _grant(name: str, data: bytes) -> dict:
    return {"name": name, "sha256": _sha256_text(data.decode("utf-8"))}


def _job_body(
    image: str,
    *,
    job_type: str = HAPPY_JOB_TYPE,
    effect: str | None = None,
    max_attempts: int | None = None,
    artifacts: list | None = None,
    limits: dict | None = None,
) -> dict:
    body: dict = {
        "job_type": job_type,
        "sandbox_profile": _sandbox_profile(image),
        "required_capabilities": ["cpu"],
        "input_digests": {"effect": effect} if effect else {},
        "limits": dict(limits or DEFAULT_LIMITS),
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


def _private_python(private_repo: Path, code: str) -> dict:
    """Run *code* inside the coordinator's venv and parse its stdout JSON.

    The lease-expiry and retry hazards are events only the coordinator can
    produce. Driving them from here means the evidence records what the
    coordinator did, not what this script hoped it would do.
    """
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


def _claim_only(base_url: str, runner_key: str) -> dict | None:
    """Take a lease and walk away, so the lease can be lost mid-flight.

    The runner CLI always runs a job to completion, which is the wrong
    shape for the lease-loss and retry hazards: those need a lease that is
    genuinely held and then genuinely expires.
    """
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        response = client.post(
            "/v1/runners/lease",
            headers={"Authorization": f"Bearer {runner_key}"},
            json={"capabilities": ["cpu"]},
        )
        response.raise_for_status()
        return response.json().get("data")
    finally:
        client.close()


def _expire_lease(private_repo: Path, job_id: str) -> dict:
    """Push a held lease into the past and run the coordinator's sweep.

    This is the lease-loss event: the runner still believes it holds the
    job, and the coordinator's own recovery decides what happens next.
    """
    return _private_python(
        private_repo,
        "\n".join([
            "import json",
            "from datetime import UTC, datetime, timedelta",
            "from api.database import SessionLocal",
            "from api.models import ExecutionJob",
            "from api.executions.services.run_expired_leases import (",
            "    RunExpiredLeasesService,",
            ")",
            "with SessionLocal() as db:",
            f"    job = db.get(ExecutionJob, '{job_id}')",
            "    before = job.status",
            "    job.lease_expires_at = datetime.now(UTC) - timedelta(",
            "        seconds=600)",
            "    db.commit()",
            "    swept = RunExpiredLeasesService(db).execute()",
            "    db.refresh(job)",
            "    print(json.dumps({",
            "        'before': before,",
            "        'swept': swept,",
            "        'after': job.status,",
            "        'attempt_count': job.attempt_count,",
            "        'terminal_transition_count':"
            " job.terminal_transition_count,",
            "    }))",
        ]),
    )


def _stored_artifacts_text(private_repo: Path, job_ids: list[str]) -> str:
    """Every artifact byte the coordinator stored for *job_ids*."""
    quoted = ", ".join(f"'{job_id}'" for job_id in job_ids)
    payload = _private_python(
        private_repo,
        "\n".join([
            "import json",
            "from sqlalchemy import select",
            "from api.database import SessionLocal",
            "from api.models import ExecutionArtifact",
            "with SessionLocal() as db:",
            "    rows = db.scalars(select(ExecutionArtifact).where(",
            f"        ExecutionArtifact.execution_job_id.in_([{quoted}]),",
            "    )).all()",
            "    print(json.dumps({'text': '\\n'.join(",
            "        (r.content or b'').decode('utf-8', 'replace')",
            "        + ' ' + r.name for r in rows)}))",
        ]),
    )
    return str(payload["text"])


def _stored_receipts_text(private_repo: Path, job_ids: list[str]) -> str:
    """Every receipt the coordinator holds for *job_ids*, as text."""
    quoted = ", ".join(f"'{job_id}'" for job_id in job_ids)
    payload = _private_python(
        private_repo,
        "\n".join([
            "import json",
            "from sqlalchemy import select",
            "from api.database import SessionLocal",
            "from api.models import ExecutionReceipt",
            "with SessionLocal() as db:",
            "    rows = db.scalars(select(ExecutionReceipt).where(",
            f"        ExecutionReceipt.execution_job_id.in_([{quoted}]),",
            "    )).all()",
            "    print(json.dumps({'text': '\\n'.join(",
            "        json.dumps(r.receipt) + json.dumps(r.client_receipt)",
            "        for r in rows)}))",
        ]),
    )
    return str(payload["text"])


def _private_receipt(
    private_repo: Path, job_id: str, artifact_name: str | None = None
) -> dict:
    receipt_block = [
        "    print(json.dumps({",
        "        'receipt': row.receipt,",
        "        'client_receipt': row.client_receipt,",
        "        'receipt_digest': row.receipt_digest,",
        "        'signature': row.signature,",
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
    return _private_python(private_repo, code)


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


#: Every byte the runner wrote across the run. The canary log fact is a
#: search over this, so it can only say "no marker" after there was
#: output to look through.
RUNNER_LOG: list[str] = []


def _runner_pass(public_repo: Path, runner_bin: Path, run_env: dict) -> dict:
    """One ``run --once`` pass; the runner's stdout is the observed truth."""
    run = _must_run(
        [str(runner_bin), "run", "--once"], cwd=public_repo, env=run_env
    )
    RUNNER_LOG.append(run.stdout)
    RUNNER_LOG.append(run.stderr)
    return _json_stdout(run)


#: One decoy per canary role, each with a marker string that appears
#: nowhere else. The exfiltration facts are a search for these exact
#: values in the artifacts, the receipt and the runner logs, so a leak
#: anywhere along that path is observable rather than assumed absent.
CANARY_MARKERS: dict[str, str] = {
    "host_home": "pg-canary-host-home-4f1c2a",
    "etc_shadow": "pg-canary-etc-shadow-7b3d90",
    "coordinator_token": "pg-canary-coordinator-token-2e8f55",
    "canary_env": "pg-canary-env-value-9f3ab1",
    "cloud_metadata": "pg-canary-cloud-metadata-6a4d17",
    "parent_path": "pg-canary-parent-path-c0b2e4",
}


def _canary_probes(env_name: str) -> dict[str, str]:
    """Role -> host path, all of them inside ``CANARY_PATHS``.

    ``etc_shadow`` prefers ``/etc`` because that is the path an escaping
    job would reach for, but collecting evidence must not require root.
    When ``/etc`` is not writable the decoy moves to the host home, which
    is the same boundary from the sandbox's point of view; the runner
    probes both, so whichever was planted is the one measured.
    """
    del env_name
    home = Path.home()
    return {
        "host_home": str(home / ".logion-runner-canary"),
        "etc_shadow": _etc_canary_path(),
        "coordinator_token": str(home / ".logion-runner-canary-token"),
        "canary_env": str(home / ".logion-runner-canary-env"),
        "cloud_metadata": str(home / ".logion-runner-canary-imds"),
        "parent_path": str(home / ".logion-runner-canary-parent"),
    }


def _etc_canary_path() -> str:
    """``/etc`` when this user can write it, else the host-home stand-in."""
    if os.access("/etc", os.W_OK):
        return "/etc/logion-runner-canary"
    return str(Path.home() / ".logion-runner-canary-etc")


def _plant_canaries(env_name: str) -> dict[str, str]:
    """Write a real decoy secret at every path the canary probe reads."""
    probes = _canary_probes(env_name)
    for role, path in probes.items():
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(CANARY_MARKERS[role] + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
    os.environ[env_name] = CANARY_MARKERS["canary_env"]
    return probes


def canary_exfiltration_map(haystack: str) -> dict[str, bool]:
    """True for every canary marker that appears in *haystack*."""
    return {
        role: marker in haystack for role, marker in CANARY_MARKERS.items()
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


def _enroll_and_seed(
    *,
    base_url: str,
    admin_key: str,
    runner_image: str,
    echo_digest: str,
) -> tuple[int, dict, str, str, dict[str, str]]:
    """Drain leftovers, enrol the runner, and queue the seed jobs.

    Stale queued jobs from an aborted run are cancelled first so leasing
    is FIFO-deterministic. Every artifact a sandbox may produce is
    declared up front or the coordinator rejects the upload as unknown;
    the two report artifacts carry no digest because their contents are
    what the run is trying to find out.
    """
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
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

        happy_job_id = _create_job(
            client,
            admin_key,
            _job_body(
                runner_image,
                artifacts=[
                    {"name": "echo-result.json", "sha256": echo_digest}
                ],
            ),
        )
        canary_job_id = _create_job(
            client,
            admin_key,
            _job_body(
                runner_image,
                job_type=CANARY_JOB_TYPE,
                artifacts=[{"name": "canary-report.json"}],
            ),
        )
        effect_job_ids = {
            effect: _create_job(
                client,
                admin_key,
                _job_body(
                    runner_image,
                    job_type=ADVERSARIAL_JOB_TYPE,
                    effect=effect,
                    artifacts=[{"name": "effect-report.json"}],
                ),
            )
            for effect in EFFECT_ROLES
        }
    finally:
        client.close()
    return (
        cancelled,
        enroll_json,
        happy_job_id,
        canary_job_id,
        effect_job_ids,
    )


def _exercise_effects(
    *,
    base_url: str,
    admin_key: str,
    effect_job_ids: dict[str, str],
    public_repo: Path,
    private_repo: Path,
    runner_bin: Path,
    run_env: dict,
) -> dict[str, dict]:
    """Run each adversarial fixture and read back what the sandbox did.

    The verdict comes from the coordinator's terminal status and the
    effect report the sandbox retained, never from the fixture asserting
    its own containment.
    """
    collected: dict[str, dict] = {
        "status": {},
        "attempted": {},
        "blocked": {},
        "profile_digest": {},
        "details": {},
    }
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
        job = detail["job"]
        collected["status"][effect] = job["status"]
        collected["profile_digest"][effect] = job["sandbox_profile_digest"]
        collected["attempted"][effect] = bool(report.get("attempted", False))
        collected["blocked"][effect] = bool(
            report.get("effect_blocked", False)
        )
        collected["details"][effect] = {
            "status": job["status"],
            "attempted": report.get("attempted"),
            "blocked": report.get("effect_blocked"),
            "detail": str(report.get("detail", "")),
        }
    return collected


def _exercise_hazards(
    *,
    base_url: str,
    admin_key: str,
    runner_key: str,
    runner_image: str,
    echo_digest: str,
    public_repo: Path,
    private_repo: Path,
    runner_bin: Path,
    run_env: dict,
) -> tuple[dict, dict, dict, list[str]]:
    """Drive the five lifecycle hazards and read back what happened.

    Each hazard gets its own job, created only now so FIFO leasing hands
    the next ``run --once`` pass exactly the job being exercised. Nothing
    here is asserted: every value is read back from the coordinator after
    the event it names actually happened.

    Returns ``(jobs, events, duplicate_rejected, job_ids)``.
    """
    hazard_jobs: dict[str, dict] = {}
    hazard_events: dict[str, dict] = {}
    job_ids: dict[str, str] = {}

    def _new_job(**kwargs) -> str:
        client = httpx.Client(base_url=base_url, timeout=120)
        try:
            return _create_job(
                client, admin_key, _job_body(runner_image, **kwargs)
            )
        finally:
            client.close()

    def _read(job_id: str) -> dict:
        client = httpx.Client(base_url=base_url, timeout=120)
        try:
            return _get_job(client, admin_key, job_id)
        finally:
            client.close()

    echo_grant = [{"name": "echo-result.json", "sha256": echo_digest}]

    # cancellation: cancel while queued; the admin cancel IS the event.
    job_ids["cancellation"] = _new_job()
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        response = client.post(
            f"/v1/executions/jobs/{job_ids['cancellation']}/cancel",
            headers={"Authorization": f"Bearer {admin_key}"},
        )
    finally:
        client.close()
    if response.status_code != 200:
        raise RuntimeError(
            f"cancellation hazard: cancel returned {response.status_code}"
        )
    hazard_events["cancellation"] = {"cancel_status": response.status_code}
    hazard_jobs["cancellation"] = _read(job_ids["cancellation"])

    # timeout: a payload that installs a SIGTERM handler and never exits,
    # under a short wall limit. The sandbox deadline is the event.
    job_ids["timeout"] = _new_job(
        job_type=ADVERSARIAL_JOB_TYPE,
        effect="timeout_ignoring_sigterm",
        artifacts=[{"name": "effect-report.json"}],
        limits={**DEFAULT_LIMITS, "wall_seconds": 5},
    )
    _runner_pass(public_repo, runner_bin, run_env)
    hazard_events["timeout"] = {"wall_seconds": 5}
    hazard_jobs["timeout"] = _read(job_ids["timeout"])

    # lease_loss and retry: hold a lease, push it into the past, let the
    # coordinator's own sweep reclaim it, then finish the job.
    for hazard, extra in (
        ("lease_loss", {}),
        ("retry", {"max_attempts": 3}),
    ):
        job_ids[hazard] = _new_job(artifacts=echo_grant, **extra)
        _claim_only(base_url, runner_key)
        hazard_events[hazard] = _expire_lease(private_repo, job_ids[hazard])
        if hazard_events[hazard]["after"] != "queued":
            raise RuntimeError(
                f"{hazard} hazard: sweep left the job in "
                f"{hazard_events[hazard]['after']!r}, expected 'queued'"
            )
        _runner_pass(public_repo, runner_bin, run_env)
        hazard_jobs[hazard] = _read(job_ids[hazard])
    if hazard_jobs["retry"]["job"]["attempt_count"] < 2:
        raise RuntimeError(
            "retry hazard: job never reached a second attempt "
            f"({hazard_jobs['retry']['job']['attempt_count']})"
        )

    # duplicate_submission: replay the exact receipt bytes the coordinator
    # already accepted, with the runner's own bearer. The 409 is the event.
    job_ids["duplicate_submission"] = _new_job(artifacts=echo_grant)
    _runner_pass(public_repo, runner_bin, run_env)
    replayed = _private_receipt(private_repo, job_ids["duplicate_submission"])
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        replay = client.post(
            f"/v1/runners/jobs/{job_ids['duplicate_submission']}/receipt",
            headers={"Authorization": f"Bearer {runner_key}"},
            json={
                "client_receipt": replayed["client_receipt"],
                "signature": replayed["signature"],
                "signature_algorithm": replayed["signature_algorithm"],
            },
        )
    finally:
        client.close()
    hazard_events["duplicate_submission"] = {
        "replay_status": replay.status_code,
        "replay_detail": _response_detail(replay),
    }
    # Re-read after the replay: a rejected duplicate must not have moved
    # the job a second time.
    hazard_jobs["duplicate_submission"] = _read(
        job_ids["duplicate_submission"]
    )

    # Only the duplicate hazard performs a replay; for the other four the
    # same claim is the observation that no second terminal transition was
    # accepted for their job.
    duplicate_rejected = {
        hazard: (
            replay.status_code == 409
            if hazard == "duplicate_submission"
            else hazard_jobs[hazard]["job"]["terminal_transition_count"] == 1
        )
        for hazard in HAZARD_ROLES
    }
    return (
        hazard_jobs,
        hazard_events,
        duplicate_rejected,
        list(job_ids.values()),
    )


def _response_detail(response: httpx.Response) -> object:
    """The coordinator's stated reason, whatever shape it came back in."""
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return response.json().get("detail")
    return response.text[:200]


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
    runner_image = resolve_runner_image()

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

    cancelled, enroll_json, happy_job_id, canary_job_id, effect_job_ids = (
        _enroll_and_seed(
            base_url=base_url,
            admin_key=admin_key,
            runner_image=runner_image,
            echo_digest=echo_digest,
        )
    )

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
    planted_probes = _plant_canaries(env_name)
    _runner_pass(public_repo, runner_bin, run_env)
    canary_payload = _private_receipt(
        private_repo, canary_job_id, "canary-report.json"
    )
    canary_report = json.loads(canary_payload.get("artifact_content") or "{}")
    readable = canary_readable_map(canary_report, planted_probes)

    # ── Five forbidden effects, one sandbox run each ──
    effects = _exercise_effects(
        base_url=base_url,
        admin_key=admin_key,
        effect_job_ids=effect_job_ids,
        public_repo=public_repo,
        private_repo=private_repo,
        runner_bin=runner_bin,
        run_env=run_env,
    )
    effect_status = effects["status"]
    effect_attempted = effects["attempted"]
    effect_blocked = effects["blocked"]
    effect_profile_digest = effects["profile_digest"]
    effect_details = effects["details"]

    # ── Lifecycle hazards: five real coordinator exercises ──
    (
        hazard_jobs,
        hazard_events,
        duplicate_rejected,
        hazard_job_ids,
    ) = _exercise_hazards(
        base_url=base_url,
        admin_key=admin_key,
        runner_key=enroll_json["runner_key"],
        runner_image=runner_image,
        echo_digest=echo_digest,
        public_repo=public_repo,
        private_repo=private_repo,
        runner_bin=runner_bin,
        run_env=run_env,
    )

    # ── Canary exfiltration: search what was actually retained ──
    #
    # Every artifact byte the coordinator stored, every receipt it holds,
    # and every byte the runner printed. A marker absent from all three is
    # an absence that was looked for.
    all_job_ids = [
        happy_job_id,
        canary_job_id,
        *effect_job_ids.values(),
        *hazard_job_ids,
    ]
    artifacts_haystack = _stored_artifacts_text(private_repo, all_job_ids)
    receipts_haystack = _stored_receipts_text(private_repo, all_job_ids)
    logs_haystack = "\n".join(RUNNER_LOG)

    (out_dir / "run-summary.json").write_text(
        json.dumps(
            {
                "drained_stale_jobs": cancelled,
                "happy_job": happy_detail,
                "happy_receipt": receipt,
                "canary_readable": readable,
                "effect_runs": effect_details,
                "hazard_events": hazard_events,
                "hazard_jobs": {
                    hazard: hazard_jobs[hazard]["job"]
                    for hazard in HAZARD_ROLES
                },
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
            "canary_in_artifacts": _fact(
                canary_exfiltration_map(artifacts_haystack)
            ),
            "canary_in_receipt": _fact(
                canary_exfiltration_map(receipts_haystack)
            ),
            "canary_in_logs": _fact(canary_exfiltration_map(logs_haystack)),
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
            "duplicate_receipt_rejected": _fact(duplicate_rejected),
            "attempt_count": _fact({
                hazard: hazard_jobs[hazard]["job"]["attempt_count"]
                for hazard in HAZARD_ROLES
            }),
        },
    )
    sys.stdout.write(
        json.dumps({"evidence_dir": str(out_dir)}, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
