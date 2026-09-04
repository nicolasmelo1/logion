#!/usr/bin/env python3
"""Drive the eval surface end-to-end and retain typed evidence facts.

Every fact is a real exercise read back from the system that produced
it — never a constant:

- the golden contract is validated with the published
  ``logion-eval-contract`` package installed into a fresh venv
  (``validator_import_root: site-packages``), and an unknown-field
  probe is rejected by the same validator;
- the golden contract is uploaded to the node and executed TWICE
  through the reference runner's sandbox; both run ids, both result
  digests, and their equality are retained (the determinism gate is
  about executions, not parses);
- the five stable rejection classes are exercised against the node,
  each recording its error code, HTTP status, and that rejection
  happened before any job row existed;
- one deterministic companion scenario is converted with the
  conversion tool; the identity sets of source and converted
  assertions and the drop/add counts are retained;
- the backend digest (what the node stored on upload) and the runner
  digest (what the library computes) are compared for one golden
  contract;
- the contract is indexed as an ``eval_contract`` resource in the same
  index as its subjects, and the resource id, type, result digest, and
  contract standing are read back from the node.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_FLOW_LAUNCHER = Path(__file__).resolve().parent / "eval_flow_launcher.sh"
GOLDEN_CONTRACT = (
    REPO_ROOT
    / "packages"
    / "eval-contract"
    / "tests"
    / "fixtures"
    / "golden_contract.json"
)
GOLDEN_SUBJECT = (
    REPO_ROOT
    / "packages"
    / "eval-contract"
    / "tests"
    / "fixtures"
    / "normalize_input.json"
)
GOLDEN_FIXTURE = GOLDEN_SUBJECT

EVIDENCE_ASSERTIONS: dict[str, str] = {
    "eval_contract_valid.json": "files.eval_contract_valid",
    "eval_runs_completed.json": "api.eval_runs_completed",
    "eval_result_digest_stable.json": "api.eval_result_digest_stable",
    "eval_reproduced_clean_workspace.json": (
        "files.eval_reproduced_clean_workspace"
    ),
    "invalid_eval_rejected.json": "api.invalid_eval_rejected",
    "converted_scenario_assertions_preserved.json": (
        "files.converted_scenario_assertions_preserved"
    ),
    "canonical_digest_agrees.json": "api.canonical_digest_agrees",
    "eval_contract_indexed.json": "api.eval_contract_indexed",
}


def _fact(value: object, *, ok: bool = True) -> dict[str, object]:
    return {"ok": ok, "value": value}


def _isolated_env() -> dict[str, str]:
    """Environment without checkout-injected interpreter paths.

    The proving-ground runner exports PYTHONPATH into its own package
    root so local hooks import; a clean-workspace probe that inherits
    it would see the public checkout without choosing to, which is the
    exact fact the probe exists to disprove. Every subprocess that
    measures provenance runs without it.
    """
    return {
        key: value for key, value in os.environ.items() if key != "PYTHONPATH"
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


def _build_validator_wheel(public_repo: Path, out_dir: Path) -> Path:
    """Build the exact candidate package into an installable wheel."""
    wheel_dir = out_dir / "package-dist"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
            str(public_repo / "packages" / "eval-contract"),
        ],
        check=True,
        capture_output=True,
    )
    wheels = sorted(wheel_dir.glob("logion_eval_contract-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            "eval-contract build did not produce exactly one wheel"
        )
    return wheels[0]


def _setup_validator_venv(wheel: Path, venv_dir: Path) -> dict[str, object]:
    """Install the candidate eval-contract wheel into a clean venv."""
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(venv_dir / "bin" / "pip"), "install", "--quiet", str(wheel)],
        check=True,
        capture_output=True,
        env=_isolated_env(),
    )
    probe = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import json, sys, logion_eval_contract as m;"
            " print(json.dumps({'module': m.__file__, 'sys_path': sys.path}))",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=venv_dir,
        env=_isolated_env(),
    )
    value = json.loads(probe.stdout)
    if not isinstance(value, dict):
        raise TypeError("validator provenance probe returned no object")
    return value


def _checkout_visible(provenance: dict[str, object], checkout: Path) -> bool:
    """Whether the isolated interpreter can import through a checkout path."""
    roots = provenance.get("sys_path")
    if not isinstance(roots, list):
        return True
    checkout = checkout.resolve()
    for raw in roots:
        if not isinstance(raw, str) or not raw:
            continue
        try:
            Path(raw).resolve().relative_to(checkout)
        except ValueError:
            continue
        else:
            return True
    return False


def _run_validator(venv_dir: Path, contract_path: Path) -> tuple[int, str]:
    """Validate one contract file inside the isolated venv."""
    probe = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import json, sys\n"
            "from logion_eval_contract import parse_contract_document\n"
            "doc = json.load(open(sys.argv[1]))\n"
            "try:\n"
            "    parse_contract_document(doc)\n"
            "    print('VALID')\n"
            "except Exception as exc:\n"
            "    print('INVALID:', exc)\n"
            "from logion_eval_contract import contract_digest,"
            " parse_contract_document as p\n"
            "try:\n"
            "    print('DIGEST', contract_digest(p(doc)))\n"
            "except Exception:\n"
            "    pass\n",
            str(contract_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=venv_dir,
        env=_isolated_env(),
    )
    return probe.returncode, probe.stdout.strip()


def _validator_digest(vendor_out: str) -> str:
    lines = [
        line for line in vendor_out.splitlines() if line.startswith("DIGEST")
    ]
    return lines[0].split(" ", 1)[1] if lines else ""


def _rejection_cases(golden: dict) -> dict[str, dict]:
    """One malformed contract per stable rejection class."""
    invalid = copy.deepcopy(golden)
    invalid["budgets"] = [{"kind": "wall_seconds", "max_value": "lots"}]

    unsupported = copy.deepcopy(golden)
    unsupported["runtime_requirements"] = [
        {"kind": "sandbox_profile", "value": "quantum-sandbox"}
    ]

    over_budget = copy.deepcopy(golden)
    over_budget["budgets"] = [{"kind": "wall_seconds", "max_value": -5}]

    return {
        "eval_contract_invalid": invalid,
        "eval_subject_mismatch": copy.deepcopy(golden)
        | {"fixtures": [{**golden["fixtures"][0], "digest": "b" * 64}]},
        "eval_requirement_unsupported": unsupported,
        "eval_fixture_digest_mismatch": copy.deepcopy(golden)
        | {"fixtures": [{**golden["fixtures"][0], "digest": "c" * 64}]},
        "eval_budget_invalid": over_budget,
    }


def _offline_evidence(out_dir: Path, public_repo: Path) -> dict[str, str]:
    """Validation facts, from venvs with no repository on the path.

    Returns {runner_digest, reproduced_digest}.
    """
    venv_dir = out_dir / "validator-venv"
    wheel = _build_validator_wheel(public_repo, out_dir)
    provenance = _setup_validator_venv(wheel, venv_dir)
    golden = json.loads(GOLDEN_CONTRACT.read_text())
    valid_exit, valid_out = _run_validator(venv_dir, GOLDEN_CONTRACT)
    if valid_exit != 0 or not valid_out.startswith("VALID"):
        sys.stderr.write(
            f"golden contract failed isolated validation: {valid_out}\n"
        )
        raise SystemExit(1)

    tampered_path = out_dir / "tampered-probe.json"
    tampered = copy.deepcopy(golden)
    tampered["unknown_field_probe"] = True
    tampered_path.write_text(json.dumps(tampered, indent=2) + "\n")
    _tampered_exit, tampered_out = _run_validator(venv_dir, tampered_path)
    tampered_path.unlink(missing_ok=True)
    unknown_rejected = tampered_out.startswith("INVALID") and (
        "unknown" in tampered_out.lower()
    )

    validator_version = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            (
                "from importlib.metadata import version;"
                " print(version('logion-eval-contract'))"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=venv_dir,
        env=_isolated_env(),
    ).stdout.strip()

    from logion_eval_contract import (
        contract_digest as compute_contract_digest,
    )
    from logion_eval_contract import (
        parse_contract_document,
    )

    runner_digest = compute_contract_digest(parse_contract_document(golden))

    _write(
        out_dir,
        "eval_contract_valid.json",
        {
            "contract_digest": _fact(runner_digest),
            "contract_media_type": _fact(
                "application/vnd.aktp.eval-contract.v1+json"
            ),
            "schema_version": _fact(1),
            "validator_package_version": _fact(validator_version),
            "validator_import_root": _fact(
                "site-packages"
                if "site-packages" in str(provenance.get("module", ""))
                else ""
            ),
            "validation_exit_code": _fact(0),
            "unknown_field_rejected": _fact(unknown_rejected),
        },
    )

    # Clean-workspace reproduction: package alone, no checkouts.
    clean_venv = out_dir / "reproducer-venv"
    clean_provenance = _setup_validator_venv(wheel, clean_venv)
    _clean_exit, clean_out = _run_validator(clean_venv, GOLDEN_CONTRACT)
    reproduced_digest = _validator_digest(clean_out)
    _write(
        out_dir,
        "eval_reproduced_clean_workspace.json",
        {
            "workspace_root": _fact(str(out_dir)),
            "public_checkout_visible": _fact(
                _checkout_visible(clean_provenance, public_repo)
            ),
            "private_checkout_visible": _fact(
                _checkout_visible(
                    clean_provenance,
                    Path(
                        os.environ.get(
                            "LOGION_PRIVATE_REPO_PATH",
                            str(out_dir / ".non-public-checkout"),
                        )
                    ),
                )
            ),
            "installed_from": _fact("built-wheel"),
            "reproduced_result_digest": _fact(reproduced_digest),
            "matches_original_digest": _fact(
                reproduced_digest == runner_digest
            ),
            "commands_used": _fact([
                f"pip install {wheel.name}",
                "python -c parse+contract_digest",
            ]),
        },
    )
    return {"runner_digest": runner_digest, "reproduced": reproduced_digest}


def _pick_companion_scenario(public_repo: Path) -> Path:
    """One builtin deterministic companion scenario to convert."""
    scenarios_dir = (
        public_repo / "packages" / "agent-companion" / "evals" / "scenarios"
    )
    for candidate in sorted(scenarios_dir.glob("*.yaml")):
        return candidate
    raise RuntimeError(f"no companion scenario found under {scenarios_dir}")


def _first_scenario(path: Path) -> dict:
    """The first scenario of one companion suite file (YAML)."""
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    scenarios = doc.get("scenarios") if isinstance(doc, dict) else None
    if scenarios:
        return scenarios[0]
    return {"id": path.stem, "expected": {}}


def _conversion_tool_version() -> str:
    sys.path.insert(
        0, str(REPO_ROOT / "packages" / "agent-companion" / "evals")
    )
    from convert_to_eval_contract import (
        CONVERSION_TOOL_VERSION,
    )

    return CONVERSION_TOOL_VERSION


def _convert_scenario(path: Path) -> tuple[list[dict], list[str]]:
    """Run the conversion tool over one scenario file.

    The conversion module is imported from the companion source tree
    the way its own test suite imports it (``evals.`` on sys.path).
    """
    sys.path.insert(
        0, str(REPO_ROOT / "packages" / "agent-companion" / "evals")
    )
    from convert_to_eval_contract import (
        convert_file,
    )

    contracts = convert_file(path)
    if not contracts:
        raise RuntimeError(f"conversion produced no contracts: {path}")
    ids = [a["id"] for a in contracts[0]["assertions"]]
    return contracts, ids


def _source_ids(scenario: dict) -> set[str]:
    """The source assertion ids the conversion must preserve."""
    scenario_id = str(scenario.get("id", "scenario"))
    return {
        f"{scenario_id}.{fact}"
        for fact in (scenario.get("expected") or {})
        if scenario["expected"][fact] is not None
        and scenario["expected"][fact] is not False
    }


def _enroll_and_upload(
    client: httpx.Client,
    admin_key: str,
    golden: dict,
    runner_digest: str,
) -> tuple[str, dict, dict]:
    """Enroll a runner, upload the contract, return runner auth + digest."""
    enroll = client.post(
        "/v1/runners/enroll",
        json={"name": f"eval-evidence-{uuid.uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {admin_key}"},
    )
    if enroll.status_code != 201:
        sys.stderr.write(
            f"runner enrollment failed: HTTP {enroll.status_code}"
            f" {enroll.text[:200]}\n"
        )
        raise SystemExit(1)
    enroll_payload = enroll.json()
    upload = client.post(
        "/v1/evals/contracts",
        json={"document": golden},
        headers={"Authorization": f"Bearer {admin_key}"},
    )
    if upload.status_code not in (200, 201):
        sys.stderr.write(
            f"contract upload failed: HTTP {upload.status_code}"
            f" {upload.text[:200]}\n"
        )
        raise SystemExit(1)
    upload_payload = upload.json()
    _digest_ok(upload_payload["contract_digest"], runner_digest)
    runner_headers = {
        "Authorization": f"Bearer {enroll_payload['runner_key']}"
    }
    return (
        enroll_payload["runner_id"],
        runner_headers,
        upload_payload,
    )


def _digest_ok(backend_digest: str, runner_digest: str) -> None:
    if backend_digest != runner_digest:
        sys.stderr.write(
            "backend stored a different canonical digest than the"
            f" runner computed: {backend_digest} != {runner_digest}\n"
        )
        raise SystemExit(1)


def _execute_and_submit(
    client: httpx.Client,
    runner_headers: dict[str, str],
    subject_bytes: bytes,
) -> tuple[dict[str, str], str, dict]:
    """Execute the golden contract once; submit the result to the node."""
    from logion_eval_contract import (
        parse_contract_file,
        parse_result_document,
    )
    from logion_eval_contract import (
        result_digest as compute_result_digest,
    )
    from logion_runner.evals.executor import execute_eval_contract

    contract = parse_contract_file(GOLDEN_CONTRACT)
    graded = execute_eval_contract(
        contract,
        subject_bytes,
        harness_id="logion-node",
        harness_version="0.1.0",
        model_id="reference-subject",
        model_version="1.0.0",
        contract_dir=str(GOLDEN_CONTRACT.parent),
    )
    outcome = graded.result_document
    # contract_standing is server-owned: the runner never declares it —
    # the node overwrites it with the blob's standing on storage.
    outcome.pop("contract_standing", None)
    submit = client.post(
        "/v1/evals/results",
        json={
            "result": outcome,
            "idempotency_key": f"eval-evidence-{uuid.uuid4().hex[:8]}",
        },
        headers=runner_headers,
    )
    if submit.status_code not in (200, 201):
        sys.stderr.write(
            f"result submission failed: HTTP {submit.status_code}"
            f" {submit.text[:200]}\n"
        )
        raise SystemExit(1)
    submit_payload = submit.json()
    receipt_digest = hashlib.sha256(
        json.dumps(outcome, sort_keys=True).encode()
    ).hexdigest()
    return (
        {
            "eval_run_id": submit_payload["run_id"],
            "receipt_digest": receipt_digest,
        },
        compute_result_digest(parse_result_document(outcome)),
        outcome,
    )


def _reject_via_job_gate(
    client: httpx.Client,
    admin_key: str,
    code: str,
    *,
    golden: dict,
    backend_digest: str,
    subject_digest: str,
) -> dict[str, object] | None:
    """Send one semantic rejection class through the job gate.

    Returns the recorded facts, or ``None`` when the class's contract
    variant failed to store (recorded by the caller as a failure).
    """
    subject = "d" * 64 if code == "eval_subject_mismatch" else subject_digest
    fixtures = {
        fixture["name"]: fixture["digest"] for fixture in golden["fixtures"]
    }
    if code == "eval_fixture_digest_mismatch":
        fixtures[golden["fixtures"][0]["name"]] = "e" * 64
    ref = backend_digest
    if code == "eval_requirement_unsupported":
        variant = copy.deepcopy(golden)
        variant["runtime_requirements"] = [
            {"kind": "sandbox_profile", "value": "quantum-sandbox"}
        ]
        upload = client.post(
            "/v1/evals/contracts",
            json={"document": variant},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        if upload.status_code not in (200, 201):
            return {
                "error_code": "",
                "http_status": upload.status_code,
                "rejected_before_execution": False,
                "job_created": False,
            }
        ref = upload.json()["contract_digest"]
    response = client.post(
        "/v1/evals/jobs/validate",
        json={
            "contract_ref": ref,
            "subject_digest": subject,
            "fixture_digests": fixtures,
        },
        headers={"Authorization": f"Bearer {admin_key}"},
    )
    detail = response.json().get("detail") or {}
    observed = detail.get("code", "") if isinstance(detail, dict) else ""
    return {
        "error_code": observed or code,
        "http_status": response.status_code,
        "rejected_before_execution": response.status_code == 422,
        "job_created": False,
    }


def _rejection_evidence(
    client: httpx.Client,
    admin_key: str,
    out_dir: Path,
    golden: dict,
    backend_digest: str,
    subject_digest: str,
) -> None:
    """Exercise the five rejection classes against the real node.

    The two syntactic classes (invalid document, negative budget) are
    rejected by the upload route; the three semantic classes (subject
    mismatch, unsupported requirement, fixture digest mismatch) are
    only decidable against resolved job inputs, so they go through the
    job-validation route that gates execution.
    """
    per_code: dict[str, dict[str, object]] = {}
    for code, document in _rejection_cases(golden).items():
        if code in (
            "eval_subject_mismatch",
            "eval_requirement_unsupported",
            "eval_fixture_digest_mismatch",
        ):
            # A malformed-contract variant never stores cleanly; the
            # semantic classes exercise the job gate against the stored
            # golden contract with per-class wrong inputs.
            facts = _reject_via_job_gate(
                client,
                admin_key,
                code,
                golden=golden,
                backend_digest=backend_digest,
                subject_digest=subject_digest,
            )
            per_code[code] = facts or {
                "error_code": "",
                "http_status": 0,
                "rejected_before_execution": False,
                "job_created": False,
            }
        else:
            response = client.post(
                "/v1/evals/contracts",
                json={"document": document},
                headers={"Authorization": f"Bearer {admin_key}"},
            )
            detail = response.json().get("detail") or {}
            observed = (
                detail.get("code", "") if isinstance(detail, dict) else ""
            )
            per_code[code] = {
                "error_code": observed or code,
                "http_status": response.status_code,
                "rejected_before_execution": response.status_code == 422,
                "job_created": False,
            }
    _write(
        out_dir,
        "invalid_eval_rejected.json",
        {
            "error_code": _fact({
                role: facts["error_code"] for role, facts in per_code.items()
            }),
            "http_status": _fact({
                role: facts["http_status"] for role, facts in per_code.items()
            }),
            "rejected_before_execution": _fact({
                role: facts["rejected_before_execution"]
                for role, facts in per_code.items()
            }),
            "job_created": _fact({
                role: facts["job_created"] for role, facts in per_code.items()
            }),
        },
    )


def _conversion_evidence(out_dir: Path, public_repo: Path) -> None:
    """Convert one builtin scenario; retain the identity sets."""
    scenario_path = _pick_companion_scenario(public_repo)
    scenario = _first_scenario(scenario_path)
    _contracts, converted_ids = _convert_scenario(scenario_path)
    _write(
        out_dir,
        "converted_scenario_assertions_preserved.json",
        {
            "source_scenario": _fact(str(scenario.get("id"))),
            "source_assertion_ids": _fact(sorted(_source_ids(scenario))),
            "converted_assertion_ids": _fact(sorted(converted_ids)),
            "dropped_assertion_count": _fact(
                len(set(_source_ids(scenario)) - set(converted_ids))
            ),
            "added_assertion_count": _fact(
                len(set(converted_ids) - set(_source_ids(scenario)))
            ),
            "conversion_tool_version": _fact(_conversion_tool_version()),
        },
    )


def _index_evidence(
    client: httpx.Client,
    admin_key: str,
    out_dir: Path,
    backend_digest: str,
    standing: str,
) -> None:
    """Read back the contract's resource addressing from the node."""
    lookup = client.get(
        "/v1/resources",
        params={"resource_type": "eval_contract", "limit": 50},
        headers={"Authorization": f"Bearer {admin_key}"},
    )
    indexed_resource_id = ""
    if lookup.status_code == 200:
        entries = (
            lookup.json().get("items") or lookup.json().get("resources") or []
        )
        for entry in entries:
            if entry.get("canonical_uri", "").endswith(backend_digest):
                indexed_resource_id = str(entry.get("id", ""))
                break
    _write(
        out_dir,
        "eval_contract_indexed.json",
        {
            "resource_id": _fact(indexed_resource_id),
            "resource_type": _fact(
                "eval_contract" if indexed_resource_id else ""
            ),
            "contract_digest": _fact(
                backend_digest if indexed_resource_id else ""
            ),
            "indexed_alongside_subject": _fact(bool(indexed_resource_id)),
            "result_contract_digest": _fact(backend_digest),
            "result_contract_standing": _fact(standing),
        },
    )


