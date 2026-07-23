<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.1 — AI Catalog/ARD/AKTP conformance and upstream proposals

> **Dogfood status:** every proposed extension is first exercised by Logion and at least one clean reference consumer.
> **After this phase:** Logion contributes gaps found in real operation without
> conflating or forking AI Catalog and ARD.
> **Honesty boundary:** experiments remain namespaced and preserve compatibility
> with both base specifications until accepted upstream.

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

Prove AI Catalog and ARD work together in production, document each boundary,
and propose changes to the specification that actually owns the missing concept.

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

- Maintain `packages/interop/compatibility.yaml` with separately pinned AI
  Catalog revisions, ARD revisions, AKTP versions, codec releases, and tested
  implementations.
- Add CI jobs for AI Catalog producer/consumer, ARD client/registry, and AKTP
  producer/verifier fixtures across current and N-1 supported versions.
- Publish machine-readable conformance reports containing implementation/version, fixture suite digest, timestamp, pass/fail/skip, environment, and limitations.
- Spec examples and schemas are release artifacts with changelog and semantic version rules.

## Upstream proposal workflow

1. Classify the gap as AI Catalog schema/publication/trust, ARD
   discovery/registry, or AKTP evidence/improvement before drafting anything.
2. Open a local issue with exact owning-spec text/revision, expected behavior,
   real resource/catalog, observed behavior, redacted logs, and reproduction.
3. Prove the gap against two implementations or official fixtures.
4. Test existing extension/link/version/trust mechanisms first.
5. Implement a namespaced optional experiment and verify base clients ignore it.
6. Draft the smallest proposal for the owning upstream.

Likely subject is evidence/trust link relations, not embedding AKTP objects or authority into ARD. No proposal is an acceptance criterion; a high-quality rejected proposal may still pass this phase.

## Code/docs changes

- Public interop runner/fixtures/report generator; no private test-only protocol semantics.
- Backend emits selected AI Catalog, ARD, and AKTP revisions independently.
- CLI `logion protocol doctor --node URL` downloads only public metadata and produces a support bundle.
- Documentation separates normative AKTP requirements, Logion policy, and experimental extensions.

## Tests/acceptance additions

- Base AI Catalog consumers process Logion's catalog without AKTP extensions;
  base ARD clients discover the same entries without AKTP.
- Downgrade/N-1 and unknown-extension tests.
- At least one public interop report from Logion and one clean reference/independent consumer.
- Every upstream issue/PR link includes a passing minimal reproduction committed locally.

## Build

- Track AI Catalog, ARD, and AKTP versions/conformance separately.
- Publish interop reports from self-crawl and independent-node tests.
- Draft minimal ARD proposals for trust/evidence link relations or missing version semantics discovered in practice.
- Keep experimental fields namespaced and optional.
- Publish AKTP schemas, examples, threat model, versioning policy, and reference verifier.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_1_protocol_conformance`.

- **Prompt:** “Run the public AI Catalog, ARD, and AKTP conformance suites.
  Diagnose the failing extension fixture, identify which specification owns the
  gap, and generate a minimal upstream proposal with an executable test. Do not
  claim adoption.”
- **Fixtures:** current-version pass cases, unsupported-major, canonicalization,
  signature, cursor, unknown-extension, and one Logion attestation-extension
  case that upstream ARD cannot currently express.
- **Assertions to add:** `files.ai_catalog_conformance_report_valid`,
  `files.ard_conformance_report_valid`,
  `files.aktp_conformance_report_valid`,
  `files.upstream_proposal_has_executable_fixture`,
  `api.extension_backward_compatible`, and
  `api.no_upstream_adoption_claim`.
- **Evidence:** retain spec commits/versions, reports, minimized fixture,
  proposal diff/rationale, model cost, redaction, and no 500s.

## Gates

- Base AI Catalog consumers and ARD clients work without AKTP.
- Every proposed spec change cites a reproduced operational limitation.
- No proposal duplicates an existing ARD mechanism.
- Protocol artifacts build from tested examples.
