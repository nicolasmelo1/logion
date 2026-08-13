<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.14 — Feedback-driven platform bounties

> **Dogfood — Level 5 (demand becomes improvement):** Logion uses its own attributed usage/feedback corpus to choose and draft an improvement for a resource the team actually uses.
> **After this phase:** platform sponsorship prioritizes repeated real-world friction rather than founder taste, raw catalog popularity, or whichever listing is easiest to understand.
> **Honesty boundary:** feedback nominates and scopes work; it does not prove the fix, authorize spending, or determine payout.

## Goal

Extend 15.8 so the platform-funded bounty queue is driven by observed use and actionable failure patterns:

```text
exact attributed use
→ repeated feedback/problem cluster
→ eligibility and impact policy
→ operator-reviewed candidate
→ draft/publish/fund
→ delivery
→ affected users/resources rerun or report again
```

## Dependencies

- 15.8 platform-funded bounties, sponsorship ledger, indexed-listing targets, delivery lanes, and payout.
- 15.9 generic resource identity.
- 15.10 acquisition channel/inventory.
- 15.11 usage receipts, generic feedback, identity tiers, and Course projection.
- 15.13 portable scan evidence for security/provenance problems when applicable.

## Mandatory dogfood prompt for the implementing agent

```text
You are implementing Phase 15.14. Do not hand-pick a fashionable skill.

1. Run recall, then on LOW/NONE search:
   `logion listings search --query "feedback analytics improvement prioritization"
   --include-indexed --limit 5 --json`.
2. Inspect/acquire/reconcile one exact resource and use it to critique the selection
   policy. Verify pending use and submit one intentional
   `logion feedback submit RESOURCE_ID VERSION_ID ... --json` report.
3. Query the internal dogfood feedback summary for resources actually used during
   phases 15.10–15.13.
4. Filter to exact-version feedback with at least the configured minimum distinct
   reporters/sessions or a severe reproducible security/provenance finding.
5. Inspect the top candidates, raw redacted feedback, acquisition channels, identity
   tiers, ownership/license, existing issues/bounties, and reproducibility.
6. Select one bounded improvement whose supporting users include a real Logion
   workflow. Document why the next candidates were not selected.
7. Generate a draft bounty through the implemented recommendation service. Verify
   target digest, problem cluster, reproduction, acceptance criteria, delivery lane,
   affected task classes, evidence links, suggested reward, and exclusions.
8. Ask for separate explicit approval before publishing or funding. Dogfood may stop
   at an operator-approved draft if the user does not authorize credit spend.
9. If funded/delivered, reacquire or update the exact candidate version, use it again,
   submit linked post-improvement feedback, and compare—not overwrite—the original.
10. Save `artifacts/dogfood/phase-15.14.md` with candidate scores/explanations, rejected
   alternatives, operator decision, bounty IDs, spend authorization, before/after
   feedback, and whether the signal was genuinely useful.
```

## Selection policy

Selection is a versioned, explainable policy. Hard eligibility first:

- exact resource/version attribution;
- legally improvable/redistributable or owner-approved delivery path;
- bounded problem with reproduction or repeated structured feedback;
- no open equivalent bounty/accepted unresolved fix;
- resource not blocked/suspended for abuse;
- funding/delivery compatible with 15.8;
- minimum privacy cohort unless severity policy permits a single confidential security report.

Then prioritize with separately visible signals:

- distinct attributed users/sessions, deduplicated;
- repeated task-class demand;
- completed-task failure/regression rate;
- usefulness/reliability/tool-safety friction;
- recency and affected current version;
- identity tier and reporter history;
- availability of reproduction/acceptance test;
- estimated improvement cost and number of affected users;
- security/provenance severity;
- maintainer responsiveness and delivery feasibility.

Do not use downloads, stars, hub rank, or anonymous event count as a hidden universal score.

## Closed-resource and deliverable boundary

A closed, hosted, or otherwise non-contributable resource may still accumulate
lawful attributed-use signals, feedback, static evidence, eval baselines,
scorecards, regressions, and improvement recommendations. Those records remain
attached to the original publisher's exact resource/version and do not imply
that Logion or a contributor can modify the service.

A recommendation becomes a funded bounty only when the bounty names a bounded
deliverable that a participant has authority to produce:

- an eval suite, benchmark, baseline, scorecard, minimal reproduction,
  interoperability adapter, documentation change, or improvement proposal may
  be eligible when its own artifact/license/delivery path is valid;
