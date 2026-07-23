<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.8 — Portable field evidence and aggregation

> **Dogfood status:** Logion upgrades the 15.11 usage receipts from its real workflows into disclosure-safe, signed field evidence and compares aggregates across acquisition channels.
> **After this phase:** native-use signals can travel between consenting nodes/organizations without exposing prompts, paths, code, or treating passive use as a review.
> **Honesty boundary:** field evidence is a statement from a real environment with selection bias; it is not a controlled benchmark, causal proof, or universal ranking.

## Mandatory dogfood protocol

The implementing agent uses the common interoperable loop:

1. Discover an exact resource relevant to privacy/telemetry/field evidence.
   On LOW/NONE run `logion listings search --query "privacy telemetry field evidence"
   --include-indexed --limit 5 --json`.
2. Acquire it through its recommended distribution, including a native manager when available.
3. Reconcile the installed artifact to the exact `ResourceVersion`.
4. Use it in the normal harness to review this phase's schema and privacy fixtures.
5. Verify `logion usage pending --json`.
6. Submit one intentional
   `logion feedback submit RESOURCE_ID VERSION_ID ... --json` report and record the
   Course projection disposition.
7. Save `artifacts/dogfood/phase-16.8.md` with acquisition channel, use, feedback ID, field-evidence ID, disclosure policy, and canary results.

Passive observation alone never justifies feedback or publication.

## Dependencies and non-duplication rule

- 15.10 owns acquisition inventory and native-manager reconciliation.
- 15.11 owns local observation hooks/plugins, consent modes, local spool, generic usage receipts, feedback, and Course-review projection.
- This phase **must not** create a second telemetry hook, spool, opt-in preference, receipt endpoint, or resource resolver.
- 15.17 provides the AKTP envelope/feed primitives reused for portable publication.
- 16.5 provides issuer keys and local authority distinctions.

## Goal

Convert selected 15.11 receipts into privacy-safe aggregate/portable evidence:

```text
local fixed-schema receipts
→ consent + disclosure policy
→ cohort aggregation/minimum threshold
→ signed field evidence
→ optional AKTP publication/import
→ benchmark reconciliation in 16.9
```

## Field-evidence predicate

Add `aktp.field.aggregate/v1`:

```json
{
  "schema": "aktp.field.aggregate/v1",
  "subject": {"resource_id": "uuid", "version_id": "uuid", "digest": "sha256:..."},
  "window": {"start": "RFC3339", "end": "RFC3339"},
  "population": {
    "task_class": "software-development",
    "environment_class": "coding-agent",
    "acquisition_channels": ["npx_skills", "logion_bundle"],
    "identity_tiers": ["shadow", "account", "verified"]
  },
  "counts": {
    "distinct_reporters_bucket": "10-24",
    "distinct_sessions_bucket": "25-49",
    "receipts": 47,
    "feedback_reports": 18
  },
  "outcomes": {
    "completed_rate": {"bucket": "0.75-0.89", "sample": 18},
    "unknown_receipts": 29
  },
  "ratings": {
    "usefulness": {"mean_bucket": "4.0-4.49", "sample": 18},
    "reliability": {"mean_bucket": "3.5-3.99", "sample": 18}
  },
  "method": {
    "name": "logion-field-aggregate",
    "version": "1",
    "policy_digest": "sha256:...",
    "input_high_watermark_digest": "sha256:..."
  },
  "limitations": ["opt-in population", "agent-reported task outcomes"],
  "issuer": {"id": "...", "key_id": "..."},
  "issued_at": "RFC3339"
}
```

No individual receipt ID, free text, exact timestamp, path, session hash, user/org, repository, prompt, tool call, or rare dimension value appears.

## Disclosure policy

A versioned policy defines:

- eligible receipt/feedback sources and identity tiers;
- permitted resource/task/environment/acquisition dimensions;
- minimum reporter/session/feedback cohort;
- fixed buckets and rounding;
- time window and maximum age;
- public, peer-only, organization-only, or local visibility;
- issuer/signing key;
- retention and revocation/supersession.

Policy cannot widen 15.11 consent. `local-only` inputs never leave the machine/node and cannot enter a public aggregate. Revoked consent excludes future aggregates; published historical signed aggregates follow the disclosed retention/supersession policy.

## Backend implementation

Add `api/field_evidence/`:

```text
policies.py
aggregate.py
privacy.py
publish.py
repositories/
controllers/
responses.py
```

Add:

```text
field_aggregate_policies
  id, owner/organization, version, policy JSONB, digest, visibility, active

field_aggregate_runs
  id, policy_id, resource_version_id
  window_start/end, input_high_watermark_digest
  state, counts_private JSONB, output_evidence_id NULL
  created_at, completed_at
  UNIQUE(policy_id, resource_version_id, window_start, window_end, input_digest)
```

