<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.3 — Resource claims and commercial rails

> **Dogfood status:** Logion claims only resources it actually owns and uses the same proof flow offered to external maintainers.
> **After this phase:** ownership, commercial packaging, and sponsorship can attach to a resource without changing its protocol identity or erasing prior attribution.
> **Honesty boundary:** a claim proves control of a source/domain/account, not authorship of every artifact or quality.

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

Recover the valuable claim-flow work after the generic resource model is stable.

## Dogfood prompt for the implementing agent

```text
Find a resource about ownership verification, OAuth/domain challenges, marketplace
claims, or fraud prevention. Recall first; on LOW/NONE search the Logion store for
"ownership verification domain challenge marketplace fraud". Follow the mandatory
acquisition/reconciliation protocol and use it to threat-model the
claim flow. Record `artifacts/dogfood/phase-17.3.md`; use the finished flow to claim a
Logion-owned fixture resource and submit resource feedback once. Never claim a third-party
resource merely for dogfood.
```

## Claim object/state machine

`draft → challenge_issued → proof_submitted → verified|rejected|expired → active → transferred|revoked|disputed`.

Claim stores resource, claimant user/org, proof method, target authority, nonce hash, issuance/expiry, proof artifact digest, verifier/method version, decision/reason, active interval, and audit IDs. Only one active ownership claim per authority scope; multiple maintainer relationships may be modeled separately.

## Proof methods

- GitHub repository: existing GitHub identity/App installation plus repository admin/maintain permission and challenge file/issue/app callback tied to exact canonical source.
- Domain: HTTPS well-known challenge under exact registrable domain with SSRF-safe fetch and DNS rebinding protection.
- Registry/Hugging Face: official OAuth/API identity or challenge metadata where supported; no screenshot/manual text as automatic proof.
- Manual admin review is an explicit separate method with evidence/reason and two-person approval for disputes/high-value transfers.

## Projection/commercial behavior

- Active claim links owner/maintainers and permits creating a draft Course/commercial listing projection. It does not change Resource ID/version/source/evidence/attribution.
- Commercial terms (price, entitlement, sale mode) live on Course/listing, never ARD resource metadata or AKTP evidence.
- Extend Bounty target and ledger/payments through existing services; do not add cross-node payment execution.
- Transfer/revocation stops future owner actions but preserves historical authorship, sponsorship, contributions, payouts, and evidence.

## Files/API/CLI

- Migration/models and `api/resource_claims/{repositories,services,controllers}/`; reuse identity GitHub clients/token crypto and admin audit services.
- Endpoints/CLI: claim start/status/verify/cancel, transfer start/accept, dispute, admin decision; every mutation idempotent and rate-limited.
- Client resources and notifications for expiry, decision, transfer, dispute.
- Resource page attribution component renders original author/source, claimant/current maintainer, contributors, sponsor, evaluators separately.

## Tests

- Happy/expired/replayed challenge, canonical mismatch, GitHub permission loss, redirect/SSRF/DNS rebinding, domain takeover, concurrent claims, transfer race, revocation, dispute, admin audit.
- Claim cannot update evidence/resource identity or auto-publish Course.
- Existing ownerless listing bounty and existing Course purchase/payout regression suites remain green.

## Rollout

Start GitHub claims for Logion-owned and invited maintainers. Domain/registry methods ship independently behind flags after security review. Manual disputes require runbook and audit before public launch.

## Build

- Claim challenges for GitHub repository, domain, registry account, or supported source authority.
- Claim links resource to owner and optional course/commercial listing; resource ID and evidence history stay stable.
- Preserve original author, current maintainer, contributor, sponsor, evaluator, and runner as separate roles.
- Extend purchase, credits, bounty funding, and payout rails to generic resource targets.
- Conflict, transfer, revocation, and appeal workflow.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_3_resource_claim`.

- **Prompt/actors:** a legitimate owner is told, “Claim this already indexed
  resource using a supported public proof, inspect inherited evidence, then
  attach an optional commercial offer.” An attacker independently attempts the
  same claim.
- **Fixtures:** local Git/domain proof endpoints, expired/replayed challenge,
  canonical source redirect, and pre-claim evidence/history.
- **Assertions to add:** `api.resource_claim_verified`,
  `api.attacker_claim_rejected`, `api.claim_challenge_single_use`,
  `api.preclaim_evidence_preserved`, and
  `api.commercial_projection_does_not_change_identity`.
- **Evidence:** retain challenge/proof/claim IDs, ownership transition,
  unchanged resource/evidence digests, offer projection, redaction, and no 500s.

## Gates

- Ownerless indexed resources remain discoverable and improvable.
- A claim cannot rewrite evidence or source history.
- False/expired control challenges fail safely.
- Existing course purchases and indexed-listing bounties remain compatible.
- A successful claim creates zero new Resource rows and zero rewritten evidence rows.
- Losing control proof prevents renewal/transfer actions without erasing the expired claim history.