- a public plugin or client integration may be eligible only under its actual
  source license and contribution policy;
- a change to a private MCP server, hosted model, proprietary dataset, or other
  closed upstream surface is ineligible without an owner-approved delivery
  path and acceptance authority.

An evidence bounty must name the evaluation/reproduction artifact as its
deliverable; it must not be presented as a fix to the evaluated upstream
resource. Without an authorized implementation path, the signal remains
`maintainer_contact`, `license_blocked`, or an unfunded recommendation. Logion
must not create a speculative server-fix bounty merely because a black-box
score regressed.

When the owner later participates, delivery may be private. Logion records the
owner's acceptance authority and disclosure policy, observes a new canonical
version, reruns the pinned evals, and reports the before/after evidence without
claiming access to the patch or causal proof beyond the evidence. A newly
observed upstream version is not proof that an external recommendation was
implemented unless the owner supplies that lineage.

## Feedback clustering

Create deterministic first-pass clustering:

- structured failure/reason codes;
- resource version;
- task class;
- acquisition channel;
- completed/not-completed;
- normalized operator-applied labels.

Free-text bodies may be summarized only through a redacted, auditable operator/agent job. Original feedback stays private according to policy. No embedding of private body text into a public vector index in this phase.

Cluster states:

```text
candidate
needs_reproduction
actionable
duplicate_existing
insufficient_signal
license_blocked
maintainer_contact
bounty_drafted
bounty_open
improvement_delivered
post_feedback_pending
closed
```

## Database and services

Add:

```text
improvement_signal_clusters
  id, resource_id, version_id
  policy_version, task_class, reason_code
  summary_private, summary_public
  reporter/session/use counts by tier
  state, severity, confidence/limitations
  first_seen_at, last_seen_at
  created_at, updated_at

platform_bounty_recommendations
  id, cluster_id
  selection_policy_digest
  score_components JSONB
  eligibility JSONB
  proposed_scope JSONB
  proposed_reward_credits
  proposed_delivery_lane
  state draft|approved|rejected|published|expired
  operator_user_id, decision_reason
  bounty_id NULL
  created_at, decided_at

improvement_feedback_links
  bounty_id / submission_id
  before_feedback_or_evidence_id
  after_feedback_or_evidence_id NULL
  relation affected|reproduced|post_improvement
```

Use `api/improvements/` for clustering/recommendation. Publishing/funding calls existing 15.8 Bounty and ledger services. No direct credit mutations.

## API and operator CLI

- `GET /v1/admin/improvement-signals`
- `GET /v1/admin/improvement-signals/{id}`
- `POST /v1/admin/improvement-signals/{id}/reproduce`
- `POST /v1/admin/improvement-signals/{id}/recommendation`
- `POST /v1/admin/bounty-recommendations/{id}/approve|reject`
- `POST /v1/admin/bounty-recommendations/{id}/publish`

CLI:

```bash
LOGION_ENABLE_ADMIN=1 logion admin improvements list --json
LOGION_ENABLE_ADMIN=1 logion admin improvements inspect CLUSTER_ID --json
LOGION_ENABLE_ADMIN=1 logion admin improvements draft-bounty CLUSTER_ID --dry-run
LOGION_ENABLE_ADMIN=1 logion admin improvements approve RECOMMENDATION_ID
LOGION_ENABLE_ADMIN=1 logion admin improvements publish RECOMMENDATION_ID
```

Approval and funding are separate confirmations. `draft-bounty` never debits credits.

## Public product surface

Resource page may show:

- “used in N attributed workflows” only above privacy threshold;
- top structured friction categories;
- “improvement funded because…” explanation;
- original resource/author, sponsor, contributor, delivery, and before/after feedback separately;
- affected versions and acquisition channels.

It may not show private feedback bodies, reporter identity, internal repository/task data, or claim causal improvement from uncontrolled feedback alone.

## Abuse and Goodhart defenses

- Deduplicate by reporter/session/resource/task window.
- Identity tiers and concentration are visible; no secret magic weighting.
- Detect sudden new-subject bursts, reciprocal/self feedback, sponsor/author conflicts, and identical bodies.
- Resource author/owner feedback can inform reproduction but cannot alone trigger platform funding.
- Recommendation service is read-only with respect to money.
- Operator must review raw signal limitations and conflicts.
- Severe security reports use a confidential lane and disclosure policy.