The signed output itself lives in the existing evidence store. Private counts used to build it are access-controlled and retained only as policy requires.

Services:

- `ValidateFieldAggregatePolicy`
- `PlanFieldAggregate`
- `RunFieldAggregate`
- `CheckCohortPrivacy`
- `PublishFieldEvidence`
- `SupersedeFieldEvidence`

Aggregation queries use receipt/feedback domain repositories or explicit read models, never copy raw body text.

## CLI and operator surface

```bash
logion field-evidence policy validate POLICY.yaml
logion field-evidence plan RESOURCE_ID --policy POLICY.yaml --json
logion field-evidence build RESOURCE_ID --policy POLICY.yaml --dry-run --json
logion field-evidence show EVIDENCE_ID --json
logion field-evidence verify EVIDENCE_ID --offline
```

`plan` displays included channels/tiers/task classes, excluded inputs/reasons, cohort thresholds, buckets, visibility, and whether publication is allowed. `build --dry-run` neither signs nor stores.

Organization/private-node UI exposes policies, aggregate health, suppressed cohorts, publication state, and audit history.

## Privacy and abuse invariants

- Minimum cohort applies after every combination of filters.
- Differencing protection prevents repeated overlapping queries from isolating one reporter; public policies use fixed windows/dimensions rather than arbitrary user queries.
- High-cardinality/unknown task classes collapse to `other` or suppress.
- Feedback bodies are never aggregation inputs except pre-existing structured reason codes.
- Acquisition channel is allowed only above threshold; it must not reveal one user's tool choice.
- Identity tiers remain counts/buckets, not a hidden “trust score.”
- A signed aggregate with insufficient sample is impossible; outcome is `suppressed`, not zero.

## Files to change

### `backend repository`

- Migration/models for policies/runs.
- New `api/field_evidence/`.
- Reuse `api/resource_feedback/` and evidence signer/store.
- Add scheduled job handler, metrics, audit, admin/private-node controllers.
- Extend AKTP object resolution for public field evidence.

### `logion`

- Protocol predicate schema/goldens.
- Client and CLI commands.
- Offline verifier.
- Proving-ground privacy/differencing scenarios.

## Tests

- Policy schema, digest, visibility, consent intersection.
- Minimum cohort at base and every dimension/filter.
- Differencing/overlap, rare task class, channel isolation, identity-tier isolation.
- Prompt/path/repo/secret/free-text canaries absent from query, private run output, signed predicate, logs, and AKTP event.
- Deterministic aggregate from fixed inputs; retry idempotency; late receipt creates a new window/input digest, never rewrites old evidence.
- `local-only` and opted-out inputs excluded.
- Signed evidence offline verification and foreign import as visible-but-not-authoritative.
- 15.11 hook/spool/feedback regression: this phase adds no duplicate collection path.

## Rollout

1. Build local-only aggregates from Logion dogfood.
2. Compare manual calculations and privacy suppression for four windows.
3. Publish one disclosure-safe Logion first-party aggregate.
4. Import it into a clean node.
5. Enable organization/private-node policies.

No public cross-user aggregate ships before privacy review and minimum-cohort fixtures pass.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_8_field_evidence`.

- **Actors/prompt:** pseudonymous users acquire/use the same resource and are
  asked to submit minimum-disclosure outcomes. An operator asks: “Publish only
  the aggregate field claim allowed by cohort/privacy policy and prove what was
  suppressed.”
- **Fixtures:** one below-threshold cohort, one eligible diverse cohort,
  duplicate receipts, and one author-controlled identity.
- **Assertions to add:** `api.field_evidence_aggregate_published`,
  `api.small_cohort_suppressed`, `api.duplicate_receipts_excluded`,
  `api.identity_concentration_limited`,
  `crypto.field_evidence_signature_valid`, and
  `api.raw_feedback_not_exported`.
- **Evidence:** retain pseudonymous inclusion/exclusion receipts, policy and
  aggregate digest, signature/limitations, costs, redaction, and no 500s.

## Acceptance criteria

- [ ] One real Logion dogfood resource produces a verifiable signed field aggregate from 15.11 receipts.
- [ ] No raw/private observation field appears in the predicate or publication traffic.
- [ ] Small or differentiable cohorts are suppressed.
- [ ] Users do not install a second observer or grant new collection consent for this phase.
- [ ] Acquisition channels can be compared only above the privacy threshold.
- [ ] Offline verification succeeds with the Logion API unavailable.
- [ ] Generic feedback, Course reviews, field aggregates, and controlled evals remain visibly distinct.

## Out of scope

New hooks/telemetry collection, feedback submission, ranking, causal inference, benchmark reconciliation (16.9), automatic bounty selection, or a universal trust score.