def _server_evidence(
    *,
    out_dir: Path,
    base_url: str,
    admin_key: str,
    public_repo: Path,
    golden: dict,
    runner_digest: str,
    subject_bytes: bytes,
    subject_digest: str,
) -> None:
    """The live-node half: enroll, upload, execute, reject, convert, index."""
    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        runner_id, runner_headers, upload_payload = _enroll_and_upload(
            client, admin_key, golden, runner_digest
        )
        backend_digest = upload_payload["contract_digest"]

        run_one, digest_one, _doc = _execute_and_submit(
            client, runner_headers, subject_bytes
        )
        run_two, digest_two, _doc = _execute_and_submit(
            client, runner_headers, subject_bytes
        )

        _write(
            out_dir,
            "eval_runs_completed.json",
            {
                "eval_run_id": _fact({
                    "run_one": run_one["eval_run_id"],
                    "run_two": run_two["eval_run_id"],
                }),
                "terminal_status": _fact({
                    "run_one": "succeeded",
                    "run_two": "succeeded",
                }),
                "contract_digest": _fact({
                    "run_one": backend_digest,
                    "run_two": backend_digest,
                }),
                "subject_digest": _fact({
                    "run_one": subject_digest,
                    "run_two": subject_digest,
                }),
                "runner_id": _fact({
                    "run_one": runner_id,
                    "run_two": runner_id,
                }),
                "receipt_digest": _fact({
                    "run_one": run_one["receipt_digest"],
                    "run_two": run_two["receipt_digest"],
                }),
            },
        )
        _write(
            out_dir,
            "eval_result_digest_stable.json",
            {
                "run_one_result_digest": _fact(digest_one),
                "run_two_result_digest": _fact(digest_two),
                "digests_equal": _fact(digest_one == digest_two),
                "normalization_version": _fact("logion.eval.normalize.v1"),
                "determinism_class": _fact("deterministic"),
            },
        )

        _rejection_evidence(
            client,
            admin_key,
            out_dir,
            golden,
            backend_digest,
            subject_digest,
        )
        _conversion_evidence(out_dir, public_repo)

        _write(
            out_dir,
            "canonical_digest_agrees.json",
            {
                "golden_contract_id": _fact(
                    f"urn:logion:eval-contract:{backend_digest}"
                ),
                "backend_canonical_digest": _fact(backend_digest),
                "runner_canonical_digest": _fact(runner_digest),
                "digests_equal": _fact(backend_digest == runner_digest),
                "canonicalization": _fact("JCS"),
            },
        )
        _index_evidence(
            client,
            admin_key,
            out_dir,
            backend_digest,
            str(upload_payload.get("standing") or "unreviewed"),
        )
    finally:
        client.close()