## Files to change

### `backend repository`

- Migration/models.
- New `api/improvements/{repositories,services,controllers,responses}/`.
- Extend admin router/events/notifications.
- Reuse `api/bounties/services/create_bounty.py`, platform funding services from 15.8, and ledger services.
- Extend resource/listing read models with safe public improvement summaries.
- Add metrics and scheduled/lazy clustering job handler.

### `logion`

- Client admin/resource read methods.
- CLI admin improvements commands.
- Companion behavior: when a used resource almost fits, submit feedback with a bounded improvement reason; do not open/fund automatically.
- Proving-ground scenario for feedback → recommendation → approved draft.

## Tests

- Eligibility for exact/repeated feedback, insufficient cohort, ambiguous resource, license blocked, duplicate bounty, suspended resource.
- Closed remote MCP: evidence/recommendation remains valid while an unapproved
  server-fix bounty is ineligible and routes to `maintainer_contact`.
- Evidence bounty targets and pays for the eval/reproduction artifact, never
  falsely records the closed upstream server as improved.
- Owner-approved private delivery records acceptance authority and disclosure
  limits; a later version/eval comparison does not expose a patch or fabricate
  causal lineage.
- Identity-tier/concentration and sybil bursts do not dominate.
- Same feedback retry/idempotency and cluster version separation.
- Free-text redaction/private-public summary boundary.
- Recommendation explanation recomputes from immutable inputs and policy.
- Draft creates no ledger entry; approval creates no funding; funding uses existing balanced ledger.
- Concurrent recommendation/publish produces one bounty.
- Course and ownerless indexed listing delivery lanes.
- Before/after links append and never rewrite original feedback.
- Public resource response privacy thresholds and attribution labels.
- End-to-end dogfood fixture from direct `npx skills` use feedback to platform bounty draft.

## Rollout

1. Shadow recommendations on internal dogfood only.
2. Weekly operator review with zero publishing for four weeks.
3. Draft one real bounty and compare recommendation usefulness to manual choice.
4. Publish/fund with explicit user approval and small cap.
5. Invite opt-in external feedback into recommendations after abuse/privacy review.

Metrics: clusters by state/reason, candidates accepted/rejected and why, time to reproduction/draft/delivery, spend, affected users, post-feedback rate, concentration, false-positive/operator override. No vanity “AI chose this” metric.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_14_feedback_bounty`.

- **Actors/seed:** three pseudonymous buyers and one platform operator; the seed
  exposes one actually broken indexed skill and one healthy control. Buyers
  must acquire/use the broken fixture before feedback.
- **Buyer prompt:** “Use the indexed formatter on this repository. If it fails,
  submit concise feedback through Logion with the minimum reproduction
  evidence.”
- **Operator prompt:** “Show recurring eligible problems on resources people
  actually used. Draft a bounty for the strongest cluster, explain exclusions,
  but do not fund it without separate approval.” A later prompt explicitly
  approves one bounded amount.
- **Assertions to implement:** `api.feedback_cluster_exists`,
  `api.cluster_has_distinct_users`, `api.bounty_recommendation_explained`,
  `api.bounty_draft_unfunded`, `api.platform_bounty_funded_once`, and
  `api.control_resource_not_selected`, plus exact-ledger/no-double-debit checks.
- **Abuse/evidence:** duplicate identity feedback and unlinked feedback cannot
  meet threshold. Retain pseudonymous receipt IDs, score/exclusions, audited
  draft/funding transition, approval actor, exact ledger, and no-500 proof.

## Acceptance criteria

- [ ] The first recommended bounty is traceable to actual attributed use/feedback, not catalog popularity.
- [ ] An operator can explain every eligibility and priority component.
- [ ] Drafting, approving, publishing, and funding remain separate audited actions.
- [ ] Sybil/self/author-only feedback cannot independently trigger funding.
- [ ] Existing 15.8 ledger, payout, attribution, and delivery invariants remain intact.
- [ ] After an improvement, new feedback links to the old signal without rewriting history.
- [ ] Closed resources can retain evidence, scorecards, and recommendations
      without implying that Logion can modify them or opening an undeliverable
      server-fix bounty.
- [ ] Dogfood produces at least one useful recommendation and records rejected alternatives.

## Out of scope

Automatic funding/payout, LLM-only opaque prioritization, universal ranking, tokens, cross-node settlement, controlled benchmark proof, and public disclosure of private feedback.
