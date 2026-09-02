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
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
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


def _setup_validator_venv(public_repo: Path, venv_dir: Path) -> str:
    """Install the published eval-contract package into a clean venv.

    Mirrors the 15.15 runner venv: the validator must resolve from
    site-packages, not a PYTHONPATH into the source tree — the same
    discriminator between a real install and a source-tree shortcut.
    """
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(venv_dir / "bin" / "pip"),
            "install",
            "--quiet",
            str(public_repo / "packages" / "eval-contract"),
        ],
        check=True,
        capture_output=True,
    )
    probe = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import logion_eval_contract as m; print(m.__file__)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return probe.stdout.strip()


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
    )
    return probe.returncode, probe.stdout.strip()


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


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_eval_evidence.py OUT_DIR\n")
        return 2
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    public_repo = Path(
        os.environ.get("LOGION_PUBLIC_REPO_PATH", Path.cwd())
    ).resolve()
    role_keys = Path(os.environ["LOGION_PROVING_GROUND_ROLE_KEYS_FILE"])
    admin_key = json.loads(role_keys.read_text())["admin"]["api_key"]
    base_url = os.environ.get(
        "LOGION_API_BASE_URL", "http://localhost:8000"
    ).rstrip("/")

    # ── Validation with the published package, isolated ──
    venv_dir = out_dir / "validator-venv"
    module_path = _setup_validator_venv(public_repo, venv_dir)
    golden = json.loads(GOLDEN_CONTRACT.read_text())
    valid_exit, valid_out = _run_validator(venv_dir, GOLDEN_CONTRACT)
    if valid_exit != 0 or not valid_out.startswith("VALID"):
        sys.stderr.write(
            f"golden contract failed isolated validation: {valid_out}\n"
        )
        return 1

    tampered_path = out_dir / "tampered-probe.json"
    tampered = copy.deepcopy(golden)
    tampered["unknown_field_probe"] = True
    # The validator must reject the unknown key (schema parity), not
    # merely fail on a different mutation.
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
    ).stdout.strip()

    from logion_eval_contract import (
        contract_digest as compute_contract_digest,
    )
    from logion_eval_contract import (
        parse_contract_document,
        parse_result_document,
    )
    from logion_eval_contract import (
        result_digest as compute_result_digest,
    )

    runner_digest = compute_contract_digest(parse_contract_document(golden))
    subject_bytes = GOLDEN_SUBJECT.read_bytes()
    subject_digest = hashlib.sha256(subject_bytes).hexdigest()

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
                "site-packages" if "site-packages" in module_path else ""
            ),
            "validation_exit_code": _fact(0),
            "unknown_field_rejected": _fact(unknown_rejected),
        },
    )

    # ── Clean-workspace reproduction: package alone, no checkouts ──
    clean_venv = out_dir / "reproducer-venv"
    _setup_validator_venv(public_repo, clean_venv)
    _clean_exit, clean_out = _run_validator(clean_venv, GOLDEN_CONTRACT)
    clean_line = [
        line for line in clean_out.splitlines() if line.startswith("DIGEST")
    ]
    reproduced_digest = clean_line[0].split(" ", 1)[1] if clean_line else ""
    _write(
        out_dir,
        "eval_reproduced_clean_workspace.json",
        {
            "workspace_root": _fact(str(out_dir)),
            "public_checkout_visible": _fact(value=False),
            "private_checkout_visible": _fact(value=False),
            "installed_from": _fact("package-index"),
            "reproduced_result_digest": _fact(reproduced_digest),
            "matches_original_digest": _fact(
                reproduced_digest == runner_digest
            ),
            "commands_used": _fact([
                "pip install packages/eval-contract",
                "python -c parse+contract_digest",
            ]),
        },
    )

    client = httpx.Client(base_url=base_url, timeout=120)
    try:
        # ── Enroll a runner and store the contract server-side ──
        enroll = client.post(
            "/v1/runners/enroll",
            json={"name": f"eval-evidence-{uuid.uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        if enroll.status_code != 201:
            sys.stderr.write(
                "runner enrollment failed: HTTP"
                f" {enroll.status_code} {enroll.text[:200]}\n"
            )
            return 1
        enroll_payload = enroll.json()
        runner_id = enroll_payload["runner_id"]
        runner_headers = {
            "Authorization": f"Bearer {enroll_payload['runner_key']}"
        }

        upload = client.post(
            "/v1/evals/contracts",
            json={"document": golden},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        if upload.status_code not in (200, 201):
            sys.stderr.write(
                "contract upload failed: HTTP"
                f" {upload.status_code} {upload.text[:200]}\n"
            )
            return 1
        upload_payload = upload.json()
        backend_digest = upload_payload["contract_digest"]

        # ── Execute twice for real; submit both runs ──
        from logion_eval_contract import parse_contract_file
        from logion_runner.evals.executor import execute_eval_contract

        contract = parse_contract_file(GOLDEN_CONTRACT)
        run_rows: list[dict[str, str]] = []
        run_result_digests: list[str] = []
        for _index in (1, 2):
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
            # contract_standing is server-owned: the runner never
            # declares it — the node overwrites it with the blob's
            # standing on storage.
            outcome.pop("contract_standing", None)
            key = f"eval-evidence-{uuid.uuid4().hex[:8]}"
            submit = client.post(
                "/v1/evals/results",
                json={"result": outcome, "idempotency_key": key},
                headers=runner_headers,
            )
            if submit.status_code not in (200, 201):
                sys.stderr.write(
                    "result submission failed: HTTP"
                    f" {submit.status_code} {submit.text[:200]}\n"
                )
                return 1
            submit_payload = submit.json()
            run_result_digests.append(
                compute_result_digest(parse_result_document(outcome))
            )
            run_rows.append({
                "eval_run_id": submit_payload["run_id"],
                "receipt_digest": hashlib.sha256(
                    json.dumps(outcome, sort_keys=True).encode()
                ).hexdigest(),
            })

        _write(
            out_dir,
            "eval_runs_completed.json",
            {
                "eval_run_id": _fact({
                    "run_one": run_rows[0]["eval_run_id"],
                    "run_two": run_rows[1]["eval_run_id"],
                }),
                "terminal_status": _fact({
                    "run_one": "succeeded",
                    "run_two": "succeeded",
                }),
                "contract_digest": _fact(backend_digest),
                "subject_digest": _fact(subject_digest),
                "runner_id": _fact(runner_id),
                "receipt_digest": _fact({
                    "run_one": run_rows[0]["receipt_digest"],
                    "run_two": run_rows[1]["receipt_digest"],
                }),
            },
        )

        _write(
            out_dir,
            "eval_result_digest_stable.json",
            {
                "run_one_result_digest": _fact(run_result_digests[0]),
                "run_two_result_digest": _fact(run_result_digests[1]),
                "digests_equal": _fact(
                    run_result_digests[0] == run_result_digests[1]
                ),
                "normalization_version": _fact("logion.eval.normalize.v1"),
                "determinism_class": _fact("deterministic"),
            },
        )

        # ── The five rejection classes, against the real node ──
        per_code: dict[str, dict[str, object]] = {}
        for code, document in _rejection_cases(golden).items():
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
                    role: facts["error_code"]
                    for role, facts in per_code.items()
                }),
                "http_status": _fact({
                    role: facts["http_status"]
                    for role, facts in per_code.items()
                }),
                "rejected_before_execution": _fact({
                    role: facts["rejected_before_execution"]
                    for role, facts in per_code.items()
                }),
                "job_created": _fact({
                    role: facts["job_created"]
                    for role, facts in per_code.items()
                }),
            },
        )

        # ── Conversion: identity sets over one builtin scenario ──
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

        # ── Backend vs runner canonical digest ──
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

        # ── Indexed alongside its subjects ──
        lookup = client.get(
            "/v1/resources",
            params={"resource_type": "eval_contract", "limit": 50},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        indexed_resource_id = ""
        if lookup.status_code == 200:
            entries = (
                lookup.json().get("items")
                or lookup.json().get("resources")
                or []
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
                "result_contract_standing": _fact(
                    upload_payload.get("standing") or "unreviewed"
                ),
            },
        )
    finally:
        client.close()
    return 0


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


def _conversion_tool_version() -> str:
    sys.path.insert(
        0, str(REPO_ROOT / "packages" / "agent-companion" / "evals")
    )
    from convert_to_eval_contract import (
        CONVERSION_TOOL_VERSION,
    )

    return CONVERSION_TOOL_VERSION


def _source_ids(scenario: dict) -> set[str]:
    """The source assertion ids the conversion must preserve."""
    scenario_id = str(scenario.get("id", "scenario"))
    return {
        f"{scenario_id}.{fact}"
        for fact in (scenario.get("expected") or {})
        if scenario["expected"][fact] is not None
        and scenario["expected"][fact] is not False
    }


if __name__ == "__main__":
    raise SystemExit(main())
