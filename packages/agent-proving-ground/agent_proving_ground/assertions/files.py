from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.artifacts import resolve_artifact_path
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


def _resolve_pending_artifact(artifacts_dir: Path, path: str) -> Path:
    raw_target = Path(path)
    if not raw_target.is_absolute():
        return resolve_artifact_path(artifacts_dir, path)
    target = raw_target.resolve()
    target.relative_to(artifacts_dir.resolve())
    return target


class FileExistsAssertion(Assertion):
    type = "files.exists"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        try:
            target = resolve_artifact_path(ctx.artifacts_dir, path)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"path": path},
            )
        if target.exists():
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=f"file exists: {path}",
                evidence={"path": str(target)},
            )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=f"file missing: {path}",
            evidence={"path": str(target)},
        )


class UsagePendingEmptyAssertion(Assertion):
    type = "files.usage_pending_empty"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        path = params.get("path")
        if not path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing path parameter",
                evidence=params,
            )
        try:
            target = _resolve_pending_artifact(ctx.artifacts_dir, path)
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid pending usage artifact: {exc}",
                evidence={"path": str(path)},
            )
        items = payload.get("data") if isinstance(payload, dict) else None
        passed = items == []
        return AssertionOutcome(
            type=self.type,
            status="passed" if passed else "failed",
            message=(
                "isolated usage spool is empty"
                if passed
                else "isolated usage spool contains observations"
            ),
            evidence={
                "path": str(target),
                "pending_count": (
                    len(items) if isinstance(items, list) else None
                ),
            },
        )


class ObservationFromLiveHookAssertion(Assertion):
    """Prove the recorded observation came from the harness, not a replay.

    Every other observation assertion is satisfied by piping a recorded
    payload into the hook command by hand, which proves the CLI parses a
    payload and nothing about whether a harness ever delivered one. The
    shim on the agent's PATH keeps the stdin of the invocation that
    actually recorded an observation; a payload the harness produced names
    a transcript that exists on this machine, while a checked-in fixture
    carries placeholder paths that resolve nowhere.
    """

    type = "files.observation_from_live_hook"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        raw_dir = params.get("invocations_dir")
        if not raw_dir:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing invocations_dir parameter",
                evidence=params,
            )
        try:
            records_dir = _resolve_pending_artifact(
                ctx.artifacts_dir, str(raw_dir)
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"invocations_dir": str(raw_dir)},
            )
        attempts = sorted(records_dir.glob("*.stdin.json"))
        recorded = records_dir / "recorded.stdin.json"
        if not recorded.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "no hook invocation recorded an observation"
                    if attempts
                    else "the harness never ran the installed hook"
                ),
                evidence={
                    "invocations_dir": str(records_dir),
                    "invocations": len(attempts),
                },
            )
        reason = _live_hook_verdict(recorded)
        return AssertionOutcome(
            type=self.type,
            status="failed" if reason else "passed",
            message=(
                f"recorded observation is not from a live hook: {reason}"
                if reason
                else "the harness delivered the payload that was recorded"
            ),
            evidence={
                "payload": str(recorded),
                "invocations": len(attempts),
            },
        )


