<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.1 — ARD/AKTP conformance and upstream proposals

> **Dogfood status:** every proposed extension is first exercised by Logion and at least one clean reference consumer.
> **After this phase:** Logion contributes gaps found in real operation—especially attestation links—without forking ARD.
> **Honesty boundary:** until accepted upstream, extensions are namespaced experiments and ARD base compatibility remains intact.

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

Prove ARD works in production, document its boundaries, and propose only evidence-backed changes.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about standards work, protocol conformance, RFC writing, or
interoperability testing. Recall first; on LOW/NONE marketplace-search "protocol
conformance RFC interoperability". Follow the mandatory acquisition/reconciliation
protocol and use it to write/review the interop report and proposal.
Save `artifacts/dogfood/phase-17.1.md`; submit one honest feedback report only after the proposal
is backed by a reproduced fixture, not merely drafted.
```

## Version matrix and repository artifacts

- Maintain `packages/interop/compatibility.yaml` with ARD spec revisions, AKTP versions, codec package releases, supported/must-ignore behavior, and tested implementations.
- Add CI jobs that run ARD producer/consumer fixtures and AKTP producer/verifier fixtures across current and N-1 supported versions.
- Publish machine-readable conformance reports containing implementation/version, fixture suite digest, timestamp, pass/fail/skip, environment, and limitations.
- Spec examples and schemas are release artifacts with changelog and semantic version rules.

## Upstream proposal workflow

1. Open a local issue with exact ARD text/revision, expected behavior, real resource/catalog, observed behavior, logs/pcap redacted, and minimal reproduction.
2. Prove the gap against two independent implementations or upstream reference fixtures where possible.
3. Test whether existing extension/link/version mechanisms solve it.
4. Implement a namespaced optional experiment and verify base clients ignore it.
5. Draft the smallest proposal with compatibility/security/privacy analysis and remove it locally if upstream chooses another valid mechanism.

Likely subject is evidence/trust link relations, not embedding AKTP objects or authority into ARD. No proposal is an acceptance criterion; a high-quality rejected proposal may still pass this phase.

## Code/docs changes

- Public interop runner/fixtures/report generator; no private test-only protocol semantics.
- Backend emits selected ARD revision and extension namespace in diagnostics.
- CLI `logion protocol doctor --node URL` downloads only public metadata and produces a support bundle.
- Documentation separates normative AKTP requirements, Logion policy, and experimental extensions.

## Tests/acceptance additions

- Base ARD consumer fixture processes every Logion catalog with experimental fields removed/ignored.
- Downgrade/N-1 and unknown-extension tests.
- At least one public interop report from Logion and one clean reference/independent consumer.
- Every upstream issue/PR link includes a passing minimal reproduction committed locally.

## Build

- Track ARD versions and conformance fixtures separately from AKTP codecs.
- Publish interop reports from self-crawl and independent-node tests.
- Draft minimal ARD proposals for trust/evidence link relations or missing version semantics discovered in practice.
- Keep experimental fields namespaced and optional.
- Publish AKTP schemas, examples, threat model, versioning policy, and reference verifier.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_1_protocol_conformance`.

- **Prompt:** a clean implementer receives: “Run the public ARD and AKTP
  conformance suites against this node, diagnose the failing extension fixture,
  and generate a minimal upstream proposal backed by an executable test. Do not
  claim upstream adoption.”
- **Fixtures:** current-version pass cases, unsupported-major, canonicalization,
  signature, cursor, unknown-extension, and one Logion attestation-extension
  case that upstream ARD cannot currently express.
- **Assertions to add:** `files.ard_conformance_report_valid`,
  `files.aktp_conformance_report_valid`,
  `files.upstream_proposal_has_executable_fixture`,
  `api.extension_backward_compatible`, and
  `api.no_upstream_adoption_claim`.
- **Evidence:** retain spec commits/versions, reports, minimized fixture,
  proposal diff/rationale, model cost, redaction, and no 500s.

## Gates

- Base ARD clients ignore AKTP extensions safely.
- Every proposed spec change cites a reproduced operational limitation.
- No proposal duplicates an existing ARD mechanism.
- Protocol artifacts build from tested examples.
