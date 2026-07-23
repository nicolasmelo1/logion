<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.5 — Trust-boundary invariant tests

> **Dogfood status:** the invariant suite gates Logion production releases and the reference runner release.
> **After this phase:** protocol and product claims are mechanically constrained by adversarial tests.
> **Honesty boundary:** tests reduce known failure modes; they do not certify absolute security.

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

Protect the distinctions on which the product's credibility depends.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about threat modeling, security invariants, property-based tests,
or abuse-case testing. Recall first; on LOW/NONE search "threat modeling security
invariants property testing". Follow the mandatory acquisition/reconciliation protocol
and use it to add at least one adversarial invariant fixture not already listed. Record
`artifacts/dogfood/phase-17.5.md`; submit one honest feedback report after
the new fixture fails against a deliberately vulnerable test double and passes against
the product.
```

## Machine-readable invariant manifest

Add root `trust_boundaries.yaml` with stable invariant ID, statement, source and destination signals, forbidden transition/label/action, owning phases/domains, enforcement code, test IDs, UI/API copy surfaces, severity, and exception policy. Add schema and `make trust-audit`.

Example IDs:

- `TB-DISCOVERY-NOT-EVIDENCE`
- `TB-ACQUISITION-NOT-USAGE`
- `TB-OBSERVATION-NOT-FEEDBACK`
- `TB-FEEDBACK-NOT-EVAL`
- `TB-NATIVE-INSTALL-NOT-ENTITLEMENT`
- `TB-UPSTREAM-CONSENT-NOT-LOGION-CONSENT`
- `TB-EVIDENCE-NOT-AUTHORITY`
- `TB-FIRST-PARTY-NOT-INDEPENDENT`
- `TB-MISSING-NOT-PASS`
- `TB-SPONSOR-NOT-AUTHOR`
- `TB-FOREIGN-PAYOUT-NOT-LOCAL-LEDGER`
- `TB-METADATA-NOT-MODEL-EVAL`
- `TB-CLAIM-NOT-ENDORSEMENT`

## Enforcement layers

- Domain tests assert forbidden state transitions and service calls.
- Contract tests inspect API/OpenAPI fields and derived labels.
- UI/landing snapshot/copy linter maps strong terms (`verified`, `safe`, `consensus`, `decentralized`, `best`) to required scoped evidence fields.
- Protocol fixtures attack issuer/origin/signature/object/relay/authority boundaries.
- Ledger tests prevent foreign/display-only events from invoking local money services.
- Privacy tests prevent evidence/receipts/support bundles crossing disclosure policy.

## Required adversarial tests and harness

Create reusable malicious issuer, runner, relay, peer, registry, MCP server, model metadata, claimant, sponsor, and client fixtures. Each fixture declares expected rejected/quarantined/visible-but-untrusted behavior. Include concurrency and retry, not only happy HTTP requests.

## CI and exception process

- `make trust-audit` validates manifest completeness, named test existence, prohibited copy, and phase/owner links.
- Required in both repositories; shared invariant IDs/fixture package are version-pinned.
- Exceptions require expiry, owner, reason, compensating control, and user-visible limitation. No permanent blanket waiver.
- Failure blocks release; no flaky network dependency in the invariant suite.

## Acceptance criteria additions

- Every listed invariant has at least one negative test that demonstrably fails when its guard is removed/test double is vulnerable.
- Every public status label maps to the exact evidence+authority fields that permit it.
- A foreign valid signed event cannot trigger a local payout, “verified” label, or claim ownership in adversarial E2E.
- The manifest is linked from the threat model and release checklist.

## Invariants

- Discovery metadata is not evidence.
- Acquisition/inventory is not usage.
- Passive observation is not intentional feedback.
- Feedback is not controlled evaluation.
- External/native installation is not a paid entitlement or verified-buyer review.
- Upstream manager telemetry consent is not Logion telemetry consent.
- Evidence transport is not authority.
- Same-operator replication is not independent verification.
- Missing evidence is not a pass.
- Scan success is not universal safety.
- Benchmark score is not field performance.
- Sponsorship is not authorship.
- Claim control is not quality endorsement.
- Coordinator availability is not required to verify old attestations.
- Runner compute ownership is explicit.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_5_trust_invariants`.

- **Prompt:** a red-team agent is told: “Using only public customer/operator
  surfaces, attempt every transition in the published trust-invariant manifest
  that your role should not have. Report exact denials and verify ordinary
  allowed work still succeeds.”
- **Fixtures:** forged issuer, self-review/self-eval, replayed payout,
  cross-tenant read, resource-ID collision, receipt tamper, sandbox escape,
  duplicate import, and automatic-funding attempts.
- **Assertions:** create one registered assertion per machine-readable invariant
  plus `api.allowed_control_flow_succeeds`; unsupported invariant checks fail
  the scenario. The result must map every manifest ID to enforcement layer and
  observed evidence.
- **Evidence:** retain manifest digest, attack transcript/outcomes, unchanged
  ledgers/catalog/evidence, canary state, redaction, and no 500s.

## Build and gates

- Encode each invariant as API, UI copy, policy, and negative integration fixtures where applicable.
- Add malicious issuer, relay, runner, artifact, key-rotation, privacy, and payout scenarios.
- Fail CI when a projection invents stronger wording than source evidence supports.
- Publish a concise threat model and residual-risk register.