class InstrumentationProfileValidAssertion(Assertion):
    """Assert the generated instrumentation profile validates.

    Reads ``.logion/instrumentation.json`` from each projection under
    the given ``projection_root``, validates it is well-formed JSON with
    the expected schema version, and confirms the profile digest stored
    in the projection's receipt matches a recomputed canonical digest.
    """

    type = "files.instrumentation_profile_valid"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        projection_root = params.get("projection_root")
        evidence_dir = params.get("evidence_dir")
        if not projection_root:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing projection_root parameter",
                evidence=params,
            )
        try:
            root = resolve_artifact_path(ctx.artifacts_dir, projection_root)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"projection_root": str(projection_root)},
            )
        if not root.is_dir():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"projection root does not exist: {root}",
                evidence={"projection_root": str(root)},
            )
        profiles_found, mismatches = self._scan_profiles(root)
        if profiles_found == 0:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "no instrumentation profiles found under projection root"
                ),
                evidence={"projection_root": str(root)},
            )
        if mismatches:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"profile validation failed: {mismatches}",
                evidence={
                    "projection_root": str(root),
                    "profiles_found": profiles_found,
                    "mismatches": mismatches,
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=f"{profiles_found} instrumentation profiles validate",
            evidence={
                "projection_root": str(root),
                "profiles_found": profiles_found,
                "evidence_dir": str(evidence_dir) if evidence_dir else None,
            },
        )

    @staticmethod
    def _scan_profiles(
        root: Path,
    ) -> tuple[int, list[str]]:
        """Scan projection directories for instrumentation profiles."""
        profiles_found = 0
        mismatches: list[str] = []
        for target_dir in sorted(root.iterdir()):
            if not target_dir.is_dir():
                continue
            for proj_dir in sorted(target_dir.iterdir()):
                if not proj_dir.is_dir():
                    continue
                profile_path = proj_dir / ".logion" / "instrumentation.json"
                if not profile_path.is_file():
                    continue
                profiles_found += 1
                try:
                    payload = json.loads(
                        profile_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    mismatches.append(f"{profile_path.name}: {exc}")
                    continue
                if not isinstance(payload, dict):
                    mismatches.append(f"{profile_path.name}: not an object")
                    continue
                schema = payload.get("schema")
                if schema != "logion.instrumentation.v1":
                    mismatches.append(
                        f"{profile_path.name}: schema is {schema!r}"
                    )
        return profiles_found, mismatches


class NativeProjectionDigestMatchesAssertion(Assertion):
    """Assert the portable core inside the projection is byte-identical.

    Compares the ``plugin.json`` (portable core) and the publisher's
    ``SKILL.md`` artifact between the publisher's projection tree and
    the installed copy, proving the projection was copied, not rewritten.
    """

    type = "files.native_projection_digest_matches"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        publisher_projection = params.get("publisher_projection")
        installed_projection = params.get("installed_projection")
        if not publisher_projection or not installed_projection:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing publisher_projection or installed_projection",
                evidence=params,
            )
        try:
            pub_root = resolve_artifact_path(
                ctx.artifacts_dir, publisher_projection
            )
            inst_root = resolve_artifact_path(
                ctx.artifacts_dir, installed_projection
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence=params,
            )
        if not pub_root.is_dir():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"publisher projection missing: {pub_root}",
                evidence=params,
            )
        if not inst_root.is_dir():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"installed projection missing: {inst_root}",
                evidence=params,
            )
        mismatches, checked = self._compare_core_files(pub_root, inst_root)
        if mismatches:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"portable core is not byte-identical: {mismatches}",
                evidence={
                    "publisher_projection": str(pub_root),
                    "installed_projection": str(inst_root),
                    "mismatches": mismatches,
                    "files_checked": checked,
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=f"portable core is byte-identical across {checked} files",
            evidence={
                "publisher_projection": str(pub_root),
                "installed_projection": str(inst_root),
                "files_checked": checked,
            },
        )

    @staticmethod
    def _compare_core_files(
        pub_root: Path, inst_root: Path
    ) -> tuple[list[str], int]:
        """Compare portable core files by SHA-256 digest."""
        import hashlib

        def _file_digest(path: Path) -> str | None:
            if not path.is_file():
                return None
            return hashlib.sha256(path.read_bytes()).hexdigest()

        core_files = ["plugin.json"]
        # Also compare SKILL.md under skills/*/SKILL.md
        pub_skills = list(pub_root.glob("skills/*/SKILL.md"))
        if pub_skills:
            rel = pub_skills[0].relative_to(pub_root)
            core_files.append(str(rel))

        mismatches: list[str] = []
        checked = 0
        for core_rel in core_files:
            pub_digest = _file_digest(pub_root / core_rel)
            inst_digest = _file_digest(inst_root / core_rel)
            if pub_digest is None:
                mismatches.append(f"{core_rel}: missing in publisher")
                continue
            if inst_digest is None:
                mismatches.append(f"{core_rel}: missing in installed")
                continue
            checked += 1
            if pub_digest != inst_digest:
                mismatches.append(
                    f"{core_rel}: digest mismatch "
                    f"{pub_digest[:12]} != {inst_digest[:12]}"
                )
        return mismatches, checked