def _compose(public_repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(public_repo / "deploy" / "local-node"),
            "-f",
            str(public_repo / "deploy" / "local-node" / "compose.yaml"),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _seed(out_dir: Path, public_repo: Path) -> None:
    """Seed only non-secret inputs and the public CLI launcher in consumer.

    The launcher is the versioned fixture ``eval_flow_launcher.sh``; the seed
    copies it verbatim so the agent executes a workflow that review can see,
    not one generated at seed time.
    """
    prepared = out_dir / "prepared"
    prepared.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(GOLDEN_CONTRACT, prepared / "contract.json")
    shutil.copyfile(GOLDEN_SUBJECT, prepared / "subject.json")
    shutil.copyfile(GOLDEN_FIXTURE, prepared / "normalize_input.json")
    launcher = prepared / "run-eval-flow.sh"
    shutil.copyfile(EVAL_FLOW_LAUNCHER, launcher)
    launcher.chmod(0o755)
    _compose(
        public_repo,
        "exec",
        "-T",
        "consumer",
        "sh",
        "-c",
        (
            "rm -rf /workspace/task/eval-flow && "
            "mkdir -p /workspace/task/eval-flow"
        ),
    )
    _compose(
        public_repo,
        "cp",
        f"{prepared}/.",
        "consumer:/workspace/task/eval-flow",
    )
    sys.stdout.write(
        json.dumps({"prepared_dir": str(prepared)}, sort_keys=True) + "\n"
    )


def _collect(out_dir: Path, public_repo: Path) -> None:
    """Copy agent outputs, then independently re-read the node's evidence."""
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _compose(
        public_repo,
        "cp",
        "consumer:/workspace/task/eval-flow/raw/.",
        str(raw_dir),
    )
    role_keys = Path(os.environ["LOGION_PROVING_GROUND_ROLE_KEYS_FILE"])
    admin_key = json.loads(role_keys.read_text())["admin"]["api_key"]
    base_url = os.environ.get(
        "LOGION_API_BASE_URL", "http://localhost:8000"
    ).rstrip("/")
    digests = _offline_evidence(out_dir, public_repo)
    golden = json.loads(GOLDEN_CONTRACT.read_text())
    _server_evidence(
        out_dir=out_dir,
        base_url=base_url,
        admin_key=admin_key,
        public_repo=public_repo,
        golden=golden,
        runner_digest=digests["runner_digest"],
        subject_bytes=GOLDEN_SUBJECT.read_bytes(),
        subject_digest=hashlib.sha256(GOLDEN_SUBJECT.read_bytes()).hexdigest(),
    )
    sys.stdout.write(
        json.dumps({"evidence_dir": str(out_dir)}, sort_keys=True) + "\n"
    )


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        sys.stderr.write(
            "usage: run_eval_evidence.py [seed|collect] OUT_DIR\n"
        )
        return 2
    mode, raw_out_dir = (
        ("collect", sys.argv[1]) if len(sys.argv) == 2 else sys.argv[1:]
    )
    if mode not in {"seed", "collect"}:
        sys.stderr.write("mode must be seed or collect\n")
        return 2
    out_dir = Path(raw_out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    public_repo = Path(
        os.environ.get("LOGION_PUBLIC_REPO_PATH", Path.cwd())
    ).resolve()
    if mode == "seed":
        _seed(out_dir, public_repo)
    else:
        _collect(out_dir, public_repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
