<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Economic Network And Rewards

> **2026 direction note:** economics follow attributed use and independently
> verifiable improvement; they do not create demand. Founder subsidies are
> labeled, settlement remains node-local, and no token or owned compute fleet is
> implied here. [The sequenced roadmap](sequenced-roadmap.md) governs order.

This document covers post-MVP economic expansion beyond creator-funded
bounties.

## Current Foundation

The current product already has the right primitives:

- course purchases
- creator payouts
- Stripe Connect seller onboarding
- entitlements
- internal ledger
- creator-funded bounties
- bounty submissions
- bounty payouts
- publication review
- reports/moderation

The first MVP can launch with creator-funded bounties only.

## Core Economic Boundary

Keep these concepts separate:

```text
funding authority != publication authority != trust authority
```

Examples:

- A sponsor can fund an improvement without owning the course.
- A creator can accept an improvement without bypassing review.
- A reviewer can approve publication without deciding bounty payout.
- A platform reward can pay a contributor without implying future versions are
  trusted.

This boundary prevents the economy from corrupting trust controls.

## Open Improvement Proposals

See the normative paid/unpaid lifecycle in
[`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md).

Open proposals should be the next step after MVP.

Initial behavior:

- any entitled buyer or qualified user can suggest an improvement
- proposal targets a course or version
- proposal is unfunded by default
- creator can accept, reject, ignore, or convert to bounty
- platform/admin can mark strategically important proposals
- proposal can collect discussion/evidence

An accepted free contribution records attribution, evidence and upstream or
derivative lineage; it has no payout. Funding is an explicit prospective
conversion, never an implied obligation.

Do not attach automatic payout at first.

## Sponsor-Funded And Platform-Funded Bounties

After open proposals exist, add more funding lanes:

1. creator-funded bounties
2. sponsor-funded bounties
3. platform-funded bounties

Sponsor examples:

- enterprise customer
- course buyer
- platform partner
- Logion itself

Rules:

- sponsor funds work
- course creator retains release authority
- publication review remains mandatory
- payout requires accepted submission under defined criteria
- disputes require admin path

## Reviewer Marketplace

Paid review is valuable but adversarial.
Do not launch it until Logion has:

- reviewer reputation
- historical review outcomes
- anti-sybil controls
- anti-collusion checks
- admin override
- appeal path
- sampling of reviewer quality

Possible future flow:

```text
automated scan -> evidence package -> qualified network evaluators -> consensus band or escalation -> payout by review quality
```

Important constraints:

- reviewers should not be able to approve their own courses
- reciprocal review patterns should be detected
- low-effort reviews should not earn
- disagreement should not automatically punish a reviewer
- final authority should remain with platform/admin policy where required

The key design rule is:

```text
platform-owned evaluation policy + network-executed evaluators
!= open consensus with no trust controls
```

Logion can use its own network of agents to run bounded review or eval tasks, but
it should still define:

- evaluator eligibility
- diversity requirements
- rubric/schema for the judgment
- what counts as agreement or disagreement
- when results auto-resolve
- when results escalate
- how payout depends on later observed accuracy

This keeps the marketplace alive without turning trust into a popularity contest.

## Ranking And Points

Contribution scoring can be useful for:

- reputation
- discoverability
- reviewer eligibility
- reward eligibility
- creator trust

But points with cash redemption become a financial attack surface.

Score inputs should favor hard-to-fake events:

- accepted bounty work
- published improvements
- buyer-rated usefulness over time
- confirmed useful reports
- reviewer accuracy
- low report rates
- maintenance consistency
- tests/evals contributed and reused

Avoid over-weighting:

- raw activity
- proposal count
- self-reviews
- reciprocal reviews
- downloads without usage
- easily farmed votes

## Network Reward Pool

A reward pool can eventually distribute surplus to valuable contributors.

Prerequisites:

- append-only ledger support
- clear pool funding source
- contribution score model
- eligibility rules
- payout thresholds
- delayed settlement
- fraud review
- dispute/appeal path
- tax/payment compliance review

Start small:

- capped monthly pool
- manual review for payouts
- limited eligible categories
- transparent rules
- ability to freeze suspicious payouts

Do not let reward automation ship before anti-fraud visibility.

## Agent Voting And RLAF

Agent-assisted evaluation should begin as evidence, not authority.

Good early use:

- agents compare outputs
- agents run evals
- agents summarize diffs
- agents detect regressions
- agents produce confidence signals for reviewers

Bad early use:

- agents automatically release versions
- agents automatically pay bounties
- agents automatically rank contributors for cash rewards
- agents run untrusted submissions without sandboxing

## Enterprise Private Bounties

B2B teams may want private economic loops:

- internal bounties
- internal reviewers
- private proposal queues
- internal reward budgets
- department-level funding
- compliance approval before payout

This should reuse the same product model, but with organization-level policy and
visibility controls.

## Mechanisms From Multi-Agent Economic Research

The mechanisms below sharpen what is already in this document. They should
land only after sandbox stage 3+ (see
[Sandbox And Runtime Trust](sandbox-and-runtime-trust.md)) and only for task
classes with enough repeated activity for market selection to apply. Treat
this as v2 territory. Reference: "Economy of Minds" (arXiv 2606.02859).

### Bucket-brigade payout chaining

Today a bounty payout goes to one accepted submitter. Accepted work usually
depends on earlier work: a regression test, an eval harness, the upstream
course it patches. A flat single-contributor payout removes the incentive
for that earlier work to exist.

Allocate a single bounty payout across the dependency chain that produced
the accepted submission. Illustrative split:

```text
accepted submitter   60%
prior contributors   25%   (e.g. regression author, eval harness author)
original artifact    15%   (course author whose version chain this extends)
```

Fractions are policy and should be tuned per task class. The required
property is that contributors anywhere in a successful chain earn, so chains
actually form.

See the matching note in
[Eval-Backed Bounties And Improvement Evidence](eval-backed-bounties-and-improvement-evidence.md).

### Novice eligibility rule

A pure reputation gate has a cold-start problem: a new agent has no history,
so the market never tests it. Reserve a small low-stake bounty pool for
first-time participants, with stakes capped so a bad first attempt has
bounded damage.

Bad first attempt: small loss, exit. Good first attempt: enters the regular
reputation pool. This preserves selection without locking the network into
incumbents.

### Periodic rent and reputation decay

The score model in this document is monotonic: good acts add, no decay. Add
a slow decay term so reputation requires continued contribution. Listed but
unmaintained courses can pay a small listing rent against earnings to
discourage dead inventory.

The point is to keep the eligibility gate responsive to *current*
contribution rather than historic standing.

### Coalition-wealth collusion detection

Reciprocal review and sock-puppet rings are listed as risks above, without a
detection method. The detection target is measurable: cluster accounts by
transaction graph, then compute each cluster's *net external* inflow.

```text
internal cluster transfers cancel
only external wealth drift matters
```

A real improvement chain has external buyers funding it. A sock-puppet
cluster has only ring-internal transfers with near-zero external footprint
relative to its internal volume. Clusters whose internal volume dominates
external inflow are the collusion candidates.

The same algorithm applies to reviewer/submitter rings in
[Eval-Backed Bounties And Improvement Evidence](eval-backed-bounties-and-improvement-evidence.md).

### Recurrence and stationarity as preconditions

The rule "do not let money move faster than trust" is qualitative. The
quantitative companion: a bounty market only converges to quality when

- the same task class is attempted many times (recurrence)
- the evaluation rubric stays stable across attempts (stationarity)

One-off bounties and shifting rubrics break the convergence argument.
Automated payout for a task class should unlock per-archetype, gated on
accumulated repeat activity at stable rules, not on calendar time.

This tightens the staged unlock order in
[Eval-Backed Bounties And Improvement Evidence](eval-backed-bounties-and-improvement-evidence.md).

## Mechanisms From The 2026 Agent-Marketplace Field Scan

Three mechanisms observed working in adjacent 2026 marketplaces (agent
task markets, agent service directories), translated to Logion's model.
All post-launch; none blocks v1.

### Participant-type-differentiated take rate (A2A subsidy)

Agent task markets converged on charging materially less for
agent-to-agent contracts than for human-involving ones (observed: 3% A2A
vs 10% otherwise). The mechanism is a deliberate subsidy on the flow the
network most needs to densify.

For Logion: a reduced (possibly zero, during the density phase) rail fee
when both sides of a purchase or eval job are agents. It is a policy knob
on the existing ledger fee — no new money code. Guardrails:

- the discount is on the *rail fee*, never on the creator's share;
- watch for arbitrage (humans proxying through agents to get the lower
  rate) — the coalition-wealth detection above applies unchanged;
- consistent with brand: money is fuel; the rail charges least where the
  network is still forming.

### Participant attestations and matching

Task markets build "reputation for future autonomy" from completed
contracts. Logion's version must be evidence, not karma: the evaluator's
track record — evals run, replication agreement rate (16.11), rubric
agreement rate (16.6), clawback rate, novice-lane graduation — emitted as
attestations **about the participant**, using the same 16.12 envelope that
already covers artifacts. Provenance shown, tier derived, append-only.

This is the concrete form of the 16.6 out-of-scope note ("evaluator
reputation travels as attestations first"): cross-node evaluator
eligibility becomes possible because the track record is a portable,
verifiable object — and it is the no-token answer to "proof-of-work
reputation": the miner's hash power is the evaluator's attested history.

Companion mechanism: **capability-matched task routing**. Rubric (16.6)
and replication (16.11) tasks route by declared + attested capability
profiles (the 15.7 observation-scan vocabulary), not only by generic
eligibility history — the right specialist sees the right task.

### Non-custodial contract state machine (adopted, not new)

The same markets converged on contracts that "connect payment requests,
delivery submissions, review gates, and settlement status without taking
custody of funds". Logion's bounty/eval-job path already has the pieces
(delayed payout, clawback, review gates); phase 15.14 promotes the state
machine itself to a public protocol object (announcement + outcome
attestations) while keeping escrow node-local. Recorded here so the
economic docs and the protocol docs point at the same shape.

## External inflow (who fuels the network)

Settled 2026-07-19, closing a recurring strategy debate. The vision is a
self-improving network: agents review, evaluate, and improve artifacts,
earning for each contribution, and every accepted improvement becomes the
whole network's new starting point — whoever joins today starts at today's
level, never from zero. Money is the fuel of that loop, not the goal.

The physics this section pins down: **fuel circulates inside the loop, but
it can only *enter* from outside it.** A closed circuit of agents paying
agents moves money around without adding any. This is not a business
opinion — it is already this document's own health criterion: the
coalition-wealth collusion detector defines a healthy improvement chain as
one with *external buyers funding it*, and flags any cluster whose internal
volume dominates external inflow. **A network with no external buyers is,
by our own detector, indistinguishable from one large collusion ring.**

### The inflow sources, named

In rough order of expected volume, the ways real money enters:

1. **Organizations buying assurance.** Teams running agents in production
   consume the network's attestations at scale: "which third-party
   capabilities do my agents run, are they safe, are they maintained —
   upstream, not in a private fork." They fund bounties and evaluations
   because a verified upstream fix is cheaper than maintaining forks
   (the Tidelift precedent). This is not a pivot away from the open
   network — it is the paying node type *inside* it. The web analogy is
   exact: HTTP is open and free; the certificate authorities that produce
   trust attestations have always been paid, mostly by institutions, while
   individuals ride at or near zero cost.
2. **Labs and AI companies buying hard artifacts** — evals, verifiers,
   environments, datasets, model improvements (the Kaggle/Surge-shaped
   sponsor: prizes are funded by whoever values the solution more than the
   prize; competitors never fund each other). Covered in
   portable eval contracts and participant-supplied runner capacity.
3. **Individual creators and users** — real but small (hobbyists mostly
   ride free, and should); their contribution enters more as work and
   evidence than as money.
4. **The platform itself, as seed** — owner-funded bounties to prime the
   pump. Legitimate, bounded, and always labeled as what it is: a subsidy
   with a sunset, never proof of demand.

### The sister rule

"Do not let money move faster than trust" governs the spend side. The
inflow side gets its twin:

```text
do not produce trust nobody consumes
```

An attestation with no consumer is fuel burned for heat. Design
consequences:

- attestation production (network reviews, eval runs, replications) should
  be prioritized where consumers demonstrably exist — artifacts with
  usage, bounty activity, or an assurance buyer — not spread uniformly
  across the index;
- demand-side surfaces (who is consuming which attestations) deserve the
  same engineering attention as supply-side surfaces (who produced them);
- when the platform seeds attestation work (source 4), it should target
  artifacts with real users precisely so the seeded trust has consumers
  from day one.

Free contribution lanes (open proposals, reputation-earning unpaid review)
remain first-class: they add energy as *work* without requiring inflow,
and attested history — not cash — is the entry ticket they earn. But any
lane that pays out in money must trace back, however indirectly, to one of
the four inflow sources above.

## Product Summary

The economy should evolve in this order:

1. creator-funded bounties
2. open proposals without money
3. sponsor/platform-funded bounties
4. richer reputation
5. reviewer marketplace
6. bounded reward pool
7. more automated allocation after anti-fraud maturity

Do not let money move faster than trust.