class ConsentRecordedBeforeObservationAssertion(Assertion):
    """Assert consent.json mtime and content precede any spool entry.

    The consent record must exist, must carry an ``accepted`` or
    ``allowed`` decision, and its mtime must precede any file in the
    spool directory. An observation written before consent is a
    privacy violation, not a timing detail.
    """

    type = "files.consent_recorded_before_observation"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        consent_path = params.get("consent_path")
        spool_dir = params.get("spool_dir")
        if not consent_path or not spool_dir:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing consent_path or spool_dir",
                evidence=params,
            )
        try:
            consent = resolve_artifact_path(ctx.artifacts_dir, consent_path)
            spool = resolve_artifact_path(ctx.artifacts_dir, spool_dir)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence=params,
            )
        if not consent.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"consent record missing: {consent}",
                evidence={"consent_path": str(consent)},
            )
        try:
            payload = json.loads(consent.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid consent record: {exc}",
                evidence={"consent_path": str(consent)},
            )
        if not isinstance(payload, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="consent record is not a JSON object",
                evidence={"consent_path": str(consent)},
            )
        decision = payload.get("decision") or payload.get("status")
        if decision not in ("accepted", "allowed", "granted"):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"consent decision is {decision!r}, not accepted/allowed"
                ),
                evidence={"consent_path": str(consent), "decision": decision},
            )
        consent_mtime = consent.stat().st_mtime
        spool_entries: list[Path] = []
        if spool.is_dir():
            spool_entries = sorted(p for p in spool.rglob("*") if p.is_file())
        violations: list[str] = []
        for entry in spool_entries:
            if entry.stat().st_mtime < consent_mtime:
                violations.append(
                    f"{entry.name}: mtime precedes consent "
                    f"({entry.stat().st_mtime} < {consent_mtime})"
                )
        if violations:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "spool entries exist before consent was recorded: "
                    f"{violations}"
                ),
                evidence={
                    "consent_path": str(consent),
                    "consent_mtime": consent_mtime,
                    "violations": violations,
                    "spool_entry_count": len(spool_entries),
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=(
                "consent recorded before any observation; "
                f"{len(spool_entries)} spool entries"
            ),
            evidence={
                "consent_path": str(consent),
                "consent_mtime": consent_mtime,
                "decision": decision,
                "spool_entry_count": len(spool_entries),
            },
        )


class NoFullCliInstalledAssertion(Assertion):
    """Assert no ``logion`` binary on the consumer's PATH, home, or workspace.

    The entire point of projections is that an end user never needs the
    Logion CLI. Finding one means either the consumer installed it
    (against instructions) or the rig leaked it into the environment.
    """

    type = "files.no_full_cli_installed"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        workspace = params.get("workspace")
        home = params.get("home")
        if not workspace:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing workspace parameter",
                evidence=params,
            )
        try:
            ws_root = resolve_artifact_path(ctx.artifacts_dir, workspace)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence=params,
            )
        findings = self._scan_for_logion_cli(ws_root, home, ctx.artifacts_dir)
        if findings:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"logion CLI found in consumer environment: {findings}"
                ),
                evidence={"findings": findings},
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message="no logion CLI found on PATH, in home, or workspace",
            evidence={"workspace": str(ws_root)},
        )

    @staticmethod
    def _scan_for_logion_cli(
        ws_root: Path, home: str | None, artifacts_dir: Path
    ) -> list[str]:
        """Search PATH, workspace, and home for a logion binary."""
        import shutil

        findings: list[str] = []
        # Check PATH
        path_logion = shutil.which("logion")
        if path_logion:
            findings.append(f"PATH: {path_logion}")
        # Check workspace for a logion binary or script
        if ws_root.is_dir():
            for name in ("logion", "logion-cli"):
                candidate = ws_root / name
                if candidate.exists():
                    findings.append(f"workspace: {candidate}")
        # Check home directory
        if home:
            try:
                home_root = resolve_artifact_path(artifacts_dir, home)
            except ValueError:
                home_root = Path(home)
            if home_root.is_dir():
                for name in ("logion", "bin/logion"):
                    candidate = home_root / name
                    if candidate.exists():
                        findings.append(f"home: {candidate}")
        return findings


class ResourceWorksWhenDisabledAssertion(Assertion):
    """Assert the skill's own output artifact exists in the disabled leg.

    Disabling telemetry must never prevent normal resource use. The
    skill's output file is the proof it still works.
    """

    type = "files.resource_works_when_disabled"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        output_artifact = params.get("output_artifact")
        if not output_artifact:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing output_artifact parameter",
                evidence=params,
            )
        try:
            output = resolve_artifact_path(ctx.artifacts_dir, output_artifact)
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"output_artifact": str(output_artifact)},
            )
        if not output.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"skill output artifact missing: {output}",
                evidence={"output_artifact": str(output)},
            )
        content = output.read_text(encoding="utf-8")
        if not content.strip():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"skill output artifact is empty: {output}",
                evidence={"output_artifact": str(output)},
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message="skill produced output with telemetry disabled",
            evidence={
                "output_artifact": str(output),
                "output_size": len(content),
            },
        )


