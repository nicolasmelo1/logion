<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.13 — Portable scan evidence

> **Dogfood — Level 4 (evidence):** Logion scans third-party resources it actually acquired/used and publishes explicitly first-party evidence about immutable resource versions.
> **After this phase:** existing observation scans become portable, signed evidence rather than mutable listing fields only.
> **Honesty boundary:** a scan result reports method and observations; absence of findings is never a universal safety claim.

## Mandatory dogfood protocol

The phase-specific prompt below is implementation work, not optional documentation. The implementing agent must exercise the interoperable resource loop delivered by 15.10–15.11:

1. run local recall, then `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json` only on LOW/NONE;
2. inspect the exact `ResourceVersion`, distributions, evidence, permissions, license, and acquisition plan—not only a Course projection;
3. obtain explicit approval, run `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root --channel auto --dry-run --json`, then acquire through the recommended Logion or native channel;
4. run `logion resources reconcile --scope repo-root --json` and require exact version attribution;
5. use the resource in the normal harness on this phase's real task and verify it appears in `logion usage pending --json`;
6. submit exactly one intentional post-task report:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --task-class TASK_CLASS \
  --body "One or two resource-focused sentences; no private repository data" \
  --json
```

Use `--not-completed-task` when appropriate. Record the feedback ID and `course_review_projection` disposition. A native external installation is valid dogfood; Logion must not require reinstalling it. If acquisition, exact attribution, consent, or actual use is absent, record the blocker and **do not submit feedback/review**. Passive observation alone never justifies a rating.

## Goal

Create the smallest useful AKTP primitive: verifiable evidence tied to an exact resource version and reproducible method.

## Dogfood prompt for the implementing agent

```text
Use Logion to find one acquirable resource about supply-chain security, security
scanning, SBOM/provenance, or attestations. Recall first with
`logion recall search "software supply chain attestation scanner" --limit 5`, then
search with `logion listings search --query "supply chain attestation security scan"
--include-indexed --limit 5 --json` only on LOW/NONE. Inspect the exact candidate/version,
follow the mandatory acquisition/reconciliation protocol, and apply
the acquired resource to threat-model the evidence envelope and review the scan normalization
rules. Put the applied findings in `artifacts/dogfood/phase-15.13.md`. When the phase
tests pass, submit one honest usage review. No actual use means no review.
```

## Required evidence envelope

Canonical JSON uses RFC 8785/JCS before SHA-256 and signing. The signed payload is the statement, not a database row or presigned URL:

```json
{
  "schema": "sh.logion.aktp/evidence/v0",
  "evidence_id": "uuid",
  "subject": {"resource_id": "uuid", "version_id": "uuid", "digest": "sha256:..."},
  "predicate_type": "sh.logion.scan.source/v1",
  "predicate": {"outcome": "pass|fail|inconclusive|error", "findings": [], "summary": {}},
  "method": {"name": "trivy", "version": "...", "config_digest": "sha256:..."},
  "execution": {"runner_id": "...", "started_at": "...", "finished_at": "..."},
  "artifacts": [{"digest": "sha256:...", "media_type": "...", "size_bytes": 0}],
  "limitations": ["..."],
  "issuer": {"id": "...", "key_id": "..."},
  "issued_at": "...",
  "supersedes": null
}
```

Envelope signatures use an existing audited library and Ed25519 keys stored outside the database. If no key-management primitive exists, add a settings-backed file/secret key for the first node plus a public JWKS-like key document; never invent custom cryptography. Key rotation preserves old public keys.

## Database and storage

- Migration adds `evidence_statements` (IDs, subject FKs/digest, predicate type/version, issuer/key, canonical payload JSONB, payload digest, signature, outcome, issued/superseded timestamps) and `evidence_artifacts` (statement FK, digest, media type, size, object key).
- Unique `(issuer_id, payload_digest)` makes retry idempotent. Payload and signature are immutable; supersession is a new row.
- Object keys are content-addressed and private by default. Read endpoints return short-lived URLs only after authorization, while public safe summaries remain inline.
- Existing `IndexedListing.observed_*` fields remain a derived compatibility view updated from the newest Logion scan evidence.

## Concrete code plan

- Add `api/evidence/{constants,schemas,repositories,services,controllers}/` and register the router in `api/main.py`.
- Implement `BuildScanEvidenceService`, `PublishEvidenceService`, `VerifyEvidenceService`, `ListEvidenceService`, and `SupersedeEvidenceService`.
- Change `api/indexing/services/run_observation_scan.py` and its job handler to persist raw scanner artifacts, normalize predicates, then publish evidence in the same terminal job path.
- Keep scanner adapters in their current packages; normalization belongs in evidence predicate builders, not scanner subprocess code.
- Public client: `EvidenceResource.list/show/verify_keys`; CLI: `evidence list`, `show`, `verify --offline --key-file`.
- An AI Catalog entry or ARD result may expose only the optional, spec-valid
  evidence relation/reference; it must not copy “pass/safe” into discovery.

## Stable error/outcome rules

- Scanner exit/finding policy maps separately: a scanner process error is `error`, unsupported content is `inconclusive`, detected policy violation is `fail`, and clean completion is `pass` with limitations.
- Stable API errors: `evidence_subject_digest_mismatch`, `evidence_predicate_invalid`, `evidence_signature_invalid`, `evidence_artifact_digest_mismatch`, `evidence_issuer_unknown`, `evidence_supersession_cycle`.
- Verification can return cryptographically valid but locally untrusted; never merge those states.

## Tests

- Golden canonicalization/signature fixtures shared between backend, client, and protocol examples.
- Mutation tests: one-byte payload/artifact/key/signature changes fail verification.
- Observation job tests for pass/fail/error/inconclusive and retry idempotency.
- Supersession chain, key rotation, unknown issuer, deleted resource prevention, artifact authorization/expiry.
- Compatibility tests prove old listing observation JSON is unchanged except additive evidence IDs.
- CLI offline verification succeeds with API unavailable.

## Rollout

Dual-write evidence behind `portable_scan_evidence`; compare derived fields with legacy observation fields for one week. Backfill only from scan artifacts whose subject digest and scanner version are known; do not convert ambiguous historical rows into signed claims.

## Build

- Add an append-only `resource_evidence` store with subject resource/version/digest, issuer, predicate type, method/version, timestamps, result, limitations, artifact references, and signature envelope.
- Define v0 predicates for source scan, dependency scan, declared-vs-observed capabilities, and provenance/mirror integrity.
- Adapt `RunObservationScanService`, Trivy, OSV, and agent-scanner output into those predicates.
- Store bulky logs as content-addressed artifacts; keep normalized summaries queryable.
- Publish evidence links through the owning AI Catalog/ARD extension mechanism
  without embedding Logion trust conclusions in base discovery metadata.
- Add `logion evidence list|show|verify` and SDK verification helpers.

## Security and truth rules

- Evidence references an immutable digest, never “latest”.
- Issuer identity and execution environment are explicit.
- Failed, timed-out, and inconclusive runs are first-class outcomes.
- Corrections append a superseding record; evidence is not rewritten.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_13_portable_scan_evidence`.

- **Actors/fixtures:** `publisher`, `scanner_operator`, and clean offline
  `consumer`; seed benign, suspicious-permission, and byte-tampered bundles with
  deterministic digests.
- **Customer prompt:** “Scan both candidate capabilities, publish only truthful
  portable evidence, then verify the benign bundle's evidence from a clean
  workspace without trusting the mutable API response.”
- **Flow:** use public publish/scan/evidence commands, move only the envelope
  and public verification material offline, then try it against the tampered
  bundle.
- **Assertions to implement:** `api.scan_evidence_published`,
  `crypto.evidence_signature_valid`, `crypto.evidence_subject_digest_matches`,
  `files.offline_evidence_verifies`, `files.tampered_subject_rejected`, and
  `api.scan_claim_scope_truthful`.
- **Truth/evidence:** “scan completed” must never become an unqualified “safe”.
  Retain envelope digest, issuer key ID, scanner/version, predicate, subject
  digest, limitations, tamper rejection, redaction, and no-500 proof.

## Acceptance gates

- Re-running the same scanner fixture yields equivalent normalized evidence.
- Signature, subject digest, artifact digest, and predicate schema verify offline.
- An indexed skill page can show what was observed, how, when, and by whom.
- Existing listing observation fields are derived compatibility views.
