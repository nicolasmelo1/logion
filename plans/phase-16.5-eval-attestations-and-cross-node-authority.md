<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.5 — Eval attestations and cross-node authority

> **Dogfood status:** Logion consumes its own and independent issuers' attestations using an explicit local trust policy.
> **After this phase:** every node can calculate its own decision from the same evidence set.
> **Honesty boundary:** AKTP carries evidence; authority is local, issuer-aware, and policy-versioned.

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

Prevent “network verified” from becoming an unverifiable marketing label.

## Dogfood prompt for the implementing agent

```text
Use Logion to find a resource about PKI, trust policy, attestations, or authorization
engines. Recall first; on LOW/NONE search "attestation PKI trust policy authorization".
Follow the mandatory acquisition/reconciliation protocol. Use it to critique issuer/key
lifecycle and the local authority evaluator. Record `artifacts/dogfood/phase-16.5.md`;
submit feedback after an offline policy decision matches
the backend result. No actual resource use means no feedback.
```

## Attestation predicate and cryptography

- Add `aktp.eval.result/v1` to the public protocol package. It embeds/references eval contract digest, subject digest, evaluator descriptor digest, runner receipt digest, normalized result digest, environment class, artifacts, outcome, limitations, and replication group/decision when present.
- Reuse the 15.11 canonicalization, signature, issuer, key rotation, and artifact code. Do not create an “eval signature” subsystem.
- An attestation is cryptographically `valid|invalid|unverifiable`; local authority is separately `accepted|rejected|insufficient|expired`. API/UI must expose both.

## Local authority policy

Versioned JSON/YAML policy supports allowed predicate/evaluator versions, issuer IDs, independence groups, minimum fresh attestations, maximum age, required reproduction state, environment constraints, explicit deny rules, and default unknown handling. Compile to a pure decision function in a public `authority` module with an explanation tree.

Example explanation nodes: issuer allowed/denied, key valid at issue time, subject digest match, evaluator accepted, freshness, independence, quorum, contradiction, missing requirement. No hidden weights.

## Files/services

- Protocol/public package: predicate schema, authority policy schema/parser/evaluator, CLI verifier, golden bundles.
- Backend: `api/authority/` policy storage, organization/default policy selection, decision materialization/cache, invalidate-on-new-evidence/key/policy services, read controllers.
- CLI: `logion evidence decide SUBJECT --policy FILE`, `policy validate`, `policy explain DECISION_ID`.
- Landing/resource read models add explicit `first_party`, `independently_reproduced`, `contradicted`, `unknown`; never a boolean `verified` without scope.

## Tests

- Cross-language/canonical signature goldens and issue-time key rotation/revocation.
- Policy fixtures for distinct accepted decisions from the same evidence, unknown issuer, stale evidence, conflicting issuer, same-operator quorum, and policy revision.
- Cache invalidation and decision append-only history.
- Copy tripwire tests reject stronger labels such as “safe” from scan-only evidence.

## Rollout

Default public policy initially trusts only Logion first-party evidence and labels it accordingly. Add independent issuers explicitly after conformance. Organization policies remain private unless intentionally shared.

## Build

- Eval attestation predicate containing contract, subject, result, runner receipt, environment, artifacts, issuer, and limitations.
- Key discovery/rotation/revocation and offline verification.
- Local authority policy: accepted issuers, independence groups, predicate/evaluator allowlists, freshness, and quorum.
- Explainable decision endpoint returning evidence and policy inputs.
- Supersession and appeal records without destructive mutation.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_5_local_authority`.

- **Prompt/actors:** two clean consumers import the same signed eval
  attestation, then answer: “May this resource run here? Apply this node's local
  issuer/threshold policy and explain the decision without treating the
  attestation as global truth.” Their policies intentionally differ.
- **Assertions to add:** `crypto.eval_attestation_valid`,
  `api.attestation_imported_with_provenance`,
  `api.local_policy_allow`, `api.local_policy_deny`, and
  `api.no_global_authority_claim`.
- **Negative/evidence:** unknown issuer and changed subject digest fail closed.
  Retain policy/attestation digests, issuer, both decisions/explanations,
  rejection reasons, redaction, and no 500s.

## Gates

- Two nodes can reach different valid decisions and explain why.
- Revocation affects future decisions but preserves historical verification context.
- Unknown issuers remain visible but untrusted by default.
- No single global score or hidden issuer weighting is introduced.
- Public verifier reaches the same explanation tree as the backend for every golden policy/evidence bundle.
- An invalid signature can never be rescued by a permissive authority policy.