class PublisherObservationUnsupportedDeclaredAssertion(Assertion):
    """Assert capability.json says ``unsupported`` with a reason, spool absent.

    A projection with no pinned client hook, or no available reporter
    runtime, must declare ``publisher_observation_unsupported``, keep
    the resource fully functional, and emit no event.
    """

    type = "files.publisher_observation_unsupported_declared"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        capability_path = params.get("capability_path")
        spool_dir = params.get("spool_dir")
        if not capability_path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing capability_path parameter",
                evidence=params,
            )
        try:
            cap_file = resolve_artifact_path(
                ctx.artifacts_dir, capability_path
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"capability_path": str(capability_path)},
            )
        if not cap_file.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"capability.json missing: {cap_file}",
                evidence={"capability_path": str(cap_file)},
            )
        try:
            payload = json.loads(cap_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid capability.json: {exc}",
                evidence={"capability_path": str(cap_file)},
            )
        if not isinstance(payload, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="capability.json is not a JSON object",
                evidence={"capability_path": str(cap_file)},
            )
        tier = payload.get("tier")
        reason = payload.get("reason")
        if tier != "unsupported":
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"capability tier is {tier!r}, not 'unsupported'",
                evidence={"capability_path": str(cap_file), "tier": tier},
            )
        if not reason:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "capability.json declares unsupported but gives no reason"
                ),
                evidence={"capability_path": str(cap_file), "tier": tier},
            )
        # Spool must be absent or empty
        spool_entries: list[Path] = []
        if spool_dir:
            try:
                spool = resolve_artifact_path(ctx.artifacts_dir, spool_dir)
            except ValueError:
                spool = Path(str(spool_dir))
            if spool.is_dir():
                spool_entries = [p for p in spool.rglob("*") if p.is_file()]
        if spool_entries:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"spool is not absent: {len(spool_entries)} entries found"
                ),
                evidence={
                    "capability_path": str(cap_file),
                    "tier": tier,
                    "reason": reason,
                    "spool_entry_count": len(spool_entries),
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=(
                "capability declares unsupported with reason "
                f"({reason!r}) and spool is absent"
            ),
            evidence={
                "capability_path": str(cap_file),
                "tier": tier,
                "reason": reason,
                "spool_entry_count": 0,
            },
        )


class CapabilityClaimsFailClosedOnDriftAssertion(Assertion):
    """Assert after drift the tier is ``unsupported`` and no new event exists.

    When the pinned client release or hook contract drifts from the
    recorded fixture, the capability claim must fail closed to
    ``unsupported`` instead of falling back to inferred telemetry.
    """

    type = "files.capability_claims_fail_closed_on_drift"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        capability_path = params.get("capability_path")
        spool_dir = params.get("spool_dir")
        if not capability_path:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing capability_path parameter",
                evidence=params,
            )
        try:
            cap_file = resolve_artifact_path(
                ctx.artifacts_dir, capability_path
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"capability_path": str(capability_path)},
            )
        if not cap_file.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"drifted capability.json missing: {cap_file}",
                evidence={"capability_path": str(cap_file)},
            )
        try:
            payload = json.loads(cap_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid capability.json: {exc}",
                evidence={"capability_path": str(cap_file)},
            )
        if not isinstance(payload, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="capability.json is not a JSON object",
                evidence={"capability_path": str(cap_file)},
            )
        tier = payload.get("tier")
        reason = payload.get("reason")
        if tier != "unsupported":
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"capability tier after drift is {tier!r}, "
                    "expected 'unsupported' (failed closed)"
                ),
                evidence={"capability_path": str(cap_file), "tier": tier},
            )
        if not reason:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="capability.json downgraded but gives no reason",
                evidence={"capability_path": str(cap_file), "tier": tier},
            )
        # No new event must exist in the spool
        spool_entries: list[Path] = []
        if spool_dir:
            try:
                spool = resolve_artifact_path(ctx.artifacts_dir, spool_dir)
            except ValueError:
                spool = Path(str(spool_dir))
            if spool.is_dir():
                spool_entries = [p for p in spool.rglob("*") if p.is_file()]
        if spool_entries:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"new event emitted after drift: "
                    f"{len(spool_entries)} spool entries"
                ),
                evidence={
                    "capability_path": str(cap_file),
                    "tier": tier,
                    "reason": reason,
                    "spool_entry_count": len(spool_entries),
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=(
                "capability failed closed to unsupported after drift "
                f"({reason!r}) with no new event"
            ),
            evidence={
                "capability_path": str(cap_file),
                "tier": tier,
                "reason": reason,
                "spool_entry_count": 0,
            },
        )


class HermesHookProjectionObservedAssertion(Assertion):
    """Assert the live Hermes plugin produced an activation event.

    The hermes-plugin projection must produce a real activation receipt
    from a live Hermes session. No terminal outcome may be attached —
    Hermes cannot report one, and inventing one is the failure this
    assertion exists to catch.
    """

    type = "files.hermes_hook_projection_observed"

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        activation_artifact = params.get("activation_artifact")
        resource_id = params.get("resource_id")
        version_id = params.get("version_id")
        if not activation_artifact:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="missing activation_artifact parameter",
                evidence=params,
            )
        try:
            activation = resolve_artifact_path(
                ctx.artifacts_dir, activation_artifact
            )
        except ValueError as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=str(exc),
                evidence={"activation_artifact": str(activation_artifact)},
            )
        if not activation.is_file():
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    "no activation receipt from the live Hermes plugin: "
                    f"{activation} is missing"
                ),
                evidence={"activation_artifact": str(activation)},
            )
        try:
            payload = json.loads(activation.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=f"invalid activation receipt: {exc}",
                evidence={"activation_artifact": str(activation)},
            )
        if not isinstance(payload, dict):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message="activation receipt is not a JSON object",
                evidence={"activation_artifact": str(activation)},
            )
        # Must carry an event for the exact version
        event = payload.get("event")
        if event != "resource_invoked":
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"activation event is {event!r},"
                    " expected 'resource_invoked'"
                ),
                evidence={
                    "activation_artifact": str(activation),
                    "event": event,
                },
            )
        # Must name the exact resource version
        observed_rid = payload.get("resource_id")
        observed_vid = payload.get("resource_version_id") or payload.get(
            "resource_version"
        )
        if resource_id and str(observed_rid) != str(resource_id):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"activation resource_id is {observed_rid!r}, "
                    f"expected {resource_id!r}"
                ),
                evidence={
                    "activation_artifact": str(activation),
                    "expected_resource_id": resource_id,
                    "observed_resource_id": observed_rid,
                },
            )
        if version_id and str(observed_vid) != str(version_id):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"activation version is {observed_vid!r}, "
                    f"expected {version_id!r}"
                ),
                evidence={
                    "activation_artifact": str(activation),
                    "expected_version_id": version_id,
                    "observed_version_id": observed_vid,
                },
            )
        # No terminal outcome may be attached
        outcome = payload.get("outcome")
        if outcome is not None and outcome not in ("", "unknown"):
            return AssertionOutcome(
                type=self.type,
                status="failed",
                message=(
                    f"terminal outcome {outcome!r} attached to a Hermes "
                    "activation — Hermes cannot report one"
                ),
                evidence={
                    "activation_artifact": str(activation),
                    "outcome": outcome,
                },
            )
        return AssertionOutcome(
            type=self.type,
            status="passed",
            message=(
                "live Hermes plugin produced an activation event for the "
                "exact version with no terminal outcome"
            ),
            evidence={
                "activation_artifact": str(activation),
                "event": event,
                "resource_id": observed_rid,
                "resource_version_id": observed_vid,
                "outcome": outcome,
            },
        )


def _live_hook_verdict(path: Path) -> str | None:
    """``None`` if *path* holds a live harness payload, else the reason."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"unreadable payload: {exc}"
    if not isinstance(payload, dict):
        return "payload is not an object"
    raw = path.read_text(encoding="utf-8")
    if "PLACEHOLDER" in raw:
        return "carries fixture placeholders"
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return "no session_id"
    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return "no transcript_path"
    if not Path(transcript).exists():
        return f"transcript_path does not exist: {transcript}"
    return None
